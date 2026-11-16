from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from bobby_hedgefund.archive import sources
from bobby_hedgefund.archive.fetch import Fetcher
from bobby_hedgefund.archive.sources import FileGroup, FileSource, SourceError
from bobby_hedgefund.archive.store import Archive


def manifest(root: Path) -> list[dict]:
    return [json.loads(x) for x in (root / "manifest.jsonl").read_text().splitlines()]


def studies(n: int) -> list[dict]:
    return [{"protocolSection": {"identificationModule": {"nctId": f"NCT{i:08d}"}}} for i in range(n)]


# -- plain files --------------------------------------------------------------------------------------------------


def group(site, *files: FileSource) -> FileGroup:
    return FileGroup(
        "demo",
        tuple(FileSource(f.name, site.base + f.url, f.starts_with, f.min_bytes, f.compress) for f in files),
        7.0,
    )


def test_file_group_stores_files_and_pauses_between_requests(site, fetcher: Fetcher, waits, tmp_path: Path) -> None:
    site.add("/a", {"body": b"Symbol|rest of the file"})
    site.add("/b", {"body": b'  {"meta": 1}'})
    g = group(site, FileSource("a.txt", "/a", (b"Symbol|",), 10), FileSource("b.json", "/b", (b"{", b"["), 5, False))
    with Archive(tmp_path) as archive:
        assert sources.run_file_group(archive, fetcher, g, "r1") == {"stored": 2, "unchanged": 0}
        assert sources.run_file_group(archive, fetcher, g, "r2") == {"stored": 0, "unchanged": 2}
        first = manifest(tmp_path)[0]
        assert archive.read(first) == b"Symbol|rest of the file"
        assert archive.verify().ok
    assert waits == [7.0, 7.0]  # one pause per run, between the two files
    assert first["url"] == site.base + "/a" and first["status"] == 200 and "suspect" not in first


def test_error_page_is_kept_but_flagged_and_reported(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.add("/a", {"body": b"<!DOCTYPE html><html>Page Not Available" + b" " * 100})
    site.add("/b", {"body": b"PK"})
    site.add("/c", {"body": b"Symbol|a good file"})
    g = group(
        site,
        FileSource("a.txt", "/a", (b"Symbol|",), 10),
        FileSource("b.xlsx", "/b", (b"PK",), 1000, False),
        FileSource("c.txt", "/c", (b"Symbol|",), 10),
    )
    with Archive(tmp_path) as archive, pytest.raises(SourceError) as err:
        sources.run_file_group(archive, fetcher, g, "r1")
    assert "a.txt" in str(err.value) and "b.xlsx" in str(err.value) and "c.txt" not in str(err.value)
    rows = manifest(tmp_path)
    assert [("suspect" in r) for r in rows] == [True, True, False]  # all three were saved, the good one too


# -- trial registry -----------------------------------------------------------------------------------------------


def updates(archive: Archive, fetcher: Fetcher, site, run: str, **kw) -> dict:
    return sources.run_ctgov_updates(archive, fetcher, run, api=site.base + "/api/v2", page_size=2, **kw)


def test_updates_fetch_all_pages_and_store_them_as_received(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.studies = studies(5)
    with Archive(tmp_path) as archive:
        summary = updates(archive, fetcher, site, "r1", today=date(2026, 11, 16))
        archive.record_run(sources.CTGOV_UPDATES, "r1", "ok", meta=summary)
        pages = [r for r in archive.records if r.get("source") == sources.CTGOV_UPDATES and r["kind"] == "file"]
        got = [s for p in pages for s in json.loads(archive.read(p))["studies"]]
        assert archive.verify().ok
    assert summary["pages"] == 3 and summary["n_studies"] == 5 and summary["total_count"] == 5
    assert summary["since"] == "2026-11-09"  # first run ever: one week back
    assert got == site.studies
    assert [p["name"] for p in pages] == ["p0001.json", "p0002.json", "p0003.json"]
    assert [p["meta"]["next_page_token"] for p in pages] == ["2", "4", None]
    assert "LastUpdatePostDate]RANGE[2026-11-09,MAX]" in site.exprs[0] and "INDUSTRY" in site.exprs[0]


def test_updates_skip_when_registry_has_no_new_data_and_then_look_back_one_day(site, fetcher, tmp_path: Path) -> None:
    site.studies = studies(3)
    with Archive(tmp_path) as archive:
        first = updates(archive, fetcher, site, "r1", today=date(2026, 11, 16))
        archive.record_run(sources.CTGOV_UPDATES, "r1", "ok", meta=first)
        hits = len(site.hits)
        second = updates(archive, fetcher, site, "r2")
        assert "skipped" in second and len(site.hits) == hits + 1  # only the version was asked
        site.data_timestamp = "2026-11-16T10:00:03"
        third = updates(archive, fetcher, site, "r3")
    assert third["since"] == "2026-11-12"  # the day before the data date of the last good run (2026-11-13)
    assert third["data_timestamp"] == "2026-11-16T10:00:03"


def test_failed_run_does_not_move_the_starting_date(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.studies = studies(3)
    with Archive(tmp_path) as archive:
        first = updates(archive, fetcher, site, "r1", today=date(2026, 11, 16))
        archive.record_run(sources.CTGOV_UPDATES, "r1", "ok", meta=first)
        site.data_timestamp = "2026-11-16T10:00:03"
        site.lie_about_total = 99
        with pytest.raises(SourceError, match="received 3 trial records, but the registry announced 99"):
            updates(archive, fetcher, site, "r2")
        archive.record_run(sources.CTGOV_UPDATES, "r2", "failed", error="count")
        site.lie_about_total = None
        site.data_timestamp = "2026-11-17T10:00:03"
        again = updates(archive, fetcher, site, "r3")
    assert again["since"] == "2026-11-12"  # still counted from the last *good* run


def test_refresh_during_download_fails_the_run(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.studies = studies(3)
    site.stamp_after_pages = "2026-11-16T10:00:03"
    with (
        Archive(tmp_path) as archive,
        pytest.raises(SourceError, match="refreshed its data during the download"),
    ):
        updates(archive, fetcher, site, "r1", today=date(2026, 11, 16))


def test_updates_start_from_the_baseline_when_there_is_one(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.studies = studies(3)
    with Archive(tmp_path) as archive:
        base = sources.run_ctgov_baseline(archive, fetcher, "b1", api=site.base + "/api/v2", page_size=2)
        archive.record_run(sources.CTGOV_BASELINE, "b1", "ok", meta=base)
        assert base["n_studies"] == 3 and site.exprs[0] == sources.CTGOV_INDUSTRY
        summary = updates(archive, fetcher, site, "r1", today=date(2030, 1, 1))
    assert summary["since"] == "2026-11-12"


def test_baseline_can_be_resumed(site, tmp_path: Path, waits) -> None:
    site.studies = studies(7)
    api = site.base + "/api/v2"
    flaky = Fetcher(timeout=5, backoff=(), sleep=waits.append)
    site.lie_about_total = None
    with Archive(tmp_path) as archive:
        # First attempt: the third page fails for good.
        real_get = flaky.get
        calls = {"n": 0}

        def failing_get(url: str):
            if "/studies" in url:
                calls["n"] += 1
                if calls["n"] == 3:
                    raise sources.SourceError("network down")
            return real_get(url)

        flaky.get = failing_get  # type: ignore[method-assign]
        with pytest.raises(SourceError, match="network down"):
            sources.run_ctgov_baseline(archive, flaky, "b1", api=api, page_size=2)
        flaky.get = real_get  # type: ignore[method-assign]
    with Archive(tmp_path) as archive:  # a later process
        summary = sources.run_ctgov_baseline(archive, flaky, "b2", api=api, page_size=2, resume=True)
        pages = [r for r in archive.records if r.get("source") == sources.CTGOV_BASELINE and r["kind"] == "file"]
        got = [s for p in pages for s in json.loads(archive.read(p))["studies"]]
        archive.record_run(sources.CTGOV_BASELINE, "b2", "ok", meta=summary)
        with pytest.raises(SourceError, match="nothing to resume"):
            sources.run_ctgov_baseline(archive, flaky, "b3", api=api, page_size=2, resume=True)
    assert got == site.studies  # every record exactly once
    assert summary["n_studies"] == 7 and summary["pages"] == 4 and summary["batch"] == "b1"
    assert [p["name"] for p in pages] == ["p0001.json", "p0002.json", "p0003.json", "p0004.json"]


def test_baseline_resume_refuses_after_a_registry_refresh(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.studies = studies(5)
    api = site.base + "/api/v2"
    site.lie_about_total = 99  # makes the first attempt fail after all pages
    with Archive(tmp_path) as archive:
        with pytest.raises(SourceError):
            sources.run_ctgov_baseline(archive, fetcher, "b1", api=api, page_size=2)
        with pytest.raises(SourceError, match="nothing to resume"):  # all pages are there; it needs a fresh start
            sources.run_ctgov_baseline(archive, fetcher, "b2", api=api, page_size=2, resume=True)


def test_resume_refuses_when_the_data_changed(site, tmp_path: Path, waits) -> None:
    site.studies = studies(5)
    api = site.base + "/api/v2"
    fetcher = Fetcher(timeout=5, backoff=(), sleep=waits.append)
    real_get = fetcher.get

    def failing_get(url: str):
        if "pageToken" in url:
            raise sources.SourceError("network down")
        return real_get(url)

    with Archive(tmp_path) as archive:
        fetcher.get = failing_get  # type: ignore[method-assign]
        with pytest.raises(SourceError, match="network down"):
            sources.run_ctgov_baseline(archive, fetcher, "b1", api=api, page_size=2)
        fetcher.get = real_get  # type: ignore[method-assign]
        site.data_timestamp = "2026-11-16T10:00:03"
        with pytest.raises(SourceError, match="start a new one"):
            sources.run_ctgov_baseline(archive, fetcher, "b2", api=api, page_size=2, resume=True)


def test_broken_registry_answers(site, fetcher: Fetcher, tmp_path: Path) -> None:
    api = site.base + "/broken"
    site.add("/broken/version", {"body": b'{"apiVersion": "2"}'})
    with Archive(tmp_path) as archive, pytest.raises(SourceError, match="no dataTimestamp"):
        sources.run_ctgov_updates(archive, fetcher, "r1", api=api)
    site.add("/broken/version", {"body": b'{"dataTimestamp": "2026-11-13T10:00:06"}'})
    site.add("/broken/studies", {"body": b"<html>maintenance</html>"})
    with Archive(tmp_path) as archive:
        with pytest.raises(SourceError, match="not the expected JSON"):
            sources.run_ctgov_updates(archive, fetcher, "r2", api=api)
        assert not [r for r in archive.records if r.get("source") == sources.CTGOV_UPDATES]  # junk page not stored

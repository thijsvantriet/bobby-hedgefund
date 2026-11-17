"""Cases found in the independent review of 2026-11-16: things that go wrong halfway."""

from __future__ import annotations

import errno
import gzip
import io
import json
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from bobby_hedgefund.archive import cli, sources, store
from bobby_hedgefund.archive.fetch import Fetcher, FetchError, _gunzip_bounded
from bobby_hedgefund.archive.sources import FileGroup, FileSource, SourceError, _looks_wrong
from bobby_hedgefund.archive.store import Archive, ArchiveError, Busy

WHEN = datetime(2026, 11, 16, 22, 30, 5, tzinfo=UTC)


def manifest(root: Path) -> list[dict]:
    return [json.loads(x) for x in (root / "manifest.jsonl").read_text().splitlines()]


# -- one failing file must not stop the others ---------------------------------------------------------------------


def test_failed_download_does_not_stop_the_other_files_of_the_group(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.add("/gone", {"status": 404})
    site.add("/b", {"body": b"Symbol|file b"})
    site.add("/c", {"body": b"Symbol|file c"})
    files = tuple(
        FileSource(f"{n}.txt", site.base + path, (b"Symbol|",), 5)
        for n, path in (("a", "/gone"), ("b", "/b"), ("c", "/c"))
    )
    with Archive(tmp_path) as archive, pytest.raises(SourceError) as err:
        sources.run_file_group(archive, fetcher, FileGroup("demo", files, 0.0), "r1")
    assert "a.txt: not downloaded" in str(err.value) and "404" in str(err.value)
    assert [r["name"] for r in manifest(tmp_path)] == ["b.txt", "c.txt"]


# -- cut-off files -------------------------------------------------------------------------------------------------


def xlsx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("[Content_Types].xml", "<Types/>" * 200)
        book.writestr("xl/workbook.xml", "<workbook/>" * 200)
    return buffer.getvalue()


def test_cut_off_files_are_flagged() -> None:
    js = FileSource("m.json", "u", (b"{",), 5)
    assert _looks_wrong(b'{"medicines": [1, 2, 3]}', js) is None
    assert "cut off" in str(_looks_wrong(b'{"medicines": [1, 2, 3', js))

    book = FileSource("h.xlsx", "u", (b"PK",), 5, compress=False)
    whole = xlsx_bytes()
    assert _looks_wrong(whole, book) is None
    assert "spreadsheet" in str(_looks_wrong(whole[: len(whole) // 2], book))

    listing = FileSource("n.txt", "u", (b"Symbol|",), 5, last_line=b"File Creation Time:")
    good = b"Symbol|Name\r\nABC|Abc Inc\r\nFile Creation Time: 1116202603:02|||\r\n"
    assert _looks_wrong(good, listing) is None
    assert "cut off" in str(_looks_wrong(good[:25], listing))


def test_cut_off_file_is_kept_flagged_and_reported(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.add("/m", {"body": b'{"medicines": [1, 2, 3'})
    group = FileGroup("demo", (FileSource("m.json", site.base + "/m", (b"{",), 5),), 0.0)
    with Archive(tmp_path) as archive, pytest.raises(SourceError, match="cut off"):
        sources.run_file_group(archive, fetcher, group, "r1")
    assert "suspect" in manifest(tmp_path)[0]


def test_gzip_in_several_parts_and_cut_off_gzip() -> None:
    two_parts = gzip.compress(b"first half, ") + gzip.compress(b"second half")
    assert _gunzip_bounded(two_parts, 1000) == b"first half, second half"
    with pytest.raises(FetchError, match="ended early"):
        _gunzip_bounded(gzip.compress(b"x" * 5000)[:-20], 100_000)
    with pytest.raises(FetchError, match="larger than the limit"):
        _gunzip_bounded(two_parts, 15)
    with pytest.raises(FetchError, match="broken gzip"):
        _gunzip_bounded(gzip.compress(b"ok") + b"trailing junk that is not gzip", 1000)


def test_redirect_to_a_non_web_address_is_refused(site, fetcher: Fetcher) -> None:
    site.add("/away", {"status": 302, "headers": {"Location": "ftp://example.invalid/file"}})
    site.add("/local", {"status": 302, "headers": {"Location": "/target"}})
    site.add("/target", {"body": b"moved here"})
    with pytest.raises(FetchError, match="HTTP 302"):
        fetcher.get(site.base + "/away")
    resp = fetcher.get(site.base + "/local")
    assert resp.body == b"moved here" and resp.final_url == site.base + "/target"


# -- disk full while writing the manifest --------------------------------------------------------------------------


@pytest.fixture
def disk_full_on_manifest(monkeypatch: pytest.MonkeyPatch):
    """After switching on: a manifest write puts half the line on disk and then fails, like a full disk."""
    state = {"on": False}
    real = store._write_all

    def flaky(fd: int, data: bytes) -> None:
        if state["on"] and data.startswith(b'{"v":1'):
            real(fd, data[: len(data) // 2])
            raise OSError(errno.ENOSPC, "No space left on device")
        real(fd, data)

    monkeypatch.setattr(store, "_write_all", flaky)
    return state


def test_disk_full_leaves_no_half_line_in_the_manifest(tmp_path: Path, disk_full_on_manifest) -> None:
    with Archive(tmp_path) as archive:
        archive.store("src", "a.txt", b"aaa", run="r1", when=WHEN)
        before = (tmp_path / "manifest.jsonl").read_bytes()
        disk_full_on_manifest["on"] = True
        with pytest.raises(ArchiveError, match="half-written line was removed"):
            archive.store("src", "b.txt", b"bbb", run="r1", when=WHEN)
        assert (tmp_path / "manifest.jsonl").read_bytes() == before
        disk_full_on_manifest["on"] = False
        archive.store("src", "c.txt", b"ccc", run="r1", when=WHEN)  # space is back: the list is still sound
    with Archive(tmp_path, readonly=True) as archive:
        report = archive.verify()
    assert report.ok, report.problems
    assert len(report.orphans) == 1 and report.orphans[0].endswith("_b.txt")  # saved, but never listed


def test_run_stops_at_once_when_the_archive_cannot_be_written(
    site, tmp_path, monkeypatch, disk_full_on_manifest, capsys
) -> None:
    site.add("/good", {"body": b"Symbol|a good file"})
    groups = tuple(
        FileGroup(name, (FileSource("good.txt", site.base + "/good", (b"Symbol|",), 5),), 0.0)
        for name in ("one", "two")
    )
    monkeypatch.setattr(sources, "FILE_GROUPS", groups)
    monkeypatch.setattr(cli, "make_fetcher", lambda: Fetcher(timeout=5, backoff=(), sleep=lambda s: None))
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    disk_full_on_manifest["on"] = True
    assert cli.main(["run", "--only", "one", "two"]) == 1
    assert "ARCHIVE ERROR" in capsys.readouterr().out
    assert len(site.hits) == 1  # the second source was not even tried
    assert (tmp_path / "data" / "archive" / "manifest.jsonl").read_bytes() == b""


# -- two commands at once ------------------------------------------------------------------------------------------


def test_waiting_for_another_run_to_finish(tmp_path: Path) -> None:
    other = Archive(tmp_path)
    other.__enter__()
    naps: list[float] = []

    def nap(seconds: float) -> None:
        naps.append(seconds)
        if len(naps) == 2:
            other.__exit__(None, None, None)  # the other run finishes while we wait

    with Archive(tmp_path, wait=300, sleep=nap) as archive:
        archive.store("src", "a.txt", b"aaa", run="r1", when=WHEN)
    assert naps == [30.0, 30.0]


def test_waiting_gives_up_after_the_time_limit(tmp_path: Path) -> None:
    naps: list[float] = []
    with Archive(tmp_path), pytest.raises(Busy), Archive(tmp_path, wait=70, sleep=naps.append):
        pass
    assert naps == [30.0, 30.0, 10.0]


# -- checking ------------------------------------------------------------------------------------------------------


def test_verify_notices_when_the_newest_lines_are_gone(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        for i in range(4):
            archive.store("src", f"f{i}.txt", f"body{i}".encode(), run="r1", when=WHEN)
    path = tmp_path / "manifest.jsonl"
    rows = path.read_text().splitlines()
    path.write_text("\n".join(rows[:2]) + "\n")  # an older copy of the list was put back
    with Archive(tmp_path, readonly=True) as archive:
        report = archive.verify()
    assert any("newest lines are gone" in p for p in report.problems)
    assert len(report.orphans) == 2

    path.write_text("\n".join([*rows[:3], rows[3].replace('"r1"', '"rX"')]) + "\n")  # the very last line edited
    with Archive(tmp_path, readonly=True) as archive:
        assert any("differs from the fingerprint noted" in p for p in archive.verify().problems)

    path.write_text("\n".join(rows) + "\n")
    with Archive(tmp_path, readonly=True) as archive:
        assert archive.verify().ok


def test_checking_writes_nothing_even_with_a_half_line(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        archive.store("src", "a.txt", b"aaa", run="r1", when=WHEN)
    with open(tmp_path / "manifest.jsonl", "ab") as fh:
        fh.write(b'{"v":1,"ki')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    with Archive(tmp_path, readonly=True) as archive:
        report = archive.verify()
        with pytest.raises(ArchiveError, match="checking only"):
            archive.store("src", "b.txt", b"bbb", run="r2")
    assert any("incomplete line" in p for p in report.problems)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before
    with pytest.raises(ArchiveError, match="no archive"):
        Archive(tmp_path / "nowhere", readonly=True).__enter__()
    assert not (tmp_path / "nowhere").exists()


def test_identical_download_is_stored_again_when_the_old_file_is_damaged(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        first = archive.store("src", "a.txt", b"same content", run="r1", when=WHEN, compress=True)
        damaged = tmp_path / first["path"]
        damaged.chmod(0o600)
        damaged.write_bytes(b"rubbish")
        again = archive.store("src", "a.txt", b"same content", run="r2")
        assert again["kind"] == "file" and again["path"] != first["path"]
        assert archive.read(again) == b"same content"
        (tmp_path / again["path"]).unlink()
        assert archive.store("src", "a.txt", b"same content", run="r3")["kind"] == "file"  # missing: stored again


def test_extra_fields_cannot_replace_the_archive_own_fields(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        rec = archive.store(
            "src",
            "a.txt",
            b"aaa",
            run="r1",
            when=WHEN,
            info={"kind": "x", "path": "/etc/passwd", "sha256": "0", "url": "u"},
        )
    assert (
        rec["kind"] == "file" and rec["path"].startswith("raw/src/") and len(rec["sha256"]) == 64 and rec["url"] == "u"
    )


# -- trial registry ------------------------------------------------------------------------------------------------


def test_registry_that_never_stops_paging_is_cut_short(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.studies = [{"n": i} for i in range(5)]
    site.endless = True
    with Archive(tmp_path) as archive, pytest.raises(SourceError, match=r"already had|more pages announced"):
        sources.run_ctgov_updates(
            archive, fetcher, "r1", api=site.base + "/api/v2", page_size=2, today=date(2026, 11, 16)
        )
    assert len([h for h in site.hits if "/studies" in h]) <= 3


def test_more_pages_than_announced_fails(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.studies = [{"n": i} for i in range(6)]
    site.lie_about_total = 2
    with Archive(tmp_path) as archive, pytest.raises(SourceError, match="more pages announced"):
        sources.run_ctgov_updates(
            archive, fetcher, "r1", api=site.base + "/api/v2", page_size=2, today=date(2026, 11, 16)
        )
    assert len([h for h in site.hits if "/studies" in h]) == 1


def test_registry_without_any_matching_record_is_a_good_run(site, fetcher: Fetcher, tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        summary = sources.run_ctgov_updates(archive, fetcher, "r1", api=site.base + "/api/v2", today=date(2026, 11, 16))
    assert summary["n_studies"] == 0 and summary["pages"] == 1


def test_skipping_for_too_long_becomes_a_failure(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.studies = [{"n": 1}]
    api = site.base + "/api/v2"
    with Archive(tmp_path) as archive:
        first = sources.run_ctgov_updates(archive, fetcher, "r1", api=api, today=date(2026, 11, 16))
        archive.record_run(sources.CTGOV_UPDATES, "r1", "ok", meta=first)
        now = datetime.now(UTC)
        assert "skipped" in sources.run_ctgov_updates(archive, fetcher, "r2", api=api, now=now + timedelta(days=4))
        with pytest.raises(SourceError, match="no data refresh"):
            sources.run_ctgov_updates(archive, fetcher, "r3", api=api, now=now + timedelta(days=6))


def test_refused_file_gets_a_second_round_after_the_others(site, fetcher: Fetcher, waits, tmp_path: Path) -> None:
    busy = {"status": 429, "body": b"slow down"}
    site.add("/a", busy, busy, busy, {"body": b"Symbol|file a, served again later"})  # 3 tries fail, then fine
    site.add("/b", {"body": b"Symbol|file b is always fine"})
    files = tuple(FileSource(n, site.base + "/" + n[0], (b"Symbol|",), 10) for n in ("a.txt", "b.txt"))
    with Archive(tmp_path) as archive:
        result = sources.run_file_group(archive, fetcher, FileGroup("demo", files, 7.0), "r1")
        assert archive.verify().ok
    assert result == {"stored": 2, "unchanged": 0, "second_try": 1}
    assert site.hits == ["/a", "/a", "/a", "/b", "/a"]
    assert waits == [1.0, 2.0, 7.0, 7.0]  # two retries, the pause before b, the pause before the second round


def test_file_still_refused_in_the_second_round_is_reported_once(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.add("/a", {"status": 429, "body": b"slow down"})
    site.add("/b", {"body": b"Symbol|file b is always fine"})
    files = tuple(FileSource(n, site.base + "/" + n[0], (b"Symbol|",), 10) for n in ("a.txt", "b.txt"))
    with Archive(tmp_path) as archive, pytest.raises(SourceError) as err:
        sources.run_file_group(archive, fetcher, FileGroup("demo", files, 7.0), "r1")
    assert str(err.value).count("a.txt: not downloaded") == 1 and "b.txt" not in str(err.value)
    assert site.hits.count("/a") == 6 and site.hits.count("/b") == 1


def test_patient_group_leaves_a_refused_file_alone_and_comes_back_later(
    site, fetcher: Fetcher, waits, tmp_path: Path
) -> None:
    busy = {"status": 429, "body": b"slow down", "headers": {"Retry-After": "40"}}
    site.add("/a", busy, busy, {"body": b"Symbol|file a, served in the third round"})
    site.add("/b", {"body": b"Symbol|file b is always fine"})
    files = tuple(FileSource(n, site.base + "/" + n[0], (b"Symbol|",), 10) for n in ("a.txt", "b.txt"))
    with Archive(tmp_path) as archive:
        group = FileGroup("demo", files, 7.0, later_rounds=(100.0, 200.0, 400.0))
        result = sources.run_file_group(archive, fetcher, group, "r1")
        assert archive.verify().ok
    assert result == {"stored": 2, "unchanged": 0, "second_try": 1}
    assert site.hits == ["/a", "/b", "/a", "/a"]  # one request per round, no quick retries
    assert waits == [7.0, 100.0, 200.0]  # the third extra round is not needed


def test_patient_group_reports_a_file_refused_in_every_round_once(
    site, fetcher: Fetcher, waits, tmp_path: Path
) -> None:
    site.add("/a", {"status": 429, "body": b"slow down", "headers": {"Retry-After": "40"}})
    site.add("/b", {"status": 429, "body": b"slow down"})
    site.add("/c", {"status": 503}, {"body": b"Symbol|file c after a server error"})
    files = tuple(FileSource(n, site.base + "/" + n[0], (b"Symbol|",), 10) for n in ("a.txt", "b.txt", "c.txt"))
    with Archive(tmp_path) as archive, pytest.raises(SourceError) as err:
        sources.run_file_group(archive, fetcher, FileGroup("demo", files, 7.0, later_rounds=(100.0, 200.0)), "r1")
    text = str(err.value)
    assert text.count("a.txt: not downloaded") == 1 and text.count("b.txt: not downloaded") == 1
    assert "asked to wait 40 s" in text and "c.txt" not in text
    assert site.hits.count("/a") == 3 and site.hits.count("/b") == 3  # first pass plus two rounds
    assert site.hits.count("/c") == 2  # a server error is still retried at once
    assert waits == [7.0, 7.0, 1.0, 100.0, 7.0, 200.0, 7.0]


def test_patient_group_starts_no_round_past_its_time_limit(site, fetcher: Fetcher, waits, tmp_path: Path) -> None:
    site.add("/a", {"status": 429, "body": b"slow down"})
    files = (FileSource("a.txt", site.base + "/a", (b"Symbol|",), 10),)
    group = FileGroup("demo", files, 7.0, later_rounds=(100.0, 200.0, 400.0), time_limit=1000.0)
    ticks = iter([0.0, 50.0, 900.0])  # the start, before round 1 (50 + 100 fits), before round 2 (900 + 200 does not)
    with Archive(tmp_path) as archive, pytest.raises(SourceError, match=r"a\.txt: not downloaded"):
        sources.run_file_group(archive, fetcher, group, "r1", clock=lambda: next(ticks))
    assert site.hits == ["/a", "/a"] and waits == [100.0]


def test_patient_group_with_nothing_refused_does_not_wait(site, fetcher: Fetcher, waits, tmp_path: Path) -> None:
    site.add("/a", {"body": b"Symbol|file a is fine"})
    files = (FileSource("a.txt", site.base + "/a", (b"Symbol|",), 10),)
    with Archive(tmp_path) as archive:
        group = FileGroup("demo", files, 7.0, later_rounds=(100.0, 200.0), time_limit=1000.0)
        assert sources.run_file_group(archive, fetcher, group, "r1") == {"stored": 1, "unchanged": 0}
    assert site.hits == ["/a"] and waits == []


def test_suspect_file_in_a_later_round_is_kept_and_reported_once(site, fetcher: Fetcher, tmp_path: Path) -> None:
    site.add("/a", {"status": 429, "body": b"slow down"}, {"body": b"<html>an error page, long enough</html>"})
    files = (FileSource("a.txt", site.base + "/a", (b"Symbol|",), 10),)
    with Archive(tmp_path) as archive, pytest.raises(SourceError) as err:
        sources.run_file_group(archive, fetcher, FileGroup("demo", files, 7.0, later_rounds=(100.0, 200.0)), "r1")
    assert str(err.value).count("a.txt") == 1 and "does not start like" in str(err.value)
    assert site.hits == ["/a", "/a"]  # stored as suspect in round 1, not asked for again


def test_the_ema_group_is_patient_and_fits_the_job_time_limit() -> None:
    ema = next(g for g in sources.FILE_GROUPS if g.source == "ema")
    assert ema.later_rounds and min(ema.later_rounds) >= 600
    assert 0 < ema.time_limit <= 4 * 3600


def _three_lines(root: Path) -> tuple[Path, Path]:
    with Archive(root) as archive:
        for i in range(3):
            archive.store("src", f"f{i}.txt", f"body{i}".encode(), run="r1")
    return root / "manifest.jsonl", root / "manifest.head"


def test_run_refuses_to_write_when_the_newest_manifest_lines_are_gone(tmp_path: Path) -> None:
    manifest, head = _three_lines(tmp_path)
    note = head.read_bytes()
    shorter = b"".join(manifest.read_bytes().splitlines(keepends=True)[:2])  # an older copy was put back
    manifest.write_bytes(shorter)
    with pytest.raises(ArchiveError, match="newest lines are gone"), Archive(tmp_path):
        pass
    assert manifest.read_bytes() == shorter and head.read_bytes() == note  # nothing written, the evidence stays
    with Archive(tmp_path, readonly=True) as archive:  # looking is still possible, and it reports the loss
        assert any("newest lines are gone" in p for p in archive.verify().problems)


def test_run_refuses_to_write_when_the_noted_line_was_replaced(tmp_path: Path) -> None:
    manifest, _head = _three_lines(tmp_path)
    rows = manifest.read_bytes().splitlines(keepends=True)
    manifest.write_bytes(b"".join([*rows[:2], rows[2].replace(b'"r1"', b'"rX"')]))
    with pytest.raises(ArchiveError, match="differs from the fingerprint"), Archive(tmp_path):
        pass


def test_manifest_longer_than_the_note_is_accepted(tmp_path: Path) -> None:
    _, head = _three_lines(tmp_path)
    note = head.read_bytes()
    with Archive(tmp_path) as archive:
        archive.store("src", "later.txt", b"later", run="r2")
    head.write_bytes(note)  # as if that run was killed before it could update the note
    with Archive(tmp_path) as archive:
        archive.store("src", "more.txt", b"more", run="r3")
        assert archive.verify().ok
    assert json.loads(head.read_bytes())["lines"] == 5


def test_damaged_spreadsheet_or_deep_json_is_flagged_not_a_crash() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("sheet.xml", b"<x>" + b"abcdefgh" * 4000 + b"</x>")
    whole = bytearray(buf.getvalue())
    whole[60:120] = b"\xff" * 60  # damage inside the packed data; the file still opens as a zip
    assert _looks_wrong(bytes(whole), FileSource("a.xlsx", "u", (b"PK",), 10, False))
    deep = b"[" * 200_000 + b"]" * 200_000
    assert _looks_wrong(deep, FileSource("a.json", "u", (b"[",), 10))

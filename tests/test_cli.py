from __future__ import annotations

import json
from pathlib import Path

import pytest

from bobby_hedgefund.archive import cli, sources
from bobby_hedgefund.archive.fetch import Fetcher
from bobby_hedgefund.archive.sources import FileGroup, FileSource
from bobby_hedgefund.archive.store import Archive


@pytest.fixture
def setup(site, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, waits):
    site.add("/good", {"body": b"Symbol|a good file"})
    site.add("/bad", {"status": 404})
    groups = (
        FileGroup("good-files", (FileSource("good.txt", site.base + "/good", (b"Symbol|",), 5),), 0.0),
        FileGroup("bad-files", (FileSource("bad.txt", site.base + "/bad", (b"Symbol|",), 5),), 0.0),
    )
    site.studies = [{"n": i} for i in range(3)]
    monkeypatch.setattr(sources, "FILE_GROUPS", groups)
    monkeypatch.setattr(sources, "CTGOV_API", site.base + "/api/v2")
    monkeypatch.setattr(cli, "make_fetcher", lambda: Fetcher(timeout=5, backoff=(), sleep=waits.append))
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data" / "archive"


def manifest(root: Path) -> list[dict]:
    return [json.loads(x) for x in (root / "manifest.jsonl").read_text().splitlines()]


def test_run_keeps_going_after_one_source_fails_and_reports_it(setup: Path, capsys) -> None:
    assert cli.main(["run"]) == 1  # one source failed: the timer's alert must fire
    runs = {r["source"]: r for r in manifest(setup) if r["kind"] == "run"}
    assert runs["good-files"]["status"] == "ok"
    assert runs["bad-files"]["status"] == "failed" and "404" in runs["bad-files"]["error"]
    assert runs["ctgov-updates"]["status"] == "ok" and runs["ctgov-updates"]["meta"]["n_studies"] == 3
    out = capsys.readouterr().out
    assert "FAILED  bad-files" in out and "ok      good-files" in out


def test_run_only_selected_sources(setup: Path) -> None:
    assert cli.main(["run", "--only", "good-files"]) == 0
    assert [r["source"] for r in manifest(setup) if r["kind"] == "run"] == ["good-files"]
    assert cli.main(["run", "--only", "nonsense"]) == 2


def test_second_run_notes_unchanged_and_skips_registry(setup: Path) -> None:
    assert cli.main(["run", "--only", "good-files", "ctgov-updates"]) == 0
    assert cli.main(["run", "--only", "good-files", "ctgov-updates"]) == 0
    rows = manifest(setup)
    assert [r["kind"] for r in rows if r.get("name") == "good.txt"] == ["file", "unchanged"]
    assert [r["status"] for r in rows if r["kind"] == "run" and r["source"] == "ctgov-updates"] == [
        "ok",
        "skip",
    ]


def test_verify_and_status(setup: Path, capsys) -> None:
    assert cli.main(["status"]) == 0 and "no runs yet" in capsys.readouterr().out
    assert cli.main(["run", "--only", "good-files"]) == 0
    assert cli.main(["verify"]) == 0
    assert cli.main(["verify", "--quick"]) == 0
    assert "verify: OK" in capsys.readouterr().out
    assert cli.main(["status"]) == 0
    assert "good-files" in capsys.readouterr().out
    stored = next(setup.rglob("*_good.txt.xz"))
    stored.chmod(0o600)
    stored.write_bytes(b"tampered")
    assert cli.main(["verify"]) == 1
    assert "PROBLEM" in capsys.readouterr().out


def test_run_while_another_is_busy_fails_loudly(setup: Path, capsys) -> None:
    with Archive(setup):
        assert cli.main(["run", "--wait", "0"]) == 1  # today's files were not saved: the alert must fire
    assert "NOT DONE" in capsys.readouterr().out
    assert not (setup / "manifest.jsonl").exists()


def test_baseline_command(setup: Path) -> None:
    assert cli.main(["baseline"]) == 0
    runs = [r for r in manifest(setup) if r["kind"] == "run"]
    assert runs[-1]["source"] == "ctgov-baseline" and runs[-1]["status"] == "ok"
    assert cli.main(["baseline", "--resume"]) == 1  # nothing to resume is reported as a failure, not hidden


def test_default_location_is_outside_the_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOBBY_DATA_DIR", raising=False)
    assert cli.archive_root() == Path.home() / "bobby-hedgefund-data" / "archive"
    assert cli.make_fetcher().user_agent == "public-data-archiver/0.1"

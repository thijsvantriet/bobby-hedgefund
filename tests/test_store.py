from __future__ import annotations

import json
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bobby_hedgefund.archive.store import GENESIS, Archive, ArchiveError, Busy, read_records, sha256_hex

WHEN = datetime(2026, 11, 16, 22, 30, 5, tzinfo=UTC)


def lines(root: Path) -> list[dict]:
    return [json.loads(x) for x in (root / "manifest.jsonl").read_text().splitlines()]


def test_store_writes_file_and_manifest_line(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        rec = archive.store("src", "a.txt", b"hello", run="r1", when=WHEN, info={"url": "http://x/a"})
        assert archive.read(rec) == b"hello"
    assert rec["path"] == "raw/src/2026/11/16/223005Z_a.txt"
    stored = tmp_path / rec["path"]
    assert stored.read_bytes() == b"hello"
    assert stat.S_IMODE(stored.stat().st_mode) == 0o400
    (only,) = lines(tmp_path)
    assert only["kind"] == "file" and only["sha256"] == sha256_hex(b"hello") and only["bytes"] == 5
    assert only["prev"] == GENESIS and only["url"] == "http://x/a"
    assert not list(tmp_path.rglob(".tmp-*"))


def test_compressed_file_round_trips(tmp_path: Path) -> None:
    body = b'{"a": 1}' * 5000
    with Archive(tmp_path) as archive:
        rec = archive.store("src", "big.json", body, run="r1", when=WHEN, compress=True)
        assert rec["path"].endswith("big.json.xz") and rec["stored_bytes"] < len(body)
        assert archive.read(rec) == body
        assert archive.verify().ok


def test_existing_file_is_never_overwritten(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        first = archive.store("src", "a.txt", b"one", run="r1", when=WHEN)
        second = archive.store("src", "a.txt", b"two", run="r1", when=WHEN)  # same second, same name
        assert first["path"] != second["path"]
        assert archive.read(first) == b"one" and archive.read(second) == b"two"
        assert archive.verify().ok


def test_identical_content_is_noted_not_stored_again(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        first = archive.store("src", "a.txt", b"same", run="r1", when=WHEN)
        again = archive.store("src", "a.txt", b"same", run="r2")
        assert again["kind"] == "unchanged" and again["path"] == first["path"]
        changed = archive.store("src", "a.txt", b"different", run="r3")
        assert changed["kind"] == "file"
        back = archive.store("src", "a.txt", b"same", run="r4")  # differs from the last one: stored again
        assert back["kind"] == "file"
        assert archive.verify().ok
    assert len([p for p in (tmp_path / "raw").rglob("*") if p.is_file()]) == 3


def test_dedup_survives_reopening_and_can_be_switched_off(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        archive.store("src", "a.txt", b"same", run="r1", when=WHEN)
    with Archive(tmp_path) as archive:
        assert archive.store("src", "a.txt", b"same", run="r2")["kind"] == "unchanged"
        assert archive.store("src", "a.txt", b"same", run="r3", dedup=False)["kind"] == "file"


@pytest.mark.parametrize("bad", ["../x", "a/b", ".hidden", "", "UPPER", "a..b", "x" * 200])
def test_unsafe_names_are_refused(tmp_path: Path, bad: str) -> None:
    with Archive(tmp_path) as archive:
        with pytest.raises(ArchiveError):
            archive.store("src", bad, b"x", run="r1")
        with pytest.raises(ArchiveError):
            archive.store(bad, "a.txt", b"x", run="r1")
    assert not (tmp_path / "manifest.jsonl").exists()
    assert not (tmp_path / "raw").exists()


def test_read_refuses_paths_outside_the_archive(tmp_path: Path) -> None:
    (tmp_path.parent / "secret.txt").write_text("secret")
    with Archive(tmp_path) as archive:
        for path in ("../secret.txt", "/etc/hostname", "raw/../../secret.txt", "other/file"):
            with pytest.raises(ArchiveError):
                archive.read({"path": path})


def test_only_one_run_at_a_time(tmp_path: Path) -> None:
    with Archive(tmp_path), pytest.raises(Busy), Archive(tmp_path):
        pass
    with Archive(tmp_path):  # the lock is released afterwards
        pass


def test_writing_needs_an_open_archive(tmp_path: Path) -> None:
    with pytest.raises(ArchiveError):
        Archive(tmp_path).store("src", "a.txt", b"x", run="r1")


def test_verify_detects_changed_missing_and_extra_files(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        a = archive.store("src", "a.txt", b"aaa", run="r1", when=WHEN)
        b = archive.store("src", "b.txt", b"bbb", run="r1", when=WHEN, compress=True)
        c = archive.store("src", "c.txt", b"ccc", run="r1", when=WHEN)
        assert archive.verify().ok
        (tmp_path / a["path"]).chmod(0o600)
        (tmp_path / a["path"]).write_bytes(b"aaX")  # same size, other content
        (tmp_path / b["path"]).chmod(0o600)
        (tmp_path / b["path"]).write_bytes(b"not xz at all")
        (tmp_path / c["path"]).unlink()
        (tmp_path / "raw" / "src" / "stray.bin").write_bytes(b"?")
        report = archive.verify()
        quick = archive.verify(quick=True)
    assert len(report.problems) == 3
    assert any("checksum" in p for p in report.problems)
    assert any("missing" in p for p in report.problems)
    assert report.orphans == ["raw/src/stray.bin"]
    assert any("missing" in p for p in quick.problems)  # quick mode still notices missing files and sizes


def test_verify_detects_edited_and_removed_manifest_lines(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        for i in range(4):
            archive.store("src", f"f{i}.txt", f"body{i}".encode(), run="r1", when=WHEN)
    manifest = tmp_path / "manifest.jsonl"
    original = manifest.read_text()
    rows = original.splitlines()

    manifest.write_text("\n".join([rows[0], rows[1].replace('"r1"', '"rX"'), *rows[2:]]) + "\n")
    with Archive(tmp_path) as archive:
        assert any("chain broken" in p for p in archive.verify().problems)

    manifest.write_text("\n".join([rows[0], *rows[2:]]) + "\n")  # a line removed
    with Archive(tmp_path, readonly=True) as archive:  # a writing run refuses a list that became shorter
        assert any("chain broken" in p for p in archive.verify().problems)

    manifest.write_text(original)
    with Archive(tmp_path) as archive:
        assert archive.verify().ok


def test_half_written_last_line_is_set_aside_and_archiving_continues(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        archive.store("src", "a.txt", b"aaa", run="r1", when=WHEN)
    manifest = tmp_path / "manifest.jsonl"
    good = manifest.read_bytes()
    manifest.write_bytes(good + b'{"v":1,"kind":"file","ts":"2026')  # power cut in the middle of a line
    with Archive(tmp_path) as archive:
        archive.store("src", "b.txt", b"bbb", run="r2", when=WHEN)
        report = archive.verify()
    assert report.ok, report.problems
    assert manifest.read_bytes().startswith(good)  # complete lines untouched
    rows = lines(tmp_path)
    assert [r["kind"] for r in rows] == ["file", "repair", "file"]
    torn = tmp_path / rows[1]["torn_file"]
    assert torn.read_bytes() == b'{"v":1,"kind":"file","ts":"2026'
    assert rows[1]["torn_sha256"] == sha256_hex(torn.read_bytes())


def test_manifest_with_only_a_half_line(tmp_path: Path) -> None:
    (tmp_path / "manifest.jsonl").write_bytes(b'{"v":1,"ki')
    with Archive(tmp_path) as archive:
        archive.store("src", "a.txt", b"aaa", run="r1", when=WHEN)
        assert archive.verify().ok
    assert [r["kind"] for r in lines(tmp_path)] == ["repair", "file"]


def test_damaged_line_does_not_stop_new_writes(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        archive.store("src", "a.txt", b"aaa", run="r1", when=WHEN)
    with open(tmp_path / "manifest.jsonl", "ab") as fh:
        fh.write(b"this is not json\n")
    with Archive(tmp_path) as archive:
        archive.store("src", "b.txt", b"bbb", run="r2", when=WHEN)
        report = archive.verify()
    assert report.problems == ["line 2: not valid JSON"]  # reported, and the chain continues after it
    assert len(read_records(tmp_path)) == 2


def test_run_records_and_last_ok_run(tmp_path: Path) -> None:
    with Archive(tmp_path) as archive:
        archive.record_run("src", "r1", "ok", meta={"n": 1})
        archive.record_run("src", "r2", "failed", error="boom " * 300)
        archive.record_run("src", "r3", "skip")
    with Archive(tmp_path) as archive:
        last = archive.last_ok_run("src")
        assert last is not None and last["run"] == "r1"
        assert archive.last_ok_run("other") is None
    assert len(lines(tmp_path)[1]["error"]) == 500


def test_read_records_ignores_a_half_written_tail(tmp_path: Path) -> None:
    assert read_records(tmp_path) == []
    with Archive(tmp_path) as archive:
        archive.store("src", "a.txt", b"aaa", run="r1", when=WHEN)
    with open(tmp_path / "manifest.jsonl", "ab") as fh:
        fh.write(b'{"v":1,"kind"')
    before = (tmp_path / "manifest.jsonl").read_bytes()
    assert [r["kind"] for r in read_records(tmp_path)] == ["file"]
    assert (tmp_path / "manifest.jsonl").read_bytes() == before  # reading changes nothing

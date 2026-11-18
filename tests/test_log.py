from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest
from logkit import ACME, DAY1, DAY2, H, clock, day_file, decision, fill, forecast, lines, make_log, session_start

from bobby_hedgefund import paths
from bobby_hedgefund.log import canon, cli, forecasts, records, seal
from bobby_hedgefund.log.seal import Sealed
from bobby_hedgefund.log.store import DELETED, START, Log, LogError, fingerprint, read_head
from bobby_hedgefund.prices import purge


def filled(tmp_path: Path, mode: str = "pilot") -> Log:
    log = make_log(tmp_path, mode)
    with log.writer(DAY1, clock()) as w:
        w.add("session_start", session_start())
        w.add("decision", decision())
        w.add("fill", fill())
    return log


# ---------------------------------------------------------------- the fixed way of writing


def test_a_line_is_written_one_way_only() -> None:
    assert canon.encode({"b": 1, "a": "é", "c": [True, None]}) == b'{"a":"\\u00e9","b":1,"c":[true,null]}'
    assert canon.decode(b'{"a":1,"b":2}') == {"a": 1, "b": 2}
    for other in (b'{"b":2,"a":1}', b'{"a": 1,"b":2}', b'{"a":1.0}', b'{"a":1,"a":1}', b"not json"):
        with pytest.raises(canon.CanonError):
            canon.decode(other)


def test_a_number_with_a_decimal_point_is_refused_wherever_it_hides() -> None:
    with pytest.raises(canon.CanonError, match="record/a/1/b"):
        canon.encode({"a": [1, {"b": 0.5}]})
    with pytest.raises(canon.CanonError):
        canon.encode({"a": float("nan")})
    with pytest.raises(canon.CanonError):
        canon.encode({1: "a"})


def test_percentages_and_prices_convert_exactly_and_the_same_way_everywhere() -> None:
    assert canon.pct_fraction("2.5%") == Fraction(1, 40) and canon.pct_fraction("100%") == 1
    assert canon.format_pct(Fraction(1, 40)) == "2.5%" and canon.format_pct(Fraction(3, 100)) == "3%"
    assert canon.format_pct(Fraction(1, 3)) == "33.33%"  # rounded down: a limit is never passed by rounding
    assert canon.format_pct(Fraction(49999, 1000000)) == "4.99%"
    for bad in ("3", "03%", "3.123%", "-1%", "3 %", 3):
        assert not canon.is_pct(bad)
    assert canon.decimal_fraction("12.34") == Fraction(617, 50)
    assert canon.format_decimal(12.34) == "12.34" and canon.format_decimal(Fraction(1, 3)) == "0.333333"
    assert canon.format_decimal(7.0) == "7"
    with pytest.raises(canon.CanonError):
        canon.decimal_fraction("1e3")


def test_the_published_example_of_a_sealed_fingerprint() -> None:
    by_hand = hashlib.sha256(b"0" * 64 + b"\n" + b'"12.34"').hexdigest()
    assert seal.seal_fingerprint(seal.EXAMPLE_SALT, seal.EXAMPLE_CONTENT) == by_hand == seal.EXAMPLE


# ---------------------------------------------------------------- the chain


def test_the_fingerprint_rule_of_record_0004_across_day_files(tmp_path: Path) -> None:
    log = filled(tmp_path)
    with log.writer(DAY2, clock(10)) as w:
        w.add("stop_file", {"state": "on", "noticed": "2027-02-04T07:00:00Z"})
    entries = log.entries()
    assert [e.seq for e in entries] == [1, 2, 3, 4] and entries[3].file == "log/2027/02/2027-02-04.jsonl"
    prev = START["pilot"]
    for entry, raw in zip(entries, lines(log) + lines(log, DAY2), strict=True):
        assert entry.record["prev"] == prev
        prev = hashlib.sha256(prev.encode() + b"\n" + raw.rstrip(b"\n")).hexdigest()
        assert entry.sha256 == prev == fingerprint(entry.record["prev"], raw.rstrip(b"\n"))
    assert read_head(log.staging) == {"records": 4, "sha256": prev, "v": 1}
    assert START["pilot"] != START["live"]
    assert not log.verify().problems


def test_a_record_carries_its_number_kind_time_and_mode(tmp_path: Path) -> None:
    log = filled(tmp_path)
    first = log.entries()[0].record
    assert (first["v"], first["seq"], first["kind"], first["mode"]) == (1, 1, "session_start", "pilot")
    assert first["time"] == "2027-02-03T09:00:00Z"


@pytest.mark.parametrize("damage", ["changed", "removed", "reordered", "inserted", "half line", "extra file"])
def test_verify_catches_a_changed_removed_or_reordered_line(tmp_path: Path, damage: str) -> None:
    log = filled(tmp_path)
    path = day_file(log)
    raw = lines(log)
    if damage == "changed":
        path.write_bytes(raw[0] + raw[1].replace(b'"3%"', b'"4%"') + raw[2])
    elif damage == "removed":
        path.write_bytes(raw[0] + raw[2])
    elif damage == "reordered":
        path.write_bytes(raw[1] + raw[0] + raw[2])
    elif damage == "inserted":
        path.write_bytes(raw[0] + raw[0] + raw[1] + raw[2])
    elif damage == "half line":
        path.write_bytes(b"".join(raw)[:-5])
    else:
        (path.parent / "notes.txt").write_text("x")
    report = log.verify()
    assert report.problems and cli_verify(tmp_path) == 1
    with pytest.raises(LogError), log.writer(DAY1):  # and nothing can be added to a damaged log
        pass


def cli_verify(tmp_path: Path) -> int:
    return cli.main(["verify", "--dir", str(tmp_path / "staging")])


def test_a_log_that_lost_its_newest_lines_is_caught_by_head(tmp_path: Path) -> None:
    log = filled(tmp_path)
    raw = lines(log)
    day_file(log).write_bytes(raw[0] + raw[1])  # the chain itself is still unbroken
    assert log.entries()[-1].seq == 2
    report = log.verify()
    assert any("lost its newest lines" in p for p in report.problems)
    with pytest.raises(LogError, match="lost its newest lines"), log.writer(DAY1):
        pass


def test_head_one_behind_after_a_crash_is_harmless_and_repaired_by_the_next_writer(tmp_path: Path) -> None:
    log = filled(tmp_path)
    entries = log.entries()
    (log.staging / "HEAD").write_bytes(canon.encode({"records": 2, "sha256": entries[1].sha256, "v": 1}) + b"\n")
    report = log.verify()
    assert not report.problems and any("one record behind" in n for n in report.notes)
    with log.writer(DAY1, clock()) as w:
        assert "one record behind" in w.note
        w.add("stop_file", {"state": "off", "noticed": "2027-02-03T09:30:00Z"})
    assert read_head(log.staging)["records"] == 4 and not log.verify().notes


def test_head_further_behind_wrong_or_missing_is_damage(tmp_path: Path, capsys) -> None:
    log = filled(tmp_path)
    entries = log.entries()
    head = log.staging / "HEAD"
    head.write_bytes(canon.encode({"records": 1, "sha256": entries[0].sha256, "v": 1}) + b"\n")
    assert any("2 records behind" in p for p in log.verify().problems)
    head.write_bytes(canon.encode({"records": 3, "sha256": H, "v": 1}) + b"\n")
    assert any("does not match" in p for p in log.verify().problems)
    head.unlink()
    assert any("HEAD is missing" in p for p in log.verify().problems)


def test_head_can_be_written_anew_by_hand_from_an_unbroken_chain(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    log = Log.for_mode("pilot")
    with log.writer(DAY1, clock()) as w:
        w.add("session_start", session_start())
        w.add("decision", decision("nothing"))
    (log.staging / "HEAD").unlink()
    assert cli.main(["verify"]) == 1
    assert cli.main(["head", "--rewrite"]) == 0 and cli.main(["verify"]) == 0
    assert "ok: one unbroken chain" in capsys.readouterr().out


def test_the_day_cannot_go_backwards_and_two_writers_cannot_interleave(tmp_path: Path) -> None:
    log = filled(tmp_path)
    with log.writer(DAY2, clock()) as w:
        w.add("stop_file", {"state": "on", "noticed": "2027-02-04T07:00:00Z"})
        with pytest.raises(LogError, match="another program"), log.writer(DAY2):
            pass
    with pytest.raises(LogError, match="cannot follow"), log.writer(DAY1):
        pass


def test_a_pilot_record_can_never_be_placed_in_the_real_log(tmp_path: Path) -> None:
    pilot = filled(tmp_path / "p", "pilot")
    live = make_log(tmp_path / "l", "live")
    target = day_file(live)
    target.parent.mkdir(parents=True)
    target.write_bytes(day_file(pilot).read_bytes())
    with pytest.raises(LogError, match="mode 'pilot' in the live log"):
        live.entries()
    target.write_bytes(day_file(pilot).read_bytes().replace(b'"mode":"pilot"', b'"mode":"live"'))
    with pytest.raises(LogError, match="chain of fingerprints breaks"):  # the starting value differs too
        live.entries()


def test_live_mode_stays_off_until_the_owner_makes_the_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path))
    with pytest.raises(paths.ModeError, match="switched off"):
        Log.for_mode("live")
    assert cli.main(["verify", "--live"]) == 1 and "switched off" in capsys.readouterr().out
    assert paths.mode_root("pilot") == tmp_path / "pilot"
    (tmp_path / "LIVE").write_text("go\n")
    assert Log.for_mode("live").staging == tmp_path / "staging"


# ---------------------------------------------------------------- forms


def test_a_record_that_is_not_in_its_form_is_not_written(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    bad = [
        ("mystery", {}),
        ("stop_file", {"state": "maybe", "noticed": "2027-02-03T09:30:00Z"}),
        ("stop_file", {"state": "on", "noticed": "yesterday"}),
        ("stop_file", {"state": "on", "noticed": "2027-02-03T09:30:00Z", "extra": 1}),
        ("stop_file", {"state": "on", "noticed": "2027-02-03T09:30:00Z", "seq": 7}),
        ("decision", decision(size="3")),
        ("decision", decision(size=None)),
        ("decision", decision(size="0%")),
        ("decision", decision(fill_rule="at a price we like")),
        ("decision", {k: v for k, v in decision().items() if k != "thesis"}),
        ("decision", {k: v for k, v in decision("sell").items() if k != "reason"}),
        ("decision", {**decision("nothing"), "company": dict(ACME)}),
        ("forecast", forecast("101%")),
        ("forecast", {**forecast(), "by_date": "2027-02-30"}),
        ("fill", {**fill(), "details": {"shares": 100, "price": "12.34"}}),  # must be sealed
        ("session_start", {**session_start(), "inputs_sha256": "abc"}),
    ]
    with log.writer(DAY1, clock()) as w:
        for kind, body in bad:
            with pytest.raises(LogError):
                w.add(kind, body)
        with pytest.raises(LogError):
            w.add("refusal", {"when": "2027-02-03T09:30:00Z", "reason": "x", "note": 0.5})
    assert log.entries() == [] and not (log.staging / "log").exists()


def test_the_fields_that_say_what_was_decided_can_never_be_sealed(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    with log.writer(DAY1, clock()) as w:
        for name, value in (("fund", "careful"), ("action", "buy"), ("size_pct", "3%"), ("fill_rule", "x")):
            with pytest.raises(LogError):
                w.add("decision", decision(**{name: Sealed(value, "other")}))
        with pytest.raises(LogError):
            w.add("decision", decision(company=Sealed(dict(ACME), "other")))
        w.add("decision", decision())
        # Nor can a caller hand in something that already looks sealed: its content would exist nowhere.
        with pytest.raises(LogError, match="only be made by the log writer"):
            w.add("fill", {**fill(1), "details": {"sealed": H, "why": "price"}})
    assert len(log.entries()) == 1


def test_sell_reduce_and_nothing_have_their_own_forms() -> None:
    records.validate("decision", decision("sell", None))  # selling the whole position: no size
    records.validate("decision", decision("reduce", "2%"))
    records.validate("decision", decision("nothing"))
    dice = {k: v for k, v in decision().items() if k != "thesis"} | {"fund": "dice", "draw": 3}
    records.validate("decision", dice)  # a fund without AI states no thesis


# ---------------------------------------------------------------- sealed content


def test_sealed_content_is_in_the_private_file_only(tmp_path: Path) -> None:
    log = filled(tmp_path)
    public = b"".join(lines(log))
    assert b"12.34" not in public and b"123400" not in public and b'"1.8"' not in public
    entry = log.entries()[2]
    assert set(entry.record["details"]) == {"sealed", "why"} and entry.record["details"]["why"] == "price"
    assert log.opened(entry)["details"]["price"] == "12.34"
    assert log.opened(log.entries()[1])["thesis"]["numbers"][1]["value"] == "1.8"
    private = json.loads(log.private_path(3).read_bytes())
    assert private["seq"] == 3 and set(private["fields"]) == {"/details"}
    assert (log.private_path(3).stat().st_mode & 0o777) == 0o400
    assert not log.private_path(1).exists()  # a record without sealed content has no private file
    report = log.verify()
    assert (report.sealed, report.sealed_checked, report.problems) == (2, 2, [])


def test_the_same_content_sealed_twice_gives_two_different_fingerprints(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    with log.writer(DAY1, clock()) as w:
        w.add("decision", decision())
        a = w.add("fill", fill(1))
        b = w.add("fill", fill(1))
    assert a.record["details"]["sealed"] != b.record["details"]["sealed"]


def test_changed_or_missing_private_content_is_damage(tmp_path: Path) -> None:
    log = filled(tmp_path)
    path = log.private_path(3)
    path.chmod(0o600)
    path.write_bytes(path.read_bytes().replace(b"12.34", b"12.35"))
    assert any("does not match its fingerprint" in p for p in log.verify().problems)
    with pytest.raises(LogError, match="does not match"):
        log.opened(log.entries()[2])
    path.unlink()
    assert any("private content of /details is missing" in p for p in log.verify().problems)


def test_a_key_or_address_is_kept_nowhere(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    key = "sk_live_" + "a1B2c3D4" * 4
    with log.writer(DAY1, clock()) as w:
        w.add("stop_file", {"state": "on", "noticed": "2027-02-03T09:30:00Z"})
        entry = w.add("correction", {"ref": 1, "text": f"The key {key} was pasted by mistake."})
    assert entry.record["text"] == "The key [removed] was pasted by mistake."
    assert key.encode() not in log.private_path(2).read_bytes() and key.encode() not in b"".join(lines(log))
    report = log.verify()
    assert (report.sealed_not_kept, report.problems) == (1, [])
    assert log.opened(entry)["removed"][0]["why"] == "secret"  # there is no content to put back


def test_a_private_file_left_by_a_crash_is_set_aside_not_reused(tmp_path: Path) -> None:
    log = filled(tmp_path)
    orphan = log.private_path(4)
    orphan.write_bytes(b'{"fields":{"/details":{"content":"old","salt":"00"}},"kind":"fill","seq":4}\n')
    assert any("belongs to no record" in n for n in log.verify().notes)
    with log.writer(DAY1, clock()) as w:
        w.add("fill", fill())
    report = log.verify()
    assert not report.problems and report.sealed_checked == 3
    assert any("set aside after a crash" in n for n in report.notes)
    assert len(list(log.private.glob("00000004.orphan-*.json"))) == 1  # type: ignore[union-attr]


def test_a_failed_write_leaves_no_half_line(tmp_path: Path, monkeypatch) -> None:
    log = filled(tmp_path)
    before = day_file(log).read_bytes()
    from bobby_hedgefund.log import store

    real = store.os.fsync

    def breaks(fd: int) -> None:
        raise OSError("disk full")

    with log.writer(DAY1, clock()) as w:
        monkeypatch.setattr(store.os, "fsync", breaks)
        with pytest.raises(LogError, match="nothing was added"):
            w.add("stop_file", {"state": "on", "noticed": "2027-02-03T09:30:00Z"})
        monkeypatch.setattr(store.os, "fsync", real)
        assert day_file(log).read_bytes() == before
        w.add("stop_file", {"state": "off", "noticed": "2027-02-03T09:31:00Z"})
    assert day_file(log).read_bytes().startswith(before) and len(log.entries()) == 4
    assert not log.verify().problems


def test_a_failed_first_write_of_a_new_day_leaves_no_empty_file_and_the_log_stays_writable(
    tmp_path: Path, monkeypatch
) -> None:
    log = filled(tmp_path)
    from bobby_hedgefund.log import store

    real = store.os.fsync

    def breaks(fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(store.os, "fsync", breaks)
    with log.writer(DAY2, clock()) as w, pytest.raises(LogError, match="nothing was added"):
        w.add("stop_file", {"state": "on", "noticed": "2027-02-04T09:30:00Z"})
    monkeypatch.setattr(store.os, "fsync", real)
    assert not day_file(log, DAY2).exists() and not log.verify().problems
    # Even a half-written first line that a crash left under its temporary name does not get in the way.
    (day_file(log, DAY2).parent / ".2027-02-04.jsonl-123").write_bytes(b"half")
    with log.writer(DAY2, clock()) as w:
        w.add("stop_file", {"state": "on", "noticed": "2027-02-04T09:30:00Z"})
    assert len(log.entries()) == 4 and not log.verify().problems


def test_once_a_line_is_written_add_never_raises_so_nothing_is_written_twice(tmp_path: Path, monkeypatch) -> None:
    log = filled(tmp_path)
    from bobby_hedgefund.log import store

    real = store._write_head

    def no_head(staging: Path, count: int, sha256: str) -> None:
        raise OSError("disk full")

    with log.writer(DAY1, clock()) as w:
        monkeypatch.setattr(store, "_write_head", no_head)
        entry = w.add("stop_file", {"state": "on", "noticed": "2027-02-03T09:30:00Z"})  # does not raise
        assert entry.seq == 4 and "could not be written" in w.note
        monkeypatch.setattr(store, "_write_head", real)
    assert [e.seq for e in log.entries()] == [1, 2, 3, 4]
    report = log.verify()
    assert not report.problems and any("one record behind" in n for n in report.notes)
    with log.writer(DAY1, clock()) as w:
        assert w.add("stop_file", {"state": "off", "noticed": "2027-02-03T09:40:00Z"}).seq == 5
    assert not log.verify().notes


def test_the_writer_checks_the_text_itself_so_no_caller_can_forget_it(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    body = decision()
    body["thesis"]["risks"] = "The shares fell 40% last month. The rest is fine."
    link = {"n": 1, "source": "x", "summary": "y", "link": "https://example.org/a?token=1"}
    with log.writer(DAY1, clock()) as w:
        entry = w.add("decision", body)
        with pytest.raises(LogError, match="defined by a price"):
            w.add("forecast", {**forecast(), "event": "The share price is above 20 dollars on 1 June"})
        key = "sk_live_" + "a1B2c3D4" * 4
        with pytest.raises(LogError, match="looks like a key or an address"):  # not free text: cannot be cut out
            w.add("session_start", {**session_start(), "universe": {"file": key, "sha256": H}})
        with pytest.raises(LogError, match="plain https link"):
            w.add("forecast", {**forecast(), "sources": [link]})
    assert entry.record["thesis"]["risks"] == "[sealed] The rest is fine."
    assert body["thesis"]["risks"].startswith("The shares fell")  # the caller's own copy is not changed
    assert len(log.entries()) == 1 and log.opened(entry)["removed"] == ["The shares fell 40% last month."]


def test_a_number_from_prices_must_be_sealed(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    body = decision()
    body["thesis"]["numbers"] = [{"label": "market value against cash", "value": "1.8", "basis": "price"}]
    with log.writer(DAY1, clock()) as w:
        with pytest.raises(LogError, match="must be sealed"):
            w.add("decision", body)
        body["thesis"]["numbers"] = [{"label": "months of cash", "value": "22"}]
        with pytest.raises(LogError, match="'basis' is missing"):
            w.add("decision", body)
    assert log.entries() == []


def test_messages_never_hold_a_value_or_the_home_folder(tmp_path: Path, monkeypatch, capsys) -> None:
    for call in (lambda: canon.encode({"price": 12.34}), lambda: canon.decimal_fraction("77,34")):
        with pytest.raises(canon.CanonError) as refused:
            call()
        assert "12.3" not in str(refused.value).replace("'12.34'", "") and "77" not in str(refused.value)
    data = tmp_path / "home" / "somebody" / "data"
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    log = Log.for_mode("pilot")
    with log.writer(DAY1, clock()) as w:
        w.add("decision", decision("nothing"))
    (day_file(log).parent / "notes.txt").write_text("x")
    assert cli.main(["verify"]) == 1
    out = capsys.readouterr().out
    assert "somebody" not in out and "log: <data folder>/pilot/staging" in out and "log/2027/02/notes.txt" in out


def test_a_copy_without_private_files_checks_the_public_half(tmp_path: Path, capsys) -> None:
    filled(tmp_path)
    assert cli_verify(tmp_path) == 0
    out = capsys.readouterr().out
    assert "records: 3 in 1 day file(s)" in out and "not checked: 2" in out and "(pilot)" in out


def test_after_a_purge_verify_reports_deleted_content_not_damage(tmp_path: Path, monkeypatch, capsys) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    log = Log.for_mode("pilot")
    with log.writer(DAY1, clock()) as w:
        w.add("session_start", session_start())
        w.add("decision", decision())
        w.add("fill", fill())
    for folder in ("books", "sessions/2027-02-03", "reports", "conversations"):
        (data / "pilot" / folder).mkdir(parents=True)
        (data / "pilot" / folder / "x.txt").write_text("12.34")
    public = day_file(log).read_bytes()
    note, counts = purge.purge_private(data)
    assert note is not None and counts == {
        "pilot/log-private": 2,
        "pilot/books": 1,
        "pilot/sessions": 1,
        "pilot/reports": 1,
        "pilot/conversations": 1,
    }
    assert "12.34" not in note.read_text()
    assert [p.name for p in (data / "pilot" / "log-private").iterdir()] == [DELETED]
    assert (data / "pilot" / "log-private" / DELETED).read_text().startswith("upto 3\n")
    assert not (data / "pilot" / "books").exists() and day_file(log).read_bytes() == public
    assert cli.main(["verify"]) == 0
    assert "content deleted under record 0007: 2" in capsys.readouterr().out
    assert purge.purge_private(data) == (None, {})  # nothing left: running it again does nothing
    # Content that goes missing after the purge is damage again: the marker only covers records up to the purge.
    with log.writer(DAY2, clock()) as w:
        w.add("fill", fill())
    assert cli.main(["verify"]) == 0
    log.private_path(4).unlink()
    assert cli.main(["verify"]) == 1 and "private content of /details is missing" in capsys.readouterr().out


def test_a_purge_that_stopped_before_its_marker_leaves_it_when_run_again(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    log = Log.for_mode("pilot")
    with log.writer(DAY1, clock()) as w:
        w.add("decision", decision())
        w.add("fill", fill(1))
    real = purge._leave_marker

    def power_cut(root: Path, stamp: str) -> None:
        raise OSError("power cut")

    monkeypatch.setattr(purge, "_leave_marker", power_cut)
    with pytest.raises(OSError):
        purge.purge_private(data)
    monkeypatch.setattr(purge, "_leave_marker", real)
    assert cli.main(["verify"]) == 1  # between the two runs the content is simply missing
    purge.purge_private(data)
    assert (data / "pilot" / "log-private" / DELETED).read_text().startswith("upto 2\n")
    assert not list((data / "pilot").glob(".log-private-purging-*")) and cli.main(["verify"]) == 0


def test_the_purge_refuses_a_folder_that_is_a_link(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "pilot").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "keep.txt").write_text("keep")
    (data / "pilot" / "books").symlink_to(elsewhere)
    with pytest.raises(purge.PurgeError, match="link"):
        purge.purge_private(data)
    assert (elsewhere / "keep.txt").exists()


# ---------------------------------------------------------------- forecasts.csv


def test_forecasts_csv_only_grows_and_an_outcome_is_a_new_line(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    with log.writer(DAY1, clock()) as w:
        w.add("forecast", forecast("60%"))
        w.add("forecast", forecast("10%"))
    assert forecasts.write(log.staging, log.entries()) == 3  # the header and two forecasts
    first = (log.staging / "forecasts.csv").read_bytes()
    with log.writer(DAY2, clock()) as w:
        w.add("outcome", {"ref": 1, "result": "yes", "resolved_on": "2027-05-20", "summary": "Met.", "sources": []})
        w.add(
            "outcome", {"ref": 2, "result": "void", "resolved_on": "2027-05-20", "summary": "Stopped.", "sources": []}
        )
    assert forecasts.write(log.staging, log.entries()) == 2 and forecasts.write(log.staging, log.entries()) == 0
    text = (log.staging / "forecasts.csv").read_bytes()
    assert text.startswith(first)
    rows = [line.split(",") for line in text.decode().splitlines()]
    assert rows[3][2:4] == ["outcome", "1"] and rows[3][-3:] == ["yes", "2027-05-20", "0.1600"]
    assert rows[4][-3:] == ["void", "2027-05-20", ""]
    (log.staging / "forecasts.csv").write_bytes(text.replace(b"60%", b"90%"))
    with pytest.raises(LogError, match="existing line would change"):
        forecasts.write(log.staging, log.entries())


def test_brier_scores_are_exact_text() -> None:
    assert forecasts.brier("60%", "yes") == "0.1600" and forecasts.brier("60%", "no") == "0.3600"
    assert forecasts.brier("50%", "yes") == "0.2500" and forecasts.brier("100%", "no") == "1.0000"
    assert forecasts.brier("0%", "no") == "0.0000" and forecasts.brier("33.33%", "yes") == "0.4445"


def test_a_pointer_to_the_wrong_record_is_refused_before_it_is_written(tmp_path: Path) -> None:
    log = filled(tmp_path)  # 1 session start, 2 decision, 3 fill
    outcome = {"result": "yes", "resolved_on": "2027-05-20", "summary": "Met.", "sources": []}
    closed = {"fund": "careful", "company": dict(ACME), "outcome": "replaced", "day": "2027-02-03"}
    with log.writer(DAY1, clock()) as w:
        for kind, body in (
            ("outcome", {**outcome, "ref": 2}),  # a decision is no forecast
            ("outcome", {**outcome, "ref": 99}),  # does not exist
            ("fill", fill(1)),  # a session start is no decision
            ("fill", fill(4)),  # itself: not written yet
            ("order_closed", {**closed, "ref": 2, "by": 3}),  # replaced by a fill?
            ("dice_draw", {"month": "2027-02", "covered": [], "rule_version": "1", "seed_ref": 1}),
        ):
            with pytest.raises(LogError, match="points to record"):
                w.add(kind, body)
        w.add("correction", {"ref": 3, "text": "Any earlier record may be corrected."})
    assert len(log.entries()) == 4 and forecasts.write(log.staging, log.entries()) == 1  # only the header


def test_verify_checks_the_pointers_too(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    with log.writer(DAY1, clock()) as w:
        w.add("forecast", forecast())
        w.add("outcome", {"ref": 1, "result": "yes", "resolved_on": "2027-05-20", "summary": "Met.", "sources": []})
    raw = lines(log)
    # Rebuild the chain by hand around a first line of another kind: the fingerprints are right, the pointer is not.
    first = canon.decode(raw[0].rstrip(b"\n"))
    stop = {"kind": "stop_file", "state": "on", "noticed": "2027-02-03T09:30:00Z"}
    other = canon.encode({k: first[k] for k in ("v", "seq", "time", "mode", "prev")} | stop)
    second = canon.decode(raw[1].rstrip(b"\n")) | {"prev": fingerprint(first["prev"], other)}
    second_line = canon.encode(second)
    day_file(log).write_bytes(other + b"\n" + second_line + b"\n")
    head = {"records": 2, "sha256": fingerprint(second["prev"], second_line), "v": 1}
    (log.staging / "HEAD").write_bytes(canon.encode(head) + b"\n")
    assert any("which is a stop_file, not a forecast" in p for p in log.verify().problems)

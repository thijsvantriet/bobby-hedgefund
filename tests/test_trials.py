"""Changes in trial records. Every trial and sponsor here is invented."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from bobby_hedgefund.archive.store import Archive
from bobby_hedgefund.trials import changes, cli


def study(nct: str = "NCT001", **over) -> dict:
    status = {
        "overallStatus": over.get("status", "RECRUITING"),
        "startDateStruct": {"date": "2025-01-10", "type": "ACTUAL"},
        "primaryCompletionDateStruct": {"date": over.get("pcd", "2027-03"), "type": "ESTIMATED"},
        "completionDateStruct": {"date": "2027-09", "type": "ESTIMATED"},
        "lastUpdatePostDateStruct": {"date": over.get("posted", "2026-11-01"), "type": "ACTUAL"},
    }
    if "why_stopped" in over:
        status["whyStopped"] = over["why_stopped"]
    outcome = {
        "measure": over.get("measure", "Overall survival"),
        "timeFrame": "24 months",
        "description": over.get("text", "x"),
    }
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct},
            "statusModule": status,
            "designModule": {
                "phases": ["PHASE3"],
                "enrollmentInfo": {"count": over.get("n", 300), "type": "ESTIMATED"},
            },
            "outcomesModule": {"primaryOutcomes": [outcome]},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Alpha Therapeutics", "class": "INDUSTRY"}},
            "descriptionModule": {"briefSummary": over.get("summary", "a summary")},
        },
        "hasResults": over.get("results", False),
    }


def test_no_line_for_a_first_copy_the_same_copy_again_or_a_field_we_do_not_follow() -> None:
    finder = changes.ChangeFinder()
    assert finder.add(study(), "f1", "t1") == []
    assert finder.add(study(), "f2", "t2") == []  # nightly pages overlap: the same copy comes twice
    assert finder.add(study(summary="rewritten", text="other description", posted="2026-11-05"), "f3", "t3") == []
    assert finder.trials == 1 and finder.copies == 3


def test_one_line_per_changed_field_with_both_files_and_how_far_a_date_moved() -> None:
    finder = changes.ChangeFinder()
    finder.add(study(), "f1", "t1")
    finder.add(study("NCT002"), "f1", "t1")
    lines = finder.add(study(pcd="2027-09-15", measure="Progression-free survival", posted="2026-11-10"), "f2", "t2")
    assert [x["field"] for x in lines] == ["primary_completion_date", "primary_outcomes"]
    moved = lines[0]
    assert moved["old"] == {"date": "2027-03", "type": "ESTIMATED"} and moved["new"]["date"] == "2027-09-15"
    assert moved["moved_days"] == (date(2027, 9, 15) - date(2027, 3, 1)).days
    assert (moved["old_file"], moved["old_saved"], moved["old_posted"]) == ("f1", "t1", "2026-11-01")
    assert (moved["new_file"], moved["new_saved"], moved["new_posted"]) == ("f2", "t2", "2026-11-10")
    assert (
        lines[1]["old"] == [{"measure": "Overall survival", "time_frame": "24 months"}] and "moved_days" not in lines[1]
    )
    # the next comparison is against the newest copy, not the first one
    back = finder.add(study(pcd="2027-06", measure="Progression-free survival", posted="2026-11-12"), "f3", "t3")
    assert [(x["field"], x["moved_days"]) for x in back] == [("primary_completion_date", -106)]
    assert (
        finder.add(study("NCT002", status="TERMINATED", why_stopped="funding", n=12, results=True), "f3", "t3")[0][
            "nct"
        ]
        == "NCT002"
    )


@pytest.mark.parametrize(
    ("old", "new", "days"),
    [
        ({"date": "2027-03"}, {"date": "2027-04"}, 31),
        ({"date": "2027-03-15"}, {"date": "2027-03-15"}, 0),  # only the type changed (estimated to actual)
        (None, {"date": "2027-03"}, None),
        ({"date": "soon"}, {"date": "2027-03"}, None),
        ({"date": "2027-13"}, {"date": "2027-03"}, None),
    ],
)
def test_moved_days(old, new, days) -> None:
    assert changes.moved_days(old, new) == days


def test_a_record_with_missing_parts_is_read_with_empty_fields() -> None:
    nct, fields, posted = changes.extract({"protocolSection": {"identificationModule": {"nctId": "NCT9"}}})
    assert nct == "NCT9" and posted == "" and fields["primary_outcomes"] == [] and fields["enrollment"] is None
    assert set(fields) == set(changes.FIELDS)
    with pytest.raises(KeyError):
        changes.extract({"protocolSection": {}})


def page(*studies: dict) -> bytes:
    return json.dumps({"studies": list(studies)}).encode()


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "data" / "archive"
    with Archive(root) as archive:
        archive.store(
            "ctgov-baseline", "p0001.json", page(study(), study("NCT002")), run="b", compress=True, dedup=False
        )
        archive.store("ctgov-baseline", "expr.txt", b"not a page", run="b")
        newer = page(study(pcd="2028-01", posted="2026-11-12"), study("NCT003"))
        archive.store("ctgov-updates", "p0001.json", newer, run="u1", compress=True, dedup=False)
        archive.store("ctgov-updates", "p0001.json", newer, run="u2", compress=True, dedup=False)  # the overlap
    return root


def test_changes_command_writes_only_what_is_new_and_nothing_on_a_night_without_news(root: Path, capsys) -> None:
    assert cli.main(["changes"]) == 0
    folder, today = root.parent / "trial-changes", date.today().isoformat()
    lines = [json.loads(x) for x in (folder / f"{today}_changes.jsonl").read_text().splitlines()]
    assert [(x["nct"], x["field"], x["moved_days"]) for x in lines] == [("NCT001", "primary_completion_date", 306)]
    assert lines[0]["old_file"].startswith("raw/ctgov-baseline/") and lines[0]["new_file"].startswith(
        "raw/ctgov-updates/"
    )
    inputs = (folder / f"{today}_changes-inputs.txt").read_text()
    assert "# trials: 3" in inputs and "# new_changes: 1" in inputs and inputs.count("raw/ctgov-") == 3
    assert "new_primary_completion_date      1" in capsys.readouterr().out

    assert cli.main(["changes"]) == 0  # the same archive again
    assert "nothing new: no file written" in capsys.readouterr().out
    assert sorted(p.name for p in folder.iterdir()) == [f"{today}_changes-inputs.txt", f"{today}_changes.jsonl"]

    with Archive(root) as archive:
        night = page(study(pcd="2028-01", status="COMPLETED", posted="2026-11-14"))
        archive.store("ctgov-updates", "p0001.json", night, run="u3", compress=True, dedup=False)
    assert cli.main(["changes"]) == 0
    second = [json.loads(x) for x in (folder / f"{today}-2_changes.jsonl").read_text().splitlines()]
    assert [(x["nct"], x["field"], x["new"]) for x in second] == [("NCT001", "overall_status", "COMPLETED")]
    assert "changes_since_the_baseline       2" in capsys.readouterr().out


def test_an_older_version_saved_later_is_not_compared() -> None:
    finder = changes.ChangeFinder()
    finder.add(study(posted="2026-11-01"), "f1", "t1")
    assert len(finder.add(study(pcd="2028-01", posted="2026-11-10"), "f2", "t2")) == 1
    assert finder.add(study(posted="2026-11-01"), "f3", "t3") == [] and finder.older_copies_skipped == 1
    assert finder.add(study(pcd="2028-01", posted="2026-11-10"), "f4", "t4") == []  # still the newest version


def test_an_unreadable_record_or_page_fails_once_and_not_every_night(root: Path, capsys) -> None:
    assert cli.main(["changes"]) == 0
    with Archive(root) as archive:
        archive.store(
            "ctgov-updates", "p0001.json", page({"protocolSection": {}}), run="u3", compress=True, dedup=False
        )
        archive.store("ctgov-updates", "p0002.json", b"<html>not a page</html>", run="u3", compress=True, dedup=False)
    assert cli.main(["changes"]) == 1
    out = capsys.readouterr().out
    assert (
        "records_not_readable             1" in out and "pages_not_readable               1" in out and "WARNING" in out
    )
    assert cli.main(["changes"]) == 0  # the same two the next night: known, no alarm
    assert "nothing new" in capsys.readouterr().out


def test_without_trial_records_or_with_a_damaged_file_nothing_is_written(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    assert cli.main(["changes"]) == 1 and "NOT DONE" in capsys.readouterr().out
    with Archive(tmp_path / "data" / "archive") as archive:
        rec = archive.store("ctgov-baseline", "p0001.json", page(study()), run="b")
    stored = tmp_path / "data" / "archive" / rec["path"]
    stored.chmod(0o600)
    stored.write_bytes(b"changed")
    assert cli.main(["changes"]) == 1 and "fingerprint" in capsys.readouterr().out
    assert not (tmp_path / "data" / "trial-changes").exists()

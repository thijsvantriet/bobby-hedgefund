from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fundkit import store_day
from roundkit import FLAT, THU_8, WED_8, agent_run, began, buy, decisions, fresh_jobs, make_data, section

from bobby_hedgefund.funds import cli as funds_cli
from bobby_hedgefund.funds.book import replay
from bobby_hedgefund.log.store import Log
from bobby_hedgefund.session import decide, marker, steps, tasks
from bobby_hedgefund.session import round as rounds
from bobby_hedgefund.session.round import RoundError

WED = date(2027, 2, 3)


@pytest.fixture
def world(tmp_path: Path, monkeypatch):
    data, cwd, records = make_data(tmp_path)
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    assert funds_cli.main(["start", "--funds", "careful,rules,dice", "--day", "2027-02-01"]) == 0
    return {"data": data, "cwd": cwd, "records": records, "monkeypatch": monkeypatch}


def begin(world: dict, session_id: str = "session-1", now: datetime = WED_8, **options) -> rounds.Round:
    began(world["data"], session_id)
    lines = steps.start(
        "pilot", session_id, world["cwd"], now=now, project=world["records"], claude_code="9.9.9", **options
    )
    world["start_lines"] = lines
    return rounds.current("pilot")


def answer_all(world: dict, rnd: rounds.Round, prefix: str, answers, at: datetime, **more) -> list[tasks.Task]:
    made = rounds.step_tasks(rnd, prefix)
    for task in made:
        found = answers(task) if callable(answers) else answers
        if found is not None:
            agent_run(world["records"], rnd.session_id, rnd.session_dir, task, found, at=at, **more)
    return made


def screening_yes(task: tasks.Task) -> dict:
    return {
        "companies": [{"cik": 101, "deep_look": True, "urgent": True, "why": "A results announcement."}],
        "lacked": [],
    }


def run_day(world: dict, rnd: rounds.Round, pm_answers, analyst_answers=None) -> list[str]:
    """One whole round with recorded answers, from booking to the end."""
    minute = lambda n: rnd.start + timedelta(minutes=n)  # noqa: E731
    out = steps.book(rnd)
    out += steps.screening(rnd)
    answer_all(world, rnd, "screening-", screening_yes, minute(3))
    out += steps.collect(rnd, "screening", 0)
    out += steps.analysts(rnd, now=minute(7))

    def default(task: tasks.Task) -> dict:
        cik = int(task.task.split("-")[1])
        if task.task.endswith("results"):
            reading = {"main_goal_met": "yes", "planned_in_advance": "unclear", "subgroup_pushed": "no"}
            return {
                "cik": cik,
                "section": "Our reading.",
                "reading": reading,
                "sources": [],
                "lacked": ["the protocol"],
            }
        return section(cik, forecast=task.task.endswith("clinical"))

    answer_all(world, rnd, "analysis-", analyst_answers or default, minute(9), seconds=300)
    out += steps.collect(rnd, "analysts", 0)
    out += steps.debate(rnd)
    out += steps.managers(rnd, now=minute(26))
    answer_all(world, rnd, "pm-", pm_answers, minute(28), seconds=240)
    out += steps.collect(rnd, "managers", 0)
    out += decide.decide(rnd, world["cwd"], "9.9.9")
    out += decide.publish_day(rnd)
    out += decide.end(rnd)
    return out


# ---------------------------------------------------------------- one whole day, and the day after


def test_a_whole_round_with_recorded_answers_and_the_day_after(world: dict) -> None:
    rnd = begin(world)
    assert rnd.day == WED and rnd.cutoff == WED_8 and rnd.extras == ["monthly"] and marker.read(world["data"])
    assert any("NEXT: bobby-session book" in line for line in world["start_lines"])

    def managers(task: tasks.Task) -> dict:
        return {
            1: decisions("careful", buy(101, "4%")),
            2: decisions("careful", buy(101, "3%")),
            3: decisions("careful"),
        }[task.run]

    out = run_day(world, rnd, managers)
    text = "\n".join(out)
    assert "screening: 1 ok" in text and "deep analysis of 2 companies" in text  # an extras day: two, not four
    assert "company 101: report joined from 5 sections" in text  # four analysts and the results reader
    assert "careful: 3 of 3 runs readable; 1 order(s); 0 refused, 0 reduced" in text
    assert "dice: drawn for 2027-02 from 2 covered companies" in text and "rules: 0 companies chosen" in text
    assert "committed on this machine only" in text and "Bobby Hedgefund, round of 2027-02-03 (pilot)" in text
    assert marker.read(world["data"]) is None  # the round's checks are switched off again

    log = Log.for_mode("pilot")
    today = [e for e in log.entries() if e.day == WED]
    kinds = [e.kind for e in today]
    assert kinds[0] == "session_start" and kinds.count("forecast") == 2 and kinds.count("decision") == 1
    assert "rules_draw" in kinds and "dice_draw" in kinds and not log.verify().problems
    start = today[0].record
    assert start["cutoff"] == "2027-02-03T08:00:00Z" and start["code"]["claude_code"] == "9.9.9"
    forecast = next(e for e in today if e.kind == "forecast").record
    assert forecast["role"] == "clinical-analyst" and forecast["agent"]["model"] == "claude-opus-5-5"
    assert forecast["sources"][0]["link"].startswith("https://www.sec.gov/Archives/edgar/data/101/")
    (decision,) = [e.record for e in today if e.kind == "decision"]
    # Two of three said buy: the position is opened at the smallest size among them, with that run's thesis.
    assert (decision["action"], decision["size_pct"], decision["from_run"]) == ("buy", "3%", 2)
    assert [(r["run"], r.get("action"), r.get("size_pct")) for r in decision["runs"]] == [
        (1, "buy", "4%"),
        (2, "buy", "3%"),
        (3, "nothing", None),
    ]
    assert decision["agreed"] is False and decision["thesis"]["numbers"] == [] and decision["saw"][0]["n"] == 2
    roles_named = sorted(a["role"] for a in decision["agents"])
    assert (
        roles_named.count("pm-careful") == 3 and "clinical-analyst" in roles_named and "results-reader" in roles_named
    )
    agent = decision["agents"][0]
    assert (agent["model"], agent["effort"], agent["file_model"], agent["substituted"]) == (
        "claude-fable-5-2",
        "high",
        "claude-fable-5-2",
        False,
    )
    assert agent["claude_code"] == "9.9.9" and len(agent["agent_file_sha256"]) == 64 and agent["run"] == 1

    root = world["data"] / "pilot"
    assert (root / "reports" / "101" / "2027-02-03.md").exists()  # the company is covered from today
    page = (root / "staging" / "days" / "2027" / "02" / "2027-02-03.md").read_text()
    assert "Paper money, not investment advice" in page and "**Buy 3%: Aaa Therapeutics Inc**" in page
    assert "The three runs said: buy 4%, buy 3%, nothing. Agreed: no." in page and "We sell if: The filing" in page
    assert "ClinicalTrials.gov" in page and "$" not in page
    repo = root / "track-record-repo"
    assert (repo / "track-record" / "days" / "2027" / "02" / "2027-02-03.md").exists()
    usage = json.loads((root / "rounds" / "2027-02-03" / "usage.json").read_text())
    assert usage["per_role"]["pm-careful"]["runs"] == 3 and usage["per_role"]["screening"]["models"] == [
        "claude-haiku-5-5"
    ]
    assert usage["per_role"]["clinical-analyst"]["tokens"]["output_tokens"] > 0
    assert (
        usage["minutes_per_step"]["4 deep analysis"]["began"] is not None and usage["for_the_log"]["agent_runs"] == 13
    )
    assert usage["decisions"]["funds"]["careful"]["companies_on_which_the_runs_agreed"] == 0
    copied = root / "conversations" / "2027-02-03_session-1" / "end"
    assert len(list(copied.rglob("agent-*.jsonl"))) == 13
    public = b"".join(p.read_bytes() for p in (root / "staging").rglob("*") if p.is_file())
    assert b"245.3" not in public and b"value_cents" not in public

    # The same session cannot do a second round, and no other session can do one for the same day.
    with pytest.raises(RoundError, match="started a round before"):
        begin(world)
    with pytest.raises(RoundError, match="one round of decisions per calendar day"):
        begin(world, "session-2")

    # Thursday, a fresh session: it learns when Wednesday was published, and Wednesday's order gets its fill day.
    fresh_jobs(world["data"], THU_8)
    store_day(world["data"] / "prices", WED, {**FLAT, "AAA": (11.0, 11.5)}, when=datetime(2027, 2, 4, 6, tzinfo=UTC))
    thursday = begin(world, "session-3", THU_8)
    first = next(
        e.record for e in Log.for_mode("pilot").entries() if e.day == thursday.day and e.kind == "session_start"
    )
    assert (
        first["previous_publication"]["session_day"] == "2027-02-03"
        and first["previous_publication"]["source"] == "local commit (pilot)"
    )
    assert len(first["previous_conversation"]["sha256"]) == 64 and first["usage"]["agent_runs"] == 13
    assert first["skipped_working_days"] == 0 and len(first.get("dry_run", "")) == 0
    assert thursday.extras == []  # not the first session of the week or the month any more
    out = steps.book(thursday)
    assert "booked: 1 trading day(s), 1 fill(s)" in out[0]
    # Wednesday's session started at 09:00 Amsterdam time, well before the opening: filled at Wednesday's opening
    # price of $11. (The pilot's stand-in for the time of receipt is the time of the local commit; in this test
    # that is the real clock of today, which lies before the made-up session: the session's own start then counts.)
    fund = replay(Log.for_mode("pilot")).funds["careful"]
    assert fund.positions[101].shares == 2727 and not fund.orders  # 3% of $1,000,000 at $11, rounded down

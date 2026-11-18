from __future__ import annotations

import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fundkit import store_day
from roundkit import FLAT, THU_8, WED_8, agent_run, began, buy, decisions, fresh_jobs, make_data, section

from bobby_hedgefund.funds import cli as funds_cli
from bobby_hedgefund.funds.book import replay
from bobby_hedgefund.log.store import Log
from bobby_hedgefund.session import cli as session_cli
from bobby_hedgefund.session import decide, marker, steps, tasks
from bobby_hedgefund.session import prepare as prep
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


def analyst_answer(task: tasks.Task) -> dict:
    cik = int(task.task.split("-")[1])
    if task.task.endswith("results"):
        reading = {"main_goal_met": "yes", "planned_in_advance": "unclear", "subgroup_pushed": "no"}
        return {"cik": cik, "section": "Our reading.", "reading": reading, "sources": [], "lacked": ["the protocol"]}
    return section(cik, forecast=task.task.endswith("clinical"))


def run_day(world: dict, rnd: rounds.Round, pm_answers, analyst_answers=None, end: bool = True) -> list[str]:
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
    return out + decide.end(rnd) if end else out


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


def test_the_three_runs_rule() -> None:
    from bobby_hedgefund.funds.engine import Fund, Order, Position
    from bobby_hedgefund.session.round import Collected

    def got(*orders: dict, status: str = "ok") -> Collected:
        answer = decisions("careful", *orders) if status == "ok" else None
        return Collected("t", "bobby-pm-careful", status, answer=answer, model="m")

    fund = Fund("careful", 1)
    fund.positions[200] = Position(200, "HHH", "Held", 10)
    fund.orders[9] = Order(9, "careful", 300, "WWW", "Waiting", "buy", None, date(2027, 2, 1))
    sell = {"cik": 200, "action": "sell", "reason": "r", "sources": []}

    def result(runs: dict[int, Collected]) -> list[tuple]:
        chosen, _ = decide.combine(fund, runs)
        return [(d["cik"], d["action"], d.get("size_pct"), d["from_run"]) for d in chosen]

    # Two of three buy: opened at the smallest size among those that do; with a tie, the lowest-numbered run.
    assert result({1: got(buy(101, "4%")), 2: got(buy(101, "2%")), 3: got()}) == [(101, "buy", "2%", 2)]
    assert result({1: got(buy(101, "3%")), 2: got(buy(101, "3%")), 3: got(buy(101, "5%"))}) == [(101, "buy", "3%", 1)]
    assert result({1: got(buy(101)), 2: got(), 3: got()}) == []  # one of three: not opened
    assert result({1: got(), 2: got(buy(101)), 3: got(buy(101))}) == [(101, "buy", "3%", 2)]  # run 1 is no veto
    # Everything else follows run 1: its sale counts, another run's does not.
    assert result({1: got(sell), 2: got(), 3: got()}) == [(200, "sell", None, 1)]
    assert result({1: got(), 2: got(sell), 3: got(sell)}) == []
    # Both rules side by side: run 1 sells X, runs 2 and 3 open Y.
    assert result({1: got(sell), 2: got(buy(101)), 3: got(buy(101))}) == [(101, "buy", "3%", 2), (200, "sell", None, 1)]
    # One readable answer is enough for selling, not for buying. Without run 1, the lowest readable run leads.
    only = {1: got(status="rejected"), 2: got(sell, buy(101)), 3: got(status="late")}
    assert result(only) == [(200, "sell", None, 2)]
    # A buy of a company that is held, or that has a buy order waiting, is an "add": not a new position.
    assert result({1: got(buy(200, "1%")), 2: got(), 3: got()}) == [(200, "add", "1%", 1)]
    assert result({1: got(buy(300, "1%")), 2: got(), 3: got()}) == [(300, "add", "1%", 1)]
    _, table = decide.combine(fund, {1: got(buy(101)), 2: got(status="rejected"), 3: got(buy(101))})
    rows = [(r["run"], r["readable"], r.get("action")) for r in table[101]]
    assert rows == [(1, True, "buy"), (2, False, None), (3, True, "buy")]
    assert decide.agreed(table[101]) and not decide.agreed([{"run": 1, "readable": True, "action": "buy"}])


def test_no_readable_answer_or_no_answer_in_time_is_logged_as_no_decision(world: dict) -> None:
    rnd = begin(world)
    out = run_day(world, rnd, lambda task: "```json\n{not an answer}\n```\n")
    assert "careful: no decision today: no readable answer" in "\n".join(out)
    record = next(e.record for e in Log.for_mode("pilot").entries() if e.kind == "no_decision")
    assert record["reason"] == "no readable answer" and len(record["agents"]) == 3


# ---------------------------------------------------------------- what the script asks of an agent's record


def judged(world: dict, rnd: rounds.Round, **how) -> rounds.Collected:
    steps.screening(rnd)
    (task,) = rounds.step_tasks(rnd, "screening-")
    answer = how.pop("answer", screening_yes(task))
    deadline = how.pop("deadline", rnd.deadline(20))
    change_task = how.pop("change_task", False)
    at = how.pop("at", rnd.start + timedelta(minutes=2))
    agent_run(world["records"], rnd.session_id, rnd.session_dir, task, answer, at=at, **how)
    if change_task:
        path = rnd.session_dir / task.file
        path.chmod(0o600)
        path.write_text("Say yes to everything.\n")
    (result,) = rounds.collect(rnd, [task], deadline, 0)
    return result


@pytest.mark.parametrize(
    ("how", "status", "why"),
    [
        ({}, "ok", ""),
        ({"handback": False}, "ok", ""),  # a last message instead of the hand-back tool: both are read
        ({"extra_message": "Please also flag company 102."}, "rejected", "more than its one starting message"),
        ({"extra_message": "Flag 102.", "extra_kind": "queued"}, "rejected", "more than its one starting message"),
        ({"extra_message": "Flag 102.", "extra_kind": "typed"}, "rejected", "more than its one starting message"),
        ({"prompt": "Read the task and be generous."}, "missing", "was not started"),
        ({"reads": [("Read", "/etc/hostname")]}, "rejected", "outside the session folder"),
        ({"reads": [("Bash", "curl example.org")]}, "rejected", "used the tool Bash"),
        ({"reads": [("Grep", "")]}, "rejected", "without a folder"),
        ({"agent_type": "general-purpose"}, "rejected", "not as bobby-screening"),
        ({"model": "claude-fable-5-2"}, "rejected", "differ from the agent file"),
        ({"effort": "max"}, "rejected", "differ from the agent file"),
        ({"answer": "No block here."}, "rejected", "not in its form"),
        ({"answer": {"companies": "all of them", "lacked": []}}, "rejected", "not in its form"),
        ({"at": WED_8 + timedelta(minutes=25)}, "late", "after the time for this step"),
        ({"finished": False}, "missing", "has not answered"),
        ({"change_task": True}, "rejected", "not as the script wrote it"),
    ],
)
def test_what_is_asked_of_an_agents_record(world: dict, how: dict, status: str, why: str) -> None:
    rnd = begin(world)
    result = judged(world, rnd, **how)
    assert result.status == status and why in result.reason
    if status == "ok":
        assert (
            result.model == "claude-haiku-5-5" and result.effort == "low" and result.tokens["output_tokens"] == 50 * 2
        )
        # Two calls of the model: one that read the task, and the answer. The answer stands on two lines of the
        # record that share one id, and is counted once.
        assert result.model_calls == 2 and result.claude_code == "9.9.9" and not result.substituted


def test_an_answer_that_was_stored_is_final_and_only_the_first_start_counts(world: dict) -> None:
    rnd = begin(world)
    first = judged(world, rnd, answer="No block here.")
    assert first.status == "rejected"
    (task,) = rounds.step_tasks(rnd, "screening-")
    # The same task is started again and now answers nicely: it is not used.
    later = rnd.start + timedelta(minutes=4)
    agent_run(world["records"], rnd.session_id, rnd.session_dir, task, screening_yes(task), at=later)
    (again,) = rounds.collect(rnd, [task], rnd.deadline(20), 0)
    assert again.status == "rejected" and again.reason == first.reason


def test_a_try_out_with_stand_ins_notes_what_differs_and_uses_the_answer(world: dict) -> None:
    rnd = begin(world, dry_run="try-out by the building session", stand_ins=True, relaxed_clock=True)
    steps.screening(rnd)
    (task,) = rounds.step_tasks(rnd, "screening-")
    assert task.stand_in == {"subagent_type": "general-purpose", "model": "haiku", "effort": "low"}
    text = (rnd.session_dir / task.file).read_text()
    assert "# Your instructions" in text and "## Your role: screening" in text and "# Your task" in text
    late = rnd.start + timedelta(minutes=50)
    answer = screening_yes(task)
    agent_run(
        world["records"],
        rnd.session_id,
        rnd.session_dir,
        task,
        answer,
        at=late,
        agent_type="general-purpose",
        effort="medium",
    )
    (result,) = rounds.collect(rnd, [task], rnd.deadline(20), 0)
    assert result.status == "ok" and result.substituted and result.stand_in and "late (noted only" in result.reason
    start = next(e.record for e in Log.for_mode("pilot").entries() if e.kind == "session_start")
    assert start["dry_run"] == "try-out by the building session"
    assert marker.read(world["data"])["stand_ins"] is True
    with pytest.raises(RoundError, match="try-out only"):
        steps.start("pilot", "session-9", world["cwd"], now=WED_8, project=world["records"], stand_ins=True)


# ---------------------------------------------------------------- when a round may start


def test_a_round_needs_a_fresh_session_and_a_refusal_reaches_the_log_with_the_next_round(world: dict) -> None:
    data = world["data"]
    began(data, "resumed", "startup")
    began(data, "resumed", "resume")
    with pytest.raises(RoundError, match="began as 'resume'"):
        steps.start("pilot", "resumed", world["cwd"], now=WED_8, project=world["records"])
    with pytest.raises(RoundError, match="not known how this session began"):
        steps.start("pilot", "unknown", world["cwd"], now=WED_8, project=world["records"])
    (data / "STOP").write_text("stop\n")
    began(data, "stopped", "clear")
    with pytest.raises(RoundError, match="STOP file"):
        steps.start("pilot", "stopped", world["cwd"], now=WED_8, project=world["records"])
    (data / "STOP").unlink()
    (world["cwd"] / "work-in-progress.py").write_text("x = 1\n")
    began(data, "dirty", "clear")
    with pytest.raises(RoundError, match="changes that are not committed"):
        steps.start("pilot", "dirty", world["cwd"], now=WED_8, project=world["records"])
    (world["cwd"] / "work-in-progress.py").unlink()
    assert not (data / "pilot" / "sessions").exists() and marker.read(data) is None  # none of them got anywhere
    begin(world, "good")
    today = [e for e in Log.for_mode("pilot").entries() if e.day == WED]
    kinds = [(e.kind, e.record.get("state") or e.record.get("reason", "")[:24]) for e in today]
    assert kinds[:-1] == [
        ("refusal", "this session began as 'r"),
        ("refusal", "it is not known how this"),
        ("stop_file", "on"),
        ("refusal", "a STOP file is in the da"),
        ("stop_file", "off"),
        ("refusal", "the project folder has c"),
    ]
    assert kinds[-1][0] == "session_start"


def test_last_nights_jobs_must_have_run(world: dict) -> None:
    began(world["data"], "late", "startup")
    with pytest.raises(RoundError, match="no good run in the last 30 hours"):
        steps.start("pilot", "late", world["cwd"], now=WED_8 + timedelta(days=3), project=world["records"])


def test_a_round_that_broke_off_may_be_started_once_more_with_its_first_start_time(world: dict) -> None:
    rnd = begin(world)
    steps.book(rnd)
    decide.end(rnd, abort=True)  # the session crashed; the owner (or the next start) switches the checks off
    assert marker.read(world["data"]) is None
    with pytest.raises(RoundError, match="started a round before"):
        begin(world)  # the crashed session counts as used
    later = WED_8 + timedelta(minutes=50)
    again = begin(world, "session-2", later)
    assert again.start == WED_8 and again.cutoff == WED_8 and again.restarts == 1 and again.session_id == "session-2"
    kinds = [e.kind for e in Log.for_mode("pilot").entries() if e.day == WED]
    assert kinds.count("session_start") == 1 and kinds[-1] == "restart"
    decide.end(again, abort=True)
    with pytest.raises(RoundError, match="broke off twice"):
        begin(world, "session-3", later)


# ---------------------------------------------------------------- the step clock


def test_the_step_clock_is_kept_by_the_script(world: dict) -> None:
    rnd = begin(world)
    steps.book(rnd)
    steps.screening(rnd)
    answer_all(world, rnd, "screening-", screening_yes, rnd.start + timedelta(minutes=3))
    steps.collect(rnd, "screening", 0)
    out = steps.analysts(rnd, now=rnd.start + timedelta(minutes=21))
    assert any("no new deep analysis starts after minute 20" in line for line in out)
    assert "no deep analysis today" in out and rounds.step_tasks(rnd, "analysis-") == []
    assert rnd.deadline(38) == WED_8 + timedelta(minutes=38) and rounds.HARD_STOP == 45
    steps.managers(rnd, now=rnd.start + timedelta(minutes=26))
    at = rnd.start + timedelta(minutes=36)
    made = answer_all(world, rnd, "pm-", decisions("careful"), at, seconds=180)  # they end at minute 39
    results = rounds.collect(rnd, made, rnd.deadline(rounds.DECISIONS_UNTIL), 0)
    assert {r.status for r in results} == {"late"}
    out = decide.decide(rnd, world["cwd"])
    assert "careful: no decision today: out of time" in out
    with pytest.raises(RoundError, match="decides once"):
        decide.decide(rnd, world["cwd"])


# ---------------------------------------------------------------- the Debate fund, with recorded answers


def test_the_debate_fund_hears_bull_and_bear_twice_before_its_manager_decides(tmp_path: Path, monkeypatch) -> None:
    data, cwd, records = make_data(tmp_path)
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    assert funds_cli.main(["start", "--funds", "careful,debate", "--day", "2027-02-01"]) == 0
    world = {"data": data, "cwd": cwd, "records": records}
    rnd = begin(world)
    minute = lambda n: rnd.start + timedelta(minutes=n)  # noqa: E731
    steps.book(rnd)
    steps.screening(rnd)
    answer_all(world, rnd, "screening-", screening_yes, minute(3))
    steps.collect(rnd, "screening", 0)
    steps.analysts(rnd, now=minute(7))
    answer_all(
        world,
        rnd,
        "analysis-",
        analyst_answer,
        minute(9),
    )
    joined = steps.collect(rnd, "analysts", 0)
    assert any("report joined" in line for line in joined), joined

    def case(task: tasks.Task) -> dict:
        _, cik, side, number = task.task.split("-")
        answer = "Where the other side is right, and where not." if number == "2" else ""
        return {
            "cik": int(cik),
            "case": f"The {side} case.",
            "strongest_points": ["One."],
            "answer_to_other_side": answer,
            "sources": [],
            "lacked": [],
        }

    first = steps.debate(rnd)
    assert sum("PROMPT" in line for line in first) == 4, first  # bull and bear for each of the two reports of today
    assert all(t.agent in ("bobby-bull", "bobby-bear") for t in rounds.step_tasks(rnd, "debate-"))
    answer_all(world, rnd, "debate-", case, minute(22))
    out = steps.collect(rnd, "debate", 0)
    assert "bull case for company 101, round 1: written" in out and out[-1] == "NEXT: bobby-session debate"
    second = steps.debate(rnd)
    second_tasks = [t for t in rounds.step_tasks(rnd, "debate-") if t.task.endswith("-2")]
    assert len(second_tasks) == 4 and sum("PROMPT" in line for line in second) == 4
    bear_two = (rnd.session_dir / "tasks" / "debate-101-bear-2.md").read_text()
    assert "round/debate/101-bull-1.md" in bear_two and "Second round" in bear_two  # it reads the other side's case
    for task in second_tasks:
        agent_run(records, rnd.session_id, rnd.session_dir, task, case(task), at=minute(25))
    steps.collect(rnd, "debate", 0)
    assert steps.debate(rnd) == ["the debate is over", "NEXT: bobby-session managers"]
    cases = sorted(p.name for p in (rnd.session_dir / "round" / "debate").iterdir())
    assert (
        len(cases) == 8
        and "Answer to the other side" in (rnd.session_dir / "round" / "debate" / "101-bear-2.md").read_text()
    )
    steps.managers(rnd, now=minute(27))
    debate_task = (rnd.session_dir / "tasks" / "pm-debate-run-1.md").read_text()
    careful_task = (rnd.session_dir / "tasks" / "pm-careful-run-1.md").read_text()
    assert "The bull and bear cases:" in debate_task and "101-bull-2.md" in debate_task
    assert "bull" not in careful_task  # the Careful fund's manager is not pointed to the debate
    for run in (1, 2, 3):  # the three runs of the Debate fund's manager get the same task text: the debate ran once
        assert (rnd.session_dir / "tasks" / f"pm-debate-run-{run}.md").read_text() == debate_task


# ---------------------------------------------------------------- what the review of this part found


def three(*answers: dict):
    return lambda task: answers[task.run - 1]


def test_a_round_whose_last_step_never_ran_does_not_stop_the_next_day(world: dict, capsys) -> None:
    rnd = begin(world)
    out = run_day(world, rnd, three(*[decisions("careful", buy(101))] * 3), end=False)
    assert out[-1] == "NEXT: bobby-session end" and not (rnd.round_dir / "done.json").exists()
    with pytest.raises(RoundError, match="is done: one round of decisions per calendar day"):
        begin(world, "session-2", WED_8 + timedelta(hours=3))  # published is done, with or without the last step
    marker.clear(world["data"])  # the marker has run out
    assert session_cli.main(["end"]) == 0  # the open round is ended all the same
    assert "Bobby Hedgefund, round of 2027-02-03" in capsys.readouterr().out and (rnd.round_dir / "done.json").exists()
    (rnd.round_dir / "done.json").unlink()  # and had it never been ended at all:
    store_day(world["data"] / "prices", WED, FLAT)
    fresh_jobs(world["data"], THU_8)
    begin(world, "session-2", THU_8)
    start = [e.record for e in Log.for_mode("pilot").entries() if e.kind == "session_start"][-1]
    assert start["previous_publication"]["session_day"] == "2027-02-03" and "previous_conversation" in start


def test_the_days_records_are_written_once_also_after_a_failure_halfway(world: dict) -> None:
    rnd = begin(world)

    def broken(*args, **kwargs):
        raise RuntimeError("the disk is full")

    world["monkeypatch"].setattr(decide.orders, "place", broken)
    with pytest.raises(RuntimeError):
        run_day(world, rnd, three(*[decisions("careful", buy(101))] * 3))
    world["monkeypatch"].undo()
    world["monkeypatch"].setenv("BOBBY_DATA_DIR", str(world["data"]))
    forecasts = sum(e.kind == "forecast" for e in Log.for_mode("pilot").entries())
    with pytest.raises(RoundError, match="begun before"):
        decide.decide(rnd, world["cwd"])
    assert sum(e.kind == "forecast" for e in Log.for_mode("pilot").entries()) == forecasts == 2


def test_nothing_is_decided_while_a_managers_answer_is_still_on_its_way(world: dict) -> None:
    rnd = begin(world)
    steps.book(rnd)
    with pytest.raises(RoundError, match="run `bobby-session managers` first"):
        decide.decide(rnd, world["cwd"])
    steps.managers(rnd, now=rnd.start + timedelta(minutes=5))
    made = rounds.step_tasks(rnd, "pm-")
    for task in made[1:]:  # run 1 has not answered yet
        agent_run(world["records"], rnd.session_id, rnd.session_dir, task, decisions("careful"), at=rnd.start)
    with pytest.raises(RoundError, match="not every portfolio manager has answered"):
        decide.decide(rnd, world["cwd"])
    assert not (rnd.round_dir / decide.BEGAN).exists() and rounds.stored(rnd, made[0].task) is None


def test_what_the_runs_said_about_a_company_that_got_no_order_is_in_the_log(world: dict) -> None:
    rnd = begin(world)
    answers = three(decisions("careful", buy(101)), decisions("careful", buy(101)), decisions("careful", buy(102)))
    run_day(world, rnd, answers)
    (record,) = [
        e.record for e in Log.for_mode("pilot").entries() if e.kind == "decision" and e.record["fund"] == "careful"
    ]
    (other,) = record["not_taken"]
    assert other["company"]["cik"] == 102 and [row.get("action") for row in other["runs"]] == [
        "nothing",
        "nothing",
        "buy",
    ]
    usage = json.loads((rnd.round_dir / "usage.json").read_text())
    assert usage["per_role"]["pm-careful"]["starts"] == 3 and usage["per_role"]["pm-careful"]["tokens"]["output_tokens"]


def test_after_a_restart_no_task_is_handed_out_twice(world: dict) -> None:
    rnd = begin(world)
    steps.book(rnd)
    first = steps.screening(rnd)
    assert sum("PROMPT" in line for line in first) == 1 and "Nothing to start" not in "\n".join(first)
    assert sum("PROMPT" in line for line in steps.screening(rnd)) == 1  # asked again: the same task, not a new one
    decide.end(rnd, abort=True)
    again = begin(world, "session-2", WED_8 + timedelta(minutes=10))
    assert any("1 task(s) of the session that broke off" in line for line in world["start_lines"])
    out = steps.screening(again)
    assert out[0].startswith("Nothing to start") and "collect screening" in out[-1]
    assert "broke off" in rounds.stored(again, "screening-01").reason
    assert steps.collect(again, "screening", 0)[-1] == "NEXT: bobby-session analysts"


def test_a_start_that_stopped_before_the_session_folder_was_made_is_carried_on(world: dict) -> None:
    real = prep.prepare

    def broken(**kwargs):
        raise prep.PrepareError("a saved file does not match its fingerprint")

    world["monkeypatch"].setattr(prep, "prepare", broken)
    with pytest.raises(prep.PrepareError):
        begin(world)
    world["monkeypatch"].setattr(prep, "prepare", real)
    rnd = begin(world, now=WED_8 + timedelta(minutes=4))
    assert rnd.start == WED_8 and rnd.restarts == 0 and rnd.extras == ["monthly"]
    kinds = [e.kind for e in Log.for_mode("pilot").entries() if e.day == WED]
    assert kinds == ["refusal", "session_start"]


def test_a_second_session_cannot_take_a_round_over_while_the_first_is_at_work(world: dict) -> None:
    rnd = begin(world)
    record = world["records"] / f"{rnd.session_id}.jsonl"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text("{}\n")
    with pytest.raises(RoundError, match="another session is running a round right now"):
        begin(world, "session-2", WED_8 + timedelta(minutes=10))
    assert marker.read(world["data"])["session_id"] == rnd.session_id
    quiet = time.time() - 600
    os.utime(record, (quiet, quiet))  # the first session has been silent for ten minutes: it broke off
    assert begin(world, "session-2", WED_8 + timedelta(minutes=10)).restarts == 1


def test_a_finished_copy_of_a_conversation_is_never_made_again(world: dict, tmp_path: Path) -> None:
    project, root = tmp_path / "records", tmp_path / "pilot"
    (project / "s1" / "subagents").mkdir(parents=True)
    (project / "s1.jsonl").write_text("one\n")
    (project / "s1" / "subagents" / "agent-a.jsonl").write_text("agent\n")
    first = steps.copy_conversation(root, project, "s1", WED, "end")
    (project / "s1.jsonl").write_text("one\nchanged afterwards\n")
    assert steps.copy_conversation(root, project, "s1", WED, "end") == first
    kept = root / "conversations" / "2027-02-03_s1" / "end"
    assert (kept / "s1.jsonl").read_text() == "one\n" and (kept / "s1" / "subagents" / "agent-a.jsonl").exists()
    assert steps.copy_conversation(root, project, "s1", WED, "complete") != first  # the later, fuller copy


def test_a_debate_ends_when_one_side_gave_no_readable_case(tmp_path: Path, monkeypatch) -> None:
    data, cwd, records = make_data(tmp_path)
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    assert funds_cli.main(["start", "--funds", "careful,debate", "--day", "2027-02-01"]) == 0
    world = {"data": data, "cwd": cwd, "records": records}
    rnd = begin(world)
    minute = lambda n: rnd.start + timedelta(minutes=n)  # noqa: E731
    steps.book(rnd)
    steps.screening(rnd)
    answer_all(world, rnd, "screening-", screening_yes, minute(3))
    steps.collect(rnd, "screening", 0)
    steps.analysts(rnd, now=minute(7))
    answer_all(world, rnd, "analysis-", analyst_answer, minute(9))
    steps.collect(rnd, "analysts", 0)

    def case(task: tasks.Task) -> dict | str:
        _, cik, side, number = task.task.split("-")
        if side == "bear" and number == "1":
            return "No block here."
        return {
            "cik": int(cik), "case": "A case.", "strongest_points": ["One."], "sources": [], "lacked": [],
            "answer_to_other_side": "An answer." if number == "2" else "",
        }  # fmt: skip

    steps.debate(rnd)
    answer_all(world, rnd, "debate-", case, minute(22))
    steps.collect(rnd, "debate", 0)
    second = steps.debate(rnd)
    assert sum("PROMPT" in line for line in second) == 2  # only the bears have a case to answer
    assert "not collected yet" in steps.debate(rnd)[0]  # asked again: no error, and nothing is handed out twice
    for task in [t for t in rounds.step_tasks(rnd, "debate-") if t.task.endswith("-2")]:
        agent_run(records, rnd.session_id, rnd.session_dir, task, case(task), at=minute(25))
    assert steps.collect(rnd, "debate", 0)[-1] == "NEXT: bobby-session debate"
    assert steps.debate(rnd) == ["the debate is over", "NEXT: bobby-session managers"]

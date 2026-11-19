"""Shared helpers for the tests of the decision log: made-up records. No real company, price or source."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from bobby_hedgefund.log.records import FILL_RULE_PILOT
from bobby_hedgefund.log.seal import Sealed
from bobby_hedgefund.log.store import Log

DAY1 = date(2027, 2, 3)
DAY2 = date(2027, 2, 4)
ACME = {"cik": 1234567, "name": "Acme Therapeutics Inc", "ticker": "ACME"}
H = "ab" * 32


def clock(hour: int = 9):
    def now() -> datetime:
        return datetime(2027, 2, 3, hour, 0, 0, tzinfo=UTC)

    return now


def make_log(tmp_path: Path, mode: str = "pilot") -> Log:
    return Log(tmp_path / "staging", tmp_path / "log-private", mode)


def agent(role: str = "pm-careful") -> dict[str, Any]:
    return {
        "role": role,
        "agent_file_sha256": H,
        "task_sha256": H,
        "model": "claude-test-1",
        "effort": "high",
        "claude_code": "0.0.0",
    }


def session_start() -> dict[str, Any]:
    return {
        "session_day": DAY1.isoformat(),
        "start_time": "2027-02-03T08:00:00Z",
        "cutoff": "2027-02-03T08:00:00Z",
        "universe": {"file": "2027-02-01_universe.csv", "sha256": H},
        "inputs_sha256": H,
        "code": {"commit": "0" * 40, "claude_code": "0.0.0"},
    }


def thesis() -> dict[str, Any]:
    return {
        "claim": "The main goal of the trial will be met.",
        "edge": "The earlier study already showed the effect in the same patients.",
        "catalyst": "Results of the final-phase trial",
        "catalyst_date": "2027-05-01",
        "probability": "60%",
        "numbers": [
            {"label": "months of cash", "value": "22", "basis": "filing"},
            {"label": "market value against cash", "value": Sealed("1.8", "price"), "basis": "price"},
        ],
        "risks": "The patient group is small.",
        "sell_if": "The main goal is missed, or the result is delayed past June.",
    }


def decision(action: str = "buy", size: str | None = "3%", **more: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "fund": "careful",
        "action": action,
        "fill_rule": FILL_RULE_PILOT,
        "cutoff": "2027-02-03T08:00:00Z",
    }
    if action != "nothing":
        body["company"] = dict(ACME)
        body["size_pct"] = size
    if action in ("buy", "add"):
        body["thesis"] = thesis()
    if action in ("reduce", "sell"):
        body["reason"] = "The sell rule of the thesis was met."
    body.update(more)
    return body


def forecast(probability: str = "60%") -> dict[str, Any]:
    return {
        "company": dict(ACME),
        "role": "clinical-analyst",
        "event": "The main goal of trial X is met, announced before 1 June 2027",
        "event_kind": "trial result",
        "by_date": "2027-06-01",
        "probability": probability,
        "make_or_break": True,
        "sources": [
            {"n": 1, "source": "trial registry", "date": "2027-01-15", "summary": "Our summary of the record."}
        ],
        "agent": agent("clinical-analyst"),
        "cutoff": "2027-02-03T08:00:00Z",
    }


def fill(ref: int = 2) -> dict[str, Any]:
    return {
        "ref": ref,
        "fund": "careful",
        "company": dict(ACME),
        "side": "buy",
        "fill_day": "2027-02-04",
        "rule_version": "1",
        "details": Sealed({"shares": 100, "price": "12.34", "amount_cents": 123400, "cost_cents": 1234}),
    }


def lines(log: Log, day: date = DAY1) -> list[bytes]:
    path = log.staging / "log" / f"{day:%Y}" / f"{day:%m}" / f"{day.isoformat()}.jsonl"
    return path.read_bytes().splitlines(keepends=True)


def day_file(log: Log, day: date = DAY1) -> Path:
    return log.staging / "log" / f"{day:%Y}" / f"{day:%m}" / f"{day.isoformat()}.jsonl"

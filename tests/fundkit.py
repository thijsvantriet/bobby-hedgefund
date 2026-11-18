"""Shared helpers for the tests of the fund books: a made-up price folder, universe and session records."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from logkit import H

from bobby_hedgefund.archive.store import Archive
from bobby_hedgefund.funds.universe import Listed, Universe
from bobby_hedgefund.log.records import FILL_RULE_PILOT
from bobby_hedgefund.log.store import Log
from bobby_hedgefund.prices import massive

# A week without holidays: Monday 1 February 2027 to Friday 5 February, and the Monday after.
MON, TUE, WED, THU, FRI = (date(2027, 2, d) for d in (1, 2, 3, 4, 5))
NEXT_MON = date(2027, 2, 8)
COMPANIES = {
    101: ("AAA", "Aaa Therapeutics Inc", 3_000_000_000),
    102: ("BBB", "Bbb Bio Inc", 1_500_000_000),
    103: ("CCC", "Ccc Pharma Inc", 500_000_000),
    104: ("DDD", "Ddd Medicines Inc", None),
}


def universe(extra: dict[int, tuple[str, str, int | None]] | None = None, xbi_only: set[int] | None = None) -> Universe:
    rows = {**COMPANIES, **(extra or {})}
    return Universe(
        "test_universe.csv",
        H,
        {cik: Listed(cik, name, ticker, mv, cik in (xbi_only or set())) for cik, (ticker, name, mv) in rows.items()},
    )


def company(cik: int) -> dict[str, Any]:
    ticker, name, _ = COMPANIES[cik]
    return {"cik": cik, "name": name, "ticker": ticker}


def stored_at(day: date) -> datetime:
    """The morning after a trading day, when its price file is fetched."""
    return datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC) + timedelta(hours=6)


def store_day(root: Path, day: date, bars: dict[str, tuple[float | None, float]], when: datetime | None = None) -> None:
    """One day's price file: ticker -> (opening price or None, closing price)."""
    rows = [
        {"T": t, "o": o, "h": c, "l": c, "c": c, "v": 1000} if o is not None else {"T": t, "c": c, "v": 1000}
        for t, (o, c) in bars.items()
    ]
    body = json.dumps({"status": "OK", "adjusted": False, "results": rows}).encode()
    with Archive(root) as archive:
        archive.store(
            massive.DAILY_SOURCE,
            massive.day_name(day),
            body,
            run=f"run-{day}",
            when=when or stored_at(day),
            compress=True,
        )


def store_splits(root: Path, rows: list[tuple[str, date, float, float]], run: str = "splits-1") -> None:
    doc = {
        "status": "OK",
        "results": [
            {"ticker": t, "execution_date": d.isoformat(), "split_from": a, "split_to": b} for t, d, a, b in rows
        ],
    }
    with Archive(root) as archive:
        archive.store(massive.SPLITS_SOURCE, "splits-p01.json", json.dumps(doc).encode(), run=run, compress=True)
        archive.record_run(massive.SPLITS_SOURCE, run, "ok", meta={"pages": 1, "splits": len(rows)})


def session(log: Log, day: date, hour: int = 9, received_for: tuple[date, int, int] | None = None) -> dict[str, Any]:
    """The fields of a session start. `received_for`: (the earlier session day, hour, minute) at which that
    session's publication was received, UTC."""
    body: dict[str, Any] = {
        "session_day": day.isoformat(),
        "start_time": f"{day.isoformat()}T{hour:02d}:00:00Z",
        "cutoff": f"{day.isoformat()}T{hour:02d}:00:00Z",
        "universe": {"file": "test_universe.csv", "sha256": H},
        "inputs_sha256": H,
        "code": {"commit": "0" * 40, "claude_code": "0.0.0"},
    }
    if received_for is not None:
        earlier, h, m = received_for
        body["previous_publication"] = {
            "session_day": earlier.isoformat(),
            "received": f"{earlier.isoformat()}T{h:02d}:{m:02d}:00Z",
            "source": "local commit (pilot)",
        }
    return body


def order(cik: int, action: str = "buy", size: str | None = "3%", fund: str = "careful") -> dict[str, Any]:
    body: dict[str, Any] = {
        "fund": fund,
        "action": action,
        "fill_rule": FILL_RULE_PILOT,
        "cutoff": "2027-02-01T09:00:00Z",
        "company": company(cik),
        "size_pct": size,
    }
    if fund in ("careful", "bold", "debate"):
        if action in ("buy", "add"):
            body["thesis"] = {
                "claim": "The main goal will be met.",
                "edge": "Our reading of the earlier study.",
                "catalyst": "Results of the trial",
                "probability": "60%",
                "numbers": [],
                "risks": "A small trial.",
                "sell_if": "The main goal is missed.",
            }
        else:
            body["reason"] = "The sell rule of the thesis was met."
    return body

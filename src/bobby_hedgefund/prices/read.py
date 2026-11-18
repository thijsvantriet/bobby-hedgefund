"""Read stored price files. Every file read is checked against its fingerprint (`Inputs`).

Prices are the ones traded on the day itself: nothing here is recalculated for later share splits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..universe.inputs import InputError, Inputs
from . import massive


@dataclass(frozen=True)
class Bar:
    open: float | None  # None: the share did not open that day
    high: float | None
    low: float | None
    close: float
    volume: float


@dataclass(frozen=True)
class Split:
    ticker: str
    day: date
    split_from: float  # old shares
    split_to: float  # new shares


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def day_records(inputs: Inputs) -> dict[date, dict[str, Any]]:
    """The stored price file of each day (the newest one, should a day ever be stored twice), oldest day first."""
    found: dict[date, dict[str, Any]] = {}
    for rec in inputs.files(massive.DAILY_SOURCE):
        day = massive.name_day(str(rec.get("name")))
        if day is not None:
            found[day] = rec
    return dict(sorted(found.items()))


def load_day(inputs: Inputs, rec: dict[str, Any]) -> dict[str, Bar]:
    """Ticker -> prices of one stored day. Lines without a closing price or a volume are left out."""
    try:
        rows = json.loads(inputs.read(rec)).get("results") or []
        bars: dict[str, Bar] = {}
        for row in rows:
            close, volume = _number(row.get("c")), _number(row.get("v"))
            if close is None or volume is None or not isinstance(row.get("T"), str):
                continue
            bars[row["T"]] = Bar(_number(row.get("o")), _number(row.get("h")), _number(row.get("l")), close, volume)
    except (ValueError, AttributeError, TypeError) as exc:
        raise InputError(f"{rec.get('path')} is not a price file ({type(exc).__name__})") from exc
    return bars


def load_splits(inputs: Inputs) -> list[Split]:
    """The share splits in the newest complete copy of the split list."""
    done = [r for r in inputs.runs(massive.SPLITS_SOURCE) if r.get("status") == "ok"]
    if not done:
        raise InputError("no complete list of share splits is stored")
    run = done[-1].get("run")
    pages = [r for r in inputs.files(massive.SPLITS_SOURCE) if r.get("run") == run]
    if len(pages) != (done[-1].get("meta") or {}).get("pages"):
        raise InputError("the newest list of share splits is not complete")
    splits: list[Split] = []
    for rec in pages:
        try:
            for row in json.loads(inputs.read(rec)).get("results") or []:
                splits.append(
                    Split(
                        str(row["ticker"]),
                        date.fromisoformat(str(row["execution_date"])),
                        float(row["split_from"]),
                        float(row["split_to"]),
                    )
                )
        except (ValueError, KeyError, AttributeError, TypeError) as exc:
            raise InputError(f"{rec.get('path')} is not a list of share splits ({type(exc).__name__})") from exc
    return splits

"""The table of company events: takeovers and the like, entered by hand from the SEC filing (docs/decisions/0005,
point 4). A file in the data folder that only grows; every line carries the fingerprint of the line before it.
No agent that manages a fund writes here: a line is added in a normal working session, and the daily script books
it in the next round. Share splits are not in this table: they come from the saved list of splits.

Built so far: a takeover for cash and a takeover for shares. The rarer kinds (a spin-off, a removal from the
exchange, a right to a later payment) are refused with a message until one is needed.
"""

from __future__ import annotations

import fcntl
import json
import os
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..archive.store import GENESIS, sha256_hex
from ..log import canon

FILE = "company-events.jsonl"
CASH_TAKEOVER = "cash takeover"
SHARE_TAKEOVER = "share takeover"
BUILT = (CASH_TAKEOVER, SHARE_TAKEOVER)
NOT_BUILT = ("mixed deal", "spin-off", "removal", "later payment", "cash dividend")


class EventError(Exception):
    pass


@dataclass(frozen=True)
class Event:
    key: str  # the fingerprint of its line in the table
    cik: int
    name: str
    kind: str
    effective: date
    filing: str
    cash_per_share: Fraction | None = None  # cash takeover
    ratio: Fraction | None = None  # share takeover: buyer's shares per share
    buyer_cik: int | None = None
    buyer_ticker: str = ""
    buyer_name: str = ""


def load(folder: Path) -> list[Event]:
    """Every line of the table, oldest first. Raises EventError when a line was changed or removed."""
    path = folder / FILE
    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise EventError(f"{path.name} ends with half a line")
    out: list[Event] = []
    prev = GENESIS
    for number, raw in enumerate(data.splitlines(), start=1):
        try:
            rec = json.loads(raw)
            if not isinstance(rec, dict) or rec.get("prev") != prev:
                raise ValueError
            prev = sha256_hex(raw)
            terms = rec.get("terms") or {}
            out.append(
                Event(
                    key=prev,
                    cik=int(rec["cik"]),
                    name=str(rec["name"]),
                    kind=str(rec["event"]),
                    effective=date.fromisoformat(rec["effective"]),
                    filing=str(rec["filing"]),
                    cash_per_share=canon.decimal_fraction(terms["cash_per_share"])
                    if "cash_per_share" in terms
                    else None,
                    ratio=canon.decimal_fraction(terms["ratio"]) if "ratio" in terms else None,
                    buyer_cik=terms.get("buyer_cik"),
                    buyer_ticker=str(terms.get("buyer_ticker") or ""),
                    buyer_name=str(terms.get("buyer_name") or ""),
                )
            )
        except (ValueError, KeyError, TypeError, canon.CanonError):
            raise EventError(f"{path.name}, line {number}: changed, removed or not an event line") from None
    return out


def add(
    folder: Path,
    when: str,
    *,
    cik: int,
    name: str,
    kind: str,
    effective: date,
    filing: str,
    cash_per_share: str | None = None,
    ratio: str | None = None,
    buyer_cik: int | None = None,
    buyer_ticker: str = "",
    buyer_name: str = "",
) -> Event:
    """Add one line. The terms are text ("12.50", "0.4321"), read exactly."""
    if kind in NOT_BUILT:
        raise EventError(
            f"'{kind}' is not built yet (docs/decisions/0005, point 4); it has to be built before it can be booked"
        )
    if kind not in BUILT:
        raise EventError(f"unknown kind of event {kind!r}; built are: {', '.join(BUILT)}")
    if not filing.startswith("https://www.sec.gov/"):
        raise EventError("an event needs the link to its SEC filing (https://www.sec.gov/...)")
    terms: dict[str, Any] = {}
    try:
        if kind == CASH_TAKEOVER:
            if cash_per_share is None or canon.decimal_fraction(cash_per_share) <= 0:
                raise EventError("a takeover for cash needs the cash per share, above zero")
            terms = {"cash_per_share": cash_per_share}
        else:
            if ratio is None or canon.decimal_fraction(ratio) <= 0 or buyer_cik is None or not buyer_ticker:
                raise EventError("a takeover for shares needs the ratio, and the buyer's SEC number and ticker")
            terms = {"ratio": ratio, "buyer_cik": buyer_cik, "buyer_ticker": buyer_ticker, "buyer_name": buyer_name}
    except canon.CanonError as exc:
        raise EventError(str(exc)) from None
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / FILE
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        lines = load(folder)
        rec = {
            "v": 1,
            "ts": when,
            "cik": cik,
            "name": name,
            "event": kind,
            "effective": effective.isoformat(),
            "filing": filing,
            "terms": terms,
            "prev": lines[-1].key if lines else GENESIS,
        }
        raw = json.dumps(rec, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        size = os.fstat(fd).st_size
        try:
            os.write(fd, raw + b"\n")
            os.fsync(fd)
        except OSError as exc:
            os.ftruncate(fd, size)
            raise EventError(f"could not write the event ({exc}); nothing was added") from exc
    finally:
        os.close(fd)
    return load(folder)[-1]

"""The Rules fund: no AI, simple rules (docs/SPEC.md section 4). It holds, in equal parts, the covered companies
with at least 18 months of cash and a catalyst from a large final-phase trial or an FDA decision on our calendar
within 6 months; nearest catalyst first, at most 20; re-drawn on the first session of each month.

**As far as it goes for now.** The months of cash come from the quarterly reports (stream 4) and the catalysts
from our own calendar (stream 5). Neither exists yet, and the exact rules are fixed in record 0010 after the
historical study. Until a file with these inputs exists the fund holds nothing, and its monthly record says why.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

RULE_VERSION = "rules-2026-11-18-provisional"  # until record 0010 fixes the exact rules
MIN_MONTHS_OF_CASH = 18
CATALYST_WITHIN_DAYS = 183  # six months
MOST = 20
KINDS = ("final-phase trial", "fda decision")
NO_INPUTS = (
    "no inputs yet: the months of cash come from the quarterly reports and the catalysts from our own calendar "
    "(streams 4 and 5), which are not built"
)


class RulesError(Exception):
    pass


@dataclass(frozen=True)
class Candidate:
    cik: int
    months_of_cash: int
    catalyst: date
    kind: str


def load_inputs(folder: Path) -> tuple[str, list[Candidate]] | None:
    """The newest `<date>_rules-inputs.json` in `folder`, or None when there is none yet. The file is written by
    the scripts of streams 4 and 5: {"companies": [{"cik", "months_of_cash", "catalyst", "kind"}, ...]}."""
    files = (
        sorted(p for p in folder.glob("*_rules-inputs.json") if not p.name.startswith(".")) if folder.is_dir() else []
    )
    if not files:
        return None
    try:
        rows = json.loads(files[-1].read_text(encoding="utf-8"))["companies"]
        found = [
            Candidate(int(r["cik"]), int(r["months_of_cash"]), date.fromisoformat(r["catalyst"]), str(r["kind"]))
            for r in rows
        ]
    except (ValueError, KeyError, TypeError) as exc:
        raise RulesError(f"{files[-1].name} is not a file of inputs for the Rules fund ({type(exc).__name__})") from exc
    return files[-1].name, found


def select(candidates: list[Candidate], covered: set[int], today: date) -> list[int]:
    """The companies the fund holds from this draw on: nearest catalyst first, at most 20."""
    horizon = today + timedelta(days=CATALYST_WITHIN_DAYS)
    fit = [
        c
        for c in candidates
        if c.cik in covered
        and c.months_of_cash >= MIN_MONTHS_OF_CASH
        and c.kind in KINDS
        and today < c.catalyst <= horizon
    ]
    best: dict[int, Candidate] = {}
    for c in sorted(fit, key=lambda c: (c.catalyst, c.cik)):
        best.setdefault(c.cik, c)
    return [c.cik for c in sorted(best.values(), key=lambda c: (c.catalyst, c.cik))][:MOST]

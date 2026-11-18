"""Read a company's reported number of shares from the files stored by `bobby-archive sec-shares`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from .read_sec import ReadError


@dataclass(frozen=True)
class ShareCount:
    shares: float
    as_of: date  # the day the company counted its shares
    filed: date  # the day the report was filed
    form: str
    source: str  # "cover page" or "balance sheet"
    note: str = ""


SOURCE_NAMES = {"dei": "cover page", "us-gaap": "balance sheet", "weighted": "average over the period"}


def newest(body: bytes, key: str) -> ShareCount | None:
    """The newest share count in one stored answer, or None when it holds no usable figure.

    A company with several share classes can report several figures for one day in one report; these are added
    up, and the note says so. For the average over a period ("weighted") nothing is added up: of the figures
    that end on the newest day, the one over the shortest period is taken (the quarter, not the year so far)."""
    try:
        doc = json.loads(body)
        facts = []
        for unit, rows in doc["units"].items():
            if unit != "shares":
                continue
            for row in rows:
                value = row.get("val")
                if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
                    as_of, filed = date.fromisoformat(str(row["end"])), date.fromisoformat(str(row["filed"]))
                    span = (as_of - date.fromisoformat(str(row["start"]))).days if row.get("start") else 0
                    facts.append(
                        (as_of, filed, str(row.get("accn") or ""), float(value), str(row.get("form") or ""), span)
                    )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ReadError(f"a share-count file is not the expected JSON ({type(exc).__name__})") from exc
    if not facts:
        return None
    as_of, filed, accn, _, form, _ = max(facts, key=lambda f: (f[0], f[1], f[2]))
    same = [f for f in facts if f[0] == as_of and f[2] == accn]
    if key == "weighted":
        shortest = min(same, key=lambda f: f[5])
        note = "average number of shares over the reported period, not a count on one day"
        return ShareCount(shortest[3], as_of, filed, form, SOURCE_NAMES[key], note)
    values = sorted({f[3] for f in same})
    note = f"{len(values)} figures for that day added up (share classes)" if len(values) > 1 else ""
    return ShareCount(sum(values), as_of, filed, form, SOURCE_NAMES.get(key, key), note)

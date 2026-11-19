"""Which companies get a deep analysis today, and in which order (docs/SPEC.md section 1):

1. companies a fund holds that have news;
2. other companies the screening flagged;
3. companies with a catalyst on our calendar within 60 days, nearest first;
4. the rest of the universe in rotation, so that every company gets a first report.

Holdings come first because a missed sell signal costs most. A session analyses at most four companies, or two
on a day with weekly or monthly extras.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..archive.store import sha256_hex
from ..log.store import Entry

MOST = 4
MOST_WITH_EXTRAS = 2
CATALYST_DAYS = 60


def rotation(companies: set[int]) -> list[int]:
    """A fixed order of the universe that favours no letter of the alphabet and no size: by the fingerprint of
    the company's SEC number. The same list every day; the rotation walks through it."""
    return sorted(companies, key=lambda cik: (sha256_hex(f"bobby rotation\n{cik}".encode("ascii")), cik))


def calendar_from_forecasts(entries: list[Entry], today: date) -> dict[int, date]:
    """Until our own catalyst calendar exists (stream 5): the dated events of our open forecasts. Company ->
    its nearest date within 60 days."""
    resolved = {e.record["ref"] for e in entries if e.kind == "outcome"}
    horizon = today + timedelta(days=CATALYST_DAYS)
    found: dict[int, date] = {}
    for e in entries:
        if e.kind != "forecast" or e.seq in resolved:
            continue
        when = date.fromisoformat(e.record["by_date"])
        cik = e.record["company"]["cik"]
        if today <= when <= horizon and (cik not in found or when < found[cik]):
            found[cik] = when
    return found


def deep_order(
    *,
    universe: set[int],
    held_with_news: set[int],
    flagged: list[int],
    catalysts: dict[int, date],
    last_report: dict[int, date],
    limit: int = MOST,
) -> list[tuple[int, str]]:
    """The companies to analyse today, with the reason each is on the list. `flagged`: what the screening said
    yes to, most urgent first. `last_report`: company -> the day of its newest report (missing: none yet)."""
    order = rotation(universe)
    place = {cik: i for i, cik in enumerate(order)}
    chosen: list[tuple[int, str]] = []
    seen: set[int] = set()

    def take(ciks: list[int], why: str) -> None:
        for cik in ciks:
            if cik in universe and cik not in seen:
                seen.add(cik)
                chosen.append((cik, why))

    take(sorted(held_with_news, key=lambda c: place.get(c, len(place))), "a fund holds it and there is news")
    take(flagged, "the screening flagged it")
    take(
        sorted((c for c in catalysts if c in universe), key=lambda c: (catalysts[c], place[c])),
        "a catalyst within 60 days",
    )
    without = [c for c in order if c not in last_report]
    take(without, "rotation: no report yet")
    take(
        sorted((c for c in order if c in last_report), key=lambda c: (last_report[c], place[c])),
        "rotation: oldest report",
    )
    return chosen[:limit]

"""Fetch daily prices and the list of share splits, and store them exactly as received (docs/decisions/0007).

One request gives the whole US market for one day, with prices as they were traded (not recalculated afterwards
for share splits). The free plan allows five requests a minute and two years of history. The key travels in a
request header, never in an address: addresses are stored and printed, headers are not.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..archive.fetch import Fetcher, FetchError
from ..archive.sources import SourceError
from ..archive.store import Archive

DAILY_SOURCE = "massive-daily"
SPLITS_SOURCE = "massive-splits"
CLIENT_NAME = "public-data-archiver/0.1"
HOSTS = frozenset({"api.massive.com"})
DAILY_URL = "https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/{day}?adjusted=false"
SPLITS_URL = "https://api.massive.com/stocks/v1/splits?execution_date.gte={start}&limit=5000&sort=execution_date.asc"
PAUSE = 13.0  # seconds before every request: under five requests a minute
HISTORY_DAYS = 730  # the free plan offers two years
# The oldest days of those two years can already be out of reach; a refusal there is noted, not a failure.
HISTORY_EDGE_DAYS = 10
# A working day without prices is a market holiday, or a day whose prices are not out yet. For this many days it is
# asked again; after that it counts as a holiday for good.
EMPTY_IS_FINAL_AFTER_DAYS = 4
DAILY_LOOKBACK_DAYS = 14  # the morning job also fills gaps of the last two weeks
MAX_SPLIT_PAGES = 50
MARKET_ZONE = ZoneInfo("America/New_York")


def massive_fetcher(key: str, *, allowed_hosts: frozenset[str] = HOSTS, **kwargs: Any) -> Fetcher:
    """A fetcher that carries the key as a header, and only ever asks the price service's own host."""
    return Fetcher(
        user_agent=CLIENT_NAME, allowed_hosts=allowed_hosts, headers={"Authorization": f"Bearer {key}"}, **kwargs
    )


def market_today(now: datetime | None = None) -> date:
    """Today's date where the market is (New York)."""
    return (now or datetime.now(UTC)).astimezone(MARKET_ZONE).date()


def day_name(day: date) -> str:
    return f"grouped-{day.isoformat()}.json"


def name_day(name: str) -> date | None:
    if not (name.startswith("grouped-") and name.endswith(".json")):
        return None
    try:
        return date.fromisoformat(name[len("grouped-") : -len(".json")])
    except ValueError:
        return None


def _get(fetcher: Fetcher, url: str, pause: float) -> Any:
    fetcher.sleep(pause)
    return fetcher.get(url, retry_refused=False)  # "too many requests" ends the job; no quick second try


def _notes(records: list[dict[str, Any]], key: str) -> set[date]:
    found: set[date] = set()
    for r in records:
        if r.get("source") == DAILY_SOURCE and r.get("kind") == "run" and r.get("status") == "note":
            meta = r.get("meta")
            if isinstance(meta, dict) and key in meta:
                try:
                    found.add(date.fromisoformat(str(meta[key])))
                except ValueError:
                    continue
    return found


def stored_days(records: list[dict[str, Any]]) -> set[date]:
    days = set()
    for r in records:
        if r.get("source") == DAILY_SOURCE and r.get("kind") in ("file", "unchanged"):
            day = name_day(str(r.get("name")))
            if day is not None:
                days.add(day)
    return days


def closed_days(records: list[dict[str, Any]]) -> set[date]:
    """Working days on which the market was closed: asked for, and without prices for good."""
    return _notes(records, "closed_day")


def _working_days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)


def check_day(body: bytes, day: date) -> int:
    """Check that `body` is the service's answer for `day` with unadjusted prices. Returns the number of shares
    in it (0: no prices for that day). Raises SourceError for anything else; such an answer is never stored."""
    try:
        doc = json.loads(body)
        if not isinstance(doc, dict) or doc.get("status") != "OK":
            raise ValueError("no OK status")
        if doc.get("adjusted") is not False:
            raise ValueError("prices are not marked as unadjusted")
        results = doc.get("results") or []
        if not isinstance(results, list) or int(doc.get("resultsCount", -1)) != len(results):
            raise ValueError("the count does not match the list")
        days = set()
        for row in results:
            if not isinstance(row["T"], str) or not row["T"]:
                raise ValueError("a line without a ticker")
            days.add(datetime.fromtimestamp(int(row["t"]) / 1000, UTC).astimezone(MARKET_ZONE).date())
    except (ValueError, KeyError, TypeError, OverflowError, OSError) as exc:
        raise SourceError(f"the answer for {day} is not the expected price list ({exc})") from None
    if days - {day}:
        raise SourceError(f"the answer for {day} holds prices of another day")
    return len(results)


def run_days(
    archive: Archive,
    fetcher: Fetcher,
    run: str,
    *,
    start: date,
    end: date,
    today: date,
    url: str = DAILY_URL,
    pause: float = PAUSE,
    limit: int | None = None,
    keep_going: Callable[[], bool] = lambda: True,
) -> dict[str, Any]:
    """Store the price file of every working day from `start` to `end` that is not stored yet.

    Nothing is fetched twice, so an interrupted run is continued by simply running it again. `limit` stops after
    that many requests; `keep_going` answering False stops before the next request.
    """
    have = stored_days(archive.records)
    skip = have | closed_days(archive.records) | _notes(archive.records, "outside_history")
    todo = [d for d in _working_days(start, end) if d not in skip]
    asked = stored = closed = empty = outside = 0
    new_days: list[str] = []
    for day in todo:
        if (limit is not None and asked >= limit) or not keep_going():
            break
        address = url.format(day=day.isoformat())
        asked += 1
        try:
            resp = _get(fetcher, address, pause)
        except FetchError as exc:
            if exc.status == 403 and (today - day).days >= HISTORY_DAYS - HISTORY_EDGE_DAYS:
                # The oldest edge of the two years: the service no longer hands this day out. Not asked again.
                archive.record_run(DAILY_SOURCE, run, "note", meta={"outside_history": day.isoformat()})
                outside += 1
                continue
            raise  # a refusal or a broken connection stops the job; running it again continues
        count = check_day(resp.body, day)
        if count == 0:
            final = (today - day).days > EMPTY_IS_FINAL_AFTER_DAYS
            archive.record_run(
                DAILY_SOURCE, run, "note", meta={("closed_day" if final else "empty_day"): day.isoformat()}
            )
            closed += final
            empty += not final
            continue
        archive.store(
            DAILY_SOURCE,
            day_name(day),
            resp.body,
            run=run,
            compress=True,
            dedup=False,
            info={
                "url": address,
                "status": resp.status,
                "headers": resp.headers,
                "meta": {"day": day.isoformat(), "shares": count},
            },
        )
        stored += 1
        new_days.append(day.isoformat())
    left = len(todo) - asked
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "asked": asked,
        "stored": stored,
        "new_days": new_days,
        "market_closed": closed,
        "no_prices_yet": empty,
        "outside_history": outside,
        "had_already": len([d for d in _working_days(start, end) if d in have]),
        "left": left,
        "complete": left == 0,
    }


def check_splits(body: bytes) -> tuple[int, str | None]:
    """Check one page of the split list. Returns the number of lines and the address of the next page, if any."""
    try:
        doc = json.loads(body)
        if not isinstance(doc, dict) or doc.get("status") != "OK":
            raise ValueError("no OK status")
        results = doc.get("results") or []
        if not isinstance(results, list):
            raise ValueError("no list")
        for row in results:
            date.fromisoformat(str(row["execution_date"]))
            if not isinstance(row["ticker"], str) or float(row["split_from"]) <= 0 or float(row["split_to"]) <= 0:
                raise ValueError("a line that is not a split")
        next_url = doc.get("next_url")
        if next_url is not None and not isinstance(next_url, str):
            raise ValueError("a strange next page")
    except (ValueError, KeyError, TypeError) as exc:
        raise SourceError(f"the answer is not the expected list of share splits ({exc})") from None
    return len(results), next_url


def run_splits(
    archive: Archive, fetcher: Fetcher, run: str, *, start: date, url: str = SPLITS_URL, pause: float = PAUSE
) -> dict[str, Any]:
    """Store the list of share splits from `start` on (announced future ones included), page by page.

    The pages of one run belong together: a reader takes all pages of the newest run that finished."""
    address: str | None = url.format(start=start.isoformat())
    page = total = 0
    while address is not None:
        page += 1
        if page > MAX_SPLIT_PAGES:
            raise SourceError(f"the split list did not end after {MAX_SPLIT_PAGES} pages")
        if "apikey" in address.lower():
            raise SourceError("the address of the next page carries a key; not fetched and not stored")
        resp = _get(fetcher, address, pause)
        count, next_url = check_splits(resp.body)
        archive.store(
            SPLITS_SOURCE,
            f"splits-p{page:02d}.json",
            resp.body,
            run=run,
            compress=True,
            dedup=True,
            info={
                "url": address,
                "status": resp.status,
                "headers": resp.headers,
                "meta": {"page": page, "from": start.isoformat(), "splits": count},
            },
        )
        total += count
        address = next_url
    return {"from": start.isoformat(), "pages": page, "splits": total}

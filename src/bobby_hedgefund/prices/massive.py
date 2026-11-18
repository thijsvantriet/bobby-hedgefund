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
from . import holidays

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
# A day with far fewer shares than the days around it was probably fetched while the service was still filling it.
THIN_SHARE = 0.8  # of the usual number of shares in a day's file
THIN_NEEDS_DAYS = 5  # stored days needed nearby before "usual" means anything
THIN_WINDOW_DAYS = 30
# An HTTP answer that says something about one day only; the job notes it and goes on with the next day.
ONE_DAY_STATUS = frozenset({400, 404})
DAILY_LOOKBACK_DAYS = 14  # the morning job also fills gaps of the last two weeks
MAX_SPLIT_PAGES = 50
MARKET_ZONE = ZoneInfo("America/New_York")
# The service marks the newest day "DELAYED" for some hours and "OK" after that. A delayed copy is complete enough
# to use and is stored, marked; the day is asked again on later runs, and the copy marked OK is stored next to it
# (stored files are never replaced; readers take the newest copy of a day).
OK, DELAYED = "OK", "DELAYED"


def massive_fetcher(
    key: str, *, allowed_hosts: frozenset[str] = HOSTS, https_only: bool = True, **kwargs: Any
) -> Fetcher:
    """A fetcher that carries the key as a header, and only ever asks the price service's own host, encrypted."""
    return Fetcher(
        user_agent=CLIENT_NAME,
        allowed_hosts=allowed_hosts,
        https_only=https_only,
        headers={"Authorization": f"Bearer {key}"},
        **kwargs,
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


def _noted_days(records: list[dict[str, Any]], key: str) -> list[date]:
    """The days of all notes with this key, one entry per note."""
    found: list[date] = []
    for r in records:
        if r.get("source") == DAILY_SOURCE and r.get("kind") == "run" and r.get("status") == "note":
            meta = r.get("meta")
            if isinstance(meta, dict) and key in meta:
                try:
                    found.append(date.fromisoformat(str(meta[key])))
                except ValueError:
                    continue
    return found


def stored_days(records: list[dict[str, Any]], *, final_only: bool = False) -> set[date]:
    """Days with a stored price file. `final_only`: leave out days of which only a copy marked "delayed" by the
    service is stored (the newest day, in the first hours after it becomes available)."""
    days = set()
    for r in records:
        if r.get("source") == DAILY_SOURCE and r.get("kind") in ("file", "unchanged"):
            day = name_day(str(r.get("name")))
            meta = r.get("meta")
            delayed = isinstance(meta, dict) and meta.get("service_status") == DELAYED
            if day is not None and not (final_only and delayed):
                days.add(day)
    return days


def closed_days(records: list[dict[str, Any]], today: date) -> set[date]:
    """Working days on which the market was closed: the service had no prices for them, and that is settled.

    Settled means: the day is more than a few days old, and either it is a regular market holiday, or the service
    gave the same empty answer in two separate runs (a single empty answer can be a hiccup of the service)."""
    answers: dict[date, int] = {}
    for key in ("empty_day", "closed_day"):  # "closed_day" is the name the first version of this job wrote
        for day in _noted_days(records, key):
            answers[day] = answers.get(day, 0) + 1
    return {
        day
        for day, n in answers.items()
        if (today - day).days > EMPTY_IS_FINAL_AFTER_DAYS and (n >= 2 or holidays.is_regular_holiday(day))
    }


def unexpected_closed_days(records: list[dict[str, Any]], today: date) -> list[date]:
    """Settled closed days that are not a regular holiday: worth one look by a person."""
    return sorted(d for d in closed_days(records, today) if not holidays.is_regular_holiday(d))


def _usual_shares(records: list[dict[str, Any]], day: date) -> float | None:
    """The middle number of shares in the stored files of the days around `day`; None with too few of them."""
    counts = []
    for r in records:
        if r.get("source") == DAILY_SOURCE and r.get("kind") == "file" and isinstance(r.get("meta"), dict):
            other = name_day(str(r.get("name")))
            n = r["meta"].get("shares")
            if other is not None and isinstance(n, int) and abs((other - day).days) <= THIN_WINDOW_DAYS:
                counts.append(n)
    if len(counts) < THIN_NEEDS_DAYS:
        return None
    counts.sort()
    return float(counts[len(counts) // 2])


def _working_days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)


def check_day(body: bytes, day: date) -> tuple[int, str]:
    """Check that `body` is the service's answer for `day` with unadjusted prices. Returns the number of shares
    in it (0: no prices for that day) and the service's status, "OK" or "DELAYED". Raises SourceError for
    anything else; such an answer is never stored."""
    try:
        doc = json.loads(body)
        if not isinstance(doc, dict) or doc.get("status") not in (OK, DELAYED):
            raise ValueError("neither an OK nor a DELAYED status")
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
    return len(results), str(doc["status"])


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
    stored_now: list[date] | None = None,
) -> dict[str, Any]:
    """Store the price file of every working day from `start` to `end` that is not stored yet.

    Nothing is fetched twice, so an interrupted run is continued by simply running it again. `limit` stops after
    that many requests; `keep_going` answering False stops before the next request. Each day that is stored is
    added to `stored_now` at once, so the caller knows them also when a later day stops the run.

    A wrong answer for one day is noted and the job goes on with the next day; at the end the run fails, so that
    it is noticed. A refusal ("too many requests", "forbidden") or a broken connection stops the job at once.
    """
    have = stored_days(archive.records)
    # A day of which only a delayed copy is stored is asked again while it is fresh, for the final copy.
    final = stored_days(archive.records, final_only=True)
    settled = final | {d for d in have if (today - d).days > EMPTY_IS_FINAL_AFTER_DAYS}
    skip = settled | closed_days(archive.records, today) | set(_noted_days(archive.records, "outside_history"))
    todo = [d for d in _working_days(start, end) if d not in skip]
    asked = stored = empty = outside = thin = delayed = 0
    failed: list[str] = []
    for day in todo:
        if (limit is not None and asked >= limit) or not keep_going():
            break
        address = url.format(day=day.isoformat())
        age = (today - day).days
        asked += 1
        try:
            resp = _get(fetcher, address, pause)
            count, service_status = check_day(resp.body, day)
        except FetchError as exc:
            if exc.status == 403 and age >= HISTORY_DAYS - HISTORY_EDGE_DAYS:
                # The oldest edge of the two years: the service no longer hands this day out. Not asked again.
                archive.record_run(DAILY_SOURCE, run, "note", meta={"outside_history": day.isoformat()})
                outside += 1
                continue
            if exc.status not in ONE_DAY_STATUS:
                raise  # a refusal or a broken connection stops the job; running it again continues
            archive.record_run(DAILY_SOURCE, run, "note", meta={"failed_day": day.isoformat()}, error=str(exc))
            failed.append(day.isoformat())
            continue
        except SourceError as exc:
            archive.record_run(DAILY_SOURCE, run, "note", meta={"failed_day": day.isoformat()}, error=str(exc))
            failed.append(day.isoformat())
            continue
        if count == 0:
            # A holiday, or prices that are not out yet, or a hiccup: `closed_days` decides when it is settled.
            archive.record_run(DAILY_SOURCE, run, "note", meta={"empty_day": day.isoformat()})
            empty += 1
            continue
        usual = _usual_shares(archive.records, day)
        is_thin = usual is not None and count < THIN_SHARE * usual
        if is_thin and age <= EMPTY_IS_FINAL_AFTER_DAYS:
            # Probably still being filled by the service: not stored, asked again on the next run.
            archive.record_run(DAILY_SOURCE, run, "note", meta={"thin_day": day.isoformat(), "shares": count})
            thin += 1
            continue
        meta: dict[str, Any] = {"day": day.isoformat(), "shares": count}
        if is_thin:
            meta["thin"] = True  # an old day that stays thin is stored as it is, and marked
        if service_status == DELAYED:
            meta["service_status"] = DELAYED
            delayed += 1
        rec = archive.store(
            DAILY_SOURCE,
            day_name(day),
            resp.body,
            run=run,
            compress=True,
            dedup=True,  # the same delayed copy again is not stored twice
            info={"url": address, "status": resp.status, "headers": resp.headers, "meta": meta},
        )
        if rec["kind"] == "file":
            stored += 1
            if stored_now is not None and day not in stored_now:
                stored_now.append(day)
    left = len(todo) - asked
    summary = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "asked": asked,
        "stored": stored,
        "of_which_marked_delayed": delayed,
        "no_prices": empty,
        "too_few_shares_asked_again_later": thin,
        "outside_history": outside,
        "had_already": len([d for d in _working_days(start, end) if d in have]),
        "left": left,
        # Complete: every working day in the range is stored or settled as a day without trading.
        "complete": left == 0 and not failed and thin == 0 and not _open_days(archive.records, start, end, today),
    }
    if failed:
        raise SourceError(
            f"wrong answer for {len(failed)} day(s): {', '.join(failed[:5])}; the rest went on: {summary}"
        )
    return summary


def _open_days(records: list[dict[str, Any]], start: date, end: date, today: date) -> list[date]:
    settled = stored_days(records) | closed_days(records, today) | set(_noted_days(records, "outside_history"))
    return [d for d in _working_days(start, end) if d not in settled]


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
        secrets = [v.split()[-1] for v in fetcher.headers.values() if v.split()]
        if "apikey" in address.lower() or any(secret in address for secret in secrets):
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

"""SEC filings of the companies in the universe (stream 2; docs/decisions/0008): each company's filing list, and
every new filing of the form types we follow as the one complete text file, stored exactly as received.

Same rules as the other SEC requests: the declared header, at most one request a second, a refusal stops the job.
Runs every night after the other archive sources, and by hand for the first fetch.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from typing import Any

from ..prices.holidays import is_regular_holiday
from .fetch import Fetcher, FetchError, ResponseTooLarge
from .sec import MAX_ODD_IN_A_ROW, SEC_PAUSE, SEC_SUBMISSIONS_URL, _get, submissions_name
from .sources import SourceError
from .store import Archive

FILINGS_SOURCE = "sec-filings"
INDEX_SOURCE = "sec-index"
# The complete filing as one text file: all its documents in one. Under /Archives/edgar/data, which the SEC's
# robots file allows and its "Accessing EDGAR Data" page describes for automated use.
SEC_FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}.txt"
SEC_DAILY_INDEX_URL = "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/master.{day:%Y%m%d}.idx"
# A filing the SEC's list names can be missing from the file store for a short while. It is asked again on later
# runs; after this many "not found" answers it is left alone.
NOT_FOUND_IS_FINAL_AFTER = 3
_ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}", re.ASCII)
# Event reports; share sales (shelf registrations and their supplements); insider trades; holders of more than
# 5%, under the old and the new form names; quarterly and yearly reports (for stream 4). Amendments included.
FOLLOWED_FORMS = frozenset(
    {"8-K", "S-3", "S-3ASR", "424B5", "4", "SC 13D", "SC 13G", "SCHEDULE 13D", "SCHEDULE 13G", "10-Q", "10-K"}
)
# Filings from this day on are fetched. Earlier ones are not: the first fetch must stay a modest number of requests.
FILINGS_FROM = date(2026, 9, 1)


def followed(form: str) -> bool:
    return form.strip().upper().removesuffix("/A") in FOLLOWED_FORMS


def filing_name(accession: str) -> str:
    return f"filing-{accession}.txt"


def recent_filings(body: bytes, cik: int) -> list[dict[str, str]]:
    """The filings in a company's filing list, newest first: accession number, form, filing day, acceptance time.
    Raises ValueError when the file is not this company's filing list."""
    doc = json.loads(body)
    if int(doc["cik"]) != cik:
        raise ValueError("another company's filing list")
    recent = doc["filings"]["recent"]
    numbers, forms, days = recent["accessionNumber"], recent["form"], recent["filingDate"]
    accepted = recent.get("acceptanceDateTime") or [""] * len(numbers)
    if not (len(numbers) == len(forms) == len(days) == len(accepted)):
        raise ValueError("columns of different length")
    out = []
    for number, form, day, when in zip(numbers, forms, days, accepted, strict=True):
        number = str(number)
        # The number becomes part of an address and of a file name: only the SEC's own form is accepted.
        if not _ACCESSION.fullmatch(number):
            raise ValueError("an accession number in an unexpected form")
        date.fromisoformat(str(day))
        out.append({"accession": number, "form": str(form), "filed": str(day), "accepted": str(when)})
    return out


def stored_accessions(archive: Archive) -> set[str]:
    """Filings that are really stored."""
    found = set()
    for r in archive.records:
        meta = r.get("meta")
        if r.get("source") != FILINGS_SOURCE or r.get("kind") not in ("file", "unchanged"):
            continue
        if isinstance(meta, dict) and "accession" in meta:
            found.add(str(meta["accession"]))
    return found


def given_up(archive: Archive) -> set[str]:
    """Filings that are not asked for again: "not found" several times, or too large to fetch."""
    counts: dict[str, int] = {}
    for r in archive.records:
        meta = r.get("meta")
        if r.get("source") != FILINGS_SOURCE or r.get("status") != "note" or not isinstance(meta, dict):
            continue
        if meta.get("too_large"):
            counts[str(meta.get("accession"))] = NOT_FOUND_IS_FINAL_AFTER
        elif meta.get("not_found") and "accession" in meta:
            counts[str(meta["accession"])] = counts.get(str(meta["accession"]), 0) + 1
    return {accession for accession, n in counts.items() if n >= NOT_FOUND_IS_FINAL_AFTER}


def run_sec_filings(
    archive: Archive,
    fetcher: Fetcher,
    run: str,
    *,
    ciks: list[int],
    since: date = FILINGS_FROM,
    submissions_url: str = SEC_SUBMISSIONS_URL,
    filing_url: str = SEC_FILING_URL,
    limit: int | None = None,
    pause: float = SEC_PAUSE,
    keep_going: Callable[[], bool] = lambda: True,
) -> dict[str, Any]:
    """For each company: store its filing list (when it changed), then every followed filing from `since` on that
    is not stored yet. `limit` stops after that many requests in all; `keep_going` answering False stops before
    the next request. Nothing is fetched twice, so a run that stopped is continued by running it again."""
    have = stored_accessions(archive) | given_up(archive)
    asked = lists = filings = not_found = too_large = odd = odd_in_a_row = companies_done = 0
    by_form: dict[str, int] = {}

    def may_ask() -> bool:
        return (limit is None or asked < limit) and keep_going()

    stopped = False
    for cik in sorted(set(ciks)):
        if not may_ask():
            stopped = True
            break
        url = submissions_url.format(cik=cik)
        asked += 1
        try:
            resp = _get(fetcher, url, pause)
            listed = recent_filings(resp.body, cik)
        except FetchError as exc:
            if exc.status != 404:
                raise  # a refusal or a broken connection stops the job
            archive.record_run(FILINGS_SOURCE, run, "note", meta={"cik": cik, "no_filing_list": True})
            not_found += 1
            continue
        except (ValueError, KeyError, TypeError):
            archive.record_run(FILINGS_SOURCE, run, "note", meta={"cik": cik, "odd": True})
            odd += 1
            odd_in_a_row += 1
            if odd_in_a_row >= MAX_ODD_IN_A_ROW:
                raise SourceError(f"{odd_in_a_row} answers in a row were not filing lists; stopped") from None
            continue
        odd_in_a_row = 0
        # Kept apart from the monthly company files (source "sec"): those belong to batches of the whole market.
        archive.store(
            FILINGS_SOURCE,
            submissions_name(cik),
            resp.body,
            run=run,
            compress=True,
            dedup=True,
            info={"url": url, "status": resp.status, "headers": resp.headers, "meta": {"cik": cik}},
        )
        lists += 1
        wanted = [
            f for f in listed if followed(f["form"]) and f["filed"] >= since.isoformat() and f["accession"] not in have
        ]
        complete = True
        for filing in reversed(wanted):  # oldest first
            if not may_ask():
                complete = False
                break
            address = filing_url.format(cik=cik, accession=filing["accession"])
            meta = {"cik": cik, **filing}
            asked += 1
            try:
                resp = _get(fetcher, address, pause)
            except ResponseTooLarge:
                # Asking again gives the same: noted once, never asked again, and the job goes on.
                archive.record_run(FILINGS_SOURCE, run, "note", meta={**meta, "too_large": True})
                have.add(filing["accession"])
                too_large += 1
                continue
            except FetchError as exc:
                if exc.status != 404:
                    raise  # a refusal or a broken connection stops the job
                # Asked again on later runs; `given_up` decides when it is left alone.
                archive.record_run(FILINGS_SOURCE, run, "note", meta={**meta, "not_found": True})
                not_found += 1
                continue
            first_line = resp.body[:300].split(b"\n", 1)[0]
            if not (resp.body.startswith(b"<SEC-DOCUMENT>") and filing["accession"].encode() in first_line):
                # Not this filing (for example a "please wait" page with status 200): not stored, asked again
                # on the next run. Many in a row mean the SEC is sending something else altogether: stop.
                archive.record_run(FILINGS_SOURCE, run, "note", meta={**meta, "odd": True})
                odd += 1
                odd_in_a_row += 1
                if odd_in_a_row >= MAX_ODD_IN_A_ROW:
                    raise SourceError(f"{odd_in_a_row} answers in a row were not filings; stopped") from None
                continue
            odd_in_a_row = 0
            archive.store(
                FILINGS_SOURCE,
                filing_name(filing["accession"]),
                resp.body,
                run=run,
                compress=True,
                dedup=True,
                info={"url": address, "status": resp.status, "headers": resp.headers, "meta": meta},
            )
            have.add(filing["accession"])
            filings += 1
            base = filing["form"].strip().upper().removesuffix("/A")
            by_form[base] = by_form.get(base, 0) + 1
        if not complete:
            stopped = True
            break
        companies_done += 1
    return {
        "companies": len(set(ciks)),
        "companies_done": companies_done,
        "since": since.isoformat(),
        "asked": asked,
        "filing_lists": lists,
        "filings_stored": filings,
        "by_form": dict(sorted(by_form.items())),
        "not_found": not_found,
        "too_large": too_large,
        "odd": odd,
        "complete": not stopped and odd == 0 and not_found == 0,
    }


def index_name(day: date) -> str:
    return f"form-{day:%Y%m%d}.idx"


def index_entries(body: bytes) -> list[tuple[str, int, str]]:
    """(form, company number, accession number) for every line of a daily index file (the "master" layout:
    company number | company name | form | day | file name)."""
    lines = body.decode("latin-1").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("-----")) + 1
        if "CIK|Company Name|Form Type|Date Filed|File Name" not in lines[:start]:
            raise StopIteration
    except StopIteration:
        raise SourceError("the daily index does not have the expected table") from None
    out = []
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = line.split("|")
        try:
            cik, form, path = int(parts[0]), parts[-3].strip(), parts[-1].strip()  # a name may hold a "|" itself
            accession = path.rsplit("/", 1)[1].removesuffix(".txt")
        except (IndexError, ValueError):
            raise SourceError("a line of the daily index is not in the expected layout") from None
        out.append((form, cik, accession))
    return out


def run_crosscheck(
    archive: Archive,
    fetcher: Fetcher,
    run: str,
    *,
    ciks: list[int],
    days: list[date],
    since: date = FILINGS_FROM,
    index_url: str = SEC_DAILY_INDEX_URL,
    pause: float = SEC_PAUSE,
) -> dict[str, Any]:
    """Compare what is stored with the SEC's own list of each day's filings (record 0008, point 8). One request
    per day. Weekends and regular market holidays have no index and are not asked for (the SEC answers
    "forbidden" for a missing index, the same answer as a refusal, so such a day cannot be told apart by asking).
    Lists followed filings of our companies that the index names and the archive does not hold."""
    have = stored_accessions(archive)
    ours = set(ciks)
    missing: list[str] = []
    checked = without_index = seen = 0
    for day in days:
        if day < since or day.weekday() >= 5 or is_regular_holiday(day):
            continue
        url = index_url.format(year=day.year, quarter=(day.month - 1) // 3 + 1, day=day)
        try:
            resp = _get(fetcher, url, pause)
        except FetchError as exc:
            if exc.status != 404:  # "forbidden" is a refusal and stops the job, like everywhere else
                raise
            without_index += 1
            continue
        entries = index_entries(resp.body)
        archive.store(
            INDEX_SOURCE,
            index_name(day),
            resp.body,
            run=run,
            compress=True,
            dedup=True,
            info={"url": url, "status": resp.status, "headers": resp.headers, "meta": {"day": day.isoformat()}},
        )
        checked += 1
        for form, cik, accession in entries:
            if cik in ours and followed(form):
                seen += 1
                if accession not in have:
                    missing.append(f"{day.isoformat()} {cik} {form} {accession}")
    summary = {
        "days_checked": checked,
        "days_without_index": without_index,
        "our_filings_in_the_index": seen,
        "missing": len(missing),
        "missing_first": missing[:20],
    }
    if missing:
        raise SourceError(f"{len(missing)} filing(s) in the SEC's daily index are not stored: {summary}")
    return summary

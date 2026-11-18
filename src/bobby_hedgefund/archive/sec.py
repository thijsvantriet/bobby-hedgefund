"""SEC company files for the universe (docs/decisions/0006 and 0008): the ticker file and each listed company's
filing list, stored exactly as received. Run by hand, about once a month; no analysis here.

Rules from record 0008: a declared header (generic client name plus the contact address), at most one request a
second, no parallel requests, and a refusal stops the whole job. The contact address is never written anywhere.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .fetch import Fetcher, FetchError
from .sources import SourceError
from .store import Archive

SEC_SOURCE = "sec"
# The SEC's example form is "Sample Company Name AdminContact@<domain>": a name, a space, the contact address.
SEC_CLIENT_NAME = "public-data-archiver"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_PAUSE = 1.0  # seconds before every request: a tenth of the speed the SEC allows
TICKERS_NAME = "company-tickers-exchange.json"
# Companies without a stock-exchange listing cannot be in the universe; their filing lists are not fetched.
NOT_LISTED = frozenset({"", "OTC"})
# The header declares who is asking; it may only ever reach the SEC's own hosts, also after a redirect.
SEC_HOSTS = frozenset({"www.sec.gov", "data.sec.gov"})
# This many unexpected answers in a row mean the service is sending something else than filing lists: stop.
MAX_ODD_IN_A_ROW = 10


def sec_fetcher(contact: str, *, allowed_hosts: frozenset[str] = SEC_HOSTS, **kwargs: Any) -> Fetcher:
    """A fetcher whose header declares who is asking, in the form the SEC prescribes."""
    return Fetcher(user_agent=f"{SEC_CLIENT_NAME} {contact}", allowed_hosts=allowed_hosts, **kwargs)


def submissions_name(cik: int) -> str:
    return f"submissions-cik{cik:010d}.json"


def _get(fetcher: Fetcher, url: str, pause: float) -> Any:
    fetcher.sleep(pause)
    return fetcher.get(url, retry_refused=False)  # "too many requests" ends the job; no quick second try


def listed_companies(body: bytes) -> list[int]:
    """The company numbers (CIK) in the SEC's ticker file that have a stock-exchange listing, in rising order."""
    try:
        doc = json.loads(body)
        fields = doc["fields"]
        i_cik, i_exchange = fields.index("cik"), fields.index("exchange")
        ciks = {int(row[i_cik]) for row in doc["data"] if str(row[i_exchange] or "").strip() not in NOT_LISTED}
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        raise SourceError(f"the ticker file is not the expected JSON ({type(exc).__name__})") from exc
    if any(cik <= 0 or cik >= 10**10 for cik in ciks):
        raise SourceError("the ticker file holds a company number outside the expected range")
    return sorted(ciks)


def _batch_records(archive: Archive, batch: str) -> list[dict[str, Any]]:
    return [
        r
        for r in archive.records
        if r.get("source") == SEC_SOURCE
        and r.get("kind") in ("file", "unchanged")
        and isinstance(r.get("meta"), dict)
        and r["meta"].get("batch") == batch
    ]


def _unfinished_batch(archive: Archive) -> str | None:
    """The newest batch of company files, unless a run already finished it."""
    batches = [
        r["meta"]["batch"]
        for r in archive.records
        if r.get("source") == SEC_SOURCE and r.get("kind") in ("file", "unchanged") and isinstance(r.get("meta"), dict)
    ]
    if not batches:
        return None
    finished = {
        r["meta"].get("batch")
        for r in archive.records
        if r.get("source") == SEC_SOURCE
        and r.get("kind") == "run"
        and r.get("status") == "ok"
        and isinstance(r.get("meta"), dict)
        and r["meta"].get("complete")
    }
    return None if batches[-1] in finished else batches[-1]


def run_sec_companies(
    archive: Archive,
    fetcher: Fetcher,
    run: str,
    *,
    tickers_url: str = SEC_TICKERS_URL,
    submissions_url: str = SEC_SUBMISSIONS_URL,
    resume: bool = False,
    new: bool = False,
    limit: int | None = None,
    pause: float = SEC_PAUSE,
    keep_going: Callable[[], bool] = lambda: True,
) -> dict[str, Any]:
    """Store the ticker file and the filing list of every listed company in it.

    One batch belongs to one copy of the ticker file. An interrupted batch is continued with `resume`; `limit`
    stops after that many companies, and `keep_going` answering False stops before the next request (the batch
    then stays open for a later `resume`). While a batch is open, a fresh one starts only with `new`.
    """
    batch = run
    if not resume and not new and _unfinished_batch(archive) is not None:
        raise SourceError("an earlier batch of company files is not finished: continue it with --resume (or --new)")
    if resume:
        found = _unfinished_batch(archive)
        if found is None:
            raise SourceError("nothing to resume: no unfinished batch of company files found")
        batch = found
        tickers = [r for r in _batch_records(archive, batch) if r.get("name") == TICKERS_NAME]
        if not tickers:
            raise SourceError("the unfinished batch has no ticker file; start a new one")
        tickers_body = archive.read(tickers[-1])
    else:
        resp = _get(fetcher, tickers_url, pause)
        ciks = listed_companies(resp.body)  # checked before it is stored: a wrong file starts no batch
        archive.store(
            SEC_SOURCE,
            TICKERS_NAME,
            resp.body,
            run=run,
            compress=True,
            dedup=False,  # every batch keeps its own copy: the file shows today's tickers only (record 0006)
            info={"url": tickers_url, "status": resp.status, "headers": resp.headers, "meta": {"batch": batch}},
        )
        tickers_body = resp.body
    ciks = listed_companies(tickers_body)
    done = {r["meta"].get("cik") for r in _batch_records(archive, batch)}
    missing = {r["meta"].get("missing_cik") for r in _missing_notes(archive, batch)}
    todo = [cik for cik in ciks if cik not in done and cik not in missing]
    fetched = not_found = odd = odd_in_a_row = 0
    for cik in todo:
        if (limit is not None and fetched + not_found + odd >= limit) or not keep_going():
            break
        url = submissions_url.format(cik=cik)
        try:
            resp = _get(fetcher, url, pause)
        except FetchError as exc:
            if exc.status != 404:
                raise  # a refusal or a broken connection stops the job; `resume` continues later
            # The ticker file names a company the data service does not know: note it and go on.
            archive.record_run(SEC_SOURCE, run, "note", meta={"batch": batch, "missing_cik": cik})
            not_found += 1
            continue
        try:
            doc = json.loads(resp.body)
            if int(doc["cik"]) != cik or "filings" not in doc:
                raise ValueError("not this company's filing list")
        except (ValueError, KeyError, TypeError):
            # One strange answer must not block the batch for good: note it, do not store it, and go on. It is
            # asked again on the next `resume`. Many in a row mean something else is wrong: then stop.
            archive.record_run(SEC_SOURCE, run, "note", meta={"batch": batch, "odd_cik": cik})
            odd += 1
            odd_in_a_row += 1
            if odd_in_a_row >= MAX_ODD_IN_A_ROW:
                raise SourceError(f"{odd_in_a_row} answers in a row were not filing lists; stopped") from None
            continue
        odd_in_a_row = 0
        archive.store(
            SEC_SOURCE,
            submissions_name(cik),
            resp.body,
            run=run,
            compress=True,
            dedup=True,  # an unchanged filing list is not stored twice (record 0008, point 5)
            info={
                "url": url,
                "status": resp.status,
                "headers": resp.headers,
                "meta": {"batch": batch, "cik": cik},
            },
        )
        fetched += 1
    left = len(todo) - fetched - not_found - odd
    return {
        "batch": batch,
        "listed_companies": len(ciks),
        "fetched": fetched,
        "not_found": not_found,
        "odd": odd,
        "had_already": len(ciks) - len(todo),
        "left": left,
        "complete": left == 0,  # companies with an odd answer are listed in the notes; the batch still counts
    }


def _missing_notes(archive: Archive, batch: str) -> list[dict[str, Any]]:
    return [
        r
        for r in archive.records
        if r.get("source") == SEC_SOURCE
        and r.get("kind") == "run"
        and r.get("status") == "note"
        and isinstance(r.get("meta"), dict)
        and r["meta"].get("batch") == batch
        and "missing_cik" in r["meta"]
    ]

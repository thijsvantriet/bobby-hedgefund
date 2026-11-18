"""Reported share counts for the universe filter (docs/decisions/0006, point 2): for each candidate company, what
the SEC's data service holds for the number of shares on the cover page of its reports. Stored as received.

Same rules as the other SEC requests (record 0008): the declared header, at most one request a second, a refusal
stops the job. Run by hand, about once a month, after `sec-companies`; no analysis here.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .fetch import Fetcher, FetchError
from .sec import MAX_ODD_IN_A_ROW, SEC_PAUSE, _get
from .sources import SourceError
from .store import Archive

SHARES_SOURCE = "sec-shares"
SEC_CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/{taxonomy}/{tag}.json"
# Two places where a company reports its number of shares: the cover page of a report, and its balance sheet.
# Both are asked for; the reader takes the newer one. The service only holds figures that a company reports for
# the company as a whole, so a company that reports each share class apart may have neither.
CONCEPTS = (("dei", "EntityCommonStockSharesOutstanding"), ("us-gaap", "CommonStockSharesOutstanding"))


def shares_name(cik: int, taxonomy: str) -> str:
    return f"shares-{taxonomy}-cik{cik:010d}.json"


# This many "not found" answers in a row mean the address is wrong or the service moved, not that all these
# companies report nothing: stop, and do not count those answers.
MAX_NOT_FOUND_IN_A_ROW = 50


def _batch_metas(archive: Archive, batch: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [
        (r, r["meta"])
        for r in archive.records
        if r.get("source") == SHARES_SOURCE and isinstance(r.get("meta"), dict) and r["meta"].get("batch") == batch
    ]


def not_reported(archive_records: list[dict[str, Any]], batch: str) -> set[tuple[int, str]]:
    """(company, taxonomy) pairs for which the service answered "not found" in this batch. Answers of a run that
    was stopped for too many of them in a row do not count."""
    metas = [
        (r, r["meta"])
        for r in archive_records
        if r.get("source") == SHARES_SOURCE and isinstance(r.get("meta"), dict) and r["meta"].get("batch") == batch
    ]
    void = {m.get("void_run") for _, m in metas if m.get("void_run")}
    found: set[tuple[int, str]] = set()
    for r, m in metas:
        if r.get("status") == "note" and m.get("not_reported") is True and r.get("run") not in void:
            found.add((int(m["cik"]), str(m["taxonomy"])))
    return found


def batch_complete(archive_records: list[dict[str, Any]], batch: str) -> bool:
    """True when a run finished this batch: every company was asked for both figures."""
    return any(
        r.get("source") == SHARES_SOURCE
        and r.get("kind") == "run"
        and r.get("status") == "ok"
        and isinstance(r.get("meta"), dict)
        and r["meta"].get("batch") == batch
        and r["meta"].get("complete") is True
        for r in archive_records
    )


def _done(archive: Archive, batch: str) -> set[tuple[int, str]]:
    """(company, taxonomy) pairs this batch already has an answer for: a stored file, or a note "not there"."""
    done: set[tuple[int, str]] = set(not_reported(archive.records, batch))
    for r, meta in _batch_metas(archive, batch):
        if r.get("kind") in ("file", "unchanged"):
            try:
                done.add((int(meta["cik"]), str(meta["taxonomy"])))
            except (KeyError, TypeError, ValueError):
                continue
    return done


def run_sec_shares(
    archive: Archive,
    fetcher: Fetcher,
    run: str,
    *,
    ciks: list[int],
    batch: str,
    concept_url: str = SEC_CONCEPT_URL,
    limit: int | None = None,
    pause: float = SEC_PAUSE,
    keep_going: Callable[[], bool] = lambda: True,
) -> dict[str, Any]:
    """Store the reported share counts of every company in `ciks`.

    `batch` names the candidate list the companies come from. An answer that this batch already has is not asked
    for again, so an interrupted run is continued by running it again. `limit` stops after that many requests;
    `keep_going` answering False stops before the next request.
    """
    done = _done(archive, batch)
    todo = [
        (cik, taxonomy, tag) for cik in sorted(set(ciks)) for taxonomy, tag in CONCEPTS if (cik, taxonomy) not in done
    ]
    asked = stored = missing = odd = odd_in_a_row = missing_in_a_row = 0
    for cik, taxonomy, tag in todo:
        if (limit is not None and asked >= limit) or not keep_going():
            break
        url = concept_url.format(cik=cik, taxonomy=taxonomy, tag=tag)
        meta = {"batch": batch, "cik": cik, "taxonomy": taxonomy}
        asked += 1
        try:
            resp = _get(fetcher, url, pause)
        except FetchError as exc:
            if exc.status != 404:
                raise  # a refusal or a broken connection stops the job; running it again continues
            # The company does not report this figure for the company as a whole: note it, do not ask again.
            archive.record_run(SHARES_SOURCE, run, "note", meta={**meta, "not_reported": True})
            missing += 1
            missing_in_a_row += 1
            if missing_in_a_row >= MAX_NOT_FOUND_IN_A_ROW:
                archive.record_run(SHARES_SOURCE, run, "note", meta={"batch": batch, "void_run": run})
                raise SourceError(
                    f"{missing_in_a_row} answers in a row were 'not found': the address may be wrong. Stopped; "
                    "the 'not found' answers of this run are not counted"
                ) from None
            continue
        missing_in_a_row = 0
        try:
            doc = json.loads(resp.body)
            right = int(doc["cik"]) == cik and doc["tag"] == tag and doc["taxonomy"] == taxonomy
            if not right or not isinstance(doc["units"], dict):
                raise ValueError("not this company's figure")
        except (ValueError, KeyError, TypeError):
            # A strange answer is not stored and not counted as done: it is asked again on the next run.
            archive.record_run(SHARES_SOURCE, run, "note", meta={**meta, "odd": True})
            odd += 1
            odd_in_a_row += 1
            if odd_in_a_row >= MAX_ODD_IN_A_ROW:
                raise SourceError(f"{odd_in_a_row} answers in a row were not share counts; stopped") from None
            continue
        odd_in_a_row = 0
        archive.store(
            SHARES_SOURCE,
            shares_name(cik, taxonomy),
            resp.body,
            run=run,
            compress=True,
            dedup=True,
            info={"url": url, "status": resp.status, "headers": resp.headers, "meta": meta},
        )
        stored += 1
    left = len(todo) - asked
    return {
        "batch": batch,
        "companies": len(set(ciks)),
        "asked": asked,
        "stored": stored,
        "not_found": missing,
        "odd": odd,
        "had_already": len(set(ciks)) * len(CONCEPTS) - len(todo),
        "left": left,
        "complete": left == 0 and odd == 0,
    }

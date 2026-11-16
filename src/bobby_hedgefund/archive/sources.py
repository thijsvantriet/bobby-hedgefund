"""What the day-1 archive downloads. Terms of each source were checked on 2026-11-16 (docs/decisions/0001).

Adding a source: check its terms of use and robots.txt first (project rule), then add it here.
"""

from __future__ import annotations

import io
import json
import math
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from .fetch import Fetcher, FetchError
from .store import Archive, utcnow


class SourceError(Exception):
    """A source answered, but not with what we expect."""


# -- plain files: one address, one file ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileSource:
    name: str  # file name in the archive
    url: str
    starts_with: tuple[bytes, ...]  # the real file begins with one of these; an error page does not
    min_bytes: int
    compress: bool = True
    last_line: bytes = b""  # the complete file ends with a line that starts like this (guards against cut-off files)


@dataclass(frozen=True)
class FileGroup:
    source: str
    files: tuple[FileSource, ...]
    pause: float  # seconds between two requests to this publisher


_EMA = "https://www.ema.europa.eu/en/documents/report/"
_JSON = (b"{", b"[")

FILE_GROUPS: tuple[FileGroup, ...] = (
    # Nasdaq symbol directory: all listed symbols, with the "financial status" flag (deficient, delinquent, bankrupt).
    FileGroup(
        "nasdaq-symdir",
        (
            FileSource(
                "nasdaqlisted.txt",
                "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
                (b"Symbol|",),
                50_000,
                last_line=b"File Creation Time:",
            ),
            FileSource(
                "otherlisted.txt",
                "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
                (b"ACT Symbol|",),
                50_000,
                last_line=b"File Creation Time:",
            ),
        ),
        pause=2.0,
    ),
    # SPDR S&P Biotech ETF (XBI) daily holdings: the core of the company universe and a benchmark.
    # Kept as a private copy only; State Street's terms do not allow passing the file on.
    FileGroup(
        "ssga-xbi",
        (
            FileSource(
                "holdings-xbi.xlsx",
                "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-xbi.xlsx",
                (b"PK",),
                5_000,
                compress=False,  # an .xlsx file is already compressed
            ),
        ),
        pause=2.0,
    ),
    # European Medicines Agency data files, made by EMA for automated use. EMA answered "too many requests" at one
    # request per second, hence the long pause.
    FileGroup(
        "ema",
        (
            FileSource("medicines.json", _EMA + "medicines-output-medicines_json-report_en.json", _JSON, 100_000),
            FileSource(
                "post-authorisation.json",
                _EMA + "medicines-output-post_authorisation_json-report_en.json",
                _JSON,
                10_000,
            ),
            FileSource(
                "orphan-designations.json",
                _EMA + "medicines-output-orphan_designations-json-report_en.json",
                _JSON,
                100_000,
            ),
            FileSource("referrals.json", _EMA + "referrals-output-json-report_en.json", _JSON, 10_000),
            FileSource(
                "paediatric-investigation-plans.json",
                _EMA + "medicines-output-paediatric_investigation_plans-output-json-report_en.json",
                _JSON,
                10_000,
            ),
        ),
        pause=20.0,
    ),
)


def run_file_group(archive: Archive, fetcher: Fetcher, group: FileGroup, run: str) -> dict[str, Any]:
    """Download and store every file of a group.

    Each file is tried on its own: one that fails or looks wrong never stops the others. At the end a SourceError
    is raised when any file failed or looked wrong, so the run is reported.
    """
    wrong: list[str] = []
    stored = unchanged = 0
    for index, item in enumerate(group.files):
        if index:
            fetcher.sleep(group.pause)
        try:
            resp = fetcher.get(item.url)
        except FetchError as exc:
            wrong.append(f"{item.name}: not downloaded ({exc})")
            continue
        suspect = _looks_wrong(resp.body, item)
        info: dict[str, Any] = {"url": item.url, "status": resp.status, "headers": resp.headers}
        if resp.final_url != item.url:
            info["final_url"] = resp.final_url
        if suspect:
            # Keep what we were given (it is what the publisher showed that day), but flag it and raise the alarm.
            info["suspect"] = suspect
            wrong.append(f"{item.name}: {suspect}")
        rec = archive.store(group.source, item.name, resp.body, run=run, compress=item.compress, info=info)
        if rec["kind"] == "file":
            stored += 1
        else:
            unchanged += 1
    if wrong:
        raise SourceError("; ".join(wrong))
    return {"stored": stored, "unchanged": unchanged}


def _looks_wrong(body: bytes, item: FileSource) -> str | None:
    """Cheap checks that the body is the whole, real file: not an error page and not cut off halfway."""
    if len(body) < item.min_bytes:
        return f"only {len(body)} bytes, expected at least {item.min_bytes}"
    if not body.lstrip()[:20].startswith(item.starts_with):
        return "does not start like the expected file (an error page?)"
    if item.name.endswith(".json"):
        try:
            json.loads(body)
        except ValueError:
            return "is not complete, valid JSON (cut off?)"
    if item.name.endswith(".xlsx"):
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as book:
                damaged = book.testzip()
        except (zipfile.BadZipFile, OSError, ValueError, RuntimeError):
            return "is not a complete spreadsheet file (cut off?)"
        if damaged:
            return f"spreadsheet file is damaged inside ({damaged})"
    if item.last_line:
        lines = body.rstrip().rsplit(b"\n", 1)
        if not lines[-1].startswith(item.last_line):
            return "does not end like the complete file (cut off?)"
    return None


# -- ClinicalTrials.gov: the trial registry, page by page ----------------------------------------------------------

CTGOV_API = "https://clinicaltrials.gov/api/v2"
CTGOV_UPDATES = "ctgov-updates"
CTGOV_BASELINE = "ctgov-baseline"
CTGOV_VERSION = "ctgov-version"
# Trials with a company as lead sponsor or as collaborator. Chosen to limit volume (decision 0001); the records of
# purely academic trials are not saved.
CTGOV_INDUSTRY = "(AREA[LeadSponsorClass]INDUSTRY OR AREA[CollaboratorClass]INDUSTRY)"
CTGOV_PAGE_SIZE = 1000  # the largest page the API gives
CTGOV_PAUSE = 2.0  # robots.txt of the site asks for at least 1 second between requests
CTGOV_LOOKBACK_DAYS = 1
CTGOV_FIRST_RUN_DAYS = 7
# The registry refreshes on working days. This many days without a refresh is not a long weekend any more.
CTGOV_STALE_DAYS = 5


def ctgov_data_timestamp(archive: Archive, fetcher: Fetcher, api: str, run: str) -> str:
    """Ask the registry when its data was last refreshed (it refreshes once per working day)."""
    resp = fetcher.get(f"{api}/version")
    archive.store(
        CTGOV_VERSION,
        "version.json",
        resp.body,
        run=run,
        info={"url": resp.url, "status": resp.status, "headers": resp.headers},
    )
    try:
        stamp = json.loads(resp.body)["dataTimestamp"]
    except (ValueError, KeyError, TypeError) as exc:
        raise SourceError("version answer has no dataTimestamp") from exc
    if not isinstance(stamp, str) or len(stamp) < 10:
        raise SourceError(f"unexpected dataTimestamp: {stamp!r}")
    return stamp


def _stamp_date(stamp: str) -> date:
    try:
        return date.fromisoformat(stamp[:10])
    except ValueError as exc:
        raise SourceError(f"unexpected dataTimestamp: {stamp!r}") from exc


def ctgov_pages(
    archive: Archive,
    fetcher: Fetcher,
    *,
    api: str,
    source: str,
    expr: str,
    run: str,
    batch: str,
    data_timestamp: str,
    page_size: int = CTGOV_PAGE_SIZE,
    start_page: int = 1,
    start_token: str | None = None,
    studies_before: int = 0,
    total_before: int | None = None,
) -> dict[str, Any]:
    """Fetch all result pages for `expr`, store each page exactly as received, and check the count adds up."""
    page = start_page
    token = start_token
    n_studies = studies_before
    total = total_before
    seen_tokens = {token} if token else set()
    while True:
        params = {"filter.advanced": expr, "pageSize": str(page_size)}
        if page == 1:
            params["countTotal"] = "true"
        if token:
            params["pageToken"] = token
        if page > start_page:
            fetcher.sleep(CTGOV_PAUSE)
        url = f"{api}/studies?{urlencode(params)}"
        resp = fetcher.get(url)
        try:
            doc = json.loads(resp.body)
            studies = doc["studies"]
            if not isinstance(studies, list):
                raise TypeError("studies is not a list")
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceError(f"page {page} is not the expected JSON ({type(exc).__name__})") from exc
        token = doc.get("nextPageToken")
        if page == 1:
            total = doc.get("totalCount")
        n_studies += len(studies)
        info_url = {"final_url": resp.final_url} if resp.final_url != url else {}
        archive.store(
            source,
            f"p{page:04d}.json",
            resp.body,
            run=run,
            compress=True,
            dedup=False,
            info={
                "url": url,
                **info_url,
                "status": resp.status,
                "headers": resp.headers,
                "meta": {
                    "batch": batch,
                    "page": page,
                    "n_studies": len(studies),
                    "total_count": total,
                    "data_timestamp": data_timestamp,
                    "next_page_token": token,
                },
            },
        )
        if not token:
            break
        if not studies:
            raise SourceError(f"page {page} is empty but more pages are announced")
        # Guards against a registry that never stops handing out pages.
        if token in seen_tokens:
            raise SourceError(f"page {page} points back to a page we already had")
        seen_tokens.add(token)
        if not isinstance(total, int):
            raise SourceError("the registry did not announce how many records to expect")
        if n_studies >= total or page > math.ceil(total / page_size):
            raise SourceError(f"more pages announced after {n_studies} records, but only {total} were expected")
        page += 1
    if not isinstance(total, int) or total != n_studies:
        raise SourceError(f"received {n_studies} trial records, but the registry announced {total}")
    return {"pages": page, "n_studies": n_studies, "total_count": total}


def run_ctgov_updates(
    archive: Archive,
    fetcher: Fetcher,
    run: str,
    *,
    api: str = CTGOV_API,
    today: date | None = None,
    now: datetime | None = None,
    page_size: int = CTGOV_PAGE_SIZE,
) -> dict[str, Any]:
    """Save every company-linked trial record whose latest update was posted since the previous successful run.

    Returns the summary for the run record. A summary with "skipped" means the registry had no new data.
    The starting date only moves forward after a complete, consistent run, so a failed run is redone next time.
    """
    stamp = ctgov_data_timestamp(archive, fetcher, api, run)
    previous = archive.last_ok_run(CTGOV_UPDATES)
    last_stamp = (previous or {}).get("meta", {}).get("data_timestamp")
    if last_stamp == stamp:
        age = _days_since(str((previous or {}).get("ts")), now or utcnow())
        if age is None or age > CTGOV_STALE_DAYS:
            # Skipping is right over a weekend, but not for ever: then nothing is saved and nobody would notice.
            raise SourceError(
                f"the registry reports no data refresh since {stamp}, for more than {CTGOV_STALE_DAYS} days"
            )
        return {"skipped": "registry data not refreshed since the last run", "data_timestamp": stamp}
    if last_stamp:
        since = _stamp_date(last_stamp) - timedelta(days=CTGOV_LOOKBACK_DAYS)
    else:
        baseline = archive.last_ok_run(CTGOV_BASELINE)
        base_stamp = (baseline or {}).get("meta", {}).get("data_timestamp")
        if base_stamp:
            since = _stamp_date(base_stamp) - timedelta(days=CTGOV_LOOKBACK_DAYS)
        else:
            since = (today or utcnow().date()) - timedelta(days=CTGOV_FIRST_RUN_DAYS)
    expr = f"{CTGOV_INDUSTRY} AND AREA[LastUpdatePostDate]RANGE[{since.isoformat()},MAX]"
    fetcher.sleep(CTGOV_PAUSE)
    summary = ctgov_pages(
        archive,
        fetcher,
        api=api,
        source=CTGOV_UPDATES,
        expr=expr,
        run=run,
        batch=run,
        data_timestamp=stamp,
        page_size=page_size,
    )
    _require_same_stamp(archive, fetcher, api, run, stamp)
    return {**summary, "since": since.isoformat(), "data_timestamp": stamp, "expr": expr}


def run_ctgov_baseline(
    archive: Archive,
    fetcher: Fetcher,
    run: str,
    *,
    api: str = CTGOV_API,
    resume: bool = False,
    page_size: int = CTGOV_PAGE_SIZE,
) -> dict[str, Any]:
    """One-time full copy of all company-linked trial records, so later changes have a "before" to compare with."""
    stamp = ctgov_data_timestamp(archive, fetcher, api, run)
    kwargs: dict[str, Any] = {}
    batch = run
    if resume:
        last = _last_baseline_page(archive)
        if last is None:
            raise SourceError("nothing to resume: no unfinished baseline found")
        meta = last["meta"]
        if meta["data_timestamp"] != stamp:
            raise SourceError("the registry data was refreshed since that baseline started; start a new one")
        batch = meta["batch"]
        done = [r for r in archive.records if r.get("source") == CTGOV_BASELINE and _batch_of(r) == batch]
        kwargs = {
            "start_page": meta["page"] + 1,
            "start_token": meta["next_page_token"],
            "studies_before": sum(r["meta"]["n_studies"] for r in done),
            "total_before": meta["total_count"],
        }
    fetcher.sleep(CTGOV_PAUSE)
    summary = ctgov_pages(
        archive,
        fetcher,
        api=api,
        source=CTGOV_BASELINE,
        expr=CTGOV_INDUSTRY,
        run=run,
        batch=batch,
        data_timestamp=stamp,
        page_size=page_size,
        **kwargs,
    )
    _require_same_stamp(archive, fetcher, api, run, stamp)
    return {**summary, "data_timestamp": stamp, "expr": CTGOV_INDUSTRY, "batch": batch}


def _days_since(ts: str, now: datetime) -> float | None:
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    return (now - then).total_seconds() / 86400


def _batch_of(rec: dict[str, Any]) -> str | None:
    meta = rec.get("meta")
    return meta.get("batch") if rec.get("kind") == "file" and isinstance(meta, dict) else None


def _last_baseline_page(archive: Archive) -> dict[str, Any] | None:
    """The last stored page of the newest baseline, if that baseline still has pages to fetch."""
    pages = [r for r in archive.records if r.get("source") == CTGOV_BASELINE and _batch_of(r)]
    if not pages:
        return None
    last = pages[-1]
    return last if last["meta"].get("next_page_token") else None


def _require_same_stamp(archive: Archive, fetcher: Fetcher, api: str, run: str, stamp: str) -> None:
    fetcher.sleep(CTGOV_PAUSE)
    after = ctgov_data_timestamp(archive, fetcher, api, run)
    if after != stamp:
        raise SourceError("the registry refreshed its data during the download; the pages may not fit together")

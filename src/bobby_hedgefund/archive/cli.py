"""Command line for the archive: `bobby-archive run | baseline | sec-companies | sec-shares | verify | status`."""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .. import settings
from . import sec, sec_shares, sources
from .fetch import DEFAULT_USER_AGENT, Fetcher, FetchError
from .store import Archive, ArchiveError, Busy, new_run_id, read_records


def data_dir() -> Path:
    """Where the archive lives: outside the repository, inside the home folder that is backed up every night."""
    return Path(os.environ.get("BOBBY_DATA_DIR") or Path.home() / "bobby-hedgefund-data")


def archive_root() -> Path:
    return data_dir() / "archive"


def make_fetcher() -> Fetcher:
    return Fetcher(user_agent=os.environ.get("BOBBY_USER_AGENT") or DEFAULT_USER_AGENT)


def make_sec_fetcher() -> Fetcher:
    # Raises SettingsError when the contact address is missing: no request is ever sent without it (record 0008).
    return sec.sec_fetcher(settings.sec_contact())


def _attempt(archive: Archive, source: str, run: str, job: Callable[[], dict[str, Any]]) -> bool:
    """Run one source. A failure is recorded and reported, and never stops the other sources."""
    try:
        summary = job()
    except (FetchError, sources.SourceError) as exc:
        archive.record_run(source, run, "failed", error=str(exc))
        print(f"FAILED  {source}: {exc}")
        return False
    except (ArchiveError, OSError):
        raise  # the archive itself is in trouble (damaged, disk full, not writable): stop, write nothing more
    except Exception as exc:
        archive.record_run(source, run, "failed", error=f"{type(exc).__name__}: {exc}")
        print(f"FAILED  {source}: unexpected {type(exc).__name__}: {exc}")
        return False
    if "skipped" in summary:
        archive.record_run(source, run, "skip", meta=summary)
        print(f"skipped {source}: {summary['skipped']}")
    else:
        archive.record_run(source, run, "ok", meta=summary)
        shown = {k: v for k, v in summary.items() if k != "expr"}
        print(f"ok      {source}: {shown}")
    return True


def cmd_run(args: argparse.Namespace) -> int:
    jobs: dict[str, Callable[[Archive, Fetcher, str], dict[str, Any]]] = {}
    # Quick sources first; a publisher that needs minutes between requests goes last and holds nobody up.
    quick = [g for g in sources.FILE_GROUPS if g.pause < 60]
    slow = [g for g in sources.FILE_GROUPS if g.pause >= 60]
    for group in quick:
        jobs[group.source] = lambda a, f, r, g=group: sources.run_file_group(a, f, g, r)
    jobs[sources.CTGOV_UPDATES] = lambda a, f, r: sources.run_ctgov_updates(a, f, r, api=sources.CTGOV_API)
    for group in slow:
        jobs[group.source] = lambda a, f, r, g=group: sources.run_file_group(a, f, g, r)
    wanted = args.only or list(jobs)
    unknown = [name for name in wanted if name not in jobs]
    if unknown:
        print(f"unknown source(s): {', '.join(unknown)}. Known: {', '.join(jobs)}")
        return 2
    fetcher = make_fetcher()
    run = new_run_id()
    with Archive(archive_root(), wait=args.wait) as archive:
        results = [_attempt(archive, name, run, lambda n=name: jobs[n](archive, fetcher, run)) for name in wanted]
    return 0 if all(results) else 1


def cmd_baseline(args: argparse.Namespace) -> int:
    fetcher = make_fetcher()
    run = new_run_id()
    with Archive(archive_root()) as archive:
        ok = _attempt(
            archive,
            sources.CTGOV_BASELINE,
            run,
            lambda: sources.run_ctgov_baseline(archive, fetcher, run, api=sources.CTGOV_API, resume=args.resume),
        )
    return 0 if ok else 1


# The company files take hours and hold the archive's lock. The nightly run starts at 23:30 and must get the lock:
# no new request after this local time; the batch is then finished the next day with --resume.
SEC_LAST_REQUEST = (22, 30)


def _before_evening(now: Callable[[], time.struct_time] = time.localtime) -> bool:
    return (now().tm_hour, now().tm_min) < SEC_LAST_REQUEST


def _at_least_one(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def cmd_sec_companies(args: argparse.Namespace) -> int:
    if not _before_evening():
        print("NOT RUN: too close to the nightly run; start it during the day")
        return 1
    try:
        fetcher = make_sec_fetcher()
    except settings.SettingsError as exc:
        print(f"NOT RUN: {exc}")
        return 1
    run = new_run_id()
    with Archive(archive_root()) as archive:
        ok = _attempt(
            archive,
            sec.SEC_SOURCE,
            run,
            lambda: sec.run_sec_companies(
                archive,
                fetcher,
                run,
                tickers_url=sec.SEC_TICKERS_URL,
                submissions_url=sec.SEC_SUBMISSIONS_URL,
                resume=args.resume,
                new=args.new,
                limit=args.limit,
                keep_going=_before_evening,
            ),
        )
    return 0 if ok else 1


def cmd_sec_shares(args: argparse.Namespace) -> int:
    from ..universe import candidates  # here, not at the top: the universe code itself imports this module
    from ..universe.inputs import InputError, Inputs
    from ..universe.read_sec import ReadError

    if not _before_evening():
        print("NOT RUN: too close to the nightly run; start it during the day")
        return 1
    try:
        fetcher = make_sec_fetcher()
        found = candidates.build(Inputs(archive_root()))
    except (settings.SettingsError, InputError, ReadError) as exc:
        print(f"NOT RUN: {exc}")
        return 1
    ciks = [c.cik for c in found.candidates]
    run = new_run_id()
    with Archive(archive_root()) as archive:
        ok = _attempt(
            archive,
            sec_shares.SHARES_SOURCE,
            run,
            lambda: sec_shares.run_sec_shares(
                archive,
                fetcher,
                run,
                ciks=ciks,
                batch=str(found.counts["sec_batch"]),
                concept_url=sec_shares.SEC_CONCEPT_URL,
                limit=args.limit,
                keep_going=_before_evening,
            ),
        )
    return 0 if ok else 1


def print_verify(root: Path, *, quick: bool) -> int:
    """Check one store of files (the archive, or the prices folder) and print the outcome."""
    with Archive(root, readonly=True) as archive:
        report = archive.verify(quick=quick)
    how = "sizes only" if quick else "every file re-read and re-hashed"
    print(f"manifest lines: {report.lines}; files: {report.files} ({how}); unchanged notes: {report.unchanged}")
    print(f"stored: {report.stored_bytes / 1e6:.1f} MB")
    for note in report.notes:
        print(f"note: {note}")
    for orphan in report.orphans:
        print(f"note: file without a manifest line (left by an interrupted run): {orphan}")
    for problem in report.problems:
        print(f"PROBLEM: {problem}")
    print("verify: OK" if report.ok else f"verify: {len(report.problems)} PROBLEM(S)")
    return 0 if report.ok else 1


def cmd_verify(args: argparse.Namespace) -> int:
    return print_verify(archive_root(), quick=args.quick)


def cmd_status(_: argparse.Namespace) -> int:
    return print_status(archive_root(), "archive")


def print_status(root: Path, what: str) -> int:
    records = read_records(root)
    print(f"{what}: {root}")
    last: dict[str, dict[str, Any]] = {}
    last_ok: dict[str, str] = {}
    stored: dict[str, int] = {}
    for rec in records:
        source = str(rec.get("source"))
        if rec.get("kind") == "run" and rec.get("status") != "note":  # a note is a remark inside a run
            last[source] = rec
            if rec.get("status") in ("ok", "skip"):
                last_ok[source] = str(rec.get("ts"))
        elif rec.get("kind") == "file":
            stored[source] = stored.get(source, 0) + int(rec.get("stored_bytes") or 0)
    if not last:
        print("no runs yet")
    for source, rec in last.items():
        line = f"{source:16} last run {rec.get('ts')} {rec.get('status')}; last good {last_ok.get(source, 'never')}"
        if rec.get("error"):
            line += f"; error: {rec['error']}"
        print(line)
    for source, size in sorted(stored.items()):
        print(f"{source:16} {size / 1e6:9.1f} MB stored")
    print(f"{'total':16} {sum(stored.values()) / 1e6:9.1f} MB stored")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bobby-archive", description="Save public files that are overwritten daily. No analysis."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="the daily download (started by the systemd timer)")
    p_run.add_argument("--only", nargs="+", metavar="SOURCE", help="run only these sources")
    p_run.add_argument(
        "--wait",
        type=float,
        default=7200.0,
        metavar="SECONDS",
        help="how long to wait when another archive command is running (default: 2 hours)",
    )
    p_run.set_defaults(func=cmd_run)
    p_base = sub.add_parser("baseline", help="one-time full copy of company-linked trial records (large)")
    p_base.add_argument("--resume", action="store_true", help="continue an interrupted baseline")
    p_base.set_defaults(func=cmd_baseline)
    p_sec = sub.add_parser(
        "sec-companies", help="SEC ticker file and the filing list of every listed company (monthly, by hand; hours)"
    )
    p_sec_how = p_sec.add_mutually_exclusive_group()
    p_sec_how.add_argument("--resume", action="store_true", help="continue an interrupted or limited batch")
    p_sec_how.add_argument("--new", action="store_true", help="start a fresh batch although one is unfinished")
    p_sec.add_argument("--limit", type=_at_least_one, metavar="N", help="stop after N companies (for a first try)")
    p_sec.set_defaults(func=cmd_sec_companies)
    p_shares = sub.add_parser(
        "sec-shares", help="reported share counts of the candidate companies (monthly, by hand, after sec-companies)"
    )
    p_shares.add_argument("--limit", type=_at_least_one, metavar="N", help="stop after N requests (for a first try)")
    p_shares.set_defaults(func=cmd_sec_shares)
    p_verify = sub.add_parser("verify", help="check every stored file against the manifest; writes nothing")
    p_verify.add_argument("--quick", action="store_true", help="check the manifest and file sizes only")
    p_verify.set_defaults(func=cmd_verify)
    sub.add_parser("status", help="last run per source and stored size").set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Busy:
        # Not a success: for the nightly run this means today's files were not saved, and the alert must fire.
        print("NOT DONE: another archive command is still running")
        return 1
    except ArchiveError as exc:
        print(f"ARCHIVE ERROR: {exc}")
        return 1
    except OSError as exc:
        print(f"ARCHIVE ERROR: could not read or write the archive: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

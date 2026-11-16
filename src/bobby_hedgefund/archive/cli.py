"""Command line for the day-1 archive: `bobby-archive run | baseline | verify | status`."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import sources
from .fetch import DEFAULT_USER_AGENT, Fetcher, FetchError
from .store import Archive, ArchiveError, Busy, new_run_id, read_records


def data_dir() -> Path:
    """Where the archive lives: outside the repository, inside the home folder that is backed up every night."""
    return Path(os.environ.get("BOBBY_DATA_DIR") or Path.home() / "bobby-hedgefund-data")


def archive_root() -> Path:
    return data_dir() / "archive"


def make_fetcher() -> Fetcher:
    return Fetcher(user_agent=os.environ.get("BOBBY_USER_AGENT") or DEFAULT_USER_AGENT)


def _attempt(archive: Archive, source: str, run: str, job: Callable[[], dict[str, Any]]) -> bool:
    """Run one source. A failure is recorded and reported, and never stops the other sources."""
    try:
        summary = job()
    except (FetchError, sources.SourceError) as exc:
        archive.record_run(source, run, "failed", error=str(exc))
        print(f"FAILED  {source}: {exc}")
        return False
    except ArchiveError:
        raise  # the archive itself is in trouble: stop, do not write further
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
    for group in sources.FILE_GROUPS:
        jobs[group.source] = lambda a, f, r, g=group: sources.run_file_group(a, f, g, r)
    jobs[sources.CTGOV_UPDATES] = lambda a, f, r: sources.run_ctgov_updates(a, f, r, api=sources.CTGOV_API)
    wanted = args.only or list(jobs)
    unknown = [name for name in wanted if name not in jobs]
    if unknown:
        print(f"unknown source(s): {', '.join(unknown)}. Known: {', '.join(jobs)}")
        return 2
    fetcher = make_fetcher()
    run = new_run_id()
    with Archive(archive_root()) as archive:
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


def cmd_verify(args: argparse.Namespace) -> int:
    with Archive(archive_root()) as archive:
        report = archive.verify(quick=args.quick)
    how = "sizes only" if args.quick else "every file re-read and re-hashed"
    print(f"manifest lines: {report.lines}; files: {report.files} ({how}); unchanged notes: {report.unchanged}")
    print(f"stored: {report.stored_bytes / 1e6:.1f} MB")
    for orphan in report.orphans:
        print(f"note: file without a manifest line (left by an interrupted run): {orphan}")
    for problem in report.problems:
        print(f"PROBLEM: {problem}")
    print("verify: OK" if report.ok else f"verify: {len(report.problems)} PROBLEM(S)")
    return 0 if report.ok else 1


def cmd_status(_: argparse.Namespace) -> int:
    records = read_records(archive_root())
    print(f"archive: {archive_root()}")
    last: dict[str, dict[str, Any]] = {}
    last_ok: dict[str, str] = {}
    stored: dict[str, int] = {}
    for rec in records:
        source = str(rec.get("source"))
        if rec.get("kind") == "run":
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
    p_run.set_defaults(func=cmd_run)
    p_base = sub.add_parser("baseline", help="one-time full copy of company-linked trial records (large)")
    p_base.add_argument("--resume", action="store_true", help="continue an interrupted baseline")
    p_base.set_defaults(func=cmd_baseline)
    p_verify = sub.add_parser("verify", help="check every stored file against the manifest; changes nothing")
    p_verify.add_argument("--quick", action="store_true", help="check the manifest and file sizes only")
    p_verify.set_defaults(func=cmd_verify)
    sub.add_parser("status", help="last run per source and stored size").set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Busy:
        print("another archive run is in progress; nothing done")
        return 0
    except ArchiveError as exc:
        print(f"ARCHIVE ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

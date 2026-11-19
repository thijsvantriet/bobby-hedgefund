"""Command line for the daily session: `bobby-session <command>`. So far: prepare (the session folder)."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta

from .. import paths
from ..archive.store import ArchiveError, iso, utcnow
from ..funds import calendar
from ..funds.book import replay
from ..log import private
from ..log.store import Log, LogError
from ..universe.inputs import InputError
from ..universe.output import OutputError
from . import prepare as prep

FIRST_LOOK_BACK = timedelta(days=7)  # what counts as "new" in the very first session


def _when(text: str | None) -> datetime | None:
    if not text:
        return None
    when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if when.tzinfo is None:
        raise ValueError("a time must carry its time zone, for example 2026-11-30T08:00:00Z")
    return when


def last_cutoff(log: Log) -> datetime | None:
    """The data cut-off of the newest session in the log: everything saved after it is new today."""
    starts = [e for e in log.entries() if e.kind == "session_start"]
    return _when(starts[-1].record["cutoff"]) if starts else None


def cmd_prepare(args: argparse.Namespace) -> int:
    mode = paths.check_mode(paths.LIVE if args.live else paths.PILOT)
    started = time.monotonic()
    now = utcnow().replace(microsecond=0)
    cutoff = _when(args.cutoff) or now
    if cutoff > now + timedelta(seconds=5):
        print("NOT DONE: a data cut-off in the future is not allowed")
        return 1
    day = date.fromisoformat(args.day) if args.day else now.astimezone(calendar.AMSTERDAM).date()
    log = Log.for_mode(mode)
    since = _when(args.since) or last_cutoff(log) or cutoff - FIRST_LOOK_BACK
    held = {cik for fund in replay(log).funds.values() for cik in fund.positions}
    done = prep.prepare(
        data_dir=paths.data_dir(),
        mode_root=paths.mode_root(mode),
        session_day=day,
        start_time=now,
        cutoff=cutoff,
        since=since,
        held=held,
    )
    size = sum(p.stat().st_size for p in done.folder.rglob("*") if p.is_file())
    print(f"session folder: <data folder>/{done.folder.relative_to(paths.data_dir()).as_posix()}")
    print(f"data cut-off: {iso(cutoff)}    new since: {iso(since)}")
    for key, value in done.counts.items():
        print(f"{key:28} {value}")
    print(f"{'size':28} {size / 1e6:.1f} MB")
    print(f"{'seconds':28} {time.monotonic() - started:.1f}")
    for note in done.notes:
        print(f"note: {note}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bobby-session", description="The daily session: prepare, and its steps.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_prepare = sub.add_parser("prepare", help="build the session folder from what was saved before the cut-off")
    p_prepare.add_argument("--live", action="store_true", help="the real funds instead of the pilot")
    p_prepare.add_argument("--day", metavar="YYYY-MM-DD", help="the session day (default: today in Amsterdam)")
    p_prepare.add_argument("--cutoff", metavar="TIME", help="the data cut-off (default: now)")
    p_prepare.add_argument("--since", metavar="TIME", help="what counts as new (default: the last session's cut-off)")
    p_prepare.set_defaults(func=cmd_prepare)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (
        prep.PrepareError, LogError, InputError, OutputError, ArchiveError, private.PrivateError,
        paths.ModeError, calendar.CalendarError, ValueError,
    ) as exc:  # fmt: skip
        print(f"NOT DONE: {exc}")
        return 1
    except OSError as exc:
        print(f"NOT DONE: a file could not be read or written ({type(exc).__name__})")
        return 1


if __name__ == "__main__":
    sys.exit(main())

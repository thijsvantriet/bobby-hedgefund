"""Command line for the daily round: `bobby-session <command>`: start, book, screening, analysts, managers, collect,
decide, publish, end, clock; and prepare, which only builds a session folder."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from .. import paths
from ..archive.store import ArchiveError, iso, utcnow
from ..funds import calendar, dice
from ..funds.book import BookError, replay
from ..log import private, publish
from ..log.store import Log, LogError
from ..universe.inputs import InputError
from ..universe.output import OutputError
from . import decide, marker, steps, tasks
from . import prepare as prep
from . import round as rounds

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


def _claude_code() -> str:
    try:
        done = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=20, check=False)
        return done.stdout.split()[0] if done.returncode == 0 and done.stdout.split() else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _show(lines: list[str]) -> int:
    for line in lines:
        print(line)
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    mode = paths.check_mode(paths.LIVE if args.live else paths.PILOT)
    return _show(
        steps.start(
            mode,
            args.session_id,
            Path.cwd(),
            dry_run=args.dry_run or "",
            relaxed_clock=args.relaxed_clock,
            stand_ins=args.stand_ins,
            claude_code=_claude_code(),
        )
    )


def _round(args: argparse.Namespace) -> rounds.Round:
    return rounds.current(paths.check_mode(paths.LIVE if args.live else paths.PILOT))


def cmd_step(args: argparse.Namespace) -> int:
    rnd = _round(args)
    name = args.command
    if name == "book":
        return _show(steps.book(rnd))
    if name == "canary":
        return _show(steps.canary(rnd))
    if name == "screening":
        return _show(steps.screening(rnd))
    if name == "analysts":
        return _show(steps.analysts(rnd))
    if name == "debate":
        return _show(steps.debate(rnd))
    if name == "managers":
        return _show(steps.managers(rnd))
    if name == "collect":
        return _show(steps.collect(rnd, args.step, args.wait))
    if name == "decide":
        return _show(decide.decide(rnd, Path.cwd(), _claude_code()))
    if name == "publish":
        return _show(decide.publish_day(rnd))
    raise rounds.RoundError(f"unknown step {name}")


def cmd_end(args: argparse.Namespace) -> int:
    mode = paths.check_mode(paths.LIVE if args.live else paths.PILOT)
    active = marker.read(paths.data_dir())
    if active is None:
        print("no round is active: nothing to end")
        return 0
    rnd = rounds.load(mode, date.fromisoformat(Path(active["session_dir"]).name))
    return _show(decide.end(rnd, abort=args.abort))


def cmd_clock(args: argparse.Namespace) -> int:
    rnd = _round(args)
    minute = rnd.minutes()
    print(f"minute {minute:.1f} of the round of {rnd.day} (started {iso(rnd.start)})")
    for limit, what in (
        (rounds.NO_NEW_ANALYSIS, "no new deep analysis starts after this"),
        (rounds.ANALYSIS_USED_UNTIL, "an analyst's answer that comes later waits for the next session"),
        (rounds.DECISIONS_UNTIL, "a portfolio manager's answer that comes later is 'out of time'"),
        (rounds.HARD_STOP, "the hard stop"),
    ):
        state = "passed" if minute > limit else f"in {limit - minute:.0f} min"
        print(f"  minute {limit}: {what} ({state})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bobby-session", description="The daily round: prepare, and its steps.")
    sub = parser.add_subparsers(dest="command", required=True)
    live_help = "the real funds instead of the pilot (not switched on in this version)"
    p_prepare = sub.add_parser("prepare", help="only build a session folder (the round's `start` does this itself)")
    p_prepare.add_argument("--live", action="store_true", help=live_help)
    p_prepare.add_argument("--day", metavar="YYYY-MM-DD", help="the session day (default: today in Amsterdam)")
    p_prepare.add_argument("--cutoff", metavar="TIME", help="the data cut-off (default: now)")
    p_prepare.add_argument("--since", metavar="TIME", help="what counts as new (default: the last session's cut-off)")
    p_prepare.set_defaults(func=cmd_prepare)
    p_start = sub.add_parser("start", help="step 1: checks, start time and data cut-off, the session folder")
    p_start.add_argument("--live", action="store_true", help=live_help)
    p_start.add_argument("--session-id", required=True, help="the running Claude Code session")
    p_start.add_argument("--dry-run", metavar="MARK", help="a try-out: this text goes into every record of it")
    p_start.add_argument(
        "--relaxed-clock", action="store_true", help="try-out only: a late answer is noted, not refused"
    )
    p_start.add_argument("--stand-ins", action="store_true", help="try-out only: the agent files could not be loaded")
    p_start.set_defaults(func=cmd_start)
    for name, text in (
        ("book", "step 2: fills, company events and values since the last session"),
        ("canary", "a test of the reading check with one agent (first pilot days)"),
        ("screening", "step 3: the tasks for the screening"),
        ("analysts", "step 4: who gets a deep analysis, and the analysts' tasks"),
        ("debate", "step 5, Debate fund only: the bull and the bear, two rounds at most"),
        ("managers", "step 5: the portfolio managers' tasks, three runs per fund"),
        ("decide", "step 6: the two-of-three rule, the limits, the day's records"),
        ("publish", "steps 7 and 8: the day page and the commit"),
    ):
        p_step = sub.add_parser(name, help=text)
        p_step.add_argument("--live", action="store_true", help=live_help)
        p_step.set_defaults(func=cmd_step)
    p_collect = sub.add_parser("collect", help="take the answers of a step from the agents' own records")
    p_collect.add_argument("step", choices=sorted(steps.STEPS))
    p_collect.add_argument("--wait", type=float, default=90.0, metavar="SECONDS")
    p_collect.add_argument("--live", action="store_true", help=live_help)
    p_collect.set_defaults(func=cmd_step)
    p_end = sub.add_parser("end", help="step 9: the copy of the conversation, the usage figures, the summary")
    p_end.add_argument(
        "--abort", action="store_true", help="only switch the round's checks off after a round broke off"
    )
    p_end.add_argument("--live", action="store_true", help=live_help)
    p_end.set_defaults(func=cmd_end)
    p_clock = sub.add_parser("clock", help="the minute of the round, and what is still allowed")
    p_clock.add_argument("--live", action="store_true", help=live_help)
    p_clock.set_defaults(func=cmd_clock)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (
        prep.PrepareError, rounds.RoundError, LogError, InputError, OutputError, ArchiveError, private.PrivateError,
        paths.ModeError, calendar.CalendarError, publish.PublishError, tasks.TaskError, BookError, dice.DiceError,
        ValueError,
    ) as exc:  # fmt: skip
        print(f"NOT DONE: {exc}")
        return 1
    except OSError as exc:
        print(f"NOT DONE: a file could not be read or written ({type(exc).__name__})")
        return 1


if __name__ == "__main__":
    sys.exit(main())

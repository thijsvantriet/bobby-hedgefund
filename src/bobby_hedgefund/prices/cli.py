"""Command line for the prices: `bobby-prices daily | backfill | check | verify | status | purge`.

Everything is stored in `<data folder>/prices/`, apart from the archive (docs/decisions/0007). Private: nothing
from this folder is ever published.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from .. import settings
from ..archive.cli import _at_least_one, _attempt, data_dir, print_status, print_verify
from ..archive.fetch import Fetcher
from ..archive.store import Archive, ArchiveError, Busy, new_run_id
from ..universe.inputs import InputError, Inputs
from ..universe.output import OutputError, csv_text, free_label, write_new
from . import check, massive, purge, read


def prices_root() -> Path:
    return data_dir() / purge.FOLDER


def checks_dir() -> Path:
    return prices_root() / "checks"


def make_fetcher() -> Fetcher:
    # Raises SettingsError when the key is missing: no request is sent without it.
    return massive.massive_fetcher(settings.massive_key())


def _fetch(args: argparse.Namespace, *, start_days_back: int, with_splits: bool) -> tuple[bool, list[date]]:
    """Fetch missing days (and the split list). Returns whether all went well and which days are new."""
    fetcher = make_fetcher()
    run = new_run_id()
    today = massive.market_today()
    new_days: list[date] = []

    def days() -> dict:
        return massive.run_days(
            archive,
            fetcher,
            run,
            start=today - timedelta(days=start_days_back),
            end=today - timedelta(days=1),  # a day's prices are out after midnight where the market is
            today=today,
            url=massive.DAILY_URL,
            limit=getattr(args, "limit", None),
            stored_now=new_days,  # filled as each day is stored, so also when a later day stops the run
        )

    with Archive(prices_root(), wait=args.wait) as archive:
        ok = _attempt(archive, massive.DAILY_SOURCE, run, days)
        if with_splits:
            # From the first day of a month two years back: the address then stays the same for a month, and an
            # unchanged list is not stored again.
            start = (today - timedelta(days=massive.HISTORY_DAYS)).replace(day=1)
            ok = (
                _attempt(
                    archive,
                    massive.SPLITS_SOURCE,
                    run,
                    lambda: massive.run_splits(archive, fetcher, run, start=start, url=massive.SPLITS_URL),
                )
                and ok
            )
    return ok, new_days


def cmd_daily(args: argparse.Namespace) -> int:
    try:
        ok, new_days = _fetch(args, start_days_back=massive.DAILY_LOOKBACK_DAYS, with_splits=True)
    except settings.SettingsError as exc:
        print(f"NOT RUN: {exc}")
        return 1
    if new_days:
        try:
            _check(new_days)
        except (InputError, OutputError) as exc:
            # The prices are saved; only the comparison could not be made. Not a failed download.
            print(f"check skipped: {exc}")
    return 0 if ok else 1


def cmd_backfill(args: argparse.Namespace) -> int:
    try:
        ok, _ = _fetch(args, start_days_back=massive.HISTORY_DAYS, with_splits=not args.limit)
    except settings.SettingsError as exc:
        print(f"NOT RUN: {exc}")
        return 1
    return 0 if ok else 1


def _check(days: list[date] | None) -> int:
    """Compare each of `days` (None: every stored day) with the stored day before it; write the jumps found."""
    inputs = Inputs(prices_root())
    records = read.day_records(inputs)
    splits = read.load_splits(inputs)
    order = list(records)
    if days is not None:
        # A day that was stored late changes the comparison of the day after it too.
        wanted = set(days) | {order[i + 1] for i, day in enumerate(order[:-1]) if day in days}
        days = sorted(wanted)
    rows: list[tuple[object, ...]] = []
    checked = 0
    loaded: tuple[date, dict[str, read.Bar]] | None = None
    for i, day in enumerate(order):
        if i == 0 or (days is not None and day not in days):
            continue
        before = order[i - 1]
        previous = loaded[1] if loaded and loaded[0] == before else read.load_day(inputs, records[before])
        bars = read.load_day(inputs, records[day])
        rows += check.jumps(day, before, bars, previous, splits)
        loaded = (day, bars)
        checked += 1
    if not checked:
        print("check: no day to compare (a day needs a stored day before it)")
        return 0
    folder = checks_dir()
    label = free_label(date.today(), [(folder, "jumps.csv")])
    path = folder / f"{label}_jumps.csv"
    write_new(path, csv_text(check.HEADER, rows))
    print(f"check: {checked} day(s) compared, {len(rows)} closing prices moved by more than half without a split")
    print(f"written: {path}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    if args.all:
        return _check(None)
    order = list(read.day_records(Inputs(prices_root())))
    return _check(order[-args.days :])


def cmd_verify(args: argparse.Namespace) -> int:
    return print_verify(prices_root(), quick=args.quick)


def cmd_status(_: argparse.Namespace) -> int:
    code = print_status(prices_root(), "prices")
    records = Inputs(prices_root()).records
    days = sorted(massive.stored_days(records))
    if days:
        print(f"days stored: {len(days)}, from {days[0]} to {days[-1]}")
    today = massive.market_today()
    odd = massive.unexpected_closed_days(records, today)
    if odd:
        print(f"working days without prices that are not a regular holiday: {', '.join(d.isoformat() for d in odd)}")
    waiting = massive._open_days(records, days[0], today - timedelta(days=1), today) if days else []
    if waiting:
        print(f"working days not stored yet: {len(waiting)} ({', '.join(d.isoformat() for d in waiting[:8])})")
    return code


def cmd_purge(args: argparse.Namespace) -> int:
    if not args.yes_delete_everything:
        print("NOT DONE: this deletes every saved price for good. It is meant for the day the account with the")
        print("price service ends (docs/decisions/0007, point 4). First switch the morning download off")
        print("(systemctl --user disable --now bobby-prices.timer) and take the key out of the .env file.")
        print("To go ahead: add --yes-delete-everything")
        return 1
    stripped, left = purge.strip_universe_files(data_dir())  # first: it needs nothing from the prices folder
    if stripped:
        print(f"universe files: {len(stripped)} replaced by a copy without the price columns")
    for name in left:
        print(f"STILL HOLDS PRICES, look at it by hand: universe/{name}")
    private_note, counts = purge.purge_private(data_dir())
    for name, count in counts.items():
        print(
            f"deleted: {name}/ with {count} files (private log content, fund books, sessions, reports, conversations)"
        )
    if private_note is not None:
        print(f"What was removed there is listed in {private_note}")
        print("The public log stays; `bobby-log verify` now reports its sealed content as deleted under record 0007.")
    note, files = purge.purge(data_dir())
    if note is None:
        print("nothing to delete: there is no prices folder")
        return 1 if left else 0
    print(f"deleted: the prices folder with {files} files. What was removed is listed in {note}")
    print("Still to do by hand (docs/decisions/0007, point 4): older copies in the machine's backup must be gone")
    print("within 90 days, and Claude Code's own records of the sessions must not be kept longer than its default.")
    return 1 if left else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bobby-prices", description="Save daily prices. Private; no analysis.")
    sub = parser.add_subparsers(dest="command", required=True)
    wait_help = "how long to wait when another prices command is running"
    p_daily = sub.add_parser("daily", help="the morning download: missing days of the last two weeks, and the splits")
    p_daily.add_argument("--wait", type=float, default=3 * 3600.0, metavar="SECONDS", help=wait_help)
    p_daily.set_defaults(func=cmd_daily)
    p_back = sub.add_parser("backfill", help="one-time: the two years of history (hours; run it again to continue)")
    p_back.add_argument("--limit", type=_at_least_one, metavar="N", help="stop after N requests (for a first try)")
    p_back.add_argument("--wait", type=float, default=0.0, metavar="SECONDS", help=wait_help)
    p_back.set_defaults(func=cmd_backfill)
    p_check = sub.add_parser("check", help="list closing prices that moved by more than half without a share split")
    p_check_what = p_check.add_mutually_exclusive_group()
    p_check_what.add_argument(
        "--days", type=_at_least_one, default=1, metavar="N", help="the newest N days (default 1)"
    )
    p_check_what.add_argument("--all", action="store_true", help="every stored day")
    p_check.set_defaults(func=cmd_check)
    p_verify = sub.add_parser("verify", help="check every stored file against its fingerprint; writes nothing")
    p_verify.add_argument("--quick", action="store_true", help="check the list and file sizes only")
    p_verify.set_defaults(func=cmd_verify)
    sub.add_parser("status", help="last run and stored days").set_defaults(func=cmd_status)
    p_purge = sub.add_parser("purge", help="delete every saved price (only when the account with the service ends)")
    p_purge.add_argument("--yes-delete-everything", action="store_true")
    p_purge.set_defaults(func=cmd_purge)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Busy:
        print("NOT DONE: another prices command is still running")
        return 1
    except (ArchiveError, InputError, OutputError, purge.PurgeError) as exc:
        print(f"NOT DONE: {exc}")
        return 1
    except OSError as exc:
        print(f"NOT DONE: could not read or write the prices folder: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

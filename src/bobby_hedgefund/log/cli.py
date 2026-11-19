"""Command lines for the decision log: `bobby-log` (verify, show, head) and `bobby-publish` (plan, day)."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .. import paths
from . import canon, private, publish
from .seal import sealed_fields
from .store import HEAD, START, Log, LogError, _write_head, day_files, read_entries


def _mode(args: argparse.Namespace) -> str:
    return paths.check_mode(paths.LIVE if args.live else paths.PILOT)


def _shown(path: Path) -> str:
    """A path as it is printed: from the data folder on, so that the home folder never ends up in a message that
    is pasted somewhere."""
    try:
        return "<data folder>/" + path.resolve().relative_to(paths.data_dir().resolve()).as_posix()
    except ValueError:
        return path.name


def _log_of_copy(folder: Path) -> Log:
    """A copy of `track-record/` (for example in a copy of the repository): the public half only. Which log it is
    (the real one or the pilot's) is read from its first record."""
    files = day_files(folder)
    mode = paths.LIVE
    if files:
        first = canon.decode(files[0].read_bytes().split(b"\n", 1)[0])
        mode = first.get("mode") if isinstance(first, dict) else None
        if mode not in paths.MODES:
            raise LogError("the first record does not say which log this is")
    return Log(folder, None, mode)


def cmd_verify(args: argparse.Namespace) -> int:
    log = _log_of_copy(Path(args.dir)) if args.dir else Log.for_mode(_mode(args))
    report = log.verify(check_private=not args.dir)
    print(f"log: {_shown(log.staging)} ({log.mode})")
    print(f"records: {report.records} in {report.files} day file(s)")
    if report.head:
        print(f"newest fingerprint: {report.head}")
    if report.sealed:
        print(
            f"sealed fields: {report.sealed} (checked against the private files: {report.sealed_checked}; "
            f"content deleted under record 0007: {report.sealed_deleted}; never kept: {report.sealed_not_kept}; "
            f"not checked: {report.sealed_not_checked})"
        )
    for note in report.notes:
        print(f"note: {note}")
    for problem in report.problems:
        print(f"PROBLEM: {problem}")
    if report.problems:
        print("NOT OK: the log does not pass its check")
        return 1
    print("ok: one unbroken chain" + ("" if report.records else " (the log is empty)"))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    log = Log.for_mode(_mode(args))
    shown = 0
    for entry in log.entries():
        if args.day and entry.day.isoformat() != args.day:
            continue
        if args.kind and entry.kind != args.kind:
            continue
        record = log.opened(entry) if args.open else entry.record
        mark = f"  [{len(sealed_fields(entry.record))} sealed]" if sealed_fields(entry.record) and not args.open else ""
        print(f"{entry.seq:>6}  {entry.day}  {entry.kind}{mark}")
        print(
            "        "
            + canon.encode({k: v for k, v in record.items() if k not in ("prev", "v", "seq", "kind")}).decode()
        )
        shown += 1
    print(f"{shown} record(s)" + (" (sealed content shown: private, never paste this anywhere)" if args.open else ""))
    return 0


def cmd_head(args: argparse.Namespace) -> int:
    mode = _mode(args)
    log = Log.for_mode(mode)
    entries = read_entries(log.staging, mode)  # raises when the chain itself is broken
    newest = entries[-1].sha256 if entries else START[mode]
    print(f"records: {len(entries)}\nnewest fingerprint: {newest}")
    if args.rewrite:
        _write_head(log.staging, len(entries), newest)
        print(f"written: {_shown(log.staging / HEAD)} (from the chain as it stands)")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    mode = _mode(args)
    staging, repo = paths.staging_dir(mode), _repo(mode)
    changes = publish.plan(staging, repo / publish.TRACK)
    for change in changes:
        if change.kind != "same":
            print(f"{change.kind:>6}  {change.path}")
    todo = sum(c.kind != "same" for c in changes)
    print(f"{todo} file(s) to publish, {len(changes) - todo} unchanged")
    return 0


def _repo(mode: str) -> Path:
    if mode == paths.PILOT:
        return publish.pilot_repo(paths.mode_root(mode))
    return Path.cwd()


def cmd_day(args: argparse.Namespace) -> int:
    mode = _mode(args)
    root = paths.mode_root(mode)
    names = private.PrivateNames(private.load(root / private.FILE))
    day = date.fromisoformat(args.day)
    repo = _repo(mode)
    commit, changes = publish.publish(
        paths.staging_dir(mode), repo, mode, day, private_names=names, push=mode == paths.LIVE
    )
    if commit is None:
        print("nothing new to publish")
        return 0
    print(f"published: {sum(c.kind != 'same' for c in changes)} file(s), commit {commit[:12]} in {_shown(repo)}")
    if mode == paths.PILOT:
        print("pilot: committed on this machine only, nothing was sent")
        print(f"commit time (stands in for the time GitHub received it): {publish.commit_time(repo).isoformat()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bobby-log", description="The decision log: check it, read it.")
    sub = parser.add_subparsers(dest="command", required=True)
    live_help = "the real log instead of the pilot's (only after the owner's go)"
    p_verify = sub.add_parser("verify", help="re-check the whole chain of fingerprints; writes nothing")
    p_verify.add_argument("--live", action="store_true", help=live_help)
    p_verify.add_argument("--dir", metavar="FOLDER", help="check a copy of track-record/ (the public half only)")
    p_verify.set_defaults(func=cmd_verify)
    p_show = sub.add_parser("show", help="print records")
    p_show.add_argument("--live", action="store_true", help=live_help)
    p_show.add_argument("--day", metavar="YYYY-MM-DD")
    p_show.add_argument("--kind")
    p_show.add_argument("--open", action="store_true", help="show sealed content too (private)")
    p_show.set_defaults(func=cmd_show)
    p_head = sub.add_parser("head", help="the newest fingerprint and the number of records")
    p_head.add_argument("--live", action="store_true", help=live_help)
    p_head.add_argument("--rewrite", action="store_true", help="write HEAD anew from the chain (after a look by hand)")
    p_head.set_defaults(func=cmd_head)
    return _run(parser, argv)


def publish_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bobby-publish", description="Place the day's prepared files in track-record/ and commit them."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    live_help = "the real track record, sent to GitHub (only after the owner's go)"
    p_plan = sub.add_parser("plan", help="show what would be published; writes nothing in track-record/")
    p_plan.add_argument("--live", action="store_true", help=live_help)
    p_plan.set_defaults(func=cmd_plan)
    p_day = sub.add_parser("day", help="publish: one commit for the day")
    p_day.add_argument("day", metavar="YYYY-MM-DD")
    p_day.add_argument("--live", action="store_true", help=live_help)
    p_day.set_defaults(func=cmd_day)
    return _run(parser, argv)


def _run(parser: argparse.ArgumentParser, argv: list[str] | None) -> int:
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (LogError, publish.PublishError, private.PrivateError, paths.ModeError, canon.CanonError, ValueError) as exc:
        print(f"NOT DONE: {exc}")
        return 1
    except OSError as exc:  # its own text can hold a full path, with the home folder in it
        print(f"NOT DONE: a file could not be read or written ({type(exc).__name__})")
        return 1


if __name__ == "__main__":
    sys.exit(main())

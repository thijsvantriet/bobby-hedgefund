"""Delete everything that holds prices (docs/decisions/0007, point 4). Only for the day the account with the price
service ends: its terms then give 30 days to delete all saved data. This is the one place in the project that
deletes downloaded files, and it can only delete the prices folder inside the data folder."""

from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path

from ..archive.store import Archive, ArchiveError, iso, read_records, utcnow
from ..universe.output import write_new

FOLDER = "prices"
NOTES_FOLDER = "purged"


class PurgeError(Exception):
    pass


def _checked_target(data_dir: Path) -> Path:
    target = data_dir / FOLDER
    # No path from outside is ever accepted: the target is always this one folder, directly inside the data folder.
    if data_dir.is_symlink() or target.is_symlink():
        raise PurgeError("the data folder or the prices folder is a link to somewhere else; nothing was deleted")
    if target.resolve().parent != data_dir.resolve() or target.name != FOLDER:
        raise PurgeError("the prices folder is not where it should be; nothing was deleted")
    return target


def _remove_leftovers(data_dir: Path) -> int:
    """Finish an earlier purge that was interrupted: remove folders it had already set aside."""
    removed = 0
    for left in sorted(data_dir.glob(f".{FOLDER}-purging-*")):
        if left.is_dir() and not left.is_symlink():
            shutil.rmtree(left)
            removed += 1
    return removed


UNIVERSE_FOLDER = "universe"
# Columns of a universe file that hold a price or a number computed from prices (docs/decisions/0006, point 6).
PRICE_COLUMNS = frozenset({"last_close", "market_value", "avg_traded_per_day"})


def strip_universe_files(data_dir: Path) -> tuple[list[str], list[str]]:
    """Replace every universe file by a copy without the columns that come from prices: who was in and out, and
    why, stays (record 0006). The copy is written first, under a new name; then the original is removed.
    Returns the names done, and the names that could not be handled and still need a look by hand."""
    folder = data_dir / UNIVERSE_FOLDER
    if folder.is_symlink():
        raise PurgeError("the universe folder is a link to somewhere else; nothing was deleted there")
    done: list[str] = []
    left: list[str] = []
    for path in sorted(folder.glob("*_universe.csv")) if folder.is_dir() else []:
        if path.name.startswith("."):
            continue
        if path.is_symlink() or not path.is_file():
            left.append(f"{path.name} (a link or not a file)")
            continue
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                rows = list(csv.reader(fh))
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            left.append(f"{path.name} (not readable: {type(exc).__name__})")
            continue
        keep = [i for i, name in enumerate(rows[0]) if name not in PRICE_COLUMNS] if rows else []
        copy = path.with_name(path.name.removesuffix(".csv") + "-without-prices.csv")
        if not copy.exists():  # left by an interrupted purge: complete, because it is written in one step
            out = io.StringIO()
            csv.writer(out, lineterminator="\n").writerows([row[i] for i in keep if i < len(row)] for row in rows)
            write_new(copy, out.getvalue())
        path.unlink()
        done.append(path.name)
    return done, left


def purge(data_dir: Path) -> tuple[Path | None, int]:
    """Remove the prices folder with everything in it. Returns the path of the note that lists what was removed
    (paths and fingerprints, no prices) and the number of files; (None, 0) when there was no prices folder.

    Order: take the folder's lock (so no download is running), set the whole folder aside under another name in
    one step (a download that starts now begins an empty folder and cannot write into the one being deleted),
    write the note, then delete. If deleting is interrupted, running the purge again finishes it."""
    target = _checked_target(data_dir)
    leftovers = _remove_leftovers(data_dir) if data_dir.is_dir() else 0
    if not target.exists():
        return None, leftovers
    if not target.is_dir():
        raise PurgeError("the prices folder is not a folder; nothing was deleted")
    stamp = utcnow()
    aside = data_dir / f".{FOLDER}-purging-{stamp:%Y%m%dT%H%M%SZ}"
    with Archive(target, readonly=True):  # raises Busy while a download holds the lock
        try:
            records = [r for r in read_records(target) if r.get("kind") == "file"]
        except (OSError, ArchiveError) as exc:
            raise PurgeError(f"the list of stored price files could not be read ({type(exc).__name__})") from exc
        on_disk = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
        lines = [
            "# Deleted under docs/decisions/0007, point 4: everything saved from the price service",
            f"# when: {iso(stamp)}",
            f"# folder: {FOLDER}/ ({len(on_disk)} files on disk, {len(records)} in the list of stored files)",
            "# stored files (fingerprint, path):",
        ]
        lines += [f"{r.get('sha256')}  {r.get('path')}" for r in records]
        lines.append("# every file that was on disk:")
        lines += on_disk
        note = data_dir / NOTES_FOLDER / f"{stamp:%Y%m%dT%H%M%SZ}_prices.txt"
        write_new(note, "\n".join(lines) + "\n")  # the note exists before anything is removed
        target.rename(aside)  # one step; the lock is still held, on the folder that is now set aside
    try:
        shutil.rmtree(aside)  # does not follow links inside the folder
    except OSError as exc:
        raise PurgeError(
            f"the prices folder was set aside but not fully deleted ({type(exc).__name__}); "
            "run the purge again to finish it"
        ) from exc
    return note, len(on_disk)


# Everything else that holds prices (docs/decisions/0007, point 4): the private half of the decision log, the
# private fund books, the session folders, the reports and the saved conversations, of the real run and the pilot.
PRIVATE_FOLDERS = ("log-private", "books", "sessions", "reports", "conversations")
PRIVATE_ROOTS = ("", "pilot")
LOG_PRIVATE = "log-private"
DELETED_MARK = "DELETED-0007"


def _records_in_head(root: Path) -> int:
    """The number of records the log of this root has, read from its HEAD file; 0 when there is none."""
    try:
        head = json.loads((root / "staging" / "HEAD").read_text(encoding="utf-8"))
        return int(head["records"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def _leave_marker(root: Path, stamp_text: str) -> None:
    """The marker that tells `bobby-log verify` up to which record the private content was deleted on purpose."""
    folder = root / LOG_PRIVATE
    folder.mkdir(mode=0o700, exist_ok=True)
    marker = folder / DELETED_MARK
    if not marker.exists():
        write_new(
            marker,
            f"upto {_records_in_head(root)}\ncontent deleted under docs/decisions/0007, point 4, on {stamp_text}\n",
        )


def purge_private(data_dir: Path) -> tuple[Path | None, dict[str, int]]:
    """Remove the private folders that hold prices. Returns the note that lists what was removed (folder names
    and file counts, nothing else) and the number of files per folder; (None, {}) when there was nothing.

    The public log stays: its sealed fingerprints then have no content any more. A marker is left in the place
    of the log's private folder, so that `bobby-log verify` reports "content deleted under record 0007" and not
    damage. Each folder is set aside under another name in one step and then deleted; running the purge again
    finishes an interrupted one, the marker included."""
    if data_dir.is_symlink():
        raise PurgeError("the data folder is a link to somewhere else; nothing was deleted")
    stamp = utcnow()
    counts: dict[str, int] = {}
    todo: list[tuple[Path, Path, str]] = []
    for root_name in PRIVATE_ROOTS:
        root = data_dir / root_name if root_name else data_dir
        if root.is_symlink():
            raise PurgeError(f"the folder {root_name}/ is a link to somewhere else; nothing was deleted")
        if not root.is_dir():
            continue
        for left in sorted(root.glob(".*-purging-private-*")):
            if left.is_dir() and not left.is_symlink():
                if left.name.startswith(f".{LOG_PRIVATE}-"):
                    _leave_marker(root, iso(stamp))  # the earlier purge stopped before it could leave one
                shutil.rmtree(left)
        for name in PRIVATE_FOLDERS:
            target = root / name
            if target.is_symlink():
                raise PurgeError(f"{root_name or '.'}/{name} is a link to somewhere else; nothing was deleted")
            if target.resolve().parent != root.resolve():
                raise PurgeError(f"{root_name or '.'}/{name} is not where it should be; nothing was deleted")
            if not target.is_dir():
                continue
            files = sum(1 for p in target.rglob("*") if p.is_file() and p.name != DELETED_MARK)
            if files == 0:
                continue
            counts[f"{root_name + '/' if root_name else ''}{name}"] = files
            todo.append((root, target, name))
    if not todo:
        return None, counts
    lines = [
        "# Deleted under docs/decisions/0007, point 4: the private files that hold prices",
        f"# when: {iso(stamp)}",
        "# folder, number of files:",
        *[f"{name}  {count}" for name, count in counts.items()],
    ]
    note = data_dir / NOTES_FOLDER / f"{stamp:%Y%m%dT%H%M%SZ}_private.txt"
    write_new(note, "\n".join(lines) + "\n")  # the note exists before anything is removed
    for root, target, name in todo:
        aside = target.with_name(f".{name}-purging-private-{stamp:%Y%m%dT%H%M%SZ}")
        target.rename(aside)
        if name == LOG_PRIVATE:
            _leave_marker(root, iso(stamp))  # a new marker: after a second purge it names the newest record
        try:
            shutil.rmtree(aside)
        except OSError as exc:
            raise PurgeError(
                f"{name} was set aside but not fully deleted ({type(exc).__name__}); run the purge again to finish it"
            ) from exc
    return note, counts

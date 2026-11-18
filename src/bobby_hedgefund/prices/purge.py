"""Delete everything that holds prices (docs/decisions/0007, point 4). Only for the day the account with the price
service ends: its terms then give 30 days to delete all saved data. This is the one place in the project that
deletes downloaded files, and it can only delete the prices folder inside the data folder."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..archive.store import ArchiveError, iso, read_records, utcnow
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


def purge(data_dir: Path) -> tuple[Path | None, int]:
    """Remove the prices folder with everything in it. First writes a note listing what is removed (paths and
    fingerprints, no prices). Returns the note's path and the number of files listed; (None, 0) when there is
    no prices folder."""
    target = _checked_target(data_dir)
    if not target.exists():
        return None, 0
    if not target.is_dir():
        raise PurgeError("the prices folder is not a folder; nothing was deleted")
    try:
        records = [r for r in read_records(target) if r.get("kind") == "file"]
    except (OSError, ArchiveError) as exc:
        raise PurgeError(f"the list of stored price files could not be read ({type(exc).__name__})") from exc
    on_disk = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    stamp = utcnow()
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
    shutil.rmtree(target)  # does not follow links inside the folder
    return note, len(on_disk)

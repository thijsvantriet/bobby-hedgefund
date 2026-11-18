"""Write result files that are never overwritten: every run gets its own dated files (docs/decisions/0006)."""

from __future__ import annotations

import csv
import io
import os
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path


class OutputError(Exception):
    pass


def free_label(day: date, targets: Sequence[tuple[Path, str]]) -> str:
    """A label for this run's files: the date, or the date with -2, -3, ... when files of that day exist already.
    `targets` are (folder, file name ending) pairs; the label is free when none of the files exists."""
    for n in range(1, 100):
        label = day.isoformat() if n == 1 else f"{day.isoformat()}-{n}"
        if not any((folder / f"{label}_{ending}").exists() for folder, ending in targets):
            return label
    raise OutputError("too many result files for one day")


def write_new(path: Path, text: str) -> None:
    """Create `path` with `text`. Refuses to replace an existing file; a failed write leaves no half file under
    the final name. Folders and files are for the owner only: the results hold private data."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f".tmp-{os.getpid()}-{path.name}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            data = text.encode("utf-8")
            done = 0
            while done < len(data):
                done += os.write(fd, data[done:])
            os.fchmod(fd, 0o400)  # read-only: a result is never edited afterwards
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.link(tmp, path)  # unlike a rename, a link never replaces an existing file
        except FileExistsError:
            raise OutputError(f"{path} exists already; nothing was overwritten") from None
    finally:
        tmp.unlink(missing_ok=True)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: object) -> object:
    """Text from outside (a sponsor name, a holding's name) that a spreadsheet would run as a formula gets an
    apostrophe in front, the usual way to mark a cell as plain text. Readers of these files take it off again
    with `plain_cell`."""
    return "'" + value if isinstance(value, str) and value.startswith(FORMULA_START) else value


def plain_cell(value: str) -> str:
    return value[1:] if value.startswith("'") and value[1:].startswith(FORMULA_START) else value


def csv_text(header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows([safe_cell(cell) for cell in row] for row in rows)
    return out.getvalue()

"""Only what was saved before the data cut-off (docs/decisions/0003, point 1; docs/SPEC.md section 2, point 6).

A saved file counts by the time in its line of the saved-files list, never by a date of the file system. A file
that one of our own jobs made (the universe, the linking table) has no such line: it is admitted only when every
file in its own list of inputs was saved before the cut-off, and its own "made" time lies before it too.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..archive.store import iso, read_records
from ..universe.inputs import Inputs

_LISTED = re.compile(r"^([0-9a-f]{64})  (\S.*)$")
_MADE = re.compile(r"^# made: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s*$", re.MULTILINE)


class SourceError(Exception):
    pass


def before(root: Path, cutoff: datetime) -> Inputs:
    """The saved files of one folder (the archive, or the prices), as far as they were saved before the cut-off."""
    inputs = Inputs(root)
    limit = iso(cutoff)
    inputs.records = [r for r in inputs.records if str(r.get("ts", "")) < limit]
    return inputs


def stored_times(*roots: Path) -> dict[tuple[str, str], str]:
    """(path, fingerprint) -> the first time that file was saved, over the given folders."""
    times: dict[tuple[str, str], str] = {}
    for root in roots:
        if not (root / "manifest.jsonl").exists():
            continue
        for rec in read_records(root):
            if rec.get("kind") in ("file", "unchanged") and rec.get("path") and rec.get("sha256"):
                key = (str(rec["path"]), str(rec["sha256"]))
                ts = str(rec.get("ts", ""))
                if key not in times or ts < times[key]:
                    times[key] = ts
    return times


def admitted(inputs_file: Path, times: dict[tuple[str, str], str], cutoff: datetime) -> tuple[bool, str]:
    """May a file our own jobs made be used at this cut-off? Returns the answer and, when not, why."""
    limit = iso(cutoff)
    try:
        text = inputs_file.read_text(encoding="utf-8")
    except OSError:
        return False, "its list of inputs is missing"
    made = _MADE.search(text)
    if made is None:
        return False, "its list of inputs does not say when it was made"
    if made.group(1) >= limit:
        return False, "it was made after the cut-off"
    for line in text.splitlines():
        match = _LISTED.match(line)
        if match is None:
            continue
        stored = times.get((match.group(2), match.group(1)))
        if stored is None:
            return False, "one of its inputs is not in the lists of saved files"
        if stored >= limit:
            return False, "one of its inputs was saved after the cut-off"
    return True, ""


def newest_admitted(
    folder: Path, ending: str, inputs_ending: str, times: dict[tuple[str, str], str], cutoff: datetime
) -> tuple[Path | None, list[str]]:
    """The newest `<label>_<ending>` in `folder` that may be used at this cut-off, and a note for every newer one
    that was passed over. Newest by its label (the date in its name), never by a date of the file system."""

    def label_key(path: Path) -> tuple[str, int]:
        parts = path.name[: -len(ending) - 1].split("-")  # 2026-11-18 or, for a second run that day, 2026-11-18-2
        return "-".join(parts[:3]), int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1

    files = sorted((p for p in folder.glob(f"*_{ending}") if not p.name.startswith(".")), key=label_key, reverse=True)
    notes: list[str] = []
    for path in files:
        ok, why = admitted(path.with_name(path.name[: -len(ending)] + inputs_ending), times, cutoff)
        if ok:
            return path, notes
        notes.append(f"{path.name} is not used: {why}")
    return None, notes


def record_meta(rec: dict[str, Any]) -> dict[str, Any]:
    meta = rec.get("meta")
    return meta if isinstance(meta, dict) else {}

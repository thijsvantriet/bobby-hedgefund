"""Command line for trial-record changes: `bobby-trials changes`.

Reads the archive, writes a dated private file next to it. Downloads nothing and changes nothing in the archive.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from ..archive.cli import archive_root, data_dir
from ..archive.store import iso, utcnow
from ..universe.inputs import InputError, Inputs
from ..universe.output import OutputError, free_label, write_new
from ..universe.read_sec import ReadError
from ..universe.read_trials import page_studies
from . import changes

TRIAL_SOURCES = ("ctgov-baseline", "ctgov-updates")  # read together, in the order the pages were saved


def changes_dir() -> Path:
    return data_dir() / "trial-changes"


def _earlier(folder: Path) -> tuple[set[tuple[str, str, str]], dict[str, int]]:
    """What earlier runs already wrote: the changes (trial, field, the file the new value was read from), and the
    counts of unreadable pages and records in the newest list of inputs."""
    seen: set[tuple[str, str, str]] = set()
    files = sorted(p for p in folder.glob("*_changes.jsonl") if not p.name.startswith(".")) if folder.is_dir() else []
    for path in files:
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                line = json.loads(raw)
                seen.add((str(line["nct"]), str(line["field"]), str(line["new_file"])))
            except (ValueError, KeyError, TypeError):
                raise InputError(f"{path.name} holds a line that is not a change line") from None
    counts = {"pages_not_readable": 0, "records_not_readable": 0}
    notes = (
        sorted(p for p in folder.glob("*_changes-inputs.txt") if not p.name.startswith(".")) if folder.is_dir() else []
    )
    if notes:
        newest = max(notes, key=lambda p: (p.stat().st_mtime, p.name))
        for raw in newest.read_text(encoding="utf-8").splitlines():
            for key in counts:
                if raw.startswith(f"# {key}: "):
                    try:
                        counts[key] = int(raw.split(": ", 1)[1])
                    except ValueError:
                        continue
    return seen, counts


def cmd_changes(_: argparse.Namespace) -> int:
    """Each run reads the whole archive again, and writes only the changes that no earlier run wrote. All the
    dated files together are the full list. Nothing is written on a night without news."""
    inputs = Inputs(archive_root())
    folder = changes_dir()
    already, before = _earlier(folder)
    finder = changes.ChangeFinder()
    lines: list[str] = []
    per_field: dict[str, int] = {}
    pages = bad_pages = bad = total = 0
    for rec in inputs.files_in_order(TRIAL_SOURCES):
        if not str(rec.get("name", "")).endswith(".json"):
            continue
        pages += 1
        try:
            studies = page_studies(inputs.read(rec))
        except ReadError:
            bad_pages += 1  # an archived page stays as it is for good: counted, and the rest is still read
            continue
        for study in studies:
            try:
                found = finder.add(study, str(rec["path"]), str(rec.get("ts") or ""))
            except (KeyError, TypeError, AttributeError):
                bad += 1  # a record without a trial number or with an unexpected layout: counted, not guessed at
                continue
            for line in found:
                total += 1
                if (line["nct"], line["field"], line["new_file"]) in already:
                    continue
                per_field[line["field"]] = per_field.get(line["field"], 0) + 1
                lines.append(json.dumps(line, ensure_ascii=False, separators=(",", ":")))
    if not pages:
        raise InputError("the archive holds no trial records")
    facts: dict[str, object] = {
        "pages_read": pages,
        "pages_not_readable": bad_pages,
        "copies_of_records_read": finder.copies,
        "trials": finder.trials,
        "records_not_readable": bad,
        "older_copies_skipped": finder.older_copies_skipped,
        "changes_since_the_baseline": total,
        "new_changes": len(lines),
        "trials_with_a_new_change": len({json.loads(x)["nct"] for x in lines}),
        **{f"new_{name}": per_field.get(name, 0) for name in changes.FIELDS},
    }
    for key, value in facts.items():
        print(f"{key:32} {value}")
    # More unreadable pages or records than last time is news, and a failure; the same number as before is not
    # (an archived page never changes, so it would otherwise fail every night for good).
    worse = bad_pages > before["pages_not_readable"] or bad > before["records_not_readable"]
    changed_counts = (bad_pages, bad) != (before["pages_not_readable"], before["records_not_readable"])
    if not lines and not changed_counts and already:
        print("nothing new: no file written")
        return 0
    label = free_label(date.today(), [(folder, "changes.jsonl"), (folder, "changes-inputs.txt")])
    head = [f"# new changes in trial records; made: {iso(utcnow())}"]
    head += [f"# {key}: {value}" for key, value in facts.items()]
    head.append("# files read from the archive (fingerprint, path):")
    # The list of inputs is written first: a result never exists without the record of what it was made from.
    write_new(folder / f"{label}_changes-inputs.txt", "\n".join(head) + "\n" + inputs.listing())
    write_new(folder / f"{label}_changes.jsonl", "".join(x + "\n" for x in lines))
    print(f"written: {folder / f'{label}_changes.jsonl'}")
    if worse:
        print("WARNING: more unreadable pages or records than at the last run")
    return 1 if worse else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bobby-trials", description="Changes in archived trial records. Private output; no downloads."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "changes", help="every change of the followed fields since the baseline, from the archived copies"
    ).set_defaults(func=cmd_changes)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (InputError, ReadError, OutputError) as exc:
        print(f"NOT DONE: {exc}")
        return 1
    except OSError as exc:
        print(f"NOT DONE: could not read or write a file: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

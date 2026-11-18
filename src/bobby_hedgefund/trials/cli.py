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


def cmd_changes(_: argparse.Namespace) -> int:
    inputs = Inputs(archive_root())
    finder = changes.ChangeFinder()
    lines: list[str] = []
    per_field: dict[str, int] = {}
    pages = bad = 0
    for rec in inputs.files_in_order(TRIAL_SOURCES):
        if not str(rec.get("name", "")).endswith(".json"):
            continue
        pages += 1
        for study in page_studies(inputs.read(rec)):
            try:
                found = finder.add(study, str(rec["path"]), str(rec.get("ts") or ""))
            except (KeyError, TypeError, AttributeError):
                bad += 1  # a record without a trial number or with an unexpected layout: counted, not guessed at
                continue
            for line in found:
                per_field[line["field"]] = per_field.get(line["field"], 0) + 1
                lines.append(json.dumps(line, ensure_ascii=False, separators=(",", ":")))
    if not pages:
        raise InputError("the archive holds no trial records")
    folder = changes_dir()
    label = free_label(date.today(), [(folder, "changes.jsonl"), (folder, "changes-inputs.txt")])
    facts: dict[str, object] = {
        "pages_read": pages,
        "copies_of_records_read": finder.copies,
        "trials": finder.trials,
        "records_not_readable": bad,
        "changes": len(lines),
        "trials_with_a_change": len({json.loads(x)["nct"] for x in lines}),
        **{f"changes_{name}": per_field.get(name, 0) for name in changes.FIELDS},
    }
    head = [f"# changes in trial records since the baseline; made: {iso(utcnow())}"]
    head += [f"# {key}: {value}" for key, value in facts.items()]
    head.append("# files read from the archive (fingerprint, path):")
    # The list of inputs is written first: a result never exists without the record of what it was made from.
    write_new(folder / f"{label}_changes-inputs.txt", "\n".join(head) + "\n" + inputs.listing())
    write_new(folder / f"{label}_changes.jsonl", "".join(x + "\n" for x in lines))
    for key, value in facts.items():
        print(f"{key:32} {value}")
    print(f"written: {folder / f'{label}_changes.jsonl'}")
    return 0 if not bad else 1


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

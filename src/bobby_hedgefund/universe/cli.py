"""Command line for the universe and linking table: `bobby-universe candidates | sponsor-names`.

Reads the archive, writes dated private files next to it. Downloads nothing and changes nothing in the archive.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from ..archive.cli import archive_root, data_dir
from ..archive.store import iso, utcnow
from . import candidates, read_trials
from .inputs import InputError, Inputs
from .output import OutputError, csv_text, free_label, write_new
from .read_sec import ReadError

TRIAL_SOURCES = ("ctgov-baseline", "ctgov-updates")  # read together, in the order the pages were saved


def universe_dir() -> Path:
    return data_dir() / "universe"


def linking_dir() -> Path:
    return data_dir() / "linking"


def _inputs_text(title: str, facts: Mapping[str, object], inputs: Inputs) -> str:
    lines = [f"# {title}", f"# made: {iso(utcnow())}"]
    lines += [f"# {key}: {value}" for key, value in facts.items()]
    lines.append("# files read from the archive (fingerprint, path):")
    return "\n".join(lines) + "\n" + inputs.listing()


def cmd_candidates(args: argparse.Namespace) -> int:
    inputs = Inputs(archive_root())
    result = candidates.build(inputs, allow_partial=args.allow_partial)
    folder = universe_dir()
    endings = ["candidates.csv", "inputs.txt", "xbi-unmatched.csv"]
    label = free_label(date.today(), [(folder, e) for e in endings])
    # The list of inputs is written first: a result never exists without the record of what it was made from.
    write_new(folder / f"{label}_inputs.txt", _inputs_text("candidate list", result.counts, inputs))
    if result.xbi_unmatched:
        text = csv_text(("name_in_holdings_file", "ticker", "why"), result.xbi_unmatched)
        write_new(folder / f"{label}_xbi-unmatched.csv", text)
    write_new(folder / f"{label}_candidates.csv", csv_text(candidates.HEADER, (c.row() for c in result.candidates)))
    for key, value in result.counts.items():
        print(f"{key:28} {value}")
    print(f"written: {folder / f'{label}_candidates.csv'}")
    return 0


def cmd_sponsor_names(_: argparse.Namespace) -> int:
    inputs = Inputs(archive_root())
    collector = read_trials.SponsorCollector()
    pages = 0
    # Oldest page first across both sources, so the copy of a trial that was saved last is the one that counts.
    for rec in inputs.files_in_order(TRIAL_SOURCES):
        if str(rec.get("name", "")).endswith(".json"):
            collector.add_page(inputs.read(rec))
            pages += 1
    if not pages:
        raise InputError("the archive holds no trial records")
    names = collector.names()
    rows = (
        (
            s.name,
            " ".join(sorted(c or "none" for c in s.classes)),
            len(s.trials),
            len(s.lead),
            len(s.collaborator),
            max(s.trials),
        )
        for s in names
    )
    header = ("sponsor_name", "classes", "trials", "as_lead", "as_collaborator", "example_trial")
    folder = linking_dir()
    label = free_label(date.today(), [(folder, "sponsor-names.csv"), (folder, "sponsor-names-inputs.txt")])
    facts = {"pages_read": pages, "trials": collector.n_trials, "sponsor_names": len(names)}
    write_new(folder / f"{label}_sponsor-names-inputs.txt", _inputs_text("sponsor names", facts, inputs))
    write_new(folder / f"{label}_sponsor-names.csv", csv_text(header, rows))
    for key, value in facts.items():
        print(f"{key:28} {value}")
    print(f"written: {folder / f'{label}_sponsor-names.csv'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bobby-universe", description="Candidate list and sponsor names from archived files. Private output."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_cand = sub.add_parser("candidates", help="companies that can enter the universe, before the filter")
    p_cand.add_argument(
        "--allow-partial", action="store_true", help="also run while the SEC company files are incomplete (a try-out)"
    )
    p_cand.set_defaults(func=cmd_candidates)
    sub.add_parser("sponsor-names", help="distinct company-like sponsor names in the trial records").set_defaults(
        func=cmd_sponsor_names
    )
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

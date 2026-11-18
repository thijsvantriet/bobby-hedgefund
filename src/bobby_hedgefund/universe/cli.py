"""Command line for the universe and linking table: `bobby-universe <command>`, with the commands
`candidates`, `build`, `sponsor-names`, `match`, `decisions`, `linking` and `missed-check`.

Reads the archive, writes dated private files next to it. Downloads nothing and changes nothing in the archive.
"""

from __future__ import annotations

import argparse
import csv
import random
import secrets
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from ..archive.cli import archive_root, data_dir
from ..archive.store import iso, sha256_hex, utcnow
from . import build, candidates, decisions, match, read_trials, review
from .inputs import InputError, Inputs
from .output import OutputError, csv_text, free_label, plain_cell, write_new, write_new_bytes
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


def prices_root() -> Path:
    return data_dir() / "prices"


def cmd_build(_: argparse.Namespace) -> int:
    arch, price_inputs = Inputs(archive_root()), Inputs(prices_root())
    marks = decisions.current(decisions.load(linking_dir()))
    not_biotech = frozenset(cik for (cik, _), rec in marks.items() if rec.get("decision") == "not biotech")
    result = build.build(arch, price_inputs, not_biotech)
    folder = universe_dir()
    label = free_label(date.today(), [(folder, "universe.csv"), (folder, "universe-inputs.txt")])
    text = _inputs_text("universe", result.counts, arch)
    text += "# files read from the prices folder (fingerprint, path):\n" + price_inputs.listing()
    write_new(folder / f"{label}_universe-inputs.txt", text)
    write_new(folder / f"{label}_universe.csv", csv_text(build.HEADER, (line.row() for line in result.lines)))
    for key, value in result.counts.items():
        print(f"{key:44} {value}")
    print(f"written: {folder / f'{label}_universe.csv'}")
    return 0


def _collect_sponsors(inputs: Inputs) -> tuple[read_trials.SponsorCollector, int]:
    collector = read_trials.SponsorCollector()
    pages = 0
    # Oldest page first across both sources, so the copy of a trial that was saved last is the one that counts.
    for rec in inputs.files_in_order(TRIAL_SOURCES):
        if str(rec.get("name", "")).endswith(".json"):
            collector.add_page(inputs.read(rec))
            pages += 1
    if not pages:
        raise InputError("the archive holds no trial records")
    return collector, pages


def _newest_universe() -> tuple[Path, list[match.Company]]:
    """The newest universe file and the companies that are in the universe according to it."""
    files = sorted(universe_dir().glob("*_universe.csv"), key=lambda p: (p.stat().st_mtime, p.name))
    if not files:
        raise InputError("no universe file yet: run `bobby-universe build` first")
    path = files[-1]
    try:
        rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
        companies = [
            match.Company(
                cik=int(r["cik"]),
                name=plain_cell(r["name"]),
                ticker=r["ticker_used"],
                former_names=tuple(plain_cell(n) for n in r["former_names"].split(" | ") if n),
            )
            for r in rows
            if r["in_universe"] == "yes"
        ]
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise InputError(f"{path.name} is not a universe file ({type(exc).__name__})") from exc
    return path, sorted(companies, key=lambda c: c.name.lower())


def _file_line(path: Path) -> str:
    return f"{sha256_hex(path.read_bytes())}  {path.parent.name}/{path.name}\n"


def cmd_match(_: argparse.Namespace) -> int:
    universe_file, companies = _newest_universe()
    inputs = Inputs(archive_root())
    collector, pages = _collect_sponsors(inputs)
    sponsors = collector.names()
    suggestions = match.suggest(companies, sponsors)
    table = review.rows(companies, suggestions)
    folder = linking_dir()
    endings = ("review.xlsx", "review.csv", "review-inputs.txt")
    label = free_label(date.today(), [(folder, e) for e in endings])
    with_suggestion = len({s.company.cik for s in suggestions})
    facts: dict[str, object] = {
        "universe_file": universe_file.name,
        "companies": len(companies),
        "companies_with_a_suggestion": with_suggestion,
        "companies_without": len(companies) - with_suggestion,
        "sponsor_names_compared": len(sponsors),
        "suggestions": len(suggestions),
        **{f"suggestions_{kind}": sum(s.kind == kind for s in suggestions) for kind in match.KINDS},
        "suggestions_through_a_former_name": sum(s.is_former_name for s in suggestions),
    }
    text = _inputs_text("review sheet of suggested matches", {**facts, "pages_read": pages}, inputs)
    text += "# universe file (fingerprint, path):\n" + _file_line(universe_file)
    write_new(folder / f"{label}_review-inputs.txt", text)
    write_new(folder / f"{label}_review.csv", review.machine_copy(table))  # the copy that is never edited
    write_new_bytes(folder / f"{label}_review.xlsx", review.workbook(table), editable=True)
    for key, value in facts.items():
        print(f"{key:36} {value}")
    print(f"for the owner to fill in: {folder / f'{label}_review.xlsx'}")
    return 0


def cmd_decisions(args: argparse.Namespace) -> int:
    sheet = Path(args.sheet).expanduser()
    if sheet.suffix != ".xlsx" or not sheet.name.endswith("_review.xlsx"):
        raise decisions.DecisionError("give the filled-in review sheet (a file ending in _review.xlsx)")
    # The machine copy is looked up next to the sheet's original place, never in a folder named by the sheet.
    copy = linking_dir() / (sheet.name.removesuffix(".xlsx") + ".csv")
    found, undecided = review.read_decisions(sheet, copy)
    counts = decisions.append(linking_dir(), found, iso(utcnow()))
    print(
        f"decisions read: {len(found)}; new: {counts['added']}; changed: {counts['changed']}; "
        f"same as before: {counts['same']}; lines still undecided: {undecided}"
    )
    print(f"kept in: {linking_dir() / decisions.FILE}")
    return 0


def cmd_linking(_: argparse.Namespace) -> int:
    lines = decisions.load(linking_dir())
    now = decisions.current(lines)
    inputs = Inputs(archive_root())
    collector, pages = _collect_sponsors(inputs)
    by_name = {s.name: s for s in collector.names()}
    rows = []
    gone = 0
    for (cik, sponsor_name), rec in sorted(now.items(), key=lambda kv: (str(kv[1].get("company")).lower(), kv[0])):
        if rec.get("decision") not in decisions.LINKED:
            continue
        sponsor = by_name.get(sponsor_name)
        gone += sponsor is None  # the name no longer occurs in the registry: the link stays, without trials
        trials = sorted(sponsor.trials) if sponsor else []
        lead = len(sponsor.lead) if sponsor else 0
        rows.append((cik, rec.get("company") or "", sponsor_name, rec["decision"], len(trials), lead, " ".join(trials)))
    folder = linking_dir()
    label = free_label(date.today(), [(folder, "linking.csv"), (folder, "linking-inputs.txt")])
    facts: dict[str, object] = {
        "decision_lines": len(lines),
        "decisions_that_count": len(now),
        "linked_sponsor_names": len(rows),
        "companies_with_a_link": len({r[0] for r in rows}),
        "companies_marked_not_biotech": sum(r.get("decision") == "not biotech" for r in now.values()),
        "linked_names_no_longer_in_the_registry": gone,
        "trials_linked": len({t for r in rows for t in str(r[6]).split()}),
        "note": "trials run by a partner under another sponsor name are missing until the drug-name step is built",
    }
    text = _inputs_text("linking table", {**facts, "pages_read": pages}, inputs)
    if lines:
        text += f"# decisions file: {len(lines)} lines, fingerprint of the last line {lines[-1]['_sha256']}\n"
    write_new(folder / f"{label}_linking-inputs.txt", text)
    header = ("cik", "company", "sponsor_name", "relation", "trials", "as_lead", "trial_numbers")
    write_new(folder / f"{label}_linking.csv", csv_text(header, rows))
    for key, value in facts.items():
        print(f"{key:40} {value}")
    print(f"written: {folder / f'{label}_linking.csv'}")
    return 0


def cmd_missed_check(args: argparse.Namespace) -> int:
    """Draw companies at random for the by-hand search of record 0006, point 3.5."""
    _, companies = _newest_universe()
    seed = args.seed if args.seed is not None else secrets.randbelow(10**9)
    drawn = random.Random(seed).sample(companies, min(args.count, len(companies)))
    now = decisions.current(decisions.load(linking_dir()))
    header = ("cik", "company", "ticker", "former_names", "sponsor_names_linked_so_far", "found_by_hand_and_missing")
    rows = []
    for c in sorted(drawn, key=lambda c: c.name.lower()):
        linked = sorted(n for (cik, n), r in now.items() if cik == c.cik and r.get("decision") in decisions.LINKED)
        rows.append((c.cik, c.name, c.ticker, " | ".join(c.former_names), " | ".join(linked), ""))
    folder = linking_dir()
    label = free_label(date.today(), [(folder, "missed-check.csv")])
    write_new_bytes(folder / f"{label}_missed-check.csv", csv_text(header, rows).encode("utf-8"), editable=True)
    print(f"drawn: {len(rows)} companies, with random seed {seed} (the same seed draws the same companies)")
    print("For each: search the registry by hand for the company and its drugs, and write in the last column")
    print("every sponsor name that is the company but is not in the linked names.")
    print(f"written: {folder / f'{label}_missed-check.csv'}")
    return 0


def cmd_sponsor_names(_: argparse.Namespace) -> int:
    inputs = Inputs(archive_root())
    collector, pages = _collect_sponsors(inputs)
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
    sub.add_parser(
        "build", help="the universe: the candidates put through the filter on size, trading and price"
    ).set_defaults(func=cmd_build)
    sub.add_parser(
        "match", help="suggest sponsor names for every company in the universe; writes the review sheet"
    ).set_defaults(func=cmd_match)
    p_dec = sub.add_parser("decisions", help="take over the owner's decisions from a filled-in review sheet")
    p_dec.add_argument("sheet", help="the filled-in file ending in _review.xlsx")
    p_dec.set_defaults(func=cmd_decisions)
    sub.add_parser("linking", help="the linking table as it follows from the decisions so far").set_defaults(
        func=cmd_linking
    )
    p_missed = sub.add_parser("missed-check", help="draw companies at random for a by-hand search of missed names")
    p_missed.add_argument("--count", type=int, default=20)
    p_missed.add_argument("--seed", type=int, help="repeat an earlier draw")
    p_missed.set_defaults(func=cmd_missed_check)
    sub.add_parser("sponsor-names", help="distinct company-like sponsor names in the trial records").set_defaults(
        func=cmd_sponsor_names
    )
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (InputError, ReadError, OutputError, decisions.DecisionError) as exc:
        print(f"NOT DONE: {exc}")
        return 1
    except OSError as exc:
        print(f"NOT DONE: could not read or write a file: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

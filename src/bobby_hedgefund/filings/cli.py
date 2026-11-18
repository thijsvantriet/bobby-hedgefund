"""Command line for stored filings: `bobby-filings recent`. Reads the archive; no network, nothing written."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from ..archive.cli import archive_root, data_dir
from ..archive.sec_filings import FILINGS_SOURCE
from ..universe import current
from ..universe.inputs import InputError, Inputs
from . import read


def _detail(form: str, body: bytes) -> str:
    base = form.upper().removesuffix("/A")
    if base == "8-K":
        return "; ".join(read.header(body).items) or "(no items listed)"
    if base == "4":
        trades = read.insider_trades(body)
        if not trades:
            return "no transactions"
        first = trades[0]
        codes = " ".join(sorted({t.code for t in trades}))
        return (
            f"{first.owner} [{', '.join(first.roles) or 'role not given'}]: {len(trades)} transaction(s), codes {codes}"
        )
    names = [name for role, name in read.header(body).names if role == "filed by"]
    return f"filed by {', '.join(names)}" if names else ""


def cmd_recent(args: argparse.Namespace) -> int:
    inputs = Inputs(archive_root())
    since = (date.today() - timedelta(days=args.days)).isoformat()
    try:
        names = {c.cik: c.name for c in current.newest_universe(data_dir() / "universe")[1]}
    except InputError:
        names = {}
    shown = bad = 0
    recs = [r for r in inputs.files(FILINGS_SOURCE) if isinstance(r.get("meta"), dict) and "accession" in r["meta"]]
    for rec in sorted(recs, key=lambda r: (str(r["meta"].get("filed")), str(r["meta"].get("accession")))):
        meta = rec["meta"]
        if str(meta.get("filed")) < since or (args.form and str(meta.get("form")).upper() != args.form.upper()):
            continue
        try:
            detail = _detail(str(meta.get("form")), inputs.read(rec))
        except (read.FilingError, InputError) as exc:
            detail, bad = f"NOT READABLE: {exc}", bad + 1
        company = names.get(meta.get("cik"), f"company {meta.get('cik')}")
        print(f"{meta.get('filed')}  {meta.get('form')!s:14} {company[:34]:34} {detail}")
        shown += 1
    print(f"{shown} filing(s) since {since}" + (f"; {bad} not readable" if bad else ""))
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bobby-filings", description="Look at stored SEC filings. No downloads.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_recent = sub.add_parser("recent", help="stored filings of the last days, with the items or trades they report")
    p_recent.add_argument("--days", type=int, default=7)
    p_recent.add_argument("--form", help="only this form type, for example 8-K or 4")
    p_recent.set_defaults(func=cmd_recent)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except InputError as exc:
        print(f"NOT DONE: {exc}")
        return 1
    except OSError as exc:
        print(f"NOT DONE: could not read the archive: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

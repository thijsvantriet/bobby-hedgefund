"""The newest universe file, and the companies that are in the universe according to it."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from .inputs import InputError
from .match import Company
from .output import plain_cell


def newest_universe(folder: Path) -> tuple[Path, list[Company]]:
    """The newest `*_universe.csv` in `folder` and its companies marked "in", sorted by name."""
    files = [p for p in folder.glob("*_universe.csv") if not p.name.startswith(".")] if folder.is_dir() else []
    files.sort(key=lambda p: (p.stat().st_mtime, p.name))
    if not files:
        raise InputError("no universe file yet: run `bobby-universe build` first")
    path = files[-1]
    try:
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))
        companies = [
            Company(
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

"""What the fund books need from a universe file (docs/decisions/0006): who is in, the ticker, the market value
for the trading cost, and which companies came in through the XBI fund only. The file is private."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from ..archive.store import sha256_hex
from ..universe.inputs import InputError
from ..universe.output import plain_cell

XBI_ONLY = "xbi only"


@dataclass(frozen=True)
class Listed:
    cik: int
    name: str
    ticker: str
    market_value: int | None  # whole dollars, as of the universe run
    xbi_only: bool


@dataclass(frozen=True)
class Universe:
    file: str
    sha256: str
    companies: dict[int, Listed]  # the companies that are in

    def market_value(self, cik: int) -> int | None:
        company = self.companies.get(cik)
        return company.market_value if company is not None else None

    def buyable(self) -> set[int]:
        """The companies a fund may buy: in the universe, and not there through the XBI fund only (those may
        never be named in public, so they get no analysis and no orders; docs/decisions/0009, open point 2)."""
        return {cik for cik, c in self.companies.items() if not c.xbi_only}


def newest_path(folder: Path) -> Path:
    """The newest `*_universe.csv` in `folder` (the same choice as `universe.current.newest_universe`)."""
    files = [p for p in folder.glob("*_universe.csv") if not p.name.startswith(".")] if folder.is_dir() else []
    if not files:
        raise InputError("no universe file yet: run `bobby-universe build` first")
    return max(files, key=lambda p: (p.stat().st_mtime, p.name))


def load(path: Path) -> Universe:
    data = path.read_bytes()
    try:
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))
        companies = {
            int(r["cik"]): Listed(
                cik=int(r["cik"]),
                name=plain_cell(r["name"]),
                ticker=r["ticker_used"],
                market_value=int(float(r["market_value"])) if r.get("market_value") else None,
                xbi_only=r.get("door") == XBI_ONLY,
            )
            for r in rows
            if r["in_universe"] == "yes"
        }
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise InputError(f"{path.name} is not a universe file ({type(exc).__name__})") from exc
    return Universe(path.name, sha256_hex(data), companies)


def covered_list(reports: Path) -> set[int]:
    """The covered list (docs/SPEC.md section 4): the companies that have an analyst report. A report is a file
    in `reports/<SEC number>/`; only these companies can be bought, by any fund."""
    if not reports.is_dir():
        return set()
    return {
        int(folder.name)
        for folder in reports.iterdir()
        if folder.is_dir() and folder.name.isdigit() and any(f.suffix == ".md" for f in folder.iterdir())
    }

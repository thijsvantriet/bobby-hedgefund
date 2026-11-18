"""Read the XBI fund's daily holdings file from the archive. The file is a private copy: what is read here goes
into private files only and is never published (docs/decisions/0001 and 0006)."""

from __future__ import annotations

import io
from dataclasses import dataclass

from openpyxl import load_workbook

from .read_sec import ReadError


@dataclass(frozen=True)
class Holding:
    name: str
    ticker: str


def holdings(body: bytes) -> list[Holding]:
    """The holdings that are shares: lines with a name and a ticker. Cash and other lines without a ticker are
    left out."""
    try:
        book = load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    except Exception as exc:  # the library raises several unrelated error types on a damaged file
        raise ReadError(f"the holdings file could not be opened ({type(exc).__name__})") from exc
    try:
        sheet = book.worksheets[0]
        columns: dict[str, int] | None = None
        found: list[Holding] = []
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if c is None else str(c).strip() for c in row]
            if columns is None:
                if "Name" in cells and "Ticker" in cells:
                    columns = {"name": cells.index("Name"), "ticker": cells.index("Ticker")}
                continue
            if len(cells) <= max(columns.values()):
                continue
            name, ticker = cells[columns["name"]], cells[columns["ticker"]].upper()
            if name and ticker and ticker != "-":
                found.append(Holding(name=name, ticker=ticker))
    finally:
        book.close()
    if columns is None:
        raise ReadError("the holdings file has no header line with Name and Ticker")
    if not found:
        raise ReadError("the holdings file lists no holdings")
    return found

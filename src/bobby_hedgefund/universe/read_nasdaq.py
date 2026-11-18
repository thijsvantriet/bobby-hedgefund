"""Read the Nasdaq symbol lists from the archive. Used only as a private check on the SEC's tickers."""

from __future__ import annotations

from .read_sec import ReadError

# file name -> (column with the symbol, column that marks a test issue)
LISTS = {"nasdaqlisted.txt": ("Symbol", "Test Issue"), "otherlisted.txt": ("ACT Symbol", "Test Issue")}


def symbols(name: str, body: bytes) -> set[str]:
    """The symbols in one list, without test issues and without the closing "File Creation Time" line."""
    symbol_column, test_column = LISTS[name]
    lines = body.decode("utf-8", errors="replace").splitlines()
    if not lines:
        raise ReadError(f"{name} is empty")
    header = lines[0].split("|")
    if symbol_column not in header or test_column not in header:
        raise ReadError(f"{name} does not have the expected columns")
    i_symbol, i_test = header.index(symbol_column), header.index(test_column)
    found: set[str] = set()
    for line in lines[1:]:
        cells = line.split("|")
        if line.startswith("File Creation Time") or len(cells) <= max(i_symbol, i_test):
            continue
        if cells[i_test].strip().upper() != "Y" and cells[i_symbol].strip():
            found.add(cells[i_symbol].strip().upper())
    return found


def dashed(ticker: str) -> str:
    """One spelling for a share class: the SEC writes it with a dash (BRK-B), other files with a dot (BRK.B)."""
    return ticker.replace(".", "-")


def stripped(ticker: str) -> str:
    """The ticker without the share-class mark. Two different companies can share this form (AB-C and ABC), so it
    is only ever used as a last resort, and only when it points to exactly one company."""
    return ticker.replace(".", "").replace("-", "")

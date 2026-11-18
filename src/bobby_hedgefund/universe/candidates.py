"""The candidate list: every company that can enter the universe through one of its doors, before the filter.

Doors (docs/decisions/0006): an industry code of our own choice, or a place in the XBI fund. The filter on size,
trading and price comes later and needs prices. The list holds the XBI flag and is therefore private.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..archive.sec import NOT_LISTED, SEC_SOURCE, TICKERS_NAME, submissions_name
from . import read_nasdaq, read_sec, read_xbi
from .inputs import InputError, Inputs

# Pharmaceutical preparations, biological products, research services, diagnostics (record 0006, option a).
OWN_CODES = frozenset({"2834", "2836", "8731", "2835"})
XBI_SOURCE, XBI_NAME = "ssga-xbi", "holdings-xbi.xlsx"
NASDAQ_SOURCE = "nasdaq-symdir"

HEADER = (
    "cik",
    "name",
    "tickers",
    "exchanges",
    "sic",
    "sic_description",
    "door",
    "in_xbi",
    "filer_type",
    "in_version_1",
    "ticker_check",
    "former_names",
    "filing_list_saved",
    "name_in_xbi_file",
)


@dataclass(frozen=True)
class Candidate:
    cik: int
    name: str
    tickers: tuple[str, ...]
    exchanges: tuple[str, ...]
    sic: str
    sic_description: str
    door: str  # "own code", "own code + xbi" or "xbi only"
    in_xbi: bool
    filer_type: str
    ticker_check: str
    former_names: tuple[str, ...]
    filing_list_saved: str
    name_in_xbi_file: str = ""  # the link was made by ticker, so the fund's own name is shown next to the SEC's

    @property
    def in_version_1(self) -> bool:
        return self.filer_type != "foreign"  # foreign filers are left out of version 1; "unknown" stays visible

    def row(self) -> tuple[object, ...]:
        return (
            self.cik,
            self.name,
            " ".join(self.tickers),
            " ".join(self.exchanges),
            self.sic,
            self.sic_description,
            self.door,
            "yes" if self.in_xbi else "no",
            self.filer_type,
            "yes" if self.in_version_1 else "no",
            self.ticker_check,
            " | ".join(self.former_names),
            self.filing_list_saved,
            self.name_in_xbi_file,
        )


@dataclass
class Result:
    candidates: list[Candidate] = field(default_factory=list)
    xbi_unmatched: list[tuple[str, str, str]] = field(default_factory=list)  # name, ticker, why
    counts: dict[str, Any] = field(default_factory=dict)


def sec_batch(inputs: Inputs) -> tuple[dict[str, Any], str, bool]:
    """The newest ticker file, its batch, and whether that batch was fetched completely."""
    rec = inputs.newest(SEC_SOURCE, TICKERS_NAME)
    meta = rec.get("meta")
    batch = str(meta.get("batch")) if isinstance(meta, dict) else ""
    complete = any(
        r.get("status") == "ok"
        and isinstance(r.get("meta"), dict)
        and r["meta"].get("batch") == batch
        and r["meta"].get("complete") is True
        for r in inputs.runs(SEC_SOURCE)
    )
    return rec, batch, complete


def _ticker_check(tickers: tuple[str, ...], listed_symbols: set[str]) -> str:
    """`listed_symbols` are in the dashed spelling. Only the same ticker counts, never a look-alike."""
    absent = [t for t in tickers if read_nasdaq.dashed(t) not in listed_symbols]
    return "ok" if not absent else "not in the Nasdaq lists: " + " ".join(absent)


class TickerIndex:
    """Find the company behind a ticker from another file. A wrong link is worse than no link: the same spelling
    wins, then the same ticker with dot and dash treated alike, and only then the form without the share-class
    mark. A form that points to more than one company gives no link at all."""

    def __init__(self) -> None:
        self._exact: dict[str, set[int]] = {}
        self._dashed: dict[str, set[int]] = {}
        self._stripped: dict[str, set[int]] = {}

    def add(self, ticker: str, cik: int) -> None:
        self._exact.setdefault(ticker, set()).add(cik)
        self._dashed.setdefault(read_nasdaq.dashed(ticker), set()).add(cik)
        self._stripped.setdefault(read_nasdaq.stripped(ticker), set()).add(cik)

    def find(self, ticker: str) -> tuple[int | None, str]:
        """(company number, "") or (None, why not)."""
        steps = (
            self._exact.get(ticker),
            self._dashed.get(read_nasdaq.dashed(ticker)),
            self._stripped.get(read_nasdaq.stripped(ticker)),
        )
        for found in steps:
            if found:
                if len(found) == 1:
                    return next(iter(found)), ""
                return None, "ticker fits more than one company in the SEC's ticker file"
        return None, "ticker not in the SEC's ticker file"


def build(inputs: Inputs, *, allow_partial: bool = False) -> Result:
    tickers_rec, batch, complete = sec_batch(inputs)
    if not complete and not allow_partial:
        raise InputError("the newest batch of SEC company files is not complete; finish it with --resume first")
    rows = read_sec.ticker_rows(inputs.read(tickers_rec))

    tickers_of: dict[int, list[str]] = {}
    exchanges_of: dict[int, list[str]] = {}
    index = TickerIndex()
    for row in rows:
        tickers_of.setdefault(row.cik, [])
        exchanges_of.setdefault(row.cik, [])
        if row.ticker and row.ticker not in tickers_of[row.cik]:
            tickers_of[row.cik].append(row.ticker)
        if row.exchange and row.exchange not in exchanges_of[row.cik]:
            exchanges_of[row.cik].append(row.exchange)
        if row.ticker:
            index.add(row.ticker, row.cik)
    listed = sorted(cik for cik, found in exchanges_of.items() if any(e not in NOT_LISTED for e in found))
    is_listed = set(listed)

    result = Result()
    xbi_names: dict[int, list[str]] = {}
    holdings = read_xbi.holdings(inputs.read(inputs.newest(XBI_SOURCE, XBI_NAME)))
    for holding in holdings:
        cik, why_not = index.find(holding.ticker)
        if cik is None:
            result.xbi_unmatched.append((holding.name, holding.ticker, why_not))
        elif cik not in is_listed:
            result.xbi_unmatched.append((holding.name, holding.ticker, "no exchange listing in the SEC's ticker file"))
        else:
            xbi_names.setdefault(cik, []).append(holding.name)
    xbi_ciks = set(xbi_names)

    listed_symbols: set[str] = set()
    for name in read_nasdaq.LISTS:
        found_symbols = read_nasdaq.symbols(name, inputs.read(inputs.newest(NASDAQ_SOURCE, name)))
        listed_symbols |= {read_nasdaq.dashed(s) for s in found_symbols}

    without_list = older_batch = 0
    for cik in listed:
        found = inputs.files(SEC_SOURCE, submissions_name(cik))
        if not found:
            without_list += 1
            if cik in xbi_ciks:
                ticker = " ".join(tickers_of[cik])
                result.xbi_unmatched.append((f"company number {cik}", ticker, "no filing list in the archive"))
            continue
        company = read_sec.company(inputs.read(found[-1]))
        if company.cik != cik:
            raise InputError(f"the stored filing list of company {cik} belongs to another company")
        own, in_xbi = company.sic in OWN_CODES, cik in xbi_ciks
        if not (own or in_xbi):
            continue
        tickers = tuple(tickers_of[cik])
        list_meta = found[-1].get("meta")
        if not isinstance(list_meta, dict) or list_meta.get("batch") != batch:
            older_batch += 1  # this batch did not store the company's list: an older copy is used
        result.candidates.append(
            Candidate(
                cik=cik,
                name=company.name,
                tickers=tickers,
                exchanges=tuple(exchanges_of[cik]),
                sic=company.sic,
                sic_description=company.sic_description,
                door="own code + xbi" if own and in_xbi else "own code" if own else "xbi only",
                in_xbi=in_xbi,
                filer_type=company.filer_type,
                ticker_check=_ticker_check(tickers, listed_symbols),
                former_names=company.former_names,
                filing_list_saved=str(found[-1].get("ts") or ""),
                name_in_xbi_file=" | ".join(xbi_names.get(cik, [])),
            )
        )

    c = result.candidates
    v1 = [x for x in c if x.in_version_1]
    result.counts = {
        "sec_batch": batch,
        "sec_batch_complete": complete,
        "listed_companies": len(listed),
        "without_filing_list": without_list,
        "candidates_with_filing_list_from_older_batch": older_batch,
        "candidates": len(c),
        "door_own_code": sum(x.door == "own code" for x in c),
        "door_own_code_and_xbi": sum(x.door == "own code + xbi" for x in c),
        "door_xbi_only": sum(x.door == "xbi only" for x in c),
        "foreign_filers_left_out": sum(x.filer_type == "foreign" for x in c),
        "filer_type_unknown": sum(x.filer_type == "unknown" for x in c),
        "in_version_1": len(v1),
        "in_version_1_xbi_only": sum(x.door == "xbi only" for x in v1),
        "ticker_not_in_nasdaq_lists": sum(x.ticker_check != "ok" for x in c),
        "xbi_holdings": len(holdings),
        "xbi_matched": len(xbi_ciks),
        "xbi_unmatched": len(result.xbi_unmatched),
    }
    return result

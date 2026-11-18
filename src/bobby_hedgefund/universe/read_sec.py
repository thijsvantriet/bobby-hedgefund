"""Read the SEC's ticker file and a company's filing-list file (stored by `bobby-archive sec-companies`)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# The yearly report tells how a company reports: 10-K is the domestic form, 20-F and 40-F are the forms for
# companies that report to the SEC as foreign companies (left out of version 1, docs/decisions/0006).
DOMESTIC_YEARLY = frozenset({"10-K", "10-KT", "10-K405", "10-KSB"})
FOREIGN_YEARLY = frozenset({"20-F", "40-F"})
DOMESTIC_OTHER = frozenset({"10-Q", "S-1", "8-K"})
FOREIGN_OTHER = frozenset({"6-K", "F-1"})


class ReadError(Exception):
    """An archived file does not have the expected layout."""


@dataclass(frozen=True)
class TickerRow:
    cik: int
    name: str
    ticker: str
    exchange: str


@dataclass(frozen=True)
class Company:
    cik: int
    name: str
    former_names: tuple[str, ...]
    sic: str
    sic_description: str
    entity_type: str
    tickers: tuple[str, ...]
    exchanges: tuple[str, ...]
    filer_type: str  # "domestic", "foreign" or "unknown"


def ticker_rows(body: bytes) -> list[TickerRow]:
    try:
        doc = json.loads(body)
        fields = doc["fields"]
        i = {name: fields.index(name) for name in ("cik", "name", "ticker", "exchange")}
        return [
            TickerRow(
                cik=int(row[i["cik"]]),
                name=str(row[i["name"]] or ""),
                ticker=str(row[i["ticker"]] or "").strip().upper(),
                exchange=str(row[i["exchange"]] or "").strip(),
            )
            for row in doc["data"]
        ]
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise ReadError(f"the ticker file is not the expected JSON ({type(exc).__name__})") from exc


def _base_form(form: str) -> str:
    return form.strip().upper().removesuffix("/A")


def filer_type(forms: list[str]) -> str:
    """How the company reports, judged from its filings, newest first. The newest yearly report decides; a company
    too young to have one is judged by its other forms."""
    base = [_base_form(f) for f in forms]
    for form in base:
        if form in DOMESTIC_YEARLY:
            return "domestic"
        if form in FOREIGN_YEARLY:
            return "foreign"
    domestic = any(f in DOMESTIC_OTHER for f in base)
    foreign = any(f in FOREIGN_OTHER for f in base)
    if foreign and not domestic:
        return "foreign"
    if domestic and not foreign:
        return "domestic"
    return "unknown"


def _text_list(value: Any) -> tuple[str, ...]:
    return tuple(str(x).strip() for x in value if x) if isinstance(value, list) else ()


def company(body: bytes) -> Company:
    try:
        doc = json.loads(body)
        forms = doc["filings"]["recent"].get("form") or []
        former = doc.get("formerNames") or []
        return Company(
            cik=int(doc["cik"]),
            name=str(doc.get("name") or "").strip(),
            former_names=tuple(str(f["name"]).strip() for f in former if isinstance(f, dict) and f.get("name")),
            sic=str(doc.get("sic") or "").strip(),
            sic_description=str(doc.get("sicDescription") or "").strip(),
            entity_type=str(doc.get("entityType") or "").strip(),
            tickers=tuple(t.upper() for t in _text_list(doc.get("tickers"))),
            exchanges=_text_list(doc.get("exchanges")),
            filer_type=filer_type([str(f) for f in forms]),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ReadError(f"a filing list is not the expected JSON ({type(exc).__name__})") from exc

"""The universe: the candidate list put through the filter of docs/decisions/0006, point 2.

    market value   = reported shares (all classes) x the last closing price     $300 million to $10 billion
    traded per day = average of closing price x volume, last 60 trading days    at least $2 million
    share price    = the last closing price                                     at least $2
    listed on an exchange we accept, not a shell company, not a foreign filer

Every candidate gets a line with the numbers used and their dates, also the ones that fail, with every rule they
fail. The result holds prices and the XBI flag: private, never published.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from ..archive import sec_shares
from ..archive.sec_shares import CONCEPTS, SHARES_SOURCE, shares_name
from ..prices import read as prices
from . import candidates, read_shares
from .inputs import InputError, Inputs

MIN_VALUE, MAX_VALUE = 300e6, 10e9
MIN_TRADED = 2e6
MIN_PRICE = 2.0
TRADING_DAYS = 60
STALE_AFTER_DAYS = 5  # a share without a price for this many trading days no longer trades (taken over, removed)
# In the SEC's ticker file "NYSE" also covers NYSE American. Other exchanges and unlisted shares are out.
ACCEPTED_EXCHANGES = frozenset({"Nasdaq", "NYSE"})
SHELL_CODE = "6770"  # the industry code of blank-check companies
# A share count older than this says little about today; the company then counts as having none.
MAX_SHARES_AGE = timedelta(days=456)  # 15 months: a yearly report plus the time allowed to file it

HEADER = (
    "cik",
    "name",
    "in_universe",
    "why_out",
    "ticker_used",
    "exchanges",
    "sic",
    "door",
    "in_xbi",
    "filer_type",
    "shares",
    "shares_as_of",
    "shares_source",
    "shares_note",
    "last_close",
    "last_close_day",
    "market_value",
    "avg_traded_per_day",
    "days_with_prices",
    "tickers_with_prices",
    "tickers",
    "former_names",
)


@dataclass(frozen=True)
class Line:
    candidate: candidates.Candidate
    why_out: tuple[str, ...]
    ticker_used: str = ""
    count: read_shares.ShareCount | None = None
    shares: float | None = None  # after share splits since the count
    shares_note: str = ""
    last_close: float | None = None
    last_close_day: date | None = None
    market_value: float | None = None
    avg_traded: float | None = None
    days_with_prices: int = 0
    priced_tickers: tuple[str, ...] = ()

    @property
    def in_universe(self) -> bool:
        return not self.why_out

    def row(self) -> tuple[object, ...]:
        c = self.candidate
        return (
            c.cik,
            c.name,
            "yes" if self.in_universe else "no",
            "; ".join(self.why_out),
            self.ticker_used,
            " ".join(c.exchanges),
            c.sic,
            c.door,
            "yes" if c.in_xbi else "no",
            c.filer_type,
            "" if self.shares is None else round(self.shares),
            self.count.as_of.isoformat() if self.count else "",
            self.count.source if self.count else "",
            self.shares_note,
            "" if self.last_close is None else self.last_close,
            self.last_close_day.isoformat() if self.last_close_day else "",
            "" if self.market_value is None else round(self.market_value),
            "" if self.avg_traded is None else round(self.avg_traded),
            self.days_with_prices,
            " ".join(self.priced_tickers),
            " ".join(c.tickers),
            " | ".join(c.former_names),
        )


@dataclass
class Result:
    lines: list[Line] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)
    days: list[date] = field(default_factory=list)


def price_ticker(ticker: str, known: set[str]) -> str | None:
    """The spelling of an SEC ticker in the price files. Only the same ticker counts: the SEC writes a share
    class with a dash (AB-C), the price service with a dot (AB.C)."""
    for form in (ticker, ticker.replace("-", ".")):
        if form in known:
            return form
    return None


def share_count(arch: Inputs, cik: int, batch: str, as_of: date) -> tuple[read_shares.ShareCount | None, str]:
    """The newest usable share count of a company among the answers stored for this batch, and a note."""
    found: list[read_shares.ShareCount] = []
    for taxonomy, _ in CONCEPTS:
        recs = [
            r
            for r in arch.files(SHARES_SOURCE, shares_name(cik, taxonomy))
            if isinstance(r.get("meta"), dict) and r["meta"].get("batch") == batch
        ]
        if recs:
            count = read_shares.newest(arch.read(recs[-1]), taxonomy)
            if count is not None:
                found.append(count)
    if not found:
        asked = sec_shares.not_reported(arch.records, batch)
        if all((cik, taxonomy) in asked for taxonomy, _ in CONCEPTS):
            return None, "no share count reported for the company as a whole"
        return None, "no usable share count in the SEC's answers"
    best = max(found, key=lambda c: (c.as_of, c.filed, c.source == "cover page"))
    if as_of - best.as_of > MAX_SHARES_AGE:
        return None, f"newest share count is of {best.as_of.isoformat()}: too old"
    return best, best.note


def build(
    arch: Inputs, price_inputs: Inputs, not_biotech: frozenset[int] = frozenset(), *, allow_partial: bool = False
) -> Result:
    cands = candidates.build(arch)
    batch = str(cands.counts["sec_batch"])
    shares_complete = sec_shares.batch_complete(arch.records, batch)
    if not shares_complete and not allow_partial:
        # Without this check a company whose share count was simply not fetched yet would fall out unnoticed.
        raise InputError("the share counts of this batch are not complete: finish `bobby-archive sec-shares` first")
    day_recs = prices.day_records(price_inputs)
    days = list(day_recs)[-TRADING_DAYS:]
    if len(days) < TRADING_DAYS:
        raise InputError(f"the filter needs {TRADING_DAYS} trading days of prices; {len(days)} are stored")
    splits = prices.load_splits(price_inputs)
    bars = {day: prices.load_day(price_inputs, day_recs[day]) for day in days}
    last_day = days[-1]
    known = set().union(*(b.keys() for b in bars.values()))

    result = Result(days=days)
    for cand in cands.candidates:
        why: list[str] = []
        if cand.filer_type == "foreign":
            why.append("reports as a foreign company (left out of version 1)")
        if not ACCEPTED_EXCHANGES.intersection(cand.exchanges):
            why.append("not listed on an accepted exchange")
        if cand.sic == SHELL_CODE:
            why.append("shell company")
        if cand.cik in not_biotech:
            why.append("marked 'not biotech' by the owner")

        # A company can have several tickers (share classes, warrants, units, preferred shares). The one with the
        # most money traded over the 60 days is taken as the common share; all priced ones are shown.
        priced = [t for t in dict.fromkeys(price_ticker(t, known) for t in cand.tickers) if t]
        traded = {t: sum(b[t].close * b[t].volume for b in bars.values() if t in b) for t in priced}
        ticker = max(priced, key=lambda t: traded[t]) if priced else None
        count, shares_note = share_count(arch, cand.cik, batch, last_day)
        if ticker is None:
            why.append("no prices in the last 60 trading days")
            result.lines.append(Line(cand, tuple(why), count=count, shares=count.shares if count else None))
            continue
        seen = [(day, bars[day][ticker]) for day in days if ticker in bars[day]]
        close_day, last = seen[-1]
        avg_traded = sum(bar.close * bar.volume for _, bar in seen) / TRADING_DAYS
        shares = value = None
        if count is None:
            why.append(shares_note)
        else:
            # The count is from an earlier report. A share split after that report was filed changed the number
            # of shares. A split between the day of the count and the filing day is left alone: companies must
            # restate their share figures for such a split, so it is normally in the count already. It is noted,
            # because for a cover-page count that is not certain.
            factor = 1.0
            between = []
            for s in splits:
                if s.ticker != ticker:
                    continue
                if count.filed < s.day <= close_day:
                    factor *= s.split_to / s.split_from
                elif count.as_of < s.day <= count.filed:
                    between.append(s.day.isoformat())
            shares = count.shares * factor
            notes = [shares_note] if shares_note else []
            if factor != 1.0:
                notes.append(f"share split since the report: x{factor:g}")
            if between:
                notes.append(f"CHECK: share split on {', '.join(between)}, between the count and its filing")
            shares_note = "; ".join(notes)
            value = shares * last.close
            if value < MIN_VALUE:
                why.append("market value under $300 million")
            elif value > MAX_VALUE:
                why.append("market value over $10 billion")
        if close_day not in days[-STALE_AFTER_DAYS:]:
            why.append(f"no price in the last {STALE_AFTER_DAYS} trading days")
        if avg_traded < MIN_TRADED:
            why.append("under $2 million traded a day")
        if last.close < MIN_PRICE:
            why.append("share price under $2")
        result.lines.append(
            Line(
                cand,
                tuple(why),
                ticker,
                count,
                shares,
                shares_note,
                last.close,
                close_day,
                value,
                avg_traded,
                len(seen),
                tuple(priced),
            )
        )

    lines = result.lines
    inside = [x for x in lines if x.in_universe]
    reasons: dict[str, int] = {}
    for line in lines:
        for reason in line.why_out:
            key = "no usable share count" if "share count" in reason else reason.split(" (")[0]
            reasons[key] = reasons.get(key, 0) + 1
    result.counts = {
        "sec_batch": batch,
        "share_counts_complete": shares_complete,
        "price_days": f"{days[0].isoformat()} to {last_day.isoformat()}",
        "check_split_between_count_and_filing": sum("CHECK:" in x.shares_note for x in result.lines),
        "companies_with_several_priced_tickers": sum(len(x.priced_tickers) > 1 for x in result.lines),
        "candidates": len(lines),
        "in_universe": len(inside),
        "in_universe_xbi_only": sum(x.candidate.door == "xbi only" for x in inside),
        "in_universe_filer_type_unknown": sum(x.candidate.filer_type == "unknown" for x in inside),
        "xbi_members_out": sum(x.candidate.in_xbi and not x.in_universe for x in lines),
        **{f"out: {reason}": n for reason, n in sorted(reasons.items())},
    }
    return result

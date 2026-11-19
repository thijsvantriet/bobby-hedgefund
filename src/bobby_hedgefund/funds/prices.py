"""The saved price files as the fund books use them: only files stored before the data cut-off, each checked
against its fingerprint, prices as exact fractions. Nothing here is ever fetched (docs/decisions/0005, point 1)."""

from __future__ import annotations

from datetime import date, datetime
from fractions import Fraction
from pathlib import Path

from ..archive.store import iso
from ..prices import massive, read
from ..universe.inputs import InputError, Inputs

LOOK_BACK_DAYS = 30  # how far back a share without a price keeps its last one
KEPT_DAYS = 12  # price files kept in memory at a time (each is the whole market of one day)


def exact(value: float | None) -> Fraction | None:
    """A price from a price file as an exact fraction of what the file says ("12.34" stays 12.34)."""
    if value is None or value <= 0:
        return None
    return Fraction(repr(value))


class PriceBook:
    def __init__(self, root: Path, cutoff: datetime | None = None, today: date | None = None) -> None:
        self.inputs = Inputs(root)
        if cutoff is not None:
            limit = iso(cutoff)
            self.inputs.records = [r for r in self.inputs.records if str(r.get("ts", "")) < limit]
        records = self.inputs.records
        final = massive.stored_days(records, final_only=True)
        self._records = {day: rec for day, rec in read.day_records(self.inputs).items() if day in final}
        self.closed = massive.closed_days(records, today or massive.market_today(cutoff))
        self._days = sorted(self._records)
        self._bars: dict[date, dict[str, read.Bar]] = {}
        self._last: dict[tuple[str, date], tuple[Fraction, date] | None] = {}
        self._splits: list[read.Split] | None = None

    def days(self) -> list[date]:
        """The days with a final price file stored before the cut-off, oldest first."""
        return self._days

    def has(self, day: date) -> bool:
        return day in self._records

    def sha256(self, day: date) -> str:
        return str(self._records[day]["sha256"])

    def bars(self, day: date) -> dict[str, read.Bar]:
        bars = self._bars.pop(day, None)
        if bars is None:
            bars = read.load_day(self.inputs, self._records[day])
        self._bars[day] = bars  # the day used last is at the end
        while len(self._bars) > KEPT_DAYS:
            self._bars.pop(next(iter(self._bars)))  # the day that was not used for the longest time goes
        return bars

    def _bar(self, ticker: str, day: date) -> read.Bar | None:
        """Only the same ticker counts: the SEC writes a share class with a dash (AB-C), the price files with a
        point (AB.C)."""
        bars = self.bars(day)
        return bars.get(ticker) or bars.get(ticker.replace("-", "."))

    def opening(self, ticker: str, day: date) -> Fraction | None:
        bar = self._bar(ticker, day)
        return exact(bar.open) if bar is not None else None

    def close(self, ticker: str, day: date) -> Fraction | None:
        bar = self._bar(ticker, day)
        return exact(bar.close) if bar is not None else None

    def last_close(self, ticker: str, upto: date) -> tuple[Fraction, date] | None:
        """The newest closing price on or before `upto`, and its day; None when the last weeks hold none."""
        key = (ticker, upto)
        if key not in self._last:
            found = None
            for day in reversed([d for d in self._days if d <= upto][-LOOK_BACK_DAYS:]):
                price = self.close(ticker, day)
                if price is not None:
                    found = (price, day)
                    break
            if len(self._last) > 200_000:
                self._last.clear()
            self._last[key] = found
        return self._last[key]

    def splits_as_of(self) -> date:
        """The day the newest complete list of share splits was fetched. A day later than this cannot be booked:
        a split of that day might not be in the list yet."""
        done = [r for r in self.inputs.runs(massive.SPLITS_SOURCE) if r.get("status") == "ok"]
        if not done:
            raise InputError("no complete list of share splits is stored")
        return date.fromisoformat(str(done[-1]["ts"])[:10])

    def splits(self) -> list[read.Split]:
        if self._splits is None:
            self._splits = read.load_splits(self.inputs)
        return self._splits

"""The Dice fund: 1,000 funds that each hold 20 random covered companies in equal parts, re-drawn on the first
session of each month (docs/SPEC.md section 4; docs/decisions/0005, point 1). It shows the size of luck.

**The draw can be repeated by anyone, in any language.** It uses no random function of a library. For fund
number n (1 to 1,000) every covered company gets the SHA-256 of the text

    <starting number> line-feed <month as YYYY-MM> line-feed <n> line-feed <SEC company number>

and the fund holds the 20 companies with the lowest fingerprints (a tie goes to the lower company number). With
fewer than 20 covered companies a fund holds them all at 5% each and keeps the rest in cash (provisional until
record 0010 fixes the exact rules). The starting number is logged before the first covered list exists.

The public log holds the starting number and each month's draw (the month, the covered list, the rule version),
not a line for each of the funds' trades. Their orders and fills are facts in private files whose fingerprints
are logged, so a later change of this code cannot change their past. Their daily values are never published:
with a thousand funds of twenty known companies each, every share's price move could be worked back out of them.

The funds follow the same booking rules as every other fund (`engine.book_day`).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Iterable
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..archive.store import sha256_hex
from ..log import canon
from ..log.seal import Sealed
from ..log.store import Log
from ..universe.output import write_new_bytes
from . import calendar, engine, orders
from .book import Booker, apply_effect, split_effect, takeover_effect
from .engine import Closed, Fill, Fund, Order
from .events import SHARE_TAKEOVER

RULE_VERSION = "dice-2026-11-18-provisional"  # until record 0010 fixes the exact rules
FUNDS = 1000
PER_FUND = 20
NAME = "dice"


class DiceError(Exception):
    pass


def new_seed() -> str:
    """A starting number nobody chose: 64 hex characters from the machine's random source."""
    return secrets.token_hex(32)


def draw(seed: str, month: str, covered: Iterable[int], fund: int, per_fund: int = PER_FUND) -> list[int]:
    """The companies fund number `fund` holds in `month`."""

    def rank(cik: int) -> tuple[str, int]:
        return sha256_hex(f"{seed}\n{month}\n{fund}\n{cik}".encode("ascii")), cik

    return sorted(sorted(set(covered), key=rank)[:per_fund])


def place_among(value: int, dice_values: list[int]) -> int:
    """Where a fund falls among the Dice funds: the number of them it is ahead of or level with (0 to 1,000)."""
    return sum(1 for v in dice_values if value >= v)


def _write_fact(path: Path, data: bytes) -> str:
    """Write a private file of facts, never over an existing one. A file of the same name that an earlier run
    left without logging it (a crash in between) is set aside. Returns the fingerprint."""
    if path.exists():
        path.rename(path.with_name(f"{path.stem}.orphan-{secrets.token_hex(4)}{path.suffix}"))
    write_new_bytes(path, data)
    return sha256_hex(data)


def _read_fact(folder: Path, ref: dict[str, Any]) -> dict[str, Any]:
    path = folder / ref["file"]
    try:
        data = path.read_bytes()
    except OSError:
        raise DiceError(f"the Dice file {ref['file']} is missing") from None
    if sha256_hex(data) != ref["sha256"]:
        raise DiceError(f"the Dice file {ref['file']} does not match its fingerprint in the log")
    return canon.decode(data.removesuffix(b"\n"))


class DiceBooks:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.started: date | None = None
        self.seed: str | None = None
        self.seed_ref: int | None = None
        self.funds: list[Fund] = []
        self.months: list[str] = []
        self.values: dict[date, list[int]] = {}
        self._next_ref = 1

    @classmethod
    def load(cls, log: Log, folder: Path) -> DiceBooks:
        """The state of the thousand funds as it follows from the log and the private files it names."""
        books = cls(folder)
        for entry in log.entries():
            rec = entry.record
            if entry.kind == "funds_start" and NAME in rec["funds"]:
                books.started = date.fromisoformat(rec["day"])
                books.funds = [Fund(NAME, rec["cash_cents"], peak=rec["cash_cents"]) for _ in range(FUNDS)]
            elif entry.kind == "dice_seed":
                books.seed, books.seed_ref = rec["seed"], entry.seq
            elif entry.kind == "dice_draw":
                books.months.append(rec["month"])
                if "orders" in rec:
                    books._take_orders(_read_fact(folder, log.opened(entry)["orders"]))
            elif entry.kind == "day_booked":
                values = log.opened(entry)["values"]
                if "dice" in values:
                    books._take_day(_read_fact(folder, values["dice"]))
        return books

    def _take_orders(self, fact: dict[str, Any]) -> None:
        decided = date.fromisoformat(fact["session_day"])
        for number, ref in fact["replaced"]:
            self.funds[number - 1].orders.pop(ref, None)
        for number, ref, cik, ticker, name, side, size in fact["orders"]:
            self.funds[number - 1].orders[ref] = Order(
                ref, NAME, cik, ticker, name, side, canon.pct_fraction(size) if size else None, decided
            )
            self._next_ref = max(self._next_ref, ref + 1)

    def _take_day(self, fact: dict[str, Any]) -> None:
        for number, effect in fact["events"]:
            apply_effect(self.funds[number - 1], effect)
        for number, ref, side, cik, ticker, name, shares, _price, amount, cost in fact["fills"]:
            fund = self.funds[number - 1]
            fund.orders.pop(ref, None)
            engine.apply_fill(fund, side, cik, ticker, name, shares, amount, cost)
        for number, ref, _outcome in fact["closed"]:
            self.funds[number - 1].orders.pop(ref, None)
        day = date.fromisoformat(fact["day"])
        self.values[day] = [value for value, _cash in fact["values"]]
        for fund, (value, _cash) in zip(self.funds, fact["values"], strict=True):
            fund.peak = max(fund.peak or 0, value)

    def plan_draw(
        self,
        month: str,
        session_day: date,
        covered: set[int],
        info: dict[int, tuple[str, str]],
        price_of: Callable[[str], Fraction | None],
    ) -> dict[str, Any]:
        """Make the month's draw for all funds and write their orders to a private file. Returns the fields of
        the `dice_draw` record. The same limits are checked as for every other fund."""
        if self.seed is None or self.seed_ref is None or not self.funds:
            raise DiceError("the Dice funds have no starting number yet: start the funds first")
        if month in self.months:
            raise DiceError(f"the draw of {month} was made already")
        listed: list[list[Any]] = []
        replaced: list[list[int]] = []
        for number, fund in enumerate(self.funds, start=1):
            for ref in sorted(fund.orders):  # a new draw replaces what was still waiting
                replaced.append([number, ref])
            fund.orders.clear()
            value, _ = engine.fund_value(fund, price_of)
            wanted = orders.rebalance(fund, draw(self.seed, month, covered, number), info, value, price_of)
            verdicts = orders.check(fund, value, price_of, wanted, buyable=covered, covered=covered, risky=set())
            for verdict in verdicts:
                p = verdict.proposal
                if verdict.outcome == "refused":
                    continue
                size = canon.format_pct(verdict.allowed) if verdict.allowed is not None else None
                side = "buy" if p.action in ("buy", "add") else "sell"
                listed.append([number, self._next_ref, p.cik, p.ticker, p.name, side, size])
                fund.orders[self._next_ref] = Order(
                    self._next_ref, NAME, p.cik, p.ticker, p.name, side, verdict.allowed, session_day
                )
                self._next_ref += 1
        fact = {
            "month": month,
            "session_day": session_day.isoformat(),
            "rule_version": RULE_VERSION,
            "replaced": replaced,
            "orders": listed,
        }
        name = f"orders-{session_day.isoformat()}.json"
        sha = _write_fact(self.folder / name, canon.encode(fact) + b"\n")
        self.months.append(month)
        return {
            "month": month,
            "covered": sorted(covered),
            "rule_version": RULE_VERSION,
            "seed_ref": self.seed_ref,
            "orders": Sealed({"file": name, "sha256": sha, "orders": len(listed)}),
        }

    def book_day(self, day: date, booker: Booker) -> dict[str, Any] | None:
        """Book one trading day for all funds (called by the daily booking step). Returns what the day's log
        record stores about it: the private file with the facts, and its fingerprint."""
        if self.started is None or self.started > day or not self.funds:
            return None
        prices = booker.prices
        before = booker.price_before(day)
        splits = booker.splits_due(day)
        # A takeover applies to every fund that still holds the company: once booked, the position is gone.
        table = [e for e in booker.events if e.effective <= day]
        events: list[list[Any]] = []
        fills: list[list[Any]] = []
        closed: list[list[Any]] = []
        values: list[list[int]] = []

        def opening(ticker: str) -> Fraction | None:
            return prices.opening(ticker, day)

        def at_close(ticker: str) -> Fraction | None:
            found = prices.last_close(ticker, day)
            return found[0] if found else None

        for number, fund in enumerate(self.funds, start=1):
            booker.books.set_due(list(fund.orders.values()))
            for ticker, ratio in splits:
                effect = split_effect(fund, ticker, ratio, opening(ticker))
                if effect:
                    events.append([number, effect])
                    apply_effect(fund, effect)
            for event in table:
                buyer_open = opening(event.buyer_ticker) if event.kind == SHARE_TAKEOVER else None
                rate = booker.rate_of(event.buyer_cik) if event.buyer_cik else engine.COST_BELOW_1BN
                waited = max(0, len(calendar.trading_days(event.effective, day)) - 1)
                effect = takeover_effect(fund, event, buyer_open, event.buyer_cik in booker.covered, rate, waited)
                if effect:
                    events.append([number, effect])
                    apply_effect(fund, effect)
                    for order in [o for o in fund.orders.values() if o.cik == event.cik]:
                        closed.append([number, order.ref, "company left"])
                        del fund.orders[order.ref]
            value_before, _ = engine.fund_value(fund, before)
            for booking in engine.book_day(
                fund, day, value_before, opening, booker.rate_of, lambda order: booker.waited(order, day)
            ):
                order = booking.order
                if isinstance(booking, Fill):
                    fills.append(
                        [
                            number,
                            order.ref,
                            order.side,
                            order.cik,
                            order.ticker,
                            order.name,
                            booking.shares,
                            canon.format_decimal(booking.price),
                            booking.amount,
                            booking.cost,
                        ]
                    )
                else:
                    assert isinstance(booking, Closed)
                    closed.append([number, order.ref, booking.outcome])
                engine.apply(fund, booking)
            value, _ = engine.fund_value(fund, at_close)
            fund.peak = max(fund.peak or 0, value)
            values.append([value, fund.cash])
        fact = {
            "day": day.isoformat(),
            "rule_version": engine.RULE_VERSION,
            "price_file_sha256": prices.sha256(day),
            "events": events,
            "fills": fills,
            "closed": closed,
            "values": values,
        }
        name = f"booked-{day.isoformat()}.json"
        sha = _write_fact(self.folder / name, canon.encode(fact) + b"\n")
        self.values[day] = [value for value, _ in values]
        return {"file": name, "sha256": sha, "fills": len(fills), "closed": len(closed)}

"""The books of the funds, recomputed from the decision log (docs/decisions/0005, point 1: option A).

The log, with its private files, is the only truth. `replay` adds its facts up: a fill is a fact (shares, price,
amount, cost) and is never worked out again, so a later change of this code cannot change the past. `book` is
the daily step that writes new facts: for every trading day since the last one that was booked it books company
events, then the due orders of each fund, then the values at the close.

Dice funds are not in here (a thousand funds do not get a log line per trade); see `dice.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from fractions import Fraction
from typing import Any

from ..log import canon
from ..log.records import FUNDS, INDEX_FUNDS
from ..log.seal import Sealed
from ..log.store import Entry, Log, Writer
from . import calendar, engine
from .engine import Booking, Closed, Fill, Fund, Order, Position
from .events import CASH_TAKEOVER, SHARE_TAKEOVER, Event
from .prices import PriceBook, exact
from .universe import Universe

LOGGED_FUNDS = tuple(f for f in FUNDS if f != "dice")


class BookError(Exception):
    pass


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@dataclass
class Books:
    funds: dict[str, Fund] = field(default_factory=dict)
    started: dict[str, date] = field(default_factory=dict)
    booked: list[date] = field(default_factory=list)
    starts: dict[date, datetime] = field(default_factory=dict)  # session day -> its start time
    received: dict[date, datetime] = field(default_factory=dict)  # session day -> when its publication was received
    index_units: dict[str, Fraction] = field(default_factory=dict)
    events_done: set[str] = field(default_factory=set)
    values: dict[date, dict[str, Any]] = field(default_factory=dict)  # the stored values of each booked day
    draw_days: list[date] = field(default_factory=list)  # session days with a monthly draw (Dice or Rules)
    rules_months: list[str] = field(default_factory=list)
    index_bought: date | None = None  # the day the index funds were bought

    def undated(self) -> date | None:
        """The earliest session day whose orders have no fill day yet, because the time its publication was
        received is not in the log. No day from then on may be booked: a fill would move to a later day."""
        days = [o.decided for f in self.funds.values() for o in f.orders.values() if o.due is None]
        days += [d for d in self.draw_days if d not in self.received]
        return min(days) if days else None

    def set_due(self, orders: list[Order] | None = None) -> None:
        """The fill day of every open order whose session has a known time of publication (record 0003)."""
        todo = orders if orders is not None else [o for f in self.funds.values() for o in f.orders.values()]
        for order in todo:
            if order.due is None and order.decided in self.received and order.decided in self.starts:
                order.due = calendar.fill_day(self.received[order.decided], self.starts[order.decided])


# What the daily booking writes. After a crash in the middle of a day these records exist without the day's own
# record; the next run works that day out again from the state before it (see `Booker`).
BOOKED_OUTCOMES = ("lapsed", "too small", "nothing to sell", "company left", engine.BRAKED)


def unfinished_day(entries: list[Entry]) -> list[Entry]:
    """The booking records written after the last complete day: what a run left that stopped half-way."""
    last = max((i for i, e in enumerate(entries) if e.kind == "day_booked"), default=-1)
    return [
        e
        for e in entries[last + 1 :]
        if e.kind == "fill"
        or (e.kind == "company_event" and "booked" in e.record)
        or (e.kind == "order_closed" and e.record["outcome"] in BOOKED_OUTCOMES)
    ]


class Replayer:
    """Adds the facts of the log up, one record at a time."""

    def __init__(self, log: Log) -> None:
        self.log = log
        self.books = Books()

    def feed(self, entry: Entry) -> None:
        books, rec, kind = self.books, entry.record, entry.kind
        if kind == "funds_start":
            for name in rec["funds"]:
                if name in books.started:
                    raise BookError(f"fund {name} was started twice (record {entry.seq})")
                books.started[name] = date.fromisoformat(rec["day"])
                if name != "dice":
                    books.funds[name] = Fund(name, rec["cash_cents"], peak=rec["cash_cents"])
        elif kind == "session_start":
            day = date.fromisoformat(rec["session_day"])
            books.starts[day] = _time(rec["start_time"])
            previous = rec.get("previous_publication")
            if previous:
                books.received[date.fromisoformat(previous["session_day"])] = _time(previous["received"])
        elif kind == "decision":
            if rec["action"] == "nothing" or rec["fund"] not in books.funds:
                return
            company = rec["company"]
            side = "buy" if rec["action"] in ("buy", "add") else "sell"
            size = canon.pct_fraction(rec["size_pct"]) if rec.get("size_pct") else None
            books.funds[rec["fund"]].orders[entry.seq] = Order(
                entry.seq,
                rec["fund"],
                company["cik"],
                company.get("ticker", ""),
                company["name"],
                side,
                size,
                entry.day,
            )
        elif kind == "order_refused":
            self._fund(rec).orders.pop(rec["ref"], None)
        elif kind == "order_reduced":
            order = self._fund(rec).orders.get(rec["ref"])
            if order is not None:
                allowed = rec["allowed_pct"]
                if not isinstance(allowed, str):  # sealed: it follows from what the position was worth
                    allowed = self.log.opened(entry)["allowed_pct"]
                order.size = canon.pct_fraction(allowed)
        elif kind in ("dice_draw", "rules_draw"):
            books.draw_days.append(entry.day)
            if kind == "rules_draw":
                books.rules_months.append(rec["month"])
        elif kind == "order_closed":
            self._fund(rec).orders.pop(rec["ref"], None)
        elif kind == "fill":
            details = self.log.opened(entry)["details"]
            fund = self._fund(rec)
            fund.orders.pop(rec["ref"], None)
            company = rec["company"]
            engine.apply_fill(
                fund,
                rec["side"],
                company["cik"],
                company.get("ticker", ""),
                company["name"],
                details["shares"],
                details["amount_cents"],
                details["cost_cents"],
            )
        elif kind == "company_event" and "booked" in rec:
            booked = self.log.opened(entry)["booked"]
            for effect in booked["effects"]:
                if effect["fund"] in books.funds:
                    apply_effect(books.funds[effect["fund"]], effect)
            books.events_done.add(booked["key"])
        elif kind == "day_booked":
            values = self.log.opened(entry)["values"]
            day = date.fromisoformat(rec["day"])
            books.booked.append(day)
            books.values[day] = values
            for name, stored in values["funds"].items():
                if name in books.funds:
                    fund = books.funds[name]
                    fund.peak = max(fund.peak or 0, stored["value_cents"])
            for symbol, stored in values.get("index", {}).items():
                books.index_units[symbol] = Fraction(stored["units_num"], stored["units_den"])
            if values.get("index") and books.index_bought is None:
                books.index_bought = day

    def _fund(self, rec: dict[str, Any]) -> Fund:
        fund = self.books.funds.get(rec["fund"])
        if fund is None:
            raise BookError(f"a record for fund {rec['fund']}, which was never started")
        return fund


def replay(log: Log, *, skip: set[int] | None = None) -> Books:
    """The state of every fund as it follows from the log. `skip`: record numbers to leave out (the booking
    step uses this to go back to the state before a day that was left half-booked)."""
    replayer = Replayer(log)
    for entry in log.entries():
        if not skip or entry.seq not in skip:
            replayer.feed(entry)
    replayer.books.set_due()
    return replayer.books


def apply_effect(fund: Fund, effect: dict[str, Any]) -> None:
    """Book what a company event did to one fund: the shares it holds afterwards, cash in or out, and a new
    position where the event gives shares of another company."""
    cik = effect["cik"]
    position = fund.positions.get(cik)
    if position is not None:
        if effect["shares"] == 0:
            del fund.positions[cik]
        else:
            position.shares = effect["shares"]
    fund.cash += effect["cash_cents"]
    new = effect.get("new")
    if new:
        held = fund.positions.get(new["cik"])
        if held is None:
            fund.positions[new["cik"]] = Position(new["cik"], new["ticker"], new["name"], new["shares"])
        else:
            held.shares += new["shares"]


def same_ticker(a: str, b: str) -> bool:
    return a.replace("-", ".") == b.replace("-", ".")


def split_effect(fund: Fund, ticker: str, ratio: Fraction, price: Fraction | None) -> dict[str, Any] | None:
    """A share split for one fund: shares times the ratio; a fraction of a share is paid out in cash at the first
    opening price after the split, without cost. `price`: that opening price, or, when the share did not open
    that day, its last closing price before the split brought to the new shares."""
    for position in fund.positions.values():
        if same_ticker(position.ticker, ticker):
            exact_shares = position.shares * ratio
            whole = exact_shares.__floor__()
            part = exact_shares - whole
            cash = engine.to_cents(part * price) if part and price is not None else 0
            return {"fund": fund.name, "cik": position.cik, "shares": whole, "cash_cents": cash}
    return None


def takeover_effect(
    fund: Fund,
    event: Event,
    buyer_open: Fraction | None,
    buyer_covered: bool,
    rate: Fraction,
    waited: int,
) -> dict[str, Any] | None:
    """A takeover for one fund (docs/decisions/0005, point 4). Returns None when the fund does not hold the
    company, and also when the booking has to wait for the buyer's opening price."""
    position = fund.positions.get(event.cik)
    if position is None:
        return None
    if event.kind == CASH_TAKEOVER:
        assert event.cash_per_share is not None
        cash = engine.to_cents(event.cash_per_share * position.shares)  # at the deal price, without trading cost
        return {"fund": fund.name, "cik": event.cik, "shares": 0, "cash_cents": cash}
    assert event.kind == SHARE_TAKEOVER and event.ratio is not None and event.buyer_cik is not None
    exact_shares = position.shares * event.ratio
    whole = exact_shares.__floor__()
    part = exact_shares - whole
    new = {"cik": event.buyer_cik, "ticker": event.buyer_ticker, "name": event.buyer_name, "shares": whole}
    if buyer_open is None:
        if waited < engine.WAIT_DAYS:
            return None  # wait for the first day the buyer's share opens
        # No price for five trading days: the shares are kept as they are, the fraction of a share is dropped.
        return {"fund": fund.name, "cik": event.cik, "shares": 0, "cash_cents": 0, "new": new, "no_price": True}
    cash = engine.to_cents(part * buyer_open)
    if buyer_covered:
        return {"fund": fund.name, "cik": event.cik, "shares": 0, "cash_cents": cash, "new": new if whole else None}
    amount = engine.to_cents(buyer_open * whole)  # a buyer that is not covered: sold at its opening price, with cost
    cost = engine.cost_cents(rate, amount)
    return {"fund": fund.name, "cik": event.cik, "shares": 0, "cash_cents": cash + amount - cost, "sold": whole}


@dataclass
class BookReport:
    days: list[date] = field(default_factory=list)
    fills: int = 0
    closed: int = 0
    events: int = 0
    waiting_for: date | None = None  # a trading day whose price file is not stored yet: booking stops there
    notes: list[str] = field(default_factory=list)


def _company(cik: int, name: str, ticker: str) -> dict[str, Any]:
    return {"cik": cik, "name": name, "ticker": ticker} if ticker else {"cik": cik, "name": name}


def fill_body(fill: Fill, price_file: str, value_before: int) -> dict[str, Any]:
    order = fill.order
    return {
        "ref": order.ref,
        "fund": order.fund,
        "company": _company(order.cik, order.name, order.ticker),
        "side": order.side,
        "fill_day": fill.day.isoformat(),
        "rule_version": engine.RULE_VERSION,
        "cut_for_cash": fill.cut_for_cash,
        "waited_days": fill.waited,
        "details": Sealed(
            {
                "shares": fill.shares,
                "price": canon.format_decimal(fill.price),
                "amount_cents": fill.amount,
                "cost_cents": fill.cost,
                "cost_rate": canon.format_pct(fill.rate),
                "fund_value_before_cents": value_before,
                "price_file_sha256": price_file,
            }
        ),
    }


def closed_body(closed: Closed) -> dict[str, Any]:
    order = closed.order
    return {
        "ref": order.ref,
        "fund": order.fund,
        "company": _company(order.cik, order.name, order.ticker),
        "outcome": closed.outcome,
        "day": closed.day.isoformat(),
    }


class Booker:
    """The daily booking step (docs/SPEC.md section 1, step 2)."""

    def __init__(
        self,
        log: Log,
        writer: Writer,
        prices: PriceBook,
        universe: Universe,
        events: list[Event],
        covered: set[int],
        on_day: Callable[[date, Booker], dict[str, Any] | None] | None = None,
    ) -> None:
        self.log = log
        self.writer = writer
        self.prices = prices
        self.universe = universe
        self.events = events
        self.covered = covered
        self.on_day = on_day  # the Dice funds book their day through this, and hand back what to store with it
        # A run that stopped in the middle of a day left some of that day's records. The day is worked out again
        # from the state before it, so that it comes out exactly as it would have without the stop; what is in
        # the log already is not written again.
        left = unfinished_day(log.entries())
        self.books = replay(log, skip={e.seq for e in left})
        self.logged_fills = {e.record["ref"] for e in left if e.kind == "fill"}
        self.logged_closed = {e.record["ref"] for e in left if e.kind == "order_closed"}
        self.logged_events = {log.opened(e)["booked"]["key"] for e in left if e.kind == "company_event"}
        self.report = BookReport()
        if left:
            self.report.notes.append(
                f"an earlier run stopped half-way through a day; {len(left)} of its records are kept"
            )

    def rate_of(self, cik: int) -> Fraction:
        return engine.cost_rate(self.universe.market_value(cik))

    def run(self, upto: date | None = None) -> BookReport:
        """Book every trading day since the last booked one for which a price file is stored (and, when `upto`
        is given, not later than that day)."""
        books = self.books
        if not books.started:
            self.report.notes.append("no fund has been started yet")
            return self.report
        stored = self.prices.days()
        if not stored:
            self.report.notes.append("no price file is stored before the cut-off")
            return self.report
        first = min(books.started.values())
        day = (books.booked[-1] if books.booked else first - timedelta(days=1)) + timedelta(days=1)
        undated = books.undated()
        while day <= (min(stored[-1], upto) if upto else stored[-1]):
            if undated is not None and day >= undated:
                # The fill day of that session's orders follows from when its publication was received
                # (record 0003); until the log holds that time, no day from then on is booked.
                self.report.notes.append(f"waiting for the time the publication of {undated} was received")
                break
            if self.prices.has(day):
                if self.prices.splits_as_of() < day:
                    self.report.waiting_for = day
                    self.report.notes.append("the saved list of share splits is older than this day")
                    break
                self.book_day(day)
            elif day.weekday() < 5 and day not in self.prices.closed and calendar.is_trading_day(day):
                self.report.waiting_for = day  # the price file must be there first (record 0005, point 2.1)
                break
            day += timedelta(days=1)
        return self.report

    def last_booked(self) -> date | None:
        return self.books.booked[-1] if self.books.booked else None

    def waited(self, order: Order, day: date) -> int:
        assert order.due is not None
        return max(0, len(calendar.trading_days(order.due, day)) - 1)

    def price_before(self, day: date) -> Callable[[str], Fraction | None]:
        earlier = [d for d in self.prices.days() if d < day]

        def price(ticker: str) -> Fraction | None:
            found = self.prices.last_close(ticker, earlier[-1]) if earlier else None
            return found[0] if found else None

        return price

    def book_day(self, day: date) -> None:
        books, prices = self.books, self.prices
        sha = prices.sha256(day)
        before = self.price_before(day)
        active = [books.funds[n] for n in LOGGED_FUNDS if n in books.funds and books.started[n] <= day]

        def opening(ticker: str) -> Fraction | None:
            return prices.opening(ticker, day)

        # First of all: each fund's value at the last closing prices before this day, "with the shares as they
        # were at that close" (record 0005, point 2.2). A split of today must not be in it.
        value_before = {fund.name: engine.fund_value(fund, before)[0] for fund in active}
        self._book_splits(day, active, opening, before, sha)
        self._book_table_events(day, active, opening, sha)
        for fund in active:
            bookings = engine.book_day(
                fund, day, value_before[fund.name], opening, self.rate_of, lambda order: self.waited(order, day)
            )
            for booking in bookings:
                self._write(booking, sha, value_before[fund.name])
                engine.apply(fund, booking)
        values: dict[str, Any] = {"funds": {}, "index": {}, "price_file_sha256": sha}
        for fund in active:
            values["funds"][fund.name] = self.close_value(fund, day)
            fund.peak = max(fund.peak or 0, values["funds"][fund.name]["value_cents"])
        values["index"] = self._index(day)
        if self.on_day is not None:
            extra = self.on_day(day, self)
            if extra:
                values["dice"] = extra
        self.writer.add(
            "day_booked", {"day": day.isoformat(), "rule_version": engine.RULE_VERSION, "values": Sealed(values)}
        )
        books.booked.append(day)
        books.values[day] = values
        self.report.days.append(day)
        self.logged_fills, self.logged_closed, self.logged_events = set(), set(), set()

    def close_value(self, fund: Fund, day: date) -> dict[str, Any]:
        """A fund's value at the close of `day`. A share without a price that day keeps its last one, and is named
        under "stale"; one without any price in the last weeks counts as zero, under "no_price"."""
        stale: list[int] = []

        def price(ticker: str) -> Fraction | None:
            found = self.prices.last_close(ticker, day)
            if found is None:
                return None
            if found[1] != day:
                stale.extend(p.cik for p in fund.positions.values() if p.ticker == ticker)
            return found[0]

        value, missing = engine.fund_value(fund, price)
        return {"value_cents": value, "cash_cents": fund.cash, "stale": sorted(set(stale)), "no_price": missing}

    def _write(self, booking: Booking, price_file: str, value_before: int) -> None:
        """Log one booking, unless a run that stopped half-way logged it already."""
        ref = booking.order.ref
        if isinstance(booking, Fill):
            if ref not in self.logged_fills:
                self.writer.add("fill", fill_body(booking, price_file, value_before))
            self.report.fills += 1
        else:
            if ref not in self.logged_closed:
                self.writer.add("order_closed", closed_body(booking))
            self.report.closed += 1

    def splits_due(self, day: date) -> list[tuple[str, Fraction, date]]:
        """(ticker, new shares per old share, the split's own day) of every split after the last booked day up
        to `day`. Before the first booked day nothing was held, so nothing older than the start counts."""
        last = self.last_booked() or min(self.books.started.values()) - timedelta(days=1)
        out: list[tuple[str, Fraction, date]] = []
        for split in self.prices.splits():
            if last < split.day <= day:
                old, new = exact(split.split_from), exact(split.split_to)
                if old and new:
                    out.append((split.ticker, new / old, split.day))
        return out

    def _book_splits(
        self,
        day: date,
        active: list[Fund],
        opening: Callable[[str], Fraction | None],
        before: Callable[[str], Fraction | None],
        sha: str,
    ) -> None:
        for ticker, ratio, split_day in self.splits_due(day):
            key = f"split:{ticker}:{split_day.isoformat()}"
            if key in self.books.events_done:
                continue
            if not any(same_ticker(p.ticker, ticker) for f in active for p in f.positions.values()):
                continue  # nobody holds it
            price = opening(ticker)
            if price is None:  # no opening price today: the last close before the split, in new shares
                old_close = before(ticker)
                price = old_close / ratio if old_close is not None else None
            effects = [e for e in (split_effect(f, ticker, ratio, price) for f in active) if e]
            held = next(p for f in active for p in f.positions.values() if p.cik == effects[0]["cik"])
            if key not in self.logged_events:
                self.writer.add(
                    "company_event",
                    {
                        "company": _company(held.cik, held.name, held.ticker),
                        "event": "split",
                        "effective": split_day.isoformat(),
                        # From the price service's list; to be checked against the company's filing by hand.
                        "checked_against_filing": False,
                        "terms": Sealed(
                            {"new_per_old_num": ratio.numerator, "new_per_old_den": ratio.denominator}, "other"
                        ),
                        "booked": Sealed({"key": key, "effects": effects, "price_file_sha256": sha}),
                    },
                )
            for effect in effects:
                apply_effect(self.books.funds[effect["fund"]], effect)
            self.books.events_done.add(key)
            self.report.events += 1

    def _book_table_events(
        self, day: date, active: list[Fund], opening: Callable[[str], Fraction | None], sha: str
    ) -> None:
        for event in self.events:
            if event.effective > day or event.key in self.books.events_done:
                continue
            buyer_open = opening(event.buyer_ticker) if event.kind == SHARE_TAKEOVER else None
            waited = max(0, len(calendar.trading_days(event.effective, day)) - 1)
            rate = self.rate_of(event.buyer_cik) if event.buyer_cik else engine.COST_BELOW_1BN
            covered = event.buyer_cik in self.covered
            effects = [e for e in (takeover_effect(f, event, buyer_open, covered, rate, waited) for f in active) if e]
            if not effects:
                continue
            held = next(p for f in active for p in f.positions.values() if p.cik == event.cik)
            terms: dict[str, Any] = {"table_line": event.key}
            if event.cash_per_share is not None:
                terms["cash_per_share"] = canon.format_decimal(event.cash_per_share)
            if event.ratio is not None:
                terms |= {"ratio": canon.format_decimal(event.ratio), "buyer_cik": event.buyer_cik}
            if event.key not in self.logged_events:
                self.writer.add(
                    "company_event",
                    {
                        "company": _company(held.cik, held.name, held.ticker),
                        "event": event.kind,
                        "effective": event.effective.isoformat(),
                        "checked_against_filing": True,  # entered by hand from the filing
                        "filing": event.filing,
                        "terms": Sealed(terms, "other"),
                        "booked": Sealed({"key": event.key, "effects": effects, "price_file_sha256": sha}),
                    },
                )
            for effect in effects:
                fund = self.books.funds[effect["fund"]]
                apply_effect(fund, effect)
                for order in [o for o in fund.orders.values() if o.cik == event.cik]:
                    gone = Closed(order, day, "company left")  # the company is gone: its open orders end here
                    self._write(gone, sha, 0)
                    engine.apply(fund, gone)
            self.books.events_done.add(event.key)
            self.report.events += 1

    def _index(self, day: date) -> dict[str, Any]:
        """XBI, IBB and URTH, bought on day one and held (docs/SPEC.md section 4). Kept privately only."""
        out: dict[str, Any] = {}
        for symbol in INDEX_FUNDS:
            units = self.books.index_units.get(symbol)
            if units is None:
                price = self.prices.opening(symbol, day)
                if price is None:
                    continue  # bought at the first opening price there is
                units = Fraction(engine.START_CASH_CENTS, 100) / price  # bought today: today's split is in the price
            else:
                for ticker, ratio, _ in self.splits_due(day):
                    if ticker == symbol:
                        units *= ratio
            self.books.index_units[symbol] = units
            found = self.prices.last_close(symbol, day)
            out[symbol] = {
                "units_num": units.numerator,
                "units_den": units.denominator,
                "value_cents": engine.to_cents(units * found[0]) if found else 0,
            }
        return out


def check(log: Log, prices: PriceBook) -> list[str]:
    """Recompute every stored day value from the facts in the log and the saved prices. Returns what differs;
    an empty list means the books add up to the cent (docs/decisions/0005, point 1)."""
    replayer = Replayer(log)
    differences: list[str] = []
    for entry in log.entries():
        replayer.feed(entry)
        if entry.kind != "day_booked":
            continue
        day = date.fromisoformat(entry.record["day"])
        stored = replayer.books.values[day]
        if not prices.has(day):
            differences.append(f"{day}: its price file is not stored (any more)")
            continue
        if prices.sha256(day) != stored.get("price_file_sha256"):
            differences.append(f"{day}: the price file is not the one the day was booked with")
        for name, was in stored["funds"].items():
            fund = replayer.books.funds[name]

            def price(ticker: str, day: date = day) -> Fraction | None:
                found = prices.last_close(ticker, day)
                return found[0] if found else None

            value, _ = engine.fund_value(fund, price)
            if value != was["value_cents"] or fund.cash != was["cash_cents"]:
                differences.append(f"{day}, fund {name}: the recomputed value or cash differs from what was stored")
    return differences

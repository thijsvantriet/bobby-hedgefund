"""Booking the orders of one fund on one trading day: the rules of docs/decisions/0005, point 2, as arithmetic.

Nothing here reads a file or writes one. The same function books an AI fund, the Rules fund and each of the 1,000
Dice funds, so they all follow the same rules: whole shares, the same costs, the same wait for a missing price.

Money is whole cents. Prices and sizes are exact fractions, never numbers with a floating decimal point. Amounts
are rounded to the nearest cent (a half goes up); a trading cost is rounded up.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction

RULE_VERSION = "2026-11-18"  # written into every fill; a change of any rule in this file gets a new version
MIN_TRADE = Fraction(1, 200)  # a trade below 0.5% of the fund is not made
BRAKE = Fraction(7, 10)  # at 30% or more below its own highest value a fund buys nothing
WAIT_DAYS = 5  # an order without an opening price waits this many trading days, then lapses
START_CASH_CENTS = 100_000_000  # $1,000,000
BRAKED = "cancelled by a limit on the fund's value"  # the brake; not named in public (records.VALUE_CANCELLED)
# Trading cost on the amount traded, by the company's market value (starting figures; record 0005, point 3).
COST_ABOVE_2BN = Fraction(25, 10000)
COST_1_TO_2BN = Fraction(50, 10000)
COST_BELOW_1BN = Fraction(100, 10000)


@dataclass
class Position:
    cik: int
    ticker: str  # as the price files spell it
    name: str
    shares: int


@dataclass
class Order:
    ref: int  # the number of the decision record
    fund: str
    cik: int
    ticker: str
    name: str
    side: str  # "buy" or "sell"
    size: Fraction | None  # the size of the trade as a share of the fund; None: sell the whole position
    decided: date  # the session day of the decision
    due: date | None = None  # the fill day, once the time of publication is known


@dataclass
class Fund:
    name: str
    cash: int
    positions: dict[int, Position] = field(default_factory=dict)
    orders: dict[int, Order] = field(default_factory=dict)
    peak: int | None = None  # the highest value so far, in cents


@dataclass(frozen=True)
class Fill:
    order: Order
    day: date
    shares: int
    price: Fraction
    amount: int
    cost: int
    rate: Fraction
    cut_for_cash: bool
    waited: int


@dataclass(frozen=True)
class Closed:
    order: Order
    day: date
    outcome: str  # one of records.CLOSED


Booking = Fill | Closed


def cost_rate(market_value_dollars: int | None) -> Fraction:
    """The trading cost for a company of this size. Unknown size counts as small: the cautious side."""
    if market_value_dollars is None or market_value_dollars < 1_000_000_000:
        return COST_BELOW_1BN
    if market_value_dollars <= 2_000_000_000:
        return COST_1_TO_2BN
    return COST_ABOVE_2BN


def to_cents(dollars: Fraction) -> int:
    """Nearest cent; exactly half a cent goes up."""
    return (dollars * 100 + Fraction(1, 2)).__floor__()


def cost_cents(rate: Fraction, amount: int) -> int:
    """The trading cost of a trade, rounded up to a whole cent."""
    return -((-rate * amount).__floor__())


def shares_for(size: Fraction, value: int, price: Fraction) -> int:
    """`size` of a fund worth `value` cents, in whole shares at `price` dollars, rounded down."""
    if price <= 0:
        return 0
    return (size * value / (price * 100)).__floor__()


def fund_value(fund: Fund, price_of: Callable[[str], Fraction | None]) -> tuple[int, list[int]]:
    """Cash plus every position at the price `price_of` gives (dollars). Returns the value in cents and the
    companies for which no price at all was found; those count as zero."""
    total = fund.cash
    missing: list[int] = []
    for cik in sorted(fund.positions):
        position = fund.positions[cik]
        price = price_of(position.ticker)
        if price is None:
            missing.append(cik)
        else:
            total += to_cents(price * position.shares)
    return total, missing


def book_day(
    fund: Fund,
    day: date,
    value_before: int,
    opening_price: Callable[[str], Fraction | None],
    rate_of: Callable[[int], Fraction],
    waited: Callable[[Order], int],
) -> list[Booking]:
    """What happens to the fund's due orders on `day`. Does not change the fund: `apply` does.

    `value_before`: the fund's value in cents at the last closing prices before `day`.
    `opening_price`: ticker -> the opening price on `day`, or None when the share did not open.
    `waited`: order -> the number of trading days from its fill day to `day` (0 on the fill day itself).
    """
    due = sorted((o for o in fund.orders.values() if o.due is not None and o.due <= day), key=lambda o: o.ref)
    out: list[Booking] = []
    floor = MIN_TRADE * value_before
    braked = fund.peak is not None and value_before <= BRAKE * fund.peak
    cash = fund.cash

    def no_price(order: Order) -> None:
        if waited(order) >= WAIT_DAYS:
            out.append(Closed(order, day, "lapsed"))

    for order in (o for o in due if o.side == "sell"):  # sells are booked before buys
        position = fund.positions.get(order.cik)
        if position is None or position.shares <= 0:
            out.append(Closed(order, day, "nothing to sell"))
            continue
        price = opening_price(position.ticker)
        if price is None:
            no_price(order)
            continue
        shares = (
            position.shares if order.size is None else min(position.shares, shares_for(order.size, value_before, price))
        )
        whole = shares == position.shares
        amount = to_cents(price * shares)
        if shares == 0 or (not whole and amount < floor):  # the sale of a whole position is always made
            out.append(Closed(order, day, "too small"))
            continue
        rate = rate_of(order.cik)
        cost = cost_cents(rate, amount)
        cash += amount - cost
        out.append(Fill(order, day, shares, price, amount, cost, rate, False, waited(order)))

    wanted: list[tuple[Order, Fraction, int, Fraction]] = []
    for order in (o for o in due if o.side == "buy"):
        if braked:
            out.append(Closed(order, day, BRAKED))
            continue
        price = opening_price(order.ticker)
        if price is None:
            no_price(order)
            continue
        assert order.size is not None
        wanted.append((order, price, shares_for(order.size, value_before, price), rate_of(order.cik)))

    def need(items: list[tuple[Order, Fraction, int, Fraction]]) -> int:
        return sum(to_cents(p * n) + cost_cents(r, to_cents(p * n)) for _, p, n, r in items)

    cut = False
    total = need(wanted)
    if total > max(cash, 0):
        cut = True
        part = Fraction(max(cash, 0), total)  # every buy of the day is cut by the same proportion
        wanted = [(o, p, (n * part).__floor__(), r) for o, p, n, r in wanted]
        while need(wanted) > max(cash, 0):  # rounding of costs can leave a few cents short: take one share off
            i = max(range(len(wanted)), key=lambda k: (to_cents(wanted[k][1] * wanted[k][2]), -wanted[k][0].ref))
            o, p, n, r = wanted[i]
            wanted[i] = (o, p, n - 1, r)
    for order, price, shares, rate in wanted:
        amount = to_cents(price * shares)
        if shares <= 0 or amount < floor:
            out.append(Closed(order, day, "too small"))
            continue
        out.append(Fill(order, day, shares, price, amount, cost_cents(rate, amount), rate, cut, waited(order)))
    return sorted(out, key=lambda b: (0 if isinstance(b, Fill) and b.order.side == "sell" else 1, b.order.ref))


def apply(fund: Fund, booking: Booking) -> None:
    """Book one fact in the fund."""
    order = booking.order
    fund.orders.pop(order.ref, None)
    if isinstance(booking, Closed):
        return
    apply_fill(fund, order.side, order.cik, order.ticker, order.name, booking.shares, booking.amount, booking.cost)


def apply_fill(fund: Fund, side: str, cik: int, ticker: str, name: str, shares: int, amount: int, cost: int) -> None:
    if side == "buy":
        position = fund.positions.get(cik)
        if position is None:
            fund.positions[cik] = Position(cik, ticker, name, shares)
        else:
            position.shares += shares
        fund.cash -= amount + cost
    else:
        position = fund.positions[cik]
        position.shares -= shares
        if position.shares == 0:
            del fund.positions[cik]
        fund.cash += amount - cost
    if fund.cash < 0:
        raise ValueError(f"the cash of fund {fund.name} would go below zero: the books do not add up")

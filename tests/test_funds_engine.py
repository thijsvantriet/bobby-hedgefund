from __future__ import annotations

from datetime import UTC, date, datetime
from fractions import Fraction as F
from zoneinfo import ZoneInfo

import pytest

from bobby_hedgefund.funds import calendar, engine
from bobby_hedgefund.funds.engine import Closed, Fill, Fund, Order, Position
from bobby_hedgefund.prices import holidays

DAY = date(2027, 2, 2)
AMS = ZoneInfo("Europe/Amsterdam")
M = 100_000_000  # one million dollars in cents


def fund(cash: int = M, **positions: int) -> Fund:
    f = Fund("careful", cash, peak=M)
    for i, (ticker, shares) in enumerate(positions.items(), start=1):
        f.positions[i] = Position(i, ticker, ticker, shares)
    return f


def add(f: Fund, ref: int, cik: int, ticker: str, side: str, size: str | None, due: date = DAY) -> Order:
    order = Order(ref, f.name, cik, ticker, ticker, side, F(size) if size else None, DAY, due)
    f.orders[ref] = order
    return order


def book(f: Fund, prices: dict[str, str | None], value: int = M, waited: int = 0, rate: F = engine.COST_1_TO_2BN):
    return engine.book_day(
        f, DAY, value, lambda t: F(prices[t]) if prices.get(t) else None, lambda cik: rate, lambda o: waited
    )


# ---------------------------------------------------------------- the arithmetic of record 0005, point 2


def test_whole_shares_rounded_down_amount_to_the_cent_cost_rounded_up() -> None:
    f = fund()
    add(f, 1, 1, "AAA", "buy", "3/100")
    (fill,) = book(f, {"AAA": "12.34"})
    assert isinstance(fill, Fill)
    assert fill.shares == 2431  # 3% of $1,000,000 is $30,000; 30,000 / 12.34 = 2431.1
    assert fill.amount == 2_999_854  # 2431 x 12.34 = 29,998.54
    assert fill.cost == 15_000  # 0.5% of 29,998.54 = 149.9927, rounded up to 150.00
    engine.apply(f, fill)
    assert f.cash == M - 2_999_854 - 15_000 and f.positions[1].shares == 2431 and not f.orders


def test_rounding_to_the_cent_a_half_goes_up_and_a_cost_always_goes_up() -> None:
    assert engine.to_cents(F("0.005")) == 1 and engine.to_cents(F("0.0049")) == 0 and engine.to_cents(F("1.015")) == 102
    assert engine.cost_cents(F(1, 100), 1) == 1 and engine.cost_cents(F(1, 100), 100) == 1
    assert engine.cost_cents(F(25, 10000), 10_001) == 26 and engine.cost_cents(F(1, 100), 0) == 0


def test_the_trading_cost_goes_by_the_size_of_the_company() -> None:
    assert engine.cost_rate(3_000_000_000) == F(25, 10000)
    assert engine.cost_rate(2_000_000_000) == engine.cost_rate(1_000_000_000) == F(50, 10000)
    assert engine.cost_rate(999_999_999) == F(1, 100)
    assert engine.cost_rate(None) == F(1, 100)  # unknown size counts as small: the cautious side


def test_sells_are_booked_before_buys_and_pay_for_them() -> None:
    f = fund(cash=0, AAA=1000)
    f.peak = 10_000_000
    add(f, 1, 2, "BBB", "buy", "5/100")
    add(f, 2, 1, "AAA", "sell", None)
    value = 10_000_000  # 1000 shares at $100
    sell, buy = book(f, {"AAA": "100", "BBB": "50"}, value=value)
    assert (sell.order.side, buy.order.side) == ("sell", "buy") and isinstance(buy, Fill) and not buy.cut_for_cash
    assert sell.amount == 10_000_000 and sell.cost == 50_000 and buy.shares == 100  # 5% of 100,000 at $50
    for b in (sell, buy):
        engine.apply(f, b)
    assert f.cash == 10_000_000 - 50_000 - 500_000 - 2_500 and 1 not in f.positions


def test_when_cash_is_short_every_buy_is_cut_by_the_same_proportion() -> None:
    f = fund(cash=3_000_000)  # $30,000 in cash in a fund that is worth $1,000,000
    f.positions[9] = Position(9, "ZZZ", "ZZZ", 1)
    add(f, 1, 1, "AAA", "buy", "4/100")
    add(f, 2, 2, "BBB", "buy", "2/100")
    a, b = book(f, {"AAA": "10", "BBB": "10"})
    assert isinstance(a, Fill) and isinstance(b, Fill) and a.cut_for_cash and b.cut_for_cash
    # Asked: 4000 and 2000 shares, 60,300 with costs. There is 30,000: both are cut to about half.
    assert (a.shares, b.shares) == (1990, 995)
    assert a.amount + a.cost + b.amount + b.cost <= 3_000_000
    for x in (a, b):
        engine.apply(f, x)
    assert 0 <= f.cash < 20_000  # what rounding down leaves: less than two more shares with their cost


def test_cash_can_never_go_below_zero_whatever_the_rounding() -> None:
    for cash in range(100_000, 100_400, 7):
        f = fund(cash=cash)
        add(f, 1, 1, "AAA", "buy", "5/100")
        add(f, 2, 2, "BBB", "buy", "5/100")
        add(f, 3, 3, "CCC", "buy", "5/100")
        for b in book(f, {"AAA": "3.33", "BBB": "7.77", "CCC": "0.19"}, rate=F(1, 100)):
            engine.apply(f, b)
        assert f.cash >= 0


def test_a_trade_below_half_a_percent_is_not_made_but_a_whole_position_is_always_sold() -> None:
    f = fund(AAA=10, BBB=10_000)
    add(f, 1, 9, "CCC", "buy", "4/1000")  # 0.4% of the fund
    add(f, 2, 1, "AAA", "sell", None)  # 10 shares at $1: far below 0.5%, but the whole position
    add(f, 3, 2, "BBB", "sell", "1/1000")  # a part of a position below 0.5%
    results = {b.order.ref: b for b in book(f, {"AAA": "1", "BBB": "5", "CCC": "10"})}
    assert isinstance(results[2], Fill) and results[2].shares == 10
    assert isinstance(results[1], Closed) and results[1].outcome == "too small"
    assert isinstance(results[3], Closed) and results[3].outcome == "too small"


def test_a_sale_is_never_larger_than_the_shares_held() -> None:
    f = fund(AAA=100)
    add(f, 1, 1, "AAA", "sell", "5/100")  # 5% of the fund would be 5000 shares at $10
    (fill,) = book(f, {"AAA": "10"})
    assert isinstance(fill, Fill) and fill.shares == 100
    f2 = fund()
    add(f2, 1, 1, "AAA", "sell", None)
    (closed,) = book(f2, {"AAA": "10"})
    assert isinstance(closed, Closed) and closed.outcome == "nothing to sell"


def test_without_an_opening_price_an_order_waits_five_trading_days_and_then_lapses() -> None:
    f = fund()
    add(f, 1, 1, "AAA", "buy", "3/100")
    assert book(f, {"AAA": None}, waited=0) == [] and book(f, {"AAA": None}, waited=4) == []
    (closed,) = book(f, {"AAA": None}, waited=5)
    assert isinstance(closed, Closed) and closed.outcome == "lapsed"
    (fill,) = book(f, {"AAA": "10"}, waited=5)  # on the fifth day after its own it can still be filled
    assert isinstance(fill, Fill) and fill.waited == 5


def test_an_order_is_not_touched_before_its_fill_day_or_without_one() -> None:
    f = fund()
    add(f, 1, 1, "AAA", "buy", "3/100", due=date(2027, 2, 3))
    f.orders[2] = Order(2, "careful", 2, "BBB", "BBB", "buy", F(3, 100), DAY, None)
    assert book(f, {"AAA": "10", "BBB": "10"}) == []


def test_the_brake_cancels_buys_at_thirty_percent_below_the_highest_value_and_still_sells() -> None:
    f = fund(AAA=100)
    add(f, 1, 2, "BBB", "buy", "3/100")
    add(f, 2, 1, "AAA", "sell", None)
    results = {b.order.ref: b for b in book(f, {"AAA": "10", "BBB": "10"}, value=70_000_000)}  # exactly 30% down
    assert isinstance(results[1], Closed) and results[1].outcome == engine.BRAKED
    assert isinstance(results[2], Fill)
    f.orders[1] = add(fund(), 1, 2, "BBB", "buy", "3/100")
    (fill,) = [b for b in book(f, {"AAA": "10", "BBB": "10"}, value=70_000_001) if b.order.ref == 1]
    assert isinstance(fill, Fill)  # one cent above the line: no brake


def test_a_fund_is_valued_at_the_prices_given_and_says_what_has_none() -> None:
    f = fund(cash=1_000, AAA=3, BBB=2)
    assert engine.fund_value(f, lambda t: {"AAA": F("1.115")}.get(t)) == (1_000 + 335, [2])


# ---------------------------------------------------------------- trading days and the fill day (record 0003)


def test_the_hand_made_list_of_closed_days_agrees_with_the_rule_and_the_library() -> None:
    for year, days in calendar.CLOSED.items():
        assert set(days) == holidays.regular_holidays(year), year
    xc = pytest.importorskip("exchange_calendars")
    library = {d.date() for d in xc.get_calendar("XNYS", start="2026-01-01", end="2027-12-31").sessions}
    assert library == set(calendar.trading_days(date(2026, 1, 1), date(2027, 12, 31)))
    with pytest.raises(calendar.CalendarError, match="no year 2030"):
        calendar.is_trading_day(date(2030, 1, 2))


def at(day: str, hour: int, minute: int = 0) -> datetime:
    return datetime.fromisoformat(f"{day}T{hour:02d}:{minute:02d}:00").replace(tzinfo=AMS)


@pytest.mark.parametrize(
    ("started", "received", "expected", "why"),
    [
        (at("2027-02-03", 9), at("2027-02-03", 9, 40), "2027-02-03", "started before 14:00, published in time"),
        (
            at("2027-02-03", 13, 59),
            at("2027-02-03", 15, 0),
            "2027-02-03",
            "received exactly 30 minutes before the open",
        ),
        (at("2027-02-03", 13, 59), at("2027-02-03", 15, 1), "2027-02-04", "published too late for that day's open"),
        (at("2027-02-03", 14, 0), at("2027-02-03", 14, 30), "2027-02-04", "started at 14:00: never the same day"),
        (at("2027-02-03", 22, 0), at("2027-02-03", 22, 30), "2027-02-04", "an evening session"),
        (at("2027-02-05", 16, 0), at("2027-02-05", 16, 30), "2027-02-08", "Friday afternoon: Monday"),
        (at("2027-02-06", 10, 0), at("2027-02-06", 10, 30), "2027-02-08", "a weekend session"),
        (at("2026-11-26", 9, 0), at("2026-11-26", 9, 30), "2026-11-27", "Thanksgiving: the next trading day"),
        (at("2027-02-03", 9), at("2027-02-04", 16, 0), "2027-02-05", "publishing failed: received after the next open"),
        (at("2027-03-15", 13, 15), at("2027-03-15", 13, 45), "2027-03-15", "clocks differ: the open is at 14:30"),
        (at("2027-03-15", 13, 30), at("2027-03-15", 14, 5), "2027-03-16", "clocks differ: received too late"),
    ],
)
def test_the_fill_day(started: datetime, received: datetime, expected: str, why: str) -> None:
    assert calendar.fill_day(received, started).isoformat() == expected, why


def test_the_opening_time_follows_the_clocks_of_both_places() -> None:
    assert calendar.opening(date(2027, 2, 3)).astimezone(AMS).strftime("%H:%M") == "15:30"
    assert (
        calendar.opening(date(2027, 3, 15)).astimezone(AMS).strftime("%H:%M") == "14:30"
    )  # US changed, Europe not yet
    assert calendar.opening(date(2027, 3, 29)).astimezone(AMS).strftime("%H:%M") == "15:30"
    with pytest.raises(calendar.CalendarError):
        calendar.fill_day(datetime(2027, 2, 3, 9), datetime(2027, 2, 3, 9, tzinfo=UTC))

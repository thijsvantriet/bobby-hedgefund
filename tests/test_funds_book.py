from __future__ import annotations

from datetime import UTC, date, datetime
from fractions import Fraction as F
from pathlib import Path

import pytest
from fundkit import (
    COMPANIES,
    FRI,
    MON,
    NEXT_MON,
    THU,
    TUE,
    WED,
    company,
    order,
    session,
    store_day,
    store_splits,
    universe,
)
from logkit import clock, forecast, make_log

from bobby_hedgefund.funds import dice, engine, events, orders
from bobby_hedgefund.funds.book import Booker, check, replay
from bobby_hedgefund.funds.orders import Proposal
from bobby_hedgefund.funds.prices import PriceBook
from bobby_hedgefund.log.records import FILL_RULE_PILOT
from bobby_hedgefund.log.store import Log

FLAT = {
    "AAA": (10.0, 10.0),
    "BBB": (20.0, 20.0),
    "CCC": (5.0, 5.0),
    "XBI": (100.0, 100.0),
    "IBB": (50.0, 50.0),
    "URTH": (200.0, 200.0),
}
M = engine.START_CASH_CENTS


def setup(tmp_path: Path, funds: tuple[str, ...] = ("careful",)) -> tuple[Log, Path]:
    log = make_log(tmp_path)
    with log.writer(MON, clock()) as w:
        w.add("funds_start", {"day": MON.isoformat(), "funds": list(funds), "cash_cents": M})
        if "dice" in funds:
            w.add(
                "dice_seed",
                {"seed": "ab" * 32, "rule_version": dice.RULE_VERSION, "funds": dice.FUNDS, "per_fund": dice.PER_FUND},
            )
    store_splits(tmp_path / "prices", [])
    return log, tmp_path / "prices"


def run(
    log: Log, prices_root: Path, day: date, covered: set[int] | None = None, table=None, dice_books=None, cutoff=None
) -> Booker:
    with log.writer(day, clock()) as w:
        booker = Booker(
            log,
            w,
            PriceBook(prices_root, cutoff, today=date(2027, 3, 1)),
            universe(),
            table or [],
            covered if covered is not None else set(COMPANIES),
            on_day=dice_books.book_day if dice_books else None,
        )
        booker.run()
    return booker


def decide(log: Log, day: date, *bodies: dict, received_for=None) -> list[int]:
    with log.writer(day, clock()) as w:
        w.add("session_start", session(log, day, 9, received_for))
        return [w.add("decision", body).seq for body in bodies]


# ---------------------------------------------------------------- a decision, its fill and the books


def test_a_decision_is_filled_at_the_next_opening_price_and_the_books_follow_from_the_log(tmp_path: Path) -> None:
    log, prices = setup(tmp_path)
    (ref,) = decide(log, MON, order(101, "buy", "3%"))
    store_day(prices, MON, FLAT)
    store_day(prices, TUE, {**FLAT, "AAA": (12.34, 13.0)})
    # Tuesday's session: it learns when Monday's publication was received (10:00 Amsterdam, before the open).
    decide(log, TUE, received_for=(MON, 9, 0))
    booker = run(log, prices, WED)
    assert booker.report.days == [MON, TUE] and booker.report.fills == 1
    fills = [e for e in log.entries() if e.kind == "fill"]
    assert fills[0].record["ref"] == ref and fills[0].record["fill_day"] == MON.isoformat()
    assert set(fills[0].record["details"]) == {"sealed", "why"}
    details = log.opened(fills[0])["details"]
    assert details["shares"] == 3000 and details["price"] == "10" and details["amount_cents"] == 3_000_000
    assert details["cost_cents"] == 7_500 and details["cost_rate"] == "0.25%"  # a company above $2 billion
    books = replay(log)
    fund = books.funds["careful"]
    assert fund.cash == M - 3_000_000 - 7_500 and fund.positions[101].shares == 3000 and not fund.orders
    assert books.values[MON]["funds"]["careful"]["value_cents"] == M - 7_500
    assert books.values[TUE]["funds"]["careful"]["value_cents"] == M - 3_000_000 - 7_500 + 3000 * 1300
    assert check(log, PriceBook(prices)) == [] and not log.verify().problems
    public = b"".join(p.read_bytes() for p in sorted((log.staging / "log").rglob("*.jsonl")))
    for private in (b"3000000", b"12.34", b'"shares"', b"7500", b"value_cents"):
        assert private not in public


def test_an_afternoon_session_is_filled_the_next_trading_day_and_a_weekend_is_walked_over(tmp_path: Path) -> None:
    log, prices = setup(tmp_path)
    with log.writer(FRI, clock()) as w:
        w.add("session_start", session(log, FRI, 15))  # 16:00 in Amsterdam
        w.add("decision", order(102, "buy", "2%"))
    for day in (MON, TUE, WED, THU, FRI, NEXT_MON):
        store_day(prices, day, FLAT)
    decide(log, NEXT_MON, received_for=(FRI, 15, 30))
    booker = run(log, prices, date(2027, 2, 9))
    assert booker.report.days == [MON, TUE, WED, THU, FRI, NEXT_MON]  # every trading day, no Saturday or Sunday
    (fill,) = [e for e in log.entries() if e.kind == "fill"]
    assert fill.record["fill_day"] == NEXT_MON.isoformat()


def test_without_the_price_file_of_a_trading_day_nothing_is_booked_past_it(tmp_path: Path) -> None:
    log, prices = setup(tmp_path)
    store_day(prices, MON, FLAT)
    store_day(prices, WED, FLAT)  # Tuesday's download failed
    booker = run(log, prices, THU)
    assert booker.report.days == [MON] and booker.report.waiting_for == TUE
    store_day(prices, TUE, FLAT, when=datetime(2027, 2, 5, 6, tzinfo=UTC))
    assert run(log, prices, FRI).report.days == [TUE, WED]


def test_no_day_is_booked_before_the_fill_day_of_its_orders_is_known(tmp_path: Path) -> None:
    log, prices = setup(tmp_path)
    decide(log, MON, order(101))
    store_day(prices, MON, FLAT)
    store_day(prices, TUE, {**FLAT, "AAA": (11.0, 11.0)})
    # The log does not say yet when Monday's publication was received: its orders have no fill day.
    early = run(log, prices, WED)
    assert early.report.days == [] and "publication of 2027-02-01 was received" in early.report.notes[0]
    decide(log, WED, received_for=(MON, 9, 0))
    assert run(log, prices, WED).report.days == [MON, TUE]
    (fill,) = [e for e in log.entries() if e.kind == "fill"]
    assert fill.record["fill_day"] == MON.isoformat() and log.opened(fill)["details"]["price"] == "10"


def test_a_list_of_splits_older_than_the_day_stops_the_booking(tmp_path: Path) -> None:
    from bobby_hedgefund.archive.store import Archive
    from bobby_hedgefund.prices import massive

    log, prices = setup(tmp_path)
    store_day(prices, MON, FLAT)
    body = b'{"status":"OK","adjusted":false,"results":[{"T":"AAA","o":10,"h":10,"l":10,"c":10,"v":1}]}'
    with Archive(prices) as archive:  # Tuesday's prices arrive, but that morning the list of splits failed
        archive.store(
            massive.DAILY_SOURCE, massive.day_name(WED), body, run="x", when=datetime(2027, 2, 4, 6, tzinfo=UTC)
        )
    store_day(prices, TUE, FLAT, when=datetime(2027, 2, 2, 1, tzinfo=UTC))  # the list is of the night before
    booker = run(log, prices, THU)
    assert booker.report.days == [MON, TUE] and booker.report.waiting_for == WED
    assert "list of share splits is older" in booker.report.notes[-1]


def test_only_price_files_stored_before_the_cut_off_are_used(tmp_path: Path) -> None:
    log, prices = setup(tmp_path)
    store_day(prices, MON, FLAT)
    store_day(prices, TUE, FLAT)  # stored on Wednesday morning at 06:00
    early = run(log, prices, WED, cutoff=datetime(2027, 2, 3, 5, tzinfo=UTC))
    assert early.report.days == [MON]
    assert run(log, prices, WED, cutoff=datetime(2027, 2, 3, 7, tzinfo=UTC)).report.days == [TUE]


def test_booking_twice_changes_nothing(tmp_path: Path) -> None:
    log, prices = setup(tmp_path)
    decide(log, MON, order(101))
    store_day(prices, MON, FLAT)
    decide(log, TUE, received_for=(MON, 9, 0))
    run(log, prices, TUE)
    count = len(log.entries())
    again = run(log, prices, TUE)
    assert again.report.days == [] and len(log.entries()) == count


def test_a_share_without_an_opening_price_waits_and_then_lapses(tmp_path: Path) -> None:
    log, prices = setup(tmp_path)
    decide(log, MON, order(103, "buy", "2%"))
    halted = {**FLAT, "CCC": (None, 5.0)}
    days = [MON, TUE, WED, THU, FRI, NEXT_MON, date(2027, 2, 9)]
    for day in days:
        store_day(prices, day, halted)
    decide(log, TUE, received_for=(MON, 9, 0))
    run(log, prices, date(2027, 2, 10))
    (closed,) = [e for e in log.entries() if e.kind == "order_closed"]
    assert closed.record["outcome"] == "lapsed" and closed.record["day"] == NEXT_MON.isoformat()  # the fifth day after
    assert not replay(log).funds["careful"].orders


def test_a_wrong_price_file_shows_up_when_the_books_are_recomputed(tmp_path: Path) -> None:
    log, prices = setup(tmp_path)
    decide(log, MON, order(101))
    store_day(prices, MON, FLAT)
    store_day(prices, TUE, FLAT)
    decide(log, TUE, received_for=(MON, 9, 0))
    run(log, prices, WED)
    other = tmp_path / "other-prices"
    store_day(other, MON, FLAT)
    store_day(other, TUE, {**FLAT, "AAA": (10.0, 11.0)})
    problems = check(log, PriceBook(other))
    assert any("not the one the day was booked with" in p for p in problems)
    assert any("recomputed value or cash differs" in p for p in problems)


# ---------------------------------------------------------------- company events


def holding(tmp_path: Path, cik: int = 101, size: str = "5%") -> tuple[Log, Path]:
    log, prices = setup(tmp_path)
    decide(log, MON, order(cik, "buy", size))
    store_day(prices, MON, FLAT)
    decide(log, TUE, received_for=(MON, 9, 0))
    return log, prices


def test_a_share_split_multiplies_the_shares_and_pays_a_fraction_out_in_cash(tmp_path: Path) -> None:
    log, prices = holding(tmp_path, 103, "5%")  # 10,000 shares of CCC at $5
    store_splits(prices, [("CCC", TUE, 3, 1)])  # three old shares become one
    store_day(prices, TUE, {**FLAT, "CCC": (15.0, 15.0)})
    run(log, prices, WED)
    fund = replay(log).funds["careful"]
    assert fund.positions[103].shares == 3333  # 10,000 / 3 = 3333 and a third
    cost = 50_000  # 1% of $50,000: a company below $1 billion
    assert fund.cash == M - 5_000_000 - cost + 500  # a third of a share at the opening price of $15
    (event,) = [e for e in log.entries() if e.kind == "company_event"]
    assert event.record["event"] == "split" and event.record["checked_against_filing"] is False
    assert set(event.record["terms"]) == {"sealed", "why"}
    values = replay(log).values
    assert values[TUE]["funds"]["careful"]["value_cents"] == fund.cash + 3333 * 1500
    assert check(log, PriceBook(prices)) == []


def test_a_forward_split_and_one_before_the_position_existed(tmp_path: Path) -> None:
    log, prices = holding(tmp_path, 101, "5%")  # 5000 shares of AAA at $10
    store_splits(
        prices,
        [("AAA", TUE, 1, 4), ("AAA", date(2027, 1, 4), 1, 2), ("BBB", TUE, 1, 2), ("XBI", date(2027, 1, 5), 1, 2)],
    )
    store_day(prices, TUE, {**FLAT, "AAA": (2.5, 2.5)})
    run(log, prices, WED)
    books = replay(log)
    assert books.funds["careful"].positions[101].shares == 20_000  # only Tuesday's split; January's was before the fund
    assert [e.kind for e in log.entries()].count("company_event") == 1  # BBB is not held: nothing to book
    # The index funds were bought on Monday at $100: a split of last January is in that price already.
    assert books.index_units["XBI"] == 10_000 and books.values[TUE]["index"]["XBI"]["value_cents"] == M


def test_on_the_day_of_a_split_an_order_is_sized_on_the_fund_as_it_was_at_the_last_close(tmp_path: Path) -> None:
    log, prices = holding(tmp_path, 101, "5%")  # 5000 shares of AAA at $10: worth $50,000
    with log.writer(TUE, clock()) as w:
        w.add("decision", order(102, "buy", "3%"))
    store_splits(prices, [("AAA", WED, 1, 4), ("XBI", WED, 1, 2)])
    store_day(prices, TUE, FLAT)
    store_day(prices, WED, {**FLAT, "AAA": (2.5, 2.5), "XBI": (50.0, 50.0)})
    decide(log, WED, received_for=(TUE, 9, 0))
    run(log, prices, THU)
    fill = next(e for e in log.entries() if e.kind == "fill" and e.record["company"]["cik"] == 102)
    details = log.opened(fill)["details"]
    value = M - 12_500  # the fund on Tuesday's close: the buying cost of AAA is all it lost
    assert details["fund_value_before_cents"] == value  # not 20,000 new shares at the old price of $10
    assert details["shares"] == (F(3, 100) * value / 2000).__floor__() == 1499
    books = replay(log)
    assert books.funds["careful"].positions[101].shares == 20_000
    assert books.index_units["XBI"] == 20_000 and books.values[WED]["index"]["XBI"]["value_cents"] == M
    assert check(log, PriceBook(prices)) == []


def test_a_reverse_split_to_less_than_one_share_pays_the_position_out_also_without_an_opening_price(
    tmp_path: Path,
) -> None:
    log, prices = holding(tmp_path, 103, "0.5%")  # 1000 shares of CCC at $5
    store_splits(prices, [("CCC", TUE, 3000, 1)])
    store_day(prices, TUE, {**FLAT, "CCC": (None, 15_000.0)})  # the new share did not open that day
    run(log, prices, WED)
    fund = replay(log).funds["careful"]
    assert 103 not in fund.positions
    assert fund.cash == M - 500_000 - 5_000 + 500_000  # a third of a new share, at the old close of $5 times 3000


def test_a_run_that_stopped_half_way_through_a_day_comes_out_the_same_as_one_that_did_not(tmp_path: Path) -> None:
    def scenario(sub: Path, crash: bool) -> tuple[Log, Path]:
        log, prices = setup(sub)
        decide(log, MON, order(101, "buy", "60%", fund="careful"), order(102, "buy", "60%"), order(103, "buy", "5%"))
        store_splits(prices, [("XBI", MON, 1, 2)])
        store_day(prices, MON, FLAT)
        decide(log, TUE, received_for=(MON, 9, 0))
        if crash:
            real = Booker._write
            calls = {"n": 0}

            def stops(self, booking, price_file, value_before):  # the second booking of the day never happens
                calls["n"] += 1
                if calls["n"] == 2:
                    raise OSError("power cut")
                real(self, booking, price_file, value_before)

            Booker._write = stops  # type: ignore[method-assign]
            try:
                with pytest.raises(OSError):
                    run(log, prices, TUE)
            finally:
                Booker._write = real  # type: ignore[method-assign]
            assert [e.kind for e in log.entries()].count("fill") == 1 and not replay(log).booked
        report = run(log, prices, TUE).report
        assert report.days == [MON] and report.fills == 3
        return log, prices

    whole, _ = scenario(tmp_path / "whole", crash=False)
    broken, prices = scenario(tmp_path / "broken", crash=True)

    def facts(log: Log) -> list:
        return [(e.kind, e.record.get("ref"), log.opened(e).get("details")) for e in log.entries() if e.kind == "fill"]

    assert facts(whole) == facts(broken) and len(facts(broken)) == 3  # the same cut for cash, no fill twice
    assert replay(whole).funds["careful"].cash == replay(broken).funds["careful"].cash
    assert replay(whole).values == replay(broken).values and check(broken, PriceBook(prices)) == []


def test_a_takeover_for_cash_pays_the_deal_price_without_cost_and_ends_open_orders(tmp_path: Path) -> None:
    log, prices = holding(tmp_path, 101, "5%")
    with log.writer(TUE, clock()) as w:
        w.add("decision", order(101, "add", "1%"))
        w.add("session_start", session(log, TUE, 10, received_for=(TUE, 9, 30)))
    table = tmp_path / "events"
    link = "https://www.sec.gov/Archives/edgar/data/101/000000000027000001.txt"
    events.add(
        table,
        "2027-02-02T08:00:00Z",
        cik=101,
        name="Aaa Therapeutics Inc",
        kind="cash takeover",
        effective=TUE,
        filing=link,
        cash_per_share="14.25",
    )
    store_day(prices, TUE, FLAT)
    run(log, prices, WED, table=events.load(table))
    fund = replay(log).funds["careful"]
    assert 101 not in fund.positions and not fund.orders
    assert fund.cash == M - 5_000_000 - 12_500 + 5000 * 1425
    kinds = [e.kind for e in log.entries()]
    assert "company_event" in kinds and "order_closed" in kinds
    closed = next(e for e in log.entries() if e.kind == "order_closed")
    assert closed.record["outcome"] == "company left"
    assert run(log, prices, WED, table=events.load(table)).report.events == 0  # booked once


def test_a_takeover_for_shares_sells_the_buyer_when_it_is_not_covered_and_keeps_it_when_it_is(tmp_path: Path) -> None:
    link = "https://www.sec.gov/Archives/edgar/data/101/000000000027000002.txt"
    for covered, kept in ((set(), False), ({102}, True)):
        sub = tmp_path / ("kept" if kept else "sold")
        log, prices = holding(sub, 101, "5%")  # 5000 shares of AAA
        events.add(
            sub / "events",
            "2027-02-02T08:00:00Z",
            cik=101,
            name="Aaa Therapeutics Inc",
            kind="share takeover",
            effective=TUE,
            filing=link,
            ratio="0.3333",
            buyer_cik=102,
            buyer_ticker="BBB",
            buyer_name="Bbb Bio Inc",
        )
        store_day(prices, TUE, FLAT)
        run(log, prices, WED, covered=covered, table=events.load(sub / "events"))
        fund = replay(log).funds["careful"]
        base = M - 5_000_000 - 12_500
        assert 101 not in fund.positions
        if kept:  # 5000 x 0.3333 = 1666.5: 1666 shares and half a share in cash at the buyer's opening price
            assert fund.positions[102].shares == 1666 and fund.cash == base + 1000
        else:  # sold at $20 with the cost of a company between $1 and $2 billion
            assert 102 not in fund.positions and fund.cash == base + 1000 + 1666 * 2000 - 16_660
        assert check(log, PriceBook(prices)) == []


def test_the_table_of_events_only_grows_and_refuses_what_is_not_built(tmp_path: Path) -> None:
    link = "https://www.sec.gov/Archives/edgar/data/101/000000000027000001.txt"
    common = {"cik": 101, "name": "Aaa", "effective": TUE, "filing": link}
    first = events.add(tmp_path, "2027-02-02T08:00:00Z", kind="cash takeover", cash_per_share="14.25", **common)
    second = events.add(tmp_path, "2027-02-03T08:00:00Z", kind="cash takeover", cash_per_share="15", **common)
    assert [e.key for e in events.load(tmp_path)] == [first.key, second.key] and first.cash_per_share == F("14.25")
    for bad in (
        {"kind": "spin-off"},
        {"kind": "cash takeover"},
        {"kind": "cash takeover", "cash_per_share": "0"},
        {"kind": "share takeover", "ratio": "0.5"},
        {"kind": "cash takeover", "cash_per_share": "14.25", "filing": "https://example.org/x"},
    ):
        with pytest.raises(events.EventError):
            events.add(tmp_path, "2027-02-03T08:00:00Z", **{**common, **bad})
    path = tmp_path / events.FILE
    path.write_bytes(path.read_bytes().replace(b"14.25", b"99.99"))
    with pytest.raises(events.EventError, match="changed, removed"):
        events.load(tmp_path)


# ---------------------------------------------------------------- the limits, in code


def judged(
    fund_name: str = "careful", positions: dict[int, int] | None = None, waiting: list[engine.Order] | None = None, **kw
):
    fund = engine.Fund(fund_name, M, peak=M)
    for cik, shares in (positions or {}).items():
        fund.positions[cik] = engine.Position(cik, COMPANIES.get(cik, (f"T{cik}", "", 0))[0], "n", shares)
    for o in waiting or []:
        fund.orders[o.ref] = o
    prices = {"AAA": F(10), "BBB": F(20), "CCC": F(5), "DDD": F(1)}
    value, _ = engine.fund_value(fund, prices.get)

    def go(*proposals: Proposal, buyable=None, covered=None, risky=None):
        everything = set(COMPANIES) | set(positions or {})
        return orders.check(
            fund,
            kw.get("value", value),
            lambda t: prices.get(t, F(1)),
            list(proposals),
            buyable=everything if buyable is None else buyable,
            covered=everything if covered is None else covered,
            risky=risky or set(),
        )

    return go


def buy(cik: int, size: str, action: str = "buy") -> Proposal:
    ticker, name, _ = COMPANIES.get(cik, (f"T{cik}", f"Company {cik}", None))
    return Proposal(action, cik, name, ticker, F(size) / 100 if size else None)


def test_the_per_stock_limit_cuts_an_order_down_or_refuses_it() -> None:
    (v,) = judged()(buy(101, "7"))
    assert (v.outcome, v.limit, v.allowed) == ("reduced", "per-stock limit", F(5, 100))
    (v,) = judged("bold")(buy(101, "7"))
    assert (v.outcome, v.allowed) == ("ok", F(7, 100))  # the Bold fund may go to 8%
    go = judged(positions={101: 4_800})  # $48,000 in a fund of $1,048,000: 4.58%
    (v,) = go(buy(101, "3", "add"))
    assert v.outcome == "refused" and v.limit == "per-stock limit"  # the room left is below the smallest trade
    assert v.basis["weight_before"] == "4.58%" and v.basis["fund_value_cents"] == M + 4_800_000


def test_orders_that_are_still_waiting_count_as_if_they_were_filled() -> None:
    waiting = [
        engine.Order(7, "careful", 101, "AAA", "n", "buy", F(4, 100), MON),
        engine.Order(8, "careful", 102, "BBB", "n", "buy", F(4, 100), MON),
    ]
    held = {1000 + i: 1 for i in range(23)}
    go = judged(positions=held, waiting=waiting)
    (v,) = go(buy(103, "2"))
    assert v.limit == "25 positions"  # 23 held and 2 on their way
    selling = [engine.Order(9, "careful", 1000, "T1000", "n", "sell", None, MON)]
    (v,) = judged(positions=held | {1023: 1, 1024: 1}, waiting=selling)(buy(103, "2"))
    assert v.outcome == "ok"  # a whole position on its way out makes room


def test_a_new_decision_replaces_the_waiting_order_for_that_company_and_is_judged_without_it() -> None:
    # A whole sale of AAA is waiting; a new "buy 5%" replaces it. The position is still there, at about 4.8%.
    selling = [engine.Order(8, "careful", 101, "AAA", "n", "sell", None, MON)]
    (v,) = judged(positions={101: 5000}, waiting=selling)(buy(101, "5", "add"))
    assert v.outcome == "refused" and v.limit == "per-stock limit"  # not 5% on top of the 5% that stays
    # A buy of 4% is waiting; a new buy of 3% replaces it, it does not come on top of it.
    buying = [engine.Order(7, "careful", 101, "AAA", "n", "buy", F(4, 100), MON)]
    (v,) = judged(waiting=buying)(buy(101, "3"))
    assert (v.outcome, v.allowed) == ("ok", F(3, 100))
    # When the new decision is refused, the waiting order stays and counts again.
    held = {1000 + i: 1 for i in range(24)}
    a, b = judged(positions=held, waiting=buying)(buy(101, "0.1"), buy(102, "2"))
    assert a.limit == "below the smallest trade" and b.limit == "25 positions"


def test_one_order_per_company_in_a_round_whatever_the_order_they_come_in() -> None:
    go = judged(positions={101: 5000})
    for first, second in (
        (Proposal("sell", 101, "n", "AAA"), buy(101, "3", "add")),
        (buy(101, "0.5", "add"), Proposal("sell", 101, "n", "AAA")),
    ):
        results = {v.proposal.action: v for v in go(first, second)}
        assert results["sell"].outcome == "ok" and results["add"].limit == "one order per company a round"
    a, b = judged()(buy(101, "3"), buy(101, "3", "add"))
    assert (a.outcome, b.limit) == ("ok", "one order per company a round")


def test_at_most_25_positions_and_a_sale_in_the_same_round_makes_room() -> None:
    held = {1000 + i: 1 for i in range(25)}
    go = judged(positions=held)
    (v,) = go(buy(101, "2"))
    assert v.limit == "25 positions"
    sell, new = go(Proposal("sell", 1000, "n", "T1000"), buy(101, "2"))
    assert (sell.outcome, new.outcome) == ("ok", "ok")  # sells are judged first, whatever the order they came in
    new, sell = go(buy(101, "2"), Proposal("sell", 1000, "n", "T1000"))
    assert (sell.outcome, new.outcome) == ("ok", "ok")


def test_the_make_or_break_limit_differs_per_fund() -> None:
    risky = {1001, 1002, 1003, 101}
    held = {1001: 1, 1002: 1, 1003: 1}
    (v,) = judged("careful", positions=held)(buy(101, "2"), risky=risky)
    assert v.limit == "make-or-break limit"  # three such positions already
    (v,) = judged("bold", positions=held)(buy(101, "2"), risky=risky)
    assert v.outcome == "ok"
    (v,) = judged("careful", positions=held)(buy(102, "2"), risky=risky)
    assert v.outcome == "ok"  # a company without such a result is not counted
    (v,) = judged("careful", positions={**held, 101: 100})(buy(101, "2", "add"), risky=risky)
    assert v.outcome == "ok"  # adding to a position that exists is no new position


def test_only_covered_companies_of_the_universe_can_be_bought_but_anything_held_can_be_sold() -> None:
    go = judged(positions={104: 100})
    (v,) = go(buy(101, "2"), covered={102})
    assert v.limit == "not on the covered list"
    (v,) = go(buy(101, "2"), buyable={102})
    assert v.limit == "not in the universe"
    (v,) = go(Proposal("sell", 104, "n", "DDD"), buyable=set(), covered=set())
    assert v.outcome == "ok"  # a company that dropped out is no longer bought but may be held and sold


def test_the_brake_and_the_smallest_trade_at_the_moment_of_the_decision() -> None:
    (v,) = judged(value=70_000_000)(buy(101, "2"))
    assert v.limit == "a limit on the fund's value" and v.basis["limit"] == "brake"  # not named in public
    (v,) = judged()(Proposal("buy", 101, "n", "AAA"))
    assert v.limit == "below the smallest trade"  # a buy without a size is refused, not a crash
    (v,) = judged()(buy(101, "0.4"))
    assert v.limit == "below the smallest trade"
    (v,) = judged(positions={101: 5000})(Proposal("reduce", 101, "n", "AAA", F(4, 1000)))
    assert v.limit == "below the smallest trade"
    (v,) = judged()(Proposal("nothing"))
    assert v.outcome == "ok"


def test_make_or_break_companies_come_from_open_forecasts_within_thirty_days(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    near = {**forecast(), "by_date": "2027-02-20"}
    far = {**forecast(), "by_date": "2027-06-01", "company": company(102)}
    plain = {**forecast(), "by_date": "2027-02-20", "make_or_break": False, "company": company(103)}
    done = {**forecast(), "by_date": "2027-02-20", "company": company(104)}
    with log.writer(MON, clock()) as w:
        for body in (near, far, plain, done):
            w.add("forecast", body)
        w.add("outcome", {"ref": 4, "result": "yes", "resolved_on": "2027-02-01", "summary": "Met.", "sources": []})
    assert orders.make_or_break(log.entries(), MON) == {1234567}  # the company of the made-up forecast


def test_decisions_are_logged_as_made_and_then_what_the_limits_did(tmp_path: Path) -> None:
    log, _ = setup(tmp_path)
    with log.writer(MON, clock()) as w:
        w.add("session_start", session(log, MON))
        w.add("decision", order(102, "buy", "2%"))  # an earlier order for BBB that is still waiting
    books = replay(log)
    fund = books.funds["careful"]
    thesis = order(101)["thesis"]
    wanted = [
        Proposal("buy", 101, "Aaa Therapeutics Inc", "AAA", F(7, 100), {"thesis": thesis}),
        Proposal("buy", 104, "Ddd Medicines Inc", "DDD", F(2, 100), {"thesis": thesis}),
        Proposal("add", 102, "Bbb Bio Inc", "BBB", F(1, 100), {"thesis": thesis}),
    ]
    verdicts = orders.check(fund, M, lambda t: F(10), wanted, buyable=set(COMPANIES), covered={101, 102}, risky=set())
    with log.writer(MON, clock()) as w:
        written = orders.place(w, fund, MON, verdicts, fill_rule=FILL_RULE_PILOT, cutoff="2027-02-01T09:00:00Z")
    kinds = [(e.kind, e.record.get("limit") or e.record.get("outcome") or e.record.get("size_pct")) for e in written]
    assert kinds == [
        ("decision", "7%"),  # logged as the manager decided it
        ("order_reduced", "per-stock limit"),
        ("decision", "2%"),
        ("order_refused", "not on the covered list"),
        ("decision", "1%"),
        ("order_closed", "replaced"),  # the new decision about BBB replaces the waiting order
    ]
    reduced = written[1].record
    assert (reduced["asked_pct"], reduced["allowed_pct"]) == ("7%", "5%") and set(reduced["basis"]) == {"sealed", "why"}
    after = replay(log).funds["careful"]
    assert sorted((o.cik, o.size) for o in after.orders.values()) == [(101, F(5, 100)), (102, F(1, 100))]
    assert sorted((o.cik, o.size) for o in fund.orders.values()) == [(101, F(5, 100)), (102, F(1, 100))]
    assert not log.verify().problems


def test_without_a_complete_list_of_splits_nothing_is_booked(tmp_path: Path) -> None:
    from bobby_hedgefund.archive.store import Archive
    from bobby_hedgefund.prices import massive
    from bobby_hedgefund.universe.inputs import InputError

    log = make_log(tmp_path)
    with log.writer(MON, clock()) as w:
        w.add("funds_start", {"day": MON.isoformat(), "funds": ["careful"], "cash_cents": M})
    body = b'{"status":"OK","adjusted":false,"results":[{"T":"AAA","o":10,"h":10,"l":10,"c":10,"v":1}]}'
    with Archive(tmp_path / "prices") as archive:  # a price file, but never a list of splits
        archive.store(
            massive.DAILY_SOURCE, massive.day_name(MON), body, run="x", when=datetime(2027, 2, 2, 6, tzinfo=UTC)
        )
    with pytest.raises(InputError, match="no complete list of share splits"):
        run(log, tmp_path / "prices", TUE)
    assert [e.kind for e in log.entries()] == ["funds_start"]


def test_a_size_that_follows_from_what_a_position_is_worth_is_sealed(tmp_path: Path) -> None:
    log, prices = holding(tmp_path, 101, "3%")  # 3000 shares of AAA
    store_day(prices, TUE, {**FLAT, "AAA": (12.0, 12.0)})
    run(log, prices, WED)
    books = replay(log)
    fund = books.funds["careful"]
    value = books.values[TUE]["funds"]["careful"]["value_cents"]
    thesis = order(101)["thesis"]
    wanted = [Proposal("add", 101, "Aaa Therapeutics Inc", "AAA", F(3, 100), {"thesis": thesis})]
    verdicts = orders.check(fund, value, lambda t: F(12), wanted, buyable={101}, covered={101}, risky=set())
    assert verdicts[0].outcome == "reduced" and verdicts[0].from_prices
    with log.writer(WED, clock()) as w:
        written = orders.place(w, fund, WED, verdicts, fill_rule=FILL_RULE_PILOT, cutoff="2027-02-03T09:00:00Z")
    reduced = next(e for e in written if e.kind == "order_reduced")
    assert set(reduced.record["allowed_pct"]) == {"sealed", "why"}  # 5% minus today's weight would give the return away
    allowed = log.opened(reduced)["allowed_pct"]
    assert replay(log).funds["careful"].orders[written[0].seq].size == F(allowed[:-1]) / 100 == verdicts[0].allowed
    assert not log.verify().problems


def test_a_price_far_back_can_be_looked_up_without_losing_the_day_just_read(tmp_path: Path) -> None:
    prices = tmp_path / "prices"
    days = [d for d in (date(2027, 2, 1 + i) for i in range(26)) if d.weekday() < 5]
    for i, day in enumerate(days):
        store_day(prices, day, {"AAA": (10.0, 10.0), **({"OLD": (1.0, 7.0)} if i == 0 else {})})
    book = PriceBook(prices, today=date(2027, 4, 1))
    assert book.last_close("OLD", days[-1]) == (F(7), days[0])  # walks back through every stored day
    assert book.last_close("AAA", days[-1]) == (F(10), days[-1]) and book.last_close("NONE", days[-1]) is None


def test_a_fill_never_lies_before_its_decision_even_when_a_clock_says_the_publication_came_first(
    tmp_path: Path,
) -> None:
    log, prices = setup(tmp_path)
    decide(log, WED, order(101))
    for day in (MON, TUE, WED):
        store_day(prices, day, FLAT)
    with log.writer(THU, clock()) as w:  # the log says Wednesday's publication was received on Monday
        body = session(log, THU, 9)
        body["previous_publication"] = {
            "session_day": WED.isoformat(),
            "received": "2027-02-01T09:00:00Z",
            "source": "local commit (pilot)",
        }
        w.add("session_start", body)
    run(log, prices, THU)
    (fill,) = [e for e in log.entries() if e.kind == "fill"]
    assert fill.record["fill_day"] == WED.isoformat()

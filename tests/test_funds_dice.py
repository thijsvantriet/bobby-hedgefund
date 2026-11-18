from __future__ import annotations

import hashlib
import json
from datetime import date
from fractions import Fraction as F
from pathlib import Path

import pytest
from fundkit import COMPANIES, MON, TUE, WED, session, store_day, store_splits, universe
from logkit import clock, make_log

from bobby_hedgefund.funds import cli, dice, engine, rules
from bobby_hedgefund.funds.book import Booker, check, replay
from bobby_hedgefund.funds.prices import PriceBook
from bobby_hedgefund.log.store import Log

SEED = "ab" * 32
FLAT = {"AAA": (10.0, 10.0), "BBB": (20.0, 20.0), "CCC": (5.0, 5.0), "DDD": (2.0, 2.0), "XBI": (100.0, 100.0)}
M = engine.START_CASH_CENTS
INFO = {cik: (ticker, name) for cik, (ticker, name, _) in COMPANIES.items()}


def test_the_draw_can_be_repeated_by_hand_from_fingerprints() -> None:
    covered = list(range(1000, 1060))

    def by_hand(fund: int) -> list[int]:
        def rank(cik: int) -> str:
            return hashlib.sha256(f"{SEED}\n2027-02\n{fund}\n{cik}".encode()).hexdigest()

        return sorted(sorted(covered, key=lambda c: (rank(c), c))[:20])

    for fund in (1, 2, 500, 1000):
        assert dice.draw(SEED, "2027-02", covered, fund) == by_hand(fund)
    assert dice.draw(SEED, "2027-02", covered, 1) != dice.draw(SEED, "2027-02", covered, 2)
    assert dice.draw(SEED, "2027-02", covered, 1) != dice.draw(SEED, "2027-03", covered, 1)
    assert dice.draw(SEED, "2027-02", reversed(covered), 1) == dice.draw(SEED, "2027-02", covered, 1)
    assert dice.draw(SEED, "2027-02", [5, 6, 7], 9) == [5, 6, 7]  # fewer than 20 covered: all of them
    assert len(dice.new_seed()) == 64 and dice.new_seed() != dice.new_seed()


def test_every_company_is_drawn_about_equally_often() -> None:
    covered = list(range(1000, 1040))  # 40 companies, 20 per fund: each in about half of the 1,000 funds
    counts = dict.fromkeys(covered, 0)
    for fund in range(1, dice.FUNDS + 1):
        for cik in dice.draw(SEED, "2027-02", covered, fund):
            counts[cik] += 1
    assert sum(counts.values()) == 20_000 and all(420 < n < 580 for n in counts.values())


def test_a_place_among_the_dice_funds() -> None:
    assert (
        dice.place_among(5, [1, 2, 5, 9]) == 3 and dice.place_among(0, [1, 2]) == 0 and dice.place_among(9, [1, 2]) == 2
    )


def start(tmp_path: Path) -> tuple[Log, Path, Path]:
    log = make_log(tmp_path)
    prices = tmp_path / "prices"
    store_splits(prices, [])
    with log.writer(MON, clock()) as w:
        w.add("funds_start", {"day": MON.isoformat(), "funds": ["careful", "dice"], "cash_cents": M})
        w.add(
            "dice_seed",
            {"seed": SEED, "rule_version": dice.RULE_VERSION, "funds": dice.FUNDS, "per_fund": dice.PER_FUND},
        )
        w.add("session_start", session(log, MON))
    return log, prices, tmp_path / "books" / "dice"


def booked(log: Log, prices: Path, folder: Path, day: date) -> dice.DiceBooks:
    with log.writer(day, clock()) as w:
        books = dice.DiceBooks.load(log, folder)
        Booker(
            log, w, PriceBook(prices, today=date(2027, 3, 1)), universe(), [], set(COMPANIES), on_day=books.book_day
        ).run()
    return books


def test_a_thousand_funds_are_drawn_filled_and_valued_from_private_files_only(tmp_path: Path) -> None:
    log, prices, folder = start(tmp_path)
    store_day(prices, MON, FLAT)
    books = dice.DiceBooks.load(log, folder)
    assert len(books.funds) == 1000 and books.seed == SEED
    with log.writer(MON, clock()) as w:
        draw = w.add("dice_draw", books.plan_draw("2027-02", MON, set(COMPANIES), INFO, lambda t: F(10)))
    assert draw.record["covered"] == [101, 102, 103, 104] and set(draw.record["orders"]) == {"sealed", "why"}
    with pytest.raises(dice.DiceError, match="made already"):
        books.plan_draw("2027-02", MON, set(COMPANIES), INFO, lambda t: F(10))
    orders_file = json.loads((folder / "orders-2027-02-01.json").read_bytes())
    assert len(orders_file["orders"]) == 4000  # four covered companies: every fund buys 5% of each
    with log.writer(TUE, clock()) as w:
        w.add("session_start", session(log, TUE, 9, received_for=(MON, 9, 0)))
    store_day(prices, TUE, {**FLAT, "AAA": (10.0, 12.0)})
    books = booked(log, prices, folder, WED)
    fund = books.funds[0]
    assert {cik: p.shares for cik, p in fund.positions.items()} == {101: 5000, 102: 2500, 103: 10_000, 104: 25_000}
    costs = 12_500 + 25_000 + 50_000 + 50_000  # 0.25%, 0.5%, 1% and 1% (size unknown) of $50,000
    assert fund.cash == M - 4 * 5_000_000 - costs
    assert books.values[MON] == [M - costs] * 1000  # filled at Monday's open; nothing moved that day
    assert books.values[TUE] == [M - costs + 5000 * 200] * 1000
    # The state follows from the log and the files it names, also after a fresh start.
    again = dice.DiceBooks.load(log, folder)
    assert again.funds[999].cash == fund.cash and again.values == books.values and not again.funds[0].orders
    # Nothing of it is in the public log: one line for the draw, none per trade, no value.
    kinds = [e.kind for e in log.entries()]
    assert kinds.count("dice_draw") == 1 and kinds.count("fill") == 0 and kinds.count("day_booked") == 2
    public = b"".join(p.read_bytes() for p in sorted((log.staging / "log").rglob("*.jsonl")))
    assert b"booked-2027" not in public and b"orders-2027" not in public and b"5000" not in public
    assert check(log, PriceBook(prices)) == [] and not log.verify().problems


def test_a_changed_or_missing_dice_file_is_noticed(tmp_path: Path) -> None:
    log, prices, folder = start(tmp_path)
    store_day(prices, MON, FLAT)
    books = dice.DiceBooks.load(log, folder)
    with log.writer(MON, clock()) as w:
        w.add("dice_draw", books.plan_draw("2027-02", MON, set(COMPANIES), INFO, lambda t: F(10)))
    path = folder / "orders-2027-02-01.json"
    original = path.read_bytes()
    path.chmod(0o600)
    path.write_bytes(original.replace(b'"5%"', b'"4%"', 1))
    with pytest.raises(dice.DiceError, match="does not match its fingerprint"):
        dice.DiceBooks.load(log, folder)
    path.unlink()
    with pytest.raises(dice.DiceError, match="is missing"):
        dice.DiceBooks.load(log, folder)


def test_a_new_draw_sells_what_is_no_longer_drawn_and_leaves_small_differences_alone(tmp_path: Path) -> None:
    log, prices, folder = start(tmp_path)
    store_day(prices, MON, FLAT)
    books = dice.DiceBooks.load(log, folder)
    with log.writer(MON, clock()) as w:
        w.add("dice_draw", books.plan_draw("2027-02", MON, {101, 102}, INFO, lambda t: F(10)))
        w.add("session_start", session(log, MON, 10, received_for=(MON, 9, 0)))
    booked(log, prices, folder, TUE)
    books = dice.DiceBooks.load(log, folder)
    march = date(2027, 3, 1)
    price = {"AAA": F("10.4"), "BBB": F(30)}.get  # AAA drifted to 5.2% of the fund, BBB to 7%
    with log.writer(march, clock()) as w:
        w.add("dice_draw", books.plan_draw("2027-03", march, {101, 102, 103}, INFO, price))
    listed = [o for o in json.loads((folder / "orders-2027-03-01.json").read_bytes())["orders"] if o[0] == 1]
    by_cik = {o[2]: (o[5], o[6]) for o in listed}
    assert 101 not in by_cik  # 0.2% away from its equal part: below the smallest trade, left alone
    assert by_cik[102][0] == "sell" and by_cik[103] == ("buy", "5%")
    with log.writer(march, clock()) as w:  # and a company that is no longer covered is sold whole
        w.add("dice_draw", dice.DiceBooks.load(log, folder).plan_draw("2027-04", march, {101}, INFO, price))
    listed = [o for o in json.loads((folder / "orders-2027-03-01.json").read_bytes())["orders"] if o[0] == 1]
    assert [(o[2], o[5], o[6]) for o in listed if o[2] == 102] == [(102, "sell", None)]


# ---------------------------------------------------------------- the Rules fund, as far as it goes


def test_the_rules_fund_picks_by_cash_and_the_nearest_catalyst() -> None:
    today = date(2027, 2, 1)
    c = rules.Candidate
    candidates = [
        c(1, 24, date(2027, 6, 1), "final-phase trial"),
        c(2, 17, date(2027, 3, 1), "final-phase trial"),  # too little cash
        c(3, 30, date(2027, 3, 15), "fda decision"),
        c(4, 30, date(2027, 9, 1), "fda decision"),  # more than six months away
        c(5, 30, date(2027, 3, 1), "early trial"),  # not a large final-phase trial or an FDA decision
        c(6, 30, date(2027, 2, 1), "fda decision"),  # today: no longer ahead
        c(7, 40, date(2027, 4, 1), "fda decision"),  # not covered
        c(1, 24, date(2027, 4, 20), "fda decision"),  # a second, nearer catalyst of company 1
    ]
    assert rules.select(candidates, {1, 2, 3, 4, 5, 6}, today) == [3, 1]
    many = [c(100 + i, 20, date(2027, 3, 1 + i % 20), "fda decision") for i in range(30)]
    assert len(rules.select(many, {100 + i for i in range(30)}, today)) == 20


def test_without_its_inputs_the_rules_fund_holds_nothing_and_says_why(tmp_path: Path, monkeypatch, capsys) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    (data / "universe").mkdir(parents=True)
    header = "cik,name,in_universe,why_out,ticker_used,exchanges,sic,door,in_xbi,filer_type,market_value\n"
    rows = "".join(
        f"{cik},{name},yes,,{t},Nasdaq,2834,own code,no,domestic,{mv or ''}\n"
        for cik, (t, name, mv) in COMPANIES.items()
    )
    hidden = "105,Eee Hidden Inc,yes,,EEE,Nasdaq,3841,xbi only,yes,domestic,700000000\n"
    (data / "universe" / "2027-02-01_universe.csv").write_text(header + rows + hidden)
    store_splits(data / "prices", [])
    store_day(data / "prices", MON, {**FLAT, "EEE": (3.0, 3.0)})
    for cik in (101, 102, 105):
        (data / "pilot" / "reports" / str(cik)).mkdir(parents=True)
        (data / "pilot" / "reports" / str(cik) / "2027-02-01.md").write_text("report\n")
    assert cli.main(["start", "--funds", "careful,rules,dice", "--day", "2027-02-01"]) == 0
    assert cli.main(["start", "--funds", "nonsense", "--day", "2027-02-01"]) == 1
    assert cli.main(["draw", "--day", "2027-02-01", "--cutoff", "2027-02-03T00:00:00Z"]) == 0
    out = capsys.readouterr().out
    assert "rules: 0 companies chosen, 0 orders" in out and "dice: drawn for 2027-02 from 2 covered companies" in out
    log = Log.for_mode("pilot")
    draw = next(e for e in log.entries() if e.kind == "rules_draw")
    assert draw.record["chosen"] == [] and "not built" in draw.record["why_empty"]
    dice_draw = next(e for e in log.entries() if e.kind == "dice_draw")
    assert dice_draw.record["covered"] == [101, 102]  # the company that is there through the XBI fund only is left out
    # With inputs the fund orders its equal parts, as ordinary decisions that point to the draw.
    (data / "pilot" / "rules").mkdir()
    inputs = {"companies": [{"cik": 101, "months_of_cash": 24, "catalyst": "2027-04-01", "kind": "fda decision"}]}
    (data / "pilot" / "rules" / "2027-03-01_rules-inputs.json").write_text(json.dumps(inputs))
    assert cli.main(["draw", "--day", "2027-03-01", "--cutoff", "2027-02-03T00:00:00Z"]) == 0
    decision = [e for e in log.entries() if e.kind == "decision"][-1]
    assert (
        decision.record["fund"] == "rules" and decision.record["size_pct"] == "5%" and "thesis" not in decision.record
    )
    assert log.entries()[decision.record["draw"] - 1].kind == "rules_draw"
    assert cli.main(["book", "--day", "2027-03-01", "--cutoff", "2027-02-03T00:00:00Z"]) == 0
    assert "waiting for the time the publication of 2027-02-01 was received" in capsys.readouterr().out
    with log.writer(date(2027, 3, 2), clock()) as w:  # later sessions learn when those two days were published
        w.add("session_start", session(log, date(2027, 3, 1), 9, received_for=(MON, 9, 0)))
        w.add("session_start", session(log, date(2027, 3, 2), 9, received_for=(date(2027, 3, 1), 9, 0)))
    assert cli.main(["book", "--day", "2027-03-02", "--cutoff", "2027-02-03T00:00:00Z"]) == 0
    assert "booked: 1 trading day(s)" in capsys.readouterr().out
    assert cli.main(["check"]) == 0 and "equal to the cent" in capsys.readouterr().out
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("PRIVATE") and "rules: value $1,000,000.00" in out and "waiting: buy 5% AAA" in out
    assert replay(log).funds["rules"].orders and not log.verify().problems
    link = "https://www.sec.gov/Archives/edgar/data/101/000000000027000001.txt"
    event = ["event", "--cik", "101", "--name", "Aaa", "--effective", "2027-03-02", "--filing", link]
    assert cli.main([*event, "--kind", "cash takeover", "--cash-per-share", "14.25"]) == 0
    assert cli.main([*event, "--kind", "spin-off"]) == 1 and "not built yet" in capsys.readouterr().out

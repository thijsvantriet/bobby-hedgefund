"""Command line for the paper funds: `bobby-funds <command>`: start, book, draw, check, status, event.

Paper money only: nothing here talks to a broker or places an order anywhere. What `status` prints holds prices
and is private: it is for the owner's own screen, never for a pull request or a page.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path

from .. import paths
from ..archive.store import ArchiveError, iso, utcnow
from ..log import canon, records
from ..log.store import Log, LogError, Writer
from ..universe.inputs import InputError
from ..universe.output import OutputError
from . import calendar, dice, engine, events, orders, rules
from .book import Booker, BookError, Books, check, replay
from .prices import PriceBook
from .universe import Universe, covered_list, newest_path
from .universe import load as load_universe


def _mode(args: argparse.Namespace) -> str:
    return paths.check_mode(paths.LIVE if args.live else paths.PILOT)


def _session_day(args: argparse.Namespace) -> date:
    return date.fromisoformat(args.day) if args.day else utcnow().astimezone(calendar.AMSTERDAM).date()


def _cutoff(args: argparse.Namespace) -> datetime:
    return datetime.fromisoformat(args.cutoff.replace("Z", "+00:00")) if getattr(args, "cutoff", None) else utcnow()


def _universe(args: argparse.Namespace) -> Universe:
    folder = paths.data_dir() / "universe"
    return load_universe(Path(args.universe) if getattr(args, "universe", None) else newest_path(folder))


def fill_rule(mode: str) -> str:
    return records.FILL_RULE if mode == paths.LIVE else records.FILL_RULE_PILOT


def book_step(
    log: Log, writer: Writer, mode: str, cutoff: datetime, universe: Universe, upto: date | None = None
) -> tuple[Booker, dice.DiceBooks]:
    """Step 2 of the daily round: book what happened since the last session, the Dice funds included."""
    root = paths.mode_root(mode)
    prices = PriceBook(paths.data_dir() / "prices", cutoff)
    dice_books = dice.DiceBooks.load(log, root / "books" / "dice")
    booker = Booker(
        log,
        writer,
        prices,
        universe,
        events.load(root / "events"),
        covered_list(root / "reports") & universe.buyable(),
        on_day=dice_books.book_day,
    )
    booker.run(upto)
    return booker, dice_books


def monthly_draw(
    writer: Writer,
    books: Books,
    dice_books: dice.DiceBooks,
    prices: PriceBook,
    universe: Universe,
    covered: set[int],
    session_day: date,
    mode: str,
    cutoff: datetime,
) -> list[str]:
    """The first session of a month: the Rules fund and the Dice funds are drawn anew. Returns what was done."""
    month = f"{session_day:%Y-%m}"
    done: list[str] = []
    stored = prices.days()

    def price_of(ticker: str) -> Fraction | None:
        found = prices.last_close(ticker, stored[-1]) if stored else None
        return found[0] if found else None

    info = {cik: (c.ticker, c.name) for cik, c in universe.companies.items()}
    if "rules" in books.funds:
        fund = books.funds["rules"]
        inputs = rules.load_inputs(paths.mode_root(mode) / "rules")
        chosen = rules.select(inputs[1], covered, session_day) if inputs else []
        body: dict[str, object] = {"month": month, "chosen": chosen, "rule_version": rules.RULE_VERSION}
        if inputs is None:
            body["why_empty"] = rules.NO_INPUTS
        draw = writer.add("rules_draw", body)
        value, _ = engine.fund_value(fund, price_of)
        wanted = [
            orders.Proposal(p.action, p.cik, p.name, p.ticker, p.size, {"draw": draw.seq})
            for p in orders.rebalance(fund, chosen, info, value, price_of)
        ]
        verdicts = orders.check(fund, value, price_of, wanted, buyable=universe.buyable(), covered=covered, risky=set())
        orders.place(writer, fund, session_day, verdicts, fill_rule=fill_rule(mode), cutoff=iso(cutoff))
        done.append(f"rules: {len(chosen)} companies chosen, {len(wanted)} orders")
    if dice_books.funds and month not in dice_books.months:
        body = dice_books.plan_draw(month, session_day, covered, info, price_of)
        writer.add("dice_draw", body)
        done.append(f"dice: drawn for {month} from {len(covered)} covered companies")
    return done


def cmd_start(args: argparse.Namespace) -> int:
    mode = _mode(args)
    names = [n.strip() for n in args.funds.split(",") if n.strip()]
    unknown = [n for n in names if n not in records.FUNDS]
    if unknown or not names:
        print(f"NOT DONE: the funds are {', '.join(records.FUNDS)}")
        return 1
    log = Log.for_mode(mode)
    day = _session_day(args)
    with log.writer(day) as writer:
        writer.add("funds_start", {"day": day.isoformat(), "funds": names, "cash_cents": engine.START_CASH_CENTS})
        if dice.NAME in names:
            writer.add(
                "dice_seed",
                {
                    "seed": dice.new_seed(),
                    "rule_version": dice.RULE_VERSION,
                    "funds": dice.FUNDS,
                    "per_fund": dice.PER_FUND,
                },
            )
    print(f"started ({mode}): {', '.join(names)}, each with $1,000,000 of paper money, on {day}")
    return 0


def cmd_book(args: argparse.Namespace) -> int:
    mode = _mode(args)
    log = Log.for_mode(mode)
    with log.writer(_session_day(args)) as writer:
        booker, _ = book_step(log, writer, mode, _cutoff(args), _universe(args))
    report = booker.report
    print(f"booked: {len(report.days)} trading day(s), {report.fills} fill(s), {report.closed} order(s) closed, "
          f"{report.events} company event(s)")  # fmt: skip
    if report.days:
        print(f"days: {report.days[0]} to {report.days[-1]}")
    if report.waiting_for:
        print(f"waiting: the price file of {report.waiting_for} is not stored yet; booking stops there")
    for note in report.notes:
        print(f"note: {note}")
    return 0


def cmd_draw(args: argparse.Namespace) -> int:
    mode = _mode(args)
    log = Log.for_mode(mode)
    root = paths.mode_root(mode)
    universe = _universe(args)
    cutoff = _cutoff(args)
    day = _session_day(args)
    prices = PriceBook(paths.data_dir() / "prices", cutoff)
    covered = covered_list(root / "reports") & universe.buyable()
    with log.writer(day) as writer:
        books = replay(log)
        dice_books = dice.DiceBooks.load(log, root / "books" / "dice")
        for line in monthly_draw(writer, books, dice_books, prices, universe, covered, day, mode, cutoff):
            print(line)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    mode = _mode(args)
    log = Log.for_mode(mode)
    differences = check(log, PriceBook(paths.data_dir() / "prices"))
    books = replay(log)
    dice.DiceBooks.load(log, paths.mode_root(mode) / "books" / "dice")  # raises when a Dice file is not as logged
    for line in differences:
        print(f"PROBLEM: {line}")
    if differences:
        print("NOT OK: the books do not add up")
        return 1
    print(f"ok: {len(books.booked)} booked day(s) recomputed from the log and the saved prices, equal to the cent")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    mode = _mode(args)
    books = replay(Log.for_mode(mode))
    print("PRIVATE: what follows comes from prices. For your own screen only; never paste it anywhere.")
    if not books.started:
        print("no fund has been started yet")
        return 0
    last = books.booked[-1] if books.booked else None
    print(f"last booked day: {last or 'none yet'}")
    for name, fund in books.funds.items():
        stored = books.values[last]["funds"].get(name) if last else None
        value = f"${stored['value_cents'] / 100:,.2f}" if stored else "not valued yet"
        print(f"{name}: value {value}, cash ${fund.cash / 100:,.2f}, {len(fund.positions)} position(s), "
              f"{len(fund.orders)} order(s) waiting")  # fmt: skip
        for position in sorted(fund.positions.values(), key=lambda p: p.name):
            print(f"    {position.ticker:<6} {position.shares:>8} shares  {position.name}")
        for order in sorted(fund.orders.values(), key=lambda o: o.ref):
            size = canon.format_pct(order.size) if order.size is not None else "all"
            due = order.due or "not known yet"
            print(f"    waiting: {order.side} {size} {order.ticker} (record {order.ref}, fill day {due})")
    return 0


def cmd_event(args: argparse.Namespace) -> int:
    mode = _mode(args)
    event = events.add(
        paths.mode_root(mode) / "events",
        iso(utcnow()),
        cik=args.cik,
        name=args.name,
        kind=args.kind,
        effective=date.fromisoformat(args.effective),
        filing=args.filing,
        cash_per_share=args.cash_per_share,
        ratio=args.ratio,
        buyer_cik=args.buyer_cik,
        buyer_ticker=args.buyer_ticker or "",
        buyer_name=args.buyer_name or "",
    )
    print(f"added: {event.kind} of company {event.cik}, effective {event.effective}; booked in the next round")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bobby-funds", description="The paper funds' books. Paper money only.")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, day: bool = True) -> None:
        p.add_argument("--live", action="store_true", help="the real funds instead of the pilot (after the owner's go)")
        if day:
            p.add_argument("--day", metavar="YYYY-MM-DD", help="the session day (default: today in Amsterdam)")

    p_start = sub.add_parser("start", help="start funds with $1,000,000 of paper money each")
    p_start.add_argument("--funds", required=True, help="for example: careful,rules,dice")
    common(p_start)
    p_start.set_defaults(func=cmd_start)
    p_book = sub.add_parser("book", help="book fills, company events and values since the last booked day")
    common(p_book)
    p_book.add_argument("--cutoff", metavar="TIME", help="only use price files stored before this time")
    p_book.add_argument("--universe", metavar="FILE", help="the universe file (default: the newest)")
    p_book.set_defaults(func=cmd_book)
    p_draw = sub.add_parser("draw", help="the monthly draw of the Rules and Dice funds")
    common(p_draw)
    p_draw.add_argument("--cutoff", metavar="TIME")
    p_draw.add_argument("--universe", metavar="FILE")
    p_draw.set_defaults(func=cmd_draw)
    p_check = sub.add_parser("check", help="recompute every stored value from the log and the saved prices")
    common(p_check, day=False)
    p_check.set_defaults(func=cmd_check)
    p_status = sub.add_parser("status", help="positions, cash and waiting orders (private)")
    common(p_status, day=False)
    p_status.set_defaults(func=cmd_status)
    p_event = sub.add_parser("event", help="add a takeover to the table of company events, from its SEC filing")
    common(p_event, day=False)
    p_event.add_argument("--cik", type=int, required=True)
    p_event.add_argument("--name", required=True)
    p_event.add_argument("--kind", required=True, help=f"one of: {', '.join(events.BUILT)}")
    p_event.add_argument("--effective", required=True, metavar="YYYY-MM-DD", help="the day the deal completes")
    p_event.add_argument("--filing", required=True, metavar="LINK")
    p_event.add_argument("--cash-per-share", metavar="12.50")
    p_event.add_argument("--ratio", metavar="0.4321", help="buyer's shares per share")
    p_event.add_argument("--buyer-cik", type=int)
    p_event.add_argument("--buyer-ticker")
    p_event.add_argument("--buyer-name")
    p_event.set_defaults(func=cmd_event)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (
        LogError, BookError, dice.DiceError, rules.RulesError, events.EventError, calendar.CalendarError,
        InputError, OutputError, ArchiveError, paths.ModeError, canon.CanonError, ValueError,
    ) as exc:  # fmt: skip
        print(f"NOT DONE: {exc}")
        return 1
    except OSError as exc:
        print(f"NOT DONE: a file could not be read or written ({type(exc).__name__})")
        return 1


if __name__ == "__main__":
    sys.exit(main())

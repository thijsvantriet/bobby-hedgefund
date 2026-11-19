"""From what a fund wants to the orders that are logged: the risk limits, enforced in code (docs/SPEC.md section 4;
docs/decisions/0005, point 2). The limits are checked when the decision is made, against the fund as it is then,
with orders that are still waiting counted as if they were filled. Every decision is logged as it was made; an
order that breaks a limit is cut down or refused, and that is logged too.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from fractions import Fraction
from typing import Any

from ..log import canon
from ..log.records import VALUE_LIMIT
from ..log.seal import Sealed
from ..log.store import Entry, Writer
from . import engine
from .engine import Fund, Order

MAX_POSITIONS = 25
MAKE_OR_BREAK_DAYS = 30
# Per fund: the most one stock may weigh, and the most positions with a make-or-break result within 30 days.
LIMITS: dict[str, tuple[Fraction, int | None]] = {
    "careful": (Fraction(5, 100), 3),
    "bold": (Fraction(8, 100), 8),
    "debate": (Fraction(5, 100), 3),
    "rules": (Fraction(5, 100), None),
    "dice": (Fraction(5, 100), None),
}


@dataclass(frozen=True)
class Proposal:
    """One thing a fund wants to do. `more`: what goes into the decision record besides the order itself (the
    thesis, what the agent saw, the model details)."""

    action: str  # buy, add, reduce, sell or nothing
    cik: int = 0
    name: str = ""
    ticker: str = ""
    size: Fraction | None = None  # the size of the trade as a share of the fund; None: sell the whole position
    more: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    proposal: Proposal
    outcome: str  # "ok", "reduced" or "refused"
    limit: str = ""
    allowed: Fraction | None = None
    basis: dict[str, Any] = field(default_factory=dict)  # the numbers behind it: from prices, so private
    from_prices: bool = False  # the size that was allowed follows from what a position is worth today


def make_or_break(entries: list[Entry], today: date) -> set[int]:
    """The companies with a make-or-break result expected within 30 days: a forecast that says so, with its date
    inside that window, and no outcome yet."""
    resolved = {e.record["ref"] for e in entries if e.kind == "outcome"}
    horizon = today + timedelta(days=MAKE_OR_BREAK_DAYS)
    return {
        e.record["company"]["cik"]
        for e in entries
        if e.kind == "forecast"
        and e.record["make_or_break"]
        and e.seq not in resolved
        and today <= date.fromisoformat(e.record["by_date"]) <= horizon
    }


def check(
    fund: Fund,
    value: int,
    price_of: Callable[[str], Fraction | None],
    proposals: list[Proposal],
    *,
    buyable: set[int],
    covered: set[int],
    risky: set[int],
) -> list[Verdict]:
    """Hold every proposal against the limits, sells first. `value`: the fund's value in cents at the last
    closing prices; `risky`: the companies with a make-or-break result within 30 days."""
    per_stock, risky_limit = LIMITS[fund.name]
    weight: dict[int, Fraction] = {}
    priced: set[int] = set()  # companies whose weight comes from today's prices
    if value > 0:
        for cik, position in fund.positions.items():
            price = price_of(position.ticker)
            weight[cik] = (
                Fraction(engine.to_cents(price * position.shares), value) if price is not None else Fraction(0)
            )
            priced.add(cik)
    held = set(fund.positions)
    # A new decision about a company replaces an order for it that is still waiting (record 0005, point 2.8), so
    # that waiting order is left out here. All other waiting orders count as if they were filled.
    replaced = {p.cik for p in proposals if p.action != "nothing"}

    def count_waiting(order: Order) -> None:
        if order.side == "buy":
            weight[order.cik] = weight.get(order.cik, Fraction(0)) + (order.size or 0)
            held.add(order.cik)
        elif order.size is None:
            weight[order.cik] = Fraction(0)
            held.discard(order.cik)
        else:
            weight[order.cik] = max(Fraction(0), weight.get(order.cik, Fraction(0)) - order.size)

    for order in fund.orders.values():
        if order.cik not in replaced:
            count_waiting(order)
    braked = fund.peak is not None and value <= engine.BRAKE * fund.peak
    seen: set[int] = set()

    def judge(p: Proposal) -> Verdict:
        basis = {
            "fund_value_cents": value,
            "weight_before": canon.format_pct(weight.get(p.cik, Fraction(0))),
            "positions": len(held),
        }
        if p.cik in seen:  # a buy and a sale of one company in one round would depend on their order
            return Verdict(p, "refused", "one order per company a round", basis=basis)
        seen.add(p.cik)
        if p.action in ("reduce", "sell"):
            if p.cik not in held:
                return Verdict(p, "refused", "nothing to sell", basis=basis)
            if p.action == "reduce" and (p.size is None or p.size < engine.MIN_TRADE):
                return Verdict(p, "refused", "below the smallest trade", basis=basis)
            if p.size is None:
                weight[p.cik] = Fraction(0)
                held.discard(p.cik)
            else:
                weight[p.cik] = max(Fraction(0), weight.get(p.cik, Fraction(0)) - p.size)
            return Verdict(p, "ok", allowed=p.size, basis=basis)
        if p.size is None:
            return Verdict(p, "refused", "below the smallest trade", basis=basis)
        if braked:
            return Verdict(p, "refused", VALUE_LIMIT, basis={**basis, "limit": "brake"})
        if p.cik not in buyable:
            return Verdict(p, "refused", "not in the universe", basis=basis)
        if p.cik not in covered:
            return Verdict(p, "refused", "not on the covered list", basis=basis)
        new = p.cik not in held
        if new and len(held) >= MAX_POSITIONS:
            return Verdict(p, "refused", "25 positions", basis=basis)
        if new and risky_limit is not None and p.cik in risky and len(held & risky) >= risky_limit:
            return Verdict(p, "refused", "make-or-break limit", basis=basis)
        if p.size < engine.MIN_TRADE:
            return Verdict(p, "refused", "below the smallest trade", basis=basis)
        room = per_stock - weight.get(p.cik, Fraction(0))
        # Rounded down to a hundredth of a percent, as the log writes it: a limit is never passed by rounding.
        allowed = canon.pct_fraction(canon.format_pct(max(Fraction(0), min(p.size, room))))
        if allowed < engine.MIN_TRADE:
            return Verdict(p, "refused", "per-stock limit", basis=basis)
        weight[p.cik] = weight.get(p.cik, Fraction(0)) + allowed
        held.add(p.cik)
        if allowed < p.size:
            return Verdict(p, "reduced", "per-stock limit", allowed, basis, from_prices=p.cik in priced)
        return Verdict(p, "ok", allowed=allowed, basis=basis)

    order = sorted(range(len(proposals)), key=lambda i: (proposals[i].action not in ("reduce", "sell"), i))
    verdicts: dict[int, Verdict] = {}
    for i in order:
        p = proposals[i]
        verdicts[i] = Verdict(p, "ok") if p.action == "nothing" else judge(p)
        if verdicts[i].outcome == "refused":  # the waiting order it would have replaced stays, and counts again
            for waiting in fund.orders.values():
                if waiting.cik == p.cik and p.cik in replaced:
                    count_waiting(waiting)
            replaced.discard(p.cik)
    return [verdicts[i] for i in range(len(proposals))]


def place(
    writer: Writer,
    fund: Fund,
    session_day: date,
    verdicts: list[Verdict],
    *,
    fill_rule: str,
    cutoff: str,
) -> list[Entry]:
    """Write the day's decisions of one fund: each decision as it was made, then what the limits did to it, then
    the end of an earlier order that a new decision replaces. Keeps `fund` in step. Returns the records written."""
    written: list[Entry] = []
    for verdict in verdicts:
        p = verdict.proposal
        body: dict[str, Any] = {
            "fund": fund.name,
            "action": p.action,
            "fill_rule": fill_rule,
            "cutoff": cutoff,
            **p.more,
        }
        company = {"cik": p.cik, "name": p.name, "ticker": p.ticker} if p.ticker else {"cik": p.cik, "name": p.name}
        if p.action != "nothing":
            body["company"] = company
            body["size_pct"] = canon.format_pct(p.size) if p.size is not None else None
        decision = writer.add("decision", body)
        written.append(decision)
        if p.action == "nothing":
            continue
        asked = canon.format_pct(p.size) if p.size is not None else None
        common = {"ref": decision.seq, "fund": fund.name, "company": company}
        if verdict.outcome == "refused":
            written.append(
                writer.add(
                    "order_refused",
                    {**common, "limit": verdict.limit, "asked_pct": asked, "basis": Sealed(verdict.basis)},
                )
            )
            continue
        if verdict.outcome == "reduced":
            assert verdict.allowed is not None and asked is not None
            written.append(
                writer.add(
                    "order_reduced",
                    {
                        **common,
                        "limit": verdict.limit,
                        "asked_pct": asked,
                        "allowed_pct": Sealed(canon.format_pct(verdict.allowed))
                        if verdict.from_prices
                        else canon.format_pct(verdict.allowed),
                        "basis": Sealed(verdict.basis),
                    },
                )
            )
        for old in [o for o in fund.orders.values() if o.cik == p.cik]:
            # A new decision about the same company replaces an order that is still waiting (record 0005, 2.8).
            written.append(
                writer.add(
                    "order_closed",
                    {
                        **common,
                        "ref": old.ref,
                        "by": decision.seq,
                        "outcome": "replaced",
                        "day": session_day.isoformat(),
                    },
                )
            )
            del fund.orders[old.ref]
        side = "buy" if p.action in ("buy", "add") else "sell"
        fund.orders[decision.seq] = Order(
            decision.seq, fund.name, p.cik, p.ticker, p.name, side, verdict.allowed, session_day
        )
    return written


EQUAL_PART = Fraction(1, 20)  # a fund of 20 companies in equal parts holds 5% of each


def rebalance(
    fund: Fund,
    targets: list[int],
    info: dict[int, tuple[str, str]],
    value: int,
    price_of: Callable[[str], Fraction | None],
) -> list[Proposal]:
    """The orders of a fund without AI after a draw (docs/decisions/0005, point 1): companies that are no longer
    drawn are sold whole, new ones are bought at their equal part, and a company that stays is brought back to
    its equal part only when that takes a trade of 0.5% of the fund or more. `info`: SEC number -> (ticker, name)."""
    out: list[Proposal] = []
    wanted = set(targets)
    for cik in sorted(fund.positions):
        if cik not in wanted:
            position = fund.positions[cik]
            out.append(Proposal("sell", cik, position.name, position.ticker))
    for cik in sorted(wanted):
        ticker, name = info[cik]
        position = fund.positions.get(cik)
        if position is None:
            out.append(Proposal("buy", cik, name, ticker, EQUAL_PART))
            continue
        price = price_of(position.ticker)
        if price is None or value <= 0:
            continue
        gap = EQUAL_PART - Fraction(engine.to_cents(price * position.shares), value)
        size = canon.pct_fraction(canon.format_pct(abs(gap)))
        if size >= engine.MIN_TRADE:
            out.append(Proposal("add" if gap > 0 else "reduce", cik, position.name, position.ticker, size))
    return out

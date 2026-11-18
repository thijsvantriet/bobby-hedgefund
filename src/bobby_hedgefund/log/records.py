"""The kinds of record in the decision log and the fixed form of each (docs/SPEC.md section 5; records 0004,
0005 and 0009). A record that is not in its form is not written.

The same forms are used by everything that makes a record: the fund books, the session scripts and the agents'
answers. The fields that say what was decided (fund, company, action, size, fill rule) can never be sealed.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from . import canon
from .seal import SEAL_WHY, Sealed, is_sealed_form

Check = Callable[[Any, str], None]

AI_FUNDS = ("careful", "bold", "debate")
FUNDS = (*AI_FUNDS, "rules", "dice")
INDEX_FUNDS = ("XBI", "IBB", "URTH")
ACTIONS = ("buy", "add", "reduce", "sell", "nothing")
# The one sentence of docs/decisions/0003, point 4. A decision states the rule; the day is in the fill record.
FILL_RULE = (
    "Filled at the opening price of the first US trading day whose opening is at least 30 minutes after GitHub "
    "received the publication; for a session started at or after 14:00 Amsterdam time, never the day of the "
    "session itself."
)
FILL_RULE_PILOT = (
    "Pilot: as the real rule, with the time of the local commit standing in for the time GitHub received the "
    "publication. Pilot trades do not count."
)
EVENT_KINDS = ("trial result", "fda decision", "other regulator decision", "company event", "other")
LIMITS = (
    "per-stock limit",
    "25 positions",
    "make-or-break limit",
    "not on the covered list",
    "not in the universe",
    "brake",
    "nothing to sell",
    "below the smallest trade",
)
CLOSED = ("lapsed", "replaced", "cancelled by the brake", "too small", "nothing to sell", "company left")
COMPANY_EVENTS = ("split", "cash takeover", "share takeover", "cash dividend", "new ticker or name")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class RecordError(Exception):
    pass


def _fail(where: str, message: str) -> None:
    raise RecordError(f"{where}: {message}")


def text(longest: int = 6000, *, empty: bool = False) -> Check:
    def check(value: Any, where: str) -> None:
        if not isinstance(value, str):
            _fail(where, "must be text")
        elif not empty and not value.strip():
            _fail(where, "is empty")
        elif len(value) > longest:
            _fail(where, f"is longer than {longest} characters")

    return check


def whole(lowest: int = 0) -> Check:
    def check(value: Any, where: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(where, "must be a whole number")
        elif value < lowest:
            _fail(where, f"must be at least {lowest}")

    return check


def yes_no(value: Any, where: str) -> None:
    if not isinstance(value, bool):
        _fail(where, "must be true or false")


def pct(value: Any, where: str) -> None:
    if not canon.is_pct(value):
        _fail(where, "must be a percentage as text, such as '3%' or '2.5%'")


def probability(value: Any, where: str) -> None:
    pct(value, where)
    if canon.pct_fraction(value) > 1:
        _fail(where, "a probability is at most 100%")


def day(value: Any, where: str) -> None:
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError:
        _fail(where, "must be a day as YYYY-MM-DD")


def month(value: Any, where: str) -> None:
    if not isinstance(value, str) or not _MONTH.match(value):
        _fail(where, "must be a month as YYYY-MM")


def moment(value: Any, where: str) -> None:
    try:
        if not isinstance(value, str) or not _TIME.match(value):
            raise ValueError
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        _fail(where, "must be a time as YYYY-MM-DDTHH:MM:SSZ")


def hex64(value: Any, where: str) -> None:
    if not isinstance(value, str) or not _HEX64.match(value):
        _fail(where, "must be a fingerprint (64 characters, 0-9 and a-f)")


def one_of(*allowed: str) -> Check:
    def check(value: Any, where: str) -> None:
        if value not in allowed:
            _fail(where, f"must be one of: {', '.join(allowed)}")

    return check


def exactly(wanted: tuple[str, ...]) -> Check:
    def check(value: Any, where: str) -> None:
        if value not in wanted:
            _fail(where, "is not the fixed sentence")

    return check


def link(value: Any, where: str) -> None:
    """A link to a public page: https, no spaces, and nothing after a question mark (that is where keys sit)."""
    if not isinstance(value, str) or not re.match(r"^https://[^\s?#]{4,480}$", value):
        _fail(where, "must be a plain https link, without a question mark")


def maybe(inner: Check) -> Check:
    def check(value: Any, where: str) -> None:
        if value is not None:
            inner(value, where)

    return check


def many(inner: Check, lowest: int = 0, highest: int = 2000) -> Check:
    def check(value: Any, where: str) -> None:
        if not isinstance(value, list):
            _fail(where, "must be a list")
            return
        if not lowest <= len(value) <= highest:
            _fail(where, f"must have {lowest} to {highest} entries")
        for i, item in enumerate(value):
            inner(item, f"{where}/{i}")

    return check


def fields(required: dict[str, Check], optional: dict[str, Check] | None = None) -> Check:
    extra = optional or {}

    def check(value: Any, where: str) -> None:
        if not isinstance(value, dict) or is_sealed_form(value):
            _fail(where, "must be a set of named fields")
            return
        for name, inner in required.items():
            if name not in value:
                _fail(where, f"the field '{name}' is missing")
            inner(value[name], f"{where}/{name}")
        for name, item in value.items():
            if name in required:
                continue
            if name not in extra:
                _fail(where, f"unknown field '{name}'")
            extra[name](item, f"{where}/{name}")

    return check


def sealed(*why: str) -> Check:
    """The field must be sealed: a `Sealed` value on the way in, its public form in a record that is read back."""
    allowed = why or SEAL_WHY

    def check(value: Any, where: str) -> None:
        if isinstance(value, Sealed):
            if value.why not in allowed:
                _fail(where, f"sealed for the wrong reason ({value.why})")
        elif is_sealed_form(value):
            if value["why"] not in allowed:
                _fail(where, f"sealed for the wrong reason ({value['why']})")
        else:
            _fail(where, "must be sealed: this content may not be public")

    return check


def sealable(inner: Check) -> Check:
    def check(value: Any, where: str) -> None:
        if not isinstance(value, Sealed) and not is_sealed_form(value):
            inner(value, where)

    return check


# ---------------------------------------------------------------- shared forms

COMPANY = fields({"cik": whole(1), "name": text(200)}, {"ticker": text(12)})
SOURCE = fields(
    {"n": whole(1), "source": text(200), "summary": text(600)},
    {"date": maybe(day), "link": maybe(link)},
)
AGENT = fields(
    {
        "role": text(60),
        "agent_file_sha256": hex64,
        "task_sha256": hex64,
        "model": text(80),
        "effort": text(20),
        "claude_code": text(40),
    },
    {"file_model": text(80), "file_effort": text(20), "substituted": yes_no, "run": whole(1), "stand_in": yes_no},
)
# A number in a thesis is filled in by a script, which says where it comes from. One that comes from prices must
# be sealed; a forgotten seal is refused (docs/decisions/0007, point 6).
NUMBER_BASIS = ("filing", "trial registry", "our count", "price")
NUMBER = fields(
    {"label": text(200), "value": sealable(text(200)), "basis": one_of(*NUMBER_BASIS)}, {"source": maybe(whole(1))}
)
THESIS = fields(
    {
        "claim": text(1500),
        "edge": text(2500),  # what we believe that others do not, and why
        "catalyst": text(1000),
        "probability": probability,
        "numbers": many(NUMBER, 0, 40),
        "risks": text(2500),
        "sell_if": text(1500),
    },
    {"catalyst_date": maybe(day)},
)
RUN = fields(
    {"run": whole(1), "readable": yes_no},
    {"action": one_of(*ACTIONS), "size_pct": maybe(pct), "model": text(80)},
)
CODE = fields({"commit": text(64), "claude_code": text(40)}, {"branch": text(200)})
COMMON = {
    "dry_run": text(300),
    "note": text(2000),
    "removed": many(sealed("quote", "money", "price", "secret", "other")),
}


def _kind(required: dict[str, Check], optional: dict[str, Check] | None = None) -> Check:
    return fields(required, {**COMMON, **(optional or {})})


KINDS: dict[str, Check] = {
    "funds_start": _kind({"day": day, "funds": many(one_of(*FUNDS), 1, 5), "cash_cents": whole(1)}),
    "session_start": _kind(
        {
            "session_day": day,
            "start_time": moment,
            "cutoff": moment,
            "universe": fields({"file": text(200), "sha256": hex64}),
            "inputs_sha256": hex64,
            "code": CODE,
        },
        {
            "previous_publication": fields(
                {"session_day": day, "received": moment, "source": one_of("github", "local commit (pilot)")}
            ),
            "previous_conversation": fields({"session_day": day, "sha256": hex64}),
            "usage": fields(
                {"session_day": day},
                {"minutes": whole(0), "five_hour_pct": maybe(pct), "weekly_pct": maybe(pct), "agent_runs": whole(0)},
            ),
            "skipped_working_days": whole(0),
        },
    ),
    "forecast": _kind(
        {
            "company": COMPANY,
            "role": text(60),
            "event": text(600),
            "event_kind": one_of(*EVENT_KINDS),
            "by_date": day,
            "probability": probability,
            "make_or_break": yes_no,
            "sources": many(SOURCE, 0, 60),
            "agent": AGENT,
            "cutoff": moment,
        },
        {"reasoning": text(2500), "base_rate": maybe(probability)},
    ),
    "decision": _kind(
        {
            "fund": one_of(*FUNDS),
            "action": one_of(*ACTIONS),
            "fill_rule": exactly((FILL_RULE, FILL_RULE_PILOT)),
            "cutoff": moment,
        },
        {
            "company": COMPANY,
            "size_pct": maybe(
                pct
            ),  # the size of the trade as a share of the fund; nothing for selling a whole position
            "thesis": THESIS,
            "reason": text(2500),
            "saw": many(SOURCE, 0, 80),
            "agents": many(AGENT, 0, 40),
            "runs": many(RUN, 0, 3),
            "agreed": yes_no,
            "from_run": whole(1),
            "code": CODE,
            "draw": whole(1),  # Rules and Dice: the record of the draw this order follows from
        },
    ),
    "no_decision": _kind(
        {"fund": one_of(*FUNDS), "reason": one_of("out of time", "no readable answer", "model not available")},
        {"runs": many(RUN, 0, 3), "agents": many(AGENT, 0, 40)},
    ),
    "order_refused": _kind(
        {
            "ref": whole(1),
            "fund": one_of(*FUNDS),
            "company": COMPANY,
            "limit": one_of(*LIMITS),
            "asked_pct": maybe(pct),
        },
        {"basis": sealed("price")},
    ),
    "order_reduced": _kind(
        {
            "ref": whole(1),
            "fund": one_of(*FUNDS),
            "company": COMPANY,
            "limit": one_of(*LIMITS),
            "asked_pct": pct,
            "allowed_pct": pct,
        },
        {"basis": sealed("price")},
    ),
    "fill": _kind(
        {
            "ref": whole(1),
            "fund": one_of(*FUNDS),
            "company": COMPANY,
            "side": one_of("buy", "sell"),
            "fill_day": day,
            "rule_version": text(40),
            "details": sealed("price"),  # shares, price, amount, cost, the price file used
        },
        {"cut_for_cash": yes_no, "waited_days": whole(0)},
    ),
    "order_closed": _kind(
        {"ref": whole(1), "fund": one_of(*FUNDS), "company": COMPANY, "outcome": one_of(*CLOSED), "day": day},
        {"by": whole(1), "basis": sealed("price")},
    ),
    "outcome": _kind(
        {
            "ref": whole(1),  # the forecast
            "result": one_of("yes", "no", "void"),
            "resolved_on": day,
            "summary": text(1000),
            "sources": many(SOURCE, 0, 20),
        },
        {"agent": AGENT},
    ),
    "correction": _kind({"ref": whole(1), "text": text(3000)}),
    "restart": _kind({"session_day": day, "first_start": moment, "reason": text(600)}),
    "stop_file": _kind({"state": one_of("on", "off"), "noticed": moment}),
    "refusal": _kind({"when": moment, "reason": text(600)}),
    "company_event": _kind(
        {"company": COMPANY, "event": one_of(*COMPANY_EVENTS), "effective": day, "checked_against_filing": yes_no},
        {"filing": maybe(link), "terms": sealed("price", "other"), "booked": sealed("price")},
    ),
    "dice_seed": _kind({"seed": hex64, "rule_version": text(40), "funds": whole(1), "per_fund": whole(1)}),
    "dice_draw": _kind(
        {"month": month, "covered": many(whole(1), 0, 2000), "rule_version": text(40), "seed_ref": whole(1)},
        {"orders": sealed("price")},  # the private file with the orders of the 1,000 funds, and its fingerprint
    ),
    # One per trading day that was booked: the values of the funds and index funds at the close, all sealed.
    "day_booked": _kind({"day": day, "rule_version": text(40), "values": sealed("price")}),
    "rules_draw": _kind(
        {"month": month, "chosen": many(whole(1), 0, 20), "rule_version": text(40)},
        {"why_empty": text(600)},
    ),
}


def _decision_rules(body: dict[str, Any]) -> None:
    action = body["action"]
    has_company = body.get("company") is not None
    size = body.get("size_pct")
    if action == "nothing":
        if has_company or size is not None or "thesis" in body:
            _fail("decision", "'nothing' names no company, no size and no thesis")
        return
    if not has_company:
        _fail("decision", f"'{action}' must name a company")
    if action in ("buy", "add", "reduce") and size is None:
        _fail("decision", f"'{action}' must state its size as a percentage of the fund")
    if size is not None and canon.pct_fraction(size) <= 0:
        _fail("decision", "a size of 0% is not an order")
    if body["fund"] in AI_FUNDS:
        if action in ("buy", "add") and "thesis" not in body:
            _fail("decision", f"'{action}' must carry a thesis")
        if action in ("reduce", "sell") and "reason" not in body and "thesis" not in body:
            _fail("decision", f"'{action}' must say why")

    for i, number in enumerate((body.get("thesis") or {}).get("numbers") or []):
        if (
            number["basis"] == "price"
            and not isinstance(number["value"], Sealed)
            and not is_sealed_form(number["value"])
        ):
            _fail(f"decision/thesis/numbers/{i}", "a number that comes from prices must be sealed")


RULES: dict[str, Callable[[dict[str, Any]], None]] = {"decision": _decision_rules}

# A field that points to an earlier record, and the kinds that record may have (None: any kind).
REFERENCES: dict[str, tuple[tuple[str, tuple[str, ...] | None], ...]] = {
    "outcome": (("ref", ("forecast",)),),
    "fill": (("ref", ("decision",)),),
    "order_refused": (("ref", ("decision",)),),
    "order_reduced": (("ref", ("decision",)),),
    "order_closed": (("ref", ("decision",)), ("by", ("decision",))),
    "correction": (("ref", None),),
    "decision": (("draw", ("dice_draw", "rules_draw")),),
    "dice_draw": (("seed_ref", ("dice_seed",)),),
}


def check_references(kind: str, body: dict[str, Any], kinds: dict[int, str]) -> None:
    """Every pointer to an earlier record must point to a record that exists and is of the right kind. `kinds`:
    the kind of every record written so far, by its number. A wrong pointer could never be put right afterwards."""
    for name, allowed in REFERENCES.get(kind, ()):
        ref = body.get(name)
        if ref is None:
            continue
        found = kinds.get(ref)
        if found is None:
            _fail(f"{kind}/{name}", f"points to record {ref}, which does not exist (yet)")
        elif allowed is not None and found not in allowed:
            _fail(f"{kind}/{name}", f"points to record {ref}, which is a {found}, not a {' or '.join(allowed)}")


def validate(kind: str, body: Any) -> None:
    """Check the fields a writer hands in (everything but the fields the log adds itself)."""
    if kind not in KINDS:
        raise RecordError(f"unknown kind of record: {kind!r}")
    KINDS[kind](body, kind)
    if kind in RULES:
        RULES[kind](body)


def validate_public(record: dict[str, Any]) -> None:
    """Check a record as it stands in the log."""
    kind = record.get("kind")
    body = {key: value for key, value in record.items() if key not in ("v", "seq", "kind", "time", "mode", "prev")}
    if not isinstance(kind, str):
        raise RecordError("a record without a kind")
    moment(record.get("time"), "time")
    validate(kind, body)

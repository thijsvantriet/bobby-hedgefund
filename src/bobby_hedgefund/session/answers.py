"""Reading an agent's answer (docs/decisions/0009, points 1 and 3). An answer ends with one block of JSON in a
fixed form. A script takes it from the agent's own record and checks it here; an answer that is not in its form
is thrown away: nothing is repaired or retyped.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..log import records
from ..log.records import RecordError, day, fields, many, maybe, one_of, pct, probability, text, whole, yes_no

_BLOCK = re.compile(r"```json[ \t]*\n(.*?)\n```", re.DOTALL)
SOURCE = fields({"n": whole(1), "summary": text(600)})
LACKED = many(text(600), 0, 30)
NUMBERS = many(whole(1), 0, 60)

FORECAST = fields(
    {
        "event": text(600),
        "event_kind": one_of(*records.EVENT_KINDS),
        "by_date": day,
        "probability": probability,
        "make_or_break": yes_no,
        "reasoning": text(2500),
        "sources": NUMBERS,
    }
)
RESOLVED = fields(
    {
        "forecast": whole(1),
        "result": one_of("yes", "no", "void"),
        "resolved_on": day,
        "summary": text(1000),
        "sources": NUMBERS,
    }
)
THESIS = fields(
    {
        "claim": text(1500),
        "edge": text(2500),
        "catalyst": text(1000),
        "probability": probability,
        "risks": text(2500),
        "sell_if": text(1500),
    },
    {"catalyst_date": maybe(day)},
)
DECISION = fields(
    {"cik": whole(1), "action": one_of("buy", "add", "reduce", "sell"), "sources": many(SOURCE, 0, 80)},
    {"size_pct": maybe(pct), "thesis": THESIS, "reason": text(2500)},
)
THREE = one_of("yes", "no", "unclear")

FORMS = {
    "screening": fields(
        {
            "companies": many(
                fields({"cik": whole(1), "deep_look": yes_no, "urgent": yes_no, "why": text(600)}), 0, 60
            ),
            "lacked": LACKED,
        }
    ),
    "section": fields(
        {
            "cik": whole(1),
            "section": text(9000),
            "forecasts": many(FORECAST, 0, 12),
            "sources": many(SOURCE, 0, 80),
            "lacked": LACKED,
        },
        {"resolved": many(RESOLVED, 0, 30)},
    ),
    "reading": fields(
        {
            "cik": whole(1),
            "section": text(6000),
            "reading": fields({"main_goal_met": THREE, "planned_in_advance": THREE, "subgroup_pushed": THREE}),
            "sources": many(SOURCE, 0, 80),
            "lacked": LACKED,
        }
    ),
    "case": fields(
        {
            "cik": whole(1),
            "case": text(5000),
            "strongest_points": many(text(600), 0, 5),
            "answer_to_other_side": text(3000, empty=True),
            "sources": many(SOURCE, 0, 80),
            "lacked": LACKED,
        }
    ),
    "decisions": fields(
        {"fund": one_of(*records.AI_FUNDS), "decisions": many(DECISION, 0, 5), "lacked": LACKED},
    ),
}


class AnswerError(Exception):
    """The answer is not in its fixed form. The message says what is wrong, never what the answer said."""


def parse(final_text: str, kind: str) -> dict[str, Any]:
    """The answer's block of JSON, checked against the form of its kind."""
    if kind not in FORMS:
        raise AnswerError(f"unknown kind of answer: {kind}")
    blocks = _BLOCK.findall(final_text)
    if len(blocks) != 1:
        raise AnswerError(f"the answer must hold exactly one block of JSON; this one holds {len(blocks)}")
    if final_text[final_text.rindex("```") + 3 :].strip():
        raise AnswerError("there is text after the block of JSON")
    try:
        found = json.loads(blocks[0], parse_float=_no_decimal)
    except (ValueError, AnswerError):
        raise AnswerError("the block is not valid JSON, or holds a number with a decimal point") from None
    try:
        FORMS[kind](found, kind)
        if kind == "decisions":
            _decision_rules(found)
    except RecordError as exc:
        raise AnswerError(str(exc)) from None
    return found


def _no_decimal(text_: str) -> Any:
    raise AnswerError("a number with a decimal point")


def _decision_rules(answer: dict[str, Any]) -> None:
    seen: set[int] = set()
    for i, d in enumerate(answer["decisions"]):
        where = f"decisions/{i}"
        if d["cik"] in seen:
            raise RecordError(f"{where}: a second order for the same company")
        seen.add(d["cik"])
        action, size = d["action"], d.get("size_pct")
        if action in ("buy", "add"):
            if "thesis" not in d or size is None:
                raise RecordError(f"{where}: '{action}' needs a size and a thesis")
        elif "reason" not in d:
            raise RecordError(f"{where}: '{action}' needs a reason")
        if action == "reduce" and size is None:
            raise RecordError(f"{where}: 'reduce' needs a size")

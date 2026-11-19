"""The readable page of one day (docs/SPEC.md section 5): the day's log records as text a person can read.

It is made from the log and holds nothing the log does not: decisions with their reasoning, what the limits did,
forecasts, outcomes, and which orders were filled on which day. No price, no value, no return: those are sealed
in the log and are not on the page either. The text goes through the same check as the log's own text once
more before it is written.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..log.store import Entry
from ..log.text import TextCheck, clean

DISCLAIMER = "**Paper money, not investment advice. No real money is traded.**"
CREDIT = (
    "Sources: company filings from the U.S. Securities and Exchange Commission (EDGAR); trial records from "
    "ClinicalTrials.gov, as they stood at this day's data cut-off. Every statement about a trial or a filing is "
    "our own summary, not the wording of the source. This project is not affiliated with or endorsed by them."
)


def _sources(found: list[dict[str, Any]]) -> list[str]:
    out = []
    for s in found:
        link = f" <{s['link']}>" if s.get("link") else ""
        when = f", {s['date']}" if s.get("date") else ""
        out.append(f"  - {s['source']}{when}{link}: {s['summary']}")
    return out


def _decision(r: dict[str, Any], after: list[Entry]) -> list[str]:
    if r["action"] == "nothing":
        return ["- **Nothing today.**"]
    company = r["company"]
    size = r.get("size_pct") or "the whole position"
    out = [f"- **{r['action'].capitalize()} {size}: {company['name']}** ({company.get('ticker', '')})"]
    thesis = r.get("thesis")
    if thesis:
        when = f" (expected {thesis['catalyst_date']})" if thesis.get("catalyst_date") else ""
        out += [
            f"  - Claim: {thesis['claim']}",
            f"  - What we believe that others do not: {thesis['edge']}",
            f"  - Catalyst: {thesis['catalyst']}{when}; our probability: {thesis['probability']}",
            f"  - Risks: {thesis['risks']}",
            f"  - We sell if: {thesis['sell_if']}",
        ]
    if r.get("reason"):
        out.append(f"  - Why: {r['reason']}")
    runs = r.get("runs") or []
    if runs:
        said = ", ".join(
            (f"{row['action']}" + (f" {row['size_pct']}" if row.get("size_pct") else ""))
            if row["readable"]
            else "no answer"
            for row in runs
        )
        out.append(f"  - The three runs said: {said}. Agreed: {'yes' if r.get('agreed') else 'no'}.")
    for e in after:
        if e.kind == "order_refused":
            out.append(f"  - **Refused** by a limit: {e.record['limit']}.")
        elif e.kind == "order_reduced":
            to = e.record["allowed_pct"]
            shown = to if isinstance(to, str) else "a smaller size (sealed: it follows from prices)"
            out.append(f"  - **Cut down** by a limit ({e.record['limit']}): from {e.record['asked_pct']} to {shown}.")
    if r.get("saw"):
        out += ["  - What we saw:", *["  " + line for line in _sources(r["saw"])]]
    out.append(f"  - Fill rule: {r['fill_rule']}")
    return out


def render(entries: list[Entry], day: date, mode: str, check: TextCheck) -> tuple[str, int]:
    """The page, and how many pieces of text the check took out of it."""
    today = [e for e in entries if e.day == day]
    start = next((e.record for e in today if e.kind == "session_start"), None)
    lines = [f"# Bobby Hedgefund: {day.isoformat()}", "", DISCLAIMER, ""]
    if mode != "live":
        lines += ["*Pilot: these are try-outs. Pilot trades do not count.*", ""]
    marks = sorted({e.record["dry_run"] for e in today if e.record.get("dry_run")})
    if marks:
        lines += [f"*Try-out: {'; '.join(marks)}*", ""]
    if start:
        lines += [
            f"Session started {start['start_time']}; data cut-off {start['cutoff']}; universe version "
            f"{start['universe']['file'].split('_')[0]}.",
            "",
        ]
        if start.get("skipped_working_days"):
            lines += [f"Working days without a session since the last one: {start['skipped_working_days']}.", ""]
    lines.append("## Decisions")
    funds: dict[str, list[str]] = {}
    for i, e in enumerate(today):
        if e.kind == "decision":
            after = [
                x
                for x in today[i + 1 : i + 3]
                if x.kind in ("order_refused", "order_reduced") and x.record["ref"] == e.seq
            ]
            funds.setdefault(e.record["fund"], []).extend(_decision(e.record, after))
        elif e.kind == "no_decision":
            funds.setdefault(e.record["fund"], []).append(f"- **No decision today: {e.record['reason']}.**")
    for fund, body in funds.items():
        lines += ["", f"### The {fund.capitalize()} fund", *body]
    if not funds:
        lines += ["", "No fund decided today."]
    forecasts = [e for e in today if e.kind == "forecast"]
    if forecasts:
        lines += ["", "## Forecasts"]
        for e in forecasts:
            r = e.record
            marked = " Make-or-break." if r["make_or_break"] else ""
            lines.append(
                f"- {r['company']['name']}: {r['event']}, by {r['by_date']}: **{r['probability']}** "
                f"({r['role']}; record {e.seq}).{marked}"
            )
            if r.get("reasoning"):
                lines.append(f"  - {r['reasoning']}")
    outcomes = [e for e in today if e.kind == "outcome"]
    if outcomes:
        lines += ["", "## Outcomes"]
        lines += [
            f"- Forecast {e.record['ref']}: **{e.record['result']}** ({e.record['resolved_on']}). {e.record['summary']}"
            for e in outcomes
        ]
    fills = [e for e in today if e.kind == "fill"]
    closed = [e for e in today if e.kind == "order_closed"]
    if fills or closed:
        lines += ["", "## Booked in this session"]
        lines += [
            f"- {e.record['fund']}: order {e.record['ref']} ({e.record['side']} {e.record['company']['name']}) filled "
            f"at the opening price of {e.record['fill_day']}."
            for e in fills
        ]
        lines += [
            f"- {e.record['fund']}: order {e.record['ref']} ({e.record['company']['name']}) closed: "
            f"{e.record['outcome']}."
            for e in closed
        ]
    other = [e for e in today if e.kind in ("restart", "stop_file", "refusal", "correction", "company_event")]
    if other:
        lines += ["", "## Other records"]
        for e in other:
            r = e.record
            what = {
                "restart": "the round was started again after it broke off",
                "stop_file": f"the stop file was switched {r.get('state')}",
                "refusal": f"a start was refused: {r.get('reason')}",
                "correction": f"correction of record {r.get('ref')}: {r.get('text')}",
                "company_event": f"{r.get('event')} of {(r.get('company') or {}).get('name')}, "
                f"effective {r.get('effective')}",
            }[e.kind]
            lines.append(f"- {what}")
    lines += ["", "---", CREDIT, "", DISCLAIMER, ""]
    text = "\n".join(lines)
    # Once more through the check on written text: the page says nothing the log does not, but it is checked on
    # its own all the same (docs/decisions/0004, "Differs from the spec", 4).
    cleaned = clean(text, None, check.known_amounts, check.private)
    return cleaned.text, len(cleaned.removed)

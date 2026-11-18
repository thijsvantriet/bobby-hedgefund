"""Steps 6 to 9 of the round: from the portfolio managers' answers to the day's records, the day page, the
publication and the summary (docs/SPEC.md section 1; docs/decisions/0009, point 4).

**Three runs, two of three.** Each AI fund's manager ran three times on the same task. A new position is opened
only when at least two readable runs say buy, at the smallest size among them, with the thesis of that run.
Everything else (add, reduce, sell) follows the lowest-numbered readable run. One readable answer is enough for
selling, not for buying. The log records what each run said.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

from .. import paths
from ..archive.store import iso, utcnow
from ..funds import cli as funds_cli
from ..funds import dice, engine, orders
from ..funds.book import replay
from ..funds.engine import Fund
from ..funds.prices import PriceBook
from ..funds.universe import covered_list
from ..log import canon, forecasts, publish, records
from ..log import private as private_names
from ..log.store import Entry, Log, LogError, Writer
from ..universe.output import write_new
from . import daypage, marker, steps, transcripts
from . import round as rounds
from .round import Collected, Round, RoundError

RUNS = (1, 2, 3)


def is_new(fund: Fund, cik: int) -> bool:
    """A position is new when the fund does not hold the company and has no buy order waiting for it."""
    return cik not in fund.positions and not any(o.cik == cik and o.side == "buy" for o in fund.orders.values())


def combine(fund: Fund, runs: dict[int, Collected]) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    """The fund's orders for today from its three runs, and per company what each run said."""
    readable = {n: got.answer["decisions"] for n, got in runs.items() if got.status == "ok" and got.answer}
    said: dict[int, dict[int, dict[str, Any]]] = {}
    for n, decisions in readable.items():
        for d in decisions:
            said.setdefault(d["cik"], {})[n] = d
    chosen: list[dict[str, Any]] = []
    base = min(readable) if readable else None
    for cik in sorted(said):
        by_run = said[cik]
        buyers = {n: d for n, d in by_run.items() if d["action"] in ("buy", "add")}
        if is_new(fund, cik):
            if len(buyers) >= 2:
                n, d = min(buyers.items(), key=lambda item: (canon.pct_fraction(item[1]["size_pct"]), item[0]))
                chosen.append({**d, "action": "buy", "from_run": n})
            continue  # with one buyer, or a sale of something not held: nothing
        if base is not None and base in by_run:
            d = by_run[base]
            action = "add" if d["action"] in ("buy", "add") else d["action"]
            chosen.append({**d, "action": action, "from_run": base})
    table: dict[int, list[dict[str, Any]]] = {}
    for cik in said:
        rows = []
        for n in RUNS:
            got = runs.get(n)
            row: dict[str, Any] = {"run": n, "readable": n in readable}
            if got is not None and got.model:
                row["model"] = got.model
            if n in readable:
                d = said[cik].get(n)
                row["action"] = d["action"] if d else "nothing"
                if d and d.get("size_pct"):
                    row["size_pct"] = d["size_pct"]
            rows.append(row)
        table[cik] = rows
    return chosen, table


def agreed(rows: list[dict[str, Any]]) -> bool:
    actions = {row.get("action") for row in rows if row["readable"]}
    return len(actions) == 1 and sum(row["readable"] for row in rows) >= 2


def load_inputs(rnd: Round) -> dict[int, dict[str, Any]]:
    lines = (rnd.session_dir / "inputs.jsonl").read_text(encoding="utf-8").splitlines()
    return {line["n"]: line for line in map(json.loads, lines)}


def saw(sources: list[dict[str, Any]], inputs: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """What the agent saw, for the record: the source's own name, date and link from the session's list of
    inputs, with the agent's one-sentence summary. A number that is not in the list is left out."""
    out = []
    for source in sources:
        line = inputs.get(source["n"])
        if line is None:
            continue
        entry: dict[str, Any] = {
            "n": source["n"],
            "source": line.get("source") or line["kind"],
            "summary": source["summary"],
        }
        if line.get("date"):
            entry["date"] = line["date"]
        if line.get("link"):
            entry["link"] = line["link"]
        out.append(entry)
    return out


def analyst_answers(rnd: Round) -> dict[int, list[Collected]]:
    out: dict[int, list[Collected]] = {}
    for task in rounds.step_tasks(rnd, "analysis-"):
        got = rounds.stored(rnd, task.task)
        if got is not None and got.status == "ok" and got.answer is not None:
            out.setdefault(int(task.task.split("-")[1]), []).append(got)
    return out


def write_forecasts(rnd: Round, writer: Writer, entries: list[Entry], mark: dict[str, str], notes: list[str]) -> int:
    """The analysts' forecasts and the catalysts they saw resolve, as records."""
    universe = steps.session_universe(rnd)
    inputs = load_inputs(rnd)
    open_ones = {e.seq: e for e in entries if e.kind == "forecast"}
    resolved = {e.record["ref"] for e in entries if e.kind == "outcome"}
    written = 0
    for cik, sections in sorted(analyst_answers(rnd).items()):
        company = universe.companies[cik]
        about = {"cik": cik, "name": company.name, "ticker": company.ticker}
        for got in sections:
            assert got.answer is not None
            for forecast in got.answer.get("forecasts") or []:
                body = {
                    "company": about,
                    "role": got.agent.removeprefix("bobby-"),
                    "event": forecast["event"],
                    "event_kind": forecast["event_kind"],
                    "by_date": forecast["by_date"],
                    "probability": forecast["probability"],
                    "make_or_break": forecast["make_or_break"],
                    "reasoning": forecast["reasoning"],
                    "sources": saw(forecast["sources"], inputs),
                    "agent": rounds.agent_entry(got),
                    "cutoff": iso(rnd.cutoff),
                    **mark,
                }
                try:
                    writer.add("forecast", body)
                    written += 1
                except LogError as exc:
                    notes.append(f"a forecast for company {cik} was not written: {exc}")
            for done in got.answer.get("resolved") or []:
                target = open_ones.get(done["forecast"])
                if target is None or target.record["company"]["cik"] != cik or done["forecast"] in resolved:
                    notes.append(f"an outcome for company {cik} names a forecast that is not open; not written")
                    continue
                body = {
                    "ref": done["forecast"],
                    "result": done["result"],
                    "resolved_on": done["resolved_on"],
                    "summary": done["summary"],
                    "sources": saw(done["sources"], inputs),
                    "agent": rounds.agent_entry(got),
                    **mark,
                }
                try:
                    writer.add("outcome", body)
                    resolved.add(done["forecast"])
                except LogError as exc:
                    notes.append(f"an outcome for company {cik} was not written: {exc}")
    return written


def decide(rnd: Round, cwd: Path, claude_code: str = "") -> list[str]:
    """Step 6: the limits and the day's records. From here the day's decisions are final."""
    if (rnd.round_dir / "decided.json").exists():
        raise RoundError("the day's records were written already: a round decides once")
    rnd.note_step(6, "begin")
    log = Log.for_mode(rnd.mode)
    entries = log.entries()
    books = replay(log)
    universe = steps.session_universe(rnd)
    can_buy = steps.buyable(rnd, universe)
    covered = covered_list(rnd.root / "reports") & can_buy
    prices = PriceBook(paths.data_dir() / "prices", rnd.cutoff)
    days = prices.days()

    def price_of(ticker: str) -> Fraction | None:
        found = prices.last_close(ticker, days[-1]) if days else None
        return found[0] if found else None

    mark = {"dry_run": rnd.dry_run} if rnd.dry_run else {}
    code = rounds.code_version(cwd, claude_code)
    inputs = load_inputs(rnd)
    analysed = analyst_answers(rnd)
    fill_rule = funds_cli.fill_rule(rnd.mode)
    notes: list[str] = []
    summary: dict[str, Any] = {"funds": {}, "forecasts": 0}
    out: list[str] = []
    with log.writer(rnd.day, check=steps.text_check(rnd, sorted(analysed))) as writer:
        summary["forecasts"] = write_forecasts(rnd, writer, entries, mark, notes)
        risky = orders.make_or_break(log.entries(), rnd.day)
        for name in [f for f in records.AI_FUNDS if f in books.funds]:
            fund = books.funds[name]
            runs = {
                t.run: got
                for t in rounds.step_tasks(rnd, f"pm-{name}-run-")
                if (got := rounds.stored(rnd, t.task)) and t.run
            }
            ran = [got for got in runs.values() if got.model]
            pm_agents = [rounds.agent_entry(got) for got in sorted(ran, key=lambda g: g.run or 0)]
            readable = [got for got in runs.values() if got.status == "ok"]
            models = {got.model for got in ran}
            fund_note = "the three runs did not all use the same model" if len(models) > 1 else ""
            if not readable:
                late = any(got.status in ("late", "missing") for got in runs.values()) or not runs
                reason = "out of time" if late else "no readable answer"
                body: dict[str, Any] = {"fund": name, "reason": reason, "agents": pm_agents, **mark}
                if fund_note:
                    body["note"] = fund_note
                writer.add("no_decision", body)
                summary["funds"][name] = {"decision": f"none: {reason}", "runs_readable": 0}
                out.append(f"{name}: no decision today: {reason}")
                continue
            chosen, table = combine(fund, runs)
            value, _ = engine.fund_value(fund, price_of)
            proposals = []
            for d in chosen:
                cik = d["cik"]
                listed = universe.companies.get(cik)
                position = fund.positions.get(cik)
                company_name = listed.name if listed else (position.name if position else f"company {cik}")
                ticker = listed.ticker if listed else (position.ticker if position else "")
                more: dict[str, Any] = {
                    "saw": saw(d["sources"], inputs),
                    "agents": pm_agents + [rounds.agent_entry(got) for got in analysed.get(cik, [])],
                    "runs": table[cik],
                    "agreed": agreed(table[cik]),
                    "from_run": d["from_run"],
                    "code": code,
                    **mark,
                }
                if fund_note:
                    more["note"] = fund_note
                if d.get("thesis"):
                    # The numbers part of a thesis is filled in by script. Until the quarterly reports are read
                    # (stream 4) there are none to fill in; nothing an agent wrote goes here.
                    more["thesis"] = {**d["thesis"], "numbers": []}
                if d.get("reason"):
                    more["reason"] = d["reason"]
                size = canon.pct_fraction(d["size_pct"]) if d.get("size_pct") else None
                proposals.append(orders.Proposal(d["action"], cik, company_name, ticker, size, more))
            if not proposals:
                nothing: dict[str, Any] = {"agents": pm_agents, "code": code, **mark}
                if fund_note:
                    nothing["note"] = fund_note
                proposals.append(orders.Proposal("nothing", more=nothing))
            verdicts = orders.check(fund, value, price_of, proposals, buyable=can_buy, covered=covered, risky=risky)
            orders.place(writer, fund, rnd.day, verdicts, fill_rule=fill_rule, cutoff=iso(rnd.cutoff))
            wanted = [v for v in verdicts if v.proposal.action != "nothing"]
            together = [agreed(rows) for rows in table.values()]
            summary["funds"][name] = {
                "runs_readable": len(readable),
                "orders": [
                    {"cik": v.proposal.cik, "action": v.proposal.action, "outcome": v.outcome, "limit": v.limit}
                    for v in wanted
                ],
                "companies_named_by_a_run": len(table),
                "companies_on_which_the_runs_agreed": sum(together),
            }
            out.append(
                f"{name}: {len(readable)} of 3 runs readable; {len(wanted)} order(s); "
                f"{sum(v.outcome == 'refused' for v in wanted)} refused, "
                f"{sum(v.outcome == 'reduced' for v in wanted)} reduced"
            )
        if "monthly" in rnd.extras:
            dice_books = dice.DiceBooks.load(log, rnd.root / "books" / "dice")
            out += funds_cli.monthly_draw(
                writer, replay(log), dice_books, prices, universe, covered, rnd.day, rnd.mode, rnd.cutoff
            )
    summary["notes"] = notes
    write_new(rnd.round_dir / "decided.json", json.dumps(summary, indent=1, sort_keys=True) + "\n")
    rnd.note_step(6, "done", forecasts=summary["forecasts"])
    out.insert(0, f"forecasts written: {summary['forecasts']}")
    out += [f"note: {n}" for n in notes]
    return [*out, "The day's records are written: from here they are final.", "NEXT: bobby-session publish"]


def publish_day(rnd: Round) -> list[str]:
    """Steps 7 and 8: the readable day page, checked once more, and the one commit."""
    if not (rnd.round_dir / "decided.json").exists():
        raise RoundError("the day's records are not written yet: run `bobby-session decide` first")
    rnd.note_step(7, "begin")
    log = Log.for_mode(rnd.mode)
    entries = log.entries()
    staging = log.staging
    page = staging / "days" / f"{rnd.day:%Y}" / f"{rnd.day:%m}" / f"{rnd.day.isoformat()}.md"
    names = private_names.PrivateNames(private_names.load(rnd.root / private_names.FILE))
    if not page.exists():
        text, cut = daypage.render(entries, rnd.day, rnd.mode, steps.text_check(rnd))
        page.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        write_new(page, text)
        if cut:
            _append_note(rnd, f"the day page: {cut} piece(s) of text taken out by the check")
    forecasts.write(staging, entries)
    rnd.note_step(7, "done")
    rnd.note_step(8, "begin")
    if rnd.mode != paths.PILOT:
        raise RoundError("publishing for real is not switched on in this version")
    repo = publish.pilot_repo(rnd.root)
    commit, changes = publish.publish(staging, repo, rnd.mode, rnd.day, private_names=names, push=False)
    if commit is None:
        commit = rounds.git("rev-parse", "HEAD", cwd=repo)
    when = iso(publish.commit_time(repo))
    target = rnd.round_dir / "published.json"
    if not target.exists():
        write_new(target, json.dumps({"commit": commit, "commit_time": when}) + "\n")
    rnd.note_step(8, "done")
    return [
        f"day page written; {sum(c.kind != 'same' for c in changes)} file(s) committed ({commit[:12]})",
        "pilot: committed on this machine only, nothing was sent; the commit time stands in for the time GitHub "
        f"would have received it ({when})",
        "NEXT: bobby-session end",
    ]


def _append_note(rnd: Round, text: str) -> None:
    with open(rnd.round_dir / "notes.txt", "a", encoding="utf-8") as fh:
        fh.write(text + "\n")


def measure(rnd: Round) -> dict[str, Any]:
    """The usage figures of the round, from the session's own records (docs/SPEC.md section 7)."""
    by_role: dict[str, dict[str, Any]] = {}
    lacked: list[dict[str, Any]] = []
    folder = rounds.answers_dir(rnd)
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        got = Collected(**json.loads(path.read_text(encoding="utf-8")))
        role = by_role.setdefault(
            got.agent.removeprefix("bobby-"),
            {"runs": 0, "ok": 0, "model_calls": 0, "models": [], "efforts": [], "seconds": 0.0, "tokens": {}},
        )
        role["runs"] += 1
        role["ok"] += got.status == "ok"
        role["model_calls"] += got.model_calls
        for value, key in ((got.model, "models"), (got.effort, "efforts")):
            if value and value not in role[key]:
                role[key].append(value)
        for kind, count in got.tokens.items():
            role["tokens"][kind] = role["tokens"].get(kind, 0) + count
        if got.started and got.ended:
            role["seconds"] += (rounds._time(got.ended) - rounds._time(got.started)).total_seconds()
        if got.lacked:
            lacked.append({"task": got.task, "lacked": got.lacked})
    steps_seen: dict[str, dict[str, float]] = {}
    for line in steps._read_lines(rnd.round_dir / "steps.jsonl"):
        entry = steps_seen.setdefault(f"{line['step']} {line['name']}", {})
        entry["began" if line["what"] == "begin" else "ended"] = line["minute"]
    leading = transcripts.main_usage(Path(rnd.project), rnd.session_id, iso(rnd.start)[:19])
    total = dict(leading)
    total.pop("answers", None)
    for role in by_role.values():
        for kind, count in role["tokens"].items():
            total[kind] = total.get(kind, 0) + count
    limits = _rate_limits()
    minutes = max(0, round(rnd.minutes()))
    for_log: dict[str, Any] = {"minutes": minutes, "agent_runs": sum(r["runs"] for r in by_role.values())}
    for key, name in (("five_hour", "five_hour_pct"), ("seven_day", "weekly_pct")):
        used = (limits or {}).get(key, {}).get("used_percentage")
        if isinstance(used, (int, float)) and 0 <= used <= 999:
            for_log[name] = canon.format_pct(Fraction(str(used)) / 100)
    decided = rnd.round_dir / "decided.json"
    return {
        "day": rnd.day.isoformat(),
        "minutes_from_start_to_end": minutes,
        "minutes_per_step": steps_seen,
        "per_role": by_role,
        "leading_session": leading,
        "tokens_in_all": total,
        "rate_limits_at_the_end": limits,
        "what_agents_lacked": lacked,
        "decisions": json.loads(decided.read_text(encoding="utf-8")) if decided.exists() else None,
        "for_the_log": for_log,
        "dry_run": rnd.dry_run,
        "stand_ins": rnd.stand_ins,
        "relaxed_clock": rnd.relaxed_clock,
    }


def _rate_limits() -> dict[str, Any] | None:
    """The share of the usage limits, when the status line saved it (the only place Claude Code gives it to)."""
    try:
        found = json.loads((paths.data_dir() / "usage" / "rate-limits.json").read_text(encoding="utf-8"))
        return found if isinstance(found, dict) else None
    except (OSError, ValueError):
        return None


def end(rnd: Round, *, abort: bool = False) -> list[str]:
    """Step 9, or, with `abort`, only switching the round's checks off after a round that broke off."""
    if abort:
        marker.clear(paths.data_dir())
        _append_note(rnd, f"{iso(utcnow())}: the round was broken off by hand; the day may be started once more")
        return [
            f"the round of {rnd.day} is broken off; its checks are switched off",
            "A new fresh session may start it once more.",
        ]
    published = rnd.round_dir / "published.json"
    if not published.exists():
        raise RoundError("the day is not published yet: run `bobby-session publish` first (or end with --abort)")
    done = json.loads(published.read_text(encoding="utf-8"))
    rnd.note_step(9, "begin")
    digest = steps.copy_conversation(rnd.root, Path(rnd.project), rnd.session_id, rnd.day, "end")
    usage = measure(rnd)
    usage["conversation_copy_sha256"] = digest
    target = rnd.round_dir / "usage.json"
    if not target.exists():
        write_new(target, json.dumps(usage, indent=1, sort_keys=True) + "\n")
    summary = {"session_id": rnd.session_id, "project": rnd.project, "day": rnd.day.isoformat(), **done}
    if not (rnd.round_dir / "done.json").exists():
        write_new(rnd.round_dir / "done.json", json.dumps(summary, sort_keys=True) + "\n")
    marker.clear(paths.data_dir())
    rnd.note_step(9, "done")
    return summary_lines(rnd, usage)


def summary_lines(rnd: Round, usage: dict[str, Any]) -> list[str]:
    """The one-screen summary for when the owner looks again: what was decided and how much the session used."""
    log = Log.for_mode(rnd.mode)
    today = [e for e in log.entries() if e.day == rnd.day]
    out = [f"Bobby Hedgefund, round of {rnd.day} ({rnd.mode}): done in {usage['minutes_from_start_to_end']} minutes."]
    if rnd.dry_run:
        out.append(f"TRY-OUT: {rnd.dry_run}. Nothing of this counts.")
    for e in today:
        r = e.record
        if e.kind == "decision" and r["action"] != "nothing":
            size = r.get("size_pct") or "the whole position"
            claim = (r.get("thesis") or {}).get("claim") or r.get("reason") or ""
            out.append(f"- {r['fund']}: {r['action']} {size} {r['company']['name']}: {claim[:160]}")
        elif e.kind == "decision":
            out.append(f"- {r['fund']}: nothing today")
        elif e.kind == "no_decision":
            out.append(f"- {r['fund']}: no decision: {r['reason']}")
        elif e.kind in ("order_refused", "order_reduced"):
            out.append(f"  ({e.kind.replace('_', ' ')}: {r['limit']})")
    out.append(
        f"Forecasts today: {sum(e.kind == 'forecast' for e in today)}; "
        f"outcomes: {sum(e.kind == 'outcome' for e in today)}."
    )
    roles_line = ", ".join(f"{name} {role['runs']}" for name, role in sorted(usage["per_role"].items()))
    out.append(f"Agent runs: {roles_line or 'none'}.")
    tokens = usage["tokens_in_all"]
    out.append(
        f"Tokens in all: {sum(tokens.values()):,} (new input {tokens.get('input_tokens', 0):,}, written to the cache "
        f"{tokens.get('cache_creation_input_tokens', 0):,}, read from it {tokens.get('cache_read_input_tokens', 0):,}, "
        f"output {tokens.get('output_tokens', 0):,})."
    )
    limits = usage["for_the_log"]
    if "five_hour_pct" in limits or "weekly_pct" in limits:
        out.append(
            f"Usage limits now: five hours {limits.get('five_hour_pct', '?')}, week {limits.get('weekly_pct', '?')}."
        )
    else:
        out.append(
            "The share of the usage limits could not be read by script (see /usage once, at the end of the pilot)."
        )
    notes = rnd.round_dir / "notes.txt"
    if notes.exists():
        out += [f"note: {line}" for line in notes.read_text(encoding="utf-8").splitlines()]
    return out


__all__ = ["asdict", "combine", "date", "decide", "end", "measure", "publish_day"]

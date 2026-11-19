"""The steps of the daily round, one function per command of `bobby-session` (docs/SPEC.md section 1).

1 start      checks, start time and data cut-off, the session folder, the first log record
2 book       fills, company events and values since the last session
3 screening  tasks for the screening agent; `collect screening`
4 analysts   who gets a deep analysis; tasks for the analysts; `collect analysts` joins their sections
5 managers   tasks for each AI fund's portfolio manager, three runs; `collect managers`
6 decide     the two-of-three rule, the limits, and the day's records (see `decide.py`)
7-8 publish  the day page and the commit
9 end        the copy of the conversation, the usage figures, the summary
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

from .. import paths
from ..archive.store import Archive, ArchiveError, iso, read_records, sha256_hex, utcnow
from ..funds import cli as funds_cli
from ..funds.book import Books, replay
from ..funds.prices import PriceBook
from ..funds.universe import Universe, covered_list
from ..funds.universe import load as load_universe
from ..log import canon, private, records
from ..log.store import Log
from ..log.text import TextCheck
from ..universe.output import write_new
from . import marker, roles, select, transcripts
from . import prepare as prep
from . import round as rounds
from .round import Collected, Round, RoundError

JOBS_FRESH_HOURS = 30
FIRST_LOOK_BACK = timedelta(days=7)
FRESH_SOURCES = ("startup", "clear")
RETRY_KEEPS_TIMES = timedelta(minutes=5)
LIVE_SECONDS = 120  # a session whose records changed this short ago is taken to be still at work
# The leading session never waits by itself: the collecting command does the waiting, up to the step's time.
THEN = "Then, right away: bobby-session collect {step} (it waits for the answers; repeat it until it prints NEXT)"


def _append(path: Path, line: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")


def _read_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def text_check(rnd: Round, companies: list[int] | None = None) -> TextCheck:
    """The checks on written text for this session: the companies that may not be named, and, for the companies
    that were analysed, the texts the agents could read (for the long-quote check) and the amounts they state."""
    from ..log import text as log_text

    names = private.PrivateNames(private.load(rnd.root / private.FILE))
    sources: list[str] = []
    for cik in companies or []:
        folder = rnd.session_dir / "companies" / str(cik)
        sources += [p.read_text(encoding="utf-8", errors="replace") for p in sorted(folder.rglob("*")) if p.is_file()]
    known: set[int] = set()
    for source in sources:
        known |= log_text.amounts(source)
    return TextCheck(sources, known, names)


def session_universe(rnd: Round) -> Universe:
    named = rounds.session_json(rnd)["universe"]
    universe = load_universe(paths.data_dir() / "universe" / named["file"])
    if universe.sha256 != named["sha256"]:
        raise RoundError("the universe file changed since the session folder was made")
    return universe


def buyable(rnd: Round, universe: Universe) -> set[int]:
    hidden = {c.cik for c in private.load(rnd.root / private.FILE)}
    return universe.buyable() - hidden


# ---------------------------------------------------------------- step 1


def _note_pending(root: Path, kind: str, body: dict[str, Any]) -> None:
    """Something that must reach the log with the next round that is committed (record 0003, point 2)."""
    _append(root / "rounds" / "pending.jsonl", {"kind": kind, "body": body})


def check_stop_file(root: Path, now: datetime) -> bool:
    """Is the STOP file there? Its coming and going is noted at once."""
    state_file = root / "rounds" / "stop-state"
    was = state_file.read_text().strip() if state_file.exists() else "off"
    present = (paths.data_dir() / paths.STOP_FILE).exists()
    if (was == "on") != present:
        state_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        state_file.write_text("on\n" if present else "off\n")
        _note_pending(root, "stop_file", {"state": "on" if present else "off", "noticed": iso(now)})
    return present


def how_session_began(session_id: str) -> str | None:
    lines = _read_lines(paths.data_dir() / "claude-sessions" / f"{session_id}.jsonl")
    return str(lines[-1].get("source")) if lines else None


def jobs_state(now: datetime) -> list[str]:
    """What is wrong with last night's jobs; empty when they ran."""
    wrong: list[str] = []
    limit = iso(now - timedelta(hours=JOBS_FRESH_HOURS))
    for name in ("archive", "prices"):
        root = paths.data_dir() / name
        try:
            runs = [r for r in read_records(root) if r.get("kind") == "run" and r.get("status") == "ok"]
        except (OSError, ArchiveError):
            wrong.append(f"the list of saved files of the {name} cannot be read")
            continue
        if not runs or str(runs[-1].get("ts", "")) < limit:
            wrong.append(f"the {name} job has no good run in the last {JOBS_FRESH_HOURS} hours")
        try:
            with Archive(root, readonly=True) as archive:
                report = archive.verify(quick=True)
            if not report.ok:
                wrong.append(f"the {name} does not pass its check")
        except ArchiveError:
            wrong.append(f"the {name} is busy (a download is running)")
    return wrong


def previous_round(root: Path, day: date) -> tuple[date, dict[str, Any]] | None:
    """The last round before `day` that was published: its day, and what is known of it. A round whose last
    step never ran (the terminal was closed, the step failed) counts just the same: its publication is a fact,
    and the books need the time of it."""
    folder = root / "rounds"
    found = (
        sorted(p for p in folder.glob("*/published.json") if p.parent.name < day.isoformat()) if folder.is_dir() else []
    )
    if not found:
        return None
    known = json.loads(found[-1].read_text(encoding="utf-8"))
    try:
        state = json.loads((found[-1].parent / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    for key in ("session_id", "first_session_id", "project"):
        if state.get(key):
            known[key] = state[key]
    return date.fromisoformat(found[-1].parent.name), known


def copy_conversation(rnd_root: Path, project: Path, session_id: str, day: date, label: str) -> str:
    """Copy Claude Code's records of a session to the data folder (docs/SPEC.md section 3). Returns the
    fingerprint of the copy: the fingerprint of the list of its files with theirs. Claude Code removes its own
    copies after a while, and writes them with a delay: so there is a copy at the end of the session ("end") and
    a complete one at the start of the next ("complete")."""
    target = rnd_root / "conversations" / f"{day.isoformat()}_{session_id}" / label
    listed = target.parent / f"{label}.sha256"
    if listed.exists():
        # A copy that was finished stays as it is: its fingerprint may be in the log already.
        return sha256_hex(listed.read_bytes())
    final, target = target, target.with_name(f".{label}-partial")
    if target.exists():
        shutil.rmtree(target)  # a copy that an interrupted run left half-made
    listing: list[str] = []
    main = project / f"{session_id}.jsonl"
    found = ([main] if main.exists() else []) + sorted((project / session_id).rglob("*"))
    for path in found:
        if not path.is_file() or path.is_symlink():
            continue
        data = path.read_bytes()
        rel = path.relative_to(project).as_posix()
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        dest.write_bytes(data)
        dest.chmod(0o400)
        listing.append(f"{sha256_hex(data)}  {rel}")
    text = "\n".join(listing) + "\n"
    if not listing:  # Claude Code has written nothing yet: no copy, and a later one may still be made
        shutil.rmtree(target, ignore_errors=True)
        return sha256_hex(text.encode("utf-8"))
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    if final.exists():
        shutil.rmtree(final)  # without its list: never finished
    target.rename(final)
    tmp = listed.with_name(f".{label}.sha256-partial")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(listed)
    return sha256_hex(text.encode("utf-8"))


def session_is_live(project: Path, session_id: str, now: float | None = None) -> bool:
    """Did Claude Code write to this session's records in the last two minutes?"""
    import time

    now = time.time() if now is None else now
    main = project / f"{session_id}.jsonl"
    found = ([main] if main.exists() else []) + list((project / session_id).rglob("*.jsonl"))
    try:
        return any(now - p.stat().st_mtime < LIVE_SECONDS for p in found)
    except OSError:
        return True


def working_days_between(earlier: date, later: date) -> int:
    count, day = 0, earlier + timedelta(days=1)
    while day < later:
        count += day.weekday() < 5
        day += timedelta(days=1)
    return count


def start(
    mode: str,
    session_id: str,
    cwd: Path,
    *,
    dry_run: str = "",
    relaxed_clock: bool = False,
    stand_ins: bool = False,
    now: datetime | None = None,
    project: Path | None = None,
    claude_code: str = "",
) -> list[str]:
    """Step 1. Refuses unless everything record 0003 asks holds; a refusal is noted for the log."""
    now = (now or utcnow()).astimezone(UTC)
    paths.check_mode(mode)
    root = paths.mode_root(mode)
    try:
        return _start(mode, root, session_id, cwd, dry_run, relaxed_clock, stand_ins, now, project, claude_code)
    except Exception as exc:
        # Whatever stopped the start, the next round's log says that a start was refused, and why.
        said = str(exc) if isinstance(exc, RoundError | prep.PrepareError) else type(exc).__name__
        _note_pending(root, "refusal", {"when": iso(now), "reason": said[:500] or "no reason given"})
        raise


def _start(
    mode: str,
    root: Path,
    session_id: str,
    cwd: Path,
    dry_run: str,
    relaxed_clock: bool,
    stand_ins: bool,
    now: datetime,
    project: Path | None,
    claude_code: str,
) -> list[str]:
    if (relaxed_clock or stand_ins) and not dry_run:
        raise RoundError("a relaxed clock and stand-in agents are for a try-out only (--dry-run)")
    if mode == paths.LIVE and dry_run:
        raise RoundError("a try-out never writes to the real log")
    if not session_id or not all(c.isalnum() or c in "-_" for c in session_id):
        raise RoundError("the session did not say which session it is")
    out: list[str] = []
    if check_stop_file(root, now):
        raise RoundError("a STOP file is in the data folder: no round runs and no fund trades")
    began = how_session_began(session_id)
    if began not in FRESH_SOURCES:
        why = f"this session began as '{began}'" if began else "it is not known how this session began"
        if not dry_run:
            raise RoundError(f"{why}: a round needs a fresh session (a new one, or /clear)")
        out.append(f"note: {why}; accepted only because this is a try-out")
    used = _read_lines(root / "rounds" / "sessions.jsonl")
    if any(line["session_id"] == session_id for line in used):
        raise RoundError("this session has started a round before; every round starts in a fresh session")
    project = project or transcripts.project_folder(cwd)
    rnd = rounds.new_round(
        mode, session_id, project, now, dry_run=dry_run, relaxed_clock=relaxed_clock, stand_ins=stand_ins
    )
    restart_of: Round | None = None
    if any((rnd.round_dir / name).exists() for name in ("done.json", "published.json")):
        raise RoundError(f"the round of {rnd.day} is done: one round of decisions per calendar day")
    active = marker.read(paths.data_dir())
    other = active is not None and active.get("session_id") != session_id
    if active and other and session_is_live(Path(str(active.get("project") or project)), str(active["session_id"])):
        raise RoundError(
            "another session is running a round right now (its records changed in the last two minutes); "
            "two sessions never run a round together"
        )
    never_prepared = False
    if (rnd.round_dir / "state.json").exists():
        earlier = rounds.load(mode, rnd.day)
        never_prepared = not earlier.session_dir.exists()
        # A later start of the same day keeps the first start time and data cut-off, so that the fill day cannot
        # move and no newer data comes in (record 0003, point 2).
        rnd.start, rnd.cutoff = earlier.start, earlier.cutoff
        rnd.first_session_id, rnd.extras, rnd.restarts = earlier.first_session_id, earlier.extras, earlier.restarts
        if never_prepared:
            # The first start stopped before the session folder was there (a failure, a time-out): no agent
            # ever ran and nothing was logged with its times, so this is a new start, not the one restart. Only
            # a start that is just being retried keeps its times (so the cut-off cannot creep while it is fixed).
            out.append("note: an earlier start of today stopped before the session folder was made; started anew")
            rnd.first_session_id = session_id
            if now - earlier.start > RETRY_KEEPS_TIMES:
                rnd.start = rnd.cutoff = now.replace(microsecond=0)
        else:
            if earlier.restarts >= 1:
                raise RoundError(f"the round of {rnd.day} broke off twice: this day is a skipped day")
            restart_of = earlier
            rnd.restarts = 1
    problems = jobs_state(now)
    log = Log.for_mode(mode)
    report = log.verify()
    problems += [f"the decision log: {p}" for p in report.problems[:3]]
    if git_dirty(cwd):
        problems.append("the project folder has changes that are not committed")
    code = rounds.code_version(cwd, claude_code)
    if mode == paths.LIVE:
        raise RoundError("the real round is not switched on in this version; only the pilot runs")
    if problems and not dry_run:
        raise RoundError("; ".join(problems))
    out += [f"note (try-out, so not refused): {p}" for p in problems]
    if code["branch"] != "main":
        out.append(f"note: the code is on branch {code['branch']}, not on main (allowed in the pilot, and noted)")
    entries = log.entries()
    earlier_days = sorted({e.record["session_day"] for e in entries if e.kind == "session_start"})
    first: dict[str, Any] = {}
    last = previous_round(root, rnd.day)
    if last is not None:
        last_day, done = last
        if done.get("commit_time"):
            first["previous_publication"] = {
                "session_day": last_day.isoformat(),
                "received": done["commit_time"],
                "source": "local commit (pilot)",
            }
        if done.get("session_id") and done.get("project"):
            digest = copy_conversation(root, Path(done["project"]), done["session_id"], last_day, "complete")
            first["previous_conversation"] = {"session_day": last_day.isoformat(), "sha256": digest}
            broke = done.get("first_session_id")
            if broke and broke != done["session_id"]:  # that day had a restart: keep its first session too
                copy_conversation(root, Path(done["project"]), broke, last_day, "complete")
        usage_file = root / "rounds" / last_day.isoformat() / "usage.json"
        if usage_file.exists():
            usage = json.loads(usage_file.read_text(encoding="utf-8"))
            first["usage"] = {"session_day": last_day.isoformat(), **usage.get("for_the_log", {})}
        first["skipped_working_days"] = working_days_between(last_day, rnd.day)
    if restart_of is None and not never_prepared:
        this_week = f"{rnd.day.isocalendar().year}-W{rnd.day.isocalendar().week:02d}"
        weeks = {f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" for d in map(date.fromisoformat, earlier_days)}
        rnd.extras = (["weekly"] if earlier_days and this_week not in weeks else []) + (
            ["monthly"] if not any(d.startswith(f"{rnd.day:%Y-%m}") for d in earlier_days) else []
        )
    if restart_of is None:
        rnd.save()  # before the slow part: a start that stops halfway is carried on with the same times
        starts = [e for e in entries if e.kind == "session_start" and e.record["session_day"] != rnd.day.isoformat()]
        since = rounds._time(starts[-1].record["cutoff"]) if starts else rnd.cutoff - FIRST_LOOK_BACK
        held = {cik for fund in replay(log).funds.values() for cik in fund.positions}
        done_prep = prep.prepare(
            data_dir=paths.data_dir(),
            mode_root=root,
            session_day=rnd.day,
            start_time=rnd.start,
            cutoff=rnd.cutoff,
            since=since,
            held=held,
        )
        out += [f"note: {n}" for n in done_prep.notes]
    if any(p.is_symlink() for p in rnd.session_dir.rglob("*")):
        raise RoundError("the session folder holds a link; an agent's search could follow it out of the folder")
    stored = rounds.session_json(rnd)
    rnd.save()
    if restart_of is not None:
        broke = rounds.break_off(rnd)
        if broke:
            out.append(f"note: {broke} task(s) of the session that broke off have no answer; they are not run again")
        if restart_of.session_id != session_id:
            try:  # the records of the session that broke off, before Claude Code tidies them away
                copy_conversation(root, Path(restart_of.project), restart_of.session_id, rnd.day, "broke-off")
            except OSError:
                out.append("note: the records of the session that broke off could not be copied")
    _append(
        root / "rounds" / "sessions.jsonl", {"session_id": session_id, "day": rnd.day.isoformat(), "time": iso(now)}
    )
    mark = {"dry_run": dry_run} if dry_run else {}
    with log.writer(rnd.day, check=text_check(rnd)) as writer:
        pending_file = root / "rounds" / "pending.jsonl"
        for line in _read_lines(pending_file):
            writer.add(line["kind"], {**line["body"], **mark})
        if pending_file.exists():
            pending_file.rename(pending_file.with_name(f"pending-written-{now:%Y%m%dT%H%M%SZ}.jsonl"))
        has_start = any(e.kind == "session_start" and e.record["session_day"] == rnd.day.isoformat() for e in entries)
        if restart_of is not None and has_start:
            body = {"session_day": rnd.day.isoformat(), "first_start": iso(rnd.start), "reason": "the round broke off"}
            writer.add("restart", {**body, **mark})
        else:
            writer.add(
                "session_start",
                {
                    "session_day": rnd.day.isoformat(),
                    "start_time": iso(rnd.start),
                    "cutoff": iso(rnd.cutoff),
                    "universe": stored["universe"],
                    "inputs_sha256": stored["inputs_sha256"],
                    "code": code,
                    **first,
                    **mark,
                },
            )
    marker.write(
        paths.data_dir(),
        session_id=session_id,
        session_dir=rnd.session_dir,
        round_dir=rnd.round_dir,
        mode=mode,
        stand_ins=stand_ins,
        project=str(project),
    )
    rnd.note_step(1, "done", restart=restart_of is not None)
    counts = stored["counts"]
    out += [
        f"round of {rnd.day} ({mode}) started at {iso(rnd.start)}; data cut-off {iso(rnd.cutoff)}",
        f"companies: {counts['companies']}; with news: {counts['companies_with_news']}; "
        f"new filings: {counts['filings']}",
        f"extras today: {', '.join(rnd.extras) or 'none'}",
        "NEXT: bobby-session book",
    ]
    return out


def git_dirty(cwd: Path) -> bool:
    return bool(rounds.git("status", "--porcelain", cwd=cwd))


# ---------------------------------------------------------------- step 2


def book(rnd: Round) -> list[str]:
    rnd.note_step(2, "begin")
    log = Log.for_mode(rnd.mode)
    with log.writer(rnd.day, check=text_check(rnd)) as writer:
        booker, _ = funds_cli.book_step(log, writer, rnd.mode, rnd.cutoff, session_universe(rnd))
    report = booker.report
    rnd.note_step(2, "done", days=len(report.days), fills=report.fills)
    out = [
        f"booked: {len(report.days)} trading day(s), {report.fills} fill(s), {report.closed} order(s) closed, "
        f"{report.events} company event(s)"
    ]
    if report.waiting_for:
        out.append(f"waiting: the price file of {report.waiting_for} is not stored yet; booking stops there")
    out += [f"note: {n}" for n in report.notes]
    return [*out, "NEXT: bobby-session screening"]


# ---------------------------------------------------------------- step 3


def screening(rnd: Round) -> list[str]:
    rnd.note_step(3, "begin")
    batches = sorted((rnd.session_dir / "screening").glob("batch-*.md"))
    made = []
    for path in batches:
        number = path.stem.removeprefix("batch-")
        lines = [f"Your batch file: {path}", "Judge every company in it, in the order of the file."]
        made.append(rounds.write_task(rnd, f"screening-{number}", "bobby-screening", lines))
    if not made:
        return ["no company has news today: nothing to screen", "NEXT: bobby-session analysts"]
    return [*rounds.start_lines(rnd, made), THEN.format(step="screening")]


def flagged(rnd: Round) -> tuple[list[int], int, int]:
    """What the screening said yes to, urgent ones first; and how many companies it judged, and missed."""
    with_news = set(rounds.session_json(rnd)["with_news"])
    urgent: list[int] = []
    normal: list[int] = []
    judged: set[int] = set()
    for task in rounds.step_tasks(rnd, "screening-"):
        got = rounds.stored(rnd, task.task)
        if got is None or got.status != "ok" or got.answer is None:
            continue
        for company in got.answer["companies"]:
            cik = company["cik"]
            if cik not in with_news or cik in judged:
                continue  # a company that was not in a batch, or a second verdict: not taken
            judged.add(cik)
            if company["deep_look"]:
                (urgent if company["urgent"] else normal).append(cik)
    return urgent + normal, len(judged), len(with_news - judged)


# ---------------------------------------------------------------- step 4


def last_reports(root: Path) -> dict[int, date]:
    out: dict[int, date] = {}
    folder = root / "reports"
    for company in folder.iterdir() if folder.is_dir() else []:
        days = []
        for path in company.glob("*.md"):
            try:
                days.append(date.fromisoformat(path.stem))
            except ValueError:
                continue
        if company.name.isdigit() and days:
            out[int(company.name)] = max(days)
    return out


def open_forecasts(entries: list[Any], cik: int) -> list[str]:
    resolved = {e.record["ref"] for e in entries if e.kind == "outcome"}
    out = []
    for e in entries:
        if e.kind == "forecast" and e.seq not in resolved and e.record["company"]["cik"] == cik:
            r = e.record
            out.append(f'- record {e.seq}: "{r["event"]}" by {r["by_date"]}, {r["probability"]} ({r["role"]})')
    return out


def analysts(rnd: Round, now: datetime | None = None) -> list[str]:
    rnd.note_step(4, "begin")
    stored = rounds.session_json(rnd)
    universe = session_universe(rnd)
    log = Log.for_mode(rnd.mode)
    entries = log.entries()
    books = replay(log)
    held = {cik for fund in books.funds.values() for cik in fund.positions}
    yes, judged, missed = flagged(rnd)
    limit = select.MOST_WITH_EXTRAS if rnd.extras else select.MOST
    out = [f"screening: {judged} companies judged, {len(yes)} worth a deep look, {missed} not judged"]
    if rnd.minutes(now) >= rounds.NO_NEW_ANALYSIS and not rnd.relaxed_clock:
        out.append(f"minute {rnd.minutes(now):.0f}: no new deep analysis starts after minute {rounds.NO_NEW_ANALYSIS}")
        limit = 0
    chosen = select.deep_order(
        universe=buyable(rnd, universe),
        held_with_news=held & set(stored["with_news"]),
        flagged=yes,
        catalysts=select.calendar_from_forecasts(entries, rnd.day),
        last_report=last_reports(rnd.root),
        limit=limit,
    )
    _append(rnd.round_dir / "chosen.jsonl", {"chosen": [[cik, why] for cik, why in chosen]})
    made = []
    for cik, why in chosen:
        company = universe.companies[cik]
        folder = rnd.session_dir / "companies" / str(cik)
        base = [
            f"Company: {company.name} ({company.ticker}), SEC company number {cik}.",
            f"Its files are in {folder}: company.md (what is new), numbers.md (private), trials.md, the folder "
            "filings/ (the new filings as plain text) and report.md (our own last report, if there is one).",
            "Every file in that folder, by its full path (you do not need to search for them):",
            *[f"- {path}" for path in sorted(folder.rglob("*")) if path.is_file()],
            f"The numbered list of sources is {rnd.session_dir / 'inputs.jsonl'}.",
            f"Why it is analysed today: {why}.",
        ]
        forecasts = open_forecasts(entries, cik)
        for role in rounds.ANALYSTS:
            lines = list(base)
            if role == "clinical":
                lines += ["Our open forecasts for this company:", *(forecasts or ["- none"])]
            lines.append("Write your section for this company.")
            made.append(rounds.write_task(rnd, f"analysis-{cik}-{role}", f"bobby-{role}-analyst", lines))
        if cik in stored["results_news"]:
            lines = [
                *base,
                "An event report among the new filings may announce results. Read it and give your reading.",
            ]
            made.append(rounds.write_task(rnd, f"analysis-{cik}-results", "bobby-results-reader", lines))
    if not made:
        return [*out, "no deep analysis today", "NEXT: bobby-session debate"]
    out.append(f"deep analysis of {len(chosen)} companies")
    return [*out, *rounds.start_lines(rnd, made), THEN.format(step="analysts")]


def join_reports(rnd: Round) -> list[str]:
    """Join the analysts' sections into the one report per company (no model: record 0009, point 1). A company
    with fewer than two readable sections gets no report today, and so stays off the covered list."""
    universe = session_universe(rnd)
    by_company: dict[int, list[Collected]] = {}
    for task in rounds.step_tasks(rnd, "analysis-"):
        got = rounds.stored(rnd, task.task)
        if got is not None and got.status == "ok" and got.answer is not None:
            by_company.setdefault(int(task.task.split("-")[1]), []).append(got)
    out = []
    for cik, sections in sorted(by_company.items()):
        company = universe.companies[cik]
        if len(sections) < 2:
            out.append(f"company {cik}: {len(sections)} readable section(s): no report today")
            continue
        parts = [
            f"# {company.name} ({company.ticker}): report of {rnd.day}",
            f"Data cut-off: {iso(rnd.cutoff)}. Private: it holds numbers from prices and text from sources.",
        ]
        for got in sorted(sections, key=lambda g: g.task):
            assert got.answer is not None
            parts += ["", f"## {roles.BY_NAME[got.agent].what} ({got.model}, {got.effort})", "", got.answer["section"]]
            if got.answer.get("reading"):
                reading = got.answer["reading"]
                parts.append("")
                parts.append(
                    f"Main goal met: {reading['main_goal_met']}. Analysis planned in advance: "
                    f"{reading['planned_in_advance']}. Subgroup pushed forward: {reading['subgroup_pushed']}."
                )
            for forecast in got.answer.get("forecasts") or []:
                marked = " (make-or-break)" if forecast["make_or_break"] else ""
                parts.append(
                    f"\n- Forecast: {forecast['event']}, by {forecast['by_date']}: {forecast['probability']}{marked}. "
                    f"{forecast['reasoning']}"
                )
            if got.lacked:
                parts.append("\nLacked: " + "; ".join(got.lacked))
        text = "\n".join(parts) + "\n"
        target = rnd.root / "reports" / str(cik) / f"{rnd.day.isoformat()}.md"
        if not target.exists():
            write_new(target, text)  # the company is on the covered list from here on
        copy = rnd.session_dir / "round" / "reports" / f"{cik}.md"
        if not copy.exists():
            write_new(copy, text)
        out.append(f"company {cik}: report joined from {len(sections)} sections")
    return out


# ---------------------------------------------------------------- step 5


def fund_file(rnd: Round, books: Books, name: str, prices: PriceBook, universe: Universe, entries: list[Any]) -> str:
    """What a fund holds, for its portfolio manager. Private: weights come from prices."""
    fund = books.funds[name]
    days = prices.days()

    def price_of(ticker: str) -> Fraction | None:
        found = prices.last_close(ticker, days[-1]) if days else None
        return found[0] if found else None

    from ..funds import engine

    value, _ = engine.fund_value(fund, price_of)
    lines = [
        f"# The {name.capitalize()} fund",
        "PRIVATE: weights come from saved prices. Nothing here may be written into a thesis or a reason.",
        f"Cash: {canon.format_pct(Fraction(fund.cash, value)) if value else 'not known'} of the fund.",
        "",
        "## Positions",
    ]
    theses = {e.seq: e.record for e in entries if e.kind == "decision" and e.record["fund"] == name}
    bought: dict[int, dict[str, Any]] = {}
    for record in theses.values():
        if record.get("thesis") and record.get("company"):
            bought[record["company"]["cik"]] = record
    for cik in sorted(fund.positions):
        position = fund.positions[cik]
        price = price_of(position.ticker)
        weight = canon.format_pct(Fraction(engine.to_cents(price * position.shares), value)) if price and value else "?"
        lines.append(f"- {position.name} ({position.ticker}), SEC number {cik}: about {weight} of the fund")
        if cik in bought:
            thesis = bought[cik]["thesis"]
            lines.append(f"  Our thesis: {thesis['claim']}")
            lines.append(f"  Our sell rule: {thesis['sell_if']}")
    if not fund.positions:
        lines.append("- none: the fund is all in cash")
    lines += ["", "## Orders that are still waiting to be filled"]
    for order in sorted(fund.orders.values(), key=lambda o: o.ref):
        size = canon.format_pct(order.size) if order.size is not None else "the whole position"
        lines.append(f"- {order.side} {size} of {order.name} ({order.ticker}), SEC number {order.cik}")
    if not fund.orders:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def managers(rnd: Round, now: datetime | None = None) -> list[str]:
    rnd.note_step(5, "begin")
    log = Log.for_mode(rnd.mode)
    entries = log.entries()
    books = replay(log)
    universe = session_universe(rnd)
    funds = [f for f in records.AI_FUNDS if f in books.funds]
    if not funds:
        return ["no AI fund has been started (bobby-funds start): no decisions today", "NEXT: bobby-session decide"]
    prices = PriceBook(paths.data_dir() / "prices", rnd.cutoff)
    covered = covered_list(rnd.root / "reports") & buyable(rnd, universe)
    today = (
        sorted(int(p.stem) for p in (rnd.session_dir / "round" / "reports").glob("*.md"))
        if (rnd.session_dir / "round" / "reports").is_dir()
        else []
    )
    made = []
    for name in funds:
        target = rnd.session_dir / "round" / "funds" / f"{name}.md"
        if not target.exists():
            write_new(target, fund_file(rnd, books, name, prices, universe, entries))
        lines = [
            f"The fund's own file: {target}",
            "Reports written today (in the folder " + str(rnd.session_dir / "round" / "reports") + "):",
            *(
                [f"- {cik}.md: {universe.companies[cik].name} ({universe.companies[cik].ticker})" for cik in today]
                or ["- none today"]
            ),
            "Covered companies with an earlier report (each in its own folder under companies/, as report.md):",
            *(
                [
                    f"- {cik}: {universe.companies[cik].name} ({universe.companies[cik].ticker})"
                    for cik in sorted(covered - set(today))
                    if (rnd.session_dir / "companies" / str(cik) / "report.md").exists()
                ]
                or ["- none"]
            ),
            f"A company's own files are in {rnd.session_dir / 'companies'}/<SEC number>/.",
            f"The numbered list of sources is {rnd.session_dir / 'inputs.jsonl'}.",
            "Decide what the fund does today.",
        ]
        if name == "debate":
            cases = (
                sorted((rnd.session_dir / "round" / "debate").glob("*.md"))
                if (rnd.session_dir / "round" / "debate").is_dir()
                else []
            )
            lines.insert(1, "The bull and bear cases: " + (", ".join(str(c) for c in cases) or "none today"))
        for run in (1, 2, 3):
            made.append(rounds.write_task(rnd, f"pm-{name}-run-{run}", f"bobby-pm-{name}", lines, run=run))
    out = [f"decisions for: {', '.join(funds)} (each three times, independently)"]
    if rnd.minutes(now) > rounds.DECISIONS_UNTIL and not rnd.relaxed_clock:
        out.append(f"minute {rnd.minutes(now):.0f}: past the time for decisions; they will count as out of time")
    return [*out, *rounds.start_lines(rnd, made), THEN.format(step="managers")]


# ---------------------------------------------------------------- the Debate fund's bull and bear


def debate(rnd: Round) -> list[str]:
    """The bull and the bear argue about each company with a report of today, two rounds at most (docs/SPEC.md
    section 3). Only when the Debate fund runs; they argue once, and all three runs of that fund's manager read
    the same cases."""
    books = replay(Log.for_mode(rnd.mode))
    reports = rnd.session_dir / "round" / "reports"
    todays = sorted(int(p.stem) for p in reports.glob("*.md")) if reports.is_dir() else []
    if "debate" not in books.funds or not todays:
        why = "the Debate fund is not running" if "debate" not in books.funds else "no report was written today"
        return [f"no debate: {why}", "NEXT: bobby-session managers"]
    done = {t.task for t in rounds.step_tasks(rnd, "debate-")}
    first = {f"debate-{cik}-{side}-1" for cik in todays for side in ("bull", "bear")}
    number = 2 if first <= done else 1
    if number == 2 and any(rounds.stored(rnd, name) is None for name in first):
        return ["the first round of the debate is not collected yet: bobby-session collect debate"]
    if number == 2:
        # A second round answers a case; a side whose opponent gave no readable case has nothing to answer.
        cases = rnd.session_dir / "round" / "debate"
        second = {
            f"debate-{cik}-{side}-2"
            for cik in todays
            for side, other in (("bull", "bear"), ("bear", "bull"))
            if (cases / f"{cik}-{other}-1.md").exists()
        }
        if second <= done:
            if all(rounds.stored(rnd, name) is not None for name in second):
                return ["the debate is over", "NEXT: bobby-session managers"]
            return ["the second round of the debate is not collected yet: bobby-session collect debate"]
    made = []
    for cik in todays:
        for side, other in (("bull", "bear"), ("bear", "bull")):
            lines = [
                f"Company: SEC company number {cik}. Its report of today: {reports / f'{cik}.md'}",
                f"Its own files: {rnd.session_dir / 'companies' / str(cik)}",
                f"The numbered list of sources is {rnd.session_dir / 'inputs.jsonl'}.",
            ]
            if number == 2:
                case = rnd.session_dir / "round" / "debate" / f"{cik}-{other}-1.md"
                if not case.exists():
                    continue  # the other side gave no readable case: nothing to answer
                lines.append(f"Second round. The other side's case: {case} . Answer its strongest points.")
            else:
                lines.append("First round. Make your case.")
            made.append(rounds.write_task(rnd, f"debate-{cik}-{side}-{number}", f"bobby-{side}", lines))
    if not made:
        return ["no case to answer in a second round", "NEXT: bobby-session managers"]
    return [*rounds.start_lines(rnd, made), THEN.format(step="debate")]


def write_cases(rnd: Round) -> list[str]:
    """Put the collected cases where the Debate fund's manager (and the other side) can read them."""
    out = []
    for task in rounds.step_tasks(rnd, "debate-"):
        got = rounds.stored(rnd, task.task)
        _, cik, side, number = task.task.split("-")
        target = rnd.session_dir / "round" / "debate" / f"{cik}-{side}-{number}.md"
        if got is None or got.status != "ok" or got.answer is None or target.exists():
            continue
        points = "".join(f"- {point}\n" for point in got.answer["strongest_points"])
        text = f"# The {side} case for company {cik}, round {number}\n\n{got.answer['case']}\n\n{points}"
        if got.answer["answer_to_other_side"]:
            text += f"\nAnswer to the other side:\n{got.answer['answer_to_other_side']}\n"
        write_new(target, text)
        out.append(f"{side} case for company {cik}, round {number}: written")
    return out


# ---------------------------------------------------------------- collecting

STEPS = {
    "canary": ("canary-", rounds.HARD_STOP, "bobby-session screening"),
    "screening": ("screening-", rounds.NO_NEW_ANALYSIS, "bobby-session analysts"),
    "analysts": ("analysis-", rounds.ANALYSIS_USED_UNTIL, "bobby-session debate"),
    "debate": ("debate-", rounds.DEBATE_UNTIL, "bobby-session debate"),
    "managers": ("pm-", rounds.DECISIONS_UNTIL, "bobby-session decide"),
}


def collect(rnd: Round, step: str, wait_seconds: float = 90) -> list[str]:
    if step not in STEPS:
        raise RoundError(f"nothing to collect for '{step}'; it is one of: {', '.join(STEPS)}")
    prefix, minute, following = STEPS[step]
    wanted = rounds.step_tasks(rnd, prefix)
    results = rounds.collect(rnd, wanted, rnd.deadline(minute), wait_seconds)
    out = [f"{step}: {rounds.summary_line(results)}"]
    out += [f"- {r.task}: {r.status}: {r.reason}" for r in results if r.status != "ok"]
    waiting = [r for r in results if r.status == "missing"]
    if waiting:
        return [*out, f"{len(waiting)} answer(s) may still come: run this command again in a moment"]
    if any(r.status == "late" for r in results):
        # The time for this step is over: agents of it that are still running may be stopped now.
        marker.update(paths.data_dir(), may_stop=True)
        out.append("The time for this step is over: agents of it that are still running may be stopped.")
    if step == "canary":
        return [*out, *canary_result(rnd), f"NEXT: {following}"]
    number = {"screening": 3, "analysts": 4, "debate": 5, "managers": 5}[step]
    if step == "analysts":
        out += join_reports(rnd)
    if step == "debate":
        out += write_cases(rnd)
    rnd.note_step(number, "done", **{r.status: sum(x.status == r.status for x in results) for r in results})
    return [*out, f"NEXT: {following}"]


# ---------------------------------------------------------------- a test of the reading check, in a real session


def canary(rnd: Round) -> list[str]:
    """A pilot check (docs/decisions/0003, point 3; record 0009, pilot check 4): one agent is asked to read a
    file outside the session folder. The reading check must refuse that, and note it."""
    if rnd.stand_ins:
        return ["a try-out with stand-in agents has no reading check to test", "NEXT: bobby-session screening"]
    target = paths.data_dir() / "archive" / "manifest.head"
    lines = [
        "This is the round's own test of the reading check. It is not an analysis.",
        f"1. Try once to read the file {target} . It lies outside the session folder, so the read must be",
        "   refused. Do not try any other way to get at it.",
        f"2. Then read the file {rnd.session_dir / 'screening' / 'no-news.txt'} .",
        'Answer in your usual form with an empty list of companies, and under "lacked" exactly one entry: either',
        '"the read outside the folder was refused" or "the read outside the folder was NOT refused".',
    ]
    made = [rounds.write_task(rnd, "canary-fence", "bobby-screening", lines)]
    return [*rounds.start_lines(rnd, made), THEN.format(step="canary")]


def canary_result(rnd: Round) -> list[str]:
    target = str(paths.data_dir() / "archive" / "manifest.head")
    refusals = _read_lines(rnd.round_dir / "refusals.jsonl")
    fired = [r for r in refusals if r.get("check") == "fence" and r.get("path") == target]
    if fired:
        named = fired[0].get("agent") or "(no name)"
        return [f"reading check: FIRED inside the agent, and named it: {named}"]
    return ["reading check: DID NOT FIRE. An agent can read outside the session folder: stop, and tell the owner."]

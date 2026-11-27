"""One daily round (docs/SPEC.md sections 1 and 2; docs/decisions/0003 and 0009): its state, its step clock, the
tasks it hands out and the answers it takes back from the agents' own records.

The leading session only runs these commands and starts the agents they name. Everything that decides, counts,
writes the log or publishes is done here, by script.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from .. import paths
from ..archive.store import iso, sha256_hex, utcnow
from ..universe.output import write_new
from . import answers, marker, roles, tasks, transcripts
from .tasks import Task

# The step clock of the spec, in minutes from the start of the round.
NOT_IN_FORM = "the answer is not in its form"
NO_NEW_ANALYSIS = 20  # no new deep analysis starts after this
ANALYSIS_USED_UNTIL = 28  # an analyst's answer that arrives later waits for the next session
DEBATE_UNTIL = 33  # the bull and bear cases of the Debate fund must be in by then
DECISIONS_UNTIL = 38  # a portfolio manager that has not answered by then: "no decision today: out of time"
HARD_STOP = 45
STEP_NAMES = {
    1: "checks and preparation",
    2: "booking",
    3: "screening",
    4: "deep analysis",
    5: "decisions",
    6: "limits and records",
    7: "day page",
    8: "publishing",
    9: "summary",
}
ANALYSTS = ("science", "clinical", "financial", "market")


class RoundError(Exception):
    pass


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@dataclass
class Round:
    mode: str
    day: date
    session_id: str
    start: datetime
    cutoff: datetime
    project: str  # the folder with Claude Code's records of this session
    dry_run: str = ""  # a mark that goes into every record when this is a try-out
    relaxed_clock: bool = False  # try-out only: a late answer is noted, not refused
    stand_ins: bool = False  # try-out only: the agent files could not be loaded
    restarts: int = 0
    extras: list[str] = field(default_factory=list)  # weekly and monthly extras of this day
    first_session_id: str = ""

    @property
    def root(self) -> Path:
        return paths.mode_root(self.mode)

    @property
    def session_dir(self) -> Path:
        return self.root / "sessions" / self.day.isoformat()

    @property
    def round_dir(self) -> Path:
        return self.root / "rounds" / self.day.isoformat()

    def minutes(self, now: datetime | None = None) -> float:
        return ((now or utcnow()) - self.start).total_seconds() / 60

    def deadline(self, minute: int) -> datetime:
        return self.start + timedelta(minutes=minute)

    def save(self) -> None:
        body = {**asdict(self), "day": self.day.isoformat(), "start": iso(self.start), "cutoff": iso(self.cutoff)}
        self.round_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = self.round_dir / ".state.json"
        tmp.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.round_dir / "state.json")

    def note_step(self, number: int, what: str, **more: Any) -> None:
        """One line per step that began or ended: the pilot's "minutes per step" comes from these."""
        line = {"step": number, "name": STEP_NAMES[number], "what": what, "minute": round(self.minutes(), 2), **more}
        with open(self.round_dir / "steps.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"time": iso(utcnow()), **line}) + "\n")


def load(mode: str, day: date) -> Round:
    path = paths.mode_root(mode) / "rounds" / day.isoformat() / "state.json"
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RoundError(f"no round was started for {day}; run `bobby-session start` first") from None
    body["day"], body["start"], body["cutoff"] = (
        date.fromisoformat(body["day"]),
        _time(body["start"]),
        _time(body["cutoff"]),
    )
    return Round(**body)


def current(mode: str, session_id: str | None = None) -> Round:
    """The round that is active right now (the marker in the data folder says which)."""
    active = marker.read(paths.data_dir())
    if active is None or active.get("mode") != mode:
        raise RoundError("no round is active; run `bobby-session start` first")
    if session_id and active["session_id"] != session_id:
        raise RoundError("the active round belongs to another session")
    return load(mode, date.fromisoformat(Path(active["session_dir"]).name))


def git(*args: str, cwd: Path | None = None) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, check=False)
    return done.stdout.strip() if done.returncode == 0 else ""


def code_version(cwd: Path, claude_code: str = "") -> dict[str, str]:
    return {
        "commit": git("rev-parse", "HEAD", cwd=cwd) or "unknown",
        "branch": git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd) or "unknown",
        "claude_code": claude_code or "unknown",
    }


# ---------------------------------------------------------------- tasks


def task_text(rnd: Round, role: roles.Role, lines: list[str]) -> str:
    """The text of a task file. In a try-out without agent files the role's own instructions go in front."""
    body = "\n".join([f"Session folder: {rnd.session_dir}", *lines]) + "\n"
    if rnd.stand_ins:
        return (
            "# Your instructions\n\n" + roles.COMMON + "\n" + role.body + "\n# Your task\n\n" + body
            + "\nUse only the tools Read, Grep and Glob, and only on absolute paths inside the session folder.\n"
        )  # fmt: skip
    return body


def write_task(rnd: Round, name: str, role_name: str, lines: list[str], run: int | None = None) -> Task:
    role = roles.BY_NAME[role_name]
    existing = tasks.load(rnd.session_dir).get(name)
    if existing is not None:
        return existing  # a step that is run again hands out nothing twice: the task stays as first written
    stand_in = None
    if rnd.stand_ins:
        stand_in = {"subagent_type": "general-purpose", "model": roles.ALIAS[role.model], "effort": role.effort}
    return tasks.write(rnd.session_dir, name, role_name, task_text(rnd, role, lines), run=run, stand_in=stand_in)


def start_lines(rnd: Round, made: list[Task]) -> list[str]:
    """What the leading session is told: which agents to start, each with one fixed sentence. A task that has
    its result already (also "broke off") is not named again: a task is started once."""
    started = {run.prompt for run in transcripts.agent_runs(Path(rnd.project), rnd.session_id)}
    made = [t for t in made if stored(rnd, t.task) is None and t.prompt(rnd.session_dir) not in started]
    if not made:
        return ["Nothing to start: every task of this step was started already or has its result."]
    out = [f"Start these {len(made)} agents, all at once, in the background. Use each sentence exactly as it stands:"]
    for t in made:
        if t.stand_in:
            how = (
                f"agent type {t.stand_in['subagent_type']}, model {t.stand_in['model']}, effort {t.stand_in['effort']}"
            )
        else:
            how = f"agent type {t.agent} (no model, no effort)"
        out.append(f"- task {t.task}: {how}")
        out.append(f"  PROMPT: {t.prompt(rnd.session_dir)}")
    return out


# ---------------------------------------------------------------- answers


@dataclass
class Collected:
    task: str
    agent: str
    status: str  # "ok", "rejected", "late" or "missing"
    reason: str = ""
    answer: dict[str, Any] | None = None
    model: str = ""
    effort: str = ""
    claude_code: str = ""
    substituted: bool = False
    stand_in: bool = False
    run: int | None = None
    tokens: dict[str, int] = field(default_factory=dict)
    model_calls: int = 0
    started: str = ""
    ended: str = ""
    agent_id: str = ""
    task_sha256: str = ""
    lacked: list[str] = field(default_factory=list)


def answers_dir(rnd: Round) -> Path:
    return rnd.round_dir / "answers"


def stored(rnd: Round, task: str) -> Collected | None:
    path = answers_dir(rnd) / f"{task}.json"
    return Collected(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None


def judge(rnd: Round, task: Task, run: transcripts.AgentRun | None, deadline: datetime | None) -> Collected:
    """Hold one agent run against everything record 0009, point 3, asks of it."""
    role = roles.BY_NAME[task.agent]
    got = Collected(
        task.task, task.agent, "missing", run=task.run, task_sha256=task.sha256, stand_in=bool(task.stand_in)
    )
    if not tasks.unchanged(rnd.session_dir, task):
        return _reject(got, "the task file is not as the script wrote it")
    if run is None:
        return _reject(got, "the agent was not started, or left no record", status="missing")
    got.model, got.effort = "+".join(run.models), "+".join(run.efforts)
    got.claude_code, got.tokens, got.model_calls = run.version, run.tokens, run.answers
    got.started, got.ended, got.agent_id = run.started, run.ended, run.agent_id
    if not run.finished:
        return _reject(got, "the agent has not answered (yet)", status="missing")
    if run.incoming != 1:
        return _reject(got, "the agent received more than its one starting message")
    wanted_type = task.stand_in["subagent_type"] if task.stand_in else task.agent
    if run.agent_type != wanted_type:
        return _reject(got, f"it was run as {run.agent_type}, not as {wanted_type}")
    wrong = transcripts.outside(run, rnd.session_dir)
    if wrong:
        return _reject(got, "the agent " + "; ".join(sorted(set(wrong))))
    allowed_models = {role.model}
    fallback = (marker.read(paths.data_dir()) or {}).get("fallback", {}).get(task.task)
    if fallback:
        allowed_models.add(roles.NEXT_DOWN.get(role.model, role.model))
    as_filed = run.models == [role.model] and run.efforts == [role.effort]
    if not as_filed:
        got.substituted = True
        if task.stand_in:
            pass  # a try-out: noted, with both values, and the answer is used
        elif len(run.models) != 1 or run.models[0] not in allowed_models or run.efforts != [role.effort]:
            return _reject(got, f"model or effort differ from the agent file ({role.model}, {role.effort})")
    if deadline is not None and run.ended and _time(run.ended) > deadline:
        if not rnd.relaxed_clock:
            return _reject(got, "the answer came after the time for this step", status="late")
        got.reason = "late (noted only: the clock of this try-out is relaxed)"
    try:
        got.answer = answers.parse(run.final_text, role.answer)
    except answers.AnswerError as exc:
        return _reject(got, f"{NOT_IN_FORM}: {exc}")
    got.lacked = list(got.answer.get("lacked") or [])
    got.status = "ok"
    return got


def _reject(got: Collected, reason: str, status: str = "rejected") -> Collected:
    got.status, got.reason = status, reason
    return got


def collect(rnd: Round, wanted: list[Task], deadline: datetime | None, wait_seconds: float = 0) -> list[Collected]:
    """Take the answers of these tasks from the agents' own records. A result that was stored once is final.
    Waits a little for records that Claude Code is still writing."""
    project = Path(rnd.project)
    stop = time.monotonic() + wait_seconds
    answers_dir(rnd).mkdir(parents=True, exist_ok=True, mode=0o700)
    while True:
        runs = transcripts.agent_runs(project, rnd.session_id)
        by_prompt: dict[str, transcripts.AgentRun] = {}
        for run in sorted(runs, key=lambda r: r.started):
            by_prompt.setdefault(run.prompt, run)  # only the first start of a task counts
        results: list[Collected] = []
        for task in wanted:
            done = stored(rnd, task.task)
            if done is None:
                done = judge(rnd, task, by_prompt.get(task.prompt(rnd.session_dir)), deadline)
            results.append(done)
        waiting = [r for r in results if r.status == "missing"]
        past = deadline is not None and utcnow() > deadline and not rnd.relaxed_clock
        if not waiting or time.monotonic() >= stop or past:
            break
        time.sleep(3)
    for result in results:
        if result.status == "missing" and (deadline is None or utcnow() <= deadline or rnd.relaxed_clock):
            continue  # may still come: not stored, so a later collect looks again
        if result.status == "missing":
            result.status, result.reason = "late", "no answer by the time for this step"
        if stored(rnd, result.task) is None:
            write_new(answers_dir(rnd) / f"{result.task}.json", json.dumps(asdict(result), sort_keys=True) + "\n")
    return results


def break_off(rnd: Round) -> int:
    """After a round broke off: every task that was handed out and has no stored result gets one now. Its agent
    ran in the session that broke off (or never ran); a task is started once, so it is not run again."""
    answers_dir(rnd).mkdir(parents=True, exist_ok=True, mode=0o700)
    count = 0
    for name, task in tasks.load(rnd.session_dir).items():
        if stored(rnd, name) is None:
            got = Collected(
                name, task.agent, "rejected", "the round broke off before this answer was taken", run=task.run,
                task_sha256=task.sha256, stand_in=bool(task.stand_in),
            )  # fmt: skip
            write_new(answers_dir(rnd) / f"{name}.json", json.dumps(asdict(got), sort_keys=True) + "\n")
            count += 1
    return count


def step_tasks(rnd: Round, prefix: str) -> list[Task]:
    return [t for name, t in tasks.load(rnd.session_dir).items() if name.startswith(prefix)]


def summary_line(results: list[Collected]) -> str:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return ", ".join(f"{n} {status}" for status, n in sorted(counts.items())) or "nothing to collect"


def session_json(rnd: Round) -> dict[str, Any]:
    return json.loads((rnd.session_dir / "session.json").read_text(encoding="utf-8"))


def amsterdam_day(now: datetime) -> date:
    from ..funds.calendar import AMSTERDAM

    return now.astimezone(AMSTERDAM).date()


def new_round(mode: str, session_id: str, project: Path, now: datetime, **options: Any) -> Round:
    start = now.astimezone(UTC).replace(microsecond=0)
    return Round(
        mode, amsterdam_day(now), session_id, start, start, str(project), first_session_id=session_id, **options
    )


def agent_entry(got: Collected) -> dict[str, Any]:
    """An agent's line in a log record: what ran, read from its own record, next to what its file says."""
    role = roles.BY_NAME[got.agent]
    entry: dict[str, Any] = {
        "role": got.agent.removeprefix("bobby-"),
        "agent_file_sha256": sha256_hex(roles.render(role).encode("utf-8")),
        "task_sha256": got.task_sha256,
        "model": got.model or "unknown",
        "effort": got.effort or "unknown",
        "claude_code": got.claude_code or "unknown",
        "file_model": role.model,
        "file_effort": role.effort,
        "substituted": got.substituted,
    }
    if got.run is not None:
        entry["run"] = got.run
    if got.stand_in:
        entry["stand_in"] = True
    return entry

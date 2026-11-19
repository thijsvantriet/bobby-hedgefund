#!/usr/bin/env python3
"""Checks that Claude Code runs by itself during a Bobby Hedgefund round (docs/decisions/0003 point 3, 0009 point 3).

One file, six checks, chosen by the first argument:

    fence          named in every Bobby agent file: the agent may read only inside the session folder
    agent-start    before an agent is started: only with a prepared task text, once, with the right agent
    no-edits       before a file is changed: the leading session changes no files while a round is active
    hands-off      before an agent is messaged or stopped: not while a round is active
    round-commands before a command line is run: during a round only the round's own commands
    session-start  notes how a session began (new, cleared, resumed), for the fresh-session check

Each reads Claude Code's description of the event from standard input. A refusal is exit code 2 with the reason
on standard error; anything else is exit code 0. (Claude Code blocks a tool only on exit code 2.)

**Outside a round these checks do nothing.** A round is active while the file `round-active.json` exists in the
data folder, names this very session and is younger than 90 minutes. The one exception is the fence: it exists
only inside a Bobby agent, and such an agent has no business reading anything when no round is active.

**They guard against slips, not against a session that sets out to cheat.** The leading session has a command
line; during a round it is held to the round's own commands, but these checks are files it could change between
rounds. What makes cheating visible afterwards is the copy of the whole conversation.

Standard library only, and nothing is imported from the project: a check must work whatever state the code is in.
When the fence cannot tell, or fails in any way, it refuses.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

MARKER = "round-active.json"
MAX_AGE_SECONDS = 90 * 60
READ_TOOLS = ("Read", "Grep", "Glob")
HANDBACK = "SubagentHandback"  # how an agent hands its report back; it reads nothing and reaches nothing
EDIT_TOOLS = ("Write", "Edit", "NotebookEdit", "MultiEdit")
# The command lines the leading session may run during a round: the round's own commands, one at a time.
ROUND_COMMAND = re.compile(r"^\s*(?:uv run (?:--no-sync )?)?bobby-session [A-Za-z0-9 ./:=_\"'-]{1,300}\s*$")


def data_dir() -> Path:
    return Path(os.environ.get("BOBBY_DATA_DIR") or Path.home() / "bobby-hedgefund-data")


def marker() -> dict | None:
    """The active round, or None. A marker that is unreadable, incomplete, too old or dated in the future counts
    as no round, and so does anything that goes wrong while reading it."""
    try:
        path = data_dir() / MARKER
        if path.stat().st_size > 100_000:
            return None
        found = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(found, dict):
            return None
        if not all(isinstance(found.get(k), str) and found[k] for k in ("session_id", "session_dir", "round_dir")):
            return None
        started = float(found["started"])
        age = time.time() - started
        if not math.isfinite(started) or not 0 <= age <= MAX_AGE_SECONDS:
            return None
        return found
    except Exception:
        return None


def ours(event: dict) -> dict | None:
    """The active round, when it is a round of the session this event comes from."""
    active = marker()
    return active if active is not None and event.get("session_id") == active["session_id"] else None


def inside(path: str, folder: str) -> bool:
    """Is `path`, with every link followed, inside `folder`? Only a full path counts."""
    if not path or "\x00" in path or not Path(path).is_absolute():
        return False
    real = os.path.realpath(path)
    base = os.path.realpath(folder)
    return real == base or real.startswith(base + os.sep)


def note(active: dict | None, line: dict) -> None:
    """Keep a refusal for the round's records. Never fails."""
    try:
        if active:
            folder = Path(active["round_dir"])
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / "refusals.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **line}) + "\n")
    except Exception:
        pass


def leaves(pattern: str) -> bool:
    """Could this search pattern reach outside the folder it is used in?"""
    parts = pattern.replace("\\", "/").split("/")
    return pattern.startswith(("/", "~")) or ".." in parts or "{" in pattern


def fence(event: dict) -> tuple[int, str]:
    active = marker()
    tool = str(event.get("tool_name") or "")
    given = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    who = str(event.get("agent_type") or "")

    def refuse(why: str, path: str = "") -> tuple[int, str]:
        note(active, {"check": "fence", "agent": who, "tool": tool, "path": path[:300], "why": why})
        return 2, f"Refused: {why}. You may only read files inside the session folder named in your task file."

    if tool == HANDBACK:
        return 0, ""
    if active is None:
        return refuse("no round is active")
    if tool not in READ_TOOLS:
        return refuse(f"the tool {tool[:40] or '?'} is not one of {', '.join(READ_TOOLS)}")
    if tool == "Read":
        path = str(given.get("file_path") or "")
    else:
        path = str(given.get("path") or "")
        if not path:
            return refuse("a search must name a folder inside the session folder")
        patterns = [str(given.get("glob") or "")] + ([str(given.get("pattern") or "")] if tool == "Glob" else [])
        if any(leaves(p) for p in patterns if p):
            return refuse("a search pattern may not leave its folder")
    session_dir = active["session_dir"]
    if not inside(path, session_dir):
        return refuse("that is outside the session folder (give the full path)", path)
    # Inside the folder, a few places belong to one fund only, so that one fund's manager cannot read another's
    # holdings, tasks or debate, and nobody reads the list of all tasks.
    rel = list(Path(os.path.relpath(os.path.realpath(path), os.path.realpath(session_dir))).parts)
    if rel[0] == "tasks":
        if tool != "Read" or len(rel) != 2:
            return refuse("the folder of tasks is not searched; read your own task file", path)
        try:
            owners = [t["agent"] for t in _tasks(session_dir) if t["file"] == f"tasks/{rel[1]}"]
        except Exception:
            owners = []
        if owners != [who] and not active.get("stand_ins"):
            return refuse("that is not your own task file", path)
    elif rel[:2] in (["round", "funds"], ["round", "debate"]):
        fund = who.removeprefix("bobby-pm-") if who.startswith("bobby-pm-") else ""
        allowed = (rel[1] == "funds" and tool == "Read" and len(rel) == 3 and rel[2] == f"{fund}.md" and fund) or (
            rel[1] == "debate" and who in ("bobby-pm-debate", "bobby-bull", "bobby-bear")
        )
        if not allowed:
            return refuse("that belongs to another fund", path)
    elif rel[0] == "round" and len(rel) == 1 and tool != "Read":
        return refuse("search inside round/reports, not across round/", path)
    return 0, ""


def _tasks(session_dir: str) -> list[dict]:
    out = []
    seen = set()
    with open(Path(session_dir) / "tasks" / "index.jsonl", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                task = json.loads(line)
                if task["task"] not in seen:  # the first line for a task is the script's
                    seen.add(task["task"])
                    out.append(task)
    return out


def agent_start(event: dict) -> tuple[int, str]:
    active = ours(event)
    if active is None:
        return 0, ""  # not a round of this session: nothing to do with us
    given = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    prompt, agent = str(given.get("prompt") or ""), str(given.get("subagent_type") or "")

    def refuse(why: str) -> tuple[int, str]:
        note(active, {"check": "agent-start", "agent": agent[:60], "why": why})
        return 2, (
            f"Refused: {why}. While a round is active an agent is started only with the exact sentence the round's "
            "script printed for a task, with that task's agent, once, and without choosing a model or an effort."
        )

    if event.get("agent_id"):
        return refuse("an agent may not start another agent during a round")
    try:
        tasks = _tasks(active["session_dir"])
    except Exception:
        return refuse("the list of prepared tasks cannot be read")
    session_dir = Path(active["session_dir"])
    wanted = [t for t in tasks if prompt == f"Read the file {session_dir / t['file']} and do exactly what it says."]
    if not wanted:
        return refuse("this is not the text of a prepared task")
    task = wanted[0]
    try:
        unchanged = hashlib.sha256((session_dir / task["file"]).read_bytes()).hexdigest() == task["sha256"]
    except OSError:
        unchanged = False
    if not unchanged:
        return refuse("the task file is not as the script wrote it")
    for field in ("isolation", "resume", "name", "team_name"):
        if given.get(field):
            return refuse(f"a start may not set '{field}'")
    starts = Path(active["round_dir"]) / "starts.jsonl"
    try:
        earlier = [json.loads(line) for line in starts.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        earlier = []
    except ValueError:
        return refuse("the list of started tasks cannot be read")
    times = sum(s.get("task") == task["task"] for s in earlier)
    stand_in = task.get("stand_in") or {}
    extra = {k: given[k] for k in ("model", "effort") if given.get(k)}
    if stand_in:
        # The one case in which the agent files cannot be used (they were made in this very session): the script
        # prepared a stand-in, and says with which agent type, model and effort it must be started. Only a
        # try-out may do this; the round's script says so in the marker.
        prepared = {k: stand_in[k] for k in ("model", "effort") if stand_in.get(k)}
        if not active.get("stand_ins"):
            return refuse("stand-in agents are for a try-out only")
        if agent != stand_in.get("subagent_type") or extra != prepared:
            return refuse("a stand-in must be started exactly as the script prepared it")
        if times:
            return refuse("this task was started already; only the first start counts")
    else:
        if agent != task["agent"]:
            return refuse(f"this task belongs to the agent {task['agent']}")
        fallback = active.get("fallback") if isinstance(active.get("fallback"), dict) else {}
        allowed = fallback.get(task["task"])  # set by the script when the task's model could not be used
        if times == 0 and extra:
            return refuse("a model or an effort may not be chosen by hand")
        if times == 1 and (not allowed or extra != {"model": allowed}):
            return refuse("this task was started already; only the first start counts")
        if times > 1:
            return refuse("this task was started already; only the first start counts")
    try:
        starts.parent.mkdir(parents=True, exist_ok=True)
        with open(starts, "a", encoding="utf-8") as fh:
            line = {"task": task["task"], "agent": agent, "time": time.time(), **extra}
            fh.write(json.dumps({**line, "tool_use_id": event.get("tool_use_id")}) + "\n")
    except OSError:
        return refuse("the start could not be noted")
    return 0, ""


def no_edits(event: dict) -> tuple[int, str]:
    active = ours(event)
    tool = str(event.get("tool_name") or "")
    if active is None or tool not in EDIT_TOOLS:
        return 0, ""
    note(active, {"check": "no-edits", "tool": tool, "agent": str(event.get("agent_type") or "")[:60]})
    return 2, (
        "Refused: while a round is active the session changes no files; the round's scripts write everything. "
        "If the round is over or broke off, run `bobby-session end` first."
    )


def hands_off(event: dict) -> tuple[int, str]:
    active = ours(event)
    tool = str(event.get("tool_name") or "")
    if active is None:
        return 0, ""
    if tool == "TaskStop" and active.get("may_stop"):
        return 0, ""  # the script said so: the time for a step is over and its late agents may be stopped
    note(active, {"check": "hands-off", "tool": tool[:40]})
    return 2, (
        "Refused: while a round is active an agent is not sent a message and not stopped; it answers its one task. "
        "Agents may be stopped only after the round's script says the time for their step is over."
    )


def round_commands(event: dict) -> tuple[int, str]:
    active = ours(event)
    if active is None or event.get("agent_id"):
        return 0, ""
    given = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    command = str(given.get("command") or "")
    if ROUND_COMMAND.match(command) and "\n" not in command:
        return 0, ""
    note(active, {"check": "round-commands", "why": "another command line during a round"})
    return 2, (
        "Refused: while a round is active the command line is only for the round's own commands, one at a time: "
        "`bobby-session <step>`. If the round is over or broke off, run `bobby-session end` (or "
        "`bobby-session end --abort`) first."
    )


def session_start(event: dict) -> tuple[int, str]:
    """Note how this session began. Never refuses and never fails: it must not get in the way of any session."""
    try:
        session = str(event.get("session_id") or "")
        if session and len(session) < 100 and all(c.isalnum() or c in "-_" for c in session):
            folder = data_dir() / "claude-sessions"
            folder.mkdir(parents=True, exist_ok=True)
            line = {"source": event.get("source"), "time": time.time(), "transcript_path": event.get("transcript_path")}
            with open(folder / f"{session}.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line) + "\n")
    except Exception:
        pass
    return 0, ""


CHECKS = {
    "fence": fence,
    "agent-start": agent_start,
    "no-edits": no_edits,
    "hands-off": hands_off,
    "round-commands": round_commands,
    "session-start": session_start,
}


def main(argv: list[str]) -> int:
    name = argv[1] if len(argv) > 1 else ""
    check = CHECKS.get(name)
    if check is None:
        print(f"unknown check {name[:40]!r}", file=sys.stderr)
        return 0  # a wrong setting must not block every tool of a session
    try:
        event = json.loads(sys.stdin.read() or "{}")
        if not isinstance(event, dict):
            raise ValueError
        code, message = check(event)
    except BaseException as exc:
        if name == "fence":  # the fence refuses whatever went wrong, before anything else is tried
            print(f"Refused: the reading check failed ({type(exc).__name__}).", file=sys.stderr)
            return 2
        try:  # the others: inside a round of this session they refuse, everywhere else they stand aside
            event_ = event if isinstance(locals().get("event"), dict) else {}  # type: ignore[name-defined]
            if ours(event_) is not None:
                print(f"Refused: the check '{name}' failed ({type(exc).__name__}).", file=sys.stderr)
                return 2
        except BaseException:
            pass
        return 0
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    try:
        result = main(sys.argv)
    except BaseException:
        result = 2 if len(sys.argv) > 1 and sys.argv[1] == "fence" else 0
    sys.exit(result)

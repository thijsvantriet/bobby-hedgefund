#!/usr/bin/env python3
"""Checks that Claude Code runs by itself during a Bobby Hedgefund round (docs/decisions/0003 point 3, 0009 point 3).

One file, four checks, chosen by the first argument:

    fence          named in every Bobby agent file: the agent may read only inside the session folder
    agent-start    before an agent is started: only with a prepared task text, once, with the right agent
    no-edits       before a file is changed: the leading session changes no files while a round is active
    session-start  notes how a session began (new, cleared, resumed), for the fresh-session check

Each reads Claude Code's description of the event from standard input. A refusal is exit code 2 with the reason
on standard error; anything else is exit code 0.

**Outside a round these checks do nothing.** A round is active while the file `round-active.json` exists in the
data folder, names this very session and is younger than 90 minutes. The one exception is the fence: it exists
only inside a Bobby agent, and such an agent has no business reading anything when no round is active.

Standard library only, and nothing is imported from the project: a check must work whatever state the code is in.
When a check cannot tell, it refuses; it never guesses.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

MARKER = "round-active.json"
MAX_AGE_SECONDS = 90 * 60
READ_TOOLS = ("Read", "Grep", "Glob")
EDIT_TOOLS = ("Write", "Edit", "NotebookEdit", "MultiEdit")


def data_dir() -> Path:
    return Path(os.environ.get("BOBBY_DATA_DIR") or Path.home() / "bobby-hedgefund-data")


def marker() -> dict | None:
    """The active round, or None. A marker that is unreadable, incomplete or too old counts as no round."""
    try:
        found = json.loads((data_dir() / MARKER).read_text(encoding="utf-8"))
        if not isinstance(found, dict):
            return None
        if not all(isinstance(found.get(k), str) and found[k] for k in ("session_id", "session_dir", "round_dir")):
            return None
        if time.time() - float(found["started"]) > MAX_AGE_SECONDS:
            return None
        return found
    except (OSError, ValueError, KeyError, TypeError):
        return None


def inside(path: str, folder: str, cwd: str) -> bool:
    """Is `path`, with every link followed, inside `folder`?"""
    if not path:
        return False
    full = Path(path) if Path(path).is_absolute() else Path(cwd or "/nonexistent") / path
    real = os.path.realpath(full)
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
    except OSError:
        pass


def fence(event: dict) -> tuple[int, str]:
    active = marker()
    tool = str(event.get("tool_name") or "")
    given = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    who = str(event.get("agent_type") or "")

    def refuse(why: str, path: str = "") -> tuple[int, str]:
        note(active, {"check": "fence", "agent": who, "tool": tool, "path": path, "why": why})
        return 2, f"Refused: {why}. You may only read files inside the session folder named in your task file."

    if active is None:
        return refuse("no round is active")
    if tool not in READ_TOOLS:
        return refuse(f"the tool {tool or '?'} is not one of {', '.join(READ_TOOLS)}")
    cwd = str(event.get("cwd") or "")
    if tool == "Read":
        path = str(given.get("file_path") or "")
    else:
        path = str(given.get("path") or "")
        if not path:
            return refuse("a search must name a folder inside the session folder")
        pattern = str(given.get("pattern") or "")
        if tool == "Glob" and (Path(pattern).is_absolute() or ".." in pattern.replace("\\", "/").split("/")):
            return refuse("a search pattern may not leave its folder", pattern)
    if not inside(path, active["session_dir"], cwd):
        return refuse("that is outside the session folder", path)
    return 0, ""


def _tasks(session_dir: str) -> list[dict]:
    out = []
    with open(Path(session_dir) / "tasks" / "index.jsonl", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def agent_start(event: dict) -> tuple[int, str]:
    active = marker()
    if active is None or event.get("session_id") != active["session_id"]:
        return 0, ""  # not a round of this session: nothing to do with us
    given = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    prompt, agent = str(given.get("prompt") or ""), str(given.get("subagent_type") or "")

    def refuse(why: str) -> tuple[int, str]:
        note(active, {"check": "agent-start", "agent": agent, "why": why})
        return 2, (
            f"Refused: {why}. While a round is active an agent is started only with the exact sentence the round's "
            "script printed for a task, with that task's agent, once, and without choosing a model or an effort."
        )

    if event.get("agent_id"):
        return refuse("an agent may not start another agent during a round")
    try:
        tasks = _tasks(active["session_dir"])
    except (OSError, ValueError):
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
    stand_in = task.get("stand_in") or {}
    extra = {k: given[k] for k in ("model", "effort") if given.get(k)}
    if stand_in:
        # The one case in which the agent files cannot be used (they were made in this very session): the script
        # prepared a stand-in, and says with which agent type, model and effort it must be started.
        if agent != stand_in.get("subagent_type") or extra != {
            k: stand_in[k] for k in ("model", "effort") if stand_in.get(k)
        }:
            return refuse("a stand-in must be started exactly as the script prepared it")
    else:
        allowed = active.get("fallback", {}).get(task["task"])  # set by the script when a model could not be used
        if agent != task["agent"]:
            return refuse(f"this task belongs to the agent {task['agent']}")
        if extra and extra != ({"model": allowed} if allowed else {}):
            return refuse("a model or an effort may not be chosen by hand")
    starts = Path(active["round_dir"]) / "starts.jsonl"
    try:
        earlier = [json.loads(line) for line in starts.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        earlier = []
    except ValueError:
        return refuse("the list of started tasks cannot be read")
    again_allowed = (
        bool(active.get("fallback", {}).get(task["task"])) and sum(s["task"] == task["task"] for s in earlier) == 1
    )
    if any(s["task"] == task["task"] for s in earlier) and not again_allowed:
        return refuse("this task was started already; only the first start counts")
    try:
        starts.parent.mkdir(parents=True, exist_ok=True)
        with open(starts, "a", encoding="utf-8") as fh:
            line = {
                "task": task["task"],
                "agent": agent,
                "time": time.time(),
                "tool_use_id": event.get("tool_use_id"),
                **extra,
            }
            fh.write(json.dumps(line) + "\n")
    except OSError:
        return refuse("the start could not be noted")
    return 0, ""


def no_edits(event: dict) -> tuple[int, str]:
    active = marker()
    if active is None or event.get("session_id") != active["session_id"]:
        return 0, ""
    tool = str(event.get("tool_name") or "")
    if tool not in EDIT_TOOLS:
        return 0, ""
    note(active, {"check": "no-edits", "tool": tool, "agent": str(event.get("agent_type") or "")})
    return 2, (
        "Refused: while a round is active the session changes no files; the round's scripts write everything. "
        "If the round is over or broke off, run `bobby-session end` first."
    )


def session_start(event: dict) -> tuple[int, str]:
    """Note how this session began. Never refuses and never fails: it must not get in the way of any session."""
    try:
        session = str(event.get("session_id") or "")
        if session and all(c.isalnum() or c in "-_" for c in session):
            folder = data_dir() / "claude-sessions"
            folder.mkdir(parents=True, exist_ok=True)
            line = {"source": event.get("source"), "time": time.time(), "transcript_path": event.get("transcript_path")}
            with open(folder / f"{session}.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line) + "\n")
    except OSError:
        pass
    return 0, ""


CHECKS = {"fence": fence, "agent-start": agent_start, "no-edits": no_edits, "session-start": session_start}


def main(argv: list[str]) -> int:
    name = argv[1] if len(argv) > 1 else ""
    check = CHECKS.get(name)
    if check is None:
        print(f"unknown check {name!r}", file=sys.stderr)
        return 0  # a wrong setting must not block every tool of a session
    try:
        event = json.loads(sys.stdin.read() or "{}")
        if not isinstance(event, dict):
            raise ValueError
    except ValueError:
        event = None
    if event is None:
        if name == "fence":
            print("Refused: the description of this tool use cannot be read.", file=sys.stderr)
            return 2
        return 0
    try:
        code, message = check(event)
    except Exception as exc:  # a bug in a check: inside a round it refuses, outside one it stands aside
        active = marker()
        if name == "fence" or (active is not None and event.get("session_id") == active["session_id"]):
            print(f"Refused: the check '{name}' failed ({type(exc).__name__}).", file=sys.stderr)
            return 2
        return 0
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))

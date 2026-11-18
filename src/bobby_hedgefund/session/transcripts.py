"""Reading Claude Code's own records of a session (docs/decisions/0009, points 2 and 3; docs/SPEC.md section 3).

Every agent run has a file of its own, `<session>/subagents/agent-<id>.jsonl`, next to the session's main record,
with a small file that names the agent type. From it the script takes, without anybody retyping anything:
the one message the agent was started with, the tools it used, the exact model and effort of every answer, how
much text went in and out, and the final answer.

The layout is Claude Code's and can change with a version. Anything that is not as expected makes the record
unreadable for us; the script then refuses it and never guesses.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

READ_TOOLS = ("Read", "Grep", "Glob")
# How an agent made from a file hands its report back in this version of Claude Code: not as a last text, but as
# the `message` of a call to this tool. It reads nothing and reaches nothing; it is the answer itself.
HANDBACK = "SubagentHandback"
TOKEN_KINDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


class RecordError(Exception):
    pass


@dataclass
class ToolUse:
    name: str
    path: str  # the file or folder it was pointed at ("" when none was given)
    pattern: str = ""


@dataclass
class AgentRun:
    agent_id: str
    agent_type: str
    path: Path
    prompt: str  # the one message it was started with
    incoming: int  # how many messages it received (tool results not counted); more than one: somebody added to it
    tools: list[ToolUse] = field(default_factory=list)
    models: list[str] = field(default_factory=list)  # every model that answered, in order of first use
    efforts: list[str] = field(default_factory=list)
    version: str = ""
    tokens: dict[str, int] = field(default_factory=dict)
    answers: int = 0  # the number of model calls
    final_text: str = ""
    finished: bool = False  # its last answer ended the turn
    started: str = ""
    ended: str = ""


def project_folder(cwd: Path) -> Path:
    """Where Claude Code keeps the records of sessions started in `cwd`."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def _lines(path: Path) -> list[dict[str, Any]]:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                if raw.strip():
                    try:
                        line = json.loads(raw)
                    except ValueError:
                        continue  # a line that is still being written
                    if isinstance(line, dict):
                        out.append(line)
    except OSError as exc:
        raise RecordError(f"a session record cannot be read ({type(exc).__name__})") from None
    return out


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _is_tool_result(content: Any) -> bool:
    return isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)


def read_run(path: Path) -> AgentRun:
    """One agent run, from its own record."""
    meta_path = path.with_name(path.name.removesuffix(".jsonl") + ".meta.json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        agent_type = str(meta["agentType"])
    except (OSError, ValueError, KeyError, TypeError):
        raise RecordError("the agent's record does not say which agent it is") from None
    lines = _lines(path)
    users = [ln for ln in lines if ln.get("type") == "user" and isinstance(ln.get("message"), dict)]
    # Messages Claude Code adds by itself (a reminder of how to hand the report back) are marked as such and
    # do not count as something that was said to the agent.
    typed = [ln for ln in users if not _is_tool_result(ln["message"].get("content")) and not ln.get("isMeta")]
    if not typed:
        raise RecordError("the agent's record holds no starting message")
    run = AgentRun(
        agent_id=path.name.removeprefix("agent-").removesuffix(".jsonl"),
        agent_type=agent_type,
        path=path,
        prompt=_text(typed[0]["message"].get("content")),
        incoming=len(typed),
        started=str(typed[0].get("timestamp") or ""),
    )
    # One answer of the model is spread over several lines that share its id; its counts are on each of them.
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for line in lines:
        if line.get("type") != "assistant" or not isinstance(line.get("message"), dict):
            continue
        message = line["message"]
        key = str(message.get("id") or line.get("uuid"))
        if key not in by_id:
            order.append(key)
            by_id[key] = {"text": "", "usage": {}, "stop": None, "handback": None}
        entry = by_id[key]
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                entry["text"] += str(block.get("text", ""))
            elif block.get("type") == "tool_use" and block.get("name") == HANDBACK:
                given = _dict(block.get("input"))
                entry["handback"] = str(given.get("message") or "")
            elif block.get("type") == "tool_use":
                given = _dict(block.get("input"))
                where = str(given.get("file_path") or given.get("path") or given.get("notebook_path") or "")
                run.tools.append(ToolUse(str(block.get("name")), where, str(given.get("pattern") or "")))
        if isinstance(message.get("usage"), dict):
            entry["usage"] = message["usage"]
        entry["stop"] = message.get("stop_reason") or entry["stop"]
        model, effort = str(message.get("model") or ""), str(line.get("effort") or "")
        if model and model not in run.models:
            run.models.append(model)
        if effort and effort not in run.efforts:
            run.efforts.append(effort)
        run.version = str(line.get("version") or run.version)
        run.ended = str(line.get("timestamp") or run.ended)
    run.answers = len(order)
    for kind in TOKEN_KINDS:
        run.tokens[kind] = sum(int(by_id[k]["usage"].get(kind) or 0) for k in order)
    if order:
        last = by_id[order[-1]]
        handed = [by_id[k]["handback"] for k in order if by_id[k]["handback"] is not None]
        if handed:  # the report is what was handed back (the last time, should there be more than one)
            run.final_text = handed[-1]
            run.finished = True
        else:
            run.final_text = last["text"]
            run.finished = last["stop"] == "end_turn"
    return run


def agent_runs(project: Path, session_id: str) -> list[AgentRun]:
    """Every agent run of a session that can be read. A record that cannot be read yet is left out."""
    folder = project / session_id / "subagents"
    runs: list[AgentRun] = []
    for path in sorted(folder.glob("agent-*.jsonl")) if folder.is_dir() else []:
        try:
            runs.append(read_run(path))
        except RecordError:
            continue
    return runs


def outside(run: AgentRun, session_dir: Path) -> list[str]:
    """What an agent did that it may not do: a tool other than reading files, or a path outside the session
    folder (links followed). Empty when its record is clean. This is the second layer behind the tool list and
    the reading check, and the only one when the agent files could not be used."""
    base = os.path.realpath(session_dir)
    wrong: list[str] = []
    for use in run.tools:
        if use.name not in READ_TOOLS:
            wrong.append(f"used the tool {use.name}")
            continue
        if not use.path:
            wrong.append(f"{use.name} without a folder")
            continue
        real = os.path.realpath(use.path)
        if not (real == base or real.startswith(base + os.sep)) or not Path(use.path).is_absolute():
            wrong.append(f"{use.name} outside the session folder")
        if use.name == "Glob" and (Path(use.pattern).is_absolute() or ".." in use.pattern.split("/")):
            wrong.append("Glob with a pattern that leaves its folder")
    return wrong


def main_usage(project: Path, session_id: str, since: str) -> dict[str, int]:
    """What the leading session itself used from `since` (a time as in the records) on."""
    path = project / f"{session_id}.jsonl"
    by_id: dict[str, dict[str, Any]] = {}
    for line in _lines(path) if path.exists() else []:
        message = _dict(line.get("message"))
        recent = str(line.get("timestamp") or "") >= since
        if line.get("type") == "assistant" and recent and isinstance(message.get("usage"), dict):
            by_id[str(message.get("id") or line.get("uuid"))] = message["usage"]
    totals = {kind: sum(int(u.get(kind) or 0) for u in by_id.values()) for kind in TOKEN_KINDS}
    return {**totals, "answers": len(by_id)}

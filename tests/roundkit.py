"""Helpers for the tests of the daily round: a made-up data folder, and made-up records of agent runs in the
layout Claude Code writes them (the "recorded answers")."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from fundkit import COMPANIES, MON, store_day, store_splits
from test_session_prepare import store_filing, universe_file

from bobby_hedgefund.archive.store import Archive, iso
from bobby_hedgefund.session import roles
from bobby_hedgefund.session.tasks import Task

FLAT = {"AAA": (10.0, 10.0), "BBB": (20.0, 20.0), "CCC": (5.0, 5.0), "DDD": (2.0, 2.0), "XBI": (100.0, 100.0)}
WED_8 = datetime(2027, 2, 3, 8, 0, tzinfo=UTC)
THU_8 = datetime(2027, 2, 4, 8, 0, tzinfo=UTC)


def make_data(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A data folder with a universe, prices and one new filing; a clean project folder; a folder for Claude
    Code's records. Returns (data, project folder, records folder)."""
    data = tmp_path / "data"
    universe_file(data)
    store_splits(data / "prices", [])
    for day in (date(2027, 1, 28), date(2027, 1, 29), MON):
        store_day(data / "prices", day, FLAT)
    store_day(data / "prices", date(2027, 2, 2), FLAT)  # stored on Wednesday at 06:00
    evening = datetime(2027, 2, 2, 23, tzinfo=UTC)
    main = "<p>The primary endpoint of the trial was met. Cash was $245.3 million.</p>"
    store_filing(
        data, 101, "0000000101-27-000001", "8-K", "2027-02-02", evening, items="Regulation FD Disclosure", main=main
    )
    fresh_jobs(data, WED_8)
    cwd = tmp_path / "project"
    cwd.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.name", "t"], ["config", "user.email", ""]):
        subprocess.run(["git", "-C", str(cwd), *args], check=True)
    (cwd / "README.md").write_text("code\n")
    subprocess.run(["git", "-C", str(cwd), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(cwd), "commit", "-qm", "code"], check=True)
    return data, cwd, tmp_path / "claude-records"


def fresh_jobs(data: Path, now: datetime) -> None:
    """Last night's jobs ran: a good run in each saved-files list shortly before `now`."""
    for name, source in (("archive", "nasdaq-symdir"), ("prices", "massive-daily")):
        line = {
            "kind": "run",
            "ts": iso(now - timedelta(hours=2)),
            "run": f"night-{now:%d}",
            "source": source,
            "status": "ok",
        }
        with Archive(data / name) as archive:
            archive.append(line)


def began(data: Path, session_id: str, source: str = "startup") -> None:
    """What the session-start check would have noted for this session."""
    folder = data / "claude-sessions"
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{session_id}.jsonl", "a") as fh:
        fh.write(json.dumps({"source": source, "time": 0}) + "\n")


def block(answer: dict[str, Any] | str) -> str:
    body = answer if isinstance(answer, str) else json.dumps(answer, indent=1)
    return f"My answer.\n\n```json\n{body}\n```\n"


def agent_run(
    records: Path,
    session_id: str,
    session_dir: Path,
    task: Task,
    answer: dict[str, Any] | str,
    *,
    at: datetime,
    seconds: int = 60,
    model: str | None = None,
    effort: str | None = None,
    agent_type: str | None = None,
    reads: list[tuple[str, str]] | None = None,
    extra_message: str | None = None,
    extra_kind: str = "coordinator",
    prompt: str | None = None,
    handback: bool = True,
    finished: bool = True,
) -> None:
    """Write the record of one agent run as Claude Code would: the starting message, its reading, its answers."""
    role = roles.BY_NAME[task.agent]
    folder = records / session_id / "subagents"
    folder.mkdir(parents=True, exist_ok=True)
    agent_id = f"a{abs(hash((task.task, at.isoformat()))) % 10**12:012d}"
    common = {"isSidechain": True, "agentId": agent_id, "sessionId": session_id, "version": "9.9.9"}

    def stamp(offset: int) -> str:
        return (at + timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def assistant(msg: str, blocks: list[dict[str, Any]], stop: str, offset: int) -> dict[str, Any]:
        usage = {
            "input_tokens": 10,
            "cache_creation_input_tokens": 200,
            "cache_read_input_tokens": 3000,
            "output_tokens": 50,
        }
        message = {
            "id": msg,
            "role": "assistant",
            "model": model or role.model,
            "content": blocks,
            "stop_reason": stop,
            "usage": usage,
        }
        return {
            **common,
            "type": "assistant",
            "message": message,
            "effort": effort or role.effort,
            "timestamp": stamp(offset),
        }

    lines: list[dict[str, Any]] = [
        {
            **common,
            "type": "user",
            "message": {"role": "user", "content": prompt or task.prompt(session_dir)},
            "timestamp": stamp(0),
        }
    ]
    if handback:
        reminder = "<system-reminder>\nYour final report is delivered through the hand-back tool.</system-reminder>"
        lines.append(
            {
                **common,
                "type": "user",
                "isMeta": True,
                "message": {"role": "user", "content": reminder},
                "timestamp": stamp(0),
            }
        )
    used = reads if reads is not None else [("Read", str(session_dir / task.file))]
    for i, (tool, path) in enumerate(used):
        given = (
            {"file_path": path}
            if tool == "Read"
            else {"path": path, "pattern": "x"}
            if tool in ("Grep", "Glob")
            else {"command": path}
        )
        call = {"type": "tool_use", "id": f"t{i}", "name": tool, "input": given}
        lines.append(assistant(f"m{i}", [call], "tool_use", 1 + i))
        result = [{"type": "tool_result", "tool_use_id": f"t{i}", "content": "text"}]
        lines.append(
            {**common, "type": "user", "message": {"role": "user", "content": result}, "timestamp": stamp(1 + i)}
        )
    if extra_message and extra_kind == "queued":  # from another agent: Claude Code stores it as a queued command
        attached = {"type": "queued_command", "prompt": extra_message}
        lines.append({**common, "type": "attachment", "attachment": attached, "timestamp": stamp(5)})
    elif extra_message:
        said = {**common, "type": "user", "message": {"role": "user", "content": extra_message}, "timestamp": stamp(5)}
        if extra_kind == "coordinator":  # from the leading session: a marked line that names where it came from
            said |= {"isMeta": True, "origin": {"kind": "coordinator"}}
        lines.append(said)
    text = answer if isinstance(answer, str) and "```" in answer else block(answer)
    if finished and handback:
        call = {"type": "tool_use", "id": "hb", "name": "SubagentHandback", "input": {"message": text}}
        lines.append(
            assistant("final", [{"type": "text", "text": "Handing back."}], "tool_use", seconds)
        )  # same answer, two lines
        lines.append(assistant("final", [call], "tool_use", seconds))
    elif finished:
        lines.append(assistant("final", [{"type": "text", "text": text}], "end_turn", seconds))
    (folder / f"agent-{agent_id}.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
    meta = {"agentType": agent_type or task.agent, "toolUseId": f"toolu_{agent_id}"}
    (folder / f"agent-{agent_id}.meta.json").write_text(json.dumps(meta))


SOURCE = [{"n": 2, "summary": "The company reported that the main goal of its trial was met."}]
THESIS = {
    "claim": "The drug works in this disease and the market has not caught up with the result.",
    "edge": "The result was on the main goal as it was written down in advance.",
    "catalyst": "The company files for approval",
    "catalyst_date": "2027-06-01",
    "probability": "60%",
    "risks": "The safety data are thin.",
    "sell_if": "The filing for approval is delayed past June.",
}


def section(cik: int, forecast: bool = False, **more: Any) -> dict[str, Any]:
    made = []
    if forecast:
        made = [
            {
                "event": "The company files for approval of its lead drug",
                "event_kind": "company event",
                "by_date": "2027-06-01",
                "probability": "55%",
                "make_or_break": False,
                "reasoning": "It said so, and the result was clean.",
                "sources": SOURCE,
            }
        ]
    return {
        "cik": cik,
        "section": "Our view of the company.",
        "forecasts": made,
        "sources": SOURCE,
        "lacked": [],
        **more,
    }


def buy(cik: int, size: str = "3%") -> dict[str, Any]:
    return {"cik": cik, "action": "buy", "size_pct": size, "thesis": THESIS, "sources": SOURCE}


def decisions(fund: str, *orders: dict[str, Any]) -> dict[str, Any]:
    return {"fund": fund, "decisions": list(orders), "lacked": []}


__all__ = ["COMPANIES", "FLAT", "MON", "THU_8", "WED_8"]

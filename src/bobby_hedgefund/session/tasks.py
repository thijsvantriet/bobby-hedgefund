"""Task files: the exact text an agent is started with (docs/decisions/0009, point 3).

A script writes one file per agent run and stores its fingerprint at that moment. The leading session starts the
agent with one fixed sentence that names the file; it never writes a task itself. Afterwards the agent's own
record must show that sentence, and the task file must still have its fingerprint.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..archive.store import iso, sha256_hex, utcnow
from ..universe.output import write_new

FOLDER = "tasks"
INDEX = "index.jsonl"
_SAFE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


class TaskError(Exception):
    pass


@dataclass(frozen=True)
class Task:
    task: str  # for example analysis-0000012345-science or pm-careful-run-2
    agent: str  # the agent file it must be run with, for example bobby-science-analyst
    sha256: str
    file: str  # relative to the session folder
    written: str
    run: int | None = None

    def prompt(self, session_dir: Path) -> str:
        """The one sentence the agent is started with. Nothing else may be added to it."""
        return f"Read the file {session_dir / self.file} and do exactly what it says."


def write(session_dir: Path, task: str, agent: str, text: str, run: int | None = None) -> Task:
    """Write one task file (never over an existing one) and note its fingerprint in the index."""
    if not _SAFE.match(task) or not _SAFE.match(agent):
        raise TaskError(f"not a usable task or agent name: {task!r}, {agent!r}")
    folder = session_dir / FOLDER
    path = folder / f"{task}.md"
    body = text if text.endswith("\n") else text + "\n"
    write_new(path, body)  # read-only once written
    made = Task(task, agent, sha256_hex(body.encode("utf-8")), f"{FOLDER}/{task}.md", iso(utcnow()), run)
    line = json.dumps(made.__dict__, sort_keys=True) + "\n"
    with open(folder / INDEX, "a", encoding="utf-8") as fh:
        fh.write(line)
    return made


def load(session_dir: Path) -> dict[str, Task]:
    """Every task of the session by its name."""
    path = session_dir / FOLDER / INDEX
    if not path.exists():
        return {}
    out: dict[str, Task] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            made = Task(**json.loads(line))
            out[made.task] = made
    return out


def unchanged(session_dir: Path, task: Task) -> bool:
    """Does the task file still have the fingerprint it had when the script wrote it?"""
    try:
        return sha256_hex((session_dir / task.file).read_bytes()) == task.sha256
    except OSError:
        return False

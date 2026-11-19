"""The "round active" marker (docs/decisions/0009, point 3): a small file in the data folder that exists while a
round runs. The checks in `.claude/hooks/bobby_hooks.py` do nothing unless it exists, names the session they run
in and is younger than 90 minutes; so they can never get in the way of ordinary work in this repository.
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any

FILE = "round-active.json"
MAX_AGE_SECONDS = 90 * 60  # the same number as in the hooks file; a test compares the two


def path(data_dir: Path) -> Path:
    return data_dir / FILE


def write(data_dir: Path, *, session_id: str, session_dir: Path, round_dir: Path, mode: str, **more: Any) -> None:
    """Switch the round's checks on for one session."""
    body = {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "round_dir": str(round_dir),
        "mode": mode,
        "started": time.time(),
        **more,
    }
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = data_dir / f".{FILE}-{os.getpid()}"
    tmp.write_text(json.dumps(body, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path(data_dir))


def read(data_dir: Path) -> dict[str, Any] | None:
    """The active round, or None; by the same rules as the hooks."""
    try:
        found = json.loads(path(data_dir).read_text(encoding="utf-8"))
        if not isinstance(found, dict):
            return None
        started = float(found["started"])
        if not math.isfinite(started) or not 0 <= time.time() - started <= MAX_AGE_SECONDS:
            return None  # too old, or dated in the future: a marker can never stay switched on for good
        return found
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return None


def update(data_dir: Path, **changes: Any) -> None:
    """Change fields of the marker (for example: allow one new start of a task on the next model down)."""
    current = json.loads(path(data_dir).read_text(encoding="utf-8"))
    current.update(changes)
    tmp = data_dir / f".{FILE}-{os.getpid()}"
    tmp.write_text(json.dumps(current, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path(data_dir))


def clear(data_dir: Path) -> bool:
    """Switch the round's checks off. Returns whether there was a marker."""
    try:
        path(data_dir).unlink()
        return True
    except FileNotFoundError:
        return False

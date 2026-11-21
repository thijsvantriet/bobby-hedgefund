#!/usr/bin/env python3
"""Status line for this project; it also saves the share of the usage limits for the daily round.

Claude Code gives the five-hour and weekly usage percentages only to the status line script (as `rate_limits`
in the description it sends on standard input). This script prints one line and saves those two figures to
`<data folder>/usage/rate-limits.json`, where the round reads them at its start and its end (docs/SPEC.md,
section 7). Only the figures are kept: no other part of the description is saved.

It runs only in sessions of this project (`.claude/settings.json`, key `statusLine`); elsewhere the owner's own
status line stays. To remove it: delete that key and this file.

Standard library only, nothing imported from the project, and it never fails: whatever goes wrong, it still prints
a line and exits 0.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

WINDOWS = ("five_hour", "seven_day")
LABELS = {"five_hour": "5h", "seven_day": "week"}
RESAVE_SECONDS = 60  # unchanged figures are saved again after this long, so that the saved time stays recent


def data_dir() -> Path:
    return Path(os.environ.get("BOBBY_DATA_DIR") or Path.home() / "bobby-hedgefund-data")


def number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def windows(event: dict) -> dict:
    """The usable windows of `rate_limits`: a percentage from 0 to 999, and the reset time when it is given."""
    limits = event.get("rate_limits")
    found = {}
    for key in WINDOWS:
        window = limits.get(key) if isinstance(limits, dict) else None
        used = window.get("used_percentage") if isinstance(window, dict) else None
        if number(used) and 0 <= used <= 999:
            found[key] = {"used_percentage": used}
            if number(window.get("resets_at")):
                found[key]["resets_at"] = int(window["resets_at"])
    return found


def save(found: dict, session_id: str) -> None:
    """Writes the figures when they changed or were saved too long ago (the round only trusts recent figures). The
    new file is written beside the old one and then put in its place, so a reader never sees half a file. Nothing
    is written when the data folder does not exist: this script never creates it."""
    folder = data_dir()
    if not folder.is_dir():
        return
    target = folder / "usage" / "rate-limits.json"
    try:
        old = json.loads(target.read_text(encoding="utf-8"))
        same = {k: old.get(k) for k in WINDOWS if k in old} == found
        if same and time.time() - target.stat().st_mtime < RESAVE_SECONDS:
            return
    except (OSError, ValueError, AttributeError):
        pass
    target.parent.mkdir(exist_ok=True, mode=0o700)
    for left in target.parent.glob(".tmp-*-rate-limits.json"):  # left by a run that Claude Code cut short
        try:
            if time.time() - left.stat().st_mtime > 60:
                left.unlink()
        except OSError:
            pass
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = json.dumps({**found, "saved_at": now, "session_id": session_id}, sort_keys=True) + "\n"
    tmp = target.with_name(f".tmp-{os.getpid()}-{target.name}")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)


def line(event: dict, found: dict) -> str:
    model = event.get("model")
    name = model.get("display_name") if isinstance(model, dict) else None
    window = event.get("context_window")
    ctx = window.get("used_percentage") if isinstance(window, dict) else None
    parts = [str(name or "Claude"), f"ctx {ctx:.0f}%" if number(ctx) else "ctx 0%"]
    usage = [f"{LABELS[key]} {found[key]['used_percentage']:.0f}%" for key in WINDOWS if key in found]
    if usage:
        parts.append(" · ".join(usage))
    folder = event.get("workspace", {}).get("current_dir") if isinstance(event.get("workspace"), dict) else None
    parts.append(Path(str(folder or event.get("cwd") or ".")).name or ".")
    return " | ".join(parts)


def main() -> None:
    try:
        event = json.loads(sys.stdin.read(1_000_000))
        if not isinstance(event, dict):
            event = {}
    except Exception:
        event = {}
    found: dict = {}
    try:
        found = windows(event)
        if found:
            save(found, str(event.get("session_id") or "")[:100])
    except Exception:
        pass  # the figures are a help for the round, never a reason for an empty status line
    try:
        print(line(event, found))
    except Exception:
        print("Claude")


if __name__ == "__main__":
    main()

"""The owner's decisions on suggested matches: a file that only ever grows (docs/decisions/0006, point 4).

One line per decision, as JSON. Every line carries the fingerprint of the line before it, so a changed or removed
line is noticed. A changed mind is a new line that names the line it replaces; the old line stays.
"""

from __future__ import annotations

import fcntl
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..archive.store import GENESIS, sha256_hex

FILE = "decisions.jsonl"
# "parent or subsidiary": the sponsor is the company's parent or daughter. "not biotech": a decision about the
# company itself (it should not be in the universe), and "biotech" takes that back; "no": this sponsor name is
# another organisation.
ALLOWED = ("yes", "no", "parent or subsidiary", "not biotech", "biotech")
LINKED = ("yes", "parent or subsidiary")


class DecisionError(Exception):
    pass


@dataclass(frozen=True)
class Decision:
    cik: int
    sponsor_name: str
    decision: str
    note: str = ""
    company: str = ""
    kind: str = ""
    score: float | None = None
    review_file: str = ""  # fingerprint of the machine copy of the review file the decision was made on


def load(folder: Path) -> list[dict[str, Any]]:
    """All lines, oldest first. Raises DecisionError when the chain of fingerprints is broken."""
    path = folder / FILE
    if not path.exists():
        return []
    lines: list[dict[str, Any]] = []
    prev = GENESIS
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise DecisionError(f"{path} ends with half a line; nothing was read or written")
    for number, raw in enumerate(data.splitlines(), start=1):
        try:
            rec = json.loads(raw)
            if not isinstance(rec, dict) or rec.get("prev") != prev:
                raise ValueError
        except ValueError:
            raise DecisionError(f"{path}, line {number}: changed, removed or not a decision line") from None
        prev = sha256_hex(raw)
        rec["_line"] = number
        rec["_sha256"] = prev
        lines.append(rec)
    return lines


def current(lines: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    """The decision that counts for each (company, sponsor name): the newest line."""
    newest: dict[tuple[int, str], dict[str, Any]] = {}
    for rec in lines:
        newest[(int(rec["cik"]), str(rec["sponsor_name"]))] = rec
    return newest


def append(folder: Path, decisions: list[Decision], when: str) -> dict[str, int]:
    """Add decisions. One that equals the decision that already counts is skipped; a different one becomes a new
    line that names the line it replaces. Returns counts: added, changed, same."""
    for d in decisions:
        if d.decision not in ALLOWED:
            raise DecisionError(f"unknown decision {d.decision!r} for {d.sponsor_name!r}")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / FILE
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        lines = load(folder)
        now = current(lines)
        prev = lines[-1]["_sha256"] if lines else GENESIS
        out = b""
        counts = {"added": 0, "changed": 0, "same": 0}
        for d in decisions:
            key = (d.cik, d.sponsor_name)
            old = now.get(key)
            if old is not None and old.get("decision") == d.decision and (old.get("note") or "") == d.note:
                counts["same"] += 1
                continue
            rec: dict[str, Any] = {
                "v": 1,
                "ts": when,
                "cik": d.cik,
                "company": d.company,
                "sponsor_name": d.sponsor_name,
                "decision": d.decision,
                "note": d.note,
                "kind": d.kind,
                "score": d.score,
                "review_file": d.review_file,
            }
            if old is not None:
                rec["replaces_line"] = old["_line"]
                rec["replaces_sha256"] = old["_sha256"]
                counts["changed"] += 1
            else:
                counts["added"] += 1
            rec["prev"] = prev
            raw = json.dumps(rec, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            prev = sha256_hex(raw)
            out += raw + b"\n"
            now[key] = {**rec, "_line": len(lines) + counts["added"] + counts["changed"], "_sha256": prev}
        if out:
            size_before = os.fstat(fd).st_size
            try:
                done = 0
                while done < len(out):
                    done += os.write(fd, out[done:])
                os.fsync(fd)
            except OSError as exc:
                os.ftruncate(fd, size_before)  # no half line may stay behind
                raise DecisionError(f"could not write the decisions ({exc}); nothing was added") from exc
        return counts
    finally:
        os.close(fd)

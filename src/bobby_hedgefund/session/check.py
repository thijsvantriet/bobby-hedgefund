"""The weekly check on the screening (docs/SPEC.md section 3; docs/decisions/0009, "Differs from the spec", 3).

On a day with weekly extras (the first session of a week), Opus judges again a sample of 20 companies that the
screening (Haiku) marked "no deep look" in the seven days before, with the same lines of news the screening saw.
It is not told what the screening wrote. The sample is drawn from fingerprints, so anyone can draw it again.

The lines come from the batch files of those days. Those session folders are not readable for an agent today,
so the lines are copied into the task file; the source numbers in them belong to their own day's list.

The result (how many of the sample Opus would have sent to a deep look) goes into the round's `usage.json`. The
spec's rule, "more than 2 of 20 two weeks in a row: a stronger screening model at the next monthly review", is
applied at that review; nothing in the round changes because of it.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..archive.store import sha256_hex
from ..universe.output import write_new
from . import round as rounds
from .round import Round
from .tasks import Task

TASK = "check-screening"
AGENT = "bobby-screening-check"
SAMPLE = 20
LOOK_BACK_DAYS = 7
SAMPLE_FILE = "screening-check-sample.json"
RESULT_FILE = "screening-check.json"


def digests(batch_folder: Path) -> dict[int, list[str]]:
    """The lines the screening saw per company: its heading and its items, without the line naming its files."""
    out: dict[int, list[str]] = {}
    for path in sorted(batch_folder.glob("batch-*.md")) if batch_folder.is_dir() else []:
        cik = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                first = line[3:].split(" ", 1)[0]
                cik = int(first) if first.isdigit() else None
                if cik is not None:
                    out[cik] = [line]
            elif cik is not None and line.startswith("- "):
                out[cik].append(line)
    return out


def earlier_noes(root: Path, today: date) -> dict[int, tuple[str, list[str]]]:
    """The companies the screening marked "no deep look" in the rounds of the seven days before today: company ->
    (the day, the lines it saw). A company judged on several days counts once, with its latest day."""
    found: dict[int, tuple[str, list[str]]] = {}
    for back in range(LOOK_BACK_DAYS, 0, -1):  # oldest first, so a later day replaces an earlier one
        day = (today - timedelta(days=back)).isoformat()
        answers = root / "rounds" / day / "answers"
        lines = digests(root / "sessions" / day / "screening")
        for path in sorted(answers.glob("screening-*.json")) if answers.is_dir() else []:
            got = json.loads(path.read_text(encoding="utf-8"))
            if got.get("status") != "ok" or not isinstance(got.get("answer"), dict):
                continue
            for company in got["answer"].get("companies") or []:
                cik = company.get("cik")
                if company.get("deep_look") is False and cik in lines:
                    found[cik] = (day, lines[cik])
    return found


def draw(noes: dict[int, Any], today: date, size: int = SAMPLE) -> list[int]:
    """The sample: the companies with the lowest fingerprints of the day and their number."""
    key = lambda cik: sha256_hex(f"bobby screening check\n{today.isoformat()}\n{cik}".encode("ascii"))  # noqa: E731
    return sorted(noes, key=lambda cik: (key(cik), cik))[:size]


def write_task(rnd: Round) -> Task | None:
    """The check's task on a day with weekly extras, or None (another day, or nothing to check)."""
    if "weekly" not in rnd.extras:
        return None
    noes = earlier_noes(rnd.root, rnd.day)
    chosen = draw(noes, rnd.day)
    if not chosen:
        return None
    sample = rnd.round_dir / SAMPLE_FILE
    if not sample.exists():
        body = {"day": rnd.day.isoformat(), "pool": len(noes), "sample": [[c, noes[c][0]] for c in chosen]}
        write_new(sample, json.dumps(body, sort_keys=True) + "\n")
    lines = [
        f'This week\'s check: {len(chosen)} companies that the screening marked "no deep look" in the last '
        f"{LOOK_BACK_DAYS} days, each with the day it was judged and the lines of news it saw then.",
        "The files of those days are not in this folder, and the numbers in square brackets belong to that day's "
        "list of sources: judge from these lines alone. Do not try to open anything else.",
        "Answer for every company below, in this order.",
        "",
    ]
    for cik in chosen:
        day, seen = noes[cik]
        lines += [f"{seen[0]}    (judged on {day})", *seen[1:], ""]
    return rounds.write_task(rnd, TASK, AGENT, lines)


def result(rnd: Round) -> dict[str, Any] | None:
    """How the check came out, once its answer is in; written once, to the round's folder. None before that."""
    path = rnd.round_dir / RESULT_FILE
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    got = rounds.stored(rnd, TASK)
    sample_path = rnd.round_dir / SAMPLE_FILE
    if got is None or not sample_path.exists():
        return None
    sample = [c for c, _ in json.loads(sample_path.read_text(encoding="utf-8"))["sample"]]
    out: dict[str, Any] = {"sampled": len(sample), "status": got.status}
    if got.status == "ok" and got.answer is not None:
        verdicts = {}
        for company in got.answer["companies"]:
            if company["cik"] in sample and company["cik"] not in verdicts:
                verdicts[company["cik"]] = bool(company["deep_look"])
        out["judged"] = len(verdicts)
        out["disagreed"] = sorted(c for c, yes in verdicts.items() if yes)  # Opus: worth a deep look after all
        out["not_judged"] = sorted(set(sample) - set(verdicts))
    write_new(path, json.dumps(out, sort_keys=True) + "\n")
    return out


def summary(found: dict[str, Any] | None) -> str:
    if found is None:
        return "weekly check on the screening: no answer yet"
    if found.get("status") != "ok":
        return f"weekly check on the screening: its answer was {found.get('status')}; no figure this week"
    return (
        f"weekly check on the screening: Opus would have looked deeper at {len(found['disagreed'])} of "
        f"{found['judged']} companies the screening passed over (the spec's limit: 2 of 20)"
    )

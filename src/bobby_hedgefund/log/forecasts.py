"""`forecasts.csv`: every stated probability and, once known, its outcome (docs/SPEC.md section 5). The file only
grows: an outcome is a new line that points to its forecast (docs/decisions/0004, point 3). It is worked out from
the log, so it can never say something the log does not."""

from __future__ import annotations

import os
from pathlib import Path

from ..universe.output import csv_text
from . import canon
from .store import Entry, LogError

FILE = "forecasts.csv"
HEADER = (
    "record",
    "time",
    "kind",
    "forecast",
    "cik",
    "company",
    "role",
    "event_kind",
    "event",
    "by_date",
    "probability",
    "make_or_break",
    "result",
    "resolved_on",
    "brier",
)


def brier(probability: str, result: str) -> str:
    """The Brier score of one forecast as text with four decimals: 0 is perfect, 0.25 is what 50% always scores.
    Empty for a forecast that was declared void."""
    if result not in ("yes", "no"):
        return ""
    p = canon.pct_fraction(probability)
    score = (p - (1 if result == "yes" else 0)) ** 2
    parts = round(score * 10000)  # exact arithmetic; no number with a floating decimal point on the way
    return f"{parts // 10000}.{parts % 10000:04d}"


def rows(entries: list[Entry]) -> list[list[str]]:
    by_seq = {e.seq: e for e in entries}
    out: list[list[str]] = []
    for e in entries:
        r = e.record
        if e.kind == "forecast":
            c = r["company"]
            out.append(
                [
                    str(e.seq),
                    r["time"],
                    "forecast",
                    "",
                    str(c["cik"]),
                    c["name"],
                    r["role"],
                    r["event_kind"],
                    r["event"],
                    r["by_date"],
                    r["probability"],
                    "yes" if r["make_or_break"] else "no",
                    "",
                    "",
                    "",
                ]
            )
        elif e.kind == "outcome":
            forecast = by_seq.get(r["ref"])
            if forecast is None or forecast.kind != "forecast":
                raise LogError(f"record {e.seq}: an outcome that points to record {r['ref']}, which is no forecast")
            f = forecast.record
            out.append(
                [
                    str(e.seq),
                    r["time"],
                    "outcome",
                    str(forecast.seq),
                    str(f["company"]["cik"]),
                    f["company"]["name"],
                    f["role"],
                    f["event_kind"],
                    "",
                    f["by_date"],
                    f["probability"],
                    "",
                    r["result"],
                    r["resolved_on"],
                    r.get("brier") or brier(f["probability"], r["result"]),
                ]
            )
    return out


def write(staging: Path, entries: list[Entry]) -> int:
    """Bring `forecasts.csv` up to date with the log. Refuses when the existing file is not the beginning of the
    new one: a published line would change. Returns the number of lines added."""
    text = csv_text(HEADER, rows(entries)).encode("utf-8")
    path = staging / FILE
    old = path.read_bytes() if path.exists() else b""
    if not text.startswith(old):
        raise LogError(f"{FILE} no longer follows from the log: an existing line would change; nothing was written")
    if text == old:
        return 0
    tmp = staging / f".{FILE}-{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, text)
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(path)
    return text.count(b"\n") - old.count(b"\n")

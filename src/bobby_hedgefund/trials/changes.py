"""Find what changed in a trial's registry record between two archived copies.

The archive holds one full copy of every company-linked record (the baseline) and, from each night, the records
the registry changed in the days before. Reading all pages oldest first and remembering a handful of fields per
trial shows every change of those fields since the baseline. Only reading: nothing is downloaded or changed.

The fields are fixed here, before any price is looked at, because the spec's one side-hypothesis (registry edits
against later price moves, docs/SPEC.md section 4) is measured on them. Changing the list later is a change of
that measure and must be written down as one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

FIELDS = (
    "overall_status",
    "why_stopped",
    "start_date",
    "primary_completion_date",
    "completion_date",
    "phases",
    "enrollment",
    "primary_outcomes",
    "lead_sponsor",
    "has_results",
    "results_first_posted",
)
DATE_FIELDS = frozenset({"start_date", "primary_completion_date", "completion_date"})


def _date_struct(module: dict, key: str) -> dict[str, Any] | None:
    found = module.get(key)
    if not isinstance(found, dict) or not found.get("date"):
        return None
    return {"date": str(found["date"]), "type": str(found.get("type") or "")}


def extract(study: dict) -> tuple[str, dict[str, Any], str]:
    """The trial number, the followed fields, and the day the registry posted the record's last update.
    Raises KeyError or TypeError on a record without a trial number."""
    protocol = study["protocolSection"]
    nct = str(protocol["identificationModule"]["nctId"])
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    enrollment = design.get("enrollmentInfo")
    outcomes = (protocol.get("outcomesModule") or {}).get("primaryOutcomes") or []
    lead = (protocol.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}
    results_posted = _date_struct(status, "resultsFirstPostDateStruct")
    fields: dict[str, Any] = {
        "overall_status": status.get("overallStatus"),
        "why_stopped": status.get("whyStopped"),
        "start_date": _date_struct(status, "startDateStruct"),
        "primary_completion_date": _date_struct(status, "primaryCompletionDateStruct"),
        "completion_date": _date_struct(status, "completionDateStruct"),
        "phases": list(design.get("phases") or []),
        "enrollment": (
            {"count": enrollment.get("count"), "type": str(enrollment.get("type") or "")}
            if isinstance(enrollment, dict)
            else None
        ),
        # The description of an outcome is left out: it is long, and the measure and its time frame are the goal.
        "primary_outcomes": [
            {"measure": str(o.get("measure") or ""), "time_frame": str(o.get("timeFrame") or "")}
            for o in outcomes
            if isinstance(o, dict)
        ],
        "lead_sponsor": lead.get("name") if isinstance(lead, dict) else None,
        "has_results": bool(study.get("hasResults")),
        "results_first_posted": results_posted["date"] if results_posted else None,
    }
    posted = _date_struct(status, "lastUpdatePostDateStruct")
    return nct, fields, posted["date"] if posted else ""


def _as_day(text: str) -> date | None:
    """A registry date: a full date, or only a year and month (then the first of the month)."""
    try:
        parts = [int(p) for p in text.split("-")]
        return date(parts[0], parts[1], parts[2] if len(parts) > 2 else 1) if len(parts) in (2, 3) else None
    except (ValueError, IndexError):
        return None


def moved_days(old: Any, new: Any) -> int | None:
    """How many days a date moved (positive: later). None when a side is missing or not a date."""
    if not (isinstance(old, dict) and isinstance(new, dict)):
        return None
    a, b = _as_day(str(old.get("date"))), _as_day(str(new.get("date")))
    return (b - a).days if a and b else None


@dataclass(frozen=True)
class Seen:
    fields: dict[str, Any]
    path: str  # the archived file this copy of the record was read from
    saved: str  # when that file was saved
    posted: str  # the registry's "last update posted" day of this copy


class ChangeFinder:
    """Feed copies of records oldest first; `add` returns the change lines of that copy against the one before."""

    def __init__(self) -> None:
        self._last: dict[str, Seen] = {}
        self.copies = 0

    @property
    def trials(self) -> int:
        return len(self._last)

    def add(self, study: dict, path: str, saved: str) -> list[dict[str, Any]]:
        nct, fields, posted = extract(study)
        self.copies += 1
        before = self._last.get(nct)
        now = Seen(fields, path, saved, posted)
        if before is None:
            self._last[nct] = now
            return []
        if before.fields == fields:
            return []  # the same copy again (nightly pages overlap), or a change in a field we do not follow
        lines: list[dict[str, Any]] = []
        for name in FIELDS:
            old, new = before.fields.get(name), fields.get(name)
            if old == new:
                continue
            line: dict[str, Any] = {
                "nct": nct,
                "field": name,
                "old": old,
                "new": new,
                "old_file": before.path,
                "old_saved": before.saved,
                "old_posted": before.posted,
                "new_file": path,
                "new_saved": saved,
                "new_posted": posted,
            }
            if name in DATE_FIELDS:
                line["moved_days"] = moved_days(old, new)
            lines.append(line)
        self._last[nct] = now
        return lines

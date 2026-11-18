"""Collect sponsor names from the archived trial records (docs/decisions/0006, matching step 2)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .read_sec import ReadError

# The registry's classes for a sponsor. "Industry" is what we look for; AMBIG and UNKNOWN are the unclear ones, and
# a sponsor without a class is treated as unclear too.
WANTED_CLASSES = frozenset({"INDUSTRY", "AMBIG", "UNKNOWN", ""})


@dataclass
class SponsorName:
    name: str
    classes: set[str] = field(default_factory=set)
    lead: set[str] = field(default_factory=set)  # trial numbers where this name is the lead sponsor
    collaborator: set[str] = field(default_factory=set)

    @property
    def trials(self) -> set[str]:
        return self.lead | self.collaborator


def study_sponsors(study: dict) -> tuple[str, list[tuple[str, str, str]]]:
    """The trial number and its (role, name, class) entries. Raises ReadError on a record without a number."""
    try:
        protocol = study["protocolSection"]
        nct = str(protocol["identificationModule"]["nctId"])
    except (KeyError, TypeError) as exc:
        raise ReadError("a trial record has no trial number") from exc
    module = protocol.get("sponsorCollaboratorsModule") or {}
    entries: list[tuple[str, str, str]] = []
    lead = module.get("leadSponsor")
    for role, items in (
        ("lead", [lead] if isinstance(lead, dict) else []),
        ("collaborator", module.get("collaborators") or []),
    ):
        for item in items:
            if isinstance(item, dict) and str(item.get("name") or "").strip():
                entries.append((role, str(item["name"]).strip(), str(item.get("class") or "").strip().upper()))
    return nct, entries


def page_studies(body: bytes) -> list[dict]:
    try:
        studies = json.loads(body)["studies"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ReadError(f"a page of trial records is not the expected JSON ({type(exc).__name__})") from exc
    if not isinstance(studies, list):
        raise ReadError("a page of trial records is not the expected JSON (studies is not a list)")
    return studies


class SponsorCollector:
    """Feed pages oldest first: a newer copy of a trial record replaces the older one."""

    def __init__(self) -> None:
        self._by_trial: dict[str, list[tuple[str, str, str]]] = {}

    def add_page(self, body: bytes) -> int:
        studies = page_studies(body)
        for study in studies:
            nct, entries = study_sponsors(study)
            self._by_trial[nct] = entries
        return len(studies)

    @property
    def n_trials(self) -> int:
        return len(self._by_trial)

    def names(self) -> list[SponsorName]:
        """Every distinct name, exactly as written in the registry, that is classed as industry or unclear in at
        least one trial. Most trials first."""
        found: dict[str, SponsorName] = {}
        for nct, entries in self._by_trial.items():
            for role, name, cls in entries:
                entry = found.setdefault(name, SponsorName(name))
                entry.classes.add(cls)
                (entry.lead if role == "lead" else entry.collaborator).add(nct)
        wanted = [s for s in found.values() if s.classes & WANTED_CLASSES]
        return sorted(wanted, key=lambda s: (-len(s.trials), s.name))

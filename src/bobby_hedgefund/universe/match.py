"""Suggest which sponsor names in the trial registry belong to which company (docs/decisions/0006, point 3).

Nothing here decides: every suggestion goes to a person. Four kinds of suggestion, strongest first:
  strong   the names are identical after cleaning
  core     identical once the words that only say "drug company" are left out (X Therapeutics / X Pharma)
  starts   the sponsor's name starts with the company's whole cleaned name (a subsidiary, a country branch)
  similar  the cleaned names are nearly the same (a spelling variant)
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process

from . import names
from .read_trials import SponsorName

KINDS = ("strong", "core", "starts", "similar")
SIMILAR_FROM = 90.0  # of 100
MIN_CORE_LENGTH = 4  # a shorter core ("bio", "ab") fits too many names to be a suggestion by itself
MAX_PER_COMPANY = 25


@dataclass(frozen=True)
class Company:
    cik: int
    name: str
    ticker: str
    former_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class Suggestion:
    company: Company
    matched_on: str  # the company name (or former name) that led to the suggestion, as written
    sponsor: SponsorName
    kind: str
    score: float

    @property
    def is_former_name(self) -> bool:
        return self.matched_on != self.company.name


class SponsorIndex:
    def __init__(self, sponsors: list[SponsorName]):
        self.sponsors = sponsors
        self.cleaned = [names.clean(s.name) for s in sponsors]
        self.by_clean: dict[str, list[int]] = {}
        self.by_core: dict[str, list[int]] = {}
        for i, cleaned in enumerate(self.cleaned):
            self.by_clean.setdefault(cleaned, []).append(i)
            core = names.core(cleaned)
            if len(core) >= MIN_CORE_LENGTH:
                self.by_core.setdefault(core, []).append(i)

    def find(self, name: str) -> dict[int, tuple[str, float]]:
        """Sponsor index -> (kind, score) for one company name. The strongest kind wins."""
        cleaned = names.clean(name)
        found: dict[int, tuple[str, float]] = {}
        if not cleaned:
            return found

        def add(i: int, kind: str, score: float) -> None:
            if i not in found or KINDS.index(kind) < KINDS.index(found[i][0]):
                found[i] = (kind, score)

        for i in self.by_clean.get(cleaned, []):
            add(i, "strong", 100.0)
        core = names.core(cleaned)
        if len(core) >= MIN_CORE_LENGTH:
            for i in self.by_core.get(core, []):
                add(i, "core", fuzz.ratio(cleaned, self.cleaned[i]))
        if len(cleaned) >= MIN_CORE_LENGTH:
            prefix = cleaned + " "
            for i, other in enumerate(self.cleaned):
                if other.startswith(prefix):
                    add(i, "starts", fuzz.ratio(cleaned, other))
        for _, score, i in process.extract(
            cleaned, self.cleaned, scorer=fuzz.ratio, score_cutoff=SIMILAR_FROM, limit=MAX_PER_COMPANY
        ):
            add(i, "similar", score)
        return found


def suggest(companies: list[Company], sponsors: list[SponsorName]) -> list[Suggestion]:
    """All suggestions, company by company (in the order given), strongest kind and most trials first. A sponsor
    name is suggested at most once per company: under the company name that fits it best."""
    index = SponsorIndex(sponsors)
    out: list[Suggestion] = []
    for company in companies:
        best: dict[int, tuple[str, float, str]] = {}
        for written in (company.name, *company.former_names):
            for i, (kind, score) in index.find(written).items():
                rank = (KINDS.index(kind), -score)
                if i not in best or rank < (KINDS.index(best[i][0]), -best[i][1]):
                    best[i] = (kind, score, written)
        ordered = sorted(best.items(), key=lambda kv: (KINDS.index(kv[1][0]), -len(sponsors[kv[0]].trials), -kv[1][1]))
        for i, (kind, score, written) in ordered[:MAX_PER_COMPANY]:
            out.append(Suggestion(company, written, sponsors[i], kind, round(score, 1)))
    return out

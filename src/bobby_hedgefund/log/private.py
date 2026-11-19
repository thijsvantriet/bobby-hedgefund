"""Companies that may not be named in anything public (docs/decisions/0006: in the universe through the XBI fund
only). The list is private, lives in the data folder and is written by the session preparation; no name stands in
this repository. A finding is always reported by its number in the list, never by name.

A mention is looked for in three ways: the SEC number, the ticker, and the name. The name also in its short
forms: without an ending such as Inc or Corp, and without a word such as Therapeutics or Pharmaceuticals, because
that is how people write about a company. A ticker that is also a common word or abbreviation (RNA, ALT) only
counts where it is clearly used as a ticker. The list may give extra names per company.

This is a net with holes: an unusual spelling or a product name is not caught. The first protection is that these
companies get no deep analysis at all (docs/decisions/0009, open point 2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FILE = "private-names.tsv"
_ENDING = re.compile(
    r"(?:[\s,]+|\s*/\s*)(?:inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp|l\.p|s\.?a|n\.?v|a/s|ag|se"
    r"|gmbh|b\.?v|holdings?|group|[a-z]{2})\.?/?$",
    re.IGNORECASE,
)
_STATE = re.compile(r"\s*/\s*[A-Za-z]{2,3}\s*/?$")  # the SEC's "/DE/" or "/ MA" after a name
_INDUSTRY = re.compile(
    r"\s+(?:therapeutics?|pharmaceuticals?|pharma|biopharma|biopharmaceuticals?|biosciences?|biotherapeutics"
    r"|biotech|biotechnolog(?:y|ies)|biologics|bio|medicines?|medical|sciences?|genetics|genomics|oncology"
    r"|technolog(?:y|ies)|laborator(?:y|ies)|labs|health|healthcare|international|global|holdings?|group)$",
    re.IGNORECASE,
)
# Tickers that are also ordinary abbreviations in this field: they count only where clearly used as a ticker.
COMMON_TOKENS = frozenset(
    [
        "DNA",
        "RNA",
        "ALT",
        "AST",
        "CAR",
        "ALL",
        "AML",
        "CLL",
        "CML",
        "HIV",
        "HBV",
        "HCV",
        "RSV",
        "FDA",
        "EMA",
        "CEO",
        "CFO",
        "CMO",
        "IPO",
        "USA",
        "NIH",
        "SEC",
        "CMS",
        "PD",
        "PK",
        "OS",
        "PFS",
        "ORR",
        "AE",
        "SAE",
        "MS",
        "ALS",
        "RA",
        "UC",
        "CD",
        "IBD",
        "COPD",
        "NASH",
        "MASH",
        "GLP",
        "TKI",
        "ADC",
        "MOA",
        "IND",
        "NDA",
        "BLA",
        "CRL",
        "EPS",
        "ROI",
        "CNS",
        "GI",
        "IV",
        "SC",
        "QD",
        "BID",
        "MRI",
        "CT",
        "PET",
        "ICU",
        "ER",
        "OR",
        "BMI",
        "LDL",
        "HDL",
        "MTD",
        "DLT",
        "CR",
        "PR",
        "SD",
        "HR",
        "CI",
        "ITT",
        "PP",
        "SOC",
        "BSC",
        "NK",
        "TIL",
        "TCR",
        "BCR",
        "EGFR",
        "HER",
        "PSA",
        "AAV",
        "LNP",
        "GMP",
        "CMC",
        "ARM",
        "EYE",
        "CELL",
        "GENE",
        "CURE",
        "LIFE",
        "CARE",
        "HOPE",
        "NOVA",
        "BEAM",
        "EDIT",
        "FATE",
        "KEY",
        "ONE",
        "TWO",
        "ALPHA",
        "BETA",
        "GAMMA",
        "OMEGA",
    ]
)


class PrivateError(Exception):
    pass


@dataclass(frozen=True)
class PrivateCompany:
    cik: int
    ticker: str
    name: str
    aliases: tuple[str, ...] = ()


def load(path: Path) -> list[PrivateCompany]:
    """One company per line: SEC number, ticker, name and optionally more names (separated by |), with tabs
    between. Without the file nothing that names a company can be published."""
    if not path.exists():
        raise PrivateError(
            f"the private list {path.name} is missing: without it nothing that names a company is written"
        )
    out: list[PrivateCompany] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) not in (3, 4) or not parts[0].isdigit():
            raise PrivateError(f"{path.name}: a line that is not 'number, ticker, name[, other names]'")
        aliases = tuple(a.strip() for a in parts[3].split("|") if a.strip()) if len(parts) == 4 else ()
        out.append(PrivateCompany(int(parts[0]), parts[1].strip(), parts[2].strip(), aliases))
    return out


def short_names(name: str) -> list[str]:
    """The name as the SEC writes it, and the shorter forms people use: "X Therapeutics, Inc. /DE/" also gives
    "X Therapeutics" and "X"."""
    forms: list[str] = []
    current = _STATE.sub("", name.strip())
    for pattern in (_ENDING, _ENDING, _INDUSTRY, _INDUSTRY):
        if current and current not in forms:
            forms.append(current)
        current = pattern.sub("", current).strip(" ,.")
    if current and current not in forms:
        forms.append(current)
    return forms


def _patterns(company: PrivateCompany) -> list[re.Pattern[str]]:
    out = [
        re.compile(rf'"cik":\s*{company.cik}\b'),
        re.compile(rf"\bCIK\W{{0,3}}0*{company.cik}\b", re.IGNORECASE),
        re.compile(rf"(?<!\d)0{{0,9}}{company.cik}(?!\d)") if company.cik >= 100000 else re.compile(r"(?!x)x"),
    ]
    ticker = company.ticker
    if ticker:
        t = re.escape(ticker)
        out.append(
            re.compile(rf'\${t}\b|\(\s*{t}\s*\)|(?:nasdaq|nyse|ticker|symbol)\W{{1,4}}{t}\b|"ticker":\s*"{t}"', re.I)
        )
        if ticker.upper() not in COMMON_TOKENS and len(ticker) >= 2:
            out.append(re.compile(rf"(?<![A-Za-z0-9.$]){t}(?![A-Za-z0-9])"))
    full = short_names(company.name)
    for i, form in enumerate([*full, *company.aliases]):
        words = [re.escape(w) for w in re.split(r"[\s,.\-]+", form) if w]
        if not words:
            continue
        body = r"[\s,.\-]+".join(words)
        single = len(words) == 1
        if single and len(form) < 3:
            continue
        # A one-word short form ("Beam") counts as a name only when written with its capital, not as the word "beam".
        flags = 0 if single and (i >= len(full) - 1 or form.upper() in COMMON_TOKENS) else re.IGNORECASE
        out.append(re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", flags))
    return out


class PrivateNames:
    def __init__(self, companies: list[PrivateCompany]) -> None:
        self.companies = companies
        self._patterns = [_patterns(c) for c in companies]
        # Plain pieces of text one of which every mention must hold (the number, the ticker, the first word of
        # a name). A long text is searched for these first, which is fast; only a text that holds one is then
        # looked at closely with the patterns.
        needles: set[str] = set()
        for c in companies:
            needles.add(str(c.cik))
            if c.ticker:
                needles.add(c.ticker.lower())
            for form in [*short_names(c.name), *c.aliases]:
                words = [w for w in re.split(r"[\s,.\-]+", form) if w]
                if words:
                    needles.add(words[0].lower())
        self._needles = sorted(needles)

    def spans(self, text: str) -> list[tuple[int, int, int]]:
        """(start, end, number in the list) of every mention in `text`, none overlapping another."""
        found: list[tuple[int, int, int]] = []
        lowered = text.lower()
        if not any(needle in lowered for needle in self._needles):
            return found
        for n, patterns in enumerate(self._patterns, start=1):
            for pattern in patterns:
                found += [(m.start(), m.end(), n) for m in pattern.finditer(text)]
        # A name is found in several of its forms at once ("X Devices" inside "X Devices Inc"): pieces that
        # touch or overlap become one mention, so that nothing of the longest form is left standing.
        merged: list[tuple[int, int, int]] = []
        for start, end, n in sorted(found, key=lambda s: (s[0], -s[1])):
            if merged and start <= merged[-1][1]:
                last = merged[-1]
                merged[-1] = (last[0], max(last[1], end), last[2])
            else:
                merged.append((start, end, n))
        return merged

    def named(self, text: str) -> list[int]:
        """The numbers (1, 2, ...) of the companies of the list that `text` names."""
        return sorted({n for _, _, n in self.spans(text)})

    def ticker_notes(self) -> int:
        """How many tickers of the list are common abbreviations and are therefore only recognised where they are
        clearly used as a ticker."""
        return sum(1 for c in self.companies if c.ticker.upper() in COMMON_TOKENS)

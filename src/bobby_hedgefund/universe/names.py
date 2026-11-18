"""Clean company and sponsor names for comparing them (docs/decisions/0006, matching steps 1 and 2).

The cleaned form is only ever used to compare; the name as written is kept next to it everywhere.
"""

from __future__ import annotations

import re
import unicodedata

# Legal forms and the like at the end of a name. Removed from the end only, as often as they occur there.
LEGAL_ENDINGS = frozenset(
    [
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "co",
        "company",
        "ltd",
        "limited",
        "llc",
        "lp",
        "llp",
        "plc",
        "sa",
        "ag",
        "nv",
        "bv",
        "se",
        "gmbh",
        "kk",
        "pty",
        "pte",
        "holdings",
        "holding",
        "group",
    ]
)
# Words that say "a drug company" without telling one company from another. Left out of the "core" of a name.
SECTOR_WORDS = frozenset(
    [
        "therapeutics",
        "therapeutic",
        "pharmaceuticals",
        "pharmaceutical",
        "pharma",
        "biopharma",
        "biopharmaceuticals",
        "biopharmaceutical",
        "biosciences",
        "bioscience",
        "biotech",
        "biotechnology",
        "biotechnologies",
        "biologics",
        "sciences",
        "science",
        "medicines",
        "medicine",
        "oncology",
        "laboratories",
        "laboratory",
        "labs",
        "bio",
        "tx",
        "rx",
    ]
)
_NOT_WORD = re.compile(r"[^a-z0-9]+")
_DOTTED = re.compile(r"\b(?:[a-z]\.){2,}")


def clean(name: str) -> str:
    """Lower case, accents and punctuation removed, "&" read as "and", legal endings dropped."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    text = _DOTTED.sub(lambda m: m.group().replace(".", ""), text)  # "S.A." and "N.V." become "sa" and "nv"
    text = text.replace("&", " and ").replace("'", "")
    words = _NOT_WORD.sub(" ", text).split()
    while len(words) > 1 and words[-1] in LEGAL_ENDINGS:
        words.pop()
    return " ".join(words)


def core(cleaned: str) -> str:
    """The cleaned name without the words that only say it is a drug company. Empty when nothing else is left."""
    return " ".join(w for w in cleaned.split() if w not in SECTOR_WORDS and w != "and")

"""Checks on written text before it becomes a log line (docs/decisions/0004 point 2, 0007 point 6, 0009 point 5).

Three things are taken out of free text and sealed, so that a public line never has to be changed afterwards:
1. a quote that is too long (copied from a source file);
2. anything from prices: a sentence with a share price, a market value, a figure per share, or something worked
   out from a price (a rise or fall, a ratio, "trades below its cash");
3. any other amount of money that cannot be found in a filing among the session's inputs;
plus keys, e-mail addresses and paths of the home folder, which are kept nowhere.

The patterns can miss an unusual wording. The agents are told the rules too, and in doubt the check seals.
The fields that say what was decided (fund, company, action, size, fill rule) are never touched.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .private import PrivateNames
from .seal import Sealed

WINDOW = 8  # a copied run is found from 8 words in a row on
LONG_QUOTE = 40  # more than this many copied words in a row is a long quote
SHORT_QUOTE = 15  # more than two copies of more than this many words is too much quoting as well
SHORT_QUOTES_ALLOWED = 2
REMOVED = "[removed]"
SEALED = "[sealed]"

_WORD = re.compile(r"[A-Za-z0-9]+")
# A sentence ends at . ! or ? followed by a space or the end, or at a line break. A point inside a number or an
# address (1.5x, $4.20) does not end one, and neither does the point of a usual abbreviation.
_SENTENCE_END = re.compile(r"[.!?]+(?=\s|$)|\n")
_ABBREVIATIONS = frozenset(
    [
        "approx",
        "ca",
        "vs",
        "etc",
        "eg",
        "ie",
        "e.g",
        "i.e",
        "inc",
        "corp",
        "co",
        "ltd",
        "dr",
        "mr",
        "mrs",
        "ms",
        "prof",
        "fig",
        "no",
        "nos",
        "est",
        "al",
        "cf",
        "incl",
        "excl",
        "resp",
        "viz",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
        "st",
        "vol",
        "ph",
    ]
)
_UNITS = {
    "thousand": 10**3,
    "k": 10**3,
    "million": 10**6,
    "mm": 10**6,
    "mn": 10**6,
    "m": 10**6,
    "billion": 10**9,
    "bn": 10**9,
    "b": 10**9,
    "trillion": 10**12,
}
_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_UNIT = r"(?:thousand|million|billion|trillion|bn|mm|mn|m|k|b)"
_MONEY = re.compile(
    rf"(?:US\$|\$|USD\s?|EUR\s?|€|£)\s?(?P<a>{_NUMBER})(?:\s?(?P<au>{_UNIT})\b)?"
    rf"|\b(?P<b>{_NUMBER})\s?(?:(?P<bu>{_UNIT})\s)?(?:US\s)?(?:dollars?|USD|euros?|EUR)\b",
    re.IGNORECASE,
)
# An amount written without a currency ("peak sales of 2B", "300M in cash"): money when the sentence is about money.
_BARE_AMOUNT = re.compile(
    rf"\b(?P<a>{_NUMBER})\s?(?P<au>thousand|million|billion|trillion|bn|mm|mn|M|B|K)\b(?P<b>)(?P<bu>)"
)
_MONEY_TALK = re.compile(
    r"\b(?:sales|revenues?|cash|market|cap|worth|rais(?:e|ed|es|ing)|funding|financing|costs?|pric\w*|deals?"
    r"|milestones?|upfront|royalt\w+|debt|loans?|burn|spend\w*|income|loss(?:es)?|profits?|budget|valu\w+|paid|pays?"
    r"|payments?|proceeds|offering|runway|expenses?|grant)\b",
    re.IGNORECASE,
)
# Wordings that say something about a price or a market value.
_PRICE = re.compile(
    r"per[\s-]share|\d\s?(?:dollars?|USD|cents?)?\s?a share\b|per ADS|share price|stock price"
    r"|price of the (?:share|stock)|price target|target price"
    r"|market[\s-]value|market[\s-]cap|\bmkt\.? cap|capitali[sz]ation|valuation|valued at|enterprise value"
    r"|(?:negative|positive|low|high)\s+EV\b|\bEV\s?/"
    r"|trad(?:es|ed|ing) (?:at|below|above|near|under|around|for)|priced at|closing price|opening price"
    r"|closed at|opened at|52[\s-]week|all[\s-]time (?:high|low)"
    r"|(?:below|above|under|less than|more than|discount to|premium to|times|multiple of|relative to|versus|vs\.?)"
    r" (?:its |the |net )*cash"
    r"|price[\s-]to[\s-]|\b(?:upside|downside)\b|pric(?:ing|ed|es) in\b|\bis pricing\b"
    r"|market (?:is )?(?:implies|implying|assum\w+|expects?)"
    r"|\b(?:XBI|IBB|URTH|IWDA)\b",
    re.IGNORECASE,
)
# "Shares" and "the stock"; "the share of patients" is no share on an exchange.
_SHARE = re.compile(r"\bshares\b|\bstock\b|\bequity\b|\bthe share\b(?! of\b)|\bits share\b(?! of\b)", re.IGNORECASE)
_MOVE = re.compile(
    r"\b(?:rose|risen|rise|fell|fallen|fall|dropp?ed|drop|gain(?:ed|s)?|jump(?:ed|s)?|plung(?:ed|es?)|surg(?:ed|es?)"
    r"|declin(?:ed|es?)|los[te]|lost|rall(?:y|ied)|soar(?:ed|s)?|slump(?:ed|s)?|sank|climb(?:ed|s)?|up|down|run|ran"
    r"|halv(?:ed|es?)|doubl(?:ed|es?)|tripl(?:ed|es?)|return(?:ed|s)?|outperform(?:ed|s)?|underperform(?:ed|s)?"
    r"|below|above|off|since|peak|high|low|rebound(?:ed|s)?|recover(?:ed|s)?|sell[\s-]?off|crash(?:ed)?)\b|[+\u2212-]\s?\d",
    re.IGNORECASE,
)
_FIGURE = re.compile(
    r"\d\s?%|\bpercent\b|\d(?:\.\d+)?\s?x\b|\b(?:half|halv\w*|doubl\w*|twice|tripl\w*)\b", re.IGNORECASE
)
_PRICE_EVENT = re.compile(
    r"\b(?:shares?|stock|price|market value|market cap\w*|valuation)\b.{0,60}\b(?:above|below|over|under|at least"
    r"|at most|exceeds?|higher|lower|reach(?:es)?|rise|fall|doubl\w+|halv\w+|up|down)\b",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]{18,}[A-Za-z0-9]")
_HOME = re.compile(r"(?:/home/|/Users/|C:\\Users\\)[^\s/\\]+(?:[/\\][^\s]*)?")
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_FINGERPRINT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")  # a commit or a SHA-256: no key
TRACE_MARGIN = 20  # an amount counts as stated by a filing when it is within one twentieth (5%) of an amount in it


@dataclass(frozen=True)
class Copy:
    """A run of words in a text that also stands, word for word, in a source file."""

    start: int
    end: int
    words: int


@dataclass
class Cleaned:
    text: str
    removed: list[Sealed] = field(default_factory=list)


def _words(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group().lower()) for m in _WORD.finditer(text)]


def find_copies(texts: list[str], sources: Iterable[str]) -> list[list[Copy]]:
    """For each text: the runs of at least `WINDOW` words that are copied from one of the sources. The sources are
    read once, in passing, so a large filing costs time but no memory."""
    split = [_words(t) for t in texts]
    wanted: dict[tuple[str, ...], list[tuple[int, int]]] = {}
    for t, words in enumerate(split):
        for i in range(len(words) - WINDOW + 1):
            wanted.setdefault(tuple(w for _, _, w in words[i : i + WINDOW]), []).append((t, i))
    hit = [[False] * len(words) for words in split]
    if wanted:
        for source in sources:
            src = [m.group().lower() for m in _WORD.finditer(source)]
            for i in range(len(src) - WINDOW + 1):
                places = wanted.get(tuple(src[i : i + WINDOW]))
                if places:
                    for t, at in places:
                        for j in range(at, at + WINDOW):
                            hit[t][j] = True
    found: list[list[Copy]] = []
    for words, marks in zip(split, hit, strict=True):
        runs: list[Copy] = []
        i = 0
        while i < len(words):
            if not marks[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(words) and marks[j + 1]:
                j += 1
            runs.append(Copy(words[i][0], words[j][1], j - i + 1))
            i = j + 1
        found.append(runs)
    return found


def long_quotes(copies: list[Copy]) -> list[Copy]:
    """The copies that must go (docs/decisions/0009, point 5): every run of more than 40 words, and, when a text
    has more than two runs of more than 15 words, the third and later ones."""
    out = [c for c in copies if c.words > LONG_QUOTE]
    short = [c for c in copies if SHORT_QUOTE < c.words <= LONG_QUOTE]
    allowed = max(0, SHORT_QUOTES_ALLOWED - len(out))
    return sorted(out + short[allowed:], key=lambda c: c.start)


def looks_like_key(token: str) -> bool:
    """Is this run of letters and digits likely a key? A file name, a date, a filing number or a fingerprint is
    not: a key switches between letters and digits all the time, or is one long run without any pattern."""
    if _FINGERPRINT.match(token):
        return False
    plain = re.sub(r"[_.\-]", "", token)
    if len(plain) >= 32 and re.fullmatch(r"[0-9a-fA-F]+", plain):
        return True
    switches = sum(1 for a, b in itertools.pairwise(plain) if a.isdigit() != b.isdigit())
    if switches >= 6:
        return True
    unbroken = max((len(part) for part in re.split(r"[_.\-]", token)), default=0)
    return unbroken >= 32 and any(c.islower() for c in plain) and any(c.isupper() for c in plain)


def secrets(text: str) -> list[tuple[int, int]]:
    """(start, end) of everything in `text` that looks like a key, an e-mail address, a path of a home folder or
    a network address."""
    found = [(m.start(), m.end()) for pattern in (_EMAIL, _HOME, _IP) for m in pattern.finditer(text)]
    found += [(m.start(), m.end()) for m in _TOKEN.finditer(text) if looks_like_key(m.group())]
    return sorted(found)


def sentences(text: str) -> list[tuple[int, int]]:
    """(start, end) of every sentence in `text`, each without the white space around it."""
    out: list[tuple[int, int]] = []
    start = 0
    for m in _SENTENCE_END.finditer(text):
        if m.group().startswith("."):
            before = re.search(r"([A-Za-z.]+)$", text[start : m.start()])
            word = before.group(1).lower() if before else ""
            if word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()):
                continue  # "approx." or an initial: the sentence goes on
        out.append((start, m.end()))
        start = m.end()
    out.append((start, len(text)))
    trimmed = []
    for a, b in out:
        piece = text[a:b]
        if piece.strip():
            lead = len(piece) - len(piece.lstrip())
            trimmed.append((a + lead, a + lead + len(piece.strip())))
    return trimmed


def money_value(match: re.Match[str]) -> int | None:
    """An amount as whole dollars (or euros): '$1.5 million' -> 1500000. None when it cannot be read."""
    number = match.group("a") or match.group("b")
    unit = (match.group("au") or match.group("bu") or "").lower()
    try:
        whole, _, part = number.replace(",", "").partition(".")
        value = int(whole) * 10 ** len(part) + int(part or 0)
        return value * _UNITS.get(unit, 1) // 10 ** len(part)
    except ValueError:
        return None


def amounts(text: str) -> set[int]:
    """Every amount of money in a text, as whole dollars: the amounts a filing states."""
    found = {money_value(m) for m in _MONEY.finditer(text)}
    return {a for a in found if a is not None}


def about_price(sentence: str) -> bool:
    """Does this sentence say something about a price, a market value, an index fund, or a move of a share?"""
    if _PRICE.search(sentence):
        return True
    return bool(_SHARE.search(sentence) and _MOVE.search(sentence) and _FIGURE.search(sentence))


def traced(value: int | None, known: set[int]) -> bool:
    """Does a filing among the session's inputs state this amount (also when ours is rounded)?"""
    if value is None:
        return False
    return any(abs(value - k) * TRACE_MARGIN <= k for k in known)


def price_defined(event: str) -> bool:
    """Is this forecast event defined by a price? Such a forecast is refused: its outcome could not be published."""
    return bool(_PRICE.search(event) or _PRICE_EVENT.search(event))


def clean(
    text: str,
    copies: list[Copy] | None = None,
    known_amounts: set[int] | None = None,
    private: PrivateNames | None = None,
) -> Cleaned:
    """The text as it may be public, and what was taken out of it."""
    known = known_amounts or set()
    spans: list[tuple[int, int, str, Sealed]] = []
    for copy in long_quotes(copies or []):
        spans.append((copy.start, copy.end, REMOVED, Sealed(text[copy.start : copy.end], "quote")))
    for start, end in secrets(text):
        spans.append((start, end, REMOVED, Sealed(text[start:end], "secret", keep=False)))
    if private is not None:
        for start, end, _ in private.spans(text):
            spans.append((start, end, REMOVED, Sealed(text[start:end], "other")))
    for start, end in sentences(text):
        sentence = text[start:end]
        if about_price(sentence):
            spans.append((start, end, SEALED, Sealed(sentence, "price")))
            continue
        found = list(_MONEY.finditer(sentence))
        if _MONEY_TALK.search(sentence):
            found += list(_BARE_AMOUNT.finditer(sentence))
        for money in found:
            if not traced(money_value(money), known):
                spans.append((start + money.start(), start + money.end(), SEALED, Sealed(money.group(), "money")))
    if not spans:
        return Cleaned(text)
    # Longest first at each place, so a span inside another is dropped and none is counted twice.
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept: list[tuple[int, int, str, Sealed]] = []
    for span in spans:
        if kept and span[0] < kept[-1][1]:
            last = kept[-1]
            keep = last[3].keep and span[3].keep  # it holds a key or an address: then it is kept nowhere
            end = max(last[1], span[1])
            if end != last[1] or keep != last[3].keep:
                kept[-1] = (last[0], end, last[2], Sealed(text[last[0] : end], last[3].why, keep=keep))
            continue
        kept.append(span)
    out = []
    at = 0
    for start, end, mark, _ in kept:
        out.append(text[at:start])
        out.append(mark)
        at = end
    out.append(text[at:])
    return Cleaned("".join(out), [s[3] for s in kept])


# The free-text fields of each kind of record, as paths; "*" stands for every entry of a list. The numbers part of
# a thesis is not in it: scripts fill it in, with a fixed label and a value that is sealed when it comes from prices.
TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "decision": (
        "thesis/claim",
        "thesis/edge",
        "thesis/catalyst",
        "thesis/risks",
        "thesis/sell_if",
        "reason",
        "saw/*/summary",
    ),
    "forecast": ("event", "reasoning", "sources/*/summary"),
    "outcome": ("summary", "sources/*/summary"),
    "correction": ("text",),
    "restart": ("reason",),
    "refusal": ("reason",),
}
# Free text every kind of record may carry.
COMMON_TEXT = ("note", "dry_run", "why_empty")


def _places(value: Any, parts: list[str]) -> list[tuple[Any, Any]]:
    """(container, key) for every text the path points at."""
    if not parts:
        return []
    head, rest = parts[0], parts[1:]
    if head == "*":
        if not isinstance(value, list):
            return []
        if not rest:
            return [(value, i) for i, item in enumerate(value) if isinstance(item, str)]
        return [place for item in value for place in _places(item, rest)]
    if not isinstance(value, dict) or head not in value:
        return []
    if not rest:
        return [(value, head)] if isinstance(value[head], str) else []
    return _places(value[head], rest)


def _strings(value: Any, where: str = "") -> list[tuple[str, str]]:
    """(place, text) of every text anywhere in a record. Content that is sealed is not looked into."""
    if isinstance(value, str):
        return [(where, value)]
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found += _strings(item, f"{where}/{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found += _strings(item, f"{where}/{i}")
    return found


class TextCheck:
    """The checks for one session: the source files the agents could read, the amounts their filings state, and
    the companies that may not be named. Without any of these it still seals prices and removes keys."""

    def __init__(
        self,
        sources: list[str] | None = None,
        known_amounts: set[int] | None = None,
        private: PrivateNames | None = None,
    ) -> None:
        self.sources = sources or []
        self.known_amounts = known_amounts or set()
        self.private = private

    def clean_body(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        """Clean every free-text field of a record in place and add what was taken out to its `removed` list.
        Raises ValueError for a forecast whose event is defined by a price, and for a key, an address or a
        private company's name in a field that is not free text (there it cannot be cut out)."""
        if kind == "forecast" and isinstance(body.get("event"), str) and price_defined(body["event"]):
            raise ValueError("a forecast whose event is defined by a price is refused (docs/decisions/0009, point 5)")
        paths = (*TEXT_FIELDS.get(kind, ()), *COMMON_TEXT)
        places = [p for path in paths for p in _places(body, path.split("/"))]
        texts = [container[key] for container, key in places]
        copies = find_copies(texts, self.sources) if self.sources and texts else [[] for _ in texts]
        removed: list[Sealed] = []
        for (container, key), text, found in zip(places, texts, copies, strict=True):
            cleaned = clean(text, found, self.known_amounts, self.private)
            container[key] = cleaned.text
            removed += cleaned.removed
        if removed:
            body["removed"] = [*body.get("removed", []), *removed]
        self.refuse_leftovers(kind, body)
        return body

    def refuse_leftovers(self, kind: str, body: dict[str, Any]) -> None:
        """After cleaning, no text anywhere in the record may hold a key, an address or (outside the fields that
        say which company a record is about) a private company's name. The message names the field only."""
        for where, text in _strings(body):
            if secrets(text):
                raise ValueError(f"{kind}{where} holds something that looks like a key or an address")
        if self.private is not None:
            for where, text in _strings(body):
                if self.private.named(text):
                    raise ValueError(f"{kind}{where} names a company that may not be named in public")
            company = body.get("company")
            if isinstance(company, dict) and any(c.cik == company.get("cik") for c in self.private.companies):
                raise ValueError(f"{kind}/company is a company that may not be named in public")

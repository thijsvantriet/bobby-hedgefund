"""Read a stored SEC filing: the complete text file with a header and all documents of the filing in a row.

Only what the first steps need: what kind of filing it is and when, the items of an event report (8-K), and the
lines of an insider trade (Form 4). Everything else stays in the stored file, to be read later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from xml.etree.ElementTree import Element

from defusedxml import ElementTree  # refuses the XML tricks that can make a parser read files or use up memory
from defusedxml.common import DefusedXmlException

HEADER_END = b"</SEC-HEADER>"
MAX_HEADER = 200_000


class FilingError(Exception):
    """A stored file is not a filing in the expected layout."""


@dataclass(frozen=True)
class Header:
    accession: str
    form: str
    filed: date
    accepted: datetime | None  # the SEC's own acceptance time, US Eastern time
    period: date | None
    items: tuple[str, ...]  # 8-K: the item descriptions the SEC lists
    names: tuple[tuple[str, str], ...]  # (role, name): filer, subject company, filed by, issuer, reporting owner


@dataclass(frozen=True)
class Document:
    type: str
    sequence: str
    filename: str
    description: str
    text: bytes


@dataclass(frozen=True)
class Trade:
    owner: str
    roles: tuple[str, ...]  # director, officer (with title), ten percent owner, other
    security: str
    day: date | None
    code: str  # the SEC's transaction code: P bought, S sold, A granted, M option exercised, F shares for tax ...
    shares: float | None
    price: float | None
    acquired: bool | None  # True: acquired, False: disposed of
    shares_after: float | None
    derivative: bool  # an option or other derivative, not the share itself


def _day(text: str) -> date | None:
    try:
        return datetime.strptime(text.strip(), "%Y%m%d").date()
    except ValueError:
        return None


def header(body: bytes) -> Header:
    end = body.find(HEADER_END, 0, MAX_HEADER)
    if end < 0 or not body.startswith(b"<SEC-DOCUMENT>"):
        raise FilingError("no filing header found")
    fields: dict[str, list[str]] = {}
    names: list[tuple[str, str]] = []
    role = ""
    accepted = None
    for raw in body[:end].decode("latin-1").splitlines():
        line = raw.strip()
        if line.startswith("<ACCEPTANCE-DATETIME>"):
            try:
                accepted = datetime.strptime(line.removeprefix("<ACCEPTANCE-DATETIME>").strip(), "%Y%m%d%H%M%S")
            except ValueError:
                accepted = None
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if not value and key in ("FILER", "SUBJECT COMPANY", "FILED BY", "ISSUER", "REPORTING-OWNER"):
            role = key.lower().replace("-", " ")
        elif key == "COMPANY CONFORMED NAME" and role:
            names.append((role, value))
        elif value:
            fields.setdefault(key, []).append(value)
    try:
        filed = _day(fields["FILED AS OF DATE"][0])
        if filed is None:
            raise KeyError("FILED AS OF DATE")
        return Header(
            accession=fields["ACCESSION NUMBER"][0],
            form=fields["CONFORMED SUBMISSION TYPE"][0],
            filed=filed,
            accepted=accepted,
            period=_day(fields.get("CONFORMED PERIOD OF REPORT", [""])[0]),
            items=tuple(fields.get("ITEM INFORMATION", [])),
            names=tuple(names),
        )
    except (KeyError, IndexError) as exc:
        raise FilingError(f"the filing header misses {exc}") from None


def documents(body: bytes) -> list[Document]:
    """The documents of the filing, in order. The text of each is kept as bytes, exactly as stored."""
    out: list[Document] = []
    pos = 0
    while True:
        start = body.find(b"<DOCUMENT>", pos)
        if start < 0:
            return out
        end = body.find(b"</DOCUMENT>", start)
        end = len(body) if end < 0 else end
        text_at = body.find(b"<TEXT>", start, end)
        head = body[start : text_at if text_at >= 0 else end].decode("latin-1")
        tags = {}
        for line in head.splitlines():
            for tag in ("TYPE", "SEQUENCE", "FILENAME", "DESCRIPTION"):
                if line.startswith(f"<{tag}>"):
                    tags[tag] = line[len(tag) + 2 :].strip()
        text = body[text_at + 6 : end] if text_at >= 0 else b""
        text = text.removesuffix(b"\n").removesuffix(b"</TEXT>")
        out.append(
            Document(
                tags.get("TYPE", ""),
                tags.get("SEQUENCE", ""),
                tags.get("FILENAME", ""),
                tags.get("DESCRIPTION", ""),
                text,
            )
        )
        pos = end + 1


def _text(node: Element | None, path: str) -> str:
    found = node.find(path) if node is not None else None
    return (found.text or "").strip() if found is not None else ""


def _number(node: Element | None, path: str) -> float | None:
    try:
        return float(_text(node, path))
    except ValueError:
        return None


def _iso_day(text: str) -> date | None:
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _flag(node: Element, path: str) -> bool:
    return _text(node, path).lower() in ("1", "true")


def insider_trades(body: bytes) -> list[Trade]:
    """The transactions reported in an insider filing (Form 4 or 4/A). Empty when the filing reports none.
    Raises FilingError when the filing has no readable ownership document."""
    doc = next((d for d in documents(body) if d.type.upper().removesuffix("/A") == "4" and b"<XML>" in d.text), None)
    if doc is None:
        raise FilingError("no ownership document in this filing")
    start = doc.text.find(b"<XML>") + 5
    end = doc.text.find(b"</XML>", start)
    try:
        root = ElementTree.fromstring(doc.text[start : end if end >= 0 else len(doc.text)].strip())
    except (ElementTree.ParseError, DefusedXmlException, ValueError) as exc:
        raise FilingError(f"the ownership document is not readable XML ({type(exc).__name__})") from None
    owners: list[tuple[str, tuple[str, ...]]] = []
    for owner in root.findall("reportingOwner"):
        rel = owner.find("reportingOwnerRelationship")
        roles: list[str] = []
        if rel is not None:
            if _flag(rel, "isDirector"):
                roles.append("director")
            if _flag(rel, "isOfficer"):
                title = _text(rel, "officerTitle")
                roles.append(f"officer ({title})" if title else "officer")
            if _flag(rel, "isTenPercentOwner"):
                roles.append("ten percent owner")
            if _flag(rel, "isOther"):
                roles.append("other")
        owners.append((_text(owner, "reportingOwnerId/rptOwnerName"), tuple(roles)))
    owner_name = " / ".join(name for name, _ in owners if name)
    owner_roles = tuple(dict.fromkeys(role for _, roles in owners for role in roles))
    trades: list[Trade] = []
    for table, tag, derivative in (
        ("nonDerivativeTable", "nonDerivativeTransaction", False),
        ("derivativeTable", "derivativeTransaction", True),
    ):
        for row in root.findall(f"{table}/{tag}"):
            way = _text(row, "transactionAmounts/transactionAcquiredDisposedCode/value").upper()
            trades.append(
                Trade(
                    owner=owner_name,
                    roles=owner_roles,
                    security=_text(row, "securityTitle/value"),
                    day=_iso_day(_text(row, "transactionDate/value")),
                    code=_text(row, "transactionCoding/transactionCode"),
                    shares=_number(row, "transactionAmounts/transactionShares/value"),
                    price=_number(row, "transactionAmounts/transactionPricePerShare/value"),
                    acquired={"A": True, "D": False}.get(way),
                    shares_after=_number(row, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"),
                    derivative=derivative,
                )
            )
    return trades

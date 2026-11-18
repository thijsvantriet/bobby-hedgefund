"""Turn a document of an SEC filing into plain text for the agents to read. Tags, scripts and styles go; every
block starts on a new line; a table row becomes one line with its cells separated by " | "."""

from __future__ import annotations

import html
import re

_BLOCK = frozenset(
    [
        "p",
        "div",
        "br",
        "tr",
        "table",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ul",
        "ol",
        "hr",
        "title",
        "section",
        "article",
        "header",
        "footer",
        "pre",
        "blockquote",
        "center",
    ]
)
_SPACES = re.compile("[ \t\r\f\v\xa0]+")  # \xa0: the space that does not break a line
_BLANK_LINES = re.compile(r"\n\s*\n\s*(?:\n\s*)+")
_BINARY_START = re.compile(rb"^\s*begin \d{3} ")


_DROPPED = re.compile(
    r"<(script|style|head|ix:header)\b[^>]*>.*?</\1\s*>|<!--.*?-->", re.DOTALL | re.IGNORECASE
)  # with all that is inside them
_CELL = re.compile(r"<t[dh]\b[^>]*>", re.IGNORECASE)
_BLOCK_TAG = re.compile(r"</?(?:" + "|".join(sorted(_BLOCK)) + r")\b[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^<>]{0,2000}>")
_LOOKS_LIKE_HTML = re.compile(r"<(?:html|body|div|p|table|font|span|br)\b", re.IGNORECASE)


def strip_tags(raw: str) -> str:
    """The text of a page without its tags. Done with patterns, not with a parser: a quarterly report is several
    megabytes, and a parser written in Python takes most of a minute over a day's filings."""
    raw = _DROPPED.sub(" ", raw)
    raw = _CELL.sub(" | ", raw)
    raw = _BLOCK_TAG.sub("\n", raw)
    return html.unescape(_TAG.sub("", raw))


def is_binary(data: bytes) -> bool:
    """A picture or another file packed as text inside the filing: nothing to read."""
    return bool(_BINARY_START.match(data[:200])) or b"\x00" in data[:2000]


def to_text(data: bytes) -> str:
    """Plain text of a document. A document without tags is returned as it is, tidied."""
    try:
        raw = data.decode("utf-8")
    except UnicodeDecodeError:
        raw = data.decode("cp1252", errors="replace")  # the other encoding filings come in
    if "<" in raw and _LOOKS_LIKE_HTML.search(raw):
        raw = strip_tags(raw)
    lines = [_SPACES.sub(" ", line).strip(" |") for line in raw.split("\n")]
    text = "\n".join(line.strip() for line in lines)
    return _BLANK_LINES.sub("\n\n", text).strip() + "\n"

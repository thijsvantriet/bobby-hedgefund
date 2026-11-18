"""Turn a document of an SEC filing into plain text for the agents to read. Tags, scripts and styles go; every
block starts on a new line; a table row becomes one line with its cells separated by " | "."""

from __future__ import annotations

import re
from html.parser import HTMLParser

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
_SKIP = frozenset(("script", "style", "head", "ix:header", "xbrli:context", "xbrli:unit"))
_SPACES = re.compile("[ \t\r\f\v\xa0]+")  # \xa0: the space that does not break a line
_BLANK_LINES = re.compile(r"\n\s*\n\s*(?:\n\s*)+")
_BINARY_START = re.compile(rb"^\s*begin \d{3} ")


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self.skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def is_binary(data: bytes) -> bool:
    """A picture or another file packed as text inside the filing: nothing to read."""
    return bool(_BINARY_START.match(data[:200])) or b"\x00" in data[:2000]


def to_text(data: bytes) -> str:
    """Plain text of a document. A document without tags is returned as it is, tidied."""
    raw = data.decode("utf-8", errors="replace") if b"\xc3" in data[:20000] else data.decode("latin-1")
    if "<" in raw and re.search(r"<(?:html|body|div|p|table|font|span|br)\b", raw, re.IGNORECASE):
        parser = _Text()
        try:
            parser.feed(raw)
            parser.close()
        except Exception:  # a broken page: what was read up to there is still worth having
            pass
        raw = "".join(parser.parts)
    lines = [_SPACES.sub(" ", line).strip(" |") for line in raw.split("\n")]
    text = "\n".join(line.strip() for line in lines)
    return _BLANK_LINES.sub("\n\n", text).strip() + "\n"

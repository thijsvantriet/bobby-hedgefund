"""Sealed fields: content that may not be public (docs/decisions/0004, point 2; the list of what must be sealed is
docs/decisions/0007, point 6, and lives in `SEALED_CONTENT` below, in one place).

The public line shows, in place of the content, its fingerprint mixed with a random value. Worked out as:

    SHA-256( <random value as 64 hex characters> + line-feed + <the content written in the log's fixed form> )

Example (also a test): random value sixty-four times "0", content the text "12.34" (written as `"12.34"`, with
its quotes) gives the fingerprint in `EXAMPLE`. The random value is new for every field, so a price cannot be found
by trying all prices. Content and random value go to a private file; without them the fingerprint says nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..archive.store import sha256_hex
from . import canon

# Why a field is sealed. "price": content that comes from prices. "money": an amount in written text that could
# not be traced to a filing. "quote": a quote that was too long. "secret": a key or an address; that content is
# kept nowhere. "other": anything else that is private.
SEAL_WHY = ("price", "money", "quote", "secret", "other")

# docs/decisions/0007, point 6, as the code applies it. Anything in this list is written through `Sealed`.
SEALED_CONTENT = (
    "a price of any share or index fund",
    "the number of shares of a position, the amount of a trade, its trading cost, a fund's cash",
    "a market value of a company or a figure per share, in any written text",
    "anything worked out from a price: a rise or fall, a return, a ratio to a price or a market value",
    "the value or return of XBI, IBB or URTH",
    "the values of the Dice funds",
    "the value and return of our own funds, their place among the Dice funds, any comparison with an index fund",
)

EXAMPLE_SALT = "0" * 64
EXAMPLE_CONTENT = "12.34"
EXAMPLE = "2c8629da9624bda7b55097b55a1f701433a8d067599434728e2f7fd1b28d4f21"  # sha256 of the example


class SealError(Exception):
    pass


@dataclass(frozen=True)
class Sealed:
    """Content for the private file. `keep=False`: a key or an address, which is kept nowhere."""

    content: Any
    why: str = "price"
    keep: bool = True


def seal_fingerprint(salt: str, content: Any) -> str:
    return sha256_hex(salt.encode("ascii") + b"\n" + canon.encode(content))


def is_sealed_form(value: Any) -> bool:
    """The public form of a sealed field: {"sealed": <fingerprint>, "why": <reason>}."""
    return (
        isinstance(value, dict)
        and set(value) == {"sealed", "why"}
        and isinstance(value["sealed"], str)
        and len(value["sealed"]) == 64
        and all(c in "0123456789abcdef" for c in value["sealed"])
        and value["why"] in SEAL_WHY
    )


def sealed_fields(value: Any, where: str = "") -> list[tuple[str, dict[str, str]]]:
    """Every sealed field in a public record, with its place (for example /details or /thesis/numbers/0/value)."""
    if is_sealed_form(value):
        return [(where, value)]
    found: list[tuple[str, dict[str, str]]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found += sealed_fields(item, f"{where}/{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found += sealed_fields(item, f"{where}/{i}")
    return found

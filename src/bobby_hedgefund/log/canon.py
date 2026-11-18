"""One fixed way of writing a log line, so that its bytes, and with them its fingerprint, are the same on every
computer (docs/decisions/0004, point 1).

- keys in alphabetical order, no spaces, letters outside the basic English set written as codes;
- no numbers with a decimal point anywhere: different programs print those differently. Money is whole cents, a
  percentage is text such as "3%" or "2.5%", a price is text such as "12.34".

Every script that reads the log converts these the same way, with the functions below.
"""

from __future__ import annotations

import json
import re
from fractions import Fraction
from typing import Any

PCT = re.compile(r"^(0|[1-9]\d{0,2})(\.\d{1,2})?%$")
DECIMAL = re.compile(r"^(0|[1-9]\d*)(\.\d{1,6})?$")


class CanonError(Exception):
    pass


def check(value: Any, where: str = "record") -> None:
    """Raise CanonError unless `value` holds only text, whole numbers, yes/no, nothing, lists and named fields."""
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise CanonError(f"{where}: a number with a decimal point ({value!r}); write cents, or text such as '2.5%'")
    if isinstance(value, list):
        for i, item in enumerate(value):
            check(item, f"{where}/{i}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonError(f"{where}: a field name that is not text ({key!r})")
            check(item, f"{where}/{key}")
        return
    raise CanonError(f"{where}: {type(value).__name__} cannot be written to the log")


def encode(value: Any) -> bytes:
    """The one way a value is written: the bytes of a line, without the line-feed that ends it."""
    check(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def decode(line: bytes) -> Any:
    """Read a line back. Refuses a line that was not written by `encode` (other spacing, another key order, a
    number with a decimal point): such a line was made or changed by something else."""
    try:
        value = json.loads(line, parse_float=_no_float)
    except (ValueError, CanonError) as exc:
        raise CanonError(f"not a log line ({exc})") from None
    if encode(value) != line:
        raise CanonError("not written in the log's fixed form")
    return value


def _no_float(text: str) -> Any:
    raise CanonError(f"a number with a decimal point ({text})")


def is_pct(text: object) -> bool:
    return isinstance(text, str) and PCT.match(text) is not None


def pct_fraction(text: str) -> Fraction:
    """'2.5%' -> 1/40. Exact: fund sizes are never rounded on the way in."""
    if not is_pct(text):
        raise CanonError(f"not a percentage in the log's form: {text!r}")
    return Fraction(text[:-1]) / 100


def format_pct(part: Fraction) -> str:
    """1/40 -> '2.5%'. Rounded down to two decimals, so a limit is never passed by rounding."""
    if part < 0:
        raise CanonError("a percentage below zero")
    hundredths = (part * 10000).__floor__()
    whole, rest = divmod(hundredths, 100)
    if whole > 999:
        raise CanonError("a percentage above 999%")
    text = str(whole) if rest == 0 else f"{whole}.{rest:02d}".rstrip("0")
    return text + "%"


def decimal_fraction(text: str) -> Fraction:
    """'12.34' -> 617/50: a price as text, read exactly."""
    if not isinstance(text, str) or not DECIMAL.match(text):
        raise CanonError(f"not a number in the log's form: {text!r}")
    return Fraction(text)


def format_decimal(value: Fraction | float, places: int = 6) -> str:
    """A price as text, at most six decimals, no trailing zeros. Floats from a price file come in here once."""
    exact = Fraction(str(value)) if isinstance(value, float) else value
    if exact < 0:
        raise CanonError("a number below zero")
    scaled = round(exact * 10**places)
    whole, rest = divmod(scaled, 10**places)
    if rest == 0:
        return str(whole)
    return f"{whole}.{rest:0{places}d}".rstrip("0")

"""Local settings: values that live in the environment or in the `.env` file that git ignores.

Nothing here prints, logs or returns a value inside an error message: a setting can be a key or a contact address.
"""

from __future__ import annotations

import os
from pathlib import Path


class SettingsError(Exception):
    """A setting is missing or unreadable. The message names the setting, never its value."""


def env_file() -> Path:
    return Path(os.environ.get("BOBBY_ENV_FILE") or Path.home() / "projects" / "bobby-hedgefund" / ".env")


def parse_env(text: str) -> dict[str, str]:
    """Read `NAME=value` lines. Blank lines and lines starting with `#` are skipped; one pair of quotes around a
    value is removed. No variable expansion, no multi-line values."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name:
            values[name] = value
    return values


def get(name: str) -> str:
    """The value of one setting: the environment first, then the `.env` file. Raises SettingsError if empty."""
    value = os.environ.get(name, "").strip()
    if not value:
        path = env_file()
        try:
            value = parse_env(path.read_text(encoding="utf-8")).get(name, "").strip()
        except FileNotFoundError:
            value = ""
        except (OSError, UnicodeDecodeError) as exc:
            raise SettingsError(f"the settings file could not be read ({type(exc).__name__})") from None
    if not value:
        raise SettingsError(f"the setting {name} is not filled in (environment or the local .env file)")
    return value


def sec_contact() -> str:
    """The contact address the SEC asks for in every request (docs/decisions/0008, point 4). Never log it."""
    value = get("SEC_CONTACT_EMAIL")
    # One plain address on one line: anything else could smuggle a second header into the request.
    if any(ch.isspace() or ord(ch) < 33 or ord(ch) > 126 for ch in value) or value.count("@") != 1:
        raise SettingsError("the setting SEC_CONTACT_EMAIL is not one plain e-mail address")
    return value


def massive_key() -> str:
    """The key of the price service (docs/decisions/0007). Never log it; it is sent as a request header only."""
    value = get("MASSIVE_API_KEY")
    # One plain word: anything else could smuggle a second header into the request.
    if any(ch.isspace() or ord(ch) < 33 or ord(ch) > 126 for ch in value):
        raise SettingsError("the setting MASSIVE_API_KEY is not one plain key")
    return value

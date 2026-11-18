"""Where things live in the data folder, and the two modes a fund run can be in.

**Pilot** is the default everywhere: everything is written under `pilot/` inside the data folder, and nothing is
ever sent to GitHub. **Live** writes the real track record. It stays switched off until the owner creates a file
named `LIVE` in the data folder (the owner's go, docs/SPEC.md section 7); a command-line flag alone is not enough.
"""

from __future__ import annotations

import os
from pathlib import Path

PILOT = "pilot"
LIVE = "live"
MODES = (PILOT, LIVE)
LIVE_FILE = "LIVE"
STOP_FILE = "STOP"


class ModeError(Exception):
    pass


def data_dir() -> Path:
    """The data folder: outside the repository, inside the home folder that is backed up every night."""
    return Path(os.environ.get("BOBBY_DATA_DIR") or Path.home() / "bobby-hedgefund-data")


def check_mode(mode: str) -> str:
    if mode not in MODES:
        raise ModeError(f"unknown mode {mode!r}; it is {PILOT} or {LIVE}")
    if mode == LIVE and not (data_dir() / LIVE_FILE).is_file():
        raise ModeError(
            f"live mode is switched off. It starts with the owner's go: a file named {LIVE_FILE} in the data folder"
        )
    return mode


def mode_root(mode: str) -> Path:
    """The folder a mode writes in: the data folder itself for live, `pilot/` inside it for the pilot."""
    check_mode(mode)
    return data_dir() if mode == LIVE else data_dir() / PILOT


def staging_dir(mode: str) -> Path:
    """The public files as they are prepared: exactly the tree that is later placed in `track-record/`."""
    return mode_root(mode) / "staging"


def private_dir(mode: str) -> Path:
    """The private half of the log: what the public lines only show a fingerprint of (docs/decisions/0004)."""
    return mode_root(mode) / "log-private"

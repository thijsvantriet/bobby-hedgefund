"""Find and read archived files for an analysis, and remember which ones were read.

Reading takes no lock and writes nothing in the archive. Every file read is checked against its fingerprint in the
manifest, so an analysis never runs on a damaged file, and the list of inputs can be written next to its result.
"""

from __future__ import annotations

import lzma
from pathlib import Path
from typing import Any

from ..archive.store import ArchiveError, read_records, read_stored, sha256_hex


class InputError(Exception):
    """An archived file that the analysis needs is missing or damaged."""


class Inputs:
    def __init__(self, root: Path):
        self.root = root
        self.records = read_records(root)
        self.used: dict[str, str] = {}  # path in the archive -> fingerprint

    def files(self, source: str, name: str | None = None) -> list[dict[str, Any]]:
        """Manifest lines of stored files of a source, oldest first. An "unchanged" line counts: it points to
        the file that was found unchanged on that day."""
        return [
            r
            for r in self.records
            if r.get("source") == source
            and r.get("kind") in ("file", "unchanged")
            and (name is None or r.get("name") == name)
        ]

    def files_in_order(self, sources: tuple[str, ...]) -> list[dict[str, Any]]:
        """Stored files of several sources together, in the order they were saved."""
        return [r for r in self.records if r.get("source") in sources and r.get("kind") in ("file", "unchanged")]

    def newest(self, source: str, name: str) -> dict[str, Any]:
        found = self.files(source, name)
        if not found:
            raise InputError(f"the archive holds no file {name} of source {source}")
        return found[-1]

    def runs(self, source: str) -> list[dict[str, Any]]:
        return [r for r in self.records if r.get("source") == source and r.get("kind") == "run"]

    def read(self, rec: dict[str, Any]) -> bytes:
        try:
            body = read_stored(self.root, rec)
        except (OSError, ValueError, ArchiveError, KeyError, lzma.LZMAError) as exc:
            raise InputError(f"could not read {rec.get('path')}: {type(exc).__name__}") from exc
        if sha256_hex(body) != rec.get("sha256"):
            raise InputError(f"{rec.get('path')} does not match its fingerprint in the manifest")
        self.used[str(rec["path"])] = str(rec["sha256"])
        return body

    def listing(self) -> str:
        """One line per file read: fingerprint, two spaces, path (the layout of the `sha256sum` tool)."""
        return "".join(f"{digest}  {path}\n" for path, digest in sorted(self.used.items()))

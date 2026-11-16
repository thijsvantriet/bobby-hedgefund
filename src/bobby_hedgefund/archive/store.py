"""Append-only file store with a checksum manifest.

Rules this module keeps (docs/decisions/0001):
- a stored file is never overwritten, changed or deleted;
- every stored file has one line in `manifest.jsonl` with its SHA-256, written after the file is safely on disk;
- every manifest line carries the SHA-256 of the line before it, so a later edit of the manifest is detectable;
- file names are built from fixed source names and the clock, never from downloaded content.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import lzma
import os
import re
import secrets
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS = "0" * 64
MANIFEST = "manifest.jsonl"
RAW = "raw"
_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")


class ArchiveError(Exception):
    """Something is wrong with the archive itself (not with a download)."""


class Busy(ArchiveError):
    """Another archive run holds the lock."""


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_run_id(when: datetime | None = None) -> str:
    when = when or utcnow()
    return f"{when.astimezone(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"


def _check_name(kind: str, value: str) -> None:
    # Guards against path escapes: no slashes, no "..", no leading dot.
    if not _SAFE_NAME.match(value) or ".." in value:
        raise ArchiveError(f"unsafe {kind} name: {value!r}")


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_records(root: Path) -> list[dict[str, Any]]:
    """Read the manifest without taking the lock or changing anything (for `status` while a run is going)."""
    path = root / MANIFEST
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_bytes().split(b"\n"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue  # empty last piece, a half-written line of a running job, or damage (`verify` reports that)
        if isinstance(rec, dict):
            records.append(rec)
    return records


@dataclass
class VerifyReport:
    lines: int = 0
    files: int = 0
    unchanged: int = 0
    stored_bytes: int = 0
    problems: list[str] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


class Archive:
    """Use as a context manager: `with Archive(root) as archive: ...` (takes an exclusive lock)."""

    def __init__(self, root: Path):
        self.root = root
        self.manifest_path = root / MANIFEST
        self._lock_fd: int | None = None
        self._head = GENESIS
        self._last_file: dict[tuple[str, str], dict[str, Any]] = {}
        self._last_ok_run: dict[str, dict[str, Any]] = {}
        self.records: list[dict[str, Any]] = []

    # -- opening and locking -------------------------------------------------------------------------------------

    def __enter__(self) -> Archive:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.root / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise Busy("another archive run is in progress") from None
        self._lock_fd = fd
        try:
            torn = self._quarantine_torn_tail()
            self._load()
            if torn:
                self.append({"kind": "repair", "ts": iso(utcnow()), **torn})
        except BaseException:
            self._unlock()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        self._unlock()

    def _unlock(self) -> None:
        if self._lock_fd is not None:
            os.close(self._lock_fd)  # closing the descriptor releases the lock
            self._lock_fd = None

    def _require_open(self) -> None:
        if self._lock_fd is None:
            raise ArchiveError("archive is not open; use it as a context manager")

    # -- manifest ------------------------------------------------------------------------------------------------

    def _quarantine_torn_tail(self) -> dict[str, Any] | None:
        """A power cut can leave half a line at the end of the manifest. Such a line was never a valid record.

        Move those bytes to a separate file and cut the manifest back to its last complete line, so archiving can
        continue. The caller records the event in the manifest. Complete lines are never touched.
        """
        if not self.manifest_path.exists():
            return None
        data = self.manifest_path.read_bytes()
        if not data or data.endswith(b"\n"):
            return None
        keep = data.rfind(b"\n") + 1  # 0 when there is no complete line at all
        torn = data[keep:]
        name = f"manifest.torn-{utcnow():%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"
        fd = os.open(self.root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            _write_all(fd, torn)
            os.fsync(fd)
        finally:
            os.close(fd)
        fd = os.open(self.manifest_path, os.O_WRONLY)
        try:
            os.ftruncate(fd, keep)
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_dir(self.root)
        return {"torn_file": name, "torn_bytes": len(torn), "torn_sha256": sha256_hex(torn)}

    def _iter_lines(self) -> Iterator[bytes]:
        if not self.manifest_path.exists():
            return
        with open(self.manifest_path, "rb") as fh:
            for line in fh:
                yield line.rstrip(b"\n")

    def _load(self) -> None:
        self._head = GENESIS
        self._last_file.clear()
        self._last_ok_run.clear()
        self.records = []
        for line in self._iter_lines():
            self._head = sha256_hex(line)
            try:
                rec = json.loads(line)
            except ValueError:
                continue  # `verify` reports it; a damaged line must not stop new downloads from being saved
            if isinstance(rec, dict):
                self._remember(rec)

    def _remember(self, rec: dict[str, Any]) -> None:
        self.records.append(rec)
        kind = rec.get("kind")
        if kind in ("file", "unchanged"):
            self._last_file[(str(rec.get("source")), str(rec.get("name")))] = rec
        elif kind == "run" and rec.get("status") == "ok":
            self._last_ok_run[str(rec.get("source"))] = rec

    def append(self, rec: dict[str, Any]) -> dict[str, Any]:
        """Add one record to the manifest. Existing lines are never rewritten."""
        self._require_open()
        full = {"v": 1, **rec, "prev": self._head}
        line = json.dumps(full, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if b"\n" in line:  # json.dumps escapes newlines; this guards the one-record-per-line rule anyway
            raise ArchiveError("manifest record would contain a line break")
        created = not self.manifest_path.exists()
        fd = os.open(self.manifest_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            _write_all(fd, line + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        if created:
            _fsync_dir(self.root)
        self._head = sha256_hex(line)
        self._remember(full)
        return full

    def last_ok_run(self, source: str) -> dict[str, Any] | None:
        return self._last_ok_run.get(source)

    def record_run(
        self,
        source: str,
        run: str,
        status: str,
        *,
        error: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "kind": "run",
            "ts": iso(utcnow()),
            "run": run,
            "source": source,
            "status": status,
        }
        if error:
            rec["error"] = error[:500]
        if meta:
            rec["meta"] = meta
        return self.append(rec)

    # -- files ---------------------------------------------------------------------------------------------------

    def store(
        self,
        source: str,
        name: str,
        body: bytes,
        *,
        run: str,
        when: datetime | None = None,
        compress: bool = False,
        dedup: bool = True,
        info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Save `body` as a new file and add its manifest line. Returns the manifest record.

        With `dedup`, a body identical to the last one saved under the same source and name is not saved again;
        the manifest gets an "unchanged" line that points to the existing file.
        """
        self._require_open()
        _check_name("source", source)
        _check_name("file", name)
        when = (when or utcnow()).astimezone(UTC)
        digest = sha256_hex(body)
        base: dict[str, Any] = {"ts": iso(when), "run": run, "source": source, "name": name}
        extra = dict(info or {})

        last = self._last_file.get((source, name))
        if dedup and last and last.get("sha256") == digest and (self.root / str(last.get("path"))).is_file():
            rec = {"kind": "unchanged", **base, "path": last["path"], "sha256": digest, "bytes": len(body)}
            return self.append({**rec, **extra})

        rel_dir = Path(RAW) / source / f"{when:%Y}" / f"{when:%m}" / f"{when:%d}"
        abs_dir = self.root / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        data = lzma.compress(body, preset=6) if compress else body
        suffix = ".xz" if compress else ""

        tmp = abs_dir / f".tmp-{secrets.token_hex(8)}"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            try:
                _write_all(fd, data)
                os.fchmod(fd, 0o400)  # read-only: a reminder that archived files are never edited
                os.fsync(fd)
            finally:
                os.close(fd)
            rel = self._link_without_overwrite(tmp, rel_dir, f"{when:%H%M%S}Z", name + suffix)
        finally:
            tmp.unlink(missing_ok=True)
        _fsync_dir(abs_dir)

        rec = {
            "kind": "file",
            **base,
            "path": rel.as_posix(),
            "sha256": digest,
            "bytes": len(body),
            "stored_bytes": len(data),
            "compress": "xz" if compress else None,
        }
        return self.append({**rec, **extra})

    def _link_without_overwrite(self, tmp: Path, rel_dir: Path, stamp: str, filename: str) -> Path:
        # os.link refuses to replace an existing file, unlike a rename. Same-second name clashes get a counter.
        for n in range(100):
            rel = rel_dir / (f"{stamp}_{filename}" if n == 0 else f"{stamp}-{n}_{filename}")
            try:
                os.link(tmp, self.root / rel)
                return rel
            except FileExistsError:
                continue
        raise ArchiveError(f"could not find a free file name for {filename} in {rel_dir}")

    def read(self, rec: dict[str, Any]) -> bytes:
        """Return the original bytes of a stored file (decompressed if it was stored compressed)."""
        rel = Path(str(rec["path"]))
        if rel.is_absolute() or ".." in rel.parts or rel.parts[:1] != (RAW,):
            raise ArchiveError(f"manifest path points outside the archive: {rec['path']!r}")
        data = (self.root / rel).read_bytes()
        return lzma.decompress(data) if rel.suffix == ".xz" else data

    # -- checking ------------------------------------------------------------------------------------------------

    def verify(self, *, quick: bool = False) -> VerifyReport:
        """Check the manifest chain and (unless `quick`) re-hash every stored file. Changes nothing."""
        report = VerifyReport()
        prev = GENESIS
        known: dict[str, str] = {}  # path -> sha256
        for number, line in enumerate(self._iter_lines(), start=1):
            report.lines += 1
            line_hash = sha256_hex(line)
            try:
                rec = json.loads(line)
                if not isinstance(rec, dict):
                    raise ValueError("not an object")
            except ValueError:
                report.problems.append(f"line {number}: not valid JSON")
                prev = line_hash
                continue
            if rec.get("prev") != prev:
                report.problems.append(f"line {number}: chain broken (a line was changed, removed or added before it)")
            prev = line_hash
            kind = rec.get("kind")
            if kind == "file":
                report.files += 1
                self._verify_file(rec, number, known, report, quick=quick)
            elif kind == "unchanged":
                report.unchanged += 1
                path = str(rec.get("path"))
                if known.get(path) != rec.get("sha256"):
                    report.problems.append(f"line {number}: 'unchanged' points to {path}, which has no matching file")
        if self.manifest_path.exists() and not self.manifest_path.read_bytes().endswith(b"\n") and report.lines:
            report.problems.append("manifest ends with an incomplete line")
        raw_dir = self.root / RAW
        if raw_dir.is_dir():
            for path in sorted(raw_dir.rglob("*")):
                if path.is_file() and path.relative_to(self.root).as_posix() not in known:
                    report.orphans.append(path.relative_to(self.root).as_posix())
        return report

    def _verify_file(
        self, rec: dict[str, Any], number: int, known: dict[str, str], report: VerifyReport, *, quick: bool
    ) -> None:
        path = str(rec.get("path"))
        if path in known:
            report.problems.append(f"line {number}: {path} is listed twice")
            return
        known[path] = str(rec.get("sha256"))
        try:
            if quick:
                size = (self.root / path).stat().st_size
            else:
                body = self.read(rec)
                size = (self.root / path).stat().st_size
                if sha256_hex(body) != rec.get("sha256") or len(body) != rec.get("bytes"):
                    report.problems.append(f"line {number}: {path} does not match its recorded checksum")
        except FileNotFoundError:
            report.problems.append(f"line {number}: {path} is missing")
            return
        except (OSError, lzma.LZMAError, ArchiveError) as exc:
            report.problems.append(f"line {number}: {path} cannot be read ({type(exc).__name__})")
            return
        if size != rec.get("stored_bytes"):
            report.problems.append(f"line {number}: {path} has a different size on disk than recorded")
        report.stored_bytes += size

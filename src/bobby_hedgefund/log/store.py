"""The decision log on disk (docs/decisions/0004, point 1).

- One file per session day, `log/<year>/<month>/<date>.jsonl`, one record per line. Lines are only ever added.
- Every record carries the fingerprint of the record before it, also across day files. The fingerprint of a record
  is the SHA-256 of: the fingerprint of the record before it (as text), a line-feed, and the exact bytes of the
  line without its own line-feed. The first record uses a fixed starting value (`START`), one for the real log and
  another for the pilot, so that a pilot record can never be placed in the real log.
- `HEAD` holds the newest fingerprint and the number of records; it catches a log that lost its last lines.
- A line that is written is final: after a crash the next writer adds lines, it never writes one again.
- Sealed content goes to a private file, which is safely on disk before the public line is written.

This chain rule differs from the archive's (docs/decisions/0001), which fingerprints the line alone.
"""

from __future__ import annotations

import copy
import fcntl
import os
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from .. import paths
from ..archive.store import iso, sha256_hex, utcnow
from ..universe.output import write_new_bytes
from . import canon, records
from . import text as text_check
from .seal import SEAL_WHY, Sealed, is_sealed_form, seal_fingerprint, sealed_fields

FORMAT = 1
START = {mode: sha256_hex(f"bobby-hedgefund decision log, format 1, {mode}".encode("ascii")) for mode in paths.MODES}
LOG = "log"
HEAD = "HEAD"
LOCK = ".lock"
# Left in the private folder by a purge (docs/decisions/0007, point 4). Its first line, "upto <number>", says up to
# which record the private content was deleted; missing content of a later record is damage.
DELETED = "DELETED-0007"
RESERVED = ("v", "seq", "kind", "time", "mode", "prev")
_DAY_FILE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.jsonl$")


class LogError(Exception):
    pass


def fingerprint(prev: str, line: bytes) -> str:
    return sha256_hex(prev.encode("ascii") + b"\n" + line)


@dataclass(frozen=True)
class Entry:
    seq: int
    kind: str
    record: dict[str, Any]
    sha256: str
    file: str  # relative to the staging folder, for example log/2026/11/2026-11-18.jsonl
    line: int

    @property
    def day(self) -> date:
        return date.fromisoformat(Path(self.file).name.removesuffix(".jsonl"))


@dataclass
class Report:
    """What `verify` found. `problems` is damage; `notes` is worth knowing but harmless."""

    records: int = 0
    files: int = 0
    sealed: int = 0
    sealed_checked: int = 0
    sealed_deleted: int = 0
    sealed_not_kept: int = 0
    sealed_not_checked: int = 0
    head: str = ""
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def day_path(day: date) -> str:
    return f"{LOG}/{day:%Y}/{day:%m}/{day.isoformat()}.jsonl"


def day_files(staging: Path) -> list[Path]:
    """The day files, oldest first. Anything else inside `log/` is refused: it does not belong there."""
    root = staging / LOG
    if not root.exists():
        return []
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() and not path.is_symlink():
            continue
        if path.name.startswith(".") and not path.is_symlink():
            continue  # a half-written first line of a day, left by a crash: it was never part of the log
        rel = path.relative_to(root).parts
        match = _DAY_FILE.match(path.name)
        if path.is_symlink() or match is None or len(rel) != 3 or rel[0] != match[1] or rel[1] != match[2]:
            raise LogError(f"{LOG}/{path.relative_to(root).as_posix()} does not belong in the log folder")
        try:
            date.fromisoformat(path.name.removesuffix(".jsonl"))
        except ValueError:
            raise LogError(f"{LOG}/{path.relative_to(root).as_posix()} is not named after a day") from None
        found.append(path)
    return found


def read_entries(staging: Path, mode: str) -> list[Entry]:
    """Every record, oldest first, with the whole chain checked. Raises LogError at the first thing that is wrong."""
    entries: list[Entry] = []
    prev = START[mode]
    for path in day_files(staging):
        rel = path.relative_to(staging).as_posix()
        data = path.read_bytes()
        if not data:
            raise LogError(f"{rel} is empty")
        if not data.endswith(b"\n"):
            raise LogError(f"{rel} ends with half a line")
        for number, raw in enumerate(data[:-1].split(b"\n"), start=1):
            where = f"{rel}, line {number}"
            try:
                rec = canon.decode(raw)
            except canon.CanonError as exc:
                raise LogError(f"{where}: {exc}") from None
            if not isinstance(rec, dict) or not isinstance(rec.get("kind"), str):
                raise LogError(f"{where}: not a log record")
            if rec.get("v") != FORMAT:
                raise LogError(f"{where}: format version {rec.get('v')!r} is not known to this program")
            if rec.get("mode") != mode:
                raise LogError(f"{where}: a record of mode {rec.get('mode')!r} in the {mode} log")
            if rec.get("seq") != len(entries) + 1 or rec.get("prev") != prev:
                raise LogError(
                    f"{where}: changed, removed or re-ordered, here or just before (the chain of fingerprints breaks)"
                )
            prev = fingerprint(prev, raw)
            entries.append(Entry(len(entries) + 1, rec["kind"], rec, prev, rel, number))
    return entries


def read_head(staging: Path) -> dict[str, Any] | None:
    path = staging / HEAD
    if not path.exists():
        return None
    try:
        head = canon.decode(path.read_bytes().removesuffix(b"\n"))
    except (canon.CanonError, OSError) as exc:
        raise LogError(f"{HEAD} cannot be read ({exc})") from None
    if (
        not isinstance(head, dict)
        or not isinstance(head.get("records"), int)
        or not isinstance(head.get("sha256"), str)
    ):
        raise LogError(f"{HEAD} is not a head file")
    return head


def _write_head(staging: Path, count: int, sha256: str) -> None:
    data = canon.encode({"records": count, "sha256": sha256, "v": FORMAT}) + b"\n"
    tmp = staging / f".{HEAD}-{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(staging / HEAD)  # HEAD is the one file of the log that is replaced
    _fsync_dir(staging)


def _make_dirs(folder: Path, stop: Path) -> None:
    """Create `folder` (inside `stop`) and make every new level safe on disk, so that a power cut cannot keep
    HEAD and lose the day file."""
    new: list[Path] = []
    level = folder
    while level != stop and not level.exists():
        new.append(level)
        level = level.parent
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    for made in new:
        _fsync_dir(made.parent)


def deleted_upto(private: Path) -> int | None:
    """Up to which record a purge deleted the private content; None when there was no purge."""
    marker = private / DELETED
    if not marker.exists():
        return None
    first = marker.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0].split()
    return int(first[1]) if len(first) == 2 and first[0] == "upto" and first[1].isdigit() else 0


def _fsync_dir(folder: Path) -> None:
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def head_state(entries: list[Entry], head: dict[str, Any] | None, mode: str) -> str:
    """Compare HEAD with the chain. Returns "" when they agree, or a note for the one harmless difference: HEAD
    one record behind (a crash between writing a line and writing HEAD). Everything else raises LogError."""
    count = len(entries)
    if head is None:
        if count <= 1:
            return "" if count == 0 else f"{HEAD} is missing; the log has one record (a crash right after it)"
        raise LogError(f"{HEAD} is missing while the log has {count} records")
    at = head["records"]
    if at > count:
        raise LogError(f"the log lost its newest lines: {HEAD} says {at} records, the files hold {count}")
    expected = entries[at - 1].sha256 if at > 0 else START[mode]
    if head["sha256"] != expected:
        raise LogError(f"{HEAD} does not match record {at} of the log")
    if at == count:
        return ""
    if at == count - 1:
        return f"{HEAD} is one record behind (a crash between writing a line and {HEAD})"
    raise LogError(f"{HEAD} is {count - at} records behind; a crash can only leave it one behind")


def _seal(value: Any, where: str, private: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, Sealed):
        if value.why not in SEAL_WHY:
            raise LogError(f"{where}: unknown reason to seal {value.why!r}")
        try:
            canon.check(value.content, where)
        except canon.CanonError as exc:
            raise LogError(str(exc)) from None
        salt = secrets.token_hex(32)
        private[where] = {"salt": salt, "content": value.content} if value.keep else {"kept": False}
        return {"sealed": seal_fingerprint(salt, value.content), "why": value.why}
    if is_sealed_form(value):
        raise LogError(f"{where}: a sealed field can only be made by the log writer")
    if isinstance(value, dict):
        return {key: _seal(item, f"{where}/{key}", private) for key, item in value.items()}
    if isinstance(value, list):
        return [_seal(item, f"{where}/{i}", private) for i, item in enumerate(value)]
    return value


def _put(value: Any, where: str, content: Any) -> None:
    """Replace the sealed field at `where` (for example /details) inside `value` by its content."""
    parts = where.strip("/").split("/")
    for part in parts[:-1]:
        value = value[int(part)] if isinstance(value, list) else value[part]
    last = parts[-1]
    if isinstance(value, list):
        value[int(last)] = content
    else:
        value[last] = content


class Log:
    def __init__(self, staging: Path, private: Path | None, mode: str) -> None:
        if mode not in paths.MODES:
            raise LogError(f"unknown mode {mode!r}")
        self.staging = staging
        self.private = private
        self.mode = mode

    @classmethod
    def for_mode(cls, mode: str) -> Log:
        paths.check_mode(mode)
        return cls(paths.staging_dir(mode), paths.private_dir(mode), mode)

    def entries(self) -> list[Entry]:
        return read_entries(self.staging, self.mode)

    def private_path(self, seq: int) -> Path:
        if self.private is None:
            raise LogError("this copy of the log has no private files")
        return self.private / f"{seq:08d}.json"

    def private_fields(self, seq: int) -> dict[str, dict[str, Any]] | None:
        """The private half of one record: place -> {salt, content}. None when there is no private file."""
        path = self.private_path(seq)
        if not path.exists():
            return None
        try:
            data = canon.decode(path.read_bytes().removesuffix(b"\n"))
        except (canon.CanonError, OSError) as exc:
            raise LogError(f"the private file of record {seq} cannot be read ({exc})") from None
        if not isinstance(data, dict) or data.get("seq") != seq or not isinstance(data.get("fields"), dict):
            raise LogError(f"the private file of record {seq} is not a private file of that record")
        return data["fields"]

    def opened(self, entry: Entry) -> dict[str, Any]:
        """The record with every sealed field replaced by its content, each checked against its fingerprint.
        A field whose content was never kept (a key, an address) stays as it is."""
        record = copy.deepcopy(entry.record)
        found = sealed_fields(entry.record)
        if not found:
            return record
        fields = self.private_fields(entry.seq)
        if fields is None:
            raise LogError(f"record {entry.seq} has sealed content but no private file")
        for where, form in found:
            kept = fields.get(where)
            if kept is None:
                raise LogError(f"record {entry.seq}: no private content for {where}")
            if kept.get("kept") is False:
                continue
            if seal_fingerprint(kept["salt"], kept["content"]) != form["sealed"]:
                raise LogError(f"record {entry.seq}: the private content of {where} does not match its fingerprint")
            _put(record, where, copy.deepcopy(kept["content"]))
        return record

    def writer(
        self,
        day: date,
        clock: Callable[[], datetime] = utcnow,
        check: text_check.TextCheck | None = None,
    ) -> Writer:
        """`check`: the session's checks on written text (its source files, the amounts its filings state, the
        companies that may not be named). Without one, every record is still checked for prices and keys."""
        return Writer(self, day, clock, check or text_check.TextCheck())

    def verify(self, *, check_private: bool = True) -> Report:
        """Re-read everything and say what is wrong. Writes nothing."""
        report = Report()
        try:
            entries = self.entries()
            report.files = len(day_files(self.staging))
        except (LogError, OSError) as exc:
            report.problems.append(str(exc))
            return report
        report.records = len(entries)
        try:
            head = read_head(self.staging)
            note = head_state(entries, head, self.mode)
            report.head = entries[-1].sha256 if entries else START[self.mode]
            if note:
                report.notes.append(note)
        except LogError as exc:
            report.problems.append(str(exc))
        kinds: dict[int, str] = {}
        for entry in entries:
            try:
                records.validate_public(entry.record)
                records.check_references(entry.kind, entry.record, kinds)
            except records.RecordError as exc:
                report.problems.append(f"record {entry.seq} ({entry.file}, line {entry.line}): {exc}")
            kinds[entry.seq] = entry.kind
        self._verify_sealed(entries, report, check_private)
        return report

    def _verify_sealed(self, entries: list[Entry], report: Report, check_private: bool) -> None:
        have_private = check_private and self.private is not None
        upto = deleted_upto(self.private) if have_private and self.private is not None else None
        for entry in entries:
            found = sealed_fields(entry.record)
            report.sealed += len(found)
            if not found:
                continue
            if not have_private:
                report.sealed_not_checked += len(found)
                continue
            try:
                fields = self.private_fields(entry.seq)
            except LogError as exc:
                report.problems.append(str(exc))
                continue
            for where, form in found:
                kept = (fields or {}).get(where)
                if kept is None:
                    if upto is not None and entry.seq <= upto:
                        report.sealed_deleted += 1
                    else:
                        report.problems.append(f"record {entry.seq}: the private content of {where} is missing")
                elif kept.get("kept") is False:
                    report.sealed_not_kept += 1
                elif (
                    not isinstance(kept.get("salt"), str)
                    or "content" not in kept
                    or seal_fingerprint(kept["salt"], kept["content"]) != form["sealed"]
                ):
                    report.problems.append(
                        f"record {entry.seq}: the private content of {where} does not match its fingerprint"
                    )
                else:
                    report.sealed_checked += 1
        if not have_private:
            if report.sealed:
                report.notes.append("sealed content was not checked: the private files are not part of this copy")
            return
        assert self.private is not None
        if report.sealed_deleted:
            report.notes.append(f"{report.sealed_deleted} sealed fields: content deleted under record 0007")
        if self.private.is_dir():
            with_sealed = {entry.seq for entry in entries if sealed_fields(entry.record)}
            for path in sorted(self.private.glob("*.json")):
                number = path.name.split(".")[0]
                if ".orphan-" in path.name:
                    report.notes.append(f"{path.name}: set aside after a crash, belongs to no record")
                elif not number.isdigit() or int(number) > len(entries):
                    report.notes.append(f"{path.name}: belongs to no record (a crash before its line was written)")
                elif int(number) not in with_sealed:
                    report.notes.append(f"{path.name}: a private file for a record that has no sealed content")


class Writer:
    """Adds records. Holds the log's lock from `with` to the end, and checks the whole chain before it writes."""

    def __init__(self, log: Log, day: date, clock: Callable[[], datetime], check: text_check.TextCheck) -> None:
        self.log = log
        self.day = day
        self.clock = clock
        self.check = check
        self.note = ""
        self._fd: int | None = None
        self._seq = 0
        self._prev = ""
        self._kinds: dict[int, str] = {}
        self._last_file = ""
        self._last_line = 0

    def __enter__(self) -> Writer:
        staging = self.log.staging
        staging.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._fd = os.open(staging / LOCK, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise LogError("another program is writing the log right now") from None
            entries = self.log.entries()
            self.note = head_state(entries, read_head(staging), self.log.mode)
            if entries and entries[-1].day > self.day:
                raise LogError(
                    f"the log already has records of {entries[-1].day}; a record of {self.day} cannot follow"
                )
            self._seq = len(entries)
            self._prev = entries[-1].sha256 if entries else START[self.log.mode]
            self._kinds = {entry.seq: entry.kind for entry in entries}
            if entries:
                self._last_file, self._last_line = entries[-1].file, entries[-1].line
            if self.note:
                _write_head(staging, self._seq, self._prev)  # bring HEAD up to date with the lines that exist
        except BaseException:
            os.close(self._fd)
            self._fd = None
            raise
        return self

    def __exit__(
        self, kind: type[BaseException] | None, value: BaseException | None, trace: TracebackType | None
    ) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def add(self, kind: str, body: dict[str, Any]) -> Entry:
        """Write one record. It is final the moment this returns.

        **An exception means that no public line was written.** Once the line is safely on disk this does not
        raise any more: if HEAD cannot be written then, that is noted (`self.note`) and the next writer repairs
        it. So a caller that tries again after an exception can never write the same decision twice.

        The record's free text is checked first (docs/decisions/0004, point 2): what may not be public is cut out
        and sealed. `body` itself is not changed."""
        if self._fd is None:
            raise LogError("the writer is not open; use it inside `with`")
        clash = sorted(set(body) & set(RESERVED))
        if clash:
            raise LogError(f"{kind}: the fields {', '.join(clash)} are written by the log itself")
        body = copy.deepcopy(body)
        try:
            records.validate(kind, body)  # first, so that the text check works on a record of the right shape
            self.check.clean_body(kind, body)
            records.validate(kind, body)
            records.check_references(kind, body, self._kinds)
        except (records.RecordError, ValueError) as exc:
            raise LogError(f"not written: {exc}") from None
        private: dict[str, dict[str, Any]] = {}
        public = _seal(body, "", private)
        seq = self._seq + 1
        record = {
            "v": FORMAT,
            "seq": seq,
            "kind": kind,
            "time": iso(self.clock()),
            "mode": self.log.mode,
            "prev": self._prev,
            **public,
        }
        try:
            line = canon.encode(record)
        except canon.CanonError as exc:
            raise LogError(f"not written: {exc}") from None
        if private:
            self._write_private(seq, kind, private)  # safely on disk before the public line exists
        rel = day_path(self.day)
        path = self.log.staging / rel
        data = line + b"\n"
        try:
            if path.exists():
                self._append(path, data)
            else:
                self._first_line(path, data)
        except OSError as exc:
            raise LogError(f"could not write the log ({type(exc).__name__}); nothing was added") from exc
        # From here on the record exists: nothing below may raise.
        sha = fingerprint(self._prev, line)
        self._seq, self._prev = seq, sha
        self._kinds[seq] = kind
        self._last_line = self._last_line + 1 if rel == self._last_file else 1
        self._last_file = rel
        try:
            _write_head(self.log.staging, seq, sha)
        except OSError as exc:
            self.note = f"{HEAD} could not be written ({type(exc).__name__}); the next writer repairs it"
        return Entry(seq, kind, record, sha, rel, self._last_line)

    def _append(self, path: Path, data: bytes) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND)
        try:
            size = os.fstat(fd).st_size
            try:
                done = 0
                while done < len(data):
                    done += os.write(fd, data[done:])
                os.fsync(fd)
            except OSError:
                os.ftruncate(fd, size)  # no half line may stay behind
                raise
        finally:
            os.close(fd)

    def _first_line(self, path: Path, data: bytes) -> None:
        """The first line of a new day: written under another name and given its real name in one step, so that an
        empty or half day file can never exist."""
        _make_dirs(path.parent, self.log.staging)
        tmp = path.with_name(f".{path.name}-{os.getpid()}")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            try:
                done = 0
                while done < len(data):
                    done += os.write(fd, data[done:])
                os.fsync(fd)
            finally:
                os.close(fd)
            os.link(tmp, path)  # unlike a rename, a link never replaces an existing file
        finally:
            tmp.unlink(missing_ok=True)
        _fsync_dir(path.parent)

    def _write_private(self, seq: int, kind: str, private: dict[str, dict[str, Any]]) -> None:
        path = self.log.private_path(seq)
        if path.exists():
            # Left by a crash between the private file and the public line: that record was never written.
            path.rename(path.with_name(f"{seq:08d}.orphan-{secrets.token_hex(4)}.json"))
        write_new_bytes(path, canon.encode({"seq": seq, "kind": kind, "fields": private}) + b"\n")

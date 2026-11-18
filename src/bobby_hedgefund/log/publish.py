"""Publishing the track record (docs/decisions/0004, point 3; docs/SPEC.md section 5).

The day's files are prepared in the data folder ("staging") and are placed in `track-record/` only at the moment
of the commit. This script is the only thing that writes there, and it refuses:
- anything outside `track-record/`;
- a change to a line that exists: the log's day files and `forecasts.csv` may only grow, `HEAD` is replaced, and
  every other file is written once;
- a file that names a company that may not be named in public (docs/decisions/0006: in the universe through the
  XBI fund only). Those names are read from a private list; a finding is reported by its number in that list, never
  by name.

GitHub cannot enforce the folder limit on this plan; this script and `bobby-log verify` do.

In the pilot the commit is made in a git repository inside the pilot folder and nothing is sent anywhere. The time
of that commit then stands in for the time GitHub received the publication.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from .. import paths
from .private import PrivateNames
from .store import HEAD, LOCK, LOG, Log

TRACK = "track-record"
GROWS = ("forecasts.csv",)
COMMIT_PREFIX = "Track record: "
PILOT_REPO = "track-record-repo"


class PublishError(Exception):
    pass


@dataclass(frozen=True)
class Change:
    path: str  # relative to track-record/
    kind: str  # "new", "grown", "head" or "same"


def _git(repo: Path, *args: str, check: bool = True) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env, check=False)
    if check and done.returncode != 0:
        raise PublishError(f"git {args[0]} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def _files(root: Path) -> dict[str, Path]:
    """Every file under `root` by its relative path. Hidden files (a lock, a half-written copy) are left out; a
    link is refused."""
    found: dict[str, Path] = {}
    if not root.exists():
        return found
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if path.is_symlink():
            raise PublishError(f"{rel} is a link; nothing was published")
        if path.is_file():
            found[rel.as_posix()] = path
    return found


def _grows(rel: str) -> bool:
    return rel in GROWS or (rel.startswith(LOG + "/") and rel.endswith(".jsonl"))


def plan(staging: Path, target: Path) -> list[Change]:
    """What publishing would do, file by file. Raises PublishError when it would change or remove something that
    is published."""
    new = _files(staging)
    old = _files(target)
    missing = sorted(set(old) - set(new))
    if missing:
        raise PublishError(f"{len(missing)} published file(s) are missing from the prepared files, first: {missing[0]}")
    changes: list[Change] = []
    for rel, path in new.items():
        if rel not in old:
            changes.append(Change(rel, "new"))
            continue
        fresh, published = path.read_bytes(), old[rel].read_bytes()
        if fresh == published:
            changes.append(Change(rel, "same"))
        elif rel == HEAD:
            changes.append(Change(rel, "head"))
        elif _grows(rel) and fresh.startswith(published):
            changes.append(Change(rel, "grown"))
        else:
            raise PublishError(f"{rel}: a published line would change; nothing was published")
    return changes


def _check_private(staging: Path, target: Path, changes: list[Change], companies: PrivateNames) -> None:
    for change in changes:
        if change.kind == "same":
            continue
        fresh = (staging / change.path).read_bytes()
        if change.kind == "grown":
            fresh = fresh[len((target / change.path).read_bytes()) :]
        hits = companies.named(fresh.decode("utf-8", errors="replace"))
        if hits:
            raise PublishError(
                f"{change.path} names a company that may not be named in public (number {hits[0]} of the private "
                "list); nothing was published"
            )


def _copy(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}-{os.getpid()}")
    data = source.read_bytes()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        done = 0
        while done < len(data):
            done += os.write(fd, data[done:])
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(dest)


def pilot_repo(mode_root: Path) -> Path:
    """The git repository the pilot commits in: inside the pilot folder, never sent anywhere."""
    repo = mode_root / PILOT_REPO
    if not (repo / ".git").exists():
        repo.mkdir(parents=True, exist_ok=True, mode=0o700)
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.name", "bobby pilot")
        _git(repo, "config", "user.email", "")  # no address at all: these commits never leave the machine
        _git(repo, "config", "commit.gpgsign", "false")
        _git(repo, "config", "core.autocrlf", "false")
    return repo


def tidy(repo: Path) -> list[str]:
    """Remove what an earlier session left in `track-record/` without committing it (a crash in the middle of
    publishing; docs/decisions/0003, point 1). They are copies: the day's files live in the data folder."""
    left = [line[3:] for line in _git(repo, "status", "--porcelain", "--", TRACK).splitlines()]
    if left:
        if _git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).strip():
            _git(repo, "reset", "-q", "--", TRACK, check=False)
            _git(repo, "checkout", "-q", "--", TRACK, check=False)
        else:  # a repository without a first commit: nothing to go back to, only to take out of the staging area
            _git(repo, "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", TRACK, check=False)
        _git(repo, "clean", "-q", "-fd", "--", TRACK)
    return left


def _only_track_record(repo: Path, commit: str) -> bool:
    names = _git(repo, "show", "--name-only", "--format=", commit).split()
    return bool(names) and all(name.startswith(TRACK + "/") for name in names)


def unsent(repo: Path, remote: str = "origin", branch: str = "main") -> list[str]:
    """The commits this script made that the remote has not received yet, oldest first. Raises when there is any
    other unsent commit: then this is not the published main branch."""
    commits = _git(repo, "rev-list", "--reverse", f"{remote}/{branch}..{branch}").split()
    for commit in commits:
        subject = _git(repo, "show", "-s", "--format=%s", commit).strip()
        if not subject.startswith(COMMIT_PREFIX) or not _only_track_record(repo, commit):
            raise PublishError(
                f"the local {branch} branch holds a commit that is not a publication; the session runs the "
                "published main branch only"
            )
    return commits


def send(repo: Path, remote: str = "origin", branch: str = "main") -> None:
    """Send the publication commits. Never forced: history is not rewritten."""
    _git(repo, "push", "-q", remote, f"{branch}:{branch}")


def commit_time(repo: Path, commit: str = "HEAD") -> datetime:
    return datetime.fromisoformat(_git(repo, "show", "-s", "--format=%cI", commit).strip()).astimezone(UTC)


def publish(
    staging: Path,
    repo: Path,
    mode: str,
    day: date,
    *,
    private_names: PrivateNames,
    push: bool = False,
) -> tuple[str | None, list[Change]]:
    """Place the prepared files in `track-record/` and make the day's one commit. Returns the commit (None when
    there was nothing new) and what changed. On any refusal `track-record/` is left as it was. The log's lock is
    held meanwhile, so nothing can be added between the check and the copy."""
    if push and mode != paths.LIVE:
        raise PublishError("the pilot is never sent to GitHub")
    staging.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = os.open(staging / LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PublishError("another program is writing the log right now; nothing was published") from None
        return _publish(staging, repo, mode, day, private_names, push)
    finally:
        os.close(lock)


def _publish(
    staging: Path, repo: Path, mode: str, day: date, private_names: PrivateNames, push: bool
) -> tuple[str | None, list[Change]]:
    report = Log(staging, None, mode).verify(check_private=False)
    if report.problems:
        raise PublishError(f"the prepared log does not pass its check ({report.problems[0]}); nothing was published")
    top = _git(repo, "rev-parse", "--show-toplevel").strip()
    if Path(top).resolve() != repo.resolve():
        raise PublishError("the folder to publish in is not the top folder of a git repository")
    if push:
        unsent(repo)  # raises when main holds a commit that is not a publication: that must never be sent along
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip()
    born = _git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).strip() != ""
    if born and branch != "main":
        raise PublishError(f"the repository is on branch {branch!r}; the track record is published from main only")
    dirty = [line for line in _git(repo, "status", "--porcelain").splitlines() if line.strip()]
    if dirty:
        raise PublishError("the repository has uncommitted changes; nothing was published")
    target = repo / TRACK
    if target.is_symlink():
        raise PublishError(f"{TRACK} is a link; nothing was published")
    changes = plan(staging, target)
    todo = [c for c in changes if c.kind != "same"]
    if not todo:
        return None, changes
    _check_private(staging, target, todo, private_names)
    try:
        for change in todo:
            _copy(staging / change.path, target / change.path)
        _git(repo, "add", "--", TRACK)
        allowed = {f"{TRACK}/{c.path}": c.kind for c in todo}
        for line in _git(repo, "diff", "--cached", "--name-status").splitlines():
            status, _, name = line.partition("\t")
            kind = allowed.get(name)
            if kind is None or (status == "A") != (kind == "new") or status not in ("A", "M"):
                raise PublishError(f"the commit would touch {name} in a way that is not allowed; nothing was published")
        for line in _git(repo, "diff", "--cached", "--numstat").splitlines():
            _added, removed, name = line.split("\t")
            if allowed.get(name) == "grown" and removed != "0":
                raise PublishError(f"{name}: a published line would be removed; nothing was published")
        _git(repo, "commit", "-q", "-m", f"{COMMIT_PREFIX}{day.isoformat()}")
    except Exception as exc:  # also a full disk in the middle of the copy: track-record/ goes back as it was
        tidy(repo)
        if isinstance(exc, PublishError):
            raise
        raise PublishError(f"publishing failed half-way ({type(exc).__name__}); track-record/ was put back") from exc
    commit = _git(repo, "rev-parse", "HEAD").strip()
    if push:
        send(repo)
    return commit, changes

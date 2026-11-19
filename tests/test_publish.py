from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from logkit import DAY1, DAY2, clock, day_file, decision, forecast, make_log, session_start

from bobby_hedgefund.log import cli, forecasts, publish
from bobby_hedgefund.log.private import PrivateCompany, PrivateNames, short_names
from bobby_hedgefund.log.publish import PublishError
from bobby_hedgefund.log.store import Log

HIDDEN = PrivateNames(
    [
        PrivateCompany(7654321, "ZZQX", "Zzyzx Biosciences Holdings, Inc. /DE/"),
        PrivateCompany(1111111, "RNA", "Avid Example Pharmaceuticals Inc", ("Avidex",)),
        PrivateCompany(2222222, "BEAM", "Beam Therapeutics Inc."),
    ]
)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def day_one(tmp_path: Path) -> Log:
    log = make_log(tmp_path)
    with log.writer(DAY1, clock()) as w:
        w.add("session_start", session_start())
        w.add("forecast", forecast())
        w.add("decision", decision())
    forecasts.write(log.staging, log.entries())
    (log.staging / "days" / "2027" / "02").mkdir(parents=True)
    (log.staging / "days" / "2027" / "02" / "2027-02-03.md").write_text(
        "# 3 February\n\nPaper money, not investment advice.\n"
    )
    return log


def day_two(log: Log) -> None:
    with log.writer(DAY2, clock(10)) as w:
        w.add("outcome", {"ref": 2, "result": "yes", "resolved_on": "2027-02-04", "summary": "Met.", "sources": []})
    forecasts.write(log.staging, log.entries())


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return publish.pilot_repo(tmp_path / "pilot")


def tree(repo: Path) -> dict[str, bytes]:
    root = repo / "track-record"
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_one_commit_per_day_that_touches_track_record_only(tmp_path: Path, repo: Path) -> None:
    log = day_one(tmp_path)
    commit, changes = publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)
    assert commit and {c.path: c.kind for c in changes} == {
        "HEAD": "new",
        "days/2027/02/2027-02-03.md": "new",
        "forecasts.csv": "new",
        "log/2027/02/2027-02-03.jsonl": "new",
    }
    assert git(repo, "log", "--format=%s").splitlines() == ["Track record: 2027-02-03"]
    assert all(name.startswith("track-record/") for name in git(repo, "show", "--name-only", "--format=").split())
    assert tree(repo)["log/2027/02/2027-02-03.jsonl"] == day_file(log).read_bytes()
    assert not (repo / "track-record" / ".lock").exists()  # the lock and other hidden files stay behind
    assert publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)[0] is None  # nothing new
    day_two(log)
    commit2, changes2 = publish.publish(log.staging, repo, "pilot", DAY2, private_names=HIDDEN)
    kinds = {c.path: c.kind for c in changes2}
    assert (
        kinds["HEAD"] == "head" and kinds["forecasts.csv"] == "grown" and kinds["log/2027/02/2027-02-04.jsonl"] == "new"
    )
    assert kinds["log/2027/02/2027-02-03.jsonl"] == "same" and commit2 != commit
    assert Log(repo / "track-record", None, "pilot").verify(check_private=False).problems == []
    assert publish.commit_time(repo).tzinfo is not None


@pytest.mark.parametrize("damage", ["changed line", "shorter", "day page changed", "published file gone from staging"])
def test_a_change_to_anything_published_is_refused_and_nothing_is_touched(
    tmp_path: Path, repo: Path, damage: str
) -> None:
    log = day_one(tmp_path)
    publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)
    day_two(log)
    before = tree(repo)
    path = repo / "track-record" / "log" / "2027" / "02" / "2027-02-03.jsonl"
    if damage == "changed line":  # the published copy and the prepared one disagree about an existing line
        path.write_bytes(path.read_bytes().replace(b'"3%"', b'"4%"'))
        git(repo, "commit", "-qam", "tampered")
    elif damage == "shorter":
        csv = log.staging / "forecasts.csv"
        csv.write_bytes(csv.read_bytes().splitlines(keepends=True)[0])
    elif damage == "day page changed":
        (log.staging / "days" / "2027" / "02" / "2027-02-03.md").write_text("# rewritten\n")
    else:
        (log.staging / "days" / "2027" / "02" / "2027-02-03.md").unlink()
    expected = tree(repo)
    with pytest.raises(PublishError):
        publish.publish(log.staging, repo, "pilot", DAY2, private_names=HIDDEN)
    assert tree(repo) == expected and git(repo, "status", "--porcelain") == ""
    assert set(before) == set(expected)


def test_a_prepared_log_that_fails_its_check_is_not_published(tmp_path: Path, repo: Path) -> None:
    log = day_one(tmp_path)
    day_file(log).write_bytes(day_file(log).read_bytes().replace(b'"3%"', b'"4%"'))
    with pytest.raises(PublishError, match="does not pass its check"):
        publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)
    assert not (repo / "track-record").exists()


def test_uncommitted_changes_or_another_branch_stop_the_publication(tmp_path: Path, repo: Path) -> None:
    log = day_one(tmp_path)
    (repo / "notes.txt").write_text("work in progress")
    with pytest.raises(PublishError, match="uncommitted changes"):
        publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)
    (repo / "notes.txt").unlink()
    publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)
    git(repo, "switch", "-q", "-c", "work")
    day_two(log)
    with pytest.raises(PublishError, match="from main only"):
        publish.publish(log.staging, repo, "pilot", DAY2, private_names=HIDDEN)


def test_a_link_among_the_prepared_files_is_refused(tmp_path: Path, repo: Path) -> None:
    log = day_one(tmp_path)
    (tmp_path / "outside.txt").write_text("private")
    (log.staging / "days" / "peek.md").symlink_to(tmp_path / "outside.txt")
    with pytest.raises(PublishError, match="is a link"):
        publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)


def test_a_company_name_also_counts_in_the_short_forms_people_use() -> None:
    assert short_names("Zzyzx Biosciences Holdings, Inc. /DE/") == [
        "Zzyzx Biosciences Holdings, Inc.",
        "Zzyzx Biosciences Holdings",
        "Zzyzx Biosciences",
        "Zzyzx",
    ]
    assert short_names("Vertexample Pharmaceuticals Inc / MA")[-1] == "Vertexample"


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ('{"company":{"cik":7654321,"name":"x"}}', 1),
        ("see CIK 0007654321 for the filings", 1),
        ("We like ZZQX here.", 1),
        ("Zzyzx Biosciences Holdings, Inc. reported results", 1),
        ("zzyzx biosciences reported results", 1),
        ("Zzyzx  Biosciences-Holdings said", 1),
        ("Zzyzx reported", 1),
        ("Zzyzx's lead drug", 1),
        ("Avid Example reported", 2),
        ("Avidex is the brand", 2),  # an extra name from the list
        ("Nasdaq: RNA rose", 2),
        ("$RNA", 2),
        ("Beam's base editing", 3),
        ("held (BEAM) since May", 3),
    ],
)
def test_a_private_company_is_recognised_by_number_ticker_or_name(text: str, number: int) -> None:
    assert HIDDEN.named(text) == [number]


@pytest.mark.parametrize(
    "text",
    [
        "cik 76543210",
        "the ZZQXY fund",
        "A.ZZQX",
        "Zzyzxian biology",
        "1234567 patients",
        "RNA-seq showed lower RNA levels",  # the ticker RNA is also a word of the field
        "an electron beam",
        "the BEAM trial",
        "avid readers",
    ],
)
def test_look_alikes_are_not_taken_for_a_private_company(text: str) -> None:
    assert HIDDEN.named(text) == []
    assert HIDDEN.ticker_notes() == 2  # RNA and BEAM: only recognised where clearly used as a ticker


def test_a_file_that_names_a_private_company_is_not_published_and_the_name_is_not_printed(
    tmp_path: Path, repo: Path, capsys
) -> None:
    log = day_one(tmp_path)
    publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)
    # A line written without the session's list (the log's own check then cannot know the name): the last guard.
    with log.writer(DAY2, clock(10)) as w:
        w.add("correction", {"ref": 2, "text": "This should have been about Zzyzx Biosciences."})
    before = tree(repo)
    with pytest.raises(PublishError) as refused:
        publish.publish(log.staging, repo, "pilot", DAY2, private_names=HIDDEN)
    assert "number 1 of the private list" in str(refused.value) and "zzyzx" not in str(refused.value).lower()
    assert tree(repo) == before and git(repo, "status", "--porcelain") == ""


def test_a_copy_that_fails_half_way_puts_track_record_back(tmp_path: Path, repo: Path, monkeypatch) -> None:
    log = day_one(tmp_path)
    publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)
    day_two(log)
    before = tree(repo)
    real = publish._copy
    calls = {"n": 0}

    def breaks(source: Path, dest: Path) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        real(source, dest)

    monkeypatch.setattr(publish, "_copy", breaks)
    with pytest.raises(PublishError, match="half-way"):
        publish.publish(log.staging, repo, "pilot", DAY2, private_names=HIDDEN)
    assert tree(repo) == before and git(repo, "status", "--porcelain") == ""
    monkeypatch.setattr(publish, "_copy", real)
    assert publish.publish(log.staging, repo, "pilot", DAY2, private_names=HIDDEN)[0]  # and the next try works


def test_nothing_is_published_while_the_log_is_being_written(tmp_path: Path, repo: Path) -> None:
    log = day_one(tmp_path)
    with log.writer(DAY1, clock()), pytest.raises(PublishError, match="writing the log right now"):
        publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN)


def test_without_the_private_list_nothing_is_published(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    log = Log.for_mode("pilot")
    with log.writer(DAY1, clock()) as w:
        w.add("session_start", session_start())
    assert cli.publish_main(["day", "2027-02-03"]) == 1
    assert "private list" in capsys.readouterr().out
    (tmp_path / "data" / "pilot" / "private-names.tsv").write_text(
        "# made-up\n7654321\tZZQX\tZzyzx Biosciences Inc\tZyx|Zzy\n"
    )
    assert cli.publish_main(["plan"]) == 0
    assert cli.publish_main(["day", "2027-02-03"]) == 0
    out = capsys.readouterr().out
    assert "nothing was sent" in out and "commit time" in out
    assert cli.publish_main(["day", "2027-02-03"]) == 0 and "nothing new" in capsys.readouterr().out
    assert cli.publish_main(["day", "2027-02-03", "--live"]) == 1  # live is off until the owner's go


def test_the_pilot_is_never_sent(tmp_path: Path, repo: Path) -> None:
    log = day_one(tmp_path)
    with pytest.raises(PublishError, match="never sent"):
        publish.publish(log.staging, repo, "pilot", DAY1, private_names=HIDDEN, push=True)


# ---------------------------------------------------------------- the real route, against a stand-in for GitHub


@pytest.fixture
def live(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    for key, value in (("user.name", "test"), ("user.email", ""), ("commit.gpgsign", "false")):
        git(work, "config", key, value)
    (work / "README.md").write_text("code\n")
    git(work, "add", "-A")
    git(work, "commit", "-qm", "code")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-q", "-u", "origin", "main")
    return work, remote


def test_publishing_for_real_sends_the_commit_and_never_rewrites(tmp_path: Path, live: tuple[Path, Path]) -> None:
    work, remote = live
    log = make_log(tmp_path, "live")
    with log.writer(DAY1, clock()) as w:
        w.add("session_start", session_start())
    commit, _ = publish.publish(log.staging, work, "live", DAY1, private_names=HIDDEN, push=True)
    assert git(remote, "rev-parse", "main").strip() == commit and publish.unsent(work) == []


def test_a_commit_that_was_not_received_is_sent_again_as_it_is(tmp_path: Path, live: tuple[Path, Path]) -> None:
    work, remote = live
    log = make_log(tmp_path, "live")
    with log.writer(DAY1, clock()) as w:
        w.add("session_start", session_start())
    commit, _ = publish.publish(log.staging, work, "live", DAY1, private_names=HIDDEN, push=False)  # "no internet"
    assert publish.unsent(work) == [commit] and git(remote, "rev-parse", "main").strip() != commit
    publish.send(work)
    assert git(remote, "rev-parse", "main").strip() == commit and publish.unsent(work) == []


def test_work_in_progress_on_main_is_not_taken_for_a_publication(tmp_path: Path, live: tuple[Path, Path]) -> None:
    work, remote = live
    (work / "code.py").write_text("x = 1\n")
    git(work, "add", "-A")
    git(work, "commit", "-qm", "Track record: 2027-02-03")  # the right title, but it touches code
    with pytest.raises(PublishError, match="not a publication"):
        publish.unsent(work)
    # And publishing for real refuses before it sends anything: an unrelated commit must never go along.
    log = make_log(tmp_path, "live")
    with log.writer(DAY1, clock()) as w:
        w.add("session_start", session_start())
    sent_before = git(remote, "rev-parse", "main")
    with pytest.raises(PublishError, match="not a publication"):
        publish.publish(log.staging, work, "live", DAY1, private_names=HIDDEN, push=True)
    assert git(remote, "rev-parse", "main") == sent_before and not (work / "track-record").exists()


def test_leftovers_of_a_crash_in_track_record_are_removed_and_nothing_else(
    tmp_path: Path, live: tuple[Path, Path]
) -> None:
    work, _ = live
    log = make_log(tmp_path, "live")
    with log.writer(DAY1, clock()) as w:
        w.add("session_start", session_start())
    publish.publish(log.staging, work, "live", DAY1, private_names=HIDDEN)
    published = tree(work)
    (work / "track-record" / "log" / "2027" / "02" / "2027-02-04.jsonl").write_text("half written\n")
    (work / "track-record" / "HEAD").write_text("changed\n")
    (work / "elsewhere.txt").write_text("the owner's own file")
    left = publish.tidy(work)
    assert len(left) == 2 and tree(work) == published
    assert (work / "elsewhere.txt").read_text() == "the owner's own file"

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from bobby_hedgefund import settings
from bobby_hedgefund.archive import cli, sec
from bobby_hedgefund.archive.fetch import Fetcher, FetchError
from bobby_hedgefund.archive.sources import SourceError
from bobby_hedgefund.archive.store import Archive

# A made-up contact, deliberately not a real internet address (no domain ending): the commit check of this public
# repository refuses anything that looks like one. Tests check that it is stored nowhere.
CONTACT = "someone@test-host"
ROWS = [
    [320193, "Alpha Inc", "ALFA", "Nasdaq"],
    [1000045, "Beta Corp", "BETA", "NYSE"],
    [1000045, "Beta Corp", "BETA-P", "NYSE"],  # a second share class: the company is fetched once
    [77, "Gamma Ltd", "GAMA", "OTC"],  # not on an exchange: skipped
    [88, "Delta plc", "DELT", None],  # no listing known: skipped
    [5000, "Epsilon Inc", "EPSI", "NYSE American"],
]


def tickers(rows: list[list] = ROWS) -> bytes:
    return json.dumps({"fields": ["cik", "name", "ticker", "exchange"], "data": rows}).encode()


def filing_list(cik: int) -> dict:
    body = json.dumps({"cik": str(cik), "sic": "2834", "name": f"Company {cik}", "filings": {"recent": {}}})
    return {"body": body.encode(), "gzip": True}


def manifest(root: Path) -> list[dict]:
    return [json.loads(x) for x in (root / "manifest.jsonl").read_text().splitlines()]


REAL_BEFORE_EVENING = cli._before_evening
LOCAL = frozenset({"127.0.0.1"})  # the fake site's host, in place of the SEC's hosts


@pytest.fixture(autouse=True)
def daytime(monkeypatch):
    # the command refuses to run late in the evening; tests must pass at any hour
    monkeypatch.setattr(cli, "_before_evening", lambda: True)


@pytest.fixture
def sec_site(site):
    site.add("/files/tickers.json", {"body": tickers()})
    for cik in (5000, 320193, 1000045):
        site.add(f"/submissions/CIK{cik:010d}.json", filing_list(cik))
    site.tickers_url = site.base + "/files/tickers.json"
    site.submissions_url = site.base + "/submissions/CIK{cik:010d}.json"
    return site


def run(archive: Archive, fetcher: Fetcher, site, name: str = "r1", **kwargs) -> dict:
    return sec.run_sec_companies(
        archive, fetcher, name, tickers_url=site.tickers_url, submissions_url=site.submissions_url, **kwargs
    )


def test_listed_companies_skips_unlisted_and_counts_a_company_once() -> None:
    assert sec.listed_companies(tickers()) == [5000, 320193, 1000045]


@pytest.mark.parametrize("body", [b"<html>blocked</html>", b"{}", b'{"fields": ["cik"], "data": [[1]]}', b"[]"])
def test_a_wrong_ticker_file_is_refused_and_starts_no_batch(sec_site, tmp_path: Path, fetcher, body: bytes) -> None:
    sec_site.add("/files/tickers.json", {"body": body})
    with Archive(tmp_path) as archive, pytest.raises(SourceError):
        run(archive, fetcher, sec_site)
    assert not (tmp_path / "manifest.jsonl").exists() or manifest(tmp_path) == []


def test_stores_ticker_file_and_one_filing_list_per_listed_company(sec_site, tmp_path: Path, fetcher, waits) -> None:
    with Archive(tmp_path) as archive:
        summary = run(archive, fetcher, sec_site)
        stored = {r["name"]: archive.read(r) for r in archive.records if r["kind"] == "file"}
    assert summary == {
        "batch": "r1",
        "listed_companies": 3,
        "fetched": 3,
        "not_found": 0,
        "odd": 0,
        "had_already": 0,
        "left": 0,
        "complete": True,
    }
    assert sorted(stored) == [
        "company-tickers-exchange.json",
        "submissions-cik0000005000.json",
        "submissions-cik0000320193.json",
        "submissions-cik0001000045.json",
    ]
    assert stored["company-tickers-exchange.json"] == tickers()  # exactly as received
    assert json.loads(stored["submissions-cik0000320193.json"])["cik"] == "320193"
    rows = manifest(tmp_path)
    assert all(r["path"].startswith("raw/sec/") and r["compress"] == "xz" for r in rows)
    assert [r["meta"].get("cik") for r in rows] == [None, 5000, 320193, 1000045]
    # one request a second: a pause before every single request, and never two requests without one
    assert waits == [1.0] * 4 and len(sec_site.hits) == 4


def test_header_is_client_name_plus_contact_and_the_contact_is_stored_nowhere(
    sec_site, tmp_path: Path, waits, capsys
) -> None:
    fetcher = sec.sec_fetcher(CONTACT, allowed_hosts=LOCAL, timeout=5, backoff=(), sleep=waits.append)
    sec_site.add("/submissions/CIK0000320193.json", {"status": 403, "body": b"denied"})
    with Archive(tmp_path) as archive:
        ok = cli._attempt(archive, sec.SEC_SOURCE, "r1", lambda: run(archive, fetcher, sec_site))
    assert not ok
    assert set(sec_site.user_agents) == {f"public-data-archiver {CONTACT}"}
    everything = b"".join(p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
    assert b"test-host" not in everything and b"someone" not in everything
    out = capsys.readouterr()
    assert "test-host" not in out.out + out.err and "FAILED  sec" in out.out
    assert "test-host" not in repr(fetcher) and "someone" not in repr(fetcher)


def test_the_contact_is_not_shown_when_the_network_fails_or_the_code_itself_breaks(
    sec_site, tmp_path: Path, waits, capsys
) -> None:
    fetcher = sec.sec_fetcher(CONTACT, allowed_hosts=LOCAL, timeout=5, backoff=(1.0,), sleep=waits.append)
    sec_site.add("/files/tickers.json", {"body": tickers(), "cut": True})  # the connection drops, twice
    with Archive(tmp_path) as archive:
        assert not cli._attempt(archive, sec.SEC_SOURCE, "r1", lambda: run(archive, fetcher, sec_site))

        def broken() -> dict:
            raise RuntimeError(f"a bug that mentions the fetcher: {fetcher!r}")

        assert not cli._attempt(archive, sec.SEC_SOURCE, "r2", broken)
    everything = b"".join(p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
    out = capsys.readouterr()
    assert b"test-host" not in everything and "test-host" not in out.out + out.err
    assert set(sec_site.user_agents) == {f"public-data-archiver {CONTACT}"}


def test_the_header_never_travels_to_another_host(sec_site, tmp_path: Path, waits) -> None:
    fetcher = sec.sec_fetcher(CONTACT, allowed_hosts=LOCAL, timeout=5, backoff=(), sleep=waits.append)
    elsewhere = sec_site.base.replace("127.0.0.1", "localhost")  # the same fake server under another host name
    sec_site.add("/elsewhere", {"body": tickers()})
    sec_site.add("/files/tickers.json", {"status": 302, "headers": {"Location": elsewhere + "/elsewhere"}})
    with Archive(tmp_path) as archive, pytest.raises(FetchError):
        run(archive, fetcher, sec_site)
    assert sec_site.hits == ["/files/tickers.json"]  # the redirect was not followed
    with pytest.raises(FetchError, match="not on the list"):
        fetcher.get(elsewhere + "/elsewhere")  # and a direct request to another host is refused too
    assert sec_site.hits == ["/files/tickers.json"]
    assert sec.sec_fetcher(CONTACT).allowed_hosts == {"www.sec.gov", "data.sec.gov"}


def test_a_redirect_within_the_allowed_host_is_followed(sec_site, tmp_path: Path, waits) -> None:
    fetcher = sec.sec_fetcher(CONTACT, allowed_hosts=LOCAL, timeout=5, backoff=(), sleep=waits.append)
    sec_site.add("/moved", {"body": tickers()})
    sec_site.add("/files/tickers.json", {"status": 302, "headers": {"Location": sec_site.base + "/moved"}})
    with Archive(tmp_path) as archive:
        assert run(archive, fetcher, sec_site)["complete"] is True


@pytest.mark.parametrize("status", [429, 403])
def test_a_refusal_stops_the_job_at_once_and_resume_continues(
    sec_site, tmp_path: Path, fetcher, waits, status: int
) -> None:
    sec_site.add("/submissions/CIK0000320193.json", {"status": status, "body": b"slow down"}, filing_list(320193))
    with Archive(tmp_path) as archive:
        with pytest.raises(FetchError):
            run(archive, fetcher, sec_site)
        assert len(sec_site.hits) == 3  # ticker file, one company, the refused one: no retry, nothing after it
        assert waits == [1.0] * 3  # and no extra waiting-and-trying-again
        assert [r["meta"].get("cik") for r in archive.records] == [None, 5000]
    with Archive(tmp_path) as archive:
        summary = run(archive, fetcher, sec_site, name="r2", resume=True)
        assert summary == {
            "batch": "r1",
            "listed_companies": 3,
            "fetched": 2,
            "not_found": 0,
            "odd": 0,
            "had_already": 1,
            "left": 0,
            "complete": True,
        }
    assert sec_site.hits.count("/files/tickers.json") == 1  # the batch keeps its own copy of the ticker file
    assert sec_site.hits.count("/submissions/CIK0000005000.json") == 1  # not fetched twice


def test_limit_leaves_the_batch_open_and_resume_finishes_it(sec_site, tmp_path: Path, monkeypatch, waits) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(cli, "make_sec_fetcher", lambda: Fetcher(timeout=5, backoff=(), sleep=waits.append))
    monkeypatch.setattr(sec, "SEC_TICKERS_URL", sec_site.tickers_url)
    monkeypatch.setattr(sec, "SEC_SUBMISSIONS_URL", sec_site.submissions_url)
    assert cli.main(["sec-companies", "--limit", "2"]) == 0
    root = tmp_path / "data" / "archive"
    first = [r for r in manifest(root) if r["kind"] == "run"][-1]
    assert first["status"] == "ok" and first["meta"]["left"] == 1 and first["meta"]["complete"] is False
    assert cli.main(["sec-companies", "--resume"]) == 0
    last = [r for r in manifest(root) if r["kind"] == "run"][-1]
    assert last["meta"]["complete"] is True and last["meta"]["batch"] == first["meta"]["batch"]
    assert len([r for r in manifest(root) if r["kind"] == "file"]) == 4
    assert cli.main(["sec-companies", "--resume"]) == 1  # the batch is finished: nothing to resume
    assert cli.main(["verify"]) == 0


def test_a_company_the_data_service_does_not_know_is_noted_and_not_asked_again(
    sec_site, tmp_path: Path, fetcher
) -> None:
    del sec_site.routes["/submissions/CIK0000320193.json"]  # the fake site answers 404
    with Archive(tmp_path) as archive:
        summary = run(archive, fetcher, sec_site, limit=2)
        assert summary["fetched"] == 1 and summary["not_found"] == 1 and summary["left"] == 1
        summary = run(archive, fetcher, sec_site, name="r2", resume=True)
        assert summary["fetched"] == 1 and summary["not_found"] == 0 and summary["complete"] is True
    assert sec_site.hits.count("/submissions/CIK0000320193.json") == 1


def test_an_odd_answer_is_noted_not_stored_and_does_not_block_the_batch(sec_site, tmp_path: Path, fetcher) -> None:
    sec_site.add("/submissions/CIK0000320193.json", filing_list(999), filing_list(320193))
    with Archive(tmp_path) as archive:
        summary = run(archive, fetcher, sec_site)
        assert summary["fetched"] == 2 and summary["odd"] == 1 and summary["complete"] is True
        files = [r["meta"].get("cik") for r in archive.records if r["kind"] == "file"]
        assert files == [None, 5000, 1000045]
        notes = [r["meta"] for r in archive.records if r["kind"] == "run" and r["status"] == "note"]
        assert notes == [{"batch": "r1", "odd_cik": 320193}]
        # the batch was not closed by a run line in this test, so a resume asks the odd one again
        summary = run(archive, fetcher, sec_site, name="r2", resume=True)
        assert summary["fetched"] == 1 and summary["odd"] == 0 and summary["had_already"] == 2


def test_many_odd_answers_in_a_row_stop_the_job(sec_site, tmp_path: Path, fetcher, monkeypatch) -> None:
    monkeypatch.setattr(sec, "MAX_ODD_IN_A_ROW", 2)
    for cik in (5000, 320193, 1000045):
        sec_site.add(f"/submissions/CIK{cik:010d}.json", {"body": b"<html>please wait</html>"})
    with Archive(tmp_path) as archive, pytest.raises(SourceError, match="in a row"):
        run(archive, fetcher, sec_site)
    assert len(sec_site.hits) == 3  # ticker file and two companies; the third is not asked


def test_an_open_batch_is_not_dropped_by_accident(sec_site, tmp_path: Path, fetcher) -> None:
    with Archive(tmp_path) as archive:
        run(archive, fetcher, sec_site, limit=1)
        hits = len(sec_site.hits)
        with pytest.raises(SourceError, match="--resume"):
            run(archive, fetcher, sec_site, name="r2")
        assert len(sec_site.hits) == hits  # refused before any request
        assert run(archive, fetcher, sec_site, name="r3", new=True)["batch"] == "r3"


def test_the_job_stops_before_the_evening_and_can_be_resumed(sec_site, tmp_path: Path, fetcher) -> None:
    answers = iter([True, False])
    with Archive(tmp_path) as archive:
        summary = run(archive, fetcher, sec_site, keep_going=lambda: next(answers))
        assert summary["fetched"] == 1 and summary["left"] == 2 and summary["complete"] is False
        assert run(archive, fetcher, sec_site, name="r2", resume=True)["complete"] is True


def test_late_in_the_evening_the_command_does_not_start(sec_site, tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(cli, "_before_evening", lambda: False)
    monkeypatch.setattr(sec, "SEC_TICKERS_URL", sec_site.tickers_url)
    assert cli.main(["sec-companies"]) == 1
    assert "NOT RUN" in capsys.readouterr().out and sec_site.hits == [] and not (tmp_path / "data").exists()


def test_before_evening_reads_the_clock() -> None:
    def at(hour: int, minute: int):
        return lambda: time.struct_time((2026, 11, 18, hour, minute, 0, 2, 322, 0))

    assert REAL_BEFORE_EVENING(at(9, 0)) and REAL_BEFORE_EVENING(at(22, 29))
    assert not REAL_BEFORE_EVENING(at(22, 30)) and not REAL_BEFORE_EVENING(at(23, 45))


def test_limit_must_be_one_or_more(sec_site, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    for bad in ("0", "-3"):
        with pytest.raises(SystemExit):
            cli.main(["sec-companies", "--limit", bad])
    with pytest.raises(SystemExit):
        cli.main(["sec-companies", "--resume", "--new"])
    assert sec_site.hits == []


def test_status_shows_the_run_not_a_note_inside_it(sec_site, tmp_path: Path, monkeypatch, fetcher, capsys) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    del sec_site.routes["/submissions/CIK0001000045.json"]  # the last company answers 404: a note is written
    with Archive(tmp_path / "data" / "archive") as archive:
        assert cli._attempt(archive, sec.SEC_SOURCE, "r1", lambda: run(archive, fetcher, sec_site))
        archive.record_run(sec.SEC_SOURCE, "r2", "note", meta={"batch": "r1", "missing_cik": 1})
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    line = next(x for x in capsys.readouterr().out.splitlines() if x.startswith("sec "))
    assert " ok;" in line and "note" not in line


def test_an_unchanged_filing_list_is_not_stored_twice(sec_site, tmp_path: Path, fetcher) -> None:
    with Archive(tmp_path) as archive:
        run(archive, fetcher, sec_site)
        archive.record_run(sec.SEC_SOURCE, "r1", "ok", meta={"batch": "r1", "complete": True})
        run(archive, fetcher, sec_site, name="r2")
        kinds = [(r["name"], r["kind"]) for r in archive.records if r.get("name", "").startswith("submissions")]
    assert [k for _, k in kinds] == ["file"] * 3 + ["unchanged"] * 3


def test_resume_without_an_open_batch_is_refused(sec_site, tmp_path: Path, fetcher) -> None:
    with Archive(tmp_path) as archive, pytest.raises(SourceError, match="nothing to resume"):
        run(archive, fetcher, sec_site, resume=True)
    assert sec_site.hits == []


def test_without_a_contact_address_no_request_is_sent(sec_site, tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BOBBY_ENV_FILE", str(tmp_path / "no-such-file"))
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)
    monkeypatch.setattr(sec, "SEC_TICKERS_URL", sec_site.tickers_url)
    assert cli.main(["sec-companies"]) == 1
    assert "NOT RUN" in capsys.readouterr().out and sec_site.hits == []
    assert not (tmp_path / "data").exists()


def test_settings_read_the_env_file_and_the_environment_wins(tmp_path: Path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\n\nOTHER = 'x y'\nexport SEC_CONTACT_EMAIL=\"file@test-host\"\nnot a setting\n")
    monkeypatch.setenv("BOBBY_ENV_FILE", str(env))
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)
    assert settings.get("OTHER") == "x y"
    assert settings.sec_contact() == "file@test-host"
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "env@test-host")
    assert settings.sec_contact() == "env@test-host"


@pytest.mark.parametrize("value", ["two words@test-host", "a@test-host\nX-Other: 1", "no-at-sign", "a@b@c"])
def test_a_contact_that_is_not_one_plain_address_is_refused_without_showing_it(
    tmp_path: Path, monkeypatch, value: str
) -> None:
    monkeypatch.setenv("BOBBY_ENV_FILE", str(tmp_path / "none"))
    monkeypatch.setenv("SEC_CONTACT_EMAIL", value)
    with pytest.raises(settings.SettingsError) as caught:
        settings.sec_contact()
    assert "test-host" not in str(caught.value) and "no-at-sign" not in str(caught.value)

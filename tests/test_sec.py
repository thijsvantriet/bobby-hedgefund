from __future__ import annotations

import json
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
    fetcher = sec.sec_fetcher(CONTACT, timeout=5, backoff=(), sleep=waits.append)
    sec_site.add("/submissions/CIK0000320193.json", {"status": 403, "body": b"denied"})
    with Archive(tmp_path) as archive:
        ok = cli._attempt(archive, sec.SEC_SOURCE, "r1", lambda: run(archive, fetcher, sec_site))
    assert not ok
    assert set(sec_site.user_agents) == {f"public-data-archiver {CONTACT}"}
    everything = b"".join(p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
    assert b"test-host" not in everything and b"someone" not in everything
    out = capsys.readouterr()
    assert "test-host" not in out.out + out.err and "FAILED  sec" in out.out


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


def test_a_filing_list_of_another_company_is_not_stored(sec_site, tmp_path: Path, fetcher) -> None:
    sec_site.add("/submissions/CIK0000320193.json", filing_list(999))
    with Archive(tmp_path) as archive:
        with pytest.raises(SourceError):
            run(archive, fetcher, sec_site)
        assert [r["meta"].get("cik") for r in archive.records] == [None, 5000]


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

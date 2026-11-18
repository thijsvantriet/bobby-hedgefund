"""SEC filings: fetching, the cross-check and reading. Every company, person and filing here is invented."""
# ruff: noqa: E501  (the made-up index and XML keep the SEC's own long lines)

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from bobby_hedgefund.archive import cli as archive_cli
from bobby_hedgefund.archive import sec, sec_filings
from bobby_hedgefund.archive.fetch import FetchError
from bobby_hedgefund.archive.sources import SourceError
from bobby_hedgefund.archive.store import Archive
from bobby_hedgefund.filings import cli as filings_cli
from bobby_hedgefund.filings import read

CONTACT = "someone@test-host"
LOCAL = frozenset({"127.0.0.1"})
SINCE = date(2026, 9, 1)
A1, A2, A3, A4, A5 = (f"0000000101-26-00000{n}" for n in range(1, 6))


def filing_list(cik: int, rows: list[tuple[str, str, str]]) -> bytes:
    """rows: (accession, form, filing day), newest first as the SEC lists them."""
    recent = {
        "accessionNumber": [r[0] for r in rows],
        "form": [r[1] for r in rows],
        "filingDate": [r[2] for r in rows],
        "acceptanceDateTime": [r[2] + "T16:05:00.000Z" for r in rows],
    }
    return json.dumps({"cik": f"{cik:010d}", "filings": {"recent": recent}}).encode()


def filing_text(accession: str, form: str = "8-K", items: tuple[str, ...] = ("Other Events",), body: str = "") -> bytes:
    lines = [
        f"<SEC-DOCUMENT>{accession}.txt : 20261103",
        f"<SEC-HEADER>{accession}.hdr.sgml : 20261103",
        "<ACCEPTANCE-DATETIME>20261103160544",
        f"ACCESSION NUMBER:\t\t{accession}",
        f"CONFORMED SUBMISSION TYPE:\t{form}",
        "CONFORMED PERIOD OF REPORT:\t20261102",
        *[f"ITEM INFORMATION:\t\t{item}" for item in items],
        "FILED AS OF DATE:\t\t20261103",
        "",
        "FILER:",
        "",
        "\tCOMPANY DATA:\t",
        "\t\tCOMPANY CONFORMED NAME:\t\t\tALPHA THERAPEUTICS INC",
        "\t\tCENTRAL INDEX KEY:\t\t\t0000000101",
        "</SEC-HEADER>",
        "<DOCUMENT>",
        f"<TYPE>{form}",
        "<SEQUENCE>1",
        "<FILENAME>main.htm" if not body else "<FILENAME>form4.xml",
        "<DESCRIPTION>PRIMARY DOCUMENT",
        "<TEXT>",
        body or "<html>made-up text</html>",
        "</TEXT>",
        "</DOCUMENT>",
        "<DOCUMENT>",
        "<TYPE>EX-99.1",
        "<SEQUENCE>2",
        "<FILENAME>press.htm",
        "<TEXT>",
        "<html>a made-up press release</html>",
        "</TEXT>",
        "</DOCUMENT>",
        "</SEC-DOCUMENT>",
    ]
    return "\n".join(lines).encode()


OWNERSHIP = """<XML>
<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>0000000900</rptOwnerCik><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>true</isOfficer><officerTitle>Chief Medical Officer</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-11-02</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>12.5</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>4000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeHolding><securityTitle><value>Common Stock</value></securityTitle></nonDerivativeHolding>
  </nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction>
      <securityTitle><value>Stock Option</value></securityTitle>
      <transactionDate><value>2026-11-02</value></transactionDate>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>500</value></transactionShares>
        <transactionPricePerShare><footnoteId id="F1"/></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </derivativeTransaction>
  </derivativeTable>
</ownershipDocument>
</XML>"""


@pytest.fixture
def filings_site(site):
    site.submissions_url = site.base + "/submissions/CIK{cik:010d}.json"
    site.filing_url = site.base + "/Archives/edgar/data/{cik}/{accession}.txt"
    site.index_url = site.base + "/daily-index/{year}/QTR{quarter}/master.{day:%Y%m%d}.idx"
    rows = [
        (A5, "4", "2026-11-03"),
        (A4, "8-K/A", "2026-11-03"),
        (A3, "DEF 14A", "2026-10-01"),  # a form we do not follow
        (A2, "8-K", "2026-09-15"),
        (A1, "10-K", "2026-03-01"),  # before the start day
    ]
    site.add("/submissions/CIK0000000101.json", {"body": filing_list(101, rows)})
    site.add("/submissions/CIK0000000103.json", {"body": filing_list(103, [])})
    site.add(f"/Archives/edgar/data/101/{A2}.txt", {"body": filing_text(A2), "gzip": True})
    site.add(f"/Archives/edgar/data/101/{A4}.txt", {"body": filing_text(A4, "8-K/A")})
    site.add(f"/Archives/edgar/data/101/{A5}.txt", {"body": filing_text(A5, "4", (), OWNERSHIP)})
    return site


def fetch(archive, fetcher, site, name="r1", ciks=(101, 103), **kwargs) -> dict:
    return sec_filings.run_sec_filings(
        archive,
        fetcher,
        name,
        ciks=list(ciks),
        since=SINCE,
        submissions_url=site.submissions_url,
        filing_url=site.filing_url,
        **kwargs,
    )


def test_followed_filings_from_the_start_day_are_stored_once_oldest_first(
    filings_site, tmp_path: Path, fetcher, waits
) -> None:
    with Archive(tmp_path) as archive:
        first = fetch(archive, fetcher, filings_site)
        again = fetch(archive, fetcher, filings_site, "r2")
        rows = list(archive.records)
        assert archive.read(next(r for r in rows if r.get("name") == f"filing-{A2}.txt")) == filing_text(A2)
    assert first["filings_stored"] == 3 and first["by_form"] == {"4": 1, "8-K": 2} and first["complete"]
    assert first["asked"] == 5 and waits[:5] == [1.0] * 5  # two filing lists and three filings, a pause before each
    assert again["filings_stored"] == 0 and again["asked"] == 2  # only the filing lists are asked again
    stored = [r for r in rows if str(r.get("name", "")).startswith("filing-") and r["kind"] == "file"]
    assert [r["meta"]["accession"] for r in stored] == [A2, A4, A5]
    assert stored[0]["meta"] == {
        "cik": 101,
        "accession": A2,
        "form": "8-K",
        "filed": "2026-09-15",
        "accepted": "2026-09-15T16:05:00.000Z",
    }
    assert all(r["path"].startswith("raw/sec-filings/") for r in stored)
    lists = [r for r in rows if str(r.get("name", "")).startswith("submissions-")]
    assert [r["kind"] for r in lists] == [
        "file",
        "file",
        "unchanged",
        "unchanged",
    ]  # an unchanged list: not stored twice
    # kept apart from the monthly company files, so the monthly fetch does not trip over them
    assert {r["source"] for r in lists} == {"sec-filings"}
    with Archive(tmp_path, readonly=True) as archive:
        assert sec._unfinished_batch(archive) is None


def test_limit_and_keep_going_stop_between_requests_and_the_next_run_continues(
    filings_site, tmp_path: Path, fetcher
) -> None:
    with Archive(tmp_path) as archive:
        part = fetch(archive, fetcher, filings_site, limit=2)
        assert part["filings_stored"] == 1 and not part["complete"] and part["companies_done"] == 0
        assert fetch(archive, fetcher, filings_site, "r2", keep_going=lambda: False)["asked"] == 0
        rest = fetch(archive, fetcher, filings_site, "r3")
    assert rest["filings_stored"] == 2 and rest["complete"]


@pytest.mark.parametrize("status", [429, 403])
def test_a_refusal_stops_the_job(filings_site, tmp_path: Path, fetcher, status: int) -> None:
    filings_site.add(f"/Archives/edgar/data/101/{A4}.txt", {"status": status})
    with Archive(tmp_path) as archive, pytest.raises(FetchError):
        fetch(archive, fetcher, filings_site)
    assert len(filings_site.hits) == 3  # stopped at the refusal: no further request


def test_a_missing_filing_is_asked_again_three_times_and_a_wrong_answer_until_it_is_right(
    filings_site, tmp_path: Path, fetcher
) -> None:
    filings_site.add(f"/Archives/edgar/data/101/{A2}.txt", {"status": 404})
    wrong = {"body": b"<html>please slow down " + A4.encode() + b"</html>"}  # names the filing, but is not it
    filings_site.add(f"/Archives/edgar/data/101/{A4}.txt", wrong, {"body": filing_text(A4)})
    filings_site.add("/submissions/CIK0000000103.json", {"body": filing_list(999, [])})
    with Archive(tmp_path) as archive:
        first = fetch(archive, fetcher, filings_site)
        assert first["not_found"] == 1 and first["odd"] == 2 and first["filings_stored"] == 1 and not first["complete"]
        again = fetch(archive, fetcher, filings_site, "r2")
        assert again["filings_stored"] == 1 and again["not_found"] == 1  # both asked again
        assert A2 not in sec_filings.stored_accessions(archive) and A2 not in sec_filings.given_up(archive)
        third = fetch(archive, fetcher, filings_site, "r3")
        fourth = fetch(archive, fetcher, filings_site, "r4")
        assert third["not_found"] == 1 and fourth["not_found"] == 0 and A2 in sec_filings.given_up(archive)
        assert A2 not in sec_filings.stored_accessions(archive)  # the cross-check still sees it as missing


def test_a_filing_that_is_too_large_is_noted_and_does_not_block_the_rest(filings_site, tmp_path: Path, waits) -> None:
    small = sec.sec_fetcher(CONTACT, allowed_hosts=LOCAL, timeout=5, backoff=(), sleep=waits.append, max_bytes=5000)
    filings_site.add(f"/Archives/edgar/data/101/{A2}.txt", {"body": filing_text(A2) + b"x" * 9000})
    with Archive(tmp_path) as archive:
        first = fetch(archive, small, filings_site)
        again = fetch(archive, small, filings_site, "r2")
    assert first["too_large"] == 1 and first["filings_stored"] == 2 and again["asked"] == 2  # not asked again


def test_many_wrong_answers_in_a_row_stop_the_job(filings_site, tmp_path: Path, fetcher, monkeypatch) -> None:
    monkeypatch.setattr(sec_filings, "MAX_ODD_IN_A_ROW", 2)
    for accession in (A2, A4, A5):
        filings_site.add(f"/Archives/edgar/data/101/{accession}.txt", {"body": b"<html>maintenance</html>"})
    with Archive(tmp_path) as archive, pytest.raises(SourceError, match="not filings"):
        fetch(archive, fetcher, filings_site)
    assert len(filings_site.hits) == 3  # one filing list, two wrong answers, then it stopped


@pytest.mark.parametrize(
    "rows",
    [
        [("../../etc/passwd", "8-K", "2026-11-03")],
        [("0000000101-26-1", "8-K", "2026-11-03")],
        [("0000000101-26-00000x", "8-K", "2026-11-03")],
        [("\u0660" * 10 + "-26-000001", "8-K", "2026-11-03")],  # digits, but not the plain ones
        [(A5, "8-K", "tomorrow")],
    ],
)
def test_an_accession_number_or_day_in_another_form_is_never_used(filings_site, tmp_path: Path, fetcher, rows) -> None:
    filings_site.add("/submissions/CIK0000000101.json", {"body": filing_list(101, rows)})
    with Archive(tmp_path) as archive:
        summary = fetch(archive, fetcher, filings_site, ciks=[101])
    assert summary["odd"] == 1 and summary["filings_stored"] == 0 and len(filings_site.hits) == 1


def test_which_forms_are_followed() -> None:
    yes = ["8-K", "8-K/A", "4", "4/A", "S-3", "S-3ASR", "424B5", "SC 13D/A", "SCHEDULE 13G", "10-Q", "10-K/A", " 8-k "]
    no = ["DEF 14A", "3", "144", "S-8", "424B3", "10-KT", ""]
    assert all(sec_filings.followed(f) for f in yes) and not any(sec_filings.followed(f) for f in no)


INDEX = f"""Description:           Daily Index of EDGAR Dissemination Feed
Last Data Received:    Nov 03, 2026

CIK|Company Name|Form Type|Date Filed|File Name
--------------------------------------------------------------------------------
101|Alpha Therapeutics, Inc.|4|20261103|edgar/data/101/{A5}.txt
101|Alpha Therapeutics, Inc.|8-K/A|20261103|edgar/data/101/{A4}.txt
103|Some Fund | Of Many Words LP|SCHEDULE 13G/A|20261103|edgar/data/103/0000000777-26-000009.txt
101|Alpha Therapeutics, Inc.|DEF 14A|20261103|edgar/data/101/{A3}.txt
555|Somebody Else Corp|8-K|20261103|edgar/data/555/0000000555-26-000001.txt
"""


def test_index_entries_reads_forms_with_spaces() -> None:
    entries = sec_filings.index_entries(INDEX.encode())
    assert entries[:3] == [("4", 101, A5), ("8-K/A", 101, A4), ("SCHEDULE 13G/A", 103, "0000000777-26-000009")]
    for bad in (b"<html>not an index</html>", b"Form Type   Company Name\n-----\n4   Alpha  101  20261103  x/y.txt\n"):
        with pytest.raises(SourceError):
            sec_filings.index_entries(bad)


def test_crosscheck_names_followed_filings_of_our_companies_that_are_not_stored(
    filings_site, tmp_path: Path, fetcher
) -> None:
    filings_site.add("/daily-index/2026/QTR4/master.20261103.idx", {"body": INDEX.encode()})
    # a Saturday and a regular holiday (not asked for), a day whose index is "not found", and a normal day
    days = [date(2026, 10, 31), date(2026, 9, 7), date(2026, 11, 2), date(2026, 11, 3)]

    def check(archive, name: str) -> dict:
        return sec_filings.run_crosscheck(
            archive, fetcher, name, ciks=[101, 103], days=days, since=SINCE, index_url=filings_site.index_url
        )

    with Archive(tmp_path) as archive:
        with pytest.raises(SourceError, match="1 filing") as caught:
            fetch(archive, fetcher, filings_site)
            check(archive, "c1")
        assert "0000000777-26-000009" in str(caught.value) and A5 not in str(caught.value)
        archive.store(
            "sec-filings",
            "filing-0000000777-26-000009.txt",
            b"x",
            run="m",
            info={"meta": {"accession": "0000000777-26-000009"}},
        )
        summary = check(archive, "c2")
    assert summary["missing"] == 0 and summary["days_checked"] == 1 and summary["days_without_index"] == 1
    assert summary["our_filings_in_the_index"] == 3
    assert sum("daily-index" in h for h in filings_site.hits) == 4  # two days asked, in two checks


def test_crosscheck_stops_at_a_forbidden_answer(filings_site, tmp_path: Path, fetcher) -> None:
    filings_site.add("/daily-index/2026/QTR4/master.20261102.idx", {"status": 403})
    with Archive(tmp_path) as archive, pytest.raises(FetchError):
        sec_filings.run_crosscheck(
            archive,
            fetcher,
            "c1",
            ciks=[101],
            days=[date(2026, 11, 2), date(2026, 11, 3)],
            since=SINCE,
            index_url=filings_site.index_url,
        )
    assert len(filings_site.hits) == 1


def test_reading_a_header_its_documents_and_an_event_reports_items() -> None:
    body = filing_text(A2, items=("Entry into a Material Definitive Agreement", "Financial Statements and Exhibits"))
    head = read.header(body)
    assert (head.accession, head.form, head.filed, head.period) == (A2, "8-K", date(2026, 11, 3), date(2026, 11, 2))
    assert head.accepted == datetime(2026, 11, 3, 16, 5, 44) and head.names == (("filer", "ALPHA THERAPEUTICS INC"),)
    assert head.items == ("Entry into a Material Definitive Agreement", "Financial Statements and Exhibits")
    docs = read.documents(body)
    assert [(d.type, d.sequence, d.filename) for d in docs] == [("8-K", "1", "main.htm"), ("EX-99.1", "2", "press.htm")]
    assert docs[1].text.strip() == b"<html>a made-up press release</html>"
    for bad in (b"", b"<html>blocked</html>", b"<SEC-DOCUMENT>x\n<SEC-HEADER>\n</SEC-HEADER>"):
        with pytest.raises(read.FilingError):
            read.header(bad)


def test_reading_the_lines_of_an_insider_trade() -> None:
    sold, option = read.insider_trades(filing_text(A5, "4", (), OWNERSHIP))
    assert sold == read.Trade(
        owner="DOE JANE",
        roles=("director", "officer (Chief Medical Officer)"),
        security="Common Stock",
        day=date(2026, 11, 2),
        code="S",
        shares=1000.0,
        price=12.5,
        acquired=False,
        shares_after=4000.0,
        derivative=False,
    )
    assert (option.code, option.derivative, option.price, option.acquired, option.shares_after) == (
        "M",
        True,
        None,
        True,
        None,
    )
    with pytest.raises(read.FilingError):
        read.insider_trades(filing_text(A2))
    with pytest.raises(read.FilingError):
        read.insider_trades(filing_text(A5, "4", (), "<XML><ownershipDocument><broken></XML>"))
    bomb = '<XML><?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><ownershipDocument>&a;</ownershipDocument></XML>'
    with pytest.raises(read.FilingError):
        read.insider_trades(filing_text(A5, "4", (), bomb))  # XML tricks are refused, not expanded


@pytest.fixture
def commands(filings_site, tmp_path: Path, monkeypatch, waits):
    data = tmp_path / "data"
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    monkeypatch.setattr(archive_cli, "_before_evening", lambda: True)
    made = sec.sec_fetcher(CONTACT, allowed_hosts=LOCAL, timeout=5, backoff=(), sleep=waits.append)
    monkeypatch.setattr(archive_cli, "make_sec_fetcher", lambda: made)
    monkeypatch.setattr(sec, "SEC_SUBMISSIONS_URL", filings_site.submissions_url)
    monkeypatch.setattr(sec_filings, "SEC_FILING_URL", filings_site.filing_url)
    monkeypatch.setattr(sec_filings, "SEC_DAILY_INDEX_URL", filings_site.index_url)
    monkeypatch.setattr(sec_filings, "FILINGS_FROM", SINCE)
    return data


def write_universe(data: Path) -> None:
    folder = data / "universe"
    folder.mkdir(parents=True)
    text = "cik,name,in_universe,ticker_used,former_names\n101,Alpha Therapeutics Inc,yes,ALFA,\n103,Gamma Corp,yes,GAMA,\n555,Out Corp,no,OUT,\n"
    (folder / "2026-11-18_universe.csv").write_text(text)


def test_without_a_universe_the_commands_do_nothing(commands: Path, filings_site, capsys) -> None:
    assert (
        archive_cli.main(["sec-filings"]) == 0
        and "skipped sec-filings: no universe file yet" in capsys.readouterr().out
    )
    assert archive_cli.main(["sec-crosscheck"]) == 1
    assert filings_site.hits == []


def test_sec_filings_command_then_recent_shows_items_and_trades(commands: Path, filings_site, capsys) -> None:
    write_universe(commands)
    assert archive_cli.main(["sec-filings", "--limit", "2"]) == 0 and archive_cli.main(["sec-filings"]) == 0
    out = capsys.readouterr().out
    assert "'filings_stored': 2" in out and "test-host" not in out
    everything = b"".join(p.read_bytes() for p in (commands / "archive").rglob("*") if p.is_file())
    assert b"test-host" not in everything
    assert filings_cli.main(["recent", "--days", "4000"]) == 0
    shown = capsys.readouterr().out
    assert "8-K            Alpha Therapeutics Inc" in shown and "Other Events" in shown
    assert "DOE JANE [director, officer (Chief Medical Officer)]: 2 transaction(s), codes M S" in shown
    assert "3 filing(s) since" in shown
    assert filings_cli.main(["recent", "--days", "4000", "--form", "4"]) == 0
    assert "1 filing(s) since" in capsys.readouterr().out


def test_the_nightly_run_includes_the_filings_and_a_refusal_fails_only_that_source(
    commands: Path, filings_site, monkeypatch, capsys
) -> None:
    from bobby_hedgefund.archive import sources

    write_universe(commands)
    monkeypatch.setattr(sources, "FILE_GROUPS", ())
    assert archive_cli.main(["run", "--only", "sec-filings"]) == 0
    assert "ok      sec-filings" in capsys.readouterr().out
    filings_site.add("/submissions/CIK0000000101.json", {"status": 429})
    assert archive_cli.main(["run", "--only", "sec-filings"]) == 1
    assert "FAILED  sec-filings" in capsys.readouterr().out


def test_the_nightly_filings_job_stops_when_its_time_is_up(commands: Path, filings_site, monkeypatch, capsys) -> None:
    from bobby_hedgefund.archive import sources

    write_universe(commands)
    monkeypatch.setattr(sources, "FILE_GROUPS", ())
    monkeypatch.setattr(archive_cli, "NIGHTLY_FILINGS_SECONDS", 0)
    assert archive_cli.main(["run", "--only", "sec-filings"]) == 0
    assert "'asked': 0" in capsys.readouterr().out and filings_site.hits == []

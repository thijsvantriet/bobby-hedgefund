from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fundkit import COMPANIES, MON, TUE, WED, session, store_day, store_splits
from logkit import clock, forecast, make_log

from bobby_hedgefund.archive.store import Archive, iso, sha256_hex
from bobby_hedgefund.session import cli, plaintext, select, sources, tasks
from bobby_hedgefund.session import prepare as prep

CUTOFF = datetime(2027, 2, 3, 8, 0, tzinfo=UTC)  # Wednesday morning
SINCE = datetime(2027, 2, 2, 8, 0, tzinfo=UTC)
HIDDEN = (105, "EEE", "Eee Hidden Devices Inc")


def filing(accession: str, form: str, filed: str, items: str = "", main: str = "", extra: str = "") -> bytes:
    item_lines = "".join(f"ITEM INFORMATION:\t\t{i}\n" for i in items.split(";") if i)
    return f"""<SEC-DOCUMENT>{accession}.txt : {filed}
<SEC-HEADER>{accession}.hdr.sgml : {filed}
<ACCEPTANCE-DATETIME>{filed}160000
ACCESSION NUMBER:\t\t{accession}
CONFORMED SUBMISSION TYPE:\t{form}
CONFORMED PERIOD OF REPORT:\t{filed}
{item_lines}FILED AS OF DATE:\t\t{filed}
FILER:
\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\t\t\tAaa Therapeutics Inc
</SEC-HEADER>
<DOCUMENT>
<TYPE>{form}
<SEQUENCE>1
<FILENAME>main.htm
<TEXT>
<html><head><style>p {{ color: red }}</style></head><body>{main}</body></html>
</TEXT>
</DOCUMENT>
{extra}</SEC-DOCUMENT>
""".encode("latin-1")


PRESS = """<DOCUMENT>
<TYPE>EX-99.1
<SEQUENCE>2
<FILENAME>press.htm
<DESCRIPTION>PRESS RELEASE
<TEXT>
<html><body><p>The primary endpoint was met &amp; the drug was well tolerated.</p></body></html>
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>GRAPHIC
<SEQUENCE>3
<FILENAME>logo.jpg
<TEXT>
begin 644 logo.jpg
M_]C_X  02D9)1@
end
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-10.1
<SEQUENCE>4
<FILENAME>loan.htm
<TEXT>
<html><body><p>A loan agreement that is not copied.</p></body></html>
</TEXT>
</DOCUMENT>
"""


def store_filing(data: Path, cik: int, accession: str, form: str, filed: str, when: datetime, **parts: str) -> str:
    body = filing(accession, form, filed.replace("-", ""), **parts)
    meta = {"cik": cik, "accession": accession, "form": form, "filed": filed}
    with Archive(data / "archive") as archive:
        rec = archive.store(
            "sec-filings", f"filing-{accession}.txt", body, run="r", when=when, compress=True, info={"meta": meta}
        )
    return rec["sha256"]


def universe_file(data: Path, label: str = "2027-02-01", made: str = "2027-02-01T07:00:00Z", listed: str = "") -> None:
    header = "cik,name,in_universe,why_out,ticker_used,exchanges,sic,door,in_xbi,filer_type,market_value\n"
    rows = "".join(
        f"{cik},{name},yes,,{ticker},Nasdaq,2834,own code,no,domestic,{mv or ''}\n"
        for cik, (ticker, name, mv) in COMPANIES.items()
    )
    hidden = f"{HIDDEN[0]},{HIDDEN[2]},yes,,{HIDDEN[1]},Nasdaq,3841,xbi only,yes,domestic,700000000\n"
    out = "999,Out Corp,no,price,OUT,Nasdaq,2834,own code,no,domestic,\n"
    folder = data / "universe"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{label}_universe.csv").write_text(header + rows + hidden + out)
    (folder / f"{label}_universe-inputs.txt").write_text(f"# universe\n# made: {made}\n# files read:\n{listed}")


@pytest.fixture
def data(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    universe_file(data)
    store_splits(data / "prices", [])
    store_day(
        data / "prices",
        date(2027, 1, 29),
        {"AAA": (10.0, 10.0), "BBB": (20.0, 20.0), "CCC": (5.0, 5.0), "EEE": (3.0, 3.0)},
    )
    store_day(data / "prices", MON, {"AAA": (10.0, 10.0), "BBB": (20.0, 20.0), "CCC": (5.0, 5.0), "EEE": (3.0, 3.0)})
    store_day(data / "prices", TUE, {"AAA": (10.0, 12.0), "BBB": (20.0, 20.4), "CCC": (5.0, 5.0), "EEE": (3.0, 9.0)})
    return data


def run(data: Path, **kw) -> prep.Prepared:
    args = {"session_day": WED, "start_time": CUTOFF, "cutoff": CUTOFF, "since": SINCE, **kw}
    return prep.prepare(data_dir=data, mode_root=data / "pilot", **args)


# ---------------------------------------------------------------- plain text and the cut-off rules


def test_a_filing_document_becomes_plain_text() -> None:
    html = b"<html><head><title>x</title><script>var a=1;</script></head><body><p>First&nbsp;line &amp; more</p>"
    html += b"<table><tr><td>Cash</td><td>100</td></tr><tr><td>Debt</td><td>20</td></tr></table>"
    html += b"<div>Last</div></body></html>"
    # The head with its title, scripts and styles goes; a table row becomes one line.
    assert plaintext.to_text(html) == "First line & more\n\nCash | 100\n\nDebt | 20\n\nLast\n"
    assert plaintext.to_text(b"Plain  text\r\n\r\n\r\n\r\nSecond") == "Plain text\n\nSecond\n"
    assert plaintext.is_binary(b"\nbegin 644 logo.jpg\nM_]C") and not plaintext.is_binary(
        b"<html>begin the trial</html>"
    )


def test_a_file_our_own_jobs_made_is_admitted_only_when_all_its_inputs_were_saved_before_the_cut_off(
    tmp_path: Path,
) -> None:
    root = tmp_path / "archive"
    with Archive(root) as archive:
        early = archive.store("x", "a.txt", b"a", run="r", when=datetime(2027, 2, 1, 6, tzinfo=UTC))
        late = archive.store("x", "b.txt", b"b", run="r", when=datetime(2027, 2, 3, 9, tzinfo=UTC))
    times = sources.stored_times(root, tmp_path / "nothing-here")
    assert times[(early["path"], early["sha256"])] == "2027-02-01T06:00:00Z"
    note = tmp_path / "x-inputs.txt"

    def verdict(made: str, *recs: dict) -> tuple[bool, str]:
        note.write_text(f"# x\n# made: {made}\n" + "".join(f"{r['sha256']}  {r['path']}\n" for r in recs))
        return sources.admitted(note, times, CUTOFF)

    assert verdict("2027-02-02T07:00:00Z", early) == (True, "")
    assert verdict("2027-02-03T08:00:00Z", early)[1] == "it was made after the cut-off"
    assert verdict("2027-02-02T07:00:00Z", early, late)[1] == "one of its inputs was saved after the cut-off"
    unknown = {"sha256": "0" * 64, "path": "raw/x/unknown.txt"}
    assert verdict("2027-02-02T07:00:00Z", unknown)[1] == "one of its inputs is not in the lists of saved files"
    note.write_text("no header at all\n")
    assert sources.admitted(note, times, CUTOFF)[1] == "its list of inputs does not say when it was made"
    assert sources.admitted(tmp_path / "missing.txt", times, CUTOFF)[1] == "its list of inputs is missing"


def test_the_newest_admitted_file_goes_by_its_name_never_by_the_date_of_the_file(data: Path) -> None:
    universe_file(data, "2027-02-02", made="2027-02-02T07:00:00Z")
    universe_file(data, "2027-02-02-2", made="2027-02-02T09:00:00Z")
    universe_file(data, "2027-02-04", made="2027-02-04T07:00:00Z")  # made after the cut-off
    (data / "universe" / "2027-02-01_universe.csv").touch()  # the oldest file has the newest date on disk
    path, notes = sources.newest_admitted(data / "universe", "universe.csv", "universe-inputs.txt", {}, CUTOFF)
    assert path is not None and path.name == "2027-02-02-2_universe.csv"
    assert notes == ["2027-02-04_universe.csv is not used: it was made after the cut-off"]
    assert (
        sources.newest_admitted(
            data / "universe", "universe.csv", "universe-inputs.txt", {}, datetime(2027, 1, 1, tzinfo=UTC)
        )[0]
        is None
    )


# ---------------------------------------------------------------- the session folder


def test_the_session_folder_holds_only_what_was_saved_before_the_cut_off(data: Path) -> None:
    main = "<p>Cash was $245.3 million.</p>"
    sha = store_filing(
        data,
        101,
        "0000000101-27-000001",
        "8-K",
        "2027-02-02",
        datetime(2027, 2, 2, 23, tzinfo=UTC),
        items="Regulation FD Disclosure;Financial Statements and Exhibits",
        main=main,
        extra=PRESS,
    )
    store_filing(
        data,
        101,
        "0000000101-27-000002",
        "8-K",
        "2027-02-03",
        datetime(2027, 2, 3, 9, tzinfo=UTC),
        main="<p>After the cut-off.</p>",
    )
    store_filing(
        data,
        102,
        "0000000102-27-000001",
        "10-Q",
        "2026-11-05",
        datetime(2027, 2, 2, 23, tzinfo=UTC),
        main="<p>Fetched late.</p>",
    )
    store_filing(
        data,
        103,
        "0000000103-27-000001",
        "8-K",
        "2027-02-01",
        datetime(2027, 2, 1, 23, tzinfo=UTC),
        main="<p>Before the last session.</p>",
    )
    store_filing(
        data,
        999,
        "0000000999-27-000001",
        "8-K",
        "2027-02-02",
        datetime(2027, 2, 2, 23, tzinfo=UTC),
        main="<p>Not in the universe.</p>",
    )
    store_day(data / "prices", WED, {"AAA": (1.0, 1.0)})  # stored on Thursday: after the cut-off
    done = run(data)
    folder = done.folder
    assert folder == data / "pilot" / "sessions" / "2027-02-03"
    assert done.counts["filings"] == 1 and done.counts["filings_saved_late_and_left_out"] == 1
    assert done.counts["price_day"] == "2027-02-02" and done.counts["companies"] == 4
    (text_file,) = (folder / "companies" / "101" / "filings").iterdir()
    text = text_file.read_text()
    assert text_file.name == "0002-8-K.txt" and "Cash was $245.3 million." in text
    assert "Items: Regulation FD Disclosure; Financial Statements and Exhibits" in text
    assert (
        "The primary endpoint was met & the drug was well tolerated." in text
        and "===== document: EX-99.1 PRESS RELEASE" in text
    )
    assert "color: red" not in text and "M_]C" not in text and "loan agreement" not in text
    assert (
        not (folder / "companies" / "102" / "filings").exists()
        and not (folder / "companies" / "103" / "filings").exists()
    )
    assert not (folder / "companies" / "999").exists()
    everything = b"".join(p.read_bytes() for p in folder.rglob("*") if p.is_file())
    assert b"After the cut-off" not in everything and b"Fetched late" not in everything
    lines = [json.loads(line) for line in (folder / "inputs.jsonl").read_text().splitlines()]
    assert [(line["n"], line["kind"]) for line in lines] == [(1, "universe"), (2, "sec filing"), (3, "prices")]
    by_kind = {line["kind"]: line for line in lines}
    assert by_kind["sec filing"]["sha256"] == sha and by_kind["sec filing"]["stored"] == "2027-02-02T23:00:00Z"
    assert (
        by_kind["sec filing"]["link"]
        == "https://www.sec.gov/Archives/edgar/data/101/000000010127000001/0000000101-27-000001-index.htm"
    )
    assert by_kind["prices"]["day"] == "2027-02-02" and by_kind["prices"]["copy"] == "final"
    assert done.inputs_sha256 == sha256_hex((folder / "inputs.jsonl").read_bytes())
    stored = json.loads((folder / "session.json").read_text())
    assert stored["cutoff"] == "2027-02-03T08:00:00Z" and stored["inputs_sha256"] == done.inputs_sha256
    assert stored["results_news"] == [101] and stored["with_news"] == [101]
    assert all((p.stat().st_mode & 0o222) == 0 for p in folder.rglob("*") if p.is_file())  # nothing in it is writable
    with pytest.raises(prep.PrepareError, match="made once"):
        run(data)


def test_what_is_new_per_company_and_the_screening_list(data: Path) -> None:
    store_filing(data, 102, "0000000102-27-000009", "4", "2027-02-02", datetime(2027, 2, 2, 23, tzinfo=UTC))
    done = run(data, held={101})
    folder = done.folder
    company = (folder / "companies" / "101" / "company.md").read_text()
    assert company.startswith("# Aaa Therapeutics Inc\nTicker: AAA    SEC company number: 101\n")
    assert "the share moved +20.0% since the last session" in company  # 10 on Monday's close, 12 on Tuesday's
    numbers = (folder / "companies" / "101" / "numbers.md").read_text()
    assert (
        "PRIVATE" in numbers
        and "Last closing price: 12.00" in numbers
        and "Change over 1 trading day: +20.0%" in numbers
    )
    assert "about $3,000 million" in numbers
    assert "nothing new" in (folder / "companies" / "103" / "company.md").read_text()
    assert "- nothing new" not in (folder / "companies" / "102" / "company.md").read_text()  # the insider filing
    batch = (folder / "screening" / "batch-01.md").read_text()
    assert "## 101 Aaa Therapeutics Inc (AAA)  (held by a fund)" in batch and "## 102 Bbb Bio Inc (BBB)\n" in batch
    assert "## 103" not in batch  # BBB moved 2%: no item; CCC did not move
    assert (folder / "screening" / "no-news.txt").read_text() == "103\n104\n"
    assert done.counts["companies_with_news"] == 2 and done.counts["screening_batches"] == 1
    insider = next((folder / "companies" / "102" / "filings").iterdir()).read_text()
    assert "Kind: 4" in insider and "could not be read" in insider  # the made-up filing has no lines to read


def test_companies_that_may_not_be_named_get_no_folder_and_go_on_the_private_list(data: Path) -> None:
    store_filing(
        data,
        HIDDEN[0],
        "0000000105-27-000001",
        "8-K",
        "2027-02-02",
        datetime(2027, 2, 2, 23, tzinfo=UTC),
        main="<p>Hidden news.</p>",
    )
    done = run(data)
    assert done.counts["left_out_as_private"] == 1 and HIDDEN[0] not in done.companies
    assert not (done.folder / "companies" / str(HIDDEN[0])).exists()
    everything = b"".join(p.read_bytes() for p in done.folder.rglob("*") if p.is_file())
    assert b"Hidden" not in everything and b"EEE" not in everything and b"xbi" not in everything.lower()
    private = data / "pilot" / "private-names.tsv"
    assert (
        f"{HIDDEN[0]}\t{HIDDEN[1]}\t{HIDDEN[2]}\n" in private.read_text() and (private.stat().st_mode & 0o777) == 0o600
    )


def test_trial_changes_wait_for_the_linking_table_and_use_it_once_it_may_be_used(data: Path, tmp_path: Path) -> None:
    changes = data / "trial-changes"
    changes.mkdir()
    change = {
        "nct": "NCT00000001",
        "field": "primary_completion_date",
        "old": {"date": "2027-03", "type": "ESTIMATED"},
        "new": {"date": "2027-09", "type": "ESTIMATED"},
        "moved_days": 184,
        "new_file": "raw/ctgov-updates/x.json.xz",
        "new_saved": "2027-02-02T22:30:00Z",
        "new_posted": "2027-02-02",
    }
    late = {**change, "nct": "NCT00000002", "new_saved": "2027-02-03T09:00:00Z"}
    other = {
        **change,
        "nct": "NCT00000003",
        "field": "overall_status",
        "old": "RECRUITING",
        "new": "TERMINATED",
        "moved_days": None,
    }
    (changes / "2027-02-03_changes.jsonl").write_text("".join(json.dumps(c) + "\n" for c in (change, late, other)))
    first = run(data)
    assert (
        first.counts["trial_changes"] == 2
        and first.counts["trial_changes_not_linked"] == 2
        and not first.counts["linking_table"]
    )
    assert "not linked yet" in (first.folder / "companies" / "101" / "trials.md").read_text()
    # The owner's check is done: a linking table exists. One made after the cut-off is passed over.
    linking = data / "linking"
    linking.mkdir()
    table = "cik,company,sponsor_name,relation,trials,as_lead,trial_numbers\n"
    table += "101,Aaa,Aaa Tx,yes,2,2,NCT00000001 NCT00000002\n105,Eee,Eee,yes,1,1,NCT00000003\n"
    (linking / "2027-02-02_linking.csv").write_text(table)
    (linking / "2027-02-02_linking-inputs.txt").write_text("# linking table\n# made: 2027-02-02T12:00:00Z\n")
    (linking / "2027-02-04_linking.csv").write_text(table.replace("101,Aaa", "102,Bbb"))
    (linking / "2027-02-04_linking-inputs.txt").write_text("# linking table\n# made: 2027-02-04T12:00:00Z\n")
    second = prep.prepare(
        data_dir=data, mode_root=tmp_path / "second", session_day=WED, start_time=CUTOFF, cutoff=CUTOFF, since=SINCE
    )
    assert second.counts["linking_table"] and second.counts["trial_changes_not_linked"] == 1  # the hidden company's
    trials = (second.folder / "companies" / "101" / "trials.md").read_text()
    wanted = "trial NCT00000001: primary completion date changed from 2027-03 (estimated) to 2027-09 (estimated)"
    assert wanted + " (moved 184 days)" in trials
    assert "NCT00000002" not in trials and "NCT00000003" not in trials
    assert "No change" in (second.folder / "companies" / "102" / "trials.md").read_text()
    assert any("2027-02-04_linking.csv is not used" in note for note in second.notes)
    kinds = [json.loads(line)["kind"] for line in (second.folder / "inputs.jsonl").read_text().splitlines()]
    assert kinds.count("trial record") == 1 and "linking table" in kinds


def test_our_own_newest_report_is_copied_in_and_no_usable_universe_stops_everything(data: Path) -> None:
    reports = data / "pilot" / "reports" / "101"
    reports.mkdir(parents=True)
    (reports / "2027-01-20.md").write_text("old report\n")
    (reports / "2027-02-01.md").write_text("newest report\n")
    done = run(data)
    assert (done.folder / "companies" / "101" / "report.md").read_text() == "newest report\n"
    assert not (done.folder / "companies" / "102" / "report.md").exists()
    with pytest.raises(prep.PrepareError, match="no universe file may be used"):
        prep.prepare(
            data_dir=data,
            mode_root=data / "early",
            session_day=WED,
            start_time=CUTOFF,
            cutoff=datetime(2027, 1, 1, tzinfo=UTC),
            since=SINCE,
        )


def test_screening_goes_in_batches_of_25(data: Path, monkeypatch) -> None:
    monkeypatch.setattr(prep, "BATCH", 1)
    store_filing(data, 102, "0000000102-27-000009", "8-K", "2027-02-02", datetime(2027, 2, 2, 23, tzinfo=UTC))
    done = run(data)
    assert sorted(p.name for p in (done.folder / "screening").iterdir()) == [
        "batch-01.md",
        "batch-02.md",
        "no-news.txt",
    ]
    assert prep.BATCH == 1 and done.counts["screening_batches"] == 2


def test_the_command_takes_what_is_new_from_the_last_session_in_the_log(data: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    from bobby_hedgefund.log.store import Log

    log = Log.for_mode("pilot")
    with log.writer(TUE, clock()) as w:
        w.add("session_start", session(log, TUE, 8))
    assert cli.last_cutoff(log) == SINCE
    monkeypatch.setattr(cli, "utcnow", lambda: datetime(2027, 2, 3, 8, 0, 5, tzinfo=UTC))
    assert cli.main(["prepare", "--day", "2027-02-03", "--cutoff", "2027-02-03T08:00:00Z"]) == 0
    out = capsys.readouterr().out
    assert "session folder: <data folder>/pilot/sessions/2027-02-03" in out and "new since: 2027-02-02T08:00:00Z" in out
    assert str(data) not in out and "companies_with_news" in out
    assert cli.main(["prepare", "--day", "2027-02-03", "--cutoff", "2027-02-03T08:00:00Z"]) == 1
    assert cli.main(["prepare", "--day", "2027-02-04", "--cutoff", "2999-01-01T00:00:00Z"]) == 1
    assert "in the future" in capsys.readouterr().out


# ---------------------------------------------------------------- who gets a deep analysis


def test_the_order_of_deep_analysis() -> None:
    universe = set(range(1, 41))
    order = select.rotation(universe)
    assert order == select.rotation(set(reversed(sorted(universe)))) and order != sorted(universe)
    chosen = select.deep_order(
        universe=universe,
        held_with_news={7, 3},
        flagged=[12, 7, 30],
        catalysts={20: date(2027, 3, 1), 21: date(2027, 2, 10), 99: date(2027, 2, 5)},
        last_report={c: date(2027, 1, 1) for c in universe if c not in (33, 34)},
        limit=40,
    )
    ciks = [c for c, _ in chosen]
    assert set(ciks[:2]) == {3, 7} and ciks[2:4] == [12, 30] and ciks[4:6] == [21, 20]  # 99 is not in the universe
    assert set(ciks[6:8]) == {33, 34} and len(ciks) == len(set(ciks)) == 40
    assert chosen[0][1] == "a fund holds it and there is news" and chosen[2][1] == "the screening flagged it"
    assert chosen[4][1] == "a catalyst within 60 days" and chosen[6][1] == "rotation: no report yet"
    four = select.deep_order(universe=universe, held_with_news=set(), flagged=[], catalysts={}, last_report={})
    assert len(four) == select.MOST == 4 and [c for c, _ in four] == order[:4]
    # When every company has a report, the one with the oldest report comes first.
    dated = {c: date(2027, 1, 1) + timedelta(days=c) for c in universe}
    oldest = select.deep_order(
        universe=universe, held_with_news=set(), flagged=[], catalysts={}, last_report=dated, limit=2
    )
    assert [c for c, _ in oldest] == [1, 2]


def test_until_there_is_a_calendar_the_catalysts_come_from_our_open_forecasts(tmp_path: Path) -> None:
    log = make_log(tmp_path)
    with log.writer(MON, clock()) as w:
        w.add("forecast", {**forecast(), "by_date": "2027-03-20"})
        w.add("forecast", {**forecast(), "by_date": "2027-02-15"})
        w.add("forecast", {**forecast(), "by_date": "2027-06-01", "company": {"cik": 102, "name": "Bbb Bio Inc"}})
        w.add("forecast", {**forecast(), "by_date": "2027-02-10", "company": {"cik": 103, "name": "Ccc Pharma Inc"}})
        w.add("outcome", {"ref": 4, "result": "no", "resolved_on": "2027-02-01", "summary": "Missed.", "sources": []})
    assert select.calendar_from_forecasts(log.entries(), MON) == {1234567: date(2027, 2, 15)}


# ---------------------------------------------------------------- task files


def test_a_task_file_is_written_once_and_a_change_to_it_is_noticed(tmp_path: Path) -> None:
    made = tasks.write(
        tmp_path, "analysis-101-science", "bobby-science-analyst", "Read companies/101 and write your section."
    )
    again = tasks.write(tmp_path, "pm-careful-run-2", "bobby-pm-careful", "Decide.\n", run=2)
    assert made.file == "tasks/analysis-101-science.md" and made.sha256 == sha256_hex(
        b"Read companies/101 and write your section.\n"
    )
    assert (
        made.prompt(tmp_path) == f"Read the file {tmp_path}/tasks/analysis-101-science.md and do exactly what it says."
    )
    assert tasks.load(tmp_path) == {"analysis-101-science": made, "pm-careful-run-2": again} and again.run == 2
    assert tasks.unchanged(tmp_path, made)
    with pytest.raises(Exception, match="exists already"):
        tasks.write(tmp_path, "analysis-101-science", "bobby-science-analyst", "Another text.")
    path = tmp_path / made.file
    path.chmod(0o600)
    path.write_text("Buy everything.\n")
    assert not tasks.unchanged(tmp_path, made)
    path.unlink()
    assert not tasks.unchanged(tmp_path, made)
    for bad in ("../escape", "Has Capitals", "", "a/b"):
        with pytest.raises(tasks.TaskError):
            tasks.write(tmp_path, bad, "bobby-x", "text")
    assert iso(CUTOFF) == "2027-02-03T08:00:00Z"

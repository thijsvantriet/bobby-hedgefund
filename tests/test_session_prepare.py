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
    header = (
        "cik,name,in_universe,why_out,ticker_used,exchanges,sic,door,in_xbi,filer_type,market_value,"
        "shares,shares_as_of,shares_source\n"
    )
    shares = {101: "300000000,2027-01-15,cover page"}
    rows = "".join(
        f"{cik},{name},yes,,{ticker},Nasdaq,2834,own code,no,domestic,{mv or ''},{shares.get(cik, ',,')}\n"
        for cik, (ticker, name, mv) in COMPANIES.items()
    )
    hidden = f"{HIDDEN[0]},{HIDDEN[2]},yes,,{HIDDEN[1]},Nasdaq,3841,xbi only,yes,domestic,700000000,,,\n"
    out = "999,Out Corp,no,price,OUT,Nasdaq,2834,own code,no,domestic,,,,\n"
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
    curly = "The company\u2019s drug"
    assert plaintext.to_text(curly.encode("utf-8")) == curly + "\n" == plaintext.to_text(curly.encode("cp1252"))
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


def shown_earlier(data: Path, day: str, lines: list[dict]) -> None:
    """An earlier session's folder, with what its list of inputs showed."""
    folder = data / "pilot" / "sessions" / day
    folder.mkdir(parents=True)
    (folder / "session.json").write_text("{}\n")
    (folder / "inputs.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))


def test_the_session_folder_holds_only_what_was_saved_before_the_cut_off(data: Path) -> None:
    main = "<p>Cash was $245.3 million.</p>"
    evening = datetime(2027, 2, 2, 23, tzinfo=UTC)
    items = "Regulation FD Disclosure;Financial Statements and Exhibits"
    sha = store_filing(
        data, 101, "0000000101-27-000001", "8-K", "2027-02-02", evening, items=items, main=main, extra=PRESS
    )
    late = datetime(2027, 2, 3, 9, tzinfo=UTC)
    store_filing(data, 101, "0000000101-27-000002", "8-K", "2027-02-03", late, main="<p>After the cut-off.</p>")
    store_filing(data, 102, "0000000102-27-000001", "10-Q", "2026-11-05", evening, main="<p>Fetched late.</p>")
    monday = datetime(2027, 2, 1, 23, tzinfo=UTC)
    store_filing(data, 103, "0000000103-27-000001", "8-K", "2027-02-01", monday, main="<p>Shown yesterday.</p>")
    shown_earlier(data, "2027-02-02", [{"n": 2, "kind": "sec filing", "accession": "0000000103-27-000001"}])
    store_filing(data, 999, "0000000999-27-000001", "8-K", "2027-02-02", evening, main="<p>Not in the universe.</p>")
    store_day(data / "prices", WED, {"AAA": (1.0, 1.0)})  # stored on Thursday: after the cut-off
    done = run(data)
    folder = done.folder
    assert folder == data / "pilot" / "sessions" / "2027-02-03" and not list(folder.parent.glob(".*partial*"))
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
    assert not (folder / "companies" / "999").exists()
    everything = b"".join(p.read_bytes() for p in folder.rglob("*") if p.is_file())
    assert b"After the cut-off" not in everything
    # A filing fetched late, and one an earlier session showed, are no news. With four companies the order of
    # deep analysis can reach every one of them, so both are in the folder as earlier filings, marked as such.
    for cik, text_ in ((102, "Fetched late"), (103, "Shown yesterday")):
        company_md = (folder / "companies" / str(cik) / "company.md").read_text()
        assert "- nothing new" in company_md and "## Earlier filings, for reference" in company_md
        (earlier_file,) = (folder / "companies" / str(cik) / "filings").iterdir()
        assert text_ in earlier_file.read_text()
    assert not (folder / "screening" / "batch-01.md").read_text().count("## 10") > 1  # only company 101 is news
    lines = [json.loads(line) for line in (folder / "inputs.jsonl").read_text().splitlines()]
    assert [(line["n"], line["kind"], line.get("earlier", False)) for line in lines] == [
        (1, "universe", False),
        (2, "sec filing", False),
        (3, "prices", False),
        (4, "prices", False),
        (5, "sec filing", True),
        (6, "sec filing", True),
    ]
    assert lines[0]["name"] == "2027-02-01_universe.csv" and "file" not in lines[0]
    assert "company.md" in lines[0]["in_folder"]
    lines = lines[:4]
    filed = lines[1]
    assert (
        filed["sha256"] == sha
        and filed["stored"] == "2027-02-02T23:00:00Z"
        and filed["accession"] == "0000000101-27-000001"
    )
    assert (
        filed["link"] == "https://www.sec.gov/Archives/edgar/data/101/000000010127000001/0000000101-27-000001-index.htm"
    )
    # Every price day a number was worked out from is listed: the last one, and the one the last session saw.
    assert [(line["day"], line["copy"]) for line in lines[2:]] == [("2027-02-02", "final"), ("2027-02-01", "final")]
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
    assert (
        "the share moved +20.0% since the prices the last session saw" in company
    )  # 10 on Monday's close, 12 on Tuesday's
    numbers = (folder / "companies" / "101" / "numbers.md").read_text()
    assert (
        "PRIVATE" in numbers
        and "Last closing price: 12.00" in numbers
        and "Change over 1 trading day: +20.0%" in numbers
    )
    assert "about $3,000 million" in numbers
    # The market value of the universe run is old; the one of today is worked out from the same shares.
    assert "Market value now: about $3,600 million (last close [" in numbers and "as of 2027-01-15)" in numbers
    assert "Market value now" not in (folder / "companies" / "102" / "numbers.md").read_text()  # no share count
    assert "shares outstanding: 300,000,000 as of 2027-01-15" in company and "3,600" not in company
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


def page(data: Path, name: str, when: datetime) -> str:
    """A saved page of the trial registry; returns its path in the archive."""
    with Archive(data / "archive") as archive:
        return archive.store("ctgov-updates", name, name.encode(), run="r", when=when, compress=True)["path"]


def change(nct: str, path: str, saved: datetime, **more) -> dict:
    estimated = {"date": "2027-03", "type": "ESTIMATED"}
    base = {"nct": nct, "field": "primary_completion_date", "old": estimated, "new": {**estimated, "date": "2027-09"}}
    return {**base, "moved_days": 184, "new_file": path, "new_saved": iso(saved), "new_posted": "2027-02-02", **more}


LINKING = "cik,company,sponsor_name,relation,trials,as_lead,trial_numbers\n"


def linking_table(data: Path, label: str, made: str, rows: str) -> None:
    folder = data / "linking"
    folder.mkdir(exist_ok=True)
    (folder / f"{label}_linking.csv").write_text(LINKING + rows)
    (folder / f"{label}_linking-inputs.txt").write_text(f"# linking table\n# made: {made}\n")


def test_trial_changes_wait_for_the_linking_table_and_use_it_once_it_may_be_used(data: Path, tmp_path: Path) -> None:
    night = datetime(2027, 2, 2, 22, 30, tzinfo=UTC)
    a, b = page(data, "p1.json", night), page(data, "p2.json", datetime(2027, 2, 3, 9, tzinfo=UTC))
    c = page(data, "p3.json", night)
    stopped = {"field": "overall_status", "old": "RECRUITING", "new": "TERMINATED", "moved_days": None}
    lines = [
        change("NCT00000001", a, night),
        change("NCT00000002", b, datetime(2027, 2, 3, 9, tzinfo=UTC)),  # saved after the cut-off
        change("NCT00000003", c, night, **stopped),
        change("NCT00000004", "raw/ctgov-updates/never-saved.json.xz", night),  # names a page nobody saved
        change(
            "NCT00000001", a, datetime(2027, 2, 2, 21, tzinfo=UTC), field="enrollment"
        ),  # another time than the page's
    ]
    changes = data / "trial-changes"
    changes.mkdir()
    (changes / "2027-02-03_changes.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
    first = run(data)
    assert (
        first.counts["trial_changes"] == 2
        and first.counts["trial_changes_not_linked"] == 2
        and not first.counts["linking_table"]
    )
    assert "not linked yet" in (first.folder / "companies" / "101" / "trials.md").read_text()
    assert any("2 trial change(s) name a page that the saved-files list does not confirm" in n for n in first.notes)
    # The owner's check is done: a linking table exists. One made after the cut-off is passed over.
    rows = "101,Aaa,Aaa Tx,yes,2,2,NCT00000001 NCT00000002\n105,Eee,Eee,yes,1,1,NCT00000003\n"
    linking_table(data, "2027-02-02", "2027-02-02T12:00:00Z", rows)
    linking_table(data, "2027-02-04", "2027-02-04T12:00:00Z", rows.replace("101,Aaa", "102,Bbb"))
    second = prep.prepare(
        data_dir=data, mode_root=tmp_path / "second", session_day=WED, start_time=CUTOFF, cutoff=CUTOFF, since=SINCE
    )
    assert second.counts["linking_table"] and second.counts["trial_changes_not_linked"] == 1  # the hidden company's
    trials = (second.folder / "companies" / "101" / "trials.md").read_text()
    wanted = "trial NCT00000001: primary completion date changed from 2027-03 (estimated) to 2027-09 (estimated)"
    assert wanted + " (moved 184 days)" in trials
    assert "trial NCT00000002" not in trials and "NCT00000003" not in trials  # a change saved after the cut-off
    # The company's own lines of the linking table (pilot, 2026-11-27: agents could not open the table itself).
    assert "Linking table [" in trials and "- Aaa Tx: 2 trial(s), 2 as lead sponsor" in trials
    assert "  - NCT00000002: https://clinicaltrials.gov/study/NCT00000002" in trials
    other = (second.folder / "companies" / "102" / "trials.md").read_text()
    assert "No change" in other and "no trials are linked to this company" in other
    linking_line = next(
        json.loads(line) for line in (second.folder / "inputs.jsonl").read_text().splitlines() if "linking" in line
    )
    assert f"Linking table [{linking_line['n']}]" in trials and "trials.md" in linking_line["in_folder"]
    assert "file" not in linking_line and linking_line["name"] == "2027-02-02_linking.csv"
    assert any("2027-02-04_linking.csv is not used" in note for note in second.notes)
    kinds = [json.loads(line)["kind"] for line in (second.folder / "inputs.jsonl").read_text().splitlines()]
    assert kinds.count("trial record") == 1 and "linking table" in kinds


def test_a_trial_change_found_late_is_still_shown_once_and_never_twice(data: Path) -> None:
    # The page was saved on Monday night, before Tuesday's session; the job that compares records only ran later.
    monday_night = datetime(2027, 2, 1, 22, 30, tzinfo=UTC)
    a = page(data, "p1.json", monday_night)
    linking_table(data, "2027-02-01", "2027-02-01T12:00:00Z", "101,Aaa,Aaa Tx,yes,1,1,NCT00000001\n")
    changes = data / "trial-changes"
    changes.mkdir()
    (changes / "2027-02-03_changes.jsonl").write_text(json.dumps(change("NCT00000001", a, monday_night)) + "\n")
    first = run(data)
    assert (
        "NCT00000001" in (first.folder / "companies" / "101" / "trials.md").read_text()
    )  # saved before `since`, yet new
    thursday = datetime(2027, 2, 4, 8, tzinfo=UTC)
    second = run(data, session_day=date(2027, 2, 4), start_time=thursday, cutoff=thursday, since=CUTOFF)
    assert "No change" in (second.folder / "companies" / "101" / "trials.md").read_text()  # shown on Wednesday
    odd = change("NCT00000009", a, monday_night, new="line one\nline two [7] " + "x" * 400)
    assert "\n" not in prep.change_line(odd) and "[7]" not in prep.change_line(odd) and len(prep.change_line(odd)) < 500


def test_our_own_newest_report_of_an_earlier_day_is_copied_in(data: Path, tmp_path: Path) -> None:
    reports = data / "pilot" / "reports" / "101"
    reports.mkdir(parents=True)
    (reports / "2027-01-20.md").write_text("old report\n")
    (reports / "2027-02-01.md").write_text("newest earlier report\n")
    (reports / "2027-02-03.md").write_text("a report of today: from a round that broke off\n")
    (reports / "2027-02-05.md").write_text("a report from the future\n")
    (reports / "notes.md").write_text("not a report\n")
    outside = tmp_path / "elsewhere.md"
    outside.write_text("private\n")
    (data / "pilot" / "reports" / "102").mkdir()
    (data / "pilot" / "reports" / "102" / "2027-02-01.md").symlink_to(outside)
    done = run(data)
    copied = (done.folder / "companies" / "101" / "report.md").read_text()
    assert copied.endswith("\n\nnewest earlier report\n") and "session of 2027-02-01" in copied
    assert not (done.folder / "companies" / "102" / "report.md").exists()  # a link is not followed
    assert not (done.folder / "companies" / "103" / "report.md").exists()


def test_times_must_be_in_order_and_carry_their_zone_and_no_usable_universe_stops_everything(
    data: Path, monkeypatch, capsys
) -> None:
    early = datetime(2027, 1, 1, tzinfo=UTC)
    with pytest.raises(prep.PrepareError, match="no universe file may be used"):
        run(data, cutoff=early, since=early - timedelta(days=1))
    with pytest.raises(prep.PrepareError, match="must lie before"):
        run(data, since=CUTOFF)
    with pytest.raises(prep.PrepareError, match="without a time zone"):
        run(data, cutoff=datetime(2027, 2, 3, 8))
    monkeypatch.setenv("BOBBY_DATA_DIR", str(data))
    monkeypatch.setattr(cli, "utcnow", lambda: datetime(2027, 2, 3, 8, 0, 5, tzinfo=UTC))
    assert cli.main(["prepare", "--day", "2027-02-03", "--cutoff", "2027-02-03T08:00"]) == 1
    assert "must carry its time zone" in capsys.readouterr().out
    assert not (data / "pilot" / "sessions").exists() or not list((data / "pilot" / "sessions").iterdir())


def test_a_preparation_that_stops_half_way_leaves_no_session_folder_and_the_next_one_works(
    data: Path, monkeypatch
) -> None:
    real = prep.write_new

    def breaks(path: Path, text: str) -> None:
        if path.name == "session.json":
            raise OSError("disk full")
        real(path, text)

    monkeypatch.setattr(prep, "write_new", breaks)
    with pytest.raises(OSError):
        run(data)
    sessions = data / "pilot" / "sessions"
    assert not (sessions / "2027-02-03").exists() and len(list(sessions.glob(".2027-02-03.partial-*"))) == 1
    monkeypatch.setattr(prep, "write_new", real)
    done = run(data)
    assert (done.folder / "session.json").exists() and not list(sessions.glob(".*partial*"))


FORM4 = "<SEC-DOCUMENT>{acc}.txt : 20270202\n<SEC-HEADER>{acc}.hdr.sgml : 20270202\nACCESSION NUMBER:\t\t{acc}\nCONFORMED SUBMISSION TYPE:\t4\nFILED AS OF DATE:\t\t20270202\nREPORTING-OWNER:\n\tOWNER DATA:\n\t\tCOMPANY CONFORMED NAME:\t\t\t{owner}\nISSUER:\n\tCOMPANY DATA:\n\t\tCOMPANY CONFORMED NAME:\t\t\t{issuer}\n</SEC-HEADER>\n</SEC-DOCUMENT>\n"  # noqa: E501


def store_raw(data: Path, cik: int, accession: str, form: str, body: str, when: datetime) -> None:
    meta = {"cik": cik, "accession": accession, "form": form, "filed": "2027-02-02"}
    with Archive(data / "archive") as archive:
        archive.store(
            "sec-filings",
            f"filing-{accession}.txt",
            body.encode(),
            run="r",
            when=when,
            compress=True,
            info={"meta": meta},
        )


def test_a_filing_a_company_makes_as_a_holder_of_another_is_marked_and_is_no_news_about_itself(data: Path) -> None:
    evening = datetime(2027, 2, 2, 23, tzinfo=UTC)
    held = FORM4.format(acc="0000000102-27-000007", owner="Bbb Bio Inc", issuer=HIDDEN[2])
    own = FORM4.format(acc="0000000103-27-000008", owner="Jane Example", issuer="CCC PHARMA INC")
    store_raw(data, 102, "0000000102-27-000007", "4", held, evening)
    store_raw(data, 103, "0000000103-27-000008", "4", own, evening)
    done = run(data)
    text = next((done.folder / "companies" / "102" / "filings").iterdir()).read_text()
    assert "NOTE: this company filed this as a holder of ANOTHER company's shares" in text
    assert "Parties: reporting owner: Bbb Bio Inc; issuer: [a company that is not named]" in text  # and not by name
    assert "as a holder of another" in (done.folder / "companies" / "102" / "company.md").read_text()
    own_text = next((done.folder / "companies" / "103" / "filings").iterdir()).read_text()
    assert "NOTE:" not in own_text and "issuer: CCC PHARMA INC" in own_text
    stored = json.loads((done.folder / "session.json").read_text())
    assert stored["with_news"] == [101, 103]  # 101 by its price move; 102's holder filing sends it to no screening
    assert "102\n" in (done.folder / "screening" / "no-news.txt").read_text()
    assert done.counts["private_names_taken_out_of_texts"] == 1


def test_a_name_that_may_not_be_public_is_taken_out_of_every_text_the_agents_read(data: Path) -> None:
    main = f"<p>We compete with {HIDDEN[2]} (Nasdaq: {HIDDEN[1]}) and with Eee Hidden Devices.</p>"
    store_filing(
        data, 101, "0000000101-27-000001", "8-K", "2027-02-02", datetime(2027, 2, 2, 23, tzinfo=UTC), main=main
    )
    reports = data / "pilot" / "reports" / "101"
    reports.mkdir(parents=True)
    (reports / "2027-02-01.md").write_text("An earlier report that mentions Eee Hidden Devices Inc.\n")
    done = run(data)
    everything = b"".join(p.read_bytes() for p in done.folder.rglob("*") if p.is_file())
    assert b"Hidden" not in everything and b"EEE" not in everything
    assert b"We compete with [a company that is not named] ([a company that is not named]) and with" in everything
    assert done.counts["private_names_taken_out_of_texts"] == 4


def test_the_private_list_only_grows_and_keeps_names_added_by_hand(data: Path, tmp_path: Path) -> None:
    private = data / "pilot" / "private-names.tsv"
    private.parent.mkdir(parents=True)
    private.write_text(
        f"# by hand\n{HIDDEN[0]}\t{HIDDEN[1]}\told name\tEeeDevice|Hidden Dx\n777\tOLD\tWas Hidden Once Inc\n"
    )
    done = run(data)
    lines = [line.split("\t") for line in private.read_text().splitlines() if not line.startswith("#")]
    assert lines == [
        [str(HIDDEN[0]), HIDDEN[1], HIDDEN[2], "EeeDevice|Hidden Dx"],
        ["777", "OLD", "Was Hidden Once Inc"],
    ]
    assert done.counts["on_the_private_list"] == 2 and not any("marks no company" in n for n in done.notes)
    # A universe file that marks nobody is suspicious: say so.
    path = data / "universe" / "2027-02-01_universe.csv"
    path.write_text(path.read_text().replace("xbi only", "own code"))
    again = prep.prepare(
        data_dir=data, mode_root=tmp_path / "other", session_day=WED, start_time=CUTOFF, cutoff=CUTOFF, since=SINCE
    )
    assert any("marks no company as in through the XBI fund only" in n for n in again.notes)
    # On the first root the company stays hidden even so: it was on the list.
    third = run(
        data,
        session_day=date(2027, 2, 4),
        start_time=CUTOFF + timedelta(days=1),
        cutoff=CUTOFF + timedelta(days=1),
        since=CUTOFF,
    )
    assert HIDDEN[0] not in third.companies and not (third.folder / "companies" / str(HIDDEN[0])).exists()


def test_a_move_of_the_share_is_measured_against_the_prices_the_last_session_saw(tmp_path: Path) -> None:
    # As in real life: the final copy of a day's prices is stored two mornings later.
    data = tmp_path / "data"
    universe_file(data)
    store_splits(data / "prices", [])
    flat = {"AAA": (10.0, 10.0), "BBB": (20.0, 20.0), "CCC": (5.0, 5.0)}
    two_later = {
        date(2027, 1, 28): datetime(2027, 2, 1, 6, tzinfo=UTC),
        date(2027, 1, 29): datetime(2027, 2, 2, 6, tzinfo=UTC),
        MON: datetime(2027, 2, 3, 6, tzinfo=UTC),
    }
    store_day(data / "prices", date(2027, 1, 28), flat, when=two_later[date(2027, 1, 28)])
    store_day(data / "prices", date(2027, 1, 29), flat, when=two_later[date(2027, 1, 29)])
    store_day(data / "prices", MON, {**flat, "AAA": (10.0, 13.0)}, when=two_later[MON])
    done = run(data)  # Wednesday 08:00; Tuesday's session (08:00) had seen the prices of Friday the 29th
    numbers = (done.folder / "companies" / "101" / "numbers.md").read_text()
    assert (
        "as of the close of 2027-02-01" in numbers
        and "Change since the prices the last session saw (2027-01-29): +30.0%" in numbers
    )
    assert json.loads((done.folder / "session.json").read_text())["with_news"] == [101]
    # A session that sees no newer price day than the one before it reports no move at all.
    same = run(data, session_day=date(2027, 2, 4), start_time=CUTOFF, cutoff=CUTOFF + timedelta(hours=1), since=CUTOFF)
    assert "Change since" not in (same.folder / "companies" / "101" / "numbers.md").read_text()
    assert json.loads((same.folder / "session.json").read_text())["with_news"] == []


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
    assert chosen[4][1] == "a catalyst within 60 days (our nearest open forecast for it is dated 2027-02-10)"
    assert chosen[6][1] == "rotation: no report yet"
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
    with open(tmp_path / "tasks" / "index.jsonl", "a") as fh:  # a second line for a task: the list was tampered with
        fh.write(json.dumps({**again.__dict__, "sha256": "0" * 64}) + "\n")
    with pytest.raises(tasks.TaskError, match="twice"):
        tasks.load(tmp_path)
    for bad in ("../escape", "Has Capitals", "", "a/b"):
        with pytest.raises(tasks.TaskError):
            tasks.write(tmp_path, bad, "bobby-x", "text")
    assert iso(CUTOFF) == "2027-02-03T08:00:00Z"


def test_an_earlier_report_gets_todays_numbers_for_the_filings_of_its_day(data: Path) -> None:
    # Pilot, 2026-11-23 to 27: a report cited [2] of its own day, while today's [2] was another company's filing,
    # and the filings behind the report were in no list of today. Now they are, as earlier filings, with a note.
    monday = datetime(2027, 2, 1, 6, tzinfo=UTC)
    store_filing(data, 101, "0000000101-27-000007", "8-K", "2027-01-29", monday, main="<p>Topline news.</p>")
    store_filing(data, 101, "0000000101-27-000008", "4", "2027-01-29", monday, main="<p>A small sale.</p>")
    store_filing(data, 101, "0000000101-26-000001", "10-Q", "2026-08-01", monday, main="<p>Long ago.</p>")
    shown_earlier(
        data,
        "2027-02-01",
        [
            {"n": 1, "kind": "universe"},
            {"n": 2, "kind": "sec filing", "cik": 101, "accession": "0000000101-27-000007"},
            {"n": 3, "kind": "sec filing", "cik": 101, "accession": "0000000101-27-000008"},
            {"n": 4, "kind": "sec filing", "cik": 101, "accession": "0000000101-26-000001"},
            {"n": 5, "kind": "sec filing", "cik": 101, "accession": "0000000101-27-000099"},  # not in the archive
            {"n": 6, "kind": "sec filing", "cik": 102, "accession": "0000000102-27-000001"},
        ],
    )
    reports = data / "pilot" / "reports" / "101"
    reports.mkdir(parents=True)
    (reports / "2027-02-01.md").write_text("The drug worked [2].\n")
    done = run(data, held={101})
    folder = done.folder / "companies" / "101"
    lines = [json.loads(line) for line in (done.folder / "inputs.jsonl").read_text().splitlines()]
    today = {line["accession"]: line["n"] for line in lines if line["kind"] == "sec filing"}
    assert all(line.get("earlier") for line in lines if line["kind"] == "sec filing")
    # Cited by the report: in, though filed more than 90 days ago. The 8-K goes before the insider trade.
    assert set(today) == {"0000000101-27-000007", "0000000101-27-000008", "0000000101-26-000001"}
    assert today["0000000101-27-000007"] < today["0000000101-27-000008"]
    report = (folder / "report.md").read_text()
    n7, n8, nq = (today[a] for a in ("0000000101-27-000007", "0000000101-27-000008", "0000000101-26-000001"))
    assert f"[2] is today [{n7}], [3] is today [{n8}], [4] is today [{nq}]" in report
    assert "Not in today's list: [5]." in report and report.endswith("The drug worked [2].\n")
    company = (folder / "company.md").read_text()
    new_part, earlier_part = company.split("## Earlier filings")
    assert f"- [{n7}] 8-K filed 2027-01-29" in earlier_part and "8-K" not in new_part
    assert "Topline news." in (folder / "filings" / f"{n7:04d}-8-K.txt").read_text()
    assert done.counts["filings"] == 0 and done.counts["earlier_filings"] == 3
    batch = (done.folder / "screening" / "batch-01.md").read_text()  # 101 is news for its price move only
    assert "the share moved" in batch and "8-K" not in batch and "10-Q" not in batch  # earlier filings are no news


def test_the_universe_line_of_a_company_without_prices_or_the_xbi_fund(tmp_path: Path) -> None:
    row = {
        "exchanges": "Nasdaq",
        "sic": "2834",
        "door": "own code + xbi",
        "in_xbi": "yes",
        "filer_type": "domestic",
        "shares": "78545051",
        "shares_as_of": "2026-10-28",
        "shares_source": "cover page",
        "last_close": "27.96",
        "market_value": "2196119626",
        "former_names": "OLD NAME INC",
    }
    line = prep.universe_line(row, 1)
    assert line.startswith("- Universe list [1]: exchange: Nasdaq; industry code (SIC): 2834")
    assert "shares outstanding: 78,545,051 as of 2026-10-28 (from the SEC, cover page)" in line
    assert "former names: OLD NAME INC" in line
    for absent in ("xbi", "27.96", "2196119626", "own code"):
        assert absent not in line.lower()


def test_no_market_value_of_today_after_a_split_since_the_share_count(tmp_path: Path) -> None:
    # Review of 2026-11-27: the shares on the universe list times today's price is wrong after a split.
    data = tmp_path / "data"
    universe_file(data)
    store_splits(data / "prices", [("AAA", date(2027, 2, 1), 1.0, 10.0)])
    prices = {"AAA": (10.0, 10.0), "BBB": (20.0, 20.0), "CCC": (5.0, 5.0), "EEE": (3.0, 3.0)}
    for day in (date(2027, 1, 29), MON, TUE):
        store_day(data / "prices", day, prices)
    numbers = (run(data).folder / "companies" / "101" / "numbers.md").read_text()
    assert "Market value now: not worked out: the shares were split since the share count" in numbers

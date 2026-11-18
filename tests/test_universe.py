"""Tests with small made-up files in the real layouts. No real data: every company and trial here is invented."""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook

from bobby_hedgefund.archive.sec import SEC_SOURCE, TICKERS_NAME, submissions_name
from bobby_hedgefund.archive.store import Archive
from bobby_hedgefund.universe import candidates, cli, read_nasdaq, read_sec, read_trials, read_xbi
from bobby_hedgefund.universe.inputs import InputError, Inputs
from bobby_hedgefund.universe.output import OutputError, csv_text, free_label, plain_cell, write_new

# cik, name, ticker, exchange, industry code, forms (newest first), former names
COMPANIES = [
    (101, "Alpha Therapeutics, Inc.", "ALFA", "Nasdaq", "2834", ["8-K", "10-Q", "10-K"], ["Alpha Old Name Corp"]),
    (102, "Beta Biologics plc", "BETA", "Nasdaq", "2836", ["6-K", "20-F"], []),  # foreign filer
    (103, "Gamma Research Corp", "GAMA", "NYSE", "8731", ["10-K"], []),
    (104, "Delta Tools Inc", "DELT", "NYSE", "3559", ["10-K"], []),  # other industry, but held by the fund
    (105, "Epsilon Bank", "EPSI", "NYSE", "6021", ["10-K"], []),  # not a candidate
    (106, "Zeta Pharma Inc", "ZETA-A", "Nasdaq", "2834", ["S-1"], []),  # too young for a yearly report
    (107, "Eta Pharma Inc", "ETAA", "OTC", "2834", ["10-K"], []),  # no exchange listing: not fetched, not in
    (108, "Theta Diagnostics Inc", "THET", "Nasdaq", "2835", ["F-1", "S-1"], []),  # mixed signals: unknown
]
HOLDINGS = [("ALPHA THERAPEUTICS INC", "ALFA"), ("DELTA TOOLS INC", "DELT"), ("ZETA PHARMA A", "ZETA.A")]


def tickers_body(rows=COMPANIES) -> bytes:
    data = [[cik, name, ticker, exchange] for cik, name, ticker, exchange, *_ in rows]
    return json.dumps({"fields": ["cik", "name", "ticker", "exchange"], "data": data}).encode()


def filing_list_body(cik: int, name: str, sic: str, forms: list[str], former: list[str]) -> bytes:
    doc = {
        "cik": f"{cik:010d}",
        "name": name,
        "sic": sic,
        "sicDescription": f"Industry {sic}",
        "entityType": "operating",
        "tickers": [],
        "exchanges": [],
        "formerNames": [
            {"name": n, "from": "2019-01-01T00:00:00.000Z", "to": "2020-01-01T00:00:00.000Z"} for n in former
        ],
        "filings": {"recent": {"form": forms}, "files": []},
    }
    return json.dumps(doc).encode()


def holdings_body(rows=HOLDINGS, header=("Name", "Ticker", "Identifier", "Weight")) -> bytes:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["Fund Name:", "Made-up Biotech Fund"])
    sheet.append(["Holdings:", "As of 17-Nov-2026"])
    sheet.append([])
    sheet.append(list(header))
    for name, ticker in rows:
        sheet.append([name, ticker, "000000000", 1.5])
    sheet.append(["US DOLLAR", "-", "", 0.1])  # cash: no ticker
    sheet.append([])
    sheet.append(["A closing remark of the fund company, without a ticker"])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


NASDAQ = b"Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
NASDAQ += b"ALFA|Alpha Therapeutics - Common Stock|Q|N|N|100|N|N\nBETA|Beta ADS|Q|N|N|100|N|N\n"
NASDAQ += (
    b"ZETA.A|Zeta Class A|Q|N|N|100|N|N\nZTEST|A test issue|Q|Y|N|100|N|N\nFile Creation Time: 1117202617:01|||||||\n"
)
OTHER = b"ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
OTHER += b"GAMA|Gamma Research|N|GAMA|N|100|N|GAMA\nDELT|Delta Tools|N|DELT|N|100|N|DELT\n"
OTHER += b"File Creation Time: 1117202617:01||||||\n"


def study(nct: str, lead: tuple[str, str], *collaborators: tuple[str, str]) -> dict:
    module: dict = {"leadSponsor": {"name": lead[0], "class": lead[1]}}
    if collaborators:
        module["collaborators"] = [{"name": n, "class": c} for n, c in collaborators]
    return {"protocolSection": {"identificationModule": {"nctId": nct}, "sponsorCollaboratorsModule": module}}


def page(*studies: dict) -> bytes:
    return json.dumps({"studies": list(studies)}).encode()


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    """A small archive: one complete batch of SEC files, a holdings file, the symbol lists and trial pages."""
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "data" / "archive"
    with Archive(root) as archive:
        meta = {"batch": "b1"}
        archive.store(
            SEC_SOURCE, TICKERS_NAME, tickers_body(), run="b1", compress=True, dedup=False, info={"meta": meta}
        )
        for cik, name, _ticker, exchange, sic, forms, former in COMPANIES:
            if exchange != "OTC":
                body = filing_list_body(cik, name, sic, forms, former)
                info = {"meta": {"batch": "b1", "cik": cik}}
                archive.store(SEC_SOURCE, submissions_name(cik), body, run="b1", compress=True, info=info)
        archive.record_run(SEC_SOURCE, "b1", "ok", meta={"batch": "b1", "complete": True})
        archive.store("ssga-xbi", "holdings-xbi.xlsx", holdings_body(), run="r")
        archive.store("nasdaq-symdir", "nasdaqlisted.txt", NASDAQ, run="r", compress=True)
        archive.store("nasdaq-symdir", "otherlisted.txt", OTHER, run="r", compress=True)
        base = page(
            study("NCT001", ("Alpha Therapeutics, Inc.", "INDUSTRY"), ("A University", "OTHER")),
            study("NCT002", ("A University", "OTHER"), ("Alpha Therapeutics", "INDUSTRY"), ("Someone", "INDIV")),
            study("NCT003", ("Old Sponsor Ltd", "INDUSTRY")),
        )
        archive.store("ctgov-baseline", "p0001.json", base, run="r", compress=True, dedup=False)
        newer = page(
            study("NCT003", ("New Sponsor Ltd", "INDUSTRY")),  # the trial changed hands: the old name is gone
            study("NCT004", ("Unclear Org", "UNKNOWN"), ("Alpha Therapeutics, Inc.", "INDUSTRY")),
        )
        archive.store("ctgov-updates", "p0001.json", newer, run="r", compress=True, dedup=False)
        archive.store("ctgov-version", "version.json", b'{"dataTimestamp": "x"}', run="r")
    return root


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


# -- readers -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("forms", "expected"),
    [
        (["8-K", "10-Q", "10-K"], "domestic"),
        (["6-K", "20-F", "10-K"], "foreign"),  # the newest yearly report decides: it switched to foreign
        (["10-K/A", "20-F"], "domestic"),
        (["40-F"], "foreign"),
        (["S-1", "8-K"], "domestic"),
        (["F-1", "6-K"], "foreign"),
        (["F-1", "S-1"], "unknown"),
        ([], "unknown"),
    ],
)
def test_filer_type(forms: list[str], expected: str) -> None:
    assert read_sec.filer_type(forms) == expected


def test_company_reads_the_fields_the_table_needs() -> None:
    c = read_sec.company(filing_list_body(101, " Alpha Therapeutics, Inc. ", "2834", ["10-K"], ["Alpha Old Name Corp"]))
    assert (c.cik, c.name, c.sic, c.former_names) == (101, "Alpha Therapeutics, Inc.", "2834", ("Alpha Old Name Corp",))
    for bad in (b"<html>", b"{}", b'{"cik": "x", "filings": {"recent": {}}}'):
        with pytest.raises(read_sec.ReadError):
            read_sec.company(bad)


def test_holdings_keeps_shares_and_drops_cash_and_remarks() -> None:
    found = read_xbi.holdings(holdings_body())
    assert [(h.name, h.ticker) for h in found] == HOLDINGS
    with pytest.raises(read_sec.ReadError, match="header"):
        read_xbi.holdings(holdings_body(header=("Company", "Symbol", "x", "y")))
    with pytest.raises(read_sec.ReadError, match="no holdings"):
        read_xbi.holdings(holdings_body(rows=[]))
    with pytest.raises(read_sec.ReadError, match="opened"):
        read_xbi.holdings(b"not a spreadsheet")


def test_symbols_skip_test_issues_and_the_closing_line() -> None:
    assert read_nasdaq.symbols("nasdaqlisted.txt", NASDAQ) == {"ALFA", "BETA", "ZETA.A"}
    assert read_nasdaq.symbols("otherlisted.txt", OTHER) == {"GAMA", "DELT"}
    with pytest.raises(read_sec.ReadError):
        read_nasdaq.symbols("nasdaqlisted.txt", b"<html>blocked</html>")
    assert read_nasdaq.dashed("ZETA.A") == "ZETA-A" and read_nasdaq.stripped("ZETA-A") == "ZETAA"


def test_sponsor_names_newer_copy_replaces_older_and_only_company_like_names_are_kept() -> None:
    collector = read_trials.SponsorCollector()
    collector.add_page(page(study("NCT1", ("Acme Inc", "INDUSTRY"), ("A Hospital", "OTHER"), ("Nameless", ""))))
    collector.add_page(page(study("NCT1", ("Acme Inc.", "INDUSTRY")), study("NCT2", ("Acme Inc.", "OTHER"))))
    names = {s.name: s for s in collector.names()}
    assert set(names) == {"Acme Inc."}  # "Acme Inc", the hospital and the nameless one went with the old copy
    assert names["Acme Inc."].trials == {"NCT1", "NCT2"} and names["Acme Inc."].classes == {"INDUSTRY", "OTHER"}
    with pytest.raises(read_sec.ReadError):
        collector.add_page(b'{"studies": [{"protocolSection": {}}]}')
    with pytest.raises(read_sec.ReadError):
        collector.add_page(b'{"nothing": 1}')


# -- inputs --------------------------------------------------------------------------------------------------------


def test_inputs_refuse_a_damaged_file_and_remember_what_was_read(root: Path) -> None:
    inputs = Inputs(root)
    rec = inputs.newest("nasdaq-symdir", "otherlisted.txt")
    assert inputs.read(rec) == OTHER and list(inputs.used) == [rec["path"]]
    assert inputs.listing() == f"{rec['sha256']}  {rec['path']}\n"
    target = root / rec["path"]
    target.chmod(0o600)
    target.write_bytes(b"damaged")
    with pytest.raises(InputError):
        Inputs(root).read(rec)
    with pytest.raises(InputError):
        Inputs(root).read({**rec, "path": "../outside"})
    with pytest.raises(InputError, match="holds no file"):
        inputs.newest("nasdaq-symdir", "nothing.txt")


def test_inputs_read_while_a_download_job_holds_the_lock(root: Path) -> None:
    with Archive(root):  # a running job
        assert Inputs(root).read(Inputs(root).newest("ssga-xbi", "holdings-xbi.xlsx"))


# -- candidate list ------------------------------------------------------------------------------------------------


def test_candidates_doors_filer_types_and_counts(root: Path) -> None:
    result = candidates.build(Inputs(root))
    by_cik = {c.cik: c for c in result.candidates}
    assert sorted(by_cik) == [101, 102, 103, 104, 106, 108]  # the bank and the unlisted company are not in
    assert by_cik[101].door == "own code + xbi" and by_cik[101].former_names == ("Alpha Old Name Corp",)
    assert by_cik[103].door == "own code" and not by_cik[103].in_xbi
    assert by_cik[104].door == "xbi only" and by_cik[104].sic == "3559"
    assert by_cik[106].door == "own code + xbi"  # the fund writes ZETA.A, the SEC writes ZETA-A
    assert by_cik[102].filer_type == "foreign" and not by_cik[102].in_version_1
    assert by_cik[108].filer_type == "unknown" and by_cik[108].in_version_1
    assert by_cik[101].ticker_check == "ok" and by_cik[106].ticker_check == "ok"
    assert by_cik[108].ticker_check == "not in the Nasdaq lists: THET"
    assert by_cik[101].name_in_xbi_file == "ALPHA THERAPEUTICS INC" and by_cik[103].name_in_xbi_file == ""
    assert result.xbi_unmatched == []
    assert result.counts == {
        "sec_batch": "b1",
        "sec_batch_complete": True,
        "listed_companies": 7,
        "without_filing_list": 0,
        "candidates_with_filing_list_from_older_batch": 0,
        "candidates": 6,
        "door_own_code": 3,
        "door_own_code_and_xbi": 2,
        "door_xbi_only": 1,
        "foreign_filers_left_out": 1,
        "filer_type_unknown": 1,
        "in_version_1": 5,
        "in_version_1_xbi_only": 1,
        "ticker_not_in_nasdaq_lists": 1,
        "xbi_holdings": 3,
        "xbi_matched": 3,
        "xbi_unmatched": 0,
    }


def test_holdings_that_cannot_be_linked_are_listed_not_dropped(root: Path) -> None:
    rows = [*HOLDINGS, ("ETA PHARMA INC", "ETAA"), ("A COMPANY THE SEC FILE LACKS", "NOPE")]
    with Archive(root) as archive:
        archive.store("ssga-xbi", "holdings-xbi.xlsx", holdings_body(rows), run="r2")
    result = candidates.build(Inputs(root))
    assert result.xbi_unmatched == [
        ("ETA PHARMA INC", "ETAA", "no exchange listing in the SEC's ticker file"),
        ("A COMPANY THE SEC FILE LACKS", "NOPE", "ticker not in the SEC's ticker file"),
    ]
    assert result.counts["xbi_holdings"] == 5 and result.counts["xbi_matched"] == 3


def index_of(*pairs: tuple[str, int]) -> candidates.TickerIndex:
    index = candidates.TickerIndex()
    for ticker, cik in pairs:
        index.add(ticker, cik)
    return index


def test_a_look_alike_ticker_never_takes_another_companys_place() -> None:
    # Company 1 has the share class AB-C, company 2 the plain ticker ABC. Whatever the order in the SEC's file,
    # a holding written ABC is company 2 and a holding written AB.C is company 1.
    for index in (index_of(("AB-C", 1), ("ABC", 2)), index_of(("ABC", 2), ("AB-C", 1))):
        assert index.find("ABC") == (2, "")
        assert index.find("AB.C") == (1, "") and index.find("AB-C") == (1, "")
    # Without the plain ticker in the file, the form without the mark is a last resort, and only when it is unique.
    assert index_of(("AB-C", 1)).find("ABC") == (1, "")
    cik, why = index_of(("AB-C", 1), ("A-BC", 3)).find("ABC")
    assert cik is None and "more than one company" in why
    assert index_of(("AB-C", 1)).find("XYZ") == (None, "ticker not in the SEC's ticker file")
    # One company with two share classes stays one company.
    assert index_of(("AB-C", 1), ("AB-D", 1)).find("AB.D") == (1, "")


def test_a_holding_whose_ticker_fits_two_companies_is_listed_as_unmatched(root: Path) -> None:
    extra = [
        *COMPANIES,
        (201, "First Lookalike Inc", "LO-OK", "Nasdaq", "2834", ["10-K"], []),
        (202, "Second Lookalike Inc", "L-OOK", "Nasdaq", "2834", ["10-K"], []),
    ]
    with Archive(root) as archive:
        info = {"meta": {"batch": "b2"}}
        archive.store(SEC_SOURCE, TICKERS_NAME, tickers_body(extra), run="b2", compress=True, dedup=False, info=info)
        archive.record_run(SEC_SOURCE, "b2", "ok", meta={"batch": "b2", "complete": True})
        archive.store("ssga-xbi", "holdings-xbi.xlsx", holdings_body([*HOLDINGS, ("LOOKALIKE", "LOOK")]), run="r2")
    result = candidates.build(Inputs(root))
    assert result.xbi_unmatched == [("LOOKALIKE", "LOOK", "ticker fits more than one company in the SEC's ticker file")]
    assert result.counts["xbi_matched"] == 3


def test_the_ticker_check_accepts_the_same_ticker_only() -> None:
    assert candidates._ticker_check(("AB-C",), {"AB-C"}) == "ok"
    assert candidates._ticker_check(("ABC",), {"AB-C"}) == "not in the Nasdaq lists: ABC"


def test_an_incomplete_batch_is_refused_unless_asked(root: Path) -> None:
    with Archive(root) as archive:
        info = {"meta": {"batch": "b2"}}
        archive.store(SEC_SOURCE, TICKERS_NAME, tickers_body(), run="b2", compress=True, dedup=False, info=info)
    with pytest.raises(InputError, match="not complete"):
        candidates.build(Inputs(root))
    result = candidates.build(Inputs(root), allow_partial=True)  # the filing lists of the older batch are used
    assert result.counts["candidates"] == 6 and result.counts["sec_batch_complete"] is False
    assert result.counts["candidates_with_filing_list_from_older_batch"] == 6  # and that is said


def test_a_listed_company_without_a_filing_list_is_counted(root: Path) -> None:
    extra = [*COMPANIES, (109, "Iota Pharma Inc", "IOTA", "Nasdaq", "2834", ["10-K"], [])]
    with Archive(root) as archive:
        info = {"meta": {"batch": "b2"}}
        archive.store(SEC_SOURCE, TICKERS_NAME, tickers_body(extra), run="b2", compress=True, dedup=False, info=info)
        archive.record_run(SEC_SOURCE, "b2", "ok", meta={"batch": "b2", "complete": True})
    counts = candidates.build(Inputs(root)).counts
    assert counts["listed_companies"] == 8 and counts["without_filing_list"] == 1 and counts["candidates"] == 6


def test_a_filing_list_from_an_older_batch_is_counted(root: Path) -> None:
    with Archive(root) as archive:
        info = {"meta": {"batch": "b2"}}
        archive.store(SEC_SOURCE, TICKERS_NAME, tickers_body(), run="b2", compress=True, dedup=False, info=info)
        for cik, name, _ticker, exchange, sic, forms, former in COMPANIES:
            if exchange != "OTC" and cik != 103:  # the new batch could not store company 103's list
                body = filing_list_body(cik, name, sic, forms, former)
                archive.store(
                    SEC_SOURCE,
                    submissions_name(cik),
                    body,
                    run="b2",
                    compress=True,
                    info={"meta": {"batch": "b2", "cik": cik}},
                )
        archive.record_run(SEC_SOURCE, "b2", "ok", meta={"batch": "b2", "complete": True})
    counts = candidates.build(Inputs(root)).counts
    assert counts["candidates"] == 6 and counts["candidates_with_filing_list_from_older_batch"] == 1


# -- command -------------------------------------------------------------------------------------------------------


def test_candidates_command_writes_dated_private_files_and_never_overwrites(root: Path, capsys) -> None:
    assert cli.main(["candidates"]) == 0
    folder = root.parent / "universe"
    label = date.today().isoformat()
    rows = read_csv(folder / f"{label}_candidates.csv")
    assert [r["cik"] for r in rows] == ["101", "102", "103", "104", "106", "108"]
    assert rows[0]["tickers"] == "ALFA" and rows[0]["in_xbi"] == "yes" and rows[1]["in_version_1"] == "no"
    inputs_text = (folder / f"{label}_inputs.txt").read_text()
    assert "# door_xbi_only: 1" in inputs_text and "raw/ssga-xbi/" in inputs_text and "raw/sec/" in inputs_text
    assert not (folder / f"{label}_xbi-unmatched.csv").exists()
    assert "door_xbi_only" in capsys.readouterr().out
    first = (folder / f"{label}_candidates.csv").read_bytes()
    assert cli.main(["candidates"]) == 0  # a second run on the same day gets its own files
    assert (folder / f"{label}_candidates.csv").read_bytes() == first
    assert (folder / f"{label}-2_candidates.csv").exists() and (folder / f"{label}-2_inputs.txt").exists()
    for path in folder.iterdir():
        assert path.stat().st_mode & 0o077 == 0  # nobody but the owner can read the private results
    assert folder.stat().st_mode & 0o077 == 0


def test_sponsor_names_command(root: Path) -> None:
    assert cli.main(["sponsor-names"]) == 0
    folder = root.parent / "linking"
    label = date.today().isoformat()
    rows = {r["sponsor_name"]: r for r in read_csv(folder / f"{label}_sponsor-names.csv")}
    assert set(rows) == {"Alpha Therapeutics, Inc.", "Alpha Therapeutics", "New Sponsor Ltd", "Unclear Org"}
    alpha = rows["Alpha Therapeutics, Inc."]
    assert (alpha["trials"], alpha["as_lead"], alpha["as_collaborator"]) == ("2", "1", "1")
    assert alpha["example_trial"] == "NCT004" and rows["Unclear Org"]["classes"] == "UNKNOWN"
    listing = (folder / f"{label}_sponsor-names-inputs.txt").read_text()
    assert "# trials: 4" in listing and "ctgov-baseline" in listing and "ctgov-updates" in listing
    assert "ctgov-version" not in listing


def test_the_copy_of_a_trial_that_was_saved_last_counts_whatever_its_source(root: Path) -> None:
    with Archive(root) as archive:  # a second baseline, saved after the update page of the fixture
        late = page(study("NCT003", ("Newest Sponsor Ltd", "INDUSTRY")))
        archive.store("ctgov-baseline", "p0001.json", late, run="r3", compress=True, dedup=False)
    assert cli.main(["sponsor-names"]) == 0
    label = date.today().isoformat()
    names = {r["sponsor_name"] for r in read_csv(root.parent / "linking" / f"{label}_sponsor-names.csv")}
    assert "Newest Sponsor Ltd" in names and "New Sponsor Ltd" not in names and "Old Sponsor Ltd" not in names


def test_text_a_spreadsheet_would_run_as_a_formula_is_marked_as_plain_text() -> None:
    text = csv_text(("name", "n"), [("=HYPERLINK(1)", 5), ("+plus", -3), ("Plain Inc", 1), ("@x", 0)])
    cells = [row[0] for row in csv.reader(text.splitlines())][1:]
    assert cells == ["'=HYPERLINK(1)", "'+plus", "Plain Inc", "'@x"]
    assert [plain_cell(c) for c in cells] == ["=HYPERLINK(1)", "+plus", "Plain Inc", "@x"]
    assert plain_cell("'s-Hertogenbosch BV") == "'s-Hertogenbosch BV"  # a real apostrophe is left alone
    assert ",-3" in text  # numbers are not touched


def test_commands_report_a_missing_archive_instead_of_crashing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "empty"))
    assert cli.main(["candidates"]) == 1 and cli.main(["sponsor-names"]) == 1
    assert capsys.readouterr().out.count("NOT DONE") == 2
    assert not (tmp_path / "empty" / "universe").exists()


# -- output --------------------------------------------------------------------------------------------------------


def test_write_new_refuses_to_replace_and_leaves_no_half_file(tmp_path: Path) -> None:
    target = tmp_path / "out" / "2026-11-18_x.csv"
    write_new(target, "first\n")
    with pytest.raises(OutputError):
        write_new(target, "second\n")
    assert target.read_text() == "first\n" and [p.name for p in target.parent.iterdir()] == [target.name]
    assert free_label(date(2026, 11, 18), [(target.parent, "x.csv"), (target.parent, "y.txt")]) == "2026-11-18-2"
    assert free_label(date(2026, 11, 19), [(target.parent, "x.csv")]) == "2026-11-19"

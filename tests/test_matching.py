"""Name matching, the review sheet and the owner's decisions. Every company and sponsor name here is invented."""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from pathlib import Path

import pytest
from openpyxl import load_workbook
from test_filter import world  # noqa: F401
from test_universe import root  # noqa: F401

from bobby_hedgefund.universe import cli, decisions, match, names, review
from bobby_hedgefund.universe.decisions import Decision, DecisionError
from bobby_hedgefund.universe.read_trials import SponsorName


def sponsor(name: str, *trials: str) -> SponsorName:
    return SponsorName(name, {"INDUSTRY"}, set(trials or ("NCT1",)), set())


@pytest.mark.parametrize(
    ("written", "cleaned", "core"),
    [
        ("Alpha Therapeutics, Inc.", "alpha therapeutics", "alpha"),
        ("ALPHA THERAPEUTICS INC", "alpha therapeutics", "alpha"),
        ("Société Générale Pharma S.A.", "societe generale pharma", "societe generale"),
        ("Smith & Jones Holdings Ltd", "smith and jones", "smith jones"),
        ("Kappa Co., Ltd.", "kappa", "kappa"),
        ("Lambda N.V.", "lambda", "lambda"),
        ("NU PHARMACEUTICALS INC /DE/", "nu pharmaceuticals", "nu"),
        ("Xi Therapeutics Inc / MA", "xi therapeutics", "xi"),
        ("OMICRON CORP /NEW", "omicron", "omicron"),
        ("Pi Bio Co., Limited/ADR", "pi bio", "pi"),
        ("Rho CORP/", "rho", "rho"),
        ("Sigma/Tau Research", "sigma tau research", "sigma tau research"),  # a slash inside a name stays
        ("Mu L.L.C.", "mu", "mu"),
        ("Inc", "inc", "inc"),  # a name that is only a legal ending keeps it
        ("Bio-Pharma Sciences", "bio pharma sciences", ""),  # nothing tells this company from another
        ("O'Brien Bio", "obrien bio", "obrien"),
    ],
)
def test_cleaning_names(written: str, cleaned: str, core: str) -> None:
    assert names.clean(written) == cleaned and names.core(cleaned) == core


def kinds(company: match.Company, *sponsors: SponsorName) -> dict[str, str]:
    return {s.sponsor.name: s.kind for s in match.suggest([company], list(sponsors))}


def test_the_four_kinds_of_suggestion_and_what_is_not_suggested() -> None:
    company = match.Company(1, "Alpha Therapeutics, Inc.", "ALFA", ("Omega Old Name Corp",))
    found = kinds(
        company,
        sponsor("Alpha Therapeutics"),
        sponsor("Alpha Pharma Ltd"),
        sponsor("Alpha Tx"),
        sponsor("Alpha Therapeutics Australia Pty Ltd"),
        sponsor("Alpha Theraputics"),  # a spelling variant
        sponsor("Omega Old Name"),  # the former name
        sponsor("Alphabet Health"),  # another company whose name starts with the same letters
        sponsor("Alpho Therapeutics"),  # one letter off in a short name: more often another company
        sponsor("Aloha Therapeutics"),
        sponsor("Delta Therapeutics"),  # alike as a whole only through the long shared word
        sponsor("Beta Therapeutics"),  # the same sector word only
        sponsor("Alpha"),
        sponsor("Kappa Bio, Inc., a wholly owned subsidiary of Alpha Therapeutics"),
        sponsor("Not Alpha Therapeuticsville"),  # the name must stand as whole words
    )
    assert found == {
        "Alpha Therapeutics": "strong",
        "Omega Old Name": "strong",
        "Alpha Pharma Ltd": "core",
        "Alpha Tx": "core",
        "Alpha": "core",
        "Alpha Therapeutics Australia Pty Ltd": "starts",
        "Kappa Bio, Inc., a wholly owned subsidiary of Alpha Therapeutics": "contains",
        "Alpha Theraputics": "similar",
    }


def test_a_short_or_empty_core_suggests_nothing_by_itself_and_order_is_strongest_then_most_trials() -> None:
    assert kinds(match.Company(1, "AB Bio Inc", "AB"), sponsor("AB Pharma"), sponsor("Bio Sciences")) == {}
    generic = match.Company(2, "Omega Tracks Inc", "OMT", ("Biopharma Company, Inc.",))
    got = kinds(generic, sponsor("Array Biopharma"), sponsor("Biopharma Company"), sponsor("Biopharma Company Europe"))
    assert got == {"Biopharma Company": "strong"}  # a former name of sector words only: identical or nothing
    company = match.Company(1, "Gamma Research Corp", "GAMA")
    got = match.suggest(
        [company],
        [
            sponsor("Gamma Research LLC", "N1"),
            sponsor("Gamma Research Europe", "N1", "N2", "N3"),
            sponsor("Gamma Research", "N1", "N2"),
        ],
    )
    assert [(s.sponsor.name, s.kind) for s in got] == [
        ("Gamma Research", "strong"),
        ("Gamma Research LLC", "strong"),
        ("Gamma Research Europe", "starts"),
    ]
    assert got[0].matched_on == "Gamma Research Corp" and not got[0].is_former_name


def test_strong_and_core_are_never_cut_and_what_is_left_out_is_counted(monkeypatch) -> None:
    monkeypatch.setattr(match, "MAX_PER_COMPANY", 2)
    company = match.Company(7, "Kappa Research", "KAPA")
    sponsors = [sponsor(f"Kappa Research Site {n}", *[f"N{i}" for i in range(n)]) for n in range(1, 6)]
    sponsors += [sponsor("Kappa Research Inc"), sponsor("Kappa Research LLC"), sponsor("Kappa Research Ltd")]
    dropped: dict[int, int] = {}
    got = match.suggest([company], sponsors, dropped)
    assert [s.kind for s in got] == ["strong"] * 3 + ["starts"] * 2 and dropped == {7: 3}
    assert [s.sponsor.name for s in got[3:]] == ["Kappa Research Site 5", "Kappa Research Site 4"]  # most trials kept
    remark = review.rows([company], got, dropped)[0][3]
    assert remark == "3 weaker suggestions left out"


def test_names_with_line_breaks_or_control_characters_do_not_break_the_sheet(tmp_path: Path) -> None:
    company = match.Company(8, "Tau\x0bBio Corp", "TAU")
    sponsors = [sponsor("Tau Bio\nCorp"), sponsor('Tau Bio, "Corp"'), sponsor("Tau Bio")]
    rows = review.rows([company], match.suggest([company], sponsors))
    assert [r[4] for r in rows] == ["", 'Tau Bio, "Corp"', "Tau Bio"]  # the name with a line break is left out
    xlsx, copy = tmp_path / "x_review.xlsx", tmp_path / "x_review.csv"
    xlsx.write_bytes(review.workbook(rows))
    copy.write_text(review.machine_copy(rows))
    fill(xlsx, {3: ("yes", "")})
    found, _ = review.read_decisions(xlsx, copy)
    assert [(d.sponsor_name, d.company) for d in found] == [('Tau Bio, "Corp"', "Tau Bio Corp")]


def table() -> list[tuple[object, ...]]:
    companies = [match.Company(101, "Alpha Therapeutics, Inc.", "ALFA"), match.Company(103, "=Gamma Corp", "GAMA")]
    sponsors = [
        sponsor("Alpha Therapeutics", "NCT001", "NCT002"),
        sponsor("Alpha Pharma", "NCT009"),
        sponsor("=Gamma", "NCT5"),
    ]
    return review.rows(companies, match.suggest(companies, sponsors))


def fill(sheet: Path, answers: dict[int, tuple[str, str]], edits: dict[tuple[int, int], object] | None = None) -> None:
    book = load_workbook(sheet)
    ws = book[review.SHEET]
    for row, (decision, note) in answers.items():
        ws.cell(row=row, column=11, value=decision)
        ws.cell(row=row, column=12, value=note)
    for (row, column), value in (edits or {}).items():
        ws.cell(row=row, column=column, value=value)
    book.save(sheet)


@pytest.fixture
def sheet(tmp_path: Path) -> tuple[Path, Path]:
    rows = table()
    xlsx, copy = tmp_path / "2026-11-18_review.xlsx", tmp_path / "2026-11-18_review.csv"
    xlsx.write_bytes(review.workbook(rows))
    copy.write_text(review.machine_copy(rows))
    return xlsx, copy


def test_the_review_sheet_has_a_company_line_then_its_suggestions_and_no_live_formula(sheet) -> None:
    xlsx, copy = sheet
    ws = load_workbook(xlsx)[review.SHEET]
    got = [[c.value for c in row] for row in ws.iter_rows()]
    assert got[0][:5] == ["cik", "company", "ticker", "matched_on", "sponsor_name"] and got[0][10:] == [
        "decision",
        "note",
    ]
    assert [(r[0], r[4], r[5]) for r in got[1:]] == [
        (101, None, "company"),
        (101, "Alpha Therapeutics", "strong"),
        (101, "Alpha Pharma", "core"),
        (103, None, "company"),
        (103, "'=Gamma", "strong"),
    ]
    assert all(c.data_type != "f" for row in ws.iter_rows() for c in row)  # a name can never run as a formula
    assert "'=Gamma" in copy.read_text()


def test_decisions_are_read_back_and_undecided_lines_are_counted(sheet) -> None:
    xlsx, copy = sheet
    fill(xlsx, {3: ("yes", "main name"), 4: ("Parent or subsidiary", ""), 5: ("not biotech", "tools"), 6: ("NO", "")})
    found, undecided = review.read_decisions(xlsx, copy)
    assert undecided == 0
    assert [(d.cik, d.sponsor_name, d.decision, d.note) for d in found] == [
        (101, "Alpha Therapeutics", "yes", "main name"),
        (101, "Alpha Pharma", "parent or subsidiary", ""),
        (103, "", "not biotech", "tools"),
        (103, "=Gamma", "no", ""),
    ]
    assert (
        found[0].company == "Alpha Therapeutics, Inc." and found[0].kind == "strong" and len(found[0].review_file) == 64
    )
    fill(xlsx, {3: ("", ""), 4: ("", "")})
    assert review.read_decisions(xlsx, copy)[1] == 2


@pytest.mark.parametrize(
    ("answers", "edits", "message"),
    [
        ({3: ("maybe", "")}, {}, "is not one of"),
        ({2: ("yes", "")}, {}, "is not one of"),  # a company line only takes "not biotech"
        ({3: ("not biotech", "")}, {}, "is not one of"),
        ({3: ("biotech", "")}, {}, "is not one of"),
        ({3: ("yes", "")}, {(3, 5): "Alpha Therapeutics Europe"}, "not a line of the original sheet"),
        ({3: ("yes", "")}, {(3, 1): 103}, "not a line of the original sheet"),
        ({}, {(1, 5): "sponsor"}, "column headings"),
    ],
)
def test_a_sheet_with_one_wrong_line_is_refused_as_a_whole(sheet, answers, edits, message: str) -> None:
    xlsx, copy = sheet
    fill(xlsx, {4: ("no", ""), **answers}, edits)
    with pytest.raises(DecisionError, match=message):
        review.read_decisions(xlsx, copy)


def test_a_missing_copy_or_a_file_that_is_no_sheet_is_refused(sheet, tmp_path: Path) -> None:
    xlsx, copy = sheet
    with pytest.raises(DecisionError, match="machine copy"):
        review.read_decisions(xlsx, tmp_path / "nothing.csv")
    xlsx.write_bytes(b"not a spreadsheet")
    with pytest.raises(DecisionError, match="could not be read"):
        review.read_decisions(xlsx, copy)


def test_the_decisions_file_only_grows_and_a_changed_mind_points_to_the_old_line(tmp_path: Path) -> None:
    first = [Decision(101, "Alpha Pharma", "no"), Decision(101, "Alpha Therapeutics", "yes", "n")]
    assert decisions.append(tmp_path, first, "t1") == {"added": 2, "changed": 0, "same": 0}
    before = (tmp_path / decisions.FILE).read_bytes()
    again = [Decision(101, "Alpha Pharma", "parent or subsidiary"), Decision(101, "Alpha Therapeutics", "yes", "n")]
    assert decisions.append(tmp_path, again, "t2") == {"added": 0, "changed": 1, "same": 1}
    after = (tmp_path / decisions.FILE).read_bytes()
    assert after.startswith(before) and after.count(b"\n") == 3
    lines = decisions.load(tmp_path)
    assert lines[2]["replaces_line"] == 1 and lines[2]["replaces_sha256"] == lines[0]["_sha256"]
    now = decisions.current(lines)
    assert now[(101, "Alpha Pharma")]["decision"] == "parent or subsidiary" and len(now) == 2
    with pytest.raises(DecisionError, match="unknown decision"):
        decisions.append(tmp_path, [Decision(1, "X", "perhaps")], "t3")
    assert (tmp_path / decisions.FILE).read_bytes() == after


@pytest.mark.parametrize("damage", ["edit", "drop", "half"])
def test_a_changed_removed_or_half_line_in_the_decisions_file_is_noticed(tmp_path: Path, damage: str) -> None:
    decisions.append(tmp_path, [Decision(1, "A", "yes"), Decision(2, "B", "no"), Decision(3, "C", "no")], "t1")
    path = tmp_path / decisions.FILE
    raw = path.read_bytes().splitlines(keepends=True)
    if damage == "edit":
        raw[0] = raw[0].replace(b'"yes"', b'"no"')
    elif damage == "drop":
        del raw[1]
    else:
        raw[2] = raw[2][:20]
    path.write_bytes(b"".join(raw))
    with pytest.raises(DecisionError):
        decisions.load(tmp_path)
    with pytest.raises(DecisionError):
        decisions.append(tmp_path, [Decision(4, "D", "yes")], "t2")
    assert path.read_bytes() == b"".join(raw)  # nothing was added to a damaged file


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def test_from_universe_to_linking_table_through_the_commands(world: Path, capsys, monkeypatch) -> None:  # noqa: F811
    # The made-up price files end on a fixed day; the age check of `build` is not what this test is about.
    monkeypatch.setattr("bobby_hedgefund.universe.cli.MAX_PRICE_AGE_DAYS", 10_000)
    data, today = world.parent, date.today().isoformat()
    assert cli.main(["match"]) == 1 and "no universe file yet" in capsys.readouterr().out
    assert cli.main(["build"]) == 0 and cli.main(["match"]) == 0
    out = capsys.readouterr().out
    assert "companies                            2" in out and "for the owner to fill in" in out
    linking = data / "linking"
    xlsx = linking / f"{today}_review.xlsx"
    rows = read_csv(linking / f"{today}_review.csv")
    assert [(r["company"], r["sponsor_name"], r["kind"], r["trials"]) for r in rows] == [
        ("Alpha Therapeutics, Inc.", "", "company", ""),
        ("Alpha Therapeutics, Inc.", "Alpha Therapeutics, Inc.", "strong", "2"),
        ("Alpha Therapeutics, Inc.", "Alpha Therapeutics", "strong", "1"),
        ("Zeta Pharma Inc", "", "company", ""),
    ]
    assert "_universe.csv" in (linking / f"{today}_review-inputs.txt").read_text()
    assert (
        oct(xlsx.stat().st_mode & 0o777) == "0o600"
        and oct((linking / f"{today}_review.csv").stat().st_mode & 0o777) == "0o400"
    )

    fill(xlsx, {3: ("yes", ""), 5: ("not biotech", "generics")})
    assert cli.main(["decisions", str(xlsx)]) == 0
    assert (
        "decisions read: 2; new: 2; changed: 0; same as before: 0; lines still undecided: 1" in capsys.readouterr().out
    )
    assert cli.main(["decisions", str(xlsx)]) == 0 and "new: 0" in capsys.readouterr().out
    assert cli.main(["decisions", str(data / "other.xlsx")]) == 1

    assert cli.main(["linking"]) == 0
    table_rows = read_csv(linking / f"{today}_linking.csv")
    assert [(r["cik"], r["sponsor_name"], r["relation"], r["trials"], r["trial_numbers"]) for r in table_rows] == [
        ("101", "Alpha Therapeutics, Inc.", "yes", "2", "NCT001 NCT004")
    ]
    assert "companies_marked_not_biotech             1" in capsys.readouterr().out

    assert cli.main(["build"]) == 0  # the owner's mark takes the company out of the next universe
    newest = read_csv(data / "universe" / f"{today}-2_universe.csv")
    assert {r["cik"]: r["why_out"] for r in newest}["106"] == "marked 'not biotech' by the owner"

    fill(xlsx, {5: ("biotech", "a mistake")})  # the mark is taken back: the company returns
    assert cli.main(["decisions", str(xlsx)]) == 0 and cli.main(["build"]) == 0
    back = read_csv(data / "universe" / f"{today}-3_universe.csv")
    assert {r["cik"]: r["in_universe"] for r in back}["106"] == "yes"
    fill(xlsx, {5: ("not biotech", "generics after all")})
    assert cli.main(["decisions", str(xlsx)]) == 0 and cli.main(["build"]) == 0
    capsys.readouterr()

    assert cli.main(["missed-check", "--count", "5", "--seed", "7"]) == 0
    drawn = read_csv(linking / f"{today}_missed-check.csv")
    assert [r["company"] for r in drawn] == ["Alpha Therapeutics, Inc."]  # one company is left in the universe
    assert drawn[0]["sponsor_names_linked_so_far"] == "Alpha Therapeutics, Inc."
    assert "random seed 7" in capsys.readouterr().out
    assert json.loads((linking / decisions.FILE).read_text().splitlines()[0])["cik"] == 101

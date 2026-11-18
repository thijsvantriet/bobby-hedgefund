"""The review sheet for the owner (docs/decisions/0006, point 3.4): one line per suggested match, with two columns
to fill in. Written as a spreadsheet for the owner and as a plain machine copy that is never edited; a filled-in
sheet is only accepted where it still agrees with that copy.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from ..archive.store import sha256_hex
from .decisions import Decision, DecisionError
from .match import Company, Suggestion
from .output import csv_text, plain_cell, safe_cell

COLUMNS = (
    "cik",
    "company",
    "ticker",
    "matched_on",
    "sponsor_name",
    "kind",
    "score",
    "trials",
    "as_lead",
    "example_trial",
)
SHEET = "Matches"
COMPANY_KIND = "company"  # the first line of each company: the place for a decision about the company itself
SPONSOR_CHOICES = ("yes", "no", "parent or subsidiary")
COMPANY_CHOICES = ("not biotech", "biotech")  # "biotech" takes an earlier "not biotech" back
HOW_TO = (
    "How to fill this in",
    "",
    "Each grey line is a company in the universe. Under it: registry names that may be the same company.",
    "For each name, choose in the column 'decision':",
    "    yes                      this sponsor name is this company",
    "    parent or subsidiary     it is this company's parent or daughter company (its trials count for the company)",
    "    no                       it is another organisation",
    "On the grey company line itself you may choose 'not biotech' when the company does not belong in a biotech",
    "universe at all (a maker of generic medicines, a diagnostics or tools company). Otherwise leave it empty.",
    "('biotech' on that line takes an earlier 'not biotech' back.)",
    "",
    "kind:  strong = identical name;  core = same name apart from words like Therapeutics / Pharma;",
    "       starts = the sponsor name starts with the company name;  similar = nearly the same spelling.",
    "'matched_on' shows which name of the company fitted: a different name there means a former name.",
    "A line you leave empty stays undecided and comes back next time. Use 'note' for anything worth remembering.",
    "Do not change the other columns: a changed line is refused when the sheet is read back.",
    "When done: save the file (keep the .xlsx format) and tell Claude, or run:  bobby-universe decisions <this file>",
)


def _printable(text: str) -> str:
    """A spreadsheet cannot hold control characters, and a line break inside a name helps nobody."""
    return "".join(ch if ch.isprintable() else " " for ch in text)


def rows(
    companies: list[Company], suggestions: list[Suggestion], dropped: dict[int, int] | None = None
) -> list[tuple[object, ...]]:
    by_company: dict[int, list[Suggestion]] = {}
    for s in suggestions:
        by_company.setdefault(s.company.cik, []).append(s)
    out: list[tuple[object, ...]] = []
    for c in companies:
        cut = (dropped or {}).get(c.cik)
        remark = f"{cut} weaker suggestions left out" if cut else ""
        out.append((c.cik, _printable(c.name), c.ticker, remark, "", COMPANY_KIND, "", "", "", ""))
        for s in by_company.get(c.cik, []):
            sp = s.sponsor
            if not sp.name.isprintable():
                continue  # a name with a control character cannot go through a spreadsheet and back unchanged
            row = (c.cik, _printable(c.name), c.ticker, _printable(s.matched_on), sp.name, s.kind, s.score)
            out.append((*row, len(sp.trials), len(sp.lead), max(sp.trials)))
    return out


def machine_copy(table: list[tuple[object, ...]]) -> str:
    return csv_text(COLUMNS, table)


def workbook(table: list[tuple[object, ...]]) -> bytes:
    book = Workbook()
    readme = book.active
    assert readme is not None
    readme.title = "Read me"
    for line in HOW_TO:
        readme.append([line])
    readme["A1"].font = Font(bold=True, size=14)
    readme.column_dimensions["A"].width = 120
    sheet = book.create_sheet(SHEET)
    sheet.append([*COLUMNS, "decision", "note"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sponsor_choice = DataValidation(type="list", formula1='"' + ",".join(SPONSOR_CHOICES) + '"', allow_blank=True)
    company_choice = DataValidation(type="list", formula1='"' + ",".join(COMPANY_CHOICES) + '"', allow_blank=True)
    sheet.add_data_validation(sponsor_choice)
    sheet.add_data_validation(company_choice)
    grey = PatternFill("solid", fgColor="DDDDDD")
    decision_column = len(COLUMNS) + 1
    for number, row in enumerate(table, start=2):
        sheet.append([safe_cell(v) for v in row] + ["", ""])
        is_company = row[COLUMNS.index("kind")] == COMPANY_KIND
        (company_choice if is_company else sponsor_choice).add(sheet.cell(row=number, column=decision_column))
        if is_company:
            for cell in sheet[number]:
                cell.fill = grey
                cell.font = Font(bold=True)
    for letter, width in zip("ABCDEFGHIJKL", (9, 34, 8, 34, 48, 9, 7, 7, 8, 14, 22, 40), strict=True):
        sheet.column_dimensions[letter].width = width
    for cell in sheet["E"]:
        cell.alignment = Alignment(wrap_text=True)
    sheet.freeze_panes = "A2"
    book.active = 1
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return plain_cell(str(value)).strip()


def read_decisions(sheet_path: Path, copy_path: Path) -> tuple[list[Decision], int]:
    """The decisions in a filled-in review sheet, and the number of lines left undecided.

    Every decided line must still be a line of the machine copy (same company, sponsor name and kind), so a typo
    in another column cannot link a wrong name. Raises DecisionError and returns nothing when one line is wrong."""
    try:
        copy_bytes = copy_path.read_bytes()
        known = {}
        for row in csv.DictReader(io.StringIO(copy_bytes.decode("utf-8"), newline="")):
            known[(row["cik"], plain_cell(row["sponsor_name"]), row["kind"])] = row
    except (OSError, KeyError, UnicodeDecodeError) as exc:
        raise DecisionError(
            f"the machine copy {copy_path.name} is missing or unreadable ({type(exc).__name__})"
        ) from exc
    try:
        book = load_workbook(sheet_path, read_only=True, data_only=True)
        try:
            table = list(book[SHEET].iter_rows(values_only=True))
        finally:
            book.close()
    except Exception as exc:  # openpyxl raises many kinds of error on a damaged file
        raise DecisionError(f"{sheet_path.name} could not be read as a review sheet ({type(exc).__name__})") from exc
    if not table or [_text(v) for v in table[0]][: len(COLUMNS) + 2] != [*COLUMNS, "decision", "note"]:
        raise DecisionError(f"{sheet_path.name}: the column headings were changed")
    fingerprint = sha256_hex(copy_bytes)
    found: list[Decision] = []
    undecided = 0
    problems: list[str] = []
    for number, raw in enumerate(table[1:], start=2):
        cells = [_text(v) for v in (*raw, *[None] * (len(COLUMNS) + 2))][: len(COLUMNS) + 2]
        row = dict(zip([*COLUMNS, "decision", "note"], cells, strict=True))
        if not any(cells):
            continue
        decision = row["decision"].lower()
        is_company = row["kind"] == COMPANY_KIND
        if not decision:
            undecided += not is_company
            continue
        original = known.get((row["cik"], row["sponsor_name"], row["kind"]))
        if original is None:
            problems.append(f"line {number}: not a line of the original sheet (company, sponsor name or kind changed)")
            continue
        if decision not in (COMPANY_CHOICES if is_company else SPONSOR_CHOICES):
            allowed = ", ".join(COMPANY_CHOICES if is_company else SPONSOR_CHOICES)
            problems.append(f"line {number}: decision {row['decision']!r} is not one of: {allowed}")
            continue
        found.append(
            Decision(
                cik=int(row["cik"]),
                sponsor_name=row["sponsor_name"],
                decision=decision,
                note=row["note"],
                company=plain_cell(original["company"]),
                kind=row["kind"],
                score=float(original["score"]) if original["score"] else None,
                review_file=fingerprint,
            )
        )
    if problems:
        shown = "; ".join(problems[:8]) + (f"; and {len(problems) - 8} more" if len(problems) > 8 else "")
        raise DecisionError(f"{sheet_path.name}: nothing was taken over. {shown}")
    return found, undecided

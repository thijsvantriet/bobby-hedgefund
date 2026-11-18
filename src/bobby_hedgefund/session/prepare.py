"""Build the folder of one session: copies of what the agents may read, and nothing else (docs/decisions/0003,
point 1; docs/SPEC.md section 1).

Everything in it was saved before the data cut-off, is re-checked against its fingerprint, and is listed with its
fingerprint and the time it was saved in the session's list of inputs (`inputs.jsonl`, one numbered line per
source). The agents name their sources by those numbers.

```
sessions/<date>/
  session.json            start time, data cut-off, universe file, what was counted
  inputs.jsonl            every source: its number, what it is, fingerprint, when it was saved, the link
  companies/<SEC number>/
    company.md            who it is, and what is new since the last session
    numbers.md            numbers worked out by script from saved prices (private; never to be copied into text)
    trials.md             changes in its trial records, or the note that its trials are not linked yet
    filings/<n>-<form>.txt   the new filings as plain text
    report.md             our own newest report on it, if there is one
  screening/batch-01.md   a short digest per company with news; companies without news are not in it
  screening/no-news.txt   the companies without any new item: marked by this script, sent to no model
```

Companies that are in the universe through the XBI fund only are left out here, in one place: they get no
folder, no screening and no analysis, so they can never be covered, bought, drawn or forecast (docs/decisions/0009,
open point 2). Their names go to a private list that the log and the publish script use as a last check.
"""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..archive.sec_filings import FILINGS_SOURCE
from ..archive.store import iso, sha256_hex
from ..filings import read as filings
from ..funds.prices import PriceBook
from ..funds.universe import Universe
from ..funds.universe import load as load_universe
from ..log import private
from ..universe.inputs import InputError
from ..universe.output import plain_cell, write_new, write_new_bytes
from . import plaintext, sources

BATCH = 25  # companies per screening file
MAX_FILING_TEXT = 2_000_000  # characters of one filing that are copied; the saved file itself is never cut
BIG_MOVE = Fraction(15, 100)  # a move of the share since the last session that counts as an item by itself
# A filing saved since the last session is news only when it was also filed around then. One that was filed long
# before and fetched late (the first big download, a gap that was filled) is not: it stays in the archive.
LATE_FILING_DAYS = 3
TEXT_EXHIBITS = ("EX-99",)  # press releases and presentations; other exhibits stay in the saved file
SKIPPED_TYPES = ("GRAPHIC", "ZIP", "EXCEL", "XML", "JSON", "PDF")
CHANGE_FIELDS = {
    "overall_status": "overall status",
    "why_stopped": "why stopped",
    "start_date": "start date",
    "primary_completion_date": "primary completion date",
    "completion_date": "completion date",
    "phases": "phases",
    "enrollment": "number of patients",
    "primary_outcomes": "primary outcomes",
    "lead_sponsor": "lead sponsor",
    "has_results": "has results",
    "results_first_posted": "results first posted",
}


class PrepareError(Exception):
    pass


@dataclass
class Item:
    """One new thing about a company, with the number of its source in the list of inputs."""

    n: int
    kind: str  # "filing", "insider trades", "trial change" or "price move"
    line: str  # one line for the screening digest
    results_news: bool = False  # an event report that announces results: the results reader looks at it


@dataclass
class Prepared:
    folder: Path
    session_day: date
    cutoff: datetime
    since: datetime
    universe: Universe
    companies: list[int] = field(default_factory=list)
    items: dict[int, list[Item]] = field(default_factory=dict)
    counts: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    inputs_sha256: str = ""


class Inputs:
    """The numbered list of everything the session folder was made from."""

    def __init__(self) -> None:
        self.lines: list[dict[str, Any]] = []

    def add(self, **fields: Any) -> int:
        n = len(self.lines) + 1
        self.lines.append({"n": n, **fields})
        return n

    def text(self) -> str:
        return "".join(json.dumps(line, sort_keys=True, ensure_ascii=True) + "\n" for line in self.lines)


def filing_link(cik: int, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{accession}-index.htm"


def trial_link(nct: str) -> str:
    return f"https://clinicaltrials.gov/study/{nct}"


def filing_text(body: bytes, head: filings.Header) -> str:
    """The readable part of a filing: the form itself and its press releases, as plain text."""
    out = [
        f"SEC filing {head.accession}",
        f"Kind: {head.form}    Filed: {head.filed.isoformat()}"
        + (f"    Period: {head.period.isoformat()}" if head.period else ""),
    ]
    if head.items:
        out.append("Items: " + "; ".join(head.items))
    out.append("")
    if head.form.split("/")[0] == "4":
        try:
            trades = filings.insider_trades(body)
        except filings.FilingError:
            out.append("The lines of this insider filing could not be read; see the filing itself.")
            return "\n".join(out) + "\n"
        out.append("Insider trades reported (who, role, what, day, code, shares, price, shares held afterwards):")
        for t in trades:
            what = "acquired" if t.acquired else "disposed of" if t.acquired is False else "?"
            shares = t.shares if t.shares is not None else "?"
            price = t.price if t.price is not None else "?"
            after = t.shares_after if t.shares_after is not None else "?"
            kind = " [option or other derivative]" if t.derivative else ""
            who = f"{t.owner} ({', '.join(t.roles) or 'role not given'})"
            out.append(
                f"- {who}: {t.security}, {t.day or 'no day'}, code {t.code}, {what} {shares} at {price}, "
                f"held afterwards {after}{kind}"
            )
        return "\n".join(out) + "\n"
    used = 0
    for doc in filings.documents(body):
        kind = doc.type.upper()
        main = kind.split("/")[0] == head.form.split("/")[0]
        if not (main or kind.startswith(TEXT_EXHIBITS)) or kind in SKIPPED_TYPES or plaintext.is_binary(doc.text):
            continue
        text = plaintext.to_text(doc.text)
        room = MAX_FILING_TEXT - used
        out.append(f"===== document: {doc.type} {doc.description or doc.filename} =====")
        if len(text) > room:
            out.append(text[: max(room, 0)])
            out.append("[cut here: the saved filing is longer than what is copied for a session]")
            break
        out.append(text)
        used += len(text)
    return "\n".join(out) + "\n"


def announces_results(head: filings.Header) -> bool:
    """An event report with a press release or a "Regulation FD" or "other events" item: where trial results
    are announced. The results reader decides whether it really is one."""
    if head.form.split("/")[0] != "8-K":
        return False
    text = " ".join(head.items).lower()
    return any(word in text for word in ("regulation fd", "other events", "results of operations"))


def read_linking(path: Path) -> dict[str, list[int]]:
    """The linking table: trial number -> the companies it belongs to."""
    out: dict[str, list[int]] = {}
    try:
        for row in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"), newline="")):
            for nct in plain_cell(row["trial_numbers"]).split():
                out.setdefault(nct, []).append(int(row["cik"]))
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise PrepareError(f"{path.name} is not a linking table ({type(exc).__name__})") from exc
    return out


def _value(value: Any) -> str:
    if isinstance(value, dict) and "date" in value:
        return f"{value['date']} ({str(value.get('type', '')).lower() or 'no type'})"
    if isinstance(value, list):
        return "; ".join(_value(v) for v in value) or "none"
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return "none" if value is None else str(value)


def change_line(change: dict[str, Any]) -> str:
    name = CHANGE_FIELDS.get(str(change.get("field")), str(change.get("field")))
    moved = f" (moved {change['moved_days']} days)" if change.get("moved_days") is not None else ""
    return (
        f"trial {change['nct']}: {name} changed from {_value(change.get('old'))} to {_value(change.get('new'))}{moved}"
    )


def pct(change: Fraction) -> str:
    sign = "+" if change >= 0 else "-"
    return f"{sign}{abs(float(change)) * 100:.1f}%"


def _replace(path: Path, text: str) -> None:
    """Write a private file that is made anew every session (the private list of names)."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f".{path.name}-{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(path)


def prepare(
    *,
    data_dir: Path,
    mode_root: Path,
    session_day: date,
    start_time: datetime,
    cutoff: datetime,
    since: datetime,
    held: set[int] | None = None,
) -> Prepared:
    """Build the session folder. Refuses when it exists already: a session folder is made once."""
    folder = mode_root / "sessions" / session_day.isoformat()
    if folder.exists():
        raise PrepareError(f"the session folder of {session_day} exists already; it is made once and never changed")
    archive_root, prices_root = data_dir / "archive", data_dir / "prices"
    times = sources.stored_times(archive_root, prices_root)
    notes: list[str] = []
    universe_path, passed = sources.newest_admitted(
        data_dir / "universe", "universe.csv", "universe-inputs.txt", times, cutoff
    )
    notes += passed
    if universe_path is None:
        raise PrepareError("no universe file may be used at this cut-off: " + ("; ".join(passed) or "there is none"))
    universe = load_universe(universe_path)
    hidden = sorted((c for c in universe.companies.values() if c.xbi_only), key=lambda c: c.cik)
    _replace(
        mode_root / private.FILE,
        "# Companies that may not be named in public (docs/decisions/0006). Made anew by every session preparation.\n"
        + "".join(f"{c.cik}\t{c.ticker}\t{c.name}\n" for c in hidden),
    )
    companies = sorted(universe.buyable())
    done = Prepared(folder, session_day, cutoff, since, universe, companies)
    done.notes = notes
    inputs = Inputs()
    inputs.add(kind="universe", file=universe.file, sha256=universe.sha256, made_before_cutoff=True)
    archive = sources.before(archive_root, cutoff)
    items: dict[int, list[Item]] = {cik: [] for cik in companies}
    files: dict[int, list[tuple[str, str]]] = {cik: [] for cik in companies}  # (file name, text)
    wanted = set(companies)
    lower = iso(since)

    # 1. new SEC filings
    seen: set[str] = set()
    old = 0
    earliest_filed = (since.date() - timedelta(days=LATE_FILING_DAYS)).isoformat()
    for rec in archive.files(FILINGS_SOURCE):
        meta = sources.record_meta(rec)
        accession, cik = meta.get("accession"), meta.get("cik")
        if not accession or cik not in wanted or accession in seen or str(rec.get("ts", "")) <= lower:
            continue
        seen.add(accession)
        if str(meta.get("filed") or "9999") < earliest_filed:
            old += 1
            continue
        try:
            body = archive.read(rec)
            head = filings.header(body)
            text = filing_text(body, head)
        except (InputError, filings.FilingError) as exc:
            done.notes.append(f"a filing of company {cik} could not be read ({type(exc).__name__}); left out")
            continue
        form = head.form.replace("/", "-").replace(" ", "")
        n = inputs.add(
            kind="sec filing",
            cik=cik,
            form=head.form,
            date=head.filed.isoformat(),
            link=filing_link(cik, head.accession),
            source="SEC filing " + head.form,
            archive_path=rec["path"],
            sha256=rec["sha256"],
            stored=rec["ts"],
            file=f"companies/{cik}/filings/{len(inputs.lines) + 1:04d}-{form}.txt",
        )
        files[cik].append((f"filings/{n:04d}-{form}.txt", text))
        about = f"; items: {'; '.join(head.items)}" if head.items else ""
        kind = "insider trades" if head.form.split("/")[0] == "4" else "filing"
        items[cik].append(
            Item(n, kind, f"[{n}] {head.form} filed {head.filed.isoformat()}{about}", announces_results(head))
        )
    done.counts["filings"] = len(seen) - old
    done.counts["filings_saved_late_and_left_out"] = old

    # 2. changes in trial records, through the linking table once the owner's check has made one
    linking_path, passed = sources.newest_admitted(
        data_dir / "linking", "linking.csv", "linking-inputs.txt", times, cutoff
    )
    done.notes += passed
    linking = read_linking(linking_path) if linking_path is not None else None
    if linking_path is not None:
        inputs.add(kind="linking table", file=linking_path.name, sha256=sha256_hex(linking_path.read_bytes()))
    upper = iso(cutoff)
    changes = unlinked = 0
    paths = {path: sha for (path, sha) in times}
    folder_changes = data_dir / "trial-changes"
    for path in sorted(folder_changes.glob("*_changes.jsonl")) if folder_changes.is_dir() else []:
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                change = json.loads(raw)
                saved = str(change["new_saved"])
            except (ValueError, KeyError, TypeError):
                done.notes.append(f"a line of {path.name} could not be read; left out")
                continue
            if not (lower < saved < upper):
                continue
            changes += 1
            owners = [c for c in (linking or {}).get(str(change.get("nct")), []) if c in wanted]
            if not owners:
                unlinked += 1
                continue
            for cik in owners:
                n = inputs.add(
                    kind="trial record",
                    cik=cik,
                    nct=change["nct"],
                    date=change.get("new_posted"),
                    link=trial_link(change["nct"]),
                    source="ClinicalTrials.gov record " + change["nct"],
                    archive_path=change.get("new_file"),
                    sha256=paths.get(str(change.get("new_file")), ""),
                    stored=saved,
                )
                items[cik].append(Item(n, "trial change", f"[{n}] {change_line(change)}"))
    done.counts |= {
        "trial_changes": changes,
        "trial_changes_not_linked": unlinked,
        "linking_table": linking is not None,
    }

    # 3. numbers from saved prices (private)
    numbers: dict[int, list[str]] = {}
    prices = PriceBook(prices_root, cutoff)
    days = prices.days()
    if days:
        last = days[-1]
        n_last = inputs.add(
            kind="prices",
            day=last.isoformat(),
            sha256=prices.sha256(last),
            copy="final",
            source="our own numbers from saved prices (private)",
        )
        before_since = [d for d in days if datetime.combine(d, datetime.max.time(), tzinfo=UTC) < since]
        refs = {"1 trading day": 1, "5 trading days": 5, "20 trading days": 20, "60 trading days": 60}
        for cik in companies:
            company = universe.companies[cik]
            now = prices.close(company.ticker, last)
            lines = [f"Numbers worked out by script from saved prices, as of the close of {last} [{n_last}]."]
            lines.append("PRIVATE: none of these may be written into a report section, a forecast or a thesis.")
            if now is None:
                lines.append(f"No closing price on {last}.")
                numbers[cik] = lines
                continue
            lines.append(f"Last closing price: {float(now):.2f}")
            if company.market_value is not None:
                lines.append(f"Market value at the last universe run: about ${company.market_value / 1e6:,.0f} million")
            for label, back in refs.items():
                if len(days) > back:
                    then = prices.close(company.ticker, days[-1 - back])
                    if then:
                        lines.append(f"Change over {label}: {pct(now / then - 1)}")
            if before_since:
                then = prices.close(company.ticker, before_since[-1])
                if then:
                    move = now / then - 1
                    lines.append(f"Change since the last session ({before_since[-1]}): {pct(move)}")
                    if abs(move) >= BIG_MOVE:
                        items[cik].append(
                            Item(n_last, "price move", f"[{n_last}] the share moved {pct(move)} since the last session")
                        )
            numbers[cik] = lines
        done.counts["price_day"] = last.isoformat()
    else:
        done.notes.append("no price file was stored before the cut-off: the numbers from prices are missing")

    # 4. the files
    reports = mode_root / "reports"
    for cik in companies:
        company = universe.companies[cik]
        base = folder / "companies" / str(cik)
        new = items[cik]
        lines = [
            f"# {company.name}",
            f"Ticker: {company.ticker}    SEC company number: {cik}",
            "",
            f"## New since the last session ({iso(since)}), saved before the data cut-off ({iso(cutoff)})",
        ]
        lines += [f"- {item.line}" for item in new] or ["- nothing new"]
        lines += ["", "The number in square brackets is the source's number in the session's list of inputs."]
        write_new(base / "company.md", "\n".join(lines) + "\n")
        write_new(base / "numbers.md", "\n".join(numbers.get(cik, ["No numbers from prices for this session."])) + "\n")
        trial_items = [item for item in new if item.kind == "trial change"]
        if linking is None:
            trials = "Its trials are not linked yet: the linking table waits for the owner's one-time check.\n"
        elif trial_items:
            trials = "Changes in its trial records since the last session:\n" + "".join(
                f"- {i.line}\n" for i in trial_items
            )
        else:
            trials = "No change in its linked trial records since the last session.\n"
        write_new(base / "trials.md", trials)
        for name, text in files[cik]:
            write_new(base / name, text)
        folder_reports = reports / str(cik)
        earlier = sorted(p for p in folder_reports.glob("*.md")) if folder_reports.is_dir() else []
        if earlier:
            write_new_bytes(base / "report.md", earlier[-1].read_bytes())
    with_news = [cik for cik in companies if items[cik]]
    for number, at in enumerate(range(0, len(with_news), BATCH), start=1):
        part = [f"# Screening, batch {number}", ""]
        for cik in with_news[at : at + BATCH]:
            company = universe.companies[cik]
            held_mark = "  (held by a fund)" if cik in (held or set()) else ""
            part.append(f"## {cik} {company.name} ({company.ticker}){held_mark}")
            part += [f"- {item.line}" for item in items[cik]]
            part.append(f"Files: companies/{cik}/")
            part.append("")
        write_new(folder / "screening" / f"batch-{number:02d}.md", "\n".join(part))
    quiet = [cik for cik in companies if not items[cik]]
    write_new(folder / "screening" / "no-news.txt", "".join(f"{cik}\n" for cik in quiet))
    text = inputs.text()
    write_new(folder / "inputs.jsonl", text)
    done.inputs_sha256 = sha256_hex(text.encode("utf-8"))
    done.items = items
    done.counts |= {
        "companies": len(companies),
        "left_out_as_private": len(hidden),
        "companies_with_news": len(with_news),
        "companies_without_news": len(quiet),
        "screening_batches": (len(with_news) + BATCH - 1) // BATCH,
        "inputs": len(inputs.lines),
    }
    session = {
        "session_day": session_day.isoformat(),
        "start_time": iso(start_time),
        "cutoff": iso(cutoff),
        "since": iso(since),
        "universe": {"file": universe.file, "sha256": universe.sha256},
        "inputs_sha256": done.inputs_sha256,
        "with_news": with_news,
        "results_news": sorted(cik for cik in companies if any(item.results_news for item in items[cik])),
        "counts": done.counts,
        "notes": done.notes,
    }
    write_new(folder / "session.json", json.dumps(session, indent=1, sort_keys=True) + "\n")
    return done

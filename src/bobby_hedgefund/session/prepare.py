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
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
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
from ..universe.output import plain_cell, write_new
from . import plaintext, sources

BATCH = 25  # companies per screening file
MAX_FILING_TEXT = 2_000_000  # characters of one filing that are copied; the saved file itself is never cut
BIG_MOVE = Fraction(15, 100)  # a move of the share since the last session that counts as an item by itself
# A filing saved since the last session is news only when it was also filed around then. One that was filed long
# before and fetched late (the first big download, a gap that was filled) is not: it stays in the archive.
LATE_FILING_DAYS = 3
HOLDER_FORMS = ("3", "4", "5", "SC 13D", "SC 13G", "SCHEDULE 13D", "SCHEDULE 13G")  # filed by an owner of shares
HOLDER_NOTE = (
    "NOTE: this company filed this as a holder of ANOTHER company's shares. It says nothing about this company's "
    "own shares or insiders."
)
NOT_NAMED = "[a company that is not named]"
MAX_VALUE = 300  # characters of one value of a trial record in a digest line
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


def filing_text(body: bytes, head: filings.Header, holder: bool = False) -> str:
    """The readable part of a filing: the form itself and its press releases, as plain text."""
    out = [
        f"SEC filing {head.accession}",
        f"Kind: {head.form}    Filed: {head.filed.isoformat()}"
        + (f"    Period: {head.period.isoformat()}" if head.period else ""),
    ]
    if head.names:
        out.append("Parties: " + "; ".join(f"{role}: {name}" for role, name in head.names))
    if holder:
        out.append(HOLDER_NOTE)
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


def _plain(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum())


def is_holder_filing(head: filings.Header, company_name: str) -> bool:
    """A company's own list of filings also holds what it files as an owner of ANOTHER company's shares (an
    insider trade, a holding above 5%). Such a filing says nothing about the company itself."""
    form = head.form.upper().split("/")[0]
    if form not in HOLDER_FORMS:
        return False
    about = [name for role, name in head.names if role in ("issuer", "subject company")]
    ours = _plain(company_name)
    return bool(about) and not any(
        _plain(name) == ours or ours in _plain(name) or _plain(name) in ours for name in about
    )


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
        text = f"{value['date']} ({str(value.get('type', '')).lower() or 'no type'})"
    elif isinstance(value, list):
        text = "; ".join(_value(v) for v in value) or "none"
    elif isinstance(value, dict):
        text = ", ".join(f"{k}: {v}" for k, v in value.items())
    else:
        text = "none" if value is None else str(value)
    # Text from a registry record: on one line, and without square brackets, which here mean "source number".
    text = " ".join(text.split()).replace("[", "(").replace("]", ")")
    return text if len(text) <= MAX_VALUE else text[:MAX_VALUE] + " ..."


def change_line(change: dict[str, Any]) -> str:
    name = CHANGE_FIELDS.get(str(change.get("field")), _value(change.get("field")))
    moved = f" (moved {change['moved_days']} days)" if isinstance(change.get("moved_days"), int) else ""
    old, new = _value(change.get("old")), _value(change.get("new"))
    return f"trial {_value(change.get('nct'))}: {name} changed from {old} to {new}{moved}"


def pct(change: Fraction) -> str:
    sign = "+" if change >= 0 else "-"
    return f"{sign}{abs(float(change)) * 100:.1f}%"


def write_private_names(path: Path, hidden: list[Any]) -> int:
    """The private list of companies that may not be named in public. It only ever grows: a company that was on
    it stays on it, and names that were added by hand (a fourth column) are kept. Returns how many it holds."""
    known: dict[int, private.PrivateCompany] = {}
    if path.exists():
        known = {c.cik: c for c in private.load(path)}
    for company in hidden:
        earlier = known.get(company.cik)
        known[company.cik] = private.PrivateCompany(
            company.cik, company.ticker, company.name, earlier.aliases if earlier else ()
        )
    lines = [
        "# Companies that may not be named in public (docs/decisions/0006). Written by the session preparation;",
        "# it only grows. A fourth column, added by hand, may give more names of a company, separated by |.",
    ]
    for cik in sorted(known):
        c = known[cik]
        lines.append("\t".join([str(c.cik), c.ticker, c.name, *(["|".join(c.aliases)] if c.aliases else [])]))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(f".{path.name}-{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, ("\n".join(lines) + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(path)
    return len(known)


def shown_before(sessions: Path, session_day: date) -> set[tuple[str, ...]]:
    """What earlier sessions were shown already: every filing and every change in a trial record in their lists
    of inputs. What is "new" is what no earlier session saw, not what happens to carry a later time."""
    seen: set[tuple[str, ...]] = set()
    for folder in sorted(sessions.iterdir()) if sessions.is_dir() else []:
        if (
            folder.name.startswith(".")
            or folder.name >= session_day.isoformat()
            or not (folder / "session.json").exists()
        ):
            continue
        for raw in (folder / "inputs.jsonl").read_text(encoding="utf-8").splitlines():
            line = json.loads(raw)
            if line.get("kind") == "sec filing":
                seen.add(("filing", str(line.get("accession"))))
            elif line.get("kind") == "trial record":
                seen.add(("trial", str(line.get("nct")), str(line.get("field")), str(line.get("archive_path"))))
    return seen


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
    """Build the session folder. Refuses when it exists already: a session folder is made once. It is built
    under another name and gets its own name in one step at the very end, so a half-built folder never counts."""
    for when in (start_time, cutoff, since):
        if when.tzinfo is None:
            raise PrepareError("a time without a time zone cannot be used as a cut-off")
    if since >= cutoff:
        raise PrepareError("the last session's cut-off must lie before this one's")
    sessions = mode_root / "sessions"
    final = sessions / session_day.isoformat()
    if final.exists():
        raise PrepareError(f"the session folder of {session_day} exists already; it is made once and never changed")
    for left in sorted(sessions.glob(f".{session_day.isoformat()}.partial-*")) if sessions.is_dir() else []:
        if left.is_dir() and not left.is_symlink():
            shutil.rmtree(left)  # left by a preparation that stopped half-way; nothing ever read it
    folder = sessions / f".{session_day.isoformat()}.partial-{os.getpid()}"
    archive_root, prices_root = data_dir / "archive", data_dir / "prices"
    times = sources.stored_times(archive_root, prices_root)
    first_stored: dict[str, str] = {}
    for (path_, _sha), ts in times.items():
        if path_ not in first_stored or ts < first_stored[path_]:
            first_stored[path_] = ts
    notes: list[str] = []
    universe_path, passed = sources.newest_admitted(
        data_dir / "universe", "universe.csv", "universe-inputs.txt", times, cutoff
    )
    notes += passed
    if universe_path is None:
        raise PrepareError("no universe file may be used at this cut-off: " + ("; ".join(passed) or "there is none"))
    universe = load_universe(universe_path)
    hidden = sorted((c for c in universe.companies.values() if c.xbi_only), key=lambda c: c.cik)
    if not hidden:
        notes.append(
            "this universe file marks no company as in through the XBI fund only; check its 'door' column before "
            "anything is published"
        )
    listed = write_private_names(mode_root / private.FILE, hidden)
    names = private.PrivateNames(private.load(mode_root / private.FILE))
    companies = sorted(universe.buyable() - {c.cik for c in names.companies})
    done = Prepared(final, session_day, cutoff, since, universe, companies)
    done.notes = notes
    inputs = Inputs()
    inputs.add(kind="universe", file=universe.file, sha256=universe.sha256, made_before_cutoff=True)
    archive = sources.before(archive_root, cutoff)
    items: dict[int, list[Item]] = {cik: [] for cik in companies}
    files: dict[int, list[tuple[str, str]]] = {cik: [] for cik in companies}  # (file name, text)
    wanted = set(companies)
    earlier = shown_before(sessions, session_day)
    veiled = 0

    def veil(text: str) -> str:
        """Take the names of companies that may not be named out of a text the agents will read."""
        nonlocal veiled
        spans = names.spans(text)
        if not spans:
            return text
        out, at = [], 0
        for start, end, _ in spans:
            if start < at:
                continue
            out += [text[at:start], NOT_NAMED]
            at = end
            veiled += 1
        return "".join(out) + text[at:]

    # 1. new SEC filings: saved before the cut-off, filed around the last session, and shown to no earlier one
    seen: set[str] = set()
    old = unreadable = 0
    earliest_filed = (since.date() - timedelta(days=LATE_FILING_DAYS)).isoformat()
    for rec in archive.files(FILINGS_SOURCE):
        meta = sources.record_meta(rec)
        accession, cik = meta.get("accession"), meta.get("cik")
        if not accession or cik not in wanted or accession in seen or ("filing", str(accession)) in earlier:
            continue
        seen.add(accession)
        if str(meta.get("filed") or "9999") < earliest_filed:
            old += 1
            continue
        try:
            body = archive.read(rec)
            head = filings.header(body)
            holder = is_holder_filing(head, universe.companies[cik].name)
            text = veil(filing_text(body, head, holder))
        except (InputError, filings.FilingError) as exc:
            unreadable += 1
            done.notes.append(f"a filing of company {cik} could not be read ({type(exc).__name__}); left out")
            continue
        form = "".join(c if c.isalnum() else "-" for c in head.form)[:20]
        n = inputs.add(
            kind="sec filing",
            cik=cik,
            accession=head.accession,
            form=head.form,
            date=head.filed.isoformat(),
            link=filing_link(cik, head.accession),
            source="SEC filing " + head.form,
            archive_path=rec["path"],
            sha256=rec["sha256"],
            stored=first_stored.get(str(rec["path"]), rec["ts"]),
            file=f"companies/{cik}/filings/{len(inputs.lines) + 1:04d}-{form}.txt",
        )
        files[cik].append((f"filings/{n:04d}-{form}.txt", text))
        if holder:
            line = f"[{n}] {head.form} filed {head.filed.isoformat()}: filed by this company as a holder of another"
            items[cik].append(Item(n, "holder filing", line))
            continue
        about = f"; items: {'; '.join(head.items)}" if head.items else ""
        kind = "insider trades" if head.form.split("/")[0] == "4" else "filing"
        items[cik].append(
            Item(n, kind, f"[{n}] {head.form} filed {head.filed.isoformat()}{about}", announces_results(head))
        )
    done.counts["filings"] = len(seen) - old - unreadable
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
    earliest_change = iso(since - timedelta(days=LATE_FILING_DAYS))
    changes = unlinked = distrusted = 0
    sha_of = {path_: sha for (path_, sha) in times}
    folder_changes = data_dir / "trial-changes"
    for path in sorted(folder_changes.glob("*_changes.jsonl")) if folder_changes.is_dir() else []:
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                change = json.loads(raw)
                saved, new_file = str(change["new_saved"]), str(change["new_file"])
                nct, field_ = str(change["nct"]), str(change["field"])
            except (ValueError, KeyError, TypeError):
                done.notes.append(f"a line of {path.name} could not be read; left out")
                continue
            if not (earliest_change < saved < upper) or ("trial", nct, field_, new_file) in earlier:
                continue
            # The line's own time is not taken on trust: the page it names must be in the saved-files list,
            # saved at that time, before the cut-off.
            if first_stored.get(new_file) != saved:
                distrusted += 1
                continue
            changes += 1
            owners = [c for c in (linking or {}).get(nct, []) if c in wanted]
            if not owners:
                unlinked += 1
                continue
            for cik in owners:
                n = inputs.add(
                    kind="trial record",
                    cik=cik,
                    nct=nct,
                    field=field_,
                    date=change.get("new_posted"),
                    link=trial_link(nct),
                    source="ClinicalTrials.gov record " + nct,
                    archive_path=new_file,
                    sha256=sha_of.get(new_file, ""),
                    stored=saved,
                )
                items[cik].append(Item(n, "trial change", veil(f"[{n}] {change_line(change)}")))
    done.counts |= {"trial_changes": changes, "trial_changes_not_linked": unlinked}
    done.counts["linking_table"] = linking is not None
    if distrusted:
        done.notes.append(
            f"{distrusted} trial change(s) name a page that the saved-files list does not confirm; left out"
        )

    # 3. numbers from saved prices (private)
    numbers: dict[int, list[str]] = {}
    prices = PriceBook(prices_root, cutoff)
    days = prices.days()
    if days:
        last = days[-1]
        # "Since the last session": against the newest price day that session could see, not against the
        # calendar. The final copy of a day arrives a day or two later, so the two differ.
        then_days = PriceBook(prices_root, since).days()
        seen_then = then_days if then_days and then_days[-1] < last else []  # no newer price day: nothing moved
        refs = {"1 trading day": 1, "5 trading days": 5, "20 trading days": 20, "60 trading days": 60}
        used_days = {
            last,
            *([seen_then[-1]] if seen_then else []),
            *(days[-1 - b] for b in refs.values() if len(days) > b),
        }
        number_of = {
            d: inputs.add(
                kind="prices",
                day=d.isoformat(),
                sha256=prices.sha256(d),
                copy="final",
                source="our own numbers from saved prices (private)",
            )
            for d in sorted(used_days, reverse=True)
        }
        n_last = number_of[last]
        for cik in companies:
            company = universe.companies[cik]
            now = prices.close(company.ticker, last)
            lines = [f"Numbers worked out by script from saved prices, as of the close of {last} [{n_last}]."]
            lines.append("PRIVATE: none of these may be written into a forecast, a thesis or a reason.")
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
            if seen_then:
                then = prices.close(company.ticker, seen_then[-1])
                if then:
                    move = now / then - 1
                    lines.append(f"Change since the prices the last session saw ({seen_then[-1]}): {pct(move)}")
                    if abs(move) >= BIG_MOVE:
                        line = f"[{n_last}] the share moved {pct(move)} since the prices the last session saw"
                        items[cik].append(Item(n_last, "price move", line))
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
            listed_changes = "".join(f"- {i.line}\n" for i in trial_items)
            trials = "Changes in its trial records since the last session:\n" + listed_changes
        else:
            trials = "No change in its linked trial records since the last session.\n"
        write_new(base / "trials.md", trials)
        for name, text in files[cik]:
            write_new(base / name, text)
        report = newest_report(reports / str(cik), session_day)
        if report is not None:
            write_new(base / "report.md", veil(report.read_text(encoding="utf-8")))
    # Who is "news": a filing a company made as a holder of another company is in its folder, but does not by
    # itself send the company to the screening.
    with_news = [cik for cik in companies if any(item.kind != "holder filing" for item in items[cik])]
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
    quiet = [cik for cik in companies if cik not in set(with_news)]
    write_new(folder / "screening" / "no-news.txt", "".join(f"{cik}\n" for cik in quiet))
    text = inputs.text()
    write_new(folder / "inputs.jsonl", text)
    done.inputs_sha256 = sha256_hex(text.encode("utf-8"))
    done.items = items
    done.counts |= {
        "companies": len(companies),
        "left_out_as_private": len(universe.companies) - len(companies),
        "on_the_private_list": listed,
        "private_names_taken_out_of_texts": veiled,
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
    write_new(folder / "session.json", json.dumps(session, indent=1, sort_keys=True) + "\n")  # the last file
    folder.rename(final)  # one step: from here on the session folder exists, and it is complete
    return done


def newest_report(folder: Path, session_day: date) -> Path | None:
    """Our own newest report on a company from an EARLIER session day (a report is named after its day). A link
    is not followed, and a report of today or later is never taken: it could come from a later round."""
    if not folder.is_dir() or folder.is_symlink():
        return None
    found = []
    for path in folder.glob("*.md"):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if day < session_day and path.is_file() and not path.is_symlink():
            found.append((day, path))
    return max(found)[1] if found else None

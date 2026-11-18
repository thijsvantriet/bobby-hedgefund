"""The share counts and the universe filter. Every company, price and share count here is invented."""

from __future__ import annotations

import csv
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from test_universe import root  # noqa: F401  (the small made-up archive)

from bobby_hedgefund.archive import cli as archive_cli
from bobby_hedgefund.archive import sec, sec_shares
from bobby_hedgefund.archive.fetch import FetchError
from bobby_hedgefund.archive.sources import SourceError
from bobby_hedgefund.archive.store import Archive
from bobby_hedgefund.prices import massive
from bobby_hedgefund.universe import build, cli, read_shares
from bobby_hedgefund.universe.inputs import InputError, Inputs
from bobby_hedgefund.universe.read_sec import ReadError

LAST = date(2026, 11, 17)
CONTACT = "someone@test-host"
LOCAL = frozenset({"127.0.0.1"})


def working_days(n: int, last: date = LAST) -> list[date]:
    days: list[date] = []
    day = last
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return days[::-1]


def concept(
    cik: int, tag: str, facts: list[tuple[str, float]], *, filed: str = "2026-11-05", unit: str = "shares"
) -> bytes:
    rows = [{"end": end, "val": val, "accn": f"a-{end}", "form": "10-Q", "filed": filed} for end, val in facts]
    taxonomy = "dei" if tag.startswith("E") else "us-gaap"
    return json.dumps({"cik": cik, "tag": tag, "taxonomy": taxonomy, "units": {unit: rows}}).encode()


def store_shares(archive: Archive, cik: int, taxonomy: str, body: bytes, batch: str = "b1") -> None:
    info = {"meta": {"batch": batch, "cik": cik, "taxonomy": taxonomy}}
    archive.store(
        sec_shares.SHARES_SOURCE, sec_shares.shares_name(cik, taxonomy), body, run="s1", compress=True, info=info
    )


def finish_shares(archive: Archive, not_reported: tuple[int, ...] = (), batch: str = "b1") -> None:
    """What a finished `sec-shares` run leaves behind: a note per figure a company does not report, and the run."""
    for cik in not_reported:
        for key in sec_shares.KEYS:
            meta = {"batch": batch, "cik": cik, "taxonomy": key, "not_reported": True}
            archive.record_run(sec_shares.SHARES_SOURCE, "s1", "note", meta=meta)
    done = {"batch": batch, "complete": True, "figures": list(sec_shares.KEYS)}
    archive.record_run(sec_shares.SHARES_SOURCE, "s1", "ok", meta=done)


def store_prices(prices_root: Path, per_ticker: dict[str, tuple[float, float]], days: list[date], skip=()) -> None:
    """One price file per day: ticker -> (close, volume). `skip` holds (ticker, day) pairs without a price."""
    with Archive(prices_root) as archive:
        for day in days:
            stamp = int(datetime(day.year, day.month, day.day, 21, tzinfo=UTC).timestamp() * 1000)
            rows = [
                {"T": t, "o": c, "h": c, "l": c, "c": c, "v": v, "t": stamp}
                for t, (c, v) in per_ticker.items()
                if (t, day) not in skip
            ]
            body = json.dumps({"status": "OK", "adjusted": False, "resultsCount": len(rows), "results": rows})
            archive.store(massive.DAILY_SOURCE, massive.day_name(day), body.encode(), run="p1", compress=True)
        splits = {
            "status": "OK",
            "results": [{"ticker": "ZETA.A", "execution_date": "2026-11-10", "split_from": 10, "split_to": 1}],
        }
        archive.store(massive.SPLITS_SOURCE, "splits-p01.json", json.dumps(splits).encode(), run="p1", compress=True)
        archive.record_run(massive.SPLITS_SOURCE, "p1", "ok", meta={"pages": 1})


PRICES = {
    "ALFA": (20.0, 500_000.0),  # 50 million shares: $1 billion, $10 million a day
    "GAMA": (20.0, 500_000.0),  # 10 million shares: $200 million, too small
    "DELT": (20.0, 500_000.0),  # no share count
    "ZETA.A": (50.0, 100_000.0),  # 100 million shares before a 1-for-10 split: 10 million now, $500 million
    "THET": (1.5, 100_000.0),  # under $2, and too little traded
    "BETA": (20.0, 500_000.0),  # foreign filer
}


@pytest.fixture
def world(root: Path) -> Path:  # noqa: F811
    with Archive(root) as archive:
        store_shares(archive, 101, "dei", concept(101, "E", [("2026-06-30", 40e6), ("2026-10-31", 50e6)]))
        store_shares(archive, 101, "us-gaap", concept(101, "C", [("2026-09-30", 49e6)]))  # older: not used
        store_shares(archive, 103, "dei", concept(103, "E", [("2026-10-31", 10e6)]))
        store_shares(archive, 106, "us-gaap", concept(106, "C", [("2026-09-30", 100e6)]))  # balance sheet only
        store_shares(archive, 108, "dei", concept(108, "E", [("2026-10-31", 500e6)]))
        store_shares(archive, 102, "dei", concept(102, "E", [("2026-10-31", 50e6)]))
        finish_shares(archive, not_reported=(104,))
    store_prices(root.parent / "prices", PRICES, working_days(60))
    return root


def lines(world: Path) -> dict[int, build.Line]:
    result = build.build(Inputs(world), Inputs(world.parent / "prices"))
    return {line.candidate.cik: line for line in result.lines}


def test_the_filter_gives_every_candidate_a_line_with_every_rule_it_fails(world: Path) -> None:
    found = lines(world)
    assert set(found) == {101, 102, 103, 104, 106, 108}
    alfa = found[101]
    assert alfa.in_universe and alfa.market_value == 1e9 and alfa.avg_traded == 10e6 and alfa.days_with_prices == 60
    assert alfa.count is not None and alfa.count.source == "cover page" and alfa.count.as_of == date(2026, 10, 31)
    assert found[103].why_out == ("market value under $300 million",)
    assert found[104].why_out == ("no share count reported for the company as a whole",)
    assert found[102].why_out == ("reports as a foreign company (left out of version 1)",)
    assert found[108].why_out == (
        "under $2 million traded a day",
        "share price under $2",
    )  # value is fine: $750 million


def test_a_share_class_ticker_is_found_and_a_split_since_the_count_is_applied(world: Path) -> None:
    zeta = lines(world)[106]
    assert zeta.ticker_used == "ZETA.A" and zeta.shares == 10e6 and zeta.market_value == 500e6
    assert zeta.count is not None and zeta.count.source == "balance sheet"
    assert "share split since the report: x0.1" in zeta.shares_note and zeta.in_universe


def test_a_split_between_the_count_and_its_filing_is_not_applied_again_but_flagged(root: Path) -> None:  # noqa: F811
    with Archive(root) as archive:
        # counted on 30 September, a 1-for-10 split on 10 November, the report filed on 12 November: the company
        # restated its figure for the split, so the 10 million is already the number after it
        store_shares(archive, 106, "us-gaap", concept(106, "C", [("2026-09-30", 10e6)], filed="2026-11-12"))
        finish_shares(archive)
    store_prices(root.parent / "prices", PRICES, working_days(60))
    zeta = lines(root)[106]
    assert zeta.shares == 10e6 and zeta.market_value == 500e6
    assert zeta.shares_note == "CHECK: share split on 2026-11-10, between the count and its filing"


def test_of_several_tickers_the_one_with_the_most_trading_is_used(root: Path) -> None:  # noqa: F811
    import bobby_hedgefund.universe.candidates as candidates_module

    with Archive(root) as archive:
        store_shares(archive, 101, "dei", concept(101, "E", [("2026-10-31", 50e6)]))
        finish_shares(archive)
    prices = {**PRICES, "ALFAW": (0.5, 1_000.0)}  # a warrant of the same company, listed first by the SEC
    store_prices(root.parent / "prices", prices, working_days(60))
    real = candidates_module.build

    def with_warrant_first(inputs, **kwargs):
        result = real(inputs, **kwargs)
        result.candidates = [
            candidates_module.Candidate(**{**c.__dict__, "tickers": ("ALFAW", "ALFA")}) if c.cik == 101 else c
            for c in result.candidates
        ]
        return result

    build.candidates.build = with_warrant_first
    try:
        alfa = lines(root)[101]
    finally:
        build.candidates.build = real
    assert alfa.ticker_used == "ALFA" and alfa.priced_tickers == ("ALFAW", "ALFA") and alfa.last_close == 20.0


def test_incomplete_share_counts_are_refused_unless_asked_for(root: Path, capsys) -> None:  # noqa: F811
    with Archive(root) as archive:
        store_shares(archive, 101, "dei", concept(101, "E", [("2026-10-31", 50e6)]))
    store_prices(root.parent / "prices", PRICES, working_days(60))
    with pytest.raises(InputError, match="share counts of this batch are not complete"):
        lines(root)
    assert cli.main(["build"]) == 1 and "sec-shares" in capsys.readouterr().out
    assert cli.main(["build", "--allow-partial"]) == 0
    assert "share_counts_complete" in capsys.readouterr().out


def test_a_look_alike_ticker_gives_no_price() -> None:
    known = {"AB.C", "ABC", "ZETA.A"}
    assert build.price_ticker("AB-C", known) == "AB.C" and build.price_ticker("ZETA-A", known) == "ZETA.A"
    assert build.price_ticker("ZETAA", known) is None and build.price_ticker("AB", known) is None


def test_bounds_missing_days_and_a_share_that_stopped_trading(root: Path) -> None:  # noqa: F811
    days = working_days(60)
    with Archive(root) as archive:
        store_shares(archive, 101, "dei", concept(101, "E", [("2026-10-31", 600e6)]))  # x $20 = $12 billion
        store_shares(archive, 103, "dei", concept(103, "E", [("2026-10-31", 50e6)]))
        store_shares(archive, 106, "dei", concept(106, "E", [("2026-10-31", 50e6)]))
        finish_shares(archive)
    skip = {("GAMA", d) for d in days[:30]} | {("ZETA.A", d) for d in days[-6:]}
    prices = {**PRICES, "GAMA": (20.0, 300_000.0)}  # $6 million on 30 days of 60: $3 million a day
    store_prices(root.parent / "prices", prices, days, skip)
    found = lines(root)
    assert found[101].why_out == ("market value over $10 billion",)
    assert found[103].in_universe and found[103].avg_traded == 3e6 and found[103].days_with_prices == 30
    assert "no price in the last 5 trading days" in found[106].why_out
    assert found[106].last_close_day == days[-7]


def test_a_share_count_that_is_too_old_does_not_count(root: Path) -> None:  # noqa: F811
    with Archive(root) as archive:
        store_shares(archive, 101, "dei", concept(101, "E", [("2025-06-30", 50e6)]))
        store_shares(archive, 103, "dei", concept(103, "E", [("2026-10-31", 50e6)], unit="USD"))  # not a share count
        store_shares(archive, 106, "dei", concept(106, "E", [("2026-10-31", 50e6)]), batch="older")  # another batch
        finish_shares(archive)
    store_prices(root.parent / "prices", PRICES, working_days(60))
    found = lines(root)
    assert found[101].why_out == ("newest share count is of 2025-06-30: too old",)
    assert found[103].why_out == ("no usable share count in the SEC's answers",)
    assert "no usable share count in the SEC's answers" in found[106].why_out


def test_fewer_than_sixty_days_of_prices_is_refused(world: Path, tmp_path: Path) -> None:
    short = tmp_path / "short"
    store_prices(short, PRICES, working_days(59))
    with pytest.raises(InputError, match="60 trading days"):
        build.build(Inputs(world), Inputs(short))


def test_newest_share_count_adds_up_classes_of_one_report_and_ignores_zero() -> None:
    rows = [
        {"end": "2026-10-31", "val": 30e6, "accn": "a1", "form": "10-Q", "filed": "2026-11-05"},
        {"end": "2026-10-31", "val": 5e6, "accn": "a1", "form": "10-Q", "filed": "2026-11-05"},
        {"end": "2026-10-31", "val": 30e6, "accn": "a1", "form": "10-Q", "filed": "2026-11-05"},  # the same again
        {"end": "2026-11-30", "val": 0, "accn": "a2", "form": "10-Q", "filed": "2026-12-05"},
        {"end": "2026-07-31", "val": 99e6, "accn": "a0", "form": "10-Q", "filed": "2026-08-05"},
    ]
    count = read_shares.newest(json.dumps({"units": {"shares": rows}}).encode(), "dei")
    assert count is not None and count.shares == 35e6 and "2 figures" in count.note
    assert read_shares.newest(b'{"units": {"shares": []}}', "dei") is None
    with pytest.raises(ReadError):
        read_shares.newest(b"<html>", "dei")


def test_build_command_writes_the_universe_and_its_inputs_and_never_replaces_them(world: Path, capsys) -> None:
    assert cli.main(["build"]) == 0 and cli.main(["build"]) == 0
    folder = world.parent / "universe"
    today = date.today().isoformat()
    names = sorted(p.name for p in folder.iterdir())
    assert names == [
        f"{today}-2_universe-inputs.txt",
        f"{today}-2_universe.csv",
        f"{today}_universe-inputs.txt",
        f"{today}_universe.csv",
    ]
    rows = {r["cik"]: r for r in csv.DictReader((folder / f"{today}_universe.csv").read_text().splitlines())}
    assert rows["101"]["in_universe"] == "yes" and rows["101"]["market_value"] == "1000000000"
    assert rows["104"]["in_universe"] == "no" and rows["104"]["in_xbi"] == "yes"
    inputs = (folder / f"{today}_universe-inputs.txt").read_text()
    assert "raw/sec-shares/" in inputs and "raw/massive-daily/" in inputs and "# in_universe: 2" in inputs
    assert "in_universe" in capsys.readouterr().out


def test_build_without_prices_says_so(root: Path, capsys) -> None:  # noqa: F811
    assert cli.main(["build"]) == 1
    assert "NOT DONE" in capsys.readouterr().out


# -- fetching the share counts ----------------------------------------------------------------------------------


@pytest.fixture
def shares_site(site):
    site.url = site.base + "/concept/CIK{cik:010d}/{taxonomy}/{tag}.json"
    for _, taxonomy, tag in sec_shares.CONCEPTS:
        site.add(f"/concept/CIK0000000101/{taxonomy}/{tag}.json", {"body": concept(101, tag, [("2026-10-31", 5e7)])})
    site.add(
        "/concept/CIK0000000103/dei/EntityCommonStockSharesOutstanding.json",
        {"body": concept(103, "EntityCommonStockSharesOutstanding", [("2026-10-31", 1e7)])},
    )
    return site  # company 103 has no balance-sheet figure: the fake site answers "not found"


def fetch(archive, fetcher, site, name="r1", ciks=(103, 101, 101), **kwargs) -> dict:
    return sec_shares.run_sec_shares(
        archive, fetcher, name, ciks=list(ciks), batch="b1", concept_url=site.url, **kwargs
    )


def test_share_counts_are_stored_and_a_missing_figure_is_noted_and_not_asked_again(
    shares_site, tmp_path: Path, fetcher, waits
) -> None:
    with Archive(tmp_path) as archive:
        first = fetch(archive, fetcher, shares_site)
        again = fetch(archive, fetcher, shares_site, "r2")
        other_batch = sec_shares.run_sec_shares(
            archive, fetcher, "r3", ciks=[101], batch="b2", concept_url=shares_site.url
        )
    assert first["stored"] == 4 and first["not_found"] == 2 and first["complete"] and first["companies"] == 2
    assert again["asked"] == 0 and again["had_already"] == 6
    assert (
        waits == [1.0] * 9 and other_batch["asked"] == 3
    )  # a new batch asks again; unchanged files are not stored twice
    rows = [json.loads(x) for x in (tmp_path / "manifest.jsonl").read_text().splitlines()]
    assert sum(r["kind"] == "file" for r in rows) == 4 and sum(r["kind"] == "unchanged" for r in rows) == 3
    assert all(r["path"].startswith("raw/sec-shares/") for r in rows if r["kind"] == "file")


def test_a_strange_answer_is_not_stored_and_is_asked_again(shares_site, tmp_path: Path, fetcher) -> None:
    path = "/concept/CIK0000000103/dei/EntityCommonStockSharesOutstanding.json"
    good = shares_site.routes[path][0]
    wrong_company = {"body": concept(999, "EntityCommonStockSharesOutstanding", [])}
    wrong_figure = {"body": concept(103, "EntityCommonStockSharesOutstanding", []).replace(b'"dei"', b'"us-gaap"')}
    shares_site.add(path, wrong_company, wrong_figure, good)
    with Archive(tmp_path) as archive:
        first = fetch(archive, fetcher, shares_site)
        again = fetch(archive, fetcher, shares_site, "r2")
        third = fetch(archive, fetcher, shares_site, "r3")
    assert first["odd"] == 1 and not first["complete"] and again["odd"] == 1 and third["stored"] == 1


@pytest.mark.parametrize("status", [429, 403])
def test_a_refusal_stops_the_job_and_limit_stops_early(shares_site, tmp_path: Path, fetcher, status: int) -> None:
    with Archive(tmp_path) as archive:
        limited = fetch(archive, fetcher, shares_site, limit=1)
        assert limited["asked"] == 1 and limited["left"] == 5 and not limited["complete"]
        shares_site.add("/concept/CIK0000000101/us-gaap/CommonStockSharesOutstanding.json", {"status": status})
        with pytest.raises(FetchError):
            fetch(archive, fetcher, shares_site, "r2")
        hits = len(shares_site.hits)
        assert fetch(archive, fetcher, shares_site, "r3", keep_going=lambda: False)["asked"] == 0
    assert len(shares_site.hits) == hits


def test_many_strange_answers_in_a_row_stop_the_job(shares_site, tmp_path: Path, fetcher, monkeypatch) -> None:
    monkeypatch.setattr(sec_shares, "MAX_ODD_IN_A_ROW", 2)
    for _, taxonomy, tag in sec_shares.CONCEPTS:
        shares_site.add(f"/concept/CIK0000000101/{taxonomy}/{tag}.json", {"body": b"<html>"})
    with Archive(tmp_path) as archive, pytest.raises(SourceError):
        fetch(archive, fetcher, shares_site, ciks=[101])


def test_many_not_found_answers_in_a_row_stop_the_job_and_do_not_count(
    shares_site, tmp_path: Path, fetcher, monkeypatch
) -> None:
    monkeypatch.setattr(sec_shares, "MAX_NOT_FOUND_IN_A_ROW", 3)
    with Archive(tmp_path) as archive:
        with pytest.raises(SourceError, match="not found"):
            fetch(archive, fetcher, shares_site, ciks=[201, 202, 203])  # the fake site knows none of them
        assert sec_shares.not_reported(archive.records, "b1") == set()
        hits = len(shares_site.hits)
        with pytest.raises(SourceError):
            fetch(archive, fetcher, shares_site, "r2", ciks=[201, 202, 203])
    assert hits == 3 and len(shares_site.hits) == 6  # asked again: the first answers were not taken as final


def test_sec_shares_command_asks_for_the_candidates_of_the_newest_batch(
    root: Path,  # noqa: F811
    shares_site,
    monkeypatch,
    waits,
    capsys,
) -> None:
    monkeypatch.setattr(archive_cli, "_before_evening", lambda: True)
    monkeypatch.setattr(sec_shares, "SEC_CONCEPT_URL", shares_site.url)
    made = sec.sec_fetcher(CONTACT, allowed_hosts=LOCAL, timeout=5, backoff=(), sleep=waits.append)
    monkeypatch.setattr(archive_cli, "make_sec_fetcher", lambda: made)
    assert archive_cli.main(["sec-shares"]) == 0
    asked = {int(h.split("CIK")[1][:10]) for h in shares_site.hits}
    assert asked == {101, 102, 103, 104, 106, 108} and len(shares_site.hits) == 18
    out = capsys.readouterr().out
    assert "ok      sec-shares" in out and "test-host" not in out
    everything = b"".join(p.read_bytes() for p in root.rglob("*") if p.is_file())
    assert b"test-host" not in everything
    monkeypatch.setattr(archive_cli, "_before_evening", lambda: False)
    assert archive_cli.main(["sec-shares"]) == 1


def test_purge_replaces_universe_files_by_copies_without_the_price_columns(world: Path, capsys) -> None:
    from bobby_hedgefund.prices import cli as prices_cli

    assert cli.main(["build"]) == 0
    folder = world.parent / "universe"
    today = date.today().isoformat()
    assert prices_cli.main(["purge", "--yes-delete-everything"]) == 0
    assert "universe files: 1 replaced" in capsys.readouterr().out
    assert not (folder / f"{today}_universe.csv").exists() and not (world.parent / "prices").exists()
    rows = list(csv.DictReader((folder / f"{today}_universe-without-prices.csv").read_text().splitlines()))
    assert {r["cik"]: r["in_universe"] for r in rows}["101"] == "yes"
    assert "market_value" not in rows[0] and "last_close" not in rows[0] and "avg_traded_per_day" not in rows[0]
    assert "20.0" not in (folder / f"{today}_universe-without-prices.csv").read_text()
    assert (folder / f"{today}_universe-inputs.txt").exists() and (world / "manifest.jsonl").exists()
    assert prices_cli.main(["purge", "--yes-delete-everything"]) == 0  # nothing left to do


def test_the_average_over_a_period_is_used_only_when_no_count_on_a_day_is_usable(root: Path) -> None:  # noqa: F811
    def weighted(cik: int, rows: list[tuple[str, str, float]]) -> bytes:
        facts = [
            {"start": a, "end": b, "val": v, "accn": "a9", "form": "10-Q", "filed": "2026-11-05"} for a, b, v in rows
        ]
        doc = {"cik": cik, "tag": "W", "taxonomy": "us-gaap", "units": {"shares": facts}}
        return json.dumps(doc).encode()

    quarter_and_year_so_far = [("2026-01-01", "2026-09-30", 40e6), ("2026-07-01", "2026-09-30", 50e6)]
    with Archive(root) as archive:
        store_shares(archive, 101, "dei", concept(101, "E", [("2012-09-30", 9e6)]))  # far too old
        store_shares(archive, 101, "weighted", weighted(101, quarter_and_year_so_far))
        store_shares(archive, 103, "dei", concept(103, "E", [("2026-10-31", 50e6)]))
        store_shares(archive, 103, "weighted", weighted(103, [("2026-07-01", "2026-09-30", 1e6)]))  # not needed
        finish_shares(archive)
    store_prices(root.parent / "prices", PRICES, working_days(60))
    found = lines(root)
    alfa = found[101]
    assert alfa.in_universe and alfa.shares == 50e6 and alfa.count is not None
    assert alfa.count.source == "average over the period" and "not a count on one day" in alfa.shares_note
    assert found[103].shares == 50e6 and found[103].count is not None and found[103].count.source == "cover page"


def test_a_finished_run_from_before_a_figure_was_added_does_not_count_as_complete(root: Path) -> None:  # noqa: F811
    with Archive(root) as archive:
        old = {"batch": "b1", "complete": True}  # the first version asked for two figures and wrote no list of them
        archive.record_run(sec_shares.SHARES_SOURCE, "s0", "ok", meta=old)
        assert not sec_shares.batch_complete(archive.records, "b1")
        finish_shares(archive)
        assert sec_shares.batch_complete(archive.records, "b1")

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from bobby_hedgefund import settings
from bobby_hedgefund.archive import cli as archive_cli
from bobby_hedgefund.archive.fetch import FetchError
from bobby_hedgefund.archive.sources import SourceError
from bobby_hedgefund.archive.store import Archive
from bobby_hedgefund.prices import check, cli, holidays, massive, purge, read
from bobby_hedgefund.universe.inputs import InputError, Inputs

# All tickers and prices here are made up. KEY is a made-up key; tests check that it is stored and shown nowhere.
KEY = "made-up-key-0123456789"
LOCAL = frozenset({"127.0.0.1"})
TODAY = date(2026, 11, 18)  # a Wednesday
MON, TUE = date(2026, 11, 16), date(2026, 11, 17)


def close_ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, 21, 0, tzinfo=UTC).timestamp() * 1000)  # 16:00 in New York


def day_body(day: date, prices: dict[str, float] | None = None, *, adjusted: bool = False, status: str = "OK") -> bytes:
    prices = {"AAA": 10.0, "BBB": 4.0} if prices is None else prices
    rows = [
        {"T": t, "o": c, "h": c + 1, "l": c - 1, "c": c, "v": 1000, "vw": c, "n": 5, "t": close_ms(day)}
        for t, c in prices.items()
    ]
    doc: dict = {"status": status, "adjusted": adjusted, "queryCount": len(rows), "resultsCount": len(rows)}
    if rows:
        doc["results"] = rows
    return json.dumps(doc).encode()


def splits_body(rows: list[tuple[str, str, int, int]], next_url: str | None = None) -> bytes:
    doc: dict = {
        "status": "OK",
        "results": [{"ticker": t, "execution_date": d, "split_from": a, "split_to": b} for t, d, a, b in rows],
    }
    if next_url:
        doc["next_url"] = next_url
    return json.dumps(doc).encode()


def manifest(root: Path) -> list[dict]:
    return [json.loads(x) for x in (root / "manifest.jsonl").read_text().splitlines()]


@pytest.fixture
def key_fetcher(waits):
    return massive.massive_fetcher(
        KEY, allowed_hosts=LOCAL, https_only=False, timeout=5, backoff=(), sleep=waits.append
    )


@pytest.fixture
def price_site(site):
    site.add("/day/2026-11-16", {"body": day_body(MON)})
    site.add("/day/2026-11-17", {"body": day_body(TUE, {"AAA": 11.0, "BBB": 1.0})})
    site.add("/splits", {"body": splits_body([("CCC", "2026-11-17", 10, 1)])})
    site.day_url = site.base + "/day/{day}?adjusted=false"
    site.splits_url = site.base + "/splits?execution_date.gte={start}"
    return site


def run_days(archive, fetcher, site, name="r1", **kwargs) -> dict:
    kwargs.setdefault("start", MON)
    kwargs.setdefault("end", TUE)
    return massive.run_days(archive, fetcher, name, today=TODAY, url=site.day_url, **kwargs)


def test_stores_each_missing_day_as_received_with_a_pause_before_every_request(
    price_site, tmp_path: Path, key_fetcher, waits
) -> None:
    with Archive(tmp_path) as archive:
        new: list[date] = []
        summary = run_days(archive, key_fetcher, price_site, stored_now=new)
        again = run_days(archive, key_fetcher, price_site, "r2")
    assert summary["stored"] == 2 and summary["complete"] and new == [MON, TUE]
    assert again["asked"] == 0 and again["had_already"] == 2  # nothing is fetched twice
    assert waits == [13.0, 13.0] and len(price_site.hits) == 2
    rows = manifest(tmp_path)
    assert [r["name"] for r in rows] == ["grouped-2026-11-16.json", "grouped-2026-11-17.json"]
    assert all(r["path"].startswith("raw/massive-daily/") and r["compress"] == "xz" for r in rows)
    with Archive(tmp_path, readonly=True) as archive:
        assert archive.read(rows[0]) == day_body(MON)
        assert archive.verify().ok


def test_weekends_are_not_asked_for(price_site, tmp_path: Path, key_fetcher) -> None:
    with Archive(tmp_path) as archive:
        run_days(archive, key_fetcher, price_site, start=date(2026, 11, 14), end=TUE)
    assert [h.split("?")[0] for h in price_site.hits] == ["/day/2026-11-16", "/day/2026-11-17"]


def test_the_key_goes_in_a_header_and_is_stored_and_shown_nowhere(
    price_site, tmp_path: Path, key_fetcher, capsys
) -> None:
    price_site.add("/day/2026-11-17", {"status": 403, "body": b'{"status":"NOT_AUTHORIZED"}'})
    with Archive(tmp_path) as archive:
        ok = archive_cli._attempt(
            archive, massive.DAILY_SOURCE, "r1", lambda: run_days(archive, key_fetcher, price_site)
        )

        def broken() -> dict:
            raise RuntimeError(f"a bug that mentions the fetcher: {key_fetcher!r}")

        assert not archive_cli._attempt(archive, massive.DAILY_SOURCE, "r2", broken)
    assert not ok  # a refusal on a recent day is a failure, not "outside the history"
    assert set(price_site.authorizations) == {f"Bearer {KEY}"}
    assert set(price_site.user_agents) == {"public-data-archiver/0.1"}
    everything = b"".join(p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
    out = capsys.readouterr()
    assert KEY.encode() not in everything and KEY not in out.out + out.err and KEY not in repr(key_fetcher)
    assert all(KEY not in hit for hit in price_site.hits)


def test_the_key_never_travels_to_another_host(price_site, tmp_path: Path, key_fetcher) -> None:
    elsewhere = price_site.base.replace("127.0.0.1", "localhost")
    price_site.add("/day/2026-11-16", {"status": 302, "headers": {"Location": elsewhere + "/day/2026-11-17"}})
    with Archive(tmp_path) as archive, pytest.raises(FetchError):
        run_days(archive, key_fetcher, price_site)
    assert len(price_site.hits) == 1
    assert massive.massive_fetcher(KEY).allowed_hosts == {"api.massive.com"}


def test_too_many_requests_stops_the_job_and_running_again_continues(price_site, tmp_path: Path, key_fetcher) -> None:
    price_site.add("/day/2026-11-17", {"status": 429, "body": b"slow down"}, {"body": day_body(TUE)})
    with Archive(tmp_path) as archive:
        with pytest.raises(FetchError):
            run_days(archive, key_fetcher, price_site)
        assert len(price_site.hits) == 2  # no quick second try
        assert run_days(archive, key_fetcher, price_site, "r2")["stored"] == 1
    assert massive.stored_days(manifest(tmp_path)) == {MON, TUE}


def test_limit_and_keep_going_stop_before_the_next_request(price_site, tmp_path: Path, key_fetcher) -> None:
    with Archive(tmp_path) as archive:
        first = run_days(archive, key_fetcher, price_site, limit=1)
        none = run_days(archive, key_fetcher, price_site, "r2", keep_going=lambda: False)
    assert first["stored"] == 1 and first["left"] == 1 and not first["complete"]
    assert none["asked"] == 0 and len(price_site.hits) == 1


def test_a_day_without_prices_is_settled_only_when_it_is_old_and_a_holiday_or_empty_twice(
    price_site, tmp_path: Path, key_fetcher
) -> None:
    holiday, odd = date(2026, 9, 7), date(2026, 9, 9)  # Labor Day, and an ordinary Wednesday
    for day in (holiday, odd, TUE):
        price_site.add(f"/day/{day.isoformat()}", {"body": day_body(day, {})})
    price_site.add("/day/2026-09-08", {"body": day_body(date(2026, 9, 8))})
    with Archive(tmp_path) as archive:
        first = run_days(archive, key_fetcher, price_site, start=holiday, end=holiday)
        assert first["no_prices"] == 1 and first["complete"]  # a regular holiday: one empty answer settles it
        one = run_days(archive, key_fetcher, price_site, "r2", start=odd, end=odd)
        assert one["no_prices"] == 1 and not one["complete"]  # could be a hiccup of the service: asked once more
        two = run_days(archive, key_fetcher, price_site, "r3", start=odd, end=odd)
        assert two["asked"] == 1 and two["complete"]
        assert run_days(archive, key_fetcher, price_site, "r4", start=holiday, end=odd)["asked"] == 1  # the 8th
        recent = run_days(archive, key_fetcher, price_site, "r5", start=TUE, end=TUE)
        again = run_days(archive, key_fetcher, price_site, "r6", start=TUE, end=TUE)
        assert not recent["complete"] and again["asked"] == 1 and not again["complete"]  # yesterday: never settled
        records = archive.records
    assert massive.closed_days(records, TODAY) == {holiday, odd}
    assert massive.unexpected_closed_days(records, TODAY) == [odd]
    assert massive.closed_days(records, date(2026, 9, 10)) == set()  # too fresh to be settled


def test_a_copy_the_service_marks_delayed_is_stored_and_the_final_copy_is_fetched_later(
    price_site, tmp_path: Path, key_fetcher
) -> None:
    late = {"body": day_body(TUE, {"AAA": 11.0, "BBB": 1.0}, status="DELAYED")}
    price_site.add("/day/2026-11-17", late, late, {"body": day_body(TUE, {"AAA": 11.5, "BBB": 1.0})})
    with Archive(tmp_path) as archive:
        new: list[date] = []
        first = run_days(archive, key_fetcher, price_site, stored_now=new)
        assert (
            first["stored"] == 2 and first["of_which_marked_delayed"] == 1 and first["complete"] and new == [MON, TUE]
        )
        assert massive.stored_days(archive.records, final_only=True) == {MON}
        second = run_days(archive, key_fetcher, price_site, "r2")  # still delayed: asked again
        third = run_days(archive, key_fetcher, price_site, "r3")  # now final
        fourth = run_days(archive, key_fetcher, price_site, "r4")
        assert (second["asked"], third["asked"], fourth["asked"]) == (1, 1, 0)
        assert massive.stored_days(archive.records, final_only=True) == {MON, TUE}
    inputs = Inputs(tmp_path)
    assert read.load_day(inputs, read.day_records(inputs)[TUE])["AAA"].close == 11.5  # readers take the newest copy
    with Archive(tmp_path) as archive:
        # a delayed copy that never became final is left alone once the day is old
        archive.store(
            massive.DAILY_SOURCE,
            massive.day_name(date(2026, 11, 2)),
            b"x",
            run="m",
            info={"meta": {"service_status": "DELAYED"}},
        )
        old = run_days(archive, key_fetcher, price_site, "r5", start=date(2026, 11, 2), end=date(2026, 11, 2))
    assert old["asked"] == 0


def test_the_regular_market_holidays_are_worked_out_by_rule() -> None:
    assert sorted(d.isoformat() for d in holidays.regular_holidays(2026)) == [
        "2026-01-01",
        "2026-01-19",
        "2026-02-16",
        "2026-04-03",
        "2026-05-25",
        "2026-06-19",
        "2026-07-03",  # the 4th of July is a Saturday
        "2026-09-07",
        "2026-11-26",
        "2026-12-25",
    ]
    assert date(2027, 12, 24) in holidays.regular_holidays(2027)  # Christmas on a Saturday
    assert date(2021, 12, 31) not in holidays.regular_holidays(2022)  # New Year on a Saturday is not made up for
    assert date(2023, 1, 2) in holidays.regular_holidays(2023)  # New Year on a Sunday


def test_a_wrong_answer_for_one_day_does_not_block_the_days_after_it(price_site, tmp_path: Path, key_fetcher) -> None:
    price_site.add("/day/2026-11-16", {"body": b"<html>odd</html>"})
    price_site.add("/day/2026-11-13", {"status": 404, "body": b"gone"})
    new: list[date] = []
    with Archive(tmp_path) as archive:
        with pytest.raises(SourceError, match="wrong answer for 2 day"):
            run_days(archive, key_fetcher, price_site, start=date(2026, 11, 13), end=TUE, stored_now=new)
        assert new == [TUE]  # the later day was stored, and the caller knows it although the run failed
        notes = [r["meta"]["failed_day"] for r in archive.records if "failed_day" in (r.get("meta") or {})]
    assert notes == ["2026-11-13", "2026-11-16"]


def test_a_recent_day_with_far_too_few_shares_is_asked_again_and_an_old_one_is_stored_and_marked(
    price_site, tmp_path: Path, key_fetcher
) -> None:
    full = {f"T{i:02d}": 5.0 for i in range(10)}
    days = [date(2026, 11, d) for d in (9, 10, 11, 12, 13)]
    for day in days:
        price_site.add(f"/day/{day.isoformat()}", {"body": day_body(day, full)})
    price_site.add("/day/2026-11-16", {"body": day_body(MON, {"T00": 5.0, "T01": 5.0})})
    price_site.add(
        "/day/2026-11-17", {"body": day_body(TUE, dict(list(full.items())[:7]))}, {"body": day_body(TUE, full)}
    )
    with Archive(tmp_path) as archive:
        first = run_days(archive, key_fetcher, price_site, start=days[0], end=TUE)
        assert first["stored"] == 5 and first["too_few_shares_asked_again_later"] == 2 and not first["complete"]
        later = date(2026, 11, 25)  # MON is old by now: stored as it is, marked; TUE has filled up meanwhile
        second = massive.run_days(
            archive, key_fetcher, "r2", start=days[0], end=TUE, today=later, url=price_site.day_url
        )
        assert second["stored"] == 2 and second["complete"]
        metas = {r["meta"]["day"]: r["meta"] for r in archive.records if r.get("kind") == "file"}
    assert metas["2026-11-16"] == {"day": "2026-11-16", "shares": 2, "thin": True}
    assert metas["2026-11-17"] == {"day": "2026-11-17", "shares": 10}


def test_a_refusal_at_the_old_edge_of_the_history_is_noted_and_not_asked_again(
    price_site, tmp_path: Path, key_fetcher
) -> None:
    edge = date(2024, 11, 19)  # two years back: the service may refuse it
    price_site.add("/day/2024-11-19", {"status": 403, "body": b"{}"})
    with Archive(tmp_path) as archive:
        first = run_days(archive, key_fetcher, price_site, start=edge, end=edge)
        again = run_days(archive, key_fetcher, price_site, "r2", start=edge, end=edge)
    assert first["outside_history"] == 1 and again["asked"] == 0


@pytest.mark.parametrize(
    "body",
    [
        b"<html>blocked</html>",
        b"{}",
        b'{"status":"ERROR"}',
        day_body(MON, status="NOT_AUTHORIZED"),
        day_body(MON, adjusted=True),  # recalculated prices are never stored
        day_body(TUE),  # the prices of another day
        json.dumps({"status": "OK", "adjusted": False, "resultsCount": 5, "results": []}).encode(),
        json.dumps({"status": "OK", "adjusted": False, "resultsCount": 1, "results": [{"c": 1, "t": 1}]}).encode(),
    ],
)
def test_a_wrong_answer_is_never_stored(price_site, tmp_path: Path, key_fetcher, body: bytes) -> None:
    price_site.add("/day/2026-11-16", {"body": body})
    with Archive(tmp_path) as archive, pytest.raises(SourceError):
        run_days(archive, key_fetcher, price_site, start=MON, end=MON)
    assert not (tmp_path / "raw").exists()


def test_splits_are_stored_page_by_page_and_read_back_from_the_newest_complete_run(
    price_site, tmp_path: Path, key_fetcher
) -> None:
    price_site.add("/splits", {"body": splits_body([("CCC", "2026-11-17", 10, 1)], price_site.base + "/splits2")})
    price_site.add("/splits2", {"body": splits_body([("DDD", "2026-12-01", 1, 4)])})
    with Archive(tmp_path) as archive:
        summary = massive.run_splits(archive, key_fetcher, "r1", start=MON, url=price_site.splits_url)
        archive.record_run(massive.SPLITS_SOURCE, "r1", "ok", meta=summary)
        # a later run that broke off after its first page is not used
        archive.store(massive.SPLITS_SOURCE, "splits-p01.json", splits_body([]), run="r2", compress=True)
    assert summary == {"from": "2026-11-16", "pages": 2, "splits": 2}
    found = read.load_splits(Inputs(tmp_path))
    assert [(s.ticker, s.day, s.split_from, s.split_to) for s in found] == [
        ("CCC", TUE, 10.0, 1.0),
        ("DDD", date(2026, 12, 1), 1.0, 4.0),
    ]


def test_a_next_page_on_another_host_or_with_a_key_in_it_is_not_fetched(
    price_site, tmp_path: Path, key_fetcher
) -> None:
    elsewhere = price_site.base.replace("127.0.0.1", "localhost")
    for bad in (elsewhere + "/splits2", price_site.base + "/splits2?apiKey=x", price_site.base + f"/splits2?t={KEY}"):
        price_site.add("/splits", {"body": splits_body([], bad)})
        with Archive(tmp_path) as archive, pytest.raises((FetchError, SourceError)):
            massive.run_splits(archive, key_fetcher, "r1", start=MON, url=price_site.splits_url)
    assert all(h.startswith("/splits?") for h in price_site.hits)


def test_the_real_fetcher_only_asks_encrypted_addresses(waits) -> None:
    real = massive.massive_fetcher(KEY, sleep=waits.append)
    assert real.https_only and real.allowed_hosts == {"api.massive.com"}
    with pytest.raises(FetchError, match="encrypted"):
        real.get("http://api.massive.com/stocks/v1/splits")  # refused before anything is sent


def test_an_unchanged_split_list_is_read_from_the_lines_that_point_to_the_stored_pages(
    price_site, tmp_path: Path, key_fetcher
) -> None:
    with Archive(tmp_path) as archive:
        for run in ("r1", "r2"):
            summary = massive.run_splits(archive, key_fetcher, run, start=MON, url=price_site.splits_url)
            archive.record_run(massive.SPLITS_SOURCE, run, "ok", meta=summary)
        assert sum(r["kind"] == "file" for r in archive.records) == 1  # the second run stored nothing new
    assert [s.ticker for s in read.load_splits(Inputs(tmp_path))] == ["CCC"]


@pytest.mark.parametrize("body", [b"[]", b'{"status":"OK","results":[{"ticker":"A"}]}', b'{"status":"OK","results":7}'])
def test_a_wrong_split_list_is_never_stored(price_site, tmp_path: Path, key_fetcher, body: bytes) -> None:
    price_site.add("/splits", {"body": body})
    with Archive(tmp_path) as archive, pytest.raises(SourceError):
        massive.run_splits(archive, key_fetcher, "r1", start=MON, url=price_site.splits_url)
    assert not (tmp_path / "raw").exists()


def test_reading_checks_the_fingerprint(price_site, tmp_path: Path, key_fetcher) -> None:
    with Archive(tmp_path) as archive:
        run_days(archive, key_fetcher, price_site)
    inputs = Inputs(tmp_path)
    records = read.day_records(inputs)
    assert list(records) == [MON, TUE]
    bars = read.load_day(inputs, records[TUE])
    assert bars["AAA"] == read.Bar(11.0, 12.0, 10.0, 11.0, 1000.0)
    stored = tmp_path / records[MON]["path"]
    stored.chmod(0o600)
    stored.write_bytes(stored.read_bytes()[:-5] + b"xxxxx")
    with pytest.raises(InputError):
        read.load_day(inputs, records[MON])
    with pytest.raises(InputError, match="no complete list"):
        read.load_splits(inputs)


def test_jumps_lists_moves_of_more_than_half_and_leaves_out_split_days() -> None:
    def bar(close: float) -> read.Bar:
        return read.Bar(close, close, close, close, 100.0)

    before = {"UP": bar(10), "DOWN": bar(10), "CALM": bar(10), "SPLIT": bar(10), "ZERO": bar(0), "GONE": bar(5)}
    now = {"UP": bar(16), "DOWN": bar(4.9), "CALM": bar(14.9), "SPLIT": bar(1), "ZERO": bar(3), "NEW": bar(5)}
    splits = [read.Split("SPLIT", TUE, 10, 1), read.Split("UP", MON, 1, 2)]  # UP's split was on the day before
    rows = check.jumps(TUE, MON, now, before, splits)
    assert [(r[2], r[5]) for r in rows] == [("DOWN", -51.0), ("UP", 60.0)]


@pytest.fixture
def command(price_site, tmp_path: Path, monkeypatch, key_fetcher):
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(cli, "make_fetcher", lambda: key_fetcher)
    monkeypatch.setattr(massive, "market_today", lambda: TODAY)
    monkeypatch.setattr(massive, "DAILY_URL", price_site.day_url)
    monkeypatch.setattr(massive, "SPLITS_URL", price_site.splits_url)
    for day in range(4, 14):  # the other working days of the last two weeks: market closed
        price_site.add(f"/day/2026-11-{day:02d}", {"body": day_body(date(2026, 11, day), {})})
    return tmp_path / "data"


def test_daily_command_stores_days_and_splits_and_writes_the_jump_list(command: Path, capsys) -> None:
    assert cli.main(["daily"]) == 0
    out = capsys.readouterr().out
    assert "ok      massive-daily" in out and "ok      massive-splits" in out
    files = list((command / "prices" / "checks").glob("*_jumps.csv"))
    assert len(files) == 1
    lines = files[0].read_text().splitlines()
    assert lines[0].startswith("day,previous_day,ticker") and len(lines) == 2 and ",BBB," in lines[1]
    assert cli.main(["daily"]) == 0  # nothing new: no second list
    assert len(list((command / "prices" / "checks").glob("*_jumps.csv"))) == 1
    assert cli.main(["check", "--all"]) == 0 and cli.main(["verify"]) == 0 and cli.main(["status"]) == 0
    assert "days stored: 2, from 2026-11-16 to 2026-11-17" in capsys.readouterr().out
    assert oct((command / "prices").stat().st_mode & 0o777) == "0o700"


def test_daily_reports_failure_when_the_service_fails_but_still_checks_the_days_it_stored(
    command: Path, price_site, capsys
) -> None:
    price_site.add("/day/2026-11-17", {"status": 500, "body": b"oops"})
    assert cli.main(["daily"]) == 1
    out = capsys.readouterr().out
    assert "FAILED  massive-daily" in out and "ok      massive-splits" in out
    assert "check: no day to compare" in out  # the one day that was stored went to the check
    price_site.add("/day/2026-11-17", {"body": day_body(TUE, {"AAA": 11.0, "BBB": 1.0})})
    assert cli.main(["daily"]) == 0
    assert "1 day(s) compared, 1 closing prices moved" in capsys.readouterr().out


def test_a_day_stored_late_also_gets_the_day_after_it_compared_again(command: Path, price_site, capsys) -> None:
    price_site.add("/day/2026-11-16", {"status": 404}, {"body": day_body(MON)})
    price_site.add("/day/2026-11-13", {"body": day_body(date(2026, 11, 13), {"AAA": 10.0, "BBB": 1.0})})
    assert cli.main(["daily"]) == 1  # Friday and Tuesday stored, Monday failed
    assert "1 day(s) compared, 0 closing" in capsys.readouterr().out  # Tuesday against Friday
    assert cli.main(["daily"]) == 0  # Monday arrives: Monday and Tuesday are both compared
    assert "2 day(s) compared, 2 closing" in capsys.readouterr().out


def test_backfill_with_a_limit_stops_early_and_fetches_no_splits(command: Path, price_site, capsys) -> None:
    price_site.add("/day/2024-11-18", {"body": day_body(date(2024, 11, 18))})
    assert cli.main(["backfill", "--limit", "1"]) == 0
    out = capsys.readouterr().out
    assert "'asked': 1" in out and "massive-splits" not in out


def test_status_names_what_is_missing_and_check_takes_a_number_of_days(command: Path, price_site, capsys) -> None:
    price_site.add("/day/2026-11-16", {"status": 404})
    assert cli.main(["daily"]) == 1 and cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "days stored: 1, from 2026-11-17 to 2026-11-17" in out
    assert cli.main(["check", "--days", "3"]) == 0
    assert "no day to compare" in capsys.readouterr().out


def test_without_a_key_no_request_is_sent(command: Path, price_site, monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.undo()
    monkeypatch.setenv("BOBBY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BOBBY_ENV_FILE", str(tmp_path / "no-such-file"))
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    assert cli.main(["daily"]) == 1 and cli.main(["backfill", "--limit", "1"]) == 1
    assert "MASSIVE_API_KEY" in capsys.readouterr().out and price_site.hits == []


def test_a_key_with_a_space_or_line_break_is_refused_without_showing_it(monkeypatch) -> None:
    monkeypatch.setenv("MASSIVE_API_KEY", "abc def")
    with pytest.raises(settings.SettingsError) as caught:
        settings.massive_key()
    assert "abc" not in str(caught.value)


def test_purge_needs_its_flag_and_then_removes_only_the_prices_folder(command: Path, capsys) -> None:
    assert cli.main(["daily"]) == 0
    other = command / "archive" / "raw" / "keep.txt"
    other.parent.mkdir(parents=True)
    other.write_text("stays")
    assert cli.main(["purge"]) == 1 and (command / "prices" / "manifest.jsonl").exists()
    capsys.readouterr()
    assert cli.main(["purge", "--yes-delete-everything"]) == 0
    assert not (command / "prices").exists() and other.read_text() == "stays"
    notes = list((command / "purged").glob("*_prices.txt"))
    assert len(notes) == 1
    text = notes[0].read_text()
    assert "raw/massive-daily/" in text and "10.0" not in text  # paths and fingerprints, no prices
    assert cli.main(["purge", "--yes-delete-everything"]) == 0
    assert "nothing to delete" in capsys.readouterr().out
    assert [p.name for p in command.iterdir() if p.name.startswith(".prices")] == []


def test_an_interrupted_purge_is_finished_by_running_it_again(command: Path, monkeypatch, capsys) -> None:
    assert cli.main(["daily"]) == 0
    real = purge.shutil.rmtree

    def breaks(path, *args, **kwargs):
        raise PermissionError("no")

    monkeypatch.setattr(purge.shutil, "rmtree", breaks)
    assert cli.main(["purge", "--yes-delete-everything"]) == 1
    assert "run the purge again" in capsys.readouterr().out
    assert not (command / "prices").exists()  # set aside in one step: a new download would start an empty folder
    assert len(list(command.glob(".prices-purging-*"))) == 1
    monkeypatch.setattr(purge.shutil, "rmtree", real)
    assert cli.main(["purge", "--yes-delete-everything"]) == 0
    assert list(command.glob(".prices-purging-*")) == []


def test_purge_refuses_a_prices_folder_that_is_a_link_and_does_not_follow_links_inside(tmp_path: Path) -> None:
    data, outside = tmp_path / "data", tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("stays")
    data.mkdir()
    (data / "prices").symlink_to(outside)
    with pytest.raises(purge.PurgeError):
        purge.purge(data)
    assert (outside / "precious.txt").exists()
    (data / "prices").unlink()
    (data / "prices").mkdir()
    (data / "prices" / "link").symlink_to(outside)
    purge.purge(data)
    assert not (data / "prices").exists() and (outside / "precious.txt").read_text() == "stays"


def test_purge_does_not_run_while_a_download_holds_the_lock(command: Path, capsys) -> None:
    assert cli.main(["daily"]) == 0
    with Archive(command / "prices"):
        assert cli.main(["purge", "--yes-delete-everything"]) == 1
    assert (command / "prices" / "manifest.jsonl").exists() and not (command / "purged").exists()

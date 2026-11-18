"""Look for prices that cannot be right (docs/decisions/0007, point 5): there is no second price source, so each
day is compared with the day before. A closing price that moved by more than half without a share split is put on
a list for a look. Real moves of that size exist (trial results); the list is a prompt to look, not an error."""

from __future__ import annotations

from datetime import date

from .read import Bar, Split

JUMP = 0.5
HEADER = ("day", "previous_day", "ticker", "previous_close", "close", "change_pct", "volume", "traded_value")


def jumps(
    day: date, previous_day: date, bars: dict[str, Bar], previous: dict[str, Bar], splits: list[Split]
) -> list[tuple[object, ...]]:
    """One line per share whose closing price moved by more than half since the previous stored day, leaving out
    shares with a split on a day after `previous_day` up to and including `day`."""
    split_now = {s.ticker for s in splits if previous_day < s.day <= day}
    rows: list[tuple[object, ...]] = []
    for ticker in sorted(bars.keys() & previous.keys()):
        before, now = previous[ticker].close, bars[ticker].close
        if before <= 0 or ticker in split_now:
            continue
        change = now / before - 1
        if abs(change) > JUMP:
            rows.append(
                (
                    day.isoformat(),
                    previous_day.isoformat(),
                    ticker,
                    before,
                    now,
                    round(change * 100, 1),
                    bars[ticker].volume,
                    round(now * bars[ticker].volume),
                )
            )
    return rows

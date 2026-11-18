"""The regular holidays of the US stock market, worked out by rule. Used to tell an expected day without prices
from an unexpected one. Not complete on purpose: the market also closes on rare special days (a day of mourning,
a storm), and those cannot be known in advance."""

from __future__ import annotations

from datetime import date, timedelta


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_monday(year: int, month: int) -> date:
    day = date(year, month + 1, 1) - timedelta(days=1)
    return day - timedelta(days=day.weekday())


def _easter(year: int) -> date:
    # The usual calculation for the Gregorian calendar ("anonymous algorithm").
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    j, k = c // 4, c % 4
    m = (a + 11 * h) // 319
    r = (2 * e + 2 * j - k - h + m + 32) % 7
    month = (h - m + r + 90) // 25
    return date(year, month, (h - m + r + month + 19) % 32)


def _observed(day: date, *, saturday_moves: bool = True) -> date | None:
    """A holiday on a Sunday is kept on the Monday; one on a Saturday on the Friday before."""
    if day.weekday() == 6:
        return day + timedelta(days=1)
    if day.weekday() == 5:
        return day - timedelta(days=1) if saturday_moves else None
    return day


def regular_holidays(year: int) -> set[date]:
    days = {
        _observed(date(year, 1, 1), saturday_moves=False),  # New Year's Day on a Saturday is not made up for
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _easter(year) - timedelta(days=2),  # Good Friday
        _last_monday(year, 5),  # Memorial Day
        _observed(date(year, 6, 19)),  # Juneteenth
        _observed(date(year, 7, 4)),  # Independence Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),  # Christmas
    }
    return {d for d in days if d is not None}


def is_regular_holiday(day: date) -> bool:
    return day in regular_holidays(day.year)

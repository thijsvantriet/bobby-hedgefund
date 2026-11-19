"""US trading days and the fill day of a decision (docs/decisions/0003, points 4 and 5).

The days the New York Stock Exchange is closed are a hand-made list, copied from the exchange's own page
(https://www.nyse.com/markets/hours-calendars, read 2026-11-18). A test compares it with the holidays worked out
by rule in `prices/holidays.py` and with the open-source library `exchange_calendars`; the library is used for
that test only. An unplanned closure (a day of mourning, a storm) is not in the list: the booking notices it
because the day has no prices, and moves the fill to the next day that has (the safety net of point 5).

Days that close early (13:00) still open at 09:30, so they need no entry here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
AMSTERDAM = ZoneInfo("Europe/Amsterdam")
OPENING = time(9, 30)
PUBLISHED_BEFORE_OPEN = timedelta(minutes=30)
LATE_SESSION_HOUR = 14  # a session started at or after 14:00 Amsterdam time never gets its own day's opening price

CLOSED = {
    2026: (
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 4, 3),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
    ),
    2027: (
        date(2027, 1, 1),
        date(2027, 1, 18),
        date(2027, 2, 15),
        date(2027, 3, 26),
        date(2027, 5, 31),
        date(2027, 6, 18),
        date(2027, 7, 5),
        date(2027, 9, 6),
        date(2027, 11, 25),
        date(2027, 12, 24),
    ),
}


class CalendarError(Exception):
    pass


def is_trading_day(day: date) -> bool:
    """Is the exchange open on this day, as far as the list knows? Raises for a year the list does not cover."""
    if day.year not in CLOSED:
        raise CalendarError(
            f"the list of closed days has no year {day.year}; extend it from the exchange's page (funds/calendar.py)"
        )
    return day.weekday() < 5 and day not in CLOSED[day.year]


def next_trading_day(day: date) -> date:
    """The first trading day after `day`."""
    day += timedelta(days=1)
    while not is_trading_day(day):
        day += timedelta(days=1)
    return day


def trading_days(start: date, end: date) -> list[date]:
    """The trading days from `start` to `end`, both included."""
    out: list[date] = []
    day = start
    while day <= end:
        if is_trading_day(day):
            out.append(day)
        day += timedelta(days=1)
    return out


def opening(day: date) -> datetime:
    """The moment the market opens on `day`: 09:30 New York time, as a UTC time. Converted with the time-zone data
    that comes with Python, so the weeks in which the clocks differ are right by themselves."""
    return datetime.combine(day, OPENING, tzinfo=NEW_YORK).astimezone(UTC)


def fill_day(received: datetime, session_start: datetime) -> date:
    """The one sentence of record 0003: the first US trading day whose opening is at least 30 minutes after GitHub
    received the publication; and for a session started at or after 14:00 Amsterdam time, never the day of the
    session itself."""
    if received.tzinfo is None or session_start.tzinfo is None:
        raise CalendarError("times must carry their time zone")
    earliest = received.astimezone(UTC) + PUBLISHED_BEFORE_OPEN
    day = earliest.astimezone(NEW_YORK).date()
    local_start = session_start.astimezone(AMSTERDAM)
    while True:
        too_late = local_start.hour >= LATE_SESSION_HOUR and day <= local_start.date()
        if is_trading_day(day) and opening(day) >= earliest and not too_late:
            return day
        day += timedelta(days=1)

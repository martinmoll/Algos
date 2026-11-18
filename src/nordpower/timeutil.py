"""All time arithmetic lives here. Stored instants are UTC; market rules are Nordic local time."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import polars as pl

MARKET_TZ = ZoneInfo("Europe/Oslo")  # shared by every Nordic bidding zone (CET/CEST)
HOUR = timedelta(hours=1)
DA_GATE_CLOSURE = time(12, 0)  # local, on D-1
DA_DECISION_MARGIN = timedelta(minutes=30)  # D-008: decide 30 min before gate closure
# Day-ahead market time unit by delivery day (D-032): 15 minutes from 2025-10-01.
DA_15MIN_FROM = date(2025, 10, 1)
RESOLUTION = {"PT60M": HOUR, "PT15M": timedelta(minutes=15)}


def local_instant(d: date, t: time) -> datetime:
    """UTC instant of local market time `t` on day `d`."""
    return datetime.combine(d, t, tzinfo=MARKET_TZ).astimezone(UTC)


def da_gate_closure(delivery_day: date) -> datetime:
    """Instant (UTC) of the day-ahead gate closure for `delivery_day`: 12:00 local on D-1."""
    return local_instant(delivery_day - timedelta(days=1), DA_GATE_CLOSURE)


def decision_cutoff(delivery_day: date) -> datetime:
    """Instant (UTC) at which day-ahead decisions for `delivery_day` are made: 11:30 local D-1.
    No clock change ever falls between 11:30 and 12:00, so UTC and wall-clock margins agree."""
    return da_gate_closure(delivery_day) - DA_DECISION_MARGIN


def local_time_on_day_before_delivery(event_time: datetime, at: time) -> datetime:
    """UTC instant of local time `at` on the day before `event_time`'s delivery day."""
    return local_instant(delivery_day_of(event_time) - timedelta(days=1), at)


def delivery_span(first: date, last: date) -> tuple[datetime, datetime]:
    """[start, end) in UTC covering delivery days first..last."""
    return local_instant(first, time(0)), local_instant(last + timedelta(days=1), time(0))


def mtus_of(delivery_day: date, resolution: timedelta) -> list[datetime]:
    """UTC start of each MTU of the delivery day; DST days have 23 or 25 hours of them."""
    start, end = delivery_span(delivery_day, delivery_day)
    return [start + i * resolution for i in range((end - start) // resolution)]


def da_resolution(delivery_day: date) -> str:
    """Day-ahead MTU of the delivery day, as an ISO 8601 duration code."""
    return "PT15M" if delivery_day >= DA_15MIN_FROM else "PT60M"


def da_mtus(delivery_day: date) -> list[datetime]:
    """UTC start of each day-ahead MTU of the delivery day."""
    return mtus_of(delivery_day, RESOLUTION[da_resolution(delivery_day)])


def hours_of(delivery_day: date) -> list[datetime]:
    """UTC start of each hour of the delivery day (23/24/25 hours)."""
    return mtus_of(delivery_day, HOUR)


def hour_start(instants: pl.Expr) -> pl.Expr:
    """Start of the hour containing each UTC instant. Truncating in UTC gives the local hour
    too, because Europe/Oslo offsets from UTC are whole hours."""
    return instants.dt.truncate("1h")


def local_clock_hour(instant: datetime) -> int:
    """Hour on the local wall clock (0-23). The repeated autumn hour maps to the same value."""
    return instant.astimezone(MARKET_TZ).hour


def naive_reference_day(delivery_day: date) -> date:
    """Same weekday a week back for Mon/Sat/Sun, the day before otherwise."""
    return delivery_day - timedelta(days=7 if delivery_day.weekday() in (0, 5, 6) else 1)


def delivery_day_of(instant: datetime) -> date:
    return instant.astimezone(MARKET_TZ).date()

"""All time arithmetic lives here. Stored instants are UTC; market rules are Nordic local time."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("Europe/Oslo")  # shared by every Nordic bidding zone (CET/CEST)
HOUR = timedelta(hours=1)
DA_GATE_CLOSURE = time(12, 0)  # local, on D-1
DA_DECISION_MARGIN = timedelta(minutes=30)  # D-008: decide 30 min before gate closure
DA_ASSUMED_KNOWN_AT = time(13, 0)  # D-024: results ~12:45 + 15 min safety lag


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


def da_assumed_knowledge_time(event_time: datetime) -> datetime:
    """Assumed knowledge time of a backfilled day-ahead price: 13:00 local on D-1."""
    return local_instant(delivery_day_of(event_time) - timedelta(days=1), DA_ASSUMED_KNOWN_AT)


def delivery_span(first: date, last: date) -> tuple[datetime, datetime]:
    """[start, end) in UTC covering delivery days first..last."""
    return local_instant(first, time(0)), local_instant(last + timedelta(days=1), time(0))


def mtus_of(delivery_day: date, resolution: timedelta) -> list[datetime]:
    """UTC start of each MTU of the delivery day; DST days have 23 or 25 hours of them."""
    start, end = delivery_span(delivery_day, delivery_day)
    return [start + i * resolution for i in range((end - start) // resolution)]


def hours_of(delivery_day: date) -> list[datetime]:
    """UTC start of each hour of the delivery day (23/24/25 hours)."""
    return mtus_of(delivery_day, HOUR)


def local_clock_hour(instant: datetime) -> int:
    """Hour on the local wall clock (0-23). The repeated autumn hour maps to the same value."""
    return instant.astimezone(MARKET_TZ).hour


def naive_reference_day(delivery_day: date) -> date:
    """Same weekday a week back for Mon/Sat/Sun, the day before otherwise."""
    return delivery_day - timedelta(days=7 if delivery_day.weekday() in (0, 5, 6) else 1)


def delivery_day_of(instant: datetime) -> date:
    return instant.astimezone(MARKET_TZ).date()

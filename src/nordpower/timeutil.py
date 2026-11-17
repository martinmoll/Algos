"""All time arithmetic lives here. Stored instants are UTC; market rules are Nordic local time."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("Europe/Oslo")  # shared by every Nordic bidding zone (CET/CEST)
DA_DECISION_CUTOFF = time(11, 30)  # D-008: 30 min before the 12:00 gate closure
DA_ASSUMED_KNOWN_AT = time(13, 0)  # D-024: results ~12:45 + 15 min safety lag


def local_instant(d: date, t: time) -> datetime:
    """UTC instant of local market time `t` on day `d`."""
    return datetime.combine(d, t, tzinfo=MARKET_TZ).astimezone(UTC)


def decision_cutoff(delivery_day: date) -> datetime:
    """Instant (UTC) at which day-ahead decisions for `delivery_day` are made."""
    return local_instant(delivery_day - timedelta(days=1), DA_DECISION_CUTOFF)


def da_assumed_knowledge_time(event_time: datetime) -> datetime:
    """Assumed knowledge time of a backfilled day-ahead price: 13:00 local on D-1."""
    return local_instant(delivery_day_of(event_time) - timedelta(days=1), DA_ASSUMED_KNOWN_AT)


def delivery_span(first: date, last: date) -> tuple[datetime, datetime]:
    """[start, end) in UTC covering delivery days first..last."""
    return local_instant(first, time(0)), local_instant(last + timedelta(days=1), time(0))


def hours_of(delivery_day: date) -> list[datetime]:
    """UTC start of each hour of the delivery day (23/24/25 hours)."""
    start, end = delivery_span(delivery_day, delivery_day)
    return [start + timedelta(hours=i) for i in range((end - start) // timedelta(hours=1))]


def naive_reference_day(delivery_day: date) -> date:
    """Same weekday a week back for Mon/Sat/Sun, the day before otherwise."""
    return delivery_day - timedelta(days=7 if delivery_day.weekday() in (0, 5, 6) else 1)


def delivery_day_of(instant: datetime) -> date:
    return instant.astimezone(MARKET_TZ).date()

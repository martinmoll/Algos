"""Seam 3: time-module properties over 2000-2040, checked against the EU clock-change rule
(last Sunday of March and of October), which is computed here independently."""

from datetime import UTC, date, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from nordpower.timeutil import (
    MARKET_TZ,
    da_gate_closure,
    decision_cutoff,
    hours_of,
    mtus_of,
)

QUARTER = timedelta(minutes=15)


def last_sunday(year: int, month: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - 6) % 7)


# Uniform dates rarely hit the ~82 clock-change days in 2000-2040, so half the draws
# are a clock-change day or one of its neighbours.
near_clock_change = st.builds(
    lambda y, m, k: last_sunday(y, m) + timedelta(days=k),
    st.integers(2000, 2040),
    st.sampled_from([3, 10]),
    st.integers(-1, 1),
)
days = st.one_of(
    st.dates(min_value=date(2000, 1, 1), max_value=date(2040, 12, 31)), near_clock_change
)


def expected_hours(d: date) -> int:
    if d == last_sunday(d.year, 3):
        return 23
    if d == last_sunday(d.year, 10):
        return 25
    return 24


@given(days)
def test_hour_count_follows_the_eu_clock_change_rule(d):
    assert len(hours_of(d)) == expected_hours(d)


@given(days)
def test_quarter_hour_count_is_four_per_hour(d):
    assert len(mtus_of(d, QUARTER)) == 4 * expected_hours(d)  # 92 / 96 / 100


@given(days)
def test_mtus_are_contiguous_and_start_at_local_midnight(d):
    mtus = mtus_of(d, QUARTER)
    first_local = mtus[0].astimezone(MARKET_TZ)
    assert (first_local.date(), first_local.hour, first_local.minute) == (d, 0, 0)
    assert all(b - a == QUARTER for a, b in zip(mtus, mtus[1:], strict=False))
    next_day = mtus_of(d + timedelta(days=1), QUARTER)[0]
    assert next_day - mtus[-1] == QUARTER


@given(days)
def test_every_mtu_start_round_trips_between_utc_and_local(d):
    for t in mtus_of(d, QUARTER):
        assert t.tzinfo == UTC
        assert t.astimezone(MARKET_TZ).astimezone(UTC) == t


@given(days)
def test_cutoff_is_30_minutes_before_gate_closure_in_local_time(d):
    gate = da_gate_closure(d).astimezone(MARKET_TZ)
    cutoff = decision_cutoff(d).astimezone(MARKET_TZ)
    assert gate.replace(tzinfo=None) - cutoff.replace(tzinfo=None) == timedelta(minutes=30)
    assert (gate.date(), gate.hour, gate.minute) == (d - timedelta(days=1), 12, 0)


def test_gate_closure_examples():
    assert da_gate_closure(date(2024, 1, 16)) == datetime(2024, 1, 15, 11, tzinfo=UTC)
    # delivery day is the spring DST day; gate closure on the Saturday is still CET
    assert da_gate_closure(date(2024, 3, 31)) == datetime(2024, 3, 30, 11, tzinfo=UTC)
    # the Sunday after: gate closure on the DST day itself, now CEST
    assert da_gate_closure(date(2024, 4, 1)) == datetime(2024, 3, 31, 10, tzinfo=UTC)

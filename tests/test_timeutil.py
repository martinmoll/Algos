from datetime import UTC, date, datetime, timedelta

from nordpower.timeutil import (
    RESOLUTION,
    da_mtus,
    da_resolution,
    decision_cutoff,
    delivery_day_of,
    hours_of,
)


def test_cutoff_is_1130_local_on_the_day_before_in_winter():
    # CET = UTC+1, so 11:30 local on 15 Jan is 10:30 UTC
    assert decision_cutoff(date(2024, 1, 16)) == datetime(2024, 1, 15, 10, 30, tzinfo=UTC)


def test_cutoff_is_1130_local_on_the_day_before_in_summer():
    # CEST = UTC+2
    assert decision_cutoff(date(2024, 7, 16)) == datetime(2024, 7, 15, 9, 30, tzinfo=UTC)


def test_ordinary_delivery_day_has_24_hours_starting_at_local_midnight():
    hours = hours_of(date(2024, 1, 16))
    assert len(hours) == 24
    assert hours[0] == datetime(2024, 1, 15, 23, tzinfo=UTC)
    assert hours[-1] == datetime(2024, 1, 16, 22, tzinfo=UTC)


def test_delivery_day_of_an_instant_uses_local_time():
    # 23:30 UTC on 15 Jan is 00:30 local on 16 Jan
    assert delivery_day_of(datetime(2024, 1, 15, 23, 30, tzinfo=UTC)) == date(2024, 1, 16)


def test_day_ahead_mtu_is_an_hour_until_sep_2025_and_15_minutes_from_oct_2025():
    # 15-minute day-ahead MTU from delivery day 2025-10-01 (✅ live DayAheadPrices, 2026-11-18)
    assert da_resolution(date(2025, 9, 30)) == "PT60M"
    assert da_resolution(date(2025, 10, 1)) == "PT15M"
    assert RESOLUTION == {"PT60M": timedelta(hours=1), "PT15M": timedelta(minutes=15)}


def test_day_ahead_mtus_follow_the_resolution_and_dst():
    assert len(da_mtus(date(2025, 9, 30))) == 24
    assert len(da_mtus(date(2025, 10, 1))) == 96
    assert len(da_mtus(date(2025, 10, 26))) == 100  # autumn DST: 25 hours
    assert da_mtus(date(2025, 10, 1))[1] == datetime(2025, 9, 30, 22, 15, tzinfo=UTC)

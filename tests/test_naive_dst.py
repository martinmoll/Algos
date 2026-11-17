"""Engine seam (golden mini-backtests, docs/plan/06 §6): naive backtests across DST days on
synthetic prices whose value encodes the local day and clock hour:
price = 100 * day_of_month + clock_hour. The price generator does its own local-time
arithmetic on purpose, so it is an independent oracle for the time module."""

import json
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from nordpower.backtest import run_backtest
from nordpower.models.naive import Naive
from nordpower.store import Store
from nordpower.timeutil import (
    MARKET_TZ,
    da_assumed_knowledge_time,
    delivery_span,
    hours_of,
)

AUTUMN_DST = date(2024, 10, 27)  # 25 hours, clock hour 2 occurs twice
SPRING_DST = date(2024, 3, 31)  # 23 hours, no clock hour 2
REPEAT_BUMP = 50.0  # the second 02:00 on AUTUMN_DST is priced 50 higher than the first


def synthetic_prices(first: date, last: date) -> pl.DataFrame:
    rows, seen = [], set()
    start, end = delivery_span(first, last)
    t = start
    while t < end:
        local = t.astimezone(MARKET_TZ)
        key = (local.date(), local.hour)
        price = 100 * local.day + local.hour + (REPEAT_BUMP if key in seen else 0)
        seen.add(key)
        rows.append(
            {
                "zone": "DK1",
                "event_time": t,
                "resolution": "PT60M",
                "price_eur_mwh": float(price),
                "knowledge_time": da_assumed_knowledge_time(t),
                "knowledge_time_grade": "assumed",
                "source": "synthetic",
                "ingested_at": start,
                "raw_ref": "synthetic",
            }
        )
        t += timedelta(hours=1)
    return pl.DataFrame(rows)


def backtest_one_day(tmp_path, day: date, prices: pl.DataFrame | None = None) -> Path:
    store = Store(tmp_path)
    store.append(
        "da_price", synthetic_prices(day - timedelta(days=8), day) if prices is None else prices
    )
    return run_backtest(store, Naive(["DK1"]), ["DK1"], day, day, tmp_path / "runs")


def forecasts_for(tmp_path, day: date) -> list[float]:
    run = backtest_one_day(tmp_path, day)
    fc = pl.read_parquet(run / "forecasts.parquet").sort("event_time")
    assert fc["event_time"].to_list() == hours_of(day)
    return fc["forecast"].to_list()


def test_spring_dst_day_gets_23_forecasts_skipping_the_missing_hour(tmp_path):
    # Sunday -> reference is the previous Sunday, 24 March (24 hours)
    assert forecasts_for(tmp_path, SPRING_DST) == [2400 + h for h in range(24) if h != 2]


def test_autumn_dst_day_repeats_the_reference_hour_for_both_0200s(tmp_path):
    # Sunday -> reference 20 October; clock hours 0,1,2,2,3..23
    hours = [0, 1, 2, *range(2, 24)]
    assert forecasts_for(tmp_path, AUTUMN_DST) == [2000 + h for h in hours]


def test_reference_day_missing_its_0200_fills_it_from_0100(tmp_path):
    # Sunday 7 April -> reference is the spring DST day, which has no 02:00
    expected = [3100 + h for h in range(24)]
    expected[2] = 3101
    assert forecasts_for(tmp_path, date(2024, 4, 7)) == expected


def test_reference_day_with_two_0200s_averages_them(tmp_path):
    # Sunday 3 November -> reference is the autumn DST day
    expected = [2700.0 + h for h in range(24)]
    expected[2] = 2702 + REPEAT_BUMP / 2
    assert forecasts_for(tmp_path, date(2024, 11, 3)) == expected


def test_a_data_gap_on_an_ordinary_reference_day_is_not_filled(tmp_path):
    day = date(2024, 1, 16)  # Tuesday -> reference Monday 15 Jan
    prices = synthetic_prices(day - timedelta(days=8), day)
    gap = hours_of(date(2024, 1, 15))[10]
    run = backtest_one_day(tmp_path, day, prices.filter(pl.col("event_time") != gap))
    fc = pl.read_parquet(run / "forecasts.parquet")
    assert len(fc) == 23
    assert hours_of(day)[10] not in fc["event_time"].to_list()


@pytest.mark.parametrize("day", [SPRING_DST, AUTUMN_DST])
def test_run_config_records_the_dst_rule(tmp_path, day):
    rule = json.loads((backtest_one_day(tmp_path, day) / "config.json").read_text())["model_rule"]
    assert "previous local hour" in rule and "averaged" in rule

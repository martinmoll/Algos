"""Engine seam: naive backtests across the 15-minute switch (2025-10-01) and the 2025 autumn
DST day, on synthetic prices. price = 100 * local day + local hour + local minute / 60, so the
hourly mean of a complete 15-minute hour is 100 * day + hour + 0.375. The generator does its
own local-time arithmetic, independent of the time module."""

import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl

from nordpower.backtest import run_backtest
from nordpower.models.naive import Naive
from nordpower.publication import assumed_knowledge_time
from nordpower.store import Store

OSLO = ZoneInfo("Europe/Oslo")
QUARTER_MEAN = (0 + 15 + 30 + 45) / 60 / 4  # 0.375
REPEAT_BUMP = 50.0  # the second 02:xx hour on 2025-10-26 is priced 50 higher


def synthetic(first: date, last: date, drop: frozenset[datetime] = frozenset()) -> pl.DataFrame:
    """Hourly prices before 2025-10-01, quarter-hourly from it (local midnight boundaries)."""
    t = datetime(first.year, first.month, first.day, tzinfo=OSLO).astimezone(UTC)
    end = datetime(last.year, last.month, last.day, tzinfo=OSLO).astimezone(UTC) + timedelta(
        days=1, hours=1
    )
    rows, seen = [], set()
    while t < end:
        local = t.astimezone(OSLO)
        if local.date() > last:
            break
        quarter = local.date() >= date(2025, 10, 1)
        key = (local.date(), local.hour, local.minute)
        price = (
            100 * local.day + local.hour + local.minute / 60 + (REPEAT_BUMP if key in seen else 0)
        )
        seen.add(key)
        if t not in drop:
            rows.append(
                {
                    "zone": "DK1",
                    "event_time": t,
                    "resolution": "PT15M" if quarter else "PT60M",
                    "price_eur_mwh": price,
                    "knowledge_time": assumed_knowledge_time("da_price", t),
                    "knowledge_time_grade": "assumed",
                    "source": "synthetic",
                    "ingested_at": datetime(2025, 11, 1, tzinfo=UTC),
                    "raw_ref": "synthetic",
                }
            )
        t += timedelta(minutes=15 if quarter else 60)
    return pl.DataFrame(rows)


def backtest(tmp_path, first: date, last: date, prices: pl.DataFrame):
    store = Store(tmp_path / "store")
    store.append("da_price", prices)
    run = run_backtest(store, Naive(["DK1"]), ["DK1"], first, last, tmp_path / "runs")
    fc = pl.read_parquet(run / "forecasts.parquet")
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))["DK1"]
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    return fc, metrics, config


def forecasts_on(fc: pl.DataFrame, day: date) -> list[tuple[int, int, float]]:
    """(local hour, local minute, forecast) for every forecast MTU of the delivery day."""
    out = []
    for t, f in (
        fc.filter(pl.col("delivery_day") == day)
        .sort("event_time")
        .select("event_time", "forecast")
        .iter_rows()
    ):
        local = t.astimezone(OSLO)
        out.append((local.hour, local.minute, f))
    return out


def test_forecasts_across_the_switch_use_hourly_means_at_the_delivery_days_mtu(tmp_path):
    prices = synthetic(date(2025, 9, 20), date(2025, 10, 3))
    fc, metrics, _ = backtest(tmp_path, date(2025, 9, 30), date(2025, 10, 3), prices)

    # Tue 30 Sep: hourly, from Mon 29 Sep (hourly)
    assert forecasts_on(fc, date(2025, 9, 30)) == [(h, 0, 2900 + h) for h in range(24)]
    # Wed 1 Oct: 96 quarter-hours, each its clock hour of Tue 30 Sep (hourly)
    assert forecasts_on(fc, date(2025, 10, 1)) == [
        (h, m, 3000 + h) for h in range(24) for m in (0, 15, 30, 45)
    ]
    # Thu 2 Oct: quarter-hours from the hourly means of Wed 1 Oct (quarter-hourly)
    assert forecasts_on(fc, date(2025, 10, 2)) == [
        (h, m, 100 + h + QUARTER_MEAN) for h in range(24) for m in (0, 15, 30, 45)
    ]
    # Sat 4 Oct is not in the run; Fri 3 Oct from Thu 2 Oct
    assert forecasts_on(fc, date(2025, 10, 3))[0] == (0, 0, 200 + QUARTER_MEAN)

    hourly, quarterly = metrics["eras"]["PT60M"], metrics["eras"]["PT15M"]
    assert hourly["n"] == hourly["n_expected"] == 24
    assert quarterly["n"] == quarterly["n_expected"] == 3 * 96
    assert metrics["n"] == metrics["n_expected"] == 24 + 3 * 96


def test_autumn_dst_in_the_15_minute_era(tmp_path):
    prices = synthetic(date(2025, 10, 19), date(2025, 11, 2))
    fc, _, _ = backtest(tmp_path, date(2025, 10, 26), date(2025, 11, 2), prices)

    # Sun 26 Oct (25 hours, from Sun 19 Oct): 100 MTUs; both 02:xx hours get 1902.375
    dst_day = forecasts_on(fc, date(2025, 10, 26))
    assert len(dst_day) == 100
    assert [f for h, _, f in dst_day if h == 2] == [1902 + QUARTER_MEAN] * 8
    # Sun 2 Nov from Sun 26 Oct: clock hour 2 averages both 02:xx hours (8 quarters)
    nov2 = dict(((h, m), f) for h, m, f in forecasts_on(fc, date(2025, 11, 2)))
    assert nov2[(2, 30)] == 2602 + QUARTER_MEAN + REPEAT_BUMP / 2
    assert nov2[(3, 0)] == 2603 + QUARTER_MEAN


def test_an_incomplete_reference_hour_gets_no_forecast(tmp_path):
    missing = datetime(2025, 10, 1, 5, 30, tzinfo=OSLO).astimezone(UTC)
    prices = synthetic(date(2025, 9, 30), date(2025, 10, 2), drop=frozenset({missing}))
    fc, metrics, _ = backtest(tmp_path, date(2025, 10, 2), date(2025, 10, 2), prices)

    hours = {h for h, _, _ in forecasts_on(fc, date(2025, 10, 2))}
    assert hours == set(range(24)) - {5}  # hour 5 of Wed 1 Oct had 3 of 4 quarters
    assert metrics["n"] == 92 and metrics["n_expected"] == 96


def test_the_aggregation_rule_is_in_the_run_config(tmp_path):
    prices = synthetic(date(2025, 9, 30), date(2025, 10, 2))
    _, _, config = backtest(tmp_path, date(2025, 10, 2), date(2025, 10, 2), prices)
    assert "quarter-hours are averaged to hourly means" in config["model_rule"]
    assert "only complete hours" in config["model_rule"]


def test_an_era_without_scored_mtus_is_still_reported(tmp_path):
    # Prices stop with Tue 30 Sep: Wed 1 Oct (the run's only 15-minute day) is forecast from
    # 30 Sep but has no actuals, so the 15-minute era scores nothing
    prices = synthetic(date(2025, 9, 29), date(2025, 9, 30))
    _, metrics, _ = backtest(tmp_path, date(2025, 9, 30), date(2025, 10, 1), prices)
    eras = metrics["eras"]
    assert eras["PT60M"]["n"] == eras["PT60M"]["n_expected"] == 24
    assert eras["PT15M"] == {
        "n": 0,
        "n_expected": 96,
        "mae": None,
        "rmse": None,
        "rmae": None,
    }


def test_spring_dst_in_the_15_minute_era(tmp_path):
    """2026-03-29 has 23 hours (no 02:00). It is inside the vault, so the run opens it."""
    store = Store(tmp_path / "store")
    store.append("da_price", synthetic(date(2026, 3, 22), date(2026, 3, 30)))
    run = run_backtest(
        store,
        Naive(["DK1"]),
        ["DK1"],
        date(2026, 3, 29),
        date(2026, 3, 30),
        tmp_path / "runs",
        vault_purpose="D-032 synthetic spring-DST test, not market data",
    )
    fc = pl.read_parquet(run / "forecasts.parquet")
    # Sun 29 Mar from Sun 22 Mar: 92 quarter-hours, clock hour 2 absent
    dst_day = forecasts_on(fc, date(2026, 3, 29))
    assert len(dst_day) == 92 and {h for h, _, _ in dst_day} == set(range(24)) - {2}
    # Mon 30 Mar from Mon 23 Mar: ordinary day, hour 3 is complete
    monday = dict(((h, m), f) for h, m, f in forecasts_on(fc, date(2026, 3, 30)))
    assert monday[(3, 45)] == 2303 + QUARTER_MEAN
    # Sun 5 Apr has the DST day as its reference (D-7): clock hour 2 is filled from hour 1
    store.append("da_price", synthetic(date(2026, 3, 31), date(2026, 4, 5)))
    run = run_backtest(
        store,
        Naive(["DK1"]),
        ["DK1"],
        date(2026, 4, 5),
        date(2026, 4, 5),
        tmp_path / "runs2",
        vault_purpose="D-032 synthetic spring-DST test, not market data",
    )
    apr5 = dict(
        ((h, m), f)
        for h, m, f in forecasts_on(pl.read_parquet(run / "forecasts.parquet"), date(2026, 4, 5))
    )
    assert apr5[(2, 15)] == 2901 + QUARTER_MEAN

"""The look-ahead suite (docs/plan/03-no-lookahead.md §5). CI-blocking; never weaken,
skip or delete these tests to get a build green (CLAUDE.md)."""

import random
import statistics
from datetime import UTC, date, datetime, timedelta

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nordpower.backtest import run_backtest
from nordpower.models.naive import Naive
from nordpower.store import KEY, Store
from nordpower.timeutil import decision_cutoff, delivery_span, hours_of

from .conftest import (
    FIRST,
    LAST,
    ZONES,
    all_rows,
    price_rows,
    write_store_bypassing_vintage_rules,
)

START, END = delivery_span(FIRST, LAST)
DECISION_DAYS = [date(2024, 3, 28) + timedelta(days=i) for i in range(10)]  # spans DST day
# Every model must pass the engine-level tests. Add new models here.
MODELS = [Naive]


def sampled_instants(n: int = 25) -> list[datetime]:
    rng = random.Random(6)
    span = (END + timedelta(days=10) - START).total_seconds()
    return [START + timedelta(seconds=rng.uniform(0, span)) for _ in range(n)] + [
        decision_cutoff(d) for d in DECISION_DAYS
    ]


def view_rows(store: Store, t: datetime) -> pl.DataFrame:
    return store.as_of(t).read("da_price", zones=ZONES, event_start=START, event_end=END)


def reference_view(rows: pl.DataFrame, t: datetime) -> dict[tuple, float]:
    """Independent re-statement of the as-of rule in plain Python: per key, the vintage with
    the greatest (knowledge_time, ingested_at) among those with knowledge_time <= t."""
    best: dict[tuple, tuple] = {}
    for r in rows.iter_rows(named=True):
        if r["knowledge_time"] > t or not (START <= r["event_time"] < END):
            continue
        k = (r["zone"], r["event_time"])
        rank = (r["knowledge_time"], r["ingested_at"])
        if k not in best or rank > best[k][0]:
            best[k] = (rank, r["price_eur_mwh"])
    return {k: v for k, (_, v) in best.items()}


def as_dict(view: pl.DataFrame) -> dict[tuple, float]:
    return {(z, t): p for z, t, p in view.select(*KEY, "price_eur_mwh").iter_rows()}


def run_forecasts(store: Store, model, first: date, last: date, tmp) -> pl.DataFrame:
    run = run_backtest(store, model(ZONES), ZONES, first, last, tmp / "runs")
    return pl.read_parquet(run / "forecasts.parquet").sort("zone", "event_time")


def test_history_really_has_several_vintages_per_key(history_store):
    rows = all_rows(history_store)
    most = rows.group_by(KEY).len()["len"].max()
    assert isinstance(most, int) and most >= 2  # otherwise the tests below prove little


def test_time_travel_equivalence(history_store, tmp_path):
    """A view at t equals (1) an independent re-statement of the as-of rule and (2) a store
    that physically holds only what was known by t."""
    rows = all_rows(history_store)
    for i, t in enumerate(sampled_instants()):
        view = view_rows(history_store, t)
        assert as_dict(view) == reference_view(rows, t), t
        known = rows.filter(pl.col("knowledge_time") <= t)
        truncated = write_store_bypassing_vintage_rules(tmp_path / f"t{i}", known)
        assert view.equals(view_rows(truncated, t)), t


def poison(rows: pl.DataFrame, t: datetime) -> pl.DataFrame:
    """Every vintage not yet knowable at t gets garbage: +1e9, -1e9, NaN in rotation."""
    garbage = [1e9, -1e9, float("nan")]
    return (
        rows.with_row_index("_i")
        .with_columns(
            price_eur_mwh=pl.when(pl.col("knowledge_time") > t)
            .then(pl.col("_i").map_elements(lambda i: garbage[i % 3], return_dtype=pl.Float64))
            .otherwise(pl.col("price_eur_mwh"))
        )
        .drop("_i")
    )


@pytest.mark.parametrize("model", MODELS)
def test_future_poison_leaves_forecasts_bit_identical(history_store, tmp_path, model):
    """Corrupting everything not yet known at a day's cutoff must not change that day's
    forecast, even inside a multi-day run (catches an engine that reuses later views)."""
    rows = all_rows(history_store)
    clean = run_forecasts(history_store, model, DECISION_DAYS[0], DECISION_DAYS[-1], tmp_path)
    for day in DECISION_DAYS:
        store = write_store_bypassing_vintage_rules(
            tmp_path / f"p{day}", poison(rows, decision_cutoff(day))
        )
        dirty = run_forecasts(store, model, day, DECISION_DAYS[-1], tmp_path / f"d{day}")
        on_day = pl.col("delivery_day") == day
        expected, got = clean.filter(on_day), dirty.filter(on_day)
        assert not expected.is_empty()
        assert expected.equals(got), day


CANARY_AT = datetime(2024, 4, 1, 12, tzinfo=UTC)
CANARY_EVENT = datetime(2024, 4, 3, 11, tzinfo=UTC)


@settings(max_examples=200, deadline=None)
@given(st.integers(min_value=1, max_value=30 * 24 * 3600 * 10**6))
def test_canary_is_invisible_before_its_knowledge_time(tmp_path_factory, microseconds_before):
    """A planted perfect-foresight value (the realised price itself) is unreadable at any
    instant before it was knowable, down to a microsecond, both on its own and as a later
    vintage of a key that already has a known value."""
    window = {
        "zones": ["DK1"],
        "event_start": CANARY_EVENT,
        "event_end": CANARY_EVENT + timedelta(hours=1),
    }
    known_earlier = CANARY_AT - timedelta(days=31)  # before any sampled t
    earlier = price_rows({("DK1", CANARY_EVENT): 50.0}, known_earlier).with_columns(
        knowledge_time=pl.lit(known_earlier)
    )
    canary = price_rows({("DK1", CANARY_EVENT): 4242.0}, CANARY_AT).with_columns(
        knowledge_time=pl.lit(CANARY_AT)
    )
    t = CANARY_AT - timedelta(microseconds=microseconds_before)
    for rows, before in [(canary, None), (pl.concat([earlier, canary]), 50.0)]:
        store = write_store_bypassing_vintage_rules(tmp_path_factory.mktemp("canary"), rows)
        seen = store.as_of(t).read("da_price", **window)["price_eur_mwh"].to_list()
        assert seen == ([] if before is None else [before])
        assert store.as_of(CANARY_AT).read("da_price", **window)["price_eur_mwh"].item() == 4242.0


@pytest.mark.parametrize("model", MODELS)
def test_shuffled_target_shows_no_skill(history_store, tmp_path, model):
    """On prices shuffled across time, the pipeline must do no better than a constant.

    A pipeline that leaked the realised price would score MAE near zero here."""
    latest = view_rows(history_store, datetime(2030, 1, 1, tzinfo=UTC))
    shuffled_prices = latest["price_eur_mwh"].sample(fraction=1.0, shuffle=True, seed=42)
    keys = zip(latest["zone"], latest["event_time"], strict=True)
    # one vintage per hour, knowable at its publication-rule time, so every hour is forecastable
    shuffled = price_rows(
        dict(zip(keys, shuffled_prices, strict=True)), datetime(2024, 3, 1, tzinfo=UTC)
    )
    store = write_store_bypassing_vintage_rules(tmp_path / "shuffled", shuffled)

    fc = run_forecasts(store, model, DECISION_DAYS[0], DECISION_DAYS[-1], tmp_path)
    actual = shuffled.select("zone", "event_time", actual="price_eur_mwh")
    scored = fc.join(actual, on=["zone", "event_time"])
    model_mae = (scored["forecast"] - scored["actual"]).abs().mean()
    median = statistics.median(shuffled["price_eur_mwh"].to_list())
    constant_mae = (scored["actual"] - median).abs().mean()

    assert len(scored) == len(ZONES) * sum(len(hours_of(d)) for d in DECISION_DAYS)
    assert isinstance(model_mae, float) and isinstance(constant_mae, float)
    assert model_mae > 0.9 * constant_mae

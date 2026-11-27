"""Run status as a look-ahead guard (plan 03 §5.5, plan 05 §6, D-037). CI-blocking; never
weaken, skip or delete these tests to get a build green (CLAUDE.md).

Three planted cheats, each through a different route:
- an oracle handed the realised prices outside the store: the view cannot stop it, so only
  the too-good alarm can (status suspect);
- a peeker that reads the store around the knowledge view: the future-poison check catches
  it (status invalid);
- a model that forecasts beyond its delivery day: the decision-time check catches it.
"""

import json
from datetime import date, timedelta

import polars as pl
import pytest

from nordpower import runs
from nordpower.backtest import run_backtest
from nordpower.models.naive import Naive
from nordpower.store import KEY, KnowledgeView, Store
from nordpower.timeutil import da_mtus

from .conftest import ZONES, all_rows

FIRST, LAST = date(2024, 3, 28), date(2024, 4, 6)


@pytest.fixture(autouse=True)
def clean_tree(monkeypatch):
    """Status must not depend on the state of the developer's checkout."""
    monkeypatch.setattr(runs, "git_state", lambda: {"sha": "test", "dirty": False})


def frame(rows: pl.DataFrame) -> pl.DataFrame:
    return rows.select(
        "zone", "event_time", forecast=pl.col("price_eur_mwh").cast(pl.Float64)
    ).sort(KEY)


class Oracle:
    """Knows the final prices from outside the store (a planted perfect forecast)."""

    name, rule = "oracle", "returns the realised price (planted cheat, test only)"

    def __init__(self, truth: pl.DataFrame):
        self.truth = truth

    def fit(self, view: KnowledgeView) -> None:
        pass

    def predict(self, view: KnowledgeView, delivery_day: date) -> pl.DataFrame:
        return frame(self.truth.filter(pl.col("event_time").is_in(da_mtus(delivery_day))))


class Peeker:
    """Reads every vintage in the store, ignoring knowledge time (bypasses the view)."""

    name, rule = "peeker", "latest vintage ignoring knowledge time (planted cheat, test only)"

    def fit(self, view: KnowledgeView) -> None:
        pass

    def predict(self, view: KnowledgeView, delivery_day: date) -> pl.DataFrame:
        parts = view._store._parts("da_price")
        assert parts is not None
        latest = parts.collect().group_by(KEY, maintain_order=True).last()
        return frame(latest.filter(pl.col("event_time").is_in(da_mtus(delivery_day))))


class Overreach(Naive):
    """Naive, plus a forecast for the first MTU of the next delivery day."""

    name = "overreach"

    def predict(self, view: KnowledgeView, delivery_day: date) -> pl.DataFrame:
        fc = super().predict(view, delivery_day)
        extra = fc.head(1).with_columns(pl.col("event_time") + timedelta(days=1))
        return pl.concat([fc, extra])


def final_prices(store: Store) -> pl.DataFrame:
    rows = all_rows(store).sort("knowledge_time", "ingested_at")
    return rows.group_by(KEY, maintain_order=True).last()


def record(run, name: str):
    return json.loads((run / name).read_text(encoding="utf-8"))


def test_honest_naive_run_is_ok(history_store, tmp_path):
    run = run_backtest(history_store, Naive(ZONES), ZONES, FIRST, LAST, tmp_path)
    assert record(run, "status.json")["status"] == "ok"
    assert all(c["passed"] for c in record(run, "leakage_checks.json"))


def test_a_planted_too_good_forecast_is_suspect(history_store, tmp_path):
    oracle = Oracle(final_prices(history_store))
    run = run_backtest(history_store, oracle, ZONES, FIRST, LAST, tmp_path)
    status = record(run, "status.json")
    assert status["status"] == "suspect"
    assert any("too good" in r for r in status["reasons"])
    # the side channel never touches the store, so the poison check cannot see it
    assert all(c["passed"] for c in record(run, "leakage_checks.json"))


def test_reading_around_the_knowledge_view_is_invalid(history_store, tmp_path):
    run = run_backtest(history_store, Peeker(), ZONES, FIRST, LAST, tmp_path)
    checks = {c["name"]: c for c in record(run, "leakage_checks.json")}
    assert not checks["future_poison"]["passed"]
    assert record(run, "status.json")["status"] == "invalid"  # invalid outranks suspect


def test_a_forecast_outside_its_delivery_day_is_invalid(history_store, tmp_path):
    run = run_backtest(history_store, Overreach(ZONES), ZONES, FIRST, LAST, tmp_path)
    checks = {c["name"]: c for c in record(run, "leakage_checks.json")}
    assert not checks["decision_times"]["passed"]
    assert record(run, "status.json")["status"] == "invalid"


def test_the_poison_check_samples_first_and_last_day(history_store, tmp_path):
    run = run_backtest(history_store, Naive(ZONES), ZONES, FIRST, LAST, tmp_path)
    checks = {c["name"]: c for c in record(run, "leakage_checks.json")}
    days = checks["future_poison"]["days"]
    assert days[0] == FIRST.isoformat() and days[-1] == LAST.isoformat()
    assert len(days) == runs.load_status_rules()["future_poison"]["sample_days"]

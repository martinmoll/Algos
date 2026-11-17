"""Seam 1: the walking skeleton through the CLI, on a recorded Energi Data Service response."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from nordpower import cli
from nordpower.ingest import energidataservice
from nordpower.timeutil import decision_cutoff

FIXTURE = Path(__file__).parent / "fixtures" / "elspotprices_dk_2024-01-01_2024-01-21.json"

# Hand-read from the fixture (SpotPriceEUR at the given HourUTC)
DK1_TUE_16_JAN_1100UTC = 103.43
DK1_MON_08_JAN_1100UTC = 95.5


@pytest.fixture
def run_dir(tmp_path, monkeypatch) -> Path:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    monkeypatch.setattr(energidataservice, "http_get", lambda url: payload)
    data = ["--data-dir", str(tmp_path)]
    cli.main([*data, "ingest", "elspotprices", "--start", "2024-01-01", "--end", "2024-01-21"])
    cli.main([*data, "curate"])
    cli.main([*data, "backtest", "--start", "2024-01-08", "--end", "2024-01-21"])
    (run,) = (tmp_path / "runs").iterdir()
    return run


def test_naive_backtest_scores_rmae_of_exactly_one_per_zone(run_dir):
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert set(metrics) == {"DK1", "DK2"}
    for m in metrics.values():
        assert m["n"] == m["n_expected"] == 14 * 24
        assert m["rmae"] == 1.0
        assert m["mae"] > 0


def test_naive_repeats_yesterday_midweek_and_last_week_on_mondays(run_dir):
    fc = pl.read_parquet(run_dir / "forecasts.parquet").filter(pl.col("zone") == "DK1")

    def at(t: datetime) -> float:
        return fc.filter(pl.col("event_time") == t)["forecast"].item()

    assert at(datetime(2024, 1, 17, 11, tzinfo=UTC)) == DK1_TUE_16_JAN_1100UTC
    assert at(datetime(2024, 1, 15, 11, tzinfo=UTC)) == DK1_MON_08_JAN_1100UTC


def test_every_forecast_was_made_at_its_decision_cutoff(run_dir):
    fc = pl.read_parquet(run_dir / "forecasts.parquet")
    for day, t in fc.select("delivery_day", "decision_time").unique().iter_rows():
        assert t == decision_cutoff(day)


def test_run_record_has_config(run_dir):
    config = json.loads((run_dir / "config.json").read_text())
    assert config["model"] == "naive"
    assert "D-7" in config["model_rule"]
    assert datetime.fromisoformat(config["scored_as_of"]).tzinfo is not None
    assert config["first_delivery_day"] == date(2024, 1, 8).isoformat()


def test_zones_config_has_12_nordic_zones_plus_system_price():
    from nordpower.zones import load_zones

    zones = load_zones()
    nordic = {z for z, v in zones.items() if not v.get("pseudo")}
    assert nordic == {
        *(f"NO{i}" for i in range(1, 6)),
        *(f"SE{i}" for i in range(1, 5)),
        "DK1",
        "DK2",
        "FI",
    }
    assert all(len(zones[z]["eic"]) == 16 for z in nordic)
    assert zones["SYS"]["pseudo"] is True

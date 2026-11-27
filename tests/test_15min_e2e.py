"""CLI seam across the 15-minute switch, on recorded Energi Data Service responses:
Elspotprices (hourly) for delivery 2025-09-17..09-30, DayAheadPrices (15-minute) for
2025-10-01..10-14."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from nordpower import cli
from nordpower.ingest import energidataservice
from nordpower.store import Store

FIXTURES = Path(__file__).parent / "fixtures"
PAYLOADS = {
    "Elspotprices": FIXTURES / "elspotprices_dk_2025-09-17_2025-09-30.json",
    "DayAheadPrices": FIXTURES / "dayaheadprices_dk_2025-10-01_2025-10-14.json",
}
SWITCH = datetime(2025, 9, 30, 22, tzinfo=UTC)  # 2025-10-01 00:00 Europe/Oslo
# Hand-read from the DayAheadPrices fixture: DK1 quarter-hours from 2025-09-30T22:00 UTC
DK1_OCT_1_FIRST_HOUR = [102.599998, 92.239998, 86.029999, 85.389999]


@pytest.fixture
def data_dir(tmp_path, monkeypatch) -> Path:
    payloads = {ds: json.loads(p.read_text(encoding="utf-8")) for ds, p in PAYLOADS.items()}
    monkeypatch.setattr(
        energidataservice, "http_get", lambda url: payloads[url.split("/dataset/")[1].split("?")[0]]
    )
    d = ["--data-dir", str(tmp_path)]
    cli.main([*d, "ingest", "elspotprices", "--start", "2025-09-17", "--end", "2025-09-30"])
    cli.main([*d, "ingest", "dayaheadprices", "--start", "2025-10-01", "--end", "2025-10-14"])
    cli.main([*d, "curate"])
    cli.main([*d, "backtest", "--start", "2025-09-24", "--end", "2025-10-14"])
    return tmp_path


def curated(data_dir: Path) -> pl.DataFrame:
    return (
        Store(data_dir)
        .as_of(datetime(2025, 11, 1, tzinfo=UTC))
        .read(
            "da_price",
            zones=["DK1", "DK2"],
            event_start=datetime(2025, 9, 1, tzinfo=UTC),
            event_end=datetime(2025, 11, 1, tzinfo=UTC),
        )
    )


def test_curated_prices_are_hourly_before_the_switch_and_15_minute_from_it(data_dir):
    rows = curated(data_dir)
    hourly = rows.filter(pl.col("event_time") < SWITCH)
    quarter = rows.filter(pl.col("event_time") >= SWITCH)
    assert hourly["resolution"].unique().to_list() == ["PT60M"]
    assert quarter["resolution"].unique().to_list() == ["PT15M"]
    assert len(hourly) == 2 * 14 * 24
    assert len(quarter) == 2 * 14 * 96
    assert set(quarter["source"]) == {"energidataservice:DayAheadPrices"}


def test_backtest_across_the_switch_scores_each_era_separately(data_dir):
    (run,) = [p for p in (data_dir / "runs").iterdir() if p.is_dir()]
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    for zone in ["DK1", "DK2"]:
        seg = metrics[zone]["eras"]
        assert seg["PT60M"]["n"] == seg["PT60M"]["n_expected"] == 7 * 24
        assert seg["PT15M"]["n"] == seg["PT15M"]["n_expected"] == 14 * 96
        assert seg["PT60M"]["rmae"] == seg["PT15M"]["rmae"] == 1.0

    fc = pl.read_parquet(run / "forecasts.parquet").filter(pl.col("zone") == "DK1")
    # Thu 2 Oct, 00:00-00:45 local: the hourly mean of Wed 1 Oct 00:00's four quarter-hours
    first_hour = fc.filter(pl.col("delivery_day") == date(2025, 10, 2)).sort("event_time").head(4)
    assert first_hour["forecast"].to_list() == [pytest.approx(sum(DK1_OCT_1_FIRST_HOUR) / 4)] * 4


def test_a_dataset_row_outside_its_era_is_rejected(tmp_path):
    from nordpower.curate import curate_prices

    d = tmp_path / "raw" / "energidataservice" / "DayAheadPrices"
    d.mkdir(parents=True)
    row = {"TimeUTC": "2025-09-30T21:00:00", "PriceArea": "DK1", "DayAheadPriceEUR": 1.0}
    snapshot = {"ingested_at": "2025-11-01T00:00:00+00:00", "url": "u", "records": [row]}
    (d / "s.json").write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(ValueError, match="PT60M era"):
        curate_prices(tmp_path / "raw", Store(tmp_path))


def test_the_recorded_market_data_passes_every_quality_check(data_dir):
    records = list((data_dir / "quality" / "da_price").glob("*.json"))
    assert len(records) == 2  # one per raw snapshot
    for r in records:
        assert json.loads(r.read_text(encoding="utf-8"))["failures"] == [], r.name

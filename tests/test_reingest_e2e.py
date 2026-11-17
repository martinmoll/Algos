"""CLI seam: re-ingesting and re-curating, on the recorded Energi Data Service response."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nordpower import cli
from nordpower.ingest import energidataservice
from nordpower.store import Store

FIXTURE = Path(__file__).parent / "fixtures" / "elspotprices_dk_2024-01-01_2024-01-21.json"
REVISED_HOUR = "2024-01-16T11:00:00"  # DK1 103.43 in the fixture


def files(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    payload = {"current": json.loads(FIXTURE.read_text(encoding="utf-8"))}
    monkeypatch.setattr(energidataservice, "http_get", lambda url: payload["current"])

    def run():
        data = ["--data-dir", str(tmp_path)]
        cli.main([*data, "ingest", "elspotprices", "--start", "2024-01-01", "--end", "2024-01-21"])
        cli.main([*data, "curate"])

    return tmp_path, payload, run


def dk1_price(root: Path, t: datetime) -> float:
    hour = datetime.fromisoformat(REVISED_HOUR).replace(tzinfo=UTC)
    df = (
        Store(root)
        .as_of(t)
        .read("da_price", zones=["DK1"], event_start=hour, event_end=hour.replace(hour=12))
    )
    return df["price_eur_mwh"].item()


def test_identical_reingest_and_recurate_leave_storage_unchanged(pipeline):
    root, _, run = pipeline
    run()
    before = files(root)
    run()
    assert files(root) == before


def test_a_revised_download_becomes_a_new_vintage_visible_only_after_ingestion(pipeline):
    root, payload, run = pipeline
    run()
    revised = copy.deepcopy(payload["current"])
    for r in revised["records"]:
        if r["PriceArea"] == "DK1" and r["HourUTC"] == REVISED_HOUR:
            r["SpotPriceEUR"] = 999.0
    payload["current"] = revised

    before_revision = datetime.now(UTC)
    run()

    assert dk1_price(root, before_revision) == 103.43
    assert dk1_price(root, datetime.now(UTC)) == 999.0
    raw = list((root / "raw" / "energidataservice" / "Elspotprices").glob("*.json"))
    assert len(raw) == 2  # both downloads kept


def test_recurating_after_a_new_vintage_leaves_storage_unchanged(pipeline):
    root, payload, run = pipeline
    run()
    payload["current"] = with_dk1_price(payload["current"], 999.0)
    run()
    before = files(root)
    run()
    assert files(root) == before


def test_a_download_that_reverts_to_an_earlier_value_is_a_third_vintage(pipeline):
    root, payload, run = pipeline
    original = payload["current"]
    run()
    payload["current"] = with_dk1_price(original, 999.0)
    run()
    payload["current"] = original
    before_revert = datetime.now(UTC)
    run()

    assert dk1_price(root, before_revert) == 999.0
    assert dk1_price(root, datetime.now(UTC)) == 103.43


def with_dk1_price(payload: dict, price: float) -> dict:
    revised = copy.deepcopy(payload)
    for r in revised["records"]:
        if r["PriceArea"] == "DK1" and r["HourUTC"] == REVISED_HOUR:
            r["SpotPriceEUR"] = price
    return revised

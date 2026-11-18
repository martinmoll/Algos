"""The vault guard (D-014, D-031). CI-blocking; never weaken, skip or delete (CLAUDE.md)."""

import json
import re
from datetime import UTC, date, datetime, time, timedelta

import pytest

from nordpower.backtest import run_backtest
from nordpower.models.naive import Naive
from nordpower.store import REPO, Store, VaultSealed, VaultToken, load_vault_start
from nordpower.timeutil import delivery_span, local_instant

from .conftest import price_rows

# Independent of the code under test: D-014 seals from 2025-11-16 00:00 Europe/Oslo (CET).
BOUNDARY = datetime(2025, 11, 15, 23, tzinfo=UTC)
JUST_BEFORE = BOUNDARY - timedelta(microseconds=1)


def test_the_boundary_is_2025_11_16_midnight_oslo(tmp_path):
    assert Store(tmp_path).vault_start == BOUNDARY


@pytest.mark.parametrize("t", [BOUNDARY, BOUNDARY + timedelta(days=400)])
def test_views_at_or_after_the_boundary_are_refused_without_a_token(tmp_path, t):
    with pytest.raises(VaultSealed, match="vault"):
        Store(tmp_path).as_of(t)


def test_a_view_just_before_the_boundary_is_allowed(tmp_path):
    assert Store(tmp_path).as_of(JUST_BEFORE).now == JUST_BEFORE


def vault_log(store: Store) -> list[dict]:
    lines = (store.root / "vault_log.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_opening_the_vault_is_logged_once_and_its_token_unlocks_views(tmp_path):
    store = Store(tmp_path)
    token = store.open_vault("D-031 final test of frozen config abc123")
    for t in [BOUNDARY, BOUNDARY + timedelta(days=30)]:
        assert store.as_of(t, vault=token).now == t
    [entry] = vault_log(store)
    assert entry["purpose"] == "D-031 final test of frozen config abc123"
    assert entry["caller"].startswith("tests") and "test_vault.py:" in entry["caller"]
    assert datetime.fromisoformat(entry["opened_at"]).tzinfo is not None
    store.open_vault("D-031 second look")
    assert len(vault_log(store)) == 2  # every opening is counted


def test_an_opening_must_cite_a_decision_log_entry(tmp_path):
    store = Store(tmp_path)
    for purpose in ["just peeking", "D-999 an entry that does not exist"]:
        with pytest.raises(ValueError, match="D-"):
            store.open_vault(purpose)
    assert not (tmp_path / "vault_log.jsonl").exists()


def test_a_token_not_issued_by_this_store_is_refused(tmp_path):
    forged = VaultToken("D-031 forged", datetime.now(UTC), "x.py:1")
    other = Store(tmp_path / "other").open_vault("D-031 other store")
    for token in [forged, other]:
        with pytest.raises(VaultSealed):
            Store(tmp_path).as_of(BOUNDARY, vault=token)


def test_a_view_before_the_boundary_never_shows_events_inside_the_vault(tmp_path):
    """Prices for delivery 2025-11-16 publish at 13:00 on the 15th, before the boundary;
    they are still vault data."""
    last_research = local_instant(date(2025, 11, 15), time(23))
    first_vault = local_instant(date(2025, 11, 16), time(0))
    store = Store(tmp_path)
    store.append(
        "da_price",
        price_rows({("DK1", last_research): 10.0, ("DK1", first_vault): 20.0}, BOUNDARY),
    )
    window = {
        "zones": ["DK1"],
        "event_start": last_research,
        "event_end": BOUNDARY + timedelta(days=1),
    }
    before = store.as_of(JUST_BEFORE).read("da_price", **window)
    assert before["price_eur_mwh"].to_list() == [10.0]
    token = store.open_vault("D-031 test")
    opened = store.as_of(BOUNDARY, vault=token).read("da_price", **window)
    assert opened["price_eur_mwh"].to_list() == [10.0, 20.0]


def store_around_boundary(root) -> Store:
    """Hourly DK1 prices for delivery 2025-11-01..2025-11-20, assumed knowledge times."""
    start, end = delivery_span(date(2025, 11, 1), date(2025, 11, 20))
    hours = [start + timedelta(hours=i) for i in range((end - start) // timedelta(hours=1))]
    store = Store(root)
    store.append("da_price", price_rows({("DK1", h): float(i) for i, h in enumerate(hours)}, end))
    return store


@pytest.mark.parametrize("last", [date(2025, 11, 16), date(2025, 12, 1)])
def test_the_engine_refuses_delivery_days_inside_the_vault_by_default(tmp_path, last):
    store = store_around_boundary(tmp_path / "s")
    with pytest.raises(VaultSealed):
        run_backtest(store, Naive(["DK1"]), ["DK1"], date(2025, 11, 10), last, tmp_path / "runs")
    assert not (tmp_path / "runs").exists()  # refused before anything is recorded


def test_a_research_run_scores_with_what_was_known_before_the_boundary(tmp_path):
    store = store_around_boundary(tmp_path / "s")
    run = run_backtest(
        store, Naive(["DK1"]), ["DK1"], date(2025, 11, 10), date(2025, 11, 15), tmp_path / "runs"
    )
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    assert datetime.fromisoformat(config["scored_as_of"]) == JUST_BEFORE
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["DK1"]["n"] == metrics["DK1"]["n_expected"] == 6 * 24


def test_a_vault_run_is_exactly_one_logged_opening(tmp_path):
    """The engine opens the vault itself, so one opening can never cover two runs."""
    store = store_around_boundary(tmp_path / "s")
    run = run_backtest(
        store,
        Naive(["DK1"]),
        ["DK1"],
        date(2025, 11, 16),
        date(2025, 11, 20),
        tmp_path / "runs",
        vault_purpose="D-031 vault test of naive",
    )
    [entry] = vault_log(store)
    assert "tests/leakage/test_vault.py:" in entry["caller"]  # who asked, not the engine
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    assert config["vault_opening"] == entry
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["DK1"]["n"] == 5 * 24


def test_the_boundary_is_one_config_value(tmp_path):
    moved = tmp_path / "vault.toml"
    moved.write_text('start = "2026-05-16"\n', encoding="utf-8")
    assert load_vault_start(moved) == datetime(2026, 5, 15, 22, tzinfo=UTC)  # CEST
    literal = re.compile(r"2025-11-1[56]|2025, 11, 1[56]")
    hard_coded = [p for p in (REPO / "src").rglob("*.py") if literal.search(p.read_text("utf-8"))]
    assert hard_coded == []

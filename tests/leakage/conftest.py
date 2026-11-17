"""Shared synthetic history for the look-ahead suite.

DK1 and DK2 hourly prices for delivery days 2024-03-20..2024-04-10 (spans the spring DST
day), backfilled with assumed knowledge times, plus later downloads that change a random
tenth of the prices so the store holds several vintages per key. Built with Store.append,
so the real vintage rules apply.
"""

import os
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from nordpower.publication import ASSUMED, assumed_knowledge_time
from nordpower.store import Store
from nordpower.timeutil import delivery_span

ZONES = ["DK1", "DK2"]
FIRST, LAST = date(2024, 3, 20), date(2024, 4, 10)
BACKFILLED_AT = datetime(2024, 4, 15, tzinfo=UTC)
CHANGES_AT = [datetime(2024, 3, d, 18, tzinfo=UTC) for d in (25, 29)] + [
    datetime(2024, 4, d, 9, tzinfo=UTC) for d in (2, 6, 12)
]


def price_rows(prices: dict[tuple[str, datetime], float], ingested_at: datetime) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "zone": zone,
                "event_time": t,
                "resolution": "PT60M",
                "price_eur_mwh": p,
                "knowledge_time": assumed_knowledge_time("da_price", t),
                "knowledge_time_grade": ASSUMED,
                "source": "synthetic",
                "ingested_at": ingested_at,
                "raw_ref": f"synthetic@{ingested_at:%m%d%H}",
            }
            for (zone, t), p in prices.items()
        ]
    )


def all_rows(store: Store, dataset: str = "da_price") -> pl.DataFrame:
    """Every stored vintage, read straight from the files (test-only: bypasses as_of)."""
    return pl.read_parquet(store.root / "curated" / dataset / "*.parquet")


def write_store_bypassing_vintage_rules(
    root: Path, rows: pl.DataFrame, dataset: str = "da_price"
) -> Store:
    """A store whose curated layer holds exactly `rows`, skipping Store.append (test-only)."""
    d = root / "curated" / dataset
    d.mkdir(parents=True)
    rows.write_parquet(d / "all.parquet")
    return Store(root)


def pytest_sessionfinish(session, exitstatus):
    """Under check.py's leakage gate, a skipped, xfailed or deselected look-ahead test fails
    the gate: the suite must run in full."""
    if os.environ.get("NORDPOWER_LEAKAGE_GATE") != "1":
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = reporter.stats if reporter else {}
    kinds = ("skipped", "xfailed", "xpassed", "deselected")
    filtered = {k: len(stats[k]) for k in kinds if stats.get(k)}
    if filtered:
        print(f"LEAKAGE GATE: tests were filtered out {filtered}; the suite must run in full")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture(scope="session")
def history_store(tmp_path_factory) -> Store:
    rng = random.Random(20261117)
    start, end = delivery_span(FIRST, LAST)
    hours = [start + timedelta(hours=i) for i in range((end - start) // timedelta(hours=1))]
    prices = {(z, t): round(rng.uniform(-20, 300), 2) for z in ZONES for t in hours}

    store = Store(tmp_path_factory.mktemp("history"))
    store.append("da_price", price_rows(prices, BACKFILLED_AT - timedelta(days=30)))
    for when in CHANGES_AT:
        changed = {k: round(rng.uniform(-20, 300), 2) for k in rng.sample(sorted(prices), 100)}
        prices.update(changed)
        store.append("da_price", price_rows(changed, when))
    return store

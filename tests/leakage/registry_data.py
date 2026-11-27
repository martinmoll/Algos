"""Synthetic history for any registered dataset, built from its registry entry (D-043).

Used by the look-ahead suite so that every dataset in configs/datasets.toml, plus a test-only
dataset with a non-zone key, gets the time-travel, future-poison and canary tests."""

import random
from datetime import UTC, date, datetime, timedelta

import polars as pl

from nordpower.datasets import Dataset, parse_registry

# A dataset keyed like cross-border flows: no zone column at all.
SYNTHETIC = parse_registry(
    """
[xborder_test]
key = ["border", "direction", "event_time"]
mtu = "PT60M"
quality = ["completeness", "duplicate"]

[xborder_test.columns]
border = "String"
direction = "String"
event_time = "Datetime"
flow_mw = "Float64"
note = "String"
"""
)["xborder_test"]

FIRST = date(2024, 3, 25)  # spans the spring DST day (2024-03-31)
DAYS = 10
START = datetime(2024, 3, 24, 23, tzinfo=UTC)
END = START + timedelta(days=DAYS)
BACKFILLED_AT = datetime(2024, 4, 20, tzinfo=UTC)
CHANGES_AT = [datetime(2024, 3, d, 18, tzinfo=UTC) for d in (27, 30)] + [
    datetime(2024, 4, 2, 9, tzinfo=UTC)
]


def series_values(spec: Dataset) -> list[tuple]:
    """Two series per dataset: every group column gets two values."""
    pool = {"zone": ["DK1", "DK2"], "border": ["DK1-DK2", "DK1-NO2"], "direction": ["in", "out"]}
    a = tuple(pool.get(c, [f"{c}-a", f"{c}-b"])[0] for c in spec.group)
    b = tuple(pool.get(c, [f"{c}-a", f"{c}-b"])[1] for c in spec.group)
    return [a, b]


def value(dtype: pl.DataType, rng: random.Random):
    if dtype == pl.Float64:
        return round(rng.uniform(-20, 300), 2)
    if dtype == pl.Int64:
        return rng.randint(0, 1000)
    if dtype == pl.Boolean:
        return rng.random() < 0.5
    if dtype == pl.String:
        return rng.choice(["PT60M", "x", "y"])
    raise TypeError(f"no synthetic value for {dtype}")


def rows(spec: Dataset, values: dict[tuple, dict], ingested_at: datetime) -> pl.DataFrame:
    """One row per (series, event_time) in `values`, knowable 13 h before the hour starts."""
    out = []
    for (series, t), vals in values.items():
        out.append(
            dict(zip(spec.group, series, strict=True))
            | {"event_time": t}
            | vals
            | {
                "knowledge_time": t - timedelta(hours=13),
                "knowledge_time_grade": "assumed",
                "source": "synthetic",
                "ingested_at": ingested_at,
                "raw_ref": f"synthetic@{ingested_at:%m%d%H}",
            }
        )
    return pl.DataFrame(out, schema=spec.schema)


def history(spec: Dataset, seed: int = 20261127) -> list[pl.DataFrame]:
    """A backfill plus later downloads that change a random fifth of the values, so the store
    holds several vintages per key. Append them in order with Store.append."""
    rng = random.Random(seed)
    hours = [START + timedelta(hours=i) for i in range(DAYS * 24)]
    keys = [(s, t) for s in series_values(spec) for t in hours]
    current = {k: {c: value(spec.columns[c], rng) for c in spec.values} for k in keys}
    batches = [rows(spec, current, BACKFILLED_AT - timedelta(days=30))]
    for when in CHANGES_AT:
        changed = {
            k: {c: value(spec.columns[c], rng) for c in spec.values}
            for k in rng.sample(keys, len(keys) // 5)
        }
        current.update(changed)
        batches.append(rows(spec, changed, when))
    return batches

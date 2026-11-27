"""The look-ahead contract for every registered dataset (D-043), not only da_price.
CI-blocking; never weaken, skip or delete these tests to get a build green (CLAUDE.md).

Each dataset in configs/datasets.toml, plus a synthetic dataset keyed by border and
direction, is filled with several vintages per key and must pass time-travel equivalence,
future poison at the view, and the read-before-knowledge-time canary."""

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from nordpower.datasets import Dataset, load_registry
from nordpower.store import Store

from .registry_data import END, START, SYNTHETIC, history, rows, series_values

SPECS = [*load_registry().values(), SYNTHETIC]
INSTANTS = [START + timedelta(hours=h) for h in range(-20, 10 * 24 + 30, 17)] + [
    datetime(2024, 3, 30, 17, 59, 59, 999999, tzinfo=UTC),
    datetime(2024, 3, 30, 18, tzinfo=UTC),
]


def ids(spec: Dataset) -> str:
    return spec.name


def registry_with(spec: Dataset) -> dict[str, Dataset]:
    return load_registry() | {spec.name: spec}


def filled(tmp_path, spec: Dataset) -> Store:
    store = Store(tmp_path / "store", registry=registry_with(spec))
    for batch in history(spec):
        store.append(spec.name, batch)
    return store


def stored_rows(store: Store, spec: Dataset) -> pl.DataFrame:
    """Every stored vintage, read straight from the files (test-only: bypasses as_of)."""
    return pl.read_parquet(store.root / "curated" / spec.name / "*.parquet")


def bypassing(root, spec: Dataset, data: pl.DataFrame) -> Store:
    d = root / "curated" / spec.name
    d.mkdir(parents=True)
    data.write_parquet(d / "all.parquet")
    return Store(root, registry=registry_with(spec))


def view(store: Store, spec: Dataset, t: datetime) -> pl.DataFrame:
    return store.as_of(t).read(spec.name, event_start=START, event_end=END)


def reference(data: pl.DataFrame, spec: Dataset, t: datetime) -> dict:
    """The as-of rule restated in plain Python: per key, the last vintage known by t, in the
    order (knowledge_time, ingested_at)."""
    best: dict[tuple, tuple] = {}
    for r in data.sort("knowledge_time", "ingested_at").iter_rows(named=True):
        if r["knowledge_time"] <= t:
            best[tuple(r[c] for c in spec.key)] = tuple(r[c] for c in spec.values)
    return best


def as_dict(df: pl.DataFrame, spec: Dataset) -> dict:
    return {
        tuple(r[c] for c in spec.key): tuple(r[c] for c in spec.values)
        for r in df.iter_rows(named=True)
    }


@pytest.mark.parametrize("spec", SPECS, ids=ids)
def test_history_has_several_vintages_per_key(tmp_path, spec):
    data = stored_rows(filled(tmp_path, spec), spec)
    most = data.group_by(list(spec.key)).len()["len"].max()
    assert isinstance(most, int) and most >= 2


@pytest.mark.parametrize("spec", SPECS, ids=ids)
def test_time_travel_equivalence(tmp_path, spec):
    store = filled(tmp_path, spec)
    data = stored_rows(store, spec)
    for i, t in enumerate(INSTANTS):
        v = view(store, spec, t)
        assert as_dict(v, spec) == reference(data, spec, t), t
        truncated = bypassing(tmp_path / f"t{i}", spec, data.filter(pl.col("knowledge_time") <= t))
        assert v.equals(view(truncated, spec, t)), t


def poisoned(data: pl.DataFrame, spec: Dataset, t: datetime) -> pl.DataFrame:
    future = pl.col("knowledge_time") > t
    garbage = {
        c: pl.lit(1e9) if spec.columns[c] == pl.Float64 else pl.lit("POISON")
        for c in spec.values
        if spec.columns[c] in (pl.Float64, pl.String)
    }
    return data.with_columns(
        pl.when(future).then(g).otherwise(pl.col(c)).alias(c) for c, g in garbage.items()
    )


@pytest.mark.parametrize("spec", SPECS, ids=ids)
def test_future_poison_leaves_the_view_bit_identical(tmp_path, spec):
    store = filled(tmp_path, spec)
    data = stored_rows(store, spec)
    for i, t in enumerate(INSTANTS):
        dirty = bypassing(tmp_path / f"p{i}", spec, poisoned(data, spec, t))
        assert view(store, spec, t).equals(view(dirty, spec, t)), t


@pytest.mark.parametrize("spec", SPECS, ids=ids)
@pytest.mark.parametrize("before", [timedelta(microseconds=1), timedelta(days=3)])
def test_canary_is_invisible_before_its_knowledge_time(tmp_path, spec, before):
    series = series_values(spec)[0]
    event = START + timedelta(hours=50)
    canary_at = datetime(2024, 3, 29, 12, tzinfo=UTC)
    first = history(spec)[0]
    known = first.filter(pl.col("event_time") == event).head(1)
    known_vals = {c: known[c].item() for c in spec.values}
    planted = {c: (4242.0 if spec.columns[c] == pl.Float64 else known_vals[c]) for c in spec.values}
    canary = rows(spec, {(series, event): planted}, canary_at).with_columns(
        knowledge_time=pl.lit(canary_at, dtype=spec.schema["knowledge_time"])
    )
    earlier = rows(
        spec, {(series, event): known_vals}, canary_at - timedelta(days=31)
    ).with_columns(
        knowledge_time=pl.lit(canary_at - timedelta(days=31), dtype=spec.schema["knowledge_time"])
    )
    filt = dict(zip(spec.group, ([v] for v in series), strict=True))
    end = event + timedelta(hours=1)
    for data, expect_before in [(canary, None), (pl.concat([earlier, canary]), known_vals)]:
        store = bypassing(tmp_path / f"c{expect_before is None}{before}", spec, data)
        seen = store.as_of(canary_at - before).read(
            spec.name, event_start=event, event_end=end, **filt
        )
        got = None if seen.is_empty() else {c: seen[c].item() for c in spec.values}
        assert got == expect_before
        now = store.as_of(canary_at).read(spec.name, event_start=event, event_end=end, **filt)
        assert {c: now[c].item() for c in spec.values} == planted

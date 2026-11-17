"""Knowledge-view seam: vintages. Identical rows are not stored again; a changed value is a
new vintage that is knowable only from when we ingested it."""

from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from nordpower.store import Store


def utc(*a: int) -> datetime:
    return datetime(*a, tzinfo=UTC)


EVENT = utc(2024, 1, 15, 12)
RULE_KT = utc(2024, 1, 14, 12)  # 13:00 local on D-1
FIRST_SEEN = utc(2024, 2, 1)
REVISED_SEEN = utc(2024, 3, 1)


def row(price: float, ingested_at: datetime) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "zone": "DK1",
                "event_time": EVENT,
                "resolution": "PT60M",
                "price_eur_mwh": price,
                "knowledge_time": RULE_KT,
                "knowledge_time_grade": "assumed",
                "source": "test",
                "ingested_at": ingested_at,
                "raw_ref": f"snap-{ingested_at:%m%d}#0",
            }
        ]
    )


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def read(store: Store, t: datetime) -> pl.DataFrame:
    return store.as_of(t).read(
        "da_price", zones=["DK1"], event_start=utc(2024, 1, 15), event_end=utc(2024, 1, 16)
    )


def test_appending_identical_values_again_leaves_storage_unchanged(tmp_path):
    store = Store(tmp_path)
    store.append("da_price", row(50.0, FIRST_SEEN))
    before = snapshot(tmp_path)

    store.append("da_price", row(50.0, REVISED_SEEN))  # same value, later download

    assert snapshot(tmp_path) == before


def test_a_revised_value_is_a_second_vintage_known_from_its_ingestion(tmp_path):
    store = Store(tmp_path)
    store.append("da_price", row(50.0, FIRST_SEEN))
    store.append("da_price", row(55.0, REVISED_SEEN))

    assert read(store, RULE_KT)["price_eur_mwh"].to_list() == [50.0]
    assert read(store, utc(2024, 2, 29))["price_eur_mwh"].to_list() == [50.0]
    latest = read(store, REVISED_SEEN)
    assert latest["price_eur_mwh"].to_list() == [55.0]
    assert latest["knowledge_time"].to_list() == [REVISED_SEEN]
    assert latest["knowledge_time_grade"].to_list() == ["observed"]


def test_reverting_to_an_earlier_value_is_a_third_vintage(tmp_path):
    store = Store(tmp_path)
    store.append("da_price", row(50.0, FIRST_SEEN))
    store.append("da_price", row(55.0, REVISED_SEEN))
    store.append("da_price", row(50.0, utc(2024, 4, 1)))

    assert read(store, utc(2024, 3, 15))["price_eur_mwh"].to_list() == [55.0]
    assert read(store, utc(2024, 4, 1))["price_eur_mwh"].to_list() == [50.0]


def test_reappending_an_older_vintage_after_a_newer_one_stores_nothing(tmp_path):
    # e.g. curate re-reads an old raw snapshot after a newer one was curated
    store = Store(tmp_path)
    store.append("da_price", row(50.0, FIRST_SEEN))
    store.append("da_price", row(55.0, REVISED_SEEN))
    before = snapshot(tmp_path)

    store.append("da_price", row(50.0, FIRST_SEEN))

    assert snapshot(tmp_path) == before


def test_duplicate_rows_within_one_append_are_stored_once(tmp_path):
    store = Store(tmp_path)
    store.append("da_price", pl.concat([row(50.0, FIRST_SEEN), row(50.0, FIRST_SEEN)]))
    before = snapshot(tmp_path)
    store.append("da_price", row(50.0, FIRST_SEEN))
    assert snapshot(tmp_path) == before
    assert len(read(store, FIRST_SEEN)) == 1

from datetime import UTC, datetime

import polars as pl

from nordpower.store import Store


def utc(*a: int) -> datetime:
    return datetime(*a, tzinfo=UTC)


def price_row(value: float, knowledge_time: datetime) -> dict:
    return {
        "zone": "DK1",
        "event_time": utc(2024, 1, 15, 12),
        "resolution": "PT60M",
        "price_eur_mwh": value,
        "knowledge_time": knowledge_time,
        "knowledge_time_grade": "assumed",
        "source": "test",
        "ingested_at": knowledge_time,  # observed live: seen the moment it was knowable
        "raw_ref": "test#0",
    }


def read_dk1(store: Store, t: datetime) -> list[float]:
    df = store.as_of(t).read(
        "da_price", zones=["DK1"], event_start=utc(2024, 1, 15), event_end=utc(2024, 1, 16)
    )
    return df["price_eur_mwh"].to_list()


def test_value_is_invisible_before_its_knowledge_time(tmp_path):
    store = Store(tmp_path)
    store.append("da_price", pl.DataFrame([price_row(50.0, utc(2024, 1, 14, 12))]))

    assert read_dk1(store, utc(2024, 1, 14, 11, 59)) == []
    assert read_dk1(store, utc(2024, 1, 14, 12)) == [50.0]


def test_view_returns_latest_vintage_known_at_its_instant(tmp_path):
    store = Store(tmp_path)
    store.append("da_price", pl.DataFrame([price_row(50.0, utc(2024, 1, 14, 12))]))
    store.append("da_price", pl.DataFrame([price_row(55.0, utc(2024, 1, 20))]))

    assert read_dk1(store, utc(2024, 1, 19)) == [50.0]
    assert read_dk1(store, utc(2024, 1, 21)) == [55.0]


def test_view_reports_its_instant(tmp_path):
    t = utc(2024, 1, 14, 10, 30)
    assert Store(tmp_path).as_of(t).now == t

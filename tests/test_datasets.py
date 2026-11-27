"""Dataset registry (#19, D-043): parsing, validation on append, key-aware reads and
per-dataset quality checks."""

from datetime import UTC, date, datetime, timedelta

import polars as pl
import pytest

from nordpower.datasets import load_registry, parse_registry
from nordpower.quality import check
from nordpower.store import Store
from tests.leakage.registry_data import SYNTHETIC, rows

EVENT = datetime(2024, 3, 25, 11, tzinfo=UTC)


def store(tmp_path) -> Store:
    return Store(tmp_path, registry=load_registry() | {SYNTHETIC.name: SYNTHETIC})


def flow(border: str, direction: str, mw: float, ingested_at: datetime, t=EVENT) -> pl.DataFrame:
    return rows(SYNTHETIC, {((border, direction), t): {"flow_mw": mw, "note": "x"}}, ingested_at)


def test_da_price_is_registered_with_its_phase_0_shape():
    spec = load_registry()["da_price"]
    assert spec.key == ("zone", "event_time")
    assert spec.values == ("resolution", "price_eur_mwh")
    assert spec.mtu == "da_era" and spec.publication_rule == "da_price"
    assert set(spec.quality) == {"completeness", "duplicate", "range"}


@pytest.mark.parametrize(
    "toml, error",
    [
        ('[x]\nkey=["zone"]\nmtu="none"\n[x.columns]\nzone="String"', "event_time"),
        (
            '[x]\nkey=["zone","event_time"]\nmtu="none"\n[x.columns]\nevent_time="Datetime"',
            "not declared",
        ),
        ('[x]\nkey=["event_time"]\nmtu="none"\n[x.columns]\nevent_time="Date"', "UTC Datetime"),
        (
            '[x]\nkey=["event_time"]\nmtu="none"\n[x.columns]\nevent_time="Datetime"\nsource="String"',
            "meta",
        ),
        (
            '[x]\nkey=["event_time"]\nmtu="none"\nquality=["vibes"]\n[x.columns]\nevent_time="Datetime"',
            "quality",
        ),
    ],
)
def test_a_malformed_registry_entry_is_refused(toml, error):
    with pytest.raises(ValueError, match=error):
        parse_registry(toml)


def test_appending_rows_that_do_not_match_the_registry_fails_loudly(tmp_path):
    s = store(tmp_path)
    good = flow("DK1-DK2", "in", 100.0, datetime(2024, 4, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="missing"):
        s.append(SYNTHETIC.name, good.drop("note"))
    with pytest.raises(ValueError, match="unexpected"):
        s.append(SYNTHETIC.name, good.with_columns(extra=pl.lit(1)))
    with pytest.raises(ValueError, match="dtypes"):
        s.append(SYNTHETIC.name, good.with_columns(pl.col("flow_mw").cast(pl.Int64)))
    with pytest.raises(KeyError, match="registry"):
        s.append("not_a_dataset", good)
    assert not (tmp_path / "curated").exists()


def test_a_non_zone_dataset_appends_versions_and_reads(tmp_path):
    s = store(tmp_path)
    first, later = datetime(2024, 4, 1, tzinfo=UTC), datetime(2024, 4, 5, tzinfo=UTC)
    assert (
        s.append(
            SYNTHETIC.name,
            pl.concat([flow("DK1-DK2", "in", 100.0, first), flow("DK1-DK2", "out", 7.0, first)]),
        )
        == 2
    )
    assert (
        s.append(SYNTHETIC.name, flow("DK1-DK2", "in", 100.0, later)) == 0
    )  # same value: no vintage
    assert s.append(SYNTHETIC.name, flow("DK1-DK2", "in", 120.0, later)) == 1  # revision

    def mw(t: datetime, **where) -> list[float]:
        v = s.as_of(t).read(
            SYNTHETIC.name, event_start=EVENT, event_end=EVENT + timedelta(hours=1), **where
        )
        return v["flow_mw"].to_list()

    assert mw(datetime(2024, 4, 2, tzinfo=UTC), direction=["in"]) == [100.0]
    assert mw(datetime(2024, 4, 6, tzinfo=UTC), direction=["in"]) == [120.0]
    assert sorted(mw(datetime(2024, 4, 6, tzinfo=UTC))) == [7.0, 120.0]


def test_reads_filter_only_on_key_columns(tmp_path):
    s = store(tmp_path)
    s.append(SYNTHETIC.name, flow("DK1-DK2", "in", 100.0, datetime(2024, 4, 1, tzinfo=UTC)))
    view = s.as_of(datetime(2024, 4, 2, tzinfo=UTC))
    end = EVENT + timedelta(hours=1)
    with pytest.raises(ValueError, match="key columns"):
        view.read(SYNTHETIC.name, event_start=EVENT, event_end=end, note=["x"])
    with pytest.raises(ValueError, match="key columns"):  # no zone in this dataset
        view.read(SYNTHETIC.name, event_start=EVENT, event_end=end, zones=["DK1"])


def test_an_empty_dataset_reads_as_an_empty_frame_with_its_schema(tmp_path):
    v = store(tmp_path).as_of(datetime(2024, 4, 2, tzinfo=UTC))
    df = v.read(SYNTHETIC.name, event_start=EVENT, event_end=EVENT + timedelta(hours=1))
    assert df.is_empty() and dict(df.schema) == SYNTHETIC.schema


def test_quality_checks_run_per_series_of_any_dataset():
    day = date(2024, 3, 25)
    start = datetime(2024, 3, 24, 23, tzinfo=UTC)
    hours = [start + timedelta(hours=i) for i in range(24)]
    full = {(("DK1-DK2", "in"), t): {"flow_mw": 1.0, "note": "x"} for t in hours}
    gappy = {(("DK1-DK2", "out"), t): {"flow_mw": 1.0, "note": "x"} for t in hours[:-1]}
    data = rows(SYNTHETIC, full | gappy, datetime(2024, 4, 1, tzinfo=UTC))
    asked = {(("DK1-DK2", "in"), day), (("DK1-DK2", "out"), day), (("DK1-NO2", "in"), day)}
    found = [(f["check"], f["border"], f["direction"]) for f in check(SYNTHETIC, data, asked)]
    assert found == [("completeness", "DK1-DK2", "out"), ("completeness", "DK1-NO2", "in")]
    dup = pl.concat([data, data.head(1)])
    assert ("duplicate", "DK1-DK2", "in") in [
        (f["check"], f["border"], f["direction"]) for f in check(SYNTHETIC, dup)
    ]

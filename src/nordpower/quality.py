"""Data-quality checks on one raw snapshot's curated rows (D-033), per registered dataset
(D-043).

Checks report; they never drop or change data. Each failure names a check, the series it
concerns (the dataset's key without event_time, e.g. a zone) and a delivery day, so later
phases can block exactly the affected ranges."""

import tomllib
from collections.abc import Iterable
from datetime import date
from functools import cache
from pathlib import Path

import polars as pl

from nordpower.datasets import Dataset, load_registry
from nordpower.timeutil import RESOLUTION, da_mtus, delivery_day_of, mtus_of

# ponytail: path assumes a source checkout, same as publication.py
BOUNDS = Path(__file__).resolve().parents[2] / "configs" / "quality.toml"


@cache
def load_bounds(path: Path = BOUNDS) -> dict[str, dict]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def expected_event_times(spec: Dataset, day: date) -> list | None:
    """The event times one series of `spec` should hold on a delivery day, or None if the
    dataset has no fixed grid."""
    if spec.mtu == "da_era":
        return da_mtus(day)
    if spec.mtu == "none":
        return None
    return mtus_of(day, RESOLUTION[spec.mtu])


def check(
    spec: Dataset,
    rows: pl.DataFrame,
    requested: Iterable[tuple[tuple, date]] = (),
    bounds: dict[str, dict] | None = None,
) -> list[dict]:
    """Failures for `rows` (key and value columns of `spec`) covering whole delivery days.

    `requested` lists the (series, delivery day) pairs the snapshot asked for, a series being
    the tuple of the dataset's group columns; one with no rows at all fails completeness.
    Details hold counts and times, never values: the checks also run over the vault (D-033)."""
    ranges = (load_bounds() if bounds is None else bounds).get(spec.name, {}).get("range", {})
    group = list(spec.group)
    failures = []

    def fail(check: str, series: tuple, day: date, detail: str) -> None:
        failures.append(
            dict(zip(group, series, strict=True))
            | {"check": check, "delivery_day": day, "detail": detail}
        )

    days = rows.with_columns(
        delivery_day=pl.col("event_time").map_elements(delivery_day_of, return_dtype=pl.Date)
    )
    present = {(tuple(r[:-1]), r[-1]) for r in days.select(*group, "delivery_day").iter_rows()}
    if "completeness" in spec.quality:
        for series, day in sorted(set(requested) - present):
            expected = expected_event_times(spec, day)
            n = "" if expected is None else f"{len(expected)} MTUs expected: "
            fail("completeness", series, day, f"{n}no rows")
    for keys, g in days.group_by(*group, "delivery_day", maintain_order=True):
        *series, day = keys
        assert isinstance(day, date)
        series = tuple(series)
        times = g["event_time"].to_list()
        expected = expected_event_times(spec, day)
        if "completeness" in spec.quality and expected is not None:
            want = set(expected)
            missing, unexpected = want - set(times), set(times) - want
            if missing or unexpected:
                fail(
                    "completeness",
                    series,
                    day,
                    f"{len(want)} MTUs expected: missing {len(missing)}, unexpected "
                    f"{len(unexpected)}; first missing {min(missing, default=None)}",
                )
        if "duplicate" in spec.quality and len(times) != len(set(times)):
            fail("duplicate", series, day, f"{len(times) - len(set(times))} repeated event times")
        if "range" in spec.quality:
            for column, b in ranges.items():
                bad = g.filter(
                    (pl.col(column) < b["min"])
                    | (pl.col(column) > b["max"])
                    | pl.col(column).is_nan()
                )
                if len(bad):
                    fail(
                        "range",
                        series,
                        day,
                        f"{len(bad)} {b.get('label', column)} outside [{b['min']}, {b['max']}] "
                        "or NaN, "
                        f"first at {bad['event_time'].min()}",
                    )
    return sorted(failures, key=lambda f: (*(f[c] for c in group), f["delivery_day"], f["check"]))


def check_da_price(
    rows: pl.DataFrame, requested: frozenset[tuple[str, date]] = frozenset()
) -> list[dict]:
    """`check` for da_price, with requested zone-days as (zone, day) pairs."""
    spec = load_registry()["da_price"]
    return check(spec, rows, {((zone,), day) for zone, day in requested})

"""Data-quality checks on one raw snapshot's curated day-ahead prices (D-033).

Checks report; they never drop or change data. Each failure names a check, a zone and a
delivery day, so later phases can block exactly the affected ranges."""

import tomllib
from datetime import date
from functools import cache
from pathlib import Path

import polars as pl

from nordpower.timeutil import da_mtus, delivery_day_of

# ponytail: path assumes a source checkout, same as publication.py
BOUNDS = Path(__file__).resolve().parents[2] / "configs" / "quality.toml"


@cache
def load_bounds(path: Path = BOUNDS) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))["da_price"]


def check_da_price(
    rows: pl.DataFrame, requested: frozenset[tuple[str, date]] = frozenset()
) -> list[dict]:
    """Failures for rows (zone, event_time, price_eur_mwh) covering whole delivery days:
    completeness against the expected MTUs, duplicate event times, price outside the bounds
    (or NaN). A requested zone-day with no rows at all fails completeness too. Details hold
    counts and times, never prices: the checks also run over the vault period (D-033)."""
    bounds = load_bounds()
    failures = []

    def fail(check: str, zone: str, day: date, detail: str) -> None:
        failures.append({"check": check, "zone": zone, "delivery_day": day, "detail": detail})

    days = rows.with_columns(
        delivery_day=pl.col("event_time").map_elements(delivery_day_of, return_dtype=pl.Date)
    )
    for zone, day in sorted(requested - set(days.select("zone", "delivery_day").iter_rows())):
        fail("completeness", zone, day, f"{len(da_mtus(day))} MTUs expected: no rows")
    for (zone, day), g in days.group_by("zone", "delivery_day", maintain_order=True):
        assert isinstance(zone, str) and isinstance(day, date)
        times = g["event_time"].to_list()
        expected = set(da_mtus(day))
        missing, unexpected = expected - set(times), set(times) - expected
        if missing or unexpected:
            fail(
                "completeness",
                zone,
                day,
                f"{len(expected)} MTUs expected: missing {len(missing)}, unexpected "
                f"{len(unexpected)}; first missing {min(missing, default=None)}",
            )
        if len(times) != len(set(times)):
            fail("duplicate", zone, day, f"{len(times) - len(set(times))} repeated event times")
        out_of_range = g.filter(
            (pl.col("price_eur_mwh") < bounds["price_min"])
            | (pl.col("price_eur_mwh") > bounds["price_max"])
            | pl.col("price_eur_mwh").is_nan()
        )
        if len(out_of_range):
            fail(
                "range",
                zone,
                day,
                f"{len(out_of_range)} prices outside [{bounds['price_min']}, "
                f"{bounds['price_max']}] or NaN, first at {out_of_range['event_time'].min()}",
            )
    return sorted(failures, key=lambda f: (f["zone"], f["delivery_day"], f["check"]))

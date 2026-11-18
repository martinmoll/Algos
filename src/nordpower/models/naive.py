"""Naive day-ahead forecast: same hour of D-7 for Mon/Sat/Sun, of D-1 otherwise, at the
delivery day's market time unit."""

from datetime import date

import polars as pl

from nordpower.store import KnowledgeView
from nordpower.timeutil import (
    RESOLUTION,
    da_mtus,
    delivery_span,
    hour_start,
    hours_of,
    local_clock_hour,
    naive_reference_day,
)

UTC_TIME = pl.Datetime("us", "UTC")


def _clock_hours(instants: list) -> pl.DataFrame:
    return pl.DataFrame(
        {"event_time": instants, "clock_hour": [local_clock_hour(t) for t in instants]},
        schema={"event_time": UTC_TIME, "clock_hour": pl.Int8},
    )


class Naive:
    name = "naive"
    rule = (
        "same hour of D-7 for Mon/Sat/Sun, D-1 otherwise. "
        "DST: hours are matched by local clock hour; a reference hour missing on the spring "
        "DST day is filled from the previous local hour; the repeated autumn hour is averaged; "
        "both 02:00s of an autumn DST target day get the same forecast. "
        "Resolution (D-032): quarter-hours are averaged to hourly means, using only complete "
        "hours (MTU durations summing to 60 minutes); each MTU of the delivery day (hourly or "
        "15-minute) gets the forecast of its clock hour."
    )

    def __init__(self, zones: list[str]):
        self.zones = zones

    def fit(self, view: KnowledgeView) -> None:
        pass

    def predict(self, view: KnowledgeView, delivery_day: date) -> pl.DataFrame:
        """Forecasts per MTU of the delivery day: columns zone, event_time, forecast."""
        ref_day = naive_reference_day(delivery_day)
        start, end = delivery_span(ref_day, ref_day)
        prices = view.read("da_price", zones=self.zones, event_start=start, event_end=end)
        if prices.is_empty():
            return pl.DataFrame(
                schema={"zone": pl.String, "event_time": UTC_TIME, "forecast": pl.Float64}
            )
        minutes_per_mtu = {code: d.total_seconds() / 60 for code, d in RESOLUTION.items()}
        hourly = (
            prices.with_columns(
                minutes=pl.col("resolution").replace_strict(
                    minutes_per_mtu, return_dtype=pl.Float64
                ),
                event_time=hour_start(pl.col("event_time")),
            )
            .group_by("zone", "event_time")
            .agg(pl.col("price_eur_mwh").mean(), pl.col("minutes").sum())
            .filter(pl.col("minutes") == 60)  # an incomplete hour stays missing (D-028, D-032)
        )
        ref_clock = _clock_hours(hours_of(ref_day))
        by_clock_hour = (
            hourly.join(ref_clock, on="event_time")
            .group_by("zone", "clock_hour")
            .agg(forecast=pl.col("price_eur_mwh").mean())  # averages the repeated autumn hour
        )
        grid = pl.DataFrame({"zone": self.zones}).join(
            pl.DataFrame({"clock_hour": range(24)}, schema={"clock_hour": pl.Int8}), how="cross"
        )
        # D-028: only a clock hour the reference day does not have (spring DST) is filled
        # from h-1; ordinary data gaps stay missing.
        skipped = set(range(24)) - set(ref_clock["clock_hour"].to_list())
        filled = (
            grid.join(by_clock_hour, on=["zone", "clock_hour"], how="left")
            .sort("zone", "clock_hour")
            .with_columns(
                pl.when(pl.col("clock_hour").is_in(list(skipped)))
                .then(pl.col("forecast").shift(1).over("zone"))
                .otherwise(pl.col("forecast"))
                .alias("forecast")
            )
        )
        return (
            _clock_hours(da_mtus(delivery_day))
            .join(filled, on="clock_hour")
            .drop_nulls("forecast")
            .select("zone", "event_time", "forecast")
            .sort("zone", "event_time")
        )

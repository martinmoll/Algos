"""Naive day-ahead forecast: same hour of D-7 for Mon/Sat/Sun, of D-1 otherwise."""

from datetime import date

import polars as pl

from nordpower.store import KnowledgeView
from nordpower.timeutil import delivery_span, hours_of, local_clock_hour, naive_reference_day

UTC_TIME = pl.Datetime("us", "UTC")


def _clock_hours(day: date) -> pl.DataFrame:
    hours = hours_of(day)
    return pl.DataFrame(
        {"event_time": hours, "clock_hour": [local_clock_hour(h) for h in hours]},
        schema={"event_time": UTC_TIME, "clock_hour": pl.Int8},
    )


class Naive:
    name = "naive"
    rule = (
        "same hour of D-7 for Mon/Sat/Sun, D-1 otherwise; hourly prices. "
        "DST: hours are matched by local clock hour; a reference hour missing on the spring "
        "DST day is filled from the previous local hour; the repeated autumn hour is averaged; "
        "both 02:00s of an autumn DST target day get the same forecast."
    )

    def __init__(self, zones: list[str]):
        self.zones = zones

    def fit(self, view: KnowledgeView) -> None:
        pass

    def predict(self, view: KnowledgeView, delivery_day: date) -> pl.DataFrame:
        """Hourly forecasts: columns zone, event_time, forecast."""
        ref_day = naive_reference_day(delivery_day)
        start, end = delivery_span(ref_day, ref_day)
        prices = view.read("da_price", zones=self.zones, event_start=start, event_end=end)
        if prices.is_empty():
            return pl.DataFrame(
                schema={"zone": pl.String, "event_time": UTC_TIME, "forecast": pl.Float64}
            )
        ref_clock = _clock_hours(ref_day)
        # ponytail: hourly prices only; the inner join drops :15/:30/:45 rows, so ticket #7
        # must aggregate 15-minute prices to hourly means before this join
        by_clock_hour = (
            prices.join(ref_clock, on="event_time")
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
            _clock_hours(delivery_day)
            .join(filled, on="clock_hour")
            .drop_nulls("forecast")
            .select("zone", "event_time", "forecast")
            .sort("zone", "event_time")
        )

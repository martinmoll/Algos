"""Naive day-ahead forecast: same hour of D-7 for Mon/Sat/Sun, of D-1 otherwise."""

from datetime import date

import polars as pl

from nordpower.store import KnowledgeView
from nordpower.timeutil import delivery_span, hours_of, naive_reference_day

EMPTY = pl.DataFrame(
    schema={"zone": pl.String, "event_time": pl.Datetime("us", "UTC"), "forecast": pl.Float64}
)


class Naive:
    name = "naive"
    rule = "same hour of D-7 for Mon/Sat/Sun, D-1 otherwise; hourly prices"

    def __init__(self, zones: list[str]):
        self.zones = zones

    def fit(self, view: KnowledgeView) -> None:
        pass

    def predict(self, view: KnowledgeView, delivery_day: date) -> pl.DataFrame:
        """Hourly forecasts: columns zone, event_time, forecast."""
        ref_day = naive_reference_day(delivery_day)
        target_hours, ref_hours = hours_of(delivery_day), hours_of(ref_day)
        if len(target_hours) != len(ref_hours):
            raise NotImplementedError("DST day mapping is ticket #3")
        start, end = delivery_span(ref_day, ref_day)
        prices = view.read("da_price", zones=self.zones, event_start=start, event_end=end)
        if prices.is_empty():
            return EMPTY
        return prices.select(
            "zone",
            (pl.col("event_time") + (target_hours[0] - ref_hours[0])).alias("event_time"),
            pl.col("price_eur_mwh").alias("forecast"),
        )

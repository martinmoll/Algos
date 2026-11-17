"""Bitemporal, append-only store. The only read path is `Store.as_of(t)`.

Each dataset is a directory of Parquet parts. Every row carries `event_time` and
`knowledge_time`; a view at instant t sees, per (zone, event_time), the latest row
with knowledge_time <= t.
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import polars as pl

KEY = ["zone", "event_time"]


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def append(self, dataset: str, rows: pl.DataFrame) -> None:
        if rows.is_empty():
            return
        d = self.root / "curated" / dataset
        d.mkdir(parents=True, exist_ok=True)
        rows.write_parquet(d / f"{uuid4().hex}.parquet")

    def as_of(self, t: datetime) -> "KnowledgeView":
        if t.tzinfo is None:
            raise ValueError("as_of needs a timezone-aware instant")
        return KnowledgeView(self, t)


class KnowledgeView:
    """The data as it was knowable at `now`. Holds no data from after `now`."""

    def __init__(self, store: Store, now: datetime):
        self._store = store
        self.now = now

    def read(
        self, dataset: str, *, zones: list[str], event_start: datetime, event_end: datetime
    ) -> pl.DataFrame:
        """Latest known vintage per (zone, event_time), event_start <= event_time < event_end."""
        d = self._store.root / "curated" / dataset
        if not d.exists() or not any(d.glob("*.parquet")):
            return pl.DataFrame()
        # ponytail: scans every part per read; partition by knowledge month when backfill gets big
        return (
            pl.scan_parquet(d / "*.parquet")
            .filter(
                (pl.col("knowledge_time") <= self.now)
                & pl.col("zone").is_in(zones)
                & (pl.col("event_time") >= event_start)
                & (pl.col("event_time") < event_end)
            )
            .sort("knowledge_time")
            .group_by(KEY, maintain_order=True)
            .last()
            .sort(KEY)
            .collect()
        )

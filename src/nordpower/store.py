"""Bitemporal, append-only store. The only read path is `Store.as_of(t)`.

Each dataset is a directory of Parquet parts, written once and never changed. Every row
is a vintage: a value for (zone, event_time) plus the time it became knowable. A view at
instant t sees, per (zone, event_time), the latest vintage with knowledge_time <= t.
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import polars as pl

KEY = ["zone", "event_time"]
META = ["knowledge_time", "knowledge_time_grade", "source", "ingested_at", "raw_ref"]


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def _parts(self, dataset: str) -> pl.LazyFrame | None:
        d = self.root / "curated" / dataset
        if not d.exists() or not any(d.glob("*.parquet")):
            return None
        # ponytail: scans every part; partition by knowledge month when backfill gets big
        return pl.scan_parquet(d / "*.parquet").sort("knowledge_time", "ingested_at")

    def append(self, dataset: str, rows: pl.DataFrame) -> int:
        """Store the rows that are new vintages; returns how many were stored (D-029).

        Each row is compared with the vintage we held for its key as of the row's own
        `ingested_at` (so re-curating an old snapshot after a newer one stores nothing).
        Identical values are dropped. A row that changes a held value cannot have been
        known before we ingested it: its knowledge time becomes max(rule time, ingested_at),
        graded `observed` when that moves it later. A row with no earlier vintage keeps the
        knowledge time it was given.
        """
        rows = rows.unique(subset=KEY, keep="last", maintain_order=True).sort("ingested_at")
        values = [c for c in rows.columns if c not in KEY and c not in META]
        stored = self._parts(dataset)
        if stored is not None:
            held = (
                stored.select(*KEY, "ingested_at", *values)
                .collect()
                .rename({c: f"{c}_prev" for c in values})
                .with_columns(_seen=pl.lit(True))
                .sort("ingested_at")
            )
            prev = rows.join_asof(
                held, on="ingested_at", by=KEY, strategy="backward", check_sortedness=False
            )  # both sides sorted by ingested_at above
            changed = pl.any_horizontal([pl.col(c).ne_missing(pl.col(f"{c}_prev")) for c in values])
            seen = pl.col("_seen").is_not_null()
            late = seen & (pl.col("ingested_at") > pl.col("knowledge_time"))
            rows = (
                prev.filter(~seen | changed)
                .with_columns(
                    knowledge_time=pl.when(late)
                    .then(pl.col("ingested_at"))
                    .otherwise(pl.col("knowledge_time")),
                    knowledge_time_grade=pl.when(late)
                    .then(pl.lit("observed"))
                    .otherwise(pl.col("knowledge_time_grade")),
                )
                .select(rows.columns)
            )
        if rows.is_empty():
            return 0
        d = self.root / "curated" / dataset
        d.mkdir(parents=True, exist_ok=True)
        with open(d / f"{uuid4().hex}.parquet", "xb") as f:  # "x": never overwrite a part
            rows.write_parquet(f)
        return len(rows)

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
        stored = self._store._parts(dataset)
        if stored is None:
            return pl.DataFrame()
        return (
            stored.filter(
                (pl.col("knowledge_time") <= self.now)
                & pl.col("zone").is_in(zones)
                & (pl.col("event_time") >= event_start)
                & (pl.col("event_time") < event_end)
            )
            .group_by(KEY, maintain_order=True)
            .last()
            .sort(KEY)
            .collect()
        )

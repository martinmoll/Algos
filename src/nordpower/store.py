"""Bitemporal, append-only store. The only read path is `Store.as_of(t)`.

Each dataset is a directory of Parquet parts, written once and never changed. Every row
is a vintage: a value for (zone, event_time) plus the time it became knowable. A view at
instant t sees, per (zone, event_time), the latest vintage with knowledge_time <= t.
"""

import json
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from uuid import uuid4

import polars as pl

from nordpower.timeutil import local_instant

KEY = ["zone", "event_time"]
META = ["knowledge_time", "knowledge_time_grade", "source", "ingested_at", "raw_ref"]
# ponytail: path assumes a source checkout, same as publication.py
REPO = Path(__file__).resolve().parents[2]
VAULT_CONFIG = REPO / "configs" / "vault.toml"
DECISIONS = REPO / "docs" / "DECISIONS.md"
PACKAGE = Path(__file__).resolve().parent


class VaultSealed(Exception):
    """A read at or after the vault boundary without a vault token (D-014)."""


@dataclass(frozen=True, eq=False)
class VaultToken:
    """Proof of one logged vault opening; only `Store.open_vault` issues valid ones."""

    purpose: str
    opened_at: datetime
    caller: str

    def record(self) -> dict:
        """The vault-log entry for this opening (also copied into a vault run's config)."""
        return {
            "opened_at": self.opened_at.isoformat(),
            "purpose": self.purpose,
            "caller": self.caller,
        }


def _caller() -> str:
    """file:line of the first frame outside the nordpower package: who asked for the vault."""
    frame = sys._getframe(1)
    while frame.f_back and Path(frame.f_code.co_filename).resolve().is_relative_to(PACKAGE):
        frame = frame.f_back
    path = Path(frame.f_code.co_filename).resolve()
    shown = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
    return f"{shown}:{frame.f_lineno}"


def load_vault_start(path: Path = VAULT_CONFIG) -> datetime:
    """The vault boundary: 00:00 Europe/Oslo on the configured day, as a UTC instant."""
    day = date.fromisoformat(tomllib.loads(path.read_text(encoding="utf-8"))["start"])
    return local_instant(day, time(0))


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.vault_start = load_vault_start()
        self._issued: set[VaultToken] = set()

    def open_vault(self, purpose: str) -> VaultToken:
        """Open the vault: append (time, purpose, caller) to the vault log, return a token.

        The purpose must cite the decision-log entry (D-nnn) that pre-registers the one
        configuration being evaluated (docs/plan/03-no-lookahead.md §6)."""
        cited = re.findall(r"\bD-\d{3}\b", purpose)
        log = DECISIONS.read_text(encoding="utf-8")
        if not cited or not all(f"## {d} " in log for d in cited):
            raise ValueError("a vault opening must cite an existing decision-log entry (D-nnn)")
        token = VaultToken(purpose, datetime.now(UTC), _caller())
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / "vault_log.jsonl", "a", encoding="utf-8") as f:  # append-only
            f.write(json.dumps(token.record()) + "\n")
        self._issued.add(token)
        return token

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

    def as_of(self, t: datetime, *, vault: VaultToken | None = None) -> "KnowledgeView":
        """The data as knowable at t. At or after the vault boundary, needs a token."""
        if t.tzinfo is None:
            raise ValueError("as_of needs a timezone-aware instant")
        opened = vault in self._issued  # identity: eq=False
        if t >= self.vault_start and not opened:
            raise VaultSealed(
                f"as_of({t.isoformat()}) is inside the vault (sealed from "
                f"{self.vault_start.isoformat()}); opening it needs store.open_vault(purpose) "
                "and a decision-log entry"
            )
        return KnowledgeView(self, t, sealed_from=None if opened else self.vault_start)


class KnowledgeView:
    """The data as it was knowable at `now`. Holds no data from after `now`, and without a
    vault token no event at or after the vault boundary (`sealed_from`)."""

    def __init__(self, store: Store, now: datetime, sealed_from: datetime | None):
        self._store = store
        self.now = now
        self._sealed_from = sealed_from

    def read(
        self, dataset: str, *, zones: list[str], event_start: datetime, event_end: datetime
    ) -> pl.DataFrame:
        """Latest known vintage per (zone, event_time), event_start <= event_time < event_end."""
        if self._sealed_from is not None:
            event_end = min(event_end, self._sealed_from)
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

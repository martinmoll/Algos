"""Raw snapshots -> curated, bitemporal tables in the store."""

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from nordpower.publication import ASSUMED, assumed_knowledge_time, load_rules
from nordpower.store import Store


def curate_elspotprices(raw_root: Path, store: Store) -> int:
    """Turn every Elspotprices raw snapshot into `da_price` vintages. Returns new vintages stored;
    re-curating unchanged snapshots stores nothing."""
    n = 0
    rules = load_rules()
    for path in sorted((raw_root / "energidataservice" / "Elspotprices").glob("*.json")):
        snap = json.loads(path.read_text(encoding="utf-8"))
        ingested_at = datetime.fromisoformat(snap["ingested_at"])
        rows = []
        for i, r in enumerate(snap["records"]):
            if r["SpotPriceEUR"] is None:
                continue
            event_time = datetime.fromisoformat(r["HourUTC"]).replace(tzinfo=UTC)
            rows.append(
                {
                    "zone": r["PriceArea"],
                    "event_time": event_time,
                    "resolution": "PT60M",
                    "price_eur_mwh": float(r["SpotPriceEUR"]),
                    "knowledge_time": assumed_knowledge_time("da_price", event_time, rules),
                    "knowledge_time_grade": ASSUMED,
                    "source": "energidataservice:Elspotprices",
                    "ingested_at": ingested_at,
                    "raw_ref": f"{path.name}#{i}",
                }
            )
        n += store.append("da_price", pl.DataFrame(rows))
    return n

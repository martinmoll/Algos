"""Raw snapshots -> curated, bitemporal tables in the store."""

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from nordpower.store import Store

# ponytail: the D-024 rule is a timeutil constant; moves to the reviewed
# publication-rules config in ticket #4
from nordpower.timeutil import da_assumed_knowledge_time


def curate_elspotprices(raw_root: Path, store: Store) -> int:
    """Turn every Elspotprices raw snapshot into `da_price` rows. Returns rows appended."""
    n = 0
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
                    "knowledge_time": da_assumed_knowledge_time(event_time),
                    "knowledge_time_grade": "assumed",
                    "source": "energidataservice:Elspotprices",
                    "ingested_at": ingested_at,
                    "raw_ref": f"{path.name}#{i}",
                }
            )
        # ponytail: re-curating appends identical rows (harmless: views take the latest);
        # dedupe of identical vintages is ticket #4
        store.append("da_price", pl.DataFrame(rows))
        n += len(rows)
    return n

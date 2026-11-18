"""Raw snapshots -> curated, bitemporal tables in the store."""

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from nordpower.ingest.energidataservice import PRICE_DATASETS, SOURCE
from nordpower.publication import ASSUMED, assumed_knowledge_time, load_rules
from nordpower.store import Store
from nordpower.timeutil import da_resolution, delivery_day_of


def curate_prices(raw_root: Path, store: Store) -> int:
    """Turn every Elspotprices and DayAheadPrices raw snapshot into `da_price` vintages at
    native resolution. Returns new vintages stored; re-curating stores nothing."""
    n = 0
    rules = load_rules()
    for dataset, (time_field, price_field, publishes) in PRICE_DATASETS.items():
        for path in sorted((raw_root / SOURCE / dataset).glob("*.json")):
            snap = json.loads(path.read_text(encoding="utf-8"))
            ingested_at = datetime.fromisoformat(snap["ingested_at"])
            rows = []
            for i, r in enumerate(snap["records"]):
                if r[price_field] is None:
                    continue
                event_time = datetime.fromisoformat(r[time_field]).replace(tzinfo=UTC)
                resolution = da_resolution(delivery_day_of(event_time))
                if resolution != publishes:
                    raise ValueError(
                        f"{path.name}#{i}: {dataset} row at {event_time} is in the "
                        f"{resolution} era; this dataset only publishes {publishes}"
                    )
                rows.append(
                    {
                        "zone": r["PriceArea"],
                        "event_time": event_time,
                        "resolution": resolution,
                        "price_eur_mwh": float(r[price_field]),
                        "knowledge_time": assumed_knowledge_time("da_price", event_time, rules),
                        "knowledge_time_grade": ASSUMED,
                        "source": f"{SOURCE}:{dataset}",
                        "ingested_at": ingested_at,
                        "raw_ref": f"{path.name}#{i}",
                    }
                )
            if rows:
                n += store.append("da_price", pl.DataFrame(rows))
    return n

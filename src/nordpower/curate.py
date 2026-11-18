"""Raw snapshots -> curated, bitemporal tables in the store."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import polars as pl

from nordpower.ingest.energidataservice import PRICE_DATASETS, SOURCE
from nordpower.publication import ASSUMED, assumed_knowledge_time, load_rules
from nordpower.quality import check_da_price
from nordpower.store import Store
from nordpower.timeutil import da_resolution, delivery_day_of


def curate_prices(raw_root: Path, store: Store) -> tuple[int, dict[str, dict]]:
    """Turn every Elspotprices and DayAheadPrices raw snapshot into `da_price` vintages at
    native resolution, checking each snapshot's data quality first (D-033).

    Returns the number of new vintages stored (re-curating stores nothing) and a per-zone
    quality summary, where each zone-day counts as checked by the latest snapshot holding it."""
    n = 0
    rules = load_rules()
    # failed checks per zone-day, from the latest snapshot holding it
    failed_checks: dict[tuple[str, date], list[str]] = {}
    for dataset, (time_field, price_field, publishes) in PRICE_DATASETS.items():
        # snapshot names start with their ingestion timestamp: sorted = ingestion order
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
            df = pl.DataFrame(rows, schema=SCHEMA)
            requested = _requested_zone_days(snap["url"])
            failures = check_da_price(df, requested)
            held = {(z, delivery_day_of(t)) for z, t in df.select("zone", "event_time").iter_rows()}
            for zone_day in requested | held:
                failed_checks[zone_day] = []
            for f in failures:
                failed_checks[(f["zone"], f["delivery_day"])].append(f["check"])
            if len(df):
                n += store.append("da_price", df)  # bad data is reported, never dropped
            _write_quality_record(
                store.root / "quality" / "da_price", path, dataset, ingested_at, failures
            )
    return n, _summary(failed_checks)


SCHEMA = {
    "zone": pl.String,
    "event_time": pl.Datetime("us", "UTC"),
    "resolution": pl.String,
    "price_eur_mwh": pl.Float64,
    "knowledge_time": pl.Datetime("us", "UTC"),
    "knowledge_time_grade": pl.String,
    "source": pl.String,
    "ingested_at": pl.Datetime("us", "UTC"),
    "raw_ref": pl.String,
}


def _requested_zone_days(url: str) -> frozenset[tuple[str, date]]:
    """The zone-days a snapshot's request asked for (zones in its filter, delivery days its
    [start, end) span covers), so a zone or day the source left out still fails completeness.
    A URL without them (hand-made test snapshots) requests nothing."""
    q = parse_qs(urlsplit(url).query)
    if not {"start", "end", "filter"} <= q.keys():
        return frozenset()
    start, end = (datetime.fromisoformat(q[k][0]).replace(tzinfo=UTC) for k in ("start", "end"))
    first, last = delivery_day_of(start), delivery_day_of(end - timedelta(microseconds=1))
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    zones = json.loads(q["filter"][0])["PriceArea"]
    return frozenset((z, d) for z in zones for d in days)


def _write_quality_record(
    out_dir: Path, snapshot: Path, dataset: str, ingested_at: datetime, failures: list[dict]
) -> None:
    """One record per raw snapshot, written once (the snapshot never changes). It carries the
    snapshot's ingestion time: a filter built on it may only use records known at decision
    time (plan 03, L17)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "snapshot": snapshot.name,
        "dataset": dataset,
        "ingested_at": ingested_at.isoformat(),
        "checked_at": datetime.now(UTC).isoformat(),
        "failures": [f | {"delivery_day": f["delivery_day"].isoformat()} for f in failures],
    }
    text = json.dumps(record, indent=1)  # serialised first: one write, no half-written record
    try:
        with open(out_dir / snapshot.name, "x", encoding="utf-8") as f:  # "x": never rewritten
            f.write(text)
    except FileExistsError:
        pass


def _summary(failed_checks: dict[tuple[str, date], list[str]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for (zone, _), checks in sorted(failed_checks.items()):
        z = out.setdefault(zone, {"zone_days": 0, "failed": 0, "by_check": {}})
        z["zone_days"] += 1
        z["failed"] += bool(checks)
        for c in checks:
            z["by_check"][c] = z["by_check"].get(c, 0) + 1
    return out

"""Energi Data Service (Energinet) ingest. No API key. Writes raw snapshots only."""

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

BASE = "https://api.energidataservice.dk/dataset/"
SOURCE = "energidataservice"
MAX_RETRIES = 3


def http_get(url: str) -> dict:
    """GET JSON; waits out HTTP 429 using the wait the API reports."""
    for _ in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            m = re.search(r"(\d+) seconds", e.read().decode("utf-8", "replace"))
            time.sleep(int(m.group(1)) + 1 if m else 60)
    raise RuntimeError(f"still rate-limited after {MAX_RETRIES} attempts: {url}")


def fetch_elspotprices(raw_root: Path, start: datetime, end: datetime, zones: list[str]) -> Path:
    """Fetch hourly day-ahead prices for start <= HourUTC < end and store one raw snapshot."""
    fmt = "%Y-%m-%dT%H:%M"
    query = urlencode(
        {
            "start": start.astimezone(UTC).strftime(fmt),
            "end": end.astimezone(UTC).strftime(fmt),
            "timezone": "UTC",
            "filter": json.dumps({"PriceArea": zones}),
            "sort": "HourUTC asc",
            "limit": 0,
        }
    )
    url = f"{BASE}Elspotprices?{query}"
    # ponytail: one request per call; paging/resume for multi-year backfills is ticket #10
    return _write_snapshot(raw_root / SOURCE / "Elspotprices", url, http_get(url)["records"])


def _write_snapshot(d: Path, url: str, records: list[dict]) -> Path:
    """Append-only raw snapshot, named <timestamp>_<content hash>. A download identical to the
    latest snapshot of the same request writes nothing; any other content (including a revert
    to an older value) is a new snapshot."""
    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[:16]
    d.mkdir(parents=True, exist_ok=True)
    # ponytail: reads snapshots newest-first until the same URL; index by URL if this gets slow
    for p in sorted(d.glob("*.json"), reverse=True):
        if json.loads(p.read_text(encoding="utf-8"))["url"] == url:
            if p.stem.endswith(digest):
                return p
            break
    ingested_at = datetime.now(UTC)
    path = d / f"{ingested_at:%Y%m%dT%H%M%S%f}_{digest}.json"
    snapshot = {"ingested_at": ingested_at.isoformat(), "url": url, "records": records}
    with open(path, "x", encoding="utf-8") as f:  # "x": never overwrite a snapshot
        json.dump(snapshot, f)
    return path

"""Energi Data Service (Energinet) ingest. No API key. Writes raw snapshots only."""

import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

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
    payload = http_get(url)
    ingested_at = datetime.now(UTC)
    d = raw_root / SOURCE / "Elspotprices"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{ingested_at:%Y%m%dT%H%M%S}_{uuid4().hex[:8]}.json"
    snapshot = {"ingested_at": ingested_at.isoformat(), "url": url, "records": payload["records"]}
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    return path

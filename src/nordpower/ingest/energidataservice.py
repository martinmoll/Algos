"""Energi Data Service (Energinet) ingest. No API key. Writes raw snapshots only."""

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from nordpower.timeutil import DA_15MIN_FROM, delivery_span

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


# dataset -> (UTC time field, EUR price field, the one MTU it publishes) (✅ live API,
# 2026-11-18): Elspotprices ends with delivery day 2025-09-30, DayAheadPrices starts 2025-10-01.
PRICE_DATASETS = {
    "Elspotprices": ("HourUTC", "SpotPriceEUR", "PT60M"),
    "DayAheadPrices": ("TimeUTC", "DayAheadPriceEUR", "PT15M"),
}


def price_url(dataset: str, start: datetime, end: datetime, zones: list[str]) -> str:
    """The request for day-ahead prices with start <= time < end. Same arguments, same URL,
    so a backfill can tell which chunks it already holds."""
    time_field, _, _ = PRICE_DATASETS[dataset]
    fmt = "%Y-%m-%dT%H:%M"
    query = urlencode(
        {
            "start": start.astimezone(UTC).strftime(fmt),
            "end": end.astimezone(UTC).strftime(fmt),
            "timezone": "UTC",
            "filter": json.dumps({"PriceArea": zones}),
            "sort": f"{time_field} asc",
            "limit": 0,
        }
    )
    return f"{BASE}{dataset}?{query}"


def fetch_prices(
    dataset: str, raw_root: Path, start: datetime, end: datetime, zones: list[str]
) -> Path:
    """Fetch day-ahead prices for start <= time < end and store one raw snapshot."""
    url = price_url(dataset, start, end, zones)
    return _write_snapshot(raw_root / SOURCE / dataset, url, http_get(url)["records"])


# Minimum seconds between two requests to one dataset in a backfill. Elspotprices answers
# HTTP 429 after about one request per 5 minutes (D-026); DayAheadPrices is not limited that
# hard, but a backfill has no reason to hurry.
MIN_INTERVAL = {"Elspotprices": 300.0, "DayAheadPrices": 5.0}


def backfill_chunks(first: date, last: date) -> list[tuple[str, date, date]]:
    """(dataset, first day, last day) per calendar year and MTU era, for delivery days
    first..last. Chunk edges depend only on the calendar, so a resumed backfill asks for
    exactly the same chunks."""
    chunks = []
    for year in range(first.year, last.year + 1):
        lo, hi = max(first, date(year, 1, 1)), min(last, date(year, 12, 31))
        for dataset, era_lo, era_hi in (
            ("Elspotprices", date.min, DA_15MIN_FROM - timedelta(days=1)),
            ("DayAheadPrices", DA_15MIN_FROM, date.max),
        ):
            a, b = max(lo, era_lo), min(hi, era_hi)
            if a <= b:
                chunks.append((dataset, a, b))
    return chunks


def backfill_prices(
    raw_root: Path,
    first: date,
    last: date,
    zones: list[str],
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = print,
) -> list[Path]:
    """Download delivery days first..last chunk by chunk, skipping chunks a raw snapshot
    already holds, pausing between requests to one dataset. Interrupt it at any point and
    run it again: it carries on with the chunks it has not stored."""
    paths, last_request = [], {}
    for dataset, a, b in backfill_chunks(first, last):
        url = price_url(dataset, *delivery_span(a, b), zones)
        held = _latest_snapshot(raw_root / SOURCE / dataset, url)
        if held is not None:
            log(f"have {dataset} {a}..{b}: {held.name}")
            paths.append(held)
            continue
        if dataset in last_request:
            wait = MIN_INTERVAL[dataset] - (clock() - last_request[dataset])
            if wait > 0:
                log(f"waiting {wait:.0f} s before the next {dataset} request")
                sleep(wait)
        last_request[dataset] = clock()
        path = _write_snapshot(raw_root / SOURCE / dataset, url, http_get(url)["records"])
        log(f"got {dataset} {a}..{b}: {path.name}")
        paths.append(path)
    return paths


def _latest_snapshot(d: Path, url: str) -> Path | None:
    """The newest snapshot of exactly this request, if any."""
    for p in sorted(d.glob("*.json"), reverse=True):
        try:
            snap = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"raw snapshot {p} is truncated or corrupt: {e}") from e
        if snap["url"] == url:
            return p
    return None


def _write_snapshot(d: Path, url: str, records: list[dict]) -> Path:
    """Append-only raw snapshot, named <timestamp>_<content hash>. A download identical to the
    latest snapshot of the same request writes nothing; any other content (including a revert
    to an older value) is a new snapshot."""
    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[:16]
    d.mkdir(parents=True, exist_ok=True)
    # ponytail: reads snapshots newest-first until the same URL; index by URL if this gets slow
    held = _latest_snapshot(d, url)
    if held is not None and held.stem.endswith(digest):
        return held
    ingested_at = datetime.now(UTC)
    path = d / f"{ingested_at:%Y%m%dT%H%M%S%f}_{digest}.json"
    snapshot = {"ingested_at": ingested_at.isoformat(), "url": url, "records": records}
    text = json.dumps(snapshot)  # serialised first: one write, so a half snapshot is unlikely
    # ponytail: a kill inside that one write can still truncate the file; it then fails to
    # parse and the backfill stops naming it. Write-then-rename would need rename in writers.
    with open(path, "x", encoding="utf-8") as f:  # "x": never overwrite a snapshot
        f.write(text)
    return path

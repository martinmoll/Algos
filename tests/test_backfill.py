"""Backfill (#10): chunked by calendar year and MTU era, paced, resumable."""

import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

from nordpower.ingest import energidataservice as eds
from nordpower.ingest.energidataservice import backfill_chunks, backfill_prices


def test_chunks_follow_calendar_years_and_split_at_the_15_minute_switch():
    assert backfill_chunks(date(2023, 6, 1), date(2025, 11, 15)) == [
        ("Elspotprices", date(2023, 6, 1), date(2023, 12, 31)),
        ("Elspotprices", date(2024, 1, 1), date(2024, 12, 31)),
        ("Elspotprices", date(2025, 1, 1), date(2025, 9, 30)),
        ("DayAheadPrices", date(2025, 10, 1), date(2025, 11, 15)),
    ]


class FakeAPI:
    """Answers each request with one record per requested zone; can be told to fail."""

    def __init__(self, fail_on: int | None = None):
        self.urls: list[str] = []
        self.fail_on = fail_on

    def __call__(self, url: str) -> dict:
        self.urls.append(url)
        if len(self.urls) == self.fail_on:
            raise ConnectionError("network dropped")
        q = parse_qs(urlsplit(url).query)
        return {"records": [{"start": q["start"][0], "zones": q["filter"][0]}]}


@pytest.fixture
def quiet(monkeypatch):
    waits: list[float] = []
    now = [0.0]

    def sleep(s: float) -> None:
        waits.append(s)
        now[0] += s

    return {"sleep": sleep, "clock": lambda: now[0], "log": lambda m: None, "waits": waits}


def snapshots(raw):
    return sorted((raw / eds.SOURCE).rglob("*.json"))


def run(raw, quiet, first=date(2022, 1, 1), last=date(2025, 11, 15)):
    kw = {k: quiet[k] for k in ("sleep", "clock", "log")}
    return backfill_prices(raw, first, last, ["DK1", "DK2"], **kw)


def test_backfill_resumes_after_interruption_without_duplicating(tmp_path, monkeypatch, quiet):
    raw = tmp_path / "raw"
    first_try = FakeAPI(fail_on=3)
    monkeypatch.setattr(eds, "http_get", first_try)
    with pytest.raises(ConnectionError):
        run(raw, quiet)
    assert len(snapshots(raw)) == 2  # two chunks stored before the network dropped

    second_try = FakeAPI()
    monkeypatch.setattr(eds, "http_get", second_try)
    paths = run(raw, quiet)
    assert len(second_try.urls) == 3  # only the chunks it did not hold
    assert first_try.urls[2] == second_try.urls[0]  # starts again where it stopped
    assert len(paths) == len(snapshots(raw)) == 5

    third_try = FakeAPI()
    monkeypatch.setattr(eds, "http_get", third_try)
    assert run(raw, quiet) == paths and third_try.urls == []  # nothing left to do
    assert len(snapshots(raw)) == 5


def test_backfill_waits_between_requests_to_one_dataset(tmp_path, monkeypatch, quiet):
    monkeypatch.setattr(eds, "http_get", FakeAPI())
    run(tmp_path / "raw", quiet)
    # 4 Elspotprices chunks (2022-2025) -> 3 waits; the single DayAheadPrices chunk never waits
    assert quiet["waits"] == [eds.MIN_INTERVAL["Elspotprices"]] * 3


def test_a_truncated_snapshot_stops_the_backfill_by_name(tmp_path, monkeypatch, quiet):
    monkeypatch.setattr(eds, "http_get", FakeAPI())
    raw = tmp_path / "raw"
    (path,) = run(raw, quiet, date(2024, 1, 1), date(2024, 1, 31))
    assert json.loads(path.read_text(encoding="utf-8"))["records"]
    bad = path.with_name("29990101T000000000000_deadbeef.json")  # sorts newest
    bad.write_text(path.read_text(encoding="utf-8")[:40], encoding="utf-8")
    with pytest.raises(ValueError, match="truncated or corrupt"):
        run(raw, quiet, date(2024, 1, 1), date(2024, 1, 31))

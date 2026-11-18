"""Seam: data-quality checks on one snapshot's day-ahead prices (ticket #8, D-033).
Expected MTU counts are hand-written here, independent of the time module."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

from nordpower import cli
from nordpower.quality import check_da_price
from nordpower.store import Store

OSLO = ZoneInfo("Europe/Oslo")


def day_rows(zone: str, day: date, step_minutes: int, price: float = 50.0) -> list[dict]:
    """A complete delivery day: every MTU from local midnight to the next local midnight."""
    t = datetime(day.year, day.month, day.day, tzinfo=OSLO).astimezone(UTC)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=OSLO).astimezone(UTC)
    rows = []
    while t < end:
        rows.append(
            {
                "zone": zone,
                "event_time": t,
                "resolution": "PT15M" if step_minutes == 15 else "PT60M",
                "price_eur_mwh": price,
            }
        )
        t += timedelta(minutes=step_minutes)
    return rows


def failures_of(rows: list[dict]) -> list[tuple[str, str, date]]:
    return sorted(
        (f["check"], f["zone"], f["delivery_day"]) for f in check_da_price(pl.DataFrame(rows))
    )


def test_complete_days_pass_including_dst_days():
    days = [
        (date(2024, 3, 31), 60, 23),  # spring DST, hourly era
        (date(2024, 10, 27), 60, 25),  # autumn DST, hourly era
        (date(2025, 10, 1), 15, 96),
        (date(2025, 10, 26), 15, 100),  # autumn DST, 15-minute era
        (date(2026, 3, 29), 15, 92),  # spring DST, 15-minute era
    ]
    for day, step, n in days:
        rows = day_rows("DK1", day, step)
        assert len(rows) == n
        assert failures_of(rows) == [], day


def test_a_missing_mtu_fails_completeness_for_that_zone_and_day():
    rows = day_rows("DK1", date(2025, 10, 2), 15) + day_rows("DK2", date(2025, 10, 2), 15)
    del rows[37]
    assert failures_of(rows) == [("completeness", "DK1", date(2025, 10, 2))]


def test_a_row_off_the_mtu_grid_fails_completeness():
    """Hourly rows in the 15-minute era: 24 present, 72 missing."""
    assert failures_of(day_rows("DK1", date(2025, 10, 2), 60)) == [
        ("completeness", "DK1", date(2025, 10, 2))
    ]
    off_grid = day_rows("DK1", date(2025, 9, 2), 60)
    off_grid[5]["event_time"] += timedelta(minutes=15)
    found = check_da_price(pl.DataFrame(off_grid))
    assert [f["check"] for f in found] == ["completeness"]
    assert "missing 1" in found[0]["detail"] and "unexpected 1" in found[0]["detail"]


def test_a_duplicate_event_time_fails():
    rows = day_rows("DK1", date(2025, 9, 2), 60)
    rows.append(dict(rows[10], price_eur_mwh=60.0))
    assert failures_of(rows) == [("duplicate", "DK1", date(2025, 9, 2))]


def test_a_price_outside_the_harmonised_limits_fails():
    rows = day_rows("DK1", date(2025, 9, 2), 60)
    rows[3]["price_eur_mwh"] = 4000.01
    rows[4]["price_eur_mwh"] = -500.0  # on the limit: allowed
    more = day_rows("DK2", date(2025, 9, 2), 60)
    more[0]["price_eur_mwh"] = -500.5
    assert failures_of(rows + more) == [
        ("range", "DK1", date(2025, 9, 2)),
        ("range", "DK2", date(2025, 9, 2)),
    ]


def request_url(first: date, last: date, zones: list[str]) -> str:
    """The URL `nordpower ingest dayaheadprices` would request for these delivery days."""
    from urllib.parse import urlencode

    start = datetime(first.year, first.month, first.day, tzinfo=OSLO).astimezone(UTC)
    nxt = last + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=OSLO).astimezone(UTC)
    query = {
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "end": end.strftime("%Y-%m-%dT%H:%M"),
        "timezone": "UTC",
        "filter": json.dumps({"PriceArea": zones}),
    }
    return f"https://api.energidataservice.dk/dataset/DayAheadPrices?{urlencode(query)}"


def write_snapshot(raw: Path, name: str, rows: list[dict], url: str = "") -> None:
    d = raw / "energidataservice" / "DayAheadPrices"
    d.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "TimeUTC": r["event_time"].strftime("%Y-%m-%dT%H:%M:%S"),
            "PriceArea": r["zone"],
            "DayAheadPriceEUR": r["price_eur_mwh"],
        }
        for r in rows
    ]
    snap = {"ingested_at": "2025-11-01T00:00:00+00:00", "url": url or name, "records": records}
    (d / f"{name}.json").write_text(json.dumps(snap), encoding="utf-8")


def test_curate_reports_per_zone_and_stores_one_quality_record_per_snapshot(tmp_path, capsys):
    dk1 = day_rows("DK1", date(2025, 10, 2), 15) + day_rows("DK1", date(2025, 10, 3), 15)
    del dk1[37]  # 2 Oct incomplete
    dk2 = day_rows("DK2", date(2025, 10, 2), 15) + day_rows("DK2", date(2025, 10, 3), 15)
    dk2[100]["price_eur_mwh"] = 5000.0  # 3 Oct out of range
    write_snapshot(tmp_path / "raw", "20251101T000000000000_abc", dk1 + dk2)

    cli.main(["--data-dir", str(tmp_path), "curate"])
    out = capsys.readouterr().out
    assert "DK1: 2 zone-days checked, 1 failed (completeness 1)" in out
    assert "DK2: 2 zone-days checked, 1 failed (range 1)" in out

    [record_path] = (tmp_path / "quality" / "da_price").glob("*.json")
    assert record_path.name == "20251101T000000000000_abc.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["dataset"] == "DayAheadPrices"
    assert record["ingested_at"] == "2025-11-01T00:00:00+00:00"
    assert [(f["check"], f["zone"], f["delivery_day"]) for f in record["failures"]] == [
        ("completeness", "DK1", "2025-10-02"),
        ("range", "DK2", "2025-10-03"),
    ]
    # reported, not dropped: the out-of-range price is in the store
    view = Store(tmp_path).as_of(datetime(2025, 11, 1, tzinfo=UTC))
    window = {"event_start": dk2[100]["event_time"], "event_end": dk2[101]["event_time"]}
    assert view.read("da_price", zones=["DK2"], **window)["price_eur_mwh"].item() == 5000.0

    before = record_path.stat().st_mtime_ns
    cli.main(["--data-dir", str(tmp_path), "curate"])
    assert "DK1: 2 zone-days checked, 1 failed" in capsys.readouterr().out
    assert record_path.stat().st_mtime_ns == before  # written once, never rewritten


def test_an_extra_row_off_the_grid_fails_even_with_nothing_missing():
    rows = day_rows("DK1", date(2025, 9, 2), 60)
    rows.append(dict(rows[5], event_time=rows[5]["event_time"] + timedelta(minutes=15)))
    [found] = check_da_price(pl.DataFrame(rows))
    assert found["check"] == "completeness"
    assert "missing 0" in found["detail"] and "unexpected 1" in found["detail"]


def test_prices_exactly_on_the_limits_pass():
    rows = day_rows("DK1", date(2025, 9, 2), 60)
    rows[3]["price_eur_mwh"] = 4000.0
    rows[4]["price_eur_mwh"] = -500.0
    assert failures_of(rows) == []


def test_a_later_complete_snapshot_clears_the_gap_in_the_summary(tmp_path, capsys):
    gap = day_rows("DK1", date(2025, 10, 2), 15)
    del gap[10]
    write_snapshot(tmp_path / "raw", "20251101T000000000000_aaa", gap)
    write_snapshot(
        tmp_path / "raw", "20251102T000000000000_bbb", day_rows("DK1", date(2025, 10, 2), 15)
    )

    cli.main(["--data-dir", str(tmp_path), "curate"])
    assert "DK1: 1 zone-days checked, 0 failed" in capsys.readouterr().out
    first = tmp_path / "quality" / "da_price" / "20251101T000000000000_aaa.json"
    assert json.loads(first.read_text(encoding="utf-8"))["failures"]  # history is kept


def test_nan_prices_fail_range_and_details_do_not_carry_prices():
    rows = day_rows("DK1", date(2025, 9, 2), 60)
    rows[3]["price_eur_mwh"] = float("nan")
    rows[4]["price_eur_mwh"] = 4321.0
    [found] = check_da_price(pl.DataFrame(rows))
    assert found["check"] == "range" and "2 prices" in found["detail"]
    assert "4321" not in found["detail"]  # counts and times only: no price values


def record_of(tmp_path: Path, name: str) -> list[tuple[str, str, str]]:
    path = tmp_path / "quality" / "da_price" / f"{name}.json"
    failures = json.loads(path.read_text(encoding="utf-8"))["failures"]
    return [(f["check"], f["zone"], f["delivery_day"]) for f in failures]


def test_null_prices_and_missing_zones_fail_completeness(tmp_path):
    first, last = date(2025, 10, 2), date(2025, 10, 3)
    dk1 = day_rows("DK1", first, 15) + day_rows("DK1", last, 15)
    dk1[5]["price_eur_mwh"] = None  # published as null
    url = request_url(first, last, ["DK1", "DK2"])  # DK2 asked for, never delivered
    write_snapshot(tmp_path / "raw", "20251101T000000000000_ccc", dk1, url)
    cli.main(["--data-dir", str(tmp_path), "curate"])
    assert record_of(tmp_path, "20251101T000000000000_ccc") == [
        ("completeness", "DK1", "2025-10-02"),
        ("completeness", "DK2", "2025-10-02"),
        ("completeness", "DK2", "2025-10-03"),
    ]


def test_an_all_null_snapshot_still_gets_a_quality_record(tmp_path, capsys):
    rows = [dict(r, price_eur_mwh=None) for r in day_rows("DK1", date(2025, 10, 2), 15)]
    url = request_url(date(2025, 10, 2), date(2025, 10, 2), ["DK1"])
    write_snapshot(tmp_path / "raw", "20251101T000000000000_ddd", rows, url)
    cli.main(["--data-dir", str(tmp_path), "curate"])
    assert record_of(tmp_path, "20251101T000000000000_ddd") == [
        ("completeness", "DK1", "2025-10-02")
    ]
    assert "DK1: 1 zone-days checked, 1 failed (completeness 1)" in capsys.readouterr().out

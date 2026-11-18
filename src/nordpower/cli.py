"""`nordpower [--data-dir DIR] ingest|curate|backtest ...`"""

import argparse
import json
from datetime import date
from pathlib import Path

from nordpower.backtest import run_backtest
from nordpower.curate import curate_prices
from nordpower.ingest.energidataservice import PRICE_DATASETS, fetch_prices
from nordpower.models.naive import Naive
from nordpower.store import Store
from nordpower.timeutil import delivery_span
from nordpower.zones import load_zones


def _zones(s: str) -> list[str]:
    zones = s.split(",")
    unknown = set(zones) - load_zones().keys()
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown zones: {sorted(unknown)}")
    return zones


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="nordpower")
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    sub = p.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="download raw snapshots")
    ing.add_argument("dataset", choices=[d.lower() for d in PRICE_DATASETS])
    ing.add_argument("--start", type=date.fromisoformat, required=True, help="first delivery day")
    ing.add_argument("--end", type=date.fromisoformat, required=True, help="last delivery day")
    ing.add_argument("--zones", type=_zones, default=["DK1", "DK2"])

    sub.add_parser("curate", help="raw snapshots -> curated store")

    bt = sub.add_parser("backtest", help="walk-forward backtest")
    bt.add_argument("--model", choices=["naive"], default="naive")
    bt.add_argument("--start", type=date.fromisoformat, required=True, help="first delivery day")
    bt.add_argument("--end", type=date.fromisoformat, required=True, help="last delivery day")
    bt.add_argument("--zones", type=_zones, default=["DK1", "DK2"])

    a = p.parse_args(argv)
    raw = a.data_dir / "raw"
    store = Store(a.data_dir)

    if a.cmd == "ingest":
        dataset = next(d for d in PRICE_DATASETS if d.lower() == a.dataset)
        print(fetch_prices(dataset, raw, *delivery_span(a.start, a.end), a.zones))
    elif a.cmd == "curate":
        stored, quality = curate_prices(raw, store)
        print(f"curated {stored} da_price rows")
        for zone, result in quality.items():
            by_check = sorted(result["by_check"].items())
            checks = ", ".join(f"{check} {count}" for check, count in by_check)
            failed = f"{result['failed']} failed" + (f" ({checks})" if checks else "")
            print(f"{zone}: {result['zone_days']} zone-days checked, {failed}")
    elif a.cmd == "backtest":
        run_dir = run_backtest(store, Naive(a.zones), a.zones, a.start, a.end, a.data_dir / "runs")
        print(run_dir)
        print(json.dumps(json.loads((run_dir / "metrics.json").read_text()), indent=2))


if __name__ == "__main__":
    main()

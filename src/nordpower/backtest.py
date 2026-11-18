"""Walk-forward engine. Decide phase: models see only `store.as_of(cutoff)`.
Score phase: runs after every forecast is frozen; only this phase reads realised prices."""

import json
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import polars as pl

from nordpower.models.naive import Naive
from nordpower.store import KnowledgeView, Store, VaultSealed, VaultToken
from nordpower.timeutil import decision_cutoff, delivery_span, hours_of


class Model(Protocol):
    name: str
    rule: str

    def fit(self, view: KnowledgeView) -> None: ...
    def predict(self, view: KnowledgeView, delivery_day: date) -> pl.DataFrame: ...


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _decide(store: Store, model: Model, days: list[date], vault: VaultToken | None) -> pl.DataFrame:
    out = []
    for day in days:
        view = store.as_of(decision_cutoff(day), vault=vault)
        model.fit(view)
        forecast = model.predict(view, day)
        out.append(forecast.with_columns(delivery_day=pl.lit(day), decision_time=pl.lit(view.now)))
    return pl.concat(out)


def _score(
    store: Store,
    scored_at: datetime,
    forecasts: pl.DataFrame,
    bench: pl.DataFrame,
    zones: list[str],
    days: list[date],
    vault: VaultToken | None,
) -> dict:
    start, end = delivery_span(days[0], days[-1])
    actual = store.as_of(scored_at, vault=vault).read(
        "da_price", zones=zones, event_start=start, event_end=end
    )
    joined = (
        forecasts.join(
            bench.select("zone", "event_time", bench="forecast"), on=["zone", "event_time"]
        )
        .join(
            actual.select("zone", "event_time", actual="price_eur_mwh"), on=["zone", "event_time"]
        )
        .with_columns(
            err=pl.col("forecast") - pl.col("actual"), bench_err=pl.col("bench") - pl.col("actual")
        )
    )
    per_zone = joined.group_by("zone").agg(
        n=pl.len(),
        mae=pl.col("err").abs().mean(),
        rmse=(pl.col("err") ** 2).mean().sqrt(),
        bench_mae=pl.col("bench_err").abs().mean(),
    )
    expected = sum(len(hours_of(d)) for d in days)
    # ponytail: hours missing a forecast or an actual are only counted, not flagged; ticket #8
    return {
        r["zone"]: {
            "n": r["n"],
            "n_expected": expected,
            "mae": r["mae"],
            "rmse": r["rmse"],
            "rmae": r["mae"] / r["bench_mae"] if r["bench_mae"] else None,
        }
        for r in per_zone.sort("zone").iter_rows(named=True)
    }


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_backtest(
    store: Store,
    model: Model,
    zones: list[str],
    first: date,
    last: date,
    runs_root: Path,
    *,
    vault_purpose: str | None = None,
) -> Path:
    """Walk forward over delivery days first..last; write an immutable run record.

    Without `vault_purpose`, delivery days inside the vault are refused and actuals are
    scored as known just before the vault boundary. With it, the run opens the vault itself:
    one logged opening per run, never shared between runs (D-031)."""
    started_at = datetime.now(UTC)
    if vault_purpose is None and delivery_span(last, last)[1] > store.vault_start:
        raise VaultSealed(
            f"delivery day {last} is inside the vault (sealed from "
            f"{store.vault_start.isoformat()}); a vault run needs vault_purpose citing D-nnn"
        )
    vault = store.open_vault(vault_purpose) if vault_purpose else None
    scored_at = started_at if vault else min(started_at, store.vault_start - timedelta.resolution)
    days = _days(first, last)
    forecasts = _decide(store, model, days, vault)
    bench = _decide(store, Naive(zones), days, vault)  # always recomputed, never reused
    metrics = _score(store, scored_at, forecasts, bench, zones, days, vault)

    run_id = f"{started_at:%Y%m%dT%H%M%S}-{model.name}-{uuid4().hex[:6]}"
    d = runs_root / run_id
    d.mkdir(parents=True)
    config = {
        "run_id": run_id,
        "model": model.name,
        "model_rule": model.rule,
        "zones": zones,
        "first_delivery_day": first.isoformat(),
        "last_delivery_day": last.isoformat(),
        "decision_cutoff": "11:30 Europe/Oslo on D-1",
        "benchmark": "naive",
        "scored_as_of": scored_at.isoformat(),
        "vault_opening": vault.record() if vault else None,
        "git_sha": _git_sha(),
    }
    (d / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    forecasts.write_parquet(d / "forecasts.parquet")
    (d / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return d

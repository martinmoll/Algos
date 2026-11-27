"""Walk-forward engine. Decide phase: models see only `store.as_of(cutoff)`.
Score phase: runs after every forecast is frozen; only this phase reads realised prices."""

import copy
import itertools
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import polars as pl

from nordpower import runs
from nordpower.models.naive import Naive
from nordpower.quality import check_da_price
from nordpower.store import KEY, META, KnowledgeView, Store, VaultSealed, VaultToken
from nordpower.timeutil import (
    da_gate_closure,
    da_mtus,
    da_resolution,
    decision_cutoff,
    delivery_span,
)


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
    # Era = the delivery day's MTU: the hourly and 15-minute eras are scored apart (D-032).
    # Every zone and every era in the run is reported, with n = 0 when nothing was scored.
    era_of = {d: da_resolution(d) for d in days}
    joined = joined.with_columns(era=pl.col("delivery_day").replace_strict(era_of))
    expected = {
        e: sum(len(da_mtus(d)) for d in days if era_of[d] == e) for e in set(era_of.values())
    }

    def summary(scored: pl.DataFrame, n_expected: int) -> dict:
        mae, bench_mae = scored["err"].abs().mean(), scored["bench_err"].abs().mean()
        return {
            "n": len(scored),
            "n_expected": n_expected,
            "mae": mae,
            "rmse": (scored["err"] ** 2).mean() ** 0.5 if len(scored) else None,  # type: ignore[operator]
            "rmae": mae / bench_mae if mae is not None and bench_mae else None,  # type: ignore[operator]
        }

    # ponytail: MTUs missing a forecast or an actual are only counted here; quality records
    # (D-033) say which zone-days are bad, and blocking on them comes with the first consumer
    out = {}
    for zone in zones:
        z = joined.filter(pl.col("zone") == zone)
        out[zone] = summary(z, sum(expected.values())) | {
            "eras": {
                e: summary(z.filter(pl.col("era") == e), expected[e]) for e in sorted(expected)
            }
        }
    return out


class _PoisonedStore(Store):
    """The same store, but every vintage not yet knowable at `t` holds garbage. A model that
    reads only through `as_of(t)` cannot tell the difference (plan 03 §5.2)."""

    def __init__(self, base: Store, t: datetime):
        self.root, self.vault_start, self._issued = base.root, base.vault_start, base._issued
        self._base, self._t = base, t

    def _parts(self, dataset: str) -> pl.LazyFrame | None:
        stored = self._base._parts(dataset)
        if stored is None:
            return None
        schema = stored.collect_schema()
        future = pl.col("knowledge_time") > self._t

        def garbage(dtype: pl.DataType) -> pl.Expr:
            if dtype.is_float():
                return pl.lit(1e9, dtype=dtype)
            if dtype.is_numeric():
                return pl.lit(999, dtype=dtype)
            if dtype == pl.String:
                return pl.lit("POISONED")
            return pl.lit(None, dtype=dtype)

        return stored.with_columns(
            pl.when(future).then(garbage(schema[c])).otherwise(pl.col(c)).alias(c)
            for c in schema
            if c not in KEY and c not in META
        )


def _check_decision_times(forecasts: pl.DataFrame) -> dict:
    """Every forecast was made at its day's cutoff, before gate closure, for that day only."""
    bad = []
    for day, t, first, last in (
        forecasts.group_by("delivery_day", "decision_time")
        .agg(first=pl.col("event_time").min(), last=pl.col("event_time").max())
        .sort("delivery_day")
        .iter_rows()
    ):
        start, end = delivery_span(day, day)
        if t != decision_cutoff(day) or t >= da_gate_closure(day):
            bad.append(f"{day}: decided at {t.isoformat()}")
        if first < start or last >= end:
            bad.append(f"{day}: forecasts outside the delivery day")
    return {"name": "decision_times", "passed": not bad, "detail": bad}


def _sample(days: list[date], n: int) -> list[date]:
    """n days spread over the run, always including the last (the longest replay)."""
    if len(days) <= n:
        return days
    if n <= 1:
        return days[-1:]
    return sorted({days[round(i * (len(days) - 1) / (n - 1))] for i in range(n)})


def _check_future_poison(
    store: Store,
    pristine: Model,
    days: list[date],
    forecasts: pl.DataFrame,
    vault: VaultToken | None,
    n_days: int,
) -> dict:
    """Re-run the walk-forward up to each sampled day on a store whose not-yet-knowable
    vintages are garbage; that day's forecasts must be bit-identical. Catches a model or an
    engine that reads around the knowledge view."""
    bad, checked = [], []
    for day in _sample(days, n_days):
        poisoned = _PoisonedStore(store, decision_cutoff(day))
        replay = _decide(poisoned, copy.deepcopy(pristine), days[: days.index(day) + 1], vault)
        on_day = pl.col("delivery_day") == day
        expected = forecasts.filter(on_day).sort("zone", "event_time")
        if not expected.equals(replay.filter(on_day).sort("zone", "event_time")):
            bad.append(f"{day}: forecasts changed when unknowable data was poisoned")
        checked.append(day.isoformat())
    return {"name": "future_poison", "passed": not bad, "days": checked, "detail": bad}


def _data_snapshot_id(store: Store) -> str | None:
    """Latest `ingested_at` across every curated dataset: names the data the run started on."""
    curated = store.root / "curated"
    latest = [
        lf.select(pl.col("ingested_at").max()).collect().item()
        for d in (sorted(curated.iterdir()) if curated.exists() else [])
        if (lf := store._parts(d.name)) is not None
    ]
    return max(latest).isoformat() if latest else None


LOOKBACK = timedelta(days=7)  # the naive model's longest reference (D-7)


def _quality_summary(
    store: Store, scored_at: datetime, zones: list[str], days: list[date], vault: VaultToken | None
) -> dict:
    """Data quality over every delivery day the run read (its days plus the naive lookback).

    `view`: the checks (D-033) re-run on the latest vintages as of the scoring instant, i.e.
    on exactly the data the run used. `snapshots`: failures recorded at curation, from quality
    records ingested by then (L17), which also shows problems later downloads fixed."""
    first, last = days[0] - LOOKBACK, days[-1]
    span = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    start, end = delivery_span(first, last)
    rows = store.as_of(scored_at, vault=vault).read(
        "da_price", zones=zones, event_start=start, event_end=end
    )
    failures = check_da_price(rows, frozenset((z, d) for z in zones for d in span))

    def counts(fs: list[dict]) -> dict:
        out = {z: {"zone_days": len(span), "failed": 0, "by_check": {}} for z in zones}
        for zone, group in itertools.groupby(
            sorted(fs, key=lambda f: f["zone"]), lambda f: f["zone"]
        ):
            group = list(group)
            out[zone]["failed"] = len({f["delivery_day"] for f in group})
            for f in group:
                by = out[zone]["by_check"]
                by[f["check"]] = by.get(f["check"], 0) + 1
        return out

    recorded = []
    for p in sorted((store.root / "quality" / "da_price").glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        if datetime.fromisoformat(rec["ingested_at"]) > scored_at:
            continue
        recorded += [
            f
            for f in rec["failures"]
            if f["zone"] in zones and first.isoformat() <= f["delivery_day"] <= last.isoformat()
        ]
    return {
        "first_delivery_day": first.isoformat(),
        "last_delivery_day": last.isoformat(),
        "view": counts(failures)
        | {"failures": [f | {"delivery_day": f["delivery_day"].isoformat()} for f in failures]},
        "snapshots": counts(recorded),
    }


def _write_json(path: Path, obj: dict | list) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def run_backtest(
    store: Store,
    model: Model,
    zones: list[str],
    first: date,
    last: date,
    runs_root: Path,
    *,
    vault_purpose: str | None = None,
    family: str = "S1",
) -> Path:
    """Walk forward over delivery days first..last; write a sealed run record (D-037).

    Without `vault_purpose`, delivery days inside the vault are refused and actuals are
    scored as known just before the vault boundary. With it, the run opens the vault itself:
    one logged opening per run, never shared between runs (D-031).

    Every run that gets past the vault check is a trial: it is registered before any work,
    and its outcome (status, or the error) is registered after. The model must be
    deep-copyable: the future-poison check replays it from its state before the run."""
    started_at = datetime.now(UTC)
    if vault_purpose is None and delivery_span(last, last)[1] > store.vault_start:
        raise VaultSealed(
            f"delivery day {last} is inside the vault (sealed from "
            f"{store.vault_start.isoformat()}); a vault run needs vault_purpose citing D-nnn"
        )
    run_id = f"{started_at:%Y%m%dT%H%M%S}-{model.name}-{uuid4().hex[:6]}"
    runs.register(
        runs_root,
        {
            "event": "started",
            "run_id": run_id,
            "at": started_at.isoformat(),
            "family": family,
            "model": model.name,
            "zones": zones,
            "first_delivery_day": first.isoformat(),
            "last_delivery_day": last.isoformat(),
        },
    )
    try:
        d, status = _run(
            store, model, zones, first, last, runs_root, run_id, started_at, vault_purpose, family
        )
    except BaseException as e:
        runs.register(
            runs_root,
            {
                "event": "failed",
                "run_id": run_id,
                "at": datetime.now(UTC).isoformat(),
                "error": f"{type(e).__name__}: {e}",
            },
        )
        raise
    runs.register(
        runs_root,
        {"event": "finished", "run_id": run_id, "at": datetime.now(UTC).isoformat(), **status},
    )
    return d


def _run(
    store: Store,
    model: Model,
    zones: list[str],
    first: date,
    last: date,
    runs_root: Path,
    run_id: str,
    started_at: datetime,
    vault_purpose: str | None,
    family: str,
) -> tuple[Path, dict]:
    rules = runs.load_status_rules()
    git = runs.git_state()
    snapshot = _data_snapshot_id(store)
    vault = store.open_vault(vault_purpose) if vault_purpose else None
    scored_at = started_at if vault else min(started_at, store.vault_start - timedelta.resolution)
    days = _days(first, last)
    pristine = copy.deepcopy(model)
    forecasts = _decide(store, model, days, vault)
    bench = _decide(store, Naive(zones), days, vault)  # always recomputed, never reused
    metrics = _score(store, scored_at, forecasts, bench, zones, days, vault)
    quality = _quality_summary(store, scored_at, zones, days, vault)
    checks = [
        _check_decision_times(forecasts),
        _check_future_poison(
            store, pristine, days, forecasts, vault, rules["future_poison"]["sample_days"]
        ),
    ]
    status = runs.run_status(metrics, checks, git["dirty"], rules)

    config = {
        "run_id": run_id,
        "family": family,
        "model": model.name,
        "model_rule": model.rule,
        "zones": zones,
        "first_delivery_day": first.isoformat(),
        "last_delivery_day": last.isoformat(),
        "decision_cutoff": "11:30 Europe/Oslo on D-1",
        "benchmark": "naive",
        "scored_as_of": scored_at.isoformat(),
        "vault_opening": vault.record() if vault else None,
    }
    provenance = {
        "git_sha": git["sha"],
        "git_dirty": git["dirty"],
        "packages": runs.package_versions(),
        "data_snapshot_id": snapshot,
        "vault_opening": vault.record() if vault else None,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
    }
    tmp = runs_root / f".incomplete-{run_id}"
    tmp.mkdir(parents=True)
    _write_json(tmp / "config.json", config)
    _write_json(tmp / "provenance.json", provenance)
    forecasts.write_parquet(tmp / "forecasts.parquet")
    _write_json(tmp / "metrics.json", metrics)
    _write_json(tmp / "leakage_checks.json", checks)
    _write_json(tmp / "quality.json", quality)
    _write_json(tmp / "status.json", status | {"rules": rules})
    return runs.seal(tmp, runs_root / run_id), status

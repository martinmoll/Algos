# 06 — Architecture and repository layout

One Python package, one storage directory, one CLI. Boring on purpose: the sophistication budget goes into data integrity and evaluation, not infrastructure.

## 1. Stack

| Concern | Choice | Why / when to revisit |
|---|---|---|
| Language | Python 3.12 (pinned via `uv`; the machine has 3.14 but ML wheels lag new releases) | — |
| Env / packaging | `uv`, `pyproject.toml`, `src/` layout | — |
| DataFrames | Polars | Fast, strict dtypes, lazy; pandas only at library boundaries (`entsoe-py`) |
| Storage | Parquet files (append-only, partitioned by dataset / knowledge month) queried with DuckDB | No server to run. Revisit (Postgres/Timescale, Delta/Iceberg) only if concurrent writers or > ~100 GB |
| Models | scikit-learn (LASSO), LightGBM, PyTorch (DNN/distributional), `chronos-forecasting`; Optuna for nested tuning | — |
| Stats | `scipy`, `arch` (bootstrap, DM helpers) | — |
| Scheduling | OS scheduler (Task Scheduler / cron / systemd timers) calling the CLI | Revisit (Dagster/Prefect) when collectors exceed ~20 jobs or need backfill orchestration |
| Experiment tracking | File-based run registry (`data/runs/`), indexed by DuckDB | Revisit MLflow if model artefact management becomes painful |
| Dashboard | Streamlit + Plotly reading the run registry and store | See [07](07-dashboard.md) |
| Quality | `pytest` (+ `hypothesis` for time/DST properties), `ruff`, `import-linter`, `pyright` | CI via GitHub Actions once a remote exists |
| Config | Typed config objects (pydantic) loaded from YAML in `configs/` | — |
| Secrets | `.env` (git-ignored), read via environment variables | — |

## 2. Layout

```
EnergyTrading/
├── CLAUDE.md                  # agent rules (no-look-ahead invariants first)
├── GLOSSARY.md                # domain language
├── README.md
├── pyproject.toml
├── configs/
│   ├── zones.yaml             # zones, EIC codes, country, tz, neighbours
│   ├── publication_rules.yaml # assumed knowledge-time rule per dataset (reviewed!)
│   ├── regimes.yaml           # regime calendar with announcement dates
│   ├── costs/                 # fee + slippage profiles (base, stress)
│   └── experiments/           # one YAML per pre-registered experiment
├── src/nordpower/
│   ├── timeutil.py            # MTU, delivery day, gate closures, DST — the only place time math lives
│   ├── zones.py
│   ├── store/                 # bitemporal store: append(), as_of(t) -> KnowledgeView, vault guard
│   ├── ingest/                # one module per source; writes raw snapshots only
│   │   ├── energidataservice.py  entsoe.py  esett.py  nve.py
│   │   ├── openmeteo.py  jao.py  fingrid.py  umm.py
│   ├── curate.py / quality.py  # raw → typed curated tables; quality checks per snapshot (D-033)
│   ├── features/              # declarative feature specs; computed only from a KnowledgeView
│   ├── models/                # naive.py lear.py gbm.py dnn.py prob/ tsfm.py ensemble.py
│   ├── strategies/            # decide(view, t) -> forecasts + orders
│   ├── execution/             # market simulators + cost models (da_auction, ida, continuous, imbalance, futures, battery)
│   ├── backtest/              # walk-forward engine, splitters (purge/embargo), run registry, trial counting
│   ├── evaluation/            # metrics, DM/GW, CRPS, coverage tests, DSR, PBO, attribution
│   ├── live/                  # paper-trading loop, hash-chained commitment log, settlement job
│   ├── dashboard/             # Streamlit app
│   └── cli.py                 # `nordpower ingest|curate|backtest|live|dash ...`
├── tests/
│   ├── leakage/               # time-travel, future-poison, shuffled-target, canary (CI-blocking)
│   ├── unit/  integration/
├── data/                      # git-ignored
│   ├── raw/<source>/<dataset>/…parquet      # append-only snapshots
│   ├── curated/<dataset>/…parquet           # bitemporal tables
│   ├── quality/<dataset>/<snapshot>.json    # one quality record per raw snapshot (D-033)
│   ├── runs/<run_id>/                       # immutable run records
│   └── live/commitments.jsonl               # hash chain
└── docs/
    ├── DECISIONS.md           # decision log (append-only)
    ├── OPEN-QUESTIONS.md      # things only the user can decide
    ├── plan/                  # these documents
    └── research/              # references, per-topic research notes
```

## 3. Dependency rule (enforced by import-linter)

```
ingest ─▶ store ◀─ curate   (curate also reads ingest's source definitions, never the reverse)
              ▲
              │ KnowledgeView only
features ─▶ models ─▶ strategies ─▶ backtest/live engine ─▶ execution, evaluation
```

- `features`, `models`, `strategies` may import `store` **only** for the `KnowledgeView` type. They may not import `ingest`, `curate`, `execution`, `evaluation`, nor open files under `data/`.
- `execution` and `evaluation` read settlement data through the engine, after decisions are frozen.
- `timeutil` and `zones` are leaf modules importable by all.

## 4. The core interface

```python
view = store.as_of(t)                  # raises inside the vault without a token
df = view.read("da_price", zones=[...], event_start=..., event_end=...)
#   → latest version per (key, event_time) with knowledge_time <= t
view.now                               # == t; features use it for lags
```

Design intent: a deep module. Small interface, all the bitemporal complexity (version resolution, assumed-vintage rules, vault, DST) hidden behind it. Everything downstream is ordinary dataframe code that *cannot* leak because it never holds data from after `t`.

## 5. Store schema (curated tables)

Common columns: `zone` (or other key), `event_time` (UTC), `resolution` (`PT15M|PT60M|P1D|P1W`), `value` columns, `knowledge_time` (UTC), `knowledge_time_grade`, `source`, `ingested_at`, `raw_ref` (pointer to the raw snapshot row for audit).

Native resolution is stored as published; resampling (e.g. 15-min → hourly mean) happens in features with explicit rules, never in storage.

## 6. Testing strategy (test seams)

| Seam | Test |
|---|---|
| `timeutil` | Property tests: DST days, round-trips, gate-closure conversion across years |
| `store.as_of` | Version resolution, vault refusal, time-travel equivalence on synthetic data |
| Each ingest module | Recorded-response fixtures → raw snapshot; schema + idempotency |
| Curate | Quality gates on crafted bad data; cross-source reconciliation |
| Features | Future-poison per feature spec (auto-generated from the declarative specs) |
| Engine | Golden mini-backtest on synthetic prices with a known answer; settle phase isolation |
| Evaluation | Metrics against hand-computed and `epftoolbox` reference values |
| End-to-end | Shuffled-target null; naive model reproduces known rMAE = 1.0 |

## 7. Operations

- **Collectors host**: always-on machine runs `nordpower ingest --schedule`; research happens anywhere on a synced copy of `data/` (rsync/object storage). Until the host exists, collectors run on this PC when it is on, and gaps are recorded honestly.
- **Backups**: raw snapshots are irreplaceable (vintages!). Nightly copy to a second location from day one.
- **Reproducibility**: a run is reproducible from (git SHA, config, data snapshot id). Data snapshot id = max `ingested_at` at run start; the store can replay as of any snapshot id.

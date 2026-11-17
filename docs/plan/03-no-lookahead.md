# 03 — The no-look-ahead contract

This is the constitution of the project. Every other document defers to it. If a shortcut conflicts with this file, the shortcut loses.

**Principle:** a backtested decision at time *t* may depend only on information that was *actually knowable* at *t*, and its outcome is computed by code the strategy cannot reach.

Look-ahead is prevented **by construction** (the architecture makes leaking hard), **by test** (automated checks that fail the build when it happens anyway), and **by protocol** (rules for the humans and agents running experiments).

## 1. Three clocks on every value

| Field | Meaning |
|---|---|
| `event_time` | Start of the period the value describes (the delivery MTU, the forecast valid time). UTC. |
| `knowledge_time` | Earliest instant the value was knowable to a market participant. UTC. |
| `ingested_at` | When *we* stored it. UTC. Never used for modelling; used for audit. |

Plus `knowledge_time_source ∈ {observed, published, assumed}`:

- **observed** — we snapshotted it live; `knowledge_time = ingested_at` (conservative: we cannot have known it earlier than we saw it).
- **published** — the source supplies a trustworthy publication timestamp (UMM messages, Energinet `Forecasts_Hour.TimestampUTC`, NVE publication dates, weather model run time + documented dissemination delay).
- **assumed** — backfilled; `knowledge_time` = documented publication schedule **plus a safety lag**, defined per dataset in one reviewed table (`publication_rules`). Rules err late, never early.

## 2. Storage rules

1. **Raw is append-only.** A re-download that differs is a *new version* with a later `knowledge_time`; nothing is updated or deleted.
2. The only read path for features, models and strategies is an **as-of view**: `view = store.as_of(t)` returns, per `(dataset, key, event_time)`, the latest version with `knowledge_time <= t`. There is no API that returns "the data" without a `t`.
3. Raw files are not importable from modelling code. An import-linter rule forbids `features/`, `models/`, `strategies/` from importing `ingest/` or touching `data/raw` paths. Only `store` reads storage.
4. Settlement data used to score a decision is read by the **backtest engine**, in a separate step, after the strategy has returned its orders.

## 3. Decision times

Each strategy declares a **decision clock**: the instants at which it may act, and a cutoff margin.

| Market | Gate closure | Default decision cutoff |
|---|---|---|
| Day-ahead | 12:00 CET D-1 | **11:30 CET D-1** (30 min for compute + submission) |
| IDA1 / IDA2 / IDA3 | 15:00 D-1 / 22:00 D-1 / 10:00 D ✅ | 20 min before |
| Intraday continuous | 60 min before delivery ⚠️ (per zone rules) | Per-order timestamps; latency model |
| Futures | Exchange hours | Daily at a fixed time using data up to then; fills at *next* available price, never the price that triggered the signal |

All gate times are defined in **Europe/Oslo local time** and converted with the tz database — never as fixed UTC offsets. DST days have 23/25 hours (92/100 quarter-hours) and get dedicated tests.

## 4. Known leak catalogue (each has a guard)

| # | Leak | Guard |
|---|---|---|
| L1 | Using revised/final data that differed at decision time (load, generation, imbalance, forecasts) | As-of view; assumed-vintage flag; revision-size monitoring |
| L2 | **Realised weather** for the delivery period as a feature (ERA5 "forecast") | Weather observations are a distinct dataset whose knowledge time is after the event; the as-of view simply cannot return them for future periods. No "perfect foresight" switch exists in production code |
| L3 | Weekly reservoir/hydro data joined on the week it describes rather than its Wednesday publication | `published` knowledge time from NVE; test with a known week |
| L4 | D-1 features that include hours after the cutoff (e.g. "yesterday's prices" is fine; "today's actual load for hours 12–24" is not, at 11:30) | As-of view; feature specs declare lags relative to decision time, not delivery time |
| L5 | Day-ahead results for D used when forecasting D (results appear ≈12:45, after the cutoff) | Publication rule: `da_price` knowledge time = 12:45 CET D-1 + lag |
| L6 | Full-sample preprocessing: scalers, PCA, feature selection, imputation, outlier clipping fit on train+test | All transforms are part of the model object and are fit inside `fit(view)`; engine never passes future rows |
| L7 | Hyperparameter tuning / early stopping / model selection on the test period | Nested walk-forward: tuning uses only data before the evaluation block ([05](05-backtesting.md)) |
| L8 | Researcher overfitting: iterating on the same backtest until it looks good | Trial registry, deflated Sharpe, PBO, sealed vault period ([05](05-backtesting.md)) |
| L9 | Target leakage through overlapping labels (multi-day horizons, rolling targets) | Purge + embargo between train and test |
| L10 | Regime knowledge: using a rule/feature designed after seeing the outcome (e.g. a flow-based feature "before" it existed, a 2022 crisis dummy) | Regime calendar entries have their own knowledge time (announcement date); hindsight features must be logged as such in the decision log |
| L11 | Survivorship/selection in zones or periods ("drop the weird months") | Exclusions must be declared in config before the run and appear in the run record |
| L12 | Execution fantasy: filling at the price you forecast against; ignoring your own price impact, fees, imbalance cost | Execution simulators with costs; pessimistic fill rules ([05](05-backtesting.md) §5) |
| L13 | Time-zone / DST / "hour 24" off-by-one shifting data one period into the future | One `time` module; property tests; cross-source reconciliation |
| L14 | Forward-fill across the knowledge boundary, or interpolation using later points | Imputation is causal only (last-known as of *t*); linted |
| L15 | Pretrained models (time-series foundation models, LLMs) whose training data includes the test period | Record each pretrained model's training cutoff; evaluate only on data after it, or label the result "contaminated benchmark" |
| L16 | Currency/price data restated (FX fixing, price corrections after auction re-runs) | Versioned like everything else |
| L17 | Leak via the data-quality filter (dropping days because the *outcome* was extreme) | Filters may only use information known at decision time |

## 5. Automated tests (CI-blocking)

1. **Time-travel equivalence.** For sampled decision times *t*: features computed from the full store via `as_of(t)` must be identical to features computed from a store physically truncated to rows with `knowledge_time <= t`.
2. **Future poison.** Replace every value with `knowledge_time > t` by garbage (NaN / ±1e9 / shuffled). Features, predictions and orders at *t* must be bit-identical.
3. **Shuffled-target null.** A pipeline trained on a time-permuted target must show no skill (rMAE ≈ 1 vs naive, Sharpe ≈ 0). Skill on noise means a leak.
4. **Synthetic leak canary.** A planted feature equal to the target must be *impossible* to request with a legal knowledge time; the test asserts the store refuses.
5. **Too-good alarm.** Any run with DA rMAE below a floor (e.g. < 0.5 vs naive) or annualised Sharpe above a ceiling (e.g. > 4) is auto-flagged `suspect` and cannot be promoted without a written review.
6. **Import boundaries** (L-rules 2.3) and **causal-imputation lint**.
7. **DST and boundary property tests** on the time module.

## 6. Protocol (for humans and agents)

- No result is quoted anywhere (docs, dashboard, chat) without its run id.
- Every backtest run is recorded automatically — including failed and abandoned ones. Deleting run records is forbidden.
- The **vault** (most recent 12 months at project start, then rolling by rule) is not readable by research code. Opening it is a logged, counted event requiring a decision-log entry stating the single pre-registered configuration being evaluated.
- An idea's hypothesis, features and success metric are written down **before** its first backtest (pre-registration, a short entry in the run config).
- Agents may not weaken a leakage test to make a build pass. A failing leakage test is treated as a bug in the pipeline until proven otherwise, and the diagnosis is logged.

## 7. The gold standard: tamper-evident paper trading

Backtests can only ever approximate. The definitive evidence is forward performance:

- Before each gate closure, the live loop writes forecasts and intended orders to an **append-only, hash-chained log** (each record includes the SHA-256 of the previous record), and publishes the chain head to an external timestamp (e.g. a commit pushed to a remote, or an OpenTimestamps proof).
- After results are published, a separate settlement job scores them.
- The dashboard shows backtest vs forward performance side by side. A persistent gap is the most honest leak detector there is.

This also means: the sooner the live loop starts — even with a naive model — the sooner real, unimpeachable history accumulates.

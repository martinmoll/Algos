# 05 — Backtesting and evaluation protocol

How we measure, so that a number on the dashboard means something. Builds on [03-no-lookahead](03-no-lookahead.md).

## 1. Data partitions

```
|<----------- research period ----------->|<-- vault -->|<-- forward (live paper) ...
 history start                      T_vault = project start − 12 months      now →
```

- **Research period**: everything before `T_vault`. All development, tuning and model selection happen here, by walk-forward only.
- **Vault**: the 12 months before project start (2025-11-16 → 2026-11-16). Conveniently it is almost exactly the 15-minute day-ahead era so far. Unreadable by research code (the store refuses `as_of` times inside it unless a vault token is supplied). Each opening is logged and counted; the expectation is single digits per year.
- **Forward**: everything after go-live of the paper-trading loop; hash-chained. Grows forever and gradually becomes the main evidence.

Because the vault covers nearly all 15-minute DA data, intra-hour shape models are developed on the short pre-vault slice (2025-10-01 → 2025-11-15) plus *forward* data, and are labelled low-confidence until a year of forward data exists. This trade-off is recorded in the decision log (D-014). Until a forward read path exists, forward data is sealed along with the vault (D-031).

## 2. Walk-forward engine

Event-driven over decision times; one loop for backtest and live.

```
for t in decision_clock:
    view   = store.as_of(t)                 # only knowable data
    if retrain_due(t): model.fit(view)      # transforms fit inside
    orders = strategy.decide(view, t)       # forecasts + orders, recorded
engine.settle(orders)                       # separate phase, strategy code cannot reach it
```

- **Rolling-origin, expanding or sliding window**; no random K-fold, ever, for anything time-indexed.
- **Hyperparameter tuning is nested**: at each (re)tuning date, candidate configs are scored by walk-forward on the trailing validation block that ends before the next evaluation block. Tuning cadence ≥ quarterly.
- **Purge and embargo** whenever labels overlap or features are long rolling aggregates: drop training samples whose label window intersects the test block, plus an embargo equal to the longest feature lookback that could straddle.
- The same `strategy.decide` runs live. No separate "research implementation".

## 3. Forecast evaluation

| Aspect | Metric |
|---|---|
| Point accuracy | MAE, RMSE, **rMAE** vs naive (primary), sMAPE only for reference (unstable near zero/negative prices) |
| Significance | Diebold–Mariano (multivariate, daily loss-vector version) and Giacomini–White conditional predictive ability; reported as a model × model matrix |
| Probabilistic | Pinball loss per quantile, **CRPS**, energy score for joint (multi-zone/multi-hour) forecasts |
| Calibration | PIT histogram, empirical coverage of 50/80/90/98% intervals, Kupiec (unconditional) and Christoffersen (conditional) coverage tests |
| Tails | Separate scores for price deciles 1 and 10, negative-price hours, spike hours |
| Stability | Scores by zone, hour, month, weekday/holiday, and regime-calendar segment; rolling 90-day rMAE |
| Minimum test length | ≥ 1 year (ideally 2+) of out-of-sample decisions before any claim |

## 4. Strategy evaluation

- P&L in EUR per MWh traded and per day; equity curve; **max drawdown**, time under water.
- Annualised Sharpe and Sortino **on daily P&L** (not per-MTU — intraday P&L is autocorrelated), with Newey–West / block-bootstrap confidence intervals.
- Hit rate, profit factor, average win/loss, tail loss (CVaR 95/99).
- Turnover, cost share of gross P&L, capacity estimate (P&L vs assumed volume).
- **Attribution**: by zone, hour block, month, regime, long/short, and by forecast-error bucket.
- **Benchmarks**: zero-position, always-long/always-short the spread, naive-forecast-driven version of the same strategy, random-entry with matched turnover (permutation distribution).

### Multiple-testing discipline

- **Trial registry**: every run (config hash, git SHA, data snapshot, metrics) is recorded automatically; the count of trials per strategy family is an input to the statistics, not an afterthought.
- **Deflated Sharpe Ratio** (Bailey & López de Prado): reported next to every Sharpe, using the number and variance of trials in the family.
- **Probability of Backtest Overfitting** via combinatorially symmetric cross-validation when selecting among many configurations.
- **Reality check / SPA** (White; Hansen) for "best of N strategies vs benchmark".
- Promotion rule (research → vault test → paper → live): DSR > 0.95 on research walk-forward, PBO < 0.2, all leakage tests green, stable across ≥ 3 of 4 yearly sub-periods, survives 2× cost stress. Then **one** vault evaluation with the frozen config.

## 5. Execution simulation (pessimism by default)

| Market | Fill model | Costs |
|---|---|---|
| Day-ahead auction | Price-taker for small volume: price-independent or limit order fills at the published clearing price if the limit is satisfied. Sensitivity: price impact curve (assumed EUR/MWh per MW until bid-curve data exists) | Nord Pool variable fee, clearing fee, fixed fees amortised ⚠️ (take from the current fee schedule) |
| Intraday auction | As DA | Fees |
| Intraday continuous | Only against recorded trades/quotes; cross the spread; fill ≤ a fraction of traded volume in the window; latency ≥ 1–5 s; no fills at prices that never traded | Fees + half-spread + slippage assumption |
| Imbalance | Single imbalance price from eSett (final version, for settlement only) + imbalance fees ⚠️ | BRP fees, volume fees |
| Futures | Next-day settlement or next available quote ± half-spread; margin and financing | Exchange + clearing fees |
| Battery (S6) | Physical constraints: power, energy, efficiency, cycle cost | Degradation EUR/MWh throughput |

Rules: orders are timestamped; a fill can never use a price with knowledge time ≤ the order's decision time as its own trigger; partial fills and rejected orders are modelled; every assumption is a config value shown on the run page; every strategy is re-run under a **stress profile** (2× costs, 2× slippage, 15 min extra latency).

## 6. Run record (what a run writes)

Immutable directory `data/runs/<run_id>/`, sealed as one step (D-037): written under `.incomplete-<run_id>`, hashed into `manifest.json`, made read-only, then renamed into place. `runs.verify(dir)` reports any changed, missing or extra file.

Built (Phase 0, #9):

- `config.json` (model, rule, zones, delivery days, family, cutoff, scoring instant, vault opening)
- `provenance.json` (git SHA + dirty flag, package versions, data snapshot id = latest `ingested_at` in the store at start, vault token use, start and finish times)
- `forecasts.parquet`, `metrics.json`
- `leakage_checks.json`: `decision_times` (every forecast made at its day's cutoff, before gate closure, for that day only) and `future_poison` (the walk-forward replayed up to sampled days on a store whose not-yet-knowable vintages are garbage; forecasts must be bit-identical)
- `status.json`: `invalid | suspect | exploratory | ok` with reasons and the rules applied (`configs/run_status.toml`). Most severe wins: invalid = a look-ahead check failed; suspect = rMAE vs naive below 0.5 in any zone or era; exploratory = dirty or unknown git tree. Only `ok` runs can be promoted; every run counts as a trial.
- `manifest.json`

Later: full resolved config incl. feature list, cadence, cost profile, exclusions and pre-registered hypothesis; share of features with `assumed` knowledge time; `orders.parquet`, `fills.parquet`, `pnl.parquet`; Sharpe ceiling in the too-good alarm.

**Registry.** `data/runs/registry.jsonl` is append-only: a `started` line before any work, then `finished` (with status) or `failed` (with the error). A run with no second line is `abandoned`. `nordpower runs` lists every run and the trial count per strategy family.

## 7. Reporting honesty rules

- Always show gross and net, and the trial count.
- Always show assumed-vintage vs observed-vintage performance separately once both exist.
- Never report a backtest Sharpe without its deflated counterpart and its confidence interval.
- Negative and null results are recorded in the decision log with the same care as positive ones.

# 07 — Dashboard

A local Streamlit app (`nordpower dash`) over the store and run registry. Purpose: make it *easy to see when something is wrong* and *hard to fool yourself*. Every chart that shows performance also shows its run id, trial count and integrity status.

## Pages

### 1. Integrity (home page)

The first thing you see, because it qualifies everything else.

- Leakage test suite status (last run, pass/fail per test).
- Runs by status: `ok / suspect / invalid / exploratory`.
- Trial counter per strategy family; vault openings (count, dates, linked decision-log entries).
- Share of feature values with `observed / published / assumed` knowledge time, per dataset and over time.
- Backtest-vs-forward gap for each live strategy (the ultimate leak detector).

### 2. Data health

- Freshness per dataset/zone (last event time, last ingest), with expected schedule.
- Completeness heatmap (zone × day), DST days highlighted.
- Revision monitor: how much did values change between first-seen and latest version (distribution per dataset) — quantifies the risk in assumed-vintage backfill.
- Cross-source reconciliation diffs.
- Collector gaps (when the host was down).

### 3. Market explorer

- Zone prices, spreads, system price; 15-min and hourly; map of zones coloured by price.
- Drivers overlay: residual load, wind, temperature, reservoir vs median, nuclear availability, flow-based max net positions.
- **As-of slider**: view any chart "as known at time *t*" — a direct, visual demonstration of the bitemporal store, and a debugging tool.
- Regime calendar markers on every time axis.

### 4. Forecast evaluation

- Leaderboard: model × zone, rMAE / MAE / CRPS, with DM/GW significance matrix.
- Error by hour, weekday, month, regime; rolling 90-day rMAE.
- Calibration: PIT histogram, coverage vs nominal, pinball by quantile.
- Tail panels: spikes, negative prices, deciles 1 and 10.
- Forecast vs actual day viewer with prediction intervals (pick any delivery day).
- Feature importance / SHAP for GBM; LASSO coefficient paths for LEAR.

### 5. Backtest

- Equity curve gross/net, drawdown, daily P&L distribution.
- Headline: Sharpe with CI, **deflated Sharpe**, PBO, hit rate, profit factor, CVaR, turnover, cost share.
- Attribution: zone, hour block, month, regime, long/short.
- Cost and stress sensitivity (base vs stress profile; P&L vs assumed volume).
- Trade inspector: for any decision time, the exact inputs the strategy saw (rendered from `as_of(t)`), its forecast distribution, orders, fills, outcome.
- Config and provenance panel (git SHA, data snapshot, exclusions, pre-registered hypothesis).

### 6. Run comparison

- Pick N runs → metric table diff, config diff, equity overlay, paired DM test.

### 7. Live / paper trading

- Today's committed forecasts and orders (with commitment hash and time-before-gate), then realised prices and P&L as they arrive.
- Forward track record since go-live; chain verification status.

## Design notes

- Read-only: the dashboard never triggers training or writes runs.
- All queries go through DuckDB views over Parquet; pages load a single run or a small aggregate, never raw history.
- Colour and layout follow one consistent palette; zone colours are fixed everywhere. Use the `dataviz` skill when building charts.
- `suspect` and `invalid` runs are visually marked wherever they appear and excluded from leaderboards by default.

## Later

- Static HTML export of a run report (for sharing a track record).
- Alerting (collector down, data gap before gate closure, calibration drift) via email/push.

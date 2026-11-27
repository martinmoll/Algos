# 08 — Roadmap

Phases are ordered so that (a) irreplaceable live vintages start accumulating as early as possible, and (b) every later phase stands on tested no-look-ahead machinery. Each phase is a candidate spec → tickets (`/to-spec`, `/to-tickets`).

## Phase 0 — Foundations (the skeleton that cannot leak)

- Repo scaffold (`uv`, package, CI config, lint, import boundaries).
- `timeutil` (MTU, delivery day, gate closures, DST) with property tests.
- `zones` config.
- Bitemporal `store`: `append`, `as_of → KnowledgeView`, vault guard, publication rules.
- Leakage test harness on synthetic data (time-travel, future-poison, canary).
- First ingest: **Energi Data Service** (no key): `Elspotprices`, `DayAheadPrices`, `Forecasts_Hour`.
- Naive model + minimal walk-forward engine + run record.

**Exit:** a naive DK1/DK2 day-ahead backtest runs end-to-end with rMAE = 1.00 by construction and all leakage tests green.

## Phase 1 — Data platform + live collection

- Ingest: ENTSO-E (prices all zones, load, RES forecasts, generation, flows, capacities, outages, reservoir, imbalance), eSett, NVE, Open-Meteo (previous runs backfill + live), JAO, Fingrid, UMM.
- Curate + quality gates + reconciliation.
- **Scheduled live collectors** + backup. *Start the moment the store exists — do not wait for the rest of the phase.*
- Dashboard v0: Data health + Integrity pages.
- Quality checks for every new dataset at ingest time (completeness, duplicates, ranges, plausibility), plus cross-source reconciliation and revision counting once a second source exists (D-034).
- TSO method documents logged with versions and effective dates in the regime calendar ([09](09-tso-methods.md)).
- Live NWP snapshots at park and population points (deterministic + ensemble), and dated installed-capacity lists ([10](10-weather-and-satellite.md)).

**Exit:** all Tier-1 datasets backfilled (assumed vintage) and collecting live (observed vintage) for 12 zones; health page green for 2 consecutive weeks.

**Blocked on user:** ENTSO-E token, Fingrid key, UMM registration (Q3); collectors host (Q6).

## Phase 2 — Day-ahead forecasting benchmark

- Feature library v1 (declarative specs). Built and ablated on LEAR first (D-034): price lags → calendar → residual-load deltas → TSO forecast errors/revisions → hydro → cross-zone.
- Own wind/solar/load models from NWP (power curves, clear-sky index), entered as deltas vs TSO forecasts; CAMS irradiance as labels ([10](10-weather-and-satellite.md)).
- M0 naive, M1 LEAR, M2 LightGBM, M3 DNN for 12 zones + system price, hourly.
- Evaluation module (rMAE, DM, GW) validated against `epftoolbox` on its public Nord Pool dataset — proves our harness reproduces published numbers.
- Dashboard: Market explorer, Forecast evaluation, Run comparison.

**Exit:** LEAR and LightGBM beat naive significantly (DM) on ≥ 2 years of walk-forward for most zones; results reproducible from run records.

## Phase 3 — Probabilistic forecasts, ensembles, 15-minute

- Quantile models, QRA, distributional DNN, conformal calibration; CRPS/coverage evaluation.
- Ensemble/stacking; Chronos-2 member.
- Multi-zone joint model with flow-based features.
- Intra-hour shape model.

**Exit:** calibrated intervals (coverage tests pass) and an ensemble that significantly beats its best member.

## Phase 4 — Forward test (optional; can start with Phase 2 models)

The only evidence a backtest cannot fake. It is not a step toward live trading: the project never uses real money (D-041).

- `live/` loop: forecast before 11:30 CET, hash-chained commitment, external timestamp, settlement job.
- Dashboard: Forward-test page; backtest-vs-forward gap.

**Exit:** 30 consecutive days of committed forecasts with verified chain.

## Phase 5 — Strategy research

- Execution simulators + cost profiles.
- S6 battery benchmark (forecast value in EUR).
- S2 DA↔imbalance research, starting from an imbalance-price replica per country ([09](09-tso-methods.md) §2.1).
- Satellite nowcasting for S2/S3/S6; snow products for S4 ([10](10-weather-and-satellite.md) §4).
- S3 DA↔intraday (if data: Q4). S4 futures/EPAD (if data: Q4).
- Trial registry statistics: DSR, PBO, SPA. Dashboard: Backtest page.

**Exit:** for each family, a written verdict (edge / no edge after costs) with deflated statistics; at most one vault opening per promoted configuration.

## No Phase 6

There is no path to real money (D-041). The project ends at research verdicts: for each strategy family, edge or no edge after costs, with deflated statistics and at most one vault evaluation per promoted configuration.

## Suggested order of the first tickets

1. Scaffold + `timeutil` + tests.
2. `store` + leakage harness on synthetic data.
3. Energi Data Service ingest + curate `da_price`.
4. Naive model + engine + run record (walking skeleton complete).
5. Scheduled collector for Energi Data Service + Open-Meteo live (vintages start accumulating).
6. ENTSO-E ingest (once the token arrives).

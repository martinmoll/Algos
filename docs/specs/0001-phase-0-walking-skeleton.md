---
title: Phase 0 — walking skeleton that cannot look ahead
labels: [ready-for-agent]
status: open
created: 2026-11-17
plan: docs/plan/08-roadmap.md#phase-0
---

## Problem Statement

I want to trade Nordic power algorithmically, but I don't trust any backtest I can't prove is free of look-ahead. Power data is revised after the fact, published on irregular schedules and full of DST traps, and the usual research workflow (download a CSV, shift some columns, cross-validate) leaks the future silently. Before building any serious model I need a foundation where look-ahead is impossible by construction and detected by automated tests, and I want to see it work end to end on real Nordic data.

## Solution

A minimal but complete pipeline. It downloads real day-ahead prices for DK1 and DK2 (and the system price) from Energi Data Service, a source that needs no key. It stores every value with the time it became knowable, and runs a walk-forward backtest of the naive forecast. The model can read data only as it was knowable at each decision cutoff. Every run writes an immutable, reproducible run record. A suite of look-ahead tests blocks the build if any part of the pipeline can see the future. When this works, the naive model's rMAE is exactly 1.00 against itself, all look-ahead tests are green, and every later phase reuses the same pieces.

## User Stories

1. As the researcher, I want one command that installs the project environment, so that I (and agents) can start from a clean machine.
2. As the researcher, I want the project pinned to Python 3.12, so that ML libraries install reliably even though 3.14 is on the machine.
3. As the researcher, I want lint, type-check and tests to run with one command, so that quality checks are habitual.
4. As the researcher, I want import boundaries enforced automatically, so that model or strategy code physically cannot read raw data files.
5. As the researcher, I want a canonical list of bidding zones with their EIC codes, country and time zone, so that every module uses the same identifiers.
6. As the researcher, I want the system price treated as a pseudo-zone, so that it flows through the same storage and models as real zones.
7. As the researcher, I want every timestamp stored in UTC, so that there is one unambiguous time axis.
8. As the researcher, I want a delivery day defined in Nordic local time, so that 23- and 25-hour days are handled correctly.
9. As the researcher, I want to list the MTUs of a delivery day at a given resolution, so that completeness checks know how many values to expect (92/96/100 quarter-hours, 23/24/25 hours).
10. As the researcher, I want gate closure and decision cutoff instants computed from local market time, so that DST never shifts a cutoff by an hour.
11. As the researcher, I want the day-ahead decision cutoff to default to 11:30 local on D-1 and to be configurable, so that backtests aren't flattered by unrealistically late information.
12. As the researcher, I want each stored value to carry event time, knowledge time, knowledge-time grade and ingestion time, so that I can always ask what was knowable when.
13. As the researcher, I want raw downloads stored append-only, so that no re-download can overwrite history.
14. As the researcher, I want a re-download whose values differ to become a new vintage, so that revisions are preserved and measurable.
15. As the researcher, I want an identical re-download to be a no-op, so that scheduled collection doesn't bloat storage.
16. As the researcher, I want backfilled values to get an assumed knowledge time from a reviewed publication rule, so that history I didn't watch live is still dated conservatively.
17. As the researcher, I want publication rules kept in one reviewed configuration, so that the assumptions are visible and auditable in one place.
18. As the researcher, I want publication rules to err late, so that uncertainty never turns into look-ahead.
19. As the researcher, I want to obtain data only through a knowledge view at an instant, so that there is no API that returns "the data" without a time.
20. As the researcher, I want the knowledge view to return, for each key and event time, the latest vintage known at that instant, so that revised values appear only after they were published.
21. As the researcher, I want the knowledge view to refuse any instant inside the vault unless given a vault token, so that the final test period stays untouched.
22. As the researcher, I want every vault opening logged, so that the number of looks is countable.
23. As the researcher, I want Energi Data Service hourly prices (to 2025-09-30, including the system price) ingested, so that I have a long history.
24. As the researcher, I want Energi Data Service 15-minute day-ahead prices (from 2025-10-01) ingested, so that the current market design is covered.
25. As the researcher, I want ingestion to page through the API politely and resume after interruption, so that a full backfill finishes reliably.
26. As the researcher, I want each raw snapshot to keep the source's original fields, so that I can audit curation later.
27. As the researcher, I want a curated day-ahead price table at native resolution, so that models never depend on source-specific field names.
28. As the researcher, I want data-quality checks on the curated table (completeness per zone-day, price range, duplicates), so that bad data is visible before it reaches a model.
29. As the researcher, I want a naive forecast model (same MTU from D-7 for Monday, Saturday and Sunday; D-1 otherwise), so that I have the reference every later model must beat.
30. As the researcher, I want the naive model to forecast hourly means and be told explicitly how to aggregate 15-minute prices, so that resampling is a declared modelling choice and not hidden in storage.
31. As the researcher, I want a model interface with fit on a knowledge view and predict for a delivery day, so that every future model plugs into the same engine.
32. As the researcher, I want a walk-forward engine that steps through decision cutoffs, builds the knowledge view, and asks the model for forecasts, so that backtest and later live use share one loop.
33. As the researcher, I want scoring done in a separate phase after all forecasts are frozen, so that model code can never reach realised outcomes.
34. As the researcher, I want each backtest to write an immutable run record (resolved config, git SHA and dirty flag, package versions, data snapshot id, forecasts, metrics, look-ahead check results, status), so that every number is reproducible and attributable.
35. As the researcher, I want runs from a dirty working tree marked exploratory, so that they count as trials but can't be promoted.
36. As the researcher, I want MAE, RMSE and rMAE versus naive computed per zone, so that Phase 0 proves the evaluation path.
37. As the researcher, I want the naive backtest to report rMAE of exactly 1.00, so that the harness is proven consistent by construction.
38. As the researcher, I want a time-travel equivalence test (knowledge view at t equals a store physically truncated at t), so that version resolution is proven correct.
39. As the researcher, I want a future-poison test (corrupting everything known after t leaves forecasts at t bit-identical), so that any leak in features or models fails the build.
40. As the researcher, I want a canary test asserting that a value can't be read before its knowledge time, so that the store's core guarantee is pinned.
41. As the researcher, I want a shuffled-target test showing no skill on time-permuted prices, so that hidden leaks producing fake skill are caught.
42. As the researcher, I want DST and gate-closure property tests, so that the classic one-hour shift can't creep in.
43. As the researcher, I want a too-good alarm that marks runs with implausible skill as suspect, so that an implausible result triggers review, not celebration.
44. As the researcher, I want a single CLI with subcommands for ingest, curate and backtest, so that runs are scriptable and schedulable.
45. As an agent, I want the leakage tests to be CI-blocking and documented as untouchable, so that I never "fix" a build by weakening them.
46. As the researcher, I want new decisions made during implementation appended to the decision log, so that the reasoning survives.

## Implementation Decisions

- **Modules** (deep, small interfaces):
  - *Time*: owns all time arithmetic: delivery day ↔ UTC interval, MTUs of a day at a resolution, gate closure and decision cutoff instants. Market time zone Europe/Oslo (CET/CEST, identical for all Nordic zones). Only stdlib `zoneinfo`.
  - *Zones*: loads the zone configuration (id, EIC code, country, time zone, is_pseudo for SYS). Phase 0 populates all 12 Nordic zones plus SYS; only DK1, DK2 and SYS get data.
  - *Store*: `append(dataset, rows)`; `as_of(t, vault_token=None) → KnowledgeView`; `KnowledgeView.read(dataset, keys, event_start, event_end)`; `KnowledgeView.now`. Hides version resolution, publication rules, vault guard and the file layout. Implemented as Parquet files queried with DuckDB.
  - *Ingest (Energi Data Service)*: fetches `Elspotprices` (hourly, `HourUTC`, `PriceArea`, `SpotPriceEUR`) and `DayAheadPrices` (15-minute, `TimeUTC`, `PriceArea`, `DayAheadPriceEUR`), pages with offset/limit, writes raw snapshots only.
  - *Curate*: raw → curated `da_price` (columns below), applies publication rules, runs quality checks, appends to the store.
  - *Models*: `Model` protocol with `fit(view)` and `predict(view, delivery_day) → forecasts`; one implementation, naive.
  - *Backtest*: walk-forward engine over a decision clock; separate settle/score phase; run registry writer; trial counting (every run recorded).
  - *Evaluation*: MAE, RMSE, rMAE.
  - *CLI*: `ingest`, `curate`, `backtest` subcommands.
- **Curated row schema (`da_price`)**: zone, event_time (UTC, start of MTU), resolution (`PT60M | PT15M`), price_eur_mwh, knowledge_time (UTC), knowledge_time_grade (`observed | published | assumed`), source, ingested_at, raw_ref.
- **Vintage rule**: a row is a new vintage iff its value differs from the latest stored vintage for the same (dataset, key, event_time). Identical re-ingests write nothing.
- **Publication rule for `da_price` backfill**: assumed knowledge time = 13:00 Europe/Oslo on D-1 for delivery day D (results publish ≈12:45; 15-minute safety lag). Rules live in one config file, reviewed in PRs.
- **Vault**: event or decision instants ≥ 2025-11-16 00:00 Europe/Oslo are refused without a token (D-014). Vault openings append to a log.
- **Decision clock (day-ahead)**: 11:30 Europe/Oslo on D-1 for each delivery day D (D-008), from config.
- **Naive model**: forecasts the hourly mean for each hour of D. For Mon/Sat/Sun it uses the same hour of D-7, otherwise D-1. Where the source is 15-minute, it uses the arithmetic mean of the four quarter-hours. On DST days it maps hours by local clock hour; a missing source hour (spring-forward) is filled from the previous local hour, and the extra autumn hour is averaged. This rule is written into the run config.
- **Scoring target**: realised hourly-mean day-ahead price, read by the engine's settle phase, not by the model.
- **Run record**: an immutable directory per run id with config, provenance, forecasts, metrics, leakage_checks, status (`ok | suspect | invalid | exploratory`).
- **Too-good alarm thresholds**: rMAE < 0.5 versus naive marks a run suspect (configurable).
- **Stack**: Python 3.12 via uv, Polars, DuckDB, httpx, pydantic for config, pytest + hypothesis, ruff, pyright, import-linter (D-010, D-011).
- **Import contract**: features/models/strategies may import the store only for the KnowledgeView type; they may not import ingest or curate.
- **Backtest period for the exit criterion**: from the first delivery day where DK1/DK2 data plus a 7-day lookback exist (≈ 2015) through 2025-11-15. Results are split into hourly-era and 15-minute-era segments.

## Testing Decisions

- Good tests exercise external behaviour through public interfaces: the CLI/engine, the KnowledgeView, the time module. They must survive internal refactoring. No mocks of our own modules. HTTP is replaced by recorded real responses from Energi Data Service.
- **Seam 1 — backtest run (primary):** end-to-end on recorded responses: ingest → curate → backtest naive → run record exists, rMAE = 1.00, status ok. Also covers idempotent re-ingest and revision creating a new vintage.
- **Seam 2 — knowledge view:** time-travel equivalence, future poison, read-before-knowledge-time canary, vault refusal, latest-vintage resolution. These live in a dedicated leakage test package marked CI-blocking. Future poison and shuffled-target run through the engine so they cover the model too.
- **Seam 3 — time module:** hypothesis property tests over years 2000–2040: MTU counts per day, UTC round-trips, cutoff always 30 min before gate closure in local time, DST days in both directions.
- Quality checks are tested with crafted bad curated data (missing MTUs, duplicates, out-of-range prices).
- Prior art: none in the repo yet; these tests become the pattern for later phases.

## Out of Scope

- ENTSO-E, eSett, NVE, Open-Meteo, JAO, Fingrid, UMM ingestion (Phase 1).
- Scheduled live collection and the always-on host (Phase 1; Q6).
- Any model beyond naive; features library; probabilistic metrics; DM/GW tests (Phase 2+).
- Execution simulation, strategies, P&L, deflated Sharpe (Phase 5).
- Dashboard (Phase 1 v0 onwards).
- Paper-trading loop and hash chain (Phase 4).
- GitHub remote and CI service (Q10); Phase 0 provides the local check command that CI will call.

## Further Notes

- Facts this spec relies on, verified 2026-11-16: Energi Data Service needs no key; `Elspotprices` runs 1999-07-01 → 2025-09-30, hourly, includes SYS; `DayAheadPrices` is 15-minute from 2025-10-01 for DK1, DK2, DE, NO2, SE3, SE4.
- Unverified: Energinet's dataset changes around the DataHub upgrade (from 17 Sep 2026). Check `Elspotprices` and `DayAheadPrices` status at implementation time.
- Vault start 2025-11-16 is provisional (Q7); the boundary must be a single config value.
- Rules and rationale: docs/plan/03-no-lookahead.md, docs/plan/06-architecture.md, docs/DECISIONS.md (D-004 – D-016).

# Decision log

Append-only. Newest at the bottom. Never edit a past entry's substance — add a new entry that supersedes it and set the old one's status.

**Format:** `D-NNN — title` · date · status (`accepted | provisional | superseded by D-NNN | rejected`) · who decided.
`provisional` = made by the agent without the user in the loop; stands until the user confirms or overrides (see [OPEN-QUESTIONS](OPEN-QUESTIONS.md)).
Record: context, decision, why, alternatives rejected, and what would make us revisit. Null/negative research results belong here too.

---

## D-001 — Scope: 12 Nordic bidding zones + system price; neighbours as features

2026-11-16 · provisional · agent

**Context.** User asked for Norway, Sweden, Denmark and "who else".
**Decision.** Targets: NO1–NO5, SE1–SE4, DK1, DK2, FI, plus the Nordic system price. Baltics (EE, LV, LT) and DE-LU, NL, PL, GB are inputs only. Iceland excluded (isolated grid).
**Why.** Finland is part of the Nordic synchronous area and price formation; leaving it out breaks the physics. Neighbours set the marginal price in southern zones.
**Revisit if** the user wants Baltic zones tradable (cheap to add: same sources).

## D-002 — Day-ahead forecasting first; strategies are spreads, built on top

2026-11-16 · provisional · agent

**Context.** "Trade the Nordic power markets" does not name a market. A day-ahead position cannot be held alone.
**Decision.** Order of work: S1 day-ahead forecasting (foundation) → S6 simulated battery and S2 day-ahead↔imbalance (free data) → S3 intraday and S4 futures/EPAD when data access is settled. Details: [01](plan/01-markets-and-strategies.md).
**Why.** S1 has free data, a deep literature with reproducible benchmarks, and feeds every other strategy; it lets us prove the no-look-ahead machinery against published numbers before betting on it.
**Rejected.** Starting with intraday (no free historical data); starting with RL-based trading (easiest place to hide overfitting).

## D-003 — Paper trading is a first-class, tamper-evident mode

2026-11-16 · provisional · agent

**Context.** Physical Nordic markets need exchange membership plus balance responsibility; futures need a clearing relationship. No retail route was found.
**Decision.** Build a live paper loop that commits forecasts/orders to a hash-chained append-only log with an external timestamp before each gate closure, then settles against published prices.
**Why.** It is the only evidence that cannot contain look-ahead, and it produces a track record usable to justify (or not) the cost of real market access.
**Revisit if** the user already has market access (Q1).

## D-004 — Bitemporal append-only store; `as_of(t)` is the only read path

2026-11-16 · accepted (core invariant; user's explicit requirement) · agent

**Context.** "No look-ahead bias on any of it… no cheating."
**Decision.** Every value carries `event_time`, `knowledge_time`, `ingested_at`. Raw data is never updated. Features/models/strategies can obtain data only through `store.as_of(t)`, which returns the latest version known at `t`. Import boundaries enforce it. Details: [03](plan/03-no-lookahead.md).
**Why.** Prevention by construction beats review. Discipline-based approaches ("remember to lag this column") fail silently.
**Rejected.** Plain tables with a convention of shifting features (unenforceable); a commercial point-in-time database (cost, lock-in, unnecessary at this scale).
**Consequence.** More storage and a slightly awkward API everywhere — accepted permanently.

## D-005 — Three grades of knowledge time; backfill is "assumed" and reported separately

2026-11-16 · provisional · agent

**Context.** Public APIs return the latest revision only; true publication times of historical values are mostly unknowable.
**Decision.** `knowledge_time_source ∈ {observed, published, assumed}`. Assumed times come from one reviewed table of publication rules with a safety lag, erring late. Results are reported split by grade once both exist.
**Why.** Honest about what we cannot know; makes the residual risk measurable (via the revision monitor) instead of invisible.
**Revisit if** a source of true historical vintages is bought.

## D-006 — Start live snapshot collection before anything else is finished

2026-11-16 · provisional · agent

**Decision.** As soon as the store exists, schedule collectors for every free source, even with no model to consume them.
**Why.** Vintages are the one asset that cannot be recreated later; everything else can be rebuilt.
**Needs.** An always-on host (Q6) and API keys (Q3).

## D-007 — Realised weather is never an input for the delivery period

2026-11-16 · accepted (follows from the user's requirement) · agent

**Context.** The commonest cheat in energy ML is using reanalysis/observed weather (ERA5) as if it were the forecast.
**Decision.** Weather features come only from forecast vintages (Open-Meteo Previous Runs from 2024; MEPS archive if needed earlier) or from TSO forecasts that embed weather and were published before gate closure. Observations are used only lagged, or as targets for learning forecast error. No "perfect foresight" mode exists in production code.
**Consequence.** Weather-driven models have effectively < 3 years of honest history today; before 2024 we rely on TSO load/wind forecasts. Accepted.

## D-008 — Day-ahead decision cutoff 11:30 CET D-1

2026-11-16 · provisional · agent

**Decision.** Strategies acting in the day-ahead auction may use data with `knowledge_time ≤ 11:30` Europe/Oslo on D-1 (gate closure 12:00). Config value, recorded per run.
**Why.** 30 minutes covers computation, submission and operational slack. Tighter cutoffs flatter the backtest.
**Revisit** after live pre-gate snapshots show what is reliably available by when.

## D-009 — UTC everywhere; market times defined in Europe/Oslo via tz database

2026-11-16 · accepted · agent

**Decision.** All stored timestamps are UTC. Delivery days, gate closures and holidays are defined in local market time and converted with `zoneinfo`. One module owns all time arithmetic.
**Why.** DST and "hour 24" off-by-ones are a classic source of one-period look-ahead.

## D-010 — Stack: Python 3.12, uv, Polars, DuckDB over Parquet

2026-11-16 · provisional · agent

**Why.** Single-user research system; files + embedded engine are enough and keep operations at zero. Python 3.12 rather than the installed 3.14 for ML wheel availability.
**Rejected.** Postgres/TimescaleDB (a server to run, no benefit yet); pandas as primary (slower, looser types); Spark/Delta (scale we do not have).
**Revisit if** data exceeds ~100 GB or concurrent writers appear.

## D-011 — No orchestrator, no MLflow: CLI + OS scheduler + file-based run registry

2026-11-16 · provisional · agent

**Why.** Fewer moving parts. A run is an immutable directory; DuckDB indexes them.
**Revisit if** > ~20 scheduled jobs, complex backfills, or model-artefact management pain.

## D-012 — Dashboard: local Streamlit app, read-only

2026-11-16 · provisional · agent

**Why.** Fastest path from Parquet to interactive pages in Python; the user is the only viewer.
**Rejected.** Custom React front-end (weeks of work for no analytical gain); Grafana (weak for run comparison and statistics); notebooks (not reproducible, encourage ad-hoc peeking).
**Revisit if** multi-user access or public sharing is needed.

## D-013 — Evaluation: walk-forward only, nested tuning, every run is a counted trial

2026-11-16 · accepted (follows from the user's requirement) · agent

**Decision.** No random cross-validation. Tuning inside the walk-forward. Automatic trial registry; Deflated Sharpe, PBO and DM/GW tests reported next to raw metrics; promotion rule in [05](plan/05-backtesting.md) §4.
**Why.** After data leakage, researcher overfitting is the second way backtests lie.

## D-014 — Vault: the 12 months before project start are sealed

2026-11-16 · provisional · agent

**Decision.** 2025-11-16 → 2026-11-16 is unreadable by research code; openings are logged, counted and need a decision-log entry.
**Trade-off.** This seals almost all of the 15-minute day-ahead era (began 2025-10-01), so 15-minute-specific modelling has ~6 weeks of research data plus whatever accumulates forward. Chosen anyway: an untouched recent year in the current market design is worth more than faster 15-minute research, and forward data accrues daily.
**Alternative for the user (Q7).** Seal only the most recent 6 months.

## D-015 — Model hourly means on long history; separate intra-hour shape model

2026-11-16 · provisional · agent

**Why.** Hourly history spans a decade; 15-minute day-ahead history is one year. Decomposing keeps the long-history signal and isolates the data-poor part.
**Revisit** when two years of 15-minute data exist.

## D-016 — Model ladder: naive → LEAR → LightGBM → DNN → probabilistic → ensemble; each rung must earn its place

2026-11-16 · provisional · agent

**Why.** Published evidence: regularised linear and tuned DNN ensembles are state of the art; many claimed deep-learning gains vanish under proper evaluation. Transformers and foundation models enter only as ensemble candidates through the same gate. Details: [04](plan/04-models.md).

## D-017 — Data licensing: no scraping of Nord Pool; free tiers treated as research-only

2026-11-16 · provisional · agent

**Decision.** Primary sources are ENTSO-E, TSOs, eSett, Energinet, NVE, JAO, UMM. Nord Pool portal data is not scraped. Open-Meteo free tier and Energy-Charts prices are used for research only; a commercial licence is required before real-money trading depends on them.
**Why.** Terms of use; and a system that depends on scraped data is fragile.

## D-018 — Prices in EUR/MWh

2026-11-16 · accepted · agent

**Why.** Auction currency. Local-currency P&L (NOK/SEK/DKK) is a reporting concern, converted with as-of FX.

## D-019 — One decision log file instead of an ADR directory

2026-11-16 · provisional · agent

**Why.** The user asked for a decision log that people and agents can scan top to bottom. One append-only file is easier to keep honest than many small ones. Split into `docs/adr/` if it passes ~100 entries.

## D-020 — Facts are tagged verified / unverified in plan documents

2026-11-16 · accepted · agent

**Decision.** In `docs/plan` and `docs/research`, ✅ marks facts checked against a primary source or live API on the stated date; ⚠️ marks facts from the agent's memory. An ingest or model ticket must verify the ⚠️ facts it depends on and update the mark.
**Why.** The plan was produced unattended; market rules change often; false confidence is expensive here.

## D-021 — Planning session produced documents only; no application code

2026-11-16 · accepted · agent

**Context.** The user asked for a plan and a first version without being in the loop. Their workflow routes multi-session features through spec → tickets → implementation.
**Decision.** Stop at plan + decision log + glossary + agent rules. Phase 0 tickets are listed in [08](plan/08-roadmap.md).
**Why.** Several provisional decisions (stack, vault, scope) shape the first lines of code; cheaper for the user to overrule them now than after a scaffold exists.

## D-022 — Specs live in `docs/specs/` until an issue tracker exists

2026-11-17 · superseded by D-025 · agent

**Context.** `/to-spec` publishes to an issue tracker; none is configured and there is no git remote (Q10).
**Decision.** Specs are Markdown files `docs/specs/NNNN-slug.md` with a `labels` front-matter field (`ready-for-agent`). Move them to the tracker when one exists.

## D-023 — Phase 0 test seams: backtest run, knowledge view, time module

2026-11-17 · provisional · agent

**Decision.** Phase 0 is tested at three seams only: (1) end-to-end backtest run on recorded HTTP responses; (2) the knowledge view, where all look-ahead tests live; (3) property tests on the time module. No mocks of internal modules.
**Why.** The highest seams survive refactoring; look-ahead guarantees belong on the single read path.

## D-024 — Day-ahead backfill knowledge time: 13:00 local on D-1

2026-11-17 · provisional · agent

**Decision.** Assumed knowledge time for backfilled day-ahead prices = 13:00 Europe/Oslo on D-1 (results ≈12:45, plus 15 min safety lag).
**Revisit** after live snapshots record actual publication times.

## D-025 — GitHub Issues on a private repo is the tracker; specs and tickets live there

2026-11-17 · accepted · user

**Context.** `/setup-matt-pocock-skills`: the user chose a new private GitHub repo and the default triage labels. This also answers Q10 (remote: yes).
**Decision.** Repo `martinmoll/EnergyTrading` (private). Specs and tickets are GitHub issues; the Phase 0 spec moved from `docs/specs/` to issue #1. Config in `docs/agents/`.

## D-026 — No system price in Phase 0; free SYS source is an open research item

2026-11-17 · provisional · agent

**Context.** Plan and spec assumed Energi Data Service `Elspotprices` carried the Nordic system price until 2025-09. A live query shows its `SYS` series ends 2010-12-31.
**Decision.** Phase 0 runs on DK1 and DK2 only. The SYS pseudo-zone stays in the zones config. Finding a source for the system price (needed for futures/EPAD work, S4) is added to the research backlog; Nord Pool's paid data is the known fallback (Q4).
**Also found.** `Elspotprices` rate-limits to about one request per 5 minutes (it is a discontinued dataset). Ingest waits out HTTP 429; the backfill in #10 should use few, large requests.

## D-027 — Phase 0 stack is trimmed to what the code uses

2026-11-17 · provisional · agent

**Context.** Spec #1 listed DuckDB, httpx, pydantic, hypothesis and import-linter (D-010, D-011). The walking skeleton (#2) needs none of them yet.
**Decision.** Phase 0 uses Polars (Parquet scans for the store), stdlib `urllib` for HTTP, stdlib `tomllib` with TOML configs instead of pydantic + YAML, and `tzdata` (Windows has no system time-zone database). hypothesis arrives with #3 and import-linter with #6. DuckDB comes back when a query needs SQL or Polars scans get slow.
**Also.** The curated column is `knowledge_time_grade`, matching the glossary; plan docs 03 and 06 were updated from `knowledge_time_source`. The zones config has no per-zone time zone because every Nordic zone uses the single market time zone in the time module.

## D-028 — Naive forecasts on DST days match by local clock hour; data gaps stay missing

2026-11-17 · provisional · agent

**Decision.** The naive model maps the reference day to the delivery day by local clock hour. When the reference day is the spring DST day (no 02:00), 02:00 is filled from 01:00. When it is the autumn DST day, its two 02:00 prices are averaged. On an autumn DST delivery day both 02:00 hours get the same forecast. An hour missing from an ordinary reference day is **not** filled: that hour gets no forecast and the run's `n` drops below `n_expected`.
**Why.** Clock-hour matching is the standard EPF convention and keeps daily load shapes aligned. Filling ordinary gaps would hide data problems; quality checks (#8) should surface them instead.
**Also.** The decision cutoff is now derived as gate closure (12:00 local D-1) minus a 30-minute margin, so the two cannot drift apart.

## D-029 — Vintage rules: compare with what we held at ingestion; a changed value is known from when we ingested it

2026-11-17 · provisional · agent

**Decision.**
- `Store.append` compares each row with the vintage held for its key as of the row's own `ingested_at` (an as-of join). Identical values are dropped, so re-curating any old snapshot stores nothing.
- A row that changes a held value gets knowledge time max(publication-rule time, ingested_at), graded `observed` when that moves it later. Without this, a corrected price would appear in views from before we downloaded it: look-ahead.
- A row with no earlier vintage keeps the knowledge time the curator gave it (for backfill: the publication rule, graded `assumed`).
- Raw snapshots are named `<timestamp>_<content hash>`. A download identical to the latest snapshot of the same request writes nothing; any other content, including a revert to an older value, is a new snapshot. Files are opened with mode `x` and never overwritten, renamed or deleted.
- The D-024 day-ahead rule (13:00 local on D-1) now lives only in `configs/publication_rules.toml`; every rule carries a `reviewed` note.

**Known limits.** A changed value ingested *before* its rule time keeps the rule time, so it ties with its predecessor and wins on ingestion order; that is correct, since it really was the latest value by then. If raw snapshots were curated out of ingestion order, an earlier-ingested change could not move a later vintage's stored knowledge time (rows are immutable); curate processes snapshots in timestamp order, so this does not arise today. The store does not check that `assumed` knowledge times came from the rules; only curate assigns them. Prices published as null are skipped, so a withdrawn value never becomes a vintage.

## D-030 — How the look-ahead suite enforces the contract, and what it does not cover yet

2026-11-17 · provisional · agent

**Decision.**
- Tests live in `tests/leakage/` and run as their own gate in `check.py`, with config `addopts` and `PYTEST_ADDOPTS` cleared. Under that gate a skipped, xfailed or deselected test fails the run.
- Time-travel compares each view with an independent plain-Python statement of the as-of rule and with a physically truncated store. Future poison runs multi-day backtests so an engine that reuses later views is caught. The canary goes down to microsecond offsets and covers a future vintage on a key that already has a known one. The shuffled-target null and future poison run over `MODELS`, and every new model must be added there.
- The import boundary is an import-linter **forbidden** contract: models may not import ingest, curate, the engine or the CLI. A line-regex scan forbids direct data access (file readers, `Path`, `Store`, dynamic imports). This is not an allow-list of "KnowledgeView only" as in plan 06 §3. A forbid-list is what import-linter expresses cleanly, and the regex covers the rest. Its ceiling (aliased or multi-line calls) is marked `ponytail:`.
- The canary asserts the view returns nothing before the knowledge time. That is how "the store refuses" (plan 03 §5.4) shows up through this interface.
- Every check was mutation-tested: six injected leaks and two attempts to filter the gate all failed the check command.

**Not covered yet.** The too-good alarm (plan 03 §5.5) belongs to the run status in #9. The causal-imputation lint (§5.6) waits until code that imputes exists. Features and strategies packages must be added to the import contract when created (CLAUDE.md says so).

## D-031 — Vault guard: what is sealed, how it is opened, how research runs are scored

2026-11-18 · accepted (user confirmed 2026-11-18: forward period stays sealed until Phase 3) · agent

**Context.** Ticket #5 seals the vault (D-014) in code. Plan 03 §6 says an opening is logged, counted and backed by a decision-log entry naming the single configuration being evaluated.

**Decision.**
- The boundary is one config value: `start` in `configs/vault.toml`, read as 00:00 Europe/Oslo on that day (2025-11-16, D-014). Nothing in `src` repeats it.
- `as_of(t)` raises `VaultSealed` for any t at or after the boundary, the forward period after 2026-11-16 included, since a view there would also see vault data.
- Without a token, a view before the boundary hides every event at or after the boundary. Prices for delivery on 2025-11-16 publish at 13:00 on the 15th, before the boundary, but they are vault data.
- `store.open_vault(purpose)` is the only way in. The purpose must cite a decision-log entry (D-nnn) that exists in this file. Each opening appends one line (time, purpose, caller file:line) to `vault_log.jsonl` in the store root and returns a token. `as_of` accepts only tokens that store issued.
- `run_backtest` refuses every delivery day inside the vault, not only decision cutoffs there: the 2025-11-16 delivery day has its cutoff on the 15th but is still vault data. A vault run takes `vault_purpose` and opens the vault itself, so one run is exactly one logged opening and a token can never be reused for a second configuration. Its run config copies the log entry.
- Research runs score against actuals as known just before the boundary. Vault runs score with current knowledge, as a final evaluation should.
- Model code may not build a `KnowledgeView` or mention the vault (the boundary scan in `tests/leakage/test_boundaries.py`).

**Why.** Counting per opening, not per `as_of` call, keeps the count meaningful: a one-year vault run makes 365 views but is one look. Opening inside `run_backtest` closes the gap where one token could evaluate several configurations.

**Alternatives rejected.**
- Logging every `as_of` call with a token: it inflates the count by hundreds per run.
- A caller-held token for `run_backtest`: it can be reused across runs.
- Letting views before the boundary see vault events: that leaks one delivery day.

**Cost.**
- A price corrected after the boundary has the ingestion time as its knowledge time, so research scoring uses the earlier vintage.
- The vault log sits with the data, which git ignores. The decision-log entry each opening cites is what stays in git.
- **This changes plan 05:** forward data is unreadable for now. The plan's intra-hour models "on the pre-vault slice plus forward data" wait for a forward read path.
- Tests that read today's downloads open the vault, citing this entry.

**Revisit if:**
- Phase 3 needs forward data. It then needs a read path for t after the vault that still hides vault-era events.
- The user resizes the vault (Q7).

## D-032 — 15-minute day-ahead prices: native storage, hourly means in the naive model, scoring per MTU

2026-11-18 · accepted (user confirmed 2026-11-18: naive stays hourly-flat within each hour) · agent

**Context.** Ticket #7. The day-ahead MTU became 15 minutes from delivery day 2025-10-01. Energi Data Service publishes the two eras as separate datasets.

**Dataset status, checked against the live API on 2026-11-18 ✅.**
- `Elspotprices` is unchanged (fields `HourUTC`, `SpotPriceEUR`). Its last row is delivery day 2025-09-30, 23:00 local (HourUTC 2025-09-30T21:00).
- `DayAheadPrices` (fields `TimeUTC`, `DayAheadPriceEUR`) starts at 2025-10-01 00:00 local, every 15 minutes, with no hourly rows before.
- Neither record carries a resolution field. Nothing changed from what D-026 and plan 02 assumed.

**Decision.**
- **Storage.** `da_price` stores both datasets at native resolution, with no resampling. The `resolution` code comes from the delivery day, using one market-design date in the time module (`da_resolution`: PT60M before 2025-10-01, PT15M from it). Curation stops with an error on any row whose dataset does not match its day's era, so the two sources cannot overlap silently. It checks the era only, not row spacing: an hourly-spaced row in the 15-minute era becomes an incomplete hour in the naive model, and data-shape checks are ticket #8.
- **Naive model.** Reference-day prices are averaged to hourly means, and only complete hours count (MTU durations adding up to 60 minutes; the `PT…` code → duration map lives in the time module). The existing clock-hour rules (D-028) then apply. Each MTU of the delivery day, hourly or 15-minute, gets its clock hour's forecast. The rule is part of `model_rule` in the run config.
- **Scoring.** Scoring is per MTU of the delivery day, so `n_expected` is 96 for an ordinary 15-minute day. Metrics per zone carry `eras` keyed by the delivery day's MTU (`PT60M`, `PT15M`), alongside the totals. Every zone and every era in the run is reported, with `n` 0 when nothing was scored.

**Why.**
- A 15-minute product settles per quarter-hour, so scoring hourly means would hide the intra-hour error that the 15-minute market is about.
- Using only complete hours follows D-028: a gap stays visible instead of being half-filled.

**Alternatives rejected.**
- Resampling to hourly in storage: the ticket forbids it, and it loses the native data.
- Scoring against hourly mean actuals: that measures a product nobody trades.
- Averaging whatever quarter-hours are present: a missing quarter would shift the mean unnoticed.

**Revisit if:**
- The intra-hour shape model (D-015) lands: the naive benchmark then stays hourly-flat by design.
- A source publishes mixed resolutions within a day.

## D-033 — Data-quality checks on day-ahead prices: per snapshot, reported not dropped

2026-11-18 · accepted (user confirmed 2026-11-18: quality checks are exempt over the vault, Q12) · agent

**Context.** Ticket #8. Bad data must be visible before it reaches a model (plan 02 §5).

**Decision.**
- Curate checks each raw snapshot's `da_price` rows before storing them, per zone and delivery day:
  - **completeness:** the set of event times must equal the delivery day's MTUs from the time module (23/24/25 hours, 92/96/100 quarter-hours). This also catches rows off the MTU grid, such as hourly rows in the 15-minute era. A null price counts as a missing MTU. Every zone-day the snapshot's request asked for (the zones in its filter and the days its start and end span) is checked, so a zone or day the source left out entirely also fails.
  - **duplicate:** an event time appears more than once in a snapshot. Checked before `Store.append`, which would otherwise keep the last row silently.
  - **range:** a price outside `configs/quality.toml` bounds, which are the SDAC reference limits −500/+4000 EUR/MWh (✅ ACER Decision 02/2026 Annex I Art. 3, checked 2026-11-18), or NaN.
- Checks report and never drop or change data. A failing snapshot is still stored.
- One quality record per raw snapshot, at `data/quality/da_price/<snapshot>.json`, written once. It holds the failures (check, zone, delivery day, detail) and the snapshot's `ingested_at`. Every snapshot gets one, even an all-null one. Details give counts and times, never prices.
- **Vault (accepted, OPEN-QUESTIONS Q12).** The checks also run over vault-period snapshots, because curation has to store them. That is allowed without a decision-log entry, on the grounds that the checks reveal nothing about genuine outcomes:
  - Completeness and duplicates are about delivery, not price.
  - The range bounds are the hard market limits, so only bad data fails them.
  - No price value is recorded.
- `nordpower curate` prints one line per zone: zone-days checked, how many failed, by check. A zone-day counts as checked by the latest snapshot holding it, so a later complete download clears an earlier gap in the summary. Older records keep the history.

**Why.**
- Per-snapshot records match how data arrives, and they never need rewriting because snapshots never change.
- Reporting rather than dropping keeps the append-only store the full truth. Blocking belongs to the consumer that knows its decision time.

**Alternatives rejected.**
- Dropping failing rows at curation: the data is lost, and dropping on outcomes is leak L17.
- A single rolling quality table: it needs rewriting, or a vintage scheme of its own.

**Cost / follow-up.**
- The SDAC limits move automatically (Art. 4). A range failure means either bad data or a moved limit, and the config must be updated when NEMOs announce a change.
- Range bounds are the hard market limits, so a genuine price can never fail them. Blocking on range failures cannot become a filter on extreme outcomes (L17), as long as the bounds stay the market limits.
- Later phases that block ranges must use only quality records with `ingested_at` at or before their decision time.
- Not built yet (plan 02 §5): cross-source reconciliation (ENTSO-E vs Energi Data Service), timestamp sanity, revision counting. They wait until a second price source is ingested.
- Quality records are not re-written when check logic changes. Records made by old logic stay as they were.

**Revisit if:**
- NEMOs move a harmonised limit.
- The dashboard's Data Health page needs a query-friendlier format.

## D-034 — Data quality and feature engineering before model complexity

2026-11-24 · provisional · agent (on the user's direction, 2026-11-24)

**Context.** The user asked that data quality stay at the forefront, and that good features rather than complicated models be the main route to results. Plan 04 already ranks models as a ladder; it did not say where effort goes between rungs.

**Decision.**
- A model rung above M1 (LEAR) is only worked on once M1 runs on the feature set that the current data supports, and every dataset it reads has quality checks (plan 02 §5) whose failures have been looked at.
- Each feature family enters through an ablation on a fixed simple model (LEAR, or a small LightGBM): walk-forward rMAE per family added, with run ids. A family is kept only if the gain is significant (Diebold–Mariano). Families that do not help are recorded here as null results.
- When a complex model beats a simple one, the next step is to find what it exploited and try to engineer that as a feature for the simple model, before promoting the complex one.
- Features are stated as deltas where the naive forecast already carries the level (day-over-day, forecast revisions, deviation from normal); see `docs/learn/03-drivers-and-deltas.md`.

**Why.** In the EPF literature a well-specified LEAR is the benchmark most complex models struggle to beat clearly (Lago et al. 2021, plan 04 §1). Most failures in power forecasting are data and timing errors, which a more complex model hides better. Simple models on explained features also make leaks easier to see.

**Alternatives rejected.** Model-first exploration (try LightGBM/DNN on raw inputs and see): fast to a number, slow to understanding, and the gains are hard to attribute or trust.

**Revisit if** two years of walk-forward show complex models on raw inputs consistently and significantly beating LEAR/LightGBM on engineered features.

## D-035 — Replicate TSO methods and model their residuals

2026-11-24 · provisional · agent (on the user's direction, 2026-11-24)

**Context.** TSOs and their bodies (eSett, JAO) publish the formulas behind imbalance prices, flow-based capacities and their forecasts. The user wants these used to understand the market and to find where they are weak.

**Decision.** New plan document [09-tso-methods](plan/09-tso-methods.md). For each method: read the current document and log its version and effective date in the regime calendar; replicate the published value from published inputs as of the TSO's decision time; measure the residual of TSO forecasts vs outcomes; turn explained residuals into features, which then go through the normal ladder (D-034). Priorities: imbalance price (S2), flow-based domain (S1/S5), TSO load and wind/solar forecast errors (S1).

**Why.** A number we can recompute is a number we can forecast and audit. Replication is also a data-quality check: failing to reproduce a TSO's own number from its own inputs exposes our data bugs. Known assumptions (fixed margins, generation shift keys, stale capacity registers, one weather model) give predictable errors.

**Alternatives rejected.** Treating TSO outputs only as black-box features: loses the structure (e.g. the imbalance price's step on activation direction) and the audit.

**Revisit if** replication turns out impossible for a method because inputs are not published; then record it as a null result.

## D-036 — Weather and satellite data: NWP for day-ahead, satellite for nowcasting, labels and snow

2026-11-24 · provisional · agent (on the user's direction, 2026-11-24)

**Context.** The user asked how satellite data can improve wind and solar prediction, and how this works at day-ahead granularity.

**Decision.** New plan document [10-weather-and-satellite](plan/10-weather-and-satellite.md).
- Day-ahead weather inputs are NWP forecast runs available before the decision cutoff; satellite data reaches them through the weather models' data assimilation.
- Satellite data is used directly for: (a) solar nowcasting at 0–6 h for S2/S3/S6; (b) satellite-derived irradiance history (CAMS) as training labels and to measure NWP error on past days, never as a delivery-period input; (c) snow cover/snow water for hydro and S4.
- Our own wind and solar MW forecasts (power curves, clear-sky index, installed capacity as of t) enter as features expressed as deltas vs the TSO forecast, and stay only if they beat it walk-forward.

**Why.** A raw satellite image of today says little about clouds 12–36 hours ahead that NWP does not already contain. The value of satellites is at short horizons, as ground truth, and for slow hydrology states.

**Alternatives rejected.** Building a satellite-image deep model for day-ahead solar: large effort, weak expected gain over NWP at that horizon, and poor geostationary coverage at Nordic latitudes.

**Revisit if** a day-ahead solar error analysis shows NWP irradiance is the dominant error in DK/SE4 prices and a satellite-informed product beats it.

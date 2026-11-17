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

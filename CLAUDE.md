# Nordic power trading — agent rules

Algorithmic and ML trading research for the Nordic power markets (NO, SE, DK, FI). Status: Phase 0 in progress (tickets #2–#10, parent #1). Start at [docs/plan/08-roadmap.md](docs/plan/08-roadmap.md). Run `uv run python check.py` before every commit.

## Non-negotiable: no look-ahead

The full contract is [docs/plan/03-no-lookahead.md](docs/plan/03-no-lookahead.md). Read it before touching data, features, models or backtests. In short:

- Every stored value has an event time and a knowledge time. Raw data is append-only.
- Features, models and strategies read data **only** through `store.as_of(t)`. Never open files under `data/` from that code; never add a read path without a time.
- Realised weather (or any realised value) for the delivery period is never a model input.
- Fit every transform (scaler, imputer, selector) inside the model's `fit` on the knowledge view it is given.
- Time-series evaluation is walk-forward only. No random splits.
- Never weaken, skip or delete a leakage test to get a build green. A failing leakage test means the pipeline is wrong until proven otherwise.
- The vault period is sealed. Do not read it, plot it or compute statistics on it without an explicit decision-log entry.
- Every backtest is a recorded run; quote results only with their run id. Do not delete run records.
- A result that looks too good is a bug report, not a finding.

## Working rules

- Log decisions in [docs/DECISIONS.md](docs/DECISIONS.md) as you make them (append-only; supersede, do not rewrite). Record null results too.
- Use the terms in [GLOSSARY.md](GLOSSARY.md); add a term when a new concept is settled.
- In docs, mark facts ✅ (verified against a primary source, with date) or ⚠️ (unverified). Verify the ⚠️ facts your ticket depends on.
- Things only the user can decide go in [docs/OPEN-QUESTIONS.md](docs/OPEN-QUESTIONS.md) with a recommended answer; then proceed on the recommendation and mark the decision `provisional`.
- All timestamps UTC; market times via the single time module in Europe/Oslo. No ad-hoc timezone arithmetic.
- Do not scrape Nord Pool. Respect source licences ([docs/plan/02-data.md](docs/plan/02-data.md)).
- Secrets live in `.env`, never in the repo.

## Agent skills

### Issue tracker

GitHub Issues on the private repo `martinmoll/EnergyTrading`, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md`, decisions in `docs/DECISIONS.md` (no `docs/adr/`). See `docs/agents/domain.md`.

## Map

- [docs/plan/](docs/plan/) — markets, data, no-look-ahead contract, models, backtesting, architecture, dashboard, roadmap
- [docs/research/references.md](docs/research/references.md) — sources, with verified/unverified status

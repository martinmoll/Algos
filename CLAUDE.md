# Nordic power trading — agent rules

Algorithmic and ML trading research for the Nordic power markets (NO, SE, DK, FI). Status: Phase 0 complete (exit run 20261127T131921-naive-245114, D-039); Phase 1 next. Start at [docs/plan/08-roadmap.md](docs/plan/08-roadmap.md). Run `uv run python check.py` before every commit.

## Non-negotiable: no look-ahead

The full contract is [docs/plan/03-no-lookahead.md](docs/plan/03-no-lookahead.md). Read it before touching data, features, models or backtests. In short:

- Every stored value has an event time and a knowledge time. Raw data is append-only.
- Features, models and strategies read data **only** through `store.as_of(t)`. Never open files under `data/` from that code; never add a read path without a time.
- Realised weather (or any realised value) for the delivery period is never a model input.
- Fit every transform (scaler, imputer, selector) inside the model's `fit` on the knowledge view it is given.
- Time-series evaluation is walk-forward only. No random splits.
- Never weaken, skip or delete a leakage test to get a build green. A failing leakage test means the pipeline is wrong until proven otherwise. The suite is `tests/leakage/` plus the import contract in `pyproject.toml` (`[tool.importlinter]`); `check.py` runs both as their own gates. When you add a package that consumes data (features, strategies), add it to the import contract and to `GUARDED` in `tests/leakage/test_boundaries.py`.
- The vault period is sealed. Do not read it, plot it or compute statistics on it without an explicit decision-log entry.
- Every backtest is a recorded run; quote results only with their run id. Do not delete run records.
- A result that looks too good is a bug report, not a finding.
- Data quality and features before model complexity (D-034): a new dataset gets quality checks before any model reads it; a feature family enters by ablation on a simple model.

## Working rules

- Log decisions in [docs/DECISIONS.md](docs/DECISIONS.md) as you make them (append-only; supersede, do not rewrite). Record null results too.
- Use the terms in [GLOSSARY.md](GLOSSARY.md); add a term when a new concept is settled.
- In docs, mark facts ✅ (verified against a primary source, with date) or ⚠️ (unverified). Verify the ⚠️ facts your ticket depends on.
- Things only the user can decide go in [docs/OPEN-QUESTIONS.md](docs/OPEN-QUESTIONS.md) with a recommended answer; then proceed on the recommendation and mark the decision `provisional`.
- All timestamps UTC; market times via the single time module in Europe/Oslo. No ad-hoc timezone arithmetic.
- Do not scrape Nord Pool. Respect source licences ([docs/plan/02-data.md](docs/plan/02-data.md)).
- Secrets live in `.env`, never in the repo.
- **Finishing a ticket (D-038):** when the work is done and `check.py` passes, open a PR (`Closes #<n>` in the body), review the full diff yourself, post the findings as a PR comment, fix them, re-run `check.py`, and merge. Do not wait for the user. Stop and ask instead if a fix would weaken a leakage test, open or move the vault, change a too-good or quality threshold, or delete data or run records, or if a finding needs a decision only the user can make (put it in OPEN-QUESTIONS).

## Agent skills

### Issue tracker

GitHub Issues on the private repo `martinmoll/EnergyTrading`, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md`, decisions in `docs/DECISIONS.md` (no `docs/adr/`). See `docs/agents/domain.md`.

## Map

- [docs/plan/](docs/plan/) — markets, data, no-look-ahead contract, models, backtesting, architecture, dashboard, roadmap, TSO methods (09), weather and satellite (10)
- [docs/learn/](docs/learn/) — the owner's learning track. Agents may improve it when asked, but must not fill in the owner's journal or estimate tables for them
- [docs/research/references.md](docs/research/references.md) — sources, with verified/unverified status

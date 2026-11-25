# Module 5 — Models and what good looks like

Goal: read a run record and decide whether a model is good, lucky, or leaking.

## 1. The ladder, in one table

Full detail in [plan 04](../plan/04-models.md). Each rung must beat the one below under the walk-forward protocol ([plan 05](../plan/05-backtesting.md)).

| Rung | Model | Your question about it |
|---|---|---|
| M0 | Naive (reference day) | Did the walking skeleton get rMAE = 1.00? (It must, by construction.) |
| M1 | LEAR: LASSO on asinh prices + features | Which features did LASSO keep? Do they match your driver table? |
| M2 | LightGBM | What did it gain over M1, and which interactions explain it? |
| M3+ | DNN, multi-zone, probabilistic, ensemble | Is the gain significant and stable across zones and years? |

Start with M0 and M1. Spend your time on modules 2–4 until M1 on good features is strong; only then is M2 worth reading closely.

## 2. Metrics and what they mean

| Metric | Meaning | Good looks like |
|---|---|---|
| **rMAE** = MAE(model) / MAE(naive) | Fraction of naive error left | < 1.00 everywhere; well below it for a serious model. What "well below" means for Nordic zones is a Phase 2 measurement — quote it with a run id, not from memory |
| MAE, RMSE (EUR/MWh) | Absolute size of errors | RMSE ≫ MAE means a few large misses (spikes) dominate |
| Per-era, per-zone, per-hour breakdown | Where the model is weak | No zone or era worse than naive without an explanation |
| **Diebold–Mariano** | Is the difference between two models more than noise? | p < 0.05 across most zones before claiming an improvement |
| Pinball loss / CRPS, coverage | Quality of probabilistic forecasts | 90% intervals contain the outcome ~90% of the time, not 70% or 99% |

## 3. Good, lucky or leaking?

| Signal | Probably |
|---|---|
| Steady gain across zones, years and eras; DM significant; features you can explain | **Good** |
| Gain in one zone or one year only; DM insignificant; many trials before this one | **Lucky** (multiple testing — plan 05) |
| Gain is huge (rMAE halves); appears suddenly when one feature is added; strongest at the hour just after a publication time | **Leaking** — check knowledge times first |
| Backtest strong, forward (live paper) record weak | Leak or overfit; the forward record wins |

## 4. Exercises

1. **Run the skeleton.** `uv run nordpower backtest --start 2024-03-01 --end 2024-03-31` (after ingesting and curating from 2024-02-23, so the naive forecast has its reference days a week back). Open the run record in `data/runs/`. Find: run id, config, model rule, metrics per era. Confirm rMAE = 1.00 and explain why.
2. **Read the decisions behind it.** D-028 and D-032 in [DECISIONS.md](../DECISIONS.md): why only complete hours count, why scoring is per MTU.
3. **Plant a leak.** In a scratch branch, make a model that uses the actual price of D as a feature. Run the leakage suite (`uv run pytest tests/leakage`). Which test fails? If none does, you have found a gap in the suite — write it down and raise an issue, because that is a real finding. Then delete the branch. Never merge it.
4. **Significance by hand.** Once two models exist: compute the daily loss differential, its mean and its standard error. Is the mean more than two standard errors from zero? That is the intuition behind DM.

## 5. What good looks like

- Every number you quote has a run id.
- You can say for each model what it gained over the rung below, in which zones, and whether that is significant.
- You have at least one recorded null result — a feature or model that did not help.

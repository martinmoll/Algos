# Module 4 — Feature engineering

Goal: turn raw drivers into features that are legal at the decision time, carry the signal in a form a simple model can use, and earn their place in a walk-forward test.

## 1. A feature is a contract

Every feature in this repo is declarative (plan 04 §2): **name, source dataset, lag relative to decision time, aggregation**. The leakage tests enumerate them. When you design a feature, write those four things first:

```
name:        dk1_resload_delta_d1
source:      load_forecast, res_forecast (DK1), as of decision time
lag:         target day D vs realised D-1 (lagged actuals, published by 11:30 CET D-1?)  ← check!
aggregation: hourly; resload = load − wind − solar; delta = forecast(D,h) − actual(D-1,h)
```

The "check!" is the habit: is D-1's actual for the late hours really published by 11:30 CET on D-1? Usually not for the evening hours — they are still in the future. The legal version uses D-2, or the D-1 forecast instead of the actual.

## 2. The toolbox, roughly in order of payoff

| Technique | Example | Why it works |
|---|---|---|
| **Physics-based combinations** | Residual load; wind × hour; capacity factor = wind MW / installed MW | Encodes the merit order; a linear model cannot invent the subtraction |
| **Deltas** (module 3) | Forecast(D) − actual(reference day); latest forecast − TSO forecast | Matches what the naive forecast leaves unexplained |
| **Deviation from normal** | Temperature − seasonal normal; reservoir − weekly median | Removes seasonality the model would otherwise burn parameters on |
| **Variance-stabilising transform of the target** | asinh after median/MAD scaling | Spikes and negative prices dominate squared errors otherwise (plan 04 §1) |
| **Calendar done properly** | Holidays per country, bridge days, DST days, school holidays | Cheap, large effect, easy to get wrong |
| **Regime flags** | Flow-based era, 15-min era, mFRR EAM | Lets one model span structural breaks (plan 01 §3) |
| **Uncertainty features** | Ensemble spread of wind MW; spread of temperature | Predicts *how wrong* the point forecast will be — needed for sizing |
| **Cross-zone features** | Neighbour residual load; DE price lagged; min RAM on key CNECs | Zones are one coupled system |
| **Interactions** | Residual load × hour; wind × temperature | The stack is non-linear; trees find these, linear models need them spelled out |

## 3. Rules

- **Fit every transform inside `fit`.** Scalers, normals, power curves, PCA — computed on the knowledge view the model is given, never on the full dataset (CLAUDE.md).
- **One feature, one test.** Add a feature to a fixed simple model (LEAR or a small LightGBM) and run walk-forward. Keep it only if rMAE improves *and* the improvement survives a Diebold–Mariano test. Log the null results too (DECISIONS.md).
- **Prefer a feature that explains to a feature that fits.** If you cannot say why a feature should work (module 3), a gain is more likely luck or leakage.
- **Too good is a bug.** A single feature that cuts rMAE by half is almost certainly leaking. Check its knowledge time first.

## 4. Exercises

1. **Write five feature contracts** for DK1 in the format above: residual-load delta, wind revision vs TSO, temperature deviation from normal, holiday/bridge flag, DE price lagged. For each, state the latest legal lag.
2. **Find the leak in your own list.** Swap with Claude in a session: ask it to attack each contract for look-ahead. Fix what it finds.
3. **Ablation.** When Phase 2 exists: run LEAR with only price lags, then add one feature family at a time. Plot rMAE per step. Which family gives most? Does that match your module 3 table?
4. **Simple vs complex.** Run LightGBM on raw inputs and LEAR on your engineered features. Which wins? Write why in your journal. (Expect it to be closer than you think.)

## 5. What good looks like

- Every feature has a written contract and a one-line economic reason.
- The feature set is small enough that you can explain each one.
- You have an ablation table showing what each family added, with run ids.
- When a fancier model beats a simpler one, you know which features it exploited that you did not engineer — and you try engineering them.

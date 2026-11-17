# 04 — Models

A ladder. Each rung must beat the one below it under the [05-backtesting](05-backtesting.md) protocol to earn its complexity. Citations are in [references](../research/references.md); ✅ = verified there, ⚠️ = from memory.

## 1. What the literature says works (summary)

- **Simple, well-regularised linear models are hard to beat.** LEAR (LASSO-estimated autoregression on hundreds of lagged price/exogenous inputs) is the standard strong baseline; a tuned DNN is somewhat better; **ensembles of either are significantly better than single models** ✅ (Lago et al. 2021).
- **Most published gains are evaluation artefacts**: short test periods, weak baselines, no significance tests ✅ (same paper). Hence at least a full year of out-of-sample, rMAE vs naive, and Diebold–Mariano / Giacomini–White tests.
- **Variance-stabilising transforms** (asinh / mirror-log after median–MAD scaling) matter with spikes and negative prices ⚠️ (Uniejewski, Weron, Ziel 2018).
- **Combining calibration windows** of different lengths (e.g. 8 weeks, 12 weeks, 3 years, 4 years) beats any single window ⚠️ (Hubicka, Marcjasz, Weron 2019) — a cheap answer to regime change.
- **Probabilistic forecasts carry the economic value.** Distributional DNNs (Johnson SU output) beat LEAR/DNN + quantile regression averaging on German data ✅ (Marcjasz et al. 2023) but fail coverage tests without recalibration; **online conformal** wrappers fix reliability ✅. Decisions based on probabilistic forecasts have been reported to yield up to ~20% higher trading profit than point forecasts ✅ (secondary citation).
- **Time-series foundation models** (Chronos-Bolt/Chronos-2, Time-MoE, Moirai, TimesFM) are roughly on par with tuned task-specific models on 2024–25 day-ahead data, weaker in the price tails, and best used as an **ensemble member** ✅.
- **Balancing/imbalance is near-unpredictable from public data.** LSTMs barely beat naive on Nordic balancing; activation classifiers reach AUC 0.5–0.6; modelling the imbalance price *as a spread to day-ahead* makes simple AR models competitive ✅.
- **Intraday prices are close to a martingale** in the last hours; the latest traded price is a brutal benchmark ⚠️ (Narajewski & Ziel 2020).

## 2. Nordic-specific drivers (the feature thesis)

The Nordic price is a hydro-reservoir opportunity cost (the "water value") capped and floored by continental thermal prices via interconnectors, perturbed daily by wind, temperature and outages.

| Driver | Features (all strictly as-of decision time) |
|---|---|
| Autoregression | Prices D-1, D-2, D-3, D-7 per MTU; previous-day min/max/mean; last known hour of D-1 |
| Demand | TSO load DA forecast; temperature forecast (population-weighted); heating degree hours; calendar (weekday, national holidays, school holidays, bridge days) |
| Wind / solar | TSO DA wind & solar forecasts; our own weather-forecast-driven estimates; ensemble spread; **residual load** = load − wind − solar − must-run |
| Hydro | Reservoir filling vs median for week (level and deviation); weekly change; snow/inflow proxies (cumulative precipitation and temperature forecast over catchments); spring-flood season indicators |
| Nuclear / thermal availability | Available capacity from UMM (SE/FI nuclear units, CHP), planned vs unplanned |
| Network | DA cross-zonal capacities (NTC era); flow-based domain summary since 2024-10-29: max net positions, min RAM on key CNECs, number of presumably binding CNECs; interconnector outages (NordLink, NSL, Baltic Cable, EstLink, etc.) |
| Continental coupling | DE-LU/NL/PL/GB DA prices lagged; German wind/solar DA forecast; gas (TTF), carbon (EUA), coal → short-run marginal cost of gas and coal plants |
| Neighbour-zone interaction | Other Nordic zones' lagged prices and residual loads (multi-zone models) |
| Regime | Regime-calendar dummies; MTU resolution; rolling volatility |
| Balancing-specific | Wind/load forecast *revisions* since DA cutoff; previous ISPs' imbalance direction and mFRR prices; frequency; time of day; ramps at hour shifts |

Feature definitions are declarative (name, source dataset, lag relative to decision time, aggregation) so the leakage tests can enumerate them.

## 3. The ladder — day-ahead price (S1)

| Rung | Model | Why |
|---|---|---|
| M0 | **Naive**: same MTU of D-7 for Sat/Sun/Mon, D-1 otherwise ⚠️ (standard EPF naive) | Denominator of rMAE; anything not beating it is broken |
| M1 | **LEAR**: per-zone, per-hour LASSO on asinh-transformed prices + exogenous; daily recalibration; average over 4 calibration windows | The literature's benchmark; fast; interpretable |
| M2 | **Gradient boosting** (LightGBM), one model per zone with hour as feature and one per hour, point + quantile objectives | Handles interactions (hydro × wind × capacity), missing values; strong on tabular data; cheap to retrain |
| M3 | **DNN** (Lago-style MLP, 24/96 outputs, Bayesian-optimised hyperparameters, ensemble of 4+ seeds/configs) | Published SOTA single-family |
| M4 | **Multi-zone model**: one network predicting all 12 zones + system price jointly, with flow-based features | Zones are one coupled system; spreads are the tradable quantity |
| M5 | **Probabilistic layer**: (a) quantile regression averaging over M1–M4 point forecasts; (b) LightGBM quantiles; (c) distributional DNN with Johnson-SU head; all wrapped in **online/adaptive conformal calibration** | Trading needs calibrated distributions |
| M6 | **Foundation model member** (Chronos-2 with covariates, zero-shot and fine-tuned) | Cheap diversity for the ensemble. Subject to leak rule L15 (training cutoff) |
| M7 | **Ensemble / stacking**: constrained (non-negative, sum-to-one) weights learned on a trailing window; CRPS-optimal pooling for distributions | The most reliable gain in the literature |
| M8 | **Structural hybrid** (research track): a reduced-form supply-stack / water-value model whose output is a feature for M2–M4 | Extrapolates in regimes ML has never seen; this is where domain intuition goes |

**15-minute handling:** hourly history is long (2015+ on ENTSO-E ⚠️), 15-minute history starts 2025-10-01. Decision: model the **hourly mean** with the full ladder, and a separate small model for the **intra-hour shape** (quarter-hour deviation from the hourly mean) trained on post-October-2025 data, with ramp features (load/solar gradients). Revisit when two years of 15-minute data exist.

**Training cadence:** daily recalibration for M1; weekly for M2; monthly (with daily bias correction) for M3–M6. Cadence is a config field and part of the run record.

## 4. Imbalance / balancing (S2)

- Targets: (i) sign of system imbalance / regulation direction per ISP; (ii) spread `imbalance_price − da_price`; (iii) its quantiles.
- Models: logistic/GBM classifier for direction; quantile GBM for spread; AR on the spread as baseline; naive = "same as last known ISP" and "zero spread".
- Evaluate on post-2025-03-04 (mFRR EAM) data primarily; earlier data only as pre-training with a regime flag.
- Expect little skill. A tight, honest null result here is fine.

## 5. Intraday (S3) — when data exists

- Targets: IDA price − DA price; continuous VWAP (ID3-style index) − DA price.
- Features: forecast revisions since DA cutoff (wind, temperature, load), new UMMs, neighbouring-market ID moves.
- Benchmarks: zero spread (DA price as forecast), last traded price.

## 6. Futures / EPAD (S4)

- Fundamental expectation of average delivery-period spot: hydro balance deviation, reservoir trajectory simulation, weather-regime climatology, nuclear maintenance calendar, forward fuel prices.
- Compare with market price → position sized by a risk-premium model. Few independent bets per year: use Bayesian shrinkage and state uncertainty honestly; never optimise many parameters on this.

## 7. From forecast to position

- **Sizing**: start with fixed-fraction sizing on calibrated edge (expected spread / predictive std), hard position and drawdown limits per zone and in total. Kelly-style fractions only at ≤ ¼ Kelly and only after calibration tests pass.
- **Battery benchmark (S6)**: a 1 MW / 2 MWh simulated battery optimised by a small LP against forecast quantiles — the standard, low-controversy way to express forecast value in euros.
- **Reinforcement learning** for execution/asset control is deliberately deferred: sample-inefficient and the easiest place to hide overfitting.

## 8. What we will *not* do (yet)

- Transformers/TFT/N-HiTS as primary models — evidence of consistent gains over tuned GBM/DNN ensembles in EPF is weak; they enter only as ensemble candidates through the same gate.
- LLM/news sentiment — UMMs already carry the structured outage information.
- Order-book microstructure models — no data.

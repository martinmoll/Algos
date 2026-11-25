# 09 — TSO methods: copy the formula, find where it is weak

TSOs (Statnett, Svenska kraftnät, Energinet, Fingrid) and the bodies they run (eSett, JAO, the Nordic RCC) publish how they compute the numbers the market reacts to: imbalance prices, flow-based capacities, load and wind forecasts. These are rule books, not black boxes. Two things follow:

1. **We can reimplement them.** A number we can recompute from its inputs is a number we can *forecast* from forecasts of its inputs, and audit when the published value disagrees.
2. **Their assumptions are public, so their blind spots are too.** A formula with a fixed margin, a stale capacity register or one weather model has predictable errors. The residual (published value minus what a better model says) is a feature, and sometimes a trade.

✅ = verified against the primary document, with date. ⚠️ = from memory or a search summary only — read the document before code depends on it.

## 1. The method: replicate → measure the residual → use it

For every TSO method we take on:

| Step | Output | Gate |
|---|---|---|
| 1. **Read** the current document and the version history. Log the effective date of each version in the regime calendar | Formula + inputs + effective dates | Formula written in our docs with a ✅ citation |
| 2. **Replicate** the published value from published inputs, as of the TSO's own decision time | `replica` dataset | Replica matches the published value on ≥ 99% of MTUs; mismatches explained (rounding, special rules) |
| 3. **Measure** the residual between the TSO's forward-looking number and the realised outcome (e.g. TSO wind forecast − actual wind) | Residual series by zone, hour, season, regime | Residual is stable enough to describe (bias, seasonality, conditional on weather) |
| 4. **Explain** the residual with variables known at decision time | Feature candidates | Walk-forward test that the feature improves the price forecast (D-034) |
| 5. **Trade** only through the normal ladder: the residual feeds S1–S6, never bypasses the backtest | — | Same evidence bar as any other feature |

Step 2 is the data-quality payoff: if we cannot reproduce the TSO's own number from its own inputs, our inputs are wrong (missing MTUs, wrong time zone, wrong vintage), and we find out before a model does.

**No look-ahead.** The TSO computes with what *it* knew. A replica that uses a later revision of an input leaks. Inputs are read through `store.as_of(t)` at the TSO's documented decision time; the method version is the one in force at `t`.

## 2. Catalogue of methods worth replicating

Ordered by value to the plan.

### 2.1 Imbalance price (S2)

- **Documents.** NBS Handbook (eSett), current version 5.4, June 2026 ✅ (esett.com/handbook, checked 2026-11-24). National pricing notes, e.g. Fingrid *Imbalance price in Finland from 1.6.2026* ✅ (document exists, checked 2026-11-24).
- **Formula, as summarised from Fingrid's 2026 note ⚠️ (read §16 of the note before coding):**
  - If mFRR was activated in the *dominating direction* in the ISP:
    - upward: `imbalance_price = max(mFRR_marginal_price, aFRR_volume_weighted_price)`
    - downward: `imbalance_price = min(mFRR_marginal_price, aFRR_volume_weighted_price)`
  - Otherwise: `imbalance_price = da_price`.
  - An optional *incentivising component* can be added per country (NBS Handbook ✅ mentions it; values ⚠️).
- **Inputs and knowledge time.** mFRR marginal prices and activated volumes per ISP (ENTSO-E, eSett, Fingrid, Energinet): known shortly after the ISP. Dominating direction: from activated volumes. aFRR prices: after the ISP.
- **Where it is weak / exploitable.**
  - The price is a *step function of the activation direction*. Forecasting the direction (classification) is most of the problem; the spread conditional on direction is a second, easier model. This is the structure plan 04 §4 already assumes — the formula confirms it.
  - "No mFRR in the dominating direction → DA price" means many ISPs have zero spread by construction. A model that ignores this wastes capacity predicting noise.
  - Differences between countries (incentive components, aFRR treatment) are rule differences, not market signals. Replicating per country stops us learning them as "patterns".
- **Status.** Not started. Needs eSett endpoints (references: research owed).

### 2.2 Flow-based capacity domain (S1 zone spreads, S5)

- **Documents.** Nordic CCR capacity calculation methodology (CCM), approved by ACER, with "a mathematical description of RAM on CNE for the FB approach" (Art. 15 ⚠️ — article seen in a search summary, text not read). JAO Nordic Publication Handbook defines Fmax, FRM, AMR (adjustment for minimum RAM), GSK, RAM ✅ (abbreviation list, checked 2026-11-24).
- **Formula (standard flow-based form ⚠️, confirm against Art. 15):**
  - Flow on critical network element *k* for net positions **NP**: `F_k = F0_k + Σ_z PTDF_{k,z} · NP_z`
  - Remaining available margin: `RAM_k = Fmax_k − FRM_k − F0_k + AMR_k (+ other adjustments)`
  - Auction constraint: `Σ_z PTDF_{k,z} · NP_z ≤ RAM_k` for every CNEC *k*.
  - A binding constraint has a non-zero **shadow price** μ_k; zone price differences are `p_a − p_b = Σ_k μ_k (PTDF_{k,b} − PTDF_{k,a})` ⚠️ (standard KKT result).
- **Inputs and knowledge time.** JAO publishes the domain before the auction (sample `lastModifiedOn` 09:27 UTC on D-1 ✅, plan 02). PTDFs and RAMs are therefore legal day-ahead inputs; shadow prices are results (after 12:45 CET) and are *lagged-only* features.
- **Where it is weak / exploitable.**
  - **GSK** (generation shift keys) assume how generation in a zone moves when its net position moves. When the real dispatch differs (hydro vs wind dominated shifts), PTDFs are wrong and the realised flow differs.
  - **FRM** is a fixed margin per CNEC set from historical statistics; it is conservative on calm days and thin on volatile ones.
  - **Base case F0** comes from a D-2 common grid model; outages announced after it (UMM) are not in it.
  - **AMR** forces a minimum RAM; when it binds, the domain is policy, not physics.
  - Practical use: summarise the domain into features (min RAM on key CNECs, number of presumably binding CNECs, max net positions) and learn which CNECs historically bind under which residual-load patterns. A replica of the clearing with a simple supply curve per zone (plan 04 M8) can tell us *which constraint* will separate prices tomorrow.
- **Status.** Data reachable without key ✅. Not started.

### 2.3 TSO load forecasts (S1)

- **Documents.** ENTSO-E Transparency "day-ahead total load forecast" (A65 ⚠️ document type), plus each TSO's methodology note where published ⚠️ (Statnett, SvK, Energinet, Fingrid — to find).
- **Formula.** Usually not a single closed formula: regression or ML on temperature forecasts, calendar, recent load. What is documented is the *input set* and *issue time*.
- **Where it is weak / exploitable.**
  - Holidays, bridge days and school holidays: TSO models are national; regional holidays and bridge days are a known error source ⚠️.
  - Temperature: a TSO forecast issued in the morning uses an earlier weather run than the one we can see at 11:30 CET. **The delta between the latest temperature forecast and the one the TSO used** is a direct, legal feature.
  - Behind-the-meter solar reduces measured load on sunny days; if the TSO does not model it, the forecast error correlates with irradiance.
- **What we measure.** `load_actual − load_forecast_TSO` by zone, hour, temperature band, holiday flag. A stable bias is a feature; a residual explained by our temperature delta is a stronger one.

### 2.4 TSO wind and solar forecasts (S1, S2, S3)

- **Documents.** ENTSO-E "wind and solar forecast" day-ahead and intraday (A69 ⚠️). Energinet `Forecasts_Hour` with DayAhead / Intraday / 5h / 1h vintages and publication time ✅ (plan 02). Fingrid wind forecast datasets ⚠️.
- **Where it is weak / exploitable.**
  - **Installed capacity lag.** Forecasts scale by registered capacity; new parks and rooftop solar enter the register late. The error then trends with commissioning. Satellite/permit data can estimate it (plan 10 §5).
  - **Curtailment at negative prices.** Forecasts usually predict *available* output; producers curtail when the DA price is negative. Realised generation then sits below forecast exactly on negative-price MTUs — an outcome-dependent error that must not leak into features (it depends on the price we are forecasting).
  - **Icing** (Nordic winter, near 0 °C with high humidity) cuts wind output in a way simple power curves miss ⚠️.
  - **Single NWP source.** TSOs often rely on one or two weather models; an ensemble spread from other models tells us when to distrust the TSO number.
- **What we measure.** Forecast error by zone, hour, season, wind-speed band, temperature band; and the revision from DayAhead to Intraday vintages (a pure *delta*, known before ID gate closures — the S3 signal).

### 2.5 Reservoir and hydro balance (S4)

- **Documents.** NVE Magasinstatistikk ✅ (published Wed 13:00 for previous week). Not a TSO, but the same pattern: a documented publication rule. Nordic hydro balance definitions (snow + soil + reservoir deviation vs normal) ⚠️ are used by analysts, not published as one official number.
- **Replicate.** Reservoir deviation vs median, by zone and week, from NVE's own min/median/max.

### 2.6 Later

- mFRR/aFRR capacity procurement and FCR prices (Fingrid, Statnett, SvK): price formation is documented per auction ⚠️.
- HVDC ramping restrictions and implicit loss factors on interconnectors ⚠️: they shape hour-to-hour and 15-minute spreads at zone borders.
- Common grid model and D-2 congestion forecasts ⚠️.

## 3. What this does *not* license

- Reimplementing a TSO formula does not create an edge by itself; the market already knows the formula. Edge comes from forecasting its *inputs* better, or from recognising when the TSO's assumption is wrong *before* the price reflects it.
- Fingrid's terms bar systematic use of imbalance positions ✅ (plan 01). Understanding the imbalance price is for forecasting and hedging, not for deliberately running imbalance.
- A replica that matches too well over a period where the inputs were revised is suspicious: it probably uses the revised inputs. Check vintages.

## 4. Work items

Feeds the roadmap (plan 08):

1. Phase 1: add each TSO method document to `docs/research/references.md` with version and effective date; add effective dates to the regime calendar.
2. Phase 1: `tso_forecast_error` curated views (load, wind, solar) once ENTSO-E ingest exists. Quality gate: forecast knowledge time < valid time.
3. Phase 2: features from forecast errors and revisions (D-034 feature-first rule applies).
4. Phase 5 (S2): imbalance price replica per country, then direction classifier.
5. Phase 3/5 (S5): flow-based domain summary features; clearing replica with simple zonal supply curves (M8).

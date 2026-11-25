# 10 — Weather, wind, solar and satellite data

Weather is the largest daily driver of Nordic prices after the hydro balance: wind sets output in DK, SE and increasingly NO and FI; temperature sets winter demand; solar shapes midday in DK and southern Sweden. This plan says how weather becomes a day-ahead forecast, where satellite data fits, and where it does not.

✅ = verified against the primary source, with date. ⚠️ = from memory or a search summary only.

## 1. The chain from satellite to price

```
satellites, radiosondes, surface stations, aircraft
        │  (observations, minutes to hours old)
        ▼
data assimilation  →  numerical weather prediction (NWP) run, e.g. 00 UTC
        │  (run available a few hours after its nominal time)
        ▼
forecast fields: wind at 100 m, temperature 2 m, irradiance, cloud, precipitation — hourly for D+1
        │  (our snapshot: knowledge time = when we saw it)
        ▼
zone aggregation: capacity-weighted wind, population-weighted temperature, capacity-weighted irradiance
        │
        ▼
power models: power curve → wind MW, PV model → solar MW, temperature → load
        │
        ▼
features: residual load, deltas vs TSO forecast, ensemble spread  →  price model
```

**The key point for day-ahead:** satellite data reaches a day-ahead forecast *through* NWP. The weather model has already assimilated the satellite observations. For a delivery period 12–36 hours ahead, a raw satellite image of today's clouds says almost nothing that the NWP run does not; the clouds over Denmark at 10:00 today are gone by tomorrow afternoon. Direct satellite use pays off in three other places (§4).

## 2. Granularity and timing for day-ahead

- **Decision time.** Our day-ahead decision cutoff is before 12:00 CET gate closure (plan 01). Every weather input must be a run *available* by then.
- **Which runs.** The 00 UTC runs of the global and regional models are usually available by mid-morning CET; 06 UTC runs of some models arrive just before or after the cutoff ⚠️ (availability times per model to be measured by our own snapshots — that is exactly what the pre-gate burst in plan 02 §4 is for).
- **Lead time.** Delivery day D runs 00:00–24:00 CET; from a 00 UTC run on D-1 that is roughly 23–47 hours ahead.
- **Time resolution.** NWP output is typically hourly at these leads ⚠️; the 15-minute MTU (since 2025-10-01) needs interpolation. Do it deliberately: linear for temperature, solar geometry-aware for irradiance (interpolate the clear-sky index, not the irradiance), and keep the hourly value as the primary feature. The intra-hour shape model (plan 04 §3) uses ramps.
- **Spatial resolution.** Global models ~9–25 km; MET Nordic/MEPS ~2.5 km ⚠️. Wind is local (coasts, ridges, offshore); aggregate at turbine/park locations, not zone centroids.
- **Knowledge time.** Run time + availability delay, as *observed* when we snapshot live, *published* where the API states the run, *assumed* for Open-Meteo previous-runs backfill (day-granular lead offsets, most models from Jan 2024 ✅, plan 02).

## 3. Wind and solar — from weather to megawatts

### 3.1 Wind

| Step | What | Notes |
|---|---|---|
| Locations | Park coordinates and capacities per zone | From TSO/registry lists ⚠️ and OpenStreetMap ⚠️; date each capacity entry (commissioning) so the capacity *as of t* is used |
| Wind speed | 100 m wind (or hub-height extrapolation) at each park | Power scales roughly with wind speed cubed up to rated speed |
| Power curve | Empirical per zone: fit realised zone output vs capacity-weighted wind, on *lagged* data | Fit inside `model.fit` on the knowledge view (CLAUDE.md). A per-zone empirical curve beats a textbook curve because it absorbs wake losses and availability |
| Features | Forecast capacity factor; our MW forecast; **delta vs TSO forecast**; ensemble spread; ramp (change hour to hour); icing risk flag (temperature near 0 °C and high humidity ⚠️); offshore vs onshore split | The delta vs TSO is often the strongest single feature: the market prices the TSO number, our better number is the information |
| Pitfall | Curtailment at negative prices makes *realised* output depend on price. Fit power curves on past hours that were not curtailed, judged from prices and curtailment data known at fit time; the curve then predicts *available* output. Curtailment for the delivery day is a separate step that depends on the price forecast, never on the realised price | Leak L17-type trap |

### 3.2 Solar

| Step | What | Notes |
|---|---|---|
| Irradiance | Global horizontal irradiance (GHI) forecast | From NWP |
| Clear-sky index | `k = GHI / GHI_clearsky` | Clear-sky GHI from solar geometry (pvlib) or CAMS McClear (free ✅ per CAMS docs, checked 2026-11-24). Removes the deterministic daily/seasonal shape so the model learns *clouds* |
| Plane of array | Transpose to panel tilt/orientation (pvlib) | Nordic fleet is mostly rooftop, mixed orientations ⚠️ — use an effective orientation fitted on lagged data |
| Capacity | Installed PV per zone *as of t* | The weakest input: rooftop PV grows fast and is registered late. Biggest source of TSO solar error (plan 09 §2.4) |
| Nordic specifics | Low sun angle, long twilight, snow on panels in winter, high-latitude geostationary viewing problems (§4) | Solar matters mostly in DK1, DK2, SE3, SE4 ⚠️; small in NO |
| Features | Solar MW forecast, delta vs TSO, midday residual-load trough, ramp around sunrise/sunset (15-minute shape) | |

### 3.3 Temperature and load

Population-weighted temperature per zone, heating degree hours, wind chill for buildings ⚠️, and the *delta* between the latest temperature forecast and the one available when the TSO issued its load forecast (plan 09 §2.3).

### 3.4 Uncertainty

Ensembles (ECMWF ENS, ICON-EPS, GEFS via Open-Meteo ✅ plan 02; MEPS ensemble ⚠️) give a spread per variable. Spread of zone wind MW is the best free uncertainty feature for the price distribution (plan 04 M5) and for sizing (plan 04 §7).

## 4. Where satellite data is used directly

| Use | Horizon | Strategy | Source | Rule |
|---|---|---|---|---|
| **Solar nowcasting**: cloud motion from geostationary images every 10–15 min | 0–6 h | S2 imbalance, S3 intraday, S6 battery | EUMETSAT Meteosat / MTG FCI via the EUMETSAT Data Store (FCI Level 1c listed ✅, checked 2026-11-24) | Not a day-ahead input. Knowledge time = image time + delivery latency |
| **Irradiance history as truth** | Training labels only | S1 (solar model), forecast-error learning | CAMS solar radiation time-series: GHI/DHI/BNI from 2004, all-sky limited to the Meteosat field of view, ~100 requests/day ✅ (CAMS docs, checked 2026-11-24) | Realised values: used to fit and evaluate our solar model and to measure NWP error on *past* days, never as a delivery-period input (contract §4) |
| **Snow cover and snow water** | Weeks–months | S4 futures/EPAD, hydro balance features | Copernicus Land snow products, MODIS, Sentinel-1/2 ⚠️ | Snow is the stored water of the spring flood; satellite coverage partly fills the SE/FI hydrology gap (plan 02 gaps) |
| **Installed capacity mapping** | Months | Explain TSO solar/wind error trend | Satellite imagery + registries ⚠️ (research-grade) | Low priority; first try registries |
| **Offshore wind** (scatterometer winds) | Hours | Nowcasting only | ASCAT ⚠️ | Mostly already assimilated in NWP; low priority |

**High-latitude caveat ⚠️.** Geostationary satellites sit over the equator; above ~60° N the view is oblique and pixels are large and distorted. Polar-orbiting satellites pass often at high latitude but not continuously. Satellite nowcasting is strongest for DK and southern SE, weakest exactly where hydro and wind in the north matter. CAMS all-sky coverage follows the Meteosat field of view ✅, so check coverage per zone before relying on it.

## 5. Licences and access

| Source | Access | Licence | Status |
|---|---|---|---|
| Open-Meteo | No key | Free tier non-commercial ✅ | In plan 02; Q5 |
| ECMWF Open Data | No key | CC BY 4.0 ⚠️ | In plan 02 |
| MET Nordic / MEPS (thredds) | No key | ⚠️ (NLOD/CC BY expected) | Archive depth to verify (research owed) |
| CAMS solar radiation (SoDa) | Free registration ✅ | Copernicus licence ⚠️ | New |
| EUMETSAT Data Store (Meteosat/MTG) | Free registration (EUMETSAT EO Portal) ⚠️ | Some data CC BY 4.0, some "recommended" data licensed; low-latency licence bars redistribution ✅ (EUMETSAT data policy, checked 2026-11-24; which applies to FCI not confirmed) | New; only needed for nowcasting |
| Copernicus Land snow | Free registration ⚠️ | Copernicus licence ⚠️ | New; S4 |

Registrations are listed in [OPEN-QUESTIONS](../OPEN-QUESTIONS.md) Q13.

## 6. Order of work

1. **Phase 1:** live snapshots of NWP (Open-Meteo deterministic + ensemble, ECMWF Open Data) for park and population points — vintages cannot be backfilled.
2. **Phase 2:** zone aggregates and power models (wind, solar, load); features as deltas vs TSO forecasts. CAMS irradiance history to fit and validate the solar model.
3. **Phase 3:** ensemble spread features in the probabilistic layer.
4. **Phase 5:** satellite nowcasting for S2/S3/S6; snow products for S4.

Each step must beat the TSO forecast it replaces or complements, measured walk-forward (D-034). If our wind MW forecast does not beat the TSO day-ahead wind forecast, the TSO number stays the feature and ours is a recorded null result.

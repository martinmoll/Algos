# 02 — Data plan

What to collect, from where, and how each source behaves with respect to **knowledge time** (when a value became knowable). The storage contract is in [03-no-lookahead](03-no-lookahead.md).

✅ = verified by live API call or primary docs on 2026-11-16. ⚠️ = from memory/secondary, verify in the ingest ticket.

## 1. The single most important fact about power data

Almost no public source lets you ask "what did you show at 11:30 on 2023-03-14?". APIs return the **latest revision**. Forecasts (load, wind, weather) and even "actuals" (generation, load, imbalance) are revised later. A backtest on today's download is silently contaminated.

Two consequences drive the whole plan:

1. **Start live snapshotting immediately.** Every collector appends what it saw with the wall-clock time it saw it. True vintages cannot be backfilled later — every week of delay is a week of high-integrity history lost. This is the top priority after the store exists.
2. **Backfilled history is second-class.** It gets an *assumed* knowledge time from the documented publication schedule plus a safety lag, and is flagged as such. Results are reported separately for "observed-vintage" and "assumed-vintage" periods.

## 2. Sources

### Tier 1 — free, start now

| Source | What | Access | Knowledge-time quality | Notes |
|---|---|---|---|---|
| **ENTSO-E Transparency Platform** | DA prices (all zones), load actual + DA forecast, wind/solar DA + intraday forecast, generation by type, cross-border flows, DA capacities, hydro reservoir (weekly), outages (generation + transmission), imbalance prices/volumes, balancing activations | REST, free token (register, then email to request API access; ~3 working days) ✅. 400 requests/min per token ✅ | Latest revision only → **assumed** for backfill, **observed** once we snapshot | Backbone source. A44 prices use curve type A03: a point equal to the previous one is omitted (DK1 2024-01-15 returned 23 of 24 positions) ✅ 2026-11-18, so the ingest must fill missing positions from the previous one within a period. Python client `entsoe-py`. Needs user action: [OPEN-QUESTIONS](../OPEN-QUESTIONS.md) Q3 |
| **Energi Data Service** (Energinet) | `DayAheadPrices` (15-min, from 2025-10-01; DK1, DK2, DE, NO2, SE3, SE4) ✅; `Elspotprices` (hourly, 1999-07 → 2025-09-30; its `SYS` series stops at 2010-12-31 ✅; heavily rate-limited, roughly one request per 5 minutes ✅); `Forecasts_Hour` (wind/solar forecast with `TimestampUTC` publication time and DayAhead/Intraday/5h/1h vintages) ✅; balancing, production, exchange datasets | REST, **no key** ✅ | `Forecasts_Hour` carries a real publication timestamp → rare **observed** vintages for DK | First ingest target: zero setup. Also has `ImbalancePrice`, `MfrrEnergyActivationMarket`, `RegulatingBalancePowerdata`, `Forecasts_5Min`, `ForeignExchange`, `NordpoolMarket`, `RealtimeMarket` ✅ (100 datasets listed). Dataset changes announced around the DataHub upgrade from 17 Sep 2026 ✅ — check dataset status in the ticket |
| **eSett Open Data** | Imbalance prices, imbalance volumes, regulation prices, per MBA (bidding zone), 15-min from 2023-05-22 ✅ | Open REST API ✅ (host `api.opendata.esett.com` responds; exact endpoint paths ⚠️ — two guessed paths returned an empty list and no OpenAPI document was found at the usual locations; read the docs linked from opendata.esett.com in the ingest ticket) | Latest only; settlement data is corrected for up to ~2 weeks ⚠️ → assumed | Authoritative imbalance settlement source for NO/SE/FI/DK |
| **NVE Magasinstatistikk** | Weekly reservoir filling per NO zone + min/max/median, since 1995 | REST, no key ✅ (`biapi.nve.no/magasinstatistikk/api/...`) | Response includes `neste_Publiseringsdato` (next publication, Wed 13:00) ✅ → knowledge time = publication Wednesday 13:00 for week ending the previous Sunday | Classic leak: joining reservoir level on its *week* rather than its *publication* date. Sweden/Finland reservoir via ENTSO-E |
| **Open-Meteo Previous Runs API** | Weather forecasts as issued 1–7 days before valid time (`*_previous_dayN`), models incl. ECMWF IFS, ICON, GFS, MET Norway Nordic ✅ | REST, no key ✅ | Real forecast vintages, **most models from Jan 2024** ✅; day-granular lead offsets | Free tier is **non-commercial**; live trading needs a licence ✅ (Q5). Single Runs API gives exact run structure |
| **Open-Meteo forecast / ensemble API** | Live forecasts + ensembles (ECMWF ENS, ICON-EPS, GEFS) for our own snapshotting | REST | **Observed** from the day we start | Ensemble spread is the best free uncertainty feature |
| **JAO Publication Tool (Nordic CCR)** | Flow-based domain: PTDFs, RAM per CNEC, max net positions, max exchanges, shadow prices | REST, no key ✅ (HTTP 200 on `/nordic/api/data/maxNetPos`) | Records carry `lastModifiedOn` (sample: 09:27 UTC on D-1 for delivery day D ✅) → **published** grade | From 2024-10-29 (plus parallel-run data before). Essential for zone spreads post flow-based |
| **Fingrid Open Data** | FI wind forecast, load forecast, imbalance, frequency, reserves | REST, free key in `x-api-key` header, 10,000 req/day, CC BY 4.0 ✅ | Some forecast datasets are stored with update history ⚠️ | Needs key: Q3 |
| **Nord Pool REMIT UMM** | Urgent market messages: outages of generation, consumption, transmission (via NUCS) | Free API for registered users ✅; public RSS | Each message has a **publication timestamp and version history** → natively bitemporal | The cleanest PIT source we have. Nuclear and interconnector outages are first-order price drivers |
| **MET Norway Frost / thredds**, **SMHI**, **FMI**, **DMI** open data | Observations; MET Nordic (MEPS) forecast archive on thredds | Free | MEPS archive files are per-run → **observed** vintages further back than 2024 ⚠️ | Use if we need pre-2024 forecast vintages for NO/SE/FI |
| **ECMWF Open Data** | IFS/AIFS real-time forecasts (0.25°), rolling window | Free, CC BY 4.0 ⚠️ | Observed when snapshotted live | Alternative to Open-Meteo for live collection without licence concerns |
| **Fuel/carbon** | TTF gas, EUA carbon, API2 coal front-month closes | No clean free API. Candidates: ENTSOG (gas flows, free), Yahoo/stooq-style delayed quotes ⚠️, EEX end-of-day pages | Daily settlement known after close → knowledge time = close + lag | Matters mostly for DK1/DK2/SE4/NO2 and futures; second priority |

### Tier 2 — paid or restricted (decide later)

| Source | What | Cost / restriction |
|---|---|---|
| Nord Pool Data Portal / API | Official DA, **intraday (continuous trades, order book, IDA)**, system price, aggregated bid curves | Subscriptions ≈ €1.7–4k+/yr per product ✅ (secondary figures); historical data behind login since Jan 2022 ✅; internal use only. **We do not scrape Nord Pool.** |
| Euronext | Nordic futures and EPAD prices/settlements | Licensed; check for delayed/EOD free pages |
| Energy-Charts API (Fraunhofer) | Convenient DA prices for many zones | Response licence text: *private and internal use only* for prices ✅ → fine for research cross-checks, not a production dependency |
| Commercial weather (ECMWF full ENS/EC46, Meteomatics), Montel, Volue, Refinitiv, Energy Quantified | Pro-grade hydrology, ensembles, curated vintages | €€€ — what professional competitors use. Not planned |

### Gaps to be honest about

- **Intraday prices**: no free historical source with adequate depth. ENTSO-E carries IDA results ⚠️ (verify); continuous trade data is paid. Strategy S3 is blocked on Q4.
- **Aggregated bid/offer curves**: paid (Nord Pool). Limits fundamental stack modelling.
- **Pre-2024 weather forecast vintages**: only via MEPS archive (NO/SE/FI) or TSO forecasts that embed weather (ENTSO-E wind/load DA forecasts). **Realised weather is never an input for the delivery period** — see [03](03-no-lookahead.md) §4.
- **Hydrology beyond reservoir filling** (snow reservoir, inflow forecasts): NVE publishes weekly snow/inflow summaries ⚠️; SE/FI coverage is weak. Proxy via precipitation/temperature forecasts over catchment polygons.

## 3. Dataset catalogue (logical)

Each row becomes one curated table. `zone` uses our canonical zone ids; all times UTC.

| Dataset | Grain | Primary source | Cross-check |
|---|---|---|---|
| `da_price` | zone × MTU | ENTSO-E | Energi Data Service (6 zones), Energy-Charts |
| `system_price` | MTU | **No free source found.** Energi Data Service `SYS` ends 2010-12-31 ✅ (D-026); Nord Pool (paid) ⚠️ | — |
| `ida_price`, `id_continuous` | zone × MTU (× trade) | ENTSO-E ⚠️ / Nord Pool (paid) | — |
| `imbalance_price`, `imbalance_volume` | zone × ISP | eSett | ENTSO-E, Energi Data Service, Fingrid |
| `mfrr_activation` | zone × ISP × direction | ENTSO-E / TSOs | — |
| `load_actual`, `load_forecast` | zone × MTU × vintage | ENTSO-E | TSOs |
| `res_forecast` (wind on/offshore, solar) | zone × MTU × vintage | ENTSO-E | Energi Data Service, Fingrid |
| `generation_by_type` | zone × MTU | ENTSO-E | — |
| `xborder_flow`, `xborder_capacity` | border × MTU | ENTSO-E | JAO |
| `fb_domain` | CNEC × MTU | JAO | — |
| `outage_message` | message × version | Nord Pool UMM | ENTSO-E outages |
| `reservoir` | zone × week | NVE (NO), ENTSO-E (SE, FI) | — |
| `weather_forecast` | grid point/zone aggregate × valid time × run | Open-Meteo / MEPS / ECMWF | — |
| `weather_obs` | station/grid × hour | ERA5 / national met services | Only for *lagged* features and forecast-error learning |
| `fuel_carbon` | product × day | TBD | — |
| `futures_settlement` | contract × day | Euronext (TBD) | — |
| `calendar` | zone × day | Generated (holidays per country, DST, regime calendar) | — |

## 4. Collection schedule (live)

Collectors are idempotent CLI commands run by a scheduler; each appends a new snapshot with `ingested_at` and never overwrites.

| Cadence | Collect |
|---|---|
| Every 15 min | UMM messages; imbalance/mFRR prices; intraday forecasts (wind/load) |
| Hourly | Weather forecast runs as they land; generation, flows |
| Pre-gate burst 09:00–11:45 CET | Everything the DA decision uses (load/RES DA forecasts, FB domain, latest weather run) — snapshot at 10:00, 11:00, 11:30 so we learn what is reliably available by cutoff |
| 12:45–14:00 CET | DA results (poll every 5 min, as Energinet recommends ✅) |
| Daily | Fuel/carbon closes, futures settlements, eSett corrections (re-pull last 14 days as new snapshots) |
| Weekly Wed 13:05 CET | NVE reservoir |

A PC that is off loses vintages. Recommendation: a small always-on host (cheap VPS or home server) for collectors only — Q6.

## 5. Data quality gates

Run on every ingest; failures are visible on the dashboard's Data Health page and block downstream backtests on affected ranges:

- Completeness per zone-day (expected MTU count, DST days = 92/100 quarter-hours).
- Range and unit checks (price bounds: harmonised min/max −500/+4000 EUR/MWh ⚠️).
- Cross-source reconciliation (ENTSO-E vs Energi Data Service DA prices must match to the cent).
- Revision tracking: when a re-pull differs from an earlier snapshot, both are kept and the diff is counted — this *measures* how wrong the "assumed" backfill could be.
- Timestamp sanity: `knowledge_time >= ` earliest physically possible time; no forecast with knowledge time after its valid time.

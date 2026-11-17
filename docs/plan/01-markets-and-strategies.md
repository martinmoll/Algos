# 01 — Markets and strategies

What we trade, where an edge could plausibly come from, and what is realistically accessible.
Facts marked ✅ were verified against a primary source on 2026-11-16 (see [references](../research/references.md)); facts marked ⚠️ are from memory and must be verified before code depends on them.

## 1. Who is "the Nordic market"

| Country | Bidding zones | TSO | Role in this project |
|---|---|---|---|
| Norway | NO1, NO2, NO3, NO4, NO5 | Statnett | **Target** |
| Sweden | SE1, SE2, SE3, SE4 | Svenska kraftnät | **Target** |
| Denmark | DK1 (west, continental synchronous area), DK2 (east, Nordic synchronous area) | Energinet | **Target** |
| Finland | FI | Fingrid | **Target** — part of the Nordic synchronous area and price formation; cannot be left out |
| Estonia, Latvia, Lithuania | EE, LV, LT | Elering, AST, Litgrid | Features only (coupled via Nord Pool; desynchronised from the Russian grid Feb 2025 ⚠️) |
| Germany, Netherlands, Poland, Great Britain | DE-LU, NL, PL, GB | — | Features only (interconnected neighbours that set the marginal price in the south) |
| Iceland | — | Landsnet | Excluded: electrically isolated, no coupled market |

12 target zones. The **system price** (an unconstrained Nordic reference price calculated by Nord Pool) is the underlying of the financial futures and is a 13th target.

## 2. Market sequence (what can be traded, in time order)

| Market | Timing | Resolution | Notes |
|---|---|---|---|
| Financial futures (Euronext Nord Pool Power Futures) | Years → days ahead | Day/week/month/quarter/year | Cash-settled against system price; **EPADs** settle against (zone price − system price). Migrated from Nasdaq, fully live 16 Mar 2026 ✅ |
| Day-ahead auction (SDAC, run by Nord Pool/EPEX) | Gate closure 12:00 CET D-1, results ≈12:45–13:00 | 15 min since delivery day 1 Oct 2025 ✅ (hourly before) | The reference price. Flow-based capacity allocation in the Nordic CCR since 29 Oct 2024 ✅ |
| Intraday auctions (SIDC IDA1/2/3) | Gate closure 15:00 D-1, 22:00 D-1, 10:00 D (IDA3 covers 12–24h only); results 20 min later ✅ | 15 min | Live since 13 June 2024 ✅ |
| Intraday continuous (SIDC/XBID) | From ≈15:00 D-1 to 1h (or less) before delivery | 15 min in Nordics since 18 Mar 2025 ✅ | Pay-as-bid order book |
| Balancing: mFRR energy activation market (EAM) | Automated, per 15 min | 15 min | Live 4 Mar 2025 ✅; produced a volatility regime change and more negative imbalance prices ✅ |
| Imbalance settlement (eSett) | After delivery | 15 min ISP since 22 May 2023 ✅ | Single price, single position since 1 Nov 2021 ✅ |

## 3. Structural breaks every model must respect

These are regime boundaries. Any training window or backtest spanning them must treat them explicitly (regime features, window choice, or separate evaluation):

- 2021-11-01 single imbalance price ✅
- 2021 H2 – 2023: European gas crisis (price level and volatility regime)
- 2023-05-22 15-minute imbalance settlement period ✅
- 2024-06-13 intraday auctions (IDAs) ✅
- 2024-10-29 Nordic flow-based market coupling ✅ (changes how zone spreads form; NTC-era spread models break)
- 2025-03-04 mFRR EAM ✅ (imbalance price regime break)
- 2025-03-18 15-minute intraday in the Nordics ✅
- 2025-10-01 15-minute day-ahead MTU ✅
- New interconnectors / nuclear units (e.g. Olkiluoto 3 regular operation 2023 ⚠️)

These live in code as a dated `regime calendar`, not as tribal knowledge.

## 4. Where edge can plausibly come from

A day-ahead price forecast is **not a strategy** — you cannot hold a day-ahead position on its own. Every tradable idea is a *spread between two settlement prices for the same delivery period*, or an asset optimisation. Ranked by (data availability × research support × accessibility):

| # | Strategy family | Legs | Edge hypothesis | Data cost | Realism notes |
|---|---|---|---|---|---|
| S1 | **DA forecasting** (foundation, not tradable alone) | — | Feeds everything else; richly studied; lets us prove the no-look-ahead machinery against published benchmarks | Free | Phase 2 deliverable |
| S2 | **DA ↔ imbalance** direction/spread | DA vs imbalance price | System imbalance direction is partly predictable from wind forecast error, outages, ramps | Free (eSett, ENTSO-E) | Literature says public data carries limited signal and naive baselines are strong ✅. BRPs have a **balance obligation** (plan for and achieve balance — NBS handbook ✅); Fingrid's terms explicitly bar systematic use of imbalance ✅; NO/SE wording not yet checked ⚠️. Treat as *research + hedging signal*, not a stand-alone live strategy |
| S3 | **DA ↔ intraday** (IDA and continuous) | DA vs ID VWAP / IDA price | Forecast-update drift (wind/temperature revisions after 12:00) | ID prices are **paid** Nord Pool data, or self-collected going forward | Intraday prices are close to a martingale given the latest price ⚠️ (Narajewski & Ziel); edge is in the *update* information |
| S4 | **Futures vs expected spot** (system price weeks/months; EPADs) | Future vs realised average spot | Hydrology (reservoir, snow, inflow), nuclear availability, weather regimes, risk premia | Futures prices are paid/delayed (Euronext) | The only family accessible without being a balance responsible party; lower frequency → few independent bets → hard to validate statistically |
| S5 | **Cross-zone spreads** | Zone A vs zone B (via EPADs or physical) | Flow-based domain + hydro balance predict congestion | Free (JAO) | Expressed through S1/S4 |
| S6 | **Flexible asset optimisation** (battery, hydro, demand) | DA + ID + reserves | Probabilistic forecasts → better bids; papers report up to ~20% higher profit vs point forecasts ✅ (secondary citation) | Free | Only if you have or simulate an asset. Simulated battery is a clean, well-studied way to turn forecast quality into money |

**Plan:** build S1 first (it is the measuring stick and the shared input), then S2 and S6 (free data, honest economic evaluation), then S3/S4 as data access allows.

## 5. Market access — the uncomfortable part

- Physical markets (DA, ID, balancing) require Nord Pool (or EPEX) membership **and** balance responsibility — being a BRP or contracting with one ✅. This is a company-level commitment with collateral, not a retail account.
- Financial futures need a clearing-member relationship; no evidence of retail broker access was found ✅ (absence of evidence — ask Euronext/brokers).
- Therefore the project is designed so that **paper trading is a first-class, tamper-evident mode** (see [03-no-lookahead](03-no-lookahead.md) §7): forecasts and orders are committed to an append-only, hash-chained log *before* gate closure, then settled against published prices. This gives a real, uncheatable track record that can be shown to a BRP, a fund, or an employer, or used to justify the cost of membership.
- Route to live is an open question for the user: [OPEN-QUESTIONS](../OPEN-QUESTIONS.md) Q1.

## 6. Honest prior

Nordic power is traded by utilities and specialist funds with paid weather ensembles, hydrological models and physical assets. A realistic first goal is: *match published state-of-the-art forecast accuracy on Nordic zones under a strictly point-in-time protocol, then measure whether any spread strategy survives costs and multiple-testing corrections.* Finding "no edge after costs" is a valid, valuable result, and the system must be able to report it.

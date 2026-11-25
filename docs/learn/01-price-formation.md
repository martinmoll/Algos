# Module 1 — Price formation

Goal: explain tomorrow's price in a zone from first principles, before any model.

## 1. The auction in one paragraph

At 12:00 CET on D-1, buyers and sellers in every European coupled zone submit bids for each 15-minute MTU of D. The coupling algorithm (Euphemia) finds prices and flows that maximise total welfare subject to the network limits (the flow-based domain in the Nordics since 2024-10-29). Results are published around 12:45–13:00 CET. Every seller who clears is paid the zone's clearing price — the price of the most expensive accepted offer, adjusted for congestion. Read [plan 01 §2](../plan/01-markets-and-strategies.md) for the full sequence of markets.

## 2. The merit order

Sort supply offers by price. Roughly, from cheap to expensive:

| Supply | Marginal cost | Nordic note |
|---|---|---|
| Wind, solar, run-of-river | ≈ 0 | Wind is large in DK, SE, FI and growing in NO |
| Nuclear | Low | SE3, FI; outages (UMM) move prices a lot |
| Reservoir hydro | **Water value** — the opportunity cost of using water now instead of later | Most of NO, northern SE. Not fuel cost: an expectation of future prices given reservoir, snow and inflow |
| CHP, biomass | Medium | Heat-driven in winter |
| Gas, coal (mostly via imports) | Fuel + carbon | Sets the price in the south (DK1, DK2, SE4, NO2) when interconnectors import from DE, NL, PL |

Demand is fairly inelastic in the short run. The price is where demand crosses the stack.

**Residual load** = demand − wind − solar (− other must-run). It is the part dispatchable plants and imports must cover, and it is the single most useful idea in this whole track: high residual load pushes you up the stack, low pushes you down — sometimes below zero when must-run output exceeds demand.

## 3. Why Nordic prices differ by zone

- **Hydro dominates the north.** NO and northern SE price near the water value most of the time; that changes slowly (weeks).
- **The south is coupled to the continent.** DK1, DK2, SE4, NO2 import the continental gas/coal price when interconnectors are not full.
- **Congestion splits zones.** When the network binds, zones decouple and spreads open. Flow-based capacity (plan 09 §2.2) decides which constraint binds.
- **Weather moves prices daily.** Wind and temperature change residual load hour by hour.

## 4. Exercises

1. **Draw the stack.** For a cold, windless January evening in DK1 and a windy, mild Sunday in May: sketch supply and demand, mark where they cross. Write your expected price range for each before looking anything up.
2. **Pull real prices** for DK1 and DK2 over 2024 (pre-vault):

   ```bash
   uv run nordpower ingest elspotprices --start 2024-01-01 --end 2024-12-31 --zones DK1,DK2
   ```

   ```bash
   uv run nordpower curate
   ```

   `Elspotprices` allows about one request per 5 minutes and ingest waits automatically, so a full year can take a while; start with a month if you are impatient.

   Then in a notebook, through `Store("data").as_of(...)`: plot the hourly profile by month, and the DK1−DK2 spread. When is the spread non-zero? Write your explanation in the journal.
3. **Negative prices.** Find the hours in 2024 when DK1 was negative. Which hours of the day, which months, which weekdays? Predict the answer first.
4. **Whiteboard test.** Explain to someone (or to Claude, in a session) why NO2 is usually closer to DK1 than NO4 is. If you need to look something up, note what.

## 5. Read

- [Plan 01](../plan/01-markets-and-strategies.md) §1–3 (zones, market sequence, regime breaks).
- [Plan 04](../plan/04-models.md) §2 (the Nordic driver table) — you should be able to defend every row of it by the end of module 3.
- [Glossary](../../GLOSSARY.md), Market section.

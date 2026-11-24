# Module 3 — Drivers and deltas

Goal: know which explanatory variables move each zone's price, in which direction, by roughly how much — and why the *change* in a driver matters more than its level.

## 1. Explain the change, not the level

The naive forecast says "tomorrow looks like the reference day" (yesterday, or a week ago for Mon/Sat/Sun). Everything a model adds is an explanation of **why tomorrow differs from the reference day**. So the natural question is:

> price(D) − price(reference day) = f( driver(D) − driver(reference day), … )

These differences are the **deltas**. Three kinds matter:

| Delta | Example | Why it matters |
|---|---|---|
| **Day-over-day** | Residual load forecast for D minus realised residual load on D-1 | The naive forecast already contains yesterday's level; only the change is news |
| **Forecast revision** | Latest wind forecast minus the one available at an earlier time (or the TSO's) | Markets price the older number; the revision is information not yet in the price (plan 09 §2.3–2.4) |
| **Deviation from normal** | Reservoir filling minus the weekly median; temperature minus seasonal normal | Removes the seasonal pattern the model would otherwise spend capacity on |

A model with deltas as features needs fewer parameters to say the same thing, and it degrades more gracefully when the level shifts (new regime, new capacity).

## 2. The driver map

Signs are for the zone's price when the driver goes up. Sizes are **for you to measure** in the exercises — write your guess first, then estimate it on pre-vault data. Do not copy numbers from the internet into this table.

| Driver | Zones most affected | Sign | Horizon it acts on | Your estimate (EUR/MWh per unit) |
|---|---|---|---|---|
| Wind forecast (GW) | DK1, DK2, SE3, SE4, FI | − | Hours | |
| Solar forecast (GW) | DK1, DK2, SE4 | − (midday) | Hours | |
| Temperature (°C), winter | All, strongest FI, SE3, NO1 | − | Hours–days | |
| Load forecast (GW) | All | + | Hours | |
| Residual load (GW) | All | + (non-linear: steep at the top of the stack) | Hours | |
| Reservoir deviation from median (TWh) | NO, SE1–SE2 | − | Weeks | |
| Nuclear availability (GW) | SE3, FI | − | Days–weeks | |
| Interconnector outage | Border zones | ± (decouples) | Days | |
| German/Dutch price (lagged), gas, carbon | DK1, DK2, SE4, NO2 | + | Days | |
| Flow-based min RAM on key CNECs | Spreads between zones | wider spread when low | Hours | |

**Non-linearity.** The stack is flat at the bottom (hydro, wind) and steep at the top (peakers, imports at scarcity). The same 1 GW of wind is worth little on a mild windy night and a lot on a cold still evening. That is why interactions (residual load × hour, wind × temperature) and transforms matter (module 4).

## 3. Exercises

1. **Guess, then measure.** For DK1 in 2024: regress the day-over-day change in daily mean price on the day-over-day change in daily mean residual load. (Use actual load and wind *lagged* for now, or forecasts once ENTSO-E is ingested.) Compare the coefficient with your guess. Then repeat with levels instead of deltas. Which explains more (R²)? Write why.
2. **Hour matters.** Do the same per clock hour. Where is the slope steepest? Link it to the stack.
3. **Revision as news.** Once `Forecasts_Hour` is ingested: compute DayAhead − Intraday wind forecast for DK1. Is it centred on zero? Does it correlate with the DA→imbalance price spread? (Lagged data only.)
4. **Hydro.** From NVE (when ingested): plot NO2 weekly reservoir deviation from median vs the weekly mean NO2 price. Use the *publication* Wednesday as the knowledge time, not the week.
5. **Your own driver table.** Fill in the "your estimate" column above in your journal for DK1, NO2 and SE3. Revisit it after module 5.

## 4. What good looks like

- For any day, you can explain most of the price change vs the reference day with two or three named deltas.
- You know which drivers are legal at 11:30 CET (forecasts, published reservoir, UMM) and which are not (actuals for the delivery day).
- Your estimates are written down, with the data range and method, so they can be compared with what the model learns.

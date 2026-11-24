# Module 6 — From forecast to trade

Goal: turn a forecast into a decision you write down before gate closure, then settle it honestly afterwards. Paper first (D-003); real money only through Phase 6.

## 1. A forecast is not a trade

You cannot hold "DK1 tomorrow" on its own. A trade is always a **spread between two settlements for the same delivery period** (plan 01 §4):

| Trade | You profit if | Forecast you need |
|---|---|---|
| DA vs intraday (S3) | Your DA position is on the right side of where intraday ends up | Expected ID price − DA price |
| DA vs imbalance (S2, research only) | Imbalance price is on the side you expected | Direction and spread (plan 09 §2.1) |
| Zone spread via EPAD (S4/S5) | Zone − system price moves your way | Expected spread over the contract period |
| Battery (S6) | Charge cheap, discharge dear | Shape of tomorrow's prices, with uncertainty |

The battery (S6) is the cleanest first paper trade: no counterparty, no market access needed, and the profit is a direct measure of how good your price *shape* forecast is.

## 2. The trade ticket

Write one before 11:30 CET on D-1. A template:

```
date written (UTC):    2026-..-.. 09:xx
delivery day:          D
zone / product:        DK1, 1 MW / 2 MWh battery (simulated)
inputs used (as of):   wind DA forecast (run 00 UTC, seen 07:10 UTC), load forecast (TSO, 08:00 UTC), …
expectation:           cheapest 2 h: 03:00–05:00 at ~X EUR/MWh; dearest 2 h: 17:00–19:00 at ~Y
key deltas:            wind −2.1 GW vs D-1; temperature −4 °C vs normal
uncertainty:           ensemble wind spread high in evening → widen expectations
decision:              charge 03:00–05:00, discharge 17:00–19:00
why it could be wrong: wind ramp timing; nuclear UMM pending
costs assumed:         round-trip efficiency 90%, fees …
```

After results (≈13:00 CET) and after delivery: fill in realised prices, P&L after costs, and one line of what you learned. Keep tickets in your journal until the Phase 4 commitment log exists; then the system hash-chains them before gate closure, so nobody — including you — can edit them later.

## 3. Sizing and risk (plan 04 §7)

- Size by **edge / uncertainty**: expected spread divided by predictive standard deviation. No edge estimate, no position.
- Hard limits per zone and in total; a drawdown limit that stops trading.
- Kelly fractions only at ≤ ¼ Kelly, and only after calibration tests pass.
- Costs are part of the trade: exchange and clearing fees, bid–ask in intraday, imbalance cost of being wrong.

## 4. Exercises

1. **Ten tickets by hand.** For ten pre-vault days (e.g. in March 2025), write the ticket using only data available at 11:30 CET D-1 — use `store.as_of(<D-1 11:30 CET>)`. Then settle. This trains the habit of thinking at the decision time.
2. **Battery against naive.** For the same days: what would the battery have earned using the naive forecast's shape? Using your judgement? Using perfect foresight? Your number divided by the perfect-foresight number is your *capture rate* — a far more honest measure than P&L alone.
3. **Post-mortem on the worst day.** Which delta did you miss? Was the data there at 11:30? Was it a data-quality issue? Write it as a feature contract (module 4) if it was a missing variable.
4. **Live, once Phase 4 exists.** One ticket a day, committed before cutoff. After 30 days, compare your forward record with the backtest on the same model.

## 5. What good looks like

- Every trade was written before gate closure, with the inputs and their knowledge times.
- Results are after costs, and compared with naive and perfect foresight.
- Bad days are traced back to data, drivers or features — the loop in the [track overview](README.md) closes.
- You would be comfortable showing the full ticket history to a BRP, a fund, or an employer.

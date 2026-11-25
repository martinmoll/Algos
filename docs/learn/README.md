# Learning track — from a price to a trade, end to end

This section is for the project owner, not for agents. Its job is to build your own end-to-end understanding of Nordic power trading, so that you can judge every model and every result in this repo yourself: what moves the price, how good the data is, which variables explain the move, what a good forecast looks like, and how a forecast becomes a trade.

The repo's plan docs (`docs/plan/`) say *what the system does*. This track says *what you should understand and be able to do*, in order, with exercises run against the real data in this repo.

## The one idea behind the order

**Good data and good features beat clever models.** In electricity price forecasting a well-specified linear model on clean, point-in-time features is the standard benchmark that most complex models struggle to beat clearly (Lago et al. 2021, plan 04 §1). Most of the skill is upstream of the model:

```
  data quality  →  explanatory variables  →  features (deltas, ratios, regimes)  →  simple model  →  evaluation  →  trade
   (module 2)          (module 3)                 (module 4)                        (module 5)      (module 5)     (module 6)
       ▲                                                                                                             │
       └──────────────────────────  every surprise in a result is traced back here first  ─────────────────────────┘
```

So modules 2–4 are the core, and the models come after (D-034).

## Modules

| # | Module | You can… when done | Time |
|---|---|---|---|
| 1 | [Price formation](01-price-formation.md) | Explain tomorrow's DK1 and NO2 prices from residual load, hydro, interconnectors and the merit order, on a whiteboard | 1 week |
| 2 | [Data quality first](02-data-quality.md) | Tell clean data from broken data, and explain knowledge time vs event time without looking it up | 1 week |
| 3 | [Drivers and deltas](03-drivers-and-deltas.md) | Name the explanatory variables per zone, their sign and rough size, and explain why the *change* (delta) matters more than the level | 2 weeks |
| 4 | [Feature engineering](04-feature-engineering.md) | Turn a raw variable into a feature that is legal at 11:30 CET, and test whether it helps | 2 weeks |
| 5 | [Models and what good looks like](05-models-and-evaluation.md) | Read a run record and say whether a model is good, lucky or leaking | 1 week |
| 6 | [From forecast to trade](06-forecast-to-trade.md) | Write a trade ticket for tomorrow's day-ahead, commit it before gate closure, and settle it honestly | ongoing |

Time is a guide at a few hours per week. Do the modules in order; module 6 becomes a daily habit once Phase 4 (live paper loop) exists, and can start by hand before that.

## Rules that apply to you too

The no-look-ahead contract ([plan 03](../plan/03-no-lookahead.md)) binds exploration as much as code:

- **Explore through the store.** Use `Store("data").as_of(t).read(...)` in a notebook, not files under `data/`. It is slower to type and it is the point: you learn to ask "what did I know at `t`?".
- **The vault is sealed for you as well.** Delivery days from 2025-11-16 are off limits for exploration and plots ([configs/vault.toml](../../configs/vault.toml), D-031). Every chart you look at before a vault opening is a chart that biases the opening. Exercises here use 2023 – mid-2025.
- **Write down what you expect before you look.** One line in your journal ("I expect DK1 to be higher than SE3 on windless winter evenings") before running the query. This is how intuition becomes testable, and how you notice when a result is too good.

## Your journal

Keep a running file at `docs/learn/journal.md` (create it when you start). One dated entry per session: what you expected, what you saw, what surprised you, what you now believe. Surprises are the most valuable lines — they become questions for the decision log or features for the model.

## What good looks like — the checklist you are building toward

By the end you should be able to answer each of these from memory, then check against the repo:

- [ ] What were the knowledge times of each input to yesterday's forecast, and which one was the latest?
- [ ] Which zone-days in the last month failed a quality check, and why?
- [ ] For DK1, NO2, SE3: the three variables that move the price most, with sign and an order of magnitude in EUR/MWh.
- [ ] Why the day-over-day *change* in residual load explains more of the price change than its level.
- [ ] What rMAE the naive forecast gets (1.00 by construction), what a good model gets on our data, and which run id says so.
- [ ] Whether a given improvement is significant (Diebold–Mariano) or noise.
- [ ] What a trade on tomorrow's DK1–DE spread would have to clear in costs to be worth doing.
- [ ] What would make you distrust a backtest that looks great.

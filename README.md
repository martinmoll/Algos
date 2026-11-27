# EnergyTrading

Algorithmic and machine-learning trading research for the Nordic power markets — Norway, Sweden, Denmark and Finland (12 bidding zones) — built around one rule: **no look-ahead, ever**.

Status: Phase 0 in progress — walking skeleton (naive DK1/DK2 day-ahead backtest) works end to end.

## Setup

Needs [uv](https://docs.astral.sh/uv/). On a clean machine:

```sh
uv sync                      # installs Python 3.12 and all dependencies into .venv
uv run python check.py       # lint, format check, type check, tests
```

## Run

```sh
uv run nordpower ingest elspotprices --start 2025-09-01 --end 2025-09-21   # raw snapshot
uv run nordpower curate                                                    # -> as-of store
uv run nordpower backtest --start 2025-09-08 --end 2025-09-21              # sealed run record in data/runs/
uv run nordpower runs                                                      # registry: every run, trials per family
```

Dates are delivery days. Data lives in `data/` (git-ignored). Energi Data Service rate-limits `Elspotprices` to about one request per 5 minutes; ingest waits automatically.

## Learning track

[docs/learn/](docs/learn/README.md) — a self-study path for the project owner: price formation → data quality → drivers and deltas → feature engineering → models → a paper trade. Data quality and features come before models (D-034).

## Read in this order

1. [Open questions](docs/OPEN-QUESTIONS.md) — decisions waiting for you, each with a default
2. [Decision log](docs/DECISIONS.md) — what was decided and why
3. Plan
   - [01 Markets and strategies](docs/plan/01-markets-and-strategies.md)
   - [02 Data](docs/plan/02-data.md)
   - [03 No-look-ahead contract](docs/plan/03-no-lookahead.md)
   - [04 Models](docs/plan/04-models.md)
   - [05 Backtesting and evaluation](docs/plan/05-backtesting.md)
   - [06 Architecture and repository layout](docs/plan/06-architecture.md)
   - [07 Dashboard](docs/plan/07-dashboard.md)
   - [08 Roadmap](docs/plan/08-roadmap.md)
   - [09 TSO methods](docs/plan/09-tso-methods.md)
   - [10 Weather and satellite data](docs/plan/10-weather-and-satellite.md)
4. [References](docs/research/references.md)
5. [Glossary](GLOSSARY.md) · [Agent rules](CLAUDE.md)

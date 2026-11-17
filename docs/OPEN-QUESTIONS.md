# Open questions for the user

Decisions only you can make. Each has a recommended answer that the plan currently assumes ("yes" accepts it). Answer in any form; the result goes into [DECISIONS.md](DECISIONS.md).

---

❓ **Q1 — Route to market.** Physical Nordic markets (day-ahead, intraday, balancing) require Nord Pool/EPEX membership plus balance responsibility (being a BRP or contracting one); futures need a clearing-member relationship. Do you have, or intend to get, any of: (a) an employer/company with market access, (b) a BRP partnership, (c) futures access via a broker, (d) none — research and track record first?

➡️ Assume (d): build the tamper-evident paper-trading record first and decide on real access when Phase 5 has verdicts. (D-003)

---

❓ **Q2 — Capital and risk scale.** What size are we designing for (order of magnitude in MW or EUR at risk)? It sets price-impact assumptions, whether fixed membership fees can ever be recovered, and position limits.

➡️ Assume small price-taker (≤ 1–5 MW per MTU, no market impact), revisited at Q1.

---

❓ **Q3 — API registrations (10 minutes of your time, blocks Phase 1).** Will you register for: ENTSO-E Transparency Platform (then email <transparency@entsoe.eu> asking for RESTful API access; token takes up to 3 working days), Fingrid Open Data key, Nord Pool REMIT UMM account? Put the tokens in `.env`.

➡️ Yes — ENTSO-E first; it is the backbone and has the longest lead time.

**Status 2026-11-17:** ENTSO-E account registered and API access email sent; awaiting approval (up to 3 working days). Then generate the token under My Account Settings and put it in `.env` as `ENTSOE_API_TOKEN`. Fingrid key and UMM registration still open.

---

❓ **Q4 — Data budget.** Intraday prices (trades, order book, IDA) and futures/EPAD settlements are paid data (Nord Pool products roughly €1.7–4k+/year each; Euronext separately). Without them, strategies S3 (intraday) and S4 (futures) can only start from self-collected forward data.

➡️ €0 for now. Revisit when the day-ahead benchmark exists and we know whether S3/S4 are worth paying for.

---

❓ **Q5 — Commercial intent.** Is this personal research, or meant to become a business/fund? It determines whether research-only licences (Open-Meteo free tier, Energy-Charts) are acceptable long-term and whether REMIT/market-conduct obligations need early attention.

➡️ Personal research now; licences and regulatory review become a gate before any real-money trading. (D-017)

---

❓ **Q6 — Always-on collector host.** Forecast vintages can only be captured live. Is there a machine that is always on (home server, NAS, Raspberry Pi), or should we use a small cloud VPS (~€5/month)?

➡️ Small VPS running collectors only, nightly sync to this PC. Until then collectors run here when the PC is on and gaps are recorded.

---

❓ **Q7 — Vault size.** Sealing the last 12 months (2025-11-16 → 2026-11-16) gives a strong final test in the current market design but locks away almost all 15-minute day-ahead data from research. Alternative: seal 6 months.

➡️ Keep 12 months. (D-014)

---

❓ **Q8 — Your edge.** You said you would bring your own intuition. Which of these do you know best: hydrology/reservoir dynamics, wind/weather, grid and flow-based constraints, a specific zone, balancing operations, futures? That is where the structural-model track (M8) and feature work should start.

➡️ No assumption made; default priority is hydro balance + wind + nuclear availability for NO2/SE3/DK1.

---

❓ **Q9 — Compute.** Is there a GPU on this PC or a cloud budget? Affects DNN/foundation-model cadence only; LEAR and LightGBM run fine on CPU.

➡️ Assume CPU-only; deep models retrain monthly.

---

❓ **Q10 — Remote and commits.** Nothing has been committed. May agents commit to this repo routinely, and should there be a private GitHub remote (needed for CI and for externally timestamping the paper-trading chain)?

➡️ Yes to both: private GitHub repo, agents commit on feature branches.

---

❓ **Q11 — Stack sign-off.** Python 3.12 + uv + Polars + DuckDB/Parquet + LightGBM/PyTorch + Streamlit, no orchestrator or MLflow initially. (D-010 – D-012)

➡️ Yes.

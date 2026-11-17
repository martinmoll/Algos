# References

Research performed 2026-11-16. **Verified** = found and read (at least the abstract/summary or a live API response) in that session. **From memory** = well-known work cited from the model's training knowledge; confirm details (year, venue, exact claim) before relying on them.

## Market structure (verified)

- SDAC 15-minute MTU: trading day 30 Sep 2025, delivery day 1 Oct 2025, all bidding zones in one switch — [Nord Pool 15-min MTU transition](https://www.nordpoolgroup.com/en/trading/transition-to-15-minute-market-time-unit-mtu/), [MCSC confirmation (OTE)](https://www.ote-cr.cz/en/about-ote/ote-news/market-coupling-steering-committee-confirms-go-live-of-15-minute-mtu-in-sdac-on-trading-day-30-september-2025-for-delivery-day-1-october-2025)
- Nordic flow-based go-live 29 Oct 2024; Nordic SIDC 15-min 18 Mar 2025; Baltic SIDC 15-min 16 Dec 2024 — [Nord Pool newsletter Oct 2024](https://nordpoolgroup.com/en/message-center-container/newsroom/newsletter/2024/10)
- Nordic mFRR EAM go-live 4 Mar 2025 — [eSett mFRR EAM](https://www.esett.com/mfrr-eam), [postponement notice](https://www.esett.com/news/postponement-of-nordic-mfrr-energy-activation-market-mfrr-eam-go-live/); post-launch volatility and negative imbalance prices — [eSett Nordic Electricity Market Q2 2025](https://www.esett.com/news/nordic-electricity-market-q2-2025/)
- eSett open data at 15-min resolution from 22 May 2023 — [eSett: changes in open data due to 15-minute ISP](https://esett.com/news/changes-in-open-data-due-to-introduction-of-15-minute-isp)
- Euronext Nord Pool Power Futures fully operational 16 Mar 2026 (system price futures + EPADs, migrated from Nasdaq Clearing) — [Euronext press release](https://www.euronext.com/en/investor-relations/financial-information/news/euronext-successfully-launches-euronext-nord-pool), [Nord Pool page](https://www.nordpoolgroup.com/en/trading/euronext-nord-pool-power-futures-market/)
- Nord Pool membership, BRP requirement, fees — [General terms 2025](https://www.nordpoolgroup.com/49184b/globalassets/download-center/rules-and-regulations/nord-pool-general-terms-17.02.2025.pdf), [Fee schedule 2026](https://www.nordpoolgroup.com/4a7ad8/globalassets/trading-and-services/nord-pool-fee-schedule-2026-nordic-and-baltic-market.pdf), [API page](https://www.nordpoolgroup.com/en/api/)

- Single price / single position imbalance model live 1 Nov 2021 — [eSett confirmation](https://www.esett.com/news/confirmation-of-go-live-of-single-price-and-single-balance-on-1-11-2021/), [Fingrid](https://www.fingrid.fi/en/news/news/2021/single-price-single-position-implemented-on-1-november-in-the-nordic-countries/)
- SIDC intraday auctions live 13 June 2024; gate closures 15:00 D-1, 22:00 D-1, 10:00 D — [ENTSO-E IDA page](https://entsoe.eu/network_codes/cacm/implementation/ida), [Nord Pool support](https://support.nordpoolgroup.com/support/solutions/articles/8000111575-about-the-intraday-auctions-idas-), [NEMO Committee](https://www.nemo-committee.eu/ida)
- BRP balance obligation — [NBS Handbook v5.2](https://www.esett.com/app/uploads/2025/10/NBS-Handbook-v5.2.pdf); Fingrid bars systematic use of open deliveries — [Fingrid balance management terms](https://www.fingrid.fi/globalassets/dokumentit/fi/sahkomarkkinat/tasesahko/valid-from-1.10.2025-appendix-1-part-1-general-terms-and-conditions-concerning-balance-management.pdf)

## Data sources (verified)

- ENTSO-E Transparency Platform API: 400 requests/min per token — [API rate limits](https://transparencyplatform.zendesk.com/hc/en-us/articles/12783148966036-API-Rate-Limit-Part-1); token by registration + email — [API guide](https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html); client [entsoe-py](https://github.com/EnergieID/entsoe-py)
- Energi Data Service — [DayAheadPrices metadata](https://api.energidataservice.dk/meta/dataset/DayAheadPrices) (15-min, from 2025-10-01, DK1/DK2/DE/NO2/SE3/SE4), [Elspotprices](https://api.energidataservice.dk/meta/dataset/Elspotprices) (discontinued after 2025-09-30). Live calls confirmed: no key needed; `Elspotprices` starts 1999-07-01 and includes `SYS`; `Forecasts_Hour` has `TimestampUTC` and DayAhead/Intraday/5Hour/1Hour/Current columns.
- eSett — [Open Data blog](https://www.esett.com/blog/open-data-unlocking-transparency-for-energy-markets/), [eSett API](https://www.esett.com/esett-api/). Host `api.opendata.esett.com` responds; **endpoint paths not confirmed**.
- NVE Magasinstatistikk — [Swagger](https://biapi.nve.no/magasinstatistikk/swagger). Live call to `/api/Magasinstatistikk/HentOffentligDataSisteUke` confirmed: per `EL` area (NO1–NO5), `fyllingsgrad`, `kapasitet_TWh`, and `neste_Publiseringsdato` (Wednesday 13:00).
- Open-Meteo — [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api) (lead offsets day 1–7, most models from Jan 2024; ECMWF, ICON, GFS, MET Norway Nordic), [Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api), [Single Runs API](https://open-meteo.com/en/docs/single-runs-api). Live call confirmed. Free tier non-commercial.
- JAO — [Nordic Publication Tool handbook](https://publicationtool.jao.eu/nordic/Nordic_PublicationHandbook). `publicationtool.jao.eu/nordic/api/data/maxNetPos` works without a key and returns per-zone min/max net positions with a `lastModifiedOn` timestamp.
- Fingrid — [Open data](https://data.fingrid.fi/en), [instructions](https://data.fingrid.fi/en/instructions): `x-api-key`, 10,000 requests/24 h, CC BY 4.0. (401 without key, confirmed.)
- Nord Pool REMIT UMM — [UMM service](https://nordpoolgroup.com/en/services/compliance/umm): free API for registered users, RSS; TSO outages via NUCS.
- Energy-Charts API — [api.energy-charts.info](https://api.energy-charts.info/). Live call: price responses carry "private and internal use only" licence text.
- Nord Pool data — [Data services general terms](https://www.nordpoolgroup.com/498e4c/globalassets/download-center/power-data-services/general-terms-data-services-data.pdf), [day-ahead data products](https://www.nordpoolgroup.com/en/services/power-market-data-services/day-ahead-market-data/); historical data removed from the public site Jan 2022 — [operational message](https://nordpoolgroup.com/en/trading/Operational-Message-List/2022/01/new-data-portal-for-2022-20220114124600).

## Forecasting literature (verified)

- Lago, Marcjasz, De Schutter, Weron (2021). *Forecasting day-ahead electricity prices: A review of state-of-the-art algorithms, best practices and an open-access benchmark.* Applied Energy 293, 116983. [arXiv:2008.08004](https://arxiv.org/abs/2008.08004). Code: [epftoolbox](https://github.com/jeslago/epftoolbox) (LEAR, DNN, DM and GW tests, Nord Pool benchmark dataset).
- Marcjasz, Narajewski, Weron, Ziel (2023). *Distributional neural networks for electricity price forecasting.* Energy Economics 125, 106843. [arXiv:2207.02832](https://arxiv.org/abs/2207.02832).
- *On-line conformalized neural networks ensembles for probabilistic forecasting of day-ahead electricity prices* (2024) — authors not confirmed in session (from memory: Brusaferri et al.).
- Maciejowska, Uniejewski, Weron — forecasting electricity prices (review chapter). [arXiv:2204.11735](https://arxiv.org/abs/2204.11735).
- Maciejowska, Serafin, Uniejewski. *Probabilistic forecasting with a hybrid Factor-QRA approach: Application to electricity trading.* [arXiv:2303.08565](https://arxiv.org/abs/2303.08565).
- Serafin, Weron. *Loss functions in regression models: impact on profits and risk in day-ahead electricity trading.* [WORMS 24/03](https://worms.pwr.edu.pl/RePEc/ahh/wpaper/WORMS_24_03.pdf).
- Lipiecki, Uniejewski, Weron. Postprocessing of point predictions for probabilistic forecasting of day-ahead prices (cites up to ~20% profit gains from probabilistic forecasts). [arXiv:2404.02270](https://arxiv.org/abs/2404.02270).
- Day-ahead trading strategy with storage, no balancing leg. [arXiv:2302.00411](https://arxiv.org/abs/2302.00411).
- Hornek et al. (2025). *Benchmarking Pre-Trained Time Series Models for Electricity Price Forecasting.* [arXiv:2506.08113](https://arxiv.org/abs/2506.08113). Plus a 2025 Belgian DA + imbalance study with Chronos-2/TimesFM 2.5 vs LEAR/DNN (title seen via secondary summary only).
- mFRR activation price forecasting, Norway, XGBoost vs explainable boosting (2026). [arXiv:2602.00049](https://arxiv.org/abs/2602.00049).
- SINTEF (EEM 2023). *Predictions of prices and volumes in the Nordic balancing markets for electricity.* [SINTEF Open](https://sintef.brage.unit.no/sintef-xmlui/handle/11250/3085067).
- Aalborg University thesis (2025), LSTM for Danish imbalance price, cointegration with spot. [AAU](https://projekter.aau.dk/projekter/files/784574069/P10_Jysk_Energi.pdf).

## From memory — confirm before relying on

- Weron (2014). Electricity price forecasting: a review of the state-of-the-art with a look into the future. *Int. J. Forecasting.*
- Nowotarski & Weron (2018). Recent advances in electricity price forecasting: a review of probabilistic forecasting. *Renewable and Sustainable Energy Reviews.*
- Ziel & Weron (2018). Day-ahead electricity price forecasting with high-dimensional structures: univariate vs. multivariate modeling frameworks. *Energy Economics.*
- Uniejewski, Weron, Ziel (2018). Variance stabilizing transformations for electricity spot price forecasting. *IEEE Trans. Power Systems.*
- Hubicka, Marcjasz, Weron (2019). A note on averaging day-ahead electricity price forecasts across calibration windows. *IEEE Trans. Sustainable Energy.*
- Uniejewski & Weron (2021). Regularized quantile regression averaging for probabilistic electricity price forecasting. *Energy Economics.*
- Narajewski & Ziel (2020). Econometric modelling and forecasting of intraday electricity prices. *J. Commodity Markets.*
- Kath & Ziel (2021). Conformal prediction interval estimation and applications to day-ahead and intraday power markets. *Int. J. Forecasting.*
- Diebold & Mariano (1995); Giacomini & White (2006); Gneiting & Raftery (2007, proper scoring rules).
- Bailey & López de Prado (2014). The Deflated Sharpe Ratio. *J. Portfolio Management.*
- Bailey, Borwein, López de Prado, Zhu (2017). The probability of backtest overfitting. *J. Computational Finance.*
- López de Prado (2018). *Advances in Financial Machine Learning* (purged K-fold, embargo, trial accounting).
- Harvey, Liu, Zhu (2016). …and the Cross-Section of Expected Returns. White (2000) Reality Check; Hansen (2005) SPA test.
- Market facts not verified in session: Baltic synchronisation Feb 2025; Olkiluoto 3 regular operation 2023; harmonised DA price limits; intraday continuous gate closure per zone.

## Research still owed

- Exact eSett Open Data endpoints and correction windows.
- Whether ENTSO-E carries intraday auction (IDA) prices for Nordic zones, and from when.
- Statnett and Svenska kraftnät wording on deliberate imbalance positions (Fingrid's is verified).
- Free/cheap sources for TTF, EUA, and Nordic futures settlements.
- MET Norway MEPS forecast archive (thredds) depth and access pattern.
- Current Nord Pool fee schedule numbers for the cost model.
- Hydrology data for Sweden/Finland (inflow, snow).

# Nordic Power Trading

Research and trading of Nordic wholesale electricity under a strict point-in-time discipline. This glossary fixes the words; plans and decisions live in `docs/`.

## Language

### Market

**Bidding zone**:
A geographic area with a single wholesale electricity price per market time unit (NO1–NO5, SE1–SE4, DK1, DK2, FI).
_Avoid_: Price area, region, market area

**Market time unit (MTU)**:
The period a market price applies to; 15 minutes in day-ahead since delivery day 2025-10-01, 60 minutes before.
_Avoid_: Interval, slot, period, hour (unless it really is an hour)

**Era**:
The span of delivery days sharing one day-ahead MTU: the hourly era (to 2025-09-30) and the 15-minute era (from 2025-10-01). Backtest metrics are reported per era.
_Avoid_: Regime (the regime calendar lists every market-design change; an era is defined by the MTU alone)

**Zone-day**:
One bidding zone on one delivery day; the unit that data-quality checks pass or fail.
_Avoid_: Day (when the zone matters)

**Quality record**:
The data-quality result for one raw snapshot: which checks failed for which zone-days.
_Avoid_: Quality flag, data health status

**Delivery day**:
The 24-hour local-time (CET/CEST) day in which electricity is delivered; has 23 or 25 hours on DST changes.
_Avoid_: Trading day (that is the day the auction runs), date

**Day-ahead price**:
The clearing price of the single day-ahead coupling auction for one bidding zone and MTU.
_Avoid_: Spot price, Elspot, system price

**System price**:
Nord Pool's unconstrained reference price for the whole Nordic area, the underlying of Nordic power futures.
_Avoid_: Nordic price, spot

**EPAD**:
A futures contract on the difference between a bidding zone's day-ahead price and the system price.
_Avoid_: Area contract, CfD

**Gate closure**:
The instant after which orders for a given market are no longer accepted.
_Avoid_: Deadline, cutoff (cutoff is ours — see Decision cutoff)

**Imbalance price**:
The price at which a balance responsible party's deviation from its plan is settled for one imbalance settlement period.
_Avoid_: Balancing price, regulation price (a different thing: the mFRR activation price)

**Imbalance settlement period (ISP)**:
The period over which imbalances are measured and settled; 15 minutes in the Nordics since 2023-05-22.

**Balance responsible party (BRP)**:
A company financially responsible to the TSO for imbalances; required, directly or by contract, to trade physical power.

**Flow-based domain**:
The set of linear constraints (PTDFs and remaining available margins on critical network elements) limiting zone net positions in the day-ahead auction, used in the Nordics since 2024-10-29.
_Avoid_: Capacities, NTC (the earlier, different method)

**Urgent market message (UMM)**:
A REMIT disclosure of an outage or other inside information, with a publication time and versions.

**Clock hour**:
The hour shown on the local wall clock (00–23); the repeated autumn hour has the same clock hour twice and the spring DST day has no 02.
_Avoid_: Local hour, hour number, hour index

**Reference day**:
The past delivery day whose prices the naive forecast repeats: the same weekday a week earlier for Monday, Saturday and Sunday, the day before otherwise.
_Avoid_: Lag day, source day

**Residual load**:
Demand minus wind, solar and other must-run generation; what dispatchable plants must cover.
_Avoid_: Net load, net demand

**Water value**:
The opportunity cost of using stored hydro water now rather than later; the marginal cost of reservoir hydro.
_Avoid_: Hydro cost, fuel cost

**Delta**:
The difference between a driver's value for the target period and its value in a comparison: the reference day, an earlier forecast vintage, or a seasonal normal. Features are stated as deltas where the naive forecast already carries the level (D-034).
_Avoid_: Diff; say what the comparison is (vs reference day, vs earlier vintage, vs normal)

**Forecast revision**:
A delta between two vintages of the same forecast for the same event time, e.g. the latest wind forecast minus the day-ahead vintage.
_Avoid_: Update, forecast change

**TSO forecast error**:
A TSO's published forecast minus the realised value for the same event time; studied to find systematic weaknesses (plan 09). The realised side is only ever a lagged input.

**Replica**:
Our recomputation of a published TSO value (imbalance price, flow-based RAM) from its published inputs, as of the TSO's own decision time.
_Avoid_: Clone, simulation

**Clear-sky index**:
Forecast or observed irradiance divided by the irradiance under a cloudless sky at the same place and time; isolates the effect of clouds.

**Nowcasting**:
Forecasting the next 0–6 hours from the latest observations (e.g. satellite cloud motion) rather than from a weather-model run. Not a day-ahead input.

### Point-in-time discipline

**Event time**:
The start of the period a value describes.
_Avoid_: Timestamp, date, valid time (reserve *valid time* for weather forecasts)

**Knowledge time**:
The earliest instant a value was knowable to a market participant.
_Avoid_: Publication time (only one way of establishing it), as-of date, created-at

**Knowledge-time grade**:
How a knowledge time was established: *observed* (we snapshotted it live), *published* (the source states it), or *assumed* (derived from a publication rule for backfilled data).

**Vintage**:
One version of a value for a given event time, distinguished by its knowledge time.
_Avoid_: Revision, version, snapshot (a snapshot is a whole download)

**Knowledge view**:
The data as it was knowable at one instant: for each event time, the latest vintage not later than that instant.
_Avoid_: Snapshot, as-of table, dataset

**Decision time**:
An instant at which a strategy is allowed to act, using only the knowledge view at that instant.

**Decision cutoff**:
The decision time used for an auction, deliberately earlier than gate closure.

**Look-ahead**:
Any dependence of a decision, model fit or selection on information with knowledge time after the decision time.
_Avoid_: Leakage (use only for the broader ML sense), peeking

**Publication rule**:
The reviewed, per-dataset rule that assigns an assumed knowledge time to backfilled values.

**Regime calendar**:
The dated list of market-design changes that models and evaluations must treat as structural breaks.

### Research protocol

**Run**:
One recorded execution of a backtest or evaluation, immutable and identified by a run id.
_Avoid_: Experiment (that is a pre-registered question that may have many runs), job

**Trial**:
A run counted toward multiple-testing statistics for its strategy family; every run is a trial.

**Vault**:
The sealed period of recent history that research code cannot read, reserved for single final evaluations.
_Avoid_: Holdout, test set (ambiguous with walk-forward test blocks)

**Vault opening**:
One deliberate, logged decision to read the vault, citing the decision-log entry that pre-registers the configuration being evaluated. Openings are counted; one opening may cover a whole evaluation.
_Avoid_: Vault access, peek

**Walk-forward**:
Evaluation in which a model is repeatedly fit on data known up to a decision time and scored on the periods that follow.
_Avoid_: Cross-validation, backtest (the broader activity)

**Forward record**:
Performance on decisions committed live before their outcomes existed.
_Avoid_: Live results (implies real money), out-of-sample (ambiguous)

**Commitment**:
A hash-chained, externally timestamped record of forecasts and orders made before gate closure.

**Naive forecast**:
The reference forecast that repeats a recent day's prices; the denominator of rMAE.
_Avoid_: Baseline (reserve for any comparison model)

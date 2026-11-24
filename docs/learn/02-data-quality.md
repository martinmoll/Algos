# Module 2 — Data quality first

Goal: never trust a number you have not checked, and know exactly *when* each number was knowable.

Most bad results in power forecasting are data bugs: a missing hour on a DST day, a time zone shifted by one, a forecast that was silently revised, a wind series that includes curtailment. A model fitted on bad data learns the bug. A model fitted on data from the future learns the answer. Both look like skill.

## 1. Two times on every value

| Time | Question | Example |
|---|---|---|
| **Event time** | What period does this value describe? | DK1 price for 2024-03-14 18:00–18:15 |
| **Knowledge time** | When could a market participant first know it? | 2024-03-13 ≈ 12:45 CET (auction results) |

A forecast for tomorrow's wind also has an event time (tomorrow 18:00) and a knowledge time (when the run was published). Using a value whose knowledge time is after your decision time is look-ahead. The store enforces this: `store.as_of(t)` only returns rows with `knowledge_time <= t`. Read [plan 03](../plan/03-no-lookahead.md) once fully; it is the most important document in the repo.

## 2. The quality dimensions

| Dimension | Question | How the repo checks it | Status |
|---|---|---|---|
| Completeness | Are all MTUs present? (24 h, 23/25 on DST days; 96, 92/100 quarter-hours) | `quality.py` completeness check per zone-day (D-033) | ✅ built for `da_price` |
| Uniqueness | Any duplicate event times in one snapshot? | duplicate check (D-033) | ✅ built |
| Validity | Is every value within physical/market limits? | range check against SDAC limits −500/+4000 EUR/MWh | ✅ built |
| Consistency | Do two sources agree? (ENTSO-E vs Energi Data Service prices) | cross-source reconciliation | not yet |
| Timeliness | Was it available at the decision time? | knowledge time, publication rules | ✅ in the store |
| Stability | Has it been revised since? By how much? | revision counting across snapshots | not yet |
| Plausibility | Is it believable in context? (wind output above installed capacity; solar at night) | domain checks per dataset | not yet |
| Units and time zone | MW vs MWh, EUR vs DKK, UTC vs local | ingest code; `timeutil` is the only place for time zones | ✅ by design |

## 3. Exercises

1. **Read a quality record.** After `nordpower curate`, open a file in `data/quality/da_price/`. Which checks ran? Which failed? Explain each failure in one line.
2. **Break it on purpose.** In the fixtures under `tests/fixtures/`, find a DST day. Count the MTUs by hand. Then read `tests/test_quality.py` and find the test that would catch a missing hour.
3. **Find the leak.** For each of these, write whether it leaks and why:
   - joining NVE reservoir level on its week number;
   - using actual wind generation for tomorrow as a feature;
   - standardising prices with the mean of the full dataset;
   - using the ENTSO-E load forecast downloaded today for a 2023 backtest.
   Check your answers against plan 03 §4 and the leak list.
4. **Revision hunt (when ENTSO-E ingest exists).** Download the same week of a forecast dataset twice, a week apart. Diff. How many values changed and by how much? This number is how wrong a backfilled history can be.
5. **Write one new check.** Pick a plausibility rule (e.g. "a zone's wind output never exceeds its installed capacity as of that day"). Write it in your journal as: dataset, rule, threshold, what a failure would mean. Good ones go to an issue.

## 4. What good looks like

- Every dataset you use has a quality record, and you have looked at the failures.
- You can say, for any feature, its knowledge-time grade: *observed*, *published* or *assumed*.
- Results are reported separately for observed-vintage and assumed-vintage periods.
- When something in a backtest surprises you, your first move is to check the data, not to tune the model.

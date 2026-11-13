# Analyses added after the results

Written after the declared results in `results/summary.json` were seen, and committed before any of these was run.
None of them replaces a declared result; each is reported on the page as "added after the results".

What the declared results showed: the fixed default weights were the closest arm in 6 of 8 quarters and always
over-forecast; weights learned for the same rule under-forecast by about 60%; time in stage under-forecast by about
28% point in time and by about 11% with every award known; no arm's 80% interval covered the actual more than once.

1. **Where the wins come from.** For each scored quarter, the pipeline wins split by where the deal's expected close
   date sat at the snapshot: inside the quarter, before it (past due), after it. And, for deals in each stage at the
   snapshot, the share ever won by the cutoff and the share won inside the quarter, beside the default weights.
2. **Late-recording correction.** Time in stage and run rate with each history label divided by the share of wins
   that would already have been published by the snapshot. That share comes, point in time, from wins awarded 365 to
   730 days before the snapshot and published before it: for a history quarter, the average over its days t of the
   share of those wins published within S minus t days of award. Nothing published after S is used.
3. **Intervals from past misses.** For each scored quarter with at least 3 earlier scored quarters, an 80% interval
   from the 10th and 90th percentiles of the earlier quarters' percentage errors of the same arm, applied to the
   forecast. Coverage reported over those quarters.
4. **Capacity plan from the forecast.** The corrected time-in-stage forecast for the main quarter turned into contract
   starts per month with the go-live lags (62% start on the award day), and onboarding hours from a declared
   assumption of hours per start, shown over a range.

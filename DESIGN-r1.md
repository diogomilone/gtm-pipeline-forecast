# GTM pipeline forecast: design, round 1

Committed before any forecast is computed or scored. The frozen parameters are in `protocol-r1.json` and the
predictions in `predictions-r1.json`; where this file and the JSON differ, the JSON wins. Any later change is a
labelled change to the protocol, committed before it is used, and a change made after results are seen says so.

What was seen before this design: a profile of the two source files (row counts, status counts, the share of closed
tenders that match an award notice, about 40% overall, the spread of days from closing to award, from award to
contract start and from award to its publication, and the share of award amounts that are missing). No forecast had
been built or scored. The lag figures from that profile are reported as description, never as predictions.

## Question

A sales team forecasts the quarter from its open pipeline: each open deal times a stage probability. How far off is
that forecast when the probabilities are a CRM's defaults, when they are learned from history, and when they depend on
how long a deal has sat in its stage? And once a deal is signed, how long until the contract starts?

## Overlap test (one question, one study)

`marketplace-revenue-forecast` forecasts a monthly revenue total from its drivers (trips, price) on a time series; it
has no deals, no stages and no pipeline. `arr-reconciliation` reconciles one ARR number across billing and CRM on
synthetic data; it forecasts nothing. This study forecasts wins from a pipeline of individual opportunities with dated
stages and scores the forecast against what closed. Different question and different data, so it is a new study.

## Data (open)

CanadaBuys open data, Government of Canada, Open Government Licence - Canada:
- tender notices, all published on CanadaBuys since 2022-08-08 (`tenderNoticeComplete-avisAppelOffresComplet.csv`);
- award notices since 2022-08-08 (`awardNoticeComplete-avisAttributionComplet.csv`).
Files are downloaded by `tools/get_data.py`, hashed, and reduced at load to the fields in the protocol. Contact names,
emails and phone numbers are never loaded.

Stand-in: a tender is an opportunity, the buying department is the account, the notice type is the channel, the
award is the signed deal, the contract start is go-live. A supplier that sells to government watches exactly this
pipeline; a software company's sales team runs the same arithmetic on its CRM.

## Opportunity table (CRM-shaped)

One row per solicitation number (reference number when it is blank), excluding Requests for Information:
`opportunity_id, account (department), channel (notice type group), category, created_at (first publication),
bid_close_at (latest closing date), expected_start (latest expected contract start), cancelled_at (amendment date of
a cancelled notice), won_at (earliest award date of an original award notice on or after created_at),
won_known_at (earliest publication date of those award notices), amount (sum of positive award amounts, missing when
none is above 1), go_live_at (earliest contract start)`.

Stage at a snapshot date S, using only what was published before S:
- not yet created: created_at >= S (out of the pipeline);
- closed won: won_known_at < S; closed lost: cancelled_at < S (both out of the pipeline);
- open for bids: created_at < S <= bid_close_at;
- bids closed, awaiting award: bid_close_at < S, not closed.
Days in stage: since created_at (open for bids) or since bid_close_at (awaiting award).

## Target

For each snapshot S (a quarter start), the number of opportunities in the pipeline at S whose won_at falls in
[S, next quarter start), counted with every award published up to the data cutoff. Also reported: all awards in the
quarter, so the share coming from opportunities created after S is visible.

Scored quarters: snapshots from 2023-10-01 to 2025-07-01 (8). The latest scored quarter ends more than 13 months
before the cutoff, because a quarter of awards are published 90 or more days late. The main run is the snapshot
2025-07-01; the follow-up is the backtest over all 8.

## Forecasts compared (declared)

1. **Fixed stage weights (the CRM default).** HubSpot's default deal pipeline probabilities: open for bids at 60%
   (its "Presentation scheduled"), awaiting award at 80% ("Decision maker bought-in"). A deal counts in the quarter when
   its expected close date falls in the quarter: the expected contract start when given, otherwise the bid closing
   date. Range shown: 40/60 and 80/90.
2. **Learned stage weights.** Same date rule. Each stage's weight is the share of past deals in that stage with an
   expected close date in the quarter that were won within the quarter, pooled over the 4 previous snapshots, counting
   only awards published before S.
3. **Time in stage.** No date rule: every deal in the pipeline counts. Its weight is the share of past deals in the
   same stage and the same days-in-stage band (0-14, 15-30, 31-60, 61-120, 121-365, over 365) that were won within the
   quarter after their snapshot, pooled over the 4 previous snapshots, counting only awards published before S.
4. **Run rate (baseline).** The previous quarter's count of pipeline wins, as known at S.

Leakage contrast (declared): arms 2 to 4 recomputed with every award published up to the cutoff, which a backtest
that ignores publication dates would use. Reported beside the honest arms, never as a result a team could have had.

Intervals: arms 1 to 3 give an 80% interval from the sum of independent Bernoulli deals (normal approximation,
plus or minus 1.2816 standard deviations).

Scores: signed error and absolute percentage error per quarter; over the backtest, the mean absolute percentage error
(MAPE), the mean signed percentage error (bias) and the 80% interval's coverage (quarters of 8).

## Description (not predictions)

- Award to contract start (go-live): median, quartiles, share starting before the award, share starting 30 or more
  days after; and actual start against the expected start where given. Awards from 2022-08-08 to 2025-09-30.
- By channel and by department (8 largest): opportunities, win rate, median days from creation to award, share
  cancelled. Opportunities created from 2022-08-08 to 2025-06-30, outcome as at the cutoff.
- Amount coverage: share of wins with a usable amount, and the median amount, which prices one win in the worth
  section (labelled as an assumption).

## Stopping rule

Every arm is scored on every snapshot and every result is published, whatever it shows. No arm, band or weight is
tuned after the results; anything added after the results is labelled so on the page.

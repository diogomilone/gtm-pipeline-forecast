# Forecasting a sales pipeline: stage win chances and close dates

How far off is a pipeline forecast of a quarter's wins when its stage probabilities are a CRM's defaults, when they
are learned from history, and when they depend on how long a deal has sat in its stage? And how long from signed to
live? This study scores four forecasts on 8 quarters of Canadian federal tenders, each made at the start of its quarter
with the awards on record then (tender fields as last amended; rebuilding them moved no average by more
than 0.51 points). The pages are `index.html` (summary), `backtest.html` (the eight quarters),
`results.html` (every table) and `method.html` (method and checks).

## Data

CanadaBuys open data, Government of Canada: all tender notices published on CanadaBuys since 2022-08-08 and all award
notices since the same date. Contains information licensed under the Open Government Licence (Canada)
(https://open.canada.ca/en/open-government-licence-canada).

`data/opportunities.csv.gz` is the reduced opportunity table, one row per solicitation number, with no contact,
supplier or address field. `data/sources.json` records the source URLs, their sha256 and the row counts.

## Reproduce

Python 3.12. DuckDB (`pip install duckdb`) is needed only to rebuild the opportunity table from the source files; the
forecasts, the tests and the pages need only the standard library.

```
python3 -I -B tools/get_data.py /path/to/new/dir        # downloads both files, rebuilds data/
python3 -I -B tools/get_notices.py /path/to/new/dir      # the tender file again, one row per notice: data/notices.csv.gz
python3 -I -B tools/dash_free.py                         # an en or em dash inside a field becomes a hyphen
python3 -B tests/test_pipeline.py
python3 -B tools/run_study.py                            # the declared run: results/summary.json
python3 -B tools/after_results.py                        # analyses added after the results: results/after.json
python3 -B tools/run_study_r2.py                         # the further changes: results/summary-r2.json
python3 -B tools/stale_deals.py                          # added later: results/stale-deals.json
python3 -I -B site/render.py                             # the four pages
```

The source files are refreshed daily, so a fresh download can differ from the one used here; `data/sources.json`
holds the hashes of the files this study used. With the shipped `data/` tables, the three runs reproduce the results
files exactly.
`get_notices.py` refuses a tender file whose sha256 differs from the one recorded.

The shipped tables are the output of `dash_free.py`, added after every result. 33 solicitation numbers (the same in
both tables) and 6 buyer names held an en or em dash, and each is now a hyphen. No two values merged, and the three
runs give the same results files, byte for byte, on the tables before and after that step.

## Files

- `DESIGN-r1.md`, `protocol-r1.json`, `predictions-r1.json`: the design, rules and predictions, committed before any
  forecast was computed.
- `CHANGES-r1.md`: the analyses added after the results, committed before they were run.
- The further changes (tender notices as known at each quarter's start, scoring on the same target, the past-due
  split, ranges from misses known at the time) and their bets are listed on the method page; they were declared before
  any code or run for them, in a file not included here.
- `tools/pipeline.py`: stages at a snapshot, the four forecasts, ranges and scores.
- `tools/run_study.py`, `tools/after_results.py`: the declared run and the analyses added after it.
- `tools/run_study_r2.py`: the further changes; results in `results/summary-r2.json`.
- `tools/get_data.py`, `tools/get_notices.py`: download and reduction of the source files; the notice table keeps one
  row per tender notice, each as last amended, with no contact, supplier or address field.
- `tools/dash_free.py`: replaces each en or em dash inside a field of the two tables with a hyphen.
- `tools/stale_deals.py`: added later, and not written down before it was run. It counts the deals dated outside
  each quarter by how long they had sat at their stage, with their wins; results in `results/stale-deals.json`.
- `assumptions.json`: the onboarding hours and costs behind the declared onboarding plan, whose figures are in
  `results/after.json`; the pages do not use them. They are assumptions, not data.
- `site/render.py`, `site/page.css`: the pages, with every number taken from `results/` or `assumptions.json`.
- `vendor/viz-design-system/`: the chart kit (version 2.3.0) with its licences.

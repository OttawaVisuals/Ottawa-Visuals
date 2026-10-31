# Canada’s wealth distribution

Page: [wealth.html](wealth.html). Canada-level wealth distributions; no Ottawa-specific inference.

## Coverage and charts

| Series | Reference dates | Page controls | Source |
|---|---|---|---|
| Household accounts (DHEA) | 34 observations, 2010–2025: Q4 before 2020, all quarters from 2020 | Five-quintile snapshot, year-end/all-quarter trend, exact table | StatCan 36-10-0660-01 |
| Survey of Financial Security | 1999, 2005, 2012, 2016, 2019, 2023 | Five quintiles: wealth shares, median or mean net worth | StatCan 11-10-0049-01 |
| PBO 2021 history | 1999, 2012, 2016, 2019 | Top 0.01%, 0.1%, 0.5%, 1%, 5%, 10%; Forbes/Canadian Business variants | Table 3-1 |
| PBO 2025 history | 2016, 2019, 2023 | Top 1% and 5%; survey/Forbes/enriched variants | Figures 1–2 numeric descriptions |
| PBO percentile snapshots | 2019 and 2023 estimates; Q2 2021 and Q4 2024 projections | Nine overlapping percentile/range groups, wealth share; exact cutoff, count and total table | 2021 Tables 2-2/2-4; 2025 Tables 2/4 |
| PBO wealth thresholds | 2019 and 2023 | Share held above ten dollar cutoffs, family counts and wealth totals | 2021 Table 2-3; 2025 Table 3 |
| Original historical study | 1970, 1977, 1984 | Ten decile shares, selected/all-decile charts, Gini | G. Oja, StatCan, Table 1, printed p.25 |
| Reanalysed historical study | 1984, 1999, 2005 | Ten decile shares, medians in 2005 dollars, Gini | StatCan, Revisiting wealth inequality (2006), Table 1 and article |

This is the national net-wealth distribution history from these source families.
It does not import every asset component, demographic breakdown, geography or
alternative standardized/excluded-top-family sample in the source publications.
No annual observations are invented between survey years. No data series or
report editions are spliced. It is not a claim of an exhaustive inventory of
all Canadian wealth research or every historical report vintage.

## Reproduce

Python 3, standard library only for the builders, from the repository root:

```powershell
python Wealth/scripts/build_data.py
python Wealth/scripts/build_history.py
python -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/Wealth/wealth.html`. Direct file opening also works:
both builders create local JavaScript data bundles; charts need no CDN library.

PBO/early-study values are checked numeric transcriptions in
`data/historical-transcription.json`, with source URLs, report editions, table/page
locators and limitations. PBO values come from tables and numeric figure
summaries, not estimated chart coordinates. Both reports’ missing observations
are explicit JSON nulls and empty CSV values. Rebuilding does not automatically
re-transcribe new reports; review the source notes before adding a new edition.

## Data and calculation

- `wealth.json` / `wealth-data.js`: all 34 DHEA observations plus a Q4 subset for
  the default view. `wealth.csv`: 170 quintile-period rows.
- `statcan-source-rows.csv`: 612 exact DHEA net-worth rows with original vectors,
  units, status flags and values. Source ZIP SHA-256 and UTC download retained.
- Individual DHEA shares use published `Distribution of value`. Combined bottom
  40% and middle 40% use summed dollar totals / all-household total, rounded to
  one decimal. Gap = top-20% share minus bottom-40% share, in percentage points.
- `sfs-source-rows.csv`: 648 national net-worth source rows, including all six
  statistics and three confidence-interval levels. Values/flags retained even
  where unavailable. `survey.csv`: 30 quintile-year observations.
- SFS wealth shares are calculated as quintile net-worth total / all-unit total.
  **Do not use the source’s “Percentage of total assets or total debts” statistic
  for these shares:** it is not the quintile’s share of nationwide net worth.
  Means/medians are the source’s “for those holding asset or debt” statistics.
  SFS dollar values are constant 2023 CAD, unlike nominal DHEA dollars.
- `history.json` / `history-data.js`: SFS plus historical transcriptions and source
  notes. `historical.csv`: 366 metric records, including explicit unavailable
  observations; source ID, locator, variant, unit-bearing metric and
  estimate/projection status accompany each row.
- PBO percentile/threshold groups overlap. For example, top 1% is contained in
  top 10%; never stack or sum all percentile bars. Only top 20% + middle 40% +
  bottom 40% forms a full partition (within published rounding).
- Historical deciles use the all-family-unit, unadjusted published share columns.
  Negative and zero values are retained. Gini values are only comparable within
  their study. All-decile views split into lower/upper panels with separate scales.

## Sources and limitations

- [DHEA table](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610066001),
  [SFS table](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110004901),
  [DHEA methodology](https://www150.statcan.gc.ca/n1/pub/13-604-m/13-604-m2026001-eng.htm).
- [PBO 2021 report](https://www.pbo-dpb.ca/en/publications/RP-2122-023-M--estimating-top-tail-family-wealth-distribution-in-canada-updates-trends--estimation-extremite-superieure-distribution-patrimoine-familial-canada-mises-jour-tendances),
  [PBO 2025 update](https://www.pbo-dpb.ca/en/publications/RP-2526-009-S--estimating-top-tail-family-wealth-distribution-in-canada-2025-update--estimation-extremite-superieure-distribution-patrimoine-familial-canada-mises-jour-2025).
- [Original 1970–1984 study](https://publications.gc.ca/collections/collection_2017/statcan/CS13-588-1.pdf),
  [1984–2005 reanalysis](https://www150.statcan.gc.ca/n1/pub/75-001-x/11206/9543-eng.htm),
  [reanalysis numeric table](https://www150.statcan.gc.ca/n1/pub/75-001-x/11206/4096770-eng.htm).

Wealth is assets minus debts; modern measures include housing and pension wealth.
The original 1970–1984 study excludes insurance and pension rights. The later
1984–2005 analysis excludes employer-sponsored pensions across all three years.
Original/reanalysed 1984 estimates differ and must remain separate.

DHEA combines accounts, surveys and models. SFS underrepresents the very wealthy
and covers the ten provinces, excluding Indigenous communities and collective
dwellings. PBO adjusts the upper tail using rich lists; uncertainty remains.
The 2021 PBO edition uses public-use SFS, while the 2025 update uses full microdata
and updated lists. A vintage difference is not a measured economic change.
Canadian Business/enriched data are missing in 2019; PBO excludes 2005 from its
older top-wealth history because of the small sample. There is no filled estimate
for either gap. PBO projections are not new survey observations.

Shares can sum slightly above/below 100% because of rounding. Group membership
changes over time. Means and medians differ; neither is an entry threshold.
No causal or fixed-cohort interpretation. Charts show point estimates; original
SFS confidence intervals and quality flags remain available in the source CSV.

DHEA returns to annual releases; 2026 data scheduled April 13, 2027, per the
[Q4 2025 release](https://www150.statcan.gc.ca/n1/daily-quotidien/260413/dq260413a-eng.htm).
No automatic refresh or public deployment configured by this change.

## Verification

Builders validate coverage, units, source statuses, quintile totals, published
share rounding, nested-percentile monotonicity, partition sums and array shapes.
The 2025 DHEA endpoint matches the checked release: 65.7%, 3.0%, 62.7 pp.

`check_transcription.py` independently compares the PBO history, four percentile
snapshots and two threshold tables against the downloaded primary PDFs, and all
2006-study decile shares/medians against the primary HTML table. It requires
PyMuPDF and original PDFs named `pbo2021.pdf` / `pbo2025.pdf` under the untracked
`output/wealth-research/` folder. It passes. PBO source table/figure pages were
rendered and visually reviewed. The 1987 transcription was checked against the
primary report’s extracted Table 1 text; direct download returned an archive
cover, so local PDF visual inspection
of that historical table was unavailable.

Browser verification (October 31, 2026): all three SFS metrics (30 dots each),
all eight PBO report/group combinations (7/8 dots, retaining missing values),
all four percentile snapshots and both threshold snapshots, and 11 early-study
metric/group combinations passed. Q4/all-quarter trend counts are 48/102 dots.
Expanded historical tables and unavailable labels checked. Desktop and 320px/390px
phone layouts reviewed in light, dark and colour-blind themes; no page overflow
or browser warning/error logs. Fixed dense year ticks after observing a phone
label collision. All 20 local page links, export counts, JS syntax and whitespace
checks pass. Public deployment remains untested; publication pending.

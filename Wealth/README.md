# Canada's wealth distribution

Page: [wealth.html](wealth.html). Canada-level estimates; no Ottawa-specific inference.

Two charts: five wealth quintiles' shares for a selected year, and annual Q4 wealth
shares for the top 20%, middle 40% and bottom 40%, 2010–2025. The top-20% minus
bottom-40% gap is shown in percentage points. A separate PBO callout describes its
2023 top-1% family wealth estimate; it is not spliced into the StatCan household series.

## Reproduce

From the repository root, using Python 3 (standard library only):

```powershell
python Wealth/scripts/build_data.py
python -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/Wealth/wealth.html`. Direct file opening also works:
the page reads the generated `data/wealth-data.js` bundle without a fetch/CDN chart dependency.

## Sources and calculation

- StatCan [36-10-0660-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610066001), downloaded from its official ZIP/CSV. Latest checked release April 13, 2026, through Q4 2025.
- Filter: Canada, Net worth (wealth), five wealth quintiles plus all households,
  Q4 (`REF_DATE` ends `-10`), non-missing values. No interpolation.
- Use published `Distribution of value` for individual quintile shares and
  `Value per household` for mean nominal dollar values.
- Combine the `Value` totals for the bottom two/middle two groups before dividing
  by the all-household total and rounding to one decimal. This avoids summing
  rounded shares. `Value` is in millions of dollars; per-household values are dollars.
- Gap = published top-quintile share minus rounded bottom-40% share.
- Validations: continuous annual coverage, accepted status flags, expected units,
  source shares within rounding tolerance of totals, five totals reconcile to the
  all-household amount, and latest figures match StatCan's release (65.7%, 3.0%, 62.7 pp).
- Exact input rows with vectors and status flags are retained in
  `data/statcan-source-rows.csv` (288 rows). The ZIP SHA-256 and UTC download time
  are retained in `wealth.json`. The large full table is not committed.
- `data/wealth.csv` contains 80 quintile-year records; JSON also includes combined shares.
- PBO [2025 update](https://www.pbo-dpb.ca/en/publications/RP-2526-009-S--estimating-top-tail-family-wealth-distribution-in-canada-2025-update--estimation-extremite-superieure-distribution-patrimoine-familial-canada-mises-jour-2025): 24% of net wealth held by top 1% of economic families in 2023. Adjusted/modelled estimate using survey data and billionaire lists; significant uncertainty.

## Limits / refresh

Wealth is assets minus debts, including housing and pension wealth. Negative
quintile values are retained. Average values are neither medians nor entry cutoffs.
Groups can contain different households each year. Shares are rounded, and totals
can differ slightly from 100%. Dollar values are not adjusted for inflation.

DHEA combines national accounts with surveys and other sources and uses modelling
assumptions. SFS underrepresents the very wealthy and covers the ten provinces,
excluding Indigenous communities and collective dwellings. The PBO estimate uses
a different family unit and method. No causal or fixed-cohort interpretation.

DHEA returns to annual releases; 2026 data scheduled April 13, 2027, per the
[Q4 2025 release](https://www150.statcan.gc.ca/n1/daily-quotidien/260413/dq260413a-eng.htm).
Re-run the script for revisions; review dates, displayed coverage, narrative,
and release-match assertions when adding a year. No automatic refresh configured.

## Verification (October 31, 2026)

Builder checks passed for 16 years / 288 source rows; latest shares and all five
mean net-worth values match the checked release/table. Browser checks covered
all 16 year selections (five table rows and matching chart/summary per year),
expanded exact/annual/source details, desktop dark/light and phone light/colour-blind
views, and 320px/390px viewport overflow. No browser warning/error logs. Local
links, JavaScript syntax and whitespace checks passed. Public deployment untested.

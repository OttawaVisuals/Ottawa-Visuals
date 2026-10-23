# Ottawa budget explorer

`budget.html` is a buildless page for the existing GitHub Pages site. It uses the
**adopted** 2026 budget, not the draft Budget Explorer. Snapshot reviewed October 23, 2026.

## Coverage

- 17 operating service groups, 11 capital committee groups and 11 operating revenue categories.
- 2025 budget comparator and 2026 adopted amounts from the same publication; nominal CAD.
- Expandable breakdowns for social services, recreation, emergency services, corporate costs,
  environment, audit and three capital committees.
- Year, funding coverage, dollars/share and 2025 comparison controls; shareable URL parameters.
- Accessible native bars, exact table, CSV, JSON, source PDF page links and shared themes.
- Lansdowne: distinct main project / parking / retail authority, initial financing,
  July 21, 2026 spending snapshot and separately labelled modelled revenue offsets.
- 2023–2026 full-accrual budget expenses by 10 City functions, with selectable comparison
  years, dollar/percentage changes, zero-centred increase/decrease bars, annual values and CSV.
- 26 dated KPI series: paramedic response (including citywide/urban/rural), Level Zero,
  transportation condition measures and housing wait-list/shelter measures. Targets shown
  where extracted; no citywide performance score or causal spending/outcome claims.

## Added historical comparison and KPI sources

Run `python Budget/scripts/build_history_kpis.py` to rebuild `history.json/csv`,
`kpis.json/csv` and `history-kpi-source-excerpts.txt`. Requires `pypdf`. PDFs are cached
in the OS temp directory; source URLs, SHA-256 hashes and PDF pages are retained.

- **Budget history:** 2024 adopted book, Table 1, PDF p. 14, gives 2023/2024 budget expenses;
  2026 adopted book, Table 1, PDF p. 15, gives 2025/2026. Same ten function labels.
  These are **full-accrual consolidated budget expenses**, not the cash-oriented operating
  budget in the original service chart. They spread asset costs over useful life and include
  consolidated entities. Never splice these totals into the operating series. Reported
  as published, without restating historical program scope, inflation or population.
- **Paramedics:** 2025 annual report, official eScribe DocumentId 318696, PDF pp. 18–22.
  CTAS 1–5 targets and citywide response (2021–2025), urban/rural response (2021–2025),
  sudden cardiac arrest response and Level Zero minutes. The clock starts at crew
  notification, not the original 9-1-1 call. AED arrival can involve any person with an AED.
  Urban/rural charts reference the citywide target; separate geographic targets are not asserted.
  MPDS was introduced in April 2024. If automated download returns 403, use the official
  report link in the browser and save as `ottawa-paramedic-2025.pdf` in the temp directory.
- **Infrastructure:** 2025 Transportation Services AMP, PDF p. 16 gives dated 2019 and
  2023 condition measures. No annual interpolation. PDF p. 11 gives overall condition
  shares weighted by replacement value; these are a separate plan snapshot with varied
  inspection dates, not percentages of kilometres or assets. Transportation only; water,
  sewer and other infrastructure classes are not included. Targets not extracted.
- **Housing:** 2024 Housing Needs Assessment, Figures 57 and 62, PDF pp. 117 and 123.
  The chart labels are raster content, so `housing-reviewed.csv` holds manually transcribed
  and visually verified labels for 2019–2024. Wait-list 2024 is **December 10**, not December 31.
  Source p. 215, Table 52 provides shelter users and nights. Wait-list placements are
  not housing starts/completions; shelter users do not count all people experiencing homelessness.

After **any data rebuild**, run `python Budget/scripts/build_inflation.py`, then
`python Budget/scripts/package_page_data.py`.
It generates `data/page-data.js` from the four canonical JSON files, allowing a local
`file://` page to load without fetch. Over HTTP, the page continues to load the JSON files
and preserves shared URL controls. Local-file controls work without rewriting the URL.
Check the package with `scripts/check_history_kpis.py` before committing.

## Inflation option

The global dollar-basis control defaults to nominal and can show **2025 dollars**.
It updates budget overview cards, history, operating/capital/funding bars, children,
tables and changes. Within-year shares stay the same. `prices=real` persists in HTTP URLs.
Lansdowne's separately dated source figures and non-monetary service KPIs keep their units.

Formula: `nominal amount * CPI(2025) / CPI(year)`. Ottawa-Gatineau, Ontario part,
all-items, not seasonally adjusted, CPI index 2002=100; StatCan geography member 15,
product member 2. Annual Table 18-10-0005-01 gives 2023=159.2, 2024=162.8, 2025=166.3.
2026 uses a **provisional Jan–Sep monthly average**, 170.4444444, from Table 18-10-0004-01.
It is a YTD proxy, not full-year inflation or a forecast. No missing months are invented.
CPI is a consumer-price benchmark, not a municipal wage or construction-cost deflator.

`build_inflation.py` caches WDS responses in the OS temp directory, retains source hashes
and every 2026 monthly observation in `data/inflation.json`, and writes CPI/factor CSV
and `budget-inflation-adjusted.csv` (122 overview/history observations, original plus adjusted).
The script stops if the cutoff changes from nine months so labels must be reviewed explicitly.
To refresh, move/remove the two specifically named cached `ottawa-cpi-18100005.json` and
`ottawa-cpi-18100004.json` files; rerun and review. Repackage after rebuilding.

Validate with `python Budget/scripts/check_inflation.py` and `node --check Budget/inflation.js`.

## Sources and reproducible budget extraction

Primary book:
https://documents.ottawa.ca/sites/default/files/2026%20Adopted%20Budget%20Book%20English%20Condensed.pdf

`scripts/build_budget.py` requires Python and `pypdf`. Run from the repository root:

```powershell
python Budget/scripts/build_budget.py
```

It downloads the book to the OS temporary directory (`ottawa-budget-2026.pdf`) only
when missing. It retains a SHA-256 fingerprint in `data/budget.json`. To deliberately
refresh the source, first move or remove that **specific** cached PDF, rerun, inspect
the diff and manually review any changes. Review the date and source mappings in the
script too; this is not an automated yearly rollover.

- Printed p. 1 / PDF p. 20: revenue and expenditure totals.
- Printed pp. 2–5 / PDF pp. 21–24: operating expense columns. 2025 budget is the
  middle expense column, not the first (actual) column. 2026 adopted is the third.
- Printed pp. 17–19 / PDF pp. 36–38: capital new authority and forecast. Only 2025
  adopted and 2026 authority are used; 2027–2029 are forecasts, not actual results.
- Keep `data/source-excerpts.txt` with the build for auditability; keep the large PDF outside Git.
- Labelled rows must be found and annual totals must reconcile within $5,000 of
  the published totals. The tolerance covers summing separately rounded source rows.
  Current operating differences: +$2,000 (2025), +$4,000 (2026); capital: $0 (2025),
  -$1,000 (2026). Do not force rows to match by inserting invented adjustments.
- `budget.csv` exports both years for all overview rows. JSON additionally includes child rows,
  capital purpose categories, funding classification, totals, document pages and source hash.

## Meaning of amounts

Operating expenses are net of recoveries and after interdepartmental allocations,
**before program revenue**. They are not the tax levy. The tax-supported filter uses
the source's program classification, not a claim that all costs are paid by property tax.
Water, wastewater and stormwater use the separate rate-supported classification.

Capital is **new spending authority**, potentially used over several years. It excludes
previous authority. Preserve committees as published; transit investments appear in
Public Works, Finance and Transit. The largest capital committee groups expose the
published subcategories so readers can see this.

Operating costs include reserve contributions and debt charges. Never add the operating,
capital and tax-funding overview cards to create a city spending total. The adopted book's
full-accrual reconciliation uses a different presentation again.

Shares use the selected view/year's printed total. Filtering operating programs changes
the denominator. Share comparison bars use each year's own denominator. All dollar bars
start at zero, with a common scale within the selected view.

## Lansdowne review

`data/lansdowne.json` is a manually reviewed source snapshot, not a collector.
Original URLs and section locators are retained for every document. Review later
project updates, financing terms, authority changes and revenue realization before updates.

- Main authority $418.8M; separate parking $19.2M and retail $45.9M. Their derived
  sum is $483.9M, excluding private towers and interest. Do not add contract and
  contingency subtotals to authority: they may overlap.
- Main project spending $59.5M in the first-half 2026 City memo, published July 21.
  Approximately 14.2% of budget, not construction completion. Do not relabel it September
  spending merely because later news reports repeated this amount.
- November 6, 2025 City memo: debt $331M, air rights $33.9M, premiums $32.4M,
  capital reserves $15.6M and accommodation tax $6M. Rounded sum $418.9M vs $418.8M authority.
- City model: net investment $130.7M and projected offsets $288.2M. These are not
  cash received, and they are not additive to the initial financing sources.
- Debt-payment estimate $17.4M/year assumes 4.25% over 40 years in that memo;
  the budget allocation reaches $17.4M in 2036. Final borrowing terms not verified.
- Do not copy the City's “no cost to taxpayers” language as an independently established conclusion.

The static Lansdowne headline copy and progress bar repeat this snapshot for readable
fallback content; update them together with the JSON. `scripts/check_budget.py` checks consistency.

## Verification

```powershell
python Budget/scripts/check_budget.py
python Budget/scripts/check_history_kpis.py
node --check Budget/budget.js
node --check Budget/history-kpis.js
python -m http.server 8765 --bind 127.0.0.1
```

Open `/Budget/budget.html`. Review all three chart modes, both years, both display
units, each funding subset, comparison bars, service disclosures, CSV, shareable URL,
error/retry state, and light/dark/colour-blind layouts. Browser QA results are recorded
in `CHECKS.md`. No external chart library or build tooling is required.

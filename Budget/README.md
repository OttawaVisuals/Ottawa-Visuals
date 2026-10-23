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
- Service KPI source directory; no new citywide KPI score or causal spending/outcome claims.

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
node --check Budget/budget.js
python -m http.server 8765 --bind 127.0.0.1
```

Open `/Budget/budget.html`. Review all three chart modes, both years, both display
units, each funding subset, comparison bars, service disclosures, CSV, shareable URL,
error/retry state, and light/dark/colour-blind layouts. Browser QA results are recorded
in `CHECKS.md`. No external chart library or build tooling is required.

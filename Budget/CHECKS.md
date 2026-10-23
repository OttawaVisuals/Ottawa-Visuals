# Verification — October 23, 2026

## Historical comparison and KPI expansion (same day)

- Built `history.json/csv` from Table 1 of the 2024 and 2026 adopted books. Ten
  identical function labels, four years, reconciled annual full-accrual totals.
- Downloaded the official 2025 paramedic report (eScribe DocumentId 318696) through
  the browser after automated source retrieval was blocked. Cached PDF stays outside
  Git. Visually checked PDF p. 18 response table against the extracted 2021–2025 values.
- Visually checked Housing Needs Assessment Figure 57 (PDF p. 117) and Figure 62
  (p. 123). Exact chart-image labels retained in `housing-reviewed.csv`.
- Extracted transportation condition measures (2019/2023) and the separate replacement-
  value-weighted condition snapshot. Did not interpolate missing years or infer targets.
- **124 original accounting/source/file checks and 208 history/KPI/package checks passed.**
  JS syntax checks passed for both scripts. Packaged JSON matches all canonical files.
- Exercised **all 12** valid historical year-pair/ranking combinations and **all 26** KPI
  series through the browser, including urban/rural choices and target markers. No invalid
  numeric labels. Confirmed negative changes remain negative and zero-centred.
- Verified URL controls coexist with the original operating/capital chart controls.
  Added a bundled JSON snapshot for direct-file use; browser automation cannot inspect
  `file://` URLs, so direct-file rendering is not browser-verified. HTTP preview is verified.
- Added mobile-specific count/unit separation after finding awkward wrapping in housing
  headlines. Checked 390px and 320px widths; no horizontal page overflow. Reviewed tablet
  (768px), desktop, dark and colour-blind modes, and the dashed target-line contrast.
- Reloaded a combined history/KPI/capital/share URL and verified every selection persisted.
  No console errors in the completed HTTP preview.

The original checks below describe the initial page; this section supersedes its
former limitation that KPI cards were only source links.

## Data

- Ran `scripts/build_budget.py` against the adopted 352-page City PDF. Source SHA-256
  is retained in `data/budget.json`; source text tables in `data/source-excerpts.txt`.
- Visually inspected rendered PDF page 24 to confirm the expense/revenue/net columns,
  the 2025 budget versus actual distinction and the tax/rate program totals.
- **115 accounting, source, scope and file checks passed** (`scripts/check_budget.py`).
  Includes overview totals, child reconciliation, correct budget columns, library expense
  versus net requirement, program coverage, Lansdowne financing/scope sums, CSV coverage,
  static Lansdowne fallback consistency and all local page links.
- Operating service sums differ from City totals by +$2,000 (2025) and +$4,000 (2026).
  Capital committee sums differ by $0 (2025) and -$1,000 (2026). Differences are disclosed.
- `node --check Budget/budget.js` and `git diff --check` passed.

## Browser

Used the in-app browser against the local static server.

- Exercised **20 combinations**: all 3 views, 2 years, 2 unit formats and the 3
  operating coverage filters. Correct category counts and displayed totals; no NaN,
  Infinity or undefined values, and no horizontal page overflow in those combinations.
- Checked comparison bars: 17 all-service, 14 tax-supported, 3 rate-supported and
  11 in each other view. 2025 selection suppresses comparisons and disables the checkbox.
- Expanded social-services and Public Works capital groups; checked rendered subcategory
  amounts and PDF page links. Capital breakdown exposes transit-related authority.
- Checked default desktop, 768px tablet, 390px phone and 320px narrow phone widths.
  Visually reviewed service charts, capital details and Lansdowne cards. No page overflow.
- Exercised light, dark and colour-blind theme controls. Theme state changed correctly;
  visually reviewed light/tablet/mobile and dark/narrow-phone presentation.
- Tested data failure by temporarily renaming the local budget JSON: error notice and CSV
  fallback appeared. Restored the exact file and clicked Retry; the chart recovered.
- Reloaded a URL containing selected view, year, coverage, units and comparison parameters;
  selections persisted.

## Limits

- No screen-reader session or full automated accessibility audit. Semantic labels,
  native controls, exact tables, keyboard focus and reduced-motion CSS are provided.
- External City pages can return 403 to automated requests. Research used official
  search-indexed content when direct reading was blocked; original URLs are retained.
- The Lansdowne ledger is a July 21, 2026 snapshot, not a claim to be the newest available
  update. Final borrowing terms and realized future revenue are not established.
- This verification does not certify the City's forecasts or provide an independent
  project cost audit. The initial release's KPI link cards were expanded into sourced
  time series in the same-day update described above.
- Local build only; no publication or remote push was performed.

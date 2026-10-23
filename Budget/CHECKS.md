# Verification — October 23, 2026

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
  project cost audit. KPI cards are a source directory, not extracted KPI time series.
- Local build only; no publication or remote push was performed.

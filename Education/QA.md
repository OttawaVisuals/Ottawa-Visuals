# Education verification — November 2, 2026

## Data and source checks

- `python Education/scripts/check_data.py`: **6,488 checks pass**. Original StatCan source amounts, scale, status, vectors and coordinates reconcile; CPI factors and the 2023–24 price base agree. Seven source hashes match.
- An independent `openpyxl` read of the entire 2025–26 English-labelled worksheet reproduces the XML builder's province and four board aggregates, including both suppression bounds and above-25 counts. French-labelled duplicate sheets are excluded.
- Latest workbook: 64,496 populated board rows, including 3,015 entirely zero rows; **61,481 non-empty reported classes** enter Ontario's all-class aggregate. The class coverage export retains original/zero row counts. Board totals reconcile to school-name aggregates; grade groups reconcile to each all-class total.
- Four board aliases (including the 2025–26 abbreviations) supply continuous 2014–15 to 2025–26 all-class coverage. Early source sheets contain no upper-only class rows; no all-class/upper history is claimed before 2014–15.
- 1,823 financial source rows, 404 board/province aggregates and 17,744 school-name/group/year aggregates retained. JSON and bundled JS payloads parse to identical objects.

## Browser checks

- All **60** board × class-group × measure combinations render with current-year readouts, valid chart paths and no data-error panel.
- All **24** funding/spending × price-basis × history combinations render. The 2000–2023 public/private expenditure view has 43 line segments, consistent with the 2012–13 methodology breaks and the additional private-school 2006–07 estimation break.
- **20** default-school board/group combinations render without errors. Search finds Agincourt Road Public School; a deliberate no-match query produces the empty state. Missing groups remain unavailable, with any board comparator identified separately.
- Selected-view browser CSV: all **24** downloaded rows reconcile to the source government's totals and the sum of fees/other private funding for the selected nominal 2012–2023 view.
- Expanded exact tables checked at 320/390/768/1240 CSS pixels in light/dark/colour-blind themes: no page overflow or data errors. Phone axis-label crowding found and fixed using shorter school-year labels; both phone widths rechecked in all three themes, with no overlapping chart ticks.
- Keyboard Enter on a class point updates its readout. No browser JavaScript errors. Header artwork loads; homepage education card and return navigation work. Local anchors, download/assets paths, unique IDs and JS syntax pass. Proof screenshots: `output/education/page-preview.jpg` and `class-size-preview.jpg` (local/untracked).

## Limits

These are source-snapshot and interface checks, not a verification of schools' submissions or a regulatory compliance audit. Interpretation of `<5` as a positive 1–4 count assumes the source suppresses positive cells, since true zeros are separately published. The page makes this assumption explicit; no individual cell is reconstructed. Repeated school-name/class-number keys are conservatively flagged; their cause is not established. No stable school-ID join, school-renaming crosswalk, private/secondary class-size history or teachers-by-school series is claimed. The four boards do not equal City-of-Ottawa-resident geography.

Built and committed locally; no publication or collector changes.

## Threshold-count extension

- `check_thresholds.py`: **1,192 checks pass**, covering source hashes, population identities, nested cap counts, suppression uncertainty and average denominators. All 2025–26 counts independently reconcile using a direct XML import; the new builder reads the original files with `openpyxl`.
- Seven fixed references × seven years × five areas = 245 count rows; 70 kindergarten/upper average rows. Count bounds distinguish certainly above from possibly above; exact zeros remain zeros. Kindergarten mixed-class fractions and inclusion of mixed classes in upper averages are explicit. Existing financial and class-size exports remain unchanged.
- Latest source flags: Ontario primary above 23 = 0–6; kindergarten above 32 = 0; OCSB kindergarten above 29 = 8. The latter can include permitted exceptions; no approvals or class-property fields are available and no violation verdict is produced.
- **140** browser combinations (all areas/references, count/share, first/latest years) render without errors/invalid paths; all seven cutoff years produce the expected one-to-seven points. Zero-count axes use integer ticks. A 10% reference line appears only for the relevant board-share views and is omitted for combined Ontario/count views.
- 320/390/768/1240px × three themes with the average table expanded: no document overflow, data errors or invalid paths. Two average rows and the share-reference line remain present. Browser CSV download matches all 245 exported rows exactly; JSON/JS payloads agree, local assets/anchors resolve and existing IDs are retained. No browser JavaScript errors.
- A long initial 490-case UI batch exceeded the tool time limit; the completed 140-case boundary sweep and seven cutoff checks above are the reported UI coverage. This was a test-run timeout, not a page error.
- Threshold benchmarks are screening references held constant, not a historical compliance audit. The original `<5` = 1–4 positive-cell assumption continues to apply. Source flags cannot identify excluded self-contained classes or prove exception eligibility.


## OECD comparison extension

- `check_thresholds.py`: **2,062 checks pass**, including independent XML reconciliation of all latest OECD counts/scopes, population identities and nested 21/23 counts. The 245 prior count rows and 70 average rows are unchanged in values; scope metadata is added.
- Two published rounded OECD 2024 averages (21 primary, 23 lower secondary), each with three Ontario comparison scopes, add 210 rows: 455 total. All JK/K-containing classes are excluded. No exact OECD-grade or special-needs population match is claimed; averages are descriptive, held fixed across history.
- Browser: all six OECD reference/scope combinations verified for Ontario 2025–26 with nine reference-table rows; legacy primary-23 values and hidden scope control checked. Percentage mode and the first-year single-point history checked. Latest Ontario grades 1–8 above 21 = 27,941–28,185 / 50,890; above 23 = 20,250–20,287 / 50,890.
- New OECD controls checked at 320/390/1240px with no document overflow or invalid paths. Downloaded CSV is byte-identical to the 455-row export; JSON/JS agree. JS syntax passes. Screenshot: `output/education/oecd-preview.jpg` (local/untracked).
- An attempted larger UI sweep timed out; only the completed checks above are claimed. Existing financial/class-size exports remain unchanged. Local, publication pending.


## Alberta snapshot extension

- Original Alberta 2025–26 workbook metadata and source URL/hash retained; 88,932 unique classroom identifiers across 61 authorities. Band and authority totals reconcile; all threshold counts nest correctly. 3,723 suppressed sizes below 10 remain in denominators and cannot exceed either 21 or 23. No enrolment midpoint is imputed.
- `check_alberta.py`: all **310 aggregates** independently reproduce from original workbook XML (builder uses openpyxl), including exact count/suppression/above-21/above-23 fields. Source hash and CSV/JSON/JS consistency pass.
- Browser: all 10 province band/reference combinations render with five table rows and no invalid values. Calgary and Edmonton authority filters checked. New section at 320/390/1240px: no document overflow. Downloaded 310-row CSV is byte-identical. Local assets/download links and unique HTML IDs pass; JS syntax passes and no console errors observed. Proof: `output/education/alberta-preview.jpg` (local/untracked).
- Separate single-year panel; no Ontario caps applied to Alberta and no province ranking claimed. K–3 includes kindergarten; unique pupils, physical rooms and teachers are not derived. Excluded school/program types and duplicate student participation across instructional groups are explicit. Only 2025–26 imported; older series not spliced. Ontario datasets are unchanged. Local, publication pending.

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

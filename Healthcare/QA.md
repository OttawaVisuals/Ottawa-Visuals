# Healthcare verification — November 2, 2026

## Artwork

- Header illustration and all seven decorative markers present at 320/390/1240px in light, dark and colour-blind themes; no document overflow. Homepage healthcare card loads the same illustration.
- Seven SVGs parse and return HTTP 200. Generated WebP preserves the original PNG's exact RGBA pixels and actual transparency.
- Existing HTML IDs and controls retained; no scripts, datasets or formulas changed. No browser console errors. Preview: `output/healthcare/artwork-preview.jpg`.

## Source/data checks

- `python Healthcare/scripts/check_data.py`: **514 source/value checks pass**.
- All 459 calculated per-resident spending values match CIHI’s separate published per-resident tables (tolerance $0.00001).
- Every printed expense component subtotal reconciles in both current and comparator columns of all 14 hospital financial statements. Derived expenses retain separately reported building, parking and explicit wage costs.
- All source-file SHA-256 hashes match; 459 distinct spending keys, 10 workforce years, 28 financial years and six staffing years.
- 2024/2025 spending flags match the forecast convention; 2023-dollar adjustment equals nominal in the reference year.
- Visually inspected rendered full statement pages: TOH 2026, CHEO 2024, QCH 2024 and Montfort 2024, including below-subtotal adjustments. Rendered PNGs are in ignored/untracked `output/healthcare/`, not required by the page.

## Browser checks

- Local server responds HTTP 200; no page JavaScript errors.
- Original finance/workforce charts still render; hospital selection with missing staffing retains an explicit unavailable panel.
- Final 320, 390, 768 and 1240 CSS-pixel widths × light, dark and colour-blind themes: no document overflow, header-control overlap or visible data-error panel. Chart paths checked for NaN during control testing. Shared author credit included; duplicate header home link hidden on phones.
- Public/private funding selection, care category and forecasts: two source series; 2024–2025 forecast line segments dashed.
- All four hospitals × all three financial measures: expected point counts and latest values render; TOH nurse selector renders separately from employee headcount.
- Spending controls checked across all three care categories, both funding views, both dollar bases, total/per-resident measures, all five start years and forecasts on/off. Four staff/bed measure combinations render.
- Selected-view CSV downloaded and parsed: 12 physician records match the chosen two financing sources, period, nominal per-resident units and actual-only status. Source-cell references present.
- Local assets/download links resolve, HTML IDs are unique, shared integration files have no conflict markers and JavaScript syntax passes. The local preview remains available; no deployment performed.

Checks are a manual source snapshot, not an automated live-data monitor. Different accounting scopes and populations are explained in the page. Source dates do not imply all datasets end in the same year.

## ER and provider-access extension

- `check_access.py`: **700 source-record/hash reconciliations pass**. All 312 monthly rows match their raw API record; each site's separately returned Ontario comparator agrees with the Ontario export; latest first-assessment means match the independent site comparison table. All 30 annual rows match FAO accessible tables and the partial-year flag.
- All 11 provider estimates reconcile to original CCHS CSV or CIHI workbook rows; confidence limits contain the point estimates and complement/reverse correctly for the without-provider view. Age scopes and all specified definition/collection breaks are asserted.
- The original 514 source checks still pass after the chart extension.
- All 30 combinations of five Ottawa ER sites × two statistics × three full-stay groups: 26 points in each comparison chart, no NaN paths or visible data-error panel. Both annual history groups render 15 points with one dashed segment and an explicitly labelled partial endpoint.
- Historical provider comparison renders eight points, eight uncertainty whiskers and four line segments; the two 2021/22 points remain disconnected. Recent Ontario adult view renders three points/whiskers and zero connected segments.
- Four provider view/measure combinations pass; with-provider axes stop at 100%. Keyboard Enter selects an ER point and updates its readout.
- Expanded monthly tables, annual history and provider tables: 320/390/768/1240 CSS-pixel widths × all three themes pass without document overflow, invalid paths or visible error panels. All nine charts render with annual history open.
- Browser CSV downloads match the local exports exactly: 312 monthly ER records and 11 provider-access estimates. No browser JavaScript errors. Local anchors/assets/downloads and JS syntax pass.

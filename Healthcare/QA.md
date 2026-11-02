# Healthcare verification — November 2, 2026

## Source/data checks

- `python Healthcare/scripts/check_data.py`: **514 source/value checks pass**.
- All 459 calculated per-resident spending values match CIHI’s separate published per-resident tables (tolerance $0.00001).
- Every printed expense component subtotal reconciles in both current and comparator columns of all 14 hospital financial statements. Derived expenses retain separately reported building, parking and explicit wage costs.
- All source-file SHA-256 hashes match; 459 distinct spending keys, 10 workforce years, 28 financial years and six staffing years.
- 2024/2025 spending flags match the forecast convention; 2023-dollar adjustment equals nominal in the reference year.
- Visually inspected rendered full statement pages: TOH 2026, CHEO 2024, QCH 2024 and Montfort 2024, including below-subtotal adjustments. Rendered PNGs are in ignored/untracked `output/healthcare/`, not required by the page.

## Browser checks

- Local server responds HTTP 200; no page JavaScript errors.
- Initial five charts render; hospital selection with missing staffing intentionally renders four charts plus an explicit unavailable panel.
- Final 320, 390, 768 and 1240 CSS-pixel widths × light, dark and colour-blind themes: no document overflow, header-control overlap or visible data-error panel. Chart paths checked for NaN during control testing. Shared author credit included; duplicate header home link hidden on phones.
- Public/private funding selection, care category and forecasts: two source series; 2024–2025 forecast line segments dashed.
- All four hospitals × all three financial measures: expected point counts and latest values render; TOH nurse selector renders separately from employee headcount.
- Spending controls checked across all three care categories, both funding views, both dollar bases, total/per-resident measures, all five start years and forecasts on/off. Four staff/bed measure combinations render.
- Selected-view CSV downloaded and parsed: 12 physician records match the chosen two financing sources, period, nominal per-resident units and actual-only status. Source-cell references present.
- Local assets/download links resolve, HTML IDs are unique, shared integration files have no conflict markers and JavaScript syntax passes. The local preview remains available; no deployment performed.

Checks are a manual source snapshot, not an automated live-data monitor. Different accounting scopes and populations are explained in the page. Source dates do not imply all datasets end in the same year.

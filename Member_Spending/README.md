# MP & MPP spending

Page: [`spending.html`](spending.html). Static, with local JSON/JS data (also works when opened as a local file). Published November 1, 2026.

## Coverage

- House of Commons: five individual quarters, April–June 2025 to April–June 2026. Salaries are employees’ pay; travel, hospitality and contracts retain the official definitions. Report records include former members and vacancies. No annualization.
- Ontario: fiscal 2025–26 annual Individual Members’ Expenditures PDF, issued June 2026. 142 office records, 127 travel/accommodation records; 124 district boundaries. Records include closing costs for former members, and a part-year resignation. No current-party join is inferred.
- Own salary, pension costs, ministerial office spending and separately reported party-leader/House-officer expenses are outside scope. Federal and provincial periods and categories differ.

## Method

Ontario column positions are extracted from the landscape PDF with pdfplumber. Original PDF pages 2 and 10 were rendered and visually checked. Every monetary column is reconciled to its printed total. Individual rounded rows produce column differences of up to $8. Published office grand total is $53,656,360; travel/accommodation total is $3,651,861. The dashboard sums the individual rounded records, rather than replacing those sums with the printed aggregate.

Toronto accommodation overages appear in both sections of the PDF, but only the office section includes them in its total. This page adds office grand total + travel/accommodation total; the accommodation category adds base accommodation + overage once. Category sums can differ from published individual totals by a few dollars due to independent rounding. The difference is retained per member.

Travel means the federal source category; Ontario defaults to residence–Queen’s Park travel (also includes committee travel), with options for all separately reported travel or Toronto accommodation. Some urban/northern/staff travel and hospitality remain bundled in Ontario office operations. These cannot be extracted separately from this source.

## Distance

- Elections Canada 2023 representation-order boundaries (343 shapes), with district codes joined to the official district-name list and its former/current-name table. This resolves 2026 renames and malformed/truncated DBF labels without fuzzy matching.
- Elections Ontario 2025 polling divisions, dissolved by electoral district (124 shapes).
- Geometric centroid in EPSG:3347; transformed to WGS84, with ellipsoidal geodesic distance to Parliament Hill (45.4218, −75.7009) or Queen’s Park (43.6624, −79.3917). These building reference coordinates are approximate. Display rounded to the nearest kilometre; downloads preserve 0.1 km.
- Not population-weighted; not actual routes, homes, trips or distance travelled. Northern geographic centres can be far from settlements. This is context, not an efficiency score. No dollars-per-kilometre ratio or fitted trend line.
- Federal April–June 2025 distance comparison is disabled because the election changed boundaries. Unmatched records retain missing distances. Federal vacancies and Ontario former-member closing costs are excluded from the scatter. Federal former/part-year records may remain: a name match does not establish service duration. No spending is removed from the rankings/downloads.

## Reproduce

Python packages: requests, beautifulsoup4, pdfplumber, geopandas, pyproj, shapely. Run from the repository root:

```powershell
python Member_Spending/scripts/build_data.py
python Member_Spending/scripts/test_data.py
node --check Member_Spending/spending.js
```

The builder reuses cached inputs. `--refresh` refetches the fixed report periods and geometry; it does not discover new periods automatically. Update the period list deliberately after checking source availability. `data/source-manifest.json` records source URLs and SHA-256 hashes; original federal HTML/CSV and Ontario PDF are retained in `data/sources/`. Large boundary ZIPs, extracted shapefiles and QA screenshots stay in ignored `tmp/`. A fresh build downloads geometry again.

`data/spending.csv` has one row per period/member/category. **The member total repeats on each category row; do not sum that column across categories.** Missing distance is blank. JSON retains source page/row references, rounding differences and travel subcategories.

## Interface

Legislature and period selectors; federal province/territory filter; accent-insensitive member/riding search; category ranking; selectable member breakdown; travel scatter with hover, click and keyboard selection; exact filtered table and CSV/JSON downloads. All three shared themes and narrow screens use the existing Ottawa Visuals styling.

## Verification · November 1, 2026

Six data checks pass: all federal CSV/category rows, selected Ontario PDF transcriptions and overage accounting, printed-column reconciliation, independently calculated spherical distance bounds, election-transition exclusions, and unique IDs/complete CSV exports. Builder assertions also enforce district and PDF row counts and individual rounding bounds.

Browser checks: both legislatures at 320, 390, 768 and 1280 px in light, dark and colour-blind themes (24 combinations), with no page overflow or overlapping KPI values. Phone and desktop travel charts visually reviewed. Member search, no-result/reset flow, Ontario accommodation selection, keyboard dot selection and the federal election-transition gap verified. Browser warning/error log was empty. Filters and selected members persist across theme changes. Source files are a snapshot; no scheduled refresh was configured. Published on GitHub Pages November 1, 2026.

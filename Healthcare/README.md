# Healthcare: money, staff & capacity

Page: [`healthcare.html`](healthcare.html). Static, buildless, shared Ottawa Visuals themes. Built locally November 2, 2026; publication pending. Schools are a separate follow-up.

## Coverage

| Data | Coverage | Source |
|---|---|---|
| Ontario spending | 1975–2025; 2024 and 2025 forecasts, optional in the page | CIHI NHEX 2025, D2/D3/D4 Ontario sheets |
| Hospital staff and beds | 2014–15 to 2023–24 | CIHI Spending Trends in Health Service Delivery 2025, underlying FTE and staffed-bed tables |
| TOH, CHEO, QCH financials | Fiscal 2018–19 to 2025–26 | Paired audited statements ending 2020/2022/2024/2026 |
| Montfort financials | Fiscal 2022–23 to 2025–26 | Paired audited statements ending 2024/2026 |
| TOH + Heart Institute staffing | Fiscal 2020–21 to 2025–26 | Historical accessible annual reports and dated fast-fact pages |
| ER assessment and length of stay | Monthly August 2025–August 2026, five Ottawa sites + Ontario | Current Ontario Health public reporting export; mean, 90th percentile and visit counts |
| Longer ER history | Fiscal 2008–09 to 2022–23; final year April–November only | FAO March 2023 accessible tables, Figures 20 and 21; separate reporting vintage |
| Historical regular-provider access | Pooled 2015/16, 2017/18, 2019/20, 2021/22; Ottawa and Ontario, ages 12+ | StatCan CCHS archived Table 13-10-0113-01 |
| Recent Ontario provider access | 2023, 2024 and 2025; adults 18+ | CIHI indicator 880; separate snapshots with changed definitions |

459 spending observations (51 years × three care categories × three financing scopes), 10 provincial workforce years, 28 hospital financial years, six local headcount years. No figures are interpolated. The page defaults to Ontario-government hospital funding per resident, adjusted to 2023 health-price dollars, with forecasts off.

Access extension: 312 monthly ER records, 30 annual ER observations and 11 provider-access estimates. Separate `data/access-data.js` and `data/access.json` keep access snapshots distinct from the original finance/workforce data.

## ER and primary-care method

- Monthly ER API calls are traced from Ontario Health's current page scripts. `ResultType=PIA` is first assessment by a doctor, nurse practitioner or dentist; `A` is admitted full stay; `NAH` and `L` are high-/low-urgency non-admitted full stays. `showOnlyLatestPeriod=false` returns 13 months, not an unrestricted history. No undocumented date parameters or extrapolation are used.
- The directory's latest first-assessment comparison provides site IDs. Sites are TOH Civic and General, CHEO, Queensway Carleton and Montfort. Hospital organizations in the financial explorer and ER sites are different entities/scopes; CHEO's patient mix is pediatric. Ontario comparisons are not case-mix adjusted rankings.
- Means, 90th percentiles and visit counts are preserved directly; no averages of hospital means or monthly percentile averaging. Current exports include the December 2025 reporting expansion (43 sites); do not splice earlier exports with this vintage.
- The FAO annual history is a separate view using exact accessible source tables. Both all-patient and admitted-patient mean lengths of stay are available. 2022–23 covers April–November 2022 only and is marked with a dashed segment/open point. No connection is drawn across the gap to current monthly data.
- Historical provider access is broader than family-doctor-only attachment and includes regular healthcare providers under the survey definition. Non-response categories are excluded. The survey's 2015 health-region boundaries identify Ottawa; these are not Champlain or Ontario Health East. The original percent, 95% CI limits, weighted counts, vector/coordinate and source flags are retained. The current replacement table (13-10-0972-01) does not supply this provider indicator; the archived table remains the source.
- Without-provider percentage = 100 − has-provider percentage. Confidence limits reverse under this complement: lower_without = 100 − upper_has; upper_without = 100 − lower_has. Pandemic collection disruption affects 2019/20; 2021/22 combines different collection strategies/response rates and is separated by a line break.
- Recent Ontario adult snapshots use ages 18+, not 12+. CIHI's definition lists specialists in 2023, removes that listed category in 2024, and changes to primary-care professionals/teams excluding private-pay models in 2025. Each point is disconnected. No change percentage or spliced long trend is calculated across these definition/age breaks. CIHI weighted counts describe the covered survey population, not all Ontario residents.
- This does not establish current Ottawa family-doctor attachment, Health Care Connect wait-list size, appointment timeliness, or the effect of funding changes on access.

## Sources and definitions

- [CIHI NHEX](https://www.cihi.ca/en/national-health-expenditure-trends/nhex-trends-data): source cells and sheet names in the spending CSV. D4 provincial government is a subset of D3 all-public funding; never add them. D2 private funding describes the payer, not provider ownership. All-health includes capital; the hospital category has a different scope.
- [CIHI hospital workforce](https://www.cihi.ca/en/spending-trends-in-health-service-delivery): `FTE data` filtered to `ON`, `Calculated FTEs`, `Hospital`, `All`; use `ttl_hours`, already calculated in FTE units despite the column name. `tbD data` filtered to staffed-and-operating beds, Ontario. Acute and all-bed totals remain separate.
- CIHI Appendix D.1 population for calendar-year spending and D.2 for fiscal-year staff/bed rates. Appendix B.3 Ontario total-health implicit price index for a common price adjustment. Our rates use this edition’s population denominator and can differ from other CIHI products or older vintages. Not consumer CPI.
- Ottawa finances: non-consolidated TOH/Montfort, hospital statements for QCH, CHEO–Ottawa Children’s Treatment Centre for CHEO. Full URLs and SHA-256 hashes in [`source-manifest.json`](data/source-manifest.json); source pages and current/prior-year columns are attached to financial rows.
- The government-funding line is the named line in each statement. It excludes public revenue recorded in other categories, including QCH’s separately listed OHIP line. It is not total provincial payments and must not be used to infer a private-funding share or deficit.
- Statement expenses = printed expense subtotal + separately presented building/parking expenses + explicit separately reported retroactive wage costs. All components retained in the CSV. Montfort’s net prior-years adjustment is not attributed to expenses or funding. Compensation is the named line, before separately reported retroactive wages; CHEO has compensation embedded in other programs that this line does not capture.
- TOH headcounts explicitly include the University of Ottawa Heart Institute; financial statements here are TOH non-consolidated. No cost-per-worker calculation. Nurse headcounts overlap employee counts. No physicians added to employment.
- The four hospitals are a selected set, not all Ottawa providers. Catchments extend beyond Ottawa. No municipal spending-per-resident estimate is derived from hospital totals.

## Rebuild

Python dependencies: `requests`, `truststore`, `beautifulsoup4`, `openpyxl`, `pymupdf`. Truststore uses the OS certificate store; certificate verification stays enabled.

From the repository root, run these commands in order:

```powershell
python Healthcare/scripts/fetch_sources.py
python Healthcare/scripts/fetch_hospitals.py
python Healthcare/scripts/fetch_staffing.py
python Healthcare/scripts/build_hospitals.py
python Healthcare/scripts/build_data.py
python Healthcare/scripts/check_data.py
node --check Healthcare/healthcare.js
python Healthcare/scripts/build_access.py
python Healthcare/scripts/check_access.py
```

Downloads are cached in ignored `data/raw/`. The tracked manifest, compact excerpts and exports retain provenance; large original files stay outside Git. To refresh an original, remove that named cached file first and review the new edition before rebuilding. Refreshing these scripts is deliberately manual; they do not silently adopt a new release.

`build_hospitals.py` contains reviewed source-line transcription, not a general-purpose PDF scraper. When updating it, inspect complete statement pages and footnotes, retain original units and comparator-year labels, and update the component reconciliations. Source-link discovery can change when hospitals migrate websites; verify download errors before updating paths. A Montfort index HTTP error does not prevent retrieval of the already verified direct statement URLs.

The bundled `data/page-data.js` supports direct `file://` opening as well as GitHub Pages. No data API or chart CDN is required at view time; Google Fonts has system fallbacks. Exact tables and source CSV/JSON provide alternatives to the charts.

## Verification and limits

See [`QA.md`](QA.md). Source checks cover published per-resident spending, all audited expense component sums, source hashes, forecast status, coverage and distinct keys. Browser checks cover controls, missing data, phone/tablet/desktop and all three themes.

Remaining gaps: complete government payments and employees by private-clinic ownership; comparable historical staffing for CHEO/QCH/Montfort; other Ottawa providers; current comparable Ottawa provider-access estimates; historical monthly ER data outside the returned 13 months; regional nursing/physician series and appointment access. These are not filled with estimates or zeros. No claim that spending changes cause staffing, quality or access changes. Access sources have their own URL/hash manifest, `data/access-source-manifest.json`; cached originals remain ignored.

# Sutcliffe’s original 2022 promises

First topic: annual municipal property-tax increases, 2013–2026, with Ottawa CPI inflation. The 2022 promise comparison applies only to 2023–2026. Reviewed October 24, 2026. No 2026 campaign commitments included.

## Data and methodology

`data/property-tax.json` is the manually reviewed source of truth: annual increases, commitment type, source URLs, document locations and evidence limitations. `scripts/build_property_tax.py` generates the standalone `promises.html` and downloadable CSV using Python’s standard library. No browser fetch or chart dependency; content remains readable offline and without JavaScript.

Rebuild: `python Promises/scripts/build_property_tax.py`. Validate: `python Promises/scripts/check_property_tax.py` and `node --check Promises/promises.js`.

The chart uses vertical SVG bars (years on x, increases on y), horizontal 2% and 2.5% references within 2023–2026, and an optional CPI line on the same percentage axis. Controls switch between all years and Sutcliffe’s four budgets; `range=term` and `inflation=0` are shareable URL parameters. All years remain in the exact table/CSV. Native SVG titles give point values; the table provides touch/keyboard access. Narrow screens scroll horizontally.

Annual/Cumulative controls use `measure=cumulative` in the URL. Cumulative taxes compound each annual budget rate: `(product(1 + rate/100) − 1) × 100`, starting from 2012 for the full history or 2022 for Sutcliffe’s budgets. This is an illustrative tax index, not a household bill or total levy revenue. Cumulative CPI uses `(endpoint index / baseline annual index − 1) × 100`. The 2026 endpoint is the Jan–Sep CPI average; earlier endpoints are annual averages. Do not compound 2026’s matched-period YTD rate onto the full 2025 annual index. The graph labels this difference in endpoint coverage. Annual promise references are hidden in cumulative mode. `data/property-tax-cumulative.csv` and a second exact table retain both baseline series; the original annual CSV is unchanged.

Compare the adopted overall municipal increase with the 2.5% upper benchmark. The original framework limits 2023–24 to 2–2.5% and targets the same in 2025–26. Do not turn the latter into an unconditional four-year cap. Values are 2.5%, 2.5%, 3.9%, 3.75%; gaps are 0, 0, 1.4, 1.25 percentage points.

The campaign source is contemporary CityNews coverage; the original archived platform has not been obtained. Its opening paragraph has a typo, but headline and detailed framework agree. The City’s own historical budget comparison table supplies 2013–2023: 2.09%, 1.91%, 2% for 2015–2018, 3% for 2019–2022 and 2.5% for 2023. Earlier years receive no promise assessment. 2024–25 use council members’ contemporary adoption accounts; 2026 uses the City adoption announcement. Source notes remain visible on the page.

`data/inflation.json` retains Statistics Canada annual CPI levels for 2012–2025, January–September monthly observations for 2025/2026, calculated changes and API response hashes. Geography: Ottawa-Gatineau, Ontario part; all-items, not seasonally adjusted. Annual formula: `(CPI(year) / CPI(year−1) − 1) × 100`. 2026 uses `(mean(Jan–Sep 2026) / mean(Jan–Sep 2025) − 1) × 100`, yielding approximately 2.6%. Do not compare a partial-year mean against the previous full-year mean. The dashed segment and hollow point flag the partial year. CPI is a consumer-price benchmark, not a municipal cost index; same-year inflation was not fully known at budget adoption.

To deliberately refresh CPI: `python Promises/scripts/fetch_cpi.py`, review the cutoff and inputs, then rebuild and validate. The fetch script stops if the 2026 published cutoff differs from September. This is separate from Budget’s inflation factors and does not modify that page’s inputs.

The metric is not total levy revenue growth, an individual bill, a statutory tax-rate series or an inflation-adjusted amount. Distinguish transit’s levy from transit fares. Excludes separate fees, provincial education taxes and assessment changes. Avoid cumulative household estimates from these rounded overall figures.

## Adding topics

Add only after separately verifying the 2022 wording, deadline, baseline and outcome series. User’s next topics: transit fares, bus KPIs, housing. Other candidates: building energy upgrades, EV chargers, Stage 2 LRT, municipal savings, ByWard Market safety and suburban dog parks. Road clearing and traffic calming need more source reconciliation. No statuses assigned to unresearched topics.

## Verification — October 24, 2026

Headless Edge / Playwright: 390, 768 and 1440 px widths in light, dark and colour-blind themes (nine combinations), no document overflow or page errors; 14 history bars, four term bars and 14 table rows. Range and inflation controls, URL persistence, local download/navigation links, file:// controls and no-JavaScript chart checked. Visually inspected phone/light (including scroll to recent years) and desktop/dark renders. Independent offline checks reconcile annual/YTD CPI calculations and CSV values, including blank promise benchmarks for historical years. No collector files changed.

Cumulative extension: 36 viewport/theme/range/measure combinations checked; one chart visible at a time, annual references absent in cumulative mode, URL restoration, CPI visibility, CSV download and offline switching pass. All 18 cumulative observations reconcile against independent compounding and direct CPI-ratio calculations; the two-year 2023–24 tax change is 5.0625%, confirming rates are not summed. Desktop cumulative rendering visually reviewed.

# Sutcliffe’s original 2022 promises

First topic: annual municipal property-tax increases, 2023–2026. Reviewed October 24, 2026. No 2026 campaign commitments included.

## Data and methodology

`data/property-tax.json` is the manually reviewed source of truth: annual increases, commitment type, source URLs, document locations and evidence limitations. `scripts/build_property_tax.py` generates the standalone `promises.html` and downloadable CSV using Python’s standard library. No browser fetch or chart dependency; content remains readable offline and without JavaScript.

Rebuild: `python Promises/scripts/build_property_tax.py`.

Compare the adopted overall municipal increase with the 2.5% upper benchmark. The original framework limits 2023–24 to 2–2.5% and targets the same in 2025–26. Do not turn the latter into an unconditional four-year cap. Values are 2.5%, 2.5%, 3.9%, 3.75%; gaps are 0, 0, 1.4, 1.25 percentage points.

The campaign source is contemporary CityNews coverage; the original archived platform has not been obtained. Its opening paragraph has a typo, but headline and detailed framework agree. 2023 final adoption is confirmed by CBC’s 2026 review (Yahoo republication), with the City’s draft as a primary-source cross-check. 2024–25 use council members’ contemporary adoption accounts; 2026 uses the City adoption announcement. Source notes remain visible on the page.

The metric is not total levy revenue growth, an individual bill, a statutory tax-rate series or an inflation-adjusted amount. Distinguish transit’s levy from transit fares. Excludes separate fees, provincial education taxes and assessment changes. Avoid cumulative household estimates from these rounded overall figures.

## Adding topics

Add only after separately verifying the 2022 wording, deadline, baseline and outcome series. User’s next topics: transit fares, bus KPIs, housing. Other candidates: building energy upgrades, EV chargers, Stage 2 LRT, municipal savings, ByWard Market safety and suburban dog parks. Road clearing and traffic calming need more source reconciliation. No statuses assigned to unresearched topics.

## Verification — October 24, 2026

Headless Edge / Playwright: 390, 768 and 1440 px widths in light, dark and colour-blind themes (nine combinations), no document overflow or page errors; four chart and table rows; local download/navigation links resolve; homepage entry present; file:// content available. Visually inspected phone/light and desktop/dark renders; moved the exact table into a disclosure with horizontal scrolling to avoid compressed mobile columns. Source URLs and values manually reviewed. No collector files changed.

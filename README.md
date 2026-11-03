# Ottawa Visuals

**Live site:** https://ottawavisuals.github.io/Ottawa-Visuals/
**Project tracker:** [`tracker.html`](tracker.html) — a project atlas: status, build timeline, data sources, pipeline/methodology write-ups and a checkbox list of assumptions to verify, per sub-project.

A static site served straight from `index.html` on GitHub Pages (no Jekyll — see
`.nojekyll`). Each report is a standalone HTML page; the homepage shows one tile per report linking to it
(old `#report-<id>` links redirect to the page).
Deployed reports may be deliberately unlisted: `hidden` in `ALL_REPORTS` controls
homepage visibility without removing the page or its existing links.

Each sub-project lives in its own folder (data, scripts, README) with its
page inside that folder — e.g. `Mortgage/mortgage.html`, `Weather/weather.html`.
A thin redirect stub is kept at the old root path (e.g. `/mortgage.html`) for
any bookmarked or shared links.

## Sub-projects
| Folder | What it is |
|---|---|
| [`Education/`](Education/README.md) | Ontario school spending/funding and reported elementary class sizes, Ottawa-area boards and searchable school-name histories, suppression ranges and CSV/JSON ([`education.html`](Education/education.html)); published November 3, 2026 |
| [`Healthcare/`](Healthcare/README.md) | Ontario funding, hospital staffing/beds, four Ottawa hospital financial histories, ER waits and regular-provider access with uncertainty, source scopes and downloads ([`healthcare.html`](Healthcare/healthcare.html)); published November 3, 2026 |
| [`Member_Spending/`](Member_Spending/README.md) | Federal MP and Ontario MPP office spending by category; travel spending versus riding-centroid distance, exact values and downloads ([`spending.html`](Member_Spending/spending.html)); published November 1, 2026 |
| [`Wealth/`](Wealth/README.md) | Canada's wealth distribution: wealth shares and all available household-account quarters, SFS surveys, PBO top-wealth history and earlier studies back to 1970, source rows and downloads ([`wealth.html`](Wealth/wealth.html)) |
| [`Promises/`](Promises/README.md) | Sutcliffe’s original 2022 commitments and results: property taxes, transit fares, bus reliability, housing, Stage 2 LRT and ByWard Market safety; historical trends, targets and source notes ([`promises.html`](Promises/promises.html)) |
| [`Budget/`](Budget/README.md) | Ottawa budget: 2023–2026 expense changes; operating/capital/funding charts; Lansdowne 2.0; paramedic, transportation-condition and housing KPI series ([`budget.html`](Budget/budget.html)) |
| [`OPS/`](OPS/README.md) | Published OPS disciplinary records: unique officers, findings/dismissals, penalties, source links and separately listed upcoming hearings ([`ops.html`](OPS/ops.html)); manually reviewed partial snapshot |
| [`Mortgage/`](Mortgage/README.md) | Mortgage affordability calculator ([`mortgage.html`](Mortgage/mortgage.html)) |
| [`Weather/`](Weather/README.md) | Ottawa climate history dashboard ([`weather.html`](Weather/weather.html)) |
| [`Vehicles/`](Vehicles/README.md) | Road safety / vehicle-pedestrian impact calculator ([`road-safety.html`](Vehicles/road-safety.html)) |
| [`Ottawa_Elections/`](Ottawa_Elections/README.md) | Ward-by-ward municipal election results ([`ottawa_ward_elections.html`](Ottawa_Elections/ottawa_ward_elections.html)) |
| [`BC_Elections/`](BC_Elections/README.md) | BC 2026 preliminary initial-count maps and NDP/Green consolidation scenarios, with 2024 final results retained separately ([`BCelections.html`](BC_Elections/BCelections.html)); published November 1, 2026 |
| [`Alberta_Elections/`](Alberta_Elections/README.md) | Alberta 2023 riding map, vote-consolidation scenarios, turnout and source reconciliation ([`ABelections.html`](Alberta_Elections/ABelections.html)) |
| [`Ontario_Elections/`](Ontario_Elections/README.md) | Ontario provincial election + coalition scenarios ([`ONelections.html`](Ontario_Elections/ONelections.html)) |
| [`Ontario_Trials/`](Ontario_Trials/README.md) | How Ottawa court cases end: criminal and provincial/traffic outcomes, offence filters, calendar/non-calendar periods, count/share charts and downloads ([`courts.html`](Ontario_Trials/courts.html)) |
| [`PWHL/`](PWHL/README.md) | PWHL stats dashboard ([`pwhl.html`](PWHL/pwhl.html)) |
| [`Energy/`](Energy/README.md) | Geothermal feasibility (companion to the separate Energy repo) |
| [`Traffic/`](Traffic/README.md) | TomTom commute-time, parking and road-event collectors (feed RTO Watch), plus weekly City/Police road datasets behind the road-safety report [`stops.html`](Traffic/stops.html) (its Where tab replaced `roads.html`) and the impact calculator |
| [`OC_Transpo/`](OC_Transpo/README.md) | OC Transpo GTFS-RT + KPI collector (feeds RTO Watch), plus KPI history 2019–2026 extracted from Transit Committee reports ([`octranspo_kpis.html`](OC_Transpo/octranspo_kpis.html)) |
| [`RTO4/`](RTO4/README.md) | External datasets behind RTO Watch (311, IESO, volumes, GHG) |
| [`Ontario_Votes/`](Ontario_Votes/README.md) | Ontario Legislature divisions weighted by each MPP's election ballots ([`mpp_mandates.html`](mpp_mandates.html)); collected in the browser because ola.org blocks scripts |
| [`CityHall_Index/`](CityHall_Index/README.md) | eScribe committee/council meeting indexer; public decision search ([`cityhall.html`](cityhall.html), fed by `public/items.json`; [`council_mandates.html`](council_mandates.html) weights Council votes by councillors' 2022 ballots) |
| [`Tax/`](Tax/README.md) | Taxing the top: top income-tax rate since 1920 vs top-1% share, who grew in high- vs low-tax eras, donations by neighbourhood income ([`tax.html`](Tax/tax.html)) |
| [`Ontario_Costs/`](Ontario_Costs/README.md) | Ontario decisions the Auditor General / FAO costed or criticized, 2009–2024, each with what the figure measures ([`ontario_costs.html`](Ontario_Costs/ontario_costs.html)) |
| [`OilGas/`](OilGas/README.md) | Canada's oil & gas industry since 2002: profits, dividends, corporate income tax and jobs, in 2025 dollars ([`oilgas.html`](OilGas/oilgas.html)) |
| [`GovContracts/`](GovContracts/README.md) | Federal disclosed management-consulting contract values and 2019–2025 award-method charts with category/dollars/share controls ([`govcontracts.html`](govcontracts.html)); homepage link added Nov 3, 2026 |

[`rto.html`](rto.html) — **Ottawa RTO Watch**, the return-to-office page — sits at
the root because it draws on three folders at once: `Traffic/` and `OC_Transpo/`
for our own live collection, and `RTO4/` for everything published by others. See
[`RTO4_PLAN.md`](RTO4_PLAN.md) for the policy timeline and
[`RTO4/README.md`](RTO4/README.md) for what each dataset can and cannot prove.

`ghg_calculator.html`, `Comparator.html` and `dataset_prospector.html` are
standalone root-level tools not (yet) tied to a specific data folder.

## Edit points
- Home page tiles: `/index.html` (edit `ALL_REPORTS` near the bottom; `page` is the report's own page)
- Report pages: each sub-project's own folder (e.g. `Mortgage/mortgage.html`,
  `Weather/weather.html`) plus root-level standalone pages (`rto.html`,
  `ghg_calculator.html`, `Comparator.html`, `dataset_prospector.html`)
- Project status: `/tracker.html` and `/PROJECTS.md`
- About / footer copy: the `#about` and footer sections of `/index.html`
- Shared author credit: `assets/author-credit.js`, included once on each page
  using the shared site theme (including PWHL detail pages and previews). Adds
  “Built by Simon”, an author panel focused on public data and visualization,
  and root-relative report/contact destinations resolved from the script URL.
  The header button shortens or hides when space is tight; the footer credit
  remains. Mortgage's credit lives in its scrollable results column.
  Nov 1 checks: all 40 pages mounted the credit; representative phone layouts,
  theme contrast, close/Escape focus and nested links checked. Page content and
  report scripts otherwise unchanged.
- Contact: `#contact` in `/index.html` + `assets/contact.js`. Uses Energy's existing
  `https://energy.madeclear.ca/api/contact` service (GitHub Pages origin is
  allow-listed); the destination mailbox stays in Energy's server configuration.
  Name is optional; email/message are required. The v2 preview links to this form.
  Nov 1 check: live CORS preflight, browser validation, and mocked success/failure/
  duplicate-submit handling passed. No real email was sent during this check.
- Images: `/assets/img/`
- Report artwork: `assets/report-art.css` + [`assets/report-art/README.md`](assets/report-art/README.md); shared illustrations, homepage cards and decorative section markers for published report entry pages.
- Styles: inline in each page's `<style>` block, then overridden site-wide by
  `assets/site-theme.css` + `assets/site-theme.js` (Retrofit Explorer look: navy bar,
  cream, Fraunces, light/dark/colour-blind switch). Change brand colours there, not per page.
  `tracker.html`, `rto.html` and `dataset_prospector.html` keep their own token names but load it too.
  Shared theme CSS uses `?v=a11y-20261103`, JS uses `?v=share-20261103`;
  author credit uses `?v=audit-20261103`. The theme
  pill explicitly resets button padding, flex sizing and SVG dimensions. Report
  headers use a compact phone row; the homepage keeps its existing header layout.
  Author initialization waits for the theme control so its button consistently
  appears before the pill. Nov 1 checks: 13 report/detail phone headers at 390px,
  wealth/weather/mortgage at 320px, and three-mode selection on four reports.

## Chart sharing

Native canvas and SVG charts gain a **Share chart** button through
`assets/chart-sharing.js`, loaded by the shared theme. It previews a local PNG
with the current chart, selections, nearby legends/notes, report link and Ottawa
Visuals credit. Readers can download it, copy the image (supported browsers), or
copy a chart link. Nothing is uploaded. Clipboard failures retain the download
and a selectable link.

Links preserve existing report query parameters and jump to the chart; they do
not add filter-state persistence. Charts without a local source label refer to
the full report for sources and methods. This is a snapshot of the rendered
view, including its current theme/mobile layout; external embeds and Leaflet
maps are excluded. Animated Weather snapshots pause playback.

Optional `data-share-title`, `data-share-source` and `data-share-note` attributes
on the chart supply explicit export text. Chart.js snapshots temporarily use a
higher pixel ratio and restore the original chart dimensions and data. SVG
exports inline their paint/text styles to retain colours and hidden-series state.

Local checks (with the temporary dependencies described in `SITE_AUDIT.md` and
an HTTP server on port 8768): `node scripts/check_chart_sharing.cjs` and
`node scripts/check_chart_sharing_interactions.cjs`. Evidence stays in
`output/chart-sharing/`.

## Traffic report
[`Traffic/stops.html`](Traffic/stops.html) uses native charts and maps, with no
Power BI dependency. Source coverage, reproducible preparation and weekly refresh
are documented in [`Traffic/README.md`](Traffic/README.md).

## Notes
- Static site (no server).
- Keep large files out of the repo.

## Site audit
November 3, 2026: audit and follow-up fixes; 282 phone/desktop/theme cases pass automated accessibility checks. Keyboard access and chart value alternatives were also checked.
Coverage, screen-reader testing limits and repeat instructions: [SITE_AUDIT.md](SITE_AUDIT.md).

`assets/chart-accessibility.js` loads through the shared theme script. It supplies missing skip links and expandable chart values/series controls, retaining report-specific data tables where already present.

Catalogue sync, November 3, 2026: City Hall search and GovContracts added to the homepage; live/publication status and remaining work aligned with PROJECTS.md and tracker.html. Existing hidden reports remain unlisted.

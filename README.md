# Ottawa Visuals

**Live site:** https://ottawavisuals.github.io/Ottawa-Visuals/
**Project tracker:** [`tracker.html`](tracker.html) — a project atlas: status, build timeline, data sources, pipeline/methodology write-ups and a checkbox list of assumptions to verify, per sub-project.

A static site served straight from `index.html` on GitHub Pages (no Jekyll — see
`.nojekyll`). Each report is a standalone HTML page; the homepage shows one tile per report linking to it
(old `#report-<id>` links redirect to the page).
Each sub-project lives in its own folder (data, scripts, README) with its
page inside that folder — e.g. `Mortgage/mortgage.html`, `Weather/weather.html`.
A thin redirect stub is kept at the old root path (e.g. `/mortgage.html`) for
any bookmarked or shared links.

## Sub-projects
| Folder | What it is |
|---|---|
| [`Wealth/`](Wealth/README.md) | Canada's wealth distribution: five wealth quintiles, 2010–2025 Q4 shares, separate PBO top-1% context, source rows and downloads ([`wealth.html`](Wealth/wealth.html)) |
| [`Promises/`](Promises/README.md) | Sutcliffe’s original 2022 commitments and results: property taxes, transit fares, bus reliability, housing, Stage 2 LRT and ByWard Market safety; historical trends, targets and source notes ([`promises.html`](Promises/promises.html)) |
| [`Budget/`](Budget/README.md) | Ottawa budget: 2023–2026 expense changes; operating/capital/funding charts; Lansdowne 2.0; paramedic, transportation-condition and housing KPI series ([`budget.html`](Budget/budget.html)) |
| [`OPS/`](OPS/README.md) | Published OPS disciplinary records: unique officers, findings/dismissals, penalties, source links and separately listed upcoming hearings ([`ops.html`](OPS/ops.html)); manually reviewed partial snapshot |
| [`Mortgage/`](Mortgage/README.md) | Mortgage affordability calculator |
| [`Weather/`](Weather/README.md) | Ottawa climate history dashboard |
| [`Vehicles/`](Vehicles/README.md) | Road safety / vehicle-pedestrian impact calculator |
| [`Ottawa_Elections/`](Ottawa_Elections/README.md) | Ward-by-ward municipal election results |
| [`Ontario_Elections/`](Ontario_Elections/README.md) | Ontario provincial election + coalition scenarios |
| [`Ontario_Trials/`](Ontario_Trials/README.md) | How Ottawa court cases end: criminal and provincial/traffic outcomes, offence filters, calendar/non-calendar periods, count/share charts and downloads ([`courts.html`](Ontario_Trials/courts.html)) |
| [`PWHL/`](PWHL/README.md) | PWHL stats dashboard |
| [`Energy/`](Energy/README.md) | Geothermal feasibility (companion to the separate Energy repo) |
| [`Traffic/`](Traffic/README.md) | TomTom commute-time, parking and road-event collectors (feed RTO Watch), plus weekly City/Police road datasets behind the road-safety report [`stops.html`](Traffic/stops.html) (its Where tab replaced `roads.html`) and the impact calculator |
| [`OC_Transpo/`](OC_Transpo/README.md) | OC Transpo GTFS-RT + KPI collector (feeds RTO Watch), plus KPI history 2019–2026 extracted from Transit Committee reports ([`octranspo_kpis.html`](OC_Transpo/octranspo_kpis.html)) |
| [`RTO4/`](RTO4/README.md) | External datasets behind RTO Watch (311, IESO, volumes, GHG) |
| [`Ontario_Votes/`](Ontario_Votes/README.md) | Ontario Legislature divisions weighted by each MPP's election ballots ([`mpp_mandates.html`](mpp_mandates.html)); collected in the browser because ola.org blocks scripts |
| [`CityHall_Index/`](CityHall_Index/README.md) | eScribe committee/council meeting indexer; public decision search ([`cityhall.html`](cityhall.html), fed by `public/items.json`; [`council_mandates.html`](council_mandates.html) weights Council votes by councillors' 2022 ballots) |
| [`Tax/`](Tax/README.md) | Taxing the top: top income-tax rate since 1920 vs top-1% share, who grew in high- vs low-tax eras, donations by neighbourhood income ([`tax.html`](Tax/tax.html)) |
| [`Ontario_Costs/`](Ontario_Costs/README.md) | Ontario decisions the Auditor General / FAO costed or criticized, 2009–2024, each with what the figure measures ([`ontario_costs.html`](Ontario_Costs/ontario_costs.html)) |
| [`OilGas/`](OilGas/README.md) | Canada's oil & gas industry since 2002: profits, dividends, corporate income tax and jobs, in 2025 dollars ([`oilgas.html`](OilGas/oilgas.html)) |
| [`GovContracts/`](GovContracts/README.md) | Federal Proactive Disclosure contracts — management-consulting spend ([`govcontracts.html`](govcontracts.html)) |

[`rto.html`](rto.html) — **Ottawa RTO Watch**, the return-to-office page — sits at
the root because it draws on three folders at once: `Traffic/` and `OC_Transpo/`
for our own live collection, and `RTO4/` for everything published by others. See
[`RTO4_PLAN.md`](RTO4_PLAN.md) for the policy timeline and
[`RTO4/README.md`](RTO4/README.md) for what each dataset can and cannot prove.

`ghg_calculator.html`, `Comparator.html` and `dataset_prospector.html` are
standalone root-level tools not (yet) tied to a specific data folder.

## Edit points
- Home page tiles: `/index.html` (edit the `REPORTS` array near the bottom; `page` is the report's own page)
- Report pages: each sub-project's own folder (e.g. `Mortgage/mortgage.html`,
  `Weather/weather.html`) plus root-level standalone pages (`rto.html`,
  `ghg_calculator.html`, `Comparator.html`, `dataset_prospector.html`)
- Project status: `/tracker.html` and `/PROJECTS.md`
- About / footer copy: the `#about` and footer sections of `/index.html`
- Images: `/assets/img/`
- Styles: inline in each page's `<style>` block, then overridden site-wide by
  `assets/site-theme.css` + `assets/site-theme.js` (Retrofit Explorer look: navy bar,
  cream, Fraunces, light/dark/colour-blind switch). Change brand colours there, not per page.
  `tracker.html`, `rto.html` and `dataset_prospector.html` keep their own token names but load it too.

## Traffic report
[`Traffic/stops.html`](Traffic/stops.html) uses native charts and maps, with no
Power BI dependency. Source coverage, reproducible preparation and weekly refresh
are documented in [`Traffic/README.md`](Traffic/README.md).

## Notes
- Static site (no server).
- Keep large files out of the repo.

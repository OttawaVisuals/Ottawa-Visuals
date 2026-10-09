# Ottawa Visuals

**Live site:** https://ottawavisuals.github.io/Ottawa-Visuals/
**Project tracker:** [`tracker.html`](tracker.html) — a project atlas: status, build timeline, data sources, pipeline/methodology write-ups and a checkbox list of assumptions to verify, per sub-project.

A static site served straight from `index.html` on GitHub Pages (no Jekyll — see
`.nojekyll`). Each report is a standalone HTML page embedded in the homepage.
Each sub-project lives in its own folder (data, scripts, README) with its
page inside that folder — e.g. `Mortgage/mortgage.html`, `Weather/weather.html`.
A thin redirect stub is kept at the old root path (e.g. `/mortgage.html`) for
any bookmarked or shared links.

## Sub-projects
| Folder | What it is |
|---|---|
| [`Mortgage/`](Mortgage/README.md) | Mortgage affordability calculator |
| [`Weather/`](Weather/README.md) | Ottawa climate history dashboard |
| [`Vehicles/`](Vehicles/README.md) | Road safety / vehicle-pedestrian impact calculator |
| [`Ottawa_Elections/`](Ottawa_Elections/README.md) | Ward-by-ward municipal election results |
| [`Ontario_Elections/`](Ontario_Elections/README.md) | Ontario provincial election + coalition scenarios |
| [`Ontario_Trials/`](Ontario_Trials/README.md) | Ontario Court traffic cases (exploration) |
| [`PWHL/`](PWHL/README.md) | PWHL stats dashboard |
| [`Energy/`](Energy/README.md) | Geothermal feasibility (companion to the separate Energy repo) |
| [`Traffic/`](Traffic/README.md) | TomTom commute-time, parking and road-event collectors (feed RTO Watch), plus weekly City/Police road datasets behind [`roads.html`](Traffic/roads.html) and the road-safety page |
| [`OC_Transpo/`](OC_Transpo/README.md) | OC Transpo GTFS-RT + KPI collector, feeds RTO Watch |
| [`RTO4/`](RTO4/README.md) | External datasets behind RTO Watch (311, IESO, volumes, GHG) |
| [`CityHall_Index/`](CityHall_Index/README.md) | eScribe committee/council meeting indexer |
| [`Tax/`](Tax/README.md) | Taxing the top: top income-tax rate since 1920 vs top-1% share, who grew in high- vs low-tax eras, donations by neighbourhood income ([`tax.html`](Tax/tax.html)) |
| [`GovContracts/`](GovContracts/README.md) | Federal Proactive Disclosure contracts — consulting spend / in-house duplication (exploration) |

[`rto.html`](rto.html) — **Ottawa RTO Watch**, the return-to-office page — sits at
the root because it draws on three folders at once: `Traffic/` and `OC_Transpo/`
for our own live collection, and `RTO4/` for everything published by others. See
[`RTO4_PLAN.md`](RTO4_PLAN.md) for the policy timeline and
[`RTO4/README.md`](RTO4/README.md) for what each dataset can and cannot prove.

`ghg_calculator.html`, `Comparator.html` and `dataset_prospector.html` are
standalone root-level tools not (yet) tied to a specific data folder.

## Edit points
- Home page + report list: `/index.html` (edit the `REPORTS` array near the bottom)
- Report pages: each sub-project's own folder (e.g. `Mortgage/mortgage.html`,
  `Weather/weather.html`) plus root-level standalone pages (`rto.html`,
  `ghg_calculator.html`, `Comparator.html`, `dataset_prospector.html`)
- Project status: `/tracker.html` and `/PROJECTS.md`
- About / footer copy: the `#about` and footer sections of `/index.html`
- Images: `/assets/img/`
- Styles: inline in each page's `<style>` block, then overridden site-wide by
  `assets/site-theme.css` + `assets/site-theme.js` (Retrofit Explorer look: navy bar,
  cream, Fraunces, light/dark/colour-blind switch). Change brand colours there, not per page.
  `tracker.html`, `rto.html` and `dataset_prospector.html` don't load it yet.

## Power BI
Power BI → File → **Publish to web** → paste the `app.powerbi.com/view?...` URL
into the relevant report's `embedUrl` in `index.html`.

## Notes
- Static site (no server).
- Keep large files out of the repo.

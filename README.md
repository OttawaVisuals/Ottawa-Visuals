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
| [`Traffic/`](Traffic/README.md) | TomTom commute-time collector, feeds RTO Watch |
| [`OC_Transpo/`](OC_Transpo/README.md) | OC Transpo GTFS-RT + KPI collector, feeds RTO Watch |
| [`CityHall_Index/`](CityHall_Index/README.md) | eScribe committee/council meeting indexer |

`rto.html`, `ghg_calculator.html`, `Comparator.html` and `dataset_prospector.html`
are standalone root-level tools not (yet) tied to a specific data folder.

## Edit points
- Home page + report list: `/index.html` (edit the `REPORTS` array near the bottom)
- Report pages: each sub-project's own folder (e.g. `Mortgage/mortgage.html`,
  `Weather/weather.html`) plus root-level standalone pages (`rto.html`,
  `ghg_calculator.html`, `Comparator.html`, `dataset_prospector.html`)
- Project status: `/tracker.html` and `/PROJECTS.md`
- About / footer copy: the `#about` and footer sections of `/index.html`
- Images: `/assets/img/`
- Styles: inline in each page's `<style>` block

## Power BI
Power BI → File → **Publish to web** → paste the `app.powerbi.com/view?...` URL
into the relevant report's `embedUrl` in `index.html`.

## Notes
- Static site (no server).
- Keep large files out of the repo.

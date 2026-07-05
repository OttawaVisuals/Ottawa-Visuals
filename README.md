# Ottawa Visuals

**Live site:** https://ottawavisuals.github.io/Ottawa-Visuals/

A static site served straight from `index.html` on GitHub Pages (no Jekyll — see
`.nojekyll`). Each report is a standalone HTML page embedded in the homepage.

## Edit points
- Home page + report list: `/index.html` (edit the `REPORTS` array near the bottom)
- Report pages: `/*.html` (e.g. `road-safety.html`, `mortgage.html`, `pwhl.html`) and `/Ontario_Elections/ONelections.html`
- About / footer copy: the `#about` and footer sections of `/index.html`
- Images: `/assets/img/`
- Styles: inline in each page's `<style>` block

## Power BI
Power BI → File → **Publish to web** → paste the `app.powerbi.com/view?...` URL
into the relevant report's `embedUrl` in `index.html`.

## Notes
- Static site (no server).
- Keep large files out of the repo.

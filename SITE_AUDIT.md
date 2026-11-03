# Site audit — November 3, 2026

Status: audit completed locally; first fixes applied. Remaining contrast work is
listed below. This is not a WCAG conformance certification or a deployment check.

## Coverage and method

- 47 non-meta-refresh HTML entry points, including reports, PWHL detail pages,
  internal tools and v2 previews; retained source HTML under `data/` excluded.
- 188 browser cases: 1280px light, plus 320px light/dark/colour-blind. This is
  a stricter phone width than most current phones. Pages without the shared
  theme do not acquire theme support merely because a preference was supplied.
- Playwright with installed Chrome; local HTTP serving; rendered document width,
  uncaught JavaScript errors, failed HTTP responses, visible broken images and
  rendered local links checked. Axe-core WCAG 2 A/AA and 2.1 AA rules run on all
  188 cases after the initial baseline.
- Additional 390px checks on Home, Mortgage, Weather, Courts, Education and PWHL
  Superlatives: actual theme-button clicks, author open/Escape closing, header
  overlap and generated same-page fragment links. Screenshots reviewed for the
  homepage, Courts and Mortgage; targeted phone screenshots retained locally.
- Changed tables and initially incomplete asset loads received targeted rechecks.
  The audit runner retries incomplete local styles/images before reporting layout
  defects. Raw evidence and screenshots: `output/site-audit/` (not committed).
- Compact findings and remaining examples: `audits/site-audit-2026-11-03.json`.

## Verified result

After targeted rechecks: all 188 cases have no document-width overflow, visible
broken images or uncaught JavaScript errors. Observed internal file destinations
resolve. Remaining automated findings are colour contrast only; exact cases and
examples are retained in the findings JSON.

## Fixes included

- Mortgage and Weather: corrected six broken header destinations.
- Mortgage: named static inputs and generated desktop/mobile spending inputs;
  Weather: named the climate-spiral slider; four election pages: named map mode.
- Tracker: connected all 46 assumption checkboxes to their visible wording.
- Keyboard access: focusable, named scroll regions for flagged results tables,
  PWHL standings/bracket/recap, transit routes and tracker tables/timeline.
- Phone layout: contained Tax/Oil & Gas/Weather chart grids, wrapped court-source
  links and contract category controls, contained tracker code/chips/table, and
  kept homepage navigation and hero content usable at narrow widths.
- Shared author button now considers brand overlap when shortening/hiding.
- Shared light/colour-blind muted text and accent colours have stronger contrast;
  header subtitles remain readable; prose links have underlines.
- Changed shared CSS/author-script references use `audit-20261103` cache versions.

## Remaining work, in priority order

1. **Contrast on RTO Watch, tracker and Dataset Prospector.** These pages use
   additional local colour tokens; changing the shared theme does not resolve all
   muted labels and legacy styles. See exact selectors in the findings JSON.
2. **Election party text and specialty chart text.** Party colours used directly
   as small text can fail on light or dark surfaces. Keep party fills/swatches,
   but choose readable text colours independently. Review Ontario, BC and Alberta
   together. Some colour-blind and dark chart labels also remain flagged.
3. **Other report-specific contrast.** Healthcare/Education download links,
   Mortgage coloured notices, comparator sidebar, and a smaller set of homepage,
   Weather, Promises and progress-page labels need individual treatment. Consult
   the findings JSON rather than treating absence from this short list as a pass.
4. **Manual accessibility review.** Full keyboard traversal, screen-reader use,
   map/graph interaction and chart alternatives need a dedicated pass. Automated
   rules cannot establish that every visual is understandable without sight.

## Limits

- Local working-tree audit. GitHub Pages publication, collector health and source
  data accuracy were not reassessed. No collector data was edited.
- External source links were not exhaustively requested or checked for semantic
  correctness. Local file destinations were checked; generated fragment links
  were verified on the representative pages noted above.
- Default PWHL detail states were covered; every player/team/season combination
  was not opened. All filter combinations, map popups, geolocation and real email
  submission were outside this audit.
- Desktop dark/colour-blind layouts were not separate exhaustive cases. Those
  themes were checked at phone width, with representative interactive switching.
- Axe counts are flagged DOM nodes, not unique user-facing defects. They vary
  with viewport, data, collapsed content and third-party loading.

## Repeat

From this repository, install the temporary audit dependencies:

```powershell
npm install --prefix output/site-audit --no-package-lock --no-save playwright axe-core
python -m http.server 8767 --bind 127.0.0.1 > output/site-audit/server.log 2>&1
```

Run the audit from a second terminal:

```powershell
node scripts/audit_site.cjs
```

The runner defaults to two browser workers and Chrome's standard Windows path.
`AUDIT_ORIGIN` can change the server URL; `AUDIT_PAGES` accepts comma-separated
repo-relative HTML paths for targeted checks. Results overwrite
`output/site-audit/results.json`; retain prior runs before comparing them.

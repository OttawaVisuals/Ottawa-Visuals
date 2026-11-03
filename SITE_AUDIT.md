# Site audit — November 3, 2026

Status: identified findings fixed locally and committed. No publication or WCAG
conformance certification is implied. Actual screen-reader application testing
remains unverified (see Limits).

## Result

- 47 entry points, 282 distinct cases: 320px and 1280px in light, dark and
  colour-blind themes. No automated WCAG 2 A/AA or 2.1 AA violations remain in
  those tested states after targeted rechecks.
- No document-width overflow, visible broken images, unnamed visible informative
  canvases, displayed load errors or uncaught JavaScript errors remain.
- Observed internal file destinations resolve; tracked destination casing was
  checked for GitHub Pages. Generated section links were checked on representative
  pages. External source URLs were not exhaustively tested.
- PWHL detail fixtures use `player.html?id=1` and `team.html?code=OTT`; opening a
  detail URL without an identifier is an intentional missing-selection state.
- Compact per-case evidence: `audits/site-audit-2026-11-03.json`. Raw results and
  screenshots are retained locally in `output/site-audit/`.

## First pass

The initial audit covered 188 cases: desktop light and all three phone themes.
It fixed six Mortgage/Weather navigation destinations, input labels, all 46
tracker checkbox associations, scroll-region keyboard access, shared text
contrast, author-button overlap and narrow-screen chart/table/header layouts.
The homepage hero now stacks on phones.

The initial desktop-light pass flagged 2,337 DOM nodes. First fixes reduced that
count to 441. Follow-up fixes brought the count to zero in the tested states.
Counts are DOM nodes, not independent usability defects.

## Follow-up fixes

- Separated readable text colours from chart fills and party swatches. Fixed
  election result text/flip labels, legacy RTO/tracker/prospector colours,
  comparator sidebar, report source links, Mortgage notices/distributions,
  footer text and active PWHL/progress/procurement controls.
- Added an Ontario riding selector as a keyboard alternative to selecting the
  SVG map. Existing BC/Alberta selectors are retained.
- Added shared skip links/main landmarks where absent. Existing skip links are
  first in keyboard order and preserve report query/filter state. Focus outlines
  remain visible on inputs and controls.
- Added expandable chart-value tables for Chart.js charts without an existing
  matching table, using the same labels and values supplied to the renderer.
  Multi-series charts expose native series checkboxes. Updates refresh open
  tables; removed charts remove their generated disclosures. Existing PWHL and
  traffic tables are retained rather than duplicated.
- Added value tables for RTO time-series/sparklines and Mortgage demographic
  distributions. Missing chart values stay unavailable rather than becoming zero.
- Added a selected-year Weather spiral table, with 365 source values and the
  documented February 29 exclusion. Opening it pauses playback. Reduced-motion
  preferences pause initial playback; play/pause state and year are named.
  Its background layer and Leaflet's duplicate bitmap layer are decorative to
  assistive technology; named chart/map regions and alternatives remain.
- Fixed the V2 traffic preview's missing-summary exception and default section.
  It loads Traffic stops, including when handed an unsupported summary link;
  the public report still defaults to Summary. The audit now checks displayed
  load errors as well as uncaught exceptions.
- Valid PWHL detail views received named scroll regions and readable overtime/
  shootout labels. Theme and affected report assets have updated cache versions.

## Verification

- Playwright with installed Chrome, local HTTP serving and axe-core WCAG 2 A/AA
  and 2.1 AA rules across all 282 cases, plus targeted rechecks after final edits.
  Incomplete local styles/images and transient navigation failures are retried.
- Keyboard Tab/Enter checks on Weather, Mortgage, RTO, Ontario elections and the
  V2 traffic preview: skip-target focus, opening chart disclosures and selecting
  a riding. Browser accessibility-tree snapshots checked table names/headers.
- Chart values independently compared with the live chart dataset. Keyboard
  series hide/restore changes the chart and table together and preserves focus.
  An open chart table also passes the automated accessibility rules.
- Weather spiral: reduced-motion pause, keyboard year selection, 365 rows,
  correct selected-year date labels, February 29 exclusion, open-table contrast
  and no phone overflow checked.
- V2 traffic: default and summary-link fallback both show the populated stops
  report; the public traffic page still shows its summary. Five preview charts
  loaded in the checked default state.
- Screenshots reviewed for phone chart tables and selected report layouts,
  including the loaded PWHL team view. JavaScript syntax and Git whitespace
  checks pass. No collector data or report calculations were changed.

## Limits

- No NVDA, JAWS or VoiceOver session was run. Browser accessibility trees and
  keyboard checks verify semantics and interaction, but cannot establish each
  screen reader's announcements or complete reading experience.
- Default states and representative interactions were tested, not every filter,
  player, team, season, map popup or dataset combination. Pages without shared
  theme support do not gain theme support simply by receiving a preference.
- This was a local working-tree audit. Deployment, collector health, data-source
  accuracy, live geolocation and real email submission were not reassessed.

## Repeat

Install temporary dependencies, then start a server from this repo:

```powershell
npm install --prefix output/site-audit --no-package-lock --no-save playwright axe-core
python -m http.server 8767 --bind 127.0.0.1 > output/site-audit/server.log 2>&1
```

In a second terminal, run all themes at both viewport widths:

```powershell
$env:AUDIT_ALL_THEMES='1'
node scripts/audit_site.cjs
```

Without `AUDIT_ALL_THEMES`, the runner uses the original 188-case matrix.
`AUDIT_ORIGIN` changes the server URL; `AUDIT_PAGES` accepts comma-separated
repo-relative HTML paths. Two browser workers and Chrome's standard Windows path
are the defaults. Results overwrite `output/site-audit/results.json`; retain
previous runs before comparing them.

# Site-wide redesign — "compact utility" style + dark/light switch

## Goal

Restyle every HTML page in this repo to match the approved design in
`weather-design-c.html` (compact utility: light-grey background, dense white
panels, small uppercase section headings, Inter + JetBrains Mono), and add a
dark/light theme switch to every page.

**This is a styling-and-navigation pass only.** Do not change any data
loading, chart logic, calculations, or page content. Let the data do the
talking: no big hero banners, no oversized titles, no decorative gimmicks.

## Reference implementation

`weather-design-c.html` is the approved reference (light mode only, theme
toggle currently hidden). Its `<style>` block is the canonical starting point
for every page: copy it as the base, then adapt any page-specific components
to the same tokens. Open it in a browser next to each page you convert.

## Pages to convert, in this order

1. `weather.html` — replace its current dark-dashboard style with the
   reference style and add the theme switch (spec below). When it is done and
   verified, delete `weather-design-a.html`, `weather-design-b.html` and
   `weather-design-c.html` (design experiments, superseded).
2. `mortgage.html`
3. `pwhl.html`
4. `road-safety.html`
5. `ottawa_ward_elections.html`
6. `Ontario_Elections/ONelections.html`
7. `Comparator.html`
8. `ghg_calculator.html`
9. `progress.html`
10. `index.html` last — it embeds other pages in iframes, so check the
    embedded views after converting it.

Read each page fully before touching it; several have their own JS that reads
colors from CSS variables or element IDs. Commit after each page so any
regression is easy to bisect.

## Design tokens

Every color anywhere on a page (including canvas/Chart.js code) must come from
these CSS variables — no hardcoded hex in components, or the theme switch
can't restyle them.

```css
:root {
  --font-display:"Inter",system-ui,sans-serif;
  --font-cond:"Inter",system-ui,sans-serif;
  --font-body:"Inter",system-ui,sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,Consolas,monospace;
  /* light theme (default) */
  --bg:#F1F3F6; --bg-2:#FFFFFF; --bg-3:#F5F7FA;
  --line:#DCE1E8; --line-2:#C3CAD4;
  --ink:#1F2530; --ink-2:#4E586A; --ink-3:#7C8698;
  --accent:#C9542F; --accent-2:#E06B45;
  --accent-bg:rgba(201,84,47,0.08); --hl:rgba(201,84,47,0.14);
  --green:#22885F; --amber:#C98A1F; --red:#D0483A; --blue:#2F6FB4; --purple:#6E62C8;
}
[data-theme="dark"] {
  --bg:#0E1117; --bg-2:#161A23; --bg-3:#1D2230;
  --line:#2A2F3D; --line-2:#383E4E;
  --ink:#EEF1F7; --ink-2:#B6BDCC; --ink-3:#7A8094;
  --accent:#E06B45; --accent-2:#F08A66;
  --accent-bg:rgba(224,107,69,0.12); --hl:rgba(224,107,69,0.18);
  --green:#2FB584; --amber:#E8A030; --red:#E85A44; --blue:#5B9BE0; --purple:#8F84E8;
}
```

Semantics: `--red` = hot/up/worse, `--blue` = cold/down, `--green` = good,
`--accent` = UI accent and primary trend lines. Keep those meanings when
mapping each page's existing colors onto the tokens.

## Layout & typography rules (from the reference)

- Body: Inter, 13.5px, `--ink` on `--bg`.
- Topbar: `--bg-2`, 48px, sticky, 1px `--line` bottom border. Brand (avatar +
  "Ottawa Visuals"), site nav links, spacer, page-specific link
  (e.g. Methodology), theme toggle button. Nav hidden under 720px.
- Jump nav: sticky pill bar directly under the topbar (`top:48px`), built
  automatically from the page's section `h2`s — copy the small
  `DOMContentLoaded` script from the reference. Include it on every page long
  enough to scroll (skip it on short pages like `ghg_calculator.html` if it
  would only hold one or two links).
- Page title (`.hero h1`): 20px / 700, one short line, with a one-sentence
  13px description under it. Nothing bigger anywhere.
- Section headings (`.section-head h2`): 12px, uppercase, letter-spacing
  0.07em, `--ink-2`. Optional 12.5px description in `--ink-3`.
- Cards: `--bg-2`, 1px `--line` border, 8px radius, 12px padding. No shadows.
- Fine print / axis labels / timestamps: JetBrains Mono, 9.5–11px, `--ink-3`.
- Numbers in stat tiles and tables: `font-variant-numeric:tabular-nums`.
- Content width ~1240px, vertical gap between sections ~24px.
- Keep each page responsive at 375px width (grids collapse to one column —
  see the media queries in the reference).

## Theme switch

- Sun/moon icon button in the topbar (the current `weather.html` and
  `mortgage.html` already contain this exact toggle — reuse its markup and
  icon SVGs; in `weather-design-c.html` the button exists but is hidden with
  `display:none`, so un-hide it).
- Mechanics: `data-theme` attribute on `<html>`, persisted in localStorage
  under the key `ov-theme`. All pages share that key so a choice made on one
  page follows the visitor across the site.
- First visit (no stored choice): follow `prefers-color-scheme`.
- Apply the attribute from an inline `<script>` in `<head>` (before any
  visible markup renders) so there is no wrong-theme flash.
- On toggle, charts must re-read the CSS variables. `weather.html` already
  has the pattern: every chart is registered in a `CHARTS` array with the
  CSS-variable names it uses, and `refreshChartColors()` re-reads them and
  calls `chart.update('none')`. Replicate that pattern on any page whose
  charts bake colors in at build time, and also rebuild non-Chart.js visuals
  that cache colors (e.g. the warming stripes and temperature spiral on the
  weather page, or any canvas/SVG drawn imperatively).
- The brand avatar sits in a dark circle with `filter:invert(1)` in light
  mode; in dark mode drop the invert (see how the old pages handled
  `[data-theme]` on `.brand-logo img`).

## Hard constraints

- Keep every element id and class that any script references. If unsure
  whether a class is styling-only, grep the page's JS first.
- Do not modify fetch/data-processing/chart-construction logic except the
  lines that read colors or fonts.
- Keep the "hide topbar when embedded in an iframe" script
  (`window.self !== window.top`) that `weather.html` has, and add the same
  guard to any other page `index.html` embeds.
- Keep each page's `<title>`, meta description, favicon, and data-source
  notes/methodology sections exactly as they are.
- Chart.js options: legend/tooltip/tick fonts go to Inter 10–11px; grid lines
  use `--line`; tooltip background `--bg-3` with `--line` border (the
  `baseOptions()` helper in `weather.html` shows the target).

## Verification (every page, before moving to the next)

Serve the repo locally (`.claude/launch.json` has python http.server configs)
and check:

1. No console errors.
2. Light and dark mode both legible — especially chart grid lines, axis
   ticks, and hover tooltips.
3. The toggle persists across a reload and carries to another page.
4. Jump nav links scroll to the right sections.
5. Interactive features still work (selectors, sliders, calculators, maps).
6. Page still looks right embedded in `index.html`'s iframes and at mobile
   width (375px).

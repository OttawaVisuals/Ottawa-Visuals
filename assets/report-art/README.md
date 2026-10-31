# Public report artwork

Approved visual direction: the wealth page's design 2, extended to the other
eleven reports visible on the homepage. Navy outlines, white interiors, teal and
amber fills. All illustrations are decorative, qualitative imagery; none encodes
an actual result, statistic, map boundary or official agency/league logo.

## Files and scope

`manifest.json` records the eleven report pages, homepage report IDs, illustration
files and 59 section-label assignments. `prompts.json` contains the exact shared
prompt and all eleven subject briefs. Created with built-in image generation
using the approved design B board as a style reference. Generated transparent
PNGs were converted to lossless WebP without resizing or content edits; their
original files remain in the Codex generated-images directory.

`lightning.svg` is a hand-drawn amber bolt with a navy outline, used for the
weather report's lightning heading instead of the general weather illustration.

| Asset | Report |
|---|---|
| promises.webp | Sutcliffe's 2022 promises |
| budget.webp | Ottawa budget |
| courts.webp | Ottawa court outcomes |
| police.webp | OPS complaints and discipline |
| traffic.webp | How Ottawa really moves |
| ottawa-elections.webp | Ottawa ward elections |
| ontario-elections.webp | Ontario election scenarios |
| road-safety.webp | Vehicle–pedestrian impact calculator |
| mortgage.webp | Mortgage affordability calculator |
| hockey.webp | PWHL dashboard entry page |
| weather.webp | Ottawa climate dashboard |

The shared style is `../report-art.css`, loaded after each page's own styles.
Existing header copy sits in `.ov-report-copy` beside one `.ov-report-art` image.
The mortgage header lives inside the scrollable results column, preserving the
calculator's full-height input/results layout. Homepage cards reuse each report's
illustration through the existing `artwork` property. The wealth page retains its
approved assets and styles. Player/team detail pages and hidden reports are
outside this homepage-report rollout.

Section labels use decorative CSS backgrounds and an empty pseudo-element, so
dynamic `.textContent` updates retain the icon without changing accessible
heading names. Reused chart/history/clipboard icons live in `../../Wealth/assets/`;
domain-specific labels reuse their report illustration. No executable report
scripts, element IDs, data files or formulas were changed. Light image panels
keep navy outlines legible in light, dark and colour-blind themes.

## Checks — October 31, 2026

- All eleven images have actual transparency; all new asset references exist.
- All eleven reports compared to their previous HTML at 1280px and 390px:
  same controls after asynchronous loading, no added page overflow. PWHL's
  initial loading frame was rechecked after its app became visible.
- Every report checked at phone width in dark and colour-blind themes; report
  artwork loads and all 59 section markers remain present.
- Existing court-page overflow at phone width and the existing narrow homepage
  topbar overflow were observed in the baseline and were not expanded by this
  artwork change. Internal table/chart scrolling remains page-owned.
- Impact-speed changes update risk; mortgage rate + Calculate updates results;
  traffic navigation retains the dynamic section heading/icon; hockey season
  selection and the ward search work. All 12 homepage cards have illustrations.
- Original report scripts and element IDs compare unchanged against the previous
  commit. No data or collector files modified. Syntax/link/whitespace checks pass.

These checks verify the artwork integration and representative interactions;
they are not a new audit of each report's underlying data or mathematical model.

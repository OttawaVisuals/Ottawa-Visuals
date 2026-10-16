# Codex sprint, Oct 15–31 2026

Rules: one task per day · commit after each · never two sessions on the same files ·
never hand-edit collector data (fix the scripts) · tick the box when done.
Resets: use one per week (marked **RESET**).

## How to change this plan (it's a living file)
- Did extra work or a different project? Tick its box, or add a line under "Extra work" below.
- Want a different task today? Edit the "TODAY (override)" line; the 9am reminder shows it first. Clear it when done.
- Task wasn't finished? Leave it unticked; it stays next in line.
- Two projects in one day is fine: tick each when done. The reminder picks the next unticked item.
- Tell any session (Claude Code or Codex): "update CODEX_PLAN.md: I did X" or "swap today to Y".

TODAY (override): none

## Extra work (done outside the plan)
- [x] Ward elections map (Oct 16: 2010–2022 year selector, mayor-race "largest group" and "ward winner" map modes, sortable ward list, councillor history per ward, colour scale fitted to 30–55%, nav links fixed, dark-mode labels, mobile stacking)
- [x] PWHL mobile map and player comparisons (Oct 16: route following, goalie minimum-games filter and tap-to-inspect scatter points)
- [x] PWHL usability improvements (Oct 16: historical headers, accent-insensitive search, shareable filters, keyboard sorting and retry messages)
- [x] PWHL image fallbacks (Oct 16: local league logo for missing or failed player photos and team logos)
- [x] PWHL travel graphics (Oct 16: transport icons, distinct route patterns and theme colours)
- [x] PWHL recap icon refresh (Oct 16: five event icons, matching award style and theme colours)
- [x] PWHL award SVG refresh (Oct 16: full icon set, clearer metric symbols and theme-aware colours)
- [x] PWHL page work with Codex (Oct 15: historical overview, season summaries and team awards)

## Before anything
- [x] Commit or stash uncommitted edits, then `git pull` (done Oct 15; PWHL work pushed Oct 15)
- [x] Create `AGENTS.md` ("Read CLAUDE.md and follow it.")

## Week 1 (Oct 15–21): RTO Watch + collectors
- [x] Day 1: Claude Code checks Cloudflare cron + `collect.yml`; update `PROJECTS.md` + `tracker.html` together (done Oct 16: collectors down since Oct 12; `collect.yml` has never run because the Worker setup is unfinished; owner steps in PROJECTS.md)
- [ ] Day 2: **RESET 1** — Codex builds RTO Watch before/after charts (strongest model)
- [ ] Day 3: finish/review the charts
- [ ] Day 4: Tax polish (mid model)
- [ ] Day 5: Ontario Costs: swap the 2 news-relayed FAO figures (mid model)
- [ ] Day 6: Oil & Gas polish or PWHL open item (mid model)
- (Roads "why was the commute bad?" waits until ~Nov 5 for event logs)

## Week 2 (Oct 22–28): new pages from data in hand
- [ ] Day 1: **RESET 2** — GovContracts stacked-bar page + category filter (strongest model)
- [ ] Day 2: review/fix GovContracts page
- [x] Day 3: OC Transpo KPI extraction from PDFs into a time series (strongest model) (done Oct 16 in Claude Code, plus the page `OC_Transpo/octranspo_kpis.html`)
- [ ] Day 4: review the extracted series
- [ ] Day 5: Geothermal "Ottawa Case Study" page (Energy repo)
- [ ] Day 6–7: buffer / catch-up

## Week 3 (Oct 29–31): audit + wrap-up
- [ ] Day 1: **RESET 3** — audit all live pages: mobile, dark mode, accessibility, links (mid model)
- [ ] Day 2: fix audit findings
- [ ] Day 3: smallest model syncs `PROJECTS.md`, `tracker.html`, `README.md`, `index.html` tiles

## Model tiers (verify in the picker; names change)
- Strongest reasoning, high effort: long builds, PDF/data extraction
- Default/mid, medium effort: audits, polish
- Smallest/fastest: bulk mechanical edits, doc sync

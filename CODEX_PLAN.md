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
- [x] Expand budget history and service KPIs (Oct 23: 2023–2026 full-accrual budget changes, dollar/percent ranking; 26 paramedic/transportation-condition/housing series with targets and dates, sourced CSV/JSON; bundled local-file fallback)
- [x] Ottawa budget page (Oct 23: adopted 2026 operating/capital/funding, 2025 budget comparison, service breakdowns, source extraction/reconciliation, CSV/JSON; separate Lansdowne scope/financing/July 2026 spending snapshot and service KPI links)
- [x] Simplify traffic court charts (Oct 23: removed camera-issued versus court-completed chart; selected-offence chart 30% taller at each screen breakpoint)
- [x] Clarify traffic trial category (Oct 23: “Completed after trial · outcome not reported”; CanLII follow-up dropped, aggregate source remains the report basis)
- [x] Review all 133 s.53 search candidates (Oct 23: 131 full-text relevance screens, two exclusions by proceeding scope after long-page failures; per-document classifications, source locators, CSV/JSON and checks; one Toronto trial conviction, one Pembroke-area plea, one Pembroke procedural ruling; no Ottawa trial verdict established in the candidate set)
- [x] S.53 published-judgment search pilot (Oct 23: five retained CanLII searches for 2016–2025; 133 deduplicated candidate links, 27 candidate texts checked plus one supplemental judgment; verified Ontario examples and exclusions documented; no Ottawa s.53 trial verdict confirmed, no chart reclassification)
- [x] Traffic court tab in How Ottawa Really Moves (Oct 23: reused audited OCJ data; revised to offence-driven latest-year KPIs, outcome-stacked first chart with five groups, count/share buttons, no year dropdown, all-calendar-year CSV and camera context; 15 checks pass, desktop and narrow-phone layouts reviewed)
- [x] Ottawa court outcomes (Oct 23: 27 official publications, 903 validated rows; separate criminal/POA views, offence/period filters, count/share bars, tables and downloads; non-calendar periods and 2016 source discrepancy preserved)
- [x] OPS complaints and discipline (Oct 23: official-source snapshot; 23 officers in published decisions, 18 with findings/admissions, 20 cases; 2 upcoming-hearing officers separate; source reconciliation, filters, annual bars, CSV and JSON)
- [x] PWHL mobile review (Oct 23: checked 11 page types at phone/tablet widths; fixed clipped birthplace popups and rotation, enlarged form/sort/playback controls, verified 44 updated page/width combinations; limitations in PWHL/MOBILE_CHECKS.md)
- [x] PWHL publication accuracy fixes (Oct 23: shot/goal pairing, club-specific player and franchise totals, combined league leaders, full standings win columns, replay seeking, roster/estimate labels and scorer counts; rebuilt JSON, 12 regression checks and documented causes)
- [x] Traffic report without Power BI (Oct 18: five native sections, charts/maps/filters/downloads; official source audit, monthly police extraction, red-light data through Aug 2026, separate OPS 2025/2026 summaries and speed monitoring through Sep 2026; weekly rebuild)
- [x] Election navigation improvements (Oct 17: searchable ward picker, full mobile ward names with two-column list, visible partial-mayor coverage, explicit missing/comparison reasons and shareable ward/year/map URLs)
- [x] Election methodology section (Oct 17: simple collapsible sources, formulas, special-vote coverage and historical data gaps, matching the retrofit page's approach)
- [x] Ottawa election source reconciliation (Oct 17: 93 ward-years, four City workbooks, field audit and reproducible import; valid votes separated from ballots, special mayor votes preserved, Ward 4 registration corrected, unsupported estimates removed, remaining source gaps documented)
- [x] Ward elections map (Oct 16: 2010–2022 year selector, mayor-race "largest group" and "ward winner" map modes, sortable ward list, councillor history per ward, mayor chart as % of all residents, colour scale fitted to 30–55%, nav links fixed, dark-mode labels, mobile stacking)
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
- [x] Day 2: **RESET 1** — Codex builds RTO Watch before/after charts (strongest model) (done Oct 17 in Claude Code: 311 + electricity vs same weeks of 2025, dot plot + rolling line in section 5; reset not used)
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

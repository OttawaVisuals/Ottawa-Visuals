# Ottawa Visuals — Master Project List

> Personal roadmap of data-visualization projects.
> **Sources:** claude.ai chat export (`conversations.json`, 279 chats, Aug 2025–Jun 2026)
> + Claude Code session history.
> Progress % is a rough self-estimate, not a hard metric.

Legend: ✅ live · 🔄 in progress · 🧪 prototype/exploration · 💡 idea/planned · ☐ backlog

**Overall theme:** open-data visuals about Ottawa, Ontario, and Canada — leaning
toward civic accountability (RTO mandates, transit, budgets, traffic safety) with
an eye on informing the next Ottawa mayoral / Ontario elections.

---

## Pipeline status — checked 2026-09-03 (resolved; one thing left unexplained)

| Collector | Cadence | Last reading | State |
|---|---|---|---|
| TomTom traffic (`Traffic/`) | adaptive, ~hourly–15min | 2026-09-03 01:05 UTC | ✅ current, backlog fully recovered |
| OC Transpo GTFS-RT (`OC_Transpo/`) | adaptive, ~hourly–15min | 2026-09-03 01:35 UTC | ✅ current, backlog fully recovered |
| OC Transpo KPI snapshots | weekly (Mon) | not re-verified this pass | ❓ Pi reachable by its owner now, but not re-checked from here |
| GTFS-RT raw archive (Pi, outside repo) | every sample | not re-verified this pass | ❓ not re-checked this pass |
| Static GTFS snapshots (Pi, outside repo) | weekly (Tue) | not re-verified this pass | ❓ not re-checked this pass |
| Disk (`/dev/mmcblk0p2`) | — | **76% used, 3.3 GB free** (checked 2026-09-03, `df -h` on the Pi) | ✅ essentially unchanged from 73%/3.7 GB free on 2026-07-26 |

**Incident timeline (2026-08-03 → 2026-09-03, ~1 month):**
1. `traffic:`/`transit:` commits (Pi cron only) stopped dead at **2026-08-03
   15:05/15:35 UTC**, confirmed from GitHub commit history (pulled first, then diffed —
   see the outage-detection method below). GitHub-Actions collectors in the same repo
   (PWHL, ASE, weekly refresh) kept committing normally the whole time, ruling out a
   GitHub-wide issue.
2. `ssh ottawa-pi` timed out (`10.0.0.142:22`) on 2026-09-02 — the box itself was
   unreachable, not just slow to push.
3. Physically checked: **the LEDs were blinking red/green with no fixed pattern** —
   not a coded boot-diagnostic flash, more consistent with an under-voltage condition
   (power supply/cable) than SD-card corruption.
4. **Swapped the power cable.** The Pi came back up (`uptime` showed 2 min at first
   check) and `df -h` showed 76% used / 3.3 GB free — almost identical to the
   2026-07-26 reading (73%/3.7 GB), which **rules out the disk-full hypothesis**: the
   card had ~13 days' worth of headroom left and never filled. This was a power
   incident, not a storage one.
5. Within minutes of power being restored, GitHub received a **full, gap-free backlog**
   of hourly `traffic:`/`transit:` commits covering the *entire* outage window
   (2026-08-03 15:xx → 2026-09-03 01:xx UTC), each with an accurate embedded hourly
   timestamp and no missing hours.

**⚠️ Step 5 is not fully explained and is worth understanding before trusting it blindly.**
The push scripts (`pi_push.sh` / `pi_push_transit.sh`) timestamp each commit with
`date -u` *at commit time*, so a genuinely continuous, evenly-spaced month of hourly
commits implies the Pi kept polling and committing **locally** the whole time and only
lost the ability to *reach GitHub* — but that's hard to square with the box being fully
unreachable over SSH and showing a power-fault LED pattern. Possibilities, none
confirmed: (a) the Pi had power/network intermittently and this session simply never
caught it up; (b) local polling continued on battery/partial power while only the
network/push path was down; (c) something else backfilled the gap. **Worth checking
directly on the Pi** (`~/traffic_poll.log`, `~/traffic_push.log`, `~/transit_poll.log`,
`~/transit_push.log` — do the local log timestamps actually span the outage window, or
does the log itself show a gap that the git history doesn't?) before assuming every
one of those "hourly readings" reflects a real live sample rather than a replay.

**Monitoring added as a result of this incident** (2026-09-03): see
[`Traffic/PI_SETUP.md` §7](Traffic/PI_SETUP.md) — a daily GitHub Actions heartbeat
(`.github/workflows/collector-heartbeat.yml`) that opens a GitHub Issue if either
collector goes quiet for 24h, independent of the Pi's own health, plus an optional
healthchecks.io dead-man's-switch ping from the push scripts for faster (~1h) detection.

**There was no Jul 19–24 outage**, and this local clone hit the *exact same trap
again* on 2026-07-31 — found 211 commits behind after not being pulled for four
days. Pulling first (as the lesson below says) confirmed collection ran
continuously the whole time, at roughly 23–24 commits/day per collector. Note the
cadence isn't a flat "30 min" as earlier entries here claimed — actual reading
timestamps show it adapts, landing every 15–30 min in some windows and hourly in
others (e.g. 2026-07-31: 13:00, 13:15, 13:30, 14:00, 15:00, then 15-min spacing
again from 19:00 onward). Worth confirming against the collector script whether
this is intentional peak-hour densification or worth documenting explicitly.

**Triage rule learned the hard way (twice now): `git pull` before concluding
anything from commit timestamps.** The first time, this false premise produced
three successive wrong diagnoses in a single session. Consider making this the
first line of any future pipeline-check workflow, not just a lesson in the
narrative below.

**Not re-verified this pass:** Pi disk usage (73% full / 3.7 GB free as of
2026-07-26 — check again, it's had 5 more days of the raw archive growing at
~450 MB/month) and the raw/static archive sizes on the Pi itself, since this
check was done from the GitHub remote rather than SSH'd into the Pi.

One real but minor event: a single transient `git@github.com: Permission denied
(publickey)` in `~/traffic_push.log` shortly after 2026-07-24T15:05Z. It self-resolved
and pushes have run normally since. Worth a retry-with-backoff in the pusher, not
worth chasing.

**The KPI snapshot cron was never broken.** It looked broken because
`kpi_snapshots/` still held only the `2026-07-11` files, but `snapshot_kpis.py`
writes a dated copy *only when content changes*, and `~/transit_snapshot.log` on the
Pi shows clean runs on both Jul 13 and Jul 20 that correctly saved nothing — the city
had not republished. A manual run on 2026-07-26 independently confirmed all four
files are byte-identical to Jul 11. The rolling-window risk is real but paces with
the city's publication cadence (roughly monthly), not with our weekly polling.

Lesson for future triage: **this job cannot be diagnosed from the contents of
`kpi_snapshots/`.** Absence of new files is the expected output. Read the log.

**Verified on the Pi 2026-07-26** — uptime 24 days (so the Jul 19–24 stall was never
a reboot), all six crontab lines installed and firing, raw GTFS-RT archive at 327 MB
and current, static GTFS snapshots complete. The one live concern is disk: the SD
card is **73% full with 3.7 GB free**, and the raw archive alone grows ~450 MB/month,
giving roughly 8 months before it fills. A full card would stop collection silently.

**Coverage so far:** traffic 21 days (2026-07-06 →), transit 16 days (2026-07-11 →).
RTO4 took effect Jul 6, so there is *no* pre-RTO4 baseline in our own collection —
the before/after comparison depends entirely on the TomTom MOVE backfill
(`Traffic/BACKFILL_SPEC.md`) and the eScribe/KPI history.

---

## ✅ Live

### Ottawa Traffic Stops, Red Lights & Speed Violations
- **Progress:** ~100% · Power BI dashboard (featured on home page + Dashboards page).
- OPS traffic stops by result type (charged / warning / no action).
- **Data:** Ottawa Police data portal. · **Page:** `/#report-traffic`

### Ottawa Ward Elections
- **Progress:** ~90% (live, iterating) · Interactive ward-level election map/visual.
- Ongoing work on ward redistribution impact + Deneb custom visual with ward labels/leader lines.
- **Page:** `/ottawa_ward_elections`

### Ottawa Mortgage / Housing Affordability Tool
- **Progress:** ~90% (live, iterating) · Federal-employee-focused affordability + retirement-planning calculator.
- Census-data context for home buyers; spending breakdown; mobile-friendly.
- **Page:** `/mortgage`

### Retrofit Explorer (Energy repo)
- **Progress:** ~85% · Static site (`retrofits.html`, vanilla JS + Chart.js) of EnerGuide home-energy retrofit data per province/FSA.
- FSA choropleth by median % saving; pre/post EUI charts; fuel waterfall; emissions tracking.
- **Location:** `C:\Energy` · **Live:** https://ottawavisuals.github.io/Energy/retrofits
- **Open:** finalize fuel-chart variant; push `CA.json`; reconcile data-source URLs.

### Ottawa Weather / Climate Evolution
- **Progress:** ~90% (live, iterating) · 135-yr daily (1889–present, station 4333) + 73-yr hourly
  (1953–present, stations 4337→49568) ECCC pipelines feeding an interactive dashboard: warming
  stripes, an animated multi-year "spaghetti plot" of daily temperature (365-day radial sweep,
  years accumulate as faint traces), seasonal small-multiples, hot-vs-cold extremes, snow→rain
  regime shift, hourly wind/hot-hours/tropical-hours/humidex/wind-chill/thunderstorm extremes
  (thunderstorms split into total vs. severe), and a "pick a year you remember" comparison tool.
- Honest framing, checked against a peer-reviewed 1890–2019 Ottawa climate study: not "more
  extreme weather" broadly, but a real shift in *which* kind of extreme occurs.
- **Data:** Environment and Climate Change Canada (climate.weather.gc.ca) — scripted, resumable
  fetch pipelines in [`Weather/`](Weather/PLAN.md).
- **Page:** `/weather.html` · also on the homepage as Report № 04 · Climate.

---

## 🔄 In Progress

### RTO4 Impact Page — "Ottawa RTO Watch"
- **Progress:** ~35% · Live dashboard at `/rto.html` (roads + OC Transpo live sections;
  former `Traffic/traffic.html`, which now redirects). Historical before/after charts come
  as the daily rollups accumulate.
- **Collectors healthy (2026-07-26)** — see the pipeline status table above.
- Commutes (TomTom, collecting since Jul 2026) + transit (own GTFS-RT logging on the Pi +
  official KPI snapshots + eScribe history) + TBS NCR headcounts, 311, bike counters, IESO load.
- **Plan / data inventory:** [RTO4_PLAN.md](RTO4_PLAN.md) · collector docs in [OC_Transpo/README.md](OC_Transpo/README.md)

### Ontario Elections Visual (coalition scenarios)
- **Progress:** ~70% · Past Ontario elections with "what if Liberals + NDP banded together"
  coalition scenarios, per-riding survivor logic, strategic-candidate analysis, turnout/gauge charts.
- Combined multi-zoom GeoJSON filled map (main + 2 zoom insets, custom placement).
- **Location:** `C:\Ottawa_Visuals\Ontario_Elections` (+ `Ontario_Trials`)
- **Related angle:** "crazy spending by the Ford government" visual.

### Ontario Court Cases
- **Progress:** ~30% · Extraction/structuring of Ontario Court traffic cases → CSV/JSON, then a visual.

### Canada Geothermal Feasibility Map
- **Progress:** ~15% · GSC bedrock geology + NRCan open-file data → national feasibility map.
- **Location:** `C:\Energy` (Geothermal).

---

## 💡 Big Idea — Ottawa Quality of Life Over Time
*(Largest planned project; intended to inform the next mayoral election — "get people out to vote to improve Ottawa's quality of life.")*
- **Progress:** ~10% (data scoped, no build yet).
- **Narrative goals:**
  - RTO (return-to-office) decisions have made life worse for people.
  - "No property-tax increase" → worse outcomes (road quality, services).
  - Some decisions benefited only a few (downtown parking costs, commercial landlords).
- **Candidate metrics / data:**
  - Traffic + traffic incidents (TomTom Area Analytics 30-day trial = historical commute times; Google mobility/sustainability insights).
  - 311 / 911 service calls (volume of reports, not just resolutions).
  - Ottawa GHG inventory dashboard (emissions rising).
  - Day-parking prices over time (Parkopedia + Wayback Machine).
  - Office rents / commercial building assessed values (COVID dip → RTO rise).
- **Sibling chats:** "Public data sources for quality-of-life metrics" (surveys/approval polls), "Ottawa data visualization sources" (road conditions, traffic, budget).

---

## 💡 Planned / Scoped Ideas

### OC Transpo Transit Ridership + Service KPIs  🔄 ~35%
- Ridership + service-quality KPIs over time. Data gap on OC Transpo site (KPIs only 2019–2022 downloadable).
- **Built:** Pi/Windows-ready scraper in [`OC_Transpo/`](OC_Transpo/oc_transpo_kpi_scraper.py) — auto-discovers Transit
  Committee/Commission meetings via eScribe's calendar API, downloads the KPI/ridership
  PDF attachments, and optionally extracts text/tables. Rate-limited, resumable, OS-trust-store TLS.
- **Harvest complete (2026-07-31):** 109 PDFs across 31 Transit Committee/Commission meetings, 2019–2026,
  all text-extracted (67 with structured tables) into `OC_Transpo/data/` (gitignored, local only —
  `manifest.csv` is the index). Fixed a real bug along the way: eScribe's `filestream.ashx` links carry
  the `DocumentId` query param in inconsistent casing (`DocumentId` vs `documentid`), and the scraper's
  lookup was case-sensitive, silently dropping every attachment on any page using the lowercase form —
  it turned out **every 2019–2021 meeting** hit this, contributing 0 of the original 82 downloaded files.
  Fixed to a case-insensitive lookup; a scoped re-run recovered 27 more files and now covers 2019 onward.
- **Next:** design the visual. `manifest.csv` + the extracted `.txt`/`.tables.csv` per PDF are the raw
  material; will need a pass to pull the actual KPI numbers out of the extracted tables (format varies a
  lot report-to-report) before there's a clean time series to chart.

### Ottawa City Finances / Budget Dashboard
- Municipal spending; ties into the property-tax / quality-of-life narrative.

### Ottawa Real Estate Dashboard (weekly auto-updates)
- Real-estate trends with a weekly refresh pipeline. (Prototyped in chat.)

### Province Spending by Category
- Provincial spending across healthcare, education, etc. *(also on site roadmap)*

### Canada Car & Gas Sales vs. GHG Targets
- Vehicle + gasoline sales vs. GHG reduction targets. *(also on site roadmap)*

### Visualizing Voter Apathy Across Canadian Elections
- Historical participation rates, province-wide + per district.

### Federal Consulting Spend / In-House Duplication  🔄 ~20%
- Government of Canada Proactive Disclosure of Contracts dataset, mined for consulting/IT
  spend that plausibly duplicates in-house public-service capacity, plus an RTO-keyword pass —
  a federal-level companion to the RTO4 narrative (NCR federal headcount is a big share of
  Ottawa's downtown workforce). **Location:** [`GovContracts/`](GovContracts/README.md).
- **Data quirk worth knowing:** the dataset's `description_en` field isn't a narrative
  description at all — it just names the `economic_object_code` accounting category. Real
  categorization comes from the structured `commodity_code` (GSIN) field instead, joined
  against PSPC's own GSIN code table — not from parsing free text.
- **First pass (2026-08-01), 3 iterations:** 1.31M contract line items, 2007–2026. (1) A
  prefix-based `commodity_code` match (e.g. `R199*`) pulled in BGIS's ~$5.7B real-property
  contract and VF Worldwide's ~$24.6M overseas logistics support as "consulting" — rejected.
  (2) Switched to an exact-code whitelist built from the GSIN table's own descriptions, plus a
  new "office footprint" category (furniture/fit-up/leasing/moves, via the verified-clean
  `N7110*` code family — a single word like "office" is too noisy for text search but precise
  as a commodity code). (3) Had to drop `V502A` "Relocation Services" after finding it's
  dominated by the government's *Integrated Relocation Program* (employee household moves
  between postings, not office moves) — a single Jan 2023 cluster of mover contracts totalled
  >$700M and would have swamped the category the same way as (1).
- **Current totals:** Management & business consulting $4.73B/9,116 contracts; IT/informatics
  consulting $541M/906; Office furniture & fit-up $386M/9,299; Office space leasing & moves
  $129M/999. Top vendors now sane (PwC/Accenture JV, IBM, ADGA, EY, S.I. Systems, Randstad);
  annual consulting-code spend ~$500–800M/yr 2020 onward.
- **RTO angle is thin so far:** 106 contracts (broadened phrase list) out of 1.3M rows matched
  RTO keywords (`comments_en` is mostly boilerplate, not narrative) — real signal exists (movers,
  office fit-up firms, an "Architectural & Engineering Services - Office..." contract) but this
  alone can't prove an RTO-driven spending link. Most promising untested lead: whether the
  furniture/leasing categories spike near the Jul 2026 RTO4 mandate date.
- **Switched primary axis to `description_en`** (v4, 2026-08-01): it's blank on only 0.08% of
  rows vs. 35% for `commodity_code` (which was $137.9B of unresolvable spend). After normalizing
  (strip leading economic_object_code numbers, unify case/dashes) and prefix-matching a curated
  whitelist, the seven RTO-relevant categories total far more than the commodity_code axis:
  Engineering consultants–construction $32.3B/14,964 contracts, Office buildings $23.6B/14,329,
  Architectural services $19.3B/5,498, Repair & maintenance–Office buildings $10.0B/1,571,
  Contracted building cleaning $2.7B/8,407, Office furniture & furnishings $1.3B/22,740, Other
  office equipment $0.4B/3,029.
- **RTO-mandate-spike check is blocked on data, not analysis:** built a month-level series
  (`office_footprint_by_month.json`) plus an automatic data-coverage check
  (`data_coverage.json`) specifically to catch this — but found the dataset's proactive-disclosure
  reporting lag means it only reliably covers contracts through **June 2026**; row counts collapse
  from ~5,300/month to 17 in July, 1 in September. The Jul 6, 2026 RTO4 mandate date isn't in the
  data yet at all. Concrete next step: re-run once a refreshed `contracts.csv` actually covers Jul
  2026 onward (check `last_reliable_month` first), then compare pre/post-mandate months.
- **Contracts under $10K are a dead end for category detail** (checked 2026-08-01): the
  companion "aggregated" resource only breaks spend into Goods/Services/Construction totals per
  department per year, plus a separate acquisition-card (P-card) total (~$700–850M/yr,
  1.6–2M transactions government-wide) — no vendor, no description, no code. Small purchases
  (e.g. a single office chair) are aggregated away at publication, not just messy. Documented in
  [`GovContracts/README.md`](GovContracts/README.md) so it isn't re-discovered later.
- **Competitive vs. non-competitive split added** (2026-08-01): joined `solicitation_procedure`
  (TC/OB/ST = competitive, TN = non-competitive, AC = ACAN/notice-based, kept separate since it's
  functionally closer to sole-source) onto the 7 office-footprint categories, by year, in
  `office_footprint_by_year_procurement.json`. Field is unreliable before 2017 (90–100% blank
  2005–2015) and only fully clean from 2019 on — scope any competitive-share chart accordingly.
  Quick sanity check across all 7 categories: competitive spend dominates every year (e.g. 2023:
  $6.97B competitive vs. $110M non-competitive vs. $6.9M ACAN) — worth checking whether that
  holds *per category* (Architectural/Engineering likely skew more sole-sourced than Furniture)
  before this becomes a chart.
- **Not yet built:** the page. Presentation idea floated but not built: stacked bar per year
  (segments = procurement type) with a category filter, ideally paired with a 100%-stacked
  version to isolate the competitive-share trend from raw dollar growth, plus small multiples
  per category. See "Next steps" below.

**Next steps to pick this back up:**
1. Watch for the dataset's next quarterly refresh; re-download `contracts.csv`, check
   `data_coverage.json`'s `last_reliable_month` reaches past Jul 2026, then compare
   `office_footprint_by_month.json` pre- vs. post-RTO4-mandate.
2. Build the actual chart(s) — stacked bar by year × procurement type, category filter, informed
   by the `dataviz` skill for styling. Data is ready in `GovContracts/data/`.
3. Split the broad "Office buildings" category (capital construction mixed with plain leasing) if
   isolating "we pay rent" from "we built a building" turns out to matter for the narrative.
4. Second human read of `rto_candidates.json` / `office_footprint_top_vendors.json` /
   `top_vendors.json` before any of this becomes a public-facing page.

### Political Spending / Transparency
- Pierre Poilievre taxpayer expenses; Canadian MP spending transparency; Alberta oil-company profits & capital flows.

---

## ☐ Backlog / Future

- **Ottawa Census Data** — age, income, languages… *(site roadmap)*
- **Ottawa Biking** — % of commute vs. % of city roadway; city spending; NCC vs. City. *(site roadmap)*
- **RTO Road Maintenance** — spending on road maintenance; office permits. *(site roadmap)*
- **Ottawa Building Permits** — permit data analysis/visual.
- **Bike Collision / Traffic Collision Map** — Ottawa collision data.
- **PWHL Hockey Dashboard** — Power BI on the PWHL API (side project).
- **Stop-sign / speed compliance monitoring** — Raspberry Pi camera at a local intersection.
- **Natural gas / electricity grid emissions** — Ontario gas distribution, Yukon hourly grid emissions, IESO data.

---

## Data sources
- Statistics Canada — https://www.statcan.gc.ca/en/start
- Open Ottawa — https://open.ottawa.ca/
- Open Ontario / Ontario open data
- Ottawa Police data — https://data.ottawapolice.ca/
- Ottawa GHG emissions dashboard — https://ottawa.ca/en/.../greenhouse-gas-emissions/greenhouse-gas-emissions-dashboard/dashboard
- TomTom Area Analytics — https://www.tomtom.com/products/area-analytics/ (30-day trial, historical traffic)
- Google sustainability/mobility insights — https://insights.sustainability.google/
- OC Transpo Transit Committee minutes (eScribe)
- EnerGuide / NRCan open data; Geological Survey of Canada

---

> ℹ️ This list now covers both claude.ai web/desktop/mobile chats and Claude Code
> sessions. It excludes clearly off-topic threads (escape-room backpack business,
> SharePoint/work HVAC consulting, stock trading, 3D printing).

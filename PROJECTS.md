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

## Pipeline status — checked 2026-07-26

| Collector | Cadence | Last reading | State |
|---|---|---|---|
| TomTom traffic (`Traffic/`) | 30 min | 2026-07-26 14:00 UTC | ✅ current, no gaps |
| OC Transpo GTFS-RT (`OC_Transpo/`) | 30 min | 2026-07-26 14:30 UTC | ✅ current, no gaps |
| OC Transpo KPI snapshots | weekly (Mon) | 2026-07-11 | ✅ cron firing; Jul 13 + Jul 20 ran, content unchanged |
| GTFS-RT raw archive (Pi, outside repo) | every sample | 2026-07-26 | ✅ 327 MB, on track (~15 MB/day) |
| Static GTFS snapshots (Pi, outside repo) | weekly (Tue) | 2026-07-21 | ✅ complete since collection began |

**There was no Jul 19–24 outage.** It was an artifact of a local clone that had not
been pulled for five days — `git log` on a stale working copy shows the last *synced*
commit, not the last *collected* reading. Verified 2026-07-26: 334 collector commits
exist on the remote across that window at normal hourly cadence, the Pi's push logs
show successful pushes throughout (`2026-07-24T15:05:06Z pushed`), per-day reading
counts hold steady at 440 weekday / 240 weekend for traffic and 560 / 336 for
transit, and Pi uptime was 24 days. Nothing failed at any layer.

**Triage rule learned the hard way: `git pull` before concluding anything from
commit timestamps.** This one false premise produced three successive wrong
diagnoses in a single session.

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

### OC Transpo Transit Ridership + Service KPIs  🔄 ~25%
- Ridership + service-quality KPIs over time. Data gap on OC Transpo site (KPIs only 2019–2022 downloadable).
- **Built:** Pi/Windows-ready scraper in [`OC_Transpo/`](OC_Transpo/oc_transpo_kpi_scraper.py) — auto-discovers Transit
  Committee/Commission meetings via eScribe's calendar API, downloads the KPI/ridership
  PDF attachments, and optionally extracts text/tables. Rate-limited, resumable, OS-trust-store TLS.
- **Next:** run it to harvest the PDFs, then design the visual.

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

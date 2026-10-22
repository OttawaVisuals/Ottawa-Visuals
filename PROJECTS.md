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

## Pipeline status — checked 2026-10-16 (✅ collectors resumed 2026-10-16 18:01 UTC after a 4.3-day gap; `collect.yml` re-confirmed running every 5 min 2026-10-20)

| Collector | Cadence | Last reading | State |
|---|---|---|---|
| TomTom traffic (`Traffic/`) | adaptive, ~hourly–15min | 2026-10-16 17:56 UTC | ✅ resumed on Cloudflare → `collect.yml`. Gap 2026-10-12 10:05 → 10-16 17:56 UTC is permanent |
| OC Transpo GTFS-RT (`OC_Transpo/`) | adaptive, ~hourly–15min | 2026-10-16 18:01 UTC | ✅ resumed (first sample: 632 trips tracked, 69 cancelled). Gap 2026-10-12 09:35 → 10-16 18:00 UTC is permanent |
| OC Transpo KPI snapshots | weekly (Mon) | files from 2026-07-11 | ✅ nothing lost: the current Open Ottawa files are byte-identical to Jul 11 (checked 2026-10-16). Job moved off the Pi to `.github/workflows/kpi_snapshots.yml` |
| Bus on-time (replaces the Pi's raw GTFS-RT archive) | every transit sample | 2026-10-16 19:11 UTC | ✅ computed live in `collect.yml` since 2026-10-16: predicted departure at each bus's next timepoint vs the timetable. Raw archive retired. Calibrated 2026-10-20: reads ~11 pts below OC Transpo's KPI, about half of it a method artefact (see item 5) |
| Static timetable (replaces the Pi's weekly GTFS download) | when OC Transpo publishes | index built 2026-10-16 (feed S1000523) | ✅ `build_schedule_index.py` runs in `collect.yml` whenever the zip's ETag changes; kept in the Actions cache, not archived |
| Disk (`/dev/mmcblk0p2`) | — | 76% used, 3.3 GB free (2026-09-03) | ❓ stale; only matters if the Pi comes back |

**Incident 2026-10-12 → (open), checked 2026-10-16 after `git pull`:**
1. The last `traffic: readings` / `transit: readings` commits on origin/main are
   2026-10-12 10:05 / 09:35 UTC. The heartbeat workflow opened issue #1 on
   2026-10-15 and has re-flagged it daily since. Other Actions (PWHL daily, Pages)
   kept running, so this isn't GitHub-wide.
2. The Pi stopped **before** the replacement was committed (`Add Cloudflare cron +
   collect.yml to replace Pi collectors`, 2026-10-14 21:44 local). Whether it was
   switched off on purpose or failed again isn't known from here.
3. `collect.yml` is active but has **zero runs ever**. The Worker code
   (`cloudflare-worker/worker.js`, `*/5` cron, `workflow_dispatch` on `main`) looks
   right, so the setup in `cloudflare-worker/README.md` was never finished: the Worker
   isn't deployed, or it has no valid `GITHUB_TOKEN`. Repo secrets also lack
   `OCTRANSPO_API_KEY` (only `TOMTOM_API_KEY` exists).
4. **To fix (needs the account owner):** create the fine-grained PAT (Actions: read
   and write, this repo only) → add the `OCTRANSPO_API_KEY` repo secret →
   `npx wrangler login`, `npx wrangler deploy`, `npx wrangler secret put GITHUB_TOKEN`
   in `cloudflare-worker/` → test with Actions → *Collect Ottawa Data* → Run workflow.
   Readings from 2026-10-12 onward can't be backfilled; the gap is permanent.
5. ~~Still Pi-only: the raw GTFS-RT archive and the weekly static GTFS download.~~
   Replaced 2026-10-16 (the Pi stopped on its own, so it's retired): `collect.yml`
   computes bus on-time live against a cached timetable index and commits only the
   summaries; `transit_daily.json` keeps daily on-time figures permanently.
   **Calibration open:** first samples read below OC Transpo's KPI. Every-stop
   measurement gave 58–64% on time for less-frequent routes (18:31–19:01 UTC) vs
   their ~70–74%; switching to timepoint departures (their method) gave 60.1% vs
   55.6% every-stop in the same 15:11 PM-peak sample. Their PM peak historically runs
   ~6 pts below all-day, so compare a full weekday's `punctuality_pct` before
   concluding there's a systematic gap.
   **Calibration checked 2026-10-20 (after `git pull`), on Mon 2026-10-19, a full
   weekday (139 samples):** less-frequent punctuality **59.0%** all day (early 20.0 /
   late 21.0), AM peak 59.4% (15.7 / 25.0), PM peak 48.0% (19.6 / 32.4). OC Transpo's
   KPI: 69.5% for Oct 2025, ~71% Oct 2025–Apr 2026; 2020–21 averaged 76.0% with 14.1%
   early / 9.9% late, AM peak ≈ all-day (+1) and PM peak ~5 pts below. Our shape matches
   (AM ≈ all-day) but the PM dip is twice as deep (−11). **Verdict: mixed — the early half
   of the gap is a method artefact, the late half is unexplained (possibly real).**
   - *Early side = artefact.* Over 78 collect.yml runs (Mon PM peak + Tue AM peak) the
     every-stop and timepoint on-time figures differ by **+0.2 / 0.0 pts on average**
     (range −5 to +7 per run; the Oct 16 "60.1 vs 55.6" was one noisy sample). If the
     feed's predictions modelled buses waiting at timepoints, the timepoint figure would
     show fewer early buses. They don't, so ~20% early (vs their ~14%) includes buses
     that will hold and leave on time. Counting every early timepoint departure as on
     time gives an upper bound of 79.0% all day (AM 75.1, PM 67.6); the truth is inside
     59–79%, and the KPI's ~70% sits in that range.
   - *Late side = unexplained.* 21% late vs ~15% implied by the KPI (100 − 71 − 14) and
     32% in the PM peak. Sampling running buses weights slow (late) segments a little more
     than a per-departure KPI does; that is worth maybe 1–2 pts, not 6.
   - *Skips don't explain it.* Per run, `not_started` is ~50% of uncancelled trips (mostly
     trips that haven't begun; excluding a bus still at its terminal biases us *up*),
     `no_timepoint` 17–18% of started buses, `far` 1–3%. The every-stop figure includes
     the `no_timepoint` buses and still matches, so dropping them doesn't move the result.
   **Rechecked 2026-10-21 (after `git pull`) on two full weekdays, Mon Oct 19 and Tue
   Oct 20 (139 samples each), less-frequent routes:**

   | Day | All-day | AM peak | PM peak | PM − all-day |
   |---|---|---|---|---|
   | Mon Oct 19 | 59.0% (early 19.3 / late 23.6) | 59.4% (15.7 / 25.0) | 48.0% (19.6 / 32.4) | −11.0 |
   | Tue Oct 20 | 57.6% (early 16.5 / late 29.1) | 54.8% (13.0 / 32.2) | 41.4% (13.0 / 45.6) | −16.2 |

   (Punctuality is the weighted `transit_daily.json` figure; the early/late split is
   delay-weighted from `trip_updates_summary.csv`, so its all-day on-time differs by a
   point or two.) **The gap persists across full weekdays and the Tue PM dip is deeper
   (−16 vs OC Transpo's ~−5), and it sits entirely in the late share** (early *falls*
   to 13% in the PM, close to their 14%). **Confirms the 2026-10-20 verdict**: early
   side = artefact, late side unexplained. Wed Oct 21 AM so far (partial, 47 samples) reads
   66.6% all-day / 62.0% AM, so the late share varies a lot by day; it may track real
   conditions, so don't read a single day as the answer. Code review of
   `poll_gtfsrt.py`: the late threshold (> +300 s) and early threshold (< −60 s) match
   OC Transpo's definition, and the timepoint matching drops passed stops and
   uses `startDate` correctly, so no clear bug. Open candidate, **not applied, awaits
   approval:** the prediction is up to 15 min ahead (`NEXT_STOP_MAX_AHEAD_S`) and may carry
   lateness the bus would recover at a layover, so also log the late share by look-ahead
   bucket and by route (log-only) to test that.
   - **Proposed fix, NOT applied (awaits approval):** log a hold-adjusted figure
     (`hold-adjusted-punctuality(less-frequent)%`, early at a non-final timepoint → on
     time) in the run log next to every-stop, leaving the CSV columns unchanged. A week of
     both figures would show where the real number sits between them. Patch + synthetic
     test (6 trips, checks headline rows unchanged) passed locally on 2026-10-20.
6. **Resolved 2026-10-16:** the owner created the PAT, added `OCTRANSPO_API_KEY` and
   deployed the Worker. The first dispatched run (17:55 UTC) succeeded and pushed
   `traffic: readings 2026-10-16 17:56 UTC`; transit was self-gated off-peak on that run,
   then the 18:00 UTC run pushed `transit: readings 2026-10-16 18:01 UTC`. Heartbeat
   issue #1 closes itself on its next daily run once it sees the fresh commits.

**Previous incident timeline (2026-08-03 → 2026-09-03, ~1 month):**
1. `traffic:`/`transit:` commits (Pi cron only) stopped dead at **2026-08-03
   15:05/15:35 UTC**, confirmed from GitHub commit history (pulled first, then diffed —
   see the outage-detection method below). GitHub-Actions collectors in the same repo
   (PWHL, ASE, weekly refresh) kept committing normally the whole time, ruling out a
   GitHub-wide issue.
2. `ssh` to the Pi timed out on 2026-09-02 — the box itself was
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
- **Progress:** ~100% · Native HTML report rebuilt Oct 18, 2026; Power BI removed.
- Five sections: stops/outcomes, demographics, collisions, speed cameras, red-light cameras; filters, maps, chart tables and CSV downloads.
- **Sources checked Oct 18:** stops through 2024; detailed collisions through 2024 (2023 absent); speed-camera tickets through Nov 2025; red-light tickets through Aug 2026; separate speed monitoring through Sep 2026. OPS 2025 year-end and Sep 19 2026 YTD summaries are kept separate with their definitions.
- Weekly source audit/rebuild; manually verified OPS snapshots stay pinned until reviewed. **Page:** `Traffic/stops.html` (`/#report-traffic` redirects there). **Method:** `Traffic/README.md`.
- **OPS release log (2026-10-20):** `Traffic/scripts/poll_ops_news.py` parses OPS news releases into `Traffic/data/ops_collision_releases.csv`. It runs hourly via `collect.yml`. The backfill covers Dec 2025 → now: 23 original collision releases (12 fatal) and 12 enforcement releases. By `collision_type`: 7 pedestrian, 5 motorcycle, 3 multi-vehicle, 2 cyclist, 2 single-vehicle, 1 each ATV / train / into-a-building, 1 unknown. Checked against CTV Ottawa (Mar–Oct): OPS released 14 of 18 fatal crashes but only 8 of 28 serious non-fatal ones. Sep–Oct is much better (14 of 16). Details are in `Traffic/README.md`.
- **CTV second source (2026-10-20):** `Traffic/scripts/poll_ctv_crashes.py` logs CTV Ottawa crash headlines from CTV's daily sitemaps, hourly via `collect.yml`. Its rows use the same `collision_type` labels as the OPS file and link to the matching OPS release. The backfill from Dec 2025 has 116 in-area crash stories, among them 29 pedestrian, 11 into a building, 8 cyclist and 24 fatal. Only 16 of the 55 fatal or serious stories have an OPS release. It's headline-only, and one crash can have several stories, so don't count rows as crashes. It is a **news-release sample (serious/fatal only), not a complete dataset**, so keep it separate from the City series. Not on a page yet. Traffic stops have no equivalent: enforcement releases give totals only.

### Ottawa Roads — risk vs enforcement
- **Progress:** ~85% (live Oct 2026) · `Traffic/roads.html`, also a home-page report (`#report-roads`).
- Neighbourhood map of police-stop share vs injury-collision share, riskiest busy intersections
  (collisions per million vehicles), and an intersection-volume index vs 2015–19 (downtown core 89%
  in 2025, rest of the city 105%).
- **Data:** weekly City + Police pull → Geo_ID join → `stories.json` (see `Traffic/README.md`).
  The same pull also feeds the rebuilt road-safety cards (photo-radar on/off, red-light trade-off).
- **Outcomes + movers tabs (2026-10-19):** `public/motions.json` (7.8k substantive motions tagged by topic via `topics.py`: title keywords, then the committee; ~1/3 of Council motions stay "Other"; 975 mover/seconder pairs parsed from `item_text`). Topics are keyword guesses and routine motions are excluded by title pattern.
- **Still to do:** the "why was the commute bad?" section, once ~4 weeks of `events_log.csv`
  (Pi, since 2026-10-08) overlap the TomTom readings.

### Taxing the Top — income tax, inequality & donations (Canada)
- **Progress:** ~80% (live Oct 2026) · `Tax/tax.html`, also a home-page report (`#report-tax`).
- Top fed+ON rate 1920–2026 vs average rate actually paid (top 0.01% / top 1% / bottom 50%);
  top-1% share vs top rate (r = −0.58 postwar); real income growth by group, 1950–80 vs
  1980–2019; Elections Canada individual donations by FSA income decile (richest tenth gives
  6.7× per filer); WID wealth shares + estate/capital-gains/PBO wealth-tax timeline.
- **Data:** Saez & Veall tables (committed CSVs), WID.world, StatCan 11-10-0055, Elections
  Canada contributions, CRA FSA stats → `Tax/scripts/build_data.py` → `tax.json`. See `Tax/README.md`.
- **Still to do:** extend WID real-income series past 2019 when WID updates; a provincial
  comparison (Quebec/Alberta top rates); an Ontario donations version (Elections Ontario, corporate
  ban 2017) if the open data has postal codes.

### Ontario's costly decisions (watchdog-costed)
- **Progress:** ~70% (live Oct 2026) · `Ontario_Costs/ontario_costs.html`, also a home-page report (`#report-ontario-costs`).
- 12 decisions, 3 Liberal (eHealth, gas plants, Fair Hydro financing) and 9 PC (cap-and-trade,
  renewable contracts, Bill 124, Ontario Place, licence fees, Greenbelt, ads, early alcohol
  expansion, $200 rebate). Each card: official figure, what it measures, watchdog finding,
  government response, source. Filters by government / type; never totals unlike figures.
- **Data:** hand-curated `Ontario_Costs/data/decisions.json`, sources checked 2026-10-10.
- **Still to do:** swap the two news-relayed FAO figures (Bill 124, licence fees) for the FAO
  reports; consider Ornge, smart meters, Skills Development Fund, Highway 413.

### Oil & Gas — profits, tax, jobs (Canada)
- **Progress:** ~60% (live Oct 2026) · `OilGas/oilgas.html`, also a home-page report (`#report-oilgas`).
- Net profit and dividends 2002–2025 (record $53B in 2022, 2025 dollars; $179B over 2021–25);
  employees down 20% from the 2014 peak while real revenue is up 8%; federal + provincial
  corporate income tax ($4.4B in 2022); jobs by province.
- **Data:** StatCan 33-10-0500-01, 33-10-0225-01, 14-10-0202-01, 18-10-0005-01 via the WDS API →
  `OilGas/scripts/build_data.py` → `oilgas.json`. See `OilGas/README.md`.
- **Still to do:** government money in and out as sourced estimates: provincial royalties,
  federal support (Trans Mountain, CCUS credit, EDC, 2020 site rehab), Alberta (Keystone XL,
  Sturgeon, orphan wells), Environmental Defence / IISD / Auditor General 2023 tallies.

### OC Transpo Ridership + Service KPIs (2019–2026)
- **Progress:** ~65% (live Oct 2026) · `OC_Transpo/octranspo_kpis.html`, also a home-page report (`#report-octranspo`).
- Ridership 2019 vs 2022–25 (2025 = ~72% of 2019), weekday ridership share by time of day (a.m. peak
  26% → 23%, midday 29% → 34%, winter 2020 vs 2026), 2023–25 scorecard reliability vs targets, and the
  published monthly figures (Line 1 service not delivered 2020–21, trips delivered Aug 2022–Aug 2023,
  weekday bus punctuality by peak 2020–21). Gaps are left empty; hours-based and trip-based delivery
  measures are never spliced.
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
- **Extracted (2026-10-16):** `OC_Transpo/scripts/extract_kpis.py` pulls the numbers out of the extracts with one
  explicit spec per document (11 of 65 English PDFs carry KPIs; the rest are logged with a reason) →
  `OC_Transpo/kpi_history/` (1,114 observations → 828 series points, 6 source conflicts logged). After 2021 the
  monthly charts are images, so 2022+ monthly values exist only where a deck printed them.
- **Still to do:** add recent months from the Open Ottawa KPI snapshots (`rt_data/kpi_snapshots/`, since Jul 2026),
  after checking their definitions match the report measures; add new scorecards/decks as specs when published.

### Ottawa Ward Elections
- **Progress:** ~90% (live, iterating) · Interactive ward-level election map/visual.
- Ongoing work on ward redistribution impact + Deneb custom visual with ward labels/leader lines.
- 2026-10-16 (pre-election): map gained a 2010/2014/2018/2022 year selector (`?year=` in the URL), a "Mayor race: largest group" map mode (`?map=mayor`; didn't-vote / elected mayor / other candidates as % of registered voters; "Didn't vote" is the largest group in every ward in all four elections), a "ward winner (voters only)" mode (`?map=winner`; e.g. 2022: Sutcliffe 19 wards, McKenney 5), a turnout colour scale fitted to 30–55%, working nav links, dark-mode labels and a mobile layout. A sortable ward list (turnout, change vs previous election, top mayoral candidate) fills the side panel until a ward is picked. The ward panel also lists who won the council seat in each election 2010–2022, with vote share and re-elected/new tags. The mayor chart can switch from % of registered voters to % of all residents (StatCan population and under-18 estimates; ?basis=residents): in 2022 the mayor was elected with the votes of 14.9% of residents.
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

### PWHL Dashboard
- **Progress:** ~85% (live, multi-page) · every PWHL
  season (2024 → 2025-26 plus playoffs/preseason) from the league's HockeyTech feed, refreshed by
  the `daily_update.yml` GitHub Action (last run checked green 2026-10-09 22:51 UTC).
- **Pages (split 2026-10-10):** Home (standings, leaders, bracket, transactions) · Forecast (Elo,
  win chances, 10,000-run playoff odds, prediction scorecard) · Teams + a page per team (outlook,
  results, top contributors, most-used 5v5 lines, roster stats, franchise leaders, current roster,
  incl. the four 2026-27 expansion teams) · Players (sortable table) + a page per player (role tag,
  shot map, shot mix by type, goalie matchups, home/away, best games, career) · Superlatives (incl.
  the Vulture, Shin-Pad Shooter, Rap Sheet, Hall of Sustained Quirk) · How it works.
- **Models:** expected goals (logistic, held-out AUC ~0.69), player impact ratings (5v5 RAPM +
  finishing/penalties/faceoffs), Elo forecasts. **2026-10-10 fix:** the feed's on-ice lists at goals
  were unions across line changes, so the ratings had been skipping ~half of 5v5 goals; they're now
  rebuilt from the goal's plus/minus lists (median rating moved ~0.1 goals).
- **Gotcha:** `PWHL/data/pwhl_pbp.csv` is gitignored and goes stale locally — download CI's
  `pwhl-pbp` artifact before running `build_models.py` by hand (a stale copy silently drops older
  seasons to the box-score ratings fallback).
- **Open:** in-game win probability; line chemistry (together vs. apart).
- **Page:** `/PWHL/pwhl.html` · on the homepage as report *PWHL dashboard* · details in
  [`PWHL/README.md`](PWHL/README.md).

---

## 🔄 In Progress

### City Hall Index — searchable council & committee records
- **Progress:** ~75% (public search page live Oct 2026) · `CityHall_Index/`, page `cityhall.html`.
- **Public page (2026-10-19):** `cityhall.html` searches 17.8k substantive agenda items client-side from `CityHall_Index/public/items.json` (title, body, date, report number, decision, first motion, eScribe link; procedural items dropped). `export_public.py` builds it and runs at the end of `weekly_update.py`; the weekly run doesn't commit, so commit the refreshed JSON by hand.
- eScribe indexer: 1,898 meetings 2020–2026 → meetings / items / motions / votes / attachments,
  plus `item_text.csv` (everything each item's page shows; pre-2022 meetings as one whole-page
  text each). `search.py` = SQLite full-text search with snippets, meeting + PDF links, CSV export.
- **PDFs:** eScribe's PDF links sit behind a browser check (since Oct 2026), so scripts can't
  fetch them. Workflow: `search.py --pdf-list` → download in a browser → `ingest_pdfs.py`
  matches each PDF to its item and makes it searchable page by page.
- **Weekly:** `weekly_update.py` indexes new meetings and re-indexes ones first seen before
  their minutes were posted (eScribe also swaps placeholder meeting IDs; those get dropped).
  Scheduled on the desktop PC (Windows Task Scheduler, "OttawaVisuals CityHall weekly",
  Sundays 09:00, catches up at next start if missed; set up 2026-10-09). Not on the Pi: the
  index is gitignored, so it lives where search and the PDFs are. Log: `data/weekly_update.log`.
- **Votes split (2026-10-19):** `split_votes.py` → `data/votes_by_member.csv` (6,188 member votes, one row each; names normalised to "initial. surname"; every tally's stated count matches the names parsed). Run by `weekly_update.py`.
- **Votes view (2026-10-19):** "Recorded votes" tab on `cityhall.html` (`public/votes.json`, 349 motions with named votes; 189 at Council): per-member table with how often each was on the losing side, click to filter, closest votes first. Callout explains that names are recorded only for contested motions.
- **Still to do:** add it to the home-page `REPORTS`; PDF full text stays local-only.

### RTO4 Impact Page — "Ottawa RTO Watch"
- **Progress:** ~45% · Live dashboard at `/rto.html` (roads + OC Transpo live sections;
  former `Traffic/traffic.html`, which now redirects).
- **Before/after charts (2026-10-17):** section 5 now compares 311 (central wards, roads,
  parking, all) and the IESO weekday÷weekend ratio with the *same weeks a year earlier*, in
  three windows: 12 weeks before RTO4, phase-in (Jul 6–Sep 13), full RTO4 (week of Sep 14 on).
  Dot plot + 4-week rolling line, computed in the page from `RTO4/data/` (refreshed the same
  day). First read: central-ward 311 went +1% → −9% (phase-in) → −1% (full); city-wide roads
  and parking stayed ~+12–20% throughout; electricity ratio flat. Still missing: commute and
  transit before/after (needs the TomTom MOVE backfill, and KPI months after Apr 2026).
- **Collectors healthy (2026-07-26)** — see the pipeline status table above.
- Commutes (TomTom, collecting since Jul 2026) + transit (own GTFS-RT logging on the Pi +
  official KPI snapshots + eScribe history) + TBS NCR headcounts, 311, bike counters, IESO load.
- **Plan / data inventory:** [RTO4_PLAN.md](RTO4_PLAN.md) · collector docs in [OC_Transpo/README.md](OC_Transpo/README.md)

### Ontario Elections Visual (coalition scenarios)
- **Progress:** ~95% (bumped from a stale ~70% on 2026-09-03) · Past Ontario elections with a
  "what if the opposition consolidated" scenario model, per-riding survivor logic,
  strategic-candidate flip-threshold analysis, turnout/gauge charts.
- Combined multi-zoom GeoJSON filled map (main + 2 zoom insets, custom placement).
- **Live:** [`Ontario_Elections/ONelections.html`](Ontario_Elections/ONelections.html), embedded on the homepage.
- **What changed 2026-10-09 (design pass):** reframed the headline around the coalition question
  and reordered the page (map → gauges → winnable seats → table → turnout history → methodology);
  moved the coordination slider into the map card (moving it switches the map to "Modelled");
  "Most winnable" is now a clickable card grid that opens the riding on the map; the full table
  got a name search + "flips only" filter; on phones the Ottawa/Southern Ontario insets stack
  full-width under the main map. Fixed dark-mode bugs: unreadable white-on-white map tooltip,
  hard-coded light banner/flip-tag colours, and the topbar brand subtitle running into the name.
- **What changed 2026-09-03:** confirmed the page was already substantially further along than
  ~70% (build_data.py runs clean with 100% name-join coverage, zero console errors, real data
  loads correctly — the file:// preview tool's "sample data" banner was a preview-tool artifact,
  not a real bug). Added the missing piece: a "flip threshold" per PCP-held riding (minimum
  vote-transfer share needed for the opposition survivor to overtake PCP's actual vote count,
  solved directly rather than read off the slider), surfaced as a "Most winnable PCP-held seats"
  ranked list and a per-riding "Vote-splitting" callout. Filled in the previously-empty
  `Ontario_Election_Methodology.txt`.
- **Location:** `C:\Ottawa_Visuals\Ontario_Elections`. (`Ontario_Trials` is a different, unrelated
  project — Ontario Court Cases — despite the similar name; the old "+ Ontario_Trials" location
  note here was wrong and has been removed.)
- **What's left for 100%:** none of it code — just occasional review as Elections Ontario data
  ages, and the separately-tracked Ontario government spending companion visual is
  still just an idea, not scoped.

### Ontario Court Cases
- **Progress:** ~30% · Extraction/structuring of Ontario Court traffic cases → CSV/JSON, then a visual.

### Ottawa Geothermal Suitability Map — live (this entry was stale; corrected 2026-09-03)
- **Progress:** ✅ **live**, not the ~15% this entry previously said. **Ottawa-scoped, not national** —
  a prior version of this entry mislabeled it as a national feasibility map; the well data (WWIS) is
  Ontario-only and the built map is Ottawa-only ("Quebec side of the river is empty by construction").
- **Live:** <https://ottawavisuals.github.io/Energy/Geothermal/output/>
- **What it actually is:** a ground-source-heat-pump suitability map combining WWIS well records, GSC
  bedrock geology, City of Ottawa zoning/sewer/open-loop-potential layers, and Hydro Ottawa feeder
  capacity, with a literature-sourced (VDI 4640) conductivity table editable live in the map, a
  drilling-difficulty layer, and three per-segment suitability scores (residential / large buildings /
  district energy). A second, separately-tracked sub-project on top of it models building-level heat
  demand and electrification load (414k buildings, census-reconciled stock, three electrification
  scenarios, grid-capacity integration) — still being actively built as of 2026-08-03.
- **Location:** `C:\Energy\Geothermal` — full build log in `GEOTHERMAL_STATUS.md`, method docs in
  `README.md`.
- **What's genuinely still missing:** an "Ottawa Case Study" narrative page (Phase 6 of
  `HEATDEMAND_PLAN.md`) — a plain-language front door explaining the six-step argument (grid
  constraints → ground resource → building heat loads → electrified share → electrification peak vs
  grid → candidate areas). The map itself is not what's unfinished.
- **True national expansion is a distinct, essentially unstarted idea** (~0%, not ~15%) — WWIS is an
  Ontario-only well database, so scaling past Ottawa needs a different well-data source per province,
  not just re-running the existing pipeline on a bigger bounding box. Worth scoping separately rather
  than assuming it inherits the Ottawa build's progress.
- **⚠️ Worth a follow-up check, unrelated to scope:** the 2026-08-03 entry in `GEOTHERMAL_STATUS.md`
  describes a near-miss where 1,429 of 4,903 published files were found missing from that local working
  copy — running `deploy.sh` from that machine at the time would have wiped several other live Energy
  pages (New Homes Explorer, CEUD, Construction Tracker, grid dashboard, all FSA maps) plus this map's
  own output. Recorded there as recovered, but worth confirming directly rather than assuming it stayed
  fixed.

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
- **Page built (2026-10-19):** `govcontracts.html` (management consulting 2017–2025, records, top departments, office-furniture yardstick). IT consulting left out: the 2021 switch from GSIN to UNSPSC codes broke the series (details in `GovContracts/README.md`). Not yet linked from the home page.
- **Not yet built (original idea):** the page. Presentation idea floated but not built: stacked bar per year
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
- MP expense reports (all parties, House of Commons proactive disclosure); Alberta oil-company profits & capital flows
  (industry-level profits/tax/jobs now live in `OilGas/`; company-level capital flows still open).

---

## ☐ Backlog / Future

- **Ottawa Census Data** — age, income, languages… *(site roadmap)*
- **Ottawa Biking** — % of commute vs. % of city roadway; city spending; NCC vs. City. *(site roadmap)*
- **RTO Road Maintenance** — spending on road maintenance; office permits. *(site roadmap)*
- **Ottawa Building Permits** — permit data analysis/visual.
- **Bike Collision / Traffic Collision Map** — Ottawa collision data.
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

# RTO4 Page — Plan & Data Inventory

> The comprehensive return-to-office page. Anchors the Quality-of-Life narrative
> in PROJECTS.md. Drafted 2026-07-11, five days after RTO4 took effect.

## Why now

- **Sept 9, 2024** — RTO3: federal public servants required in office 3 days/week
  (executives 4).
- **Feb 2026** — Treasury Board announces RTO4 (4 days/week).
- **May 2026** — executives move to 5 days/week; return to assigned seating announced.
- **Mon Jul 6, 2026** — RTO4 takes effect, phased implementation Jul 6 → Sep 15
  where space is short (Global Affairs, Health Canada flagged).
- **Sep 30, 2026** — PSPC closes GCcoworking sites, reallocates to departments.
- PIPSC and PSAC have filed unfair labour practice complaints.

Sources: [CBC](https://www.cbc.ca/news/canada/ottawa/rto4-ottawa-gatineau-federal-public-service-9.7257909) ·
[Radio-Canada](https://ici.radio-canada.ca/rci/en/news/2267187/federal-workers-return-to-the-office-4-days-a-week-will-it-be-smooth-sailing-or-another-hot-mess) ·
[Ground News roundup](https://ground.news/article/office-space-scarce-as-federal-public-servants-return-to-the-office-four-days-a-week)

The natural experiment: **July–September 2026** is the treatment window, with
RTO3 (Sept 2024) as the previous step. Every dataset below should be framed as
*before / after Jul 6, 2026* (and where history allows, *before / after
Sep 9, 2024*).

## Data inventory

### Already collecting (ours)

| Dataset | Where | RTO4 relevance |
|---|---|---|
| TomTom corridor commute times (5 corridors × 2 directions) | `Traffic/data/`, Pi, since Jul 2026 | The headline chart: door-to-door commute minutes before/after Jul 6 |
| TomTom segment speeds (15 points) + incident/jam summaries | `Traffic/data/` | City-wide congestion proxy |
| TomTom MOVE backfill: Aug 2024 baseline vs Aug 2026 | `Traffic/BACKFILL_SPEC.md` | Aug 2026 now captures RTO4, not just RTO3 — the plan got more valuable |
| Weather (ECCC daily/hourly) | `Weather/` | Control variable for traffic/transit comparisons |

### Start now (this commit adds the tooling)

| Dataset | Tool | Notes |
|---|---|---|
| OC Transpo GTFS-RT: cancellations, active fleet, raw predicted arrivals | `OC_Transpo/scripts/poll_gtfsrt.py` on the Pi | Our own reliability dataset; OC Transpo publishes no history. Live metrics = cancellations + fleet; true OTP computed offline from the raw archive vs static GTFS (feed publishes predicted times, not delays). Feed is bus-only — O-Train reliability comes from the KPI snapshots. **Every day before Sep 15 is baseline.** |
| Official OC Transpo KPI spreadsheets (4 files, Open Ottawa) | `OC_Transpo/scripts/snapshot_kpis.py` weekly | Monthly ridership, OTP, service delivery, daily bus delivery %, undelivered-trip reasons, fleet health. **Rolling ~13-month windows — snapshot or lose it.** |

### Available, to pull when building the page

| Dataset | Source | Angle |
|---|---|---|
| eScribe Transit Committee KPI PDFs (2019+) | `OC_Transpo/oc_transpo_kpi_scraper.py` (already built) | Extends ridership/OTP history back past the rolling window |
| TBS federal public service headcount, NCR series | open.canada.ca ([dataset](https://open.canada.ca/data/en/dataset/f0d12b41-54dc-4784-ad2b-83dffed2ab84)) | The denominator: how many workers RTO4 moves. ~40% of the core public service is NCR |
| Ottawa 311 service requests (rolling CSVs + Open311 API) | Open Ottawa | Downtown service pressure; parking complaints; garbage |
| IESO Ottawa-zone hourly electricity demand (2003–present) | reports-public.ieso.ca `/DemandZonal/` | Weekday daytime load shift downtown — an office-occupancy proxy with 20+ years of history |
| Bicycle Trip Counters | Open Ottawa (Excel) | Mode shift on Laurier etc.; multi-year history |
| OC Transpo GTFS static (daily snapshots archived externally) | [Mobility Database](https://mobilitydatabase.org) / transitfeeds archive | Scheduled service levels over time — did OC Transpo add service for RTO4? |
| StatCan LFS work-from-home rates by CMA | StatCan tables (search "work from home") | Ottawa–Gatineau WFH share over time — the policy-compliance curve |
| Directory of Federal Real Property (DFRP) | open.canada.ca | Federal office buildings + floor area in the NCR; map where RTO4 lands |
| Ottawa collisions (annual geocoded files) | Open Ottawa | More cars → more crashes? Join with ASE data already held |
| Parking: paid-parking spaces, pay & display machines | Open Ottawa | Supply side; price history needs Parkopedia/Wayback (manual) |
| Downtown office vacancy | CBRE/Colliers quarterly reports (manual transcription) | The commercial-landlord beneficiary angle |

### GitHub prior art (searched 2026-07-11, ~76 octranspo repos)

**Nobody publishes a continuous public archive of OC Transpo GTFS-RT.** The
niche is genuinely open. Closest finds:

- [gmyx/OCWatch](https://github.com/gmyx/OCWatch) — "evidence project to get better
  data on OCTranspo"; polls vehicle positions every 30 s (batch scripts + node),
  active Mar 2025–Jan 2026, but **raw data not committed to the repo**. Worth
  contacting if a longer backfill ever matters.
- [ledidk/octranspo_analysis](https://github.com/ledidk/octranspo_analysis) —
  "The Reliability Tax" (2026): fares vs ridership vs cancellations analysis.
  No RT logging, but a good source map — it's how we found the official
  Open Ottawa KPI spreadsheets, and its framing (255 cancelled trips/day,
  $138.50 pass) is quotable context.
- [cyclingzealot/ghost_bus](https://github.com/cyclingzealot/ghost_bus) — ghost-bus
  measurement idea (2022), empty repo. Validates the concept, no data.
- [lchski/octranspo-new-ways-to-bus-data](https://github.com/lchski/octranspo-new-ways-to-bus-data) —
  Lucas Cherkewski's New-Ways-To-Bus schedule analysis (static GTFS, Apr 2025).
  Useful methodology for schedule-level comparisons (stop-level service counts by ward).
- Generic archiving tools if we outgrow CSV summaries:
  [gtfs-realtime-capsule](https://github.com/tsdataclinic/gtfs-realtime-capsule),
  [gtfsrdb](https://github.com/CUTR-at-USF/gtfsrdb).

## Page structure

> **Status (2026-07-25): built.** `/rto.html` is now the full eight-section page,
> and `RTO4/` holds the external-data fetchers plus the committed aggregates it
> loads. See [`RTO4/README.md`](RTO4/README.md) for the per-dataset capability
> matrix. Sections 1–8 below are live; the outstanding gaps are listed under
> "Immediate next steps".

1. **The mandate** — policy timeline (RTO3 → RTO4 announcement → Jul 6 → Sep 15 →
   GCcoworking closure). *Still missing the TBS NCR headcount as the "how many
   people" scale-setter — see step 5.*
2. **Commutes** (live) — corridor travel times, map, congestion status, plus daily
   AM-peak and city-congestion trend charts from `Traffic/data/history/`.
3. **Transit** (live) — buses, cancellations, fleet speed, plus daily peak-fleet
   and cancellation-rate trends from `OC_Transpo/rt_data/history/`.
4. **Downtown parking** (live, new) — municipal garage occupancy via
   `Traffic/scripts/poll_parking.py`. The most direct office-occupancy proxy we
   have; only 4 downtown lots publish live counts.
5. **The city responds** — 311 weekly volumes (with a real 2025 control), IESO
   weekday÷weekend load ratio, bicycle counters (baseline only — see below).
6. **The City's own counts** — annual intersection/midblock volumes, the 2020
   COVID "% of normal" series as the step-change yardstick, collisions by year.
7. **Emissions** — GHG inventory 2012–2024 by sector, plus a commute-emissions
   estimate expressed **per 10,000 drivers** so it carries no invented headcount.
8. **Methodology & limits** — every source, cadence and caveat, including the
   datasets checked and rejected.

### What the build established about the data

- **311 is the best external series** — daily source, and the previous-year file
  gives a genuine same-calendar-week 2025 control. Nothing else here does.
- **Bicycle counters cannot show RTO4.** Coverage ends Mar 31, 2026 and only the
  Adàwe counters still report in 2026, so the cross-year total is not comparable.
  Charted as a pre-RTO4 baseline with the limit stated on the page.
- **Volume counts and GHG cannot show RTO4 either** — annual, latest edition 2024.
  Kept as context, explicitly labelled.
- **Park & Ride occupancy does not exist** in the feed (capacity only), which
  removes what would have been an excellent commuter indicator.
- **The COVID monitoring series is % of normal, not counts** — which makes it the
  natural yardstick: a real collapse took the AM peak to ~a third of normal.
- **Collisions are missing 2023**, and the 2024 injury total looks
  under-coded, so injuries are not charted.
- **A stale-data banner is now live** (P0 item 2 below): the page compares the
  newest reading to now and warns past 2 hours, so old numbers are never
  presented under a green "live" dot.

## Immediate next steps

*Reviewed 2026-07-25, after the page build.*

**Done**

- Both pollers are collecting again — readings run through Jul 25 for traffic and
  transit. (The Jul 19 → Jul 24 outage is a real gap in the series; it shows as a
  gap in the charts rather than being interpolated.)
- The stale-data banner is live in `rto.html` (old P0 item 2).
- Bike counters and IESO zonal CSVs are pulled (old P1 item 5, partially) — see
  `RTO4/scripts/`.
- Parking-garage occupancy collection added and wired into `pi_poll.sh`.

**P0 — deploy the new collector and verify it survives**

1. Pull on the Pi so `poll_parking.py` and the updated `pi_poll.sh` land there, then
   confirm after one cycle that `Traffic/data/parking_summary.csv` is growing and
   that a parking-feed failure does not stop traffic collection (the call is
   deliberately non-fatal — verify that, don't assume it).
2. The Jul 19–24 outage still has no diagnosis. Check `~/traffic_poll.log` and
   `~/transit_poll.log` for what happened, so the next one is preventable rather
   than merely visible.

**P1 — stop the ongoing data loss**

3. `snapshot_kpis.py` still has only the manual `2026-07-11` snapshot; Jul 13, 20
   were missed and now Jul 27 is due. Run it by hand, then verify the weekly cron
   line (`20 9 * * 1`) is actually installed. These are **rolling ~13-month
   windows** — a missed week is gone for good, which makes this more urgent than
   the live feeds even though it looks smaller.

**P2 — the baseline problem (unchanged, and now the main constraint)**

4. Our own collection starts Jul 6, 2026 — *the day RTO4 took effect*. The build
   confirmed there is no self-collected "before", and that only 311 and IESO carry
   a usable external control. The TomTom MOVE backfill (`BACKFILL_SPEC.md`,
   Aug 2024 vs Aug 2026) and the eScribe KPI history remain the only source of a
   real "before" for commutes and transit. Treat the MOVE trial as
   schedule-critical and book it against the Aug 2026 window.
5. Pull **TBS federal headcount for the NCR** — still the biggest hole. Section 1
   has no scale-setter and section 7's emissions figure is deliberately a rate
   (per 10,000 drivers) because the headcount is missing. Also worth pulling:
   StatCan work-from-home rates by CMA (the compliance curve) and downtown office
   vacancy from brokerage reports (manual).
6. Run the eScribe scraper for 2026 meetings to refresh the deep history (feeds
   step 4's "before" side).
7. Re-run `refresh_all.py context` once a 2025 or 2026 volume edition appears —
   that is the moment the City's own counts can finally speak to RTO4.

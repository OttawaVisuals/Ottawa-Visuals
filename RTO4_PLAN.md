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

## Page structure sketch

> **Status:** `/rto.html` ("Ottawa RTO Watch") is live — the former
> `Traffic/traffic.html` dashboard rebranded around RTO4 (old URL redirects),
> with a live OC Transpo section (buses active, trips tracked, cancellations,
> fleet speed + today sparkline). Sections 2–3 below are its live core;
> the historical before/after charts get added as `Traffic/data/history/` and
> `OC_Transpo/rt_data/history/` accumulate.

1. **The mandate** — timeline strip (RTO3 → RTO4 announcement → Jul 6 → Sep 15
   full compliance → GCcoworking closure), TBS NCR headcount as the "how many
   people" scale-setter.
2. **Commutes** (live) — corridor travel times, peak vs baseline; Aug 2024 vs
   Aug 2026 MOVE comparison when it lands.
3. **Transit** (live) — our GTFS-RT on-time %, cancellations, active fleet;
   official monthly ridership/OTP from KPI snapshots + eScribe history for context.
   Key question: did service keep up with forced demand?
4. **The city responds** — 311 volumes, bike counters, IESO downtown load curve,
   collisions.
5. **Who wins** — parking prices/supply, office vacancy, GCcoworking closures.
6. **Methodology** — every dataset linked, collection cadence documented (the
   credibility section; this repo *is* the methodology).

## Immediate next steps

1. Register the Nextrip API key, drop it in `~/.ottawa_visuals.env` on the Pi.
2. `python3 OC_Transpo/scripts/poll_gtfsrt.py --force --debug` once to verify
   the JSON field casing against the live feed, then install the cron lines
   (see `OC_Transpo/README.md`).
3. Run `snapshot_kpis.py` immediately (done at repo setup) — the current window
   still contains Apr 2025+, i.e. pre-RTO4 baseline months.
4. Pull TBS headcounts + bike counters + IESO zonal CSVs when page build starts.
5. Optional: run the eScribe scraper for 2026 meetings to refresh the deep history.

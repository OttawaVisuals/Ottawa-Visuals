# Ottawa Traffic Collection

## Traffic stops report (no Power BI)

[`stops.html`](stops.html) is a static Chart.js + Leaflet report with nine tabs:
summary (the default), collisions, where it happens, police stops, driver demographics,
speed cameras, red-light cameras, traffic court and ticket revenue.
Filter scopes are stated beside the controls. Each chart has a data table;
filtered CSV downloads and URL filters are supported. The police location map
is explicitly **all years and outcomes**: its rollup does not retain those dimensions.

**Official sources checked October 18, 2026:**

| Series | Coverage verified | Notes |
|---|---|---|
| Police traffic stops | 2014–2024 | No newer stop records found in the public layer/catalogue. All four outcomes retained. `Final` is not assumed to mean “no action”. |
| Detailed City collisions | 2017–2022, 2024 | No 2023 records or newer detailed layer found. Missing 2023 is a gap, not zero. |
| Speed-camera violations | July 2020–November 2025 | Enforcement ended November 14, 2025; November is a shortened month. |
| Red-light violations | January 2015–August 2026 | 2026 is incomplete. The collector discovers new year services. |
| Former speed-camera site monitoring | Dated observations through September 2026 | Pre-installation/active/removed stages and undated baselines retained. Not ticket counts or a causal estimate. |
| OPS collision summaries | 2025 year-end; 2026 through September 19 | Same-period comparisons from the same publication, never appended to the City series. |

The OPS summaries linked in the report were visually transcribed and checked
against the published images on October 18. Figures describe **incidents**, not
people killed/injured; severity covers officer-attended collisions. Their 2026
tickets/warnings measure is not the stop-record count. These snapshots are pinned,
not automatically OCR-updated; the audit records newer available OPS publications.

Reproduce after the regular City/Police fetch and Geo_ID build:

```text
python Traffic/scripts/fetch_city_traffic.py --only cameras,speed_monitoring
python Traffic/scripts/build_stops_report.py --refresh
```

The weekly workflow runs these after the existing fetch and join. `--refresh`
checks both public catalogues, reconciles live annual stop/collision totals to
local files, and aggregates monthly stops from official occurrence dates. A cached
rebuild uses `python Traffic/scripts/build_stops_report.py`.

Outputs: `data/police/traffic_stops_monthly.csv`,
`data/city/ase_removal_monitoring.csv`, and `data/derived/stops_report/` (one report,
a timestamped source audit, and collision locations loaded only for the selected year).
No Power BI, server or API key is needed to view the report. Fonts, Chart.js,
Leaflet and basemap tiles use external CDNs; tables remain usable if Chart.js
fails. Serve over HTTP for previews; `fetch` cannot load a `file://` page.

Checks: annual/monthly/area/driver police totals reconcile; camera site-months are
unique. OPS hour is encoded HH00 (`1400` becomes hour 14); missing 2014 hours stay
in an Unknown bar. Demographic shares include unknowns and have no population or
driving-exposure adjustment. Camera averages divide by **reporting** sites/approaches,
including numeric zeroes; unpublished months remain missing. Individual speed
readings are not averaged across sites because exposure weights are unavailable.

Detailed collision wards use the existing Geo_ID join to 2022–2026 boundaries;
unmatched records remain a category. Police location counts under three are rolled
into `(other)` by the existing collector and are not mapped. Parties involved
are recorded road users/vehicles, not injuries; blank party counts are omitted.

TomTom's live map has no history, so this pipeline **builds its own** by polling
TomTom APIs on a schedule and appending every reading to CSV. A few weeks of runs
gives a real time series for the commute / RTO / quality-of-life narrative.

## Traffic court tab

[`Traffic court`](stops.html?section=court) reuses the audited
[`Ontario_Trials/data/outcomes.json`](../Ontario_Trials/data/outcomes.json) snapshot
and shared outcome definitions. Reviewed October 23, 2026; separate from the weekly
City/Police refresh. See [court methodology and rebuild instructions](../Ontario_Trials/README.md).

- Ottawa City Highway Traffic Act **charges completed**, calendar years 2015–2025.
  The publication indexed as 2026 covers April 2025–March 2026 and is excluded.
- The mix is speeding, red lights and **all other HTA offences combined**. All other
  is the parent total minus speeding and red lights; it includes the separate source
  catch-all. All 15 source detail rows reconcile to HTA for every metric/publication.
- Offence selects all three KPIs (completed, prepaid, guilty pleas/default), the
  first chart and detail table. KPIs/table use the latest calendar year, explicitly
  labelled; there is no year picker. The first stacked chart shows that offence's
  annual completions grouped by outcome. Count/share buttons apply to the outcome
  and HTA-mix charts. CSV contains every calendar year for the selected offence,
  raw outcomes, grouped counts/fractional shares, camera coverage and source locations.
- Five outcome groups: prepaid; guilty (pleas plus no response/attendance);
  withdrawn; other; trial with unavailable verdict. Trial results are not split into
  guilty/acquitted; no complete conviction rate is available. Raw categories remain
  separate in the CSV. Context charts retain all HTA offences.
- Camera tickets **issued** appear alongside court **completions** for context.
  They are not matched cohorts and can occur in different years. Court data combine
  officer and camera enforcement, so an exact automated-enforcement share is unknown.
  Missing camera years stay missing; 2025 speed-camera coverage is 11 months with
  November shortened. Reporting months do not imply every site reported each month.

Checks: `node --test Traffic/scripts/test_court.cjs Ontario_Trials/scripts/test_outcomes.cjs`.
Court data load on first opening the tab, with retry and a link to the full report.

## What it collects

| Dataset | File | API | Meaning |
|---|---|---|---|
| Corridor travel times | `data/corridor_travel_times.csv` | Routing API | Door-to-door commute seconds, each corridor ↔ downtown, both directions |
| Segment speeds | `data/segment_speeds.csv` | Traffic Flow Segment Data | Current vs free-flow speed at 15 road points across the city |
| Incident/jam summary | `data/incidents_summary.csv` | Traffic Incidents API | Per-sample jam count, total jam length (m) + delay (s), and all-incident totals |

Targets (5 corridors, 15 segments, 1 incident bounding box) are defined in [`corridors.json`](corridors.json) — edit that file to add/change locations, no code change needed.

### Recreating the TomTom "live traffic" panel

This collects a **logged, historical** proxy of the live panel on
<https://www.tomtom.com/traffic-index/city/ottawa/> — the thing TomTom shows live
but keeps no history for. Derive at build time:

| TomTom live tile | From our data |
|---|---|
| Average speed | mean `current_speed_kmh` across segments |
| Distance driven in 15 min | `avg_speed_kmh ÷ 4` |
| Congestion level % | mean `1 − current_speed_kmh ÷ free_flow_speed_kmh` |
| Traffic jams | `jam_count` from the incident summary |
| Total jam length | `jam_length_m` |
| Rush-hour extra time | logged peak vs off-peak `travel_time_s` (with trend — better than the live page) |

Numbers are a sampled proxy (our chosen points), not TomTom's whole-network figures — directionally accurate, not identical.

## Cadence

The workflow ([`.github/workflows/traffic.yml`](../.github/workflows/traffic.yml))
fires every 15 min; [`scripts/poll_traffic.py`](scripts/poll_traffic.py) decides
whether each tick is a sample:

- **Weekday rush hours** (AM 06:30–09:30, PM 15:30–18:30 Ottawa local): every run (~15 min).
- **All other times**: only the top-of-hour run (hourly).

The gate lives in the script (not the cron) so it follows Ottawa DST correctly.

## Cost — free

TomTom free tier (as of July 2026, no credit card): **20,000 requests/month per API**.
This config uses ~11K routing + ~17K flow + ~1.1K incident requests/month — each under its own 20K limit.

## Setup (one time)

1. Create a free key at <https://developer.tomtom.com/> (no card required).
2. Add it as a repo secret named **`TOMTOM_API_KEY`**
   (Settings → Secrets and variables → Actions → New repository secret).
3. Enable the workflow (Actions tab) — or trigger it manually with **Run workflow**.

## Test locally

```bash
export TOMTOM_API_KEY=your_key_here
python Traffic/scripts/poll_traffic.py --force   # --force bypasses the peak/hourly gate
```

## Road events + cameras (Pi, every 15 min)

[`scripts/poll_events.py`](scripts/poll_events.py) runs from `pi_poll.sh` beside the
TomTom and parking pollers. It explains TomTom spikes: what was closed, and where, at the time.

| File | Meaning |
|---|---|
| `data/events_log.csv` | Append-only change log: a `new` / `updated` / `cleared` row each time an event appears, changes, or leaves the feed. Duration = `cleared` − `new`. |
| `data/events_summary.csv` | One row per source per run: active events by type, full closures, high-priority count |
| `data/events_active.json` | Current active set; the poller diffs against it. Don't edit it. |
| `data/cameras.csv` | Traffic camera inventory (about 400 city + 29 MTO), refreshed daily at 04:00. Metadata only, no images. |

Sources: the City's traffic-map feed (`traffic.ottawa.ca/service/events`, no key), plus
Ontario 511 within the Ottawa area if `ONTARIO_511_KEY` is set (see `PI_SETUP.md`).
If a feed suddenly drops below 20% of its previous event count, the run is logged as an
error and the state is kept. Otherwise one glitch would "clear" every event and then
re-add them all.

## Summary tab on `stops.html`

[`kpis.js`](kpis.js) fills the three cards on the Summary tab (the default tab) from local files, with no build step.
Each card fails on its own.

| Card | Source | Notes |
|---|---|---|
| Fatal collisions, 2026 so far vs all of 2025 (22, from `ops_annual_report_traffic.csv`) | `snapshots` in `data/derived/stops_report/report.json` (hand-transcribed OPS figures) | The "at least N more since" line counts fatal, non-follow-up rows in `data/ops_collision_releases.csv` dated after the snapshot cutoff. It is a floor. |
| Congestion, worst hour of the day | `data/history/city_daily.json` (`peak_congestion_pct`) | Median of the last 7 weekdays vs the median of all weekdays on record. |
| OC Transpo buses on time vs target | `OC_Transpo/kpi_history/kpi_observations.csv` (official monthly punctuality + scorecard target) | The live tracker figure from `rt_data/history/transit_daily.json` is shown as context only. It is measured differently. |

## TomTom Traffic Index log (daily)

[`scripts/poll_tomtom_live.py`](scripts/poll_tomtom_live.py) saves the hourly city-wide readings behind the
tiles on <https://www.tomtom.com/traffic-index/city/ottawa/> (speed and jam tiles read from the same public file the
page loads, `traffic-index/api/live-traffic.json?city=CAN_ottawa_new`). It holds about a week of hourly records, so one
fetch a day leaves no gaps. It runs from `collect.yml`, self-gates to once per Ottawa day after 05:00, waits an hour
after a failure, and identifies itself in the User-Agent.

| File | Meaning |
|---|---|
| `data/tomtom_ottawa_hourly.csv` | One row per TomTom record, keyed on `update_utc` (a later fetch overwrites the same hour). `congestion_pct` / `congestion_usual_pct` = live and usual-for-that-hour congestion level, `rel_travel_time_pct` (100 = free flow), `jams_count`, `jams_length_km`, `jams_delay_min`. |
| `data/tomtom_live_state.json` | Last success (Ottawa date) and last attempt. |

**This is TomTom's data (© TomTom).** Their terms of use reserve all rights and grant no licence to reuse site content, and
we have no agreement beyond that. We show it with attribution and a link, for comparison only. If TomTom objects, delete the
CSV and remove the job. It measures the whole city with TomTom's own method, so it will not match our sampled `segment_speeds.csv`.
Tests: `python Traffic/scripts/test_tomtom_live.py`.

`data/ops_annual_report_traffic.csv` holds the OPS annual-report traffic figures for 2019 to 2025
(PDF page and URL per row). The page reads the 2025 fatal-collision row from it.

## OPS collision + enforcement releases (hourly)

[`scripts/poll_ops_news.py`](scripts/poll_ops_news.py) reads the Ottawa Police news RSS
(`ottawapolice.ca/en/news/rss/`, no key). It fetches each new post once and keeps the
traffic ones. It runs from `collect.yml`, which triggers every 5 min, but it only
polls once an hour. The City and OPS open data layers stop at 2024, so this is the
only post-2024 per-incident source.

| File | Meaning |
|---|---|
| `data/ops_collision_releases.csv` | One row per traffic release. `kind` = `collision` (a specific incident) or `enforcement` (blitz/charge results, with `charges` where a number is given). Collision rows: `incident_date`/`incident_time` (local), `district`, `location` (block / intersection / road), `severity` (`fatal` > `critical` > `serious` > `injury` > `none` > `unknown`), `collision_type` (one label, first match wins: `pedestrian` > `cyclist` (incl. e-scooter) > `motorcycle` > `off_road` (ATV, snowmobile) > `train` > `building` (into a store/home/business) > `multi_vehicle` > `single_vehicle` > `unknown`), 0/1 flags `pedestrian` `cyclist` `motorcycle` `truck` `bus` `hit_and_run`, and `people_killed`. Blank = the text doesn't say. |
| `data/ops_news_seen.json` | Every post link already classified, plus the last poll time. Don't edit it. |

**It's a sample, not a dataset.** OPS releases cover the collisions it wants witnesses
for, so mostly fatal or life-threatening ones. Treat counts as a floor, and never append
them to the City collision series. One incident can get several releases: `follow_up = 1`
marks "UPDATE…" / "arrested in…" posts, so filter those out before counting.
The feed only holds posts the site still hosts (~216, back to about Dec 2025). The
backfill was the first run, so anything older is gone.

**Coverage check (2026-10-20, against CTV Ottawa).** I took CTV's daily sitemaps from
Mar 1 to Oct 19 and kept crashes inside the City of Ottawa on OPS roads (the 417/416 are
OPP, so they're out) that were fatal or seriously/critically injured someone. I then matched
them by hand to OPS releases:

| | CTV reported | OPS issued a release | Logged here |
|---|---|---|---|
| Fatal | 18 | 14 (78%) | 13 |
| Serious / critical, not fatal | 28 | 8 (29%) | 8 |
| Sep 1 – Oct 19 only (both) | 16 | 14 | 13 |

Notes on the table:
- Mar–Aug is thin: only 2 of 21 serious non-fatal crashes got a release.
- The one release that was missed is the Friel St pedestrian death. Its text never says
  "vehicle" or "collision".
- Fatal crashes with no OPS release: a May crash near Fallowfield Station, a child killed
  near Osgoode (June), a rural crash on Aug 22, and a car into a home in Orléans (Sep 9).
- Minor crashes almost never get a release. That covers most crashes into stores and
  minor pedestrian/cyclist hits.

Fields come from regexes on the release text. The tests in
[`scripts/test_ops_news.py`](scripts/test_ops_news.py) pin the traps found so far:
- Every release names the "Fatal Collision Investigation Unit", which does not mean a death.
- "motorcyclist" contains "cyclist".
- A cyclist "struck by a vehicle" is not a pedestrian.
- Feature stories about crashes abroad get skipped.

## CTV Ottawa crash headlines (hourly)

[`scripts/poll_ctv_crashes.py`](scripts/poll_ctv_crashes.py) is the second source. It covers
what OPS releases skip: non-fatal serious crashes, minor pedestrian and cyclist hits, and cars
into buildings. It reads CTV's daily news sitemaps
(`ctvnews.ca/arc/outboundfeeds/sitemap/YYYY-MM-DD/`, no key, ~340 URLs a day). It keeps
`/ottawa/article/` URLs with a crash word in the slug, and tags each one from the headline
slug alone. Article text is never fetched. It runs from `collect.yml` right after the OPS
poller, at most once an hour, and re-reads today's and yesterday's sitemaps. The backfill
starts 2025-12-01 (`--since`). `--reclassify` re-applies the slug rules without fetching.

| File | Meaning |
|---|---|
| `data/ctv_crash_headlines.csv` | One row per article: `sitemap_date`, `lastmod_utc`, `in_ottawa_ops` (0 = outside the city or on an OPP highway; `out_reason` names the place that excluded it), `story_kind` (`incident` / `follow_up` / `context`), `severity`, `collision_type` (same labels and order as the OPS file), 0/1 road-user and `building` flags, `matched_ops_url` + `match_basis`. Rewritten each run (~300 rows) so late OPS matches fill in. |
| `data/ctv_crashes_state.json` | Last poll time and the earliest backfilled day. |

**Matching to OPS.** A CTV row gets a match when an OPS collision release scores 3+ and no
other release ties it:
- same road named in both (3)
- same `collision_type` (2)
- same severity bucket (1), where fatal is one bucket and critical/serious another
- fatal on one side only (−3)
- dates within ±3 days, or ±1 day when the two share no road name

`match_basis` = `road` is reliable. `type+date` is probable: CTV usually names the
neighbourhood (Barrhaven) where OPS names the street (Strandherd). Check those before
relying on one. One CTV story per incident gets matched, and the others (follow-ups, the
"dies" update) often stay blank.

**Backfill, Dec 2025 – Oct 20, 2026:**
- **Rows:** 307 crash headlines, of which 146 are inside the city on OPS roads. The rest are
  mostly the 417, eastern Ontario, Kingston and Gatineau.
- **In-area crash stories:** 116 incident stories.
  - By type: 29 pedestrian, 15 multi-vehicle, 15 single-vehicle, 11 into a building,
    10 motorcycle, 8 cyclist.
  - By severity: 24 fatal, 31 critical/serious.
- **Matches:** 16 of the 55 fatal/critical/serious stories have a matched OPS release.

**Limits:**
- **Headline only.** "Pedestrian struck in Barrhaven" has no severity, so 33 in-area rows are
  `unknown` severity.
- **Duplicates:** one crash can produce several CTV stories, so don't count rows as crashes.
- **Scope:** only stories CTV filed under its Ottawa section.

The slug rules are pinned in [`scripts/test_ctv_crashes.py`](scripts/test_ctv_crashes.py):
- "clock strikes" isn't a crash.
- "crash on Bank Street" isn't into a bank, and "street" doesn't contain a "tree".
- "woman struck by vehicle" is a pedestrian.
- The 417 is OPP, and Hwy 174 is OPS.

## City + police context datasets

[`scripts/fetch_city_traffic.py`](scripts/fetch_city_traffic.py) pulls the static
open-data layers that explain *where* and *why* around the TomTom feed. It runs weekly
via [`.github/workflows/update-city-traffic.yml`](../.github/workflows/update-city-traffic.yml)
(Mondays 12:00 UTC). Don't hand-edit these files; fix the script instead.

| File | Source | Coverage |
|---|---|---|
| `data/city/collisions/<year>.csv` | City of Ottawa | Every reported collision, 2017–2024 (**2023 missing from the city's release**) |
| `data/city/intersection_volumes.csv` | City | AADT, % trucks, peds, cyclists at counted intersections, 2015–2025 (no 2020) |
| `data/city/midblock_volumes.csv` | City | AADT on road segments, 2022–2025 |
| `data/city/red_light_violations.csv` | City | Monthly violations per camera + direction, 2015–2026 |
| `data/city/ase_violations.csv` | City | Monthly photo-radar tickets per site, 2020–2025 |
| `data/city/ase_monthly_speeds.csv` | City | Monthly avg / 85th-pct speed + compliance at every ASE site |
| `data/city/covid_volumes.csv` | City | 2020–21 volume as % of baseline (intersections + Macdonald-Cartier Bridge) |
| `data/city/bike_counters.csv` | City | Daily counts per permanent bike counter, 2010– |
| `data/police/traffic_stops_by_*.csv` | Ottawa Police | 455K stops 2014–2024, aggregated by area / time / driver / location |
| `data/police/calls_by_*.csv` | Ottawa Police | 1.1M dispatched calls 2021–, aggregated by area / time (no call type, so not traffic-only) |

Quirks worth knowing:

- **Police data is aggregated server-side.** The raw stop and call records are too big to commit.
  `traffic_stops_by_location.csv` rolls locations with fewer than 3 stops into one `(other)` row.
  Its coordinates come from MTM zone 9, converted in-script.
- **Join key:** `geo_id` links collisions, midblock volumes and the 2024–25 intersection volumes.
  Older intersection years have no `geo_id`, so match those by coordinates.
- **AADT in 2025** is the city's 24h-adjusted study count. Earlier years publish a factored AADT,
  so treat 2025 as comparable but not identical.
- **New year = new layer name.** When the city publishes a new year, add it to the layer
  lists in the script. The service directory is
  <https://services.arcgis.com/G6F8XLCl5KtAlZ2G/ArcGIS/rest/services>.

## Join layer (`data/derived/`)

[`scripts/build_geo_index.py`](scripts/build_geo_index.py) runs right after the weekly fetch.
It puts every dataset on one key, the City's **Geo_ID** (a numeric ID is an intersection,
`__XXXX` is a road segment).

| File | Meaning |
|---|---|
| `geo_index.csv` | One row per Geo_ID: name, lat/lon, ward, OPS neighbourhood, collisions (total / injury / fatal / pedestrian / cyclist), latest AADT, **collisions per million vehicles**, police stops + charges, red-light cameras, ASE site |
| `snaps.csv` | Every coordinate-only record (police stop locations, red-light and ASE cameras, TomTom segments, traffic cameras, pre-2024 intersection counts) with its matched Geo_ID and distance |
| `neighbourhood_summary.csv` | Per OPS neighbourhood: collisions vs police stops vs 2016 population |
| `neighbourhoods.geojson` | Simplified OPS neighbourhood outlines (117 KB) for the map on the Where tab of [`stops.html`](stops.html?section=where) |
| `stories.json` | Small precomputed numbers that [`stops.html`](stops.html) charts (Where tab; collisions at photo-radar sites; red-light before/after and by camera age) and the road-safety page checks (pedestrian FMI check). Built by [`scripts/build_stories.py`](scripts/build_stories.py) so the page doesn't fetch 15 MB of collisions. |

How matching works:

- Intersections snap within 60 m, and segments or TomTom points within 120 m.
- Police "STREET / STREET" locations also match out to 150 m, but only if both street names agree.
- That covers 84% of stops at intersections and 67% of all stops. The rest are street addresses or highway ramps with no city node.
- Ward and neighbourhood come from point-in-polygon on the city's 2022–2026 wards and the OPS
  `ONS_2017` neighbourhoods. Those neighbourhood names match the police data exactly.

Read with care:

- `collisions_per_mev` uses the latest AADT over 7 collision years (2017–22 and 2024).
  It's unstable at low volumes, so filter to roughly AADT ≥ 5,000 before ranking.
- The 417/416 have collisions but no city AADT.
- `collisions_per_1k_residents_yr` is inflated for low-population, high-traffic areas such as
  Greenbelt and East Industrial. Compare it with stops or collisions, not on its own.

## Notes

- GitHub cron can lag several minutes under load, so 15-min samples aren't perfectly spaced. Fine for trends.
- A one-time historical backfill is still worth doing separately via the TomTom **Area Analytics** 30-day trial (see `PROJECTS.md`); this poller is the permanent forward-looking feed.
- Next step once data accumulates: an aggregator (`scripts/build_json.py`) → a dashboard page.

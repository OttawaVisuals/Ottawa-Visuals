# Ottawa Traffic Collection

TomTom's live map has no history, so this pipeline **builds its own** by polling
TomTom APIs on a schedule and appending every reading to CSV. A few weeks of runs
gives a real time series for the commute / RTO / quality-of-life narrative.

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

## Notes

- GitHub cron can lag several minutes under load, so 15-min samples aren't perfectly spaced. Fine for trends.
- A one-time historical backfill is still worth doing separately via the TomTom **Area Analytics** 30-day trial (see `PROJECTS.md`); this poller is the permanent forward-looking feed.
- Next step once data accumulates: an aggregator (`scripts/build_json.py`) → a dashboard page.

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

## Notes

- GitHub cron can lag several minutes under load, so 15-min samples aren't perfectly spaced. Fine for trends.
- A one-time historical backfill is still worth doing separately via the TomTom **Area Analytics** 30-day trial (see `PROJECTS.md`); this poller is the permanent forward-looking feed.
- Next step once data accumulates: an aggregator (`scripts/build_json.py`) → a dashboard page.

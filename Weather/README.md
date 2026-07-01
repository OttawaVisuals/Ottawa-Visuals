# Ottawa Weather / Climate Evolution

Public visual showing how Ottawa's climate has evolved over ~135 years, and
honestly characterizing how extreme weather has changed. See [PLAN.md](PLAN.md).

## Data pipelines

Two independent scripts, since the daily and hourly datasets cover different
time ranges and different ECCC endpoints.

### Daily (1889–present) — the main climate-evolution story

```bash
pip install -r requirements.txt
python ottawa_weather_fetch.py            # 1889 -> current year, both stations
```

Downloads daily historical weather (ECCC, no API key), splices the historic
(4333, still active) + modern (49568, gap-filler only) Ottawa stations into one
daily series, and computes per-year climate indices. A full run takes a few
minutes.

| File | Committed? | What |
|---|---|---|
| `data/raw/station_<id>_daily.csv` | no (gitignored) | cached per-station downloads |
| `data/ottawa_daily_combined.csv` | no (gitignored) | spliced daily series |
| `data/weather_indices.json` | **yes** | small per-year index file the dashboard reads |
| `data/weather_daily_series.json` | **yes** | per-year array of 365 daily mean temps (Feb 29 dropped), feeds the animated radial chart |

```bash
python ottawa_weather_fetch.py --start 1950      # shorter range
python ottawa_weather_fetch.py --stations 4333   # single station (no splice)
python ottawa_weather_fetch.py --refresh-current # re-pull the current year
python ottawa_weather_fetch.py --no-fetch        # rebuild JSON from cache only
```

### Hourly (1953–present) — the "recent extremes" angle

```bash
python ottawa_weather_fetch_hourly.py     # 1953 -> current year, both stations
```

Downloads hourly weather (temperature, wind speed, humidex, wind chill,
weather condition text), splices station 4337 (historic, 1953–2011) + 49568
(modern, 2012–present), and computes per-year extreme-weather counts
(high-wind days, hot/tropical hours, extreme-humidex days,
thunderstorm/severe-thunderstorm/freezing-rain/blowing-snow days, etc.).

**The hourly endpoint is paginated by month, not year** — a full 2-station
backfill is ~1,750 requests, roughly **40–45 minutes** on the first run. It's
fully resumable: re-running only fetches station-months not already cached.

| File | Committed? | What |
|---|---|---|
| `data/raw/station_<id>_hourly.csv` | no (gitignored, large) | cached per-station downloads |
| `data/ottawa_hourly_day_extremes.csv` | no (gitignored) | per-day extremes, spliced |
| `data/weather_hourly_indices.json` | **yes** | small per-year extreme-count file |

```bash
python ottawa_weather_fetch_hourly.py --start 2000       # shorter range
python ottawa_weather_fetch_hourly.py --refresh-current  # re-pull current year
python ottawa_weather_fetch_hourly.py --no-fetch         # rebuild JSON from cache only
```

Note: hourly `Precip. Amount` is essentially never populated for this station
(checked across every decade, both stations) — no rainfall-intensity index is
computed from hourly data. Precipitation totals come from the daily pipeline.

## Dashboard

`weather.html` (repo root) reads all three JSON files above. Live sections:
warming stripes, an animated radial "shape of a year" daily-temperature chart,
annual mean temp trend, seasonal small-multiples, hot-vs-cold extremes,
snow→rain regime shift, an hourly-extremes grid (wind/hot-hours/tropical-hours/
humidex/wind-chill/thunderstorms), a year-comparison tool, and a methodology
block. Wired into the homepage (`index.html` `REPORTS[]`, № 04 · Climate).

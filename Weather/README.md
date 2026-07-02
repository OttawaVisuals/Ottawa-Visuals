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

### Lightning strikes (2021–present) — supplementary, not ECCC

```bash
python ottawa_lightning_fetch.py          # 2021-01 -> today
```

Downloads strike counts from **LightningMaps.org / Blitzortung.org**, a
crowdsourced volunteer detector network — not ECCC. Fetches gzipped
per-10-minute files from geographic "Area 21" (found empirically — there's no
documented area-to-region mapping, so every area number was sampled and
checked against Ottawa's coordinates), filters each file to a bounding box
around the Ottawa region, and counts strikes.

**Why this is a weaker source than everything else in this repo:** the
network has grown over time (day-to-day availability was patchy in early
2021), so a rising strike count over the life of this dataset may partly
reflect more volunteer detectors coming online, not more real lightning. No
completeness guarantee, unlike a calibrated government station. Treat it as
supplementary color, not on the same footing as the ECCC series.

**Volume:** 10-minute granularity means ~52,600 file attempts/year. Full range
(2021–present) is ~260k attempts — measured at ~0.02–0.08s/file with 8–24
concurrent workers (10 workers, the default, targets a middle ground: fast
enough to finish in a couple of hours, not so aggressive on a volunteer-run
server). Fully resumable — already-fetched days are skipped on re-run.

| File | Committed? | What |
|---|---|---|
| `data/raw/lightning_daily_counts.csv` | no (gitignored) | per-day count cache, resumable |
| `data/weather_lightning_indices.json` | **yes** | small per-year strike-count file |

```bash
python ottawa_lightning_fetch.py --start 2023-01-01 --end 2023-12-31  # shorter range
python ottawa_lightning_fetch.py --workers 20     # faster, heavier on their server
python ottawa_lightning_fetch.py --refresh-today  # re-pull today even if cached
python ottawa_lightning_fetch.py --no-fetch       # rebuild JSON from cache only
```

## Dashboard

`weather.html` (repo root) reads all four JSON files above. Live sections:
warming stripes, an animated radial "shape of a year" daily-temperature chart,
annual mean temp trend, seasonal small-multiples, hot-vs-cold extremes,
snow→rain regime shift, an hourly-extremes grid (wind/hot-hours/tropical-hours/
humidex/wind-chill/thunderstorms), a lightning-strike panel, a year-comparison
tool, and a methodology block. Wired into the homepage (`index.html`
`REPORTS[]`, № 04 · Climate).

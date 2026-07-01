# Ottawa Weather / Climate Evolution Dashboard — Plan

> Goal: show how Ottawa's climate has evolved over ~135 years, and honestly
> characterize whether — and how — extreme weather has changed.

## 1. Narrative (the spine)
Two honest claims, in order:
1. **Ottawa's baseline climate has shifted measurably** over ~135 years —
   warmer, longer growing season, more rain-vs-snow.
2. **The *nature* of extremes has changed** — more hot days & heavy-rain events,
   fewer extreme-cold & big-snow events — even if the raw *count* of "extreme
   days" hasn't simply exploded.

This framing is defensible against the peer-reviewed 1890–2019 study
([MDPI, 2022](https://www.mdpi.com/2076-3298/9/3/35)), which found the
**means moved a lot** while the **count of extreme events stayed largely flat**.
"More/different kinds of extremes" is a stronger, harder-to-attack story than a
naive "extreme weather is rising."

## 2. Data
- **Primary source:** Environment and Climate Change Canada (ECCC) bulk CSV,
  <https://climate.weather.gc.ca/>. No API key; downloadable by URL.
- **Daily stations** (`ottawa_weather_fetch.py`):
  - `4333` — **Ottawa CDA** — daily records back to **1889**, still active today.
  - `49568` — **Ottawa (modern)** — used only to patch gaps in CDA's record from
    2011 onward (CDA itself keeps reporting through the present).
- **Hourly stations** (`ottawa_weather_fetch_hourly.py`, for the extremes angle
  — verified by hand, not assumed):
  - `4337` — **Ottawa Macdonald-Cartier Intl A (historic)** — hourly **1953–2011**.
  - `49568` — **Ottawa (modern)** — hourly **2012–present**. Clean handoff around
    Dec 2011 / Jan 2012.
  - Note: `4337` continues to return rows for years after it was retired
    (~2012+), but with every observation blank — ECCC pads discontinued
    stations with timestamp-only placeholder rows rather than omitting them.
    The splice logic treats "zero valid hourly readings that day" as "this
    station has nothing to say" and falls through to the next station.
  - **Precip. Amount is not usable at hourly resolution** — checked empirically
    across every decade from 1953–2025, on both stations: the column exists but
    is essentially always blank. No hourly rainfall-intensity index exists as a
    result; precipitation totals only come from the daily pipeline.
- **Splice logic (both pipelines):** stations are coalesced **column-by-column,
  per day** — the earlier-listed station's value is used whenever it is
  actually present; the next station only fills in specific missing
  days/fields, never a wholesale "switch over after year X." (Caught and fixed
  a real bug here: a station's placeholder rows with blank values were
  initially "winning" over a later station's real data for the same date,
  because the code checked "does a row exist" rather than "does a value
  exist." Watch for this pattern if the splice logic is ever extended.)
- **Continuity caveat:** because CDA (4333) is one continuous site with no
  station swap, the daily 1889→now series has no structural seam to worry
  about — the earlier "single-station splice vs AHCCD" concern turned out to
  be less of an issue than expected.
- **Daily fields used:** Max/Min/Mean temp, Total precip, Total rain, Total
  snow, Snow on ground, Direction/Speed of max gust.
- **Hourly fields used:** Wind Spd (continuous, not just daily max gust), Hmdx
  (humidex), Wind Chill, and the `Weather` text condition field (thunderstorm /
  freezing rain / blowing snow / ice pellets, via keyword match).

## 3. Metrics / climate indices (per year, computed once → JSON)
Standard ETCCDI-style indices:

| Category | Index |
|---|---|
| Warming | Annual & seasonal mean temp; warming-stripes series |
| Heat extremes | # days Tmax ≥ 30 °C; tropical nights (Tmin ≥ 20 °C); hottest day |
| Cold extremes | # days Tmin ≤ −25 °C; coldest night; # frost days (Tmin < 0) |
| Season | Growing-season length; frost-free days; first/last frost date |
| Precip regime | Annual rain vs snow; rain-fraction %; heavy-rain days ≥ 25 mm; max 1-day precip |
| Volatility | Freeze–thaw cycles/year (Tmax > 0 and Tmin < 0) |

Each year also carries a `data_days` count + `complete` flag so sparse early
years can be greyed out or excluded.

**Hourly extremes (1953–present only)** — a separate, shorter-range dataset for
the "recent extremes" angle, in `data/weather_hourly_indices.json`:

| Category | Index |
|---|---|
| Wind | Max wind speed/yr; high-wind days (≥ 50 km/h); damaging-wind days (≥ 70 km/h) |
| Heat | Max humidex; extreme-humidex days (Hmdx ≥ 40) |
| Cold | Min wind chill; extreme-wind-chill days (≤ −35) |
| Events | Thunderstorm / freezing-rain / blowing-snow / ice-pellet days (from `Weather` text) |

Same `hours_present` + `complete` pattern as the daily file. This dataset spans
1953–present (73 yrs), not the full 1889–present daily record.

## 4. Dashboard sections (visuals)
1. **Warming stripes** hero banner (instantly legible, shareable).
2. **Annual mean temperature** line + trend/regression + decadal averages.
3. **Seasonal small-multiples** (winter warming is usually strongest).
4. **Extremes panel** — hot-days trend ↑ beside extreme-cold-days trend ↓.
   This *is* the honest "extreme" story.
5. **Snow → rain regime shift** — stacked area of rain vs snow over time.
6. **"Pick a year you remember"** interactive — user picks a birth/move-in year
   and sees how the climate has changed since. Personal hook = engagement.

## 5. Tech stack (matches Retrofit Explorer)
- **Static site:** single `weather.html`, vanilla JS + **Chart.js**, GitHub Pages.
- **Pipeline:** two scripts (this repo):
  - `ottawa_weather_fetch.py` — daily, 1889–present → `data/weather_indices.json`.
    One request per station-year; a full run is a few minutes.
  - `ottawa_weather_fetch_hourly.py` — hourly, 1953–present →
    `data/weather_hourly_indices.json`. The hourly endpoint is paginated by
    **month**, so a full 2-station backfill is ~1,750 requests, roughly
    **40–45 minutes** on a first run. Fully resumable afterward — already-cached
    station-months are skipped.
  - Both emit small per-year JSON committed to the repo; raw multi-decade CSVs
    stay gitignored (consistent with "untrack large source files").
- **Refresh cadence:** climate moves slowly — **annual** refresh suffices, but a
  weekly GitHub Action could append the current year (matches the real-estate
  weekly-refresh pattern).

## 6. Open decisions (defer)
- Single-station splice vs. AHCCD homogenized series.
- Exact extreme thresholds (30 °C vs 32 °C hot days, etc.) — script defaults to
  Canadian conventions but they're constants at the top of the file.
- Host here (`C:\Ottawa_Visuals\Weather`) or a dedicated repo like Energy.

## 7. Status
- [x] Data landscape surveyed.
- [x] Plan written.
- [x] Daily fetch + index script (`ottawa_weather_fetch.py`) — run, verified,
  splice bug found and fixed (see §2). Also fixed a unit-mixing bug in
  `rain_fraction` (was `rain_mm / (rain_mm + snow_cm)`; now `rain_mm / total_precip_mm`,
  using ECCC's own water-equivalent total instead of hand-mixing units).
- [x] Hourly fetch + extremes script (`ottawa_weather_fetch_hourly.py`) — built,
  station IDs verified by hand, splice-fill bug (same class as the daily one)
  found and fixed. Full 1953–present run completed: 74 years, 73 complete.
- [x] `weather.html` dashboard built — topbar/theme matching `mortgage.html`'s
  conventions, Chart.js 4.4.1. Sections: warming stripes, annual mean temp +
  10-yr rolling average, seasonal small-multiples, hot-vs-cold extremes panel,
  snow→rain regime shift, hourly extremes grid (1953+), "pick a year you
  remember" comparison tool, methodology block. Verified in-browser: data
  loads, all 11 charts render real pixel content, theme toggle recolors
  charts + stripes live, year-picker comparison math checked against raw
  JSON, responsive grid collapses correctly on mobile width.
- [x] Wired into the homepage: added a `weather` card (№04 · Climate) to
  `index.html`'s `REPORTS[]`, using the real computed decade-delta stats as
  takeaways (+2.2°C, +6 hot days/yr, -7 extreme-cold days/yr). Updated the 3
  hardcoded "N reports live" / "N published" counts to 4. Added a `weather.html`
  ↔ `mortgage.html` nav cross-link (the only two standalone pages with their
  own topbar — other pages like `ottawa_ward_elections.html` are iframe-only
  fragments with no topbar of their own). Caught and fixed a real bug during
  verification: embedding `weather.html` in the homepage's iframe showed its
  own sticky topbar stacked under the homepage's topbar, so added an
  iframe-detection check to hide it when embedded — first attempt used
  `document.write()`, which would have wiped the whole embedded page (it
  implicitly calls `document.open()` when run after page load); fixed to a
  direct `style.display` set instead. Verified both the standalone and
  embedded views in-browser after the fix.
- [ ] Commit to git (nothing committed yet as of this status).

**Known pre-existing site bug, unrelated to this project:** `index.html` and
`mortgage.html` both reference the logo as `assets/avatar.png`, but the real
file is at `assets/img/avatar.png` — a 404 on every page using that pattern,
including the new `weather.html` (copied the same convention faithfully).
Flagged as a separate background task rather than fixed inline here.

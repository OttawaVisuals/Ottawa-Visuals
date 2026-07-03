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
- **Lightning strikes (2021–present), separate/supplementary source:**
  investigated Canada's official Lightning Detection Network (CLDN) first,
  since it's ECCC and matches everything else here — ruled out: the only
  public bulk access is a rolling near-real-time feed
  (`dd.weather.gc.ca/today/lightning/`, live since Jan 2023), not a historical
  archive; the 45-million-flash 1999–2018 academic dataset almost certainly
  came from a research data-sharing agreement, not open download. Fell back to
  **LightningMaps.org / Blitzortung.org**, a crowdsourced volunteer network —
  real, working, public, no auth, but a materially weaker source: found its
  `data.lightningmaps.org/Public/Strokes/Areas/<N>/YYYY/MM/DD/HH/*.json.gz`
  archive (gzipped, one file per 10-minute window), and since there's no
  documented area-number-to-region mapping, sampled all ~98 areas by hand and
  checked their lat/lon to find **Area 21** (covers ~25–49.7°N, -89.9 to
  -67.6°W — confirmed real strikes within a few km of Ottawa in a sample
  file). Data exists from ~Feb 2021, patchily at first (some early days 404
  entirely where neighbours don't) — consistent with a still-growing detector
  network. **This means a rising strike count over this dataset's life may
  partly reflect more detectors coming online, not more real lightning** —
  flagged prominently in the dashboard, not just here.

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

**Daily temperature series** (`data/weather_daily_series.json`, compact/no
indent) — a per-year array of 365 mean-temp values (Jan 1 = index 0, Feb 29
dropped so every year aligns index-for-index; missing days are `null`, not
interpolated). Feeds the animated radial "shape of a year" chart. Verified the
leap-year alignment against the raw CSV directly (Mar 1 lands on index 59 in
both a leap year like 2024 and a non-leap year like 2023).

**Hourly extremes (1953–present only)** — a separate, shorter-range dataset for
the "recent extremes" angle, in `data/weather_hourly_indices.json`:

| Category | Index |
|---|---|
| Wind | Max wind speed/yr; high-wind days (≥ 50 km/h); damaging-wind days (≥ 70 km/h) |
| Heat | Max humidex; extreme-humidex days (Hmdx ≥ 40); **hot hours/yr (Temp ≥ 30 °C, any time)** |
| Cold | Min wind chill; extreme-wind-chill days (≤ −35); **tropical hours/yr (Temp ≥ 20 °C, 21:00–05:59 LST)** |
| Events | Freezing-rain / blowing-snow / ice-pellet days; thunderstorm days **split into total vs. severe** (hail or "Heavy Thunderstorms" qualifier in the `Weather` text — a bare thunderstorm flag can't tell a brief rumble from a hail-producing storm) |

`hot_hours`/`tropical_hours` are the hour-resolution counterparts of the daily
script's `hot_days`/`tropical_nights` — same thresholds, but counting duration
instead of just whether a day tipped over the line at all. Same `hours_present`
+ `complete` pattern as the daily file. This dataset spans 1953–present
(73 yrs), not the full 1889–present daily record.

## 4. Dashboard sections (visuals)
1. **Warming stripes** hero banner (instantly legible, shareable).
2. **Annual mean temperature** line + trend/regression + decadal averages.
3. **The shape of a year** — animated radial/spiral chart, two stacked
   canvases: a persistent background that *accumulates* every year already
   shown as a faint (10% alpha), year-tinted trace (colour = that year's
   annual mean, same scale as the stripes), and a foreground that draws the
   current year day-by-day as a colour-graded line (colour = that day's temp,
   own min/max since a single year's daily range dwarfs the stripes' *annual
   mean* range) with a small marker at the sweep's leading edge. Auto-plays
   through all 136 complete years (~900ms/year sweep), stopping at the end
   with the full 136-year "spaghetti plot" left on screen; a scrub slider
   jumps anywhere and rebuilds the background to match exactly (years before
   the selected one), so scrubbing backward correctly un-accumulates too.
4. **Seasonal small-multiples**, 2×2 (Winter/Spring row, Summer/Fall row).
5. **Extremes panel** — hot-days trend ↑ beside extreme-cold-days trend ↓.
   This *is* the honest "extreme" story.
6. **Snow → rain regime shift** — rain's share of total precip over time.
7. **Hourly extremes grid**, 2×3 — max wind, hot hours, tropical hours,
   extreme-humidex days, extreme-wind-chill days, and thunderstorm days
   (total vs. severe).
8. **"Pick a year you remember"** interactive — user picks a birth/move-in year
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
- [x] Committed to git (12 files; raw CSVs and `.claude/` stayed untracked as
  intended).
- [x] Second round of feedback addressed:
  - Fixed the pre-existing `assets/avatar.png` → `assets/img/avatar.png`
    broken-path bug site-wide (index.html, mortgage.html, weather.html —
    img src + favicon link in all three). Kept the PNG over the JPG since it
    has real alpha transparency (checked the pixel data), which matters
    inside the circular, `overflow:hidden` logo container.
  - Widened `.report` to 1440px (was 1080px) to use more laptop-width screen.
  - Seasonal and hourly-extremes grids changed from a 1×4 row to a fixed
    2-column grid (2×2 / 2×3).
  - Added `hot_hours`/`tropical_hours` to the hourly script (temperature
    extraction was added to `hourly_to_day_extremes()`, which previously only
    tracked wind/humidex/wind-chill, not raw Temp) and added `severe_thunderstorm_days`
    (hail / "Heavy Thunderstorms" qualifier in the `Weather` text). Rebuilt
    from the already-cached raw hourly CSVs via `--no-fetch` — no re-fetch
    needed, under a minute to rebuild.
  - Built the animated radial "shape of a year" chart. Required a new
    `weather_daily_series.json` export from the daily script (365-value
    per-year mean-temp arrays, Feb 29 dropped, leap-year alignment verified
    directly against the raw CSV — Mar 1 lands on index 59 in both a leap and
    non-leap year). Hand-rolled on `<canvas>`, not Chart.js.
  - Answered two data questions with real evidence, not speculation: pulled
    the station's hourly wind reading for the Sept 21, 2018 Ottawa–Gatineau
    EF3 tornado (peaked at just 50 km/h that hour — confirms the "too
    localized for a fixed station to catch" hypothesis) and inspected the raw
    `Weather` text strings, which confirmed the thunderstorm metric *was* a
    bare presence flag before this round, missing intensity — now split into
    total vs. severe. Both write-ups added to the dashboard's own hourly
    section note and methodology block, not just this file.
  - Verified all of the above in-browser (not just read the code): 14 charts
    all render non-empty canvas content, the spiral animates and redraws
    correctly after slider-scrub and after a theme toggle, both grids report
    the expected `grid-template-columns`, and no console errors at any point.
- [x] Third round — reworked the spiral into an accumulating "spaghetti plot":
  split into two stacked canvases (`chart-spiral-bg` persists every completed
  year as a faint, year-tinted trace; `chart-spiral-fg` is cleared/redrawn
  every frame for the actively-sweeping year only), replaced per-day dots with
  a colour-graded line (segment-by-segment `tempColor()`, since canvas has no
  native per-vertex stroke colour) plus a single leading-edge marker dot, and
  switched the animation from an instant year-to-year swap to a real
  day-by-day sweep (~900ms/year) driven by `performance.now()` elapsed time,
  not frame count, so it's correct regardless of frame rate. Reaching the last
  year stops playback rather than looping, leaving the full 136-year
  accumulated shape on screen; pressing play again restarts the accumulation
  from scratch. The slider always fully rebuilds the background to the exact
  years before the selected index (`rebakeBackgroundUpTo()`), so it's correct
  scrubbing in either direction, not just append-only — verified in-browser
  that non-empty background pixel counts genuinely grow on forward playback
  (701→1023→1132 samples across three checkpoints) and shrink on backward
  scrub (1023→532), and that a slider drag's rapid `input` events are
  coalesced to one redraw per animation frame rather than one per event.
- [ ] Fourth round — lightning strikes. Built `ottawa_lightning_fetch.py`
  after ruling out CLDN (ECCC's own network) for public bulk historical
  access — see §2 for the investigation. Landed on LightningMaps.org/
  Blitzortung, Area 21, empirically discovered (no documented area→region
  map). Measured real request latency before committing to a design:
  sequential ~47h for the full 2021–present range, 8-concurrent ~5.7h,
  24-concurrent ~1.4h with zero errors/throttling observed — shipped with a
  default of 10 workers as a deliberate middle ground (fast enough to be
  practical, not maxed out against a volunteer-run server). Smoke-tested on
  a storm day (2500 strikes), a quiet day (1 strike), a winter day (0
  strikes, 0 failures — confirms 404-as-"no data" is handled correctly, not
  miscounted as an error), and confirmed resumability (re-running an
  already-fetched range does zero new requests). Kicked off the full
  2021–present run in the background — user asked to run it themselves
  overnight instead, so stopped it (`TaskStop`) after ~212 days; fully
  resumable, so that progress wasn't wasted.
  - **Upgraded to keep full per-strike detail** (exact time + lat/lon, not
    just a daily count) after the user said "more data is better, we can
    refine later" while their overnight run was already in progress.
    Checked `src`/`srv` (the other fields in each record) empirically before
    deciding to drop them — both are constant *per file*, not per strike
    (src=2 in every file sampled across 2021/2024/2025; srv differs between
    files but not within one — consistent with a fixed source-type tag and a
    backend-server ID, not meteorological data), so neither is worth keeping.
    No official field documentation found for either despite a real search
    effort — this is an evidence-based inference, stated as such, not a
    confirmed fact.
  - Restructured resumability around this: a day now only counts as "done"
    once `data/raw/lightning_strikes/<date>.csv` exists, and — this also
    fixed a real bug — that file is only written when the day had zero
    failed windows. The original version cached a day as done even with
    partial failures (just logged a misleading "will retry next run" that
    never actually happened, since the resume check only looked at whether
    the day was in the cache at all). The old count-only cache is kept as a
    read-only fallback for days not yet re-fetched, so nothing already
    collected is thrown away.
  - Edited the script file directly while the user's overnight run was still
    executing — safe, since Python has already loaded the old code into
    memory and doesn't re-read the file mid-run. Verified the upgraded
    script separately on a day the live run had already passed
    (2021-08-27): re-fetched correctly (full-detail cache was empty),
    produced a real 4-row time/lat/lon file matching the count the live run
    had logged for that day, and correctly skipped it on a second run.
  - **Not yet wired into weather.html** — next step once the user's
    upgraded backfill run finishes.

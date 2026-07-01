#!/usr/bin/env python3
"""
Ottawa HOURLY weather fetcher + extreme-weather index builder (ECCC).

Companion to ottawa_weather_fetch.py, which handles the long DAILY record
(1889-present) used for the main climate-evolution story. This script instead
targets a "recent extremes" angle that needs hourly resolution: sustained wind
speed, humidex, wind chill, weather-condition events (thunderstorms, freezing
rain, blowing snow), and hour-counts for heat (hot_hours, Temp >= 30 C any
time of day) and overnight warmth (tropical_hours, Temp >= 20 C during
21:00-05:59 LST) -- the hourly equivalent of the daily script's "hot day" /
"tropical night" day-counts, showing duration/intensity rather than just
occurrence. Thunderstorm hours are also split into plain vs "severe" (hail or
the "Heavy Thunderstorms" qualifier in ECCC's Weather text), since a bare
"thunderstorm" flag can't distinguish a brief rumble from a hail-producing storm.

Stations (verified by hand before writing this script - see PLAN.md):
  4337   Ottawa Macdonald-Cartier Intl A (historic)   hourly 1953-2011
  49568  Ottawa (modern)                               hourly 2012-present
These are two different bulk-download IDs for what is functionally the same
airport station across ECCC's record-keeping systems. They hand off cleanly
around Dec 2011 / Jan 2012.

Notably NOT usable (checked empirically, not assumed):
  - "Precip. Amount (mm)" is present as a column but essentially always blank
    for this station, in every decade sampled -- so no hourly rainfall-
    intensity index is computed here. Precipitation totals come from the
    daily pipeline instead.

The hourly bulk endpoint is paginated by MONTH (not year like daily), so a
full 1953-present, 2-station backfill is roughly 1,750 requests -- expect on
the order of 40-45 minutes for a first full run. It is fully resumable:
already-cached station-months are skipped on subsequent runs.

What it produces (all under ./data/)
------------------------------------
  data/raw/station_<id>_hourly.csv       cached raw hourly rows  (gitignored, large)
  data/ottawa_hourly_day_extremes.csv    per-day extremes, spliced (gitignored)
  data/weather_hourly_indices.json       per-year extreme counts (COMMITTED)

Usage
-----
  pip install -r requirements.txt
  python ottawa_weather_fetch_hourly.py                  # full 1953 -> this year
  python ottawa_weather_fetch_hourly.py --start 2000      # shorter range
  python ottawa_weather_fetch_hourly.py --refresh-current # re-pull current year
  python ottawa_weather_fetch_hourly.py --no-fetch        # rebuild JSON from cache only

Be a good citizen: this hits a public government site with ~12x the request
volume of the daily script for the same span. Keep --delay reasonable and
don't run multiple copies at once (the resume cache already avoids re-work).
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import logging
import sys
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    sys.exit("This script needs pandas.  Run:  pip install -r requirements.txt")

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:  # pragma: no cover
    pass

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BULK_URL = "https://climate.weather.gc.ca/climate_data/bulk_data_e.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Firefox/124.0"
)

# Priority order: earlier entries win on overlapping dates (see build_daily_extremes).
HOURLY_STATIONS = [
    (4337, "Ottawa Intl A (historic hourly)", 1953),
    (49568, "Ottawa (modern)", 2011),
]

FIRST_YEAR_DEFAULT = 1953
DEFAULT_DELAY = 0.5          # seconds between requests (12x the request volume of daily)

# --- Extreme-weather thresholds (tweak here) ------------------------------- #
HIGH_WIND_KMH = 50.0          # hourly Wind Spd >= this -> "high-wind hour"
DAMAGING_WIND_KMH = 70.0      # hourly Wind Spd >= this -> "damaging-wind hour"
EXTREME_HUMIDEX = 40.0        # Hmdx >= this -> "extreme humidex hour"
EXTREME_WINDCHILL = -35.0     # Wind Chill <= this -> "extreme wind-chill hour"
HOT_HOUR_C = 30.0             # hourly Temp >= this -> "hot hour" (same threshold as the daily "hot day")
TROPICAL_HOUR_C = 20.0        # overnight hourly Temp >= this -> "tropical hour"
NIGHT_HOURS = set(range(21, 24)) | set(range(0, 6))  # 21:00-05:59 LST, for tropical hours
MIN_HOURS_COMPLETE = 300 * 24  # a year needs this many valid hourly readings to be "complete"

# Weather-text keywords -> event-count columns (case-insensitive substring match).
WEATHER_EVENTS = {
    "thunderstorm_hours": "thunderstorm",
    "freezing_rain_hours": "freezing rain",
    "blowing_snow_hours": "blowing snow",
    "ice_pellet_hours": "ice pellet",
}
# A plain "thunderstorm" match doesn't distinguish a brief rumble from a severe
# storm. ECCC's Weather text does carry that signal though (checked by hand):
# entries like "Thunderstorms,Hail" or "Heavy Thunderstorms,..." exist in both
# the historic and modern station text, back to 1953. A storm hour is "severe"
# if it's tagged with hail or with the "Heavy Thunderstorms" qualifier.
SEVERE_THUNDER_KEYWORDS = ("hail", "heavy thunderstorm")

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "raw"
DAY_EXTREMES_CSV = DATA_DIR / "ottawa_hourly_day_extremes.csv"
INDICES_JSON = DATA_DIR / "weather_hourly_indices.json"

log = logging.getLogger("ottawa_weather_hourly")


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def fetch_month_csv(session: requests.Session, station_id: int, year: int, month: int) -> str | None:
    """Return the raw hourly CSV text for one station-month, or None on failure."""
    params = {
        "format": "csv",
        "stationID": station_id,
        "Year": year,
        "Month": month,
        "Day": 1,
        "timeframe": 1,          # hourly
        "submit": "Download+Data",
    }
    try:
        r = session.get(BULK_URL, params=params, timeout=60)
        r.raise_for_status()
    except requests.RequestException as exc:
        log.warning("  %s %d-%02d: request failed (%s)", station_id, year, month, exc)
        return None
    r.encoding = "utf-8-sig"
    text = r.text
    if "Date/Time" not in text:
        return None
    return text


# --------------------------------------------------------------------------- #
# Download + cache one station's full hourly record
# --------------------------------------------------------------------------- #
def download_station_hourly(
    session: requests.Session,
    station_id: int,
    label: str,
    first_year: int,
    start_year: int,
    end_year: int,
    delay: float,
    refresh_current: bool,
    do_fetch: bool,
) -> pd.DataFrame | None:
    cache = RAW_DIR / f"station_{station_id}_hourly.csv"
    frames: list[pd.DataFrame] = []

    cached_pairs: set[tuple[int, int]] = set()
    if cache.exists():
        try:
            prev = pd.read_csv(cache, low_memory=False)
            frames.append(prev)
            if {"Year", "Month"}.issubset(prev.columns):
                pairs = prev[["Year", "Month"]].dropna().astype(int)
                cached_pairs = set(map(tuple, pairs.values.tolist()))
        except Exception as exc:
            log.warning("  could not read cache %s (%s); refetching", cache.name, exc)

    if do_fetch:
        this_year = dt.date.today().year
        lo = max(start_year, first_year)
        for year in range(lo, end_year + 1):
            new_month_frames = []
            for month in range(1, 13):
                need = (year, month) not in cached_pairs
                if year == this_year and refresh_current:
                    need = True
                if not need:
                    continue
                text = fetch_month_csv(session, station_id, year, month)
                time.sleep(delay)
                if text is None:
                    continue
                df = pd.read_csv(io.StringIO(text), low_memory=False)
                if df.empty:
                    continue
                new_month_frames.append(df)
            if new_month_frames:
                log.info("  %s  fetched %d (%d months)", label, year, len(new_month_frames))
                frames = [f for f in frames
                          if not ("Year" in f.columns and (f["Year"] == year).any())] + new_month_frames

    if not frames:
        log.warning("  %s: no data obtained", label)
        return None

    combined = pd.concat(frames, ignore_index=True)
    key_col = "Date/Time (LST)" if "Date/Time (LST)" in combined.columns else "Date/Time"
    combined = combined.dropna(subset=[key_col]).drop_duplicates(subset=[key_col])
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(cache, index=False)

    dates = pd.to_datetime(combined[key_col], errors="coerce").dropna()
    if not dates.empty:
        log.info("  %s: %d hours, %s -> %s",
                 label, len(dates), dates.min(), dates.max())
    return combined


# --------------------------------------------------------------------------- #
# Reduce raw hourly rows -> per-day extremes, then splice stations
# --------------------------------------------------------------------------- #
def col(df: pd.DataFrame, needle: str) -> str | None:
    for c in df.columns:
        if needle.lower() in c.lower():
            return c
    return None


def hourly_to_day_extremes(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse one station's raw hourly rows into one row per day of extremes."""
    d = pd.DataFrame()
    dt_col = col(df, "Date/Time (LST)") or col(df, "Date/Time")
    d["datetime"] = pd.to_datetime(df[dt_col], errors="coerce")
    d["temp"] = pd.to_numeric(df[col(df, "Temp")], errors="coerce") if col(df, "Temp") else pd.NA
    d["wind_spd"] = pd.to_numeric(df[col(df, "Wind Spd")], errors="coerce")
    d["hmdx"] = pd.to_numeric(df[col(df, "Hmdx")], errors="coerce") if col(df, "Hmdx") else pd.NA
    d["wind_chill"] = pd.to_numeric(df[col(df, "Wind Chill")], errors="coerce") if col(df, "Wind Chill") else pd.NA
    weather_col = col(df, "Weather")
    d["weather"] = df[weather_col].fillna("") if weather_col else ""
    d = d.dropna(subset=["datetime"])
    d["date"] = d["datetime"].dt.normalize()
    d["hour"] = d["datetime"].dt.hour
    d["is_night"] = d["hour"].isin(NIGHT_HOURS)

    weather_lower = d["weather"].str.lower()
    event_flags = {name: weather_lower.str.contains(kw) for name, kw in WEATHER_EVENTS.items()}
    is_thunder = weather_lower.str.contains("thunderstorm")
    is_severe = is_thunder & weather_lower.str.contains("|".join(SEVERE_THUNDER_KEYWORDS))
    event_flags["severe_thunderstorm_hours"] = is_severe

    grouped = d.groupby("date")
    out = pd.DataFrame({
        "hours_present": grouped["wind_spd"].apply(lambda s: s.notna().sum()),
        "wind_spd_max": grouped["wind_spd"].max(),
        "high_wind_hours": grouped["wind_spd"].apply(lambda s: (s >= HIGH_WIND_KMH).sum()),
        "damaging_wind_hours": grouped["wind_spd"].apply(lambda s: (s >= DAMAGING_WIND_KMH).sum()),
        "hmdx_max": grouped["hmdx"].max(),
        "extreme_humidex_hours": grouped["hmdx"].apply(lambda s: (s >= EXTREME_HUMIDEX).sum()),
        "wind_chill_min": grouped["wind_chill"].min(),
        "extreme_windchill_hours": grouped["wind_chill"].apply(lambda s: (s <= EXTREME_WINDCHILL).sum()),
        "hot_hours": grouped["temp"].apply(lambda s: (s >= HOT_HOUR_C).sum()),
    })
    trop = d[d["is_night"]].groupby("date")["temp"].apply(lambda s: (s >= TROPICAL_HOUR_C).sum())
    out["tropical_hours"] = trop.reindex(out.index).fillna(0)
    for name in list(WEATHER_EVENTS) + ["severe_thunderstorm_hours"]:
        out[name] = event_flags[name].groupby(d["date"]).sum()

    # A day with zero valid wind readings means this station had no real
    # signal at all that day (wind is ~always recorded when a station is
    # actually operating - e.g. ECCC pads discontinued stations' recent years
    # with timestamp-only placeholder rows). Null out the count-type columns
    # for those days so build_daily_extremes' combine_first() correctly falls
    # through to the next station instead of "winning" with a bogus 0.
    no_data = out["hours_present"] == 0
    count_cols = ["hours_present", "high_wind_hours", "damaging_wind_hours",
                  "extreme_humidex_hours", "extreme_windchill_hours", "hot_hours",
                  "tropical_hours", *WEATHER_EVENTS, "severe_thunderstorm_hours"]
    out.loc[no_data, count_cols] = pd.NA
    return out.reset_index()


def build_daily_extremes(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Per-station day-extremes, coalesced column-by-column (earlier station wins
    whenever it actually has data for that day; same logic as the daily script)."""
    parts = [hourly_to_day_extremes(df).set_index("date").sort_index() for df in frames]
    combined = parts[0]
    for p in parts[1:]:
        combined = combined.combine_first(p)
    combined = combined.reset_index().sort_values("date").reset_index(drop=True)
    combined["year"] = combined["date"].dt.year
    return combined


# --------------------------------------------------------------------------- #
# Per-year extreme-weather indices
# --------------------------------------------------------------------------- #
def compute_indices(day_extremes: pd.DataFrame) -> list[dict]:
    out = []
    for year, g in day_extremes.groupby("year"):
        hours_present = int(g["hours_present"].sum())
        rec = {
            "year": int(year),
            "hours_present": hours_present,
            "complete": hours_present >= MIN_HOURS_COMPLETE,
            "max_wind_spd": _round(g["wind_spd_max"].max()),
            "high_wind_days": _count(g["high_wind_hours"] > 0),
            "high_wind_hours": int(g["high_wind_hours"].fillna(0).sum()),
            "damaging_wind_days": _count(g["damaging_wind_hours"] > 0),
            "max_humidex": _round(g["hmdx_max"].max()),
            "extreme_humidex_days": _count(g["extreme_humidex_hours"] > 0),
            "min_wind_chill": _round(g["wind_chill_min"].min()),
            "extreme_windchill_days": _count(g["extreme_windchill_hours"] > 0),
            "hot_hours": int(g["hot_hours"].fillna(0).sum()),
            "tropical_hours": int(g["tropical_hours"].fillna(0).sum()),
        }
        for name in list(WEATHER_EVENTS) + ["severe_thunderstorm_hours"]:
            rec[name.replace("_hours", "_days")] = _count(g[name] > 0)
        out.append(rec)
    return sorted(out, key=lambda r: r["year"])


def _round(v, ndigits: int = 1):
    if v is None or pd.isna(v):
        return None
    return round(float(v), ndigits)


def _count(mask: pd.Series) -> int:
    return int(mask.fillna(False).sum())


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=int, default=FIRST_YEAR_DEFAULT,
                    help=f"first year to fetch (default {FIRST_YEAR_DEFAULT})")
    ap.add_argument("--end", type=int, default=dt.date.today().year,
                    help="last year to fetch (default: this year)")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                    help=f"seconds between requests (default {DEFAULT_DELAY})")
    ap.add_argument("--refresh-current", action="store_true",
                    help="re-download the current year even if cached")
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip all downloads; rebuild JSON from cached CSVs only")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(Path(__file__).with_name("weather_fetch_hourly.log"),
                                      encoding="utf-8")],
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = make_session()

    log.info("Ottawa HOURLY weather fetch: %d-%d, stations=%s",
             args.start, args.end, [s[0] for s in HOURLY_STATIONS])
    log.info("This is a monthly-paginated endpoint; a full run can take ~40-45 min.")

    frames = []
    for sid, label, first_year in HOURLY_STATIONS:
        df = download_station_hourly(
            session, sid, label, first_year,
            start_year=args.start, end_year=args.end,
            delay=args.delay, refresh_current=args.refresh_current,
            do_fetch=not args.no_fetch,
        )
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        log.error("No station data available. Nothing to build.")
        return 1

    day_extremes = build_daily_extremes(frames)
    day_extremes.to_csv(DAY_EXTREMES_CSV, index=False)
    log.info("Day-extremes series: %d days, %s -> %s  (%s)",
             len(day_extremes), day_extremes["date"].min().date(),
             day_extremes["date"].max().date(), DAY_EXTREMES_CSV.name)

    years = compute_indices(day_extremes)
    payload = {
        "meta": {
            "source": "Environment and Climate Change Canada (climate.weather.gc.ca), hourly",
            "stations": [{"id": s[0], "label": s[1]} for s in HOURLY_STATIONS],
            "generated": dt.datetime.now().isoformat(timespec="seconds"),
            "thresholds": {
                "high_wind_kmh": HIGH_WIND_KMH,
                "damaging_wind_kmh": DAMAGING_WIND_KMH,
                "extreme_humidex": EXTREME_HUMIDEX,
                "extreme_windchill": EXTREME_WINDCHILL,
            },
            "note": "Hourly Precip. Amount is not populated for this station in any "
                    "decade sampled, so no rainfall-intensity index is included here; "
                    "see weather_indices.json (daily) for precipitation totals.",
            "n_years": len(years),
        },
        "years": years,
    }
    INDICES_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    complete = sum(1 for y in years if y["complete"])
    log.info("Wrote %s: %d years (%d complete).", INDICES_JSON.name, len(years), complete)
    log.info("Done. The dashboard reads data/weather_hourly_indices.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

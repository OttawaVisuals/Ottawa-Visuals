#!/usr/bin/env python3
"""
Ottawa weather / climate fetcher + index builder (Environment Canada, ECCC).

Downloads daily historical weather for Ottawa from ECCC's public bulk-CSV
endpoint, splices the historic + modern stations into one long daily series,
then computes per-year climate indices for the dashboard.

Designed to be run by hand ( `python ottawa_weather_fetch.py` ) but written to
survive unattended runs too:
  - polite, rate-limited HTTP with a real browser User-Agent
  - automatic retry/backoff on transient errors
  - resumable: a year already cached on disk is not re-downloaded
  - logs to console + file

What it produces (all under ./data/)
------------------------------------
  data/raw/station_<id>_daily.csv    one cached CSV per station  (gitignored)
  data/ottawa_daily_combined.csv     spliced daily series        (gitignored)
  data/weather_indices.json          small per-year index file   (COMMITTED)

The dashboard reads only weather_indices.json.

Data source
-----------
ECCC "bulk data" daily endpoint (no API key required):
  https://climate.weather.gc.ca/climate_data/bulk_data_e.html
    ?format=csv&stationID=<ID>&Year=<YYYY>&timeframe=2&submit=Download+Data
  timeframe=2 => daily; one request returns the whole year.

Stations (edit STATIONS below if you want a different splice):
  4333   Ottawa CDA        historic downtown site, daily back to 1889
  49568  Ottawa (modern)   active station reaching the present day
When the two overlap, the EARLIER station in the list wins for those dates, so
the long historic record is preferred and the modern station only fills recent
years. The script logs the actual first/last date it received per station so you
can inspect the seam (see PLAN.md, "continuity caveat").

Usage
-----
  pip install -r requirements.txt
  python ottawa_weather_fetch.py                     # full run, 1889 -> this year
  python ottawa_weather_fetch.py --start 1950        # shorter range
  python ottawa_weather_fetch.py --stations 4333     # single station only
  python ottawa_weather_fetch.py --refresh-current   # re-download the current year
  python ottawa_weather_fetch.py --no-fetch          # rebuild JSON from cache only

Be a good citizen: this hits a public government site. Keep --delay reasonable
and don't run several copies at once (the resume cache already avoids re-work).
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
except ImportError:  # pragma: no cover - guidance only
    sys.exit("This script needs pandas.  Run:  pip install -r requirements.txt")

# Use the OS trust store if available (harmless if the cert chain is already fine).
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:  # pragma: no cover
    pass

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BULK_URL = "https://climate.weather.gc.ca/climate_data/bulk_data_e.html"

# Realistic desktop UA. ECCC serves fine to default agents too, but be polite.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Firefox/124.0"
)

# Stations spliced newest-fills-gaps: earlier entries win on overlapping dates.
# id, human label, first year with data (used only to skip empty early requests).
STATIONS = [
    (4333, "Ottawa CDA (historic)", 1889),
    (49568, "Ottawa (modern)", 2011),
]

FIRST_YEAR_DEFAULT = 1889
DEFAULT_DELAY = 1.5          # seconds between requests

# --- Extreme-weather thresholds (Canadian conventions; tweak here) --------- #
HOT_DAY_C = 30.0             # Tmax >= this  -> "hot day"
TROPICAL_NIGHT_C = 20.0      # Tmin >= this  -> "tropical night"
EXTREME_COLD_C = -25.0       # Tmin <= this  -> "extreme cold day"
HEAVY_RAIN_MM = 25.0         # Total Precip >= this -> "heavy-rain day"
GROWING_BASE_C = 5.0         # base temp for growing-season definition
MIN_DAYS_COMPLETE = 300      # a year needs this many valid days to be "complete"

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "raw"
COMBINED_CSV = DATA_DIR / "ottawa_daily_combined.csv"
INDICES_JSON = DATA_DIR / "weather_indices.json"

log = logging.getLogger("ottawa_weather")


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


def fetch_year_csv(session: requests.Session, station_id: int, year: int) -> str | None:
    """Return the raw daily CSV text for one station-year, or None on failure."""
    params = {
        "format": "csv",
        "stationID": station_id,
        "Year": year,
        "Month": 1,
        "Day": 1,
        "timeframe": 2,          # daily
        "submit": "Download+Data",
    }
    try:
        r = session.get(BULK_URL, params=params, timeout=60)
        r.raise_for_status()
    except requests.RequestException as exc:
        log.warning("  %s %s: request failed (%s)", station_id, year, exc)
        return None
    # ECCC sends UTF-8 (with a BOM and a degree sign in headers).
    r.encoding = "utf-8-sig"
    text = r.text
    if "Date/Time" not in text:
        # Empty year (before the station existed, or a site error page).
        return None
    return text


# --------------------------------------------------------------------------- #
# Download + cache one station's full daily record
# --------------------------------------------------------------------------- #
def download_station(
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
    """Fetch every year for a station, caching to one CSV, and return a DataFrame."""
    cache = RAW_DIR / f"station_{station_id}_daily.csv"
    frames: list[pd.DataFrame] = []

    # Reuse whatever we already cached (resume support).
    cached_years: set[int] = set()
    if cache.exists():
        try:
            prev = pd.read_csv(cache, low_memory=False)
            frames.append(prev)
            if "Year" in prev.columns:
                cached_years = set(pd.to_numeric(prev["Year"], errors="coerce")
                                   .dropna().astype(int).tolist())
        except Exception as exc:
            log.warning("  could not read cache %s (%s); refetching", cache.name, exc)

    if do_fetch:
        this_year = dt.date.today().year
        lo = max(start_year, first_year)
        for year in range(lo, end_year + 1):
            need = year not in cached_years
            if year == this_year and refresh_current:
                need = True
            if not need:
                continue
            log.info("  %s  fetching %d ...", label, year)
            text = fetch_year_csv(session, station_id, year)
            time.sleep(delay)
            if text is None:
                continue
            df = pd.read_csv(io.StringIO(text), low_memory=False)
            if df.empty:
                continue
            # Drop any stale rows for this year we may already hold, then add fresh.
            frames = [f for f in frames
                      if not ("Year" in f.columns and (f["Year"] == year).any())] + [df]

    if not frames:
        log.warning("  %s: no data obtained", label)
        return None

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["Date/Time"]).drop_duplicates(subset=["Date/Time"])
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(cache, index=False)

    dates = pd.to_datetime(combined["Date/Time"], errors="coerce").dropna()
    if not dates.empty:
        log.info("  %s: %d days, %s -> %s",
                 label, len(dates), dates.min().date(), dates.max().date())
    combined["__station"] = station_id
    return combined


# --------------------------------------------------------------------------- #
# Splice stations into one daily series
# --------------------------------------------------------------------------- #
def col(df: pd.DataFrame, needle: str) -> str | None:
    """Find a column whose name contains `needle` (case-insensitive)."""
    for c in df.columns:
        if needle.lower() in c.lower():
            return c
    return None


def build_daily(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Coalesce station frames column-by-column: the first-listed station's value
    is used for a given date/field whenever it is actually present; later stations
    only fill in where the higher-priority station has a gap (e.g. ECCC's blank
    placeholder rows for dates the site hasn't reported yet)."""
    parts = []
    for df in frames:
        d = pd.DataFrame()
        d["date"] = pd.to_datetime(df[col(df, "Date/Time")], errors="coerce")
        d["tmax"] = pd.to_numeric(df[col(df, "Max Temp")], errors="coerce")
        d["tmin"] = pd.to_numeric(df[col(df, "Min Temp")], errors="coerce")
        d["tmean"] = pd.to_numeric(df[col(df, "Mean Temp")], errors="coerce")
        c_rain = col(df, "Total Rain")
        c_snow = col(df, "Total Snow")
        c_prcp = col(df, "Total Precip")
        d["rain"] = pd.to_numeric(df[c_rain], errors="coerce") if c_rain else pd.NA
        d["snow"] = pd.to_numeric(df[c_snow], errors="coerce") if c_snow else pd.NA
        d["precip"] = pd.to_numeric(df[c_prcp], errors="coerce") if c_prcp else pd.NA
        d = (d.dropna(subset=["date"])
              .drop_duplicates(subset="date")
              .set_index("date")
              .sort_index())
        parts.append(d)

    combined = parts[0]
    for d in parts[1:]:
        combined = combined.combine_first(d)   # fills NaNs only, per column
    combined = combined.reset_index().sort_values("date").reset_index(drop=True)
    combined["year"] = combined["date"].dt.year
    return combined


# --------------------------------------------------------------------------- #
# Per-year climate indices
# --------------------------------------------------------------------------- #
def season_of(month: int) -> str:
    # Meteorological seasons; Dec grouped with the following year's winter elsewhere,
    # but for a simple per-calendar-year mean this is fine and transparent.
    return {12: "winter", 1: "winter", 2: "winter",
            3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer",
            9: "fall", 10: "fall", 11: "fall"}[month]


def growing_season_length(g: pd.DataFrame) -> int | None:
    """ETCCDI growing-season length: from the first 6-day run of tmean > 5 C
    (any time in the year) to the first 6-day run of tmean < 5 C after Jul 1."""
    s = g.set_index("date")["tmean"].asfreq("D")
    if s.notna().sum() < 200:
        return None
    warm = (s > GROWING_BASE_C)
    cold = (s < GROWING_BASE_C)

    def first_run_start(mask: pd.Series, after=None):
        run = 0
        for date, val in mask.items():
            if after is not None and date < after:
                run = 0
                continue
            run = run + 1 if val else 0
            if run >= 6:
                return date - pd.Timedelta(days=5)
        return None

    year = int(g["year"].iloc[0])
    start = first_run_start(warm)
    if start is None:
        return None
    end = first_run_start(cold, after=pd.Timestamp(year, 7, 1))
    if end is None:
        return None
    return max(0, (end - start).days)


def frost_free_days(g: pd.DataFrame) -> int | None:
    """Days between the last spring frost and the first fall frost (Tmin < 0)."""
    frost = g[g["tmin"] < 0]
    if frost.empty:
        return None
    year = int(g["year"].iloc[0])
    mid = pd.Timestamp(year, 7, 1)
    spring = frost[frost["date"] < mid]["date"]
    fall = frost[frost["date"] >= mid]["date"]
    if spring.empty or fall.empty:
        return None
    return max(0, (fall.min() - spring.max()).days)


def compute_indices(daily: pd.DataFrame) -> list[dict]:
    out = []
    for year, g in daily.groupby("year"):
        g = g.sort_values("date")
        data_days = int(g[["tmax", "tmin", "tmean"]].notna().any(axis=1).sum())

        rec: dict = {
            "year": int(year),
            "data_days": data_days,
            "complete": data_days >= MIN_DAYS_COMPLETE,
            # --- means / warming ---
            "mean_temp": _round(g["tmean"].mean()),
            "mean_tmax": _round(g["tmax"].mean()),
            "mean_tmin": _round(g["tmin"].mean()),
            # --- heat extremes ---
            "hot_days": _count(g["tmax"] >= HOT_DAY_C),
            "tropical_nights": _count(g["tmin"] >= TROPICAL_NIGHT_C),
            "hottest": _round(g["tmax"].max()),
            # --- cold extremes ---
            "extreme_cold_days": _count(g["tmin"] <= EXTREME_COLD_C),
            "frost_days": _count(g["tmin"] < 0),
            "coldest": _round(g["tmin"].min()),
            # --- season ---
            "growing_season_len": growing_season_length(g),
            "frost_free_days": frost_free_days(g),
            # --- precipitation regime ---
            "total_precip": _round(g["precip"].sum(), 1),
            "total_rain": _round(g["rain"].sum(), 1),
            "total_snow": _round(g["snow"].sum(), 1),
            "heavy_rain_days": _count(g["precip"] >= HEAVY_RAIN_MM),
            "max_1day_precip": _round(g["precip"].max(), 1),
            # --- volatility ---
            "freeze_thaw_days": _count((g["tmax"] > 0) & (g["tmin"] < 0)),
        }
        # Rain's share of total precip (ECCC's own water-equivalent total, which
        # already folds snow's cm depth into mm via its standard density
        # assumption) -- NOT total_rain / (total_rain + total_snow), which would
        # wrongly add mm to raw cm.
        rain = rec["total_rain"]
        precip = rec["total_precip"]
        if rain is not None and precip:
            rec["rain_fraction"] = _round(rain / precip, 3)
        else:
            rec["rain_fraction"] = None

        # seasonal mean temps
        g = g.assign(season=g["date"].dt.month.map(season_of))
        for name, sub in g.groupby("season"):
            rec[f"mean_temp_{name}"] = _round(sub["tmean"].mean())
        out.append(rec)
    return sorted(out, key=lambda r: r["year"])


def _round(v, ndigits: int = 2):
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
    ap.add_argument("--stations", default=None,
                    help="comma-separated station IDs to override the default splice")
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
                  logging.FileHandler(Path(__file__).with_name("weather_fetch.log"),
                                      encoding="utf-8")],
    )

    if args.stations:
        ids = [int(x) for x in args.stations.split(",") if x.strip()]
        stations = [(sid, f"Station {sid}", args.start) for sid in ids]
    else:
        stations = STATIONS

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = make_session()

    log.info("Ottawa weather fetch: %d-%d, stations=%s",
             args.start, args.end, [s[0] for s in stations])

    frames = []
    for sid, label, first_year in stations:
        df = download_station(
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

    daily = build_daily(frames)
    daily.to_csv(COMBINED_CSV, index=False)
    log.info("Spliced daily series: %d days, %s -> %s  (%s)",
             len(daily), daily["date"].min().date(), daily["date"].max().date(),
             COMBINED_CSV.name)

    years = compute_indices(daily)
    payload = {
        "meta": {
            "source": "Environment and Climate Change Canada (climate.weather.gc.ca)",
            "stations": [{"id": s[0], "label": s[1]} for s in stations],
            "generated": dt.datetime.now().isoformat(timespec="seconds"),
            "thresholds": {
                "hot_day_c": HOT_DAY_C,
                "tropical_night_c": TROPICAL_NIGHT_C,
                "extreme_cold_c": EXTREME_COLD_C,
                "heavy_rain_mm": HEAVY_RAIN_MM,
                "growing_base_c": GROWING_BASE_C,
            },
            "n_years": len(years),
        },
        "years": years,
    }
    INDICES_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    complete = sum(1 for y in years if y["complete"])
    log.info("Wrote %s: %d years (%d complete).",
             INDICES_JSON.name, len(years), complete)
    log.info("Done. The dashboard reads data/weather_indices.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

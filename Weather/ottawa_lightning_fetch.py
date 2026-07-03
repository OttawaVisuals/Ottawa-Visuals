#!/usr/bin/env python3
"""
Ottawa lightning-strike fetcher (LightningMaps.org / Blitzortung.org).

Companion to the ECCC daily/hourly weather scripts. This targets lightning as
a complement to (not a replacement for) the ECCC-derived thunderstorm
day-counts in ottawa_weather_fetch_hourly.py. Keeps full per-strike detail
(exact time + lat/lon), not just a daily count, so a map view or time-of-day
analysis is possible later without re-fetching anything.

Everything below was verified by hand before writing this script, not assumed:

Source
------
LightningMaps.org publishes Blitzortung.org's community strike-detection
network as small per-10-minute gzipped JSON files, world-wide, split into ~98
numbered geographic "Areas" with no documented area->region mapping. Found the
right one empirically: fetched sample files from every area number and
inspected their lat/lon. **Area 21** covers roughly 25-49.7 N, -89.9 to
-67.6 W (Gulf Coast up through southern Ontario/Quebec) and its files do
contain real strikes within a few km of Ottawa.

URL pattern (no API key, plain static file server):
  https://data.lightningmaps.org/Public/Strokes/Areas/21/YYYY/MM/DD/HH/YYYYMMDD_HHMM_a21.json.gz
One file per 10-minute window (6/hour). A window with zero global strikes in
Area 21 simply 404s -- that's normal, not an error.

Record format inside each file (one dict per line, trailing comma, *not*
strictly valid JSON as a whole -- e.g. "time" is an unquoted ISO datetime):
  {"time":2024-07-15T18:00:03,"lat":46.010341,"lon":-77.17748,"src":2,"srv":416}
Parsed here with a regex, not json.loads(), because of that. "time"/"lat"/"lon"
are kept; "src"/"srv" are not -- checked empirically across files from
2021/2024/2025 and both are constant *within* a file (e.g. src=2 in every file
sampled; srv differs *between* files -- 416, 1, 2 -- but not within one),
consistent with src being a fixed data-source-type tag and srv the backend
server ID that produced that batch. Neither varies per-strike, so neither
carries information worth the extra columns.

Coverage & the network-growth caveat (important, read before trusting a trend)
--------------------------------------------------------------------------
Area 21 has *some* data from ~Feb 2021 onward, but early availability is
patchy day-to-day (e.g. 2021-02-05 and 2021-02-20 have no data at all where
neighbouring days do) -- consistent with a still-growing volunteer detector
network, not missing lightning. **A rising strike count over the life of this
dataset may partly reflect more detectors coming online, not more real
lightning.** Unlike the ECCC station data (a fixed, calibrated instrument for
136/73 years), this is a crowdsourced network with no stated completeness
guarantee. Treat this as a supplementary, shorter-history, lower-confidence
series -- not on the same footing as the daily/hourly ECCC pipelines.

Volume & concurrency
---------------------
10-minute granularity means ~365*24*6 ~= 52,600 file *attempts* per year. Full
range (2021-present) is roughly 260k attempts. Measured empirically:
  - sequential:        ~0.64s/file  -> ~47h for the full range (impractical)
  - 8 concurrent:       ~0.08s/file -> ~5.7h
  - 24 concurrent:      ~0.02s/file -> ~1.4h, no errors/throttling observed
Default here is a middle ground (10 workers) out of respect for a volunteer-
run community server; raise --workers if you want it faster and are willing
to push harder on their infrastructure.

What it produces (all under ./data/)
------------------------------------
  data/raw/lightning_strikes/<date>.csv   time,lat,lon per strike, one file/day
                                           (gitignored; THE resumability marker --
                                           a day only counts as done once this
                                           file exists, and it's only written
                                           when that day's fetch had zero
                                           failed windows)
  data/raw/lightning_daily_counts.csv     legacy count-only cache from an
                                           earlier version of this script
                                           (gitignored; read as a fallback for
                                           any day not yet re-fetched with full
                                           detail, so that earlier progress
                                           isn't wasted -- not written to anymore)
  data/weather_lightning_indices.json     per-year totals, derived from the
                                           per-day files              (COMMITTED)

Usage
-----
  pip install -r requirements.txt
  python ottawa_lightning_fetch.py                  # full 2021-01 -> today
  python ottawa_lightning_fetch.py --start 2023-01-01 --end 2023-12-31
  python ottawa_lightning_fetch.py --workers 20      # faster, heavier on their server
  python ottawa_lightning_fetch.py --no-fetch        # rebuild JSON from cache only
  python ottawa_lightning_fetch.py --refresh-today   # re-pull today even if cached

Re-runs are resumable: a day is skipped only once its per-day CSV exists under
data/raw/lightning_strikes/. Note this means upgrading from an earlier
count-only run of this script re-fetches every day -- that's expected, it's
how the full per-strike detail gets backfilled -- and as a side effect it also
retries (and fixes the count for) any day that previously had partial network
failures, since the old version incorrectly cached those as "done".
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import json
import logging
import re
import sys
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:  # pragma: no cover
    pass

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BASE_URL = "https://data.lightningmaps.org/Public/Strokes/Areas/21"
USER_AGENT = "Mozilla/5.0 (compatible; OttawaVisualsWeatherProject/1.0)"

OTTAWA_LAT, OTTAWA_LON = 45.4215, -75.6972
# "Ottawa region" bounding box: roughly the National Capital Region and
# surrounding countryside (Kemptville/Perth/Arnavon/Rockland-ish), not just
# the airport point. Wide enough to catch a real regional strike count,
# narrow enough to stay meaningfully "Ottawa" rather than "eastern Ontario".
LAT_HALF_DEG = 0.9   # ~100 km
LON_HALF_DEG = 1.2   # ~95 km at this latitude
LAT_MIN, LAT_MAX = OTTAWA_LAT - LAT_HALF_DEG, OTTAWA_LAT + LAT_HALF_DEG
LON_MIN, LON_MAX = OTTAWA_LON - LON_HALF_DEG, OTTAWA_LON + LON_HALF_DEG

FIRST_DATE_DEFAULT = dt.date(2021, 1, 1)  # data patchily starts ~Feb 2021; 404s handle the gap
DEFAULT_WORKERS = 10

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "raw"
DAILY_CACHE_CSV = RAW_DIR / "lightning_daily_counts.csv"
RAW_STRIKES_DIR = RAW_DIR / "lightning_strikes"  # one CSV/day: time,lat,lon (full detail, resumable)
INDICES_JSON = DATA_DIR / "weather_lightning_indices.json"

# Captures time+lat+lon per strike. "src"/"srv" are also present in the source
# (e.g. {"time":2024-07-15T18:00:03,"lat":46.01,"lon":-77.18,"src":2,"srv":416})
# but checked empirically across files from 2021/2024/2025: "src" is constant
# (=2) in every file sampled -- a fixed data-source-type tag, not per-strike --
# and "srv" is constant *within* a file but differs *between* files (416, 1, 2),
# consistent with it being the backend server ID that produced that batch, an
# infrastructure detail. Neither varies per-strike, so neither is kept.
RECORD_RE = re.compile(r'"time":([^,]+),"lat":([\-\d.]+),"lon":([\-\d.]+)')

log = logging.getLogger("ottawa_lightning")


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def make_session(pool_size: int) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    adapter = HTTPAdapter(max_retries=retry, pool_connections=pool_size, pool_maxsize=pool_size)
    s.mount("https://", adapter)
    return s


def fetch_window(session: requests.Session, day: dt.date, hour: int, minute: str) -> list | None:
    """Fetch one 10-minute file; return the list of (time, lat, lon) records
    inside the Ottawa bounding box, or None on a real failure. A 404 (no
    strikes anywhere in Area 21 that window) is normal -> empty list."""
    ymd = day.strftime("%Y/%m/%d")
    stamp = f"{day.strftime('%Y%m%d')}_{hour:02d}{minute}"
    url = f"{BASE_URL}/{ymd}/{hour:02d}/{stamp}_a21.json.gz"
    try:
        r = session.get(url, timeout=15)
    except requests.RequestException:
        return None  # transient failure, distinct from "genuinely no data"
    if r.status_code == 404:
        return []
    if r.status_code != 200:
        return None
    try:
        import gzip
        text = gzip.decompress(r.content).decode("utf-8", errors="replace")
    except Exception:
        return None
    out = []
    for m in RECORD_RE.finditer(text):
        time_str, lat, lon = m.group(1), float(m.group(2)), float(m.group(3))
        if LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX:
            out.append((time_str, lat, lon))
    return out


def fetch_day(session: requests.Session, day: dt.date, workers: int) -> tuple[int, int]:
    """Fetch all 144 windows for one day concurrently, write the matched
    strikes' full (time, lat, lon) to a per-day CSV, and return (count,
    failures). Writing the CSV -- even with zero rows -- marks the day done."""
    windows = [(h, m) for h in range(24) for m in ("00", "10", "20", "30", "40", "50")]
    records: list[tuple[str, float, float]] = []
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(fetch_window, session, day, h, m) for h, m in windows]
        for fut in concurrent.futures.as_completed(futures):
            result = fut.result()
            if result is None:
                failures += 1
            else:
                records.extend(result)
    if failures == 0:
        write_raw_day(day.isoformat(), records)
    return len(records), failures


def write_raw_day(date_str: str, records: list[tuple[str, float, float]]) -> None:
    RAW_STRIKES_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_STRIKES_DIR / f"{date_str}.csv"
    records.sort(key=lambda r: r[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "lat", "lon"])
        w.writerows(records)


def raw_day_done(date_str: str) -> bool:
    return (RAW_STRIKES_DIR / f"{date_str}.csv").exists()


# --------------------------------------------------------------------------- #
# Resumable per-day cache
# --------------------------------------------------------------------------- #
# Two generations of cache exist:
#   - legacy: data/raw/lightning_daily_counts.csv (date,count,failures), from
#     before this script kept full per-strike detail. Read-only fallback below
#     for any day not yet re-fetched with full detail -- keeps that progress
#     useful instead of throwing it away.
#   - current: data/raw/lightning_strikes/<date>.csv (time,lat,lon per strike).
#     A day is only considered "done" once this file exists, which -- unlike
#     the legacy cache -- is *not* written when a day had any failed windows,
#     so a day that failed partially is correctly retried on the next run
#     rather than silently staying under-counted forever.
def load_legacy_counts() -> dict[str, int]:
    if not DAILY_CACHE_CSV.exists():
        return {}
    out = {}
    with DAILY_CACHE_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["date"]] = int(row["count"])
    return out


def load_raw_counts() -> dict[str, int]:
    if not RAW_STRIKES_DIR.exists():
        return {}
    out = {}
    for path in RAW_STRIKES_DIR.glob("*.csv"):
        with path.open(newline="", encoding="utf-8") as f:
            out[path.stem] = sum(1 for _ in f) - 1  # minus header
    return out


OTTAWA_UTC_OFFSET_H = -4  # fixed EDT approximation, not DST-aware -- see note below

def compute_seasonality() -> dict:
    """Aggregate every strike's month-of-year and hour-of-day across the whole
    dataset. Pure local file I/O over the already-downloaded per-day raw files
    -- no network calls, runs in seconds even across ~2000 files.

    Timezone: verified empirically, not assumed -- a file's own directory hour
    (e.g. .../18/20250710_1800_a21.json.gz) always matches its records' "time"
    hour exactly, and since this is one global archive with a single unified
    directory scheme across every continent, that's only possible if "time" is
    UTC (a per-region-local folder scheme couldn't produce a single consistent
    HH path across all ~98 areas worldwide). strikes_by_hour is shifted to a
    fixed UTC-4 (EDT) below to read as Ottawa local time -- not DST-aware, so
    winter strikes (a small fraction of the total -- Nov-Feb is ~0.06% of all
    strikes in this dataset) are off by up to an hour. Month-of-year is
    unaffected by this (a +/-4h shift essentially never moves a strike from
    one month to another)."""
    by_month = [0] * 12   # index 0 = January
    by_hour = [0] * 24
    if not RAW_STRIKES_DIR.exists():
        return {"strikes_by_month": by_month, "strikes_by_hour": by_hour}
    for path in RAW_STRIKES_DIR.glob("*.csv"):
        with path.open(newline="", encoding="utf-8") as f:
            next(f, None)  # header
            for line in f:
                # "time,lat,lon" -- time like 2025-07-10T18:00:03 (UTC)
                time_str = line.split(",", 1)[0]
                if len(time_str) < 13:
                    continue
                by_month[int(time_str[5:7]) - 1] += 1
                local_hour = (int(time_str[11:13]) + OTTAWA_UTC_OFFSET_H) % 24
                by_hour[local_hour] += 1
    return {"strikes_by_month": by_month, "strikes_by_hour": by_hour}


# --------------------------------------------------------------------------- #
# Build indices JSON
# --------------------------------------------------------------------------- #
def build_indices(cached: dict[str, int]) -> dict:
    by_year: dict[int, dict] = {}
    for date_str, count in cached.items():
        year = int(date_str[:4])
        rec = by_year.setdefault(year, {"year": year, "strikes": 0, "days_with_strikes": 0, "days_recorded": 0})
        rec["strikes"] += count
        rec["days_recorded"] += 1
        if count > 0:
            rec["days_with_strikes"] += 1
    years = sorted(by_year.values(), key=lambda r: r["year"])
    return {
        "meta": {
            "source": "LightningMaps.org / Blitzortung.org community network, Area 21",
            "bounding_box": {"lat_min": LAT_MIN, "lat_max": LAT_MAX, "lon_min": LON_MIN, "lon_max": LON_MAX},
            "generated": dt.datetime.now().isoformat(timespec="seconds"),
            "caveat": "Crowdsourced volunteer detector network, not a calibrated government "
                      "instrument. Station density has grown over time (day-to-day availability "
                      "was patchy in early 2021), so a rising strike count may partly reflect "
                      "more detectors coming online rather than more real lightning. Treat as "
                      "supplementary and lower-confidence versus the ECCC daily/hourly series.",
            "n_years": len(years),
        },
        "years": years,
        **compute_seasonality(),
    }


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=str, default=FIRST_DATE_DEFAULT.isoformat())
    ap.add_argument("--end", type=str, default=dt.date.today().isoformat())
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                     help=f"concurrent requests per day (default {DEFAULT_WORKERS})")
    ap.add_argument("--refresh-today", action="store_true", help="re-fetch today even if cached")
    ap.add_argument("--no-fetch", action="store_true", help="skip all downloads; rebuild JSON from cache only")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(message)s", datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(Path(__file__).with_name("lightning_fetch.log"), encoding="utf-8")],
    )

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    today = dt.date.today()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    raw_counts = load_raw_counts()
    legacy_counts = load_legacy_counts()
    n_legacy_only = sum(1 for d in legacy_counts if d not in raw_counts)
    log.info("Ottawa lightning fetch: %s -> %s, %d days with full detail already cached "
             "(+%d legacy count-only days will be upgraded to full detail), workers=%d",
             start, end, len(raw_counts), n_legacy_only, args.workers)

    if not args.no_fetch:
        session = make_session(pool_size=args.workers)
        day = start
        n_done = 0
        t_start = time.time()
        total_days = (end - start).days + 1
        while day <= end:
            date_str = day.isoformat()
            need = not raw_day_done(date_str)
            if day == today and args.refresh_today:
                need = True
            if need:
                count, failures = fetch_day(session, day, args.workers)
                n_done += 1
                if failures:
                    log.warning("  %s: %d strikes but %d windows failed -- not cached, will retry next run",
                                date_str, count, failures)
                else:
                    raw_counts[date_str] = count
                    if n_done % 30 == 0:
                        elapsed = time.time() - t_start
                        rate = elapsed / n_done
                        remaining = (total_days - n_done) * rate
                        log.info("  ...%s: %d strikes  [%d/%d days fetched, ~%.0fs left]",
                                 date_str, count, n_done, total_days, remaining)
            day += dt.timedelta(days=1)
        log.info("Fetch complete: %d new days in %.1fs.", n_done, time.time() - t_start)

    # Prefer full-detail counts; fall back to the legacy count-only cache for
    # any day not yet re-fetched (e.g. --end cut a run short before reaching it).
    combined = {**legacy_counts, **raw_counts}
    payload = build_indices(combined)
    INDICES_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    total_strikes = sum(y["strikes"] for y in payload["years"])
    log.info("Wrote %s: %d years, %d total strikes in the Ottawa region (%d days have full "
             "per-strike detail in data/raw/lightning_strikes/, %d still legacy count-only).",
             INDICES_JSON.name, len(payload["years"]), total_strikes,
             len(raw_counts), len(combined) - len(raw_counts))
    log.info("Done. The dashboard reads data/weather_lightning_indices.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

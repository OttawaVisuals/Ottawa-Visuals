#!/usr/bin/env python3
"""
Ottawa lightning-strike fetcher (LightningMaps.org / Blitzortung.org).

Companion to the ECCC daily/hourly weather scripts. This targets a strike-
*count* angle -- "how many lightning strikes hit the Ottawa region per year"
-- as a complement to (not a replacement for) the ECCC-derived thunderstorm
day-counts in ottawa_weather_fetch_hourly.py.

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
Parsed here with a regex, not json.loads(), because of that.

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
  data/raw/lightning_daily_counts.csv   per-day counts, resumable cache (gitignored)
  data/weather_lightning_indices.json   per-year/month totals            (COMMITTED)

Usage
-----
  pip install -r requirements.txt
  python ottawa_lightning_fetch.py                  # full 2021-02 -> today
  python ottawa_lightning_fetch.py --start 2023-01-01 --end 2023-12-31
  python ottawa_lightning_fetch.py --workers 20      # faster, heavier on their server
  python ottawa_lightning_fetch.py --no-fetch        # rebuild JSON from cache only
  python ottawa_lightning_fetch.py --refresh-today    # re-pull today even if cached

Re-runs are resumable: days already in the cache CSV are skipped.
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
INDICES_JSON = DATA_DIR / "weather_lightning_indices.json"

RECORD_RE = re.compile(r'"lat":([\-\d.]+),"lon":([\-\d.]+)')

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


def fetch_window(session: requests.Session, day: dt.date, hour: int, minute: str) -> int:
    """Fetch one 10-minute file; return the count of records inside the Ottawa
    bounding box. A 404 (no strikes anywhere in Area 21 that window) -> 0."""
    ymd = day.strftime("%Y/%m/%d")
    stamp = f"{day.strftime('%Y%m%d')}_{hour:02d}{minute}"
    url = f"{BASE_URL}/{ymd}/{hour:02d}/{stamp}_a21.json.gz"
    try:
        r = session.get(url, timeout=15)
    except requests.RequestException:
        return -1  # transient failure, distinct from "genuinely no data"
    if r.status_code == 404:
        return 0
    if r.status_code != 200:
        return -1
    try:
        import gzip
        text = gzip.decompress(r.content).decode("utf-8", errors="replace")
    except Exception:
        return -1
    count = 0
    for m in RECORD_RE.finditer(text):
        lat, lon = float(m.group(1)), float(m.group(2))
        if LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX:
            count += 1
    return count


def fetch_day(session: requests.Session, day: dt.date, workers: int) -> tuple[int, int]:
    """Fetch all 144 windows for one day concurrently. Returns (count, failures)."""
    windows = [(h, m) for h in range(24) for m in ("00", "10", "20", "30", "40", "50")]
    count = 0
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(fetch_window, session, day, h, m) for h, m in windows]
        for fut in concurrent.futures.as_completed(futures):
            n = fut.result()
            if n < 0:
                failures += 1
            else:
                count += n
    return count, failures


# --------------------------------------------------------------------------- #
# Resumable per-day cache
# --------------------------------------------------------------------------- #
def load_cached_days() -> dict[str, int]:
    if not DAILY_CACHE_CSV.exists():
        return {}
    out = {}
    with DAILY_CACHE_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["date"]] = int(row["count"])
    return out


def append_cache_row(date_str: str, count: int, failures: int) -> None:
    is_new = not DAILY_CACHE_CSV.exists()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with DAILY_CACHE_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["date", "count", "failures"])
        w.writerow([date_str, count, failures])


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

    cached = load_cached_days()
    log.info("Ottawa lightning fetch: %s -> %s, %d days already cached, workers=%d",
             start, end, len(cached), args.workers)

    if not args.no_fetch:
        session = make_session(pool_size=args.workers)
        day = start
        n_done = 0
        t_start = time.time()
        total_days = (end - start).days + 1
        while day <= end:
            date_str = day.isoformat()
            need = date_str not in cached
            if day == today and args.refresh_today:
                need = True
            if need:
                count, failures = fetch_day(session, day, args.workers)
                append_cache_row(date_str, count, failures)
                cached[date_str] = count
                n_done += 1
                if failures:
                    log.warning("  %s: %d strikes (%d failed windows, will retry next run)", date_str, count, failures)
                elif n_done % 30 == 0:
                    elapsed = time.time() - t_start
                    rate = elapsed / n_done
                    remaining = (total_days - n_done) * rate
                    log.info("  ...%s: %d strikes  [%d/%d days fetched, ~%.0fs left]",
                             date_str, count, n_done, total_days, remaining)
            day += dt.timedelta(days=1)
        log.info("Fetch complete: %d new days in %.1fs.", n_done, time.time() - t_start)

    payload = build_indices(cached)
    INDICES_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    total_strikes = sum(y["strikes"] for y in payload["years"])
    log.info("Wrote %s: %d years, %d total strikes in the Ottawa region.",
             INDICES_JSON.name, len(payload["years"]), total_strikes)
    log.info("Done. The dashboard reads data/weather_lightning_indices.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

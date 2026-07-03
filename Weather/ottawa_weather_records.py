#!/usr/bin/env python3
"""
Ottawa weather RECORDS builder.

Third companion to ottawa_weather_fetch.py (daily, 1889-present) and
ottawa_weather_fetch_hourly.py (hourly, 1953-present). Those two scripts fetch
and cache the raw data and emit per-year *index* JSON. This script does no
fetching at all -- it reads the caches those two already produced and distils
them into a small "records & extremes" file for the dashboard: all-time single
records, longest streaks, and short top-N leaderboards.

Inputs (all already produced by the other two scripts / the lightning fetcher):
  data/ottawa_daily_combined.csv          spliced daily series (1889-present)
  data/raw/station_4337_hourly.csv        historic hourly (1953-2011)
  data/raw/station_49568_hourly.csv       modern hourly (2012-present)
  data/raw/lightning_strikes/<date>.csv   per-day strike detail (2021-present)

Output:
  data/weather_records.json               COMMITTED, read by weather.html

Why records come from two different ranges (kept honest on the page):
  - Temperature/precip *all-time* records use the DAILY record (1889+), so the
    headline "hottest day ever" reflects the full 136-year history. Ottawa's
    actual record highs predate 1953.
  - Humidex, wind chill, wind speed and the hour-resolution leaderboards can
    only come from the HOURLY record (1953+), which does not reach back to the
    pre-war heat. The dashboard labels the hourly block "1953+" so the two
    don't look like they contradict each other.

Usage:
  python ottawa_weather_records.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import logging
import os
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    sys.exit("This script needs pandas.  Run:  pip install -r requirements.txt")

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "raw"
DAILY_CSV = DATA_DIR / "ottawa_daily_combined.csv"
HOURLY_STATIONS = [4337, 49568]  # historic first: it wins on overlapping hours
LIGHTNING_DIR = RAW_DIR / "lightning_strikes"
OUT_JSON = DATA_DIR / "weather_records.json"

MIN_YEAR_DAYS = 350  # a year needs this many daily obs to rank for warmest/coldest

log = logging.getLogger("ottawa_weather_records")


def col(df: pd.DataFrame, needle: str) -> str | None:
    for c in df.columns:
        if needle.lower() in c.lower():
            return c
    return None


# --------------------------------------------------------------------------- #
# Label helpers (Python formats the human-readable strings so the page's JS
# doesn't have to parse dates)
# --------------------------------------------------------------------------- #
def day_label(d: dt.date) -> str:
    return d.strftime("%b %-d, %Y") if os.name != "nt" else d.strftime("%b %#d, %Y")


def hour_label(t: dt.datetime) -> str:
    hh = t.strftime("%-I %p") if os.name != "nt" else t.strftime("%#I %p")
    day = t.strftime("%b %-d, %Y") if os.name != "nt" else t.strftime("%b %#d, %Y")
    return f"{day} · {hh}"


def month_label(d: dt.date) -> str:
    return d.strftime("%b %Y")


# --------------------------------------------------------------------------- #
# Daily records (1889-present)
# --------------------------------------------------------------------------- #
def build_daily(records: dict) -> None:
    daily = pd.read_csv(DAILY_CSV, parse_dates=["date"]).sort_values("date").reset_index(drop=True)

    def extreme_day(colname, ascending):
        d = daily.dropna(subset=[colname])
        if colname in ("rain", "snow"):
            d = d[d[colname] > 0]
        r = d.sort_values(colname, ascending=ascending).iloc[0]
        return {"value": round(float(r[colname]), 1),
                "date": r["date"].date().isoformat(),
                "label": day_label(r["date"].date())}

    def leaderboard_day(colname, ascending, n=5):
        d = daily.dropna(subset=[colname])
        if colname in ("rain", "snow"):
            d = d[d[colname] > 0]
        d = d.sort_values(colname, ascending=ascending).head(n)
        return [{"value": round(float(r[colname]), 1),
                 "date": r["date"].date().isoformat(),
                 "label": day_label(r["date"].date())} for _, r in d.iterrows()]

    records["all_time"]["hottest_day"] = extreme_day("tmax", ascending=False)
    records["all_time"]["coldest_day"] = extreme_day("tmin", ascending=True)
    records["all_time"]["snowiest_day"] = extreme_day("snow", ascending=False)
    records["all_time"]["rainiest_day"] = extreme_day("rain", ascending=False)

    yr = daily.dropna(subset=["tmean"]).groupby("year").agg(
        tmean=("tmean", "mean"), n=("tmean", "size"))
    yr = yr[yr["n"] >= MIN_YEAR_DAYS]
    warm, cold = yr["tmean"].idxmax(), yr["tmean"].idxmin()
    records["all_time"]["warmest_year"] = {"value": round(float(yr.loc[warm, "tmean"]), 1),
                                           "date": int(warm), "label": str(int(warm))}
    records["all_time"]["coldest_year"] = {"value": round(float(yr.loc[cold, "tmean"]), 1),
                                           "date": int(cold), "label": str(int(cold))}

    records["leaderboards"]["snowiest_days"] = leaderboard_day("snow", ascending=False)

    # Daily streaks (consecutive calendar days meeting a predicate)
    def daily_streak(pred):
        d = daily.dropna(subset=["tmax", "tmin"])
        best = cur = 0
        best_end = None
        prev = None
        for _, r in d.iterrows():
            ok = pred(r)
            consec = prev is not None and (r["date"] - prev).days == 1
            cur = cur + 1 if (ok and consec) else (1 if ok else 0)
            if cur > best:
                best, best_end = cur, r["date"].date()
            prev = r["date"]
        return {"value": best, "when": month_label(best_end) if best_end else None}

    records["streaks"]["hot_days"] = daily_streak(lambda r: r["tmax"] >= 30)
    records["streaks"]["deep_freeze_days"] = daily_streak(lambda r: r["tmax"] < 0)
    records["streaks"]["frost_free_days"] = daily_streak(lambda r: r["tmin"] > 0)
    log.info("Daily records done (%d days, %s-%s).",
             len(daily), daily["year"].min(), daily["year"].max())


# --------------------------------------------------------------------------- #
# Hourly records (1953-present)
# --------------------------------------------------------------------------- #
def load_hourly_station(sid: int) -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / f"station_{sid}_hourly.csv", low_memory=False)
    out = pd.DataFrame()
    key = col(df, "Date/Time (LST)") or col(df, "Date/Time")
    out["dt"] = pd.to_datetime(df[key], errors="coerce")
    out["temp"] = pd.to_numeric(df[col(df, "Temp")], errors="coerce")
    out["hmdx"] = pd.to_numeric(df[col(df, "Hmdx")], errors="coerce") if col(df, "Hmdx") else pd.NA
    out["wc"] = pd.to_numeric(df[col(df, "Wind Chill")], errors="coerce") if col(df, "Wind Chill") else pd.NA
    out["wind"] = pd.to_numeric(df[col(df, "Wind Spd")], errors="coerce")
    return out.dropna(subset=["dt"])


def build_hourly(records: dict) -> None:
    parts = [load_hourly_station(sid) for sid in HOURLY_STATIONS]
    hourly = (pd.concat(parts, ignore_index=True)
              .drop_duplicates(subset=["dt"], keep="first")  # historic wins
              .sort_values("dt").reset_index(drop=True))
    hourly["date"] = hourly["dt"].dt.date

    def extreme_hour(colname, ascending):
        d = hourly.dropna(subset=[colname]).sort_values(colname, ascending=ascending).iloc[0]
        return {"value": round(float(d[colname]), 1),
                "datetime": d["dt"].isoformat(),
                "label": hour_label(d["dt"].to_pydatetime())}

    def leaderboard_hour(colname, ascending, n=5):
        d = (hourly.dropna(subset=[colname]).sort_values(colname, ascending=ascending)
             .drop_duplicates(subset=["date"], keep="first").head(n))  # one per day
        return [{"value": round(float(r[colname]), 1),
                 "datetime": r["dt"].isoformat(),
                 "label": hour_label(r["dt"].to_pydatetime())} for _, r in d.iterrows()]

    records["all_time"]["highest_humidex"] = extreme_hour("hmdx", ascending=False)
    records["all_time"]["lowest_windchill"] = extreme_hour("wc", ascending=True)
    records["all_time"]["windiest_hour"] = extreme_hour("wind", ascending=False)
    records["leaderboards"]["hottest_hours"] = leaderboard_hour("temp", ascending=False)
    records["leaderboards"]["coldest_hours"] = leaderboard_hour("temp", ascending=True)

    def hourly_streak(thresh, ge=True):
        d = hourly.dropna(subset=["temp"])
        best = cur = 0
        best_end = None
        prev = None
        for t, v in zip(d["dt"], d["temp"]):
            ok = (v >= thresh) if ge else (v <= thresh)
            consec = prev is not None and (t - prev) == pd.Timedelta(hours=1)
            cur = cur + 1 if (ok and consec) else (1 if ok else 0)
            if cur > best:
                best, best_end = cur, t
            prev = t
        return {"value": best, "when": month_label(best_end.date()) if best_end is not None else None}

    records["streaks"]["hours_20"] = hourly_streak(20, ge=True)
    records["streaks"]["hours_30"] = hourly_streak(30, ge=True)
    records["streaks"]["hours_below_20neg"] = hourly_streak(-20, ge=False)
    log.info("Hourly records done (%d hours, %s-%s).",
             len(hourly), hourly["dt"].min().year, hourly["dt"].max().year)


# --------------------------------------------------------------------------- #
# Lightning leaderboard (2021-present)
# --------------------------------------------------------------------------- #
def build_lightning(records: dict) -> None:
    files = sorted(glob.glob(str(LIGHTNING_DIR / "*.csv")))
    if not files:
        log.warning("No lightning per-day files found; skipping lightning leaderboard.")
        return
    counts = []
    for f in files:
        date = os.path.splitext(os.path.basename(f))[0]
        try:
            with open(f, encoding="utf-8") as fh:
                n = max(sum(1 for _ in fh) - 1, 0)  # minus header
        except Exception:
            n = 0
        counts.append((date, n))
    counts.sort(key=lambda x: x[1], reverse=True)
    out = []
    for date, n in counts[:5]:
        d = dt.date.fromisoformat(date)
        out.append({"value": n, "date": date, "label": day_label(d)})
    records["leaderboards"]["biggest_lightning_days"] = out
    log.info("Lightning leaderboard done (%d days scanned).", len(files))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                        datefmt="%H:%M:%S")

    if not DAILY_CSV.exists():
        log.error("Missing %s -- run ottawa_weather_fetch.py first.", DAILY_CSV.name)
        return 1

    records = {"all_time": {}, "streaks": {}, "leaderboards": {}}
    build_daily(records)
    try:
        build_hourly(records)
    except FileNotFoundError as exc:
        log.warning("Hourly cache missing (%s); hourly records skipped.", exc)
    build_lightning(records)

    payload = {
        "meta": {
            "generated": dt.datetime.now().isoformat(timespec="seconds"),
            "daily_source": "ECCC daily, Ottawa CDA (1889-present)",
            "hourly_source": "ECCC hourly, airport stations 4337/49568 (1953-present)",
            "lightning_source": "LightningMaps.org / Blitzortung Area 21 (2021-present)",
            "note": "All-time temperature/precip records use the 1889+ daily record; "
                    "humidex, wind chill, wind speed and the hour-resolution "
                    "leaderboards only exist in the 1953+ hourly record.",
        },
        **records,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Wrote %s.", OUT_JSON.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

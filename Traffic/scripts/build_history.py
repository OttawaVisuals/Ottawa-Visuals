#!/usr/bin/env python3
"""Aggregate the raw traffic CSVs into a growing historical dataset.

Reads Traffic/data/*.csv (append-only raw readings) and writes compact JSON
rollups to Traffic/data/history/ that accumulate as collection continues:

  corridor_daily.json : per date, per corridor+direction — AM/PM peak & overnight
                        mean travel time, daily min/max, sample count.
  city_daily.json     : per date — peak/mean active jams and congestion %.
  extremes.json       : per corridor+direction — all-time shortest/longest/mean.

Recomputed from the full raw files each run (raw is the source of truth), so it
is idempotent and safe to run on every push. Stdlib only.
"""
import csv
import datetime
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HIST = DATA / "history"


def load(name):
    p = DATA / name
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def date_of(ts):   # "2026-07-08T07:15:19-0400" -> "2026-07-08"
    return (ts or "")[:10]


def hour_of(ts):
    try:
        return int(ts[11:13])
    except (ValueError, IndexError):
        return None


def weekday(date_str):
    y, m, d = map(int, date_str.split("-"))
    return datetime.date(y, m, d).weekday()  # 0 = Monday


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs)) if xs else None


def main():
    HIST.mkdir(parents=True, exist_ok=True)
    corr = load("corridor_travel_times.csv")
    seg = load("segment_speeds.csv")
    inc = load("incidents_summary.csv")

    # --- corridor daily buckets + all-time extremes ---
    daily = defaultdict(lambda: defaultdict(lambda: {"am": [], "pm": [], "off": [], "all": []}))
    extremes = defaultdict(lambda: {"min": None, "max": None, "vals": []})
    for r in corr:
        tt = num(r.get("travel_time_s"))
        if tt is None:
            continue
        key = f'{r["corridor_id"]}|{r["direction"]}'
        d, h = date_of(r["timestamp_local"]), hour_of(r["timestamp_local"])
        e = extremes[key]
        e["min"] = tt if e["min"] is None else min(e["min"], tt)
        e["max"] = tt if e["max"] is None else max(e["max"], tt)
        e["vals"].append(tt)
        b = daily[d][key]
        b["all"].append(tt)
        if h is not None:
            if 7 <= h < 9:
                b["am"].append(tt)
            elif 16 <= h < 18:
                b["pm"].append(tt)
            elif 0 <= h < 5:
                b["off"].append(tt)

    corridor_daily = []
    for d in sorted(daily):
        row = {"date": d, "weekday": weekday(d), "corridors": {}}
        for key, b in sorted(daily[d].items()):
            row["corridors"][key] = {
                "am_peak_s": mean(b["am"]),
                "pm_peak_s": mean(b["pm"]),
                "overnight_s": mean(b["off"]),
                "min_s": int(min(b["all"])) if b["all"] else None,
                "max_s": int(max(b["all"])) if b["all"] else None,
                "n": len(b["all"]),
            }
        corridor_daily.append(row)

    ext_out = {
        k: {"min_s": int(v["min"]), "max_s": int(v["max"]), "mean_s": mean(v["vals"]), "n": len(v["vals"])}
        for k, v in sorted(extremes.items())
    }

    # --- city daily: congestion (segments) + jams (incidents) ---
    cong_by_ts, ts_date = defaultdict(list), {}
    for r in seg:
        cur, ff = num(r.get("current_speed_kmh")), num(r.get("free_flow_speed_kmh"))
        if cur is None or not ff:
            continue
        ts = r["timestamp_local"]
        ts_date[ts] = date_of(ts)
        cong_by_ts[ts].append(max(0.0, 1 - cur / ff))
    day_cong = defaultdict(list)
    for ts, fracs in cong_by_ts.items():
        day_cong[ts_date[ts]].append(sum(fracs) / len(fracs))  # mean congestion at that sample
    day_jams = defaultdict(list)
    for r in inc:
        j = num(r.get("jam_count"))
        if j is not None:
            day_jams[date_of(r["timestamp_local"])].append(j)

    city_daily = []
    for d in sorted(set(day_cong) | set(day_jams)):
        cong, jams = day_cong.get(d, []), day_jams.get(d, [])
        city_daily.append({
            "date": d,
            "weekday": weekday(d),
            "peak_congestion_pct": round(max(cong) * 100) if cong else None,
            "mean_congestion_pct": round(sum(cong) / len(cong) * 100) if cong else None,
            "max_jams": int(max(jams)) if jams else None,
            "mean_jams": round(sum(jams) / len(jams)) if jams else None,
        })

    (HIST / "corridor_daily.json").write_text(json.dumps(corridor_daily, indent=1), encoding="utf-8")
    (HIST / "city_daily.json").write_text(json.dumps(city_daily, indent=1), encoding="utf-8")
    (HIST / "extremes.json").write_text(json.dumps(ext_out, indent=1), encoding="utf-8")
    print(f"history: {len(corridor_daily)} day(s), {len(ext_out)} corridor-dirs, {len(city_daily)} city-day(s)")


if __name__ == "__main__":
    main()

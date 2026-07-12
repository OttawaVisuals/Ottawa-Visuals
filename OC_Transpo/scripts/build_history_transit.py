#!/usr/bin/env python3
"""Aggregate the raw transit summary CSVs into a growing historical dataset.

Reads OC_Transpo/rt_data/*.csv (append-only per-sample summaries) and writes a
compact JSON rollup to OC_Transpo/rt_data/history/ that accumulates as
collection continues:

  transit_daily.json : per date — sample count, AM/PM-peak and daily mean/max
                       active buses, mean fleet speed, mean/max cancelled
                       trips and cancellation % (of trips tracked).

Peak windows match Traffic/scripts/build_history.py (AM 07-09, PM 16-18 local)
so road and transit daily aggregates line up. Uses the group == "all" rows.
Recomputed from the full raw files each run (raw is the source of truth), so
it is idempotent and safe to run on every push. Stdlib only.
"""
import csv
import datetime
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "rt_data"
HIST = DATA / "history"


def load(name):
    p = DATA / name
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("group") == "all" and not r.get("error")]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def date_of(ts):
    return (ts or "")[:10]


def hour_of(ts):
    try:
        return int(ts[11:13])
    except (ValueError, IndexError):
        return None


def weekday(date_str):
    y, m, d = map(int, date_str.split("-"))
    return datetime.date(y, m, d).weekday()  # 0 = Monday


def mean(xs, digits=0):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), digits) if xs else None


def main():
    HIST.mkdir(parents=True, exist_ok=True)
    trips = load("trip_updates_summary.csv")
    vehicles = load("vehicle_positions_summary.csv")

    days = defaultdict(lambda: {"veh": [], "veh_am": [], "veh_pm": [], "speed": [],
                                "cx": [], "cx_pct": []})
    for r in vehicles:
        v = num(r.get("vehicles"))
        if v is None:
            continue
        d, h = date_of(r["timestamp_local"]), hour_of(r["timestamp_local"])
        b = days[d]
        b["veh"].append(v)
        if h is not None:
            if 7 <= h < 9:
                b["veh_am"].append(v)
            elif 16 <= h < 18:
                b["veh_pm"].append(v)
        s = num(r.get("mean_speed_kmh"))
        if s is not None:
            b["speed"].append(s)

    for r in trips:
        tracked, cx = num(r.get("trips_tracked")), num(r.get("trips_canceled"))
        if cx is None:
            continue
        b = days[date_of(r["timestamp_local"])]
        b["cx"].append(cx)
        if tracked:
            b["cx_pct"].append(cx / tracked * 100)

    out = []
    for d in sorted(days):
        b = days[d]
        out.append({
            "date": d,
            "weekday": weekday(d),
            "n": len(b["veh"]),
            "buses_am_peak": mean(b["veh_am"]),
            "buses_pm_peak": mean(b["veh_pm"]),
            "buses_mean": mean(b["veh"]),
            "buses_max": int(max(b["veh"])) if b["veh"] else None,
            "speed_mean_kmh": mean(b["speed"], 1),
            "cancelled_mean": mean(b["cx"], 1),
            "cancelled_max": int(max(b["cx"])) if b["cx"] else None,
            "cancelled_pct_mean": mean(b["cx_pct"], 2),
        })

    (HIST / "transit_daily.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"transit history: {len(out)} day(s)")


if __name__ == "__main__":
    main()

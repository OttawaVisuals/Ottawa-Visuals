#!/usr/bin/env python3
"""Aggregate the raw transit summary CSVs into a growing historical dataset.

Reads OC_Transpo/rt_data/*.csv (append-only per-sample summaries) and writes a
compact JSON rollup to OC_Transpo/rt_data/history/ that accumulates as
collection continues:

  transit_daily.json : per date — sample count, AM/PM-peak and daily mean/max
                       active buses, mean fleet speed, mean/max cancelled
                       trips and cancellation % (of trips tracked), and
                       on-time figures once poll_gtfsrt.py fills them in:
                       bus on-time / early / late %, punctuality of
                       less-frequent routes (all day, AM and PM peak), and
                       the share within +/-5 min (otranspo.ca's definition).

On-time % is weighted by trips observed x minutes the sample stands for (peaks
are sampled every 5 min, off-peak every 15), so the daily figure is a share of
bus-trip-time rather than over-counting the peaks. This rollup is the permanent
record: individual buses are never stored.

Peak windows match Traffic/scripts/build_history.py (AM 07-09, PM 16-18 local)
so road and transit daily aggregates line up. Fleet and cancellation figures
use the group == "all" rows.
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


def load(name, group="all"):
    p = DATA / name
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("group") == group and not r.get("error")]


def weighted_pct(samples, field, hours=None):
    """Share across a day's samples, weighted by delays_observed x sample interval."""
    num_, den = 0.0, 0.0
    for r, minutes in samples:
        h = hour_of(r["timestamp_local"])
        if hours and (h is None or not (hours[0] <= h < hours[1])):
            continue
        v, n = num(r.get(field)), num(r.get("delays_observed"))
        if v is None or not n:
            continue
        num_ += v * n * minutes
        den += n * minutes
    return round(num_ / den, 1) if den else None


def by_day_with_interval(rows):
    """{date: [(row, minutes it represents)]}: gap to the previous sample, 5-60 min."""
    out = defaultdict(list)
    prev = {}
    for r in sorted(rows, key=lambda r: r["timestamp_utc"]):
        d = date_of(r["timestamp_local"])
        t = datetime.datetime.strptime(r["timestamp_utc"], "%Y-%m-%dT%H:%M:%SZ")
        gap = (t - prev[d]).total_seconds() / 60 if d in prev else 15
        prev[d] = t
        out[d].append((r, min(60.0, max(5.0, gap))))
    return out


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

    bus = by_day_with_interval(load("trip_updates_summary.csv", "bus"))
    lessfreq = by_day_with_interval(load("trip_updates_summary.csv", "bus_less_frequent"))

    out = []
    for d in sorted(days):
        b = days[d]
        otp = {}
        if any(num(r.get("delays_observed")) for r, _ in bus.get(d, [])):
            otp = {
                "delays_observed": int(sum(num(r.get("delays_observed")) or 0 for r, _ in bus[d])),
                "bus_ontime_pct": weighted_pct(bus[d], "pct_ontime"),
                "bus_early_pct": weighted_pct(bus[d], "pct_early"),
                "bus_late_pct": weighted_pct(bus[d], "pct_late"),
                "bus_within_5min_pct": weighted_pct(bus[d], "pct_within_5min"),
                "punctuality_pct": weighted_pct(lessfreq.get(d, []), "pct_ontime"),
                "punctuality_pct_am_peak": weighted_pct(lessfreq.get(d, []), "pct_ontime", (7, 9)),
                "punctuality_pct_pm_peak": weighted_pct(lessfreq.get(d, []), "pct_ontime", (16, 18)),
            }
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
            **otp,
        })

    (HIST / "transit_daily.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"transit history: {len(out)} day(s)")


if __name__ == "__main__":
    main()

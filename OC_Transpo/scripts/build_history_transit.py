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
                       the share within +/-5 min (otranspo.ca's definition);
                       distinct cancelled trips (cancellations_daily.csv) and
                       otranspo.ca's own figure for the day, when we have them.
  transit_hourly.json : last 28 days, weekdays and weekends apart: on-time by
                       hour of day, and cancelled trips by scheduled start hour.
  transit_routes.json : last 28 days per bus route (route_daily.csv): on-time,
                       late, within +/-5 min, mean delay, cancelled trips, and
                       otranspo.ca's +/-5 figure for the route on the same days.

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
# First full day of on-time measured at timepoints (poll_gtfsrt.py, 2026-10-16
# afternoon). The hourly and route profiles start here.
METHOD_START = "2026-10-17"
WINDOW_DAYS = 28


def read_csv(name):
    p = DATA / name
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load(name, group="all"):
    return [r for r in read_csv(name) if r.get("group") == group and not r.get("error")]


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


def share(part, whole, digits=1):
    return round(100 * part / whole, digits) if whole else None


def window(dates):
    """(start, end) of the last WINDOW_DAYS calendar days with data, from METHOD_START."""
    dates = sorted(d for d in dates if d >= METHOD_START)
    if not dates:
        return None
    end = datetime.date.fromisoformat(dates[-1])
    start = max(end - datetime.timedelta(days=WINDOW_DAYS - 1), datetime.date.fromisoformat(dates[0]))
    return start.isoformat(), end.isoformat()


def cancellations_by_day(rows):
    out = defaultdict(lambda: {"cancelled_trips": 0, "cancel_notices": 0, "cancel_withdrawn": 0,
                               "cancel_ran": 0, "cancel_partial": False})
    for r in rows:
        b = out[r["date"]]
        b["cancelled_trips"] += int(r["cancelled"])
        b["cancel_notices"] += int(r["notices"])
        b["cancel_withdrawn"] += int(r["withdrawn"])
        b["cancel_ran"] += int(r["ran"])
        b["cancel_partial"] |= r.get("partial") == "1"
    return out


def build_hourly(bus, lessfreq, cancel_rows):
    win = window(bus)
    if not win:
        return None
    out = {"window": {"start": win[0], "end": win[1]}}
    # A finished day with no cancellations writes no ledger rows, so count days
    # from the first ledger day on, minus the ones it only partly covered.
    ledger_start = min((r["date"] for r in cancel_rows), default="9999")
    ledger_end = max((r["date"] for r in cancel_rows), default="")
    partial = {r["date"] for r in cancel_rows if r.get("partial") == "1"}
    for kind, want in (("weekday", lambda d: weekday(d) < 5), ("weekend", lambda d: weekday(d) >= 5)):
        dates = [d for d in bus if win[0] <= d <= win[1] and want(d)]
        samples = [s for d in dates for s in bus[d]]
        lf = [s for d in dates for s in lessfreq.get(d, [])]
        cx_days = [d for d in dates if ledger_start <= d <= ledger_end and d not in partial]
        cx = [0] * 24
        for r in cancel_rows:
            if r["date"] in cx_days:
                cx[int(r["start_hour"])] += int(r["cancelled"])
        hours = []
        for h in range(24):
            hours.append({
                "hour": h,
                "delays_observed": int(sum(num(r.get("delays_observed")) or 0 for r, _ in samples
                                           if hour_of(r["timestamp_local"]) == h)),
                "bus_ontime_pct": weighted_pct(samples, "pct_ontime", (h, h + 1)),
                "bus_late_pct": weighted_pct(samples, "pct_late", (h, h + 1)),
                "bus_early_pct": weighted_pct(samples, "pct_early", (h, h + 1)),
                "bus_within_5min_pct": weighted_pct(samples, "pct_within_5min", (h, h + 1)),
                "punctuality_pct": weighted_pct(lf, "pct_ontime", (h, h + 1)),
                "cancelled_per_day": round(cx[h] / len(cx_days), 1) if cx_days else None,
            })
        out[kind] = {"days": len(dates), "cancel_days": len(cx_days), "hours": hours}
    return out


def build_routes(route_rows, cancel_rows, ot_route_rows):
    win = window({r["date"] for r in route_rows})
    if not win:
        return None
    inwin = lambda r: win[0] <= r["date"] <= win[1]  # noqa: E731
    acc = defaultdict(lambda: defaultdict(int))
    days = defaultdict(set)
    for r in filter(inwin, route_rows):
        a = acc[r["route"]]
        for f in ("observations", "bus_minutes", "early_min", "ontime_min", "late_min",
                  "within_5min_min", "delay_s_x_min"):
            a[f] += int(r[f])
        days[r["route"]].add(r["date"])
    for r in filter(inwin, cancel_rows):
        acc[r["route"]]["cancelled"] += int(r["cancelled"])
        acc[r["route"]]["cancel_notices"] += int(r["notices"])
    ot_dates = set()
    for r in filter(inwin, ot_route_rows):
        if r["route"] in acc and r.get("on_time_arrivals"):
            acc[r["route"]]["ot_obs"] += int(r["observations"])
            acc[r["route"]]["ot_on"] += int(r["on_time_arrivals"])
            ot_dates.add(r["date"])
    routes = []
    for route, a in acc.items():
        bm = a["bus_minutes"]
        routes.append({
            "route": route,
            "school": route.isdigit() and 600 <= int(route) <= 699,
            "days": len(days[route]),
            "observations": a["observations"],
            "bus_minutes": bm,
            "ontime_pct": share(a["ontime_min"], bm),
            "late_pct": share(a["late_min"], bm),
            "early_pct": share(a["early_min"], bm),
            "within_5min_pct": share(a["within_5min_min"], bm),
            "mean_delay_min": round(a["delay_s_x_min"] / bm / 60, 1) if bm else None,
            "cancelled": a["cancelled"],
            "cancel_notices": a["cancel_notices"],
            "otranspo_within_5min_pct": share(a["ot_on"], a["ot_obs"]),
            "otranspo_observations": a["ot_obs"],
        })
    routes.sort(key=lambda r: (r["late_pct"] is None, -(r["late_pct"] or 0)))
    return {"window": {"start": win[0], "end": win[1], "otranspo_days": len(ot_dates)}, "routes": routes}


def main():
    HIST.mkdir(parents=True, exist_ok=True)
    trips = load("trip_updates_summary.csv")
    vehicles = load("vehicle_positions_summary.csv")
    cancel_rows = read_csv("cancellations_daily.csv")
    cx_day = cancellations_by_day(cancel_rows)
    ot_day = {r["date"]: r for r in read_csv("otranspo_daily.csv") if r.get("on_time_pct")}

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
            **(cx_day[d] if d in cx_day else {}),
            **({"otranspo_within_5min_pct": num(ot_day[d]["on_time_pct"]),
                "otranspo_observations": int(ot_day[d]["observations"])} if d in ot_day else {}),
        })

    (HIST / "transit_daily.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    hourly = build_hourly(bus, lessfreq, cancel_rows)
    if hourly:
        (HIST / "transit_hourly.json").write_text(json.dumps(hourly, indent=1), encoding="utf-8")
    routes = build_routes(read_csv("route_daily.csv"), cancel_rows, read_csv("otranspo_route_daily.csv"))
    if routes:
        (HIST / "transit_routes.json").write_text(json.dumps(routes, indent=1), encoding="utf-8")
    print(f"transit history: {len(out)} day(s); hourly profile {'yes' if hourly else 'no'}; "
          f"{len(routes['routes']) if routes else 0} route(s)")


if __name__ == "__main__":
    main()

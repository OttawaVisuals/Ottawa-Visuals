#!/usr/bin/env python3
"""Poll OC Transpo GTFS-Realtime and append per-sample summaries to CSV logs.

OC Transpo publishes no historical service-reliability data; this builds our
own. Two endpoints on the Nextrip public API (free key, JSON via ?format=json):

  * TripUpdates      -> per-trip cancellations (ScheduleRelationship == 3) and,
    when present, schedule deviation. Summarised per sample into cancellation
    counts, delay stats and on-time buckets, split all / bus / otrain / unknown.
  * VehiclePositions -> GPS for every active vehicle. Summarised into active
    vehicle count, distinct routes, and speed stats per group.

FEED REALITY (checked live 2026-07-11): OC Transpo sets NO delay fields —
StopTimeUpdates carry absolute predicted arrival times (Arrival.Time) only,
so the delay/on-time columns will be empty unless the beta feed changes.
On-time performance is computed OFFLINE from the raw archive (predicted times
vs the static GTFS schedule) — which is why OCTRANSPO_RAW_DIR should be set on
the Pi. The live headline metrics are cancellations and active fleet size.

On-time buckets (when delays exist) follow OC Transpo's own punctuality
definition for less-frequent routes: early = more than 1 min early
(delay < -60 s), on-time = -60..+300 s, late = more than 5 min late (> 300 s).

Sampling cadence is decided *here*, not by the cron (cron fires every 5 min):
  - weekday peaks (06:00-09:30, 15:00-18:30 Ottawa time): every run (5 min)
  - overnight 01:00-05:00 (little/no service):            hourly
  - everything else:                                      every 15 min
Pass --force to bypass the gate.

Archives the raw JSON payloads (gzipped) when OCTRANSPO_RAW_DIR is set —
point it at a directory OUTSIDE the git repo (e.g. ~/gtfsrt_raw). Measured
2026-07-11: TripUpdates ~90 KB gz + VehiclePositions ~10 KB gz per sample
=> ~15 MB/day, ~5.5 GB/year at this cadence. Strongly recommended: the raw
TripUpdates are what makes offline on-time-performance computation possible.

Stdlib only. Requires env var OCTRANSPO_API_KEY (register at
https://nextrip-public-api.developer.azure-api.net/).
"""

import argparse
import csv
import gzip
import json
import os
import statistics
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # the OC_Transpo/ directory
DATA = ROOT / "rt_data"                 # tracked (OC_Transpo/data/ is gitignored)
TZ = ZoneInfo("America/Toronto")

TRIP_LOG = DATA / "trip_updates_summary.csv"
VP_LOG = DATA / "vehicle_positions_summary.csv"

API_BASE = "https://nextrip-public-api.azure-api.net/octranspo"
TRIP_URL = f"{API_BASE}/gtfs-rt-tp/beta/v1/TripUpdates?format=json"
VP_URL = f"{API_BASE}/gtfs-rt-vp/beta/v1/VehiclePositions?format=json"

# "unknown" = entity carries no route id (e.g. ~20% of vehicle positions —
# likely deadheading / out-of-service vehicles; a handful of trip updates).
GROUPS = ("all", "bus", "otrain", "unknown")
# O-Train lines are routes 1/2/4 today (3 reserved for the west extension).
OTRAIN_ROUTES = {"1", "2", "3", "4"}

ONTIME_EARLY_S = -60    # more than 1 min early counts as "early"
ONTIME_LATE_S = 300     # more than 5 min late counts as "late"

TRIP_FIELDS = [
    "timestamp_utc", "timestamp_local", "group",
    "trips_tracked", "trips_canceled", "delays_observed",
    "mean_delay_s", "median_delay_s", "p90_delay_s",
    "pct_early", "pct_ontime", "pct_late", "error",
]
VP_FIELDS = [
    "timestamp_utc", "timestamp_local", "group",
    "vehicles", "routes_active", "speeds_observed",
    "mean_speed_kmh", "pct_moving", "error",
]


def in_peak(now_local: datetime) -> bool:
    if now_local.weekday() >= 5:
        return False
    mins = now_local.hour * 60 + now_local.minute
    return (6 * 60 <= mins <= 9 * 60 + 30) or (15 * 60 <= mins <= 18 * 60 + 30)


def should_sample(now_local: datetime) -> bool:
    """Peak -> every 5-min run; overnight -> hourly; otherwise every 15 min.

    Cron fires at :00/:05/... but can lag a minute or two, so the 15-min and
    hourly gates accept a few minutes of slack rather than exact minutes.
    """
    if in_peak(now_local):
        return True
    mins = now_local.hour * 60 + now_local.minute
    if 1 * 60 <= mins < 5 * 60:
        return now_local.minute < 5
    return now_local.minute % 15 < 5


def g(obj, *names, default=None):
    """Case/style-insensitive dict lookup: Delay / delay / schedule_relationship
    / ScheduleRelationship etc. all resolve.

    The live feed is protobuf-net JSON: every proto field is rendered with its
    default value plus a companion "Has<Field>" flag ("Delay": 0 with
    "HasDelay": false means delay is UNSET, not zero). When the companion flag
    exists and is false, the field is treated as absent."""
    if not isinstance(obj, dict):
        return default
    norm = {k.replace("_", "").lower(): v for k, v in obj.items()}
    for n in names:
        nn = n.replace("_", "").lower()
        if nn in norm:
            has = norm.get("has" + nn)
            if has is False:
                continue  # rendered default, field not actually set
            v = norm[nn]
            if v is not None:
                return v
    return default


def fetch_json(url: str, key: str, retries: int = 2) -> dict:
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "Ocp-Apim-Subscription-Key": key,
                "User-Agent": "OttawaVisuals-transit/1.0",
            })
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - one bad call shouldn't kill the run
            last = exc
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
    raise last


def route_group(route_id) -> str:
    rid = str(route_id or "").split("-")[0].strip()
    if not rid:
        return "unknown"
    return "otrain" if rid in OTRAIN_ROUTES else "bus"


def is_canceled(sr) -> bool:
    # ScheduleRelationship: enum 3 == CANCELED, or a string depending on renderer.
    return str(sr).strip().upper() in {"3", "CANCELED", "CANCELLED"}


def trip_delay_s(tu):
    """Best available schedule deviation for one TripUpdate, seconds (+ = late).

    Prefers the first stop_time_update carrying an arrival (then departure)
    delay — that's the deviation at the vehicle's next stop. Falls back to the
    trip-level delay field. None when the feed gives no deviation.
    """
    stus = g(tu, "stopTimeUpdate", default=[]) or []
    if isinstance(stus, dict):
        stus = [stus]
    for stu in stus:
        for ev_name in ("arrival", "departure"):
            d = g(g(stu, ev_name), "delay")
            if d is not None:
                try:
                    return int(d)
                except (TypeError, ValueError):
                    pass
    d = g(tu, "delay")
    try:
        return int(d) if d is not None else None
    except (TypeError, ValueError):
        return None


def blank_row(fields, group, error=""):
    row = {f: "" for f in fields if f not in ("timestamp_utc", "timestamp_local")}
    row["group"] = group
    row["error"] = error
    return row


def summarize_trips(feed):
    entities = g(feed, "entity", default=[]) or []
    per_group = {grp: {"tracked": 0, "canceled": 0, "delays": []} for grp in GROUPS}
    for ent in entities:
        tu = g(ent, "tripUpdate")
        if not tu:
            continue
        trip = g(tu, "trip", default={})
        grp = route_group(g(trip, "routeId"))
        canceled = is_canceled(g(trip, "scheduleRelationship"))
        for target in ("all", grp):
            b = per_group[target]
            b["tracked"] += 1
            if canceled:
                b["canceled"] += 1
        if not canceled:
            d = trip_delay_s(tu)
            if d is not None:
                per_group["all"]["delays"].append(d)
                per_group[grp]["delays"].append(d)

    rows = []
    for grp in GROUPS:
        b = per_group[grp]
        row = blank_row(TRIP_FIELDS, grp)
        row.update(trips_tracked=b["tracked"], trips_canceled=b["canceled"],
                   delays_observed=len(b["delays"]))
        if b["delays"]:
            ds = sorted(b["delays"])
            n = len(ds)
            row["mean_delay_s"] = round(statistics.fmean(ds), 1)
            row["median_delay_s"] = round(statistics.median(ds), 1)
            row["p90_delay_s"] = ds[min(n - 1, int(0.9 * n))]
            row["pct_early"] = round(100 * sum(1 for d in ds if d < ONTIME_EARLY_S) / n, 1)
            row["pct_ontime"] = round(100 * sum(1 for d in ds if ONTIME_EARLY_S <= d <= ONTIME_LATE_S) / n, 1)
            row["pct_late"] = round(100 * sum(1 for d in ds if d > ONTIME_LATE_S) / n, 1)
        rows.append(row)
    return rows


def summarize_vehicles(feed):
    entities = g(feed, "entity", default=[]) or []
    per_group = {grp: {"vehicles": 0, "routes": set(), "speeds": []} for grp in GROUPS}
    for ent in entities:
        veh = g(ent, "vehicle")
        if not veh:
            continue
        trip = g(veh, "trip", default={})
        rid = g(trip, "routeId")
        grp = route_group(rid)
        speed = g(g(veh, "position"), "speed")  # m/s per GTFS-RT spec
        for target in ("all", grp):
            b = per_group[target]
            b["vehicles"] += 1
            if rid:
                b["routes"].add(str(rid))
            if isinstance(speed, (int, float)):
                b["speeds"].append(float(speed))

    rows = []
    for grp in GROUPS:
        b = per_group[grp]
        row = blank_row(VP_FIELDS, grp)
        row.update(vehicles=b["vehicles"], routes_active=len(b["routes"]),
                   speeds_observed=len(b["speeds"]))
        if b["speeds"]:
            row["mean_speed_kmh"] = round(statistics.fmean(b["speeds"]) * 3.6, 1)
            row["pct_moving"] = round(100 * sum(1 for s in b["speeds"] if s > 1.0) / len(b["speeds"]), 1)
        rows.append(row)
    return rows


def archive_raw(raw_dir: Path, name: str, payload: dict, now_utc: datetime):
    day_dir = raw_dir / now_utc.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{name}_{now_utc.strftime('%H%M%S')}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))


def append_rows(path: Path, fields, rows, stamps):
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow({**stamps, **r})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="ignore the cadence gate and sample now")
    ap.add_argument("--debug", action="store_true",
                    help="print the first entity of each feed (verify parsing on a new key)")
    args = ap.parse_args()

    key = os.environ.get("OCTRANSPO_API_KEY")
    if not key:
        print("ERROR: OCTRANSPO_API_KEY not set", file=sys.stderr)
        return 1

    now_utc = datetime.now(ZoneInfo("UTC"))
    now_local = now_utc.astimezone(TZ)
    if not args.force and not should_sample(now_local):
        print(f"skip: {now_local:%Y-%m-%d %H:%M %Z} gated off")
        return 0

    stamps = {
        "timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp_local": now_local.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    raw_dir = os.environ.get("OCTRANSPO_RAW_DIR")

    trip_rows, vp_rows = None, None
    errors = []
    try:
        feed = fetch_json(TRIP_URL, key)
        if args.debug:
            ents = g(feed, "entity", default=[]) or []
            print("TripUpdates first entity:", json.dumps(ents[0], indent=2)[:2000] if ents else "(empty)")
        if raw_dir:
            archive_raw(Path(raw_dir), "tripupdates", feed, now_utc)
        trip_rows = summarize_trips(feed)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"TripUpdates: {exc}")
        trip_rows = [blank_row(TRIP_FIELDS, "all", str(exc)[:200])]

    try:
        feed = fetch_json(VP_URL, key)
        if args.debug:
            ents = g(feed, "entity", default=[]) or []
            print("VehiclePositions first entity:", json.dumps(ents[0], indent=2)[:2000] if ents else "(empty)")
        if raw_dir:
            archive_raw(Path(raw_dir), "vehiclepositions", feed, now_utc)
        vp_rows = summarize_vehicles(feed)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"VehiclePositions: {exc}")
        vp_rows = [blank_row(VP_FIELDS, "all", str(exc)[:200])]

    append_rows(TRIP_LOG, TRIP_FIELDS, trip_rows, stamps)
    append_rows(VP_LOG, VP_FIELDS, vp_rows, stamps)

    all_row_t = next((r for r in trip_rows if r["group"] == "all"), trip_rows[0])
    all_row_v = next((r for r in vp_rows if r["group"] == "all"), vp_rows[0])
    label = "PEAK" if in_peak(now_local) else "off-peak"
    print(f"{stamps['timestamp_local']} [{label}] "
          f"trips={all_row_t.get('trips_tracked', '?')} "
          f"canceled={all_row_t.get('trips_canceled', '?')} "
          f"ontime%={all_row_t.get('pct_ontime', '?')} "
          f"vehicles={all_row_v.get('vehicles', '?')}"
          + (f" ERRORS: {'; '.join(errors)}" if errors else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

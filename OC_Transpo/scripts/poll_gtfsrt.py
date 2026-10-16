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
StopTimeUpdates carry absolute predicted arrival times (Arrival.Time) only.
So delays are computed HERE against the static timetable: when
OCTRANSPO_SCHEDULE_DB points at the index built by build_schedule_index.py,
each running trip's delay = predicted departure from its next TIMEPOINT minus
the scheduled time there. Timepoints are the "major stops" OC Transpo measures
punctuality at; buses wait there if early, so measuring at every stop instead
reads both earlier and later than OC Transpo (checked live 2026-10-16: ~60% vs
their ~70% on time). The every-stop figure is still printed in the run log.
Trips that haven't left their first stop yet (their "prediction" is usually
just the schedule) or that don't match the timetable are left out of the
delay stats, and the run prints how many matched. Without the index the delay/on-time columns stay empty.

Extra trip groups split buses the way OC Transpo reports reliability:
"bus_frequent" (scheduled every 15 min or better: OC Transpo measures these
by regularity) and "bus_less_frequent" (the rest: measured by punctuality,
which is what pct_ontime approximates). It's a close proxy, not their exact
KPI: we sample every running bus at the moment of polling and use OC
Transpo's own near-term prediction for the next timepoint.

On-time buckets (when delays exist) follow OC Transpo's own punctuality
definition for less-frequent routes: early = more than 1 min early
(delay < -60 s), on-time = -60..+300 s, late = more than 5 min late (> 300 s).

Sampling cadence is decided *here*, not by the cron (cron fires every 5 min):
  - weekday peaks (06:00-09:30, 15:00-18:30 Ottawa time): every run (5 min)
  - overnight 01:00-05:00 (little/no service):            hourly
  - everything else:                                      every 15 min
Pass --force to bypass the gate.

Optionally archives the raw JSON payloads (gzipped) when OCTRANSPO_RAW_DIR
is set — ~15 MB/day, so OUTSIDE the git repo. Not needed for on-time any more
(computed live, see above); collect.yml doesn't set it.

Stdlib only. Requires env var OCTRANSPO_API_KEY (register at
https://nextrip-public-api.developer.azure-api.net/).
"""

import argparse
import csv
import gzip
import json
import os
import sqlite3
import statistics
import sys
import time
import urllib.request
from array import array
from datetime import datetime, timedelta
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
# Trip summaries add OC Transpo's frequency split for buses matched to the timetable.
TRIP_GROUPS = GROUPS + ("bus_frequent", "bus_less_frequent")
FREQUENT_MAX_HEADWAY_S = 15 * 60   # "every 15 minutes or more frequently"
NEXT_STOP_MAX_AHEAD_S = 900        # next timepoint must be within 15 min (prediction gets vaguer further out)
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


class Schedule:
    """Read-only view of the timetable index (build_schedule_index.py)."""

    def __init__(self, path):
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.version = dict(self.db.execute("SELECT key, value FROM meta")).get("feed_version", "?")

    def trip(self, trip_id):
        row = self.db.execute("SELECT route_id, headway_s, seqs, secs, tps FROM trips WHERE trip_id = ?",
                              (str(trip_id),)).fetchone()
        if not row:
            return None
        seqs, secs, tps = array("i"), array("i"), array("b")
        seqs.frombytes(row[2])
        secs.frombytes(row[3])
        tps.frombytes(row[4] or b"")
        return {"route_id": row[0], "headway_s": row[1], "seqs": seqs, "secs": secs,
                "tps": tps if len(tps) == len(seqs) else array("b", [1] * len(seqs))}


def load_schedule():
    path = os.environ.get("OCTRANSPO_SCHEDULE_DB")
    if not path or not Path(path).exists():
        return None
    try:
        return Schedule(path)
    except sqlite3.Error as exc:
        print(f"warning: schedule index unreadable ({exc}); delays left empty", file=sys.stderr)
        return None


def service_day_start(day) -> float:
    """GTFS times count from "noon minus 12h" of the service day (right across DST)."""
    return (datetime(day.year, day.month, day.day, 12, tzinfo=TZ) - timedelta(hours=12)).timestamp()


def schedule_delay_s(tu, sched, now_ts, timepoints=True):
    """(delay seconds, status) for one running trip: predicted departure from
    its next timepoint (or next stop, timepoints=False) minus scheduled.
    status is "ok" or why it was skipped."""
    trip = g(tu, "trip", default={})
    rec = sched.trip(g(trip, "tripId"))
    if not rec:
        return None, "no_match"
    stus = g(tu, "stopTimeUpdate", default=[]) or []
    if isinstance(stus, dict):
        stus = [stus]
    started = None
    for stu in stus:
        t = g(g(stu, "departure"), "time") or g(g(stu, "arrival"), "time")
        try:
            t = int(t)
        except (TypeError, ValueError):
            continue
        if t < now_ts - 120:
            continue  # already passed
        seq = g(stu, "stopSequence")
        try:
            i = rec["seqs"].index(int(seq))
        except (TypeError, ValueError):
            return None, "no_stop"
        # Next stop is the first stop: the bus hasn't left yet, and its
        # prediction is usually just the schedule, so it would inflate on-time.
        # Distance alone isn't used, because that would drop very late buses.
        if started is None:
            started = i > 0
            if not started:
                return None, "not_started"
        if timepoints and not rec["tps"][i]:
            continue  # look on to the next timepoint
        start_date = str(g(trip, "startDate") or "")
        if len(start_date) == 8 and start_date.isdigit():
            days = [datetime.strptime(start_date, "%Y%m%d").date()]
        else:  # infer: the service day that puts the scheduled time nearest the prediction
            today = datetime.fromtimestamp(now_ts, TZ).date()
            days = [today - timedelta(days=1), today, today + timedelta(days=1)]
        delay = min((t - (service_day_start(d) + rec["secs"][i]) for d in days), key=abs)
        if abs(delay) > 3 * 3600:
            return None, "implausible"
        # How far off the timepoint is: by whichever clock is sooner, so a late
        # bus (scheduled time near) and an early one (predicted time near) are
        # both kept. A cap on the prediction alone would drop the late ones.
        if min(t, t - delay) > now_ts + NEXT_STOP_MAX_AHEAD_S:
            return None, "far"
        return int(delay), "ok"
    return None, "no_timepoint" if started else "no_prediction"


def match_counts(stats):
    return {k: v for k, v in stats.items() if not k.startswith("_")}


def every_stop_pct(ds):
    if not ds:
        return "?"
    return round(100 * sum(1 for d in ds if ONTIME_EARLY_S <= d <= ONTIME_LATE_S) / len(ds), 1)


def frequency_group(rec):
    h = rec["headway_s"] if rec else None
    return "bus_frequent" if h is not None and h <= FREQUENT_MAX_HEADWAY_S else "bus_less_frequent"


def blank_row(fields, group, error=""):
    row = {f: "" for f in fields if f not in ("timestamp_utc", "timestamp_local")}
    row["group"] = group
    row["error"] = error
    return row


def summarize_trips(feed, sched=None, stats=None):
    entities = g(feed, "entity", default=[]) or []
    per_group = {grp: {"tracked": 0, "canceled": 0, "delays": []} for grp in TRIP_GROUPS}
    now_ts = g(g(feed, "header"), "timestamp")
    try:
        now_ts = int(now_ts)
    except (TypeError, ValueError):
        now_ts = int(time.time())
    for ent in entities:
        tu = g(ent, "tripUpdate")
        if not tu:
            continue
        trip = g(tu, "trip", default={})
        grp = route_group(g(trip, "routeId"))
        canceled = is_canceled(g(trip, "scheduleRelationship"))
        targets = ["all", grp]
        if grp == "bus" and sched:
            rec = sched.trip(g(trip, "tripId"))
            if rec:
                targets.append(frequency_group(rec))
        for target in targets:
            b = per_group[target]
            b["tracked"] += 1
            if canceled:
                b["canceled"] += 1
        if not canceled:
            d = trip_delay_s(tu)
            if d is None and sched:
                d, status = schedule_delay_s(tu, sched, now_ts)
                if stats is not None:
                    stats[status] = stats.get(status, 0) + 1
                    if grp == "bus":  # every-stop figure, log only (for comparison)
                        d_any, _ = schedule_delay_s(tu, sched, now_ts, timepoints=False)
                        if d_any is not None:
                            stats.setdefault("_every_stop", []).append(d_any)
            if d is not None:
                for target in targets:
                    per_group[target]["delays"].append(d)

    rows = []
    for grp in TRIP_GROUPS:
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
    sched = load_schedule()
    otp_stats = {}

    trip_rows, vp_rows = None, None
    errors = []
    try:
        feed = fetch_json(TRIP_URL, key)
        if args.debug:
            ents = g(feed, "entity", default=[]) or []
            print("TripUpdates first entity:", json.dumps(ents[0], indent=2)[:2000] if ents else "(empty)")
        if raw_dir:
            archive_raw(Path(raw_dir), "tripupdates", feed, now_utc)
        trip_rows = summarize_trips(feed, sched, otp_stats)
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
    lf_row = next((r for r in trip_rows if r["group"] == "bus_less_frequent"), {})
    all_row_v = next((r for r in vp_rows if r["group"] == "all"), vp_rows[0])
    label = "PEAK" if in_peak(now_local) else "off-peak"
    print(f"{stamps['timestamp_local']} [{label}] "
          f"trips={all_row_t.get('trips_tracked', '?')} "
          f"canceled={all_row_t.get('trips_canceled', '?')} "
          f"ontime%={all_row_t.get('pct_ontime', '?')} "
          f"punctuality(less-frequent)%={lf_row.get('pct_ontime', '?')} "
          f"vehicles={all_row_v.get('vehicles', '?')} "
          + (f"schedule={sched.version} delay-match={match_counts(otp_stats)} "
             f"every-stop-ontime%={every_stop_pct(otp_stats.get('_every_stop'))}" if sched else "schedule=none")
          + (f" ERRORS: {'; '.join(errors)}" if errors else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

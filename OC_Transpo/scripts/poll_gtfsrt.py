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
pct_within_5min is the same delays scored with a symmetric +/-5 min window,
the definition otranspo.ca publishes monthly, so the two can be compared.

Two small day-level files are kept alongside (both need the timetable index):
  * route_daily.csv         -> per local date and bus route, the same on-time
    buckets as bus-minutes (each observed bus counts for the minutes its sample
    stands for), so routes can be ranked without storing individual buses.
  * cancellations_daily.csv -> distinct cancelled trips per service date, route
    and scheduled start hour. A trip counts once however many polls showed the
    notice, and not at all if the notice was withdrawn or a vehicle later ran
    it (otranspo.ca's rule). Open service dates live in cancel_state.json and
    are written out once the day's last trips are done (05:00 next morning).

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
ROUTE_LOG = DATA / "route_daily.csv"
REGULARITY_LOG = DATA / "regularity_daily.csv"
CANCEL_LOG = DATA / "cancellations_daily.csv"
CANCEL_STATE = DATA / "cancel_state.json"

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
# Normally every running trip is in the timetable. Above this share missing,
# the index is out of step with the feed (e.g. a new timetable published the
# evening before it starts) and the few trips that do match aren't a fair
# sample, so the sample's on-time figures are left blank.
MAX_NO_MATCH = 0.10
# O-Train lines are routes 1/2/4 today (3 reserved for the west extension).
OTRAIN_ROUTES = {"1", "2", "3", "4"}

ONTIME_EARLY_S = -60    # more than 1 min early counts as "early"
ONTIME_LATE_S = 300     # more than 5 min late counts as "late"
WITHIN_S = 300          # pct_within_5min: |delay| <= 5 min (otranspo.ca's window)

# Regularity proxy for frequent routes (our own, not OC Transpo's definition): two consecutive
# trips predicted at the same timepoint stop are "bunched" if the predicted gap is under
# BUNCHED_RATIO of the scheduled gap, "gapped" if over GAPPED_RATIO of it.
BUNCHED_RATIO = 0.5
GAPPED_RATIO = 1.5
# A "gapped" pair needs a gap over 1.5x the headway (22 min on a 15-min route), so the
# prediction window for headways is longer than NEXT_STOP_MAX_AHEAD_S.
HEADWAY_LOOKAHEAD_S = 1800

TRIP_FIELDS = [
    "timestamp_utc", "timestamp_local", "group",
    "trips_tracked", "trips_canceled", "delays_observed",
    "mean_delay_s", "median_delay_s", "p90_delay_s",
    "pct_early", "pct_ontime", "pct_late", "pct_within_5min",
    # hold-adjusted: an early bus at a non-final timepoint counts as on time (it will hold).
    # headway_*: bus_frequent only, see BUNCHED_RATIO / GAPPED_RATIO.
    "pct_ontime_hold_adj", "headway_pairs", "pct_headway_bunched", "pct_headway_gapped", "error",
]
VP_FIELDS = [
    "timestamp_utc", "timestamp_local", "group",
    "vehicles", "routes_active", "speeds_observed",
    "mean_speed_kmh", "pct_moving", "error",
]
# *_min columns are bus-minutes; percentages are x_min / bus_minutes.
ROUTE_FIELDS = [
    "date", "route", "samples", "observations", "bus_minutes",
    "early_min", "ontime_min", "late_min", "within_5min_min", "delay_s_x_min",
]
# Per date and frequent route: headway pairs seen across the day's samples (the same pair
# shows in several consecutive samples, so these are observations, not unique pairs).
REGULARITY_FIELDS = ["date", "route", "samples", "pairs", "bunched", "gapped"]
CANCEL_FIELDS = [
    "date", "route", "start_hour", "notices", "withdrawn", "ran", "cancelled", "partial",
]
CANCEL_DONE_HOUR = 5    # a service date's trips are all over by 05:00 the next morning


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


def sample_minutes(now_local: datetime) -> int:
    """Minutes one sample stands for under the gate above."""
    if in_peak(now_local):
        return 5
    return 60 if 1 <= now_local.hour < 5 else 15


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


def service_date(rec, start_date, now_ts):
    """A trip's service date: the feed's startDate, else the day that puts its
    scheduled start nearest now (notices and vehicles are near-term)."""
    s = str(start_date or "")
    if len(s) == 8 and s.isdigit():
        return datetime.strptime(s, "%Y%m%d").date()
    today = datetime.fromtimestamp(now_ts, TZ).date()
    return min((today - timedelta(days=1), today, today + timedelta(days=1)),
               key=lambda d: abs(service_day_start(d) + rec["secs"][0] - now_ts))


def route_label(route_id) -> str:
    return str(route_id or "").split("-")[0].strip()


def schedule_delay_s(tu, sched, now_ts, timepoints=True, info=None):
    """(delay seconds, status) for one running trip: predicted departure from
    its next timepoint (or next stop, timepoints=False) minus scheduled.
    status is "ok" or why it was skipped. If info is a dict, an "ok" result also
    sets info["final"]: whether that stop is the trip's last (no holding there)."""
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
        if info is not None:
            info["final"] = i == len(rec["seqs"]) - 1
        return int(delay), "ok"
    return None, "no_timepoint" if started else "no_prediction"


def stop_predictions(tu, sched, now_ts):
    """[(stop_id, predicted_ts, scheduled_ts, scheduled_headway_s)] for a running frequent
    trip's upcoming timepoints within HEADWAY_LOOKAHEAD_S. Empty if the trip is unmatched
    or hasn't left its first stop (its predictions are then just the schedule)."""
    trip = g(tu, "trip", default={})
    rec = sched.trip(g(trip, "tripId"))
    if not rec or frequency_group(rec) != "bus_frequent":
        return []
    stus = g(tu, "stopTimeUpdate", default=[]) or []
    if isinstance(stus, dict):
        stus = [stus]
    start_date = str(g(trip, "startDate") or "")
    day = (datetime.strptime(start_date, "%Y%m%d").date()
           if len(start_date) == 8 and start_date.isdigit() else None)
    out, started = [], None
    for stu in stus:
        t = g(g(stu, "departure"), "time") or g(g(stu, "arrival"), "time")
        try:
            t = int(t)
            i = rec["seqs"].index(int(g(stu, "stopSequence")))
        except (TypeError, ValueError):
            continue
        if t < now_ts - 120:
            continue
        if started is None:
            started = i > 0
            if not started:
                return []
        if t > now_ts + HEADWAY_LOOKAHEAD_S:
            break
        if not rec["tps"][i] or not g(stu, "stopId"):
            continue
        d = day or datetime.fromtimestamp(now_ts, TZ).date()
        out.append((str(g(stu, "stopId")), t, service_day_start(d) + rec["secs"][i], rec["headway_s"]))
    return out


def headway_pairs(by_stop):
    """by_stop {(route, stop_id): [(pred, sched, headway)...]} -> {route: [pairs, bunched, gapped]}.
    Consecutive scheduled trips only: if a trip between two is missing from the sample the
    scheduled gap exceeds 1.6x the headway and the pair is skipped, not read as a gap."""
    out = {}
    for (route, _stop), items in by_stop.items():
        items.sort(key=lambda x: x[1])
        for (p1, s1, _), (p2, s2, h) in zip(items, items[1:]):
            gs = s2 - s1
            if gs <= 0 or not h or gs > 1.6 * h:
                continue
            gp = p2 - p1
            r = out.setdefault(route, [0, 0, 0])
            r[0] += 1
            r[1] += gp < BUNCHED_RATIO * gs
            r[2] += gp > GAPPED_RATIO * gs
    return out


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
    per_group = {grp: {"tracked": 0, "canceled": 0, "delays": [], "holds": []} for grp in TRIP_GROUPS}
    by_stop = {}
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
        if stats is not None:  # trip ids for the cancellation ledger
            stats.setdefault("_canceled" if canceled else "_live", []).append(
                (g(trip, "tripId"), g(trip, "startDate")))
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
            info = {}
            if d is None and sched:
                d, status = schedule_delay_s(tu, sched, now_ts, info=info)
                if stats is not None:
                    stats[status] = stats.get(status, 0) + 1
                    if grp == "bus":  # every-stop figure, log only (for comparison)
                        d_any, _ = schedule_delay_s(tu, sched, now_ts, timepoints=False)
                        if d_any is not None:
                            stats.setdefault("_every_stop", []).append(d_any)
            if d is not None:
                for target in targets:
                    per_group[target]["delays"].append(d)
                    if "final" in info:
                        per_group[target]["holds"].append((d, info["final"]))
                if grp == "bus" and stats is not None:
                    stats.setdefault("_routes", {}).setdefault(
                        route_label(g(trip, "routeId")), []).append(d)
            if sched and grp == "bus":
                label = route_label(g(trip, "routeId"))
                for stop_id, pred, sch, headway in stop_predictions(tu, sched, now_ts):
                    by_stop.setdefault((label, stop_id), []).append((pred, sch, headway))

    pairs = headway_pairs(by_stop)
    if stats is not None:
        stats["_headway"] = pairs

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
            row["pct_within_5min"] = round(100 * sum(1 for d in ds if abs(d) <= WITHIN_S) / n, 1)
        if b["holds"]:
            ok = sum(1 for d, final in b["holds"]
                     if ONTIME_EARLY_S <= d <= ONTIME_LATE_S or (d < ONTIME_EARLY_S and not final))
            row["pct_ontime_hold_adj"] = round(100 * ok / len(b["holds"]), 1)
        if grp == "bus_frequent" and sched:
            tot = [sum(v[i] for v in pairs.values()) for i in range(3)]
            row["headway_pairs"] = tot[0]
            if tot[0]:
                row["pct_headway_bunched"] = round(100 * tot[1] / tot[0], 1)
                row["pct_headway_gapped"] = round(100 * tot[2] / tot[0], 1)
        rows.append(row)
    return rows


def summarize_vehicles(feed, running=None):
    """running, if given, collects (tripId, startDate) of every vehicle on a trip."""
    entities = g(feed, "entity", default=[]) or []
    per_group = {grp: {"vehicles": 0, "routes": set(), "speeds": []} for grp in GROUPS}
    for ent in entities:
        veh = g(ent, "vehicle")
        if not veh:
            continue
        trip = g(veh, "trip", default={})
        rid = g(trip, "routeId")
        if running is not None and g(trip, "tripId"):
            running.append((g(trip, "tripId"), g(trip, "startDate")))
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


def migrate_header(path: Path, fields):
    """When FIELDS gains a column, rewrite the log once with the new header so
    every row has the same columns (old rows get the new column blank)."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames == fields:
            return
        old = list(reader)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(old)
    tmp.replace(path)
    print(f"migrated {path.name} header to {len(fields)} columns ({len(old)} rows)")


def append_rows(path: Path, fields, rows, stamps):
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    if not new_file:
        migrate_header(path, fields)
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow({**stamps, **r})


def route_sort_key(key):
    date, route = key
    return (date, int(route) if route.isdigit() else 10 ** 6, route)


def update_route_daily(path: Path, date_str, route_delays, minutes):
    """Add one sample's per-route delays to the day's running bus-minute totals."""
    rows = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows[(r["date"], r["route"])] = r
    for route, ds in route_delays.items():
        r = rows.setdefault((date_str, route), {f: 0 for f in ROUTE_FIELDS} | {"date": date_str, "route": route})
        add = {
            "samples": 1,
            "observations": len(ds),
            "bus_minutes": len(ds) * minutes,
            "early_min": minutes * sum(1 for d in ds if d < ONTIME_EARLY_S),
            "ontime_min": minutes * sum(1 for d in ds if ONTIME_EARLY_S <= d <= ONTIME_LATE_S),
            "late_min": minutes * sum(1 for d in ds if d > ONTIME_LATE_S),
            "within_5min_min": minutes * sum(1 for d in ds if abs(d) <= WITHIN_S),
            "delay_s_x_min": minutes * sum(ds),
        }
        for f, v in add.items():
            r[f] = int(r[f]) + v
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=ROUTE_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows[k] for k in sorted(rows, key=route_sort_key))
    tmp.replace(path)


def update_regularity_daily(path: Path, date_str, route_pairs):
    """Add one sample's per-route headway counts to the day's running totals."""
    rows = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows[(r["date"], r["route"])] = r
    for route, (n, bunched, gapped) in route_pairs.items():
        r = rows.setdefault((date_str, route), {f: 0 for f in REGULARITY_FIELDS}
                            | {"date": date_str, "route": route})
        for f, v in (("samples", 1), ("pairs", n), ("bunched", bunched), ("gapped", gapped)):
            r[f] = int(r[f]) + v
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=REGULARITY_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows[k] for k in sorted(rows, key=route_sort_key))
    tmp.replace(path)


def update_cancellations(sched, canceled, live, running, now_ts,
                         state_path=CANCEL_STATE, log_path=CANCEL_LOG):
    """Keep one ledger entry per (service date, trip) that ever had a
    cancellation notice; write finished service dates to the daily log.
    Returns (open entries, rows written)."""
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {"since": now_ts, "trips": {}}
    trips = state["trips"]

    def entry_key(tid, start_date):
        rec = sched.trip(tid) if tid else None
        return (f"{service_date(rec, start_date, now_ts):%Y-%m-%d}|{tid}", rec) if rec else (None, None)

    for tid, sd in canceled:
        k, rec = entry_key(tid, sd)
        if not k:
            continue  # not in the timetable: can't date it or say what was missed
        if k in trips:
            trips[k]["withdrawn"] = 0  # notice is (back) in force
        else:
            trips[k] = {"route": route_label(rec["route_id"]), "hour": rec["secs"][0] // 3600 % 24,
                        "withdrawn": 0, "ran": 0}
    pending = {k.split("|", 1)[1] for k in trips}
    for flag, seen in (("withdrawn", live), ("ran", running)):
        for tid, sd in seen:
            if tid in pending:
                k, _ = entry_key(tid, sd)
                if k in trips:
                    trips[k][flag] = 1

    cutoff = f"{datetime.fromtimestamp(now_ts, TZ) - timedelta(hours=CANCEL_DONE_HOUR):%Y-%m-%d}"
    logged = set()
    if log_path.exists():
        with log_path.open(newline="", encoding="utf-8") as fh:
            logged = {r["date"] for r in csv.DictReader(fh)}
    done = {}
    for k in [k for k in trips if k[:10] < cutoff]:
        e = trips.pop(k)
        date = k[:10]
        if date in logged:
            continue
        b = done.setdefault((date, e["route"], e["hour"]), {"notices": 0, "withdrawn": 0, "ran": 0, "cancelled": 0})
        b["notices"] += 1
        b["withdrawn"] += e["withdrawn"]
        b["ran"] += e["ran"] and not e["withdrawn"]
        b["cancelled"] += not (e["withdrawn"] or e["ran"])
    rows = []
    for (date, route, hour), b in sorted(done.items(), key=lambda kv: (*route_sort_key(kv[0][:2]), kv[0][2])):
        d = datetime.strptime(date, "%Y-%m-%d").date()
        # Ledger started after that day's first trips: early notices were missed.
        partial = int(state["since"] > service_day_start(d) + 4 * 3600)
        rows.append({"date": date, "route": route, "start_hour": hour, **b, "partial": partial})
    if rows:
        append_rows(log_path, CANCEL_FIELDS, rows, {})
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return len(trips), len(rows)


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
    running, vp_ok = [], False
    errors = []
    try:
        feed = fetch_json(TRIP_URL, key)
        if args.debug:
            ents = g(feed, "entity", default=[]) or []
            print("TripUpdates first entity:", json.dumps(ents[0], indent=2)[:2000] if ents else "(empty)")
        if raw_dir:
            archive_raw(Path(raw_dir), "tripupdates", feed, now_utc)
        trip_rows = summarize_trips(feed, sched, otp_stats)
        checked = sum(match_counts(otp_stats).values())
        if checked and otp_stats.get("no_match", 0) > MAX_NO_MATCH * checked:
            errors.append(f"timetable mismatch: {otp_stats['no_match']} of {checked} trips not in "
                          f"{sched.version}; on-time left blank")
            for r in trip_rows:
                r.update({f: "" for f in TRIP_FIELDS[TRIP_FIELDS.index("mean_delay_s"):-1]}, delays_observed=0)
            otp_stats.pop("_routes", None)
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
        vp_rows = summarize_vehicles(feed, running)
        vp_ok = True
    except Exception as exc:  # noqa: BLE001
        errors.append(f"VehiclePositions: {exc}")
        vp_rows = [blank_row(VP_FIELDS, "all", str(exc)[:200])]

    append_rows(TRIP_LOG, TRIP_FIELDS, trip_rows, stamps)
    append_rows(VP_LOG, VP_FIELDS, vp_rows, stamps)

    extra = ""
    if sched and "TripUpdates" not in " ".join(errors):
        routes = otp_stats.get("_routes", {})
        update_route_daily(ROUTE_LOG, f"{now_local:%Y-%m-%d}", routes, sample_minutes(now_local))
        extra = f" routes={len(routes)}"
        update_regularity_daily(REGULARITY_LOG, f"{now_local:%Y-%m-%d}", otp_stats.get("_headway", {}))
        if vp_ok:  # without vehicles a cancelled-but-ran trip can't be told apart
            open_, written = update_cancellations(sched, otp_stats.get("_canceled", []),
                                                  otp_stats.get("_live", []), running,
                                                  int(now_utc.timestamp()))
            extra += f" cancel-ledger={open_} open, {written} rows written"

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
             f"every-stop-ontime%={every_stop_pct(otp_stats.get('_every_stop'))} "
             f"hold-adjusted-punctuality(less-frequent)%={lf_row.get('pct_ontime_hold_adj', '?')} "
             f"headway-pairs={next((r.get('headway_pairs') for r in trip_rows if r['group'] == 'bus_frequent'), '?')}" if sched else "schedule=none")
          + extra
          + (f" ERRORS: {'; '.join(errors)}" if errors else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

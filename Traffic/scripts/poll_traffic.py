#!/usr/bin/env python3
"""Poll TomTom for Ottawa traffic and append one reading per target to CSV logs.

Three datasets, three free TomTom APIs (20,000 req/month each on the free tier):

  * corridors -> Routing API (calculateRoute, traffic=true): door-to-door
    commute time for each origin<->downtown pair, both directions. This is the
    number that supports the "RTO made commutes worse" narrative.
  * segments  -> Traffic Flow Segment Data API: current vs free-flow speed at a
    point on a major road. 15 points spread across the city; their average is a
    city-wide congestion proxy for a TomTom-live-panel-style card.
  * incidents -> Traffic Incidents API: one bounding-box scan of Ottawa per
    sample, summarised to jam count + total jam length + delay (the "traffic
    jams" tile on tomtom.com/traffic-index).

Sampling cadence is decided *here*, not by the cron, so it survives DST:
the workflow fires every 15 min and this script decides whether the tick is a
sample. Weekday rush hours (AM 06:30-09:30, PM 15:30-18:30 local Ottawa time)
are sampled every run (~15 min); all other times only the top-of-hour run is
kept (hourly). Pass --force to bypass the gate (useful for manual test runs).

Stdlib only (urllib + zoneinfo), so the workflow needs no pip install.
Requires env var TOMTOM_API_KEY.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # the Traffic/ directory
DATA = ROOT / "data"
CONFIG = ROOT / "corridors.json"
TZ = ZoneInfo("America/Toronto")        # Ottawa shares this zone (handles DST)

CORRIDOR_LOG = DATA / "corridor_travel_times.csv"
SEGMENT_LOG = DATA / "segment_speeds.csv"
INCIDENT_LOG = DATA / "incidents_summary.csv"

# TomTom iconCategory 6 == "Jam". See Traffic Incidents API docs.
JAM_ICON_CATEGORY = 6

CORRIDOR_FIELDS = [
    "timestamp_utc", "timestamp_local", "corridor_id", "direction",
    "travel_time_s", "traffic_delay_s", "distance_m", "error",
]
SEGMENT_FIELDS = [
    "timestamp_utc", "timestamp_local", "segment_id",
    "current_speed_kmh", "free_flow_speed_kmh",
    "current_travel_time_s", "free_flow_travel_time_s",
    "confidence", "road_closure", "error",
]
INCIDENT_FIELDS = [
    "timestamp_utc", "timestamp_local",
    "incident_count",           # every incident in the bbox (jams, closures, works...)
    "jam_count", "jam_length_m", "jam_delay_s",   # iconCategory == Jam only
    "total_length_m", "total_delay_s",            # across all incidents
    "error",
]

API_BASE = "https://api.tomtom.com"


def in_peak(now_local: datetime) -> bool:
    """Weekday AM/PM Ottawa rush windows."""
    if now_local.weekday() >= 5:  # Sat/Sun
        return False
    mins = now_local.hour * 60 + now_local.minute
    am = 6 * 60 + 30, 9 * 60 + 30      # 06:30-09:30
    pm = 15 * 60 + 30, 18 * 60 + 30    # 15:30-18:30
    return (am[0] <= mins <= am[1]) or (pm[0] <= mins <= pm[1])


def should_sample(now_local: datetime) -> bool:
    """Peak -> every run. Off-peak -> only the top-of-hour run.

    The workflow fires at :00/:15/:30/:45 but GitHub cron can lag several
    minutes, so 'top of hour' is a generous minute < 15 window rather than
    exactly :00. Worst case a lagged run double-logs one off-peak hour, which
    is harmless for trend analysis.
    """
    return in_peak(now_local) or now_local.minute < 15


def fetch_json(url: str, retries: int = 2) -> dict:
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OttawaVisuals-traffic/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - log and move on, one bad call shouldn't kill the run
            last = exc
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise last


def poll_corridor(key, cid, origin, dest):
    """Return (to_downtown_row, from_downtown_row). travel_time_s null on error."""
    (olat, olon), (dlat, dlon) = origin, dest
    rows = []
    for direction, a, b in (("to_downtown", (olat, olon), (dlat, dlon)),
                            ("from_downtown", (dlat, dlon), (olat, olon))):
        loc = f"{a[0]},{a[1]}:{b[0]},{b[1]}"
        qs = urllib.parse.urlencode({
            "key": key, "traffic": "true", "travelMode": "car", "routeType": "fastest",
        })
        url = f"{API_BASE}/routing/1/calculateRoute/{loc}/json?{qs}"
        row = {"corridor_id": cid, "direction": direction,
               "travel_time_s": "", "traffic_delay_s": "", "distance_m": "", "error": ""}
        try:
            data = fetch_json(url)
            s = data["routes"][0]["summary"]
            row["travel_time_s"] = s.get("travelTimeInSeconds", "")
            row["traffic_delay_s"] = s.get("trafficDelayInSeconds", "")
            row["distance_m"] = s.get("lengthInMeters", "")
        except Exception as exc:  # noqa: BLE001
            row["error"] = str(exc)[:200]
        rows.append(row)
    return rows


def poll_segment(key, sid, point):
    lat, lon = point
    qs = urllib.parse.urlencode({"key": key, "point": f"{lat},{lon}"})
    url = f"{API_BASE}/traffic/services/4/flowSegmentData/absolute/10/json?{qs}"
    row = {"segment_id": sid, "current_speed_kmh": "", "free_flow_speed_kmh": "",
           "current_travel_time_s": "", "free_flow_travel_time_s": "",
           "confidence": "", "road_closure": "", "error": ""}
    try:
        d = fetch_json(url)["flowSegmentData"]
        row["current_speed_kmh"] = d.get("currentSpeed", "")
        row["free_flow_speed_kmh"] = d.get("freeFlowSpeed", "")
        row["current_travel_time_s"] = d.get("currentTravelTime", "")
        row["free_flow_travel_time_s"] = d.get("freeFlowTravelTime", "")
        row["confidence"] = d.get("confidence", "")
        row["road_closure"] = d.get("roadClosure", "")
    except Exception as exc:  # noqa: BLE001
        row["error"] = str(exc)[:200]
    return row


def poll_incidents(key, bbox):
    """One bbox scan -> summary row: total incidents plus jam count/length/delay.

    Uses Traffic Incidents API v5 (incidentDetails). 'fields' selects the
    response shape; timeValidityFilter=present keeps only currently-active
    incidents. Each incident carries iconCategory, length (m) and delay (s).
    """
    fields = ("{incidents{properties{iconCategory,magnitudeOfDelay,length,delay}}}")
    qs = urllib.parse.urlencode({
        "key": key,
        "bbox": f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}",
        "fields": fields,
        "language": "en-GB",
        "timeValidityFilter": "present",
    })
    url = f"{API_BASE}/traffic/services/5/incidentDetails?{qs}"
    row = {"incident_count": "", "jam_count": "", "jam_length_m": "", "jam_delay_s": "",
           "total_length_m": "", "total_delay_s": "", "error": ""}
    try:
        incidents = fetch_json(url).get("incidents", []) or []
        jam_n = jam_len = jam_delay = tot_len = tot_delay = 0
        for inc in incidents:
            p = inc.get("properties", {}) or {}
            length = p.get("length") or 0
            delay = p.get("delay") or 0
            tot_len += length
            tot_delay += delay
            if p.get("iconCategory") == JAM_ICON_CATEGORY:
                jam_n += 1
                jam_len += length
                jam_delay += delay
        row.update(incident_count=len(incidents), jam_count=jam_n,
                   jam_length_m=round(jam_len), jam_delay_s=round(jam_delay),
                   total_length_m=round(tot_len), total_delay_s=round(tot_delay))
    except Exception as exc:  # noqa: BLE001
        row["error"] = str(exc)[:200]
    return row


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
                    help="ignore the peak/hourly gate and sample now")
    args = ap.parse_args()

    key = os.environ.get("TOMTOM_API_KEY")
    if not key:
        print("ERROR: TOMTOM_API_KEY not set", file=sys.stderr)
        return 1

    now_utc = datetime.now(ZoneInfo("UTC"))
    now_local = now_utc.astimezone(TZ)

    if not args.force and not should_sample(now_local):
        print(f"skip: {now_local:%Y-%m-%d %H:%M %Z} is off-peak, not top of hour")
        return 0

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    dt = cfg["downtown"]
    dest = (dt["lat"], dt["lon"])
    stamps = {
        "timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp_local": now_local.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    corridor_rows = []
    for c in cfg["corridors"]:
        corridor_rows += poll_corridor(key, c["id"], tuple(c["from"]), dest)

    segment_rows = [poll_segment(key, s["id"], tuple(s["point"])) for s in cfg["segments"]]

    incident_row = poll_incidents(key, cfg["incident_bbox"])

    append_rows(CORRIDOR_LOG, CORRIDOR_FIELDS, corridor_rows, stamps)
    append_rows(SEGMENT_LOG, SEGMENT_FIELDS, segment_rows, stamps)
    append_rows(INCIDENT_LOG, INCIDENT_FIELDS, [incident_row], stamps)

    all_rows = corridor_rows + segment_rows + [incident_row]
    n_err = sum(1 for r in all_rows if r["error"])
    label = "PEAK" if in_peak(now_local) else "hourly"
    print(f"{stamps['timestamp_local']} [{label}] wrote "
          f"{len(corridor_rows)} corridor + {len(segment_rows)} segment rows, "
          f"{incident_row['jam_count']} jams / {incident_row['incident_count']} incidents"
          + (f" ({n_err} errors)" if n_err else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

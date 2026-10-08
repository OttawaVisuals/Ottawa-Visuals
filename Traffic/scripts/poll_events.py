#!/usr/bin/env python3
"""Log road events (construction, incidents, special events) for Ottawa.

TomTom tells us *that* a corridor slowed down; this tells us *why*. Neither
feed below keeps history -- an event exists only while it is active -- so,
like poll_parking.py, the value only exists while we log it.

Sources:
  * city -- https://traffic.ottawa.ca/service/events, the feed behind the
            City's traffic map. Public, no key. ~120 active events, mostly
            construction, plus collisions / disabled vehicles / demos.
  * 511  -- Ontario 511 /api/v2/get/event, filtered to the Ottawa area.
            Covers the 417/416/174 (MTO roads the city feed may omit).
            Needs ONTARIO_511_KEY in ~/.ottawa_visuals.env; skipped if unset.
            Free developer key from https://511on.ca/developers (10 calls/min).

Outputs (Traffic/data/):
  * events_log.csv     -- append-only change log: one row each time an event
                          appears ('new'), changes ('updated') or drops off
                          the feed ('cleared'). Duration = cleared - new.
  * events_summary.csv -- one row per source per run: active counts by type,
                          full closures, high-priority. Joins to TomTom by time.
  * events_active.json -- the currently active set (state for the diff).
  * cameras.csv        -- traffic camera inventory (city + MTO), refreshed
                          once a day. Metadata only: archiving snapshots would
                          fill the Pi's SD card.

Runs every 15 min from pi_poll.sh. The change log is written every run (so
short incidents aren't missed); cheap because only changes produce rows.

Stdlib only.
"""

import argparse
import ast
import csv
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # the Traffic/ directory
DATA = ROOT / "data"
TZ = ZoneInfo("America/Toronto")

CITY_FEED = "https://traffic.ottawa.ca/service/events"
ONT511_FEED = "https://511on.ca/api/v2/get/event"
CAMERA_FEED = "https://traffic.ottawa.ca/beta/camera_list"

LOG = DATA / "events_log.csv"
SUMMARY = DATA / "events_summary.csv"
STATE = DATA / "events_active.json"
CAMERAS = DATA / "cameras.csv"

# Ottawa + near suburbs; 511 is province-wide, so keep only events in here.
BBOX = {"lat": (44.95, 45.55), "lon": (-76.40, -75.20)}

# A feed that suddenly returns nothing is almost certainly a glitch, not every
# event ending at once. Don't let it "clear" (then re-"new") the whole set.
MIN_PLAUSIBLE_FRACTION = 0.2

LOG_FIELDS = [
    "observed_utc", "change", "source", "event_id", "event_type", "cause",
    "priority", "road", "cross_street_1", "cross_street_2", "direction",
    "lanes", "full_closure", "headline", "created", "updated",
    "planned_start", "planned_end", "lat", "lon",
]
SUMMARY_FIELDS = [
    "timestamp_utc", "timestamp_local", "source", "active", "incidents",
    "construction", "special_events", "other", "full_closures",
    "high_priority", "error",
]
CAMERA_FIELDS = ["id", "number", "owner", "description", "description_fr", "lat", "lon"]


def fetch_json(url, params=None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ottawa-visuals-collector"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def epoch_iso(v):
    """511 timestamps are epoch seconds; the city's are local 'YYYY-MM-DD HH:MM:SS'."""
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return v


# --------------------------------------------------------------------------
# Normalisers: each feed -> the LOG_FIELDS shape (minus observed/change)
# --------------------------------------------------------------------------

def city_point(geodata):
    """geodata arrives as a dict or a stringified dict; coordinates as a JSON string."""
    if not geodata:
        return None, None
    g = ast.literal_eval(geodata) if isinstance(geodata, str) else geodata
    coords = g.get("coordinates")
    coords = json.loads(coords) if isinstance(coords, str) else coords
    while coords and isinstance(coords[0], list):   # line/polygon -> first vertex
        coords = coords[0]
    return (round(coords[1], 6), round(coords[0], 6)) if coords else (None, None)


def city_schedule(raw):
    try:
        s = ast.literal_eval(raw) if isinstance(raw, str) else raw
        return s[0].get("startDateTime"), s[-1].get("endDateTime")
    except Exception:
        return None, None


def fetch_city():
    out = []
    for e in fetch_json(CITY_FEED)["events"]:
        lat, lon = city_point(e.get("geodata"))
        start, end = city_schedule(e.get("schedule"))
        lanes = e.get("lanes") or ""
        out.append({
            "source": "city", "event_id": str(e["id"]),
            "event_type": (e.get("eventType") or "").upper(),
            "cause": (e.get("cause") or "").rstrip(". "),
            "priority": e.get("priority"),
            "road": e.get("mainStreet"),
            "cross_street_1": e.get("crossStreet1"), "cross_street_2": e.get("crossStreet2"),
            "direction": None, "lanes": lanes,
            "full_closure": lanes.strip().lower() == "closed",
            "headline": e.get("message") or e.get("headline"),
            "created": e.get("created"), "updated": e.get("updated"),
            "planned_start": start, "planned_end": end, "lat": lat, "lon": lon,
        })
    return out


def in_bbox(lat, lon):
    return (lat is not None and lon is not None
            and BBOX["lat"][0] <= lat <= BBOX["lat"][1]
            and BBOX["lon"][0] <= lon <= BBOX["lon"][1])


def fetch_511(key):
    out = []
    for e in fetch_json(ONT511_FEED, {"key": key, "format": "json", "lang": "en"}):
        lat, lon = e.get("Latitude"), e.get("Longitude")
        if not in_bbox(lat, lon):
            continue
        etype = (e.get("EventType") or "").upper()
        out.append({
            "source": "511", "event_id": str(e.get("ID")),
            "event_type": {"ACCIDENTSANDINCIDENTS": "INCIDENT", "ROADWORK": "CONSTRUCTION",
                           "SPECIALEVENTS": "SPECIAL_EVENT"}.get(etype, etype),
            "cause": e.get("EventSubType"), "priority": e.get("Severity"),
            "road": e.get("RoadwayName"), "cross_street_1": None, "cross_street_2": None,
            "direction": e.get("DirectionOfTravel"), "lanes": e.get("LanesAffected"),
            "full_closure": bool(e.get("IsFullClosure")),
            "headline": e.get("Description"),
            "created": epoch_iso(e.get("Reported")), "updated": epoch_iso(e.get("LastUpdated")),
            "planned_start": epoch_iso(e.get("StartDate")),
            "planned_end": epoch_iso(e.get("PlannedEndDate")),
            "lat": round(lat, 6), "lon": round(lon, 6),
        })
    return out


# --------------------------------------------------------------------------
# Diff + logging
# --------------------------------------------------------------------------

def fingerprint(ev):
    """What counts as an 'update': the feed's own timestamp or anything a driver would notice."""
    key = "|".join(str(ev.get(k)) for k in
                   ("updated", "event_type", "priority", "lanes", "full_closure", "headline"))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def append_csv(path, fields, rows):
    if not rows:
        return
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def summarise(source, events, now_utc, now_local, error=""):
    types = [e["event_type"] for e in events]
    return {
        "timestamp_utc": now_utc, "timestamp_local": now_local, "source": source,
        "active": len(events) if not error else "",
        "incidents": types.count("INCIDENT") if not error else "",
        "construction": types.count("CONSTRUCTION") if not error else "",
        "special_events": types.count("SPECIAL_EVENT") if not error else "",
        "other": sum(t not in ("INCIDENT", "CONSTRUCTION", "SPECIAL_EVENT") for t in types)
                 if not error else "",
        "full_closures": sum(bool(e["full_closure"]) for e in events) if not error else "",
        "high_priority": sum(str(e["priority"]).upper() in ("HIGH", "MAJOR") for e in events)
                         if not error else "",
        "error": error,
    }


def diff_source(source, events, state, now_utc):
    """Compare this run's events to the stored active set; return log rows."""
    prev = state.get(source, {})
    if prev and len(events) < MIN_PLAUSIBLE_FRACTION * len(prev):
        raise RuntimeError(f"implausible drop {len(prev)} -> {len(events)} events; state kept")
    rows, current = [], {}
    for ev in events:
        fp = fingerprint(ev)
        current[ev["event_id"]] = {"fp": fp, "event": ev}
        old = prev.get(ev["event_id"])
        if old is None:
            rows.append({**ev, "observed_utc": now_utc, "change": "new"})
        elif old["fp"] != fp:
            rows.append({**ev, "observed_utc": now_utc, "change": "updated"})
    for eid, old in prev.items():
        if eid not in current:
            rows.append({**old["event"], "observed_utc": now_utc, "change": "cleared"})
    state[source] = current
    return rows


def poll_events():
    now = datetime.now(timezone.utc)
    now_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_local = now.astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}

    sources = [("city", fetch_city)]
    key = os.environ.get("ONTARIO_511_KEY")
    if key:
        sources.append(("511", lambda: fetch_511(key)))

    log_rows, summaries, failed = [], [], []
    for name, fetch in sources:
        try:
            events = fetch()
            log_rows += diff_source(name, events, state, now_utc)
            summaries.append(summarise(name, events, now_utc, now_local))
        except Exception as e:
            summaries.append(summarise(name, [], now_utc, now_local, error=str(e)[:200]))
            failed.append(name)

    append_csv(LOG, LOG_FIELDS, log_rows)
    append_csv(SUMMARY, SUMMARY_FIELDS, summaries)
    STATE.write_text(json.dumps(state, indent=0, sort_keys=True), encoding="utf-8")
    changes = {c: sum(r["change"] == c for r in log_rows) for c in ("new", "updated", "cleared")}
    print(f"{now_local} events: " + ", ".join(f"{s['source']}={s['active'] or 'ERR'}" for s in summaries)
          + f" | changes {changes}" + ("" if key else " | 511 skipped (no ONTARIO_511_KEY)"))
    return failed


# --------------------------------------------------------------------------
# Camera inventory (daily)
# --------------------------------------------------------------------------

def refresh_cameras(force):
    now_local = datetime.now(TZ)
    if not force and not (now_local.hour == 4 and now_local.minute < 15) and CAMERAS.exists():
        return
    rows = sorted(({
        "id": c.get("id"), "number": c.get("number"), "owner": c.get("type"),
        "description": c.get("description"), "description_fr": c.get("descriptionFr"),
        "lat": c.get("latitude"), "lon": c.get("longitude"),
    } for c in fetch_json(CAMERA_FEED)), key=lambda r: r["id"])
    with open(CAMERAS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMERA_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"cameras: {len(rows)} listed")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="refresh the camera list now")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    failed = poll_events()
    try:
        refresh_cameras(args.force)
    except Exception as e:
        print(f"camera list failed: {e}", file=sys.stderr)
        failed.append("cameras")
    if failed:
        sys.exit(f"failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Log traffic incidents from TomTom's Orbis incident vector tiles (backup to poll_traffic.py).

The Incidents Details allowance (2,500/month) is nearly spent; the tiles use the separate
vector-tile allowance (200k/month, shared with poll_tiles.py). Each sample fetches the same
~20 zoom-11 tiles as poll_tiles.py (~23k requests a month), same cadence (every 15 min at
weekday rush hours, hourly otherwise), decided from this script's own log.

Outputs (Traffic/data/):
  * incident_tiles_summary.csv -- one row per sample: active incidents, by main category,
                                  delay seconds, how many are major/closures
  * incident_tiles_log.csv     -- one row per incident once it disappears: id, first/last
                                  seen, category, worst magnitude, max delay, road class, lat/lon
  * incident_tiles_state.json  -- incidents seen in the last successful full sample

An incident is only marked closed after a sample where every tile loaded. Counts are of
TomTom's incident reports, not police-confirmed events. Stdlib only; reuses tile_probe.py.
Requires TOMTOM_API_KEY with the Orbis traffic incident tiles product enabled.
"""

import argparse
import csv
import json
import os
import sys
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poll_traffic as pt  # noqa: E402  (cadence gate)
import tile_probe as tp  # noqa: E402  (tile fetch + decoder)

DATA = Path(__file__).resolve().parents[1] / "data"
SUMMARY = DATA / "incident_tiles_summary.csv"
CLOSED = DATA / "incident_tiles_log.csv"
STATE = DATA / "incident_tiles_state.json"
ZOOM = 11
URL = ("https://api.tomtom.com/maps/orbis/traffic/incidents/vector/tile/{z}/{x}/{y}"
       "?apiVersion=2&key={key}")
TZ = ZoneInfo("America/Toronto")
MAGNITUDE_RANK = {"unknown": 0, "minor": 1, "moderate": 2, "major": 3, "undefined": 4}
CATEGORIES = ("accident", "jam", "roadClosed", "laneClosed", "roadWorks")
SUMMARY_FIELDS = ["timestamp_utc", "timestamp_local", "active", *CATEGORIES, "other",
                  "major_or_closed", "total_delay_s", "tiles_ok", "tiles_total", "error"]
CLOSED_FIELDS = ["id", "first_seen_utc", "last_seen_utc", "minutes_seen", "category",
                 "worst_magnitude", "max_delay_s", "road_category", "lat", "lon"]


def main_category(props):
    """The highest-priority icon_category_N (priority rises with N)."""
    n = -1
    while f"icon_category_{n + 1}" in props:
        n += 1
    return props.get(f"icon_category_{n}", "unknown") if n >= 0 else "unknown"


def collect(tiles):
    """tiles: {(x, y): layers} -> {incident id: summary dict}, merging pieces across tiles."""
    found = {}
    for (x, y), layers in tiles.items():
        for layer in layers:
            for f in layer["features"]:
                p = f["props"]
                iid = p.get("id")
                if not iid:
                    continue
                mag = p.get("magnitude_of_delay", "unknown")
                delay = int(p.get("delay_in_seconds") or 0)
                cur = found.get(iid)
                if cur is None:
                    lon = lat = ""
                    if f.get("xy"):
                        lon, lat = tp.tile_lonlat(ZOOM, x, y, f["xy"][0], f["xy"][1], layer["extent"])
                        lon, lat = round(lon, 5), round(lat, 5)
                    cur = found[iid] = {"category": main_category(p), "magnitude": mag, "delay": delay,
                                        "road": p.get("road_category", ""), "lat": lat, "lon": lon}
                else:
                    cur["delay"] = max(cur["delay"], delay)
                    if MAGNITUDE_RANK.get(mag, 0) > MAGNITUDE_RANK.get(cur["magnitude"], 0):
                        cur["magnitude"] = mag
    return found


def summary_row(found):
    row = {c: 0 for c in CATEGORIES}
    row.update(other=0, major_or_closed=0, total_delay_s=0, active=len(found))
    for inc in found.values():
        key = inc["category"] if inc["category"] in CATEGORIES else "other"
        row[key] += 1
        row["total_delay_s"] += inc["delay"]
        if inc["magnitude"] in ("major", "undefined") or inc["category"] in ("roadClosed", "laneClosed"):
            row["major_or_closed"] += 1
    return row


def update_state(found, state, stamp, complete):
    """Merge a sample into the open-incident state; returns rows for incidents that ended."""
    open_ = state.setdefault("open", {})
    for iid, inc in found.items():
        cur = open_.get(iid)
        if cur is None:
            open_[iid] = {**inc, "first": stamp, "last": stamp, "max_delay": inc["delay"]}
        else:
            cur["last"] = stamp
            cur["max_delay"] = max(cur["max_delay"], inc["delay"])
            if MAGNITUDE_RANK.get(inc["magnitude"], 0) > MAGNITUDE_RANK.get(cur["magnitude"], 0):
                cur["magnitude"] = inc["magnitude"]
    ended = []
    if complete:
        for iid in [i for i in open_ if i not in found]:
            o = open_.pop(iid)
            t0 = datetime.strptime(o["first"], "%Y-%m-%dT%H:%M:%SZ")
            t1 = datetime.strptime(o["last"], "%Y-%m-%dT%H:%M:%SZ")
            ended.append({"id": iid, "first_seen_utc": o["first"], "last_seen_utc": o["last"],
                          "minutes_seen": round((t1 - t0).total_seconds() / 60), "category": o["category"],
                          "worst_magnitude": o["magnitude"], "max_delay_s": o["max_delay"],
                          "road_category": o["road"], "lat": o["lat"], "lon": o["lon"]})
    return ended


def append(path, fields, rows):
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ignore the cadence gate")
    args = ap.parse_args()
    key = os.environ.get("TOMTOM_API_KEY", "").strip()
    if not key:
        print("ERROR: TOMTOM_API_KEY not set", file=sys.stderr)
        return 1

    now_utc = datetime.now(ZoneInfo("UTC"))
    now_local = now_utc.astimezone(TZ)
    if not args.force and not pt.should_sample(now_local, SUMMARY):
        print(f"skip: {now_local:%Y-%m-%d %H:%M %Z} slot is already sampled")
        return 0

    base = {"timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timestamp_local": now_local.strftime("%Y-%m-%dT%H:%M:%S%z")}
    coords = tp.tiles_for_bbox(ZOOM)
    tiles, error = {}, ""
    for x, y in coords:
        try:
            tiles[(x, y)] = tp.decode_tile(tp.fetch(URL.format(z=ZOOM, x=x, y=y, key=key)))
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}"
            if 400 <= exc.code < 500:
                break  # same answer for every tile; don't spend more requests
        except Exception as exc:  # noqa: BLE001 - log it, a bad tile shouldn't kill the run
            error = type(exc).__name__

    counts = {"tiles_ok": len(tiles), "tiles_total": len(coords), "error": error}
    if not tiles:
        append(SUMMARY, SUMMARY_FIELDS, [{**base, **counts, "error": error or "no tiles"}])
        print(f"no tiles fetched ({error})")
        return 0

    found = collect(tiles)
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    ended = update_state(found, state, base["timestamp_utc"], complete=len(tiles) == len(coords))
    STATE.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    append(SUMMARY, SUMMARY_FIELDS, [{**base, **counts, **summary_row(found)}])
    if ended:
        append(CLOSED, CLOSED_FIELDS, ended)
    print(f"{len(found)} active incidents from {len(tiles)}/{len(coords)} tiles, {len(ended)} ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())

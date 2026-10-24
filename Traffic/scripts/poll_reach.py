#!/usr/bin/env python3
"""Log how far a car gets in 30 minutes from downtown and four suburbs (TomTom Reachable Range).

Uses live traffic, so the same trip's reach shrinks at rush hour. Samples at fixed local
times (slots.py): weekdays 08:00, 12:00 and 17:00, weekends 12:00; five origins a slot,
about 300 requests a month against the free 2,500.

Outputs (Traffic/data/):
  * reachable_range.csv    -- one row per origin and slot: area_km2, bounding box, error
  * reachable_range.jsonl  -- the boundary polygon of each row (lat/lon, 4 decimals) for maps

Reach from a suburb shows how deep into the city you get; reach from downtown shows how far
out. Area is of TomTom's approximate polygon, not an exact isochrone. Stdlib only.
Requires TOMTOM_API_KEY.
"""

import argparse
import csv
import json
import math
import os
import sys
import urllib.error
import urllib.parse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poll_traffic as pt  # noqa: E402  (fetch_json, config)
import slots  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"
LOG = DATA / "reachable_range.csv"
POLY = DATA / "reachable_range.jsonl"
BUDGET_S = 1800
FIELDS = ["timestamp_utc", "timestamp_local", "slot", "origin_id", "origin_lat", "origin_lon",
          "budget_s", "area_km2", "points", "min_lat", "max_lat", "min_lon", "max_lon", "error"]
TZ = ZoneInfo("America/Toronto")


def polygon_area_km2(pts):
    """Shoelace area of [(lat, lon)...] on a local equirectangular projection."""
    if len(pts) < 3:
        return 0.0
    lat0 = sum(p[0] for p in pts) / len(pts)
    kx = 111.320 * math.cos(math.radians(lat0))
    ky = 110.574
    xy = [(p[1] * kx, p[0] * ky) for p in pts]
    s = sum(xy[i][0] * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * xy[i][1]
            for i in range(len(xy)))
    return abs(s) / 2.0


def origins(cfg):
    dt = cfg["downtown"]
    out = [("downtown", dt["lat"], dt["lon"])]
    out += [(c["id"], c["from"][0], c["from"][1]) for c in cfg["corridors"]
            if c["id"] in ("kanata", "orleans", "barrhaven", "riverside")]
    return out


def poll_origin(key, oid, lat, lon):
    qs = urllib.parse.urlencode({"key": key, "timeBudgetInSec": BUDGET_S, "traffic": "true",
                                 "travelMode": "car", "routeType": "fastest", "departAt": "now"})
    url = f"{pt.API_BASE}/routing/1/calculateReachableRange/{lat},{lon}/json?{qs}"
    data = pt.fetch_json(url)
    return [(p["latitude"], p["longitude"]) for p in data["reachableRange"]["boundary"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ignore the slot schedule")
    args = ap.parse_args()
    key = os.environ.get("TOMTOM_API_KEY", "").strip()
    if not key:
        print("ERROR: TOMTOM_API_KEY not set", file=sys.stderr)
        return 1

    now_utc = datetime.now(ZoneInfo("UTC"))
    now_local = now_utc.astimezone(TZ)
    slot = f"{now_local:%Y-%m-%dT%H}" if args.force else slots.due_slot(now_local, LOG)
    if not slot:
        print("skip: no slot due")
        return 0

    cfg = json.loads(pt.CONFIG.read_text(encoding="utf-8"))
    base = {"timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timestamp_local": now_local.strftime("%Y-%m-%dT%H:%M:%S%z"), "slot": slot,
            "budget_s": BUDGET_S}
    rows, polys = [], []
    for oid, lat, lon in origins(cfg):
        row = {**base, "origin_id": oid, "origin_lat": lat, "origin_lon": lon}
        try:
            pts = poll_origin(key, oid, lat, lon)
            row.update(area_km2=f"{polygon_area_km2(pts):.1f}", points=len(pts),
                       min_lat=min(p[0] for p in pts), max_lat=max(p[0] for p in pts),
                       min_lon=min(p[1] for p in pts), max_lon=max(p[1] for p in pts))
            polys.append({"slot": slot, "origin_id": oid, "timestamp_utc": base["timestamp_utc"],
                          "boundary": [[round(a, 4), round(b, 4)] for a, b in pts]})
        except urllib.error.HTTPError as exc:
            row["error"] = f"HTTP {exc.code}"
            rows.append(row)
            if 400 <= exc.code < 500 and exc.code != 400:
                break  # key/quota problem: same answer for every origin
            continue
        except Exception as exc:  # noqa: BLE001 - log it, one origin shouldn't kill the run
            row["error"] = type(exc).__name__
        rows.append(row)

    new = not LOG.exists() or LOG.stat().st_size == 0
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)
    if polys:
        with POLY.open("a", encoding="utf-8") as fh:
            fh.writelines(json.dumps(p, separators=(",", ":")) + "\n" for p in polys)
    print(f"slot {slot}: {len(polys)}/{len(rows)} origins ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())

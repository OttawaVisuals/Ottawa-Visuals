#!/usr/bin/env python3
"""Second commute measure: live-traffic travel times from TomTom Matrix Routing v2.

One request each way per slot (5 suburbs -> downtown, downtown -> 5 suburbs), so 10 cells
a slot. Samples at fixed local times (slots.py): weekdays 08:00, 12:00 and 17:00, weekends
12:00; about 75 requests (~750 cells) a month against the free 2,500, which holds even if
the allowance counts cells. Same five corridors as corridor_travel_times.csv, but a
different product, so it still works while the Routing API allowance is spent; compare,
don't splice.

Output: Traffic/data/matrix_times.csv, one row per origin/destination pair and slot.
Matrix v2 may need an entitlement the free tier lacks; a 403 is logged once per slot.
Stdlib only. Requires TOMTOM_API_KEY.
"""

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poll_traffic as pt  # noqa: E402  (config, API_BASE)
import slots  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"
LOG = DATA / "matrix_times.csv"
FIELDS = ["timestamp_utc", "timestamp_local", "slot", "direction", "corridor_id",
          "length_m", "travel_time_s", "traffic_delay_s", "error"]
TZ = ZoneInfo("America/Toronto")


def pt_obj(lat, lon):
    return {"point": {"latitude": lat, "longitude": lon}}


def post_matrix(key, origins, destinations):
    body = json.dumps({"origins": [pt_obj(*o) for o in origins],
                       "destinations": [pt_obj(*d) for d in destinations],
                       "options": {"departAt": "now", "traffic": "live", "routeType": "fastest",
                                   "travelMode": "car"}}).encode()
    req = urllib.request.Request(f"{pt.API_BASE}/routing/matrix/2?key={key}", data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "OttawaVisuals-traffic/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cells_to_rows(data, ids, direction, base):
    """One row per cell. to_downtown: origins are suburbs; from_downtown: destinations are."""
    rows = []
    for cell in data.get("data", []):
        i = cell["originIndex"] if direction == "to_downtown" else cell["destinationIndex"]
        row = {**base, "direction": direction, "corridor_id": ids[i]}
        s = cell.get("routeSummary")
        if s:
            row.update(length_m=s.get("lengthInMeters"), travel_time_s=s.get("travelTimeInSeconds"),
                       traffic_delay_s=s.get("trafficDelayInSeconds"))
        else:
            row["error"] = (cell.get("detailedError") or {}).get("code", "no summary")
        rows.append(row)
    return rows


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
    dt = (cfg["downtown"]["lat"], cfg["downtown"]["lon"])
    ids = [c["id"] for c in cfg["corridors"]]
    subs = [tuple(c["from"]) for c in cfg["corridors"]]
    base = {"timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timestamp_local": now_local.strftime("%Y-%m-%dT%H:%M:%S%z"), "slot": slot}

    rows = []
    for direction, origins, dests in (("to_downtown", subs, [dt]), ("from_downtown", [dt], subs)):
        try:
            rows += cells_to_rows(post_matrix(key, origins, dests), ids, direction, base)
        except urllib.error.HTTPError as exc:
            rows.append({**base, "direction": direction, "corridor_id": "all", "error": f"HTTP {exc.code}"})
            if 400 <= exc.code < 500:
                break  # entitlement/quota: the other direction would fail the same way
        except Exception as exc:  # noqa: BLE001 - log it, don't kill the run
            rows.append({**base, "direction": direction, "corridor_id": "all", "error": type(exc).__name__})

    new = not LOG.exists() or LOG.stat().st_size == 0
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)
    print(f"slot {slot}: {sum(1 for r in rows if not r.get('error'))}/{len(rows)} cells ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())

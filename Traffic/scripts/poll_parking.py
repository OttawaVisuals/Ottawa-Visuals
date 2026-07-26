#!/usr/bin/env python3
"""Poll City of Ottawa municipal parking lots for live occupancy.

Source: https://traffic.ottawa.ca/map/service/parking — the feed behind the
traffic.ottawa.ca map. Public, no API key, and it publishes `freeSpaces` and
`capacity` per lot, including the downtown garages (Gloucester, Clarence,
Dalhousie, ByWard...).

Why this is on the RTO4 page: garage occupancy is the most direct
office-occupancy proxy available to us. Congestion says people are moving;
a full downtown garage says people arrived and stayed. Nothing else in our
collection distinguishes the two.

Coverage, verified 2026-07-25: the feed lists 15 lots but only 5 publish
`freeSpaces` — 4 of them downtown (Gloucester, both Clarence garages, and
110 Laurier), about 1,800 spaces. The rest report capacity only. So the
downtown occupancy figure rests on four garages, and the page says so.

Like TomTom's live map, this feed keeps **no history** — the value only exists
while we log it. Two rows per reading are appended:
  * one `lot` row per lot (id, capacity, free spaces)
  * one `all`/`downtown` summary row (occupancy % across lots)

Cadence is self-gated here, not in the cron, so it survives DST — matching
poll_traffic.py. Weekday daytime (07:00-19:00 local) samples every run; other
times only the top-of-hour run is kept. Pass --force to bypass.

Related: Park & Ride lots publish `capacity` but NOT occupancy (verified
2026-07-25), so commuter-lot fill cannot be tracked this way.

Stdlib only. No credentials needed.
"""

import argparse
import csv
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # the Traffic/ directory
DATA = ROOT / "data"
TZ = ZoneInfo("America/Toronto")

FEED = "https://traffic.ottawa.ca/map/service/parking"
LOT_LOG = DATA / "parking_lots.csv"
SUMMARY_LOG = DATA / "parking_summary.csv"

# Downtown core garages, matched on their street address. Occupancy across just
# these is the office-occupancy signal; the city-wide number includes outlying
# lots that RTO4 should not move.
DOWNTOWN_STREETS = (
    "gloucester", "clarence", "dalhousie", "york", "george",
    "slater", "lyon", "queen", "albert", "rideau", "laurier",
    "nicholas", "waller", "elgin", "kent", "o'connor", "oconnor",
    "metcalfe", "sparks", "wellington", "bank",
)

LOT_FIELDS = [
    "timestamp_utc", "timestamp_local", "lot_id", "address", "lot_type",
    "capacity", "free_spaces", "free_accessible", "occupancy_pct", "downtown", "error",
]
SUMMARY_FIELDS = [
    "timestamp_utc", "timestamp_local", "group", "lots_reporting",
    "capacity_total", "free_total", "occupancy_pct", "error",
]


def in_daytime(now_local):
    return now_local.weekday() < 5 and 7 <= now_local.hour < 19


def should_sample(now_local):
    return in_daytime(now_local) or now_local.minute < 15


def is_downtown(address):
    a = (address or "").lower()
    return any(s in a for s in DOWNTOWN_STREETS)


def fetch_lots():
    req = urllib.request.Request(FEED, headers={"User-Agent": "Ottawa-Visuals/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace")).get("parking_lots", [])


def append_rows(path, fields, rows, stamps):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({**stamps, **r})


def summarise(rows, group, keep):
    subset = [r for r in rows if keep(r) and r["capacity"] and r["free_spaces"] is not None]
    cap = sum(r["capacity"] for r in subset)
    free = sum(r["free_spaces"] for r in subset)
    return {
        "group": group,
        "lots_reporting": len(subset),
        "capacity_total": cap or "",
        "free_total": free if subset else "",
        "occupancy_pct": round((cap - free) / cap * 100, 1) if cap else "",
        "error": "" if subset else "no lots reporting",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="ignore the cadence gate")
    args = ap.parse_args()

    now_utc = datetime.now(ZoneInfo("UTC"))
    now_local = now_utc.astimezone(TZ)
    if not args.force and not should_sample(now_local):
        print(f"skip: {now_local:%Y-%m-%d %H:%M %Z} is off-peak, not top of hour")
        return 0

    stamps = {
        "timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp_local": now_local.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    try:
        lots = fetch_lots()
    except Exception as e:                                     # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        print(f"ERROR: {err}", file=sys.stderr)
        append_rows(SUMMARY_LOG, SUMMARY_FIELDS,
                    [{"group": "all", "lots_reporting": 0, "capacity_total": "",
                      "free_total": "", "occupancy_pct": "", "error": err}], stamps)
        return 1

    rows = []
    for lot in lots:
        cap = lot.get("capacity")
        free = lot.get("freeSpaces")
        addr = lot.get("address") or ""
        rows.append({
            "lot_id": lot.get("lot_id") or lot.get("id") or "",
            "address": addr.replace(",", " "),
            "lot_type": lot.get("type") or "",
            "capacity": cap if isinstance(cap, int) else None,
            "free_spaces": free if isinstance(free, int) else None,
            "free_accessible": lot.get("freeAccessibleSpaces"),
            "downtown": is_downtown(addr),
            "error": "" if isinstance(free, int) else "no freeSpaces in feed",
        })
    for r in rows:
        cap, free = r["capacity"], r["free_spaces"]
        r["occupancy_pct"] = round((cap - free) / cap * 100, 1) if cap and free is not None else ""

    summary = [
        summarise(rows, "all", lambda r: True),
        summarise(rows, "downtown", lambda r: r["downtown"]),
    ]

    append_rows(LOT_LOG, LOT_FIELDS, rows, stamps)
    append_rows(SUMMARY_LOG, SUMMARY_FIELDS, summary, stamps)

    label = "DAYTIME" if in_daytime(now_local) else "hourly"
    dt = summary[1]
    print(f"{stamps['timestamp_local']} [{label}] {len(rows)} lots · "
          f"downtown {dt['occupancy_pct']}% full "
          f"({dt['lots_reporting']} lots, {dt['free_total']} free)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

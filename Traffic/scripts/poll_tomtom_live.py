#!/usr/bin/env python3
"""Log TomTom's published hourly traffic readings for Ottawa, once a day.

TomTom's Traffic Index page for Ottawa draws its "live traffic" tiles from a public
JSON file the page itself loads:
  https://www.tomtom.com/traffic-index/api/live-traffic.json?city=CAN_ottawa_new
It holds about a week of hourly records for the whole city: congestion level (live and
"usual for that hour"), relative travel time, and jam count / length / delay. One fetch
a day therefore gives a gap-free history, and TomTom keeps none of it past the week.

This is TomTom's data, not ours: shown on the site with attribution and kept only for
comparison with our own sampled segments (Traffic/README.md). It is not an API with
terms we have signed; if TomTom asks us to stop, delete the CSV and remove this job.

Outputs (Traffic/data/):
  * tomtom_ottawa_hourly.csv  -- one row per TomTom record, keyed on update_utc; a later
                                 fetch overwrites the same hour (TomTom revises them).
  * tomtom_live_state.json    -- last success (Ottawa date) and last attempt.

Runs from collect.yml every 5 min; self-gates to one fetch per Ottawa day, after 05:00
local, and after a failure waits an hour before trying again. Stdlib only.
"""

import argparse
import csv
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
TZ = ZoneInfo("America/Toronto")

URL = "https://www.tomtom.com/traffic-index/api/live-traffic.json?city=CAN_ottawa_new"
UA = "Mozilla/5.0 (compatible; ottawa-visuals-collector)"
OUT = DATA / "tomtom_ottawa_hourly.csv"
STATE = DATA / "tomtom_live_state.json"

FROM_HOUR = 5                       # Ottawa local; the previous evening is complete by then
RETRY_AFTER = timedelta(hours=1)

# csv column -> TomTom field
FIELDS = {"congestion_pct": "trafficIndexLive", "congestion_usual_pct": "trafficIndexHistoric",
          "rel_travel_time_pct": "relTravelTimeLive", "rel_travel_time_usual_pct": "relTravelTimeHistoric",
          "jams_count": "jamsCount", "jams_length_km": "jamsLength", "jams_delay_min": "jamsDelay"}
COLUMNS = ["update_utc", "local_date", "local_hour", *FIELDS, "fetched_utc"]


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def parse(payload, fetched_utc):
    """Payload -> rows. Raises ValueError if the shape is not what we expect."""
    if payload.get("region", {}).get("id") != "CAN_ottawa_new":
        raise ValueError("unexpected region in response")
    records = payload.get("data")
    if not isinstance(records, list) or not records:
        raise ValueError("no data records")
    rows = []
    for rec in records:
        missing = [k for k in ("updateTime", *FIELDS.values()) if not isinstance(rec.get(k), (int, float))]
        if missing:
            raise ValueError(f"record missing numeric fields: {missing}")
        when = datetime.fromtimestamp(rec["updateTime"] / 1000, timezone.utc)
        local = when.astimezone(TZ)
        rows.append({"update_utc": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "local_date": local.date().isoformat(),
                     "local_hour": local.hour, **{col: rec[src] for col, src in FIELDS.items()},
                     "fetched_utc": fetched_utc})
    return rows


def load_rows():
    if not OUT.exists():
        return {}
    with open(OUT, newline="", encoding="utf-8") as fh:
        return {r["update_utc"]: r for r in csv.DictReader(fh)}


def merge(existing, rows):
    """Upsert by update_utc; returns (merged dict, number of new keys)."""
    new = sum(r["update_utc"] not in existing for r in rows)
    return {**existing, **{r["update_utc"]: r for r in rows}}, new


def write_rows(rows):
    DATA.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: r["update_utc"]))


def due(state, now):
    local = now.astimezone(TZ)
    if local.hour < FROM_HOUR or state.get("last_success_local_date") == local.date().isoformat():
        return False
    attempt = state.get("last_attempt_utc")
    if attempt and state.get("last_attempt_failed") and \
            now - datetime.fromisoformat(attempt.replace("Z", "+00:00")) < RETRY_AFTER:
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="ignore the once-a-day gate")
    ap.add_argument("--dry-run", action="store_true", help="fetch and print, write nothing")
    args = ap.parse_args()

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    now = datetime.now(timezone.utc)
    if not (args.force or args.dry_run) and not due(state, now):
        return 0
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        rows = parse(fetch(), stamp)
    except Exception as e:
        print(f"tomtom live: {e}", file=sys.stderr)
        if not args.dry_run:
            STATE.write_text(json.dumps({**state, "last_attempt_utc": stamp, "last_attempt_failed": True}, indent=1),
                             encoding="utf-8")
        return 1
    if args.dry_run:
        print(f"{len(rows)} records, {rows[0]['update_utc']} .. {rows[-1]['update_utc']}")
        print(rows[-1])
        return 0
    merged, new = merge(load_rows(), rows)
    write_rows(merged)
    STATE.write_text(json.dumps({"last_success_local_date": now.astimezone(TZ).date().isoformat(),
                                 "last_attempt_utc": stamp, "last_attempt_failed": False}, indent=1), encoding="utf-8")
    print(f"tomtom live: {len(rows)} records fetched, {new} new, {len(merged)} stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())

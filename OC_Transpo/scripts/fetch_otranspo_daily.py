#!/usr/bin/env python3
"""Fetch otranspo.ca's daily OC Transpo on-time figures, for comparison with ours.

otranspo.ca is an independent riders' site (not OC Transpo, not ours). Its
daily service report scores one settled prediction per (trip, stop) arrival
against the schedule with a +/-5 min window — the same window as our
pct_within_5min, so the two can be lined up day by day. Their public API is
MIT-licensed with attribution required (https://otranspo.ca/en/licence); the
underlying transit data stays under OC Transpo's open-data terms. robots.txt
allows /api/insights/reports/day/ and the API asks for at most 60 requests a
minute; this makes a few a run, one second apart.

Writes (append-only, one fetch per finished day):
  rt_data/otranspo_daily.csv       : date, status, network on-time % and counts
  rt_data/otranspo_route_daily.csv : date, route, on-time % and counts

Days are fetched from START to yesterday (Ottawa time). A day they have no
report for is retried until it is a week old, then logged with its status so
it isn't asked for again. Run from collect.yml's hourly transit commit.
Stdlib only.
"""
import csv
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DATA = Path(__file__).resolve().parents[1] / "rt_data"
DAILY = DATA / "otranspo_daily.csv"
ROUTES = DATA / "otranspo_route_daily.csv"
TZ = ZoneInfo("America/Toronto")

URL = "https://otranspo.ca/api/insights/reports/selected?period=day&date={d}&operator=oc_transpo"
START = date(2026, 8, 1)      # their archive begins here
MAX_PER_RUN = 15              # backfill spreads over a few hourly runs
GIVE_UP_DAYS = 7

DAILY_FIELDS = ["date", "status", "method", "observations", "on_time_arrivals",
                "on_time_pct", "routes_measured", "partial", "fetched_utc"]
ROUTE_FIELDS = ["date", "route", "observations", "on_time_arrivals", "on_time_pct"]


def fetch(d):
    req = urllib.request.Request(URL.format(d=d.isoformat()), headers={
        "User-Agent": "OttawaVisuals-transit/1.0 (+https://github.com/OttawaVisuals)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def append(path, fields, rows):
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def main():
    have = set()
    if DAILY.exists():
        with DAILY.open(newline="", encoding="utf-8") as fh:
            have = {r["date"] for r in csv.DictReader(fh)}
    today = datetime.now(TZ).date()
    todo = [START + timedelta(days=i) for i in range((today - START).days)]
    todo = [d for d in todo if d.isoformat() not in have][:MAX_PER_RUN]

    done = 0
    for d in todo:
        try:
            doc = fetch(d)
        except Exception as exc:  # noqa: BLE001 - try again next run
            print(f"otranspo.ca {d}: {exc}", file=sys.stderr)
            break
        time.sleep(1)
        sel = doc.get("selected") or {}
        win = sel.get("window") or {}
        rep = sel.get("report") or {}
        net = rep.get("network") or {}
        ok = doc.get("status") == "available" and win.get("daysCompleted") == 1 and net.get("onTimePct") is not None
        if not ok and (today - d).days <= GIVE_UP_DAYS:
            continue  # not published (yet): ask again next run
        stamp = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
        append(DAILY, DAILY_FIELDS, [{
            "date": d.isoformat(),
            "status": doc.get("status") if ok else (doc.get("status") or "unavailable"),
            "method": doc.get("method") or "",
            "observations": net.get("observations", "") if ok else "",
            "on_time_arrivals": net.get("onTimeArrivals", "") if ok else "",
            "on_time_pct": net.get("onTimePct", "") if ok else "",
            "routes_measured": net.get("routesMeasured", "") if ok else "",
            "partial": int(bool(win.get("partialDates") or win.get("partialCapture"))),
            "fetched_utc": stamp,
        }])
        if ok:
            seen, rows = set(), []
            for key in ("eligibleRoutes", "thinlyMeasured", "unsegmentedRoutes"):
                for r in rep.get(key) or []:
                    rid = str(r.get("routeId") or "")
                    if rid and rid not in seen and r.get("observations"):
                        seen.add(rid)
                        rows.append({"date": d.isoformat(), "route": rid,
                                     "observations": r["observations"],
                                     "on_time_arrivals": r.get("onTimeArrivals", ""),
                                     "on_time_pct": r.get("onTimePct", "")})
            rows.sort(key=lambda r: (int(r["route"]) if r["route"].isdigit() else 10 ** 6, r["route"]))
            append(ROUTES, ROUTE_FIELDS, rows)
        done += 1
    print(f"otranspo.ca: {done} day(s) added, {len(have) + done} on file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

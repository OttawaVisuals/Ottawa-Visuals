#!/usr/bin/env python3
"""Ottawa-zone hourly electricity demand from IESO, reduced to weekly office-hours load.

Source: reports-public.ieso.ca/public/DemandZonal/PUB_DemandZonal_<year>.csv —
one row per hour per zone column, published since 2003. We only keep the
`Ottawa` column.

Why it's on the RTO4 page: office buildings draw power when people are in them.
Weekday 09:00-17:00 zonal load is a crude but genuinely independent
occupancy proxy, and unlike almost everything else here it has 20+ years of
history, so the RTO3 step (Sep 2024) is visible too.

The honest caveat, stated on the page: this is the whole Ottawa IESO zone, not
downtown, and it is dominated by weather (heating and air-conditioning), not
occupancy. That's why the output also carries the weekend office-hours mean —
the weekday/weekend *ratio* cancels most of the weather signal, and is the
number worth reading.
"""

import csv
import io

from common import RTO4_DATE, fetch, mean, parse_iso, week_start, write_json

URL = "https://reports-public.ieso.ca/public/DemandZonal/PUB_DemandZonal_{year}.csv"
YEARS = [2023, 2024, 2025, 2026]

OFFICE_HOURS = range(9, 18)      # IESO hour 1 = 00:00-01:00, so hour h covers h-1:00


def load_year(year, buckets):
    raw = fetch(URL.format(year=year)).decode("utf-8", "replace")
    rdr = csv.reader(io.StringIO(raw))
    header = None
    for row in rdr:
        if not row or row[0].startswith("\\"):
            continue                                  # IESO comment preamble
        if header is None:
            header = [c.strip() for c in row]
            i_date, i_hour, i_ott = header.index("Date"), header.index("Hour"), header.index("Ottawa")
            continue
        if len(row) <= i_ott:
            continue
        d = parse_iso(row[i_date])
        if not d:
            continue
        try:
            hour, mw = int(row[i_hour]), float(row[i_ott])
        except ValueError:
            continue
        # IESO labels the hour *ending*, so hour 10 is 09:00-10:00 local.
        if hour - 1 not in OFFICE_HOURS:
            continue
        b = buckets.setdefault(week_start(d), {"weekday": [], "weekend": []})
        b["weekday" if d.weekday() < 5 else "weekend"].append(mw)
    print(f"  {year}: {sum(len(v['weekday']) + len(v['weekend']) for v in buckets.values()):,} office hours so far")


def main():
    buckets = {}
    for y in YEARS:
        load_year(y, buckets)

    series = []
    for wk in sorted(buckets):
        b = buckets[wk]
        wd, we = mean(b["weekday"], 0), mean(b["weekend"], 0)
        # Require a full working week before reporting, so partial weeks at the
        # edges of the data don't show up as dips.
        if wd is None or len(b["weekday"]) < 5 * len(OFFICE_HOURS):
            continue
        series.append({
            "week": wk,
            "weekday_mw": wd,
            "weekend_mw": we,
            "ratio": round(wd / we, 3) if we else None,
        })

    rto_week = week_start(RTO4_DATE)
    before = [s for s in series if s["week"] < rto_week][-6:]
    after = [s for s in series if s["week"] >= rto_week][:6]

    write_json("ieso_ottawa_weekly.json", {
        "source": URL.format(year="<year>"),
        "zone": "Ottawa",
        "office_hours_local": "09:00-18:00",
        "rto4_week": rto_week,
        "note": ("Whole-zone load, weather-dominated. Read the weekday/weekend "
                 "ratio, not the absolute MW."),
        "summary": {
            "before_ratio": mean([s["ratio"] for s in before], 3),
            "after_ratio": mean([s["ratio"] for s in after], 3),
            "weeks_before": len(before),
            "weeks_after": len(after),
        },
        "weeks": series,
    })


if __name__ == "__main__":
    main()

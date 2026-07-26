#!/usr/bin/env python3
"""Aggregate Ottawa 311 service requests into weekly counts for the RTO4 page.

Source: two rolling CSVs on the City's blob store — current year and previous
year (~35 MB each), refreshed daily. We stream them, bucket every request by
the Monday of its "Opened Date", and keep only small per-week totals.

Why this matters for RTO4: the previous-year file gives a genuine 2025 baseline
for the same calendar weeks, so the road/parking complaint curve can be read
before vs after Jul 6, 2026 *and* against the year before. That is rare among
the datasets available here — most City transportation data is annual.

Caveats worth knowing when reading the output:
  * These are *complaints*, not conditions. Volume tracks reporting behaviour
    as much as road state.
  * "Opened Date" is a date, not a timestamp — daily resolution is the floor.
  * The current-year file is a rolling snapshot: the most recent week or two
    is usually incomplete, so the page drops the final partial week.
"""

import csv
import io

from common import RTO4_DATE, mean, parse_iso, week_start, write_json, fetch

BASE = "https://311opendatastorage.blob.core.windows.net/311data"
FILES = {
    "current": f"{BASE}/311opendata_currentyear.csv",
    "previous": f"{BASE}/311opendata_lastyear.csv",
}

# The `Type` column is a bilingual service-area label. These are the ones that
# move when more people drive and park downtown every day.
CATEGORIES = {
    "roads": "Roads and Transportation",
    "parking": "Parking Control Enforcement",
    "bylaw": "Bylaw Services",
    "garbage": "Garbage and Recycling",
}

# Central wards — Somerset (14) and Rideau-Vanier (12) hold most of the federal
# office core; Kitchissippi (15) and Capital (17) are the inner commuter belt.
DOWNTOWN_WARDS = {"12", "14", "15", "17"}


def col(header, want):
    """Find a column index by its English label (headers are 'EN | FR')."""
    for i, h in enumerate(header):
        if h.split("|")[0].strip().lstrip("﻿").lower() == want.lower():
            return i
    raise KeyError(f"column {want!r} not found in {header}")


def tally(url, weeks):
    raw = fetch(url).decode("utf-8-sig", "replace")
    rdr = csv.reader(io.StringIO(raw))
    header = next(rdr)
    i_type, i_open, i_ward = col(header, "Type"), col(header, "Opened Date"), col(header, "Ward")
    label_to_key = {v: k for k, v in CATEGORIES.items()}

    n = 0
    for row in rdr:
        if len(row) <= max(i_type, i_open, i_ward):
            continue
        d = parse_iso(row[i_open])
        if not d:
            continue
        wk = weeks.setdefault(
            week_start(d),
            {"week": week_start(d), "total": 0, "downtown_total": 0,
             **{k: 0 for k in CATEGORIES}},
        )
        wk["total"] += 1
        ward = (row[i_ward] or "").strip()
        if ward in DOWNTOWN_WARDS:
            wk["downtown_total"] += 1
        key = label_to_key.get((row[i_type] or "").strip())
        if key:
            wk[key] += 1
        n += 1
    print(f"  {url.rsplit('/', 1)[-1]}: {n:,} requests")


def main():
    weeks = {}
    for name, url in FILES.items():
        tally(url, weeks)

    series = [weeks[k] for k in sorted(weeks)]
    # Drop the trailing partial week — the rolling file is mid-week most days
    # and a half-counted week reads as a cliff on the chart.
    if len(series) > 1:
        series = series[:-1]

    # A like-for-like summary: the 6 full weeks before Jul 6 2026 vs the weeks after.
    rto_week = week_start(RTO4_DATE)
    before = [w for w in series if w["week"] < rto_week][-6:]
    after = [w for w in series if w["week"] >= rto_week][:6]

    def avg(rows, key):
        return mean([r[key] for r in rows]) if rows else None

    summary = {
        key: {
            "before_weekly_avg": avg(before, key),
            "after_weekly_avg": avg(after, key),
            "weeks_before": len(before),
            "weeks_after": len(after),
        }
        for key in list(CATEGORIES) + ["total", "downtown_total"]
    }

    write_json("311_weekly.json", {
        "source": FILES,
        "categories": CATEGORIES,
        "downtown_wards": sorted(DOWNTOWN_WARDS),
        "rto4_week": rto_week,
        "summary": summary,
        "weeks": series,
    })


if __name__ == "__main__":
    main()

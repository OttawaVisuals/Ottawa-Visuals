#!/usr/bin/env python3
"""Ottawa bicycle trip counters -> weekly totals, 2019 to present.

Source: Open Ottawa "Bicycle Trip Counters" (Excel, one sheet per year
2010-2026, one column per counter, one row per day).

**Read this before using the output for RTO4.** Verified against the live file
on 2026-07-25: the 2026 sheet ends **Mar 31, 2026** and only the ADAWE
counters report that year (LMET, OGLD and OBVW all stop after 2025). So this
dataset cannot show anything after Jul 6, 2026 — it is a pre-RTO4 baseline,
nothing more, and the page must label it that way. `coverage_end` and
`counters_reporting` are emitted so the page can state the staleness itself
rather than drawing a flat line off the end of the data.

Because the reporting counter set shrinks over time, a raw cross-year `total`
is not comparable. The trustworthy series is ADAWE alone — the Adàwe Crossing
over the Rideau River, which reports continuously from 2021 through Mar 2026.
`total` is still emitted, but always alongside `counters_reporting`.

Counters referenced:
  * ADAWE  — Adàwe Crossing (continuous; the series worth reading)
  * LMET   — Laurier at Metcalfe, the downtown segregated lane (ends 2025)
Column headers carry prefixes and split sub-counters (12a/12b ADAWE), so
counters are matched on their name fragment and summed.
"""

import re

from common import RTO4_DATE, fetch, mean, week_start, write_json

XLSX = "https://www.arcgis.com/sharing/rest/content/items/f218592c7fe74788906cc6a0eb190af9/data"
FIRST_YEAR = 2019

FEATURED = {"adawe": "ADAWE", "lmet": "LMET"}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def parse_day(cell, year):
    """'Thu Jan 1, 2026' or '2026-01-01' -> (year, month, day) or None."""
    s = str(cell).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})", s)
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    y = int(re.search(r"(\d{4})", s).group(1)) if re.search(r"(\d{4})", s) else year
    return y, mon, int(m.group(2))


def main():
    from common import read_xlsx
    from datetime import date

    sheets = read_xlsx(fetch(XLSX))
    weeks = {}

    for sheet, rows in sheets.items():
        if not re.fullmatch(r"\d{4}", sheet.strip()) or int(sheet) < FIRST_YEAR:
            continue
        year = int(sheet)
        if not rows:
            continue
        header = [str(c) for c in rows[0]]
        # Which columns belong to which featured counter, and which are counters at all.
        featured_cols = {
            key: [i for i, h in enumerate(header) if frag.lower() in h.lower()]
            for key, frag in FEATURED.items()
        }
        count_cols = list(range(1, len(header)))

        for row in rows[1:]:
            if not row or not str(row[0]).strip():
                continue
            ymd = parse_day(row[0], year)
            if not ymd:
                continue
            try:
                d = date(*ymd)
            except ValueError:
                continue
            if d.year != year:
                continue

            def val(i):
                if i >= len(row):
                    return None
                s = str(row[i]).strip()
                if not s:
                    return None
                try:
                    return int(round(float(s)))
                except ValueError:
                    return None

            allv = [val(i) for i in count_cols]
            allv = [v for v in allv if v is not None]
            if not allv:
                continue

            wk = weeks.setdefault(week_start(d), {
                "week": week_start(d), "total": 0, "days": 0,
                "counters_reporting": 0, **{k: 0 for k in FEATURED},
            })
            wk["total"] += sum(allv)
            wk["days"] += 1
            wk["counters_reporting"] = max(wk["counters_reporting"], len(allv))
            for key, cols in featured_cols.items():
                wk[key] += sum(v for v in (val(i) for i in cols) if v is not None)

    # Only keep complete weeks — the counter set changes between years and a
    # 3-day week would read as a collapse in ridership.
    series = [weeks[k] for k in sorted(weeks) if weeks[k]["days"] == 7]

    rto_week = week_start(RTO4_DATE)
    after = [s for s in series if s["week"] >= rto_week]
    coverage_end = series[-1]["week"] if series else None

    # Same six calendar weeks, this year vs last, on the one counter that
    # reports continuously. This is the only cross-year comparison the data
    # actually supports.
    def adawe_weeks(year, month_from, month_to):
        return [s["adawe"] for s in series
                if s["week"][:4] == str(year) and month_from <= s["week"][5:7] <= month_to]

    write_json("bike_weekly.json", {
        "source": "Open Ottawa — Bicycle Trip Counters (Excel)",
        "source_url": "https://open.ottawa.ca/datasets/ottawa::bicycle-trip-counters",
        "featured": FEATURED,
        "rto4_week": rto_week,
        "coverage_end": coverage_end,
        "covers_rto4": bool(after),
        "trusted_series": "adawe",
        "note": ("The counter set shrinks over time — in 2026 only ADAWE reports — so "
                 "cross-year comparisons must use the 'adawe' series, not 'total'. "
                 "Always read counters_reporting before reading a level change."),
        "caveat_rto4": ("Coverage ends " + str(coverage_end) + ", before Jul 6 2026. "
                        "This is a pre-RTO4 baseline only; it cannot show RTO4."),
        "summary": {
            "adawe_jan_mar_2025": mean(adawe_weeks(2025, "01", "03"), 0),
            "adawe_jan_mar_2026": mean(adawe_weeks(2026, "01", "03"), 0),
            "weeks_after_rto4": len(after),
        },
        "weeks": series,
    })


if __name__ == "__main__":
    main()

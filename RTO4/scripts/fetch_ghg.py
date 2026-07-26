#!/usr/bin/env python3
"""City of Ottawa GHG inventory (2012-2024) -> RTO4/data/ghg_inventory.json.

Source: Open Ottawa "Greenhouse gas (GHG) emissions inventories 2024" —
11 rows (population + corporate and community sectors), one column per
inventory year.

Read the granularity before reading the chart: this is **annual, city-wide**
and the latest year is **2024**. It therefore says nothing directly about
RTO4 (Jul 2026) and cannot. What it does show is the trend RTO4 lands on top
of: community transportation emissions in 2024 were already above their 2012
level and well above the 2020 low. The page states this limit plainly and
labels the RTO4 commute figure as a derived estimate, not a measurement.
"""

from common import arcgis_query, write_json

LAYER = "Greenhouse_gas_(GHG)_emissions_inventories_2024"
PREFIX = "GHG Emissions (tonnes of CO2e) - "


def main():
    rows = arcgis_query(LAYER)
    years, series = set(), {}

    for r in rows:
        label = (r.get("Year") or "").strip()
        if not label:
            continue
        vals = {}
        for k, v in r.items():
            if len(k) == 5 and k.startswith("F") and k[1:].isdigit() and v is not None:
                y = int(k[1:])
                vals[y] = v
                years.add(y)
        if not vals:
            continue
        if label.startswith(PREFIX):
            name = label[len(PREFIX):].strip()
            scope = "corporate" if "(Corporate)" in name else "community"
            sector = name.replace("(Corporate)", "").replace("(Community)", "").strip()
            key = f"{scope}:{sector.lower()}"
        else:
            key = "population"
            scope, sector = "context", label
        series[key] = {"scope": scope, "sector": sector, "by_year": vals}

    write_json("ghg_inventory.json", {
        "source": "Open Ottawa — Greenhouse gas (GHG) emissions inventories 2024",
        "source_url": f"https://open.ottawa.ca/search?q=greenhouse%20gas",
        "granularity": "annual, city-wide",
        "latest_year": max(years) if years else None,
        "caveat": ("Annual and city-wide, latest inventory year 2024 — predates "
                   "RTO4 by 18 months. Context for the trend, not evidence about RTO4."),
        "years": sorted(years),
        "series": series,
    })


if __name__ == "__main__":
    main()

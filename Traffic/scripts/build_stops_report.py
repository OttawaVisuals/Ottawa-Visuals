#!/usr/bin/env python3
"""Build the Power-BI-free stops report. --refresh checks official sources and
fetches monthly stop totals; other inputs come from fetch_city_traffic.py.
Stdlib only. Never sum the overlapping police area/time/driver rollups together.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import fetch_city_traffic as source

DATA = source.ROOT / "data"
OUT = DATA / "derived" / "stops_report"
AUDIT = OUT / "sources.json"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"  {path.relative_to(source.ROOT)}: {path.stat().st_size:,} bytes", flush=True)


def number(value):
    return None if value in (None, "") else float(value)


def refresh():
    print("Checking official catalogues and retrieving monthly stops...", flush=True)
    services = source.get_json(source.CITY, {}).get("services", [])
    catalogue = source.get_json("https://www.arcgis.com/sharing/rest/search", {
        "q": "orgid:2vhcNzw0NfUwAD3d (traffic OR collision)", "num": 100,
        "sortField": "modified", "sortOrder": "desc",
    })
    stop_years = source.query_stats(source.OPS, source.STOPS, ["occ_year"], source.COUNT)
    collision_years = source.query_stats(source.CITY, source.COLLISION_LAYERS[0], ["Accident_Year"], source.COUNT)
    # Use original dates to recover monthly totals without downloading raw stops.
    daily = source.lower_keys(source.query_stats(
        source.OPS, source.STOPS, ["occ_year", "occ_date", "how_cleared"], source.COUNT))
    monthly = Counter()
    for row in daily:
        date = source.iso_date(row["occ_date"])
        if not date or int(date[:4]) != row["occ_year"]:
            raise ValueError(f"Missing/inconsistent stop date: {row}")
        monthly[(int(row["occ_year"]), int(date[5:7]), row["how_cleared"] or "Unknown")] += row["n"]
    actual = Counter()
    for (year, month, outcome), n in monthly.items():
        actual[year] += n
    expected = {r["occ_year"]: r["n"] for r in stop_years}
    if dict(actual) != expected:
        raise ValueError(f"Monthly police totals disagree with annual source totals: {dict(actual)} != {expected}")
    source.write_csv(DATA / "police/traffic_stops_monthly.csv", ["year", "month", "how_cleared", "n"],
                     [dict(year=y, month=m, how_cleared=o, n=n) for (y, m, o), n in sorted(monthly.items())])
    # Verify the cached detailed records, not just catalogue modification dates.
    local_stops = Counter()
    for row in read(DATA / "police/traffic_stops_by_time.csv"):
        local_stops[int(row["occ_year"])] += int(row["n"])
    local_collisions = {int(p.stem): len(read(p)) for p in (DATA / "city/collisions").glob("*.csv")}
    if dict(local_stops) != expected:
        raise ValueError("Police source has changed: refresh --only police before rebuilding")
    if local_collisions != {r["Accident_Year"]: r["n"] for r in collision_years}:
        raise ValueError("Detailed collision source has changed: refresh --only collisions before rebuilding")
    write(AUDIT, {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "police": {"url": source.layer_url(source.OPS, source.STOPS), "year_counts": expected},
        "collisions": {"url": source.layer_url(source.CITY, source.COLLISION_LAYERS[0]), "year_counts": local_collisions},
        "city_services": [s["name"] for s in services if any(t in s["name"].lower() for t in ["collision", "camera"])],
        "ops_publications": [{k: r.get(k) for k in ["id", "title", "type", "modified"]}
                             for r in catalogue.get("results", []) if r.get("type") in ("PDF", "Feature Service")],
        "ase_end": "2025-11-14",
        "ase_end_url": "https://ottawa.ca/en/city-hall/city-news/newsroom/changes-coming-automated-speed-enforcement",
    })


def police():
    time = read(DATA / "police/traffic_stops_by_time.csv")
    years = sorted({int(r["occ_year"]) for r in time})
    annual, weekdays, hourly = Counter(), Counter(), Counter()
    for row in time:
        annual[(int(row["occ_year"]), row["how_cleared"])] += int(row["n"])
        weekdays[(int(row["occ_year"]), row["dow"], row["how_cleared"])] += int(row["n"])
        # Despite the field name, OPS encodes the hour as HH00 (100, 1400...).
        hour = str(int(row["hour"]) // 100) if row["hour"] else "Unknown"
        if hour != "Unknown" and (int(row["hour"]) % 100 or not 0 <= int(hour) <= 23):
            raise ValueError(f"Unexpected OPS hour encoding: {row['hour']}")
        hourly[(int(row["occ_year"]), hour, row["how_cleared"])] += int(row["n"])
    drivers = read(DATA / "police/traffic_stops_by_driver.csv")
    areas = read(DATA / "police/traffic_stops_by_area.csv")
    totals = {y: sum(n for (yr, _), n in annual.items() if yr == y) for y in years}
    for name, rows in [("driver", drivers), ("area", areas)]:
        check = Counter()
        for row in rows:
            check[int(row["occ_year"])] += int(row["n"])
        if dict(check) != totals:
            raise ValueError(f"{name} rollup does not reconcile to police annual totals")
    locations = read(DATA / "police/traffic_stops_by_location.csv")
    assert sum(int(r["n"]) for r in locations) == sum(totals.values())
    monthly = read(DATA / "police/traffic_stops_monthly.csv")
    monthly_check = Counter()
    for row in monthly:
        monthly_check[(int(row["year"]), row["how_cleared"])] += int(row["n"])
    if monthly_check != annual:
        raise ValueError("Monthly stop totals disagree with annual outcome totals; run --refresh")
    return {
        "years": years,
        "annual": [[y, o, n] for (y, o), n in sorted(annual.items())],
        "monthly": [[int(r["year"]), int(r["month"]), r["how_cleared"], int(r["n"])]
                    for r in monthly],
        "weekdays": [[y, d, o, n] for (y, d, o), n in sorted(weekdays.items())],
        "hourly": [[y, h, o, n] for (y, h, o), n in sorted(hourly.items())],
        "drivers": [[int(r["occ_year"]), r["age_range"] or "Unknown", r["driver_gender"] or "Unknown",
                     r["driver_race"] or "Unknown", r["how_cleared"], int(r["n"])] for r in drivers],
        "areas": [[int(r["occ_year"]), r["neighbourhood"] or "Unknown", r["how_cleared"], int(r["n"])] for r in areas],
        "locations": [[r["location"], number(r["lat"]), number(r["lon"]), int(r["n"]), int(r["n_charged"])]
                      for r in locations if r["lat"] and r["lon"]],
        "unmapped_stops": sum(int(r["n"]) for r in locations if not r["lat"] or not r["lon"]),
    }


def collisions():
    nodes = {r["geo_id"]: r for r in read(DATA / "derived/geo_index.csv")}
    result = []
    for path in sorted((DATA / "city/collisions").glob("*.csv")):
        year = int(path.stem)
        groups, points = {}, Counter()
        for row in read(path):
            node = nodes.get(row["geo_id"], {})
            ward = node.get("ward") or "Unknown / outside ward match"
            if ward not in groups:
                groups[ward] = {"year": year, "ward": ward, "total": 0, "severity": Counter(),
                                "impact": Counter(), "participants": Counter(), "injuries": 0, "fatalities": 0,
                                "missing_injuries": 0, "missing_fatalities": 0}
            g = groups[ward]
            g["total"] += 1
            g["severity"][row["severity"] or "Unknown"] += 1
            g["impact"][row["impact_type"] or "Unknown"] += 1
            for field in ["vehicles", "pedestrians", "bicycles", "motorcycles"]:
                g["participants"][field] += int(row[field] or 0)
            for field in ["injuries", "fatalities"]:
                g[field] += int(row[field] or 0)
                g["missing_" + field] += int(not row[field])
            if row["lat"] and row["lon"]:
                points[(row["location"], round(float(row["lat"]), 5), round(float(row["lon"]), 5), ward)] += 1
        result.extend(groups.values())
        write(OUT / f"collisions-{year}.json", [[*key, n] for key, n in points.items()])
    return result


def cameras(filename, speed=False):
    rows = read(DATA / "city" / filename)
    sites, index, months = [], {}, []
    for row in rows:
        key = row["site_id"] if speed else row["location"] + " | " + row["camera_facing"]
        if key not in index:
            index[key] = len(sites)
            sites.append({"id": key, "name": row["location"], "direction": "" if speed else row["camera_facing"],
                          "lat": number(row["lat"]), "lon": number(row["lon"])})
        months.append([int(row["year"]), int(row["month"]), index[key], int(row["violations"])])
    assert len({tuple(r[:3]) for r in months}) == len(months), "Duplicate camera-month"
    return {"sites": sites, "months": months}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    if args.refresh:
        refresh()
    if not AUDIT.exists():
        raise SystemExit("Run once with --refresh to verify coverage and fetch monthly stops")
    report = {"built_utc": datetime.now(timezone.utc).isoformat(), "police": police(), "collisions": collisions(),
              "redlight": cameras("red_light_violations.csv"), "speed": cameras("ase_violations.csv", True)}
    report["speeds"] = [[r["site_id"], r["date"], number(r["avg_speed"]), number(r["pct85_speed"]),
                         number(r["pct_compliance"])] for r in read(DATA / "city/ase_monthly_speeds.csv")]
    report["monitoring"] = [{**r, **{k: number(r[k]) for k in ["avg_speed", "pct85_speed", "pct_compliance", "pct_high_end_speeders"]}}
                            for r in read(DATA / "city/ase_removal_monitoring.csv")]
    # Manually transcribed from the official OPS images and visually checked
    # Oct 18 2026. These are incidents, NOT people. Never splice into City data.
    report["snapshots"] = [
        {"label": "2025 year-end", "source": "https://www.arcgis.com/sharing/rest/content/items/9f84ce557ba4438cbcdfc46fc077a0ec/data",
         "period": "Full year 2025 vs full year 2024", "labels": ["2024", "2025"],
         "metrics": {"Total collisions": [19780, 20650], "Officer-attended": [2990, 3150], "Self-reported": [16790, 17500]},
         "note": "OPS reports 22 fatal-injury incidents in 2025 (officer-attended only); this is not a count of people killed."},
        {"label": "2026 year to date", "source": "https://www.arcgis.com/sharing/rest/content/items/6b5baf7f169f40b1ad19301a143f965b/data",
         "period": "January 1–September 19: 2025 vs 2026", "labels": ["2025 YTD", "2026 YTD"],
         "metrics": {"Total collisions": [14610, 14370], "Fatal collisions": [13, 23], "Collisions causing injury": [936, 817],
                     "Pedestrian-involved": [218, 164], "Cyclist-involved": [164, 124], "Tickets & warnings": [24640, 32520]},
         "note": "Same cutoff in both years. Severity figures cover officer-attended collisions. Tickets and warnings are not traffic-stop records; multiple actions can follow one stop."},
    ]
    write(OUT / "report.json", report)
    print("All police rollups reconcile. Camera-month keys are unique.")


if __name__ == "__main__":
    main()

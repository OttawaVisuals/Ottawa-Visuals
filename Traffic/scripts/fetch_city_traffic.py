#!/usr/bin/env python3
"""Pull the City of Ottawa + Ottawa Police static traffic datasets into tidy CSVs.

Companion to poll_traffic.py: TomTom gives us live congestion, these give the
context around it -- where collisions happen, how much traffic each road
carries, and where enforcement (cameras, police stops) lands.

  City of Ottawa open data (ArcGIS Online org G6F8XLCl5KtAlZ2G):
    * collisions/<year>.csv     -- every reported collision 2017-2024 (2023 is
                                   missing from the city's own release)
    * intersection_volumes.csv  -- AADT counts at intersections, 2015-2025
    * midblock_volumes.csv      -- AADT on road segments, 2022-2025
    * red_light_violations.csv  -- monthly violations per camera, 2015-2026
    * ase_violations.csv        -- monthly photo-radar tickets per camera, 2020-2025
    * ase_monthly_speeds.csv    -- monthly avg/85th speed at every ASE site
    * covid_volumes.csv         -- 2020-21 volume-vs-baseline % (intersections + bridge)
    * bike_counters.csv         -- daily counts from the permanent bike counters

  Ottawa Police Community Safety Data portal (org 2vhcNzw0NfUwAD3d):
    Raw files are 455K stops / 1.1M calls -- too big to commit -- so these are
    aggregated server-side (ArcGIS outStatistics) and only the rollups land here.
    * traffic_stops_by_area.csv / _by_time.csv / _by_driver.csv / _by_location.csv
    * calls_by_area.csv / calls_by_time.csv

The city republishes some layers under new names each year; when a new year
appears, add it to the layer lists below (see the service directory at
https://services.arcgis.com/G6F8XLCl5KtAlZ2G/ArcGIS/rest/services).

Stdlib only except openpyxl (bike counters arrive as .xlsx).
Usage: fetch_city_traffic.py [--only collisions,bike_counters,...]
"""

import argparse
import csv
import io
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # the Traffic/ directory
CITY_OUT = ROOT / "data" / "city"
POLICE_OUT = ROOT / "data" / "police"

CITY = "https://services.arcgis.com/G6F8XLCl5KtAlZ2G/ArcGIS/rest/services"
OPS = "https://services7.arcgis.com/2vhcNzw0NfUwAD3d/arcgis/rest/services"
BIKE_XLSX = "https://www.arcgis.com/sharing/rest/content/items/f218592c7fe74788906cc6a0eb190af9/data"

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# Police stop locations seen fewer times than this are rolled into one
# "(other)" row -- the long tail is ~80K one-off street addresses.
MIN_STOPS_PER_LOCATION = 3


# --------------------------------------------------------------------------
# ArcGIS REST helpers
# --------------------------------------------------------------------------

def get_json(url, params, tries=4):
    qs = urllib.parse.urlencode({**params, "f": "json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(f"{url}?{qs}", timeout=120) as r:
                d = json.load(r)
            if "error" in d:
                raise RuntimeError(f"{url}: {d['error']}")
            return d
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))


def layer_url(base, service):
    return f"{base}/{urllib.parse.quote(service)}/FeatureServer/0"


def query_all(base, service, where="1=1"):
    """Every feature of a layer as attribute dicts, plus _lat/_lon from geometry."""
    url = layer_url(base, service)
    info = get_json(url, {})
    oid = info["objectIdField"]
    page = info.get("maxRecordCount") or 1000
    rows, offset = [], 0
    while True:
        d = get_json(f"{url}/query", {
            "where": where, "outFields": "*", "outSR": 4326,
            "returnGeometry": "true", "orderByFields": oid,
            "resultOffset": offset, "resultRecordCount": page,
        })
        for f in d["features"]:
            a = dict(f["attributes"])
            g = f.get("geometry") or {}
            a["_lat"], a["_lon"] = g.get("y"), g.get("x")
            rows.append(a)
        if len(d["features"]) < page and not d.get("exceededTransferLimit"):
            break
        offset += len(d["features"])
    return rows


def query_stats(base, service, group_by, stats, where="1=1"):
    """Server-side GROUP BY. stats = [(type, field, out_name), ...]."""
    url = layer_url(base, service)
    out_stats = json.dumps([{"statisticType": t, "onStatisticField": f,
                             "outStatisticFieldName": n} for t, f, n in stats])
    rows, offset = [], 0
    while True:
        d = get_json(f"{url}/query", {
            "where": where, "groupByFieldsForStatistics": ",".join(group_by),
            "outStatistics": out_stats, "orderByFields": ",".join(group_by),
            "resultOffset": offset, "resultRecordCount": 2000,
        })
        rows += [f["attributes"] for f in d["features"]]
        if len(d["features"]) < 2000:
            break
        offset += 2000
    return rows


# --------------------------------------------------------------------------
# Value cleanup
# --------------------------------------------------------------------------

def num(v):
    """'48' -> 48, '1.72%' -> 1.72, 'N/A'/''/None -> None."""
    if v is None or isinstance(v, (int, float)):
        return v
    s = str(v).strip().rstrip("%").replace(",", "")
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


DATE_FORMATS = ["%Y-%m-%d", "%d-%b-%y", "%d-%b-%Y", "%m/%d/%Y", "%Y/%m/%d",
                "%a %b %d, %Y", "%a %d %b %Y", "%b-%y", "%B %d, %Y"]


def iso_date(v):
    """Epoch-ms or any of the city's string formats -> YYYY-MM-DD (raw if unknown)."""
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000, tz=timezone.utc).date().isoformat()
    s = str(v).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return s


def mtm9_to_latlon(x, y):
    """NAD83 MTM zone 9 (the X/Y the city and police publish) -> WGS84 lat/lon.

    Inverse transverse Mercator (Snyder 1987, eq. 8-18..8-25) on GRS80,
    central meridian 76.5 W, k0 0.9999, false easting 304800 m. Good to well
    under a metre across Ottawa, which is far finer than the source geocoding.
    """
    if x is None or y is None:
        return None, None
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0, lon0, fe = 0.9999, math.radians(-76.5), 304800.0
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu))
    c1 = ep2 * math.cos(phi1) ** 2
    t1 = math.tan(phi1) ** 2
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d = (x - fe) / (n1 * k0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = lon0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6
                  + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120
                  ) / math.cos(phi1)
    return round(math.degrees(lat), 6), round(math.degrees(lon), 6)


def rnd(v, n=6):
    return round(v, n) if isinstance(v, float) else v


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path.relative_to(ROOT)}  ({len(rows):,} rows)")


# --------------------------------------------------------------------------
# City of Ottawa datasets
# --------------------------------------------------------------------------

COLLISION_LAYERS = ["Traffic_Collisions_by_Location_2017-2024_(excluding_2023)"]


def code(v):
    """'03 - Rear end' -> 'Rear end' (the numeric prefix is just the MTO code)."""
    if not isinstance(v, str):
        return v
    return re.sub(r"^\s*\d+\s*-\s*", "", v).strip()


def fetch_collisions():
    fields = ["id", "geo_id", "date", "year", "location", "lat", "lon",
              "severity", "impact_type", "surface", "environment", "light",
              "traffic_control", "vehicles", "pedestrians", "bicycles",
              "motorcycles", "max_injury", "injuries", "major_injuries", "fatalities"]
    out = []
    for layer in COLLISION_LAYERS:
        for a in query_all(CITY, layer):
            out.append({
                "id": a.get("ID"), "geo_id": a.get("Geo_ID"),
                "date": iso_date(a.get("Accident_Date")), "year": a.get("Accident_Year"),
                # Location repeats the Geo_ID in brackets; it has its own column.
                "location": re.sub(r"\s*\([^)]*\)\s*$", "", a.get("Location") or "").strip(),
                "lat": rnd(a.get("Lat"), 5), "lon": rnd(a.get("Long"), 5),
                "severity": code(a.get("Classification_Of_Accident")),
                "impact_type": code(a.get("Initial_Impact_Type")),
                "surface": code(a.get("Road_1_Surface_Condition")),
                "environment": code(a.get("Environment_Condition")),
                "light": code(a.get("Light")),
                "traffic_control": code(a.get("Traffic_Control")),
                "vehicles": num(a.get("num_of_vehicles")),
                "pedestrians": num(a.get("num_of_pedestrians")),
                "bicycles": num(a.get("num_of_bicycles")),
                "motorcycles": num(a.get("num_of_motorcycles")),
                "max_injury": a.get("Max_injury"),
                "injuries": num(a.get("num_of_injuries")),
                "major_injuries": num(a.get("num_of_major")),
                "fatalities": num(a.get("num_of_fatal")),
            })
    # One file per year (~2 MB each) so pages load only the years they chart.
    out.sort(key=lambda r: (r["date"] or "", r["id"] or ""))
    for year in sorted({r["year"] for r in out}):
        write_csv(CITY_OUT / "collisions" / f"{year}.csv", fields,
                  [r for r in out if r["year"] == year])


# Each year's layer uses its own column names; map them onto one schema.
# (layer, year, {out_field: src_field})
INTERSECTION_LAYERS = [
    ("Transportation_Intersection_Volumes_2015", 2015,
     dict(intersection="Intersecti", aadt="All_Motori", pct_trucks="F__Trucks",
          pedestrians="Pedestrian", cyclists="Bicycles_N", study_date="Data_Colle")),
    ("Transportation_Intersection_Volumes_2016", 2016,
     dict(intersection="Intersecti", aadt="All_Motori", pct_trucks="F__Truck",
          pedestrians="Pedestrian", cyclists="Cyclist_No", study_date="Data_Colle")),
    ("Transportation_Intersection_Volumes_2017", 2017,
     dict(intersection="Intersecti", aadt="All_Motori", pct_trucks="F__Truck",
          pedestrians="Pedestrian", cyclists="Bicycles_N", study_date="Data_Colle")),
    ("Transportation_Intersection_Volumes_2018", 2018,
     dict(intersection="Intersecti", aadt="All_Motori", pct_trucks="F__Truck",
          pedestrians="Pedestrian", cyclists="Bicycles_N", study_date="Data_Colle")),
    ("Transportation_Intersection_Volumes_2019", 2019,
     dict(intersection="Intersection", aadt="All_Motorized_Vehicles_AADT_24Hour_Volume",
          pct_trucks="Percent_Trucks", pedestrians="Pedestrians_Not_Factored",
          cyclists="Bicycles_Not_Factored", study_date="Date_Collected")),
    # No 2020 layer (COVID year). Two identical 2021 layers exist; one is enough.
    ("Transportation_Intersection_Volumes_2021", 2021,
     dict(intersection="Intersection", aadt="All_Motorized_Vehicles_AADT_24H",
          pct_trucks="Percent_Trucks", pedestrians="Pedestrians_Not_Factored",
          cyclists="Bicycles_Not_factored", study_date="Date_Collected")),
    ("Intersection_Volume_2022_w_lat_long", 2022,
     dict(intersection="Intersection", aadt="All_Motorized_Vehicles_AADT_24_",
          pct_trucks="Truck_Percent", pedestrians="Pedestrians_Not_Factored",
          cyclists="Bicycles_Not_Factored", study_date="Date")),
    ("Transportation_Intersection_Volume_2023", 2023,
     dict(intersection="Intersection", aadt="All_Motorized_Vehicles_AADT_24_",
          pct_trucks="Truck_Percent", pedestrians="Pedestrians_Not_Factored",
          cyclists="Bicycles_Not_Factored", study_date="Date")),
    ("Transportation_Intersection_Volumes_2024", 2024,
     dict(geo_id="Geo_ID", intersection="Intersection", aadt="All_Motori",
          pct_trucks="Truck_Perc", pedestrians="Pedestrian", cyclists="Bicycles_N",
          study_date="Study_Date")),
    # 2025 switched to raw study counts + a 24h-adjusted total.
    ("Transportation_Intersection_Volume_2025", 2025,
     dict(geo_id="Geo_ID", intersection="Intersection", aadt="Total_Adjusted_Volume__24h_",
          pct_trucks="Total_Truck__", pedestrians="Total_Pedestrians",
          cyclists="Total_Cyclists", study_date="Study_Date")),
]

# Years whose truck share is published as a 0-1 fraction rather than a percent.
TRUCKS_AS_FRACTION = {2019, 2021, 2022, 2023, 2025}

MIDBLOCK_LAYERS = [
    ("Midblock_Volume_2022_w_lat_long", 2022,
     dict(geo_id="Geo_ID", midblock="Midblock", aadt="All_Motorized_Vehicles_AADT_24_")),
    ("Transportation_Midblock_Volume_2023", 2023,
     dict(geo_id="Geo_ID", midblock="Midblock", aadt="All_Motorized_Vehicles_AADT_24_")),
    ("Transportation_Midblock_Volumes_2024", 2024,
     dict(geo_id="Geo_ID", midblock="Midblock", aadt="Volume")),
    ("Transportation_Midblock_Volume_2025", 2025,
     dict(geo_id="Geo_ID", midblock="Midblock", aadt="AADT_Volume")),
]


def geo_id(v):
    """Geo_IDs arrive as '0004683', 4683, or 'e___2JRR'; zero-pad the numeric ones."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) or str(v).isdigit():
        return f"{int(v):07d}"
    return str(v)


def fetch_volumes():
    fields = ["year", "geo_id", "intersection", "study_date", "lat", "lon",
              "aadt", "pct_trucks", "pedestrians", "cyclists"]
    out = []
    for layer, year, m in INTERSECTION_LAYERS:
        for a in query_all(CITY, layer):
            r = {k: a.get(src) for k, src in m.items()}
            trucks = num(r.get("pct_trucks"))
            if year in TRUCKS_AS_FRACTION and trucks is not None:
                trucks = round(trucks * 100, 2)
            out.append({
                "year": year, "geo_id": geo_id(r.get("geo_id")),
                "intersection": (r["intersection"] or "").strip(),
                "study_date": iso_date(r["study_date"]),
                "lat": rnd(a["_lat"]), "lon": rnd(a["_lon"]),
                "aadt": num(r["aadt"]), "pct_trucks": rnd(trucks, 2),
                "pedestrians": num(r["pedestrians"]), "cyclists": num(r["cyclists"]),
            })
    write_csv(CITY_OUT / "intersection_volumes.csv", fields, out)

    fields = ["year", "geo_id", "midblock", "lat", "lon", "aadt"]
    out = []
    for layer, year, m in MIDBLOCK_LAYERS:
        for a in query_all(CITY, layer):
            out.append({
                "year": year, "geo_id": geo_id(a.get(m["geo_id"])),
                "midblock": (a.get(m["midblock"]) or "").strip(),
                "lat": rnd(a["_lat"]), "lon": rnd(a["_lon"]),
                "aadt": num(a.get(m["aadt"])),
            })
    write_csv(CITY_OUT / "midblock_volumes.csv", fields, out)


# Red-light layers: one per year, upper-case month columns. 2023 has an odd name.
RLC_LAYERS = {y: f"Red_Light_Camera_Violations_{y}" for y in range(2015, 2027)}
RLC_LAYERS[2023] = "Red_Light_Camera_(RLC)_Violations_2023"
ASE_LAYERS = {y: f"Automated_Speed_Enforcement_Camera_Violations_{y}" for y in range(2020, 2026)}


def monthly_long(layer, year, loc_key, extra, upper):
    """Wide (one column per month) -> one row per camera-month. 'N/A' months are dropped."""
    rows = []
    for a in query_all(CITY, layer):
        geom = (a["_lat"], a["_lon"])
        a = {k.upper(): v for k, v in a.items()} if upper else a
        base = {"year": year, "location": (a.get(loc_key) or "").strip(),
                "lat": rnd(a.get("LATITUDE" if upper else "Latitude") or geom[0]),
                "lon": rnd(a.get("LONGITUDE" if upper else "Longitude") or geom[1])}
        base.update({k: a.get(src) for k, src in extra.items()})
        for i, mname in enumerate(MONTHS, 1):
            v = num(a.get(mname.upper() if upper else mname))
            if v is not None:
                rows.append({**base, "month": i, "violations": v})
    return rows


def fetch_cameras():
    fields = ["year", "month", "location", "camera_facing", "install_year",
              "lat", "lon", "violations"]
    out = []
    for year, layer in RLC_LAYERS.items():
        out += monthly_long(layer, year, "INTERSECTION",
                            {"camera_facing": "CAMERA_FACING",
                             "install_year": "CAMERA_INSTALL_YEAR"}, upper=True)
    write_csv(CITY_OUT / "red_light_violations.csv", fields, out)

    fields = ["year", "month", "site_id", "location", "install_year",
              "lat", "lon", "violations"]
    out = []
    for year, layer in ASE_LAYERS.items():
        for r in monthly_long(layer, year, "Location",
                              {"install_year": "Camera_Install_Year"}, upper=False):
            r["site_id"], _, r["location"] = r["location"].partition(" - ")
            out.append(r)
    write_csv(CITY_OUT / "ase_violations.csv", fields, out)

    fields = ["site_id", "location", "install_year", "date", "lat", "lon",
              "avg_speed", "pct85_speed", "pct_compliance", "pct_high_end_speeders"]
    out = []
    for a in query_all(CITY, "Automated_Speed_Enforcement_Camera_Speed_Data1"):
        site, _, loc = (a.get("Location") or "").strip().partition(" - ")
        out.append({
            "site_id": site, "location": loc, "install_year": num(a.get("Camera_Install_Year")),
            "date": iso_date(a.get("Date")),
            "lat": rnd(a.get("Latitude")), "lon": rnd(a.get("Longitude")),
            "avg_speed": num(a.get("AvgSpeed")), "pct85_speed": num(a.get("Pct85th")),
            "pct_compliance": num(a.get("PctCompliance")),
            "pct_high_end_speeders": num(a.get("PctHighEndSpeeders")),
        })
    out.sort(key=lambda r: (r["site_id"], r["date"] or ""))
    write_csv(CITY_OUT / "ase_monthly_speeds.csv", fields, out)


def fetch_covid():
    """Volume as % of a normal-year baseline, by month, during 2020-21."""
    fields = ["year", "month", "location", "is_average", "pct_am", "pct_pm",
              "pct_day", "lat", "lon"]
    out = []
    for layer, loc, day in [("COVID_19_Traffic_Volume_Monitoring_at_Intersections",
                             "INTERSECTION", "F8HR"),
                            ("COVID19_Traffic_Volumes_Mcdonald_Cartier_Bridge",
                             "LOCATION", "F24HR")]:
        for a in query_all(CITY, layer):
            out.append({
                "year": a.get("YEAR"), "month": a.get("MONTH"),
                "location": (a.get(loc) or "").strip(),
                "is_average": a.get("AVERAGE") == "Y",
                "pct_am": num(a.get("AM")), "pct_pm": num(a.get("PM")),
                "pct_day": num(a.get(day)),
                "lat": rnd(a.get("LAT")), "lon": rnd(a.get("LONG")),
            })
    write_csv(CITY_OUT / "covid_volumes.csv", fields, out)


def counter_id(header):
    """'1^ALEX' / '1_ALEX' / '11 OBVW' / '9 OYNG 1' / 'Portage Bridge' -> '1_ALEX' etc."""
    s = str(header).strip()
    m = re.match(r"^(\d+[a-z]?)\s*[\^_ ]\s*([A-Za-z]+)", s)
    if m:
        return f"{m.group(1)}_{m.group(2).upper()}"
    return re.sub(r"\W+", "_", s).upper()


def fetch_bike_counters():
    import openpyxl  # only this dataset needs it

    with urllib.request.urlopen(BIKE_XLSX, timeout=120) as r:
        wb = openpyxl.load_workbook(io.BytesIO(r.read()), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        # 2010-12 sheets carry two header rows (old device names + newer-style
        # '1_ALEX' IDs, in either order); use whichever has the newer IDs.
        heads = [i for i in (0, 1) if i < len(rows) and rows[i] and rows[i][0] == "Date"]
        header_i = max(heads, key=lambda i: sum(
            bool(re.match(r"\d+[a-z]?\s*[\^_ ]", str(h or ""))) for h in rows[i]))
        header = rows[header_i]
        cols = {i: counter_id(h) for i, h in enumerate(header)
                if i > 0 and h and not str(h).startswith("Note")}
        for row in rows[max(heads) + 1:]:
            date = iso_date(row[0]) if row and row[0] else None
            if not date or not re.match(r"\d{4}-\d\d-\d\d$", date):
                continue
            for i, cid in cols.items():
                v = num(row[i]) if i < len(row) else None
                if v is not None:
                    out.append({"date": date, "counter": cid, "count": v})
    out.sort(key=lambda r: (r["date"], r["counter"]))
    write_csv(CITY_OUT / "bike_counters.csv", ["date", "counter", "count"], out)


# --------------------------------------------------------------------------
# Ottawa Police datasets (aggregated server-side)
# --------------------------------------------------------------------------

STOPS = "TSRDCP_TrafficStops_v1"
CALLS = "Calls_For_Service"
COUNT = [("count", "OBJECTID", "n")]


def lower_keys(rows):
    """ArcGIS echoes group-by field names in whatever case it likes."""
    return [{k.lower(): v for k, v in r.items()} for r in rows]


def fetch_police():
    g = ["occ_year", "division", "neighbourhood", "how_cleared"]
    write_csv(POLICE_OUT / "traffic_stops_by_area.csv", g + ["n"],
              lower_keys(query_stats(OPS, STOPS, g, COUNT)))

    g = ["occ_year", "dow", "hour", "how_cleared"]
    write_csv(POLICE_OUT / "traffic_stops_by_time.csv", g + ["n"],
              lower_keys(query_stats(OPS, STOPS, g, COUNT)))

    g = ["occ_year", "age_range", "driver_gender", "driver_race", "how_cleared"]
    write_csv(POLICE_OUT / "traffic_stops_by_driver.csv", g + ["n"],
              lower_keys(query_stats(OPS, STOPS, g, COUNT)))

    # Per-location totals over all years, with the charged share, for snapping
    # onto city Geo_IDs later. Coordinates are averaged MTM9, converted here.
    xy = [("count", "OBJECTID", "n"), ("avg", "x_coordinate", "x"),
          ("avg", "y_coordinate", "y")]
    allstops = lower_keys(query_stats(OPS, STOPS, ["location"], xy))
    charged = {r["location"]: r["n"] for r in lower_keys(
        query_stats(OPS, STOPS, ["location"], COUNT, where="how_cleared = 'Charged'"))}
    out, other = [], {"location": "(other)", "n": 0, "n_charged": 0}
    for r in allstops:
        nc = charged.get(r["location"], 0)
        if r["n"] < MIN_STOPS_PER_LOCATION or not r["location"]:
            other["n"] += r["n"]
            other["n_charged"] += nc
            continue
        lat, lon = mtm9_to_latlon(r.get("x"), r.get("y"))
        out.append({"location": r["location"].strip(), "n": r["n"], "n_charged": nc,
                    "lat": lat, "lon": lon})
    out.sort(key=lambda r: -r["n"])
    out.append(other)
    write_csv(POLICE_OUT / "traffic_stops_by_location.csv",
              ["location", "n", "n_charged", "lat", "lon"], out)

    # Dispatched calls carry no call type, so these are context, not traffic-only.
    g = ["rcvd_year", "ward_id", "nb_name_en", "priority"]
    write_csv(POLICE_OUT / "calls_by_area.csv", g + ["n"],
              lower_keys(query_stats(OPS, CALLS, ["RCVD_YEAR", "WARD_ID", "NB_NAME_EN", "PRIORITY"], COUNT)))
    g = ["rcvd_year", "dow", "rcvd_hour", "priority"]
    write_csv(POLICE_OUT / "calls_by_time.csv", g + ["n"],
              lower_keys(query_stats(OPS, CALLS, ["RCVD_YEAR", "DOW", "RCVD_HOUR", "PRIORITY"], COUNT)))


# --------------------------------------------------------------------------

JOBS = {
    "collisions": fetch_collisions,
    "volumes": fetch_volumes,
    "cameras": fetch_cameras,
    "covid": fetch_covid,
    "bike_counters": fetch_bike_counters,
    "police": fetch_police,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="comma-separated subset of: " + ", ".join(JOBS))
    args = ap.parse_args()
    names = args.only.split(",") if args.only else list(JOBS)
    failed = []
    for name in names:
        print(f"[{name}]")
        try:
            JOBS[name]()
        except Exception as e:  # keep going: one renamed layer shouldn't block the rest
            print(f"  FAILED: {e}", file=sys.stderr)
            failed.append(name)
    if failed:
        sys.exit(f"failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()

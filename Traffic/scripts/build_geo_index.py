#!/usr/bin/env python3
"""Join every traffic dataset onto one spatial key: the City's Geo_ID.

Collisions, midblock volumes and the 2024-25 intersection volumes already
carry a Geo_ID (numeric = intersection, '__XXXX' = road segment). Everything
else -- police stop locations, red-light and photo-radar cameras, TomTom
segments, traffic cameras, pre-2024 intersection counts -- only has
coordinates, so it is snapped to the nearest Geo_ID here.

Inputs: Traffic/data/city/*, Traffic/data/police/*, Traffic/data/cameras.csv,
        Traffic/corridors.json, plus ward + OPS-neighbourhood polygons fetched live.
Outputs (Traffic/data/derived/):
  * geo_index.csv            -- one row per Geo_ID: kind, name, lat/lon, ward,
                                neighbourhood, collisions, latest AADT, collisions
                                per million vehicles, police stops, cameras
  * snaps.csv                -- every coordinate-only record -> its Geo_ID + distance
  * neighbourhood_summary.csv -- per OPS neighbourhood: collisions vs stops vs population

Run after fetch_city_traffic.py (the weekly workflow does both). Stdlib only.
"""

import csv
import glob
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from fetch_city_traffic import CITY, OPS, ROOT, query_all, write_csv

DATA = ROOT / "data"
OUT = DATA / "derived"

# Collision years present in the city's release (2023 is missing at source).
COLLISION_YEARS = 7

# How far a coordinate-only record may sit from a Geo_ID and still match it.
# Intersections are geocoded to the node, so a tight radius; TomTom points
# are picked by hand on a road, so looser. Beyond this the record keeps its
# ward/neighbourhood but no Geo_ID.
SNAP_M = {"intersection": 60, "any": 120}
# Police stop locations are 'STREET / STREET' strings geocoded less precisely
# than the City's nodes. Out to this radius, accept a node only if both
# street names match, so a nearby-but-different intersection can't win.
NAME_CONFIRMED_M = 150


# --------------------------------------------------------------------------
# Geometry helpers (Ottawa is small enough for a flat local projection)
# --------------------------------------------------------------------------

LAT0 = 45.4
M_PER_DEG_LAT = 111_132.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))


def xy(lat, lon):
    return lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT


class Snapper:
    """Nearest-point lookup on a 100 m grid."""

    CELL = 100.0

    def __init__(self, points):            # points: [(key, lat, lon)]
        self.grid = defaultdict(list)
        for key, lat, lon in points:
            x, y = xy(lat, lon)
            self.grid[(int(x // self.CELL), int(y // self.CELL))].append((key, x, y))

    def within(self, lat, lon, max_m):
        """[(distance_m, key)] for every point within max_m, nearest first."""
        x, y = xy(lat, lon)
        cx, cy = int(x // self.CELL), int(y // self.CELL)
        r = int(math.ceil(max_m / self.CELL))
        hits = []
        for i in range(cx - r, cx + r + 1):
            for j in range(cy - r, cy + r + 1):
                for key, px, py in self.grid.get((i, j), ()):
                    d = math.hypot(px - x, py - y)
                    if d <= max_m:
                        hits.append((d, key))
        return sorted(hits)

    def nearest(self, lat, lon, max_m):
        hits = self.within(lat, lon, max_m)
        return (hits[0][1], round(hits[0][0])) if hits else (None, None)


def street_stems(text):
    """'REGIONAL ROAD 174 / TRIM RD' -> {'REGIONAL', 'TRIM'}: first word of each street."""
    parts = [p for p in re.split(r"\s*(?:/|@|&|\bbtwn\b|\band\b)\s*", text.upper()) if p.strip()]
    return {re.sub(r"[^A-Z0-9]", "", p.split()[0]) for p in parts if p.split()}


class Regions:
    """Point-in-polygon over ArcGIS polygon rings (even-odd, so holes work)."""

    def __init__(self, features, name_of):
        self.polys = []
        for f in features:
            rings = f.get("_rings") or []
            pts = [p for ring in rings for p in ring]
            if not pts:
                continue
            bbox = (min(p[0] for p in pts), min(p[1] for p in pts),
                    max(p[0] for p in pts), max(p[1] for p in pts))
            self.polys.append((name_of(f), bbox, rings))

    def lookup(self, lat, lon):
        for name, (x0, y0, x1, y1), rings in self.polys:
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            inside = False
            for ring in rings:
                for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
                    if (ay > lat) != (by > lat) and lon < (bx - ax) * (lat - ay) / (by - ay) + ax:
                        inside = not inside
            if inside:
                return name
        return None


def fetch_polygons(base, service):
    """query_all drops geometry rings, so fetch polygons directly."""
    from fetch_city_traffic import get_json, layer_url
    url = layer_url(base, service)
    out, offset = [], 0
    while True:
        d = get_json(f"{url}/query", {
            "where": "1=1", "outFields": "*", "outSR": 4326, "returnGeometry": "true",
            "geometryPrecision": 5, "resultOffset": offset, "resultRecordCount": 200,
        })
        for f in d["features"]:
            a = dict(f["attributes"])
            a["_rings"] = (f.get("geometry") or {}).get("rings")
            out.append(a)
        if len(d["features"]) < 200:
            return out
        offset += 200


# --------------------------------------------------------------------------

def read(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build():
    collisions = [r for p in sorted(glob.glob(str(DATA / "city/collisions/*.csv"))) for r in read(p)]
    ivol = read(DATA / "city/intersection_volumes.csv")
    mvol = read(DATA / "city/midblock_volumes.csv")

    # ---- 1. Geo_ID index: median of every coordinate published for the ID
    coords, names = defaultdict(list), defaultdict(Counter)
    for r in collisions:
        if r["geo_id"] and f(r["lat"]):
            coords[r["geo_id"]].append((f(r["lat"]), f(r["lon"])))
            names[r["geo_id"]][r["location"]] += 1
    for r, name_col in [(r, "intersection") for r in ivol] + [(r, "midblock") for r in mvol]:
        if r["geo_id"] and f(r["lat"]):
            coords[r["geo_id"]].append((f(r["lat"]), f(r["lon"])))
            names[r["geo_id"]][r[name_col].split(" (")[0]] += 1

    print("fetching ward + neighbourhood polygons")
    wards = Regions(fetch_polygons(CITY, "Wards_2022_2026"),
                    lambda a: f"{int(a['WARD'])} {a['NAME']}")
    ons_raw = fetch_polygons(OPS, "ONS_2017")
    hoods = Regions(ons_raw, lambda a: a["namese2016"])
    population = {a["namese2016"]: a.get("popest2016") for a in ons_raw}

    geo = {}
    for gid, pts in coords.items():
        lat = statistics.median(p[0] for p in pts)
        lon = statistics.median(p[1] for p in pts)
        geo[gid] = {
            "geo_id": gid, "kind": "intersection" if gid.isdigit() else "segment",
            "name": names[gid].most_common(1)[0][0],
            "lat": round(lat, 6), "lon": round(lon, 6),
            "ward": wards.lookup(lat, lon), "neighbourhood": hoods.lookup(lat, lon),
        }
    # ---- 2. Snap coordinate-only records
    snap_any = Snapper((g["geo_id"], g["lat"], g["lon"]) for g in geo.values())
    snap_int = Snapper((g["geo_id"], g["lat"], g["lon"]) for g in geo.values()
                       if g["kind"] == "intersection")

    snaps = []

    def snap(source, key, name, lat, lon, intersections_only, **extra):
        lat, lon = f(lat), f(lon)
        if lat is None or lon is None:
            gid, dist = None, None
        elif intersections_only:
            gid, dist = snap_int.nearest(lat, lon, SNAP_M["intersection"])
            stems = street_stems(name) if " / " in name else None
            if gid is None and stems and len(stems) >= 2:
                for d, cand in snap_int.within(lat, lon, NAME_CONFIRMED_M):
                    if stems <= street_stems(geo[cand]["name"]):
                        gid, dist = cand, round(d)
                        break
        else:
            gid, dist = snap_any.nearest(lat, lon, SNAP_M["any"])
        row = {"source": source, "source_key": key, "source_name": name,
               "lat": lat, "lon": lon, "geo_id": gid, "dist_m": dist,
               "ward": wards.lookup(lat, lon) if lat else None,
               "neighbourhood": hoods.lookup(lat, lon) if lat else None, **extra}
        snaps.append(row)
        return row

    for r in read(DATA / "police/traffic_stops_by_location.csv"):
        if r["lat"]:
            snap("police_stops", r["location"], r["location"], r["lat"], r["lon"], True,
                 n=int(r["n"]), n_charged=int(r["n_charged"]))

    rlc = defaultdict(int)
    rlc_meta = {}
    for r in read(DATA / "city/red_light_violations.csv"):
        k = f"{r['location']}|{r['camera_facing']}"
        rlc[k] += int(float(r["violations"]))
        rlc_meta[k] = r
    for k, total in rlc.items():
        m = rlc_meta[k]
        snap("red_light_camera", k, m["location"], m["lat"], m["lon"], True, n=total)

    ase = defaultdict(int)
    ase_meta = {}
    for r in read(DATA / "city/ase_violations.csv"):
        ase[r["site_id"]] += int(float(r["violations"]))
        ase_meta[r["site_id"]] = r
    for k, total in ase.items():
        m = ase_meta[k]
        snap("ase_camera", k, m["location"], m["lat"], m["lon"], False, n=total)

    for s in json.loads((ROOT / "corridors.json").read_text(encoding="utf-8"))["segments"]:
        snap("tomtom_segment", s["id"], s["label"], s["point"][0], s["point"][1], False)

    if (DATA / "cameras.csv").exists():
        for r in read(DATA / "cameras.csv"):
            snap("traffic_camera", r["id"], r["description"], r["lat"], r["lon"], True)

    # Pre-2024 intersection counts carry no Geo_ID; give them one.
    for r in ivol:
        if not r["geo_id"]:
            snap("intersection_volume", f"{r['year']}|{r['intersection']}",
                 r["intersection"], r["lat"], r["lon"], True)

    write_csv(OUT / "snaps.csv",
              ["source", "source_key", "source_name", "lat", "lon", "geo_id", "dist_m",
               "ward", "neighbourhood", "n", "n_charged"], snaps)
    for src, rows in sorted(_group(snaps, "source").items()):
        hit = sum(1 for r in rows if r["geo_id"])
        print(f"  snapped {src:20s} {hit:6,}/{len(rows):,} matched a Geo_ID")

    # ---- 3. Per-Geo_ID metrics (the published geo_index.csv)
    risk = {gid: {**g, "collisions": 0, "injury_collisions": 0, "fatal_collisions": 0,
                  "pedestrian_collisions": 0, "cyclist_collisions": 0,
                  "aadt": None, "aadt_year": None, "collisions_per_mev": None,
                  "police_stops": 0, "police_charged": 0,
                  "red_light_cameras": 0, "ase_site": None}
            for gid, g in geo.items()}
    for r in collisions:
        x = risk.get(r["geo_id"])
        if not x:
            continue
        x["collisions"] += 1
        x["injury_collisions"] += r["severity"] == "Non-fatal injury"
        x["fatal_collisions"] += r["severity"] == "Fatal injury"
        x["pedestrian_collisions"] += bool(f(r["pedestrians"]))
        x["cyclist_collisions"] += bool(f(r["bicycles"]))

    # Latest AADT per Geo_ID, from direct IDs or snapped older counts.
    snapped_count = {r["source_key"]: r["geo_id"] for r in snaps
                     if r["source"] == "intersection_volume" and r["geo_id"]}
    for r in ivol + mvol:
        gid = r["geo_id"] or snapped_count.get(f"{r['year']}|{r.get('intersection')}")
        aadt = f(r["aadt"])
        if gid in risk and aadt and int(r["year"]) >= (risk[gid]["aadt_year"] or 0):
            risk[gid]["aadt"], risk[gid]["aadt_year"] = int(aadt), int(r["year"])

    for r in snaps:
        x = risk.get(r["geo_id"])
        if not x:
            continue
        if r["source"] == "police_stops":
            x["police_stops"] += r["n"]
            x["police_charged"] += r["n_charged"]
        elif r["source"] == "red_light_camera":
            x["red_light_cameras"] += 1
        elif r["source"] == "ase_camera":
            x["ase_site"] = r["source_key"]

    for x in risk.values():
        # Collisions per million vehicles entering/passing -- risk per trip,
        # not just "busy roads have more crashes".
        if x["aadt"]:
            per_year = x["collisions"] / COLLISION_YEARS
            x["collisions_per_mev"] = round(per_year / (x["aadt"] * 365) * 1e6, 3)

    write_csv(OUT / "geo_index.csv", list(next(iter(risk.values())).keys()),
              sorted(risk.values(), key=lambda x: -x["collisions"]))

    # ---- 4. Neighbourhood rollup (story 1: where risk is vs where enforcement is)
    hood = defaultdict(lambda: Counter())
    for r in collisions:
        g = geo.get(r["geo_id"])
        name = g["neighbourhood"] if g else (hoods.lookup(f(r["lat"]), f(r["lon"])) if f(r["lat"]) else None)
        c = hood[name or "(unmatched)"]
        c["collisions"] += 1
        c["injury_collisions"] += r["severity"] in ("Non-fatal injury", "Fatal injury")
        c["fatal_collisions"] += r["severity"] == "Fatal injury"
    for r in read(DATA / "police/traffic_stops_by_area.csv"):
        c = hood[r["neighbourhood"] or "(unmatched)"]
        c["police_stops"] += int(r["n"])
        c["police_charged"] += int(r["n"]) if r["how_cleared"] == "Charged" else 0
    rows = []
    for name, c in hood.items():
        pop = population.get(name)
        rows.append({
            "neighbourhood": name, "population_2016": pop,
            "collisions": c["collisions"], "injury_collisions": c["injury_collisions"],
            "fatal_collisions": c["fatal_collisions"],
            "police_stops": c["police_stops"], "police_charged": c["police_charged"],
            "collisions_per_1k_residents_yr": round(c["collisions"] / COLLISION_YEARS / pop * 1000, 2) if pop else None,
            "stops_per_injury_collision": round(c["police_stops"] / c["injury_collisions"], 1) if c["injury_collisions"] else None,
        })
    write_csv(OUT / "neighbourhood_summary.csv", list(rows[0].keys()),
              sorted(rows, key=lambda r: -r["collisions"]))


def _group(rows, key):
    out = defaultdict(list)
    for r in rows:
        out[r[key]].append(r)
    return out


if __name__ == "__main__":
    build()

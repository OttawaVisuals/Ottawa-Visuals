"""Build the small, local Natural Earth basemap used by movement.html.

Source: https://github.com/nvkelso/natural-earth-vector (public domain)
Pinned revision keeps the generated geometry reproducible.
"""

import json
from pathlib import Path
from urllib.request import urlopen


REVISION = "ca96624a56bd078437bca8184e78163e5039ad19"
BASE_URL = f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{REVISION}/geojson/"
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "json" / "pwhl_movement_geography.json"
BOUNDS = (-132, 24, -60, 63)  # longitude/latitude; the continental map viewport


def download(name):
    with urlopen(BASE_URL + name, timeout=30) as response:
        return json.load(response)["features"]


def intersects(points):
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    west, south, east, north = BOUNDS
    return min(xs) <= east and max(xs) >= west and min(ys) <= north and max(ys) >= south


def compact(points):
    return [[round(lon, 3), round(lat, 3)] for lon, lat in points]


def rings(geometry):
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return [compact(ring) for polygon in polygons for ring in polygon if intersects(ring)]


countries = []
for feature in download("ne_50m_admin_0_countries.geojson"):
    code = feature["properties"].get("ISO_A3")
    if code in {"CAN", "USA", "MEX"}:
        countries.append({"code": code, "rings": rings(feature["geometry"])})

borders = []
for feature in download("ne_50m_admin_1_states_provinces_lines.geojson"):
    if feature["properties"].get("ADM0_A3") not in {"CAN", "USA"}:
        continue
    geometry = feature["geometry"]
    lines = geometry["coordinates"] if geometry["type"] == "MultiLineString" else [geometry["coordinates"]]
    borders.extend(compact(line) for line in lines if intersects(line))

lakes = []
for feature in download("ne_50m_lakes.geojson"):
    visible = rings(feature["geometry"])
    if visible:
        lakes.extend(visible)

OUTPUT.write_text(
    json.dumps({"source_revision": REVISION, "countries": countries, "borders": borders, "lakes": lakes}, separators=(",", ":")),
    encoding="utf-8",
)
print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")

"""Fetch the original 2023 boundary set (about 22 MB) into an ignored local gzip.
Run before build_data.py in a fresh clone. Never overwrites an existing snapshot.
"""
from pathlib import Path
import gzip
import json
import urllib.request

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "data/boundaries-2023.geojson.gz"
URL = "https://openmaps.gov.bc.ca/geo/pub/WHSE_ADMIN_BOUNDARIES.EBC_ELECTORAL_DISTS_BS11_SVW/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=pub:WHSE_ADMIN_BOUNDARIES.EBC_ELECTORAL_DISTS_BS11_SVW&outputFormat=application/json&count=100"

if TARGET.exists():
    print("Existing boundary snapshot retained.")
else:
    with urllib.request.urlopen(URL, timeout=90) as response:
        raw = response.read()
    geo = json.loads(raw)
    assert len(geo["features"]) == 93
    assert geo["crs"]["properties"]["name"].endswith("3005")
    TARGET.parent.mkdir(exist_ok=True)
    TARGET.write_bytes(gzip.compress(raw, mtime=0))
    print(f"Saved {len(geo['features'])} official district geometries to {TARGET.name}")

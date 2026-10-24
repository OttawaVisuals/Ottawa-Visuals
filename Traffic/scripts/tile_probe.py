"""One-off probe: fetch TomTom traffic-flow vector tiles over Ottawa and summarise them.

Purpose: see what the "Traffic Flow & Incidents Vector Tiles" product (own 200k/month
allowance, separate from the Flow Segment Data cap) actually returns before building a
collector on it. Prints tile counts, features, properties and a per-road-type summary.

Run locally; the key stays in your environment, never in the repo or chat:
    PowerShell:  $env:TOMTOM_API_KEY = "<key>"; python Traffic/scripts/tile_probe.py
    Options:     --zoom 11 (default) | 12,   --type relative (default) | absolute

Cost: one request per tile (zoom 11 ~ 12 tiles, zoom 12 ~ 48). Stdlib only; contains a
minimal Mapbox Vector Tile (protobuf) reader.
"""

import argparse
import gzip
import math
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict

# Urban Ottawa + Gatineau core, lon/lat
BBOX = (-76.00, 45.20, -75.40, 45.55)
# v4 = TomTom Maps (older); orbis = Orbis v2 (key needs the "Orbis Traffic Flow API Vector Tiles" product)
API = {
    "v4": "https://api.tomtom.com/traffic/map/4/tile/flow/{type}/{z}/{x}/{y}.pbf?key={key}",
    "orbis": ("https://api.tomtom.com/maps/orbis/traffic/flow/vector/tile/{z}/{x}/{y}"
              "?apiVersion=2&key={key}&attributes=tags(road_category,relative_speed,absolute_speed)"),
}


def tile_xy(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


def tiles_for_bbox(z):
    x0, y1 = tile_xy(BBOX[0], BBOX[1], z)
    x1, y0 = tile_xy(BBOX[2], BBOX[3], z)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


# ---- minimal protobuf / MVT reader -------------------------------------------------

def varint(buf, i):
    shift = result = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def fields(buf):
    """Yield (field_number, wire_type, value) for one protobuf message."""
    i = 0
    while i < len(buf):
        key, i = varint(buf, i)
        num, wt = key >> 3, key & 7
        if wt == 0:
            val, i = varint(buf, i)
        elif wt == 2:
            ln, i = varint(buf, i)
            val = buf[i:i + ln]
            i += ln
        elif wt == 1:
            val = buf[i:i + 8]
            i += 8
        elif wt == 5:
            val = buf[i:i + 4]
            i += 4
        else:
            raise ValueError(f"unsupported wire type {wt}")
        yield num, wt, val


def packed_varints(buf):
    i = 0
    out = []
    while i < len(buf):
        v, i = varint(buf, i)
        out.append(v)
    return out


def zigzag(n):
    return (n >> 1) ^ -(n & 1)


def decode_value(buf):
    import struct
    for num, wt, v in fields(buf):
        if num == 1:
            return v.decode("utf-8", "replace")
        if num == 2:
            return struct.unpack("<f", v)[0]
        if num == 3:
            return struct.unpack("<d", v)[0]
        if num in (4, 5):
            return v
        if num == 6:
            return zigzag(v)
        if num == 7:
            return bool(v)
    return None


def line_length(geom):
    """Total length of a LINESTRING feature's geometry, in tile units."""
    total = 0.0
    x = y = 0
    px = py = None
    i = 0
    while i < len(geom):
        cmd = geom[i]
        i += 1
        op, count = cmd & 7, cmd >> 3
        for _ in range(count):
            if op in (1, 2):
                x += zigzag(geom[i])
                y += zigzag(geom[i + 1])
                i += 2
                if op == 2 and px is not None:
                    total += math.hypot(x - px, y - py)
                px, py = x, y
    return total


def decode_tile(data):
    """Return list of layers: {name, extent, features:[{type, props, length}]}."""
    layers = []
    for num, _, lay in fields(data):
        if num != 3:
            continue
        name, extent, keys, values, feats = "", 4096, [], [], []
        for n2, _, v in fields(lay):
            if n2 == 1:
                name = v.decode()
            elif n2 == 2:
                feats.append(v)
            elif n2 == 3:
                keys.append(v.decode())
            elif n2 == 4:
                values.append(decode_value(v))
            elif n2 == 5:
                extent = v
        out = []
        for f in feats:
            tags, gtype, geom = [], 0, []
            for n3, _, v in fields(f):
                if n3 == 2:
                    tags = packed_varints(v)
                elif n3 == 3:
                    gtype = v
                elif n3 == 4:
                    geom = packed_varints(v)
            props = {keys[tags[j]]: values[tags[j + 1]] for j in range(0, len(tags) - 1, 2)}
            out.append({"type": gtype, "props": props,
                        "length": line_length(geom) if gtype == 2 else 0.0})
        layers.append({"name": name, "extent": extent, "features": out})
    return layers


# ---- fetch + summarise -------------------------------------------------------------

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "OttawaVisuals-traffic/1.0",
                                               "Accept-Encoding": "gzip",
                                               "Accept": "application/vnd.mapbox-vector-tile"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body


def metres_per_unit(z, lat, extent):
    return 40075016.686 * math.cos(math.radians(lat)) / (2 ** z) / extent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=int, default=11)
    ap.add_argument("--type", default="relative", choices=["relative", "absolute", "relative-delay"],
                    help="v4 only; Orbis returns both relative_speed and absolute_speed")
    ap.add_argument("--api", default="orbis", choices=["orbis", "v4"])
    args = ap.parse_args()
    key = os.environ.get("TOMTOM_API_KEY")
    if not key:
        sys.exit("Set TOMTOM_API_KEY in your environment first.")
    key = key.strip()
    if not key.isalnum():
        sys.exit("TOMTOM_API_KEY should be the plain key (letters and digits), not a placeholder.")

    tiles = tiles_for_bbox(args.zoom)
    print(f"{len(tiles)} tiles at zoom {args.zoom}, api={args.api}, type={args.type}")
    by_type = defaultdict(lambda: [0, 0.0, 0.0])  # features, metres, level*metres
    seen_props = defaultdict(set)
    used = 0
    for x, y in tiles:
        url = API[args.api].format(type=args.type, z=args.zoom, x=x, y=y, key=key)
        try:
            data = fetch(url)
        except urllib.error.HTTPError as exc:
            detail = exc.read(300).decode("utf-8", "replace").replace(key, "<key>")
            print(f"  tile {x},{y}: HTTP {exc.code} {detail!r}")
            if exc.code in (401, 403):
                break  # same answer for every tile; don't spend more requests
            continue
        used += 1
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / 2 ** args.zoom))))
        for layer in decode_tile(data):
            mpu = metres_per_unit(args.zoom, lat, layer["extent"])
            for f in layer["features"]:
                for k, v in f["props"].items():
                    if len(seen_props[k]) < 6:
                        seen_props[k].add(v)
                rt = f["props"].get("road_type") or f["props"].get("road_category", "?")
                lvl = f["props"].get("traffic_level", f["props"].get("relative_speed"))
                m = f["length"] * mpu
                rec = by_type[rt]
                rec[0] += 1
                rec[1] += m
                if isinstance(lvl, (int, float)):
                    rec[2] += lvl * m
        print(f"  tile {x},{y}: {len(data)} bytes")
    print(f"\nrequests used: {used}\nproperties seen (sample values):")
    for k, vals in seen_props.items():
        print(f"  {k}: {sorted(map(str, vals))}")
    print("\nroad_type: features, km, length-weighted mean traffic_level")
    for rt, (n, m, lm) in sorted(by_type.items(), key=lambda kv: -kv[1][1]):
        print(f"  {rt}: {n}, {m / 1000:.0f} km, {lm / m if m else float('nan'):.2f}")


if __name__ == "__main__":
    main()

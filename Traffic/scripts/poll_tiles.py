#!/usr/bin/env python3
"""Sample TomTom's Orbis traffic-flow vector tiles over urban Ottawa-Gatineau.

A second, citywide flow series next to the point segments in poll_traffic.py. Each
sample fetches ~20 zoom-11 tiles (own 200k/month allowance, separate from the Flow
Segment Data cap) and logs, per road category, the length-weighted mean of
relative_speed (current speed / free-flow), the share of road length below 0.7 and
0.5 of free-flow, and the mean absolute speed. Tiles carry no road IDs, so this is a
network-wide congestion measure, not a repeat of the point series: do not splice the two.

Output (Traffic/data/flow_tiles_summary.csv), one block of rows per sample:
  scope = "city"       one row per road_category, summed over every tile
  scope = "tile:x/y"   one row per tile, road_category "all"
Roads within a tile's edge margin appear in both neighbouring tiles, so km are not
exact road length; use the ratios.

Cadence matches poll_traffic.py (every 15 min at weekday rush hours, hourly otherwise),
decided from this script's own log so the 5-min cron cannot double-sample. ~20 requests a
sample, ~23k a month. A 4xx stops the run at the first tile, so a blocked key costs one
request per sample. Stdlib only; the tile reader lives in tile_probe.py.

Requires TOMTOM_API_KEY with the "Orbis Traffic Flow API Vector Tiles" product enabled.
"""

import argparse
import csv
import math
import os
import sys
import urllib.error
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poll_traffic as pt  # noqa: E402  (gate helpers, same cadence)
import tile_probe as tp  # noqa: E402  (tile fetch + decoder)

DATA = Path(__file__).resolve().parents[1] / "data"
LOG = DATA / "flow_tiles_summary.csv"
ZOOM = 11
FIELDS = ["timestamp_utc", "timestamp_local", "scope", "road_category", "features", "km",
          "mean_relative_speed", "share_km_below_0_7", "share_km_below_0_5",
          "mean_absolute_speed_kmh", "tiles_ok", "tiles_total", "error"]
TZ = ZoneInfo("America/Toronto")


class Acc:
    """Length-weighted accumulator for one group of road features."""
    __slots__ = ("n", "m", "rel", "abs_m", "abs", "lt7", "lt5")

    def __init__(self):
        self.n = 0
        self.m = self.rel = self.abs_m = self.abs = self.lt7 = self.lt5 = 0.0

    def add(self, metres, rel, absolute):
        self.n += 1
        self.m += metres
        if rel is not None:
            self.rel += rel * metres
            self.lt7 += metres if rel < 0.7 else 0.0
            self.lt5 += metres if rel < 0.5 else 0.0
        if absolute is not None:
            self.abs += absolute * metres
            self.abs_m += metres

    def row(self):
        m = self.m
        return {
            "features": self.n,
            "km": f"{m / 1000:.1f}",
            "mean_relative_speed": f"{self.rel / m:.4f}" if m else "",
            "share_km_below_0_7": f"{self.lt7 / m:.4f}" if m else "",
            "share_km_below_0_5": f"{self.lt5 / m:.4f}" if m else "",
            "mean_absolute_speed_kmh": f"{self.abs / self.abs_m:.1f}" if self.abs_m else "",
        }


def summarise(tiles):
    """tiles: {(x, y): decoded layers} -> (city {category: Acc}, per_tile {(x, y): Acc})."""
    city = defaultdict(Acc)
    per_tile = {}
    for (x, y), layers in tiles.items():
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / 2 ** ZOOM))))
        acc = per_tile[(x, y)] = Acc()
        for layer in layers:
            mpu = tp.metres_per_unit(ZOOM, lat, layer["extent"])
            for f in layer["features"]:
                if f["type"] != 2:
                    continue
                p = f["props"]
                metres = f["length"] * mpu
                rel, absolute = p.get("relative_speed"), p.get("absolute_speed")
                cat = p.get("road_category", "?")
                city[cat].add(metres, rel, absolute)
                acc.add(metres, rel, absolute)
    return city, per_tile


def append(rows):
    new = not LOG.exists() or LOG.stat().st_size == 0
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ignore the cadence gate")
    args = ap.parse_args()

    key = os.environ.get("TOMTOM_API_KEY", "").strip()
    if not key:
        print("ERROR: TOMTOM_API_KEY not set", file=sys.stderr)
        return 1

    now_utc = datetime.now(ZoneInfo("UTC"))
    now_local = now_utc.astimezone(TZ)
    if not args.force and not pt.should_sample(now_local, LOG):
        print(f"skip: {now_local:%Y-%m-%d %H:%M %Z} slot is already sampled")
        return 0

    base = {"timestamp_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timestamp_local": now_local.strftime("%Y-%m-%dT%H:%M:%S%z")}
    coords = tp.tiles_for_bbox(ZOOM)
    tiles, error = {}, ""
    for x, y in coords:
        url = tp.API["orbis"].format(type="relative", z=ZOOM, x=x, y=y, key=key)
        try:
            tiles[(x, y)] = tp.decode_tile(tp.fetch(url))
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}"
            if 400 <= exc.code < 500:
                break  # same answer for every tile; don't spend more requests
        except Exception as exc:  # noqa: BLE001 - log it, a bad tile shouldn't kill the run
            error = type(exc).__name__

    counts = {"tiles_ok": len(tiles), "tiles_total": len(coords)}
    if not tiles:
        append([{**base, "scope": "city", "road_category": "all", "error": error or "no tiles",
                 **counts}])
        print(f"no tiles fetched ({error})")
        return 0

    city, per_tile = summarise(tiles)
    rows = [{**base, "scope": "city", "road_category": cat, "error": error, **counts, **acc.row()}
            for cat, acc in sorted(city.items())]
    rows += [{**base, "scope": f"tile:{x}/{y}", "road_category": "all", "error": error, **counts,
              **acc.row()} for (x, y), acc in sorted(per_tile.items())]
    append(rows)
    print(f"logged {len(rows)} rows from {len(tiles)}/{len(coords)} tiles")
    return 0


if __name__ == "__main__":
    sys.exit(main())

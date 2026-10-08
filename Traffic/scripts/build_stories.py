#!/usr/bin/env python3
"""Precompute the small numbers the road-safety pages chart.

The raw inputs are ~20 MB (collisions alone are 15 MB), far too much for a
page to fetch for a handful of charts, so this distils them into one JSON:
Traffic/data/derived/stories.json. Run after build_geo_index.py (the weekly
workflow does both).

Story keys:
  ase_tickets_monthly   -- photo-radar tickets per active camera per month
  ase_collisions        -- collisions at ASE sites before vs after install
  rlc_by_years_since    -- red-light violations per camera-month by camera age
  rlc_before_after      -- collisions by type before vs after a red-light camera
  ped_fmi_by_year       -- pedestrian fatal + major-injury collisions per year

Before/after comparisons count collisions per site-year at the camera's own
Geo_ID, excluding the install year itself (part before, part after).
"""

import csv
import glob
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent       # the Traffic/ directory
DATA = ROOT / "data"
OUT = DATA / "derived" / "stories.json"

# Collision years present in the City's release (2023 is missing at source).
COLLISION_YEARS = (2017, 2018, 2019, 2020, 2021, 2022, 2024)

# Red-light cameras need collision years on both sides of the install year.
RLC_INSTALL_WINDOW = (2018, 2022)

IMPACT_GROUPS = {
    "Angle + turning": ("Angle", "Turning movement"),   # what red-light running causes
    "Rear end": ("Rear end",),                          # what hard stops cause
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def collisions():
    return [r for p in sorted(glob.glob(str(DATA / "city/collisions/*.csv"))) for r in read(p)]


def site_years(install_years, side):
    """How many collision-years fall before/after each site's install year."""
    if side == "before":
        return sum(sum(y < i for y in COLLISION_YEARS) for i in install_years)
    return sum(sum(y > i for y in COLLISION_YEARS) for i in install_years)


def ase_stories(cols, snaps):
    v = read(DATA / "city/ase_violations.csv")
    by_month = defaultdict(lambda: [0, 0])
    for r in v:
        k = f"{r['year']}-{int(r['month']):02d}"
        by_month[k][0] += float(r["violations"])
        by_month[k][1] += 1
    monthly = [{"month": k, "tickets": int(t), "cameras": n, "per_camera": round(t / n, 1)}
               for k, (t, n) in sorted(by_month.items())]

    install = {r["site_id"]: int(r["install_year"]) for r in v}
    site_geo = {s["geo_id"]: install[s["source_key"]] for s in snaps
                if s["source"] == "ase_camera" and s["geo_id"] and s["source_key"] in install}
    before = after = 0
    for r in cols:
        i = site_geo.get(r["geo_id"])
        if i is None:
            continue
        y = int(r["year"])
        before += y < i
        after += y > i
    by, ay = site_years(site_geo.values(), "before"), site_years(site_geo.values(), "after")
    return monthly, {
        "sites": len(site_geo),
        "before": before, "before_site_years": by,
        "after": after, "after_site_years": ay,
        "before_rate": round(before / by, 2) if by else None,
        "after_rate": round(after / ay, 2) if ay else None,
    }


def rlc_stories(cols, snaps):
    rl = read(DATA / "city/red_light_violations.csv")
    by_age = defaultdict(list)
    for r in rl:
        by_age[int(r["year"]) - int(r["install_year"])].append(float(r["violations"]))
    ages = [{"years_since_install": a, "avg_monthly": round(sum(x) / len(x), 1),
             "camera_months": len(x)} for a, x in sorted(by_age.items()) if a >= 0]

    install = {f"{r['location']}|{r['camera_facing']}": int(r["install_year"]) for r in rl}
    geo_install = {}
    for s in snaps:
        if s["source"] == "red_light_camera" and s["geo_id"] and s["source_key"] in install:
            # Several approaches can share an intersection; the first camera counts.
            geo_install[s["geo_id"]] = min(geo_install.get(s["geo_id"], 9999), install[s["source_key"]])
    lo, hi = RLC_INSTALL_WINDOW
    sites = {g: i for g, i in geo_install.items() if lo <= i <= hi}
    by, ay = site_years(sites.values(), "before"), site_years(sites.values(), "after")
    groups = {**IMPACT_GROUPS, "All collisions": None}
    out = []
    for label, types in groups.items():
        b = a = 0
        for r in cols:
            i = sites.get(r["geo_id"])
            if i is None or (types and r["impact_type"] not in types):
                continue
            y = int(r["year"])
            b += y < i
            a += y > i
        out.append({"type": label, "before": b, "after": a,
                    "before_rate": round(b / by, 2), "after_rate": round(a / ay, 2),
                    "change_pct": round((a / ay) / (b / by) * 100 - 100)})
    return ages, {"intersections": len(sites), "install_years": f"{lo}-{hi}",
                  "before_site_years": by, "after_site_years": ay, "by_type": out}


def ped_fmi(cols):
    c = Counter(r["year"] for r in cols
                if r["pedestrians"] not in ("", "0")
                and (r["severity"] == "Fatal injury" or r["max_injury"] in ("Major", "Fatal")))
    return [{"year": int(y), "collisions": n} for y, n in sorted(c.items())]


def build():
    cols = collisions()
    snaps = read(DATA / "derived/snaps.csv")
    ase_monthly, ase_col = ase_stories(cols, snaps)
    rlc_ages, rlc_ba = rlc_stories(cols, snaps)
    stories = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "collision_years": list(COLLISION_YEARS),
        "ase_tickets_monthly": ase_monthly,
        "ase_collisions": ase_col,
        "rlc_by_years_since": rlc_ages,
        "rlc_before_after": rlc_ba,
        "ped_fmi_by_year": ped_fmi(cols),
    }
    OUT.write_text(json.dumps(stories, indent=1), encoding="utf-8")
    print(f"  wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()

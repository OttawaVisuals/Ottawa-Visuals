#!/usr/bin/env python3
"""Precompute the small numbers the road-safety pages chart.

The raw inputs are ~20 MB (collisions alone are 15 MB), far too much for a
page to fetch for a handful of charts, so this distils them into one JSON:
Traffic/data/derived/stories.json. Run after build_geo_index.py (the weekly
workflow does both).

Story keys (road-safety.html):
  ase_tickets_monthly   -- photo-radar tickets per active camera per month
  ase_collisions        -- collisions at ASE sites before vs after install
  rlc_by_years_since    -- red-light violations per camera-month by camera age
  rlc_before_after      -- collisions by type before vs after a red-light camera
  ped_fmi_by_year       -- pedestrian fatal + major-injury collisions per year
Story keys (Traffic/roads.html):
  enforcement_vs_harm   -- per neighbourhood: share of police stops vs share of injury crashes
  danger_intersections  -- busiest-and-riskiest intersections (collisions per million vehicles)
  camera_sites          -- red-light + photo-radar camera locations
  volume_index          -- intersection volumes vs their own 2015-19 average, per year
  covid_monthly         -- the City's 2020-21 "% of normal" volume monitoring

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


# --------------------------------------------------------------------------
# Roads map page (Traffic/roads.html)
# --------------------------------------------------------------------------

# Neighbourhoods with fewer injury collisions than this get no index: one
# crash more or less would swing it.
MIN_INJURY_FOR_INDEX = 20

# The roads map lists intersections at least this busy; quieter ones produce
# extreme per-vehicle rates from a handful of crashes.
DANGER_MIN_AADT = 10_000
DANGER_MIN_COLLISIONS = 20
DANGER_TOP_N = 60

# "Downtown core" for the volume index: within this distance of Parliament.
CORE_KM = 4.0


def enforcement_vs_harm(geo):
    """Per neighbourhood: share of the city's police stops vs share of its injury collisions.

    Both counted over the same years (the collision years; the police data
    runs 2014-2024 but is trimmed to match). index > 1 means a neighbourhood
    gets more stops than its share of injury crashes; < 1, fewer.
    """
    years = {str(y) for y in COLLISION_YEARS}
    inj, stops, charged = Counter(), Counter(), Counter()
    for r in collisions():
        g = geo.get(r["geo_id"])
        if g and g["neighbourhood"] and r["severity"] in ("Non-fatal injury", "Fatal injury"):
            inj[g["neighbourhood"]] += 1
    for r in read(DATA / "police/traffic_stops_by_area.csv"):
        if r["occ_year"] in years and r["neighbourhood"]:
            stops[r["neighbourhood"]] += int(r["n"])
            if r["how_cleared"] == "Charged":
                charged[r["neighbourhood"]] += int(r["n"])
    t_inj, t_stops = sum(inj.values()), sum(stops.values())
    out = []
    for name in sorted(set(inj) | set(stops)):
        i, s = inj[name], stops[name]
        out.append({
            "neighbourhood": name,
            "injury_collisions": i, "police_stops": s,
            "charged_pct": round(charged[name] / s * 100) if s else None,
            "share_injury_pct": round(i / t_inj * 100, 2),
            "share_stops_pct": round(s / t_stops * 100, 2),
            "index": round((s / t_stops) / (i / t_inj), 2) if i >= MIN_INJURY_FOR_INDEX else None,
        })
    return {"years": sorted(int(y) for y in years), "min_injury_collisions": MIN_INJURY_FOR_INDEX,
            "total_injury_collisions": t_inj, "total_police_stops": t_stops, "areas": out}


def danger_intersections(geo_rows):
    rows = [g for g in geo_rows
            if g["kind"] == "intersection" and g["aadt"] and int(g["aadt"]) >= DANGER_MIN_AADT
            and int(g["collisions"]) >= DANGER_MIN_COLLISIONS and g["collisions_per_mev"]]
    rows.sort(key=lambda g: -float(g["collisions_per_mev"]))
    return {"min_aadt": DANGER_MIN_AADT, "min_collisions": DANGER_MIN_COLLISIONS,
            "candidates": len(rows), "rows": [{
                "geo_id": g["geo_id"], "name": g["name"], "neighbourhood": g["neighbourhood"],
                "lat": float(g["lat"]), "lon": float(g["lon"]),
                "collisions": int(g["collisions"]), "injury_collisions": int(g["injury_collisions"]),
                "pedestrian_collisions": int(g["pedestrian_collisions"]),
                "cyclist_collisions": int(g["cyclist_collisions"]),
                "aadt": int(g["aadt"]), "aadt_year": int(g["aadt_year"]),
                "per_mev": float(g["collisions_per_mev"]),
                "police_stops": int(g["police_stops"]), "red_light_cameras": int(g["red_light_cameras"]),
            } for g in rows[:DANGER_TOP_N]]}


def camera_sites(snaps):
    rlc_install = {f"{r['location']}|{r['camera_facing']}": int(r["install_year"])
                   for r in read(DATA / "city/red_light_violations.csv")}
    ase_install = {r["site_id"]: int(r["install_year"]) for r in read(DATA / "city/ase_violations.csv")}
    out = {"red_light": {}, "photo_radar": []}
    for s in snaps:
        if s["source"] == "red_light_camera" and s["lat"]:
            loc = s["source_name"]
            site = out["red_light"].setdefault(loc, {
                "name": loc, "lat": float(s["lat"]), "lon": float(s["lon"]),
                "installed": rlc_install.get(s["source_key"]), "violations": 0})
            site["violations"] += int(s["n"] or 0)
            site["installed"] = min(site["installed"] or 9999, rlc_install.get(s["source_key"], 9999))
        elif s["source"] == "ase_camera" and s["lat"]:
            out["photo_radar"].append({
                "site_id": s["source_key"], "name": s["source_name"],
                "lat": float(s["lat"]), "lon": float(s["lon"]),
                "installed": ase_install.get(s["source_key"]), "tickets": int(s["n"] or 0)})
    out["red_light"] = list(out["red_light"].values())
    return out


def volume_index(geo):
    """Each counted intersection vs its own 2015-19 average, summarised per year.

    The City counts different intersections each year, so a plain city-wide
    total would mostly track *which* intersections were counted. Comparing each
    one to itself removes that; the median across them is the headline.
    """
    import math
    import statistics
    snapped = {r["source_key"]: r["geo_id"] for r in read(DATA / "derived/snaps.csv")
               if r["source"] == "intersection_volume" and r["geo_id"]}
    obs = defaultdict(dict)
    for r in read(DATA / "city/intersection_volumes.csv"):
        gid = r["geo_id"] or snapped.get(f"{r['year']}|{r['intersection']}")
        if gid and r["aadt"] and float(r["aadt"]) > 0:
            obs[gid][int(r["year"])] = float(r["aadt"])
    base = {g: statistics.mean(v for y, v in o.items() if y <= 2019)
            for g, o in obs.items() if any(y <= 2019 for y in o)}
    downtown = json.loads((ROOT / "corridors.json").read_text(encoding="utf-8"))["downtown"]

    def km(gid):
        g = geo[gid]
        dy = (float(g["lat"]) - downtown["lat"]) * 111.13
        dx = (float(g["lon"]) - downtown["lon"]) * 111.32 * math.cos(math.radians(downtown["lat"]))
        return math.hypot(dx, dy)

    def summary(ratios):
        if len(ratios) < 10:
            return None
        q = statistics.quantiles(ratios, n=4)
        return {"n": len(ratios), "median": round(statistics.median(ratios) * 100, 1),
                "p25": round(q[0] * 100, 1), "p75": round(q[2] * 100, 1)}

    years = sorted({y for o in obs.values() for y in o if y > 2019})
    out = []
    for y in years:
        pairs = [(g, obs[g][y] / base[g]) for g in base if y in obs[g] and g in geo]
        out.append({"year": y,
                    "city": summary([r for _, r in pairs]),
                    "core": summary([r for g, r in pairs if km(g) <= CORE_KM]),
                    "outside_core": summary([r for g, r in pairs if km(g) > CORE_KM])})
    return {"baseline_years": "2015-2019", "core_km": CORE_KM,
            "baseline_intersections": len(base), "by_year": out}


def covid_monthly():
    """City's 2020-21 monitoring: % of normal volume, mean of the monitored
    intersections per month, plus the Macdonald-Cartier Bridge on its own."""
    order = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
    inter, bridge = defaultdict(list), {}
    for r in read(DATA / "city/covid_volumes.csv"):
        key = f"{r['year']}-{order.index(r['month']) + 1:02d}" if r["month"] in order else None
        if not key or not r["pct_day"]:
            continue
        if "bridge" in r["location"].lower() or "cartier" in r["location"].lower():
            bridge[key] = float(r["pct_day"])
        else:
            inter[key].append(float(r["pct_day"]))
    return [{"month": k,
             "intersections": round(sum(inter[k]) / len(inter[k]), 1) if inter.get(k) else None,
             "intersections_n": len(inter.get(k, [])),
             "bridge": bridge.get(k)}
            for k in sorted(set(inter) | set(bridge))]


def build():
    cols = collisions()
    snaps = read(DATA / "derived/snaps.csv")
    geo_rows = read(DATA / "derived/geo_index.csv")
    geo = {g["geo_id"]: g for g in geo_rows}
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
        "enforcement_vs_harm": enforcement_vs_harm(geo),
        "danger_intersections": danger_intersections(geo_rows),
        "camera_sites": camera_sites(snaps),
        "volume_index": volume_index(geo),
        "covid_monthly": covid_monthly(),
    }
    OUT.write_text(json.dumps(stories, indent=1), encoding="utf-8")
    print(f"  wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()

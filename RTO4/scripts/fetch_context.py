#!/usr/bin/env python3
"""The City's own annual traffic counts and collisions -> RTO4/data/context_annual.json.

Three families of Open Ottawa layers, all **annual**:

  * Transportation Intersection Volumes (2018, 2022, 2023, 2024) — AADT of all
    motorized vehicles, plus pedestrian and bicycle counts, per surveyed
    intersection. Field names differ between vintages, hence FIELD_MAPS.
  * Transportation Midblock Volumes (2023, 2024) — AADT per midblock segment,
    each row carrying its own AADT_Year.
  * Collisions (2017-2024) — 94k records; we only pull yearly aggregates.

Why annual data is still worth a section: it is the City's *own* measurement of
how much traffic Ottawa carries, it establishes the pre-RTO4 level our TomTom
collection has no history for, and the 2020 COVID intersection-monitoring series
shows what a genuine step change in commuting looks like in these same counts —
the yardstick for judging whether RTO4 registers when the 2026 edition lands.

What it cannot do: say anything about July 2026. No 2025 or 2026 edition is
published yet. The page says so where the chart sits.
"""

import urllib.parse

from common import ARCGIS, arcgis_query, fetch_json, write_json

# Field names are not stable between vintages: the 2018/2024 layers use
# truncated shapefile-style names, the 2022/2023 layers use the long ones.
INTERSECTION_LAYERS = {
    2018: ("Transportation_Intersection_Volumes_2018", "truncated"),
    2022: ("Intersection_Volume_2022_w_lat_long", "long"),
    2023: ("Transportation_Intersection_Volume_2023", "long"),
    2024: ("Transportation_Intersection_Volumes_2024", "truncated"),
}
FIELD_MAPS = {
    "truncated": {"vehicles": "All_Motori", "peds": "Pedestrian", "bikes": "Bicycles_N"},
    "long": {"vehicles": "All_Motorized_Vehicles_AADT_24_",
             "peds": "Pedestrians_Not_Factored", "bikes": "Bicycles_Not_Factored"},
}

# Same story for midblock: 2024 has AADT_Year + Volume, 2023 has Year +
# All_Motorized_Vehicles_AADT_24_.
MIDBLOCK_LAYERS = {
    "Transportation_Midblock_Volumes_2024": ("AADT_Year", "Volume"),
    "Transportation_Midblock_Volume_2023": ("Year", "All_Motorized_Vehicles_AADT_24_"),
    "Midblock_Volume_2022_w_lat_long": ("Year", "All_Motorized_Vehicles_AADT_24_"),
}
COVID_LAYER = "COVID_19_Traffic_Volume_Monitoring_at_Intersections"


def to_num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def stats(vals):
    vals = [v for v in vals if v is not None and v > 0]
    if not vals:
        return None
    vals.sort()
    return {
        "sites": len(vals),
        "total": int(sum(vals)),
        "mean": round(sum(vals) / len(vals)),
        "median": round(vals[len(vals) // 2]),
    }


def intersections():
    out = {}
    for year, (layer, shape) in INTERSECTION_LAYERS.items():
        fm = FIELD_MAPS[shape]
        try:
            rows = arcgis_query(layer, out_fields=",".join(fm.values()))
        except Exception as e:                                   # noqa: BLE001
            print(f"  intersections {year}: skipped ({e})")
            continue
        out[str(year)] = {
            metric: stats([to_num(r.get(field)) for r in rows])
            for metric, field in fm.items()
        }
        print(f"  intersections {year}: {len(rows)} sites")
    return out


def midblocks():
    by_year = {}
    for layer, (year_field, vol_field) in MIDBLOCK_LAYERS.items():
        try:
            rows = arcgis_query(layer, out_fields=f"{year_field},{vol_field}")
        except Exception as e:                                   # noqa: BLE001
            print(f"  midblock {layer}: skipped ({e})")
            continue
        for r in rows:
            y = str(r.get(year_field) or "").strip()[:4]
            if not y.isdigit():
                continue
            by_year.setdefault(y, []).append(to_num(r.get(vol_field)))
        print(f"  {layer}: {len(rows)} segments")
    return {y: stats(v) for y, v in sorted(by_year.items()) if stats(v)}


def collisions():
    """Yearly collision counts via a server-side group-by (94k rows otherwise).

    num_of_fatal is typed String on this layer, so it cannot be summed
    server-side; only the count and the injury sum are pulled.
    """
    params = {
        "where": "1=1",
        "groupByFieldsForStatistics": "Accident_Year",
        "outStatistics": ('[{"statisticType":"count","onStatisticField":"ID",'
                          '"outStatisticFieldName":"n"},'
                          '{"statisticType":"sum","onStatisticField":"num_of_injuries",'
                          '"outStatisticFieldName":"injuries"}]'),
        "f": "json",
    }
    url = f"{ARCGIS}/Collisions/FeatureServer/0/query?" + urllib.parse.urlencode(params)
    d = fetch_json(url)
    if "error" in d:
        print(f"  collisions: skipped ({d['error'].get('message')})")
        return {}
    out = {}
    for f in d.get("features", []):
        a = f["attributes"]
        y = a.get("Accident_Year")
        if y:
            out[str(y)] = {"collisions": a.get("n"), "injuries": a.get("injuries")}
    print(f"  collisions: {len(out)} years")
    return dict(sorted(out.items()))


MONTH_NUM = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"])}


def covid_monitoring():
    """The 2020 lockdown intersection series — the yardstick for a real step change.

    Note what these columns actually hold: AM / PM / F8HR are **percentages of
    normal volume** ("33%"), not counts, and the AVERAGE column is a 'Y' flag,
    not a number. So this series directly answers "what does a large, real shift
    in Ottawa commuting look like in the City's own counts?" — in March 2020 the
    AM peak fell to roughly a third of normal.
    """
    try:
        rows = arcgis_query(COVID_LAYER, out_fields="YEAR,MONTH,AM,PM,F8HR")
    except Exception as e:                                       # noqa: BLE001
        print(f"  covid monitoring: skipped ({e})")
        return {}

    def pct(v):
        return to_num(str(v).replace("%", "").strip()) if v not in (None, "") else None

    buckets = {}
    for r in rows:
        y, m = r.get("YEAR"), (r.get("MONTH") or "").strip().lower()
        mn = MONTH_NUM.get(m)
        if not y or not mn:
            continue
        b = buckets.setdefault(f"{y}-{mn:02d}", {"am": [], "pm": [], "all_day": []})
        for key, field in (("am", "AM"), ("pm", "PM"), ("all_day", "F8HR")):
            v = pct(r.get(field))
            if v is not None:
                b[key].append(v)

    out = {}
    for k in sorted(buckets):
        b = buckets[k]
        if not b["am"] and not b["all_day"]:
            continue
        out[k] = {
            "sites": max(len(b["am"]), len(b["all_day"])),
            "am_pct_of_normal": round(sum(b["am"]) / len(b["am"]), 1) if b["am"] else None,
            "pm_pct_of_normal": round(sum(b["pm"]) / len(b["pm"]), 1) if b["pm"] else None,
            "all_day_pct_of_normal": (round(sum(b["all_day"]) / len(b["all_day"]), 1)
                                      if b["all_day"] else None),
        }
    print(f"  covid monitoring: {len(out)} months")
    return out


def main():
    write_json("context_annual.json", {
        "note": ("All series here are annual (or monthly for the 2020 COVID set). "
                 "No 2025 or 2026 edition of the volume counts is published yet, so "
                 "these establish the pre-RTO4 level and cannot show RTO4 itself."),
        "intersection_volumes": intersections(),
        "midblock_volumes": midblocks(),
        "collisions": collisions(),
        "covid_intersection_monitoring": covid_monitoring(),
        "sources": {
            "intersection_volumes": "https://open.ottawa.ca/search?q=intersection%20volume",
            "midblock_volumes": "https://open.ottawa.ca/search?q=midblock%20volume",
            "collisions": f"{ARCGIS}/Collisions/FeatureServer/0",
            "covid_intersection_monitoring": f"{ARCGIS}/{COVID_LAYER}/FeatureServer/0",
        },
    })


if __name__ == "__main__":
    main()

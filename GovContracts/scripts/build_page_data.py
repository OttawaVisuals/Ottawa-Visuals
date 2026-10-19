#!/usr/bin/env python3
"""Small public data file for govcontracts.html, from the committed aggregates.

    python GovContracts/scripts/build_page_data.py

Reads data/spend_by_year_category.json, data/spend_by_department_category.json,
data/office_footprint_by_year.json and data/data_coverage.json; writes
data/page.json. Aggregates only: no vendor names and none of rto_candidates.json
(those still need a second human read).

Management consulting combines the GSIN codes and the UNSPSC 8010* family (the
two schemes joined in 2021, see README). IT consulting is NOT charted: the GSIN
IT codes are a narrow subset and UNSPSC 8111* is much broader, so no series
spans the change.
"""
import json
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
YEARS = [str(y) for y in range(2017, 2026)]  # 2026 is a part-year, left out of charts
MGMT = ("Management & business consulting", "Management & business consulting [UNSPSC]")
FURNITURE = "Office furniture and furnishings, including parts"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def main():
    yc = load("spend_by_year_category.json")
    gsin = {y: [0, 0] for y in YEARS}
    unspsc = {y: [0, 0] for y in YEARS}
    for r in yc:
        if r["year"] in gsin and r["category"] == MGMT[0]:
            gsin[r["year"]] = [round(r["spend"]), r["count"]]
        if r["year"] in unspsc and r["category"] == MGMT[1]:
            unspsc[r["year"]] = [round(r["spend"]), r["count"]]
    furn = {y: [0, 0] for y in YEARS}
    for r in load("office_footprint_by_year.json"):
        if r["category"] == FURNITURE and r["year"] in furn:
            furn[r["year"]] = [round(r["spend"]), r["count"]]
    dept = defaultdict(float)
    for r in load("spend_by_department_category.json"):
        if r["category"] in MGMT:
            dept[r["department"].split("|")[0].strip()] += r["spend"]
    top = sorted(dept.items(), key=lambda kv: -kv[1])[:10]
    cov = load("data_coverage.json")
    out = {
        "years": YEARS,
        "last_reliable_month": cov["last_reliable_month"],
        "mgmt_gsin": {"spend": [gsin[y][0] for y in YEARS], "count": [gsin[y][1] for y in YEARS]},
        "mgmt_unspsc": {"spend": [unspsc[y][0] for y in YEARS], "count": [unspsc[y][1] for y in YEARS]},
        "furniture": {"spend": [furn[y][0] for y in YEARS], "count": [furn[y][1] for y in YEARS]},
        "departments": [{"name": n, "spend": round(v)} for n, v in top],
    }
    (DATA / "page.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote data/page.json; last reliable month", cov["last_reliable_month"])


if __name__ == "__main__":
    main()

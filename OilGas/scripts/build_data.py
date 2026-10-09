"""Fetch StatCan series for the oil & gas page and write OilGas/data/oilgas.json.

Raw API responses are cached in OilGas/data/raw/ (gitignored); delete that
folder to force a fresh pull. Run from anywhere:

    python OilGas/scripts/build_data.py
"""
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "oilgas.json"
WDS = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromCubePidCoordAndLatestNPeriods"

# 33-10-0500-01 annual financial + taxation statistics, NAICS member 3 =
# "Oil and gas extraction and support services". Values in $ millions.
FIN_ANNUAL = {
    "revenue": 62,
    "operating_profit": 99,
    "net_income": 104,
    "labour": 82,
    "dividends": 57,
    "fed_tax": 137,
    "prov_tax": 138,
    "tax_total": 139,
    "itc": 133,
}
# 33-10-0225-01 quarterly, same industry; used for years the annual table
# hasn't reached yet. Member ids differ from the annual table.
FIN_QUARTERLY = {
    "revenue": 73,
    "operating_profit": 124,
    "net_income": 109,
    "dividends": 72,
}
# 14-10-0202-01 SEPH annual employment, all employees.
GEOS = {1: "Canada", 10: "Alberta", 9: "Saskatchewan", 11: "British Columbia", 2: "Newfoundland and Labrador"}
# Pipelines (NAICS 486) is suppressed after 2002, so it's left out.
JOBS_NAICS = {11: "extraction", 16: "support", 1: "all_industries"}


def coord(*ids):
    ids = list(ids) + [0] * (10 - len(ids))
    return ".".join(str(i) for i in ids)


def fetch(name, pid, coords, n):
    cache = RAW / f"{name}.json"
    if not cache.exists():
        body = json.dumps([{"productId": pid, "coordinate": c, "latestN": n} for c in coords]).encode()
        req = urllib.request.Request(WDS, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            cache.write_bytes(r.read())
    out = {}
    for item in json.loads(cache.read_text(encoding="utf-8")):
        if item["status"] != "SUCCESS":
            continue
        obj = item["object"]
        out[obj["coordinate"]] = [(p["refPer"], p["value"]) for p in obj["vectorDataPoint"] if p["value"] is not None]
    return out


def main():
    RAW.mkdir(parents=True, exist_ok=True)

    annual = fetch("fin_annual_33100500", 33100500, [coord(1, 3, m) for m in FIN_ANNUAL.values()], 40)
    fin = defaultdict(dict)  # year -> field -> $M
    for key, m in FIN_ANNUAL.items():
        for ref, v in annual.get(coord(1, 3, m), []):
            fin[int(ref[:4])][key] = v
    last_annual = max(fin)

    quarterly = fetch("fin_quarterly_33100225", 33100225, [coord(1, 3, m) for m in FIN_QUARTERLY.values()], 80)
    qsum = defaultdict(lambda: defaultdict(float))
    qcount = defaultdict(lambda: defaultdict(int))
    for key, m in FIN_QUARTERLY.items():
        for ref, v in quarterly.get(coord(1, 3, m), []):
            y = int(ref[:4])
            qsum[y][key] += v
            qcount[y][key] += 1
    # Only full years past the annual table, flagged so the page can say so.
    for y in sorted(qsum):
        if y > last_annual and all(qcount[y][k] == 4 for k in FIN_QUARTERLY):
            fin[y] = {k: round(qsum[y][k]) for k in FIN_QUARTERLY}
            fin[y]["from_quarterly"] = True
    # Overlap check: quarterly sums vs annual table, to show how far they agree.
    overlap = {
        y: {k: [fin[y].get(k), round(qsum[y][k])] for k in FIN_QUARTERLY}
        for y in sorted(qsum)
        if y <= last_annual and all(qcount[y][k] == 4 for k in FIN_QUARTERLY)
    }

    # 18-10-0005-01 CPI, Canada, all-items (annual) — page converts $ to latest-year dollars.
    cpi_raw = fetch("cpi_18100005", 18100005, [coord(2, 2)], 40)
    cpi = {int(ref[:4]): v for ref, v in cpi_raw[coord(2, 2)]}

    jobs_coords = [coord(g, 1, n) for g in GEOS for n in JOBS_NAICS]
    jobs_raw = fetch("jobs_14100202", 14100202, jobs_coords, 40)
    jobs = {}
    for g, gname in GEOS.items():
        series = defaultdict(dict)
        for n, key in JOBS_NAICS.items():
            for ref, v in jobs_raw.get(coord(g, 1, n), []):
                series[int(ref[:4])][key] = v
        jobs[gname] = {str(y): series[y] for y in sorted(series)}

    data = {
        "sources": {
            "finance_annual": "Statistics Canada, Table 33-10-0500-01 (Oil and gas extraction and support services)",
            "finance_quarterly": "Statistics Canada, Table 33-10-0225-01 (same industry, quarters summed)",
            "jobs": "Statistics Canada, Table 14-10-0202-01 (SEPH, all employees)",
            "cpi": "Statistics Canada, Table 18-10-0005-01 (CPI all-items, Canada)",
        },
        "cpi": {str(y): cpi[y] for y in sorted(cpi) if y >= min(fin)},
        "finance": {str(y): fin[y] for y in sorted(fin)},
        "finance_overlap_check": {str(y): v for y, v in overlap.items()},
        "jobs": jobs,
    }
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB); finance {min(fin)}-{max(fin)}")


if __name__ == "__main__":
    main()

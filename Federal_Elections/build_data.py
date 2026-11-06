"""Rebuild the federal election page inputs from Elections Canada's official files.

Run from any directory: python Federal_Elections/build_data.py
Requires pyshp and shapely. Reads the retained official CSV tables in data/ and
downloads the boundary zip if it is missing (it is ~9 MB, so it is not committed).
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import urllib.request
import zipfile
from collections import Counter

import shapefile
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
RAW = HERE / "data"
BASE = "https://www.elections.ca/res/rep/off/ovrGE45/62/data_donnees/"
SOURCES = {
    "results_page": "https://www.elections.ca/content.aspx?section=res&dir=rep/off/45gedata&document=summary&lang=e",
    "table11_districts": BASE + "table_tableau11.csv",
    "table12_candidates": BASE + "table_tableau12.csv",
    "table04_turnout": BASE + "table_tableau04.csv",
    "boundaries": "https://ftp.maps.canada.ca/pub/elections_elections/Electoral-districts_Circonscription-electorale/federal_electoral_districts_boundaries_2023/FED_CA_2023_EN-SHP.zip",
}
BOUNDARY_ZIP = RAW / "fed-boundaries.zip"

PARTIES = {
    "LPC": {"name": "Liberal Party", "color": "#D71920"},
    "CPC": {"name": "Conservative Party", "color": "#1A4782"},
    "NDP": {"name": "New Democratic Party", "color": "#F37021"},
    "BQ": {"name": "Bloc Québécois", "color": "#2BA4D6"},
    "GPC": {"name": "Green Party", "color": "#3D9B35"},
    "PPC": {"name": "People's Party", "color": "#6B5B95"},
    "IND": {"name": "Independent / no affiliation", "color": "#808080"},
    "OTH": {"name": "All other parties", "color": "#A0A3A8"},
}
# English party label (as it appears after the candidate name) -> code.
LABELS = [
    ("NDP-New Democratic Party", "NDP"),
    ("Liberal", "LPC"),
    ("Conservative", "CPC"),
    ("Bloc Québécois", "BQ"),
    ("Green Party", "GPC"),
    ("People's Party - PPC", "PPC"),
    ("Independent", "IND"),
    ("No Affiliation", "IND"),
] + [(label, "OTH") for label in (
    "Marxist-Leninist", "Christian Heritage Party", "Parti Rhinocéros Party", "Communist",
    "Canadian Future Party", "Centrist", "Libertarian", "United Party of Canada (UP)",
    "Animal Protection Party", "Marijuana Party")]
EXPECTED_SEATS = {"LPC": 169, "CPC": 144, "BQ": 22, "NDP": 7, "GPC": 1}
# City insets: anchor riding name and radius (m) of centroid distance, in the boundary CRS.
INSETS = {
    "OTTAWA": ("Ottawa Centre", 38000),
    "TORONTO": ("Toronto Centre", 45000),
    "MONTREAL": ("Outremont", 26000),
    "VANCOUVER": ("Vancouver Centre", 32000),
}
NATIONAL_TOLERANCE_M = 2500
INSET_TOLERANCE_M = 60
MIN_PART_AREA_M2 = 40e6   # drop specks (tiny islands) from the national view only


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())


def write_js(filename, var, value):
    (HERE / filename).write_text(f"window.{var} = " + json.dumps(value, separators=(",", ":")) + ";\n", encoding="utf-8")


def rows(name):
    with (RAW / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))[1:]


def split_candidate(text):
    """'Paul Connors Liberal/Libéral' -> (name, code, incumbent flag). '**' marks incumbents."""
    elected = " ** " in text
    for label, code in LABELS:
        m = re.search(r"\s(?:\*\* )?" + re.escape(label) + r"/[^/]+$", text)
        if m:
            return text[:m.start()].replace("**", "").strip(), code, elected, label
    # Any other registered party: English label is everything before the final "/".
    m = re.search(r"\s(?:\*\* )?([^/]+)/[^/]+$", text)
    return text[:m.start()].replace("**", "").strip(), "OTH", elected, m.group(1).strip()


def build():
    for key, fname in (("table11_districts", "table_tableau11.csv"), ("table12_candidates", "table_tableau12.csv"),
                       ("table04_turnout", "table_tableau04.csv")):
        if not (RAW / fname).exists():
            download(SOURCES[key], RAW / fname)
    if not BOUNDARY_ZIP.exists():
        download(SOURCES["boundaries"], BOUNDARY_ZIP)

    # ---- district table ----
    districts = {}
    for r in rows("table_tableau11.csv"):
        n = int(r[2])
        districts[n] = {"id": n, "name": r[1].split("/")[0].strip(), "province": r[0].split("/")[0],
                        "registered": int(r[4]), "valid": int(r[6]), "rejected": int(r[8]),
                        "ballots": int(r[10]), "turnoutPct": float(r[11]), "elected": r[12]}
    assert len(districts) == 343

    # ---- candidates ----
    candidates = []
    other_labels = Counter()
    for r in rows("table_tableau12.csv"):
        n = int(r[2])
        name, code, elected, label = split_candidate(r[3])
        if code == "OTH":
            other_labels[label] += 1
        candidates.append({"district_id": n, "district": districts[n]["name"], "candidate": name,
                           "party": code, "party_label": label, "votes": int(r[6]), "incumbent": elected})
    assert len(candidates) == 1959, len(candidates)

    ridings, seats, totals = [], Counter(), Counter()
    for n, d in sorted(districts.items(), key=lambda kv: kv[1]["name"]):
        cs = [c for c in candidates if c["district_id"] == n]
        votes = dict.fromkeys(PARTIES, 0)
        for c in cs:
            votes[c["party"]] += c["votes"]
        assert sum(votes.values()) == d["valid"], (n, d["name"])
        top = max(cs, key=lambda c: c["votes"])
        # Table 11's elected candidate ("Surname, Given Party") must be the top vote-getter.
        surname = d["elected"].split(",")[0].strip()
        assert surname in top["candidate"], (n, d["name"], d["elected"], top["candidate"])
        seats[top["party"]] += 1
        totals.update(votes)
        ridings.append({"id": n, "name": d["name"], "province": d["province"], "votes": votes,
                        "candidates": [{"name": c["candidate"], "party": c["party"], "votes": c["votes"]} for c in cs],
                        "valid": d["valid"], "ballots": d["ballots"], "registered": d["registered"],
                        "rejected": d["rejected"], "turnoutPct": d["turnoutPct"]})
    assert dict(seats) == EXPECTED_SEATS, seats

    # ---- turnout history (Table 4: per province, 4 elections) ----
    t4 = rows("table_tableau04.csv")
    history = []
    for i, year in enumerate((2025, 2021, 2019, 2015)):
        electors = sum(int(r[1 + i]) for r in t4)
        ballots = sum(int(r[5 + i]) for r in t4)
        history.append({"year": year, "turnoutPct": round(ballots / electors * 100, 1),
                        "registered": electors, "turnout": ballots})
    history.sort(key=lambda h: h["year"])
    assert history[-1]["turnout"] == sum(r["ballots"] for r in ridings)

    # ---- geometry ----
    z = zipfile.ZipFile(BOUNDARY_ZIP)
    reader = shapefile.Reader(shp=z.open("FED_CA_2023_EN.shp"), shx=z.open("FED_CA_2023_EN.shx"),
                              dbf=z.open("FED_CA_2023_EN.dbf"))
    full = {}
    for rec in reader.iterShapeRecords():
        n = int(rec.record["FED_NUM"])
        full[n] = shape(rec.shape.__geo_interface__)
    assert set(full) == set(districts)

    def feature(n, geom):
        return {"type": "Feature", "properties": {"id": n, "name": districts[n]["name"]}, "geometry": mapping(geom)}

    def national(geom):
        parts = [g for g in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom]) if g.area >= MIN_PART_AREA_M2]
        if not parts:
            parts = [max((geom.geoms if geom.geom_type == "MultiPolygon" else [geom]), key=lambda g: g.area)]
        return unary_union(parts).simplify(NATIONAL_TOLERANCE_M, preserve_topology=True)

    geo = {"FED": {"type": "FeatureCollection",
                   "features": [feature(n, national(g)) for n, g in sorted(full.items())]}}
    inset_members = {}
    by_name = {d["name"]: n for n, d in districts.items()}
    for key, (anchor, radius) in INSETS.items():
        centre = full[by_name[anchor]].centroid
        ids = sorted(n for n, g in full.items() if g.centroid.distance(centre) <= radius)
        inset_members[key] = ids
        geo[key] = {"type": "FeatureCollection",
                    "features": [feature(n, full[n].simplify(INSET_TOLERANCE_M, preserve_topology=True)) for n in ids]}
    with (HERE / "geo.js").open("w", encoding="utf-8") as f:
        for key, collection in geo.items():
            f.write(f"window.{key}_GEO = " + json.dumps(collection, separators=(",", ":")) + ";\n")

    data = {"meta": {"title": "Canada — 2025 federal election", "source": "Elections Canada — April 28, 2025 official voting results",
                      "generated": "2026-11-06", "sources": SOURCES},
            "parties": PARTIES, "ridings": ridings,
            "insets": {k: {"label": k.title(), "ids": v} for k, v in inset_members.items()}}
    write_js("data.js", "ELECTION_DATA", data)
    write_js("turnout.js", "TURNOUT_DATA", {"provinceAll": history})
    with (RAW / "candidates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(candidates[0]))
        w.writeheader()
        w.writerows(candidates)
    (RAW / "results.json").write_text(json.dumps(data, indent=1), encoding="utf-8")

    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.suffix in (".csv", ".zip") and p.name != "candidates.csv"}
    audit = {"sources": SOURCES, "retrieved": "2026-11-06", "sha256": hashes,
             "ridings": len(ridings), "candidates": len(candidates), "party_votes": dict(totals),
             "seats": dict(seats), "valid_votes": sum(totals.values()),
             "ballots": sum(r["ballots"] for r in ridings), "registered": sum(r["registered"] for r in ridings),
             "turnout_history": history, "other_party_labels": dict(other_labels),
             "inset_ridings": {k: len(v) for k, v in inset_members.items()}}
    (RAW / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in audit.items() if k not in ("sha256", "sources")}, indent=1))
    for p in ("data.js", "geo.js", "turnout.js"):
        print(p, (HERE / p).stat().st_size)


if __name__ == "__main__":
    build()

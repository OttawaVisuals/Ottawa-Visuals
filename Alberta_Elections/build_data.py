"""Rebuild Alberta's 2023 election inputs from retained official sources.

Run from any directory: python Alberta_Elections/build_data.py
Requires openpyxl, beautifulsoup4, pyshp and shapely (read-only source extraction).
"""
from pathlib import Path
import csv
import hashlib
import json
import zipfile
from collections import Counter

import openpyxl
import shapefile
from bs4 import BeautifulSoup
from shapely.geometry import shape, mapping

HERE = Path(__file__).resolve().parent
RAW = HERE / "data"
SOURCES = {
    "results": "https://www.elections.ab.ca/uploads/2023-Provincial-General-Election-Statement-of-Vote.xlsx",
    "boundaries": "https://www.elections.ab.ca/uploads/2019Boundaries_ED-Shapefiles.zip",
    "history": "https://www.elections.ab.ca/elections/election-results/historical-results/",
}
PARTIES = {
    "UCP": {"name": "United Conservative Party", "color": "#2365A0"},
    "NDP": {"name": "Alberta New Democratic Party", "color": "#E87524"},
    "LIB": {"name": "Alberta Liberal Party", "color": "#C93E49"},
    "GPA": {"name": "Green Party of Alberta", "color": "#378249"},
    "AP": {"name": "Alberta Party", "color": "#38A3B1"},
    "APA": {"name": "Advantage Party of Alberta", "color": "#64748B"},
    "CP-A": {"name": "Communist Party – Alberta", "color": "#9C3848"},
    "PAPA": {"name": "Pro-Life Alberta Political Association", "color": "#706296"},
    "REF": {"name": "Reform Party", "color": "#7C7851"},
    "SM": {"name": "Solidarity Movement of Alberta", "color": "#836C8C"},
    "BPA": {"name": "The Buffalo Party of Alberta", "color": "#76634D"},
    "TIP": {"name": "The Independence Party of Alberta", "color": "#7A8098"},
    "WIPA": {"name": "Wildrose Independence Party of Alberta", "color": "#6B8070"},
    "WLC": {"name": "Wildrose Loyalty Coalition", "color": "#877566"},
    "IND": {"name": "Independent candidates", "color": "#808080"},
}

def write_js(filename, var, value):
    (HERE / filename).write_text(f"window.{var} = " + json.dumps(value, separators=(",", ":")) + ";\n", encoding="utf-8")

def build():
    soup = BeautifulSoup((RAW / "historical-results.html").read_text(encoding="utf-8"), "html.parser")
    tables = soup.find_all("table")
    official = {}
    for row in tables[0].find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) == 5 and cells[0] != "TOTAL":
            official[cells[0]] = int(cells[3].replace(",", ""))
    assert len(official) == 15

    z = zipfile.ZipFile(RAW / "2019-boundaries.zip")
    stem = "EDS_ENACTED_BILL33_15DEC2017"
    reader = shapefile.Reader(shp=z.open(stem + ".shp"), shx=z.open(stem + ".shx"), dbf=z.open(stem + ".dbf"))
    features, names = [], {}
    for rec in reader.iterShapeRecords():
        n = int(rec.record["EDNumber20"])
        # The old geometry's name predates the division's 2022 renaming.
        name = "Calgary-Bhullar-McCall" if n == 17 else rec.record["EDName2017"]
        names[n] = name
        geom = shape(rec.shape.__geo_interface__)
        simple = geom.simplify(60, preserve_topology=True)
        features.append({"type": "Feature", "properties": {"name": name, "id": n}, "geometry": mapping(simple)})
    assert len(features) == len(names) == 87

    wb = openpyxl.load_workbook(RAW / "2023-statement-of-vote.xlsx", read_only=True, data_only=True)
    ridings, candidates, district_turnout = [], [], {}
    totals = Counter()
    seats = Counter()
    majority = Counter()
    for sheet in wb:
        n = int(sheet.title)
        rows = list(sheet.values)
        headers = list(rows[0])
        start = 4
        stop = headers.index("Names on List")
        total = next(r for r in rows if r[1] == "Total (All Voting Options)")
        votes = dict.fromkeys(PARTIES, 0)
        for col in range(start, stop):
            candidate, party = headers[col].rsplit("\n", 1)
            assert party in PARTIES, (sheet.title, party)
            count = int(total[col])
            # Independently sum voting-location rows, excluding source subtotal rows.
            locations = [r for r in rows[1:] if r[2] in ("Election Day", "Advance", "Mobile", "Special Ballot")]
            assert sum(int(r[col] or 0) for r in locations) == count, (n, candidate)
            votes[party] += count
            candidates.append({"district_id": n, "district": names[n], "candidate": candidate, "party": party, "votes": count})
        valid = int(total[headers.index("Valid Ballots Cast")])
        ballots = int(total[headers.index("Total Ballots Cast")])
        registered = int(total[stop])
        assert sum(votes.values()) == valid
        rejected = int(total[headers.index("Rejected Ballots Cast")])
        declined = int(total[headers.index("Declined Ballots Cast")])
        # Some source totals include administratively counted ballots with no vote category.
        unclassified = ballots - valid - rejected - declined
        assert unclassified >= 0
        totals.update(votes)
        winner = max(votes, key=votes.get)
        seats[winner] += 1
        if votes[winner] * 2 > valid:
            majority[winner] += 1
        ridings.append({"id": n, "name": names[n], "votes": votes,
                        "candidates": [c for c in candidates if c["district_id"] == n],
                        "valid": valid, "ballots": ballots, "registered": registered,
                        "rejected": rejected, "declined": declined, "unclassified": unclassified})
        district_turnout[names[n]] = [{"year": 2023, "turnoutPct": ballots / registered * 100,
                                            "registered": registered, "turnout": ballots}]
    name_map = {"NDP": "Alberta NDP", "IND": "Independent Candidates"}
    differences = {code: {"workbook": count, "historical_web_table": official[name_map.get(code, PARTIES[code]["name"])]}
                   for code, count in totals.items() if count != official[name_map.get(code, PARTIES[code]["name"]) ]}
    assert sum(totals.values()) == 1764915
    assert seats == {"UCP": 49, "NDP": 38}
    assert len(candidates) == 349

    history_table = next(t for t in tables if "Names on List" in t.get_text() and "1975" in t.get_text())
    history = []
    for tr in history_table.find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) != 7:
            continue
        year = int(cells[0].rstrip("*"))
        history.append({"year": year, "turnoutPct": float(cells[6]),
                        "registered": int(cells[5].replace(",", "")),
                        "turnout": int(cells[4].replace(",", ""))})
    history.sort(key=lambda r: r["year"])
    assert len(history) == 14 and history[-1]["year"] == 2023
    web_2023 = history[-1].copy()
    history[-1] = {"year": 2023, "turnoutPct": round(sum(r["ballots"] for r in ridings) / sum(r["registered"] for r in ridings) * 100, 1),
                   "turnout": sum(r["ballots"] for r in ridings), "registered": sum(r["registered"] for r in ridings),
                   "source": "2023 Statement of Vote workbook"}

    data = {"meta": {"title": "Alberta — 2023 general election", "source": "Elections Alberta — May 29, 2023 Statement of Vote",
                      "generated": "2026-11-01", "sample": False, "sources": SOURCES},
            "parties": PARTIES, "ridings": sorted(ridings, key=lambda r: r["name"])}
    write_js("data.js", "ELECTION_DATA", data)
    (RAW / "results.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    with (RAW / "candidates.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(candidates[0]))
        writer.writeheader()
        writer.writerows(candidates)
    write_js("turnout.js", "TURNOUT_DATA", {"provinceAll": history, "province": history[-3:], "districts": district_turnout})
    with (HERE / "geo.js").open("w", encoding="utf-8") as f:
        for key, subset in [("ALBERTA", features), ("CALGARY", [x for x in features if x["properties"]["id"] <= 26]),
                            ("EDMONTON", [x for x in features if 27 <= x["properties"]["id"] <= 46])]:
            f.write(f"window.{key}_GEO = " + json.dumps({"type": "FeatureCollection", "features": subset}, separators=(",", ":")) + ";\n")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.suffix in (".xlsx", ".zip", ".html")}
    audit = {"sources": SOURCES, "retrieved": "2026-11-01", "sha256": hashes,
             "ridings": len(ridings), "candidates": len(candidates), "party_votes": totals,
             "seats": seats, "majority_seats": majority, "valid_votes": sum(totals.values()),
             "ballots": sum(r["ballots"] for r in ridings), "registered": sum(r["registered"] for r in ridings),
             "unclassified_ballots": sum(r["unclassified"] for r in ridings), "turnout_history": history,
             "source_discrepancies": {"party_votes": differences, "historical_web_2023": web_2023,
                                      "historical_web_party_sum": sum(official.values()), "historical_web_total_row": 1760605}}
    (RAW / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in audit.items() if k not in ("sha256", "turnout_history", "sources")}, indent=2))

if __name__ == "__main__":
    build()

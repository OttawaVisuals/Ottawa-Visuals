"""Build BC 2024 consolidation data from retained Elections BC sources.
Run: python BC_Elections/build_data.py
Requires pypdf, beautifulsoup4 and shapely. No source files are modified.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import re
import unicodedata

from bs4 import BeautifulSoup
from pypdf import PdfReader
from shapely.geometry import shape, mapping

HERE = Path(__file__).resolve().parent
RAW = HERE / "data"
SOURCES = {
    "results": "https://catalogue.data.gov.bc.ca/dataset/44914a35-de9a-4830-ac48-870001ef8935/resource/4e7be8e3-0805-4f39-87f3-47c4c29e262d/download/provincial_voting_results_by_voting_place.csv",
    "statement": "https://elections.bc.ca/docs/rpt/statement-of-votes-2024-provincial-election.pdf",
    "boundaries": "https://catalogue.data.gov.bc.ca/dataset/1cba4b16-263f-4d42-8d84-f5fecaa03d1a",
    "boundary_request": "https://openmaps.gov.bc.ca/geo/pub/WHSE_ADMIN_BOUNDARIES.EBC_ELECTORAL_DISTS_BS11_SVW/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames=pub:WHSE_ADMIN_BOUNDARIES.EBC_ELECTORAL_DISTS_BS11_SVW&outputFormat=application/json&count=100",
    "turnout": "https://elections.bc.ca/resources/results/voter-turnout/",
}
PARTIES = {
    "CP": {"name": "Conservative Party", "color": "#2365A0"},
    "NDP": {"name": "BC New Democratic Party", "color": "#E87524"},
    "GP": {"name": "BC Green Party", "color": "#378249"},
    "IND": {"name": "Independent", "color": "#808080"},
    "UNA": {"name": "Unaffiliated", "color": "#6B7280"},
    "LBN": {"name": "Libertarian", "color": "#8A7138"},
    "FPBC": {"name": "Freedom Party of BC", "color": "#836C8C"},
    "COMM": {"name": "Communist Party of BC", "color": "#A63C49"},
    "CHP": {"name": "Christian Heritage Party of B.C.", "color": "#76634D"},
}
CODE = {v["name"]: k for k, v in PARTIES.items()}
CODE.update({"BC NDP": "NDP", "": "UNA"})
EXPECTED = {"CP": 911153, "NDP": 944579, "GP": 173377, "IND": 47117, "UNA": 25464,
            "LBN": 1380, "FPBC": 1267, "COMM": 639, "CHP": 365}

def norm(value):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower())

def js(name, var, data):
    (HERE / name).write_text(f"window.{var} = " + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8")

def build():
    rows = [r for r in csv.DictReader((RAW / "voting-place-results.csv").open(encoding="utf-8-sig", newline=""))
            if r["EVENT_NAME"] == "2024 Provincial General Election"]
    assert len({r["ID"] for r in rows}) == len(rows)
    counts, elected = Counter(), {}
    names, rejects = {}, Counter()
    combined = 0
    for r in rows:
        ed = r["ED_ABBREVIATION"]
        names[ed] = r["ED_NAME"]
        if not r["VOTES_CONSIDERED"].strip():
            # Combined source cells carry no count; it is reported at the named destination.
            assert r["COMBINED_INDICATOR"] == "Y"
            combined += 1
            continue
        n = int(r["VOTES_CONSIDERED"])
        if r["VOTE_CATEGORY"] == "Rejected":
            rejects[ed] += n
        else:
            assert r["VOTE_CATEGORY"] == "Valid" and r["CANDIDATE"]
            key = (ed, r["CANDIDATE"], CODE[r["AFFILIATION"]])
            counts[key] += n
            elected[key] = r["ELECTED"] == "Y"

    pdf = PdfReader(RAW / "statement-of-votes-2024.pdf")
    district_text = "\n".join(p.extract_text() for p in pdf.pages[17:20])
    # Published summary, printed pages 13–15: name, NDP/CP/GP/other, valid/rejected/ballots/electors/rate.
    summaries = {}
    pattern = r"^(.+?)\s+((?:(?:[\d,]+|---)\s+){8})([\d.]+)%\s*$"
    for line in district_text.splitlines():
        m = re.match(pattern, line)
        if m and norm(m[1]) in {norm(n) for n in names.values()}:
            nums = [int(x.replace(",", "")) if x != "---" else 0 for x in m[2].split()]
            summaries[norm(m[1])] = nums + [float(m[3])]
    assert len(summaries) == len(names) == 93, len(summaries)

    candidate_text = norm("\n".join(p.extract_text() for p in pdf.pages[9:17]))
    candidates, pdf_name_gaps = [], []
    for (ed, name, code), count in counts.items():
        full = " ".join(reversed(name.split(", ", 1)))
        affiliation = "BC NDP" if code == "NDP" else PARTIES[code]["name"]
        needle = norm(full + affiliation + str(count))
        if needle not in candidate_text:
            pdf_name_gaps.append({"district": names[ed], "name": full, "party": code, "votes": count})
        candidates.append({"district_id": ed, "district": names[ed], "candidate": full,
                           "party": code, "votes": count, "elected": elected[(ed, name, code)]})
    assert not pdf_name_gaps, pdf_name_gaps

    totals, seats, majority = Counter(), Counter(), Counter()
    ridings, district_turnout = [], {}
    for ed, name in sorted(names.items(), key=lambda x: x[1]):
        cs = [c for c in candidates if c["district_id"] == ed]
        votes = dict.fromkeys(PARTIES, 0)
        for c in cs:
            votes[c["party"]] += c["votes"]
        top = max(cs, key=lambda c: c["votes"])
        assert sum(c["elected"] for c in cs) == 1 and top["elected"], name
        a = summaries[norm(name)]
        assert [votes["NDP"], votes["CP"], votes["GP"], sum(v for k, v in votes.items() if k not in ("NDP", "CP", "GP"))] == a[:4], name
        assert sum(votes.values()) == a[4] and rejects[ed] == a[5] and a[4]+a[5] == a[6], name
        assert abs(a[6] / a[7] * 100 - a[8]) < .006, name
        totals.update(votes)
        seats[top["party"]] += 1
        if top["votes"] * 2 > a[4]:
            majority[top["party"]] += 1
        ridings.append({"id": ed, "name": name, "votes": votes, "candidates": cs,
                        "valid": a[4], "rejected": a[5], "ballots": a[6], "registered": a[7]})
        district_turnout[name] = [{"year": 2024, "turnoutPct": a[8], "registered": a[7], "turnout": a[6]}]
    assert totals == EXPECTED, totals
    assert seats == {"NDP": 47, "CP": 44, "GP": 2}, seats
    assert sum(r["registered"] for r in ridings) == 3609288
    assert sum(r["ballots"] for r in ridings) == 2109658

    soup = BeautifulSoup((RAW / "turnout.html").read_text(encoding="utf-8"), "html.parser")
    history = []
    for tr in soup.find("table").find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) == 4 and "General Election" in cells[0]:
            history.append({"year": int(cells[0][:4]), "turnoutPct": float(cells[1].rstrip("%")),
                            "registered": int(cells[2].replace(",", "")), "turnout": int(cells[3].replace(",", ""))})
    history.sort(key=lambda r: r["year"])
    assert len(history) == 8 and history[-1]["turnout"] == 2109658

    with gzip.open(RAW / "boundaries-2023.geojson.gz", "rt", encoding="utf-8") as f:
        geo = json.load(f)
    assert len(geo["features"]) == 93
    assert {f["properties"]["ED_ABBREVIATION"] for f in geo["features"]} == set(names)
    features = []
    for f in geo["features"]:
        ed = f["properties"]["ED_ABBREVIATION"]
        geometry = shape(f["geometry"]).simplify(60, preserve_topology=True)
        assert geometry.is_valid, ed
        features.append({"type": "Feature", "properties": {"name": names[ed], "id": ed}, "geometry": mapping(geometry)})
    metro_prefixes = ("Vancouver-", "West Vancouver-", "North Vancouver-", "Burnaby", "Surrey", "Richmond", "New Westminster", "Coquitlam", "Port Coquitlam", "Port Moody", "Delta")
    capital_names = {"Victoria-Beacon Hill", "Victoria-Swan Lake", "Saanich South", "Oak Bay-Gordon Head", "Esquimalt-Colwood", "Langford-Highlands"}
    with (HERE / "geo.js").open("w", encoding="utf-8") as f:
        for var, selected in [("BC", features), ("METRO", [x for x in features if x["properties"]["name"].startswith(metro_prefixes)]),
                              ("CAPITAL", [x for x in features if x["properties"]["name"] in capital_names])]:
            f.write(f"window.{var}_GEO = " + json.dumps({"type": "FeatureCollection", "features": selected}, separators=(",", ":")) + ";\n")
    data = {"meta": {"title": "British Columbia — 2024 general election", "source": "Elections BC — October 19, 2024 Statement of Votes and DataBC results",
                     "generated": "2026-11-01", "sources": SOURCES}, "parties": PARTIES, "ridings": ridings}
    js("data-2024.js", "ELECTION_DATA", data)
    js("turnout-2024.js", "TURNOUT_DATA", {"provinceAll": history, "province": history[-3:], "districts": district_turnout})
    (RAW / "results-2024.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    with (RAW / "candidates-2024.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(candidates[0]))
        writer.writeheader()
        writer.writerows(sorted(candidates, key=lambda c: (c["district"], c["candidate"])))
    audit = {"sources": SOURCES, "retrieved": "2026-11-01", "ridings": len(ridings), "candidates": len(candidates),
             "party_votes": totals, "seats": seats, "majority_seats": majority, "valid_votes": sum(totals.values()),
             "rejected": sum(rejects.values()), "ballots": sum(r["ballots"] for r in ridings), "registered": 3609288,
             "pdf_districts_reconciled": len(summaries), "pdf_candidates_reconciled": len(candidates)-len(pdf_name_gaps),
             "combined_blank_cells_skipped": combined, "boundary_crs": "EPSG:3005", "boundary_simplification_metres": 60,
             "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.iterdir() if p.name in ("voting-place-results.csv", "statement-of-votes-2024.pdf", "turnout.html", "boundaries-2023.geojson.gz")}}
    (RAW / "audit-2024.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in audit.items() if k not in ("sha256", "sources")}, indent=2))

if __name__ == "__main__":
    build()

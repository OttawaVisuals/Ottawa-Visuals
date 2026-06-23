import csv
import json

YEAR = "2025"

PARTY_INFO = {
    "PCP": {"name": "Progressive Conservative", "color": "#1A4FA0"},
    "LIB": {"name": "Liberal", "color": "#D71920"},
    "NDP": {"name": "New Democratic", "color": "#F37021"},
    "GPO": {"name": "Green", "color": "#45A049"},
    "NBO": {"name": "New Blue", "color": "#0F5FA6"},
    "CEN": {"name": "Ontario Centrist", "color": "#8A8D91"},
    "IND": {"name": "Independent", "color": "#6B6B6B"},
}
OTHER_KEY = "OTH"
OTHER_INFO = {"name": "Other / Independent", "color": "#8A8D91"}

def clean_district(raw):
    # "001 - Ajax" -> "Ajax"
    return raw.split(" - ", 1)[1].strip() if " - " in raw else raw.strip()

ridings = {}
with open("Explorer_All_22062026_101900.csv", encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row or row[0] != YEAR:
            continue
        votes = int(row[3])
        district = clean_district(row[4])
        party = row[5].strip()
        key = party if party in PARTY_INFO else OTHER_KEY
        r = ridings.setdefault(district, {})
        r[key] = r.get(key, 0) + votes

used_parties = set()
for v in ridings.values():
    used_parties.update(v.keys())

parties = {}
for code in PARTY_INFO:
    if code in used_parties:
        parties[code] = PARTY_INFO[code]
if OTHER_KEY in used_parties:
    parties[OTHER_KEY] = OTHER_INFO

riding_list = []
for name in sorted(ridings.keys()):
    votes = {code: ridings[name].get(code, 0) for code in parties}
    riding_list.append({"name": name, "votes": votes})

election_data = {
    "meta": {
        "title": "Ontario — 2025 general election results",
        "source": "Elections Ontario — Explorer export (2025-02-27 general election)",
        "generated": "2026-06-22",
        "sample": False,
    },
    "parties": parties,
    "ridings": riding_list,
}

with open("data.js", "w", encoding="utf-8") as f:
    f.write("window.ELECTION_DATA = ")
    json.dump(election_data, f, separators=(",", ":"))
    f.write(";\n")

print(f"data.js written: {len(riding_list)} ridings, parties={list(parties.keys())}")

# ---- Wrap the 3 original GeoJSON files (Ontario.json / Ottawa.json / SouthernOntario.json)
# as separate JS globals, untouched — no merging, no resolution-picking between them.
# These were hand-cut in mapshaper directly in the source shapefile's projected CRS
# (Ontario Lambert Conformal Conic, in metres — see ELECTORAL_DISTRICT.prj). That projection
# is what gives many ridings their clean rectangular look. Reprojecting to lat/lon would add
# back a few degrees of grid-convergence rotation and skew those rectangles — so the page
# renders the planar coordinates untouched, as a flat, literal Cartesian plane.

def load_raw(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

geo_sources = {
    "ONTARIO": ("Ontario.json", "window.ONTARIO_GEO"),
    "OTTAWA": ("Ottawa.json", "window.OTTAWA_GEO"),
    "SOUTH": ("SouthernOntario.json", "window.SOUTH_GEO"),
}

with open("geo.js", "w", encoding="utf-8") as f:
    for region, (path, var) in geo_sources.items():
        geo = load_raw(path)
        f.write(f"{var} = ")
        json.dump(geo, f, separators=(",", ":"))
        f.write(";\n")

geo_names = {feat["properties"].get("ENGLISH_NA") for feat in load_raw("Ontario.json")["features"]}
data_names = set(ridings.keys())
missing_in_geo = sorted(data_names - geo_names)
missing_in_data = sorted(geo_names - data_names)
print(f"geo.js written: ONTARIO_GEO/OTTAWA_GEO/SOUTH_GEO from the 3 original files")
print(f"  names in data but not in Ontario.json ({len(missing_in_geo)}): {missing_in_geo}")
print(f"  names in Ontario.json but not in data ({len(missing_in_data)}): {missing_in_data}")

# ---- Historical turnout: full province history (1981-2025) + last 3 elections per district ----

TURNOUT_YEARS = ["2018", "2022", "2025"]

province_all = []
with open("Explorer_Election_22062026_101948.csv", encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        if not row or not row[0].strip().isdigit():
            continue
        year = row[0]
        registered = int(row[6])
        turnout_count = int(row[7])
        province_all.append(
            {
                "year": int(year),
                "registered": registered,
                "turnout": turnout_count,
                "turnoutPct": round(turnout_count / registered * 100, 2),
            }
        )
province_all.sort(key=lambda r: r["year"])
province_turnout = [r for r in province_all if str(r["year"]) in TURNOUT_YEARS]

# province-wide winning party per year, straight from Elections Ontario's own party-level
# seat counts (Explorer_Party export) — covers every election back to 1981, not just the
# years we have candidate-level riding data for.
def match_party_code(name):
    n = name.lower()
    if "progressive conservative" in n:
        return "PCP"
    if "liberal" in n:
        return "LIB"
    if "new democratic" in n:
        return "NDP"
    if "green" in n:
        return "GPO"
    if "new blue" in n:
        return "NBO"
    if "centrist" in n:
        return "CEN"
    if n.strip() == "independent":
        return "IND"
    return None

party_rows_by_year = {}
with open("Explorer_Party_22062026_154945.csv", encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        if not row or not row[0].strip().isdigit():
            continue
        yr = int(row[0])
        party_rows_by_year.setdefault(yr, []).append({"name": row[4], "seats": int(row[6])})

year_winner = {}
for yr, rows in party_rows_by_year.items():
    top = max(rows, key=lambda r: r["seats"])
    code = match_party_code(top["name"])
    info = PARTY_INFO.get(code, OTHER_INFO)
    year_winner[yr] = {"code": code or OTHER_KEY, "name": top["name"], "color": info["color"], "seats": top["seats"]}

for r in province_all:
    r["winner"] = year_winner.get(r["year"])

district_turnout = {}
with open("Explorer_Electoral_District_22062026_101854.csv", encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        if not row or row[0] not in TURNOUT_YEARS:
            continue
        year = int(row[0])
        district = clean_district(row[4])
        registered = int(row[6])
        turnout_count = int(row[7])
        district_turnout.setdefault(district, []).append(
            {
                "year": year,
                "registered": registered,
                "turnout": turnout_count,
                "turnoutPct": round(turnout_count / registered * 100, 2),
            }
        )

for name in district_turnout:
    district_turnout[name].sort(key=lambda r: r["year"])

turnout_data = {
    "meta": {
        "title": "Ontario — historical voter turnout",
        "source": "Elections Ontario — Explorer export",
        "years": [int(y) for y in TURNOUT_YEARS],
    },
    "provinceAll": province_all,
    "province": province_turnout,
    "districts": district_turnout,
}

with open("turnout.js", "w", encoding="utf-8") as f:
    f.write("window.TURNOUT_DATA = ")
    json.dump(turnout_data, f, separators=(",", ":"))
    f.write(";\n")

missing_turnout = sorted(set(ridings.keys()) - set(district_turnout.keys()))
print(f"turnout.js written: province years={[r['year'] for r in province_turnout]}, "
      f"{len(district_turnout)} districts")
print(f"  districts missing turnout history ({len(missing_turnout)}): {missing_turnout}")

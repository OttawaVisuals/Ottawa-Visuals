"""Build reproducible, explicitly estimated 2025-26 PWHL team itineraries.

Run from the repository root. Road estimates are cached after the first OSRM
request; airport coordinates are a small snapshot of OurAirports data.
"""

import csv
import datetime as dt
import json
import math
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "json" / "pwhl_travel_2025_26.json"
CACHE = DATA / "pwhl_travel_road_cache.json"
SEASON = "8"
BUS_LIMIT_KM = 400 * 1.609344
RETURN_GAP_DAYS = 4
BASE_VENUE = {
    "BOS": "Tsongas Center | Lowell",
    "MIN": "Grand Casino Arena | St. Paul",
    "MTL": "Place Bell | Laval",
    "NY": "Prudential Center | Newark",
    "OTT": "TD Place | Ottawa",
    "SEA": "Climate Pledge Arena | Seattle",
    "TOR": "Coca-Cola Coliseum | Toronto",
    "VAN": "Pacific Coliseum | Vancouver",
}
HOME_MARKET_CITIES = {
    "BOS": {"Lowell", "Boston"}, "MIN": {"St. Paul"},
    "MTL": {"Laval", "Montréal"}, "NY": {"Newark", "New York"},
    "OTT": {"Ottawa"}, "SEA": {"Seattle"},
    "TOR": {"Toronto"}, "VAN": {"Vancouver"},
}
# Chosen major commercial airport for each venue, without checking flight schedules.
AIRPORT_FOR_VENUE = {
    "TD Place | Ottawa": "CYOW",
    "Canadian Tire Centre | Ottawa": "CYOW",
    "Coca-Cola Coliseum | Toronto": "CYYZ",
    "Pacific Coliseum | Vancouver": "CYVR",
    "Climate Pledge Arena | Seattle": "KSEA",
    "Allstate Arena | Chicago": "KORD",
    "Scotiabank Centre | Halifax": "CYHZ",
    "Place Bell | Laval": "CYUL",
    "Prudential Center | Newark": "KEWR",
    "Grand Casino Arena | St. Paul": "KMSP",
    "Canada Life Centre | Winnipeg": "CYWG",
    "Scotiabank Saddledome | Calgary": "CYYC",
    "Tsongas Center | Lowell": "KBOS",
    "Agganis Arena | Boston": "KBOS",
    "TD Garden | Boston": "KBOS",
    "Bell Centre | Montréal": "CYUL",
    "Videotron Centre | Quebec City": "CYQB",
    "Madison Square Garden | New York": "KLGA",
    "Capital One Arena | Washington": "KDCA",
    "American Airlines Center | Dallas": "KDFW",
    "Little Caesars Arena | Detroit": "KDTW",
    "Ball Arena | Denver": "KDEN",
    "TD Coliseum | Hamilton": "CYYZ",
    "Scotiabank Arena | Toronto": "CYYZ",
    "Rogers Place | Edmonton": "CYEG",
}


def read_csv(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def point(row, lat="latitude", lon="longitude"):
    return [float(row[lon]), float(row[lat])]


def great_circle(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [*a, *b])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))


road_cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def road(a, b):
    if a == b:
        return {"km": 0.0, "hours": 0.0}
    key = "|".join(f"{p[0]:.6f},{p[1]:.6f}" for p in (a, b))
    reverse = "|".join(f"{p[0]:.6f},{p[1]:.6f}" for p in (b, a))
    if key not in road_cache:
        if reverse in road_cache:
            return road_cache[reverse]
        url = f"https://router.project-osrm.org/route/v1/driving/{a[0]},{a[1]};{b[0]},{b[1]}?overview=false"
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=40) as response:
                    result = json.load(response)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        if result.get("code") != "Ok" or not result.get("routes"):
            raise RuntimeError(f"No road route for {key}: {result.get('code')}")
        route = result["routes"][0]
        road_cache[key] = {"km": round(route["distance"] / 1000, 1), "hours": round(route["duration"] / 3600, 2)}
        CACHE.write_text(json.dumps(road_cache, indent=2) + "\n", encoding="utf-8")
        time.sleep(0.12)
    return road_cache[key]


venues = {
    row["venue"]: point(row, "Latitude", "Longitude")
    for row in read_csv("PWHL_Venues.csv") if row["Latitude"] and row["Longitude"]
}
airports = {
    row["icao"]: {"name": row["name"], "iata": row["iata"], "point": point(row)}
    for row in read_csv("pwhl_travel_airports.csv")
}
all_games = [row for row in read_csv("pwhl_game_summaries.csv")
             if row["season_id"] == SEASON and row["is_final"] == "TRUE"]
assert len(all_games) == 120, f"Expected 120 games, got {len(all_games)}"
assert all(game["venue"] in AIRPORT_FOR_VENUE for game in all_games)
source_names = {row["team_code"]: row["team_name"]
                for row in read_csv("pwhl_teams.csv") if row["season_id"] == SEASON}
assert set(source_names) == set(BASE_VENUE)
display_names = dict(source_names, MTL="Montréal Victoire")


def city(venue):
    return venue.split(" | ")[-1]


def make_leg(origin, destination, date, reason, game_id=None):
    a, b = venues[origin], venues[destination]
    direct_km = round(great_circle(a, b), 1)
    # A road route cannot be shorter than great-circle distance. This avoids
    # unnecessary long-distance OSRM calls when the mode is clearly air.
    direct_road = road(a, b) if direct_km <= BUS_LIMIT_KM else None
    mode = "bus" if direct_road and direct_road["km"] <= BUS_LIMIT_KM else "air"
    segments = []
    if mode == "bus":
        segments.append({"mode": "bus", "from": a, "to": b, **direct_road,
                         "label": f"{city(origin)} → {city(destination)}"})
    else:
        from_code = AIRPORT_FOR_VENUE[origin]
        to_code = AIRPORT_FOR_VENUE[destination]
        first, last = airports[from_code]["point"], airports[to_code]["point"]
        from_label, to_label = airports[from_code]["iata"], airports[to_code]["iata"]
        if from_code == to_code:
            raise RuntimeError(f"Same airport for an air leg: {origin} → {destination}")
        drive_out, drive_in = road(a, first), road(last, b)
        flight_km = round(great_circle(first, last), 1)
        # Scenario only: 800 km/h cruise plus 2 h total for airport and flight overhead.
        flight_hours = round(flight_km / 800 + 2, 2)
        segments = [
            {"mode": "drive", "from": a, "to": first, **drive_out,
             "label": f"{city(origin)} rink → {from_label}"},
            {"mode": "air", "from": first, "to": last, "km": flight_km, "hours": flight_hours,
             "label": f"{from_label} → {to_label}"},
            {"mode": "drive", "from": last, "to": b, **drive_in,
             "label": f"{to_label} → {city(destination)} rink"},
        ]
    return {
        "date": date.isoformat(), "reason": reason, "game_id": game_id,
        "from": origin, "to": destination, "from_city": city(origin), "to_city": city(destination),
        "mode": mode, "direct_km": direct_km,
        "km": round(sum(s["km"] for s in segments), 1),
        "hours": round(sum(s["hours"] for s in segments), 2),
        "segments": segments,
    }


def build_team(code):
    base = BASE_VENUE[code]
    name = source_names[code]
    games = sorted((row for row in all_games if name in (row["home_team"], row["visitor_team"])),
                   key=lambda row: dt.datetime.strptime(" ".join(row["game_date"].split()), "%A, %B %d, %Y"))
    assert len(games) == 30, f"Expected 30 games for {code}, got {len(games)}"
    legs = []
    current = base
    previous_date = None
    for game in games:
        date = dt.datetime.strptime(" ".join(game["game_date"].split()), "%A, %B %d, %Y").date()
        venue = game["venue"]
        if (previous_date and (date - previous_date).days > RETURN_GAP_DAYS
                and city(current) not in HOME_MARKET_CITIES[code]):
            legs.append(make_leg(current, base, previous_date + dt.timedelta(days=1), "Return during break"))
            current = base
        if venue != current:
            legs.append(make_leg(current, venue, date, "Game", game["game_id"]))
            current = venue
        previous_date = date
    if current != base:
        legs.append(make_leg(current, base, previous_date + dt.timedelta(days=1), "Return after season"))
    totals = {
        "km": round(sum(leg["km"] for leg in legs), 1),
        "hours": round(sum(leg["hours"] for leg in legs), 1),
        "bus_km": round(sum(leg["km"] for leg in legs if leg["mode"] == "bus"), 1),
        "air_km": round(sum(s["km"] for leg in legs for s in leg["segments"] if s["mode"] == "air"), 1),
        "airport_drive_km": round(sum(s["km"] for leg in legs for s in leg["segments"] if s["mode"] == "drive"), 1),
        "bus_legs": sum(leg["mode"] == "bus" for leg in legs),
        "air_legs": sum(leg["mode"] == "air" for leg in legs),
    }
    assert legs and legs[0]["from"] == base and legs[-1]["to"] == base
    assert abs(totals["km"] - totals["bus_km"] - totals["air_km"] - totals["airport_drive_km"]) < 0.2
    print(f"{code}: {len(legs)} legs, {totals['km']:,.0f} km", flush=True)
    return {"team": display_names[code], "games": len(games), "base": base,
            "totals": totals, "legs": legs}


teams = {code: build_team(code) for code in BASE_VENUE}
OUTPUT.write_text(json.dumps({
    "season": "2025–26 regular season", "bus_limit_miles": 400,
    "return_gap_days": RETURN_GAP_DAYS, "teams": teams,
}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print(f"Saved {OUTPUT}")

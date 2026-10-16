"""Shared helpers for birthplace-to-home-venue PWHL distance estimates."""

import json
import math
from collections import Counter, defaultdict


def home_venue_points(teams, games, venues):
    """Infer each team-season's home point from its most-used completed home venue."""
    venue_points = {
        row["venue"]: (float(row["Latitude"]), float(row["Longitude"]))
        for row in venues if row.get("Latitude") and row.get("Longitude")
    }
    name_to_code = {
        (str(row.get("season_id", "")), row.get("team_name", "")): row.get("team_code", "")
        for row in teams
    }
    counts = defaultdict(Counter)
    for game in games:
        if str(game.get("is_final", "")).upper() != "TRUE":
            continue
        sid = str(game.get("season_id", ""))
        code = name_to_code.get((sid, game.get("home_team", "")))
        venue = game.get("venue", "")
        if code and venue in venue_points:
            counts[(sid, code)][venue] += 1
    result = {}
    for key, venue_counts in counts.items():
        venue = venue_counts.most_common(1)[0][0]
        result[key] = {"venue": venue, "point": venue_points[venue]}
    return result


def birthplace_points(data_dir):
    path = data_dir / "json" / "pwhl_birthplace_coordinates.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        place: (float(coords["lat"]), float(coords["lon"]))
        for place, coords in payload.get("locations", {}).items()
    }


def great_circle_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))


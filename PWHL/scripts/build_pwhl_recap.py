"""Build game-day snapshots for the PWHL regular-season recap.

Usage: python PWHL/scripts/build_pwhl_recap.py
All numbers come from the local HockeyTech extracts. Map routes are schematic
venue-to-venue assumptions, not observed team travel.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEASONS = {"1": "2024", "5": "2024–25", "8": "2025–26"}
PLAYOFF_SPOTS = 4
BUS_LIMIT_KM = 400 * 1.609344


def rows(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def game_date(value):
    # strptime accepts the extra space used by the feed before one-digit days.
    return datetime.strptime(value, "%A, %B %d, %Y").date().isoformat()


def great_circle(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [*a, *b])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))


def indicative_hours(a, b):
    """One consistent, deliberately simple bus/air proxy for all seasons."""
    direct = great_circle(a, b)
    road_proxy = direct * 1.25
    return road_proxy / 80 if road_proxy <= BUS_LIMIT_KM else direct / 800 + 3


def main():
    games_by_season = json.loads((DATA / "json/pwhl_games.json").read_text(encoding="utf-8"))
    logs = rows("pwhl_player_game_logs.csv")
    names = {r["player_id"]: r["player_name"] for r in rows("pwhl_players_info.csv")}
    venues = {}
    for row in rows("pwhl_venues.csv"):
        if row.get("Latitude") and row.get("Longitude"):
            venues[row["venue"]] = [float(row["Longitude"]), float(row["Latitude"])]

    result = {"seasons": {}}
    for sid, label in SEASONS.items():
        games = sorted(games_by_season[sid], key=lambda g: (game_date(g["date"]), number(g["game_id"])))
        game_ids = {g["game_id"] for g in games}
        teams = sorted({g["home_code"] for g in games} | {g["away_code"] for g in games})
        scheduled_games = Counter(code for g in games for code in (g["home_code"], g["away_code"]))
        official = {r["team_code"]: r for r in rows("pwhl_standings.csv") if r["season_id"] == sid}
        home_venues = defaultdict(Counter)
        for game in games:
            if not game["takeover"]:
                home_venues[game["home_code"]][game["venue"]] += 1
        bases = {code: counts.most_common(1)[0][0] for code, counts in home_venues.items()}
        for code in teams:
            if code not in bases:
                raise ValueError(f"No home rink for {sid} {code}")

        def coords(venue):
            if venue in venues:
                return venues[venue]
            name = venue.split(" | ")[0]
            if name in venues:
                return venues[name]
            raise ValueError(f"No coordinates for {venue}")

        players_by_game = defaultdict(list)
        pim_by_game = defaultdict(int)
        goalie_seconds_by_game = defaultdict(list)
        seen = set()
        for row in logs:
            if row["season_id"] != sid or row["game_id"] not in game_ids:
                continue
            pim_by_game[row["game_id"]] += number(row["penalty_minutes"])
            if row["goalie"] == "1":
                goalie_seconds_by_game[row["game_id"]].append(number(row["seconds_played"]))
                continue
            key = row["game_id"], row["player_id"]
            if key in seen:
                raise ValueError(f"Duplicate skater game log: {sid} {key}")
            seen.add(key)
            team = row["home_team_code"] if row["home"] == "1" else row["visiting_team_code"]
            players_by_game[row["game_id"]].append({
                "id": row["player_id"], "name": names.get(row["player_id"], row["player_id"]),
                "team": team, "goals": number(row["goals"]), "points": number(row["points"]),
            })

        by_day = defaultdict(list)
        for game in games:
            by_day[game_date(game["date"])].append(game)
        totals = {code: {"p": 0, "gf": 0, "ga": 0, "gp": 0, "rw": 0, "w": 0} for code in teams}
        skaters = {}
        previous = {code: (bases[code], None) for code in teams}
        running = {"travel_hours": 0.0, "clock_minutes": 0.0, "goals": 0, "pim": 0, "extra_games": 0}
        days = []
        for date in sorted(by_day):
            day_games, routes = [], []
            for game in by_day[date]:
                home, away = game["home_code"], game["away_code"]
                hs, vs = game["home_score"], game["away_score"]
                venue = game["venue"]
                for code in (home, away):
                    prior_venue, prior_date = previous[code]
                    # Same four-day return-home assumption as the travel page.
                    if prior_date and (datetime.fromisoformat(date) - datetime.fromisoformat(prior_date)).days > 4:
                        if coords(prior_venue) != coords(bases[code]):
                            running["travel_hours"] += indicative_hours(coords(prior_venue), coords(bases[code]))
                        prior_venue = bases[code]
                    if coords(prior_venue) != coords(venue):
                        running["travel_hours"] += indicative_hours(coords(prior_venue), coords(venue))
                        routes.append({"team": code, "from": coords(prior_venue), "to": coords(venue),
                                       "from_name": prior_venue.split(" | ")[0], "to_name": venue.split(" | ")[0]})
                    previous[code] = (venue, date)

                win = home if hs > vs else away
                lose = away if win == home else home
                totals[home]["gf"] += hs
                totals[home]["ga"] += vs
                totals[away]["gf"] += vs
                totals[away]["ga"] += hs
                for code in (home, away):
                    totals[code]["gp"] += 1
                if game["ot"]:
                    totals[win]["p"] += 2
                    totals[lose]["p"] += 1
                else:
                    totals[win]["p"] += 3
                    totals[win]["rw"] += 1
                totals[win]["w"] += 1
                day_games.append({"home": home, "away": away, "hs": hs, "as": vs, "ot": game["ot"],
                                  "venue": coords(venue)})
                running["goals"] += hs + vs
                running["pim"] += pim_by_game[game["game_id"]]
                running["extra_games"] += bool(game["ot"])
                clock_seconds = 3600
                if game["ot"]:
                    clock_seconds = min(3900, max([3600, *goalie_seconds_by_game[game["game_id"]]]))
                running["clock_minutes"] += clock_seconds / 60
                for log in players_by_game[game["game_id"]]:
                    entry = skaters.setdefault(log["id"], {"id": log["id"], "name": log["name"],
                                                            "team": log["team"], "points": 0, "goals": 0})
                    entry["points"] += log["points"]
                    entry["goals"] += log["goals"]
                    entry["team"] = log["team"]

            standing = sorted(({"team": code, **values, "gd": values["gf"] - values["ga"]}
                               for code, values in totals.items()),
                              key=lambda r: (-r["p"], -r["rw"], -r["w"], r["team"]))
            # A points tie is shown as a tie. The daily feed lacks historical
            # official tie-break snapshots, so row order within a tie is display only.
            for index, row in enumerate(standing):
                row["rank"] = 1 + sum(other["p"] > row["p"] for other in standing)
                max_points = row["p"] + 3 * (scheduled_games[row["team"]] - row["gp"])
                could_catch = sum(other["team"] != row["team"] and
                                  other["p"] + 3 * (scheduled_games[other["team"]] - other["gp"]) >= row["p"]
                                  for other in standing)
                safely_ahead = sum(other["team"] != row["team"] and other["p"] > max_points
                                   for other in standing)
                row["status"] = ("in" if could_catch < PLAYOFF_SPOTS else
                                 "out" if safely_ahead >= PLAYOFF_SPOTS else "")
                if all(item["gp"] == scheduled_games[item["team"]] for item in standing):
                    row["status"] = "in" if number(official[row["team"]]["rank"]) <= PLAYOFF_SPOTS else "out"
            leaders = sorted(skaters.values(), key=lambda r: (-r["points"], -r["goals"], r["name"]))[:5]
            days.append({"date": date, "games": day_games, "routes": routes,
                         "standings": standing, "leaders": [dict(p) for p in leaders],
                         "counters": {key: round(value, 2) for key, value in running.items()}})

        # Guard against silently shipping a partial historical season.
        for code, row in totals.items():
            source = official[code]
            expected = (number(source["points"]), number(source["goals_for"]), number(source["goals_against"]))
            actual = row["p"], row["gf"], row["ga"]
            if actual != expected:
                raise ValueError(f"{label} {code}: reconstructed {actual}, official {expected}")
        result["seasons"][sid] = {
            "label": label, "teams": teams, "bases": {code: coords(venue) for code, venue in bases.items()},
            "days": days,
        }
        print(f"{label}: {len(games)} games, {len(days)} game dates, {len(teams)} teams")

    output = DATA / "json/pwhl_season_recap.json"
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

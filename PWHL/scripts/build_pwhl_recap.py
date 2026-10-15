"""Build game-day snapshots for the PWHL season replay.

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
PLAYOFF_SEASONS = {"1": "3", "5": "6", "8": "9"}
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
    shutout_keys = {(r["game_id"], r["player_id"]) for r in logs if r.get("shutout") == "1"}
    names = {r["player_id"]: r["player_name"] for r in rows("pwhl_players_info.csv")}
    player_info = {r["player_id"]: r for r in rows("pwhl_players_info.csv")}
    pbp_by_game = defaultdict(list)
    for event in rows("pwhl_pbp.csv"):
        pbp_by_game[event["game_id"]].append(event)
    playoff_bracket = rows("pwhl_playoff_bracket.csv")
    team_rows = rows("pwhl_teams.csv")
    suspension_dates = defaultdict(list)
    for transaction in rows("pwhl_transactions.csv"):
        description = " ".join((transaction.get("title", ""), transaction.get("detail", ""))).casefold()
        if "suspend" in description:
            suspension_dates[(transaction.get("season_id", ""), transaction.get("transaction_date", ""))].append(
                transaction.get("player_name") or names.get(transaction.get("player_id", ""), "Player"))
    birth_rosters = {(r["season_id"], r["player_id"]): r
                     for r in rows("pwhl_team_rosters.csv") if r["season_id"] in SEASONS}
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
        goalies_by_game = defaultdict(list)
        pim_by_game = defaultdict(int)
        goalie_seconds_by_game = defaultdict(list)
        seen = set()
        player_ids = set()
        for row in logs:
            if row["season_id"] != sid or row["game_id"] not in game_ids:
                continue
            player_ids.add(row["player_id"])
            pim_by_game[row["game_id"]] += number(row["penalty_minutes"])
            if row["goalie"] == "1":
                goalie_seconds_by_game[row["game_id"]].append(number(row["seconds_played"]))
                key = row["game_id"], row["player_id"]
                if key in seen:
                    raise ValueError(f"Duplicate goalie game log: {sid} {key}")
                seen.add(key)
                team = row["home_team_code"] if row["home"] == "1" else row["visiting_team_code"]
                goalies_by_game[row["game_id"]].append({
                    "id": row["player_id"], "name": names.get(row["player_id"], row["player_id"]),
                    "team": team, "wins": number(row["win"]),
                    "saves": number(row["saves"]), "shots": number(row["shots_against"]),
                    "seconds": number(row["seconds_played"]),
                })
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
        goalie_totals = {}
        seen_birth_players = set()
        previous = {code: (bases[code], None) for code in teams}
        running = {"travel_hours": 0.0, "clock_minutes": 0.0, "goals": 0,
                   "pim": 0, "extra_games": 0, "attendance": 0, "attendance_games": 0}
        days = []
        for date in sorted(by_day):
            day_games, routes = [], []
            birth_debuts = []
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
                events = []
                for player in players_by_game[game["game_id"]]:
                    if player["goals"] >= 3:
                        events.append({"type": "hat-trick", "player": player["name"], "team": player["team"]})
                for goalie in goalies_by_game[game["game_id"]]:
                    if (game["game_id"], goalie["id"]) in shutout_keys:
                        events.append({"type": "shutout", "player": goalie["name"], "team": goalie["team"]})
                for event in pbp_by_game[game["game_id"]]:
                    if event.get("event") == "penalty" and event.get("event_type") == "Game Misconduct":
                        player = " ".join(filter(None, (event.get("player_name_first"), event.get("player_name_last"))))
                        events.append({"type": "game-misconduct", "player": player or "Player", "team": ""})
                day_games.append({"id": game["game_id"], "home": home, "away": away, "hs": hs, "as": vs,
                                  "ot": game["ot"], "venue": coords(venue), "events": events})
                running["goals"] += hs + vs
                running["pim"] += pim_by_game[game["game_id"]]
                running["extra_games"] += bool(game["ot"])
                if game.get("attendance") is not None:
                    running["attendance"] += number(game["attendance"])
                    running["attendance_games"] += 1
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
                for log in goalies_by_game[game["game_id"]]:
                    entry = goalie_totals.setdefault(log["id"], {
                        "id": log["id"], "name": log["name"], "team": log["team"],
                        "wins": 0, "saves": 0, "shots": 0, "seconds": 0,
                    })
                    for key in ("wins", "saves", "shots", "seconds"):
                        entry[key] += log[key]
                    entry["team"] = log["team"]

                for log in [*players_by_game[game["game_id"]], *goalies_by_game[game["game_id"]]]:
                    player_id = log["id"]
                    if player_id in seen_birth_players:
                        continue
                    seen_birth_players.add(player_id)
                    birth = birth_rosters.get((sid, player_id), {})
                    country = birth.get("birthcntry") or "Unknown"
                    region = birth.get("birthprov") if country in ("Canada", "United States") else None
                    birth_debuts.append({"country": country, "region": region,
                                         "place": player_info.get(player_id, {}).get("birthplace", "") or "Unknown"})

            for player in suspension_dates.get((sid, date), []):
                if day_games:
                    day_games[0]["events"].append({"type": "suspension", "player": player, "team": ""})

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
            goalie_leaders = sorted(goalie_totals.values(),
                                    key=lambda r: (-r["wins"], -r["seconds"], r["name"]))[:3]
            days.append({"date": date, "games": day_games, "routes": routes,
                         "birth_debuts": birth_debuts,
                         "standings": standing, "leaders": [dict(p) for p in leaders],
                          "goalies": [{"id": g["id"], "name": g["name"], "team": g["team"],
                                       "wins": g["wins"],
                                       "save_pct": round(g["saves"] / g["shots"], 3) if g["shots"] else None}
                                      for g in goalie_leaders],
                         "counters": {key: round(value, 2) for key, value in running.items()}})

        # Guard against silently shipping a partial historical season.
        if seen_birth_players != player_ids:
            raise ValueError(f"{label}: player debut count does not match game logs")
        for code, row in totals.items():
            source = official[code]
            expected = (number(source["points"]), number(source["goals_for"]), number(source["goals_against"]))
            actual = row["p"], row["gf"], row["ga"]
            if actual != expected:
                raise ValueError(f"{label} {code}: reconstructed {actual}, official {expected}")
        birth_countries = Counter()
        birth_regions = Counter()
        for player_id in player_ids:
            birth = birth_rosters.get((sid, player_id), {})
            country = birth.get("birthcntry") or "Unknown"
            birth_countries[country] += 1
            if country in ("Canada", "United States") and birth.get("birthprov"):
                birth_regions[(birth["birthprov"], country)] += 1
        result["seasons"][sid] = {
            "label": label, "teams": teams, "bases": {code: coords(venue) for code, venue in bases.items()},
            "birthplaces": {
                "players": len(player_ids), "unknown": birth_countries["Unknown"],
                "places": [{"name": player_info.get(pid, {}).get("birthplace", "") or "Unknown",
                            "country": birth_rosters.get((sid, pid), {}).get("birthcntry") or "Unknown",
                            "region": birth_rosters.get((sid, pid), {}).get("birthprov") or ""}
                           for pid in sorted(player_ids)],
                "countries": [{"name": name, "count": count}
                              for name, count in sorted(birth_countries.items(), key=lambda item: (-item[1], item[0]))],
                "regions": [{"name": name, "country": country, "count": count}
                            for (name, country), count in sorted(birth_regions.items(),
                                                                 key=lambda item: (-item[1], item[0]))[:10]],
            },
            "days": days,
        }

        # Postseason games share the same animation, but do not alter regular-season points.
        psid = PLAYOFF_SEASONS[sid]
        playoff_games = sorted(games_by_season.get(psid, []),
                               key=lambda g: (game_date(g["date"]), number(g["game_id"])))
        playoff_ids = {g["game_id"] for g in playoff_games}
        playoff_logs = [r for r in logs if r["season_id"] == psid and r["game_id"] in playoff_ids]
        playoff_pim = defaultdict(int)
        playoff_goalie_seconds = defaultdict(list)
        for row in playoff_logs:
            playoff_pim[row["game_id"]] += number(row.get("penalty_minutes"))
            if row.get("goalie") == "1":
                playoff_goalie_seconds[row["game_id"]].append(number(row.get("seconds_played")))
        playoff_previous = {code: (bases[code], None) for code in teams}
        for game in games:
            date = game_date(game["date"])
            for code in (game["home_code"], game["away_code"]):
                playoff_previous[code] = (game["venue"], date)
        playoff_running = dict(days[-1]["counters"])
        postseason = defaultdict(list)
        for game in playoff_games:
            postseason[game_date(game["date"])].append(game)
        id_to_code = {r["team_id"]: r["team_code"] for r in team_rows if r["season_id"] == psid}
        bracket_rows = [r for r in playoff_bracket if r["season_id"] == psid]
        playoff_days = []
        for date in sorted(postseason):
            day_games, routes = [], []
            for game in postseason[date]:
                game_id = game["game_id"]
                game_logs = [r for r in playoff_logs if r["game_id"] == game_id]
                venue = game["venue"]
                venue_coords = coords(venue)
                for code in (game["home_code"], game["away_code"]):
                    prior_venue, prior_date = playoff_previous[code]
                    if prior_date and (datetime.fromisoformat(date) - datetime.fromisoformat(prior_date)).days > 4:
                        if coords(prior_venue) != coords(bases[code]):
                            playoff_running["travel_hours"] += indicative_hours(coords(prior_venue), coords(bases[code]))
                        prior_venue = bases[code]
                    if coords(prior_venue) != venue_coords:
                        playoff_running["travel_hours"] += indicative_hours(coords(prior_venue), venue_coords)
                        routes.append({"team": code, "from": coords(prior_venue), "to": venue_coords,
                                       "from_name": prior_venue.split(" | ")[0], "to_name": venue.split(" | ")[0]})
                    playoff_previous[code] = (venue, date)
                playoff_running["goals"] += number(game["home_score"]) + number(game["away_score"])
                playoff_running["pim"] += playoff_pim[game_id]
                playoff_running["extra_games"] += bool(game.get("ot"))
                if game.get("attendance") is not None:
                    playoff_running["attendance"] += number(game["attendance"])
                    playoff_running["attendance_games"] += 1
                clock_seconds = 3600
                if game.get("ot"):
                    clock_seconds = min(3900, max([3600, *playoff_goalie_seconds[game_id]]))
                playoff_running["clock_minutes"] += clock_seconds / 60
                events = []
                for row in game_logs:
                    if row.get("goalie") == "0" and number(row.get("goals")) >= 3:
                        player = player_info.get(row["player_id"], {})
                        events.append({"type": "hat-trick", "player": player.get("player_name", "Player"),
                                       "team": row["home_team_code"] if row["home"] == "1" else row["visiting_team_code"]})
                    if row.get("goalie") == "1" and row.get("shutout") == "1":
                        player = player_info.get(row["player_id"], {})
                        events.append({"type": "shutout", "player": player.get("player_name", "Goalie"),
                                       "team": row["home_team_code"] if row["home"] == "1" else row["visiting_team_code"]})
                for event in pbp_by_game[game_id]:
                    if event.get("event") == "penalty" and event.get("event_type") == "Game Misconduct":
                        player = " ".join(filter(None, (event.get("player_name_first"), event.get("player_name_last"))))
                        events.append({"type": "game-misconduct", "player": player or "Player", "team": ""})
                home, away = game["home_code"], game["away_code"]
                day_games.append({"id": game_id, "home": home, "away": away,
                                  "hs": game["home_score"], "as": game["away_score"], "ot": game["ot"],
                                  "venue": coords(game["venue"]), "events": events})
            for player in suspension_dates.get((psid, date), []):
                if day_games:
                    day_games[0]["events"].append({"type": "suspension", "player": player, "team": ""})
            round_num = max((number(r["round"]) for r in bracket_rows
                             if any(g["game_id"] == r["game_id"] for g in postseason[date])), default=0)
            bracket = []
            for row in bracket_rows:
                round_games = [r for r in bracket_rows if r["round"] == row["round"]
                               and r["series_letter"] == row["series_letter"]]
                # A series appears once, carrying the latest cumulative wins from the feed.
                if any(item["series"] == row["series_letter"] and item["round"] == number(row["round"]) for item in bracket):
                    continue
                played = [g for g in round_games if g["game_id"] in playoff_ids and
                          datetime.strptime(g["game_date"][:10], "%Y-%m-%d").date().isoformat() <= date]
                wins = [0, 0]
                for played_game in played:
                    home_id = played_game["home_team_id"]
                    away_id = played_game["visiting_team_id"]
                    winner_id = home_id if number(played_game["home_goals"]) > number(played_game["visiting_goals"]) else away_id
                    if winner_id == row["team1_id"]:
                        wins[0] += 1
                    elif winner_id == row["team2_id"]:
                        wins[1] += 1
                bracket.append({"round": number(row["round"]), "series": row["series_letter"],
                                "round_name": row["round_name"], "teams": [id_to_code.get(row["team1_id"], ""), id_to_code.get(row["team2_id"], "")],
                                "wins": wins})
            playoff_days.append({"date": date, "phase": "playoff", "round": round_num,
                                 "round_name": next((r["round_name"] for r in bracket_rows
                                                     if number(r["round"]) == round_num), ""),
                                 "games": day_games, "routes": routes, "bracket": bracket,
                                 "birth_debuts": [], "standings": [], "leaders": [], "goalies": [],
                                 "counters": {key: round(value, 2) for key, value in playoff_running.items()}})
        result["seasons"][sid]["playoffs"] = playoff_days
        final_series = [b for b in (playoff_days[-1]["bracket"] if playoff_days else [])
                        if b["round"] == max((x["round"] for x in (playoff_days[-1]["bracket"] if playoff_days else [])), default=0)]
        if final_series:
            final = final_series[-1]
            result["seasons"][sid]["champion"] = final["teams"][0 if final["wins"][0] > final["wins"][1] else 1]
        print(f"  playoffs: {len(playoff_games)} games, {len(playoff_days)} game dates")
        print(f"{label}: {len(games)} games, {len(days)} game dates, {len(teams)} teams")

    output = DATA / "json/pwhl_season_recap.json"
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

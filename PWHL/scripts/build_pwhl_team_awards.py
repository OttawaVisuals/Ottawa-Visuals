"""Build historical team awards from game logs, rosters, and salary data."""

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from pwhl_geography import birthplace_points, great_circle_km, home_venue_points


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "PWHL" / "data"
OUT = DATA / "json" / "pwhl_team_awards.json"


def rows(name):
    with (DATA / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def number(v):
    try:
        return float(v) if v not in (None, "", "NA") else 0.0
    except (TypeError, ValueError):
        return 0.0


def main():
    season_teams = defaultdict(dict)
    names_to_codes = defaultdict(dict)
    for t in rows("pwhl_teams.csv"):
        season_teams[t["season_id"]][t["team_id"]] = {
            "code": t["team_code"], "name": t["team_city"] or t["team_name"]}
        names_to_codes[t["season_id"]][t["team_name"]] = t["team_code"]

    home_points = home_venue_points(
        rows("pwhl_teams.csv"), rows("pwhl_game_summaries.csv"), rows("PWHL_Venues.csv"))
    birthplace_coords = birthplace_points(DATA)
    player_info = {r["player_id"]: r for r in rows("pwhl_players_info.csv")}
    roster_people = defaultdict(dict)
    for r in rows("pwhl_team_rosters.csv"):
        sid = r.get("season_id", "")
        team = season_teams[sid].get(r.get("team_id", ""))
        pid = r.get("player_id", "")
        if team and pid:
            info = player_info.get(pid, {})
            nationality = info.get("nationality", "")
            if nationality in ("", "NA"):
                nationality = r.get("birthcntry", "")
            roster_people[(sid, team["code"])][pid] = {
                "nationality": (nationality or "").strip(),
                "birthplace": info.get("birthplace", ""),
            }

    by_season_team = defaultdict(lambda: defaultdict(lambda: {
        "points_by_player": defaultdict(float), "pim": 0.0, "games": 0}))
    for game in rows("pwhl_game_summaries.csv"):
        if str(game.get("is_final", "")).upper() != "TRUE":
            continue
        sid = game.get("season_id", "")
        for side in ("home_team", "visitor_team"):
            code = names_to_codes[sid].get(game.get(side, ""))
            if code:
                by_season_team[sid][code]["games"] += 1

    seen = set()
    for r in rows("pwhl_player_game_logs.csv"):
        sid, gid, pid = r.get("season_id", ""), r.get("game_id", ""), r.get("player_id", "")
        identity = (sid, gid, pid)
        if not all(identity) or identity in seen:
            continue
        seen.add(identity)
        team = season_teams[sid].get(r.get("player_team", ""))
        if not team:
            continue
        agg = by_season_team[sid][team["code"]]
        if r.get("goalie") == "1":
            agg["pim"] += number(r.get("pim"))
        else:
            agg["pim"] += number(r.get("penalty_minutes"))
            agg["points_by_player"][pid] += number(r.get("goals")) + number(r.get("assists"))

    salaries = defaultdict(lambda: defaultdict(list))
    for r in rows("pwhl_salaries_2025_26.csv"):
        salaries[r["season_id"]][r["team_code"]].append(number(r["salary"]))

    roster_counts = defaultdict(lambda: defaultdict(set))
    for r in rows("pwhl_team_rosters.csv"):
        sid = r.get("season_id", "")
        team = season_teams[sid].get(r.get("team_id", ""))
        if team and r.get("player_id"):
            roster_counts[sid][team["code"]].add(r["player_id"])

    result = {}
    for sid, teams in by_season_team.items():
        result[sid] = []
        for code, agg in teams.items():
            points = sorted(agg["points_by_player"].values(), reverse=True)
            total_points = sum(points)
            entry = {
                "code": code,
                "name": next((x["name"] for x in season_teams[sid].values() if x["code"] == code), code),
                "games": agg["games"],
                "pim": round(agg["pim"], 2),
                "pim_per_game": agg["pim"] / agg["games"] if agg["games"] else 0,
                "scorers": sum(p > 0 for p in points),
                "points": total_points,
                "top3_points_share": sum(points[:3]) / total_points if total_points else 0,
                "salary_count": 0,
                "roster_count": len(roster_counts[sid].get(code, set())),
                "salary_cv": None,
                "top3_salary_share": None,
            }
            roster = roster_people.get((sid, code), {})
            known_nationalities = {
                p["nationality"] for p in roster.values()
                if p["nationality"] and p["nationality"].upper() not in {"NA", "N/A", "UNKNOWN"}
            }
            home = home_points.get((sid, code))
            distances = [
                great_circle_km(birthplace_coords[p["birthplace"]], home["point"])
                for p in roster.values()
                if home and p["birthplace"] in birthplace_coords
            ]
            entry.update({
                "nationality_count": len(known_nationalities),
                "nationality_player_count": sum(
                    bool(p["nationality"])
                    and p["nationality"].upper() not in {"NA", "N/A", "UNKNOWN"}
                    for p in roster.values()
                ),
                "home_distance_median_km": round(statistics.median(distances)) if distances else None,
                "home_distance_player_count": len(distances),
            })
            vals = salaries[sid].get(code, [])
            if vals:
                mean = sum(vals) / len(vals)
                sd = math.sqrt(sum((x - mean) ** 2 for x in vals) / len(vals))
                entry.update({
                    "salary_count": len(vals),
                    "salary_coverage": len(vals) / len(roster_counts[sid].get(code, set())) if roster_counts[sid].get(code) else None,
                    "salary_cv": sd / mean if mean else 0,
                    "top3_salary_share": sum(sorted(vals, reverse=True)[:3]) / sum(vals),
                })
            result[sid].append(entry)
        result[sid].sort(key=lambda x: x["code"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"by_season": result}, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote team awards for {len(result)} seasons to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""Build league-wide historical totals used by the PWHL home page."""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "PWHL" / "data"
OUT = DATA / "json" / "pwhl_overview.json"


def read_csv(name):
    with (DATA / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def number(value):
    try:
        return int(float(value)) if value not in (None, "", "NA") else 0
    except (TypeError, ValueError):
        return 0


def main():
    games = [g for g in read_csv("pwhl_game_summaries.csv")
             if str(g.get("is_final", "")).upper() == "TRUE"]
    game_ids = {g.get("game_id") for g in games}
    seen = set()
    players = set()
    season_names = {r["season_id"]: r["season_name"] for r in read_csv("pwhl_seasons.csv")}
    totals = {
        "games": len(games),
        "attendance": sum(number(g.get("attendance")) for g in games),
        "shots_on_goal": 0,
        "player_seconds": 0,
        "players": 0,
        "pim": 0,
        "hat_tricks": 0,
        "shutouts": 0,
        "shg": 0,
        "empty_net_goals": 0,
    }
    by_season = {}
    for g in games:
        sid = g.get("season_id", "")
        if sid not in by_season:
            by_season[sid] = {
                "season": season_names.get(sid, f"Season {sid}"), "games": 0,
                "goals": 0, "attendance": 0, "teams": set(), "shots_on_goal": 0,
                "player_seconds": 0, "players": set(), "pim": 0,
                "hat_tricks": 0, "shutouts": 0, "shg": 0,
                "empty_net_goals": 0,
            }
        s = by_season[sid]
        s["games"] += 1
        s["goals"] += number(g.get("home_score")) + number(g.get("visitor_score"))
        s["attendance"] += number(g.get("attendance"))
        for field in ("home_team", "visitor_team"):
            if g.get(field):
                s["teams"].add(g[field])

    for row in read_csv("pwhl_player_game_logs.csv"):
        pid, gid = row.get("player_id"), row.get("game_id")
        if not pid or not gid or gid not in game_ids or (gid, pid) in seen:
            continue
        seen.add((gid, pid))
        players.add(pid)
        sid = row.get("season_id", "")
        s = by_season.get(sid)
        if not s:
            continue
        s["players"].add(pid)
        goalie = row.get("goalie") == "1"
        seconds = number(row.get("seconds_played") if goalie else row.get("ice_time_seconds"))
        pim = number(row.get("pim") if goalie else row.get("penalty_minutes"))
        s["player_seconds"] += seconds
        s["pim"] += pim
        totals["player_seconds"] += seconds
        totals["pim"] += pim
        if goalie:
            shutout = row.get("shutout") == "1"
            totals["shutouts"] += shutout
            s["shutouts"] += shutout
        else:
            shots = number(row.get("shots"))
            goals = number(row.get("goals"))
            shg = number(row.get("short_handed_goals"))
            en = number(row.get("empty_net_goals"))
            totals["shots_on_goal"] += shots
            totals["hat_tricks"] += goals >= 3
            totals["shg"] += shg
            totals["empty_net_goals"] += en
            s["shots_on_goal"] += shots
            s["hat_tricks"] += goals >= 3
            s["shg"] += shg
            s["empty_net_goals"] += en

    totals["players"] = len(players)
    for s in by_season.values():
        s["teams"] = len(s["teams"])
        s["players"] = len(s["players"])
        s["player_seconds"] = round(s["player_seconds"])
        s["pim"] = round(s["pim"], 2)
    by_season = dict(sorted(by_season.items(), key=lambda item: int(item[0])))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"league_totals": totals, "by_season": by_season}, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({totals['games']} completed games)")


if __name__ == "__main__":
    main()

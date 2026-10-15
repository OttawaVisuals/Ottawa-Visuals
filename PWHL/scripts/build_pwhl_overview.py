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

    for row in read_csv("pwhl_player_game_logs.csv"):
        pid, gid = row.get("player_id"), row.get("game_id")
        if not pid or not gid or gid not in game_ids or (gid, pid) in seen:
            continue
        seen.add((gid, pid))
        players.add(pid)
        goalie = row.get("goalie") == "1"
        totals["player_seconds"] += number(
            row.get("seconds_played") if goalie else row.get("ice_time_seconds"))
        totals["pim"] += number(row.get("pim") if goalie else row.get("penalty_minutes"))
        if goalie:
            totals["shutouts"] += row.get("shutout") == "1"
        else:
            totals["shots_on_goal"] += number(row.get("shots"))
            totals["hat_tricks"] += number(row.get("goals")) >= 3
            totals["shg"] += number(row.get("short_handed_goals"))
            totals["empty_net_goals"] += number(row.get("empty_net_goals"))

    totals["players"] = len(players)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"league_totals": totals}, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({totals['games']} completed games)")


if __name__ == "__main__":
    main()

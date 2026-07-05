"""
Pre-aggregates PWHL/data/*.csv into small JSON files the dashboard
(pwhl.html) fetches at runtime -- same pattern as Weather/ottawa_weather_fetch*.py
feeding weather.html. Run this after daily_update.R refreshes the raw CSVs.

Usage: python PWHL/scripts/build_dashboard_json.py
(run from the repo root; paths below are relative to it)
"""

import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

DATA_DIR = os.path.join("PWHL", "data")
OUT_DIR = os.path.join(DATA_DIR, "json")


def read_csv(name, required=True):
    path = os.path.join(DATA_DIR, name)
    # pwhl_pbp.csv is cached between CI runs rather than committed, so it can be
    # absent on a cache miss. Only the shot map depends on it -- let the rest of
    # the dashboard JSON still build instead of crashing the whole job.
    if not required and not os.path.exists(path):
        print(f"  note: {path} not found, skipping (shot map will be empty)")
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_num(x, cast=float):
    if x is None or x == "" or x == "NA":
        return None
    try:
        return cast(x)
    except (ValueError, TypeError):
        return None


def write_json(name, obj):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
    size_kb = os.path.getsize(path) / 1024
    print(f"  wrote {path} ({size_kb:.1f} KB)")


def main():
    teams = read_csv("pwhl_teams.csv")
    team_logos = read_csv("pwhl_team_logos.csv")
    game_summaries = read_csv("pwhl_game_summaries.csv")
    season_ids_rows = read_csv("pwhl_season_game_ids.csv")
    standings = read_csv("pwhl_standings.csv")
    season_stats = read_csv("pwhl_player_season_stats.csv")
    pbp = read_csv("pwhl_pbp.csv", required=False)
    bracket = read_csv("pwhl_playoff_bracket.csv")
    transactions = read_csv("pwhl_transactions.csv")

    # Logo lookup: prefer the most recent season's logo per team_id.
    logo_by_team = {}
    for r in team_logos:
        logo_by_team[r["team_id"]] = r["team_logo"]

    # ---- Season list & "current" season detection -----------------
    # A season is "current" if it has any final game; the current playoff
    # season is the most recent one with real bracket rows.
    final_games_by_season = defaultdict(list)
    for g in game_summaries:
        if str(g.get("is_final")).upper() == "TRUE":
            final_games_by_season[g["season_id"]].append(g)

    season_names = {}
    for r in season_stats:
        season_names.setdefault(r["season_id"], r.get("season_name", r["season_id"]))
    # Some seasons (e.g. preseason) never show up in season_stats; fall back
    # to the season_id itself so nothing is unlabeled.
    all_season_ids = sorted(
        {g["season_id"] for g in game_summaries if g.get("season_id")},
        key=lambda s: int(s),
    )
    for sid in all_season_ids:
        season_names.setdefault(sid, f"Season {sid}")

    # "Current season" for standings/leaders should be the regular season,
    # not playoffs -- a bare "most recent season with final games" pick
    # would land on playoffs once they start, since they're numbered later.
    regular_named_ids = sorted(
        (sid for sid in all_season_ids if "Regular" in season_names.get(sid, "") and final_games_by_season.get(sid)),
        key=lambda s: int(s),
    )
    current_season_id = regular_named_ids[-1] if regular_named_ids else (all_season_ids[-1] if all_season_ids else None)

    playoff_season_ids = sorted({r["season_id"] for r in bracket}, key=lambda s: int(s))
    current_playoff_season_id = playoff_season_ids[-1] if playoff_season_ids else None

    # ---- Teams per season ------------------------------------------
    teams_by_season = defaultdict(list)
    for r in teams:
        teams_by_season[r["season_id"]].append({
            "team_id": r["team_id"],
            "name": r["team_name"],
            "city": r["team_city"],
            "code": r["team_code"],
            "logo": logo_by_team.get(r["team_id"], r.get("team_logo", "")),
        })

    write_json("pwhl_meta.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seasons": [{"season_id": sid, "name": season_names[sid]} for sid in all_season_ids],
        "current_season_id": current_season_id,
        "current_playoff_season_id": current_playoff_season_id,
        "teams_by_season": teams_by_season,
    })

    # ---- Standings ---------------------------------------------------
    standings_by_season = defaultdict(list)
    for r in standings:
        standings_by_season[r["season_id"]].append({
            "team_id": r.get("team_id"),
            "name": r.get("name"),
            "code": r.get("team_code"),
            "logo": logo_by_team.get(r.get("team_id"), ""),
            "rank": to_num(r.get("rank"), int),
            "gp": to_num(r.get("games_played.x"), int),
            "w": to_num(r.get("regulation_wins"), int),
            "l": to_num(r.get("losses"), int),
            "otw": to_num(r.get("ot_wins"), int),
            "otl": to_num(r.get("ot_losses"), int),
            "sow": to_num(r.get("shootout_wins"), int),
            "sol": to_num(r.get("shootout_losses"), int),
            "pts": to_num(r.get("points"), int),
            "gf": to_num(r.get("goals_for"), int),
            "ga": to_num(r.get("goals_against"), int),
            "pp_pct": r.get("power_play_pct"),
            "pk_pct": r.get("penalty_kill_pct"),
        })
    for sid in standings_by_season:
        standings_by_season[sid].sort(key=lambda t: (t["rank"] is None, t["rank"]))
    write_json("pwhl_standings.json", standings_by_season)

    # ---- Player leaders (regular-season, per season) -----------------
    def leader_row(r):
        return {
            "player_id": r["player_id"],
            "name": None,  # filled in below from players_info
            "team_code": r.get("team_code"),
            "gp": to_num(r.get("games_played"), int),
            "goals": to_num(r.get("goals"), int),
            "assists": to_num(r.get("assists"), int),
            "points": to_num(r.get("points"), int),
            "shots": to_num(r.get("shots"), int),
            "hits": to_num(r.get("hits"), int),
            "pim": to_num(r.get("penalty_minutes"), int),
            "ppg": to_num(r.get("power_play_goals"), int),
            "ppa": to_num(r.get("power_play_assists"), int),
            "faceoff_pct": to_num(r.get("faceoff_pct")),
            "points_per_game": to_num(r.get("points_per_game")),
        }

    players_info = {p["player_id"]: p for p in read_csv("pwhl_players_info.csv")}

    def player_display_name(pid):
        p = players_info.get(pid)
        if not p:
            return f"Player {pid}"
        name = (p.get("first_name", "") + " " + p.get("last_name", "")).strip()
        return name or f"Player {pid}"

    leaders_by_season = {}
    for sid in all_season_ids:
        rows = [
            leader_row(r) for r in season_stats
            if r["season_id"] == sid and r.get("stat_type") in ("regular", None)
            and to_num(r.get("games_played"), int)
        ]
        for r in rows:
            r["name"] = player_display_name(r["player_id"])
        leaders_by_season[sid] = {
            "points": sorted(rows, key=lambda r: (-(r["points"] or 0), -(r["goals"] or 0)))[:15],
            "goals": sorted(rows, key=lambda r: -(r["goals"] or 0))[:15],
            "assists": sorted(rows, key=lambda r: -(r["assists"] or 0))[:15],
            "shots": sorted(rows, key=lambda r: -(r["shots"] or 0))[:15],
            "hits": sorted(rows, key=lambda r: -(r["hits"] or 0))[:15],
            "faceoff_pct": sorted(
                [r for r in rows if (r["gp"] or 0) >= 5 and r["faceoff_pct"] is not None],
                key=lambda r: -(r["faceoff_pct"] or 0),
            )[:15],
        }
    write_json("pwhl_leaders.json", leaders_by_season)

    # ---- Games (schedule/results + attendance) ------------------------
    games_by_season = defaultdict(list)
    for g in game_summaries:
        if str(g.get("is_final")).upper() != "TRUE":
            continue
        games_by_season[g["season_id"]].append({
            "game_id": g["game_id"],
            "date": g.get("game_date"),
            "home": g.get("home_team"),
            "away": g.get("visitor_team"),
            "home_score": to_num(g.get("home_score"), int),
            "away_score": to_num(g.get("visitor_score"), int),
            "attendance": to_num(g.get("attendance"), int),
            "venue": g.get("venue"),
        })
    for sid in games_by_season:
        games_by_season[sid].sort(key=lambda g: g["game_id"])
    write_json("pwhl_games.json", games_by_season)

    # ---- Play-by-play derived: shot map, event mix, goals by period ---
    # Bin shot coordinates into a coarse grid so the dashboard ships a
    # small aggregate instead of 19k raw shot rows.
    GRID_X, GRID_Y = 40, 18  # ~5ft cells over a 200x85ft-ish coordinate space
    shot_bins = defaultdict(lambda: {"shots": 0, "goals": 0})
    event_counts = defaultdict(int)
    goals_by_period = defaultdict(int)
    shots_by_period = defaultdict(int)

    for e in pbp:
        ev = e.get("event")
        if ev:
            event_counts[ev] += 1
        period = e.get("period_of_game")
        if ev in ("shot", "goal"):
            if period:
                shots_by_period[period] += 1
            if str(e.get("goal")).upper() == "TRUE":
                goals_by_period[period] += 1
            x = to_num(e.get("x_coord"))
            y = to_num(e.get("y_coord"))
            if x is not None and y is not None and -100 <= x <= 100 and -45 <= y <= 45:
                bx = min(GRID_X - 1, max(0, int((x + 100) / 200 * GRID_X)))
                by = min(GRID_Y - 1, max(0, int((y + 45) / 90 * GRID_Y)))
                cell = shot_bins[(bx, by)]
                cell["shots"] += 1
                if str(e.get("goal")).upper() == "TRUE":
                    cell["goals"] += 1

    shot_map = {
        "grid_x": GRID_X, "grid_y": GRID_Y,
        "cells": [
            {"bx": bx, "by": by, "shots": v["shots"], "goals": v["goals"]}
            for (bx, by), v in shot_bins.items()
        ],
    }
    write_json("pwhl_shot_map.json", shot_map)
    write_json("pwhl_events.json", {
        "event_counts": dict(event_counts),
        "goals_by_period": dict(goals_by_period),
        "shots_by_period": dict(shots_by_period),
    })

    # ---- Playoff bracket ------------------------------------------------
    bracket_by_season = defaultdict(list)
    for r in bracket:
        bracket_by_season[r["season_id"]].append(r)
    write_json("pwhl_bracket.json", bracket_by_season)

    # ---- Transactions -----------------------------------------------
    txn_by_type = defaultdict(int)
    txn_by_month = defaultdict(int)
    for t in transactions:
        ttype = t.get("detail") or t.get("ttype_text") or "Other"
        txn_by_type[ttype] += 1
        d = t.get("transaction_date", "")
        month = d[:7] if len(d) >= 7 else "unknown"
        txn_by_month[month] += 1
    write_json("pwhl_transactions.json", {
        "by_type": dict(sorted(txn_by_type.items(), key=lambda kv: -kv[1])),
        "by_month": dict(sorted(txn_by_month.items())),
        "recent": sorted(transactions, key=lambda t: t.get("transaction_date", ""), reverse=True)[:20],
    })

    print(f"\nCurrent season: {current_season_id} ({season_names.get(current_season_id)})")
    print(f"Current playoff season: {current_playoff_season_id}")
    print("Done.")


if __name__ == "__main__":
    main()

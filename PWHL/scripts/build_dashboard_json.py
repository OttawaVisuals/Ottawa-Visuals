"""
Pre-aggregates PWHL/data/*.csv into small JSON files the dashboard
(pwhl.html) fetches at runtime -- same pattern as Weather/ottawa_weather_fetch*.py
feeding weather.html. Run this after daily_update.R refreshes the raw CSVs.

Usage: python PWHL/scripts/build_dashboard_json.py
(run from the repo root; paths below are relative to it)
"""

import csv
import glob
import json
import os
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone

DATA_DIR = os.path.join("PWHL", "data")
OUT_DIR = os.path.join(DATA_DIR, "json")
PLAYERS_DIR = os.path.join(OUT_DIR, "players")

# Cities that count as a team's own market. A home game anywhere else (Detroit,
# Denver, Halifax ...) is a Takeover Tour / neutral-site game. Big-arena games
# inside the market (Bell Centre, Scotiabank Arena, Canadian Tire Centre) stay
# "home market". Keyed by team code; MON is the 2024 preseason's code for MTL.
HOME_MARKETS = {
    "BOS": {"boston", "lowell"},
    "MIN": {"st. paul", "minneapolis"},
    "MTL": {"montreal", "laval"}, "MON": {"montreal", "laval"},
    "NY": {"new york", "newark", "elmont", "bridgeport"},
    "OTT": {"ottawa"},
    "TOR": {"toronto"},
    "SEA": {"seattle"},
    "VAN": {"vancouver"},
    "DET": {"detroit"},
    "HAM": {"hamilton"},
    "VEG": {"las vegas", "paradise"}, "VGS": {"las vegas", "paradise"},
    "SJ": {"san jose"},
}


def fold(s):
    """Lower-case, accent-free key so 'Bell Centre | Montréal' matches 'montreal'."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


def venue_parts(venue):
    """'TD Place | Ottawa' -> ('td place', 'ottawa'); city is '' when absent."""
    name, _, city = (venue or "").partition("|")
    return fold(name), fold(city)


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
    game_logs = read_csv("pwhl_player_game_logs.csv")
    venues = read_csv("PWHL_Venues.csv")

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
    # Game summaries name teams ("Ottawa Charge"), not codes; the bracket and
    # game logs use ids. The page colours everything by code.
    code_by_name = {(r["season_id"], r["team_name"]): r["team_code"] for r in teams}
    code_by_id = {r["team_id"]: r["team_code"] for r in teams}  # later seasons win

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
        # Each season id holds one kind of stat line (regular, playoff or
        # exhibition), so take them all; skip the career "Total" rows.
        rows = [
            leader_row(r) for r in season_stats
            if r["season_id"] == sid and r.get("season_name") != "Total"
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

    # ---- Awards: full skater table per season ---------------------------
    # The dashboard's "Superlatives" section derives ~15 tongue-in-cheek
    # awards from these rows, and can re-rank any of them per 60 minutes of
    # ice time, so ship the raw per-player line rather than pre-picking
    # winners -- it's only a few hundred rows per season.
    positions = {pid: (p.get("position") or "") for pid, p in players_info.items()}
    # Fair-play award: share of a skater's games with no penalty at all, which
    # needs the per-game log (season totals can't tell 4 PIM in one game from
    # 2 PIM in two).
    logged_games = defaultdict(int)
    clean_games = defaultdict(int)
    for r in game_logs:
        if r.get("goalie") == "1":
            continue
        key = (r["season_id"], r["player_id"])
        logged_games[key] += 1
        if not (to_num(r.get("penalty_minutes"), int) or 0):
            clean_games[key] += 1
    awards_by_season = {}
    for sid in all_season_ids:
        # Each season id carries only one kind of stat line; preseason is filed
        # under "exhibition" rather than a name matching its season label.
        name = season_names.get(sid, "")
        stat_type = "playoff" if "Playoff" in name else "exhibition" if "Preseason" in name else "regular"
        # The feed carries one row per player *per team*, so a mid-season trade
        # splits a player across two rows that must be summed. It also emits the
        # occasional exact-duplicate line (same totals, blank/NA team code), so
        # dedupe on the stat line itself before summing or the traded-player fix
        # would double-count them.
        by_player = defaultdict(list)
        for r in season_stats:
            if r["season_id"] != sid or r.get("stat_type") != stat_type:
                continue
            # Career "Total" rows carry an arbitrary season_id; summing them in
            # would inflate players as if they'd been traded.
            if r.get("season_name") == "Total":
                continue
            if not to_num(r.get("games_played"), int) or not to_num(r.get("ice_time"), int):
                continue
            by_player[r["player_id"]].append(r)

        rows = []
        for pid, prows in by_player.items():
            seen, parts = set(), []
            for r in prows:
                sig = (r.get("games_played"), r.get("ice_time"), r.get("points"),
                       r.get("penalty_minutes"), r.get("shots"))
                if sig in seen:
                    continue
                seen.add(sig)
                parts.append(r)

            def total(field):
                return sum(to_num(p.get(field), int) or 0 for p in parts)

            gp, toi = total("games_played"), total("ice_time")
            # Team shown is whichever jersey they logged the most ice time in.
            best = max(parts, key=lambda p: to_num(p.get("ice_time"), int) or 0)
            team_code = best.get("team_code")
            if not team_code or team_code == "NA":
                team_code = next(
                    (p.get("team_code") for p in parts
                     if p.get("team_code") and p.get("team_code") != "NA"),
                    (players_info.get(pid) or {}).get("most_recent_team_code", ""),
                )
            rows.append({
                "player_id": pid,
                "name": player_display_name(pid),
                "team_code": team_code,
                "traded": len(parts) > 1,
                "pos": positions.get(pid, ""),
                "gp": gp,
                "toi": toi,
                "goals": total("goals"),
                "assists": total("assists"),
                "points": total("points"),
                "pim": total("penalty_minutes"),
                "plus_minus": total("plus_minus"),
                "shots": total("shots"),
                "hits": total("hits"),
                "blocks": total("shots_blocked_by_player"),
                "fo_wins": total("faceoff_wins"),
                "fo_attempts": total("faceoff_attempts"),
                "gwg": total("game_winning_goals"),
                "first_goals": total("first_goals"),
                "unassisted_goals": total("unassisted_goals"),
                "ppg": total("power_play_goals"),
                "shg": total("short_handed_goals"),
                "log_gp": logged_games.get((sid, pid), 0),
                "clean_gp": clean_games.get((sid, pid), 0),
            })
        rows.sort(key=lambda r: -r["toi"])
        if rows:
            awards_by_season[sid] = rows
    write_json("pwhl_awards.json", awards_by_season)

    # ---- Games (schedule/results + attendance) ------------------------
    # Capacity by arena name (the venue sheet sometimes omits the "| City"
    # part, e.g. "Xcel Energy Center", so match on the name alone).
    capacity_by_venue = {}
    for v in venues:
        cap = to_num((v.get("Capacity") or "").replace(",", ""), int)
        if cap:
            capacity_by_venue[venue_parts(v.get("venue"))[0]] = cap
    missing_caps = set()

    games_by_season = defaultdict(list)
    for g in game_summaries:
        if str(g.get("is_final")).upper() != "TRUE":
            continue
        sid = g["season_id"]
        home_code = code_by_name.get((sid, g.get("home_team")), "")
        vname, vcity = venue_parts(g.get("venue"))
        capacity = capacity_by_venue.get(vname)
        if not capacity and vname not in ("", "na", "tbd"):
            missing_caps.add(g.get("venue"))
        games_by_season[sid].append({
            "game_id": g["game_id"],
            "date": g.get("game_date"),
            "home": g.get("home_team"),
            "away": g.get("visitor_team"),
            "home_code": home_code,
            "away_code": code_by_name.get((sid, g.get("visitor_team")), ""),
            "home_score": to_num(g.get("home_score"), int),
            "away_score": to_num(g.get("visitor_score"), int),
            "attendance": to_num(g.get("attendance"), int),
            "venue": g.get("venue"),
            "capacity": capacity,
            # No city (e.g. the 2024 preseason's Utica showcase) = neutral site.
            "takeover": vcity not in HOME_MARKETS.get(home_code, set()),
        })
    if missing_caps:
        print("  note: no capacity in PWHL_Venues.csv for: " + "; ".join(sorted(missing_caps)))
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

    # ---- Player pages ------------------------------------------------
    write_player_pages(players_info, season_stats, game_logs, pbp, game_summaries,
                       season_names, code_by_id)

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


def write_player_pages(players_info, season_stats, game_logs, pbp, game_summaries,
                       season_names, code_by_id):
    """One small JSON per player for player.html?id=... (bio, season lines,
    game log, shot locations) plus pwhl_players_index.json for the search box."""
    season_of_game = {g["game_id"]: g["season_id"] for g in game_summaries}
    n = lambda r, f: to_num(r.get(f), int) or 0

    # Season lines: one per season x team. Skip the career "Total" rows and the
    # feed's exact-duplicate lines (same stats, NA team code).
    lines = defaultdict(list)
    seen = set()
    for r in season_stats:
        if r.get("season_name") == "Total" or not to_num(r.get("games_played"), int):
            continue
        sig = (r["player_id"], r["season_id"], r.get("stat_type"), r.get("games_played"),
               r.get("points"), r.get("ice_time"), r.get("shots_against"))
        if sig in seen:
            continue
        seen.add(sig)
        line = {
            "season_id": r["season_id"],
            "season": season_names.get(r["season_id"], r.get("season_name")),
            "team": r.get("team_code") if r.get("team_code") not in (None, "", "NA") else "",
            "gp": n(r, "games_played"),
        }
        if to_num(r.get("shots_against"), int) is not None:
            sa, ga = n(r, "shots_against"), n(r, "goals_against")
            line.update(g=True, w=n(r, "wins"), l=n(r, "losses"), otl=n(r, "ot_losses"),
                        sa=sa, ga=ga, toi=n(r, "seconds_played"),
                        svpct=round(1 - ga / sa, 4) if sa else None,
                        gaa=to_num(r.get("goals_against_average")))
        else:
            line.update(goals=n(r, "goals"), assists=n(r, "assists"), points=n(r, "points"),
                        pm=n(r, "plus_minus"), pim=n(r, "penalty_minutes"),
                        ppg=n(r, "power_play_goals"), shg=n(r, "short_handed_goals"),
                        gwg=n(r, "game_winning_goals"), shots=n(r, "shots"), hits=n(r, "hits"),
                        blocks=n(r, "shots_blocked_by_player"), fow=n(r, "faceoff_wins"),
                        foa=n(r, "faceoff_attempts"), toi=n(r, "ice_time"))
        lines[r["player_id"]].append(line)

    games = defaultdict(list)
    is_goalie = set()
    for r in game_logs:
        home = r.get("home") == "1"
        g = {"s": r["season_id"], "gid": r["game_id"], "d": r.get("date_played"),
             "opp": r.get("visiting_team_code") if home else r.get("home_team_code"),
             "team": code_by_id.get(r.get("player_team"), ""), "h": 1 if home else 0}
        if r.get("goalie") == "1":
            is_goalie.add(r["player_id"])
            g.update(sa=n(r, "shots_against"), sv=n(r, "saves"), ga=n(r, "goals_against"),
                     toi=n(r, "seconds_played"),
                     dec="W" if r.get("win") == "1" else "OTL" if r.get("ot_loss") == "1"
                     else "L" if r.get("loss") == "1" else "")
        else:
            g.update(g=n(r, "goals"), a=n(r, "assists"), p=n(r, "points"), sog=n(r, "shots"),
                     pm=n(r, "plus_minus"), pim=n(r, "penalty_minutes"), hits=n(r, "hits"),
                     blk=n(r, "shots_blocked_by_player"), toi=n(r, "ice_time_seconds"))
        games[r["player_id"]].append(g)

    # Shots on goal, flipped so every shot attacks the right-hand net. The feed
    # doesn't say which end a team attacked; teams switch ends each period, so
    # use the sign of the median x of that team's shots in that period (the
    # same inference build_models.py uses for xG).
    by_game = defaultdict(list)
    for r in pbp:
        if r.get("event") == "shot":
            by_game[r["game_id"]].append(r)
    shots_for, shots_against = defaultdict(list), defaultdict(list)
    for gid, evs in by_game.items():
        xs = defaultdict(list)
        for r in evs:
            x = to_num(r.get("x_coord"))
            if x is not None:
                xs[(r.get("period_of_game"), r.get("team_id"))].append(x)
        direction = {}
        for key, vals in xs.items():
            vals.sort()
            med = vals[len(vals) // 2]
            if med:
                direction[key] = 1 if med > 0 else -1
        sid = season_of_game.get(gid)
        for r in evs:
            d = direction.get((r.get("period_of_game"), r.get("team_id")))
            x, y = to_num(r.get("x_coord")), to_num(r.get("y_coord"))
            if d is None or x is None or y is None or sid is None:
                continue
            shot = [sid, round(x * d, 1), round(y * d, 1), 1 if r.get("goal") == "TRUE" else 0]
            if r.get("player_id") not in (None, "", "NA"):
                shots_for[r["player_id"]].append(shot)
            if r.get("goalie_id") not in (None, "", "NA"):
                shots_against[r["goalie_id"]].append(shot)

    os.makedirs(PLAYERS_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(PLAYERS_DIR, "*.json")):
        os.remove(old)
    index = []
    for pid in sorted(set(lines) | set(games), key=int):
        info = players_info.get(pid, {})
        clean = lambda f: info.get(f) if info.get(f) not in (None, "", "NA") else None
        goalie = pid in is_goalie or clean("position") == "G"
        name = (f'{info.get("first_name", "")} {info.get("last_name", "")}').strip() or f"Player {pid}"
        pos = "G" if goalie else (clean("position") or "")
        team = clean("most_recent_team_code") or ""
        obj = {
            "player_id": pid, "name": name, "pos": pos, "team": team,
            "team_name": clean("most_recent_team"), "number": clean("jersey_number"),
            "shoots": clean("catches") if goalie else clean("shoots"),
            "height": clean("height"), "dob": clean("date_of_birth"),
            "hometown": clean("hometown") or clean("birthplace"),
            "nationality": clean("nationality"), "image": clean("primary_image"),
            "seasons": sorted(lines.get(pid, []), key=lambda l: int(l["season_id"])),
            "games": sorted(games.get(pid, []), key=lambda g: (g["d"] or "", int(g["gid"]))),
            # [season_id, x, y, goal]; for goalies these are shots faced.
            "shots": (shots_against if goalie else shots_for).get(pid, []),
        }
        with open(os.path.join(PLAYERS_DIR, f"{pid}.json"), "w", encoding="utf-8") as f:
            json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
        index.append({"id": pid, "name": name, "pos": pos, "team": team})
    print(f"  wrote {len(index)} player files to {PLAYERS_DIR}")
    write_json("pwhl_players_index.json", sorted(index, key=lambda p: p["name"]))


if __name__ == "__main__":
    main()

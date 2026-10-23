"""Shared counting rules for league totals, club splits, and shot events."""

from collections import defaultdict, deque


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


SKATER_FIELDS = {
    "gp": "games_played", "toi": "ice_time", "goals": "goals",
    "assists": "assists", "points": "points", "pim": "penalty_minutes",
    "plus_minus": "plus_minus", "shots": "shots", "hits": "hits",
    "blocks": "shots_blocked_by_player", "fo_wins": "faceoff_wins",
    "fo_attempts": "faceoff_attempts", "ppg": "power_play_goals",
    "ppa": "power_play_assists", "shg": "short_handed_goals",
    "gwg": "game_winning_goals", "first_goals": "first_goals",
    "unassisted_goals": "unassisted_goals", "en_goals": "empty_net_goals",
}
GOALIE_FIELDS = {
    "gp": "games_played", "toi": "seconds_played", "w": "wins",
    "l": "losses", "otl": "ot_losses", "sol": "shootout_losses",
    "sa": "shots_against", "ga": "goals_against", "so": "shutouts",
}
STAT_FIELDS = sorted(set(SKATER_FIELDS.values()) | set(GOALIE_FIELDS.values()))


def is_goalie(row):
    return row.get("shots_against") not in (None, "", "NA")


def deduplicate_season_stats(rows):
    """Drop career totals and duplicate aliases, preserving distinct club splits.

    A blank-team copy can repeat a named club's stats. Two named clubs with
    identical stats are still two genuine stints, not duplicates.
    """
    rows = [r for r in rows if r.get("season_name") != "Total"
            and number(r.get("games_played")) > 0]

    def signature(r):
        return (r["season_id"], r["player_id"], r.get("stat_type"),
                is_goalie(r), tuple(number(r.get(k)) for k in STAT_FIELDS))

    def club(r):
        return r.get("team_code") if r.get("team_code") not in (None, "", "NA") else ""

    named = {signature(r) for r in rows if club(r)}
    seen, result = set(), []
    for row in rows:
        sig, code = signature(row), club(row)
        if not code and sig in named:
            continue
        key = (sig, code)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def skater_totals(parts):
    result = {key: int(sum(number(p.get(field)) for p in parts))
              for key, field in SKATER_FIELDS.items()}
    result["faceoff_pct"] = (100 * result["fo_wins"] / result["fo_attempts"]
                            if result["fo_attempts"] else None)
    return result


def player_name(pid, profiles):
    profile = profiles.get(pid, {})
    return " ".join(filter(None, (profile.get("first_name"), profile.get("last_name")))) or f"Player {pid}"


def build_leaders(rows, profiles):
    groups = defaultdict(list)
    for row in rows:
        if not is_goalie(row):
            groups[(row["season_id"], row["player_id"])].append(row)
    seasons = defaultdict(list)
    for (sid, pid), parts in groups.items():
        best = max(parts, key=lambda r: number(r.get("ice_time")))
        codes = sorted({r["team_code"] for r in parts if r.get("team_code") not in (None, "", "NA")})
        seasons[sid].append({**skater_totals(parts), "player_id": pid,
                             "name": player_name(pid, profiles),
                             "team_code": best.get("team_code"), "team_codes": codes})
    result = {}
    for sid, players in seasons.items():
        result[sid] = {}
        for stat in ("points", "goals", "assists", "shots", "hits", "faceoff_pct"):
            eligible = [p for p in players if stat != "faceoff_pct"
                        or (p["gp"] >= 5 and p[stat] is not None)]
            result[sid][stat] = sorted(eligible, key=lambda p:
                (-p[stat], -p["goals"] if stat == "points" else 0, p["name"]))[:15]
    return result


def build_team_players(rows, profiles):
    groups = defaultdict(list)
    for row in rows:
        code = row.get("team_code")
        if code not in (None, "", "NA"):
            groups[(row["season_id"], code, row["player_id"], is_goalie(row))].append(row)
    result = defaultdict(lambda: {"skaters": [], "goalies": []})
    for (sid, code, pid, goalie), parts in groups.items():
        stats = ({key: int(sum(number(p.get(field)) for p in parts))
                  for key, field in GOALIE_FIELDS.items()} if goalie else skater_totals(parts))
        result[sid]["goalies" if goalie else "skaters"].append({
            **stats, "player_id": pid, "name": player_name(pid, profiles),
            "team_code": code, "pos": profiles.get(pid, {}).get("position", ""),
        })
    return dict(result)


def unique_shots(pbp):
    """One on-goal attempt per shot/goal pair; retain unpaired goal events.

    Pair one-to-one so separate shots by the same player in the same second
    survive. Coordinates from a matching goal fill a shot's missing position.
    """
    def key(row):
        return tuple(row.get(k) for k in ("game_id", "period_of_game", "time_of_period", "player_id"))

    shots = [dict(r) for r in pbp if r.get("event") == "shot"]
    available = defaultdict(deque)
    # If two attempts share a clock/scorer key, match an already-scoring shot
    # first rather than accidentally turning the saved attempt into a goal.
    for i, row in sorted(enumerate(shots), key=lambda pair: str(pair[1].get("goal")).upper() != "TRUE"):
        available[key(row)].append(i)
    for goal in pbp:
        if goal.get("event") != "goal":
            continue
        matches = available[key(goal)]
        if matches:
            row = shots[matches.popleft()]
            row["goal"] = "TRUE"
            for field in ("x_coord", "y_coord"):
                if row.get(field) in (None, "", "NA"):
                    row[field] = goal.get(field)
        else:
            shots.append({**goal, "event": "shot", "goal": "TRUE"})
    return shots

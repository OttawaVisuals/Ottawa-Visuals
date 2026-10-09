"""
Team Elo ratings, game win probabilities and playoff odds for the PWHL
dashboard. Stdlib only, like the other build scripts.

Reads data/pwhl_season_game_ids.csv (schedule + results, with team ids),
data/pwhl_seasons.csv and data/pwhl_teams.csv; writes data/json/pwhl_elo.json.

  python PWHL/scripts/build_elo.py

Method (538-style):
- Every regular-season and playoff game updates both teams' ratings;
  preseason games are ignored.
- P(home win) = 1 / (1 + 10^(-(home - away + HFA) / 400)). Every PWHL game
  has a winner (OT, then shootout), so there's no draw term.
- Between seasons ratings regress part of the way back to 1500; expansion
  teams enter below average.
- K, home-ice, regression, expansion offset and the margin-of-victory
  switch are picked by grid search on pre-game log loss over past seasons.
- Playoff odds: the rest of the regular season is simulated N_SIMS times
  (ratings update inside each simulation so streaks carry), then the
  playoff bracket for that season's format.
"""

import csv
import itertools
import json
import math
import os
import random
from collections import defaultdict
from datetime import datetime, timezone

DATA_DIR = os.path.join("PWHL", "data")
OUT_DIR = os.path.join(DATA_DIR, "json")

N_SIMS = 10000
BASE = 1500.0

# Playoff formats by league year, keyed by team_id (codes drift: Las Vegas
# is VEG in the 2026-27 preseason feed but VGS in the regular season).
# Source: PWHL 2026-27 schedule announcement, 2026-10-02.
FORMATS = {
    "2026-27": {
        "conferences": {
            "East": ["1", "11", "3", "4", "5", "6"],   # BOS HAM MTL NY OTT TOR
            "West": ["10", "12", "2", "13", "8", "9"],  # DET LV MIN SJ SEA VAN
        },
        "per_conference": 4,
        "rounds": [3, 5, 5],   # best-of: first round, conference final, final
    },
}

GRID = {
    "k": [4, 6, 8, 10, 12, 15, 20, 30],
    "hfa": [0, 25, 50, 75],
    "regress": [0.25, 0.5, 0.75],
    "expansion": [0, -50, -100, -150, -200],
    "mov": [False, True],
}
# The log-loss surface is nearly flat (a few hundred games to tune on), so
# the single best cell is mostly noise. Among settings within this much of
# the best, prefer the most responsive (highest K), then the mildest
# expansion penalty -- four new teams in 2026-27 have no history at all.
TUNE_TOLERANCE = 0.001


def read_csv(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def win_prob(diff):
    return 1 / (1 + 10 ** (-diff / 400))


def season_kind(row):
    if row.get("playoff") == "1":
        return "playoff"
    if row.get("career") == "0":
        return "preseason"
    return "regular"


def league_year(name):
    return name.split(" ")[0]


class Elo:
    def __init__(self, p):
        self.p = p
        self.r = {}
        self.seen_regular = set()

    def new_season(self, team_ids):
        inaugural = not self.r
        for t in list(self.r):
            self.r[t] = BASE + (1 - self.p["regress"]) * (self.r[t] - BASE)
        for t in team_ids:
            if t not in self.r:
                # Inaugural teams start at par; later arrivals are expansion.
                self.r[t] = BASE + (0.0 if inaugural else self.p["expansion"])

    def prob(self, home, away, hfa=True):
        return win_prob(self.r[home] - self.r[away] + (self.p["hfa"] if hfa else 0))

    def update(self, home, away, hs, as_, decided_late, hfa=True):
        p = self.prob(home, away, hfa)
        home_won = hs > as_
        mult = 1.0
        if self.p["mov"]:
            margin = 1 if decided_late else abs(hs - as_)
            diff = (self.r[home] - self.r[away] + (self.p["hfa"] if hfa else 0)) * (1 if home_won else -1)
            mult = math.log(margin + 1) * 2.2 / (diff * 0.001 + 2.2)
        delta = self.p["k"] * mult * ((1 if home_won else 0) - p)
        self.r[home] += delta
        self.r[away] -= delta
        return p


def load():
    seasons = {r["season_id"]: r for r in read_csv("pwhl_seasons.csv")}
    games = []
    for r in read_csv("pwhl_season_game_ids.csv"):
        s = seasons.get(r["season_id"])
        if not s or season_kind(s) == "preseason":
            continue
        games.append({
            "season_id": r["season_id"], "game_id": r["game_id"], "date": r["date_played"],
            "home": r.get("home_team_id"), "away": r.get("visiting_team_id"),
            "hs": int(r["home_score"]) if r.get("home_score", "").isdigit() else None,
            "as": int(r["visiting_score"]) if r.get("visiting_score", "").isdigit() else None,
            "final": r["is_final"] == "TRUE",
            "late": "OT" in r.get("game_status", "") or "SO" in r.get("game_status", ""),
            "kind": season_kind(s),
        })
    games.sort(key=lambda g: (g["date"], int(g["game_id"])))
    return seasons, games


def run_history(games, params, record=None):
    """Replay every final game in order. Returns (elo, [(game, p_home)])."""
    elo = Elo(params)
    preds = []
    current_regular = None
    teams_by_season = defaultdict(set)
    for g in games:
        teams_by_season[g["season_id"]].update([g["home"], g["away"]])
    for g in games:
        if not g["final"]:
            continue
        if g["kind"] == "regular" and g["season_id"] != current_regular:
            current_regular = g["season_id"]
            elo.new_season(teams_by_season[g["season_id"]])
        for t in (g["home"], g["away"]):
            elo.r.setdefault(t, BASE + (params["expansion"] if elo.r else 0.0))
        p = elo.update(g["home"], g["away"], g["hs"], g["as"], g["late"])
        preds.append((g, p))
        if record is not None:
            record(g, elo)
    return elo, preds


def log_loss(pairs):
    return -sum(math.log(p if y else 1 - p) for p, y in pairs) / len(pairs)


def tune(games, eval_seasons):
    results = []
    keys = list(GRID)
    for combo in itertools.product(*(GRID[k] for k in keys)):
        params = dict(zip(keys, combo))
        _, preds = run_history(games, params)
        pairs = [(p, g["hs"] > g["as"]) for g, p in preds if g["season_id"] in eval_seasons]
        if pairs:
            results.append((log_loss(pairs), params))
    best_ll = min(ll for ll, _ in results)
    near = [(ll, p) for ll, p in results if ll <= best_ll + TUNE_TOLERANCE]
    near.sort(key=lambda x: (-x[1]["k"], -x[1]["expansion"], x[0]))
    return near[0][0], near[0][1], best_ll


def scorecard(pairs, base_rate):
    if not pairs:
        return None
    correct = sum((p > 0.5) == y for p, y in pairs)
    return {
        "games": len(pairs),
        "accuracy": round(correct / len(pairs), 3),
        "log_loss": round(log_loss(pairs), 4),
        "baseline_log_loss": round(log_loss([(base_rate, y) for _, y in pairs]), 4),
        "brier": round(sum((p - y) ** 2 for p, y in pairs) / len(pairs), 4),
    }


def play_series(rng, a, b, best_of, ratings):
    need = best_of // 2 + 1
    wa = wb = 0
    p = win_prob(ratings[a] - ratings[b])
    while wa < need and wb < need:
        if rng.random() < p:
            wa += 1
        else:
            wb += 1
    return a if wa == need else b


def simulate(target_games, start_ratings, params, fmt, ot_rate, seed=11):
    rng = random.Random(seed)
    teams = sorted({g["home"] for g in target_games} | {g["away"] for g in target_games})
    base_pts = defaultdict(int)
    base_rw = defaultdict(int)
    remaining = []
    for g in target_games:
        if g["final"]:
            home_won = g["hs"] > g["as"]
            w, l = (g["home"], g["away"]) if home_won else (g["away"], g["home"])
            base_pts[w] += 2 if g["late"] else 3
            base_pts[l] += 1 if g["late"] else 0
            if not g["late"]:
                base_rw[w] += 1
        else:
            remaining.append(g)

    conf_of = {}
    if fmt:
        for conf, ids in fmt["conferences"].items():
            for t in ids:
                conf_of[t] = conf

    tally = {t: defaultdict(float) for t in teams}
    for _ in range(N_SIMS):
        r = dict(start_ratings)
        pts = dict(base_pts)
        rw = dict(base_rw)
        for g in remaining:
            h, a = g["home"], g["away"]
            p = win_prob(r[h] - r[a] + params["hfa"])
            home_won = rng.random() < p
            late = rng.random() < ot_rate
            w, l = (h, a) if home_won else (a, h)
            pts[w] = pts.get(w, 0) + (2 if late else 3)
            pts[l] = pts.get(l, 0) + (1 if late else 0)
            if not late:
                rw[w] = rw.get(w, 0) + 1
            delta = params["k"] * ((1 if home_won else 0) - p)
            r[h] += delta
            r[a] -= delta

        # Points, then regulation wins, then a coin flip.
        order = sorted(teams, key=lambda t: (-pts.get(t, 0), -rw.get(t, 0), rng.random()))
        for rank, t in enumerate(order, 1):
            tally[t]["pts"] += pts.get(t, 0)
            tally[t]["rank"] += rank

        if not fmt:
            continue
        finalists = []
        for conf in fmt["conferences"]:
            seeds = [t for t in order if conf_of.get(t) == conf][:fmt["per_conference"]]
            for i, t in enumerate(seeds):
                tally[t]["playoffs"] += 1
                if i == 0:
                    tally[t]["top_seed"] += 1
            # The top seed picks whichever of 3rd/4th looks weaker by rating.
            s1, s2, s3, s4 = seeds
            pick, other = (s3, s4) if r[s3] <= r[s4] else (s4, s3)
            w1 = play_series(rng, s1, pick, fmt["rounds"][0], r)
            w2 = play_series(rng, s2, other, fmt["rounds"][0], r)
            for t in (w1, w2):
                tally[t]["conf_final"] += 1
            champ = play_series(rng, w1, w2, fmt["rounds"][1], r)
            tally[champ]["final"] += 1
            finalists.append(champ)
        cup = play_series(rng, finalists[0], finalists[1], fmt["rounds"][2], r)
        tally[cup]["cup"] += 1

    return {t: {k: v / N_SIMS for k, v in d.items()} for t, d in tally.items()}


def main():
    seasons, games = load()
    teams_rows = read_csv("pwhl_teams.csv")
    team_info = {}
    for r in teams_rows:  # later seasons overwrite earlier names/logos
        team_info[r["team_id"]] = {"code": r["team_code"], "name": r["team_name"], "logo": r["team_logo"]}

    # Target = the latest regular season with a published schedule.
    regular_ids = sorted({g["season_id"] for g in games if g["kind"] == "regular"}, key=int)
    target = regular_ids[-1]
    target_name = seasons[target]["season_name"]
    target_games = [g for g in games if g["season_id"] == target]
    fmt = FORMATS.get(league_year(target_name))
    print(f"Target season {target} ({target_name}): {sum(g['final'] for g in target_games)}"
          f"/{len(target_games)} games final, format {'known' if fmt else 'unknown'}")

    # Tune on every completed season after the inaugural one (which only
    # warms ratings up), and never on the target season itself.
    past_ids = sorted({g["season_id"] for g in games if g["final"]}, key=int)
    eval_seasons = set(past_ids[2:]) - {target}
    ll, params, best_ll = tune(games, eval_seasons)
    print(f"  tuned on seasons {sorted(eval_seasons, key=int)}: log loss {ll:.4f} "
          f"(best cell {best_ll:.4f}) with {params}")

    final_games = [g for g in games if g["final"]]
    home_rate = sum(g["hs"] > g["as"] for g in final_games) / len(final_games)
    ot_rate = (sum(g["late"] for g in final_games if g["kind"] == "regular")
               / max(1, sum(1 for g in final_games if g["kind"] == "regular")))

    # Replay with the chosen settings, keeping a rating history.
    history = defaultdict(list)
    keep_from = str(int(target) - 3)  # last full season + playoffs + target

    def record(g, elo):
        if int(g["season_id"]) >= int(keep_from):
            for t in (g["home"], g["away"]):
                history[t].append([g["date"], round(elo.r[t], 1)])

    elo, preds = run_history(games, params, record)
    past_pairs = [(p, g["hs"] > g["as"]) for g, p in preds if g["season_id"] in eval_seasons]
    current_pairs = [(p, g["hs"] > g["as"]) for g, p in preds if g["season_id"] == target]

    # If the target season hasn't started, apply the off-season regression
    # and add expansion teams now so the preview ratings are the opening ones.
    started = any(g["final"] for g in target_games)
    target_teams = sorted({g["home"] for g in target_games} | {g["away"] for g in target_games}, key=int)
    if not started:
        elo.new_season(target_teams)
        season_start = min(g["date"] for g in target_games)
        for t in target_teams:
            history[t].append([season_start, round(elo.r[t], 1)])

    proj = simulate(target_games, elo.r, params, fmt, ot_rate)

    conf_of = {t: c for c, ids in (fmt or {}).get("conferences", {}).items() for t in ids}
    table = []
    for t in target_teams:
        info = team_info.get(t, {"code": t, "name": t, "logo": ""})
        row = {"team_id": t, "code": info["code"], "name": info["name"], "logo": info["logo"],
               "conference": conf_of.get(t), "elo": round(elo.r[t], 1)}
        row.update({k: round(v, 4 if k not in ("pts", "rank") else 1) for k, v in proj[t].items()})
        table.append(row)
    table.sort(key=lambda r: -r["elo"])

    upcoming = []
    for g in target_games:
        if g["final"]:
            continue
        p = elo.prob(g["home"], g["away"])
        upcoming.append({"game_id": g["game_id"], "date": g["date"],
                         "home": team_info.get(g["home"], {}).get("code", g["home"]),
                         "away": team_info.get(g["away"], {}).get("code", g["away"]),
                         "home_id": g["home"], "away_id": g["away"], "p_home": round(p, 3)})
        if len(upcoming) >= 20:
            break

    recent = []
    for g, p in preds:
        if g["season_id"] == target:
            recent.append({"date": g["date"], "home": team_info.get(g["home"], {}).get("code"),
                           "away": team_info.get(g["away"], {}).get("code"),
                           "p_home": round(p, 3), "home_score": g["hs"], "away_score": g["as"],
                           "late": g["late"]})

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season_id": target, "season_name": target_name, "started": started,
        "params": params, "home_win_rate": round(home_rate, 3), "ot_rate": round(ot_rate, 3),
        "n_sims": N_SIMS,
        "format": fmt,
        "teams": table,
        "upcoming": upcoming,
        "recent": recent[-20:][::-1],
        "history": {team_info.get(t, {}).get("code", t): pts for t, pts in history.items() if t in target_teams},
        "scorecard": {
            "backtest": scorecard(past_pairs, home_rate),
            "backtest_seasons": [seasons[s]["season_name"] for s in sorted(eval_seasons, key=int)],
            "this_season": scorecard(current_pairs, home_rate),
        },
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "pwhl_elo.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print(f"  wrote {path} ({os.path.getsize(path) / 1024:.1f} KB)")
    print(f"  backtest: {out['scorecard']['backtest']}")


if __name__ == "__main__":
    main()

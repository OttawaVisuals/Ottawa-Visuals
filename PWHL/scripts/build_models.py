"""
Expected goals (xG), goalie GSAx and player impact ratings for the PWHL
dashboard, built from the play-by-play CSV. Stdlib only, like
build_dashboard_json.py, so the Action needs no pip install.

Writes:
  data/json/pwhl_xg.json       model card, team/goalie/skater xG, danger map
  data/json/pwhl_ratings.json  per-season skater impact ratings (in goals)

Run after build_dashboard_json.py (it reads that script's meta/awards JSON):
  python PWHL/scripts/build_models.py

Coordinates: x_coord/y_coord are feet from centre ice on a 200x85 rink and
are consistent across seasons (x_coord_right / x_coord_fixed are not -- the
fastRhockey version that produced them changed mid-history). Attack direction
isn't recorded, so it's inferred per game/period/team from where that team's
shots cluster.
"""

import csv
import json
import math
import os
import random
from collections import defaultdict

DATA_DIR = os.path.join("PWHL", "data")
OUT_DIR = os.path.join(DATA_DIR, "json")

NET_X = 89.0          # goal line, feet from centre
BLUE_X = 25.0         # blue line, feet from centre
REBOUND_SECS = 3
RUSH_SECS = 4
SHOT_TYPES = ["Snap", "Backhand", "Slap", "Tip", "Default"]  # baseline: Wrist

# Rating constants. These are assumptions, not fitted values -- they're
# shown on the page so readers can judge them.
FINISH_SHRINK_SHOTS = 300   # finishing = (G - xG) * shots / (shots + this)
A1_WEIGHT, A2_WEIGHT = 0.5, 0.25
FACEOFF_GOALS_PER_WIN = 0.01
RAPM_LAMBDA_HOURS = 6.0     # ridge penalty, in hours of 5v5 ice time
MIN_ONICE_COVERAGE = 0.8    # share of shots with on-ice lists to run RAPM


# ------------------------------------------------------------------ io

def read_csv(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(name):
    with open(os.path.join(OUT_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def write_json(name, obj):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
    print(f"  wrote {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def num(x):
    if x in (None, "", "NA"):
        return None
    try:
        return float(x)
    except ValueError:
        return None


def ids(s):
    if s in (None, "", "NA"):
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


# ------------------------------------------------------- linear algebra

def solve_spd(a, b):
    """Solve a·x = b for symmetric positive-definite a (Cholesky)."""
    n = len(a)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        Li = L[i]
        for j in range(i + 1):
            Lj = L[j]
            s = a[i][j] - sum(Li[k] * Lj[k] for k in range(j))
            if i == j:
                Li[i] = math.sqrt(max(s, 1e-12))
            else:
                Li[j] = s / Lj[j]
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


def fit_logistic(X, y, l2=1.0, iters=25):
    """Newton/IRLS logistic regression. X rows include a leading 1."""
    p = len(X[0])
    beta = [0.0] * p
    for _ in range(iters):
        H = [[0.0] * p for _ in range(p)]
        g = [0.0] * p
        for xi, yi in zip(X, y):
            z = sum(b * v for b, v in zip(beta, xi))
            mu = 1 / (1 + math.exp(-max(-30, min(30, z))))
            w = mu * (1 - mu)
            r = yi - mu
            for j in range(p):
                if xi[j] == 0:
                    continue
                g[j] += r * xi[j]
                wxj = w * xi[j]
                Hj = H[j]
                for k in range(j + 1):
                    Hj[k] += wxj * xi[k]
        for j in range(p):
            for k in range(j):
                H[k][j] = H[j][k]
            if j > 0:
                H[j][j] += l2
                g[j] -= l2 * beta[j]
        step = solve_spd(H, g)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-6:
            break
    return beta


def predict(beta, x):
    z = sum(b * v for b, v in zip(beta, x))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def auc(scores, labels):
    pairs = sorted(zip(scores, labels))
    pos = sum(labels)
    neg = len(labels) - pos
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2
        rank_sum += avg_rank * sum(l for _, l in pairs[i:j])
        i = j
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def log_loss(ps, ys):
    eps = 1e-12
    return -sum(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps))
                for p, y in zip(ps, ys)) / len(ys)


# ------------------------------------------------------- game parsing

class Penalty:
    __slots__ = ("team", "start", "end", "minor")

    def __init__(self, team, start, length_secs, minor):
        self.team, self.start, self.end, self.minor = team, start, start + length_secs, minor


def parse_games(pbp, season_of, season_kind):
    """Group events by game, infer attack direction and strength, and
    return a flat list of shot dicts (on-goal shots only) plus per-game
    event lists for the on-ice/RAPM pass."""
    by_game = defaultdict(list)
    for i, r in enumerate(pbp):
        t = num(r.get("sec_from_start"))
        if t is None:
            continue
        by_game[r["game_id"]].append((t, i, r))

    # Empty-net / strength flags live on the separate `goal` event row;
    # index them so the matching on-goal `shot` row can pick them up.
    goal_flags = {}
    for r in pbp:
        if r["event"] == "goal":
            goal_flags[(r["game_id"], r.get("sec_from_start"), r.get("player_id"))] = r

    shots, games = [], {}
    for gid, evs in by_game.items():
        evs.sort(key=lambda e: (e[0], e[1]))
        sid = season_of.get(gid)
        if sid is None:
            continue
        first = evs[0][2]
        home, away = first.get("home_team_id"), first.get("away_team_id")
        other = {home: away, away: home}

        # Attack direction per (period, team): the sign of the median x of
        # that team's shots. Teams switch ends each period.
        xs = defaultdict(list)
        for _, _, r in evs:
            if r["event"] == "shot":
                x = num(r.get("x_coord"))
                if x is not None:
                    xs[(r["period_of_game"], r["team_id"])].append(x)
        direction = {}
        for key, vals in xs.items():
            vals.sort()
            med = vals[len(vals) // 2]
            if med != 0:
                direction[key] = 1 if med > 0 else -1
        for (per, team), d in list(direction.items()):
            direction.setdefault((per, other.get(team)), -d)

        kind = season_kind.get(sid, "regular")
        penalties = []
        last_shot = {}       # team -> time of last on-goal shot
        prev = None          # previous located event (t, x, team)
        for t, _, r in evs:
            ev = r["event"]
            per = r.get("period_of_game")
            if ev == "penalty" and r.get("power_play") == "1":
                length = num(r.get("penalty_length")) or 2
                team = r.get("team_id")
                if length == 4:  # double minor = two back-to-back minors
                    penalties.append(Penalty(team, t, 120, True))
                    penalties.append(Penalty(team, t + 120, 120, True))
                elif length >= 5:
                    penalties.append(Penalty(team, t, 300, False))
                else:
                    penalties.append(Penalty(team, t, 120, True))

            if ev == "shot":
                team = r.get("team_id")
                opp = other.get(team)
                d = direction.get((per, team))
                x, y = num(r.get("x_coord")), num(r.get("y_coord"))
                if d is None or x is None or y is None:
                    continue
                xa = x * d
                dx = NET_X - xa
                dist = math.hypot(dx, y)
                angle = math.degrees(math.atan2(abs(y), dx)) if dx > 0 else 90.0

                own = sum(1 for p in penalties if p.team == team and p.start <= t < p.end)
                opp_pen = sum(1 for p in penalties if p.team == opp and p.start <= t < p.end)
                own, opp_pen = min(own, 2), min(opp_pen, 2)
                base = 3 if (kind == "regular" and per == "4") else 5
                if base == 3:
                    s_for = 3 + max(0, opp_pen - own)
                    s_against = 3 + max(0, own - opp_pen)
                else:
                    s_for, s_against = base - own, base - opp_pen

                is_goal = r.get("goal") == "TRUE"
                g = goal_flags.get((gid, r.get("sec_from_start"), r.get("player_id"))) if is_goal else None
                empty_net = bool(g and g.get("empty_net") == "1")

                # A power-play goal ends the earliest-expiring opposing minor.
                if is_goal and s_for > s_against:
                    active = [p for p in penalties if p.team == opp and p.minor and p.start <= t < p.end]
                    if active:
                        min(active, key=lambda p: p.end).end = t

                rebound = team in last_shot and 0 <= t - last_shot[team] <= REBOUND_SECS
                rush = False
                if prev and 0 <= t - prev[0] <= RUSH_SECS:
                    pd = direction.get((per, team))
                    if pd is not None and prev[1] * pd < BLUE_X:
                        rush = True
                last_shot[team] = t

                shots.append({
                    "game_id": gid, "season_id": sid, "t": t, "period": per,
                    "team_id": team, "opp_id": opp,
                    "shooter": r.get("player_id"), "goalie": r.get("goalie_id"),
                    "type": r.get("event_type") or "Default",
                    "dist": dist, "angle": angle, "behind": dx <= 0,
                    "xa": xa, "y": y,
                    "rebound": rebound, "rush": rush,
                    "s_for": s_for, "s_against": s_against,
                    "goal": is_goal, "empty_net": empty_net,
                    "pp_flag": g.get("power_play") if g else None,
                    "sh_flag": g.get("short_handed") if g else None,
                    "on_home": ids(r.get("on_ice_home")), "on_away": ids(r.get("on_ice_away")),
                    "home": home,
                })
            x = num(r.get("x_coord"))
            if x is not None:
                prev = (t, x, r.get("team_id"))

        games[gid] = {"season_id": sid, "home": home, "away": away, "events": evs}
    return shots, games


def features(s):
    d = s["dist"]
    a = s["angle"]
    row = [
        1.0,
        d / 10, (d / 10) ** 2, math.log(d + 1),
        a / 10, (a / 10) ** 2, (d / 10) * (a / 10),
        1.0 if s["behind"] else 0.0,
        1.0 if s["rebound"] else 0.0,
        1.0 if s["rush"] else 0.0,
        1.0 if s["s_for"] > s["s_against"] else 0.0,
        1.0 if s["s_for"] < s["s_against"] else 0.0,
        1.0 if s["s_for"] == s["s_against"] and s["s_for"] < 5 else 0.0,
    ]
    row += [1.0 if s["type"] == t else 0.0 for t in SHOT_TYPES]
    return row


FEATURE_NAMES = (["intercept", "dist/10", "(dist/10)^2", "log(dist+1)", "angle/10",
                  "(angle/10)^2", "dist*angle", "behind net", "rebound", "rush",
                  "power play", "shorthanded", "4v4 / 3v3"]
                 + [f"type: {t}" for t in SHOT_TYPES])


# ------------------------------------------------------------- RAPM

def build_stints(games, goalie_ids, season_id):
    """Approximate 5v5 stints from on-ice lists on consecutive events:
    each gap between events is split evenly between the on-ice sets at
    either end. Returns [(home5, away5, seconds)]."""
    stints = []
    for g in games.values():
        if g["season_id"] != season_id:
            continue
        last = None
        for t, _, r in g["events"]:
            h = [p for p in ids(r.get("on_ice_home")) if p not in goalie_ids]
            a = [p for p in ids(r.get("on_ice_away")) if p not in goalie_ids]
            cur = (tuple(sorted(h)), tuple(sorted(a))) if len(h) == 5 and len(a) == 5 else None
            if last is not None:
                lt, lper, lset = last
                if r.get("period_of_game") == lper and t > lt:
                    half = (t - lt) / 2
                    if lset:
                        stints.append((lset[0], lset[1], half))
                    if cur:
                        stints.append((cur[0], cur[1], half))
            last = (t, r.get("period_of_game"), cur)
    return stints


def rapm(stints, shots_5v5):
    """Ridge regression of 5v5 xG rates on offense/defense player terms.
    Returns {player: (off_xg60, def_xg60, toi_secs)}."""
    agg = defaultdict(lambda: [0.0, 0.0, 0.0])   # (home, away) -> secs, home xGF, away xGF
    for h, a, secs in stints:
        agg[(h, a)][0] += secs
    for s in shots_5v5:
        home_set = tuple(sorted(s["on_home_sk"]))
        away_set = tuple(sorted(s["on_away_sk"]))
        key = (home_set, away_set)
        if key not in agg:
            continue
        if s["team_id"] == s["home"]:
            agg[key][1] += s["xg"]
        else:
            agg[key][2] += s["xg"]

    players = sorted({p for h, a in agg for p in h + a})
    idx = {p: i for i, p in enumerate(players)}
    n = len(players)
    P = 2 * n + 1  # off terms, def terms, home-ice
    XtWX = [[0.0] * P for _ in range(P)]
    XtWy = [0.0] * P
    toi = defaultdict(float)
    rows = []
    tot_w = tot_wy = 0.0
    for (h, a), (secs, hx, ax) in agg.items():
        if secs <= 0:
            continue
        w = secs / 3600
        for p in h + a:
            toi[p] += secs
        rows.append(([idx[p] for p in h], [n + idx[p] for p in a], 1, w, hx / w))
        rows.append(([idx[p] for p in a], [n + idx[p] for p in h], 0, w, ax / w))
        tot_w += 2 * w
        tot_wy += hx + ax
    mean = tot_wy / tot_w if tot_w else 0.0
    for off, dfn, is_home, w, rate in rows:
        cols = off + dfn + ([2 * n] if is_home else [])
        yv = rate - mean
        for c in cols:
            XtWy[c] += w * yv
            row = XtWX[c]
            for c2 in cols:
                row[c2] += w
    for i in range(P):
        XtWX[i][i] += RAPM_LAMBDA_HOURS
    beta = solve_spd(XtWX, XtWy)
    return {p: (beta[idx[p]], beta[n + idx[p]], toi[p]) for p in players}, mean


# ------------------------------------------------------------- main

def main():
    try:
        pbp = read_csv("pwhl_pbp.csv")
    except FileNotFoundError:
        # On a CI cache miss the PBP is absent; keep last run's JSON rather
        # than overwriting it with empty output.
        print("  note: pwhl_pbp.csv not found, keeping existing model JSON")
        return

    meta = read_json("pwhl_meta.json")
    awards = read_json("pwhl_awards.json")
    season_names = {s["season_id"]: s["name"] for s in meta["seasons"]}

    def kind_of(name):
        return "playoff" if "Playoff" in name else "preseason" if "Pre" in name else "regular"

    season_kind = {sid: kind_of(n) for sid, n in season_names.items()}
    season_of = {r["game_id"]: r["season_id"] for r in read_csv("pwhl_season_game_ids.csv")}
    players_info = {p["player_id"]: p for p in read_csv("pwhl_players_info.csv")}
    # Standings come straight from the feed every run, so use them to fill
    # any team the teams list is missing.
    team_code, team_name = {}, {}
    for r in read_csv("pwhl_standings.csv"):
        key = (r.get("season_id"), r.get("team_id"))
        team_code[key], team_name[key] = r.get("team_code"), r.get("name")
    for r in read_csv("pwhl_teams.csv"):
        key = (r["season_id"], r["team_id"])
        team_code[key], team_name[key] = r["team_code"], r["team_name"]

    # Names: profiles first, then whatever name the play-by-play carries
    # (covers goalies and anyone whose profile hasn't been fetched yet).
    pbp_names = {}
    for r in pbp:
        for pid_col, first, last in (("player_id", "player_name_first", "player_name_last"),
                                     ("goalie_id", "goalie_first", "goalie_last")):
            pid = r.get(pid_col)
            if pid not in (None, "", "NA") and pid not in pbp_names and r.get(last) not in (None, "", "NA"):
                pbp_names[pid] = f"{r.get(first) or ''} {r.get(last)}".strip()

    def pname(pid):
        p = players_info.get(pid) or {}
        return ((p.get("first_name", "") + " " + p.get("last_name", "")).strip()
                or pbp_names.get(pid) or f"Player {pid}")

    print("Parsing play-by-play...")
    shots, games = parse_games(pbp, season_of, season_kind)
    model_shots = [s for s in shots if not s["empty_net"]]
    print(f"  {len(shots)} on-goal shots, {len(model_shots)} with a goalie in net")

    # Strength-tracker sanity check against the feed's own goal flags.
    checked = agree = 0
    for s in model_shots:
        if s["goal"] and s["pp_flag"] in ("0", "1"):
            checked += 1
            agree += (s["pp_flag"] == "1") == (s["s_for"] > s["s_against"])
    strength_accuracy = agree / checked if checked else None
    print(f"  strength tracker matches feed PP flag on {agree}/{checked} goals")

    # ---- xG model: validate on held-out games, then refit on everything
    X = [features(s) for s in model_shots]
    y = [1 if s["goal"] else 0 for s in model_shots]
    rng = random.Random(7)
    game_ids = sorted({s["game_id"] for s in model_shots})
    test_games = set(rng.sample(game_ids, len(game_ids) // 5))
    tr = [i for i, s in enumerate(model_shots) if s["game_id"] not in test_games]
    te = [i for i, s in enumerate(model_shots) if s["game_id"] in test_games]
    beta_cv = fit_logistic([X[i] for i in tr], [y[i] for i in tr])
    p_te = [predict(beta_cv, X[i]) for i in te]
    y_te = [y[i] for i in te]
    base_rate = sum(y[i] for i in tr) / len(tr)
    holdout = {
        "auc": round(auc(p_te, y_te), 3),
        "log_loss": round(log_loss(p_te, y_te), 4),
        "baseline_log_loss": round(log_loss([base_rate] * len(te), y_te), 4),
        "shots": len(te),
    }
    print(f"  holdout: {holdout}")

    beta = fit_logistic(X, y)

    # Scoring levels drift between league years (2025-26 ran ~4% below the
    # pooled model), so shift the intercept per league year until xG sums to
    # actual goals. Otherwise one year's whole goalie pool would look above
    # or below average. Years with too few shots so far (e.g. the first
    # weeks of a new season) keep the pooled intercept.
    # A preseason belongs to the regular season after it, playoffs to the
    # one before ("2025 Playoffs" closes out 2024-25).
    ordered = sorted(season_names, key=int)
    regulars = [s for s in ordered if season_kind[s] == "regular"]
    year_key = {}
    for sid in ordered:
        if season_kind[sid] == "playoff":
            prior = [r for r in regulars if int(r) < int(sid)]
            year_key[sid] = prior[-1] if prior else sid
        elif season_kind[sid] == "preseason":
            later = [r for r in regulars if int(r) > int(sid)]
            year_key[sid] = later[0] if later else sid
        else:
            year_key[sid] = sid

    def league_year(sid):
        return season_names.get(year_key.get(sid, sid), sid).split(" ")[0]

    year_offset = {}
    by_year = defaultdict(list)
    for i, s in enumerate(model_shots):
        by_year[league_year(s["season_id"])].append(i)
    for yr, idxs in by_year.items():
        if len(idxs) < 1500:
            year_offset[yr] = 0.0
            continue
        z = [sum(b * v for b, v in zip(beta, X[i])) for i in idxs]
        goals = sum(y[i] for i in idxs)
        off = 0.0
        for _ in range(30):
            ps = [1 / (1 + math.exp(-(zi + off))) for zi in z]
            f = sum(ps) - goals
            fp = sum(p * (1 - p) for p in ps)
            off -= f / fp
            if abs(f) < 1e-6:
                break
        year_offset[yr] = off
    print("  league-year intercept offsets:", {k: round(v, 3) for k, v in year_offset.items()})

    for s, x in zip(model_shots, X):
        z = sum(b * v for b, v in zip(beta, x)) + year_offset.get(league_year(s["season_id"]), 0.0)
        s["xg"] = 1 / (1 + math.exp(-z))
    for s in shots:
        if s["empty_net"]:
            s["xg"] = None

    # Calibration on the holdout fold, by predicted-probability decile.
    order = sorted(range(len(te)), key=lambda k: p_te[k])
    calib = []
    for b in range(10):
        chunk = order[b * len(order) // 10:(b + 1) * len(order) // 10]
        calib.append({
            "pred": round(sum(p_te[k] for k in chunk) / len(chunk), 4),
            "actual": round(sum(y_te[k] for k in chunk) / len(chunk), 4),
            "n": len(chunk),
        })

    # ---- Danger map: mean xG by location (offensive half, normalized)
    GX, GY = 20, 17   # 5 ft cells over x 0..100, y -42.5..42.5
    cells = defaultdict(lambda: [0, 0.0, 0])
    for s in model_shots:
        if 0 <= s["xa"] <= 100 and -42.5 <= s["y"] <= 42.5:
            bx = min(GX - 1, int(s["xa"] / 100 * GX))
            by = min(GY - 1, int((s["y"] + 42.5) / 85 * GY))
            c = cells[(bx, by)]
            c[0] += 1
            c[1] += s["xg"]
            c[2] += s["goal"]
    danger = {"grid_x": GX, "grid_y": GY, "x_range": [0, 100], "y_range": [-42.5, 42.5],
              "cells": [{"bx": bx, "by": by, "shots": c[0], "xg": round(c[1], 2), "goals": c[2]}
                        for (bx, by), c in cells.items() if c[0] >= 3]}

    # ---- Per-season aggregates
    xg_by_season, ratings_by_season = {}, {}
    goalie_ids = {s["goalie"] for s in shots if s["goalie"] not in (None, "", "NA")}
    goalie_ids |= {pid for pid, p in players_info.items() if (p.get("position") or "").upper() == "G"}

    pen_rows = [r for r in pbp if r["event"] == "penalty" and r.get("power_play") == "1"]

    for sid in sorted({s["season_id"] for s in shots}, key=int):
        ss = [s for s in model_shots if s["season_id"] == sid]
        if not ss:
            continue

        # Teams
        tm = defaultdict(lambda: {"xgf": 0.0, "xga": 0.0, "gf": 0, "ga": 0, "sf": 0, "sa": 0})
        for s in ss:
            f, a = tm[s["team_id"]], tm[s["opp_id"]]
            f["xgf"] += s["xg"]; f["gf"] += s["goal"]; f["sf"] += 1
            a["xga"] += s["xg"]; a["ga"] += s["goal"]; a["sa"] += 1
        teams = []
        for tid, v in tm.items():
            teams.append({
                "team_id": tid, "code": team_code.get((sid, tid), tid),
                "name": team_name.get((sid, tid), tid),
                "xgf": round(v["xgf"], 1), "xga": round(v["xga"], 1),
                "gf": v["gf"], "ga": v["ga"], "sf": v["sf"], "sa": v["sa"],
                "xgf_pct": round(100 * v["xgf"] / max(v["xgf"] + v["xga"], 1e-9), 1),
            })
        teams.sort(key=lambda r: -r["xgf_pct"])

        # Goalies
        gl = defaultdict(lambda: {"sa": 0, "ga": 0, "xga": 0.0, "teams": defaultdict(int)})
        for s in ss:
            g = gl[s["goalie"]]
            g["sa"] += 1; g["ga"] += s["goal"]; g["xga"] += s["xg"]
            g["teams"][s["opp_id"]] += 1
        goalies = []
        for pid, v in gl.items():
            if pid in (None, "", "NA"):
                continue
            tid = max(v["teams"], key=v["teams"].get)
            goalies.append({
                "player_id": pid, "name": pname(pid), "team_code": team_code.get((sid, tid), ""),
                "shots": v["sa"], "goals_against": v["ga"], "xga": round(v["xga"], 2),
                "gsax": round(v["xga"] - v["ga"], 2),
                "sv_pct": round(1 - v["ga"] / v["sa"], 4) if v["sa"] else None,
                "xsv_pct": round(1 - v["xga"] / v["sa"], 4) if v["sa"] else None,
            })
        goalies.sort(key=lambda r: -r["gsax"])

        # Skater shooting
        sk = defaultdict(lambda: {"shots": 0, "goals": 0, "ixg": 0.0})
        for s in ss:
            p = sk[s["shooter"]]
            p["shots"] += 1; p["goals"] += s["goal"]; p["ixg"] += s["xg"]

        xg_by_season[sid] = {
            "teams": teams,
            "goalies": goalies,
            "skaters": sorted(
                [{"player_id": pid, "name": pname(pid), "shots": v["shots"], "goals": v["goals"],
                  "ixg": round(v["ixg"], 2), "g_minus_xg": round(v["goals"] - v["ixg"], 2)}
                 for pid, v in sk.items() if pid not in (None, "", "NA") and pid not in goalie_ids],
                key=lambda r: -r["ixg"]),
        }

        # ---- Ratings
        skaters = {r["player_id"]: r for r in awards.get(sid, [])}
        if not skaters:
            continue

        # Assists by slot, from goal events (player_two = A1, player_three = A2)
        a1, a2 = defaultdict(int), defaultdict(int)
        for r in pbp:
            if r["event"] == "goal" and season_of.get(r["game_id"]) == sid:
                if r.get("player_two_id") not in (None, "", "NA"):
                    a1[r["player_two_id"]] += 1
                if r.get("player_three_id") not in (None, "", "NA"):
                    a2[r["player_three_id"]] += 1
        minors = defaultdict(float)
        for r in pen_rows:
            if season_of.get(r["game_id"]) == sid:
                length = num(r.get("penalty_length")) or 2
                minors[r.get("player_id")] += 2.0 if length == 4 else 2.5 if length >= 5 else 1.0

        # League power-play goal value per minor penalty this season
        pp_goals = sum(1 for s in ss if s["goal"] and s["s_for"] > s["s_against"])
        total_minors = sum(minors.values())
        pp_value = pp_goals / total_minors if total_minors else 0.17

        def pos_group(pid):
            # Feed mixes "D", "RD", "LD" for defenders and "F"/"LW"/"RW" for forwards.
            return "D" if "D" in (skaters[pid].get("pos") or "").upper() else "F"

        rate = defaultdict(lambda: defaultdict(float))
        for pid, r in skaters.items():
            g = pos_group(pid)
            rate[g]["toi"] += r["toi"]
            rate[g]["ixg"] += sk[pid]["ixg"] if pid in sk else 0.0
            rate[g]["a1"] += a1[pid]
            rate[g]["a2"] += a2[pid]
            rate[g]["minors"] += minors[pid]
        per_sec = {g: {k: v / max(rate[g]["toi"], 1) for k, v in rate[g].items()} for g in rate}

        cover = sum(1 for s in ss if s["on_home"] and s["on_away"]) / len(ss)
        full_model = cover >= MIN_ONICE_COVERAGE
        rapm_res, mean_rate = {}, None
        if full_model:
            for s in ss:
                s["on_home_sk"] = [p for p in s["on_home"] if p not in goalie_ids]
                s["on_away_sk"] = [p for p in s["on_away"] if p not in goalie_ids]
            ev5 = [s for s in ss if len(s["on_home_sk"]) == 5 and len(s["on_away_sk"]) == 5]
            stints = build_stints(games, goalie_ids, sid)
            rapm_res, mean_rate = rapm(stints, ev5)
            print(f"  season {sid}: RAPM on {len(stints)} stint pieces, {len(ev5)} 5v5 shots, "
                  f"{len(rapm_res)} skaters, league 5v5 xG/60 {mean_rate:.2f}")

        rows = []
        for pid, r in skaters.items():
            g = pos_group(pid)
            ps = per_sec.get(g, {})
            shots_n = sk[pid]["shots"] if pid in sk else 0
            ixg = sk[pid]["ixg"] if pid in sk else 0.0
            goals = sk[pid]["goals"] if pid in sk else 0
            comp = {
                "finishing": (goals - ixg) * shots_n / (shots_n + FINISH_SHRINK_SHOTS),
                "penalties": -pp_value * (minors[pid] - r["toi"] * ps.get("minors", 0)),
                "faceoffs": FACEOFF_GOALS_PER_WIN * (r["fo_wins"] - 0.5 * r["fo_attempts"]),
            }
            if full_model:
                off, dfn, toi5 = rapm_res.get(pid, (0.0, 0.0, 0.0))
                comp["ev_offense"] = off * toi5 / 3600
                comp["ev_defense"] = -dfn * toi5 / 3600
            else:
                comp["shot_generation"] = ixg - r["toi"] * ps.get("ixg", 0)
                comp["playmaking"] = (A1_WEIGHT * (a1[pid] - r["toi"] * ps.get("a1", 0))
                                      + A2_WEIGHT * (a2[pid] - r["toi"] * ps.get("a2", 0)))
            total = sum(comp.values())
            rows.append({
                "player_id": pid, "name": r["name"], "team_code": r["team_code"], "pos": g,
                "gp": r["gp"], "toi": r["toi"],
                "components": {k: round(v, 2) for k, v in comp.items()},
                "total": round(total, 2),
                "per30": round(total / r["gp"] * 30, 2) if r["gp"] else None,
            })
        rows.sort(key=lambda x: -x["total"])

        ratings_by_season[sid] = {
            "model": "full" if full_model else "box",
            "onice_coverage": round(cover, 3),
            "pp_goals_per_minor": round(pp_value, 3),
            "league_5v5_xg60": round(mean_rate, 3) if mean_rate is not None else None,
            "skaters": rows,
            "goalies": [{"player_id": x["player_id"], "name": x["name"], "team_code": x["team_code"],
                         "shots": x["shots"], "gsax": x["gsax"]} for x in goalies],
        }

    write_json("pwhl_xg.json", {
        "model": {
            "shots": len(model_shots), "goals": sum(y),
            "features": FEATURE_NAMES, "coefficients": [round(b, 4) for b in beta],
            "holdout": holdout, "calibration": calib,
            "league_year_offsets": {k: round(v, 4) for k, v in year_offset.items()},
            "strength_check": {"goals_checked": checked,
                               "accuracy": round(strength_accuracy, 3) if strength_accuracy else None},
        },
        "danger_map": danger,
        "by_season": xg_by_season,
    })
    write_json("pwhl_ratings.json", {
        "constants": {
            "finish_shrink_shots": FINISH_SHRINK_SHOTS,
            "a1_weight": A1_WEIGHT, "a2_weight": A2_WEIGHT,
            "faceoff_goals_per_win": FACEOFF_GOALS_PER_WIN,
            "rapm_lambda_hours": RAPM_LAMBDA_HOURS,
        },
        "by_season": ratings_by_season,
    })


if __name__ == "__main__":
    main()

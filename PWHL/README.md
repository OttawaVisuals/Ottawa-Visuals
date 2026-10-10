# PWHL Dashboard

**Live:** [`pwhl.html`](pwhl.html) (embedded on the homepage as report *PWHL dashboard*)

Standings, forecasts, team and player pages, expected goals and superlatives across
every PWHL season, refreshed daily from the league's own stats feed (HockeyTech).

## Pages

Every page shares one header (site bar, PWHL section nav, team-logo strip, "data
through" date) and remembers the season you picked (`?season=` / localStorage).

| Page | What's on it |
|---|---|
| `pwhl.html` | Home: league at a glance, standings, player leaders, playoff bracket, transactions, links to the rest |
| `forecast.html` | Elo ratings, upcoming-game win chances, playoff odds, prediction scorecard strip |
| `teams.html` | Team cards, goals for/against, special teams, team xG share, attendance |
| `team.html?code=OTT` | One team: outlook, record tiles, results, top contributors, most-used lines, roster stats, game log, franchise leaders, current roster |
| `players.html` | Sortable table of every skater and goalie, impact ratings, expected goals |
| `player.html?id=<player_id>` | One player: role tag, season tiles, game-by-game chart, shot map, shot mix by type, goalie matchups, home/away split, best games, career table, game log |
| `superlatives.html` | Tongue-in-cheek awards (totals or per 60), the Rap Sheet, the Hall of Sustained Quirk |
| `methodology.html` | Data sources and methods, the xG model's report card, league shot patterns |

## Layout

| Path | Purpose |
|---|---|
| `pwhl.css` | Shared styles for all pages |
| `pwhl-teams.js` | Team colours (`PWHL_TEAM_COLORS`), the in-bar label Chart.js plugin, the "show all rows" helper |
| `pwhl-core.js` | Shared header/nav/logo strip, theme hook, JSON loader (`PWHL.load`), season picker, chart helpers, sortable tables |
| `pwhl-sections.js` | Render functions for the dashboard sections; each page calls the ones it shows |
| `scripts/daily_update.R` | Pulls the latest games/standings/players from the PWHL stats feed |
| `scripts/build_dashboard_json.py` | Aggregates the raw CSVs in `data/` into the `data/json/` files the pages read, including one `players/<id>.json` per player, goalie lines, the rap sheet and current rosters |
| `scripts/build_elo.py` | Team Elo ratings, upcoming-game win chances and 10,000-run playoff simulations; writes `pwhl_elo.json`. The playoff format per league year lives in its `FORMATS` dict, so update it when the league changes format |
| `scripts/build_models.py` | Fits the expected-goals model on the play-by-play; writes `pwhl_xg.json` (GSAx, team/skater xG, danger map), `pwhl_ratings.json` (player impact ratings), `pwhl_lines.json` (most-used 5v5 trios/pairs) and a `model` block (shot mix, matchups, xG per game) into each player file |
| `data/*.csv` | Raw pulled data (games, players, standings, rosters, play-by-play, transactions, venues, logos, media) |
| `data/json/` | Committed build output for the pages, including `pwhl_meta.json` |

## Rebuilding the data

```r
Rscript PWHL/scripts/daily_update.R
```
```bash
python PWHL/scripts/build_dashboard_json.py
```
```bash
python PWHL/scripts/build_models.py
```
```bash
python PWHL/scripts/build_elo.py
```

Run them in that order from the repo root: the model step reads the meta/awards JSON
the aggregator writes, and needs `data/pwhl_pbp.csv` (gitignored, cached in CI).

# PWHL Dashboard

**Live:** [`pwhl.html`](pwhl.html) (embedded on the homepage as report *PWHL dashboard*)

Standings, player leaders, shot maps and playoff results across three PWHL
seasons, refreshed daily from the league's own stats feed (HockeyTech). An
early draft — sections are candidates, not final.

## Layout

| Path | Purpose |
|---|---|
| `pwhl.html` | The dashboard page (loads JSON from `data/json/`, `DATA_BASE = 'data/json/'`) |
| `player.html` | Per-player page, `player.html?id=<player_id>`: season tiles, game log, shot map, model ratings, career table. Reads `data/json/players/<id>.json` |
| `pwhl-teams.js` | Shared by both pages: team colours (`PWHL_TEAM_COLORS`), the in-bar label Chart.js plugin, and the "show all rows" table helper |
| `scripts/daily_update.R` | Pulls the latest games/standings/players from the PWHL stats feed |
| `scripts/build_dashboard_json.py` | Aggregates the raw CSVs in `data/` into the compact `data/json/` files the page reads |
| `scripts/build_elo.py` | Team Elo ratings, upcoming-game win chances and 10,000-run playoff simulations; writes `pwhl_elo.json`. The playoff format per league year lives in its `FORMATS` dict, so update it when the league changes format |
| `scripts/build_models.py` | Fits the expected-goals model on the play-by-play; writes `pwhl_xg.json` (GSAx, team/skater xG, danger map) and `pwhl_ratings.json` (player impact ratings) |
| `data/*.csv` | Raw pulled data (games, players, standings, rosters, play-by-play, transactions, venues, logos) |
| `data/json/` | Committed build output for the dashboard, including `pwhl_meta.json` |

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

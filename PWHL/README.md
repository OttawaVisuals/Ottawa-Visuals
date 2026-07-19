# PWHL Dashboard

**Live:** [`pwhl.html`](pwhl.html) (embedded on the homepage as report *PWHL dashboard*)

Standings, player leaders, shot maps and playoff results across three PWHL
seasons, refreshed daily from the league's own stats feed (HockeyTech). An
early draft — sections are candidates, not final.

## Layout

| Path | Purpose |
|---|---|
| `pwhl.html` | The dashboard page (loads JSON from `data/json/`, `DATA_BASE = 'data/json/'`) |
| `scripts/daily_update.R` | Pulls the latest games/standings/players from the PWHL stats feed |
| `scripts/build_dashboard_json.py` | Aggregates the raw CSVs in `data/` into the compact `data/json/` files the page reads |
| `data/*.csv` | Raw pulled data (games, players, standings, rosters, play-by-play, transactions, venues, logos) |
| `data/json/` | Committed build output for the dashboard, including `pwhl_meta.json` |

## Rebuilding the data

```r
Rscript PWHL/scripts/daily_update.R
```
```bash
python PWHL/scripts/build_dashboard_json.py
```

Run the R pull first, then the Python aggregator, from the repo root.

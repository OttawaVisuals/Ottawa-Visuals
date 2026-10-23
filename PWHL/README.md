# PWHL Dashboard

**Live:** [`pwhl.html`](pwhl.html) (embedded on the homepage as report *PWHL dashboard*)

Standings, team and player pages, historical season replays and superlatives across
every PWHL season, refreshed daily from the league's own stats feed (HockeyTech).

## Pages

Forecasts are paused; the old forecast URL returns to the historical dashboard.

Every active page shares one header (site bar, PWHL section nav, team-logo strip, "data
through" date) and remembers the season you picked (`?season=` / localStorage).

| Page | What's on it |
|---|---|
| `pwhl.html` | Home: all-time league KPIs, a season-by-season summary, standings, player leaders, playoff bracket and rotating historical awards |
| `teams.html` | Team cards, goals for/against, special teams and attendance |
| `team.html?code=OTT` | One team: historical record tiles, results, top contributors, home/away team and goalie shot maps, player award leaders, most-used lines, roster stats, game log, franchise leaders, current roster |
| `players.html` | Player search and sortable tables of every skater and goalie |
| `player.html?id=<player_id>` | One player: role tag, season tiles, game-by-game chart, shot map, goalie matchups, home/away split, best games, career table, game log |
| `superlatives.html` | Tongue-in-cheek player awards (totals or per 60), historical team awards, the Rap Sheet, the Hall of Sustained Quirk |
| `travel.html` | Animated, estimated 2025–26 regular-season itineraries for all eight teams, with road, air and airport-drive distances and times |
| `recap.html` | 75-second replay of each completed regular season through playoffs and the champion finale, with modeled routes, playoff bracket, game highlights, counters and team trends |
| `origins.html` | Zoomable player birthplace map with city-level locations and season selector |
| `methodology.html` | Data sources, stat definitions, known coverage limits and league shot patterns |

## Layout

Publication review corrections, their causes and verification are recorded in
[`ACCURACY_FIXES.md`](ACCURACY_FIXES.md).
Mobile layout checks, fixes and device-testing limits are recorded in
[`MOBILE_CHECKS.md`](MOBILE_CHECKS.md).

| Path | Purpose |
|---|---|
| `pwhl.css` | Shared styles for all pages |
| `pwhl-teams.js` | Team colours (`PWHL_TEAM_COLORS`), the in-bar label Chart.js plugin, the "show all rows" helper |
| `pwhl-core.js` | Shared header/nav/logo strip, theme hook, JSON loader (`PWHL.load`), season picker, chart helpers, sortable tables |
| `pwhl-sections.js` | Render functions for the dashboard sections; each page calls the ones it shows |
| `scripts/daily_update.R` | Pulls the latest games/standings/players from the PWHL stats feed |
| `scripts/build_dashboard_json.py` | Aggregates the raw CSVs in `data/` into the `data/json/` files the pages read, including one `players/<id>.json` per player, home/away team shot maps, goalie lines, the rap sheet and current rosters |
| `scripts/pwhl_stats.py` | Shared rules for duplicate stat rows, league-wide player totals, club-specific splits and matching shot/goal events |
| `data/json/pwhl_team_players.json` | Season × club × player splits for team pages; league leaderboards and awards use separate combined-player totals |
| `tests/test_stats.py` | Counting regressions, including traded players, shot/goal reconciliation and roster labels; run after the dashboard and team-award builders |
| `scripts/build_pwhl_overview.py` | Builds league-wide completed-game totals for the dashboard home KPIs |
| `scripts/import_pwhl_salary_guide.py` | One-time extraction of the supplied PWHLPA 2025–26 salary PDF into the reviewable salary CSV (requires `pypdf`) |
| `scripts/build_pwhl_team_awards.py` | Builds season-by-season team scoring concentration, penalty-rate and listed-salary distribution comparisons |
| `scripts/build_pwhl_recap.py` | Reconstructs regular-season standings, playoff bracket snapshots, game highlights, birthplace counts and running counters; validates season-end team totals and writes `pwhl_season_recap.json` |
| `scripts/geocode_recap_birthplaces.py` | One-time, cached lookup of player birthplace coordinates; run manually when new birthplace names are added, then rebuild the recap JSON |
| `scripts/build_elo.py` | Team Elo ratings, upcoming-game win chances and 10,000-run playoff simulations; writes `pwhl_elo.json`. The playoff format per league year lives in its `FORMATS` dict, so update it when the league changes format |
| `scripts/build_models.py` | Builds optional experimental model artifacts and most-used 5v5 line summaries; active pages do not use the experimental outputs |
| `data/*.csv` | Raw pulled data (games, players, standings, rosters, play-by-play, transactions, venues, logos, media) |
| `data/pwhl_salaries_2025_26.csv` | Player/team salary rows extracted from the PWHLPA salary guide; 2025–26 only |
| `data/json/` | Committed build output for the pages, including `pwhl_meta.json` |

When `pwhl-core.js` changes, bump its `?v=` value on every PWHL HTML page.
GitHub Pages caches JavaScript, and an unchanged URL can keep the old navigation
visible after a deployment.

## Season links and player search

Season selections are written to `?season=` as well as localStorage. Player and
team links carry that season; the player header labels selected-season teams
separately from the latest roster. The players directory also preserves name
filter (`q`), team (`team`), position (`pos`), and goalie view (`kind=goalies`) in
its URL. Search ignores accents and common apostrophe/hyphen differences and
shows selectable matches instead of choosing the first partial match.
Goalie comparisons also save `min_gp`: the default is five games, adjustable
from zero (all goalies) to 100. This is a reader-controlled small-sample filter,
not an official league qualification. The page states the applied threshold
and exclusions. Tapping or clicking a shooting-scatter point shows its stats
and a profile link for the selected season; filtering removes stale selections.

Shared sortable tables use native buttons with `aria-sort`, retain keyboard
focus after sorting, and announce direction changes. Page load failures offer
a plain-language message and a retry button; technical details stay in the
console.

## Award icons

The award SVGs in `icon-concepts/` share a 96 × 64 canvas and use theme-aware
outlines, orange accents and simplified shapes for the 62 × 40 card and 28 × 24
Hall displays. Edit the individual SVGs, then run
`python PWHL/scripts/build_award_sprite.py` to refresh `icon-concepts/awards.svg`.
The dashboard uses that sprite so colours follow the selected page theme;
standalone SVGs follow the operating system theme. After editing icons, bump the
sprite version in `awardIcon()` and the `pwhl-sections.js?v=` value on its HTML
consumers. Point Producer, its rate variant, and Fair Pay use distinct icons.

## Team travel estimates

On narrow screens the map centres on the current route marker. Manual panning
pauses following; the Follow route button, a new team, or selecting another leg
recentres it. A swipe/keyboard hint appears when the map is wider than its panel.

`python PWHL/scripts/build_pwhl_travel.py` rebuilds the static travel JSON from
season 8 game summaries and venue coordinates. Airport positions are a selected
snapshot from OurAirports in `data/pwhl_travel_airports.csv`. On first build the
script queries OSRM for road distance/time and saves responses in
`data/pwhl_travel_road_cache.json`; later builds work from that cache.

Each team starts from its most-used home rink. The model assumes a return there
when there are more than four days between games while outside its home market.
A leg is assigned bus if its OSRM road route is at
most 400 miles, otherwise air between the listed major airports plus road
transfers. The map is schematic, and neither mode nor itinerary is a record of
what the team actually booked. The league CBA also uses a six-hour rule, which
this simplified distance-only scenario does not apply.

## Rebuilding the data

```r
Rscript PWHL/scripts/daily_update.R
```
```bash
python PWHL/scripts/build_dashboard_json.py
```
```bash
python PWHL/scripts/build_pwhl_overview.py
```
```bash
python PWHL/scripts/build_pwhl_team_awards.py
```
```bash
python PWHL/scripts/build_pwhl_recap.py
```
```bash
python PWHL/scripts/build_models.py
```
```bash
python PWHL/scripts/build_elo.py
```

Run them in that order from the repo root: the model step reads the meta/awards JSON
the aggregator writes, and needs `data/pwhl_pbp.csv` (gitignored, cached in CI).

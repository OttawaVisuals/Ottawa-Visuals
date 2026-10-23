# Publication accuracy fixes — October 23, 2026

The review found counting and presentation bugs in our processing and pages. The raw league CSVs were not edited. The corrections below are implemented in the builders and frontend, with regenerated JSON.

| Problem | Why it happened | Correction and verified example |
|---|---|---|
| Methodology charts double-counted goals | HockeyTech usually supplies both a scoring shot and a separate goal record. The builder counted both. | Pair the representations one-to-one, retaining goal-only records. Goals by period now total **1,625**, down from 3,248. The map has **19,385 located shots, including 1,623 goals**; two goals lack valid coordinates. |
| Team stats used production from other clubs | The team page reused league award rows, which combine a player's clubs and assign one main team. | New `pwhl_team_players.json` retains club splits for roster stats, top scorers, season summaries, goalie selectors and franchise totals. Cava: **Ottawa 17 GP/4 points; Vancouver 13 GP/5 points**. Vanišová's Ottawa regular-season career: **36 GP/24 points**, including her 2024 stint. |
| Traded players disappeared from league leaders | The homepage builder ranked each club stint separately, unlike the Players directory. | Combine and deduplicate by player and season before ranking; derive faceoff percentage from summed wins/attempts. Eldridge now appears with **23 points in 30 games**, labelled BOS/SEA. |
| Standings records did not sum to games played | The displayed W field actually meant regulation wins; overtime and shootout win fields were not rendered. | Show **RW, OTW and SOW** separately and explain the points system. Montréal's 2025–26 row now includes its three overtime and three shootout wins. |
| Replay leaders depended on the previously viewed frame | The playoff branch updated the bracket but skipped the player tables. A direct seek retained opening-day leaders. | Every frame chooses the correct leaderboard snapshot. Playoffs explicitly display **final regular-season leaders**. Direct seeks to the end were checked in all three seasons, along with seeking back to the start. |
| Scorer counts included players with no points | The builder counted every player entry in its points dictionary, including zero totals. | Count only positive totals. Montréal's 2025–26 “players recorded a point” count is **21**, not 24. |
| Latest roster had no season label | Season names came from played-player statistics, so the upcoming roster season had no name. Rendering also replaced “Current roster” with “Roster.” | Read names from the season catalog and preserve **Current roster · 2026-27 Pre-Season**, separate from the historical selector. |
| Line time looked like measured shift time | Estimated play-by-play intervals reached the page without an explanation of how they were inferred. | Label **estimated minutes** and explain that each interval is split between endpoint lineups, subject to missing event coverage. |

The methodology now matches the selectable competition phases, links official statistics, identifies the site as independent, and explains club splits, the shot pairing and replay scope. The event-mix chart separates saved shots from goals. Goals-by-period now includes all recorded overtime periods; its former hard-coded labels omitted numeric period keys beyond regulation. The methodology layout's redundant closing tags were also removed.

## Prevention and verification

- A shared counting module, `scripts/pwhl_stats.py`, handles club splits, combined leaderboards, duplicate season-stat aliases and shot/goal pairing. Identical statistics for two different named clubs remain distinct stints.
- Twelve regression tests cover the reported examples, weighted faceoff percentages, goalie club splits, duplicate aliases, simultaneous shot timestamps, missing coordinates and roster labels.
- The GitHub daily-update workflow runs those tests after rebuilding the dashboard/team-award JSON and will not publish refreshed data if they fail.
- All external and inline PWHL JavaScript passed syntax checks. Local browser checks confirmed the corrected standings, homepage leaders, Ottawa roster/franchise totals, methodology chart values and replay seeking in 2024, 2024–25 and 2025–26. No browser errors were reported in those checks.
- Shared script URLs were versioned across their HTML consumers to avoid retaining old JavaScript after deployment.

Rebuild and verify from the repository root:

```powershell
python PWHL/scripts/build_dashboard_json.py
python PWHL/scripts/build_pwhl_team_awards.py
python -m unittest discover -s PWHL/tests -p 'test_*.py' -v
```

The test for raw play-by-play reconciliation skips when the optional cached CSV is unavailable. Our verification included that CSV. This is a targeted correction, not a certification of every upstream statistic or a full phone/accessibility audit. Deployment is separate from the local commit. Subreddit approval was not requested or obtained by this work.

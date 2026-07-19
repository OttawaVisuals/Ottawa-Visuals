# Ottawa Ward Elections

**Live:** [`ottawa_ward_elections.html`](ottawa_ward_elections.html) (embedded on the homepage as report *Ottawa historical elections*)

Ward-by-ward turnout and vote shares across Ottawa municipal elections,
including the mayor's race and each ward's council race.

## Layout

| Path | Purpose |
|---|---|
| `ottawa_ward_elections.html` | The visual page — fetches ward boundaries straight from this repo's raw GitHub URL, no local build step needed to view it |
| `ward_results.csv` | Raw per-ward, per-year results (registered voters, votes, winner) for mayor + council |
| `BuildWardData.py` | Parses `ward_results.csv` into `ward_data.json` / `Ottawa_Election.json` |
| `Ottawa_Election_Wards_Only.json` | Ward boundary GeoJSON the page loads directly (`GEOJSON_URL`) |
| `Ottawa_Election_Map_2022.json`, `ELECTORAL_DISTRICT*.json` | Supporting boundary layers (2022 map, GTA/Ottawa electoral districts) |
| `Ottawa_Summary.csv` | Rolled-up summary stats used for quick sanity checks |

## Rebuilding the data

```bash
python Ottawa_Elections/BuildWardData.py
```

Run from inside `Ottawa_Elections/` (reads `ward_results.csv` by relative path).

## Notes

Wards changed for the 2022 election (one ward added); historical results for
some wards have been estimated from their pre-2022 predecessors.

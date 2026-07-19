# Ontario Elections Visual

**Live:** [`ONelections.html`](ONelections.html) (embedded on the homepage as report *Ontario turnout and the 2025 result*)

Province-wide Ontario voter turnout since 1981, plus the February 2025 general
election broken down riding by riding, with a "what if the opposition had
consolidated" coalition scenario model.

## Layout

| Path | Purpose |
|---|---|
| `ONelections.html` | The visual page (map + charts, loads `data.js`/`geo.js`/`turnout.js`) |
| `build_data.py` | Turns the Elections Ontario `Explorer_*.csv` exports into `data.js` |
| `Explorer_*.csv` | Raw Elections Ontario "Explorer" export for the 2025 general election (results, districts, parties) |
| `*.json` (`Ontario.json`, `Ottawa.json`, `SouthernOntario.json`) | Riding boundary GeoJSON used for the map + zoom insets |
| `ELECTORAL_DISTRICT.shp.xml` | Metadata for the source shapefile the boundaries were simplified from |
| `Ontario_Election_Methodology.txt` | Notes on how the coalition/consolidation model works |

## Rebuilding the data

```bash
python Ontario_Elections/build_data.py
```

Reads the `Explorer_*.csv` files and regenerates `data.js`.

## Method

Riding-level vote counts and turnout come from Elections Ontario's public
Explorer export. A "true majority" counts only ridings where the winner
cleared 50%. The consolidation model reallocates Liberal/NDP/Green votes to
whichever of them led each riding, holding turnout fixed — a deliberate
simplification (see `Ontario_Election_Methodology.txt`).

# Road Safety / Vehicle Fleet Data

**Live:** [`road-safety.html`](road-safety.html) (embedded on the homepage as report *Vehicle–pedestrian impact*)

An interactive calculator: pick a vehicle and impact speed to see a
pedestrian's injury and fatality risk, alongside Ottawa's speed-camera
readings and the shift toward bigger, heavier vehicles.

## Layout

| Path | Purpose |
|---|---|
| `road-safety.html` | The calculator page (loads data from this folder, `DATA_FOLDER = '.'`) |
| `Pedestrian_Curves.csv` | IIHS injury/fatality-risk curves by vehicle front-end height and impact speed |
| `ase-speed-data.csv` / `.json` / `.geojson` | City of Ottawa Automated Speed Enforcement camera readings |
| `statcan_vehicle_registrations.csv` | Statistics Canada vehicle registration counts by type/year |
| `VehiclesStats.py` | Helper script for summarizing/checking the registration + ASE data |

## Method

Injury and fatality curves come from IIHS crash research (Monfort & Mueller,
2024–25), keyed to a vehicle's front-end height. The pedestrian fatal/major-injury
series is still the City's Road Safety Action Plan figures (they reach back to 2013 and include
2023), but the page now checks them against the open collision data on load. The photo-radar
ticket and red-light camera cards read `../Traffic/data/derived/stories.json`, built weekly by
`Traffic/scripts/build_stories.py`.

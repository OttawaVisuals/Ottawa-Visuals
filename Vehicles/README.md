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
2024–25), keyed to a vehicle's front-end height. Collision counts on the page
are currently hardcoded from City reports pending an open data feed.

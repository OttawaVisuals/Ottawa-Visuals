"""One-time, cached geocoding for PWHL player origin map data.

Run manually when the set of birthplace names changes. This uses one request
thread, waits at least one second between queries, and persists every result
so repeat runs only request new locations.
"""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECAP = ROOT / "data/json/pwhl_season_recap.json"
OUTPUT = ROOT / "data/json/pwhl_birthplace_coordinates.json"
UA = "OttawaVisuals-PWHLOrigins/1.0 (PWHL player birthplace map)"


def main():
    recap = json.loads(RECAP.read_text(encoding="utf-8"))
    result = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {
        "source": "OpenStreetMap Nominatim; town/city coordinates; ODbL",
        "locations": {},
    }
    names = sorted({place["name"] for season in recap["seasons"].values()
                    for place in season["birthplaces"]["places"]
                    if place.get("country") != "Unknown" and place.get("name") not in ("NA", "Unknown")})
    locations = result["locations"]
    missing = [name for name in names if not locations.get(name)]
    aliases = {
        "Massachussetts": "Massachusetts",
        "Chelyabinsk, RUS, Russia": "Chelyabinsk, Russia",
        "Göteberg, Sweden": "Gothenburg, Sweden",
        "Horni Cerekev, Czechia, Czechia": "Horní Cerekev, Czech Republic",
        "Saint-Odilon-de-Cranbourn, Québec, Canada": "Saint-Odilon-de-Cranbourne, Quebec, Canada",
        "St John's, Newfoundlan, Canada": "St. John's, Newfoundland and Labrador, Canada",
        "Strakonice, Czechia, Czechia": "Strakonice, Czech Republic",
        "Vlašim, CZE, Czechia": "Vlašim, Czech Republic",
        "Zlin, Czechia, Czechia": "Zlín, Czech Republic",
        "Örksköldsvik, Sweden": "Örnsköldsvik, Sweden",
    }
    print(f"{len(names)} unique locations; {len(missing)} need geocoding", flush=True)
    for i, name in enumerate(missing, 1):
        query = urllib.parse.urlencode({"q": aliases.get(name, name.replace("Massachussetts", "Massachusetts")),
                                        "format": "jsonv2", "limit": 1})
        request = urllib.request.Request(
            f"https://nominatim.openstreetmap.org/search?{query}",
            headers={"User-Agent": UA, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                matches = json.load(response)
            if matches:
                match = matches[0]
                locations[name] = {"lat": float(match["lat"]), "lon": float(match["lon"]),
                                   "label": match.get("name") or name}
            else:
                locations[name] = None
        except Exception as exc:
            print(f"Stopped at {i}/{len(missing)} ({name}): {exc}", flush=True)
            break
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        if i % 20 == 0 or i == len(missing):
            print(f"Geocoded {i}/{len(missing)} new places", flush=True)
        if i < len(missing):
            time.sleep(1.1)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Saved {len(locations)} cached locations to {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()

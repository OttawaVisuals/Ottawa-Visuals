import io
import requests
import pandas as pd
from zipfile import ZipFile

PRODUCT_ID = "20100025"  # pid without the last two digits
LANG = "en"

GEO_FILTER = ["Canada", "Ontario", "Ottawa"]

FUEL_FILTER = [
    "Gasoline",
    "Diesel",
    "All zero-emission vehicles",
    "Hybrid electric",
]

VEHICLE_FILTER = [
    "Passenger cars",
    "Pickup trucks",
    "Multi-purpose vehicles",
    "Vans",
]

def fetch_statcan_data():
    # Get zip URL
    api_url = f"https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/{PRODUCT_ID}/{LANG}"
    r = requests.get(api_url, timeout=30)
    r.raise_for_status()
    zip_url = r.json()["object"]

    # Download and extract
    resp = requests.get(zip_url, timeout=120)
    resp.raise_for_status()
    with ZipFile(io.BytesIO(resp.content)) as z:
        csv_name = next(n for n in z.namelist() if n.endswith(".csv") and "MetaData" not in n)
        df = pd.read_csv(z.open(csv_name), low_memory=False)

    # Filter
    filtered = df[
        df["GEO"].isin(GEO_FILTER) &
        df["Fuel type"].isin(FUEL_FILTER) &
        df["Vehicle type"].isin(VEHICLE_FILTER)
    ]

    filtered.to_csv("Vehicles/statcan_vehicle_registrations.csv", index=False)
    print(f"Saved {len(filtered)} rows ({filtered['REF_DATE'].nunique()} periods)")

if __name__ == "__main__":
    fetch_statcan_data()

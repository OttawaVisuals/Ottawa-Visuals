#!/usr/bin/env python3
"""Snapshot OC Transpo's official KPI spreadsheets from Open Ottawa.

The city publishes four small Excel files that are ROLLING WINDOWS (~13
months) — history silently drops off the back, so we archive a dated copy
whenever the content changes:

  * service_ridership_kpis   — monthly OTP, ridership, service delivery
  * bus_action_plan_kpis     — daily bus service delivery, undelivered trips
                                + reasons, fleet health, e-bus procurement
  * safety_indicators        — customer injury rate, preventable collisions
  * bus_schedule_adjustments — trips temporarily removed from schedules

Idempotent: downloads each file, hashes it, and only writes a new dated
snapshot when it differs from the latest one already stored. Safe to run
weekly (or even daily) from cron. Stdlib only, no API key.

Snapshots land in OC_Transpo/rt_data/kpi_snapshots/ (committed — the root
.gitignore has an exception for this folder's .xlsx files).
"""

import hashlib
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP_DIR = HERE.parent / "rt_data" / "kpi_snapshots"

# ArcGIS Hub item ids from open.ottawa.ca
ITEMS = {
    "service_ridership_kpis": "31d7a151c8394d1a8656ea3d08f00f46",
    "bus_action_plan_kpis": "cc65e563115a44939ad9855c0d8d1943",
    "safety_indicators": "69a9c427b4334d53864eb437ac677afa",
    "bus_schedule_adjustments": "8fc3fd0ac1a044f1abc96c5bec9ac975",
}
DATA_URL = "https://www.arcgis.com/sharing/rest/content/items/{item}/data"


def fetch(url: str, retries: int = 2) -> bytes:
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OttawaVisuals-transit/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
    raise last


def latest_snapshot(name: str):
    files = sorted(SNAP_DIR.glob(f"{name}_*.xlsx"))
    return files[-1] if files else None


def main():
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    saved, unchanged, failed = [], [], []

    for name, item in ITEMS.items():
        try:
            blob = fetch(DATA_URL.format(item=item))
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{name}: {exc}")
            continue
        if not blob.startswith(b"PK"):  # xlsx is a zip; anything else is an error page
            failed.append(f"{name}: response is not an xlsx ({blob[:60]!r})")
            continue

        prev = latest_snapshot(name)
        if prev and hashlib.sha256(prev.read_bytes()).digest() == hashlib.sha256(blob).digest():
            unchanged.append(name)
            continue

        out = SNAP_DIR / f"{name}_{today}.xlsx"
        out.write_bytes(blob)
        saved.append(f"{name} ({len(blob) // 1024} KB)")

    print(f"{today} kpi snapshots: "
          f"saved [{', '.join(saved) or '-'}] "
          f"unchanged [{', '.join(unchanged) or '-'}]"
          + (f" FAILED [{'; '.join(failed)}]" if failed else ""))
    return 1 if failed and not (saved or unchanged) else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Refresh every external dataset behind the RTO4 page.

Run from anywhere:  python RTO4/scripts/refresh_all.py [name ...]

With no arguments it refreshes all of them. Each fetcher is independent and a
failure is reported without aborting the rest — the City's ArcGIS layers get
renamed and retyped between vintages often enough that partial success is the
normal case, not an exception.

Refresh cadences that actually matter:
  * 311      — daily source. Weekly is plenty; this is the one series with a
               real 2025 baseline, so it is the most worth keeping current.
  * IESO     — the current-year CSV grows hourly. Weekly.
  * bikes    — coverage currently ends Mar 2026 (see fetch_bikes.py). Monthly
               is enough; re-run to find out when the City extends it.
  * ghg      — annual publication. Once a year.
  * context  — annual publication. Once a year, or when a 2025/2026 volume
               edition appears (that is what would finally let the City's own
               counts speak to RTO4).

The live feeds (TomTom, GTFS-RT, parking) are NOT here — those are polled
continuously on the Pi by Traffic/scripts/ and OC_Transpo/scripts/.
"""

import sys

import common
import fetch_311
import fetch_bikes
import fetch_context
import fetch_ghg
import fetch_ieso

FETCHERS = {
    "311": fetch_311.main,
    "ieso": fetch_ieso.main,
    "bikes": fetch_bikes.main,
    "ghg": fetch_ghg.main,
    "context": fetch_context.main,
}


def main(argv):
    names = argv or list(FETCHERS)
    unknown = [n for n in names if n not in FETCHERS]
    if unknown:
        print(f"unknown fetcher(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"available: {', '.join(FETCHERS)}", file=sys.stderr)
        return 2

    ok = [common.run(n, FETCHERS[n]) for n in names]
    failed = [n for n, good in zip(names, ok) if not good]
    print(f"\n{sum(ok)}/{len(ok)} refreshed" + (f" · failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

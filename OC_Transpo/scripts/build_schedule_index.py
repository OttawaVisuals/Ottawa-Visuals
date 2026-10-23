#!/usr/bin/env python3
"""Build a compact OC Transpo timetable index for on-time computation.

The GTFS-Realtime feed gives predicted arrival times but no delays, so
poll_gtfsrt.py works out each trip's delay as (predicted - scheduled). That
needs the scheduled time of every stop on every trip, which lives in the
static GTFS's stop_times.txt (~200 MB unzipped, ~4M rows) -- too slow to parse
on every 5-minute collector run. This script parses it once into a small
SQLite file that the poller queries for just the ~600 trips in each sample.

  trips(trip_id, route_id, headway_s, seqs, secs, tps)
    seqs / secs : stop_sequence and scheduled departure (seconds after the
                  service day's "noon minus 12h", GTFS convention; can exceed
                  24 h) as packed int32 arrays, in stop order.
    tps         : 1 where the stop is a timepoint (the "major stops" OC
                  Transpo measures punctuality at), packed int8. If a feed
                  leaves the timepoint column blank, every stop counts.
    headway_s   : scheduled gap to the previous trip on the same route,
                  direction and first stop, on the first date the trip runs
                  (gap to the next trip for the first trip of the day). OC
                  Transpo calls routes running every 15 min or better
                  "frequent" (measured by regularity) and the rest
                  "less-frequent" (measured by punctuality).
    feed        : feed_version the trip comes from.
  meta(key, value) : feed_version, feed_start_date, feed_end_date, etag, built_utc,
                     carried_from, carried_trips

A new feed starts on its first service date, but the evening before still
runs the old one, and its trip ids are different (seen 2026-10-22: feed
S1000524 starting Oct 23 was published at 21:30 on Oct 22, and ~85% of
running trips stopped matching). So when the index at --out is from an older
feed, its own trips (not ones it carried itself) are carried into the new
index unless the new feed reuses the trip id. One generation only, so the
index stays about twice the size of one feed at most.

collect.yml rebuilds it whenever the published zip's ETag changes and keeps it
in the Actions cache (it is not committed). Stdlib only.

    python OC_Transpo/scripts/build_schedule_index.py [--zip GTFSExport.zip] [--out PATH]
"""
import argparse
import csv
import io
import sqlite3
import sys
import tempfile
import urllib.request
import zipfile
from array import array
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "schedule_cache" / "schedule_index.sqlite"
GTFS_URL = "https://oct-gtfs-emasagcnfmcgeham.z01.azurefd.net/public-access/GTFSExport.zip"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def secs(hms: str) -> int:
    h, m, s = hms.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def rows(z: zipfile.ZipFile, name: str):
    with z.open(name) as fh:
        yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig"))


def active_services(cal, cal_dates, day: date) -> set:
    ds = day.strftime("%Y%m%d")
    out = {c["service_id"] for c in cal
           if c[WEEKDAYS[day.weekday()]] == "1" and c["start_date"] <= ds <= c["end_date"]}
    for x in cal_dates.get(ds, []):
        (out.add if x["exception_type"] == "1" else out.discard)(x["service_id"])
    return out


def previous_trips(path: Path, new_version: str):
    """(version, rows) of the older feed's trips to carry: an older index's own
    trips, or, when the same feed is rebuilt (zip republished), what it carried."""
    if not path.exists():
        return None, []
    db = None
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        meta = dict(db.execute("SELECT key, value FROM meta"))
        version = meta.get("feed_version", "")
        if version == new_version:
            version = meta.get("carried_from", "")
            if not version:
                return None, []
        cols = [c[1] for c in db.execute("PRAGMA table_info(trips)")]
        where = " WHERE feed = ?" if "feed" in cols else ""
        return version, db.execute("SELECT trip_id, route_id, headway_s, seqs, secs, tps FROM trips" + where,
                                   (version,) if where else ()).fetchall()
    except sqlite3.Error as exc:
        print(f"warning: previous index unreadable ({exc}); not carried over", file=sys.stderr)
        return None, []
    finally:
        if db:
            db.close()  # before the new index replaces this file


def build(zip_path: Path, out: Path, etag: str = ""):
    z = zipfile.ZipFile(zip_path)
    trips = {t["trip_id"]: t for t in rows(z, "trips.txt")}
    cal = list(rows(z, "calendar.txt")) if "calendar.txt" in z.namelist() else []
    cal_dates = defaultdict(list)
    if "calendar_dates.txt" in z.namelist():
        for x in rows(z, "calendar_dates.txt"):
            cal_dates[x["date"]].append(x)
    info = next(rows(z, "feed_info.txt"), {}) if "feed_info.txt" in z.namelist() else {}

    # stop_times: one pass, packed per trip. Rows are grouped by trip in this
    # feed, but don't rely on it -- accumulate in dicts of arrays.
    seqs, times, first_stop = defaultdict(lambda: array("i")), defaultdict(lambda: array("i")), {}
    tps = defaultdict(lambda: array("b"))
    with z.open("stop_times.txt") as fh:
        r = csv.reader(io.TextIOWrapper(fh, encoding="utf-8-sig"))
        head = next(r)
        i_trip, i_arr, i_dep = head.index("trip_id"), head.index("arrival_time"), head.index("departure_time")
        i_stop, i_seq = head.index("stop_id"), head.index("stop_sequence")
        i_tp = head.index("timepoint") if "timepoint" in head else None
        for row in r:
            t = row[i_trip]
            hms = row[i_dep] or row[i_arr]
            if not hms:
                continue  # untimed stop (allowed by GTFS); skip
            seqs[t].append(int(row[i_seq]))
            times[t].append(secs(hms))
            tps[t].append(0 if i_tp is not None and row[i_tp] == "0" else 1)
    for t in seqs:  # sort each trip by stop_sequence (normally already sorted)
        if any(a > b for a, b in zip(seqs[t], seqs[t][1:])):
            trip_rows = sorted(zip(seqs[t], times[t], tps[t]))
            seqs[t] = array("i", (p[0] for p in trip_rows))
            times[t] = array("i", (p[1] for p in trip_rows))
            tps[t] = array("b", (p[2] for p in trip_rows))
        first_stop[t] = times[t][0] if times[t] else None

    # Headways: for each date the feed covers, group that day's trips by
    # (route, direction, first stop) and take the gap to the previous trip.
    first_stop_id = {}
    with z.open("stop_times.txt") as fh:  # second, light pass for first stop ids
        r = csv.reader(io.TextIOWrapper(fh, encoding="utf-8-sig"))
        head = next(r)
        i_trip, i_stop, i_seq = head.index("trip_id"), head.index("stop_id"), head.index("stop_sequence")
        for row in r:
            t = row[i_trip]
            if seqs[t] and int(row[i_seq]) == seqs[t][0]:
                first_stop_id[t] = row[i_stop]
    headway = {}
    start = datetime.strptime(info.get("feed_start_date") or min(c["start_date"] for c in cal), "%Y%m%d").date()
    end = datetime.strptime(info.get("feed_end_date") or max(c["end_date"] for c in cal), "%Y%m%d").date()
    day = start
    while day <= end:
        act = active_services(cal, cal_dates, day)
        groups = defaultdict(list)
        for tid, t in trips.items():
            if t["service_id"] in act and tid not in headway and first_stop.get(tid) is not None:
                groups[(t["route_id"], t.get("direction_id", ""), first_stop_id.get(tid))].append((first_stop[tid], tid))
        for g in groups.values():
            g.sort()
            for i, (dep, tid) in enumerate(g):
                if len(g) == 1:
                    headway[tid] = None
                elif i == 0:
                    headway[tid] = g[1][0] - dep
                else:
                    headway[tid] = dep - g[i - 1][0]
        day += timedelta(days=1)

    version = info.get("feed_version", "")
    prev_version, prev_rows = previous_trips(out, version)
    carried = [r + (prev_version,) for r in prev_rows if r[0] not in seqs]

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript("""
        CREATE TABLE trips (trip_id TEXT PRIMARY KEY, route_id TEXT, headway_s INTEGER, seqs BLOB, secs BLOB, tps BLOB, feed TEXT);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    db.executemany("INSERT INTO trips VALUES (?,?,?,?,?,?,?)",
                   ((tid, trips[tid]["route_id"] if tid in trips else "", headway.get(tid),
                     seqs[tid].tobytes(), times[tid].tobytes(), tps[tid].tobytes(), version) for tid in seqs))
    db.executemany("INSERT INTO trips VALUES (?,?,?,?,?,?,?)", carried)
    meta = {"feed_version": version, "feed_start_date": info.get("feed_start_date", ""),
            "feed_end_date": info.get("feed_end_date", ""), "etag": etag,
            "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "carried_from": prev_version or "", "carried_trips": str(len(carried))}
    db.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out)
    freq = sum(1 for h in headway.values() if h is not None and h <= 900)
    print(f"schedule index: {len(seqs):,} trips ({freq:,} frequent), feed {meta['feed_version']} "
          f"{meta['feed_start_date']}..{meta['feed_end_date']}"
          + (f", plus {len(carried):,} carried from {prev_version}" if prev_version else "")
          + f", {out.stat().st_size / 1e6:.1f} MB -> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, help="use a local GTFSExport.zip instead of downloading")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--etag", default="", help="recorded in meta for traceability")
    args = ap.parse_args()
    if args.zip:
        build(args.zip, args.out, args.etag)
        return 0
    with tempfile.TemporaryDirectory() as td:
        zp = Path(td) / "GTFSExport.zip"
        req = urllib.request.Request(GTFS_URL, headers={"User-Agent": "OttawaVisuals-transit/1.0"})
        with urllib.request.urlopen(req, timeout=180) as resp, zp.open("wb") as fh:
            etag = resp.headers.get("ETag", "") or args.etag
            while chunk := resp.read(1 << 20):
                fh.write(chunk)
        build(zp, args.out, etag)
    return 0


if __name__ == "__main__":
    sys.exit(main())

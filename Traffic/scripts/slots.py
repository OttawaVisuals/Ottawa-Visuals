"""Fixed local-time sample slots for the low-quota TomTom pollers (poll_reach, poll_matrix).

The 5-min cron calls each poller every time, so the poller decides whether a slot is due:
the first run within CATCH_UP_MIN after a slot's start whose slot id is not yet in its log.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

WEEKDAY_HOURS = (8, 12, 17)   # morning peak, midday (off-peak reference), evening peak
WEEKEND_HOURS = (12,)
CATCH_UP_MIN = 25


def due_slot(now_local: datetime, log: Path, column: str = "slot"):
    """Slot id like '2026-10-26T08' if one is due and unlogged, else None."""
    hours = WEEKEND_HOURS if now_local.weekday() >= 5 else WEEKDAY_HOURS
    for h in hours:
        start = now_local.replace(hour=h, minute=0, second=0, microsecond=0)
        if timedelta(0) <= now_local - start < timedelta(minutes=CATCH_UP_MIN):
            slot = start.strftime("%Y-%m-%dT%H")
            return None if slot in logged_slots(log, column) else slot
    return None


def logged_slots(log: Path, column: str = "slot", tail_bytes: int = 200_000):
    """Slot ids in the last part of a CSV log (a day's worth is far smaller than this)."""
    try:
        with log.open("rb") as fh:
            header = fh.readline().decode("utf-8", "replace").strip().split(",")
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return set()
    if column not in header:
        return set()
    i = header.index(column)
    return {r[i] for r in csv.reader(lines) if len(r) > i}

#!/usr/bin/env python3
"""
Weekly update of the City Hall index: new meetings, minutes posted since the
last run, then a search-index rebuild. Meant for a scheduler (Windows Task
Scheduler or cron); everything goes to data/weekly_update.log.

    python weekly_update.py              # last year .. next year, 120-day refresh
    python weekly_update.py --days 365   # wider catch-up

Steps:
  1. escribe_indexer.py --years recent --refresh-days N
       new meetings get indexed; meetings indexed before their minutes were
       posted (or since replaced on the calendar) are re-indexed or dropped
  2. search.py --rebuild

The indexer's own lock (data/indexer.lock) stops this from running on top of
another indexer run, e.g. a long backfill; the week is then logged as skipped.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
LOG = DATA / "weekly_update.log"
LOCKED = 3  # escribe_indexer.py exit code when another run holds its lock


def python_exe() -> str:
    """Console python next to the running interpreter (pythonw has no stdout)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        console = exe.with_name("python.exe")
        if console.exists():
            return str(console)
    return str(exe)


def run(step: str, args: list[str], log) -> int:
    log.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S}  {step}\n")
    log.flush()
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    rc = subprocess.call([python_exe(), *args], cwd=HERE, stdout=log,
                         stderr=subprocess.STDOUT, env=env, creationflags=flags)
    log.write(f"=== exit {rc}\n")
    log.flush()
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=120,
                    help="re-check meetings from the last N days still lacking minutes")
    ap.add_argument("--delay", type=float, default=3.0, help="seconds between eScribe requests")
    ap.add_argument("--out", default=str(DATA), help="index folder (default: data/)")
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    out.mkdir(exist_ok=True)

    with open(out / LOG.name, "a", encoding="utf-8") as log:
        rc = run("index", ["escribe_indexer.py", "--years", "recent", "--out", str(out),
                           "--refresh-days", str(args.days), "--delay", str(args.delay)], log)
        if rc == 0:
            rc = run("search index", ["search.py", "--rebuild", "--data", str(out)], log)
        status = {0: "done", LOCKED: "skipped: another indexer run in progress"}.get(rc, "FAILED")
        log.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {status}\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the Ottawa traffic collector locally (e.g. on a laptop) for a day.

Loops every 15 minutes: runs poll_traffic.py (which self-gates cadence -- every
run during weekday peaks, hourly otherwise) and pushes any new readings to
GitHub. Just leave it running in a terminal; Ctrl+C to stop.

The TomTom key is read from the TOMTOM_API_KEY env var, or from an untracked
env file (default: %USERPROFILE%\\.ottawa_visuals.env or ~/.ottawa_visuals.env),
so it never lives in the repo.

Usage:
    python Traffic/scripts/run_local.py           # loop forever (15-min cycle)
    python Traffic/scripts/run_local.py --once     # one cycle then exit (test)
    python Traffic/scripts/run_local.py --interval 900   # custom seconds
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
POLLER = REPO / "Traffic" / "scripts" / "poll_traffic.py"


def load_key():
    if os.environ.get("TOMTOM_API_KEY"):
        return True
    home = Path(os.path.expanduser("~"))
    for env_path in (home / ".ottawa_visuals.env",):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            if os.environ.get("TOMTOM_API_KEY"):
                return True
    return False


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def poll():
    r = run([sys.executable, str(POLLER)])
    if r.stdout.strip():
        print("  " + r.stdout.strip())
    if r.returncode != 0:
        print("  poll error:", r.stderr.strip()[:300])
    return r.returncode == 0


def push():
    """Commit + push new readings if any. Non-fatal on failure (retries next cycle)."""
    run(["git", "add", "Traffic/data/"])
    staged = run(["git", "diff", "--cached", "--quiet"])
    if staged.returncode == 0:
        return  # nothing new
    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    run(["git", "commit", "-q", "-m", f"traffic: readings {stamp}"])
    pull = run(["git", "pull", "--rebase", "origin", "main", "-q"])
    if pull.returncode != 0:
        print("  pull --rebase failed (will retry next cycle):", pull.stderr.strip()[:200])
        return
    pr = run(["git", "push", "-q", "origin", "main"])
    if pr.returncode != 0:
        print("  push failed (will retry next cycle):", pr.stderr.strip()[:200])
    else:
        print("  pushed to GitHub")


def cycle():
    print(datetime.now().strftime("[%H:%M:%S] cycle"))
    if poll():
        push()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="run a single cycle and exit")
    ap.add_argument("--interval", type=int, default=900, help="seconds between cycles (default 900 = 15 min)")
    args = ap.parse_args()

    if not load_key():
        print("ERROR: TOMTOM_API_KEY not set and no ~/.ottawa_visuals.env found", file=sys.stderr)
        return 1

    if args.once:
        cycle()
        return 0

    print(f"Local collector running (every {args.interval}s). Leave this open; Ctrl+C to stop.")
    try:
        while True:
            cycle()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

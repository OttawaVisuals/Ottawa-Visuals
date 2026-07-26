#!/usr/bin/env bash
# Raspberry Pi poll wrapper. Runs poll_traffic.py, which self-gates cadence
# (weekday-peak every 15 min / hourly off-peak) and appends to Traffic/data/*.csv.
# Does NOT push — pi_push.sh batches commits so git history stays tidy.
#
# Crontab: */15 * * * *  /home/<user>/Ottawa-Visuals/Traffic/scripts/pi_poll.sh >> ~/traffic_poll.log 2>&1
set -euo pipefail

REPO="${OTTAWA_VISUALS_REPO:-$HOME/Ottawa-Visuals}"

# Load TOMTOM_API_KEY (and any other secrets) from an untracked env file.
if [ -f "$HOME/.ottawa_visuals.env" ]; then
  set -a; . "$HOME/.ottawa_visuals.env"; set +a
fi

cd "$REPO"
python3 Traffic/scripts/poll_traffic.py

# Municipal parking-garage occupancy (no API key). Self-gates its own cadence
# too. Kept non-fatal: a parking-feed outage must not stop traffic collection.
python3 Traffic/scripts/poll_parking.py || echo "poll_parking.py failed (non-fatal)"

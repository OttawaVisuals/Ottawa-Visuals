#!/usr/bin/env bash
# Raspberry Pi poll wrapper for the OC Transpo GTFS-RT collector.
# poll_gtfsrt.py self-gates cadence (weekday-peak 5 min / off-peak 15 min /
# overnight hourly) and appends to OC_Transpo/rt_data/*.csv.
# Does NOT push — pi_push_transit.sh batches commits.
#
# Crontab: */5 * * * *  /home/<user>/Ottawa-Visuals/OC_Transpo/scripts/pi_poll_transit.sh >> ~/transit_poll.log 2>&1
set -euo pipefail

REPO="${OTTAWA_VISUALS_REPO:-$HOME/Ottawa-Visuals}"

# Load OCTRANSPO_API_KEY (and optional OCTRANSPO_RAW_DIR) from the untracked env file.
if [ -f "$HOME/.ottawa_visuals.env" ]; then
  set -a; . "$HOME/.ottawa_visuals.env"; set +a
fi

cd "$REPO"
python3 OC_Transpo/scripts/poll_gtfsrt.py

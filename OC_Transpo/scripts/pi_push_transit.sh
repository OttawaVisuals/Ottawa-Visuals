#!/usr/bin/env bash
# Raspberry Pi push wrapper for the OC Transpo collector. Commits any new
# OC_Transpo/rt_data readings/snapshots and pushes. Runs hourly at :35 so it
# never collides with Traffic's pi_push.sh (which pushes at :05); both rebase
# before pushing anyway.
#
# Crontab: 35 * * * *  /home/<user>/Ottawa-Visuals/OC_Transpo/scripts/pi_push_transit.sh >> ~/transit_push.log 2>&1
# Plus the weekly KPI-spreadsheet snapshot (no key needed):
#          20 9 * * 1  cd /home/<user>/Ottawa-Visuals && python3 OC_Transpo/scripts/snapshot_kpis.py >> ~/transit_snapshot.log 2>&1
set -euo pipefail

REPO="${OTTAWA_VISUALS_REPO:-$HOME/Ottawa-Visuals}"
cd "$REPO"

git add OC_Transpo/rt_data/

# Nothing new? Exit quietly.
if git diff --cached --quiet; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') no new readings"
  exit 0
fi

git -c user.name="ottawa-visuals-pi" -c user.email="pi@ottawavisuals.local" \
    commit -q -m "transit: readings $(date -u +'%Y-%m-%d %H:%M UTC')"

# The Traffic pusher (and GitHub Actions pipelines) also push to main, so
# rebase on top of the remote first. Only OC_Transpo/rt_data is touched here,
# which nothing else writes, so conflicts aren't expected.
git pull --rebase origin main -q
git push -q origin main
echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') pushed"

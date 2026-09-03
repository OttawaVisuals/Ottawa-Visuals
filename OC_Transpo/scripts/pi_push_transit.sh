#!/usr/bin/env bash
# Raspberry Pi push wrapper for the OC Transpo collector. Commits any new
# OC_Transpo/rt_data readings/snapshots and pushes. Runs hourly at :35 so it
# never collides with Traffic's pi_push.sh (which pushes at :05); both rebase
# before pushing anyway.
#
# Crontab: 35 * * * *  /home/<user>/Ottawa-Visuals/OC_Transpo/scripts/pi_push_transit.sh >> ~/transit_push.log 2>&1
# Plus the weekly KPI-spreadsheet snapshot (no key needed):
#          20 9 * * 1  cd /home/<user>/Ottawa-Visuals && python3 OC_Transpo/scripts/snapshot_kpis.py >> ~/transit_snapshot.log 2>&1
#
# Optional dead-man's-switch: set HEALTHCHECK_URL_TRANSIT in
# ~/.ottawa_visuals.env to a healthchecks.io (or similar) check URL. Pinged
# on every successful run (even "nothing new") so a missed ping means the
# script itself stopped running (power/cron/Pi down), not just "no new data".
set -euo pipefail

REPO="${OTTAWA_VISUALS_REPO:-$HOME/Ottawa-Visuals}"
cd "$REPO"

ping_healthcheck() {
  # $1: /fail to report failure, empty for success. Never lets curl errors
  # break the collector itself.
  if [ -n "${HEALTHCHECK_URL_TRANSIT:-}" ]; then
    curl -fsS -m 10 --retry 3 "${HEALTHCHECK_URL_TRANSIT}${1:-}" -o /dev/null || true
  fi
}
trap 'ping_healthcheck /fail' ERR

# Refresh the daily rollup from the raw CSVs before committing.
python3 OC_Transpo/scripts/build_history_transit.py || echo "build_history_transit failed (non-fatal)"

git add OC_Transpo/rt_data/

# Nothing new? Exit quietly.
if git diff --cached --quiet; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') no new readings"
  ping_healthcheck
  exit 0
fi

git -c user.name="ottawa-visuals-pi" -c user.email="pi@ottawavisuals.local" \
    commit -q -m "transit: readings $(date -u +'%Y-%m-%d %H:%M UTC')"

# The Traffic pusher (and GitHub Actions pipelines) also push to main, so
# rebase on top of the remote first. Only OC_Transpo/rt_data is touched here,
# which nothing else writes, so conflicts aren't expected. autoStash because
# the other collector's un-pushed readings (Traffic/data) sit unstaged in the
# working tree and would otherwise abort the rebase.
git -c rebase.autoStash=true pull --rebase origin main -q
git push -q origin main
echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') pushed"
ping_healthcheck

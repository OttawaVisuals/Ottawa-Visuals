#!/usr/bin/env bash
# Raspberry Pi push wrapper. Commits any new Traffic/data readings and pushes.
# Run less often than the poller so commits batch (e.g. hourly) instead of one
# commit per 15-min sample.
#
# Crontab: 5 * * * *  /home/<user>/Ottawa-Visuals/Traffic/scripts/pi_push.sh >> ~/traffic_push.log 2>&1
set -euo pipefail

REPO="${OTTAWA_VISUALS_REPO:-$HOME/Ottawa-Visuals}"
cd "$REPO"

git add Traffic/data/

# Nothing new? Exit quietly.
if git diff --cached --quiet; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') no new readings"
  exit 0
fi

git -c user.name="ottawa-visuals-pi" -c user.email="pi@ottawavisuals.local" \
    commit -q -m "traffic: readings $(date -u +'%Y-%m-%d %H:%M UTC')"

# Other pipelines (PWHL, mortgage, ...) may still push from GitHub Actions, so
# rebase our commit on top of the remote before pushing. Only Traffic/data is
# touched here, which nothing else writes, so conflicts aren't expected.
git pull --rebase origin main -q
git push -q origin main
echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') pushed"

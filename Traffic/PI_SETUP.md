# Running the traffic collector on a Raspberry Pi

GitHub Actions throttles this account's scheduled runs by 3–4 hours, so a
15-minute `schedule:` cron never fires. The Pi runs the poller on a real cron
(exact timing, zero Actions minutes) and pushes the CSVs to GitHub.

`poll_traffic.py` is stdlib-only and self-gates cadence, so **no code changes are
needed** — just set up the Pi to run it and push.

---

## 1. Prerequisites on the Pi

Raspberry Pi OS (or any Debian/Linux). Check Python is 3.9+ (needs `zoneinfo`):

```bash
python3 --version          # expect 3.9 or newer
git --version
```

Nothing to `pip install` — the poller uses only the standard library.

## 2. Give the Pi push access (SSH deploy key — cleanest for a headless box)

```bash
ssh-keygen -t ed25519 -C "ottawa-visuals-pi" -f ~/.ssh/ottawa_visuals -N ""
cat ~/.ssh/ottawa_visuals.pub
```

Copy that public key → GitHub repo **Settings → Deploy keys → Add deploy key**,
tick **Allow write access**. Then tell SSH to use it for this host:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-ottawavisuals
  HostName github.com
  User git
  IdentityFile ~/.ssh/ottawa_visuals
  IdentitiesOnly yes
EOF
```

## 3. Clone the repo (via the deploy-key host alias)

```bash
cd ~
git clone github-ottawavisuals:OttawaVisuals/Ottawa-Visuals.git
# -> ~/Ottawa-Visuals  (the scripts default to this path)
```

## 4. Store the API key (untracked, chmod 600)

```bash
printf 'TOMTOM_API_KEY=%s\n' 'YOUR_KEY_HERE' > ~/.ottawa_visuals.env
chmod 600 ~/.ottawa_visuals.env
```

The wrappers source this file, so the key stays off disk-in-repo and out of git.

## 5. Make the wrappers executable & smoke-test

```bash
chmod +x ~/Ottawa-Visuals/Traffic/scripts/pi_poll.sh \
         ~/Ottawa-Visuals/Traffic/scripts/pi_push.sh

~/Ottawa-Visuals/Traffic/scripts/pi_poll.sh   # should print a "[PEAK]/[hourly] wrote ..." line or a skip
~/Ottawa-Visuals/Traffic/scripts/pi_push.sh   # should commit + push if the poll wrote rows
```

## 6. Schedule with cron

`crontab -e`, then add:

```cron
# Poll every 15 min (script self-gates: peak = every run, off-peak = top of hour)
*/15 * * * * /home/pi/Ottawa-Visuals/Traffic/scripts/pi_poll.sh >> /home/pi/traffic_poll.log 2>&1
# Push accumulated readings hourly (batches commits so history stays tidy)
5   * * * * /home/pi/Ottawa-Visuals/Traffic/scripts/pi_push.sh >> /home/pi/traffic_push.log 2>&1
```

Replace `/home/pi` if your username differs. If cron can't find `python3`, use the
full path (`which python3`) in `pi_poll.sh` or set `PATH=` at the top of the crontab.

---

## Notes

- **Timezone:** the poller computes Ottawa local time via `zoneinfo` regardless of
  the Pi's own clock zone, so the peak/hourly gate is correct even if the Pi is on UTC.
- **Reliability:** if the Pi is off during a window, those samples are simply missed
  (same as any gap) — no catch-up. Keep it powered for continuous coverage, especially
  through **August 2026** for the Aug-2024-vs-Aug-2026 comparison.
- **Logs:** `~/traffic_poll.log` / `~/traffic_push.log`. Rotate or truncate occasionally.
- **The GitHub Actions `schedule` is disabled** (see `traffic.yml`) so the two don't
  double-collect; `workflow_dispatch` stays for the occasional manual test run.
- **Generalizing:** the same pattern (clone once, secrets in `~/.ottawa_visuals.env`,
  cron wrapper, hourly push) can host your other pipelines (PWHL, mortgage, StatCan)
  on the Pi later — start with this one, then replicate.

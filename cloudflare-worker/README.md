# Cloudflare cron → GitHub Actions collector

Replaces the Raspberry Pi. A free Cloudflare Worker fires
[`collect.yml`](../.github/workflows/collect.yml) every 5 minutes through the
`workflow_dispatch` API (GitHub's own `schedule:` is throttled on this account).
The pollers self-gate their cadence, so most runs do nothing.

## One-time setup

1. **GitHub token** — github.com → Settings → Developer settings → Fine-grained
   tokens → new. Repository access: *only* `Ottawa-Visuals`. Permission:
   *Actions: Read and write* (nothing else). Set a long expiry and note the date.
2. **Repo secrets** (Settings → Secrets → Actions): `TOMTOM_API_KEY` already
   exists. Add `OCTRANSPO_API_KEY` (same value as in the Pi's
   `~/.ottawa_visuals.env`). Optional: `ONTARIO_511_KEY`.
3. **Deploy the Worker** (free Cloudflare account):
   ```bash
   cd cloudflare-worker
   npx wrangler login
   npx wrangler deploy
   npx wrangler secret put GITHUB_TOKEN   # paste the token from step 1
   ```
4. **Test**: Actions tab → *Collect Ottawa Data* → Run workflow. Then confirm
   the Worker's cron shows runs in the Cloudflare dashboard.
5. **Turn the Pi crons off** (`crontab -e`, comment out the four collector
   lines) so two writers don't diverge the CSVs.

## Notes

- Readings are spooled between runs in the Actions cache and committed at most
  hourly per collector (`traffic: readings …` / `transit: readings …`, so the
  heartbeat workflow keeps working). Worst case if the cache is evicted: lose
  up to ~1 h of readings.
- Public repo ⇒ Actions minutes are free.
- The fine-grained token expires — when it does, the Worker's logs show 401s
  and the heartbeat issue opens ~24 h later.

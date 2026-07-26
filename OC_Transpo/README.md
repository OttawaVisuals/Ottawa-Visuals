# OC Transpo data collection

Two independent pipelines live here:

1. **eScribe KPI scraper** (below) — one-off/occasional harvest of ridership &
   KPI PDFs from Transit Committee meetings (deep history, 2019+).
2. **GTFS-RT collector + KPI snapshotter** (`scripts/`) — continuous logging on
   the Raspberry Pi, building our own service-reliability dataset for the RTO4
   page. See [RTO4_PLAN.md](../RTO4_PLAN.md) for how it all fits together.

## GTFS-RT collector (Raspberry Pi)

OC Transpo keeps no public history of on-time performance; `scripts/poll_gtfsrt.py`
logs it ourselves from the official GTFS-Realtime feeds (TripUpdates +
VehiclePositions, JSON). Per sample it appends summary rows (cancellations,
active vehicles, speed stats, delay stats when available — split
all/bus/otrain/unknown) to `rt_data/*.csv`, which are committed. Cadence is
self-gated: weekday peaks every 5 min, off-peak every 15 min, 01:00–05:00 hourly.

**Feed reality (verified live 2026-07-11):** the beta feed sets *no* delay
fields — TripUpdates carry absolute predicted arrival times per stop instead.
So the live CSV metrics are **cancellations** (~5% of trips the day we checked)
and fleet activity; true on-time performance gets computed offline from the
raw archive (predicted arrival times vs the static GTFS schedule). That makes
the raw archive (`OCTRANSPO_RAW_DIR`) effectively required, not optional:
~15 MB/day gzipped, ~5.5 GB/year. The JSON is protobuf-net style with
`Has<Field>` companion flags (`"Delay": 0, "HasDelay": false` = unset) — the
parser respects them. Also: the feed is **bus-only** (no route 1/2/4 entities
observed) — O-Train reliability comes from the official KPI spreadsheets
below, not from GTFS-RT. The otrain group in the CSVs is kept in case trains
appear later.

`scripts/snapshot_kpis.py` archives the city's four official KPI spreadsheets
from Open Ottawa (service & ridership KPIs, bus action-plan KPIs, safety
indicators, schedule adjustments) into `rt_data/kpi_snapshots/`. Those files
are **rolling ~13-month windows** — snapshot or lose the history. It hashes
content and only saves dated copies when something changed, so it's safe to
cron weekly.

### Setup
1. Register for a free key at https://nextrip-public-api.developer.azure-api.net/
   (subscribe to the GTFS-RT product; the key goes in the
   `Ocp-Apim-Subscription-Key` header — the script handles that).
2. On the Pi, add to `~/.ottawa_visuals.env` (untracked, same file the Traffic
   collector uses):
   ```
   OCTRANSPO_API_KEY=...
   # raw JSON archive (gzipped), needed for offline OTP — keep OUTSIDE the
   # repo; ~15 MB/day:
   OCTRANSPO_RAW_DIR=/home/<user>/gtfsrt_raw
   ```
3. First run, verify parsing against the live feed:
   ```bash
   python3 OC_Transpo/scripts/poll_gtfsrt.py --force --debug
   ```
4. Crontab (alongside the existing Traffic entries):
   ```cron
   */5 * * * *  /home/<user>/Ottawa-Visuals/OC_Transpo/scripts/pi_poll_transit.sh >> ~/transit_poll.log 2>&1
   35 * * * *   /home/<user>/Ottawa-Visuals/OC_Transpo/scripts/pi_push_transit.sh >> ~/transit_push.log 2>&1
   20 9 * * 1   cd /home/<user>/Ottawa-Visuals && python3 OC_Transpo/scripts/snapshot_kpis.py >> ~/transit_snapshot.log 2>&1
   25 4 * * 2   mkdir -p ~/gtfsrt_raw/static && curl -sL "https://oct-gtfs-emasagcnfmcgeham.z01.azurefd.net/public-access/GTFSExport.zip" -o ~/gtfsrt_raw/static/GTFSExport_$(date +\%F).zip >> ~/transit_snapshot.log 2>&1
   ```

   > **Reading the KPI snapshot log.** `snapshot_kpis.py` writes a dated `.xlsx`
   > *only when the downloaded content differs* from the last snapshot. A run that
   > logs `saved [-] unchanged [...]` and produces no new file is working
   > correctly — the city republishes these roughly monthly, so most weekly runs
   > legitimately save nothing. **Do not diagnose this job by looking for new files
   > in `kpi_snapshots/`; read `~/transit_snapshot.log` instead.** Verified
   > 2026-07-26: the cron fired on Jul 13 and Jul 20 and correctly saved nothing
   > both times.
   The last line snapshots the static GTFS schedule weekly — needed to turn the
   raw predicted arrival times into on-time performance (the
   [Mobility Database](https://mobilitydatabase.org) also archives it as backup;
   feed id `...oc-transpo-gtfs-2154`).

On-time definition used wherever delays are computed (mirrors OC Transpo's
punctuality definition for less-frequent routes): early = >1 min early,
on-time = 1 min early…5 min late, late = >5 min late.

---

# eScribe Ridership & KPI scraper

Collects ridership / service-KPI reports from Ottawa's **Transit Committee**
(and the older **Transit Commission**) meetings on the city's eScribe portal,
downloading the relevant PDF attachments and optionally extracting their tables.

Built to run unattended on a Raspberry Pi: rate-limited, resumable, logged.

## Why a scraper
OC Transpo's own site only offers patchy KPI data (recent dashboard + a
2019–2022 download). The fuller history lives in the PDF attachments of Transit
Committee agendas on eScribe. This tool walks those agendas and grabs the right
PDFs for you.

## Install
```bash
python3 -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt
# for --extract (PDF text/tables): pip install pdfplumber
```
On a Raspberry Pi these install cleanly from piwheels (all pure-Python /
wheels available for ARM).

## Quick start (auto-discovery — no seed file needed)
```bash
# Preview every Transit meeting 2019-2026 and what would download:
python3 oc_transpo_kpi_scraper.py --years 2019-2026 --dry-run

# Real run — download the KPI/ridership PDFs:
python3 oc_transpo_kpi_scraper.py --years 2019-2026

# Also parse each PDF into text + table CSVs (needs pdfplumber):
python3 oc_transpo_kpi_scraper.py --years 2019-2026 --extract
```
`--years` enumerates meetings straight from eScribe's calendar API and keeps the
ones whose name contains the `--committee` substring (default `transit`, which
covers both "Transit Committee" and the older "Transit Commission").

### Optional: a hand-picked seed list instead of / in addition to --years
```bash
cp meetings.sample.txt meetings.txt    # paste specific meeting links/GUIDs
python3 oc_transpo_kpi_scraper.py --seed meetings.txt
```

## Running overnight on Windows
```powershell
# (optional) install the PDF parser for --extract:
pip install pdfplumber

# stop the PC sleeping while it runs, then start the job logging to a file:
powercfg /change standby-timeout-ac 0
python oc_transpo_kpi_scraper.py --years 2019-2026 --extract --delay 4 *> data\run.log
```
Leave the terminal open. It checkpoints after every meeting/file
(`data\state.json`), so if it stops you can re-run the same command and it
resumes, skipping finished work. (`*>` redirects both stdout and stderr in
PowerShell; in cmd.exe use `> data\run.log 2>&1`.)

## Running overnight on the Pi
```bash
# detached, survives logout, logs to the output dir:
nohup python3 oc_transpo_kpi_scraper.py --seed meetings.txt --extract \
      --delay 4 > data/run.out 2>&1 &
```
It checkpoints after every meeting/file (`data/state.json`), so if it's
interrupted just run the same command again — it resumes and skips finished work.

For a recurring refresh, add a cron entry (e.g. weekly, Sunday 02:00):
```cron
0 2 * * 0  cd /home/pi/oc_transpo && /usr/bin/python3 oc_transpo_kpi_scraper.py --seed meetings.txt >> data/cron.log 2>&1
```

## Options
| Flag | Meaning |
|------|---------|
| `--seed FILE` | Meeting URLs/GUIDs to process (use instead of, or with, --years). |
| `--years 2019-2026` | Auto-discover meetings from eScribe's calendar API for those years. |
| `--committee transit` | Name substring to keep during --years discovery (default: transit). |
| `--all` | Download every attachment, not just KPI/ridership matches. |
| `--extract` | Pull text + tables out of each PDF (needs pdfplumber; heavier CPU). |
| `--delay 4` | Seconds between requests (be polite; default 3). |
| `--limit N` | Process at most N meetings (handy for testing). |
| `--dry-run` | Show what would happen; download nothing. |
| `--no-resume` | Ignore saved state and reprocess everything. |
| `-v` | Verbose/debug logging. |

## Output
```
data/
  manifest.csv                      # every attachment found: date, name, item, file, url, path
  scraper.log                       # full run log
  state.json                        # resume checkpoint
  2025-06-12_Transit Committee/     # one folder per meeting
      OC Transpo Update Presentation (EN).pdf
      ...
```
`manifest.csv` is the index to load into your analysis / Power BI.

## What counts as "relevant"
By default an attachment is kept if its filename or agenda-item title contains
any KPI/ridership keyword (ridership, KPI, performance, statistics, "OC Transpo
update", reliability, on-time, boarding, O-Train, Para Transpo, quarterly,
annual report, …). Edit the `KEYWORDS` list at the top of the script to tune it,
or use `--all` to grab everything and filter later.

## Notes & etiquette
- This hits a **public-records** site. The portal blocks default bots by
  User-Agent; the script uses a normal browser UA. `robots.txt` only disallows
  `PetalBot`, so polite crawling is fine — keep `--delay` ≥ 3s and don't run
  parallel copies. The resume logic avoids re-downloading.
- GIS/heavy libraries are not used, so this is light on the Pi (network/IO
  bound). `--extract` is the only CPU-notable step.

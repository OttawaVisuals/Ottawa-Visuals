# OC Transpo Ridership & KPI scraper

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

## Quick start
```bash
# 1) Seed the meeting list (one-time, ~10 min in your browser).
cp meetings.sample.txt meetings.txt
#    then paste the Transit meeting links/GUIDs into meetings.txt
#    (instructions are inside the file).

# 2) Preview what would be downloaded (no files written):
python3 oc_transpo_kpi_scraper.py --seed meetings.txt --dry-run

# 3) Real run — download KPI/ridership PDFs:
python3 oc_transpo_kpi_scraper.py --seed meetings.txt

# 4) Also parse the PDFs into text + table CSVs:
python3 oc_transpo_kpi_scraper.py --seed meetings.txt --extract
```

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
| `--seed FILE` | Meeting URLs/GUIDs to process (the reliable source). |
| `--years 2019-2026` | Also try the eScribe list API for those years (best effort — see note). |
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
- **API discovery (`--years`) is best-effort.** The portal's meeting list is
  rendered by JavaScript with filter state the script can't always reproduce, so
  it may return nothing. The `--seed` file is the dependable path; `--years` is a
  bonus that may need a tweak to the query string in `discover_via_api()`.
- GIS/heavy libraries are not used, so this is light on the Pi (network/IO
  bound). `--extract` is the only CPU-notable step.

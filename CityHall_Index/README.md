# Ottawa City Hall — eScribe Universal Indexer (Stage 1)

Builds a structured, queryable **CSV index of what every City of Ottawa
committee / council / commission discussed and decided**, straight from the
public eScribe portal. This is the *metadata + decisions* layer — not the
contents of the PDFs (that's Stage 2, per-topic extraction).

## Output — five joinable CSVs
Join on `meeting_id` (and `item_number` where present).

| File | One row per | Key columns |
|------|-------------|-------------|
| `meetings.csv` | meeting | committee, date, meeting_id, source_page, n_items, url |
| `agenda_items.csv` | agenda item | item_number, title, category, **report_number** (ACS…), **disposition**, n_motions, n_attachments, has_vote |
| `motions.csv` | motion | item_number, motion_index, **result** (Carried/Lost/…), motion_text |
| `votes.csv` | recorded vote tally | item_number, motion_index, **vote** (For/Against), **count**, **voters** (names) |
| `attachments.csv` | PDF attachment | item_number, filename, document_id, url |

This turns years of meetings into a database you can query: what was discussed,
what passed/failed, which report numbers, which PDFs, and — where councils held
recorded votes — the tallies and who voted.

## Install & run
```bash
pip install -r requirements.txt

# quick test — one committee, a few meetings:
python escribe_indexer.py --years 2025 --committee transit --limit 5 -v

# a single committee, several years:
python escribe_indexer.py --years 2020-2026 --committee "planning"

# EVERYTHING — all committees (the full index; an overnight job, ~300 mtgs/yr):
python escribe_indexer.py --years 2020-2026
```

### Windows overnight (single line)
```powershell
mkdir data -Force; python escribe_indexer.py --years 2020-2026 --delay 4 | Tee-Object data\run.log
```
Resumable: it checkpoints each meeting in `data\state.json`, so re-running the
same command continues where it stopped.

## Options
| Flag | Meaning |
|------|---------|
| `--years 2020-2026` | Year or range to index (required). |
| `--committee "text"` | Only meetings whose name contains this (default: **all** committees). |
| `--out DIR` | Output directory (default: `data`). |
| `--delay 4` | Seconds between requests (be polite; default 3). |
| `--limit N` | Cap number of meetings (testing). |
| `--no-resume` | Ignore saved state, reprocess all. |
| `-v` | Verbose logging. |

## How it works
- Meetings are enumerated from eScribe's calendar API (`GetCalendarMeetings`).
- For each meeting it fetches the richest page available (`PostMinutes` →
  `Minutes` → `Agenda`) and parses the agenda-item structure: item numbers,
  titles, categories, ACS report numbers, motions + results, recorded votes,
  and PDF attachments.
- Nested items (e.g. 6 → 6.1) are handled so parents don't double-count their
  children's motions/votes/attachments.
- Browser User-Agent + OS-native trust store (`truststore`), rate-limited with
  retry/backoff, resumable, logs to `data/indexer.log`.

## Notes & limits
- Calendar API reaches back to ~2019; older meetings likely live in a separate
  archive not covered here.
- `voters` is captured as the name string per tally. Exploding it to one row
  per councillor (for a clean voting-record dataset) is a small Stage-1.1
  refinement once the pairing is validated across many committees.
- Public-records site; keep `--delay` ≥ 3s and don't run parallel copies.

## What this powers (your project ideas)
- **City finances / budget** → filter `report_number` like `ACS*-FCS-*` + budget items; `disposition` + `votes` show what passed and who backed it.
- **Program cancelled / service cuts** → search `agenda_items.title` + `disposition` over time.
- **RTO / road maintenance** → Transportation & Public Works committee items.
- **Councillor voting record** → `votes.csv` (a ready-made "how did my councillor vote" dataset).
- **OC Transpo KPIs** → `attachments.csv` filtered to transit is the input to the Stage-2 KPI extractor in `../OC_Transpo/`.

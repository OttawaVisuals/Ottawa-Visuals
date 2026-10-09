# Ottawa City Hall — eScribe Universal Indexer (Stage 1)

Builds a structured, queryable **CSV index of what every City of Ottawa
committee / council / commission discussed and decided**, straight from the
public eScribe portal. This is the *metadata + decisions* layer — not the
contents of the PDFs (that's Stage 2, per-topic extraction).

## Output — six joinable CSVs
Join on `meeting_id` (and `item_number` where present).

| File | One row per | Key columns |
|------|-------------|-------------|
| `meetings.csv` | meeting | committee, date, meeting_id, source_page, n_items, url |
| `agenda_items.csv` | agenda item | item_number, title, category, **report_number** (ACS…), **disposition**, n_motions, n_attachments, has_vote |
| `motions.csv` | motion | item_number, motion_index, **result** (Carried/Lost/…), motion_text |
| `votes.csv` | recorded vote tally | item_number, motion_index, **vote** (For/Against), **count**, **voters** (names) |
| `attachments.csv` | PDF attachment | item_number, filename, document_id, url |
| `item_text.csv` | agenda item | item_number, source_page, n_chars, **text**: everything the meeting page shows for the item (report summary, recommendations incl. amendments, motions, moved/seconded, directions to staff, minutes notes), one line per paragraph |

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

## Search
```bash
python search.py "watermain break"
python search.py "asset management plan" --from 2024 --committee council
python search.py '"funding gap" water' --sort date --limit 50
python search.py "OCC 2024-13" --full          # whole text of each hit
python search.py "watermain" --csv hits.csv    # every hit to a spreadsheet
```
Builds `data/search.db` (SQLite full-text index, gitignored) from the CSVs, and
rebuilds it automatically whenever a CSV is newer. One document per agenda item:
title, report number, page text, motions and attachment filenames. Titles and
report numbers rank highest. Words are stemmed (break/breaks match). Syntax:
`"exact phrase"`, `OR`, `NOT`, `NEAR(a b, 10)`, `prefix*`. Each hit prints the date,
committee, item, decision, a highlighted snippet, the meeting link and up to 3 PDF
links (`--pdfs N`).

Coverage: from about mid-2022, agenda items are broken out one by one. Meetings
before that (Word-exported pages, no item structure) are searchable as one
"Full meeting text" document per meeting.

## PDFs (Stage 2: browser download, then ingest)
The numbers usually live in the PDF reports, and scripts can't fetch those
(eScribe's browser check). So you download them in a browser and the tools take it from there:

```bash
python search.py "watermain" --pdf-list watermain.html   # 1. page of every hit's PDF links
#   2. open watermain.html, click each link, save into CityHall_Index/pdfs/ (or Downloads)
python ingest_pdfs.py --dir ~/Downloads                    # 3. copy + read + match (omit --dir if saved to pdfs/)
python search.py "watermain breaks" --in pdfs              # 4. search inside them
```
- `--pdf-list` skips French copies (`--french` keeps them), greys out PDFs already
  ingested, and records the requested DocumentIds in `data/pdf_wanted.json`.
- `ingest_pdfs.py` matches each file to its meeting/item through `attachments.csv`:
  DocumentId in the filename → unique filename → shared names narrowed by
  `pdf_wanted.json` and by report numbers inside the PDF → report number alone.
  Unmatched files are still searchable; renaming one to `<DocumentId> - name.pdf` links it.
- Text is read page by page (pypdf) and cached by file hash in `data/pdf_pages.csv`;
  `data/pdf_files.csv` lists every PDF with its match, page count and flags.
  Scanned PDFs (no text layer) are flagged `needs_ocr`. A browser re-download
  ("name (1).pdf") of the same document is flagged `duplicate_of` and skipped in search.
- In search, each PDF page is one document: the hit links to `…DocumentId=N#page=P`
  and prints the local file path.

## Weekly update
```bash
python weekly_update.py            # what the scheduler runs
```
Runs `escribe_indexer.py --years recent --refresh-days 120` (last year through next
year), then `search.py --rebuild`; output goes to `data/weekly_update.log`.
Scheduled on the desktop PC as the Windows task **OttawaVisuals CityHall weekly**
(Sundays 09:00 via `pythonw.exe`, runs at next start if the PC was off; it runs only
while you're signed in). Check it with `Get-ScheduledTaskInfo "OttawaVisuals CityHall weekly"`.
- New meetings are indexed as usual.
- Meetings from the last 120 days (or upcoming) that were indexed before their
  minutes were posted (Agenda page, or no items) are removed from every CSV and
  indexed again, so their decisions and votes fill in.
- eScribe replaces placeholder meetings with new meeting IDs and drops cancelled
  ones. Stale meetings no longer on the calendar are removed, but only for years
  the calendar actually returned and the committee filter in use.
- `data/indexer.lock` keeps two indexer runs off the same folder (exit code 3,
  logged as "skipped"). A lock older than 24 h counts as left over from a crash.

## Options
| Flag | Meaning |
|------|---------|
| `--years 2020-2026` | Year or range to index (required); `recent` = last year to next year. |
| `--committee "text"` | Only meetings whose name contains this (default: **all** committees). |
| `--out DIR` | Output directory (default: `data`). |
| `--delay 4` | Seconds between requests (be polite; default 3). |
| `--limit N` | Cap number of meetings (testing). |
| `--no-resume` | Ignore saved state, reprocess all. |
| `--refresh-days N` | Re-index meetings from the last N days still lacking minutes (see Weekly update). |
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
- **item_text backfill.** `item_text.csv` has its own resume file (`state_text.json`).
  Re-running the usual command over meetings indexed before it existed fetches each
  page once more and writes only `item_text` rows (logged as `(text backfill)`).
- **PDF contents are not reachable by script.** Since Oct 2026 `filestream.ashx` PDF
  links answer scripts with a "Verifying your browser" check (meeting pages and the
  calendar API are unaffected). Don't try to get around it: download the PDFs you need
  in a browser, or ask the City Clerk for bulk access.
- **Agenda-only rows go stale.** A meeting indexed before its minutes were published
  keeps its Agenda-page items/motions (no dispositions or votes); state marks it done.
  `item_text` for it comes from whatever page is current at backfill time.
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

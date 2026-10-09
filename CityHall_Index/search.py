#!/usr/bin/env python3
"""
Full-text search over the eScribe index (Stage 1.5).

Builds data/search.db (SQLite FTS5) from the indexer's CSVs, one document per
agenda item: title, report number, the item's full page text (item_text.csv),
its motions and its attachment filenames. Rebuilds automatically when any CSV
is newer than the database.

Usage
-----
  python search.py "watermain break"
  python search.py "asset management plan" --from 2024 --committee council
  python search.py '"funding gap" water' --sort date --limit 50
  python search.py "OCC 2024-13" --full          # print each hit's whole text
  python search.py "watermain" --csv hits.csv    # all hits to a spreadsheet

Query syntax is SQLite FTS5: words are ANDed, "exact phrase", OR, NOT,
NEAR(a b, 10), prefix*. Words are stemmed (break/breaks/breaking match).
If a query isn't valid FTS5 (e.g. "2024-13"), each word is quoted instead.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"      # --data overrides
DB = DATA / "search.db"
SOURCES = ["meetings", "agenda_items", "item_text", "motions", "attachments"]
# bm25 weights, in FTS column order: title, report, text, motions, attachments
WEIGHTS = (8.0, 6.0, 1.0, 1.5, 3.0)

csv.field_size_limit(2**31 - 1)


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def _rows(name):
    path = DATA / f"{name}.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _keyed(rows):
    """(meeting_id, item_number) -> rows in file order. Item numbers can repeat
    within a meeting, so callers match by occurrence."""
    out = defaultdict(list)
    for r in rows:
        out[(r["meeting_id"], r["item_number"])].append(r)
    return out


def needs_rebuild() -> bool:
    if not DB.exists():
        return True
    built = DB.stat().st_mtime
    return any((DATA / f"{n}.csv").exists() and (DATA / f"{n}.csv").stat().st_mtime > built
               for n in SOURCES)


def build():
    meetings = {r["meeting_id"]: r for r in _rows("meetings")}
    texts = _keyed(_rows("item_text"))
    motions = defaultdict(list)
    for r in _rows("motions"):
        motions[(r["meeting_id"], r["item_number"])].append(r)
    attach = defaultdict(list)
    for r in _rows("attachments"):
        attach[(r["meeting_id"], r["item_number"])].append(r)

    tmp = DB.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript("""
        CREATE TABLE items(
            id INTEGER PRIMARY KEY, meeting_id TEXT, date TEXT, committee TEXT,
            item_number TEXT, title TEXT, report_number TEXT, disposition TEXT,
            category TEXT, url TEXT, text TEXT, motions TEXT, attachments TEXT,
            attachment_urls TEXT);
        CREATE VIRTUAL TABLE fts USING fts5(
            title, report_number, text, motions, attachments,
            content='items', content_rowid='id',
            tokenize='porter unicode61 remove_diacritics 2');
    """)
    seen = defaultdict(int)
    n = 0
    for it in _rows("agenda_items"):
        key = (it["meeting_id"], it["item_number"])
        k = seen[key]
        seen[key] += 1
        t = texts.get(key, [])
        text = t[k]["text"] if k < len(t) else ""
        # Motions/attachments carry no occurrence order of their own; attach
        # them to the first item with this number.
        mot = "\n".join(m["motion_text"] + (f" [{m['result']}]" if m["result"] else "")
                        for m in motions.get(key, [])) if k == 0 else ""
        att = attach.get(key, []) if k == 0 else []
        mtg = meetings.get(it["meeting_id"], {})
        con.execute(
            "INSERT INTO items VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (it["meeting_id"], it["date"], it["committee"], it["item_number"],
             it["title"], it["report_number"], it["disposition"], it["category"],
             mtg.get("url", ""), text, mot,
             "\n".join(a["filename"] for a in att),
             "\n".join(a["url"] for a in att)))
        n += 1
    # Text rows with no agenda item: whole-meeting pages (pre-2022 meetings have
    # no item breakdown) or items the other CSVs didn't capture.
    for key, rows in texts.items():
        mtg = meetings.get(key[0], {})
        for r in rows[seen.get(key, 0):]:
            con.execute(
                "INSERT INTO items VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key[0], mtg.get("date", ""), mtg.get("committee", ""), key[1],
                 "Full meeting text (no item breakdown)" if not key[1] else "(item text only)",
                 "", "", "", mtg.get("url", ""), r["text"], "", "", ""))
            n += 1
    con.execute("INSERT INTO fts(rowid, title, report_number, text, motions, attachments) "
                "SELECT id, title, report_number, text, motions, attachments FROM items")
    con.commit()
    con.execute("INSERT INTO fts(fts) VALUES ('optimize')")
    con.commit()
    con.close()
    tmp.replace(DB)
    with_text = sum(len(v) for v in texts.values())
    print(f"built {DB.name}: {n:,} search documents, {with_text:,} with page text, "
          f"{len(meetings):,} meetings", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def _quote_words(q: str) -> str:
    return " ".join('"' + w.replace('"', '') + '"' for w in q.split() if w.replace('"', ''))


def search(con, query, args):
    where, params = ["fts MATCH ?"], []
    if args.date_from:
        where.append("i.date >= ?")
        params.append(args.date_from)
    if args.date_to:
        where.append("i.date <= ?")
        params.append(args.date_to + "-12-31" if len(args.date_to) == 4 else args.date_to)
    if args.committee:
        where.append("i.committee LIKE ?")
        params.append(f"%{args.committee}%")
    order = "i.date DESC" if args.sort == "date" else "score"
    hl = ("\033[1m", "\033[0m") if sys.stdout.isatty() and not args.csv else ("**", "**")
    sql = f"""
        SELECT i.*, bm25(fts, {', '.join(map(str, WEIGHTS))}) AS score,
               snippet(fts, 2, ?, ?, ' … ', 24) AS snip_text,
               snippet(fts, 3, ?, ?, ' … ', 24) AS snip_motion
        FROM fts JOIN items i ON i.id = fts.rowid
        WHERE {' AND '.join(where)}
        ORDER BY {order} LIMIT ?"""
    limit = -1 if args.csv else args.limit
    run = lambda q: con.execute(sql, (*hl, *hl, q, *params, limit)).fetchall()
    try:
        return run(query), query
    except sqlite3.OperationalError:
        q2 = _quote_words(query)
        return run(q2), q2


def show(rows, args):
    for r in rows:
        head = f"{r['date']}  {r['committee']}  ·  item {r['item_number'] or '—'}"
        print(head)
        title = r["title"] + (f"  [{r['report_number']}]" if r["report_number"] else "")
        print(f"  {title}" + (f"  → {r['disposition']}" if r["disposition"] else ""))
        if args.full:
            body = r["text"] or "(no page text)"
            print("  " + body.replace("\n", "\n  "))
            if r["motions"]:
                print("  Motions:\n  " + r["motions"].replace("\n", "\n  "))
        else:
            snip = r["snip_text"] if "**" in r["snip_text"] or "\033[1m" in r["snip_text"] else r["snip_motion"]
            if snip:
                print("  " + re.sub(r"\s*\n\s*", " / ", snip))
        print(f"  {r['url']}")
        for name, url in list(zip(r["attachments"].splitlines(), r["attachment_urls"].splitlines()))[:args.pdfs]:
            print(f"    PDF: {name}  {url}")
        print()


def to_csv(rows, path):
    cols = ["date", "committee", "item_number", "title", "report_number",
            "disposition", "url", "text", "motions", "attachments", "attachment_urls"]
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", help="FTS5 query (omit with --rebuild)")
    ap.add_argument("--from", dest="date_from", help="earliest date, e.g. 2023 or 2023-06-01")
    ap.add_argument("--to", dest="date_to", help="latest date, e.g. 2025 or 2025-12-31")
    ap.add_argument("--committee", help="committee name contains this, e.g. council")
    ap.add_argument("--sort", choices=["relevance", "date"], default="relevance")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--full", action="store_true", help="print each hit's full text")
    ap.add_argument("--pdfs", type=int, default=3, help="attachment links per hit (default 3)")
    ap.add_argument("--csv", help="write all hits to this CSV instead of printing")
    ap.add_argument("--rebuild", action="store_true", help="force a rebuild of search.db")
    ap.add_argument("--data", help="indexer output folder (default: data/ next to this script)")
    args = ap.parse_args(argv)

    global DATA, DB
    if args.data:
        DATA = Path(args.data)
        DB = DATA / "search.db"

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.rebuild or needs_rebuild():
        build()
    if not args.query:
        return 0

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows, used = search(con, args.query, args)
    if used != args.query:
        print(f"(searched as: {used})", file=sys.stderr)
    if args.csv:
        to_csv(rows, args.csv)
        print(f"{len(rows)} hit(s) -> {args.csv}", file=sys.stderr)
    else:
        show(rows, args)
        sys.stdout.flush()
        print(f"{len(rows)} hit(s) shown" + (f" (limit {args.limit}; use --limit or --csv for more)"
              if len(rows) == args.limit else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

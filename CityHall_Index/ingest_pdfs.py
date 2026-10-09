#!/usr/bin/env python3
"""
Add downloaded eScribe PDFs to the search index (Stage 2, manual-download route).

eScribe's PDF links sit behind a browser check, so scripts can't fetch them.
Instead: open the links in a browser (search.py --pdf-list makes a page of
them), save the PDFs, then run

    python ingest_pdfs.py                       # PDFs already in pdfs/
    python ingest_pdfs.py --dir ~/Downloads     # copy new PDFs from Downloads first

Each PDF is matched to its meeting / agenda item through attachments.csv,
its text is extracted page by page, and search.py picks it up (one search
document per page, linking to that page).

Matching, in order:
  1. a DocumentId in the filename   ("206261.pdf", "206261 - anything.pdf")
  2. a filename unique in attachments.csv (browser suffixes like " (1)" ignored)
  3. a shared filename ("Document 1 (EN).pdf"): narrowed to documents listed by
     search.py --pdf-list, then to items whose report number appears in the PDF
  4. no filename match: an item whose report number (ACS2024-...) is in the PDF
Unresolved files are still searchable, just without meeting details. Renaming
the file to start with its DocumentId fixes the match.

Outputs (data/, gitignored):
  pdf_files.csv   one row per PDF: match method, document_id, meeting, item,
                  pages, characters, needs_ocr (no text layer = scanned)
  pdf_pages.csv   one row per page: text. Cached by file hash, so re-runs
                  only read new files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
PDFS = HERE / "pdfs"
ACS_RE = re.compile(r"ACS\d{4}-[A-Z]{2,4}-[A-Z]{2,4}-\d{3,4}")
ID_PREFIX_RE = re.compile(r"^(\d{4,7})(?:[ _\-.]|$)|documentid[=_ ]?(\d{4,7})", re.I)

csv.field_size_limit(2**31 - 1)


def _norm(name: str) -> str:
    """Filename key: no extension, no browser ' (1)' suffix, alphanumerics only."""
    s = re.sub(r"\.pdf$", "", name.strip(), flags=re.I)
    s = re.sub(r"\s*\(\d+\)$", "", s)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_csv(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def extract_pages(path: Path) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    pages = []
    for p in reader.pages:
        try:
            t = p.extract_text() or ""
        except Exception as e:  # damaged page: keep going
            print(f"  page error in {path.name}: {e}", file=sys.stderr)
            t = ""
        pages.append(re.sub(r"[ \t\xa0]+", " ", t).strip())
    return pages


def copy_new(src: Path, known: set[str]) -> int:
    """Copy PDFs from src into pdfs/ unless an identical file is already there."""
    n = 0
    for f in sorted(src.glob("*.pdf")):
        digest = _sha1(f)
        if digest in known:
            continue
        dest = PDFS / f.name
        if dest.exists():
            dest = PDFS / f"{f.stem} [{digest[:8]}].pdf"
        shutil.copy2(f, dest)
        known.add(digest)
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", help="also copy new PDFs from this folder into pdfs/ first")
    ap.add_argument("--pdf-dir", help="PDF store (default: pdfs/ next to this script)")
    ap.add_argument("--data", help="indexer output folder (default: data/ next to this script)")
    args = ap.parse_args(argv)
    global DATA, PDFS
    if args.data:
        DATA = Path(args.data)
    if args.pdf_dir:
        PDFS = Path(args.pdf_dir)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    PDFS.mkdir(exist_ok=True)

    pages_path = DATA / "pdf_pages.csv"
    cached = defaultdict(list)
    for r in _read_csv(pages_path):
        cached[r["sha1"]].append(r)

    if args.dir:
        known = {_sha1(f) for f in PDFS.glob("*.pdf")}
        print(f"copied {copy_new(Path(args.dir).expanduser(), known)} new PDF(s) from {args.dir}")

    # Lookups from the meeting index.
    attachments = _read_csv(DATA / "attachments.csv")
    by_id = {a["document_id"]: a for a in attachments}
    by_name = defaultdict(list)
    for a in attachments:
        by_name[_norm(a["filename"])].append(a)
    items = _read_csv(DATA / "agenda_items.csv")
    report_of = {(i["meeting_id"], i["item_number"]): i["report_number"] for i in items}
    by_report = defaultdict(list)
    for i in items:
        if i["report_number"]:
            by_report[i["report_number"]].append(i)
    wanted_path = DATA / "pdf_wanted.json"
    wanted = set(json.loads(wanted_path.read_text("utf-8"))) if wanted_path.exists() else set()

    new_pages = []
    files = []
    first_file = {}  # document_id -> first file matched to it
    # Browser re-downloads ("name (1).pdf") sort after the original, so the
    # original is the one kept when both match the same document.
    in_order = sorted(PDFS.glob("*.pdf"),
                      key=lambda f: (bool(re.search(r"\(\d+\)$", f.stem)), f.name.lower()))
    for f in in_order:
        digest = _sha1(f)
        if digest in cached:
            texts = [r["text"] for r in sorted(cached[digest], key=lambda r: int(r["page"]))]
        else:
            try:
                texts = extract_pages(f)
            except Exception as e:
                print(f"  could not read {f.name}: {e}")
                texts = []
            rows = [{"sha1": digest, "page": i, "text": t} for i, t in enumerate(texts, 1)]
            new_pages += rows
            cached[digest] = rows
        reports = set(ACS_RE.findall("\n".join(texts)))

        # --- match -----------------------------------------------------------
        att, how = None, "none"
        m = ID_PREFIX_RE.search(f.name)
        did = next((g for g in (m.groups() if m else ()) if g), None)
        if did and did in by_id:
            att, how = by_id[did], "document_id"
        else:
            cands = by_name.get(_norm(f.name), [])
            if len(cands) > 1:
                narrowed = [a for a in cands if a["document_id"] in wanted] or cands
                if len(narrowed) > 1 and reports:
                    narrowed = [a for a in narrowed
                                if report_of.get((a["meeting_id"], a["item_number"])) in reports] or narrowed
                cands = narrowed
            if len(cands) == 1:
                att, how = cands[0], "filename"
            elif len(cands) > 1:
                how = f"ambiguous ({len(cands)} files share this name)"
        meeting_id = item_number = ""
        if att:
            meeting_id, item_number = att["meeting_id"], att["item_number"]
        elif reports:
            hits = [i for r in sorted(reports) for i in by_report[r]]
            if hits:
                # Latest meeting (council usually decides last), and the most
                # specific item: a parent (17) repeats its child's (17.1) report number.
                latest = max(hits, key=lambda i: (i["date"], len(i["item_number"])))
                meeting_id, item_number = latest["meeting_id"], latest["item_number"]
                how = "report_number" if how == "none" else how + "; report_number"

        n_chars = sum(len(t) for t in texts)
        duplicate_of = ""
        if att:
            duplicate_of = first_file.setdefault(att["document_id"], f.name)
            duplicate_of = "" if duplicate_of == f.name else duplicate_of
        files.append({
            "sha1": digest, "file": f.name, "path": str(f.resolve()), "document_id": att["document_id"] if att else "",
            "attachment_name": att["filename"] if att else "", "match": how,
            "meeting_id": meeting_id, "item_number": item_number,
            "url": att["url"] if att else "", "pages": len(texts), "n_chars": n_chars,
            "needs_ocr": int(len(texts) > 0 and n_chars < 50 * len(texts)),
            "duplicate_of": duplicate_of,
        })

    if new_pages:
        new = not pages_path.exists()
        with open(pages_path, "a", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["sha1", "page", "text"])
            if new:
                w.writeheader()
            w.writerows(new_pages)
    cols = ["sha1", "file", "path", "document_id", "attachment_name", "match", "meeting_id",
            "item_number", "url", "pages", "n_chars", "needs_ocr", "duplicate_of"]
    with open(DATA / "pdf_files.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(files)

    # --- report --------------------------------------------------------------
    print(f"{len(files)} PDF(s) in {PDFS}, {len({r['sha1'] for r in new_pages})} newly read")
    for f in files:
        flag = "  [no text layer: needs OCR]" if f["needs_ocr"] else ""
        flag += f"  [duplicate of {f['duplicate_of']}: skipped in search]" if f["duplicate_of"] else ""
        where = f"{f['meeting_id'][:8]} item {f['item_number']}" if f["meeting_id"] else "no meeting"
        print(f"  {f['match']:<22} {where:<22} {f['pages']:>4} p  {f['file']}{flag}")
    unresolved = [f for f in files if not f["meeting_id"]]
    if unresolved:
        print(f"{len(unresolved)} file(s) without a meeting: still searchable; rename to "
              f"'<DocumentId> - name.pdf' to link them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

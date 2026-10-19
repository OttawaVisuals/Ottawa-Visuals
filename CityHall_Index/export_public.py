#!/usr/bin/env python3
"""Slim, public export of the City Hall index for cityhall.html.

Reads the gitignored CSVs in data/ and writes public/items.json: one compact
record per substantive agenda item (title, committee, date, decision, report
number, first motion, eScribe link). Procedural items are dropped.

    python export_public.py
"""
import csv, json, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA, OUT = HERE / "data", HERE / "public"
csv.field_size_limit(sys.maxsize)

PROCEDURAL = re.compile(
    r"^(call to order|roll call|adjournment|declarations? of interest|confirmation of minutes|"
    r"approval of (the )?(agenda|minutes)|minutes|notice of motion|motions? of which notice|"
    r"in camera|inquiries|announcements?|regrets|communications?|bylaws? (read|enactment)|"
    r"confirming by-?law|three readings|committee reports?)\b", re.I)


def rows(name):
    with open(DATA / f"{name}.csv", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    meetings = {m["meeting_id"]: m for m in rows("meetings")}
    first_motion = {}
    for m in rows("motions"):
        key = (m["meeting_id"], m["item_number"])
        if key not in first_motion and m["motion_text"].strip():
            first_motion[key] = re.sub(r"\s+", " ", m["motion_text"]).strip()
    committees, out = [], []
    for a in rows("agenda_items"):
        title = re.sub(r"\s+", " ", a["title"]).strip()
        if not title or PROCEDURAL.match(title):
            continue
        mtg = meetings.get(a["meeting_id"])
        if not mtg:
            continue
        motion = first_motion.get((a["meeting_id"], a["item_number"]), "")
        if len(motion) > 260:
            motion = motion[:257].rsplit(" ", 1)[0] + "…"
        out.append([a["date"], a["committee"], a["item_number"], title,
                    a["report_number"], a["disposition"].strip(), motion, a["meeting_id"]])
    out.sort(key=lambda r: (r[0], r[1]), reverse=True)
    committees = [c for c, _ in Counter(r[1] for r in out).most_common()]
    OUT.mkdir(exist_ok=True)
    payload = {
        "built": max(r[0] for r in out),
        "cols": ["date", "committee", "item", "title", "report", "decision", "motion", "meeting"],
        "committees": committees,
        "base": "https://pub-ottawa.escribemeetings.com/Meeting.aspx?Id=",
        "items": out,
    }
    (OUT / "items.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} of ~23.8k items -> public/items.json "
          f"({(OUT / 'items.json').stat().st_size / 1e6:.1f} MB), {len(committees)} committees")


if __name__ == "__main__":
    main()

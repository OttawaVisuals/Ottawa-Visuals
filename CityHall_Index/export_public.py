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
sys.path.insert(0, str(HERE))
from split_votes import member_key, split_names  # noqa: E402
from topics import TOPICS, is_routine, result_bucket, topic_of  # noqa: E402
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


def export_votes(meetings):
    """public/votes.json: one record per motion with a recorded (named) vote."""
    items = {(r["meeting_id"], r["item_number"]): r for r in rows("agenda_items")}
    results = {(r["meeting_id"], r["item_number"], r["motion_index"]): r for r in rows("motions")}
    by = {}
    for v in rows("votes"):
        k = (v["meeting_id"], v["item_number"], v["motion_index"])
        by.setdefault(k, {}).setdefault(v["vote"], []).extend(member_key(n) for n in split_names(v["voters"]))
    out = []
    for k, sides in by.items():
        it, mo = items.get(k[:2]), results.get(k)
        if not it or not mo:
            continue
        text = re.sub(r"\s+", " ", mo["motion_text"]).strip()
        if len(text) > 300:
            text = text[:297].rsplit(" ", 1)[0] + "…"
        out.append([it["date"], it["committee"], re.sub(r"\s+", " ", it["title"]).strip(), it["report_number"],
                    mo["result"].strip(), text, sides.get("For", []), sides.get("Against", []),
                    [[m, t] for t in sides if t not in ("For", "Against") for m in sides[t]], k[0]])
    out.sort(key=lambda r: r[0], reverse=True)
    payload = {"cols": ["date", "committee", "title", "report", "result", "motion", "for", "against", "other", "meeting"],
               "base": "https://pub-ottawa.escribemeetings.com/Meeting.aspx?Id=", "votes": out}
    (OUT / "votes.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} recorded-vote motions -> public/votes.json "
          f"({(OUT / 'votes.json').stat().st_size / 1e6:.2f} MB)")


PAIR = re.compile(r"Moved\s*by\s*([^\n]+?)\s*\n?\s*Seconded\s*by\s*([^\n]+)")


def clean_name(raw):
    return member_key(raw.strip().lstrip(":").strip())


def export_motions():
    """public/motions.json: every substantive motion (topic + result bucket) and
    every mover/seconder pair on a substantive item."""
    items = {(r["meeting_id"], r["item_number"]): r for r in rows("agenda_items")}
    recs, seen_items = [], set()
    for m in rows("motions"):
        it = items.get((m["meeting_id"], m["item_number"]))
        if not it or is_routine(it["title"]) or PROCEDURAL.match(it["title"].strip()):
            continue
        title = re.sub(r"\s+", " ", it["title"]).strip()
        recs.append([it["date"], it["committee"], topic_of(title, it["committee"]), result_bucket(m["result"]),
                     title[:140], it["report_number"], m["meeting_id"]])
        seen_items.add((m["meeting_id"], m["item_number"]))
    recs.sort(key=lambda r: r[0], reverse=True)
    pairs = []
    for t in rows("item_text"):
        k = (t["meeting_id"], t["item_number"])
        it = items.get(k)
        if not it or is_routine(it["title"]) or PROCEDURAL.match(it["title"].strip()):
            continue
        title = re.sub(r"\s+", " ", it["title"]).strip()
        for mo, se in PAIR.findall(t["text"]):
            pairs.append([it["date"], it["committee"], topic_of(title, it["committee"]),
                          result_bucket(it["disposition"]), title[:140], it["report_number"],
                          clean_name(mo), clean_name(se), t["meeting_id"]])
    pairs.sort(key=lambda r: r[0], reverse=True)
    payload = {"topics": TOPICS, "buckets": ["Carried", "Lost", "Received", "Withdrawn", "Deferred", "Other", "No result recorded"],
               "base": "https://pub-ottawa.escribemeetings.com/Meeting.aspx?Id=",
               "motion_cols": ["date", "committee", "topic", "result", "title", "report", "meeting"],
               "mover_cols": ["date", "committee", "topic", "result", "title", "report", "mover", "seconder", "meeting"],
               "motions": recs, "movers": pairs}
    (OUT / "motions.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(recs)} substantive motions, {len(pairs)} mover/seconder pairs -> public/motions.json "
          f"({(OUT / 'motions.json').stat().st_size / 1e6:.2f} MB)")


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
    export_votes(meetings)
    export_motions()


if __name__ == "__main__":
    main()

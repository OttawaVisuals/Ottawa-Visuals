#!/usr/bin/env python3
"""Split votes.csv (one row per tally, voters as one string) into one row per
member vote: data/votes_by_member.csv.

    python split_votes.py [--data data]

Names in the minutes vary ("Councillor G. Gower", "Co-Chair: Councillor G. Gower",
"Gower", full first names, Chair/Vice-Chair/Member/Mayor prefixes). They are
reduced to a member key "<first initial>. <surname>" so one person is one key;
different people who share initial+surname would merge (none seen in the data).
Output columns: meeting_id, date, committee, item_number, motion_index, result,
vote, member, name_as_written, tally_count, parsed_count.
"""
import argparse, csv, re, sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)
HERE = Path(__file__).resolve().parent
PREFIX = re.compile(r"^(?:(?:vice-?\s*)?co-?chair:?|chair|vice-?chair|councillor|mayor|member|deputy mayor)\s*:?\s+", re.I)
ALIAS = {"Ana Maria Cruz-Valderrama": "A. Cruz-Valderrama", "A.M. Cruz-Valderrama": "A. Cruz-Valderrama",
         "C.A. Meehan": "C. Meehan"}


def member_key(raw: str) -> str:
    s = raw.strip()
    while True:
        t = PREFIX.sub("", s)
        if t == s:
            break
        s = t
    s = ALIAS.get(s, s)
    parts = s.split()
    if len(parts) >= 2:
        first, last = parts[0], " ".join(parts[1:])
        if not re.fullmatch(r"(?:[A-Z]\.)+", first):  # full first name -> initial
            first = first[0] + "."
        s = f"{first} {last}"
    return ALIAS.get(s, s)


def split_names(voters: str):
    s = re.sub(r",?\s+and\s+", ", ", voters.strip())
    return [p.strip() for p in s.split(",") if p.strip()]


def rd(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "data"))
    data = Path(ap.parse_args(argv).data)
    items = {(r["meeting_id"], r["item_number"]): r for r in rd(data / "agenda_items.csv")}
    motions = {(r["meeting_id"], r["item_number"], r["motion_index"]): r["result"] for r in rd(data / "motions.csv")}
    out, mismatch = [], 0
    for v in rd(data / "votes.csv"):
        names = split_names(v["voters"])
        it = items.get((v["meeting_id"], v["item_number"]), {})
        if v["count"].isdigit() and int(v["count"]) != len(names):
            mismatch += 1
        for n in names:
            out.append({"meeting_id": v["meeting_id"], "date": it.get("date", ""), "committee": it.get("committee", ""),
                        "item_number": v["item_number"], "motion_index": v["motion_index"],
                        "result": motions.get((v["meeting_id"], v["item_number"], v["motion_index"]), ""),
                        "vote": v["vote"], "member": member_key(n), "name_as_written": n,
                        "tally_count": v["count"], "parsed_count": len(names)})
    cols = list(out[0])
    with open(data / "votes_by_member.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(out)
    print(f"{len(out)} member votes, {len({o['member'] for o in out})} members; "
          f"{mismatch} tallies where listed names != stated count")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Ontario recorded divisions weighted by each MPP's election mandate.

Joins Ontario_Votes/ontario_votes.json.gz (collected in the browser by
collect_votes_in_browser.js) to Ontario_Elections/Explorer_*.csv and writes
Ontario_Votes/mandates.json for mpp_mandates.html.

Votes up to the 2025 election use the 2022 result, later votes the 2025 result.
An MPP only gets a mandate if they are that election's winner in their riding
(by-election winners and floor-crossers' successors have none: their ballots are
left out and counted as "unknown", electors are still counted).

    python Ontario_Votes/mandates.py
"""
import csv, gzip, json, re, sys, unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ELEC = HERE.parent / "Ontario_Elections"
ELECTION_2025 = "2025-02-27"


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def riding_key(s):
    return norm(re.sub(r"^\d+\s*-\s*", "", s))


def surname(full):
    full = re.sub(r"^(hon\.|dr\.)\s*", "", full.strip(), flags=re.I)
    parts = [p for p in re.split(r"\s+", full) if p]
    return norm(parts[-1]) if parts else ""


def same_person(winner, mpp):
    a, b = surname(winner), surname(mpp)
    return bool(a and b) and (a == b or a in b or b in a)


def load_elections():
    wins, reg = {}, {}
    with open(ELEC / "Explorer_Electoral_District_22062026_101854.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            reg[(r["Year"], riding_key(r["Electoral District"]))] = int(r["Registered Voters"])
    with open(ELEC / "Explorer_All_22062026_101900.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if int(r["Plurality"] or 0) > 0:
                wins[(r["Year"], riding_key(r["Electoral District"]))] = {
                    "name": r["Candidate"].title(), "votes": int(r["Votes Cast"])}
    return wins, reg


def main():
    wins, reg = load_elections()
    with gzip.open(HERE / "ontario_votes.json.gz", "rt", encoding="utf-8") as f:
        votes = json.load(f)
    mp = {}  # (election, riding) -> member record
    motions, unmatched = [], set()
    for v in votes:
        year = "2025" if v["date"] >= ELECTION_2025 else "2022"
        sides = {"Aye": dict(n=0, ballots=0, electors=0, unknown=0), "Nay": dict(n=0, ballots=0, electors=0, unknown=0)}
        for m in v["members"]:
            if m["vote"] not in sides:
                continue
            k = (year, riding_key(m["riding"]))
            if k not in reg:
                unmatched.add(m["riding"])
                continue
            win = wins.get(k)
            known = bool(win) and same_person(win["name"], m["name"])
            rec = mp.setdefault((year, m["name"]), {
                "name": m["name"], "party": m["party"], "riding": m["riding"], "election": year,
                "registered": reg[k], "ballots": win["votes"] if known else None, "aye": 0, "nay": 0})
            rec["aye" if m["vote"] == "Aye" else "nay"] += 1
            s = sides[m["vote"]]
            s["n"] += 1
            s["electors"] += reg[k]
            if known:
                s["ballots"] += win["votes"]
            else:
                s["unknown"] += 1
        win_side = "Aye" if v["outcome"] == "Carried" else "Nay"
        lose = "Nay" if win_side == "Aye" else "Aye"
        motions.append({
            "date": v["date"], "title": v["title"], "movedBy": v["movedBy"], "parliament": v["parliament"].split(",")[0],
            "outcome": v["outcome"], "url": v["url"], "election": year,
            "aye": sides["Aye"], "nay": sides["Nay"],
            "fewer": sides[win_side]["ballots"] < sides[lose]["ballots"],
            "fewerElectors": sides[win_side]["electors"] < sides[lose]["electors"],
            "partial": bool(sides["Aye"]["unknown"] or sides["Nay"]["unknown"]),
        })
    if unmatched:
        sys.exit(f"ridings with no election data: {sorted(unmatched)}")
    motions.sort(key=lambda m: m["date"], reverse=True)
    members = sorted(mp.values(), key=lambda r: (r["election"], r["riding"]))
    for r in members:
        r["share"] = round(r["ballots"] / r["registered"], 4) if r["ballots"] else None
    totals = {y: sum(n for (yy, _), n in reg.items() if yy == y) for y in ("2022", "2025")}
    complete = [m for m in motions if not m["partial"]]
    payload = {"motions": motions, "members": members, "totals": totals,
               "summary": {"votes": len(motions), "complete": len(complete),
                           "fewer": sum(m["fewer"] for m in complete),
                           "fewerElectors": sum(m["fewerElectors"] for m in motions)}}
    (HERE / "mandates.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(payload["summary"], "members without a mandate:", sum(r["ballots"] is None for r in members))


if __name__ == "__main__":
    main()

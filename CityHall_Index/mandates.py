#!/usr/bin/env python3
"""Council recorded votes weighted by each councillor's 2022 mandate.

Joins public/votes.json (City Council motions since the 2022-12-01 term start)
to Ottawa_Elections/ward_results.csv (2022 winner's votes and registered
electors per ward) and writes public/mandates.json for cityhall_mandates.html.

Per motion: the councillors on each side, the ballots that elected them, and the
registered electors in their wards. The mayor's vote is kept in the tally but
left out of the sums (elected citywide, no ward).

    python mandates.py
"""
import csv, json, re, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
WARDS = HERE.parent / "Ottawa_Elections" / "ward_results.csv"
TERM_START = "2022-12-01"
MAYOR = "M. Sutcliffe"

# Ward 20 by-election (June 2025) replaced G. Darouze. The City's per-ward
# numbers are not in ward_results.csv; these are derived from press figures
# (6,223 ballots, 24.17% turnout, 34.01% for the winner) and flagged as estimates.
BYELECTION = {"I. Skalski": {"ward": 20, "registered": round(6223 / 0.2417), "votes": round(6223 * 0.3401)}}


def initials(name):
    parts = re.sub(r"[^\w\s'-]", "", name).split()
    return f"{parts[0][0]}. {parts[-1]}"


def load_councillors():
    out = {}
    with open(WARDS, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["year"] != "2022":
                continue
            key = initials(r["Council_Win_Name"])
            out[key] = {"ward": int(r["ward"]), "wardName": r["name"], "name": r["Council_Win_Name"],
                        "registered": int(r["Council_Registered"]), "votes": int(r["Council_Winner"]),
                        "estimated": False}
    for key, b in BYELECTION.items():
        ward = next(c for c in out.values() if c["ward"] == b["ward"])
        out[key] = {"ward": b["ward"], "wardName": ward["wardName"], "name": "Isabelle Skalski",
                    "registered": b["registered"], "votes": b["votes"], "estimated": True}
    return out


def main():
    mandate = load_councillors()
    total_reg = sum(c["registered"] for c in mandate.values() if not c["estimated"])
    votes = json.loads((HERE / "public" / "votes.json").read_text(encoding="utf-8"))["votes"]
    motions, missing = [], set()
    for date, cmte, title, report, result, text, yes, no, other, mid in votes:
        if cmte != "City Council" or date < TERM_START:
            continue
        sides = {}
        for side, names in (("yes", yes), ("no", no)):
            ward = [n for n in names if n != MAYOR]
            missing.update(n for n in ward if n not in mandate)
            ward = [n for n in ward if n in mandate]
            sides[side] = {"n": len(names), "ward": len(ward),
                           "ballots": sum(mandate[n]["votes"] for n in ward),
                           "electors": sum(mandate[n]["registered"] for n in ward)}
        win = "yes" if result.startswith("Carried") else "no" if result.startswith("Lost") else None
        lose = {"yes": "no", "no": "yes"}.get(win)
        motions.append({
            "date": date, "title": title, "report": report, "result": result, "text": text, "meeting": mid,
            "yes": sides["yes"], "no": sides["no"], "mayor": "yes" if MAYOR in yes else "no" if MAYOR in no else "",
            "win": win,
            "fewer": bool(win and sides[win]["ballots"] < sides[lose]["ballots"]),
            "fewerElectors": bool(win and sides[win]["electors"] < sides[lose]["electors"]),
        })
    if missing:
        sys.exit(f"no ward mapping for {sorted(missing)}")
    motions.sort(key=lambda m: m["date"], reverse=True)

    members = defaultdict(lambda: {"yes": 0, "no": 0})
    for date, cmte, _t, _r, _res, _tx, yes, no, _o, _m in votes:
        if cmte == "City Council" and date >= TERM_START:
            for n in yes:
                members[n]["yes"] += 1
            for n in no:
                members[n]["no"] += 1
    council = [{"member": k, **v, **members.get(k, {"yes": 0, "no": 0}),
                "share": round(v["votes"] / v["registered"], 4)} for k, v in mandate.items()]
    council.sort(key=lambda c: c["ward"])

    decided = [m for m in motions if m["win"]]
    payload = {"termStart": TERM_START, "totalElectors": total_reg, "council": council, "motions": motions,
               "summary": {"motions": len(decided),
                           "fewerBallots": sum(m["fewer"] for m in decided),
                           "fewerElectors": sum(m["fewerElectors"] for m in decided)},
               "base": "https://pub-ottawa.escribemeetings.com/Meeting.aspx?Id=",
               "notes": ["Mandate = ballots cast for the winning councillor in 2022 (by-election estimate for Ward 20 from 2025).",
                         "The mayor's vote is in the tally but not the sums."]}
    (HERE / "public" / "mandates.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                                                   encoding="utf-8")
    print(payload["summary"], f"{len(motions)} motions, total electors {total_reg}")


if __name__ == "__main__":
    main()

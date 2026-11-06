"""Aggregate the 2025 Canadian Election Study into weighted tables for FedElections.html.

Usage: python Federal_Elections/ces_tables.py "<path to 2025 Canadian Election Study v1.dta>"

The microdata (CC BY-NC 4.0, Harvard Dataverse doi:10.7910/DVN/2YAQ8D) is NOT kept in the
repository; only the aggregated tables written here are. Requires pandas.

For respondents who say which party they would vote for (campaign survey), the tables give, for
every other party Y: the weighted share who would "absolutely not vote" for Y, the share who rate
Y 50+ on a 0-100 party slider, and the share who do neither (rule it out never, rate it 50+) -
"open to" Y. Territories have no weights and are excluded.
"""
from pathlib import Path
import hashlib
import json
import sys

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "ces_tables.json"
JS = HERE / "ces.js"

# party code -> (intended-vote value in cps25_votechoice, not_vote_for suffix, party_rating suffix)
PARTIES = {
    "LPC": (1, 1, 23),
    "CPC": (2, 2, 24),
    "NDP": (3, 3, 25),
    "BQ": (4, 4, 26),
    "GPC": (5, 5, 27),
    "PPC": (8, 9, 29),
}
VOTER_PARTIES = ["LPC", "CPC", "NDP", "BQ", "GPC", "PPC"]   # small groups are flagged by n in the page
REGIONS = {
    "Canada": None,
    "Ontario": [9],
    "Quebec": [11],
    "British Columbia": [2],
    "Prairies": [1, 12, 3],            # AB, SK, MB
    "Atlantic": [4, 5, 7, 10],         # NB, NL, NS, PEI
}
WEIGHT = "cps25_weight_general_restricted"
MIN_N = 100
FAVOURABLE = 50


def wshare(mask, w):
    tot = w.sum()
    return float((w[mask]).sum() / tot) if tot > 0 else None


def build(dta):
    df = pd.read_stata(dta, convert_categoricals=False)
    df = df[df[WEIGHT].notna() & df["cps25_votechoice"].isin([v for v, _, _ in PARTIES.values()])].copy()
    out = {"meta": {
        "source": "2025 Canadian Election Study (Stephenson, Harell, Rubenson), v1, Harvard Dataverse",
        "doi": "10.7910/DVN/2YAQ8D", "licence": "CC BY-NC 4.0",
        "wave": "campaign period survey", "weight": WEIGHT,
        "respondents_used": int(len(df)), "favourable_cutoff": FAVOURABLE, "min_n_for_display": MIN_N,
        "sha256_of_input": hashlib.sha256(Path(dta).read_bytes()).hexdigest()}, "regions": {}}
    for region, provs in REGIONS.items():
        sub = df if provs is None else df[df["cps25_province"].isin(provs)]
        res = {}
        for x in VOTER_PARTIES:
            vx, _, _ = PARTIES[x]
            vs = sub[sub["cps25_votechoice"] == vx]
            n = int(len(vs))
            row = {"n": n, "share_of_decided": wshare(sub["cps25_votechoice"] == vx, sub[WEIGHT]), "to": {}}
            w = vs[WEIGHT]
            for y, (_, nv, pr) in PARTIES.items():
                if y == x:
                    continue
                shown = vs[f"cps25_not_vote_for_{nv}"].notna()      # own-party option is hidden
                ruled_out = vs[f"cps25_not_vote_for_{nv}"] == 1
                rating = vs[f"cps25_party_rating_{pr}"]
                rated = rating >= 0                                  # -99 = no answer
                fav = rating >= FAVOURABLE
                open_to = shown & ~ruled_out & rated & fav
                base = shown & rated
                if base.sum() == 0:
                    continue
                wb = w[base]
                row["to"][y] = {
                    "n": int(base.sum()),
                    "rule_out": float(w[base & ruled_out].sum() / wb.sum()),
                    "favourable": float(w[base & fav].sum() / wb.sum()),
                    "open": float(w[open_to].sum() / wb.sum()),
                    "mean_rating": float((rating[base] * w[base]).sum() / wb.sum()),
                }
            res[x] = row
        out["regions"][region] = res
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    JS.write_text("window.CES_DATA = " + json.dumps(out, separators=(",", ":")) + ";\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    t = build(sys.argv[1])
    for region, res in t["regions"].items():
        print(region, {x: (r["n"], {y: round(v["open"] * 100) for y, v in r["to"].items() if y in ("LPC", "NDP")}) for x, r in res.items()})

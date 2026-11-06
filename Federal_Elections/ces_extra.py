"""Additional 2025 CES aggregates for FedElections.html (imported by ces_tables.py).

Tables: why people chose their party, intended-vs-actual vote, who switches, why people rule a
party out, most important issue by party (open text bucketed by keyword), why people did not vote.
Only weighted aggregates are returned; groups under MIN_N are dropped.
"""
import pandas as pd

MIN_N = 100
PW = "pes25_weight_general_restricted"
CW = "cps25_weight_general_restricted"
FAVOURABLE = 50
PES_CODE = {1: "LPC", 2: "CPC", 3: "NDP", 4: "BQ", 5: "GPC", 6: "PPC", 7: "OTH"}
CPS_CODE = {1: "LPC", 2: "CPC", 3: "NDP", 4: "BQ", 5: "GPC", 8: "PPC", 6: "OTH", 7: "UNDECIDED"}
RATING = {"LPC": 23, "CPC": 24, "NDP": 25, "BQ": 26, "GPC": 27, "PPC": 29}
NOTVOTE = {"LPC": 1, "CPC": 2, "NDP": 3, "BQ": 4, "GPC": 5, "PPC": 9}
REGION_OF = {9: "Ontario", 11: "Quebec", 2: "British Columbia", 1: "Prairies", 12: "Prairies",
             3: "Prairies", 4: "Atlantic", 5: "Atlantic", 7: "Atlantic", 10: "Atlantic"}
REASON = {1: "Party policies", 2: "Leader", 3: "Local candidate", 4: "Didn't want another party to win", 5: "Other"}
DECIDE = {1: "Before the campaign", 2: "During the campaign", 3: "On election day"}
NOVOTE = {1: "My vote won't make a difference", 2: "No time / too busy", 3: "No interest / didn't follow",
          4: "Physical limits / illness", 5: "Couldn't prove ID or address", 6: "Didn't know when/where",
          7: "Mail ballot didn't arrive", 9: "Line too long", 10: "Don't know / no answer"}
ISSUES = [  # first match wins; text is lower-cased
    ("Trump, tariffs, sovereignty", ["trump", "tarif", "sovereign", "souverain", "51st", "annex", "trade war", "u.s.", "usa", "american"]),
    ("Health care", ["health", "santé", "sante", "hospital", "doctor", "medic", "soins"]),
    ("Housing", ["housing", "logement", "rent", "mortgage", "homeless"]),
    ("Cost of living, inflation", ["cost of living", "afford", "inflation", "price", "grocer", "coût", "cout", "vie chère", "prix", "cost"]),
    ("Economy, jobs", ["econom", "économ", "job", "emploi", "unemploy", "business", "growth", "deficit", "debt", "dette", "budget"]),
    ("Immigration", ["immig", "border", "frontière", "frontiere", "refugee"]),
    ("Climate, environment", ["climat", "environ", "carbon", "pipeline", "energy", "énergie", "energie"]),
    ("Leadership, trust, democracy", ["leader", "trust", "corrupt", "honest", "integrity", "democra", "chef", "confiance", "carney", "poilievre", "singh"]),
    ("Taxes", ["tax", "impôt", "impot", "taxe"]),
    ("Crime, safety", ["crime", "safety", "sécurité", "securite", "police"]),
]
ISSUE_LABELS = [label for label, _ in ISSUES] + ["Other"]


def wshare(mask, w):
    tot = w.sum()
    return float(w[mask].sum() / tot) if tot > 0 else None


def region_slices(d, provcol):
    yield "Canada", d
    for name in ("Ontario", "Quebec", "British Columbia", "Prairies", "Atlantic"):
        yield name, d[d[provcol].isin([k for k, v in REGION_OF.items() if v == name])]


def issue_bucket(text):
    t = str(text).lower().strip()
    if t in ("", "-99", "nan"):
        return None
    for label, keys in ISSUES:
        if any(k in t for k in keys):
            return label
    return "Other"


def add_demographics(d):
    d = d.copy()
    d["Age"] = pd.cut(d["cps25_age_in_years"], [0, 34, 54, 200], labels=["18–34", "35–54", "55+"]).astype(object)
    inc = d["cps25_income"]
    d["Household income"] = None
    d.loc[inc.isin([1, 2, 3]), "Household income"] = "Under $60,000"
    d.loc[inc.isin([4, 5]), "Household income"] = "$60,000–$110,000"
    d.loc[inc.isin([6, 7, 8]), "Household income"] = "Over $110,000"
    edu = d["cps25_education"]
    d["Education"] = None
    d.loc[edu.between(1, 8), "Education"] = "No university degree"
    d.loc[edu.between(9, 11), "Education"] = "University degree"
    d["Gender"] = d["cps25_genderid"].map({1: "Men", 2: "Women"})
    d["Union membership"] = d["cps25_union"].map({1: "Union member", 2: "Not a union member"})
    d["Housing"] = None
    d.loc[d["cps25_property_1"] == 1, "Housing"] = "Owns a residence"
    d.loc[d["cps25_rent"] == 1, "Housing"] = "Rents"
    return d


def open_to(g, y):
    nv, pr = NOTVOTE[y], RATING[y]
    base = g[f"cps25_not_vote_for_{nv}"].notna() & (g[f"cps25_party_rating_{pr}"] >= 0)
    if base.sum() < MIN_N:
        return None, int(base.sum())
    op = base & (g[f"cps25_not_vote_for_{nv}"] != 1) & (g[f"cps25_party_rating_{pr}"] >= FAVOURABLE)
    return float(g[CW][op].sum() / g[CW][base].sum()), int(base.sum())


def extras(raw):
    out = {}
    pes = raw[raw[PW].notna()].copy()
    pes["prov"] = pes["pes25_province"].fillna(pes["cps25_province"])
    voted = pes[pes["pes25_votechoice2025"].between(1, 7)].copy()
    voted["party"] = voted["pes25_votechoice2025"].map(PES_CODE)

    # 1. why people chose the party they voted for, and when they decided
    tac = {}
    for region, sub in region_slices(voted, "prov"):
        res = {}
        for party in ("LPC", "CPC", "NDP", "BQ", "GPC"):
            g = sub[(sub["party"] == party) & sub["pes25_resason_chose"].between(1, 5)]
            if len(g) < MIN_N:
                continue
            r = {"n": int(len(g)), "reason": {v: wshare(g["pes25_resason_chose"] == k, g[PW]) for k, v in REASON.items()}}
            gd = sub[(sub["party"] == party) & sub["pes25_when_decide"].between(1, 3)]
            if len(gd) >= MIN_N:
                r["decided"] = {v: wshare(gd["pes25_when_decide"] == k, gd[PW]) for k, v in DECIDE.items()}
            res[party] = r
        tac[region] = res
    out["tactical"] = tac

    # 2. intended vote (campaign wave) -> actual vote (post-election wave)
    sw = voted[voted["cps25_votechoice"].isin(CPS_CODE)].copy()
    sw["intent"] = sw["cps25_votechoice"].map(CPS_CODE)
    switching = {}
    for region, sub in region_slices(sw, "prov"):
        res = {}
        for intent in ("LPC", "CPC", "NDP", "BQ", "GPC", "PPC", "UNDECIDED"):
            g = sub[sub["intent"] == intent]
            if len(g) >= MIN_N:
                res[intent] = {"n": int(len(g)), "to": {p: wshare(g["party"] == p, g[PW]) for p in PES_CODE.values()}}
        switching[region] = res
    out["switching"] = switching

    # 3. who switches / who is open, national, by demographic group
    s = add_demographics(sw)
    cps = add_demographics(raw[raw[CW].notna() & raw["cps25_votechoice"].isin([1, 3])])
    groups = {}
    for dim, levels in (("Age", ["18–34", "35–54", "55+"]),
                        ("Household income", ["Under $60,000", "$60,000–$110,000", "Over $110,000"]),
                        ("Education", ["No university degree", "University degree"]),
                        ("Gender", ["Men", "Women"]),
                        ("Housing", ["Owns a residence", "Rents"]),
                        ("Union membership", ["Union member", "Not a union member"])):
        rows = []
        for level in levels:
            a = s[(s["intent"] == "NDP") & (s[dim] == level)]
            b = cps[(cps["cps25_votechoice"] == 3) & (cps[dim] == level)]
            c = cps[(cps["cps25_votechoice"] == 1) & (cps[dim] == level)]
            row = {"level": level}
            if len(a) >= MIN_N:
                row["ndp_to_lpc_switched"] = wshare(a["party"] == "LPC", a[PW])
                row["ndp_n"] = int(len(a))
            v, n = open_to(b, "LPC")
            if v is not None:
                row["ndp_open_lpc"], row["ndp_open_n"] = v, n
            v, n = open_to(c, "NDP")
            if v is not None:
                row["lpc_open_ndp"], row["lpc_open_n"] = v, n
            rows.append(row)
        groups[dim] = rows
    out["swing_groups"] = groups

    # 4. why people rule a party out (only respondents who ruled out exactly one party and were asked)
    cw = raw[raw[CW].notna()]
    flags = pd.DataFrame({k: cw[f"cps25_not_vote_for_{v}"] == 1 for k, v in NOTVOTE.items()})
    one = (flags.sum(axis=1) == 1) & cw["cps25_not_vote_for_w_1"].notna()
    why = {}
    for party in NOTVOTE:
        g = cw[one & flags[party]]
        if len(g) >= MIN_N:
            w = g[CW]
            why[party] = {"n": int(len(g)),
                          "leader": wshare(g["cps25_not_vote_for_w_1"] == 1, w),
                          "policies": wshare(g["cps25_not_vote_for_w_2"] == 1, w),
                          "supporters": wshare(g["cps25_not_vote_for_w_3"] == 1, w)}
    out["why_rule_out"] = why

    # 5. most important issue (free text bucketed by keyword) by intended party
    iss = raw[raw[CW].notna() & raw["cps25_votechoice"].isin([1, 2, 3, 4, 5, 8])].copy()
    iss["bucket"] = iss["cps25_imp_iss"].map(issue_bucket)
    iss = iss[iss["bucket"].notna()]
    iss["party"] = iss["cps25_votechoice"].map(CPS_CODE)
    by_party = {}
    for party in ("LPC", "CPC", "NDP", "BQ", "GPC", "PPC"):
        g = iss[iss["party"] == party]
        if len(g) >= MIN_N:
            by_party[party] = {"n": int(len(g)), "share": {l: wshare(g["bucket"] == l, g[CW]) for l in ISSUE_LABELS}}
    out["issues"] = {"labels": ISSUE_LABELS, "by_party": by_party, "respondents": int(len(iss))}

    # 6. why people did not vote (self-reported non-voters), by age
    nv = pes[pes["pes25_notvotereason1"].notna()].copy()
    nv["age"] = pd.cut(nv["cps25_age_in_years"], [0, 34, 200], labels=["Under 35", "35 and over"]).astype(object)
    nov = {"labels": list(NOVOTE.values()), "groups": {}}
    for name, g in (("All non-voters", nv), ("Under 35", nv[nv["age"] == "Under 35"]), ("35 and over", nv[nv["age"] == "35 and over"])):
        if len(g) >= MIN_N:
            nov["groups"][name] = {"n": int(len(g)), "share": {v: wshare(g["pes25_notvotereason1"] == k, g[PW]) for k, v in NOVOTE.items()}}
    out["no_vote"] = nov
    return out

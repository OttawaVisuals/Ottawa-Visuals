"""Build Tax/data/tax.json — everything tax.html draws.

Inputs (Tax/data/raw/ is gitignored; see Tax/README.md for download URLs):
  sources/saez_veall_F1_marginal_rates.csv  top marginal rates 1920-2000 (committed)
  sources/saez_veall_F2_average_rates.csv   average tax rates of top groups 1920-2000 (committed)
  sources/top_rate_2001_2026.csv            statutory fed+ON top rate 2001-2026 (committed)
  raw/WID_data_CA.csv                       WID.world Canada (income shares, real incomes, wealth)
  raw/statcan_11100055_canada_on_ott.csv    StatCan 11-10-0055 high-income filers, filtered
                                            (build it with the filter step in README)
  raw/ec_contrib_by_fsa.csv                 output of aggregate_contributions.py
  raw/cra_fsa_2021_tbl1a.csv                CRA Individual Tax Statistics by FSA, 2021 tax year
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent / "data"
RAW, SRC = ROOT / "raw", ROOT / "sources"

DONATION_YEARS = range(2019, 2024)   # 5 audited years around the 2021 CRA FSA snapshot
OTTAWA_PREFIXES = ("K1", "K2", "K4")


def r(x, n=2):
    return None if x is None or pd.isna(x) else round(float(x), n)


def wid():
    d = pd.read_csv(RAW / "WID_data_CA.csv", sep=";")
    def s(var, pct):
        return d[(d.variable == var) & (d.percentile == pct)].set_index("year").value
    # Group averages = share x overall average / group size. WID's own
    # aptinci992 p50p90 is ~4x too high (sum-not-mean bug), so derive all of them.
    avg = s("aptinci992", "p0p100")                         # real pre-tax income per adult
    grp = lambda pct, size: s("sptinci992", pct) * avg / size
    return pd.DataFrame({
        "top1_share": s("sfiinci992", "p99p100") * 100,     # fiscal income, Saez-Veall basis
        "top10_share": s("sfiinci992", "p90p100") * 100,
        "b50_inc": grp("p0p50", 0.5),
        "m40_inc": grp("p50p90", 0.4),
        "t10_inc": grp("p90p100", 0.1),
        "t1_inc": grp("p99p100", 0.01),
        "all_inc": avg,
        "ni_pa": s("anninci992", "p0p100"),                 # national income per adult
        "w_top1": s("shwealj992", "p99p100") * 100,
        "w_top10": s("shwealj992", "p90p100") * 100,
        "w_b50": s("shwealj992", "p0p50") * 100,
    })


def statcan():
    d = pd.read_csv(RAW / "statcan_11100055_canada_on_ott.csv", dtype=str)
    d["VALUE"] = pd.to_numeric(d.VALUE, errors="coerce")
    d["REF_DATE"] = d.REF_DATE.astype(int)
    def s(geo, concept, group, stat):
        m = d[(d.GEO == geo) & (d["Income concepts"] == concept) &
              (d["Income groups"] == group) & (d.Statistics == stat)]
        return m.set_index("REF_DATE").VALUE
    cg = "Total income with capital gains"
    top1 = "Top 1 percent income group"
    tax = "Average federal and provincial or territorial income taxes paid"
    out = pd.DataFrame({
        "sc_top1_share": s("Canada", cg, top1, "Share of income"),
        "sc_top1_avg_tax_rate": s("Canada", cg, top1, tax) / s("Canada", cg, top1, "Average income") * 100,
        "sc_top1_tax_share": s("Canada", cg, top1, "Share of federal and provincial or territorial income taxes paid"),
        "sc_top1_threshold": s("Canada", cg, top1, "Threshold value"),
        "sc_top001_avg_tax_rate": s("Canada", cg, "Top 0.01 percent income group", tax)
            / s("Canada", cg, "Top 0.01 percent income group", "Average income") * 100,
        "sc_b50_avg_tax_rate": s("Canada", cg, "Bottom 50 percent income group", tax)
            / s("Canada", cg, "Bottom 50 percent income group", "Average income") * 100,
    })
    # Sub-national rows use the *national* thresholds, so these read as
    # "Ottawa residents who are in Canada's top 1% / 10%".
    ott = "Ottawa-Gatineau, Ontario part, Ontario"
    n = lambda grp: s(ott, cg, grp, "Number of tax filers").iloc[-1]
    ottawa = {
        "year": int(d.REF_DATE.max()),
        "top1_threshold": r(s("Canada", cg, top1, "Threshold value").iloc[-1], 0),
        "top10_threshold": r(s("Canada", cg, "Top 10 percent income group", "Threshold value").iloc[-1], 0),
        "pct_in_top1": r(n(top1) / n("All tax filers") * 100, 2),
        "pct_in_top10": r(n("Top 10 percent income group") / n("All tax filers") * 100, 1),
        "top1_avg_income": r(s(ott, cg, top1, "Average income").iloc[-1], 0),
        "top1_income_share": r(s(ott, cg, top1, "Share of income").iloc[-1], 1),
    }
    return out, ottawa


def rates():
    f1 = pd.read_csv(SRC / "saez_veall_F1_marginal_rates.csv", comment="#").set_index("year")
    f2 = pd.read_csv(SRC / "saez_veall_F2_average_rates.csv", comment="#").set_index("year")
    rec = pd.read_csv(SRC / "top_rate_2001_2026.csv", comment="#").set_index("year")
    top = pd.concat([f1.top, rec.top])
    return pd.DataFrame({"top_rate": top, "p99_mtr": f1.p99, "sv_top1_avg_tax_rate": f2.p99_100,
                         "sv_top001_avg_tax_rate": f2.p99_99_100})


def growth(series, a, b):
    """Annualized real growth (%) between years a and b."""
    va, vb = series.get(a), series.get(b)
    if va is None or vb is None or pd.isna(va) or pd.isna(vb):
        return None
    return ((vb / va) ** (1 / (b - a)) - 1) * 100


def eras(df):
    spans = [(1950, 1960), (1960, 1970), (1970, 1980), (1980, 1990),
             (1990, 2000), (2000, 2010), (2010, 2019)]
    big = [(1950, 1980), (1980, 2019)]
    def row(a, b):
        return {
            "span": f"{a}–{b}", "a": a, "b": b,
            "avg_top_rate": r(df.top_rate.loc[a:b - 1].mean(), 1),
            "b50": r(growth(df.b50_inc, a, b)), "m40": r(growth(df.m40_inc, a, b)),
            "t10": r(growth(df.t10_inc, a, b)), "t1": r(growth(df.t1_inc, a, b)),
            "all": r(growth(df.all_inc, a, b)),
        }
    return [row(*s) for s in spans], [row(*s) for s in big]


def corr(df):
    """Pearson r on annual data, plus a 5-year-lagged version; and decade-level r
    for 'top rate vs bottom-50 growth' to show how few independent points exist."""
    out = {}
    a = df[["top_rate", "top1_share"]].dropna()
    out["rate_vs_top1_same_year"] = {"r": r(a.top_rate.corr(a.top1_share)), "n": len(a),
                                     "years": f"{a.index.min()}–{a.index.max()}"}
    lag = pd.DataFrame({"rate": df.top_rate.shift(5), "share": df.top1_share}).dropna()
    out["rate_vs_top1_lag5"] = {"r": r(lag.rate.corr(lag.share)), "n": len(lag)}
    post = a.loc[1946:]
    out["rate_vs_top1_postwar"] = {"r": r(post.top_rate.corr(post.top1_share)), "n": len(post),
                                   "years": f"{post.index.min()}–{post.index.max()}"}
    dec, _ = eras(df)
    x = np.array([e["avg_top_rate"] for e in dec]);
    for k in ("b50", "m40", "t1", "all"):
        y = np.array([e[k] for e in dec], dtype=float)
        out[f"decade_rate_vs_{k}_growth"] = {"r": r(np.corrcoef(x, y)[0, 1]), "n": len(dec)}
    # "Who gained more": bottom-50 growth minus top-1 growth, per decade.
    gap = np.array([e["b50"] - e["t1"] for e in dec])
    out["decade_rate_vs_b50_minus_t1"] = {"r": r(np.corrcoef(x, gap)[0, 1]), "n": len(dec)}
    return out


def donations():
    fsa = pd.read_csv(RAW / "cra_fsa_2021_tbl1a.csv", skiprows=2)
    fsa.columns = ["prov", "fsa", "filers", "total_income", "net_income", "taxable_income"]
    fsa = fsa[fsa.fsa.str.match(r"^[A-Z]\d[A-Z]$", na=False)].copy()
    fsa["filers"] = pd.to_numeric(fsa.filers, errors="coerce")
    fsa["total_income"] = pd.to_numeric(fsa.total_income, errors="coerce") * 1000   # $000s
    fsa = fsa[fsa.filers >= 500]                     # drop tiny/odd FSAs (PO boxes, institutions)
    fsa["avg_income"] = fsa.total_income / fsa.filers

    c = pd.read_csv(RAW / "ec_contrib_by_fsa.csv")
    c = c[c.year.isin(DONATION_YEARS)]
    total_all = c.amount.sum()
    item = c[c.fsa != "UNITEMIZED"]
    by_fsa = item.groupby("fsa").agg(amount=("amount", "sum"), n=("n", "sum"))
    by_fsa_party = item.pivot_table(index="fsa", columns="party", values="amount", aggfunc="sum", fill_value=0)

    j = fsa.set_index("fsa").join(by_fsa, how="left").fillna({"amount": 0, "n": 0})
    j = j.join(by_fsa_party, how="left").fillna(0)
    nyrs = len(DONATION_YEARS)
    j["per_filer"] = j.amount / j.filers / nyrs
    j["gifts_per_1k"] = j.n / j.filers / nyrs * 1000

    # Filer-weighted deciles of FSAs by average income: each decile ≈ 10% of tax filers.
    j = j.sort_values("avg_income")
    cum = j.filers.cumsum() / j.filers.sum()
    j["decile"] = np.minimum((cum * 10).apply(np.ceil).astype(int), 10)
    parties = ["Conservative", "Liberal", "NDP", "Green", "Bloc", "PPC", "Other"]
    dec = []
    for k, g in j.groupby("decile"):
        amt = g.amount.sum()
        dec.append({
            "decile": int(k),
            "income_lo": r(g.avg_income.min(), 0), "income_hi": r(g.avg_income.max(), 0),
            "avg_income": r(g.total_income.sum() / g.filers.sum(), 0),
            "filers": int(g.filers.sum()),
            "amount_share": r(amt / j.amount.sum() * 100, 1),
            "per_filer": r(amt / g.filers.sum() / nyrs, 2),
            "gifts_per_1k": r(g.n.sum() / g.filers.sum() / nyrs * 1000, 1),
            "party_share": {p: r(g[p].sum() / amt * 100, 1) if p in g and amt else 0 for p in parties},
        })
    rr = np.corrcoef(np.log(j.avg_income), j.per_filer)[0, 1]
    nk = j.drop(index="K1P", errors="ignore")             # downtown office FSA outlier
    rr_nk = np.corrcoef(np.log(nk.avg_income), nk.per_filer)[0, 1]
    rho = j.avg_income.rank().corr(j.per_filer.rank())

    ott = j[j.index.str.startswith(OTTAWA_PREFIXES)].copy()
    ott_rows = [{"fsa": f, "avg_income": r(x.avg_income, 0), "filers": int(x.filers),
                 "per_filer": r(x.per_filer, 2), "gifts_per_1k": r(x.gifts_per_1k, 1),
                 "top_party": max(parties, key=lambda p: x.get(p, 0)) if x.amount else None}
                for f, x in ott.sort_values("avg_income", ascending=False).iterrows()]
    scatter = [[f, r(x.avg_income, 0), r(x.per_filer, 2), int(x.filers), f.startswith(OTTAWA_PREFIXES)]
               for f, x in j.iterrows()]
    return {
        "years": f"{min(DONATION_YEARS)}–{max(DONATION_YEARS)}",
        "itemized_share_pct": r(item.amount.sum() / total_all * 100, 1),
        "total_amount": r(total_all, 0),
        "matched_amount_pct": r(j.amount.sum() / item.amount.sum() * 100, 1),
        "n_fsa": int(len(j)),
        "r_log_income_vs_per_filer": r(rr),
        "r_without_k1p": r(rr_nk),
        "spearman": r(rho),
        "deciles": dec,
        "ottawa": ott_rows,
        "scatter": scatter,
        "by_year": [{"year": int(y), "amount": r(a, 0)} for y, a in
                    pd.read_csv(RAW / "ec_contrib_by_fsa.csv").query("2004 <= year <= 2023")
                      .groupby("year").amount.sum().items()],
    }


def main():
    w = wid()
    sc, ottawa = statcan()
    df = rates().join(w, how="outer").join(sc, how="outer").loc[1920:2026]
    # Average rate actually paid: Saez-Veall through 2000, StatCan after (the
    # two agree within ~0.5 pt in 2000; they diverge in the early 1980s).
    df["paid_top1"] = df.sv_top1_avg_tax_rate.where(df.index <= 2000, df.sc_top1_avg_tax_rate)
    df["paid_top001"] = df.sv_top001_avg_tax_rate.where(df.index <= 2000, df.sc_top001_avg_tax_rate)
    dec, big = eras(df)
    cols = ["top_rate", "p99_mtr", "paid_top1", "paid_top001", "sc_b50_avg_tax_rate",
            "top1_share", "top10_share", "sc_top1_share", "sc_top1_tax_share",
            "b50_inc", "m40_inc", "t10_inc", "t1_inc", "ni_pa", "w_top1", "w_top10", "w_b50"]
    series = {"year": [int(y) for y in df.index]}
    for c in cols:
        series[c] = [r(v, 1 if "inc" not in c and c != "ni_pa" else 0) for v in df[c]]
    # Wealth before 1980 is sparse/imputed on WID — keep only the annual 1980+ run.
    for c in ("w_top1", "w_top10", "w_b50"):
        series[c] = [v if y >= 1980 else None for y, v in zip(series["year"], series[c])]
    out = {
        "built": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "series": series,
        "decades": dec, "eras": big,
        "corr": corr(df),
        "ottawa_top1": ottawa,
        "donations": donations(),
    }
    p = ROOT / "tax.json"
    p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote", p, f"{p.stat().st_size/1024:.0f} KB")
    print(json.dumps({k: out[k] for k in ("corr", "eras", "ottawa_top1")}, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in out["donations"].items() if k not in ("scatter", "ottawa", "by_year")}, indent=1, ensure_ascii=False)[:3500])


if __name__ == "__main__":
    main()

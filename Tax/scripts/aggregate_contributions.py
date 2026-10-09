"""Roll the Elections Canada contributions file (2.2 GB uncompressed) up to
year x party x entity type x FSA.

Input : Tax/data/raw/ec_contributions.zip  (od_cntrbtn_audt_e.csv, from
        https://www.elections.ca/fin/oda/od_cntrbtn_audt_e.zip)
Output: Tax/data/raw/ec_contrib_by_fsa.csv  (intermediate, gitignored —
        build_data.py reads it and writes the small committed JSON)

Only *individual* contributions are kept (corporate/union money has been
banned federally since 2007). Elections Canada itemizes contributors only
above $200, so rows without a postal code (the aggregated small gifts) are
counted separately as "unitemized" rather than dropped silently.
"""
import re
import zipfile
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
SRC = RAW / "ec_contributions.zip"
OUT = RAW / "ec_contrib_by_fsa.csv"

COLS = {
    "Political Entity": "entity",
    "Political Party of Recipient": "party",
    "Fiscal/Election date": "fiscal_date",
    "Contributor type": "ctype",
    "Contributor name": "name",
    "Contributor Province": "prov",
    "Contributor Postal code": "postal",
    "Contribution Received date": "recv_date",
    "Monetary amount": "amount",
}

FSA_RE = re.compile(r"^[A-Z]\d[A-Z]$")


def party_bucket(p):
    p = str(p)
    if "Liberal" in p: return "Liberal"
    if "Conservative" in p: return "Conservative"
    if "New Democratic" in p: return "NDP"
    if "Green" in p: return "Green"
    if "Bloc" in p: return "Bloc"
    if "People's Party" in p: return "PPC"
    return "Other"


def main():
    z = zipfile.ZipFile(SRC)
    name = [n for n in z.namelist() if n.endswith(".csv")][0]
    parts = []
    reader = pd.read_csv(z.open(name), usecols=list(COLS), dtype=str,
                         chunksize=400_000, encoding="utf-8-sig")
    for i, ch in enumerate(reader):
        ch = ch.rename(columns=COLS)
        ch = ch[ch.ctype == "Individuals"]
        # Year = date the contribution was received; fall back to the
        # fiscal period / election date for returns that omit it.
        yr = ch.recv_date.str[:4].where(ch.recv_date.notna(), ch.fiscal_date.str[:4])
        ch = ch.assign(
            year=pd.to_numeric(yr, errors="coerce"),
            amount=pd.to_numeric(ch.amount.str.strip(), errors="coerce").fillna(0),
            fsa=ch.postal.fillna("").str.upper().str.replace(" ", "").str[:3],
            party=ch.party.map(party_bucket),
        )
        ch.loc[~ch.fsa.str.match(FSA_RE), "fsa"] = "UNITEMIZED"
        # A donor = name + full postal code; good enough to count heads
        # without storing names in the output.
        ch["donor"] = ch.name.fillna("").str.upper().str.strip() + "|" + ch.postal.fillna("").str.replace(" ", "")
        g = ch.groupby(["year", "party", "entity", "fsa"]).agg(
            amount=("amount", "sum"), n=("amount", "size"),
            donors=("donor", lambda s: frozenset(s)))
        parts.append(g)
        print(f"chunk {i}: {len(ch):,} individual rows", flush=True)

    allg = pd.concat(parts)
    # Merge chunks: sum money/rows, union donor sets, then count.
    out = allg.groupby(level=[0, 1, 2, 3]).agg(
        amount=("amount", "sum"), n=("n", "sum"),
        donors=("donors", lambda s: len(frozenset().union(*s))))
    out.reset_index().to_csv(OUT, index=False)
    print("wrote", OUT, len(out))


if __name__ == "__main__":
    main()

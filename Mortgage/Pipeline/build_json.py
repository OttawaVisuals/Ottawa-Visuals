"""
build_json.py

Converts static CSVs + Ottawa live CSVs into JSON files for the mortgage calculator.

Run locally:   python Mortgage/Pipeline/build_json.py
Run by CI:     same command, from repo root

Input (static):
  Mortgage/Static/fsa_to_crea.csv
  Mortgage/Static/income_by_fsa.csv
  Mortgage/Static/income_by_province.csv
  Mortgage/Static/income_canada.csv
  Mortgage/Static/crea_benchmarks_latest.csv
  Mortgage/Static/crea_benchmarks_history.csv

Input (Ottawa, auto-updated weekly):
  data/price_point_breakdown.csv
  data/freehold.csv
  data/condos.csv

Output:
  Mortgage/JSON/fsa_index.json
  Mortgage/JSON/income_by_fsa.json
  Mortgage/JSON/crea_benchmarks.json
  Mortgage/JSON/ottawa_sales.json
"""

import json
import os
import re
import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).resolve().parent.parent.parent  # repo root
STATIC  = ROOT / "Mortgage" / "Static"
OTTAWA  = ROOT / "data"
OUT     = ROOT / "Mortgage" / "JSON"

OUT.mkdir(parents=True, exist_ok=True)

def write_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    size_kb = os.path.getsize(path) / 1024
    print(f"  ✓ {path.name}  ({size_kb:.0f} KB,  {len(data)} entries)")

# ── 1. fsa_index.json ─────────────────────────────────────────────────────────
# FSA → {province, cma, cma_type, crea_board}
# Used for the instant lookup when user types their postal code

print("Building fsa_index.json...")
df = pd.read_csv(STATIC / "fsa_to_crea.csv", encoding="utf-8")
df = df.fillna("")

fsa_index = {}
for _, row in df.iterrows():
    fsa_index[row["FSA"]] = {
        "province":  row["Province"],
        "cma":       row["CMA"],
        "cma_type":  row["CMA_TYPE"],
        "crea_board": row["CREA_BOARD"],
    }

write_json(fsa_index, OUT / "fsa_index.json")

# ── 2. income_by_fsa.json ─────────────────────────────────────────────────────
# FSA → {total, cumulative bracket counts, province, cma, crea_board}
# Cumulative counts allow JS to compute percentiles without any Python logic

print("Building income_by_fsa.json...")
df = pd.read_csv(STATIC / "income_by_fsa.csv", encoding="utf-8")
df = df.fillna("")

# Identify cumulative columns (start with "Cum_")
cum_cols = [c for c in df.columns if c.startswith("Cum_")]

income_fsa = {}
for _, row in df.iterrows():
    income_fsa[row["FSA"]] = {
        "province":   row["Province"],
        "cma":        row["CMA"],
        "crea_board": row["CREA_BOARD"],
        "total":      int(row["Total_Filers"]) if row["Total_Filers"] else 0,
        # Array of cumulative counts in bracket order (Under $5K → over $250K)
        "cum": [int(row[c]) if row[c] != "" else 0 for c in cum_cols],
    }

write_json(income_fsa, OUT / "income_by_fsa.json")

# ── 3. income_canada.json (province + national) ───────────────────────────────
# Separate small file: province-level + Canada totals
# Kept separate so fsa file stays lean

print("Building income_canada.json...")

prov_df = pd.read_csv(STATIC / "income_by_province.csv", encoding="utf-8").fillna("")
can_df  = pd.read_csv(STATIC / "income_canada.csv",      encoding="utf-8").fillna("")

cum_cols_prov = [c for c in prov_df.columns if c.startswith("Cum_")]
cum_cols_can  = [c for c in can_df.columns  if c.startswith("Cum_")]

income_canada = {"provinces": {}, "canada": {}}

for _, row in prov_df.iterrows():
    income_canada["provinces"][row["Province"]] = {
        "total": int(row["Total_Filers"]) if row["Total_Filers"] else 0,
        "cum":   [int(row[c]) if row[c] != "" else 0 for c in cum_cols_prov],
    }

can_row = can_df.iloc[0]
income_canada["canada"] = {
    "total": int(can_row["Total_Filers"]) if can_row["Total_Filers"] else 0,
    "cum":   [int(can_row[c]) if can_row[c] != "" else 0 for c in cum_cols_can],
}

write_json(income_canada, OUT / "income_canada.json")

# ── 4. crea_benchmarks.json ───────────────────────────────────────────────────
# board → {latest prices, yoy change, full history for affordability chart}

print("Building crea_benchmarks.json...")

latest_df  = pd.read_csv(STATIC / "crea_benchmarks_latest.csv",  encoding="utf-8").fillna("")
history_df = pd.read_csv(STATIC / "crea_benchmarks_history.csv", encoding="utf-8").fillna("")

# Build full history per board (needed for affordability timeline chart)
history_24 = {}
for board, grp in history_df.groupby("CREA_BOARD"):
    grp = grp.sort_values("Date")
    history_24[board] = [
        {
            "date":      row["Date"],
            "composite": int(row["Composite_Benchmark"]) if row["Composite_Benchmark"] != "" else None,
            "sfh":       int(row["Single_Family_Benchmark"]) if row["Single_Family_Benchmark"] != "" else None,
            "townhouse": int(row["Townhouse_Benchmark"]) if row["Townhouse_Benchmark"] != "" else None,
            "apartment": int(row["Apartment_Benchmark"]) if row["Apartment_Benchmark"] != "" else None,
        }
        for _, row in grp.iterrows()
    ]

crea = {}
for _, row in latest_df.iterrows():
    board = row["CREA_BOARD"]

    def val(col):
        v = row.get(col, "")
        return int(float(v)) if v != "" else None

    crea[board] = {
        "updated":     row["Last_Updated"],
        "composite":   val("Composite_Benchmark"),
        "sfh":         val("Single_Family_Benchmark"),
        "townhouse":   val("Townhouse_Benchmark"),
        "apartment":   val("Apartment_Benchmark"),
        "yoy_pct":     float(row["Composite_YoY_Pct"]) if row["Composite_YoY_Pct"] != "" else None,
        "history":     history_24.get(board, []),
    }

write_json(crea, OUT / "crea_benchmarks.json")

# ── 5. ottawa_sales.json ──────────────────────────────────────────────────────
# Weekly price bracket distribution — the key Ottawa-specific data
# Allows: "X% of Ottawa freehold homes sold under $900K last 12 months"

print("Building ottawa_sales.json...")

def parse_price(s):
    """Extract integer dollar value from strings like ' $ 746,492 '"""
    if not isinstance(s, str):
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None

def parse_pct(s):
    if not isinstance(s, str):
        return None
    try:
        return round(float(s.replace("%", "")), 2)
    except:
        return None

# Price point breakdown (the most useful for affordability %)
ppb = pd.read_csv(OTTAWA / "price_point_breakdown.csv", encoding="utf-8")
ppb.columns = ppb.columns.str.strip()

# Freehold and condo summary stats
freehold = pd.read_csv(OTTAWA / "freehold.csv", encoding="utf-8")
condos   = pd.read_csv(OTTAWA / "condos.csv",   encoding="utf-8")
freehold.columns = freehold.columns.str.strip()
condos.columns   = condos.columns.str.strip()

# Date column name may vary — find it
def date_col(df):
    return next((c for c in df.columns if "date" in c.lower()), df.columns[0])

ottawa = {"price_brackets": [], "freehold": [], "condos": []}

# Price point breakdown rows
for _, row in ppb.iterrows():
    date = str(row.iloc[0]).strip()
    if not date or date == "nan" or not re.match(r"\d", date.replace("-","").replace("/","")):
        continue
    try:
        ottawa["price_brackets"].append({
            "date": date,
            # Freehold brackets
            "fh_0_249":   int(row.iloc[1])  if pd.notna(row.iloc[1])  else 0,
            "fh_250_499": int(row.iloc[2])  if pd.notna(row.iloc[2])  else 0,
            "fh_500_749": int(row.iloc[3])  if pd.notna(row.iloc[3])  else 0,
            "fh_750_999": int(row.iloc[4])  if pd.notna(row.iloc[4])  else 0,
            "fh_1m_2m":   int(row.iloc[5])  if pd.notna(row.iloc[5])  else 0,
            "fh_2m_plus": int(row.iloc[6])  if pd.notna(row.iloc[6])  else 0,
            "fh_total":   int(row.iloc[7])  if pd.notna(row.iloc[7])  else 0,
            # Condo brackets
            "co_0_249":   int(row.iloc[8])  if pd.notna(row.iloc[8])  else 0,
            "co_250_499": int(row.iloc[9])  if pd.notna(row.iloc[9])  else 0,
            "co_500_749": int(row.iloc[10]) if pd.notna(row.iloc[10]) else 0,
            "co_750_999": int(row.iloc[11]) if pd.notna(row.iloc[11]) else 0,
            "co_1m_2m":   int(row.iloc[12]) if pd.notna(row.iloc[12]) else 0,
            "co_2m_plus": int(row.iloc[13]) if pd.notna(row.iloc[13]) else 0,
            "co_total":   int(row.iloc[14]) if pd.notna(row.iloc[14]) else 0,
        })
    except Exception:
        continue

# Freehold weekly stats
dc = date_col(freehold)
for _, row in freehold.iterrows():
    date = str(row[dc]).strip()
    if not date or date == "nan":
        continue
    try:
        ottawa["freehold"].append({
            "date":         date,
            "active":       int(row.iloc[2]) if pd.notna(row.iloc[2]) else None,
            "sold":         int(row.iloc[4]) if pd.notna(row.iloc[4]) else None,
            "avg_sold":     parse_price(str(row.iloc[6])),
            "median_sold":  parse_price(str(row.iloc[11])),
            "avg_dom":      int(row.iloc[8]) if pd.notna(row.iloc[8]) else None,
            "list_sold_pct": parse_pct(str(row.iloc[7])),
        })
    except Exception:
        continue

# Condo weekly stats
dc = date_col(condos)
for _, row in condos.iterrows():
    date = str(row[dc]).strip()
    if not date or date == "nan":
        continue
    try:
        ottawa["condos"].append({
            "date":         date,
            "active":       int(row.iloc[2]) if pd.notna(row.iloc[2]) else None,
            "sold":         int(row.iloc[4]) if pd.notna(row.iloc[4]) else None,
            "avg_sold":     parse_price(str(row.iloc[6])),
            "median_sold":  parse_price(str(row.iloc[11])),
            "avg_dom":      int(row.iloc[8]) if pd.notna(row.iloc[8]) else None,
            "list_sold_pct": parse_pct(str(row.iloc[7])),
        })
    except Exception:
        continue

write_json(ottawa, OUT / "ottawa_sales.json")

# ── Summary ───────────────────────────────────────────────────────────────────

print()
print("All JSON files written to Mortgage/JSON/")
print(f"  Price bracket weeks: {len(ottawa['price_brackets'])}")
print(f"  Freehold weeks:      {len(ottawa['freehold'])}")
print(f"  Condo weeks:         {len(ottawa['condos'])}")


# ── 6. cpi.json ───────────────────────────────────────────────────────────────
# Annual all-items CPI for Canada, used for the affordability timeline chart

print("Building cpi.json...")

CPI_CSV = ROOT / "data" / "cpi_canada.csv"

cpi_out = {}

if CPI_CSV.exists():
    cpi_df = pd.read_csv(CPI_CSV, encoding="latin-1")

    # StatCan table 18-10-0004-01 column names:
    # REF_DATE, GEO, DGUID, Products and product groups, UOM, UOM_ID,
    # SCALAR_FACTOR, SCALAR_ID, VECTOR, COORDINATE, VALUE, STATUS, SYMBOL,
    # TERMINATED, DECIMALS

    # Filter: Canada, All-items, annual (REF_DATE is YYYY-MM — take December
    # each year as the year-end value, or annual average if available)
    mask = (
        (cpi_df["GEO"] == "Canada") &
        (cpi_df["Products and product groups"].str.strip() == "All-items")
    )
    filtered = cpi_df[mask].copy()
    filtered["year"] = filtered["REF_DATE"].astype(str).str[:4].astype(int)
    filtered["month"] = filtered["REF_DATE"].astype(str).str[5:7].astype(int)

    # Use December value as year-end CPI; fall back to last available month
    for year, grp in filtered.groupby("year"):
        if year < 2000:
            continue
        dec = grp[grp["month"] == 12]
        row = dec if not dec.empty else grp.sort_values("month").tail(1)
        val = row["VALUE"].iloc[0]
        if pd.notna(val):
            cpi_out[str(year)] = round(float(val), 1)

    print(f"  Found CPI data for {len(cpi_out)} years "
          f"({min(cpi_out.keys())}–{max(cpi_out.keys())})")
else:
    # Fallback hardcoded values if CSV not yet available
    print("  WARNING: cpi_canada.csv not found — using hardcoded fallback values")
    cpi_out = {
        "2000": 95.4,  "2001": 97.8,  "2002": 100.0, "2003": 102.8,
        "2004": 104.7, "2005": 107.0, "2006": 109.1, "2007": 111.5,
        "2008": 114.1, "2009": 114.4, "2010": 116.5, "2011": 119.9,
        "2012": 121.7, "2013": 122.8, "2014": 125.2, "2015": 126.6,
        "2016": 128.4, "2017": 130.4, "2018": 133.4, "2019": 136.0,
        "2020": 137.0, "2021": 141.6, "2022": 151.2, "2023": 158.1,
        "2024": 162.4,
    }

write_json(cpi_out, OUT / "cpi.json")

# ── 7. census_fsa.json ────────────────────────────────────────────────────────
# 2021 Census data per FSA: income distribution brackets, demographics,
# language, housing, education, commute.
# Source CSV generated by extract_census_fsa.py from StatCan 98-401-X2021013.
#
# Bracket labels are embedded in the JSON so the JS never needs to hardcode them.
# Total income:      <10K|10-20K|...|100-150K|150K+   (12 buckets, all pop 15+)
# Employment income: <10K|10-20K|...|100-125K|125K+   (12 buckets, workers only)
# Dwelling type:     Detached|Semi-detached|Row|Duplex|Apt<5|Apt5+|OtherAttached|Movable
 
print("Building census_fsa.json...")
 
CENSUS_CSV = STATIC / "census_fsa_2021.csv"
 
TOTAL_INC_LABELS = ['<10K','10-20K','20-30K','30-40K','40-50K','50-60K',
                    '60-70K','70-80K','80-90K','90-100K','100-150K','150K+']
EMP_INC_LABELS   = ['<10K','10-20K','20-30K','30-40K','40-50K','50-60K',
                    '60-70K','70-80K','80-90K','90-100K','100-125K','125K+']
DWELL_LABELS     = ['Detached','Semi-detached','Row','Duplex',
                    'Apt<5','Apt5+','OtherAttached','Movable']
 
def parse_pipe_int(s, n):
    if not s:
        return [None] * n
    parts = s.split('|')
    result = []
    for p in parts:
        p = p.strip()
        try:
            result.append(int(float(p)) if p else None)
        except:
            result.append(None)
    return result
 
def parse_pipe_float(s, n):
    if not s:
        return [None] * n
    parts = s.split('|')
    result = []
    for p in parts:
        p = p.strip()
        try:
            result.append(round(float(p), 2) if p else None)
        except:
            result.append(None)
    return result
 
def intorNone(v):
    try:
        f = float(v)
        return int(f) if not pd.isna(f) else None
    except:
        return None
 
def floatorNone(v, dec=1):
    try:
        f = float(v)
        return round(f, dec) if not pd.isna(f) else None
    except:
        return None
 
census_df = pd.read_csv(CENSUS_CSV, encoding='utf-8').fillna('')
 
census_fsa = {}
for _, row in census_df.iterrows():
    fsa = str(row['fsa']).strip().upper()
    if not fsa:
        continue
 
    census_fsa[fsa] = {
        # Identity
        "geo_name":        row['geo_name'],
        "province":        row['province_letter'],
 
        # Population
        "population":      intorNone(row['population_2021']),
        "pop_change_pct":  floatorNone(row['pop_change_pct']),
        "median_age":      floatorNone(row['median_age']),
 
        # Age breakdown (%)
        "pct_under_15":    floatorNone(row['pct_under_15']),
        "pct_15_to_64":    floatorNone(row['pct_15_to_64']),
        "pct_65_plus":     floatorNone(row['pct_65_plus']),
 
        # Household
        "avg_household_size": floatorNone(row['avg_household_size']),
        "pct_owners":      floatorNone(row['pct_owners']),
        "pct_renters":     floatorNone(row['pct_renters']),
 
        # Individual income
        "median_total_income":      intorNone(row['median_total_income_individual']),
        "avg_total_income":         intorNone(row['avg_total_income_individual']),
        "median_employment_income": intorNone(row['median_employment_income_individual']),
        "avg_employment_income":    intorNone(row['avg_employment_income_individual']),
        "median_emp_income_fyft":   intorNone(row['median_employment_income_fyft']),
        "avg_emp_income_fyft":      intorNone(row['avg_employment_income_fyft']),
 
        # Household income
        "median_household_income":   intorNone(row['median_household_total_income']),
        "avg_household_income":      intorNone(row['avg_household_total_income']),
        "median_household_aftertax": intorNone(row['median_household_aftertax_income']),
 
        # Low income
        "pct_low_income": floatorNone(row['pct_low_income_lim_at']),
 
        # Housing
        "median_dwelling_value":       intorNone(row['median_dwelling_value']),
        "pct_shelter_cost_burdened":   floatorNone(row['pct_spending_30pct_plus_on_shelter']),
 
        # Language (knowledge of official languages, %)
        "pct_english_only": floatorNone(row['pct_english_only']),
        "pct_french_only":  floatorNone(row['pct_french_only']),
        "pct_bilingual":    floatorNone(row['pct_bilingual']),
        "pct_neither_lang": floatorNone(row['pct_neither_lang']),
 
        # Education (%)
        "pct_postsecondary":  floatorNone(row['pct_postsecondary']),
        "pct_bachelors_plus": floatorNone(row['pct_bachelors_plus']),
 
        # Labour (%)
        "pct_employed":   floatorNone(row['pct_employed']),
        "pct_unemployed": floatorNone(row['pct_unemployed']),
 
        # Commute (%)
        "pct_commute_car":     floatorNone(row['pct_commute_car']),
        "pct_commute_transit": floatorNone(row['pct_commute_transit']),
        "pct_commute_walk":    floatorNone(row['pct_commute_walk']),
        "avg_commute_min":     floatorNone(row['avg_commute_minutes_est']),
 
        # Immigration / diversity (%)
        "pct_immigrant":        floatorNone(row['pct_immigrant']),
        "pct_visible_minority": floatorNone(row['pct_visible_minority']),
 
        # ── Income distribution — total income (all sources, pop 15+) ──────────
        "total_inc_labels": TOTAL_INC_LABELS,
        "total_inc_base":   intorNone(row['inc_total_base']),
        "total_inc_no_income": intorNone(row['inc_without_income']),
        "total_inc_count":  parse_pipe_int(row['inc_brackets_count'], 12),
        "total_inc_pct":    parse_pipe_float(row['inc_brackets_pct'], 12),
 
        # ── Income distribution — employment income (workers only) ─────────────
        "emp_inc_labels":   EMP_INC_LABELS,
        "emp_inc_base":     intorNone(row['emp_total_base']),
        "emp_inc_no_income": intorNone(row['emp_without_income']),
        "emp_inc_workers":  intorNone(row['emp_with_income']),
        "emp_inc_count":    parse_pipe_int(row['emp_brackets_count'], 12),
        "emp_inc_pct":      parse_pipe_float(row['emp_brackets_pct'], 12),
 
        # ── Dwelling type breakdown ────────────────────────────────────────────
        "dwell_labels": DWELL_LABELS,
        "dwell_total":  intorNone(row['dwell_total']),
        "dwell_count":  parse_pipe_int(row['dwell_count'], 8),
        "dwell_pct":    parse_pipe_float(row['dwell_pct'], 8),
    }
 
write_json(census_fsa, OUT / "census_fsa.json")

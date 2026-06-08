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
  Mortgage/Static/fsa.csv           ← from extract_census.py
  Mortgage/Static/province.csv      ← from extract_census.py
  Mortgage/Static/canada.csv        ← from extract_census.py

Input (Ottawa, auto-updated weekly):
  data/price_point_breakdown.csv
  data/freehold.csv
  data/condos.csv

Output:
  Mortgage/JSON/fsa_index.json
  Mortgage/JSON/income_by_fsa.json
  Mortgage/JSON/crea_benchmarks.json
  Mortgage/JSON/ottawa_sales.json
  Mortgage/JSON/cpi.json
  Mortgage/JSON/census_fsa.json
  Mortgage/JSON/census_province.json
  Mortgage/JSON/census_canada.json
"""

import json
import os
import re
import math
import pandas as pd
import numpy as np
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
    n = len(data) if hasattr(data, '__len__') else '—'
    print(f"  ✓ {path.name}  ({size_kb:.0f} KB,  {n} entries)")

def safe_int(v):
    try:
        f = float(v)
        return int(f) if not (math.isnan(f) or math.isinf(f)) else None
    except (TypeError, ValueError):
        return None

def safe_float(v, dec=1):
    try:
        f = float(v)
        return round(f, dec) if not (math.isnan(f) or math.isinf(f)) else None
    except (TypeError, ValueError):
        return None

def safe_pct(num, denom, dec=1):
    """Compute pct = num/denom*100, return None if denom is 0/None."""
    n, d = safe_float(num, 6), safe_float(denom, 6)
    if n is None or d is None or d == 0:
        return None
    return round(n / d * 100, dec)

# ── 1. fsa_index.json ─────────────────────────────────────────────────────────

print("Building fsa_index.json...")
df = pd.read_csv(STATIC / "fsa_to_crea.csv", encoding="utf-8").fillna("")

fsa_index = {}
for _, row in df.iterrows():
    fsa_index[row["FSA"]] = {
        "province":   row["Province"],
        "cma":        row["CMA"],
        "cma_type":   row["CMA_TYPE"],
        "crea_board": row["CREA_BOARD"],
    }

write_json(fsa_index, OUT / "fsa_index.json")

# ── 2. income_by_fsa.json ─────────────────────────────────────────────────────

print("Building income_by_fsa.json...")
df = pd.read_csv(STATIC / "income_by_fsa.csv", encoding="utf-8").fillna("")
cum_cols = [c for c in df.columns if c.startswith("Cum_")]

income_fsa = {}
for _, row in df.iterrows():
    income_fsa[row["FSA"]] = {
        "province":   row["Province"],
        "cma":        row["CMA"],
        "crea_board": row["CREA_BOARD"],
        "total":      int(row["Total_Filers"]) if row["Total_Filers"] else 0,
        "cum":        [int(row[c]) if row[c] != "" else 0 for c in cum_cols],
    }

write_json(income_fsa, OUT / "income_by_fsa.json")

# ── 3. income_canada.json ─────────────────────────────────────────────────────

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

print("Building crea_benchmarks.json...")

latest_df  = pd.read_csv(STATIC / "crea_benchmarks_latest.csv",  encoding="utf-8").fillna("")
history_df = pd.read_csv(STATIC / "crea_benchmarks_history.csv", encoding="utf-8").fillna("")

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
        "updated":   row["Last_Updated"],
        "composite": val("Composite_Benchmark"),
        "sfh":       val("Single_Family_Benchmark"),
        "townhouse": val("Townhouse_Benchmark"),
        "apartment": val("Apartment_Benchmark"),
        "yoy_pct":   float(row["Composite_YoY_Pct"]) if row["Composite_YoY_Pct"] != "" else None,
        "history":   history_24.get(board, []),
    }

write_json(crea, OUT / "crea_benchmarks.json")

# ── 5. ottawa_sales.json ──────────────────────────────────────────────────────

print("Building ottawa_sales.json...")

def parse_price(s):
    if not isinstance(s, str):
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None

def parse_pct(s):
    if not isinstance(s, str):
        return None
    try:
        return round(float(s.replace("%", "")), 2)
    except Exception:
        return None

ppb      = pd.read_csv(OTTAWA / "price_point_breakdown.csv", encoding="utf-8")
freehold = pd.read_csv(OTTAWA / "freehold.csv", encoding="utf-8")
condos   = pd.read_csv(OTTAWA / "condos.csv",   encoding="utf-8")
ppb.columns      = ppb.columns.str.strip()
freehold.columns = freehold.columns.str.strip()
condos.columns   = condos.columns.str.strip()

def date_col(df):
    return next((c for c in df.columns if "date" in c.lower()), df.columns[0])

ottawa = {"price_brackets": [], "freehold": [], "condos": []}

for _, row in ppb.iterrows():
    date = str(row.iloc[0]).strip()
    if not date or date == "nan" or not re.match(r"\d", date.replace("-","").replace("/","")):
        continue
    try:
        ottawa["price_brackets"].append({
            "date":       date,
            "fh_0_249":   int(row.iloc[1])  if pd.notna(row.iloc[1])  else 0,
            "fh_250_499": int(row.iloc[2])  if pd.notna(row.iloc[2])  else 0,
            "fh_500_749": int(row.iloc[3])  if pd.notna(row.iloc[3])  else 0,
            "fh_750_999": int(row.iloc[4])  if pd.notna(row.iloc[4])  else 0,
            "fh_1m_2m":   int(row.iloc[5])  if pd.notna(row.iloc[5])  else 0,
            "fh_2m_plus": int(row.iloc[6])  if pd.notna(row.iloc[6])  else 0,
            "fh_total":   int(row.iloc[7])  if pd.notna(row.iloc[7])  else 0,
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

dc = date_col(freehold)
for _, row in freehold.iterrows():
    date = str(row[dc]).strip()
    if not date or date == "nan":
        continue
    try:
        ottawa["freehold"].append({
            "date":          date,
            "active":        int(row.iloc[2]) if pd.notna(row.iloc[2]) else None,
            "sold":          int(row.iloc[4]) if pd.notna(row.iloc[4]) else None,
            "avg_sold":      parse_price(str(row.iloc[6])),
            "median_sold":   parse_price(str(row.iloc[11])),
            "avg_dom":       int(row.iloc[8]) if pd.notna(row.iloc[8]) else None,
            "list_sold_pct": parse_pct(str(row.iloc[7])),
        })
    except Exception:
        continue

dc = date_col(condos)
for _, row in condos.iterrows():
    date = str(row[dc]).strip()
    if not date or date == "nan":
        continue
    try:
        ottawa["condos"].append({
            "date":          date,
            "active":        int(row.iloc[2]) if pd.notna(row.iloc[2]) else None,
            "sold":          int(row.iloc[4]) if pd.notna(row.iloc[4]) else None,
            "avg_sold":      parse_price(str(row.iloc[6])),
            "median_sold":   parse_price(str(row.iloc[11])),
            "avg_dom":       int(row.iloc[8]) if pd.notna(row.iloc[8]) else None,
            "list_sold_pct": parse_pct(str(row.iloc[7])),
        })
    except Exception:
        continue

write_json(ottawa, OUT / "ottawa_sales.json")

print(f"  Price bracket weeks: {len(ottawa['price_brackets'])}")
print(f"  Freehold weeks:      {len(ottawa['freehold'])}")
print(f"  Condo weeks:         {len(ottawa['condos'])}")

# ── 6. cpi.json ───────────────────────────────────────────────────────────────

print("Building cpi.json...")
CPI_CSV = ROOT / "data" / "cpi_canada.csv"
cpi_out = {}

if CPI_CSV.exists():
    cpi_df   = pd.read_csv(CPI_CSV, encoding="latin-1")
    mask     = (
        (cpi_df["GEO"] == "Canada") &
        (cpi_df["Products and product groups"].str.strip() == "All-items")
    )
    filtered = cpi_df[mask].copy()
    filtered["year"]  = filtered["REF_DATE"].astype(str).str[:4].astype(int)
    filtered["month"] = filtered["REF_DATE"].astype(str).str[5:7].astype(int)
    for year, grp in filtered.groupby("year"):
        if year < 2000:
            continue
        dec = grp[grp["month"] == 12]
        row = dec if not dec.empty else grp.sort_values("month").tail(1)
        v   = row["VALUE"].iloc[0]
        if pd.notna(v):
            cpi_out[str(year)] = round(float(v), 1)
    print(f"  CPI data for {len(cpi_out)} years ({min(cpi_out.keys())}–{max(cpi_out.keys())})")
else:
    print("  WARNING: cpi_canada.csv not found — using hardcoded fallback")
    cpi_out = {
        "2000":95.4,"2001":97.8,"2002":100.0,"2003":102.8,"2004":104.7,
        "2005":107.0,"2006":109.1,"2007":111.5,"2008":114.1,"2009":114.4,
        "2010":116.5,"2011":119.9,"2012":121.7,"2013":122.8,"2014":125.2,
        "2015":126.6,"2016":128.4,"2017":130.4,"2018":133.4,"2019":136.0,
        "2020":137.0,"2021":141.6,"2022":151.2,"2023":158.1,"2024":162.4,
    }

write_json(cpi_out, OUT / "cpi.json")

# ── 7. census_fsa.json / census_province.json / census_canada.json ────────────
# Reads fsa.csv / province.csv / canada.csv (wide format from extract_census.py)
# and builds three JSON files: one per FSA, one per province, one for Canada.
#
# Computed fields (percentages, distributions) are derived here rather than
# pre-computing in extract_census.py to keep that script simple.
#
# NON-AGGREGATABLE columns (medians, averages, rates) arrive as NaN in
# province.csv and canada.csv — we emit null in JSON for those.
# ─────────────────────────────────────────────────────────────────────────────

print("Building census JSON files...")

FSA_CSV  = STATIC / "fsa.csv"
PROV_CSV = STATIC / "province.csv"
CAN_CSV  = STATIC / "canada.csv"

# ── Column name mappings (matching extract_census.py METRICS dict) ────────────
# Dwelling type order for charts
DWELL_LABELS = ["Detached","Semi-detached","Row","Duplex","Apt<5","Apt5+","Other","Movable"]
DWELL_COLS   = ["dwell_single_detached","dwell_semi_detached","dwell_row_house",
                "dwell_duplex","dwell_apt_low_rise","dwell_apt_high_rise",
                "dwell_other_attached","dwell_movable"]

# Household income distribution labels and columns (20 buckets)
HH_INC_LABELS = ["<$5K","$5–10K","$10–15K","$15–20K","$20–25K","$25–30K",
                  "$30–35K","$35–40K","$40–45K","$45–50K","$50–60K","$60–70K",
                  "$70–80K","$80–90K","$90–100K","$100–125K","$125–150K",
                  "$150–200K","$200K+"]
HH_INC_COLS   = ["hh_income_under5k","hh_income_5k_10k","hh_income_10k_15k",
                  "hh_income_15k_20k","hh_income_20k_25k","hh_income_25k_30k",
                  "hh_income_30k_35k","hh_income_35k_40k","hh_income_40k_45k",
                  "hh_income_45k_50k","hh_income_50k_60k","hh_income_60k_70k",
                  "hh_income_70k_80k","hh_income_80k_90k","hh_income_90k_100k",
                  "hh_income_100k_125k","hh_income_125k_150k",
                  "hh_income_150k_200k","hh_income_200k_plus"]

# Education labels (for 25–64 cohort) and columns
EDU_LABELS = ["No cert.","High school","Trades","College","Bachelor","Master","Doctorate"]
EDU_COLS   = ["edu_no_cert","edu_highschool","edu_trades","edu_college",
              "edu_bachelor","edu_masters","edu_doctorate"]

# Commute mode
COMMUTE_MODE_LABELS = ["Car/truck","Transit","Walk","Bicycle","Other"]
COMMUTE_MODE_COLS   = ["commute_car_truck_van","commute_transit","commute_walk",
                       "commute_bicycle","commute_other"]

# Commute duration
COMMUTE_DUR_LABELS = ["<15 min","15–29","30–44","45–59","60+ min"]
COMMUTE_DUR_COLS   = ["commute_under15","commute_15_29","commute_30_44",
                      "commute_45_59","commute_60plus"]

# Age groups (broad — fine bins stored separately for pyramid)
AGE_LABELS = ["0–4","5–9","10–14","15–19","20–24","25–29","30–34","35–39",
              "40–44","45–49","50–54","55–59","60–64","65–69","70–74",
              "75–79","80–84","85+"]
AGE_COLS   = ["age_0_4","age_5_9","age_10_14","age_15_19","age_20_24",
              "age_25_29","age_30_34","age_35_39","age_40_44","age_45_49",
              "age_50_54","age_55_59","age_60_64","age_65_69","age_70_74",
              "age_75_79","age_80_84","age_85_plus"]

# Construction period
CONSTR_LABELS = ["≤1960","1961–80","1981–90","1991–00","2001–05",
                 "2006–10","2011–15","2016–21"]
CONSTR_COLS   = ["construction_1960_or_before","construction_1961_1980",
                 "construction_1981_1990","construction_1991_2000",
                 "construction_2001_2005","construction_2006_2010",
                 "construction_2011_2015","construction_2016_2021"]

# Language
LANG_LABELS = ["English only","French only","Bilingual","Neither"]
LANG_COLS   = ["lang_english_only","lang_french_only","lang_bilingual","lang_neither"]

# Tenure
TENURE_LABELS = ["Owner","Renter","Other"]
TENURE_COLS   = ["tenure_owner","tenure_renter"]  # "Other" inferred

# Visible minority
VISMIN_LABELS = ["Visible minority","Not visible minority"]
VISMIN_COLS   = ["vismin_visible_minority","vismin_not_visible_minority"]

# Mobility (5 yr)
MOBILITY_LABELS = ["Non-movers","Non-migrants","Migrants"]
MOBILITY_COLS   = ["mobility5_nonmovers","mobility5_nonmigrants","mobility5_migrants"]

# ── Helper: build distribution list (counts + pcts) from a row ───────────────
def dist(row, cols, total_col, labels):
    """Return {labels, counts, pcts} from a DataFrame row."""
    total = safe_float(row.get(total_col), 6)
    counts, pcts = [], []
    for c in cols:
        v = safe_int(row.get(c))
        counts.append(v)
        pcts.append(safe_pct(v, total) if total else None)
    return {"labels": labels, "counts": counts, "pcts": pcts}

def tenure_dist(row):
    """Tenure with inferred 'other' segment."""
    total = safe_float(row.get("tenure_total"), 6) or 0
    owner  = safe_int(row.get("tenure_owner"))  or 0
    renter = safe_int(row.get("tenure_renter")) or 0
    other  = max(int(total) - owner - renter, 0) if total else 0
    counts = [owner, renter, other]
    pcts   = [safe_pct(v, total) for v in counts]
    return {"labels": TENURE_LABELS, "counts": counts, "pcts": pcts}

# ── Helper: build the compact scalar KPIs for a row ──────────────────────────
def build_scalars(row):
    """All single-value KPIs — returns a flat dict."""
    pop           = safe_int(row.get("pop_2021"))
    hh_total      = safe_int(row.get("hh_total"))
    tenure_total  = safe_float(row.get("tenure_total"), 6)
    owner         = safe_int(row.get("tenure_owner"))
    renter        = safe_int(row.get("tenure_renter"))
    labour_total  = safe_float(row.get("labour_total"), 6)
    employed      = safe_int(row.get("labour_employed"))
    unemployed    = safe_int(row.get("labour_unemployed"))
    in_force      = safe_int(row.get("labour_in_force"))
    lang_total    = safe_float(row.get("lang_total"), 6)
    edu_total     = safe_float(row.get("edu_total_25_64"), 6)
    vismin_total  = safe_float(row.get("vismin_total"), 6)
    immig_total   = safe_float(row.get("immig_total"), 6)
    cm_total      = safe_float(row.get("commute_mode_total"), 6)
    cd_total      = safe_float(row.get("commute_dur_total"), 6)
    age_total     = safe_float(row.get("age_total"), 6)
    lowinc_total  = safe_float(row.get("lowincome_total"), 6)
    cond_total    = safe_float(row.get("condition_total"), 6)
    shelr_total   = safe_float(row.get("shelter_ratio_total"), 6)
    mob_total     = safe_float(row.get("mobility5_total"), 6)
    hh_inc_total  = safe_float(row.get("hh_income_total"), 6)

    return {
        # Population
        "population":       pop,
        "median_age":       safe_float(row.get("median_age")),
        "avg_age":          safe_float(row.get("avg_age")),
        "avg_hh_size":      safe_float(row.get("avg_hh_size")),

        # Income — non-aggregatable (null for province/Canada)
        "median_hh_income":         safe_int(row.get("hh_median_total_income")),
        "avg_hh_income":            safe_int(row.get("hh_avg_total_income")),
        "median_hh_aftertax":       safe_int(row.get("hh_median_aftertax_income")),
        "avg_hh_aftertax":          safe_int(row.get("hh_avg_aftertax_income")),
        "median_ind_income":        safe_int(row.get("ind_median_total_income")),
        "avg_ind_income":           safe_int(row.get("ind_avg_total_income")),
        "median_dwelling_value":    safe_int(row.get("owner_median_dwelling_value")),
        "avg_dwelling_value":       safe_int(row.get("owner_avg_dwelling_value")),
        "median_owner_shelter":     safe_int(row.get("owner_median_monthly_shelter")),
        "avg_owner_shelter":        safe_int(row.get("owner_avg_monthly_shelter")),
        "median_renter_shelter":    safe_int(row.get("renter_median_monthly_shelter")),
        "avg_renter_shelter":       safe_int(row.get("renter_avg_monthly_shelter")),

        # Labour
        "labour_total":          safe_int(labour_total),
        "employed":              employed,
        "unemployed":            unemployed,
        "in_labour_force":       in_force,
        "not_in_labour_force":   safe_int(row.get("labour_not_in_force")),
        "employment_rate":       safe_float(row.get("employment_rate")),
        "unemployment_rate":     safe_float(row.get("unemployment_rate")),
        "participation_rate":    safe_float(row.get("participation_rate")),
        # Computed pcts from counts (valid for province/Canada too)
        "pct_employed":          safe_pct(employed, labour_total),
        "pct_unemployed":        safe_pct(unemployed, in_force),

        # Tenure pcts
        "pct_owners":  safe_pct(owner,  tenure_total),
        "pct_renters": safe_pct(renter, tenure_total),

        # Shelter cost burden pct (count-derived — valid for all levels)
        "pct_shelter_30plus": safe_pct(row.get("shelter_ratio_30pct_or_more"), shelr_total),

        # Mortgage pct — non-aggregatable for province/Canada
        "pct_with_mortgage": safe_float(row.get("owner_pct_with_mortgage")),

        # Dwelling condition
        "pct_major_repairs": safe_pct(row.get("condition_major_repairs"), cond_total),

        # Low income
        "pct_low_income": safe_pct(row.get("lowincome_lim_at_count"), lowinc_total),

        # Language pcts (count-derived)
        "pct_english_only": safe_pct(row.get("lang_english_only"), lang_total),
        "pct_french_only":  safe_pct(row.get("lang_french_only"),  lang_total),
        "pct_bilingual":    safe_pct(row.get("lang_bilingual"),     lang_total),
        "pct_neither_lang": safe_pct(row.get("lang_neither"),       lang_total),

        # Education (25–64 pcts)
        "pct_postsecondary":  safe_pct(row.get("edu_postsec"), edu_total),
        "pct_bachelors_plus": safe_pct(row.get("edu_bachelor_plus"), edu_total),

        # Visible minority pcts
        "pct_visible_minority": safe_pct(row.get("vismin_visible_minority"), vismin_total),

        # Immigration
        "pct_immigrant":       safe_pct(row.get("immig_immigrant"),           immig_total),
        "pct_recent_immigrant":safe_pct(row.get("immig_recent_2016_2021"),     immig_total),

        # Commute pcts (count-derived)
        "pct_commute_car":     safe_pct(row.get("commute_car_truck_van"), cm_total),
        "pct_commute_transit": safe_pct(row.get("commute_transit"),       cm_total),
        "pct_commute_walk":    safe_pct(row.get("commute_walk"),          cm_total),
        "pct_commute_bike":    safe_pct(row.get("commute_bicycle"),       cm_total),
        "pct_work_from_home":  safe_pct(row.get("work_at_home"),          row.get("work_status_total")),

        # Mobility
        "pct_nonmovers":  safe_pct(row.get("mobility5_nonmovers"),   mob_total),

        # Age buckets
        "pct_0_14":   safe_pct(row.get("age_0_14"),  age_total),
        "pct_15_64":  safe_pct(row.get("age_15_64"), age_total),
        "pct_65plus": safe_pct(row.get("age_65_plus"), age_total),
    }

def build_distributions(row):
    """All chart-ready distributions."""
    return {
        "dwelling_type": dist(row, DWELL_COLS,    "dwell_total",         DWELL_LABELS),
        "hh_income":     dist(row, HH_INC_COLS,   "hh_income_total",     HH_INC_LABELS),
        "education":     dist(row, EDU_COLS,       "edu_total_25_64",     EDU_LABELS),
        "commute_mode":  dist(row, COMMUTE_MODE_COLS, "commute_mode_total", COMMUTE_MODE_LABELS),
        "commute_dur":   dist(row, COMMUTE_DUR_COLS,  "commute_dur_total",  COMMUTE_DUR_LABELS),
        "age":           dist(row, AGE_COLS,        "age_total",           AGE_LABELS),
        "construction":  dist(row, CONSTR_COLS,     "construction_total",  CONSTR_LABELS),
        "language":      dist(row, LANG_COLS,        "lang_total",          LANG_LABELS),
        "tenure":        tenure_dist(row),
        "visible_minority": dist(row, VISMIN_COLS,  "vismin_total",        VISMIN_LABELS),
        "mobility":      dist(row, MOBILITY_COLS,   "mobility5_total",     MOBILITY_LABELS),
    }

# ── 7a. census_fsa.json ───────────────────────────────────────────────────────

print("  Building census_fsa.json...")
fsa_df = pd.read_csv(FSA_CSV, encoding="utf-8", dtype=str)

census_fsa = {}
for _, row in fsa_df.iterrows():
    fsa = str(row.get("fsa", "")).strip().upper()
    if not fsa:
        continue
    scalars = build_scalars(row)
    dists   = build_distributions(row)
    census_fsa[fsa] = {
        "province": str(row.get("province", "")).strip(),
        **scalars,
        "distributions": dists,
    }

write_json(census_fsa, OUT / "census_fsa.json")

# ── 7b. census_province.json ──────────────────────────────────────────────────

print("  Building census_province.json...")
prov_df = pd.read_csv(PROV_CSV, encoding="utf-8", dtype=str)

census_province = {}
for _, row in prov_df.iterrows():
    pname = str(row.get("province", "")).strip()
    if not pname:
        continue
    scalars = build_scalars(row)
    dists   = build_distributions(row)
    census_province[pname] = {**scalars, "distributions": dists}

write_json(census_province, OUT / "census_province.json")

# ── 7c. census_canada.json ────────────────────────────────────────────────────

print("  Building census_canada.json...")
can_df = pd.read_csv(CAN_CSV, encoding="utf-8", dtype=str)
row    = can_df.iloc[0]

census_canada = {
    **build_scalars(row),
    "distributions": build_distributions(row),
}

write_json(census_canada, OUT / "census_canada.json")

# ── Summary ───────────────────────────────────────────────────────────────────

print()
print("All JSON files written to Mortgage/JSON/")

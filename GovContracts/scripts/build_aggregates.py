"""Read the federal Proactive Disclosure contracts CSV + GSIN code table and
produce small aggregate JSON files for the page to load.

The raw contracts CSV (~600 MB, all federal departments, 2007–present) and the
GSIN reference CSV are NEVER committed to the repo — this script expects them
to already be downloaded locally and only writes small aggregates to data/.

Usage:
    python GovContracts/scripts/build_aggregates.py <contracts_csv> <gsin_csv>

Source files (re-download quarterly, matching the dataset's own cadence):
    Contracts:  https://open.canada.ca/data/en/dataset/d8f85d91-7dec-4fd1-8055-483b77225d8b
                (resource "Contracts over $10,000" -> contracts.csv)
    GSIN codes: https://open.canada.ca/data/en/dataset/2ce347e5-02fd-4487-975d-67a435efdf9b
                (nibs-gsin.csv)
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Exact GSIN commodity_code values (case-insensitive) that read as
# "study/consulting work that overlaps with what an in-house public service
# function could do". Deliberately NOT a prefix match: a bare prefix like
# "R199" or "R123" also covers unrelated multi-billion-dollar contracts (e.g.
# BGIS's national real-property management contract sits under "R123", VF
# Worldwide's overseas logistics support under "R199") which would swamp the
# real consulting spend. Built by grepping the GSIN table's own descriptions
# for "consult"/"advisory"/"change management" and hand-pruning matches that
# turned out to be unrelated (naval architecture, marine, citizen engagement,
# medical advisory, energy-systems engineering). See data/category_definitions.json
# for the human-readable mapping kept in sync with this list.
CONSULTING_CODES = {
    "R019F": "Management & business consulting",
    "R019AB": "Management & business consulting",
    "R019BF": "Management & business consulting",
    "R199H": "Management & business consulting",  # "Change Management / Organizational Development"
    "B308A": "Management & business consulting",  # "Accounting and Financial Management Studies"
    "D302AAP": "IT / informatics consulting",
    "D302AAR": "IT / informatics consulting",
    "D302AAH": "IT / informatics consulting",
    "D302AAI": "IT / informatics consulting",
    "D302AAJ": "IT / informatics consulting",
    "D309BB": "IT / informatics consulting",
    "R118AB": "Real estate / workplace advisory",
}

# A second, structural category: the *physical footprint* side of office
# space (furniture, fit-up, moves, leasing) rather than advisory work. A
# single generic word like "office" is too noisy for a text search (it
# matches "office furniture" but also "Privy Council Office," "post office,"
# etc.) — but as a *commodity code family* it's precise. "N7110" is used as a
# verified prefix (confirmed clean: every N7110* code in the GSIN table is an
# office-furniture item, e.g. desks/chairs/filing cabinets/modular systems —
# unlike the R199/R123 prefixes rejected earlier, which mixed in unrelated
# multi-billion-dollar contracts). The rest are exact codes for fit-up,
# partitions, leasing, moving and relocation services.
OFFICE_FOOTPRINT_PREFIXES = ("N7110",)
OFFICE_FOOTPRINT_CODES = {
    "N7195F": "Office furniture & fit-up",     # Partition, Free-Standing
    "N7195FE": "Office furniture & fit-up",    # Interconnecting Panels
    "N7195FEB": "Office furniture & fit-up",   # Partition, Screen Systems
    "N7195FEC": "Office furniture & fit-up",   # Interconnecting Panels
    "JI7110": "Office furniture & fit-up",     # Office Furniture - Installation
    "JX7110": "Office furniture & fit-up",     # Furniture, Office - Refinishing/Repair
    "JX7195B": "Office furniture & fit-up",    # Partitions, Screen Systems - Repair
    "5177BA": "Office space leasing & moves",  # Interior Fit-Up/Renovations
    "X111B": "Office space leasing & moves",   # Leasing of Office Space
    "M110A": "Office space leasing & moves",   # Property Management - Office Space
    "V001BA": "Office space leasing & moves",  # Movers, Furniture and Office Equipment
    # NOTE: V502A "Relocation Services" deliberately excluded -- checked and
    # it's dominated by the government's Integrated Relocation Program
    # (employee household moves between postings, largest payers Global
    # Affairs/National Defence), not office space moves. A single 2023
    # cluster of household-mover contracts (United Van Lines, Atlas, Sirva,
    # Brookfield) totalled >$700M and swamped this category the same way the
    # rejected R123/R199 prefixes did in the first pass.
}

# Phrase-based (2+ words), not single generic words: "workplace",
# "accommodation", "office", "change management", "lease" alone are too
# common in unrelated contract text/GSIN labels and produced false positives
# in the first pass — e.g. matching any contract whose GSIN label happens to
# be "...Change Management / Organizational Development" regardless of
# subject, or "office" matching "Privy Council Office." The furniture/lease/
# moving signal instead comes from OFFICE_FOOTPRINT_* above (structured
# codes); these keywords are for genuinely RTO-specific *narrative* text.
RTO_KEYWORDS = [
    "return to office", "return-to-office", "hybrid work",
    "workplace strategy", "space utilization", "space utilisation",
    "office space consolidation", "telework policy", "remote work policy",
    "workforce adjustment", "office relocation", "office move",
    "office renovation", "workstation reconfiguration",
    "space reconfiguration", "workplace densification",
    "activity-based workplace", "GC workplace",
]


# --- Office-footprint categories, from economic_object_code's description_en
# rather than commodity_code. description_en is populated on 99.9% of rows
# (vs. 65% for commodity_code) but is extremely messy: leading numeric
# economic-object-code prefixes ("1231 Office furniture..."), inconsistent
# case, mojibake dash characters, and free text appended after a second dash
# ("Engineering consultants - construction - Highways, roads and streets").
# normalize_description() strips the numeric prefix and unifies punctuation;
# categorize_by_description() then does a PREFIX match (not a bare substring
# search -- "architect" alone would wrongly catch "IT Architect" job titles)
# against a curated whitelist built by inspecting every distinct description_en
# variant in the real data. Checked most-specific-first so e.g. "Repair and
# maintenance - Office buildings" doesn't fall through to the generic "Office
# buildings" bucket.
OFFICE_DESCRIPTION_CATEGORIES = [
    ("Repair and maintenance - Office buildings", [
        "repair and maintenance-office buildings", "r&m-office buildings",
        "repair of office buildings", "office buildings-purchased repair and maintenance",
        "office buildings-repair of buildings", "repair of building-office building",
    ]),
    ("Contracted building cleaning", [
        "contracted building cleaning", "contract building cleaning",
    ]),
    ("Architectural services", [
        "architectural services", "architectual services", "services d'architecture",
    ]),
    ("Engineering consultants - construction", [
        "engineering consultants-construction", "engineering consultant-construction",
        "engineering consultants-design and construction",
    ]),
    ("Office furniture and furnishings, including parts", [
        "office furniture and furnishings", "office furniture & furnishings",
        "office furnishing furniture", "office furnishg furnit", "office furniture",
    ]),
    ("Other Office Equipment and Parts", [
        "other office equipment and parts", "other office equipment",
    ]),
    ("Office buildings", [
        "office buildings", "rental of office building",
    ]),
]


def normalize_description(desc: str) -> str:
    if not desc:
        return ""
    d = desc.strip()
    for bad in ("\x96", "–", "—", "�"):
        d = d.replace(bad, "-")
    d = re.sub(r"^\d{3,4}\s*-?\s*", "", d)  # strip leading economic_object_code number
    d = d.lower()
    d = re.sub(r"\s*-\s*", "-", d)          # collapse spaces around dashes
    d = re.sub(r"\s+", " ", d).strip()
    return d


def categorize_by_description(description_en: str) -> str | None:
    norm = normalize_description(description_en)
    if not norm:
        return None
    for name, prefixes in OFFICE_DESCRIPTION_CATEGORIES:
        if any(norm.startswith(p) for p in prefixes):
            return name
    return None


def load_gsin(gsin_csv):
    lookup = {}
    with open(gsin_csv, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            code = row.get("nibs-gsin", "").strip()
            if code:
                lookup[code] = row.get("gsin-description_en", "").strip()
    return lookup


def categorize(commodity_code: str) -> str | None:
    if not commodity_code:
        return None
    code = commodity_code.strip().upper()
    if code in CONSULTING_CODES:
        return CONSULTING_CODES[code]
    if code in OFFICE_FOOTPRINT_CODES:
        return OFFICE_FOOTPRINT_CODES[code]
    if code.startswith(OFFICE_FOOTPRINT_PREFIXES):
        return "Office furniture & fit-up"
    return None


# solicitation_procedure codes, per the Treasury Board "Guide to the
# Proactive Publication of Contracts": TC/OB/ST are the three competitive
# procedures (Traditional, Open Bidding via GETS, Selective Tendering); TN is
# non-competitive (awarded without soliciting bids); AC is an Advance
# Contract Award Notice -- nominally a notice process, not automatically
# sole-sourced, but functionally closer to non-competitive (a contract only
# becomes competitive under ACAN if a challenger's statement of capabilities
# succeeds) -- kept as its own bucket rather than folded into either side.
# IMPORTANT: this field is essentially unpopulated before 2017 (90-100% blank
# 2005-2015, still 61% blank in 2016), then ~0% blank from 2017 onward --
# treat any competitive/non-competitive split as a 2017+-only analysis.
PROCUREMENT_TYPE = {
    "TC": "Competitive", "OB": "Competitive", "ST": "Competitive",
    "TN": "Non-competitive",
    "AC": "ACAN (notice-based)",
}


def procurement_type_of(code: str) -> str:
    return PROCUREMENT_TYPE.get((code or "").strip().upper(), "Unspecified")


def text_matches(row, keywords) -> bool:
    haystack = " ".join(
        (row.get(f) or "") for f in (
            "comments_en", "additional_comments_en",
            "description_en",
        )
    ).lower()
    return any(kw in haystack for kw in keywords)


def year_of(date_str: str) -> str | None:
    if not date_str or len(date_str) < 4:
        return None
    return date_str[:4]


def month_of(date_str: str) -> str | None:
    if not date_str or len(date_str) < 7:
        return None
    return date_str[:7]


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    contracts_csv, gsin_csv = sys.argv[1], sys.argv[2]

    gsin_lookup = load_gsin(gsin_csv)

    spend_by_year_category = defaultdict(float)
    count_by_year_category = defaultdict(int)
    spend_by_dept_category = defaultdict(float)
    top_vendors = defaultdict(float)
    candidates = []  # small flagged-row list, not the full dataset

    # Office-footprint (description_en-based) axis, separate from the
    # commodity_code-based consulting categories above.
    office_spend_by_year = defaultdict(float)
    office_count_by_year = defaultdict(int)
    office_spend_by_month = defaultdict(float)
    office_count_by_month = defaultdict(int)
    office_top_vendors = defaultdict(float)
    office_spend_by_year_procurement = defaultdict(float)
    office_count_by_year_procurement = defaultdict(int)

    rows_by_month = defaultdict(int)  # all rows, for the data-coverage check

    total_rows = 0
    with open(contracts_csv, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            code = (row.get("commodity_code") or "").strip()
            category = categorize(code)

            try:
                value = float(row.get("contract_value") or 0)
            except ValueError:
                value = 0.0

            yr = year_of(row.get("contract_date", ""))
            mo = month_of(row.get("contract_date", ""))
            dept = row.get("owner_org_title") or row.get("owner_org") or "Unknown"
            vendor = row.get("vendor_name") or "Unknown"

            if mo:
                rows_by_month[mo] += 1

            if category is not None:
                if yr:
                    spend_by_year_category[(yr, category)] += value
                    count_by_year_category[(yr, category)] += 1
                spend_by_dept_category[(dept, category)] += value
                top_vendors[vendor] += value

            office_category = categorize_by_description(row.get("description_en", ""))
            if office_category is not None:
                if yr:
                    office_spend_by_year[(yr, office_category)] += value
                    office_count_by_year[(yr, office_category)] += 1
                    ptype = procurement_type_of(row.get("solicitation_procedure", ""))
                    office_spend_by_year_procurement[(yr, office_category, ptype)] += value
                    office_count_by_year_procurement[(yr, office_category, ptype)] += 1
                if mo:
                    office_spend_by_month[(mo, office_category)] += value
                    office_count_by_month[(mo, office_category)] += 1
                office_top_vendors[(vendor, office_category)] += value

            # RTO keyword match is independent of the category whitelists —
            # an office-space/workplace-strategy contract may carry a code or
            # description outside every bucket above.
            if text_matches(row, RTO_KEYWORDS):
                candidates.append({
                    "reference_number": row.get("reference_number"),
                    "vendor_name": vendor,
                    "owner_org_title": dept,
                    "contract_date": row.get("contract_date"),
                    "contract_value": value,
                    "commodity_code": code,
                    "commodity_label": gsin_lookup.get(code.upper(), category or ""),
                    "comments_en": (row.get("comments_en") or "")[:300],
                })

            if total_rows % 500000 == 0:
                print(f"...{total_rows:,} rows scanned", file=sys.stderr)

    DATA_DIR.mkdir(exist_ok=True)

    def dump(name, obj):
        with open(DATA_DIR / name, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))

    dump("spend_by_year_category.json", [
        {"year": yr, "category": cat, "spend": round(v, 2), "count": count_by_year_category[(yr, cat)]}
        for (yr, cat), v in sorted(spend_by_year_category.items())
    ])

    dump("spend_by_department_category.json", [
        {"department": dept, "category": cat, "spend": round(v, 2)}
        for (dept, cat), v in sorted(spend_by_dept_category.items(), key=lambda kv: -kv[1])
        if v > 0
    ][:500])

    dump("top_vendors.json", [
        {"vendor": vendor, "spend": round(v, 2)}
        for vendor, v in sorted(top_vendors.items(), key=lambda kv: -kv[1])[:200]
    ])

    dump("rto_candidates.json", sorted(candidates, key=lambda r: -r["contract_value"])[:500])

    dump("office_footprint_by_year.json", [
        {"year": yr, "category": cat, "spend": round(v, 2), "count": office_count_by_year[(yr, cat)]}
        for (yr, cat), v in sorted(office_spend_by_year.items())
    ])

    dump("office_footprint_by_month.json", [
        {"month": mo, "category": cat, "spend": round(v, 2), "count": office_count_by_month[(mo, cat)]}
        for (mo, cat), v in sorted(office_spend_by_month.items())
    ])

    dump("office_footprint_top_vendors.json", [
        {"vendor": vendor, "category": cat, "spend": round(v, 2)}
        for (vendor, cat), v in sorted(office_top_vendors.items(), key=lambda kv: -kv[1])[:300]
    ])

    dump("office_footprint_by_year_procurement.json", [
        {
            "year": yr, "category": cat, "procurement_type": ptype,
            "spend": round(v, 2), "count": office_count_by_year_procurement[(yr, cat, ptype)],
        }
        for (yr, cat, ptype), v in sorted(office_spend_by_year_procurement.items())
    ])

    # Data-coverage check: proactive disclosure lags actual contract dates by
    # a quarter or more, so the most recent month(s) are typically incomplete
    # -- this must be checked every refresh, not assumed. Compare each month
    # against a stable baseline (median of all months with a normal-sized
    # count), not just the immediately preceding month -- comparing only to
    # the prior month lets a run of small trailing months (17 rows, then 1,
    # then 1) each trivially pass against each other.
    months_sorted = sorted(rows_by_month)
    coverage = [{"month": m, "rows": rows_by_month[m]} for m in months_sorted]
    counts = sorted(rows_by_month.values())
    baseline = counts[len(counts) // 2] if counts else 0  # median month row count
    last_reliable_month = None
    for m in reversed(months_sorted):
        if rows_by_month[m] >= 0.5 * baseline:
            last_reliable_month = m
            break
    dump("data_coverage.json", {
        "months": coverage[-18:],
        "last_reliable_month": last_reliable_month,
        "note": ("Proactive disclosure lags real contract dates. Months at the "
                 "tail with row counts far below the preceding month are "
                 "incomplete, not a real drop in contracting activity -- "
                 "recompute last_reliable_month on every refresh."),
    })

    print(f"Done. Scanned {total_rows:,} rows, "
          f"{sum(count_by_year_category.values()):,} matched a consulting category, "
          f"{sum(office_count_by_year.values()):,} matched an office-footprint category, "
          f"{len(candidates):,} flagged as RTO-keyword candidates. "
          f"Last reliable month: {last_reliable_month}.")


if __name__ == "__main__":
    main()

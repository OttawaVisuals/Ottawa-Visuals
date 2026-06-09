import csv, json, sys
from collections import defaultdict

def parse_num(s):
    """Parse numbers like '38,618' or '14,769' to int. Returns None if empty."""
    if not s or s.strip() == '':
        return None
    return int(s.strip().replace(',', ''))

# ── 1. Load ward_results.csv ──────────────────────────────────────────────────
rows = []
with open('ward_results.csv', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        ward = int(row['ward'])
        year = int(row['year'])
        m_reg   = parse_num(row['Mayor_Registered'])
        m_votes = parse_num(row['Mayor_Votes'])
        m_win   = parse_num(row['Mayor_Winner'])
        c_reg   = parse_num(row['Council_Registered'])
        c_votes = parse_num(row['Council_Votes'])
        c_win   = parse_num(row['Council_Winner'])

        m_part = round(m_votes / m_reg * 100, 1) if m_reg and m_votes else None
        m_win_pct = round(m_win / m_votes * 100, 1) if m_votes and m_win else None
        c_part = round(c_votes / c_reg * 100, 1) if c_reg and c_votes else None
        c_win_pct = round(c_win / c_votes * 100, 1) if c_votes and c_win else None

        rows.append({
            'ward': ward, 'year': year,
            'name': row['name'].strip() if row['name'].strip() else None,
            'm_reg': m_reg, 'm_votes': m_votes, 'm_win': m_win,
            'c_reg': c_reg, 'c_votes': c_votes, 'c_win': c_win,
            'm_part': m_part, 'm_win_pct': m_win_pct,
            'c_part': c_part, 'c_win_pct': c_win_pct,
            'mayor_win_name': row['Mayor_Win_Name'].strip(),
            'council_win_name': row['Council_Win_Name'].strip(),
        })

# Index by (ward, year)
data = {(r['ward'], r['year']): r for r in rows}

# ── 2. Ward name from 2022 row ─────────────────────────────────────────────────
ward_names = {r['ward']: r['name'] for r in rows if r['year'] == 2022}

# ── 3. Ward mapping ────────────────────────────────────────────────────────────
# change_type: direct | renamed | minor | split | new
# For 'new' and 'split': source_wards lists the old ward(s) used for history
# weight: used for weighted averaging (must sum to 1.0 across sources for same ward+year)

YEARS = [2010, 2014, 2018, 2022]

mapping = {
    1:  {'change': 'renamed', 'sources': {y: [(1, 1.0)] for y in YEARS}},
    2:  {'change': 'renamed', 'sources': {y: [(2, 1.0)] for y in YEARS}},
    3:  {'change': 'split',   'sources': {
            2010: [(3, 1.0)], 2014: [(3, 1.0)], 2018: [(3, 1.0)], 2022: [(3, 1.0)]}},
    4:  {'change': 'direct',  'sources': {y: [(4, 1.0)] for y in YEARS}},
    5:  {'change': 'direct',  'sources': {y: [(5, 1.0)] for y in YEARS}},
    6:  {'change': 'direct',  'sources': {y: [(6, 1.0)] for y in YEARS}},
    7:  {'change': 'direct',  'sources': {y: [(7, 1.0)] for y in YEARS}},
    8:  {'change': 'direct',  'sources': {y: [(8, 1.0)] for y in YEARS}},
    9:  {'change': 'direct',  'sources': {y: [(9, 1.0)] for y in YEARS}},
    10: {'change': 'direct',  'sources': {y: [(10, 1.0)] for y in YEARS}},
    11: {'change': 'direct',  'sources': {y: [(11, 1.0)] for y in YEARS}},
    12: {'change': 'minor',   'sources': {y: [(12, 1.0)] for y in YEARS}},
    13: {'change': 'minor',   'sources': {y: [(13, 1.0)] for y in YEARS}},
    14: {'change': 'direct',  'sources': {y: [(14, 1.0)] for y in YEARS}},
    15: {'change': 'direct',  'sources': {y: [(15, 1.0)] for y in YEARS}},
    16: {'change': 'direct',  'sources': {y: [(16, 1.0)] for y in YEARS}},
    17: {'change': 'minor',   'sources': {y: [(17, 1.0)] for y in YEARS}},
    18: {'change': 'direct',  'sources': {y: [(18, 1.0)] for y in YEARS}},
    19: {'change': 'renamed', 'sources': {y: [(19, 1.0)] for y in YEARS}},
    20: {'change': 'direct',  'sources': {y: [(20, 1.0)] for y in YEARS}},
    21: {'change': 'renamed', 'sources': {y: [(21, 1.0)] for y in YEARS}},
    22: {'change': 'split',   'sources': {
            2010: [(22, 1.0)], 2014: [(22, 1.0)], 2018: [(22, 1.0)], 2022: [(22, 1.0)]}},
    23: {'change': 'direct',  'sources': {y: [(23, 1.0)] for y in YEARS}},
    # Ward 24: new ward carved mostly from old W3 (~60%) and old W22 (~40%)
    # Weighted by approximate registered voter contribution based on 2022 population split
    24: {'change': 'new',     'sources': {
            2010: [(3, 0.60), (22, 0.40)],
            2014: [(3, 0.60), (22, 0.40)],
            2018: [(3, 0.60), (22, 0.40)],
            2022: [(24, 1.0)]}},
}

# Caveat text per change type
CAVEAT_TEXT = {
    'direct':  None,
    'renamed': None,
    'minor': (
        "Minor boundary adjustment in 2022. Historical values (2010–2018) reflect "
        "the previous boundary and may slightly differ from the current ward area."
    ),
    'split': None,  # set per ward below
    'new':  None,   # set per ward below
}

SPLIT_CAVEAT = {
    3: (
        "Barrhaven West was created in 2022 when the old Barrhaven ward (Ward 3) "
        "was split: its eastern portion (Chapman Mills and Davidson Heights) became "
        "the new Barrhaven East (Ward 24), and Stonebridge was transferred to "
        "Riverside South-Findlay Creek (Ward 22). Historical values (2010–2018) "
        "reflect the full old Barrhaven ward and therefore cover a larger area than "
        "the current Ward 3."
    ),
    22: (
        "Riverside South-Findlay Creek (formerly Gloucester-South Nepean) lost "
        "territory in 2022: Stonebridge was transferred to Barrhaven West (Ward 3) "
        "and Chapman Mills was transferred to the new Barrhaven East (Ward 24). "
        "Historical values (2010–2018) reflect the larger former ward area."
    ),
}

NEW_CAVEAT = {
    24: (
        "Barrhaven East is a new ward created in 2022, carved approximately 60% "
        "from the old Barrhaven ward (Ward 3) and 40% from the old "
        "Gloucester-South Nepean ward (Ward 22). Historical values (2010–2018) are "
        "estimates calculated as a weighted average of those two source wards "
        "using those proportions; they do not reflect actual election results for "
        "this specific territory."
    ),
}

# ── 4. Weighted average of participation across source wards ───────────────────
def weighted_part(field, ward_2022, year):
    """
    Compute weighted average participation for a ward+year.
    field: 'm_part' or 'c_part'
    Returns (value_or_None, [source_descriptions])
    """
    sources = mapping[ward_2022]['sources'][year]
    total_reg = 0
    total_votes = 0
    reg_field = 'm_reg' if field == 'm_part' else 'c_reg'
    votes_field = 'm_votes' if field == 'm_part' else 'c_votes'

    # For single-source, just pass through raw values
    if len(sources) == 1:
        src_ward, _ = sources[0]
        r = data.get((src_ward, year))
        if r is None:
            return None
        return r[field]

    # Multi-source: weighted average by registered voters * weight
    weighted_votes = 0
    weighted_reg = 0
    any_data = False
    for src_ward, weight in sources:
        r = data.get((src_ward, year))
        if r is None or r[reg_field] is None:
            continue
        any_data = True
        weighted_reg   += r[reg_field]   * weight
        weighted_votes += (r[votes_field] or 0) * weight

    if not any_data or weighted_reg == 0:
        return None
    return round(weighted_votes / weighted_reg * 100, 1)

# ── 5. Build output JSON ───────────────────────────────────────────────────────
result = {}

for ward_2022 in range(1, 25):
    m = mapping[ward_2022]
    change = m['change']

    # 2022 actuals
    r2022 = data.get((ward_2022, 2022))
    if r2022 is None:
        print(f"WARNING: no 2022 data for ward {ward_2022}", file=sys.stderr)
        continue

    # History
    hist_mayor = []
    hist_coun  = []
    for y in YEARS:
        hist_mayor.append(weighted_part('m_part', ward_2022, y))
        hist_coun.append(weighted_part('c_part',  ward_2022, y))

    # Caveat
    if change in ('direct', 'renamed'):
        caveat = None
    elif change == 'minor':
        caveat = CAVEAT_TEXT['minor']
    elif change == 'split':
        caveat = SPLIT_CAVEAT.get(ward_2022)
    elif change == 'new':
        caveat = NEW_CAVEAT.get(ward_2022)
    else:
        caveat = None

    result[str(ward_2022)] = {
        'name': ward_names.get(ward_2022, f'Ward {ward_2022}'),
        'change_type': change,
        'caveat': caveat,
        'mayor': {
            'participation': r2022['m_part'],
            'winner_pct':    r2022['m_win_pct'],
            'winner_name':   r2022['mayor_win_name'],
        },
        'councillor': {
            'participation': r2022['c_part'],
            'winner_pct':    r2022['c_win_pct'],
            'winner_name':   r2022['council_win_name'],
        },
        'history': {
            'years':       YEARS,
            'mayor':       hist_mayor,
            'councillor':  hist_coun,
        },
    }

with open('ward_data.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"Done — {len(result)} wards written to ward_data.json")

# Print a summary to verify
print("\nSample output (Ward 3 and Ward 24):")
for w in ['3', '24']:
    d = result[w]
    print(f"\nWard {w} — {d['name']}")
    print(f"  change_type: {d['change_type']}")
    print(f"  mayor 2022: {d['mayor']['participation']}% ({d['mayor']['winner_name']})")
    print(f"  councillor 2022: {d['councillor']['participation']}%")
    print(f"  mayor history: {d['history']['mayor']}")
    print(f"  councillor history: {d['history']['councillor']}")
    if d['caveat']:
        print(f"  caveat: {d['caveat'][:80]}...")
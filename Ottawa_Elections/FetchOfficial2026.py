"""Extract the City's official 2026 Statement of Votes Cast (poll-by-poll workbook) into
reconciliation/results_2026_official.json, in the same shape as FetchResults2026.py's
unofficial feed so BuildWardData.py can use either.

Source: open.ottawa.ca item 28d0d0f0d4704ba295dd362a31c07aee (Statement_of_Votes_Cast_Final_2026_BIL.xlsx).
Only the 'Total' row of each Mayor/Ward sheet is read here; poll rows stay in the workbook.
Requires openpyxl. Run from any cwd; --refresh re-downloads the workbook.
"""
import argparse
import hashlib
import json
import re
import tempfile
from datetime import date
from pathlib import Path
from urllib.request import urlopen

import openpyxl

ROOT = Path(__file__).resolve().parent
ITEM = '28d0d0f0d4704ba295dd362a31c07aee'
URL = f'https://www.arcgis.com/sharing/rest/content/items/{ITEM}/data'
PAGE = f'https://open.ottawa.ca/documents/{ITEM}'


def name_of(cell):
    return re.sub(r'\s+', ' ', str(cell).split('\n')[0]).strip()


def race(rows, ward):
    header = next(r for r in rows if r and str(r[0]).startswith('Voting place'))
    total = next(r for r in rows if r and str(r[0]).strip() == 'Total')
    valid_col = next(i for i, v in enumerate(header) if v and 'Total votes' in str(v))
    cands = {name_of(header[i]): int(total[i] or 0) for i in range(7, valid_col) if header[i]}
    assert sum(cands.values()) == int(total[valid_col]), (ward, 'candidate sum')
    return {'year': 2026, 'ward': ward, 'office': 'mayor' if ward is None else 'councillor',
            'registered': int(total[2]), 'ballots': int(total[1]), 'valid_votes': int(total[valid_col]),
            'acclaimed': False, 'candidates': cands, 'coverage': 'ward_totals', 'certification': 'official'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache', type=Path, default=Path(tempfile.gettempdir()) / 'ottawa-election-reconciliation')
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    path = args.cache / '2026.xlsx'
    if args.refresh or not path.exists():
        with urlopen(URL, timeout=60) as r:
            path.write_bytes(r.read())
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets
              if ws.title.startswith(('Mayor', 'Ward_quartier_', 'Summary'))}
    races = [race(sheets['Mayor_Maire'], None)]
    for w in range(1, 25):
        rows = sheets[f'Ward_quartier_{w}']
        acc = next((r for r in rows if r and str(r[0]).startswith('Acclaimed')), None)
        if acc:
            who = next(name_of(r[0]) for r in rows[rows.index(acc) + 1:] if r and r[0])
            races.append({'year': 2026, 'ward': w, 'office': 'councillor', 'registered': None, 'ballots': None,
                          'valid_votes': None, 'acclaimed': True, 'candidates': {who: 0},
                          'coverage': 'ward_totals', 'certification': 'official'})
        else:
            races.append(race(rows, w))
    summary = sheets['Summary_résumé']
    city = next(r for r in summary if r and str(r[0]).strip() == 'Total')
    # Acclaimed wards have no sheet total: take their electors from the poll summary rows.
    per_ward = {}
    for r in summary:
        m = re.match(r'(\d{2})-\d{3}', str(r[0] or ''))
        if m and isinstance(r[1], (int, float)):
            per_ward[int(m[1])] = per_ward.get(int(m[1]), 0) + int(r[1])
    for r in races:
        if r['acclaimed']:
            r['registered'] = per_ward[r['ward']]
    assert sum(r['registered'] for r in races if r['office'] == 'councillor') == int(city[1]) == races[0]['registered']
    out = {'source': PAGE, 'retrieved': str(date.today()), 'registered': int(city[1]),
           'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
           'note': "City of Ottawa official 2026 Statement of Votes Cast (Elections Office, created 2026-10-30). "
                   "Ward totals only here; poll rows stay in the workbook.",
           'races': races}
    (ROOT / 'reconciliation/results_2026_official.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(f"mayor ballots {races[0]['ballots']}, {len(races) - 1} council races, registered {out['registered']}")


if __name__ == '__main__':
    main()

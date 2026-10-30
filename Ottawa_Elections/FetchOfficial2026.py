"""Extract the City's official 2026 Statement of Votes Cast (poll-by-poll workbook) into
reconciliation/results_2026_official.json, in the same shape as FetchResults2026.py's
unofficial feed so BuildWardData.py can use either.

Source: open.ottawa.ca item 28d0d0f0d4704ba295dd362a31c07aee (Statement_of_Votes_Cast_Final_2026_BIL.xlsx).
Council and citywide mayor use the 'Total' row of each sheet. The mayor's ward split sums the poll rows of
the Mayor sheet by the ward code in each poll label (advance and special polls included); polls coded 99
are citywide and stay unallocated, as in 2022.
Requires openpyxl. Run from any cwd; --refresh re-downloads the workbook.
"""
import argparse
import collections
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


PRECINCT = re.compile(r'(?<!\d)(\d{2})-\d{3}')


def mayor_by_ward(rows):
    header = next(r for r in rows if r and str(r[0]).startswith('Voting place'))
    valid_col = next(i for i, v in enumerate(header) if v and 'Total votes' in str(v))
    cols = [(i, name_of(header[i])) for i in range(7, valid_col) if header[i]]
    wards = collections.defaultdict(lambda: {'registered': 0, 'ballots': 0, 'valid_votes': 0,
                                             'candidates': collections.Counter()})
    for r in rows[rows.index(header) + 1:]:
        label = str(r[0] or '').strip()
        m = PRECINCT.search(label)
        if label == 'Total' or not m:
            continue
        w = wards[int(m[1])]
        w['registered'] += int(r[2] or 0)
        w['ballots'] += int(r[1] or 0)
        w['valid_votes'] += int(r[valid_col] or 0)
        for i, n in cols:
            w['candidates'][n] += int(r[i] or 0)
    out = []
    for ward in sorted(wards):
        w = wards[ward]
        assert sum(w['candidates'].values()) == w['valid_votes'], (ward, 'mayor ward sum')
        out.append({'year': 2026, 'ward': ward, 'office': 'mayor', 'registered': w['registered'],
                    'ballots': w['ballots'], 'valid_votes': w['valid_votes'], 'acclaimed': False,
                    'candidates': dict(w['candidates']),
                    'coverage': 'unallocated_citywide_polls' if ward == 99 else 'ward_coded_polls_only',
                    'certification': 'official'})
    return out


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
    split = mayor_by_ward(sheets['Mayor_Maire'])
    city_mayor = races[0]
    assert sum(r['valid_votes'] for r in split) == city_mayor['valid_votes']
    assert sum(r['ballots'] for r in split) == city_mayor['ballots']
    for name, votes in city_mayor['candidates'].items():
        assert sum(r['candidates'].get(name, 0) for r in split) == votes, name
    races.extend(split)
    out = {'source': PAGE, 'retrieved': str(date.today()), 'registered': int(city[1]),
           'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
           'note': "City of Ottawa official 2026 Statement of Votes Cast (Elections Office, created 2026-10-30). "
                   "Mayor split by ward is built from the Mayor sheet's poll rows.",
           'races': races}
    (ROOT / 'reconciliation/results_2026_official.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(f"mayor ballots {races[0]['ballots']}, {len(races) - 1} ward races (council + mayor split), registered {out['registered']}")


if __name__ == '__main__':
    main()

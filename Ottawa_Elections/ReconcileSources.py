"""Download City result workbooks, reconcile their controls, and retain provenance.

Requires openpyxl (xlsx) and xlrd (legacy xls). No workbook is modified.
Run from any directory. Downloads are cached outside the repository by default.
"""
import argparse
import csv
import hashlib
import json
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
ITEMS = {
    2010: ('a777b47502a246f79f51daa41c7a542d', 'xlsx'),
    2014: ('1281bd2bdd26477397aad7f2b71d6c0a', 'xls'),
    2018: ('8cb37c0751dc4ce2ae5d92fb5d85cd0a', 'xls'),
    2022: ('ec1423ac43254bff8692fabd5d47772b', 'xlsx'),
}
PRECINCT = re.compile(r'(?<!\d)(\d{2})-\d{3}')
BASELINE = ROOT / 'reconciliation' / 'legacy_ward_results.csv'


def text(value):
    return ' '.join(str(value or '').replace('\ufffd', '’').split())


def integer(value):
    if value in (None, ''):
        return None
    number = float(str(value).replace(',', ''))
    assert number == int(number), value
    return int(number)


def read_sheets(path):
    if path.suffix == '.xlsx':
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        result = {s.title: list(s.values) for s in wb}
        wb.close()
        return result
    import xlrd
    wb = xlrd.open_workbook(path)
    return {s.name: [s.row_values(r) for r in range(s.nrows)] for s in wb.sheets()}


def source_ref(sheet, row):
    return f'{sheet}!A{row}'


def grouped_ref(sheet, rows):
    """Compact original row references for a sum of non-contiguous precincts."""
    spans = []
    start = previous = rows[0]
    for row in rows[1:]:
        if row == previous+1:
            previous = row
        else:
            spans.append(str(start) if start == previous else f'{start}-{previous}')
            start = previous = row
    spans.append(str(start) if start == previous else f'{start}-{previous}')
    return sheet+'!rows '+','.join(spans)


def extract_modern(year, sheets):
    mayor_name = next(k for k in sheets if k.lower().startswith('mayor'))
    summary_name = next(k for k in sheets if k.lower().startswith('summary'))
    sm = sheets[summary_name]
    summary_total = next((i, r) for i, r in enumerate(sm, 1) if text(r[0]) == 'City / Ville - Total')
    summary_wards = defaultdict(lambda: {'registered': 0, 'ballots': 0})
    summary_rows = defaultdict(list)
    for i, row in enumerate(sm,1):
        match = PRECINCT.search(text(row[0]))
        if match and isinstance(row[3], (int, float)):
            summary_wards[int(match[1])]['registered'] += integer(row[1]) or 0
            summary_wards[int(match[1])]['ballots'] += integer(row[3]) or 0
            summary_rows[int(match[1])].append(i)
    assert sum(v['registered'] for v in summary_wards.values()) == integer(summary_total[1][1])
    assert sum(v['ballots'] for v in summary_wards.values()) == integer(summary_total[1][3])
    races = []
    city = None
    for name, rows in sheets.items():
        council_match = re.fullmatch(r'Ward(?: |_quartier_)(\d+)', name)
        is_mayor = name == mayor_name
        if not (is_mayor or council_match):
            continue
        header_i, header = next((i, r) for i, r in enumerate(rows) if any('Total Votes' in str(v) for v in r))
        valid_col = next(i for i, v in enumerate(header) if 'Total Votes' in str(v))
        precinct_col = 6 if year >= 2018 else 0
        candidate_cols = [i for i in range(precinct_col+1, valid_col) if text(header[i])]
        totals_i, totals = next((i, r) for i, r in enumerate(rows, 1) if text(r[0]) == 'City / Ville - Total')
        candidates = {text(header[i]): integer(totals[i]) for i in candidate_cols}
        assert sum(candidates.values()) == integer(totals[valid_col]), (year, name, 'candidate sum')
        # Check actual precinct detail against the independent workbook total row.
        detail = [(i, r) for i, r in enumerate(rows, 1)
                  if PRECINCT.search(text(r[precinct_col])) and isinstance(r[valid_col], (int, float))]
        for col in candidate_cols + [valid_col] + ([1, 2, 4] if year == 2018 else [1, 2, 4, 5] if year == 2022 else []):
            assert sum(integer(r[col]) or 0 for _, r in detail) == integer(totals[col]), (year, name, col)
        base = {'year': year, 'office': 'mayor' if is_mayor else 'councillor',
                'source_sheet': name, 'source_total': source_ref(name, totals_i),
                'certification': 'official', 'valid_votes': integer(totals[valid_col]),
                'candidates': candidates}
        if year >= 2018:
            base.update(ballots=integer(totals[1]), undervotes=integer(totals[4 if year == 2022 else 2]),
                        overvotes=integer(totals[5 if year == 2022 else 4]))
            assert base['ballots'] == base['valid_votes'] + base['undervotes'] + base['overvotes']
        if is_mayor:
            city = dict(base, ward=0, coverage='citywide', registered=integer(summary_total[1][1]),
                        ballots=integer(summary_total[1][3]), source_summary=source_ref(summary_name, summary_total[0]))
            if year == 2014:
                city.update(undervotes=None, overvotes=None)
            # 99 is a polling-place code, never a residential ward. Preserve it.
            groups = defaultdict(list)
            for i, row in detail:
                groups[int(PRECINCT.search(text(row[precinct_col]))[1])].append((i, row))
            for ward, group in sorted(groups.items()):
                ward_candidates = {text(header[c]): sum(integer(r[c]) or 0 for _, r in group) for c in candidate_cols}
                race = dict(base, ward=ward, candidates=ward_candidates,
                            coverage='unallocated_citywide_polls' if ward == 99 else 'ward_coded_polls_only',
                            valid_votes=sum(ward_candidates.values()),
                            source_rows=[i for i, _ in group],
                            source_total=grouped_ref(name,[i for i,_ in group]),
                            city_control=source_ref(name,totals_i),
                            registered=summary_wards[ward]['registered'],
                            registered_source=grouped_ref(summary_name,summary_rows[ward]))
                if year >= 2018:
                    race.update(ballots=sum(integer(r[1]) or 0 for _, r in group),
                                undervotes=sum(integer(r[4 if year == 2022 else 2]) or 0 for _, r in group),
                                overvotes=sum(integer(r[5 if year == 2022 else 4]) or 0 for _, r in group))
                else:
                    race.update(ballots=summary_wards[ward]['ballots'], undervotes=None, overvotes=None)
                races.append(race)
        else:
            ward = int(council_match[1])
            # Council sheets include special votes allocated to the correct home ward.
            base.update(ward=ward, coverage='full_ward', registered=summary_wards[ward]['registered'],
                        registered_source=grouped_ref(summary_name,summary_rows[ward]))
            if year == 2022:
                assert base['registered'] == integer(totals[2])
            if year == 2014:
                base.update(ballots=None, undervotes=None, overvotes=None)
            races.append(base)
    assert city is not None
    mayor = [r for r in races if r['office'] == 'mayor']
    assert sum(r['valid_votes'] for r in mayor) == city['valid_votes']
    assert sum(r['ballots'] for r in mayor) == city['ballots']
    for candidate, votes in city['candidates'].items():
        assert sum(r['candidates'][candidate] for r in mayor) == votes
    council = [r for r in races if r['office'] == 'councillor']
    assert len(council) == (24 if year == 2022 else 23)
    if year >= 2018:
        assert sum(r['ballots'] for r in council) == city['ballots']
        assert sum(r['registered'] for r in council) == city['registered']
    return races, city


def extract_2010(sheets):
    races = []
    issues = []
    for name, rows in sheets.items():
        ward = int(name.split('-')[1])
        headers = [(i, r) for i, r in enumerate(rows)
                   if str(r[0] or '').lower().startswith(('mayor', 'councillor'))]
        for start, header in headers:
            office = 'mayor' if str(header[0]).lower().startswith('mayor') else 'councillor'
            end = next((i for i in range(start+1, len(rows)) if text(rows[i][0]) == 'Total'), None)
            assert end is not None, (name, office)
            total = rows[end]
            cols = [c for c in range(3, len(header)) if text(header[c])]
            candidates = {text(header[c]): integer(total[c]) for c in cols}
            summed = sum(candidates.values())
            detail = [r for r in rows[start+1:end]
                      if text(r[0]).lower() not in ('polling', 'adv vote', 'total polling')
                      and isinstance(r[2], (int, float))]
            for col in cols + [2]:
                detail_sum = sum(integer(r[col]) or 0 for r in detail)
                if detail_sum != integer(total[col]):
                    issues.append({'year':2010, 'ward':ward, 'office':office,
                                   'issue':'Precinct detail differs from published total row',
                                   'field':text(header[col]), 'detail_sum':detail_sum,
                                   'published_total':integer(total[col]),
                                   'source':source_ref(name,end+1),
                                   'resolution':'Retain published total, flag source conflict; no inferred correction.'})
            if summed != integer(total[2]):
                issues.append({'year': 2010, 'ward': ward, 'office': office,
                               'issue': 'Candidate totals differ from source Total Votes',
                               'candidate_sum': summed, 'published_total_votes': integer(total[2]),
                               'source': source_ref(name, end+1)})
            # Use summed candidate votes as valid votes; do not pretend Total Votes = ballots.
            races.append({'year': 2010, 'ward': ward, 'office': office,
                          'source_sheet': name, 'source_total': source_ref(name, end+1),
                          'coverage': 'city_published_2010_ward', 'certification': 'not_certified',
                          'registered': integer(total[1]), 'valid_votes': summed,
                          'published_total_votes': integer(total[2]), 'ballots': None,
                          'undervotes': None, 'overvotes': None, 'candidates': candidates})
    mayor = [r for r in races if r['office'] == 'mayor']
    candidates = Counter()
    for r in mayor:
        candidates.update(r['candidates'])
    city = {'year': 2010, 'ward': 0, 'office': 'mayor', 'coverage': 'citywide_ward_sum',
            'certification': 'not_certified', 'registered': sum(r['registered'] for r in mayor),
            'valid_votes': sum(candidates.values()), 'published_total_votes': sum(r['published_total_votes'] for r in mayor),
            'ballots': None, 'undervotes': None, 'overvotes': None, 'candidates': dict(candidates)}
    assert len(mayor) == 23
    assert len(races) == 44  # Council sheets missing for wards 7 and 15.
    return races, city, issues


def canonical_name(s):
    return unicodedata.normalize('NFKD', text(s)).replace('’', "'").encode('ascii', 'ignore').decode().lower()


def comparison(races):
    by_key = {(r['year'], r['ward'], r['office']): r for r in races}
    out = []
    with BASELINE.open(encoding='utf-8-sig', newline='') as f:
        for old in csv.DictReader(f):
            year, ward = int(old['year']), int(old['ward'])
            for office, prefix in [('mayor', 'Mayor'), ('councillor', 'Council')]:
                r = by_key.get((year, ward, office))
                if r is None:
                    continue
                winner, votes = max(r['candidates'].items(), key=lambda x: x[1])
                for field, new, meaning in [
                    ('Registered', r['registered'], 'registered voters'),
                    ('Votes', r['valid_votes'], 'valid candidate votes'),
                    ('Winner', votes, 'highest candidate vote count'),
                    ('Win_Name', winner, 'highest candidate name'),
                ]:
                    key = prefix + '_' + field
                    val = old[key].strip()
                    if field != 'Win_Name':
                        val = integer(val)
                        status = 'match' if val == new else 'different'
                    else:
                        status = 'match' if canonical_name(val) == canonical_name(new) else 'different'
                    if field == 'Votes' and val != new and val == r.get('ballots'):
                        status = 'ballots_used_as_valid_votes'
                    out.append({'year': year, 'ward': ward, 'field': key, 'legacy_value': val,
                                'source_value': new, 'meaning': meaning, 'comparison': status,
                                'coverage': r['coverage'], 'certification': r['certification'],
                                'source': r.get('registered_source',r['source_total']) if field=='Registered' else r['source_total']})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path(tempfile.gettempdir())/'ottawa-election-reconciliation')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    dest = ROOT/'reconciliation'
    dest.mkdir(exist_ok=True)
    previous_path = dest/'source_results.json'
    previous = json.loads(previous_path.read_text(encoding='utf8')) if previous_path.exists() else {}
    previous_sources = {s['year']:s for s in previous.get('sources',[])}
    if not BASELINE.exists():
        BASELINE.write_bytes((ROOT/'ward_results.csv').read_bytes())
    races, cities, manifests, issues = [], [], [], []
    for year, (item, ext) in ITEMS.items():
        path = args.cache/f'{year}.{ext}'
        url = f'https://www.arcgis.com/sharing/rest/content/items/{item}/data'
        if args.refresh or not path.exists():
            with urlopen(url, timeout=60) as response:
                path.write_bytes(response.read())
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if year in previous_sources and sha256 != previous_sources[year]['sha256']:
            raise ValueError(f'{year}: source bytes changed ({sha256}). Review the new vintage before updating the retained manifest.')
        metadata_url = f'https://www.arcgis.com/sharing/rest/content/items/{item}?f=json'
        metadata_cache = args.cache/f'{year}_metadata.json'
        if args.refresh or not metadata_cache.exists():
            with urlopen(metadata_url, timeout=30) as response:
                metadata = json.load(response)
            metadata_cache.write_text(json.dumps(metadata,ensure_ascii=False),encoding='utf8')
        else:
            metadata = json.loads(metadata_cache.read_text(encoding='utf8'))
        assert metadata['owner'] == 'open.ouvert@ottawa.ca'
        sheets = read_sheets(path)
        if year == 2010:
            rr, city, ii = extract_2010(sheets)
            issues.extend(ii)
        else:
            rr, city = extract_modern(year, sheets)
        races.extend(rr)
        cities.append(city)
        manifests.append({'year': year, 'item_id': item, 'title': metadata['title'],
                          'publisher': metadata['owner'], 'original_filename': metadata['name'],
                          'download_url': url, 'catalogue_url': f'https://open.ottawa.ca/documents/{item}',
                          'metadata_url': metadata_url, 'sha256': sha256,
                          'bytes': path.stat().st_size, 'retrieved': previous_sources.get(year,{}).get('retrieved',str(date.today())),
                          'source_description': metadata.get('description'),
                          'certification': city['certification']})
    audit = comparison(races)
    obj = {'checked': str(date.today()), 'sources': manifests, 'citywide': cities, 'races': races,
           'source_issues': issues,
           'gaps': ['2010 City workbook is not certified and lacks council data for wards 7 and 15.',
                    '2010 ballots cast are unavailable in this workbook. Total Votes are candidate votes, not turnout.',
                    '2014 full ward ballots cast are unavailable. The legacy Ward 4 registered-voter count was 30 too low (22548 instead of 22578).',
                    '2014/2018/2022 mayor special citywide polls (code 99) cannot be allocated to residential wards from these workbooks.',
                    'Population and under-18 constants remain unverified; see the dated retrieval failure in SOURCE_RECONCILIATION.md.',
                    'Historical ward results have not been reaggregated onto 2022 boundaries. Ward 24 has no pre-2022 result.']}
    (dest/'source_results.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n',encoding='utf8')
    with (dest/'field_comparison.csv').open('w',encoding='utf8',newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(audit[0]))
        writer.writeheader()
        writer.writerows(audit)
    print(json.dumps({'races': len(races), 'fields':len(audit),
                      'comparison': dict(Counter(a['comparison'] for a in audit)),
                      'source_issues':issues,
                      'citywide': [{k:v for k,v in c.items() if k != 'candidates'} for c in cities]},indent=2))


if __name__ == '__main__':
    main()

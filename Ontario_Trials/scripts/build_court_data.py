"""Reproducibly extract Ottawa OCJ outcomes from the official statistics index.

python Ontario_Trials/scripts/build_court_data.py [--refresh]
Requires beautifulsoup4, openpyxl and pymupdf. Cached sources are ignored by Git.
Extraction failures abort before replacing published output; no inferred verdicts.
"""
import argparse
import calendar
import concurrent.futures
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import openpyxl
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache'
INDEX = 'https://www.ontariocourts.ca/ocj/statistics/'
MONTHS = {m: i for i, m in enumerate(calendar.month_name) if m}

def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()

def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')

def number(value):
    # Blank table cells represent an omitted zero only within a structurally valid
    # count row. Every such row must independently reconcile to its printed totals.
    if value is None or value == '':
        return 0
    value = str(value).replace(',', '').strip()
    if not re.fullmatch(r'\d+(?:\.0+)?', value):
        raise ValueError('Unexpected count cell: ' + value)
    return int(float(value))

def parse_period(text):
    match = re.search(r'([A-Z][a-z]+) (\d{4}) to ([A-Z][a-z]+) (\d{4})', text)
    if not match:
        raise ValueError('No reporting period found: ' + text[:200])
    m1, y1, m2, y2 = match.groups()
    a, b = MONTHS[m1], MONTHS[m2]
    start = date(int(y1), a, 1)
    end = date(int(y2), b, calendar.monthrange(int(y2), b)[1])
    return {'label': match[0], 'start': str(start), 'end': str(end),
            'calendar_year': int(y1) if a == 1 and b == 12 and y1 == y2 else None}

def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()

def discover(refresh=False):
    CACHE.mkdir(exist_ok=True)
    index_path = CACHE / 'index.html'
    if refresh or not index_path.exists():
        index_path.write_bytes(fetch(INDEX))
    sources = {}
    for a in BeautifulSoup(index_path.read_bytes(), 'html.parser').select('a[href]'):
        url = urljoin(INDEX, a['href'])
        match = re.search(r'/stats/(crim|poa)/(\d{4})/\2-(Offence-Based-Criminal|POA-Statute)\.(pdf|xlsx)$', url, re.I)
        if match:
            series, year, _, ext = match.groups()
            key = f'{series}-{year}'
            if key in sources:
                raise ValueError('Duplicate indexed publication: ' + key)
            sources[key] = {'id': key, 'series': series, 'publication_year': int(year), 'format': ext.lower(), 'url': url}
    if len(sources) < 20:
        raise ValueError('Unexpected statistics index coverage; manual source review required.')
    def download(s):
        p = CACHE / (s['id'] + '.' + s['format'])
        if refresh or not p.exists():
            p.write_bytes(fetch(s['url']))
        s['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
        return s
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        return sorted(pool.map(download, sources.values()), key=lambda s: s['id'])

def read_source(s):
    p = CACHE / (s['id'] + '.' + s['format'])
    if s['format'] == 'xlsx':
        workbook = openpyxl.load_workbook(p, read_only=True, data_only=True)
        name = 'Ottawa' if s['series'] == 'crim' else 'Ottawa City'
        sheet = workbook[name]
        s['locator'] = 'Sheet: ' + name
        rows = [(i, list(row)) for i, row in enumerate(sheet.values, 1)]
        s['period'] = parse_period(clean(sheet['A5'].value))
        s['source_notes'] = [clean(row[0]) for _, row in rows if row and clean(row[0]).startswith(('Case:', 'Cases Disposed:', 'Offence Type:', 'Charges Disposed:', 'The data is being', 'The Ministry'))]
        s['ignored_header_errors'] = sum(1 for _, row in rows[:6] for v in row if isinstance(v, str) and v.startswith('#'))
        return rows
    document = pymupdf.open(p)
    hits = [entry[2]-1 for entry in document.get_toc() if 'Ottawa' in entry[1]]
    if len(hits) != 1:
        raise ValueError('Expected one Ottawa PDF bookmark: ' + s['id'])
    page = document[hits[0]]
    s['locator'] = f'PDF page {hits[0]+1}'
    text = page.get_text(sort=True)
    s['period'] = parse_period(text)
    s['source_notes'] = [clean(line) for line in text.splitlines() if line.strip().startswith(('Case:', 'Cases Disposed:', 'Charges Disposed:', 'The Ministry'))]
    tables = page.find_tables().tables
    if len(tables) != 1:
        raise ValueError('Expected one table: ' + s['id'])
    return [(i, row) for i, row in enumerate(tables[0].extract(), 1)]

CRIM_GROUPS = ['Crimes Against the Person', 'Crimes Against Property', 'Administration of Justice',
               'Other Criminal Code', 'Criminal Code Traffic', 'Federal Statute']

# Visually verified in the printed 2016 Ottawa table. The Dog Owners' Liability
# Act count cells are blank while the overall row contains these residual counts.
# Do not allocate the residual to that statute or silently rewrite the total.
EXPECTED_DIFFERENCES = {
    'poa-2016': {'received': (76875,76878), 'no_response': (20824,20825),
                 'before_total': (70785,70786), 'disposed': (78535,78536),
                 'pending': (5068,5070)}
}

def row_counts(series, row):
    if series == 'crim':
        indices = {'received': 2, 'disposed': 4, 'pending': 7, 'before_total': 8,
                   'withdrawn_stayed_before': 9, 'guilty_before': 10, 'other_before': 11,
                   'at_without_total': 12, 'withdrawn_at': 13, 'guilty_at': 14,
                   'other_at': 15, 'following_trial': 16}
    else:
        indices = {'received': 2, 'prepaid': 4, 'guilty_before': 5, 'no_response': 6,
                   'withdrawn_before': 7, 'other_before': 8, 'before_total': 9,
                   'no_attendance': 10, 'guilty_at': 11, 'withdrawn_at': 12,
                   'other_at': 13, 'at_without_total': 14, 'following_trial': 15,
                   'disposed': 16, 'pending': 17}
    return {key: number(row[index]) for key, index in indices.items()}

def reconcile(series, v, context):
    before_keys = ['withdrawn_stayed_before','guilty_before','other_before'] if series == 'crim' else ['prepaid','guilty_before','no_response','withdrawn_before','other_before']
    at_keys = ['withdrawn_at','guilty_at','other_at'] if series == 'crim' else ['no_attendance','guilty_at','withdrawn_at','other_at']
    checks = [(sum(v[k] for k in before_keys),v['before_total']),
              (sum(v[k] for k in at_keys),v['at_without_total']),
              (v['before_total']+v['at_without_total']+v['following_trial'],v['disposed'])]
    for actual, expected in checks:
        if actual != expected:
            raise ValueError(f'{context}: component total {actual} != published {expected}')

def extract(s):
    rows = read_source(s)
    records = []
    s['excluded_empty_rows']=[]
    current_group = ''
    for rownum, row in rows:
        if len(row) < 18:
            continue
        a,b = clean(row[0]),clean(row[1])
        if s['series'] == 'crim':
            if a == 'TOTAL CASES':
                kind, key, label, group = 'total','all','All criminal cases','All criminal cases'
            elif b == 'TOTAL':
                # Canonical group labels keep the filter stable across PDF wrapping.
                current_group = next((g for g in CRIM_GROUPS if slug(a)==slug(g)),a)
                if not current_group:
                    raise ValueError('Missing offence group ' + s['id'])
                kind,key,label,group = 'group','group:'+slug(current_group),current_group,current_group
            elif current_group and b and b not in ('OFFENCE TYPE',):
                kind,key,label,group = 'offence','offence:'+slug(b),b,current_group
            else:
                continue
        else:
            if a.lower() == 'total poa charges':
                kind,key,label,group = 'total','all','All provincial offences','All provincial offences'
            elif 'HIGHWAY TRAFFIC ACT' in (a+' '+b).upper() and 'total' in (a+' '+b).lower():
                kind,key,label,group = 'statute','statute:highway-traffic-act','Highway Traffic Act','Highway Traffic Act'
            elif b and (b.startswith('s.') or 'Other Highway' in b):
                kind,key,label,group = 'offence','hta:'+slug(b),b,'Highway Traffic Act'
            elif a.isupper() and not b and a not in ('STATUTE',):
                kind,key,label,group = 'statute','statute:'+slug(a),a.title(),a.title()
            else:
                continue
        # Headers/footers must not pass as count rows.
        if not any(isinstance(x,(int,float)) or re.fullmatch(r'[\d,]+',str(x or '')) for x in row[2:]):
            s['excluded_empty_rows'].append({'label':label,'source_row':rownum,'reason':'No numeric count cells; unavailable, not assumed zero.'})
            continue
        values = row_counts(s['series'],row)
        context = f"{s['id']} row {rownum} {label}"
        reconcile(s['series'],values,context)
        records.append({'source_id':s['id'],'key':key,'kind':kind,'label':label,'group':group,'source_row':rownum,'values':values})
    all_rows = [r for r in records if r['kind']=='total']
    if len(all_rows)!=1:
        raise ValueError('Expected one total row: ' + s['id'])
    parents=[r for r in records if r['kind'] in ('group','statute')]
    s['hierarchy_differences']=[]
    if len(set(r['key'] for r in records))!=len(records):
        raise ValueError('Duplicate outcome keys: ' + s['id'])
    # Independent hierarchy check: overall totals must equal group/statute totals.
    for metric in all_rows[0]['values']:
        summed=sum(r['values'][metric] for r in parents)
        if summed!=all_rows[0]['values'][metric]:
            s['hierarchy_differences'].append({'level':'overall','metric':metric,'sum_of_children':summed,'published_total':all_rows[0]['values'][metric]})
    for parent in parents:
        children=[r for r in records if r['kind']=='offence' and r['group']==parent['group']]
        if children:
            for metric in parent['values']:
                summed=sum(r['values'][metric] for r in children)
                if summed!=parent['values'][metric]:
                    s['hierarchy_differences'].append({'level':parent['label'],'metric':metric,'sum_of_children':summed,'published_total':parent['values'][metric]})
    s['record_count']=len(records)
    actual={d['metric']:(d['sum_of_children'],d['published_total']) for d in s['hierarchy_differences'] if d['level']=='overall'}
    if actual!=EXPECTED_DIFFERENCES.get(s['id'],{}) or any(d['level']!='overall' for d in s['hierarchy_differences']):
        raise ValueError('Unreviewed source hierarchy difference: '+s['id']+' '+str(s['hierarchy_differences']))
    return records

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
    sources=discover(args.refresh);records=[]
    for source in sources:
        entries=extract(source);records.extend(entries)
        print(source['id'],source['period']['label'],len(entries),'rows OK',flush=True)
        if source['hierarchy_differences']:print('SOURCE HIERARCHY DIFFERENCES',source['hierarchy_differences'],flush=True)
    payload={'reviewed_on':date.today().isoformat(),'index_url':INDEX,'sources':sources,'records':records,
             'blank_policy':'Blank count cells are treated as zero only within validated source rows. Every source row and overall hierarchy reconciles exactly to published totals. Missing rows/periods remain unavailable.',
             'scope':'Ottawa Ontario Court of Justice all criminal cases (includes youth), plus Ottawa City Provincial Offences Act Parts I and III charges. No Superior Court outcomes, individual names or police-officer links.'}
    target=ROOT/'data'/'outcomes.json';target.parent.mkdir(exist_ok=True)
    temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8');temporary.replace(target)
    print('Published',len(records),'validated rows from',len(sources),'source publications.')

if __name__=='__main__': main()

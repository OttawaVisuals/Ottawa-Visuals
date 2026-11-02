"""Source reconciliation and coverage checks; does not update published data."""
from pathlib import Path
import json,re,hashlib
import openpyxl
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';RAW=DATA/'raw'
d=json.loads((DATA/'healthcare.json').read_text(encoding='utf-8'))
checks=0
for sector,funding in [('d4','Ontario government'),('d3','All public sources'),('d2','Private sources')]:
    w=openpyxl.load_workbook(RAW/f'nhex-series-{sector}.xlsx',read_only=True,data_only=True)
    # Reconcile our calculated per-resident values to CIHI's independently supplied table.
    source=list(w['Ont.'].iter_rows(min_row=224,max_row=274,max_col=14,values_only=True))
    for row in d['spending']:
        if row['funding']!=funding:continue
        col={'Hospitals':1,'Physicians':3,'All health care':13}[row['category']]
        original=source[row['year']-1975][col]
        assert abs(row['per_resident_cad']-original)<0.00001,(sector,row['year'],row['category'])
        assert (row['status']=='Forecast')==(row['year']>=2024)
        assert row['real_2023_million_cad']>0
        if row['year']==2023:assert abs(row['million_cad']-row['real_2023_million_cad'])<1e-8
        checks+=1

# Independently sum printed expense components, before any separately shown items.
for h in d['hospitals']:
 for filename in set(r['source_file'] for r in h['financials']):
    txt=(RAW/filename.replace('.pdf','.txt')).read_text(encoding='utf-8')
    page=next(p for p in txt.split('PDF PAGE ') if re.search('statement of operations',p,re.I) and 'Salaries' in p and 'Table of Contents' not in p)
    segment=re.split(r'\n\s*Expenses:?\s*\n',page,flags=re.I)[1]
    segment=re.split(r'\n\s*(?:Excess|Deficiency|\(Deficiency\)|EXCESS)',segment,flags=re.I)[0]
    pairs=[]
    for line in segment.splitlines():
        line=re.sub(r'\(note\s+\d+\)','',line,flags=re.I)
        nums=re.findall(r'(?<!\w)\d{1,3}(?:,\d{3})+(?!\w)|(?<!\w)\d+(?!\w)',line)
        if len(nums)>=2:pairs.append([int(v.replace(',','')) for v in nums[-2:]])
        elif len(nums)==1 and re.search(r'[—–−]',line):pairs.append([0,int(nums[0].replace(',',''))])
    totals=pairs[-1]; summed=[sum(p[i] for p in pairs[:-1]) for i in [0,1]]
    assert totals==summed,(filename,totals,summed)
    factor=1 if h['id']=='montfort' else 1000
    for r in [r for r in h['financials'] if r['source_file']==filename]:
        i=0 if r['source_column']=='Current year' else 1
        assert r['expense_subtotal_cad']==totals[i]*factor
        assert r['compensation_line_cad']<r['expenses_cad']
        assert r['expenses_cad']>=r['expense_subtotal_cad']
        checks+=1
    print('Expense component reconciliation:',filename,totals)

assert len(d['spending'])==459 and len(d['workforce'])==10
assert len({(r['year'],r['funding'],r['category']) for r in d['spending']})==459
for r in d['workforce']:
    assert r['acute_beds']<=r['all_beds'] and r['reporting_organizations']>0
    assert 5<r['fte_per_1000']<30 and 0.5<r['acute_beds_per_1000']<5
for src in json.loads((DATA/'source-manifest.json').read_text()):
    assert hashlib.sha256((RAW/src['file']).read_bytes()).hexdigest()==src['sha256']
    checks+=1
print('PASS:',checks,'source/value checks; coverage, unique keys, forecasts, 2023 adjustment identity and source hashes.')

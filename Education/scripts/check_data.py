"""Source reconciliation, privacy-bound checks and aggregate identities."""
from pathlib import Path
from collections import defaultdict
from openpyxl import load_workbook
import csv, hashlib, json, math

ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/'data/education.json').read_text(encoding='utf-8'))
checks=0
def check(ok,message):
    global checks
    assert ok,message
    checks+=1

for r in json.loads((ROOT/'data/source-manifest.json').read_text()):
    check(hashlib.sha256((ROOT/r['file']).read_bytes()).hexdigest()==r['sha256'],r['file'])
for table in ('37100066','37100067'):
    with (ROOT/f'data/raw/{table}.csv').open(encoding='utf-8-sig',newline='') as f:
        source={(r['REF_DATE'],r['VECTOR']):r for r in csv.DictReader(f) if r['GEO']=='Ontario'}
    for r in D['finance']:
        if r['table']!=table:continue
        raw=source[(r['period'],r['vector'])]
        check(r['cad']==(float(raw['VALUE'])*1000 if raw['VALUE'] else None),f"Financial value {r['vector']} {r['period']}")
        check(r['status']==raw['STATUS'] and r['coordinate']==raw['COORDINATE'],'Source metadata')
        if r['year']==2023 and r['cad'] is not None:check(r['real_cad']==r['cad'],'2023-24 price base')

cpi={r['year']:r['value'] for r in D['cpi']}
for r in D['finance']:
    if r['real_cad'] is not None:
        expected=r['cad']*((cpi[2023]+cpi[2024])/(cpi[r['year']]+cpi[r['year']+1]))
        check(math.isclose(r['real_cad'],expected,rel_tol=1e-12),'CPI factor')

school_sums=defaultdict(lambda:defaultdict(int))
fields=['classes','students_low','students_high','suppressed_classes','over25_low','over25_high']
for r in D['schools']:
    for field in fields:school_sums[(r['year'],r['geo'],r['group'])][field]+=r[field]
for r in D['classes']:
    check(r['classes']>0 and 0<=r['suppressed_classes']<=r['classes'],'Class count')
    check(0<r['students_low']<=r['students_high'],'Suppression bound')
    check(0<=r['over25_low']<=r['over25_high']<=r['classes'],'Threshold bound')
    if r['geo']!='ontario':
        check(all(r[f]==school_sums[(r['year'],r['geo'],r['group'])][f] for f in fields),'School to board reconciliation')
    if r['group']=='all':
        check(r['year']>=2014,'Early full-coverage claim')
        parts=[x for x in D['classes'] if x['year']==r['year'] and x['geo']==r['geo'] and x['group']!='all']
        check(all(sum(x[f] for x in parts)==r[f] for f in fields),'Grade-group identity')
for geo in D['boards']:
    years=[r['year'] for r in D['classes'] if r['geo']==geo and r['group']=='all']
    check(years==list(range(2014,2026)),f'{geo} history and current aliases')

# Independent import of all latest workbook rows, using the spreadsheet reader rather than the builder's XML reader.
latest=ROOT/'data/raw/2025-26_elementary_class_sizes_open_data1.xlsx'
w=load_workbook(latest,read_only=True,data_only=True)
aliases={'Ottawa-Carleton DSB':'ocdsb','Ottawa CSB':'ocsb',"CÉP de l'Est de l'Ontario":'cepeo',"CSDC du Centre-Est de l'Ontario":'cecce'}
totals=defaultdict(lambda:[0,0,0,0,0,0])
source_rows=zero_rows=0
for row in w.worksheets[0].iter_rows(min_row=2,max_col=10,values_only=True):
    if not row[1]:continue
    source_rows+=1;cells=row[4:10]
    low=sum(1 if v=='<5' else int(v) for v in cells)
    high=sum(4 if v=='<5' else int(v) for v in cells)
    if high==0:zero_rows+=1;continue
    for geo in ['ontario']+([aliases[row[1]]] if row[1] in aliases else []):
        vals=[1,low,high,int(low!=high),int(low>25),int(high>25)]
        totals[geo]=[a+b for a,b in zip(totals[geo],vals)]
w.close()
for geo,values in totals.items():
    r=next(r for r in D['classes'] if r['year']==2025 and r['group']=='all' and r['geo']==geo)
    check([r[f] for f in fields]==values,f'Independent 2025-26 source import: {geo}')
coverage=next(r for r in D['coverage'] if r['year']==2025)
check(coverage['source_rows']==source_rows and coverage['zero_rows']==zero_rows,'Latest coverage and empty rows')
for year in (2007,2014):
    w=load_workbook(ROOT/'data/raw/2007-08_to_2022-23_class_size_data_june_15.xlsx',read_only=True,data_only=True)
    rows=w[f'{year}-{str(year+1)[-2:]}'].iter_rows(min_row=2,max_row=2,values_only=True)
    row=next(rows);check(row[1]=='Algoma District School Board' and sum(row[4:10])>0,'Historical source cell smoke check');w.close()
print(f'PASS: {checks} financial/source, suppression and aggregate checks, including an independent full 2025-26 workbook import.')

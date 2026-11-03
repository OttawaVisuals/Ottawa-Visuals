"""Aggregate Alberta's separate November 2025 classroom snapshot. No student IDs exported."""
from pathlib import Path
from collections import defaultdict
import csv, hashlib, json
import requests
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/alberta'
RAW.mkdir(exist_ok=True)
CATALOGUE='https://open.alberta.ca/api/3/action/package_show?id=alberta-class-size'
if not (RAW/'catalogue.json').exists():
    response=requests.get(CATALOGUE,timeout=90);response.raise_for_status()
    (RAW/'catalogue.json').write_text(json.dumps(response.json()['result']),encoding='utf-8')
catalogue=json.loads((RAW/'catalogue.json').read_text(encoding='utf-8'))
resource=next(r for r in catalogue['resources'] if '2025' in r['name'])
path=RAW/'ecc-alberta-class-size-2025-2026.xlsx'
if not path.exists():
    response=requests.get(resource['url'],timeout=90);response.raise_for_status();path.write_bytes(response.content)
w=load_workbook(path,read_only=True,data_only=True)
metadata=[r[1] for r in w['Metadata'].values if r[1]]
areas={'alberta':'Alberta · published classrooms'}
groups={'all':'All published bands · K–12','K-3':'Kindergarten–Grade 3','G4-6':'Grades 4–6','G7-9':'Grades 7–9','G10-12':'Grades 10–12'}
agg=defaultdict(lambda:dict(classes=0,suppressed=0,above21=0,above23=0))
ids=set()
for uid,authority,code,school_code,school,band,size in w['Class Size'].iter_rows(min_row=2,values_only=True):
    assert uid and uid not in ids, 'Duplicate or missing classroom identifier'
    ids.add(uid)
    assert band in groups and band!='all',repr(band)
    assert size=='*' or isinstance(size,(int,float)) and int(size)==size and 10<=size<=60,repr(size)
    geo='ab-'+str(code);areas[geo]=authority
    for area in ['alberta',geo]:
        for group in ['all',band]:
            a=agg[area,group];a['classes']+=1;a['suppressed']+=size=='*'
            if size!='*':a['above21']+=size>21;a['above23']+=size>23
rows=[dict(geo=geo,group=group,**agg[geo,group]) for geo in areas for group in groups]
for geo in areas:
    for field in ['classes','suppressed','above21','above23']:
        assert agg[geo,'all'][field]==sum(agg[geo,g][field] for g in groups if g!='all')
        for group in groups:assert agg[geo,group]['above23']<=agg[geo,group]['above21']<=agg[geo,group]['classes']-agg[geo,group]['suppressed']
for group in groups:
    for field in ['classes','suppressed','above21','above23']:
        assert agg['alberta',group][field]==sum(agg[g,group][field] for g in areas if g!='alberta')
data=dict(year=2025,count_date='2025-11-24',areas=areas,groups=groups,counts=rows,metadata=metadata,
          source_url=resource['url'],catalogue_url='https://open.alberta.ca/opendata/alberta-class-size',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
          method='One published row per teacher and unique student group for a portion of instructional time. Students can recur across rows. Suppressed sizes are 1–9 and therefore below both OECD cutoffs; they remain in denominators. Excludes alternative, outreach/online and special-purpose schools and special-education subjects. Not a census of every Alberta classroom. No historical series is inferred.')
for filename,prefix,suffix in [('alberta.json','','\n'),('alberta-data.js','window.ALBERTA_CLASSES=',';\n')]:
    (ROOT/'data'/filename).write_text(prefix+json.dumps(data,ensure_ascii=False,separators=(',',':'))+suffix,encoding='utf-8')
with (ROOT/'data/alberta-class-thresholds.csv').open('w',encoding='utf-8-sig',newline='') as f:
    records=[dict(year=2025,count_date=data['count_date'],area=areas[r['geo']],grade_band=groups[r['group']],**r) for r in rows]
    writer=csv.DictWriter(f,fieldnames=records[0]);writer.writeheader();writer.writerows(records)
print(f'Alberta: {len(ids)} published classroom rows, {len(areas)-1} authorities; {len(rows)} aggregates. Population and nested-count checks pass.')
print(agg['alberta','all'])

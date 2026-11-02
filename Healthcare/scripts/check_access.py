"""Reconcile exported access data to retained official sources and guard scope breaks."""
from pathlib import Path
import csv,json,hashlib,math
import openpyxl
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';RAW=DATA/'raw'
A=json.loads((DATA/'access.json').read_text(encoding='utf-8'))
checks=0
def value(v):
 try:return float(v)
 except (TypeError,ValueError):return None
assert len(A['er'])==312
assert len({(r['site_id'],r['metric'],r['month']) for r in A['er']})==312
assert len(A['er_sites'])==6 and len({r['month'] for r in A['er']})==13
ontario={(r['metric'],r['month']):r for r in A['er'] if r['site_id']==-354}
for r in A['er']:
 source=json.loads((RAW/r['source_file']).read_text())[r['source_index']]
 assert source['Org_ID']==r['site_id'] and source['Key']==r['month']
 for original,field in [('WaitTime_mean','mean_hours'),('WaitTime_90percentile','p90_hours'),('number_of_cases','visits')]:
  assert value(source[original])==r[field]
 assert r['mean_hours'] is None or r['mean_hours']>=0
 assert r['p90_hours'] is None or r['p90_hours']>=0
 assert r['visits'] is None or (r['visits']>=0 and r['visits'].is_integer())
 checks+=1
# Each site's export carries a separately returned Ontario series. It must agree.
for fn in {r['source_file'] for r in A['er']}:
 for source in json.loads((RAW/fn).read_text()):
  if source['Org_ID']!=-354:continue
  match=ontario[(source['ResultType'],source['Key'])]
  assert value(source['WaitTime_mean'])==match['mean_hours']
  assert value(source['WaitTime_90percentile'])==match['p90_hours']
  checks+=1
# Independent latest hospital comparison table, including Ontario.
for source in json.loads((RAW/'er-sites.json').read_text()):
 if source['SNum'] not in {r['id'] for r in A['er_sites']}:continue
 row=next(r for r in A['er'] if r['site_id']==source['SNum'] and r['metric']=='PIA' and r['month']==source['Key'])
 assert row['mean_hours']==source['LOS_mean'];checks+=1
soup=BeautifulSoup((RAW/'fao-er-history.html').read_text(encoding='utf-8'),'html.parser')
for r in A['er_history']:
 t=soup.find('table',id=r['source_table'])
 cells=next([c.get_text(' ',strip=True) for c in row.select('td')] for row in t.select('tr') if row.select('td') and row.select('td')[0].get_text(strip=True)==r['period'])
 assert float(cells[1])==r['mean_hours']
 assert r['partial']==(r['period']=='2022-23')
 checks+=1
raw=list(csv.DictReader((DATA/'provider-source-rows.csv').open(encoding='utf-8')))
w=openpyxl.load_workbook(RAW/'cihi-primary-care.xlsx',read_only=True,data_only=True)
cihi=list(w['Table 1'].iter_rows(max_col=30,values_only=True))
for r in A['provider']:
 assert 0<=r['has_low']<=r['has_percent']<=r['has_high']<=100
 assert 0<=r['without_low']<=r['without_percent']<=r['without_high']<=100
 for target,source in [('without_percent','has_percent'),('without_low','has_high'),('without_high','has_low')]:assert abs(r[target]-(100-r[source]))<1e-8
 if r['series']=='Historical Ottawa comparison':
  source=next(s for s in raw if s['VECTOR']==r['source_vector'] and s['REF_DATE']==r['period'])
  assert source['GEO']==r['source_geography'] and source['REF_DATE']==r['period']
  assert float(source['VALUE'])==r['has_percent'] and source['STATUS']==r['status']
  for characteristic,key in [('Low 95% confidence interval, percent','has_low'),('High 95% confidence interval, percent','has_high')]:
   match=next(s for s in raw if s['GEO']==source['GEO'] and s['REF_DATE']==source['REF_DATE'] and s['Characteristics']==characteristic)
   assert float(match['VALUE'])==r[key]
  assert r['age']=='12 years and older'
  assert r['break_before']==(r['period']=='2021/2022')
 else:
  source=next(s for s in cihi[2:] if s[2]=='Ontario' and s[9]=='Adults' and s[12]=='Not applicable' and s[11]==r['period'])
  assert list(source[14:17])==[r['has_percent'],r['has_low'],r['has_high']]
  assert r['break_before'] and r['age']=='18 years and older'
 checks+=1
assert len(A['provider'])==11
for r in json.loads((DATA/'access-source-manifest.json').read_text()):
 assert hashlib.sha256((RAW/r['file']).read_bytes()).hexdigest()==r['sha256'];checks+=1
print(f'PASS: {checks} source-record/hash reconciliations; monthly coverage, duplicate Ontario comparators, annual partial endpoint, survey intervals and definition/age breaks.')

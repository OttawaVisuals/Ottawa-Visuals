"""Build Ottawa CPI factors and an adjusted export; 2026 uses a labelled YTD proxy."""
from pathlib import Path
import csv
import hashlib
import json
import statistics
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
API='https://www150.statcan.gc.ca/t1/wds/rest/getDataFromCubePidCoordAndLatestNPeriods'
COORD='15.2.0.0.0.0.0.0.0.0'
REVIEWED='2026-10-23'

def fetch(pid,n):
 p=Path(tempfile.gettempdir())/f'ottawa-cpi-{pid}.json'
 if not p.exists():
  req=urllib.request.Request(API,data=json.dumps([{'productId':pid,'coordinate':COORD,'latestN':n}]).encode(),headers={'Content-Type':'application/json'})
  p.write_bytes(urllib.request.urlopen(req,timeout=60).read())
 payload=json.loads(p.read_bytes())[0]
 assert payload['status']=='SUCCESS','CPI retrieval failed'
 return payload['object']['vectorDataPoint'],hashlib.sha256(p.read_bytes()).hexdigest()

annual,annual_hash=fetch(18100005,5)
monthly,monthly_hash=fetch(18100004,24)
indices={r['refPer'][:4]:r['value'] for r in annual if r['value'] is not None and r['refPer'][:4] in ['2023','2024','2025']}
assert set(indices)=={'2023','2024','2025'}
months={r['refPer'][:7]:r['value'] for r in monthly if r['refPer'].startswith('2026-') and r['value'] is not None}
assert list(sorted(months))==[f'2026-{m:02d}' for m in range(1,len(months)+1)],'YTD months must be consecutive from January'
assert len(months)==9,'Review the CPI cutoff and page labels before updating this snapshot'
indices['2026']=statistics.mean(months.values())
data={'reviewed':REVIEWED,'geography':'Ottawa-Gatineau, Ontario part, Ontario/Quebec','product':'All-items CPI, not seasonally adjusted','index_base':'2002=100','base_year':2025,'annual_indices':indices,'provisional_years':[2026],'monthly_2026':months,'factors':{year:indices['2025']/value for year,value in indices.items()},'formula':'2025 dollars = nominal dollars × 2025 annual CPI / year CPI','annual_source':'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000501','monthly_source':'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401','coordinate':COORD,'annual_response_sha256':annual_hash,'monthly_response_sha256':monthly_hash,'note':'2026 uses the January–September monthly CPI average as a provisional proxy for annual CPI. It is not a full-year index or a forecast. CPI measures consumer prices, not municipal wages, construction or procurement costs.'}
dest=ROOT/'data'
(dest/'inflation.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (dest/'inflation.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['year','cpi_index_2002_100','period','factor_to_2025_dollars','status','source'])
 for year,index in indices.items():w.writerow([year,index,'January–September average' if year=='2026' else 'annual average',data['factors'][year],'provisional' if year=='2026' else 'annual',data['monthly_source'] if year=='2026' else data['annual_source']])
with (dest/'budget-inflation-adjusted.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['view','category','year','nominal_cad_thousands','cad_2025_thousands','cpi_index','cpi_status','source_url','pdf_page'])
 history=json.loads((dest/'history.json').read_text(encoding='utf-8'))
 for r in history['rows']+[{'name':'Total budget expenses','values':history['totals']}]:
  for year,value in r['values'].items():w.writerow(['full_accrual_history',r['name'],year,value,round(value*data['factors'][year],6),indices[year],'provisional Jan–Sep CPI' if year=='2026' else 'annual CPI',history['sources'][year]['url'],history['sources'][year]['pdf_page']])
 budget=json.loads((dest/'budget.json').read_text(encoding='utf-8'))
 for view in ['operating','capital','revenue']:
  for r in budget[view]:
   for year in ['2025','2026']:
    value=r['budget_'+year];w.writerow([view,r['name'],year,value,round(value*data['factors'][year],6),indices[year],'provisional Jan–Sep CPI' if year=='2026' else 'annual CPI',budget['source_url'],r['pdf_page']])
print('Built Ottawa CPI factors and adjusted export; 2026 proxy:',indices['2026'])

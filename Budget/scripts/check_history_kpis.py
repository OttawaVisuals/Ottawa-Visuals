"""Check history accounting, KPI meaning/units, source coverage and local-file package."""
from pathlib import Path
import csv
import json
import re

ROOT=Path(__file__).resolve().parents[1]
data=ROOT/'data'
h=json.loads((data/'history.json').read_text(encoding='utf-8'))
k=json.loads((data/'kpis.json').read_text(encoding='utf-8'))
checks=0
def check(value,message):
 global checks
 assert value,message
 checks+=1

check(h['years']==[2023,2024,2025,2026],'Budget coverage')
check(h['totals']=={'2023':4458244,'2024':4586778,'2025':4898070,'2026':5288959},'Full-accrual budgets, not operating cash budget or actual spending')
for year in h['years']:
 year=str(year)
 check(abs(sum(r['values'][year] for r in h['rows'])-h['totals'][year])<=3,'Function sum '+year)
 check(len(h['sources'][year]['sha256'])==64 and h['sources'][year]['pdf_page'] in [14,15],'Year provenance')
check(len(h['rows'])==10 and len({r['name'] for r in h['rows']})==10,'One row per function')
for before in h['years']:
 for after in h['years']:
  if after<=before:continue
  delta_sum=sum(r['values'][str(after)]-r['values'][str(before)] for r in h['rows'])
  check(abs(delta_sum-(h['totals'][str(after)]-h['totals'][str(before)]))<=3,'Change reconciliation')
health=next(r for r in h['rows'] if r['name']=='Health services')
check(health['values']['2024']<health['values']['2023'],'A decrease remains negative, not absolute-valued')

for group,g in k['groups'].items():
 check(len({m['id'] for m in g['metrics']})==len(g['metrics']),'Unique metric IDs')
 for m in g['metrics']:
  check(len(m['values'])>=2,'Enough dated observations')
  check(m['source'] in k['sources'] and m['pdf_page']>0,'Source locator')
  check(all(isinstance(v,(int,float)) and v>=0 for v in m['values'].values()),'Numeric nonnegative observations')
  if m['unit'] in ['percent','index']:check(all(v<=100 for v in m['values'].values()),'Valid 0–100 scale')
  if group!='paramedics':check(m['target'] is None,'Do not invent housing/infrastructure targets')
  if group=='infrastructure':check(set(m['values'])=={'2019','2023'},'No interpolated condition years')
  if group=='housing':check(set(m['values'])==set(map(str,range(2019,2025))),'Housing annual coverage')
para={m['id']:m for m in k['groups']['paramedics']['metrics']}
check(para['ctas1-city']['values']['2025']==70.4 and para['ctas1-city']['target']==75,'Citywide CTAS 1 outcome and target')
check(para['ctas1-rural']['values']['2025']==24.6 and para['ctas1-urban']['values']['2025']==73.6,'Preserve regional results')
check(para['cardiac']['target']==65 and 'any person' in para['cardiac']['definition'],'AED measure has different responder and target')
check(para['level-zero']['values']['2024']==11372 and para['level-zero']['values']['2025']==866,'Exact Level Zero minutes, not rounded news figures')
housing={m['id']:m for m in k['groups']['housing']['metrics']}
check(housing['waitlist']['values']['2024']==15140 and 'December 10' in housing['waitlist']['note'],'Partial-year wait-list date')
check(housing['placements']['values']['2024']==1089,'Housing placement count')
check(housing['shelter-users']['direction']=='context','Shelter use does not imply better/worse outcomes by itself')
check(sum(c['value'] for c in k['groups']['infrastructure']['condition_snapshot']['categories'])==100,'Weighted condition distribution')

package=(data/'page-data.js').read_text(encoding='utf-8').split('window.OTTAWA_BUDGET_DATA = ',1)[1].strip().removesuffix(';')
bundled=json.loads(package)
for name in ['budget','lansdowne','history','kpis']:
 check(bundled[name]==json.loads((data/(name+'.json')).read_text(encoding='utf-8')),'Packaged snapshot matches '+name)
for name,expected in [('history',44),('kpis',114)]:
 with (data/(name+'.csv')).open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
 # KPI export covers all series plus the five condition categories.
 if name=='kpis':expected=sum(len(m['values']) for g in k['groups'].values() for m in g['metrics'])+5
 check(len(rows)==expected,'Export row coverage '+name)
html=(ROOT/'budget.html').read_text(encoding='utf-8')
ids=re.findall(r'\bid="([^"]+)"',html)
check(len(ids)==len(set(ids)),'Unique HTML IDs')
for script in ['budget.js','history-kpis.js']:
 for ref in re.findall(r"\$\('([^']+)'\)",(ROOT/script).read_text(encoding='utf-8')):
  check(ref in ids,'DOM target exists '+ref)
print(f'{checks} history, KPI, provenance, export and package checks passed.')

"""Source and accounting checks for the budget page. No network required."""
from pathlib import Path
import csv
import json
import re

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/budget.json').read_text(encoding='utf-8'))
project=json.loads((ROOT/'data/lansdowne.json').read_text(encoding='utf-8'))
html=(ROOT/'budget.html').read_text(encoding='utf-8')
checks=0
def check(condition,message):
    global checks
    assert condition,message
    checks+=1

for kind,count in [('operating',17),('capital',11),('revenue',11)]:
    rows=data[kind]
    check(len(rows)==count,f'{kind} category count')
    check(len({r['name'] for r in rows})==len(rows),f'{kind} unique categories')
    for year in ['2025','2026']:
        total=data['totals']['capital' if kind=='capital' else 'operating'][year]
        check(abs(sum(r['budget_'+year] for r in rows)-total)<=5,f'{kind} {year} reconciles')
    for row in rows:
        check(all(isinstance(row['budget_'+y],int) and row['budget_'+y]>=0 for y in ['2025','2026']),f'Valid units for {row["name"]}')
        for year in ['2025','2026']:
            if row.get('children'):check(abs(sum(c['budget_'+year] for c in row['children'])-row['budget_'+year])<=2,f'Child reconciliation {row["name"]} {year}')
for year,expected in [('2025',499172),('2026',532102)]:
    check(sum(r['budget_'+year] for r in data['operating'] if r['funding']=='rate')==expected,'Rate classification')
transit=next(r for r in data['operating'] if r['name']=='Transit')
check((transit['budget_2025'],transit['budget_2026'])==(818256,904760),'Budget columns, not actuals or net tax requirement')
lib=next(r for r in data['operating'] if r['name']=='Libraries')
check(lib['budget_2026']==74188,'Library operating expense, not $69.220M net requirement')
check(abs(sum(r['amount'] for r in project['scope'])-483.9)<1e-8,'Project scopes sum')
check(abs(sum(r['amount'] for r in project['financing'])-418.9)<1e-8,'Rounded financing sum')
check(round(project['reported_spend']/project['main_budget']*100,1)==14.2,'Spend share')
for key in ['main_budget','reported_spend','city_modelled_net_investment']:
    check(f"${project[key]:.1f}M" in html,'Static project fallback matches JSON')
check('14.2 percent' in html and '14.2%' in html,'Accessible spending share')
for href in re.findall(r'href="([^"]+)"',html):
    if not href.startswith(('http','#')):
        check((ROOT/href.split('?')[0]).exists(),f'Local link exists: {href}')
with (ROOT/'data/budget.csv').open(encoding='utf-8',newline='') as f: exported=list(csv.DictReader(f))
check(len(exported)==78,'CSV covers all overview categories and both years')
check(len(data['source_sha256'])==64,'Source fingerprint')
print(f'{checks} accounting, source, scope and file checks passed.')

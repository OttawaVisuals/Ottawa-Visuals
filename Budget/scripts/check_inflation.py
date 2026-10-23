"""Check CPI factors, export arithmetic and packaged source consistency."""
from pathlib import Path
import csv
import json
import statistics
import math

root=Path(__file__).resolve().parents[1]/'data'
cpi=json.loads((root/'inflation.json').read_text(encoding='utf-8'))
assert cpi['base_year']==2025
assert cpi['annual_indices']['2025']==166.3
assert cpi['annual_indices']['2023']==159.2
assert cpi['annual_indices']['2024']==162.8
assert len(cpi['monthly_2026'])==9 and cpi['provisional_years']==[2026]
assert math.isclose(cpi['annual_indices']['2026'],statistics.mean(cpi['monthly_2026'].values()))
assert cpi['factors']['2025']==1
assert cpi['factors']['2023']>1 and cpi['factors']['2026']<1
for y,factor in cpi['factors'].items():assert math.isclose(factor*cpi['annual_indices'][y],166.3)
with (root/'budget-inflation-adjusted.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==122
for r in rows:
 assert abs(float(r['cad_2025_thousands'])-float(r['nominal_cad_thousands'])*cpi['factors'][r['year']])<0.000001
 assert ('provisional' in r['cpi_status'])==(r['year']=='2026')
h=json.loads((root/'history.json').read_text(encoding='utf-8'))
for a,b in [(2023,2024),(2023,2026),(2025,2026)]:
 nominal_growth=h['totals'][str(b)]/h['totals'][str(a)]-1
 real_growth=h['totals'][str(b)]*cpi['factors'][str(b)]/(h['totals'][str(a)]*cpi['factors'][str(a)])-1
 assert real_growth<nominal_growth
 for year in [a,b]:
  assert abs(sum(r['values'][str(year)]*cpi['factors'][str(year)] for r in h['rows'])-h['totals'][str(year)]*cpi['factors'][str(year)])<=4
bundled=json.loads((root/'page-data.js').read_text(encoding='utf-8').split('window.OTTAWA_BUDGET_DATA = ',1)[1].strip().removesuffix(';'))
assert bundled['inflation']==cpi
print('CPI source, 2026 provisional coverage, base-year identity, 122 export rows and real-growth checks passed.')

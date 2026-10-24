"""Reconcile published adult prices and generated changes without fetching data."""
import csv
import json
import math
import statistics
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'data/transit-fares.json').read_text(encoding='utf-8'))
series = json.loads((root / 'data/transit-fares-series.json').read_text(encoding='utf-8'))['records']
cpi = json.loads((root / 'data/inflation.json').read_text(encoding='utf-8'))
assert len(series) == 15
assert [r['year'] for r in data['years']] == [2022,2023,2024,2025,2026]
assert data['years'][0]['adult_card'] == 3.70 and data['years'][0]['adult_cash'] == 3.75, 'Do not mix card and cash'
for product in data['products']:
    rows = [r for r in series if r['product'] == product['id']]
    prices = [r[product['field']] for r in data['years']]
    assert rows[0]['annual_increase_pct'] is None and rows[0]['change_cad'] is None
    assert prices[0] == prices[1] and rows[1]['annual_increase_pct'] == 0, 'Verify 2023 freeze'
    for i,r in enumerate(rows):
        assert r['price_cad'] == prices[i]
        assert abs(r['cumulative_fare_pct'] - (prices[i]/prices[0]-1)*100) < 1e-9
        if i:
            assert abs(r['annual_increase_pct'] - (prices[i]/prices[i-1]-1)*100) < 1e-9
        endpoint = statistics.mean(cpi['monthly_2026_jan_sep'].values()) if r['year']==2026 else cpi['annual_indices'][str(r['year'])]
        assert abs(r['cumulative_cpi_pct'] - (endpoint/cpi['annual_indices']['2022']-1)*100) < 1e-9
    compound = (math.prod(1 + r['annual_increase_pct']/100 for r in rows[1:])-1)*100
    assert abs(compound-rows[-1]['cumulative_fare_pct']) < 1e-9
card2024 = next(r for r in series if r['product']=='card' and r['year']==2024)
assert round(card2024['annual_increase_pct'],2) == 2.70, 'Use actual price rounding, not the 2.5% headline'
with (root / 'data/transit-fares.csv').open(encoding='utf-8',newline='') as f:
    exported = list(csv.DictReader(f))
assert len(exported)==15
for out,r in zip(exported,series):
    assert out['product']==r['product'] and int(out['year'])==r['year']
    for field in ['price_cad','annual_increase_pct','cumulative_fare_pct','annual_cpi_pct','cumulative_cpi_pct']:
        if r[field] is None:
            assert out[field]==''
        else:
            assert abs(float(out[field])-r[field]) < .000001
    assert out['source_url'] in [s['url'] for s in data['sources'].values()]
print('PASS: 15 fare observations; 2023 freeze; card/cash separation; rounding; cumulative compounding; CPI endpoints; CSV reconciliation.')

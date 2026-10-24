"""Check CPI denominators, historical scope and generated downloads offline."""
import csv
import json
import statistics
import math
from pathlib import Path

root = Path(__file__).resolve().parents[1]
tax = json.loads((root / 'data/property-tax.json').read_text(encoding='utf-8'))
cpi = json.loads((root / 'data/inflation.json').read_text(encoding='utf-8'))
assert [r['year'] for r in tax['years']] == list(range(2013, 2027))
assert cpi['geography'] == 'Ottawa-Gatineau, Ontario part, Ontario/Quebec'
assert cpi['product'] == 'All-items CPI, not seasonally adjusted'
for year in range(2013, 2026):
    expected = (cpi['annual_indices'][str(year)] / cpi['annual_indices'][str(year - 1)] - 1) * 100
    assert abs(expected - cpi['inflation_pct'][str(year)]) < .000001
for year in [2025, 2026]:
    assert set(cpi[f'monthly_{year}_jan_sep']) == {f'{year}-{m:02}' for m in range(1, 10)}
expected = (statistics.mean(cpi['monthly_2026_jan_sep'].values()) /
            statistics.mean(cpi['monthly_2025_jan_sep'].values()) - 1) * 100
assert abs(expected - cpi['inflation_pct']['2026']) < .000001
assert cpi['provisional_years'] == [2026]
with (root / 'data/property-tax.csv').open(encoding='utf-8', newline='') as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 14
for row, source in zip(rows, tax['years']):
    assert int(row['year']) == source['year']
    assert float(row['adopted_overall_increase_pct']) == source['increase_pct']
    assert row['source_url'] == tax['sources'][source['source']]['url']
    assert float(row['ottawa_inflation_pct']) == cpi['inflation_pct'][row['year']]
    if int(row['year']) < 2023:
        assert not row['campaign_lower_pct'] and not row['campaign_upper_pct']
        assert not row['gap_to_upper_percentage_points']
    else:
        assert float(row['gap_to_upper_percentage_points']) == round(source['increase_pct'] - 2.5, 2)
assert [r['commitment_type'] for r in rows[-4:]] == ['Firm commitment', 'Firm commitment', 'Target', 'Target']
assert 'provisional' in rows[-1]['inflation_period']
with (root / 'data/property-tax-cumulative.csv').open(encoding='utf-8', newline='') as f:
    cumulative = list(csv.DictReader(f))
assert len(cumulative) == 18
for row in cumulative:
    baseline, year = int(row['baseline_year']), int(row['year'])
    rates = [r['increase_pct'] for r in tax['years'] if baseline < r['year'] <= year]
    expected_tax = (math.prod(1 + rate / 100 for rate in rates) - 1) * 100
    endpoint = statistics.mean(cpi['monthly_2026_jan_sep'].values()) if year == 2026 else cpi['annual_indices'][str(year)]
    expected_cpi = (endpoint / cpi['annual_indices'][str(baseline)] - 1) * 100
    assert abs(float(row['compounded_tax_increase_pct']) - expected_tax) < .000001
    assert abs(float(row['cumulative_ottawa_cpi_pct']) - expected_cpi) < .000001
two_years = next(r for r in cumulative if r['baseline_year'] == '2022' and r['year'] == '2024')
assert float(two_years['compounded_tax_increase_pct']) == 5.0625, 'Compound, do not sum'
print('PASS: 14 years, CPI geography/product, annual denominators, matched Jan–Sep comparison, historical scope and CSV reconciliation.')
print('PASS: 18 cumulative observations, two baselines, compounded taxes and direct CPI endpoints including partial 2026.')

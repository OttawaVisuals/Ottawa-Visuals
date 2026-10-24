"""Reconcile aggregates, detail and export scopes against the reviewed City table."""
import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from build_savings import build

root = Path(__file__).resolve().parents[1]
d = json.loads((root / 'data/savings.json').read_text(encoding='utf-8'))
rows = d['years']
assert [r['year'] for r in rows] == [2023, 2024, 2025, 2026]
assert [r['total_cad_thousands'] for r in rows] == [53918, 99585, 54245, 44924]
assert sum(r['operating_cad_thousands'] for r in rows) == 137648
assert sum(r['capital_cad_thousands'] for r in rows) == 115024
assert sum(r['total_cad_thousands'] for r in rows[:3]) == 207748
assert sum(r['total_cad_thousands'] for r in rows) == 252672
for r in rows:
    assert r['operating_cad_thousands'] + r['capital_cad_thousands'] == r['total_cad_thousands']
    assert r['recurrence'] == 'Unknown'
assert 'draft' in rows[-1]['evidence_status']
assert not d['promise']['annual_target_verified']
assert not d['promise']['recurrence_verified']
assert len(d['items_2026']) == 14
assert sum(r['operating_cad_thousands'] for r in d['items_2026']) == rows[-1]['operating_cad_thousands']
assert sum(r['operating_cad_thousands'] for r in d['items_2026'] if r['group'] == 'Service review') == 6584
assert sum(r['operating_cad_thousands'] for r in d['items_2026'] if r['group'] == 'Department initiatives') == 20050
with (root / 'data/savings.csv').open(encoding='utf-8', newline='') as f:
    exported = list(csv.DictReader(f))
assert len(exported) == 4
assert sum(int(r['total_cad_thousands']) for r in exported) == 252672
with (root / 'data/savings-2026-items.csv').open(encoding='utf-8', newline='') as f:
    items = list(csv.DictReader(f))
assert len(items) == 14 and sum(int(r['operating_cad_thousands']) for r in items) == 44924
for r in items:
    assert r['classification'] and r['explanation'] and r['remaining_gap'] and r['evidence_basis']
    assert r['detail_source_url'] in [s['url'] for s in d['sources'].values()]
transit = d['transit_review']
assert sum(r['cad_thousands'] for r in transit['draft_notes']) == 2363 == transit['adopted_service_initiatives_savings_cad_thousands']
assert not transit['bridge_verified'] and not transit['net_electric_bus_cost_verified'] and not transit['realization_verified']
assert transit['headline_cad_thousands'] == 14031
public_html = (root / 'promises.html').read_text(encoding='utf-8')
assert 'id="savings"' not in public_html and 'href="#savings"' not in public_html
html = build()
chart = ET.fromstring(re.search(r'<svg class="savings-svg".*?</svg>', html, re.S).group())
bars = [n for n in chart.iter('rect')]
assert len(bars) == 7 and sum('draft' in n.attrib['class'] for n in bars) == 1
assert all(float(n.attrib['height']) > 0 for n in bars)
assert 'No annual $35M target is inferred.' in html
assert len(re.findall(r'id="savings"', html)) == 1
assert 'Under review: the headline totals need a fuller breakdown.' in html
assert re.search(r'<details id="savings-aggregate-context">', html), 'Aggregate chart must be collapsed context, not a score'
assert re.search(r'<details id="savings-item-evidence">', html)
print('Savings checks passed: totals, 14 evidence gaps, separate transit scopes, unknown net costs and retained analysis and hidden public section.')

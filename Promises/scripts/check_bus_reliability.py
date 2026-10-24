"""Validate reuse of official observations, targets, periods and chart gaps."""
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = json.loads((root/'data/bus-reliability.json').read_text(encoding='utf-8'))
source = root.parent/'OC_Transpo/kpi_history/kpi_series.csv'
assert hashlib.sha256(source.read_bytes()).hexdigest() == data['archive_sha256']
with source.open(encoding='utf-8-sig',newline='') as f:
    original = list(csv.DictReader(f))
with (root/'data/bus-reliability.csv').open(encoding='utf-8',newline='') as f:
    exported = list(csv.DictReader(f))
assert len(exported)==len(data['records'])
for r in data['records']:
    matches = [s for s in original if all(s[k]==r[k] for k in ['metric','mode','breakdown','period','period_type'])]
    assert len(matches)==1 and float(matches[0]['value'])==r['value']
    assert r['mode']=='bus' and not r['breakdown']
    assert r['period_type'] in ('year','month')
    assert not (r['period']=='2026' and r['period_type']=='year')
    assert r['period']!='2022', 'No complete annual 2022 baseline'
    if 'kpi_snapshots/' in r['source_file']:
        assert r['source_url'].endswith('.xlsx')
        assert (root/r['source_url']).resolve().exists()
for metric, target in data['targets'].items():
    assert target['period']=='edition 2026' and target['breakdown']=='target'
    assert target['value']==next(float(s['value']) for s in original if s['metric']==metric and s['mode']=='bus' and s['period']=='edition 2026' and s['breakdown']=='target')
html = (root/'promises.html').read_text(encoding='utf-8')
charts = [ET.fromstring(s) for s in re.findall(r'<svg class="bus-svg".*?</svg>',html,re.S)]
assert len(charts)==6
for metric in [m['metric'] for m in data['metrics']]:
    annual = next(s for s in charts if s.find('title').attrib['id']==metric+'-annual-title')
    monthly = next(s for s in charts if s.find('title').attrib['id']==metric+'-monthly-title')
    rs = [r for r in data['records'] if r['metric']==metric and r['period_type']=='month']
    observed = {r['period'] for r in rs}
    adjacent = sum(1 for p in observed if (f'{int(p[:4])+1}-01' if p.endswith('-12') else p[:5]+f'{int(p[5:])+1:02}') in observed)
    assert len([x for x in monthly if x.attrib.get('class')=='bus-line'])==adjacent, 'Never bridge missing months'
    assert len([x for x in monthly if x.attrib.get('class')=='bus-point'])==len(rs)
    assert len([x for x in annual if x.attrib.get('class')=='bus-column'])==sum(r['metric']==metric and r['period_type']=='year' for r in data['records'])
assert max(r['period'] for r in data['records'] if r['period_type']=='month')=='2026-04'
print(f'PASS: {len(data["records"])} official observations, three latest-edition targets, six charts, source hash, spreadsheet links and no bridged monthly gaps.')

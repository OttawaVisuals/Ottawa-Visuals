"""Check source precision, planning/actual separation, exports and static chart."""
import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'data/building-upgrades.json').read_text(encoding='utf-8'))
assert d['promise']['additional'] is True and d['promise']['years']==4
assert d['promise']['amount_cad']==100000000
assert d['promise']['comparable_actual_cad'] is None and d['promise']['baseline_cad'] is None
assert (d['reported_annual']['minimum_cad'],d['reported_annual']['maximum_cad'])==(3500000,4000000)
assert [r['amount_cad'] for r in d['plan_2024']]==[978000,834000,525000,500000,300000,250000]
assert [r['type'] for r in d['plan_2024']][-2:]==['Approved allocation']*2
assert len(d['projects'])==13
assert len({(r['site'],r['work']) for r in d['projects']})==13
assert sum(r['status'].startswith('Completed') for r in d['projects'])==6
for r in d['projects']:
    assert r['source'] in d['sources'] and r['as_of']<=d['reviewed']
    assert r['as_of']==('2025-04-22' if r['source']=='completed' else '2026-06-19')
with (ROOT/'data/building-upgrades-projects.csv').open(encoding='utf-8',newline='') as f:
    assert list(csv.DictReader(f))==[{**{k:r[k] for k in ['site','work','status','as_of']},'source_url':d['sources'][r['source']]['url']} for r in d['projects']]
with (ROOT/'data/building-upgrades-plan-2024.csv').open(encoding='utf-8',newline='') as f:
    assert list(csv.DictReader(f))==[{**{k:str(v) for k,v in r.items()},'source_url':d['sources']['plan']['url']} for r in d['plan_2024']]
html=(ROOT/'promises.html').read_text(encoding='utf-8')
section=html.split('<section id="building-upgrades"',1)[1].split('</section>',1)[0]
svg=ET.fromstring(re.search(r'<svg class="building-svg".*?</svg>',section,re.S)[0])
bars=list(svg.iter('rect'))
assert len(bars)==6
for bar,r in zip(bars,d['plan_2024']):
    assert float(bar.attrib['x'])==220
    assert abs(float(bar.attrib['width'])-r['amount_cad']/1000000*450)<.006
assert section.count('class="building-lane"')==2
assert 'not actual expenditures' in section and 'Term total unavailable' in section
assert 'four-year total or used to calculate pledge completion' in section
assert 'id="savings"' not in html and 'id="ev-charging"' not in html
print('PASS: original additional pledge; six plan figures, 13 site/work records, CSV parity, bar scale and explicit actual-spending gaps.')

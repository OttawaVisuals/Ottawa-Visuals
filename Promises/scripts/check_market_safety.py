"""Check OPS count reconciliation, coverage, privacy, chart scale and scope labels."""
import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'data/market-safety.json').read_text(encoding='utf-8'))
sources=json.loads((ROOT/'data/market-safety-sources.json').read_text(encoding='utf-8'))
assert d['year_field']=='Reported_Year'
assert d['neighbourhood_filter']=="Neighbourhood = 'Byward Market'"
assert sources['promise']['numeric_crime_target'] is None
expected={'Assaults':[300,318,301,276,304,303,281,303],'Robbery':[61,59,47,53,51,56,34,42],'Break and Enter':[47,105,118,110,110,128,107,66],'Theft $5000 and Under':[841,822,426,330,450,492,530,422]}
assert len(d['observations'])==32
for category,values in expected.items():
    rows=sorted((r for r in d['observations'] if r['category']==category),key=lambda r:r['year'])
    assert [r['year'] for r in rows]==list(range(2018,2026))
    assert [r['count'] for r in rows]==values
assert sum(r['count'] for r in d['observations'])==d['verification']['independent_record_rows']==7893
assert d['verification']['all_32_aggregates_match'] and d['verification']['duplicate_year_category_go']==0
assert d['boundary']['attributes']['namese2016'].lower()=='byward market'
assert d['boundary']['geometry']['rings']
assert len(d['provenance'])==2 and all(len(p['sha256'])==64 for p in d['provenance'])
assert 'GO_Number' not in json.dumps(d), 'Individual identifiers must not be retained'
with (ROOT/'data/market-safety.csv').open(encoding='utf-8',newline='') as f:
    rows=list(csv.DictReader(f))
assert len(rows)==32
for row,r in zip(rows,d['observations']):
    assert int(row['count'])==r['count'] and int(row['reported_year'])==r['year']
    assert row['category']==r['category'] and row['neighbourhood']=='Byward Market'
    assert row['source_url']==sources['sources']['api']['url']
html=(ROOT/'promises.html').read_text(encoding='utf-8')
section=html.split('<section id="market-safety"',1)[1].split('</section>',1)[0]
svgs=[ET.fromstring(x) for x in re.findall(r'<svg class="market-svg".*?</svg>',section,re.S)]
assert len(svgs)==4
for svg,category in zip(svgs,d['categories']):
    bars=[x for x in svg.iter('rect') if 'market-bar' in x.attrib.get('class','')]
    assert len(bars)==8
    for bar,value in zip(bars,expected[category]):
        assert abs(float(bar.attrib['y'])+float(bar.attrib['height'])-320)<.011
        assert f': {value:,} ' in ''.join(bar.itertext())
assert section.count('class="market-bar baseline"')==4
assert 'OPS cautions against relying on these figures for comparisons over time' in section
assert 'No 2026 annual result' in section and 'No whole-promise score' in section
for hidden in ['dog-parks','building-upgrades','ev-charging','savings']:
    assert f'id="{hidden}"' not in html and f'href="#{hidden}"' not in html
print('PASS: 32 OPS counts, 7,893-row verification, no individual identifiers, one neighbourhood, four zero-based charts, CSV and four hidden topics.')

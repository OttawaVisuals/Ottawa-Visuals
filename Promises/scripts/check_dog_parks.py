"""Check evidence categories, date precision, aliases, map provenance and exports."""
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'data/dog-parks.json').read_text(encoding='utf-8'))
m=json.loads((ROOT/'data/dog-parks-map.json').read_text(encoding='utf-8'))
assert d['promise']['minimum_parks']==3 and d['promise']['deadline'] is None
parks=d['parks'];assert len(parks)==5 and len({p['id'] for p in parks})==5
assert all(p['opening_date'] is None for p in parks), 'No exact first-public-use dates verified'
assert [(p['id'],p['ceremony_date']) for p in parks if p['ceremony_date']]==[('morgan','2026-08-09')]
assert [(p['id'],p['kind']) for p in parks if p['geography']=='suburban']==[('morgan','open'),('casey','reported'),('shea','context')]
assert all(p['kind']=='context' for p in parks if p['geography']=='rural village')
assert len({l['id'] for l in m['locations']})==5
assert hashlib.sha256((ROOT.parent/m['ward_source_path']).read_bytes()).hexdigest()==m['ward_source_sha256']
for l in m['locations']:
    assert -76.03<l['longitude']<-75.45 and 45.13<l['latitude']<45.40
    assert l['source_url'].startswith('https:') and l['method']
for p in parks:
    assert p['source'] in d['sources'] and p['evidence_as_of']<=d['reviewed']
    assert all(h['source'] in d['sources'] for h in p['history'])
with (ROOT/'data/dog-parks.csv').open(encoding='utf-8',newline='') as f:
    rows=list(csv.DictReader(f))
assert len(rows)==5
for row,p in zip(rows,parks):
    for key in row:
        assert row[key]==(d['sources'][p['source']]['url'] if key=='source_url' else str(p[key]) if p[key] is not None else '')
with (ROOT/'data/dog-parks-milestones.csv').open(encoding='utf-8',newline='') as f:
    assert list(csv.DictReader(f))==[{'park_id':p['id'],'date':h['date'] or '', 'text':h['text'],'source_url':d['sources'][h['source']]['url']} for p in parks for h in p['history']]
html=(ROOT/'promises.html').read_text(encoding='utf-8')
section=html.split('<section id="dog-parks"',1)[1].split('</section>',1)[0]
svg=ET.fromstring(re.search(r'<svg class="dog-map".*?</svg>',section,re.S)[0])
links=list(svg.iter('a'));assert len(links)==5
for link,p in zip(links,parks):assert link.attrib['href']=='#dog-'+p['id']
assert section.count('class="dog-project"')==5
assert 'Gregory Casey and McKenna Casey are one project' in section
for hidden in ['savings','ev-charging','building-upgrades']:assert f'id="{hidden}"' not in html
print('PASS: 5 distinct sites, 3 evidence categories, date precision, suburban/village separation, 5 linked map markers, boundary hash and CSV parity.')

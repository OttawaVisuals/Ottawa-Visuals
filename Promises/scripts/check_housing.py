"""Check housing period arithmetic, subsets, partial years and chart scopes."""
import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

root=Path(__file__).resolve().parents[1]
d=json.loads((root/'data/housing.json').read_text(encoding='utf-8'))
p=json.loads((root/'data/housing-progress.json').read_text(encoding='utf-8'))
annual=d['annual_completions'];monthly=d['monthly_completions']
assert [r['year'] for r in annual]==list(range(2006,2027))
assert len(monthly)==80 and len({r['period'] for r in monthly})==80
assert max(r['period'] for r in monthly)=='2026-08'
assert not any(r['period']>'2026-08' for r in monthly), 'Future formula zeros must not become observations'
for r in annual:
    if r['year']>=2020:
        ms=[m for m in monthly if m['period'].startswith(str(r['year']))]
        assert sum(m['completions'] for m in ms)==r['completions']
        assert len(ms)==r['months']
    assert r['months']==(8 if r['year']==2026 else 12)
for r in d['pipeline']:
    a=next(a for a in annual if a['year']==r['year'])
    assert r['completions']==a['completions'] and r['months']==a['months']
assert next(r['completions'] for r in annual if r['year']==2023)==7890, 'Use HNA table, not typo in prose'
assert [r['completions'] for r in annual[-4:]]==[7890,8794,7797,5559]
running=0
for r in p['cumulative_completions']:
    a=next(a for a in annual if a['year']==r['year'])
    running+=a['completions'];assert running==r['completions']
    assert abs(r['illustrative_pace']-100000/10*((r['year']-2023)+r['months']/12))<.000001
assert running==30040 and p['analysis_start']=='2023-01-01'
for r in d['affordable_supportive']:
    assert r['affordable']+r['supportive']==r['completed']
assert sum(r['completed'] for r in d['affordable_supportive'])==578==p['affordable_supportive_2023_2025']
assert sum(m['completions'] for m in monthly if '2025-01'<=m['period']<='2025-08')==4514
assert d['context'][1]['year_end_waitlist']==14721 and d['context'][1]['placements']==1077
with (root/'data/housing.csv').open(encoding='utf-8',newline='') as f:
    rows=list(csv.DictReader(f))
assert len(rows)==121
for r in rows:
    assert float(r['value'])>=0 and float(r['value']).is_integer()
    assert r['source_url'] in [s['url'] for s in d['sources'].values()]
html=(root/'promises.html').read_text(encoding='utf-8')
svgs=[ET.fromstring(s) for s in re.findall(r'<svg class="housing-svg".*?</svg>',html,re.S)]
assert len(svgs)==4
def chart(name):return next(s for s in svgs if s.find('title').attrib['id']==name+'-title')
assert len([x for x in chart('housing-history-chart') if x.attrib.get('class','').startswith('housing-column')])==21
assert len([x for x in chart('housing-cumulative') if x.attrib.get('class','').startswith('housing-column')])==4
assert len([x for x in chart('housing-community') if x.attrib.get('class','').startswith('housing-column')])==6
assert len([x for x in chart('housing-recent') if 'partial' in x.attrib.get('class','')])==1
print('PASS: 21 annual/YTD values, 80 months, 2026 cutoff, 30,040 cumulative, 578 program completions, illustrative pace, CSV and four charts.')

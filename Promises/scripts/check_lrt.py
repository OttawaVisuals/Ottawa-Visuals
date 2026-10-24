"""Validate chronology, forecast/actual separation and published evidence links."""
import csv
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / 'data/lrt-stage2.json').read_text(encoding='utf-8'))
assert d['promise']['deadline'] is None
assert [x['id'] for x in d['extensions']] == ['south', 'east', 'west']
expected = []
for ext in d['extensions']:
    assert ext['status_source'] in d['sources']
    assert ext['status_as_of'] <= d['reviewed']
    updates = [x['update_date'] for x in ext['events']]
    assert updates == sorted(updates)
    for r in ext['events']:
        assert r['source'] in d['sources']
        if r['kind'] == 'actual':
            assert date.fromisoformat(r['actual_date']) <= date.fromisoformat(d['reviewed'])
            assert r['target'] is None
        else:
            assert r['actual_date'] is None, 'Forecasts must not become actual events'
        expected.append({'extension': ext['name'], **{k: r[k] or '' for k in ['update_date', 'date_label', 'kind', 'stage', 'target', 'actual_date', 'text']}, 'source_url': d['sources'][r['source']]['url'], 'source_locator': d['sources'][r['source']]['locator']})
with (ROOT / 'data/lrt-stage2.csv').open(encoding='utf-8', newline='') as f:
    assert list(csv.DictReader(f)) == expected
south,east,west = d['extensions']
assert [r['actual_date'] for r in south['events'] if r['stage']=='passenger_service'] == ['2025-01-06', '2025-01-25', '2025-03-16']
assert all(r['actual_date'] is None for ext in [east,west] for r in ext['events'] if r['stage']=='passenger_service')
assert east['events'][-1]['stage']=='pre_trial_running' and east['events'][-1]['target']=='November 2026'
assert west['events'][-1]['target'] is None
html = (ROOT / 'promises.html').read_text(encoding='utf-8')
section = html.split('<section id="lrt-stage2"',1)[1].split('</section>',1)[0]
assert section.count('class="lrt-extension"') == 3
assert section.count('class="lrt-event ') == len(expected) == 11
assert section.count('<tr>') == 12
assert 'November 2026 is an east testing forecast' in section
assert 'Spacing is not elapsed time' in section
assert 'id="ev-charging"' not in html and 'id="savings"' not in html
ids = re.findall(r'\bid="([^"]+)"', html)
assert len(ids) == len(set(ids)), 'Duplicate document IDs'

class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        if tag!='a':return
        href = dict(attrs).get('href','')
        if href.startswith('#'):
            assert href[1:] in ids, href
        elif not href.startswith(('https:', 'http:', 'mailto:')):
            assert (ROOT / href.split('#')[0].split('?')[0]).exists(), href
Links().feed(html)
print('PASS: 3 timelines / 11 evidence records; date precision, forecast/actual separation, CSV parity, hidden sections, IDs and local links.')

"""Check snapshot scopes, locator chronology, exports and no invented pledge score."""
import csv
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / 'data/ev-charging.json').read_text(encoding='utf-8'))
evidence = json.loads((ROOT / 'data/ev-charging-sources.json').read_text(encoding='utf-8'))
records = d['stations']
assert len(records) == 347 and len({s['id'] for s in records}) == 347
assert d['in_boundary_records'] == len(records) + sum(d['excluded_sequentially'].values()) == 364
assert len(d['wards']) == 24 and len({w['ward'] for w in d['wards']}) == 24
assert hashlib.sha256((ROOT.parent / d['boundary_path']).read_bytes()).hexdigest() == d['boundary_sha256']
hydro = [s for s in records if s['hydro_named']]
assert len(hydro) == 19 and sum(s['ports'] for s in hydro) == 86
assert sum(s['ports'] for s in records) == 1158
for s in records:
    assert s['status_code'] == 'E' and s['access_code'] == 'public'
    assert s['open_date'] <= d['reviewed']
    assert 44.9 < s['latitude'] < 45.7 and -76.5 < s['longitude'] < -75.1
    assert s['ports'] == sum(s[k] or 0 for k in ['ev_level1_evse_num', 'ev_level2_evse_num', 'ev_dc_fast_num'])
    assert s['hydro_named'] == any(n in s['station_name'].lower() for n in ['hydro ottawa', 'envari'])
with (ROOT / 'data/ev-charging.csv').open(encoding='utf-8', newline='') as f:
    csv_rows = list(csv.DictReader(f))
assert len(csv_rows) == 347 and sum(int(r['ports']) for r in csv_rows) == 1158
with (ROOT / 'data/ev-charging-timeline.csv').open(encoding='utf-8', newline='') as f:
    timeline = list(csv.DictReader(f))
assert len(timeline) == 10
for scope, expected in [('hydro', [1, 13, 18, 19, 19]), ('all', [100, 176, 243, 305, 347])]:
    assert [int(r['cumulative_current_records_with_listed_date']) for r in timeline if r['scope'] == scope] == expected
assert evidence['promise']['stations'] == 200 and evidence['promise']['comparable_delivered_count'] is None
assert evidence['promise']['station_port_definition_verified'] is False
assert evidence['hydro_program']['ports'] == 1047 and not evidence['hydro_program']['additive_to_locator']
examples = evidence['verified_examples']
assert sum(r['level2'] + r['dc_fast'] for r in examples) == 7
riverain = next(s for s in records if s['id'] == 470392)
assert riverain['open_date'] == '2026-09-23' > examples[0]['operational_by'], 'Keep the documented listing/operational discrepancy'
html = (ROOT / 'promises.html').read_text(encoding='utf-8')
svgs = [ET.fromstring(s) for s in re.findall(r'<svg class="ev-(?:map|chart)".*?</svg>', html, re.S)]
assert len(svgs) == 4
assert [len(list(s.iter('circle'))) for s in svgs] == [19, 5, 347, 5]
assert 'id="savings"' not in html
assert 'This is not a verified annual installation series' in html
assert 'station-versus-port counting rule' in html
print('PASS: 347 records / 1,158 ports; 19 Hydro-named / 86 ports; 10 cohort totals, spatial provenance, CSV, four SVGs and source-scope limits.')

"""Independently reconcile every exported aggregate against workbook XML."""
from pathlib import Path
from collections import defaultdict
from zipfile import ZipFile
import csv, hashlib, json
import xml.etree.ElementTree as E

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/alberta.json').read_text(encoding='utf-8'))
path=ROOT/'data/raw/alberta/ecc-alberta-class-size-2025-2026.xlsx'
assert hashlib.sha256(path.read_bytes()).hexdigest()==data['sha256']
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
agg=defaultdict(lambda:[0,0,0,0])
with ZipFile(path) as z:
    strings=[''.join(e.itertext()) for e in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
    root=E.fromstring(z.read('xl/worksheets/sheet2.xml'))
    for row in root.findall('s:sheetData/s:row',ns)[1:]:
        cells={}
        for c in row.findall('s:c',ns):
            v=c.find('s:v',ns)
            if v is not None:cells[''.join(x for x in c.attrib['r'] if x.isalpha())]=strings[int(v.text)] if c.get('t')=='s' else v.text
        geo='ab-'+cells['C'];band=cells['F'];value=cells['G'];suppressed=value=='*';size=0 if suppressed else int(value)
        for area in ['alberta',geo]:
            for group in ['all',band]:
                a=agg[area,group];a[0]+=1;a[1]+=suppressed;a[2]+=size>21;a[3]+=size>23
for r in data['counts']:
    assert [r[k] for k in ['classes','suppressed','above21','above23']]==agg[r['geo'],r['group']],r
js=(ROOT/'data/alberta-data.js').read_text(encoding='utf-8')
assert json.loads(js.split('=',1)[1].rstrip(';\n'))==data
with (ROOT/'data/alberta-class-thresholds.csv').open(encoding='utf-8-sig',newline='') as f:
    rows=list(csv.DictReader(f))
    assert len(rows)==len(data['counts'])
    for r,expected in zip(rows,data['counts']):
        for field in ['classes','suppressed','above21','above23']:assert int(r[field])==expected[field]
print(f"PASS: {len(data['counts'])} aggregates independently match original XML; CSV/JSON/JS and source hash agree.")

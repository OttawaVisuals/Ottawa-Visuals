"""Independently reconcile latest threshold counts using original worksheet XML."""
from pathlib import Path
from collections import defaultdict
import hashlib, json, math, zipfile, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
T=json.loads((ROOT/'data/thresholds.json').read_text(encoding='utf-8'))
B=json.loads((ROOT/'data/education.json').read_text(encoding='utf-8'))
checks=0
def check(ok,message):
    global checks
    assert ok,message
    checks+=1

check(len(T['counts'])==455 and len(T['averages'])==70,'Complete seven-year/five-area/reference/scope coverage')
for r in T['counts']:
    check(0<=r['above_low']<=r['above_high']<=r['classes'],'Count bounds')
    check(0<=r['suppressed_classes']<=r['classes'],'Suppressed rows')
    check(r['above_high']-r['above_low']<=r['suppressed_classes'],'Only suppressed rows can be uncertain')
for year in T['years']:
    for geo in ['ontario',*B['boards']]:
        rows={r['rule']:r for r in T['counts'] if r['year']==year and r['geo']==geo}
        base={r['group']:r for r in B['classes'] if r['year']==year and r['geo']==geo}
        for rid,band in [('k29','kindergarten'),('etfo24','upper')]:
            check(rows[rid]['classes']==base[band]['classes'],'Same source population')
        check(sum(rows[r]['classes'] for r in ['k29','primary23','mixed23','etfo24'])==base['all']['classes'],'Disjoint population identity')
        for field in ['above_low','above_high']:
            check(rows['k32'][field]<=rows['k29'][field]<=rows['etfo26'][field],'Nested kindergarten thresholds')
            check(rows['primary23'][field]<=rows['primary20'][field],'Nested primary thresholds')
        scoped={(r['rule'],r['scope']):r for r in T['counts'] if r['year']==year and r['geo']==geo}
        for scope in T['scopes']:
            a,b=scoped[('oecd21',scope)],scoped[('oecd23',scope)]
            check(a['classes']==b['classes'] and b['above_low']<=a['above_low'] and b['above_high']<=a['above_high'],'OECD same-scope denominator and nested comparisons')
        check(scoped[('oecd21','grades1to3')]['classes']==base['primary']['classes'],'OECD grades 1-3 excludes kindergarten mixtures')
        check(scoped[('oecd21','grades4to8')]['classes']==base['upper']['classes'],'OECD grades 4-8 population')
        check(scoped[('oecd21','grades1to8')]['classes']>=scoped[('oecd21','grades1to3')]['classes']+scoped[('oecd21','grades4to8')]['classes'],'OECD combined scope also includes cross-band classes without kindergarten')
for r in T['averages']:
    check(0<r['class_equivalents_low']<=r['class_equivalents_high']<=r['classes']+1e-8,'Fractional denominator bounds')
    check(math.isclose(r['average_low'],r['students_low']/r['class_equivalents_high']) and math.isclose(r['average_high'],r['students_high']/r['class_equivalents_low']),'Conservative average bounds')
    if r['group']=='upper':check(r['class_equivalents_low']==r['classes'],'Upper-grade denominator counts full mixed classes')

# Independent parser and explicit cell-position membership tests, rather than importing the builder.
N='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
source=next(c for c in T['coverage'] if c['year']==2025)
path=ROOT/'data/raw'/source['file']
check(hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256'],'Latest source hash')
aliases={name:geo for geo,names in B['source_board_names'].items() for name in names}
expected=defaultdict(lambda:[0,0,0,0])
with zipfile.ZipFile(path) as z:
    strings=[''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    for _,row in ET.iterparse(z.open('xl/worksheets/sheet1.xml'),events=('end',)):
        if row.tag!=N+'row':continue
        cells={}
        for cell in row:
            value=cell.find(N+'v')
            if value is None:continue
            raw=strings[int(value.text)] if cell.attrib.get('t')=='s' else value.text
            col=''.join(c for c in cell.attrib['r'] if c.isalpha())
            cells[col]=raw
        if cells.get('B') and cells.get('A')=='2025-2026':
            low=[1 if cells[c]=='<5' else int(float(cells[c])) for c in ['E','F','G','H','I','J']]
            high=[4 if cells[c]=='<5' else int(float(cells[c])) for c in ['E','F','G','H','I','J']]
            if sum(high)>0:
                k=sum(high[:2])>0;p=sum(high[2:5])>0;u=high[5]>0
                applicable=[]
                if p and not u:applicable+=[('primary23',23,'rule'),('primary20',20,'rule')]
                if u and (k or p):applicable+=[('mixed23',23,'rule')]
                if k and not p and not u:applicable+=[('k29',29,'rule'),('k32',32,'rule'),('etfo26',26,'rule')]
                if u and not k and not p:applicable+=[('etfo24',24,'rule')]
                if not k:
                    scopes=['grades1to8']+(['grades1to3'] if p and not u else [])+(['grades4to8'] if u and not p else [])
                    for scope in scopes:applicable+=[('oecd21',21,scope),('oecd23',23,scope)]
                geo=aliases.get(cells['B'])
                for area in ['ontario']+([geo] if geo else []):
                    for rid,cap,scope in applicable:
                        a=expected[(area,rid,scope)];a[0]+=1;a[1]+=sum(low)>cap;a[2]+=sum(high)>cap;a[3]+=low!=high
        row.clear()
for r in T['counts']:
    if r['year']==2025:
        check([r[k] for k in ['classes','above_low','above_high','suppressed_classes']]==expected[(r['geo'],r['rule'],r['scope'])],'Independent full latest worksheet threshold counts')
print(f'PASS: {checks} threshold coverage, source, population, suppression and average checks; latest counts independently reconciled from XML.')

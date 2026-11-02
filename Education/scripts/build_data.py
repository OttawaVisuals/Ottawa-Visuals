"""Build source-linked finances and class-count aggregates. Never impute suppressed cells."""
from pathlib import Path
from collections import defaultdict, Counter
import csv, json, re, zipfile, unicodedata, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
BOARDS = {
    'ocdsb': 'Ottawa-Carleton District School Board',
    'ocsb': 'Ottawa Catholic District School Board',
    'cepeo': "Conseil des écoles publiques de l’Est de l’Ontario",
    'cecce': "Conseil des écoles catholiques du Centre-Est",
}

def board_id(name):
    n = ''.join(c for c in unicodedata.normalize('NFKD', name.casefold()) if not unicodedata.combining(c)).replace('’', "'")
    if 'ottawa-carleton' in n: return 'ocdsb'
    if 'ottawa catholic' in n or n=='ottawa csb': return 'ocsb'
    if ('publique' in n or n.startswith('cep ')) and ('est' in n or 'ontario' in n): return 'cepeo'
    if ('catholique' in n or n.startswith('csdc ')) and ('centre-est' in n or 'centre est' in n): return 'cecce'
    return None

def read_table(table):
    with (RAW / f'{table}.csv').open(encoding='utf-8-sig', newline='') as f:
        return [r for r in csv.DictReader(f) if r['GEO'] == 'Ontario']

cpi_rows = [r for r in read_table('18100005') if r['Products and product groups'] == 'All-items']
cpi = {int(r['REF_DATE']): float(r['VALUE']) for r in cpi_rows if r['VALUE']}
finance = []
for table in ('37100066', '37100067'):
    for r in read_table(table):
        y = int(r['REF_DATE'][:4])
        # All available history is retained. UI defaults to the comparable post-2012 methodology.
        category = r['Type of expenditures'] if table == '37100066' else list(r.values())[3].split(', ')[-1]
        nominal = float(r['VALUE']) * 1000 if r['VALUE'] else None
        factor = (cpi[2023] + cpi[2024]) / (cpi[y] + cpi[y+1]) if y in cpi and y+1 in cpi else None
        finance.append(dict(table=table, year=y, period=r['REF_DATE'], category=category, cad=nominal,
                            real_cad=nominal*factor if nominal is not None and factor else None,
                            status=r['STATUS'], vector=r['VECTOR'], coordinate=r['COORDINATE'],
                            private_estimate=table=='37100066' and category=='Private elementary and secondary school expenditures' and y>=2006))

def xlsx_sheets(path):
    """Read original cell values directly; avoid formatting-only rows and bilingual duplicate sheets."""
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            strings = [''.join(node.itertext()) for node in root]
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets = {r.attrib['Id']: r.attrib['Target'] for r in rels}
        sheets = list(wb.find(NS+'sheets'))
        if not path.name.startswith('2007-08'): sheets = sheets[:1]
        for sheet in sheets:
            sid = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target = targets[sid].lstrip('/')
            if not target.startswith('xl/'): target = 'xl/' + target
            with z.open(target) as stream:
                for _, row in ET.iterparse(stream, events=('end',)):
                    if row.tag != NS+'row': continue
                    values = [None]*10
                    for c in row:
                        address=c.attrib.get('r', '')
                        col=re.match('[A-Z]+', address)
                        if not col: continue
                        index=0
                        for char in col[0]: index=index*26+ord(char)-64
                        if index>10: continue
                        val=c.find(NS+'v'); typ=c.attrib.get('t')
                        if typ=='s': value=strings[int(val.text)] if val is not None else None
                        elif typ=='inlineStr': value=''.join(c.find(NS+'is').itertext())
                        else: value=float(val.text) if val is not None and val.text else None
                        values[index-1]=value
                    yield sheet.attrib['name'], int(row.attrib['r']), values
                    row.clear()

def bounds(v):
    if isinstance(v, (float, int)):
        assert v>=0 and int(v)==v, v
        return int(v), int(v)
    # A positive count below five; don't infer an exact cell value.
    if str(v).strip()=='<5': return 1,4
    raise ValueError(f'Unrecognised class cell: {v!r}')

def empty(): return dict(classes=0,students_low=0,students_high=0,suppressed_classes=0,over25_low=0,over25_high=0)

summary=defaultdict(empty); schools=defaultdict(empty); coverage=[]; source_boards=defaultdict(set); ambiguous=set()
resources=json.loads((RAW/'class-catalogue.json').read_text(encoding='utf-8'))['result']['resources']
for resource in resources:
    file=RAW/resource['url'].rsplit('/',1)[-1]
    seen=set(); counts=defaultdict(Counter)
    for sheet,rownum,row in xlsx_sheets(file):
        if rownum==1 or not row[1]: continue
        rawyear,board,school,number,*cells=row
        if not re.match(r'^20\d\d-',str(rawyear)): continue
        year=int(str(rawyear)[:4]); key=(year,board,school,str(number))
        if key in seen:
            counts[year]['repeated_name_class_keys']+=1
            bid=board_id(board)
            if bid: ambiguous.add((year,bid,school))
        seen.add(key)
        b=[bounds(v) for v in cells]; low=sum(x[0] for x in b); high=sum(x[1] for x in b)
        counts[year]['source_rows']+=1
        if high==0:
            counts[year]['zero_rows']+=1; continue
        present=[any(x[1]>0 for x in b[:2]),any(x[1]>0 for x in b[2:5]),b[5][1]>0]
        band=('kindergarten','primary','upper')[present.index(True)] if sum(present)==1 else 'mixed'
        counts[year][band]+=1
        bid=board_id(board)
        if bid: source_boards[bid].add(board)
        # Before 2014 the source has no upper-only classes. Preserve early rows but never imply full coverage.
        groups=[band]+(['all'] if year>=2014 else [])
        for group in groups:
            for geo in ['ontario']+([bid] if bid else []):
                ag=summary[(year,geo,group)]
                ag['classes']+=1;ag['students_low']+=low;ag['students_high']+=high
                ag['suppressed_classes']+=low!=high;ag['over25_low']+=low>25;ag['over25_high']+=high>25
            if bid:
                ag=schools[(year,bid,school,group)]
                ag['classes']+=1;ag['students_low']+=low;ag['students_high']+=high
                ag['suppressed_classes']+=low!=high;ag['over25_low']+=low>25;ag['over25_high']+=high>25
    for year,count in sorted(counts.items()):
        coverage.append(dict(year=year,file=file.name,url=resource['url'],**count))
        print(year,dict(count),flush=True)

def records(mapping,is_school=False):
    result=[]
    for key,values in sorted(mapping.items()):
        year,geo,*rest=key
        r=dict(year=year,geo=geo,group=rest[-1],**values)
        if is_school:
            r['school']=rest[0]
            r['ambiguous_name']=(year,geo,rest[0]) in ambiguous
        result.append(r)
    return result

data=dict(reviewed='2026-11-02',boards=BOARDS,source_board_names={k:sorted(v) for k,v in source_boards.items()},
          finance=finance,cpi=[dict(year=y,value=v) for y,v in sorted(cpi.items())],classes=records(summary),schools=records(schools,True),coverage=coverage)
out=ROOT/'data';out.mkdir(exist_ok=True)
(out/'education.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
(out/'page-data.js').write_text('window.EDUCATION_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
for name,rows in [('spending',finance),('class-sizes',data['classes']),('school-class-sizes',data['schools']),('class-coverage',coverage)]:
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (out/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print('Built',len(finance),'financial records,',len(summary),'board/province and',len(schools),'school aggregates.',flush=True)

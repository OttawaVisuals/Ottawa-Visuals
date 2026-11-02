"""Count class rows above reference thresholds; never certify regulatory compliance."""
from pathlib import Path
from collections import defaultdict
from openpyxl import load_workbook
import csv, hashlib, json

ROOT=Path(__file__).resolve().parents[1]
BASE=json.loads((ROOT/'data/education.json').read_text(encoding='utf-8'))
ALIASES={name:geo for geo,names in BASE['source_board_names'].items() for name in names}
RULES=[
 dict(id='primary23',group='primary',limit=23,label='Primary classes above 23',kind='Provincial hard-cap reference',note='Classes with grades 1–3, possibly with JK/K, and no grades 4–8. The individual-class cap is 23.'),
 dict(id='primary20',group='primary',limit=20,label='Primary classes above 20',kind='Provincial board-share reference',share_limit=10,note='At least 90% of eligible primary classes must have 20 or fewer students. A class of 21–23 is not automatically a breach.'),
 dict(id='mixed23',group='mixed',limit=23,label='Primary/upper mixed classes above 23',kind='Provincial hard-cap reference',note='Classes combining JK/K or grades 1–3 with grades 4–8. These classes also enter the upper-grade board-average calculation.'),
 dict(id='k29',group='kindergarten',limit=29,label='Kindergarten classes above 29',kind='Provincial cap with exceptions',share_limit=10,note='JK/K-only classes. Up to 10% may have 30–32 students under specified conditions. The public workbook omits those exception fields.'),
 dict(id='k32',group='kindergarten',limit=32,label='Kindergarten classes above 32',kind='Provincial absolute-cap reference',note='JK/K-only classes above the 32-student exception ceiling. These are source-row flags, not verified violations.'),
 dict(id='etfo24',group='upper',limit=24,label='Grades 4–8-only classes above 24',kind='ETFO proposed cap · 2025–26 submission',note='Union recommendation, not an individual-class legal maximum. Mixed primary/upper classes are tracked separately against 23.'),
 dict(id='etfo26',group='kindergarten',limit=26,label='Kindergarten classes above 26',kind='ETFO proposed cap · 2025–26 submission',note='Union recommendation for individual JK/K-only classes. The provincial 26-student requirement is a board average, not this individual cap.'),
 dict(id='oecd21',group='oecd',family='oecd',limit=21,label='Classes above OECD primary average (21)',kind='OECD observed average · 2024',note='Published rounded average: 21 students per primary class, corresponding to grades 1–6 in the Canadian mapping. The selected Ontario class scope is a descriptive comparison, not a matched OECD-level estimate or recommended maximum.'),
 dict(id='oecd23',group='oecd',family='oecd',limit=23,label='Classes above OECD lower-secondary average (23)',kind='OECD observed average · 2024',note='Published rounded average: 23 students per lower-secondary class, corresponding to grades 7–9 in the Canadian mapping. The selected Ontario class scope is a descriptive comparison, not a matched OECD-level estimate or recommended maximum.'),
]
SCOPES={'grades1to8':'Grades 1–8 · excludes all JK/K classes','grades1to3':'Grades 1–3 only','grades4to8':'Grades 4–8 only'}

def bounds(value):
    if value=='<5':return 1,4
    assert isinstance(value,(int,float)) and value>=0 and int(value)==value,repr(value)
    return int(value),int(value)

def empty():return dict(classes=0,above_low=0,above_high=0,suppressed_classes=0)
counts=defaultdict(empty)
averages=defaultdict(lambda:dict(classes=0,students_low=0,students_high=0,class_equivalents_low=0.,class_equivalents_high=0.))
by_file=defaultdict(list)
coverage=[]
for source in BASE['coverage']:
    if 2019<=source['year']<=2025:by_file[source['file']].append(source)
manifest=json.loads((ROOT/'data/source-manifest.json').read_text())
for filename,sources in by_file.items():
    path=ROOT/'data/raw'/filename
    expected=next(m['sha256'] for m in manifest if Path(m['file']).name==filename)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,'Source changed; rebuild the base data first'
    w=load_workbook(path,read_only=True,data_only=True)
    for source in sources:
        year=source['year'];sheet=w[f'{year}-{str(year+1)[-2:]}'] if filename.startswith('2007-08') else w.worksheets[0]
        nonempty=0
        for row in sheet.iter_rows(min_row=2,max_col=10,values_only=True):
            if not row[1]:continue
            assert int(str(row[0])[:4])==year
            cells=[bounds(v) for v in row[4:10]]
            low=sum(v[0] for v in cells);high=sum(v[1] for v in cells)
            if high==0:continue
            nonempty+=1
            kl=sum(v[0] for v in cells[:2]);kh=sum(v[1] for v in cells[:2])
            primary=any(v[1]>0 for v in cells[2:5]);upper=cells[5][1]>0;kind=kh>0
            group='mixed' if upper and (primary or kind) else 'upper' if upper else 'primary' if primary else 'kindergarten'
            geo=ALIASES.get(row[1]);geos=['ontario']+([geo] if geo else [])
            for area in geos:
                for rule in RULES:
                    scopes=[]
                    if rule.get('family')=='oecd' and not kind:
                        scopes=['grades1to8']+(['grades1to3'] if primary and not upper else [])+(['grades4to8'] if upper and not primary else [])
                    elif rule['group']==group:scopes=['rule']
                    for scope in scopes:
                        a=counts[(year,area,rule['id'],scope)]
                        a['classes']+=1;a['above_low']+=low>rule['limit'];a['above_high']+=high>rule['limit'];a['suppressed_classes']+=low!=high
                if upper:
                    a=averages[(year,area,'upper')];a['classes']+=1
                    a['students_low']+=low;a['students_high']+=high
                    a['class_equivalents_low']+=1;a['class_equivalents_high']+=1
                if kind:
                    a=averages[(year,area,'kindergarten')];a['classes']+=1
                    a['students_low']+=kl;a['students_high']+=kh
                    # For a mixed K/other class, the legal denominator counts the fraction of K pupils.
                    # Conservative bounds retain the correlation uncertainty instead of imputing any cell.
                    other_low=low-kl;other_high=high-kh
                    a['class_equivalents_low']+=kl/(kl+other_high)
                    a['class_equivalents_high']+=kh/(kh+other_low)
        assert nonempty==source['source_rows']-source.get('zero_rows',0)
        coverage.append(dict(year=year,nonempty_classes=nonempty,file=filename,sheet=sheet.title,url=source['url'],sha256=expected))
        print(f'{year}: {nonempty} non-empty source rows',flush=True)
    w.close()
rows=[]
for year in range(2019,2026):
    for geo in ['ontario',*BASE['boards']]:
        for rule in RULES:
            for scope in SCOPES if rule.get('family')=='oecd' else ['rule']:
                rows.append(dict(year=year,geo=geo,rule=rule['id'],scope=scope,**counts[(year,geo,rule['id'],scope)]))
avgs=[]
for (year,geo,group),a in sorted(averages.items()):
    avgs.append(dict(year=year,geo=geo,group=group,reference=26 if group=='kindergarten' else 24.5,
                     average_low=a['students_low']/a['class_equivalents_high'],
                     average_high=a['students_high']/a['class_equivalents_low'],**a))
data=dict(reviewed='2026-11-02',years=list(range(2019,2026)),rules=RULES,scopes=SCOPES,counts=rows,averages=avgs,coverage=coverage,
          oecd=dict(reference_year=2024,publication_year=2026,primary=21,lower_secondary=23,
                    source_url='https://www.oecd.org/en/publications/education-at-a-glance-2026_b4968bbc-en/full-report/how-do-student-teacher-ratios-and-class-sizes-vary-across-education-levels_30c0e06c.html',
                    mapping_url='https://gpseducation.oecd.org/Content/EAGCountryNotes/EAG2023_CN_CAN_pdf.pdf#page=9'),
          reference_basis='Fixed provincial numeric references, dated ETFO proposals and OECD 2024 rounded observed averages, held constant across the displayed history. Not a historical compliance audit or best-practice assessment.')
for filename,prefix,suffix in [('thresholds.json','','\n'),('threshold-data.js','window.EDUCATION_THRESHOLDS=',';\n')]:
    (ROOT/'data'/filename).write_text(prefix+json.dumps(data,ensure_ascii=False,separators=(',',':'))+suffix,encoding='utf-8')
rule_by_id={r['id']:r for r in RULES}
csv_counts=[dict(**r,reference_label=rule_by_id[r['rule']]['label'],reference_type=rule_by_id[r['rule']]['kind'],
                 scope_label=SCOPES.get(r['scope'],'Rule-defined population'),threshold_students=rule_by_id[r['rule']]['limit'],comparison='strictly greater than') for r in rows]
for filename,records in [('class-thresholds.csv',csv_counts),('board-average-references.csv',avgs)]:
    with (ROOT/'data'/filename).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
print(f'Built {len(rows)} threshold counts and {len(avgs)} board/province average comparisons.',flush=True)

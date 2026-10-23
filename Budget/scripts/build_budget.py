"""Download the adopted book, extract identified table rows, reconcile, and build JSON/CSV.
Requires pypdf. PDF cache is outside the repository. No estimates or imputation.
"""
from pathlib import Path
import csv
import hashlib
import io
import json
import re
import tempfile
import urllib.request
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://documents.ottawa.ca/sites/default/files/2026%20Adopted%20Budget%20Book%20English%20Condensed.pdf'
CACHE = Path(tempfile.gettempdir()) / 'ottawa-budget-2026.pdf'
NUMBER = r'\(?-?[\d,]+\)?'

def numbers(text):
    return [int(s.replace(',', '').replace('(', '-').replace(')', '')) for s in re.findall(NUMBER, text)]

def table_row(text, label, count):
    pattern = re.escape(label) + r'\s+' + r'\s+'.join([f'({NUMBER})'] * count)
    found = re.search(pattern, ' '.join(text.split()))
    if not found:
        raise ValueError(f'Cannot locate {label!r}; review the source before updating')
    return numbers(' '.join(found.groups()))

def build():
    if not CACHE.exists():
        request = urllib.request.Request(URL, headers={'User-Agent': 'OttawaVisuals budget research'})
        CACHE.write_bytes(urllib.request.urlopen(request, timeout=90).read())
    reader = PdfReader(CACHE)
    pages = {p: reader.pages[p-1].extract_text() for p in [20,21,22,23,24,36,37,38]}
    groups = [
        ('Rural planning',21,'tax', [('Planning Services (ARAC)', 'Rural planning')]),
        ('Audit',21,'tax',[('Office of the Auditor General','Auditor General'),('External and Special Audits','External and special audits')]),
        ('Emergency & protective services',21,'tax',[
            ('Services - Emergency & Protective Services','Management and support'),('Public Safety Service','Public safety'),
            ('Ottawa Fire Services','Fire'),('Ottawa Paramedic Service','Paramedics'),('By-law and Regulatory Services','By-law'),('Public Policy Development','Public policy')]),
        ('Community & social services',22,'tax',[
            ('Community & Social Services','Management and support'),('Analytics','Community safety and well-being'),
            ('Employment and Social Services','Employment and social services'),("Children's Services","Children's services"),
            ('Housing and Homelessness Services','Housing and homelessness'),('Long Term Care','Long-term care'),
            ('Development','Equity, inclusion and social development')]),
        ('Parks, recreation & facilities',22,'tax',[
            ('Recreation, Cultural and Facility Services','Management and support'),('Programs','Recreation and culture'),
            ('Specialized Services','Aquatics and specialized services'),('Parks & Facilities Planning','Parks and facilities planning'),
            ('Facility Operations Services','Facility operations'),('Parks','Parks maintenance')]),
        ('Environment, waste & forestry',22,'tax',[
            ('Services','Management and support'),('Infrastructure Services','Infrastructure support'),('Asset Management Services','Asset management'),
            ('Climate Change and Resiliency','Climate change and resiliency'),('Solid Waste Services','Solid waste'),('Forestry Services','Forestry')]),
        ('Corporate services & capital funding',23,'tax',None),
        ('Planning, building & strategic housing',23,'tax',None),
        ('Roads, traffic & public works',24,'tax',None),
        ('Committee of Adjustment',24,'tax',[('Committee of Adjustment','Committee of Adjustment')]),
        ('Public health',24,'tax',[('Ottawa Public Health','Public health')]),
        ('Libraries',24,'tax',[('Ottawa Public Library','Libraries')]),
        ('Police',24,'tax',[('Ottawa Police Service','Police')]),
        ('Transit',24,'tax',[('Transit Committee','Transit')]),
        ('Drinking water',24,'rate',[('Drinking Water Services','Drinking water')]),
        ('Wastewater',24,'rate',[('Wastewater Services','Wastewater')]),
        ('Stormwater',24,'rate',[('Stormwater Services','Stormwater')]),
    ]
    operating=[]
    for label,page,funding,children in groups:
        text=pages[page]
        if label=='Environment, waste & forestry': text=text.split('Environment and Climate Change Committee')[1]
        if children is None:
            totals=re.findall(r'Total\s+((?:'+NUMBER+r'\s+){9}'+NUMBER+r')', ' '.join(text.split()))
            index=1 if label.startswith('Planning,') else 0
            vals=numbers(totals[index])
            detail=[]
            if label.startswith('Corporate services'):
                non_departmental=table_row(text,'Non Departmental',10)
                detail=[{'name':'Corporate departments','budget_2025':vals[3]-non_departmental[3],'budget_2026':vals[6]-non_departmental[6]},
                        {'name':'Non-departmental: capital funding, debt and other costs','budget_2025':non_departmental[3],'budget_2026':non_departmental[6]}]
        else:
            detail=[]
            for source_name,name in children:
                vals=table_row(text,source_name,10)
                detail.append({'name':name,'budget_2025':vals[3],'budget_2026':vals[6]})
            vals=[0]*10
            vals[3]=sum(x['budget_2025'] for x in detail)
            vals[6]=sum(x['budget_2026'] for x in detail)
        operating.append({'name':label,'funding':funding,'budget_2025':vals[3],'budget_2026':vals[6], 'pdf_page':page,'children':detail})
    capital_specs=[
        ('Rural affairs',36,'Agriculture & Rural Affairs Committee Total'),
        ('Community services',36,'Community Services Committee Total'),
        ('Emergency services',36,'Protective Services Committee Total'),
        ('Water, wastewater & stormwater',36,'Committee-Rate Total'),
        ('Environment & solid waste',37,'Committee-Tax Total'),
        ('Finance & corporate services',37,'Finance and Corporate Services Committee Total'),
        ('Planning & housing',37,'Planning and Housing Committee Total'),
        ('Transit committee',37,'Transit Committee Total'),
        ('Public works & infrastructure',37,'Public Works and Infrastructure Committee Total'),
        ('Libraries',38,'Ottawa Public Library Board Total'),
        ('Police',38,'Police Services Board Total')]
    capital=[]
    for name,page,label in capital_specs:
        vals=table_row(pages[page],label,9)
        capital.append({'name':name,'budget_2025':vals[0],'budget_2026':vals[1],'pdf_page':page,
                        'renewal':vals[2],'regulatory':vals[3],'growth':vals[4],'enhancement':vals[5]})
    capital_sections={
        'Finance & corporate services':('Finance and Corporate Services Committee','Planning and Housing Committee',[
            ('Corporate Real Estate Office','Corporate real estate'),('Corporate Finance','Corporate finance'),('General Government','General government'),('Information Technology','Information technology'),('Transit Services','Transit-related projects'),('Transportation Services','Transportation')]),
        'Public works & infrastructure':('Public Works and Infrastructure Committee',None,[
            ('Fleet Services','Fleet'),('Wastewater*','Integrated roads, water and wastewater'),('Parking Services','Parking'),('Roads Services','Roads'),('Traffic Services','Traffic'),('Transit Services','Transit-related projects'),('Transportation Services','Transportation')]),
        'Community services':('Community Services Committee','Emergency Preparedness and Protective Services Committee',[
            ('Child Care','Child care'),('Long Term Care','Long-term care'),('Parks Maintenance','Parks maintenance'),('Parks, Buildings & Grounds','Parks, buildings and grounds'),('Parks, Recreation & Culture','Parks, recreation and culture'),('Social Services','Social services')])}
    for row in capital:
        if row['name'] in capital_sections:
            start,end,specs=capital_sections[row['name']]
            text=pages[row['pdf_page']].split(start)[1]
            if end: text=text.split(end)[0]
            row['children']=[]
            for source_name,name in specs:
                vals=table_row(text,source_name,9)
                row['children'].append({'name':name,'budget_2025':vals[0],'budget_2026':vals[1]})
    revenue_names=['Federal','Provincial','Municipal','Own Funds','Property Taxes','Investment Income','Development Charges','Payment-in-lieu of taxation','Fees and Service','Fines','Other']
    revenue=[]
    rt=pages[20].split('Revenues by Category')[1]
    for name in revenue_names:
        vals=table_row(rt,name,5)
        revenue.append({'name':name,'budget_2025':-vals[2],'budget_2026':-vals[3],'pdf_page':20})
    totals={'operating':{'2025':4903996,'2026':5218430},'capital':{'2025':1681432,'2026':1924233}}
    for key,rows in [('operating',operating),('capital',capital)]:
        for year in ['2025','2026']:
            delta=sum(r['budget_'+year] for r in rows)-totals[key][year]
            # Summing separately rounded service rows can differ by a few $000.
            if abs(delta)>5: raise ValueError(f'{key} {year} reconciliation failed: {delta} thousand')
            print(key,year,'row rounding difference ($000):',delta)
    for year in ['2025','2026']:
        assert abs(sum(x['budget_'+year] for x in revenue)-totals['operating'][year])<=3
    data={'reviewed':'2026-10-23','unit':'CAD thousands','status':'Adopted December 10, 2025',
          'source_url':URL,'source_sha256':hashlib.sha256(CACHE.read_bytes()).hexdigest(),
          'totals':totals,'operating':operating,'capital':capital,'revenue':revenue}
    dest=ROOT/'data'; dest.mkdir(parents=True,exist_ok=True)
    (dest/'budget.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    excerpts='\n\n'.join(f'PDF page {p} / printed page {p-19}\n{t}' for p,t in pages.items())
    (dest/'source-excerpts.txt').write_text('\n'.join(line.rstrip() for line in excerpts.splitlines())+'\n',encoding='utf-8')
    with (dest/'budget.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['budget_type','name','year','amount_cad_thousands','pdf_page'])
        for kind,rows in [('operating',operating),('capital_new_authority',capital),('operating_revenue',revenue)]:
            for row in rows:
                for year in ['2025','2026']:w.writerow([kind,row['name'],year,row['budget_'+year],row['pdf_page']])
    print('Built',dest/'budget.json')

if __name__=='__main__':build()

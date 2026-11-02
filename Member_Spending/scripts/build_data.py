"""Fetch official expense reports; retain sources and reconcile before exporting.
Run from any directory. Cached inputs are reused; --refresh refetches reports.
Dependencies: requests beautifulsoup4 pdfplumber geopandas pyproj shapely.
"""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal
import csv, gzip, hashlib, io, json, re, sys, unicodedata, zipfile
import requests
from bs4 import BeautifulSoup
import pdfplumber
import geopandas as gpd
from pyproj import Geod

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SOURCES = DATA / 'sources'
TMP = ROOT / 'tmp'
for p in [DATA, SOURCES, TMP]:
    p.mkdir(parents=True, exist_ok=True)
REFRESH = '--refresh' in sys.argv
MANIFEST = []
BASE = 'https://www.ourcommons.ca'
ONTARIO_PDF = 'https://www.ola.org/sites/default/files/common/pdf/2025-2026-individual-members-expenditures.pdf'
FED_GEO = 'https://www.elections.ca/res/cir/mapsCorner/edb/FederalElectoralDistricts_SHP.zip'
ON_GEO = 'https://www.elections.on.ca/content/dam/NGW/sitecontent/2017/preo/shapefiles/Polling%20Division%20Shapefile%20-%202025%20General%20Election.zip'

def fetch(url, path):
    if not path.exists() or REFRESH:
        r = requests.get(url, timeout=90)
        r.raise_for_status()
        path.write_bytes(gzip.compress(r.content,mtime=0) if path.suffix=='.gz' else r.content)
    raw = path.read_bytes()
    MANIFEST.append({'url':url, 'file':str(path.relative_to(ROOT)).replace('\\','/'),
                     'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw)})
    return gzip.decompress(raw) if path.suffix=='.gz' else raw

def norm(s):
    s=s.replace('œ','oe').replace('Œ','OE').replace('æ','ae').replace('Æ','AE')
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower()
    return re.sub('[^a-z0-9]', '', s.replace('(N)', ''))

def boundaries(url, name):
    raw = fetch(url, TMP / (name+'.zip'))
    target = TMP / name
    if REFRESH or not target.exists():
        zipfile.ZipFile(io.BytesIO(raw)).extractall(target)
    return gpd.read_file(next(target.rglob('*.shp')))

GEOD = Geod(ellps='WGS84')
def points(frame, field, capital):
    # Equal-area projected geometric centroid, not a population-weighted point.
    projected = frame.to_crs(3347)
    centroids = gpd.GeoSeries(projected.geometry.centroid, crs=3347).to_crs(4326)
    result = {}
    for (_, row), pt in zip(frame.iterrows(), centroids):
        _, _, metres = GEOD.inv(pt.x, pt.y, capital[0], capital[1])
        result[norm(str(row[field]))] = {'riding_id':str(row.get('ED_CF_NUM', row.get('ED_ID',''))),
             'boundary_name':str(row[field]), 'longitude':round(pt.x,6), 'latitude':round(pt.y,6),
             'distance_km':round(metres/1000,1)}
    return result

def federal():
    geo = boundaries(FED_GEO, 'federal-boundaries')
    assert len(geo) == 343
    lookup = points(geo, 'ED_NAMEE', (-75.7009,45.4218))
    # Join on official district codes. The boundary DBF contains some duplicated
    # or truncated labels; the official list supplies canonical names and renames.
    name_url='https://www.elections.ca/content.aspx?section=res&dir=cir/red/343list&document=index&lang=e'
    names=BeautifulSoup(fetch(name_url,SOURCES/'federal-district-names.html.gz'),'html.parser')
    by_code=points(geo,'ED_CF_NUM',(-75.7009,45.4218))
    lookup={};renames=[]
    for tr in names.select('tr'):
        cells=[td.get_text(' ',strip=True).strip(' *“”') for td in tr.select('td')]
        if len(cells)>=2 and re.fullmatch(r'\d{5}',cells[0]):
            match=dict(by_code[norm(cells[0])]);match['boundary_name']=cells[1]
            lookup[norm(cells[1])]=match
        elif len(cells)==2 and cells[0] and cells[1]:renames.append(cells)
    assert len(lookup)==343,len(lookup)
    for former,current in renames:
        if norm(current) in lookup:lookup[norm(former)]=lookup[norm(current)]
    periods = []
    for year, quarter in [(2027,1),(2026,4),(2026,3),(2026,2),(2026,1)]:
        key = f'federal-{year}-q{quarter}'
        url = f'{BASE}/proactivedisclosure/en/members/{year}/{quarter}'
        html = fetch(url, SOURCES / (key+'.html.gz')).decode('utf-8-sig')
        soup = BeautifulSoup(html,'html.parser')
        href = next(a['href'] for a in soup.select('a[href]') if a['href'].endswith('/csv'))
        raw = fetch(BASE+href, SOURCES / (key+'.csv')).decode('utf-8-sig')
        rows = []
        for i,r in enumerate(csv.DictReader(io.StringIO(raw,newline=''))):
            if not r.get('Name'): continue
            name = re.sub(r'\s+', ' ', r['Name']).strip()
            expenses = {k.lower(): float(Decimal(r[k])) for k in ['Salaries','Travel','Hospitality','Contracts']}
            riding = r['Constituency']
            row = {'id':key+'-'+str(i),'name':name,'riding':riding,'party':r['Caucus'],
                   'categories':expenses,'total':round(sum(expenses.values()),2),'source':url,
                   'status':'Vacant' if name.lower()=='vacant' else 'Reported member', 'source_row':i+2}
            # April 2025 election changed boundaries. Do not guess predecessor joins.
            match = lookup.get(norm(riding)) if (year,quarter)!=(2026,1) else None
            row.update(match or {'distance_km':None})
            row['province'] = {'10':'NL','11':'PE','12':'NS','13':'NB','24':'QC','35':'ON','46':'MB','47':'SK','48':'AB','59':'BC','60':'YT','61':'NT','62':'NU'}.get(row.get('riding_id','')[:2], 'Unmatched / former riding')
            rows.append(row)
        assert len(rows)>330
        months = {1:('Apr–Jun',year-1),2:('Jul–Sep',year-1),3:('Oct–Dec',year-1),4:('Jan–Mar',year)}
        label,y = months[quarter]
        periods.append({'id':key,'level':'federal','label':f'{label} {y} · quarter',
            'source':url,'rows':rows,'distance_note': '2023 riding boundaries; unmatched and vacant records omitted from the distance chart.' if quarter!=1 or year!=2026 else 'Distance comparison unavailable for this election-transition quarter: riding boundaries changed in April 2025.',
            'categories':[['salaries','Staff salaries'],['travel','Travel'],['hospitality','Hospitality'],['contracts','Contracts & offices']]})
        print(key,len(rows),'distance',sum(r['distance_km'] is not None for r in rows),flush=True)
    return periods

def pdf_rows(pdf, indexes, starts):
    """Column positions from visually checked landscape report. Blank money cells = 0."""
    rows = {}; totals = None
    for page_index in indexes:
        page = pdf.pages[page_index]
        words = page.extract_words(x_tolerance=1, y_tolerance=2)
        anchors = [w for w in words if 55<w['x0']<110 and w['top']>130 and w['text'].endswith(',') and w['text'].isupper()]
        anchors += [w for w in words if w['text']=='TOTALS']
        for anchor in anchors:
            y = anchor['top']
            same = sorted([w for w in words if abs(w['top']-y)<1.5], key=lambda w:w['x0'])
            name = ' '.join(w['text'] for w in same if 55<w['x0']<250)
            if name.startswith('GRAND TOTAL'):
                continue
            total = anchor['text']=='TOTALS'
            if total: name='TOTALS'
            if not total and ',' not in name: continue
            cells = []
            for left,right in zip(starts, starts[1:]+[780]):
                s = ''.join(w['text'] for w in same if left<=w['x0']<right).replace(',','').replace(' ','')
                cells.append(float(s) if '.' in s else int(s) if s else 0)
            if total:
                totals = cells
                break
            riding_words = sorted([w for w in words if y+3<w['top']<y+11 and 65<w['x0']<265],key=lambda w:w['x0'])
            riding = ' '.join(w['text'] for w in riding_words)
            marks = ''.join(w['text'] for w in same if w['x0']<55)
            assert name not in rows, name
            rows[name] = {'name':name,'riding':riding,'marks':marks,'cells':cells,'source_page':page_index+1}
    assert totals is not None
    return rows, totals

def ontario():
    geo = boundaries(ON_GEO, 'ontario-boundaries')
    print('Ontario geography fields',geo.columns.tolist(),flush=True)
    # Polling divisions dissolve to their enclosing electoral district.
    field = next(f for f in geo.columns if f.upper() in ['ED_NAME','ENGLISH_NA','ED_NAME_EN','ED_ENGLISH'])
    districts = geo.dissolve(by=field,as_index=False)
    assert len(districts)==124, len(districts)
    lookup = points(districts,field,(-79.3917,43.6624))
    raw = fetch(ONTARIO_PDF,SOURCES/'ontario-2025-2026.pdf')
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        travel,tt = pdf_rows(pdf,range(1,7),[280,350,420,460,510,575,645,710])
        office,ot = pdf_rows(pdf,range(9,15),[265,300,360,415,475,535,590,640,690])
    # Reconcile each monetary column against printed TOTALS (whole-dollar rounding).
    checks=[]
    for section, data, total, skip in [('travel',travel,tt,{3}),('office',office,ot,{0})]:
        for j,v in enumerate(total):
            if j in skip: continue
            actual=sum(r['cells'][j] for r in data.values())
            delta=actual-v
            assert abs(delta)<=len(data)*0.5+1,(section,j,actual,v)
            checks.append({'section':section,'column':j,'sum_rows':actual,'printed_total':v,'rounding_difference':delta})
    rows=[]
    for i,(name,o) in enumerate(office.items()):
        t=travel.get(name)
        c=o['cells']; tc=t['cells'] if t else [0]*8
        # Travel TOTAL excludes the overage: overage is already in office GRAND TOTAL.
        expenses=dict(salaries=c[1],rent=c[2],operations=c[3],communications=c[4],
                      travel=tc[0]+tc[1]+tc[2]+tc[4],accommodation=tc[5]+c[5],phone=c[7])
        published_total=c[8]+tc[6]
        row={'id':'ontario-2026-'+str(i),'name':name,'riding':o['riding'].replace(' (N)',''),
             'party':None,'province':'ON','status': 'Former member / closing costs' if o['marks']=='*' or o['marks']=='***' else 'Part-year member' if o['marks']=='**' else 'Reported member',
             'categories':expenses,'total':published_total,'rounding':published_total-sum(expenses.values()),
             'commute_travel':tc[0],'assembly_travel':tc[1],'family_travel':tc[2],
             'within_riding_travel':tc[4],'toronto_base':tc[5],'toronto_overage':c[5],
             'office_total':c[8],'travel_accommodation_total':tc[6],
             'office_page':o['source_page'],'travel_page':t['source_page'] if t else None,'source':ONTARIO_PDF}
        assert abs(row['rounding'])<=4,(name,row['rounding'])
        match=lookup.get(norm(row['riding']))
        row.update(match or {'distance_km':None})
        rows.append(row)
    assert set(travel)<=set(office)
    assert len(office)==142 and len(travel)==127,(len(office),len(travel))
    (DATA/'ontario-reconciliation.json').write_text(json.dumps({'columns':checks,'office_rows':len(office),'travel_rows':len(travel),'published_office_total':ot[-1],'published_travel_accommodation_total':tt[6]},indent=2),encoding='utf-8')
    print('Ontario',len(rows),'matched',sum(r['distance_km'] is not None for r in rows),flush=True)
    return {'id':'ontario-2026','level':'ontario','label':'Apr 2025–Mar 2026 · fiscal year','source':ONTARIO_PDF,
        'distance_note':'Geometric centre of each 2025 electoral district to Queen’s Park. Former-member closing costs excluded from the distance chart.',
        'categories':[['salaries','Support staff'],['rent','Office rent'],['operations','Office operations'],['communications','Communications'],['travel','Travel'],['accommodation','Toronto accommodation'],['phone','Long-distance phone']], 'rows':rows}

def main():
    periods=federal()+[ontario()]
    result={'checked':'2026-11-01','currency':'CAD','distance_method':'Geometric centroid in EPSG:3347; WGS84 ellipsoidal geodesic to Parliament Hill or Queen’s Park; one-way km. Not population-weighted or actual travel.', 'periods':periods}
    text=json.dumps(result,ensure_ascii=False,separators=(',',':'))
    (DATA/'spending.json').write_text(text,encoding='utf-8')
    (DATA/'spending-data.js').write_text('window.MEMBER_SPENDING='+text+';\n',encoding='utf-8')
    flat=[]
    for p in periods:
        for r in p['rows']:
            for k,label in p['categories']:
                flat.append({'period':p['label'],'level':p['level'],'member':r['name'],'riding':r['riding'],'status':r['status'], 'category':label,'amount_cad':r['categories'][k],'published_total_cad':r['total'],'distance_km':r['distance_km'],'source_url':r['source']})
    with (DATA/'spending.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    (DATA/'source-manifest.json').write_text(json.dumps(MANIFEST,indent=2),encoding='utf-8')
    print('Exported',len(flat),'category records')

if __name__=='__main__': main()

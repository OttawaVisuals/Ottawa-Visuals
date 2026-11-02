"""Official-source ER histories and regular-provider access. No series splicing."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
import csv,hashlib,json,re,zipfile
import requests,truststore,openpyxl
from bs4 import BeautifulSoup
truststore.inject_into_ssl()
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';RAW=DATA/'raw'
RAW.mkdir(parents=True,exist_ok=True)
ER_PAGE='https://www.ontariohealth.ca/system/reporting/performance/time-spent-in-emergency-departments'
ER_API='https://drivepublic.hqontario.ca/Report/'
FAO='https://fao-on.org/en/report/health-2023/'
CIHI='https://www.cihi.ca/sites/default/files/document/data-file/880-canadians-with-a-primary-health-care-provider-data-table-en.xlsx'
CCHS='https://www150.statcan.gc.ca/n1/tbl/csv/13100113-eng.zip'
manifest=[]
def fetch(name,url):
 p=RAW/name
 if not p.exists():
  x=requests.get(url,timeout=90);x.raise_for_status();p.write_bytes(x.content)
 manifest.append(dict(file=name,url=url,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 return p
def export(name,rows):
 with (DATA/name).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def number(v):
 try:return float(v)
 except (ValueError,TypeError):return None
def build():
 fetch('er-page.html',ER_PAGE)
 url=ER_API+'GetTopHospitalsEDCombined?'+urlencode({'ResultType':'PIA','org_ID':-354,'fieldName':'LOS_mean','lang':'en'})
 directory=json.loads(fetch('er-sites.json',url).read_text())
 wanted=['Ontario','Ottawa Hospital (The)-Civic Site','Ottawa Hospital (The)-General Site',"Children's Hospital Of Eastern Ontario",'Queensway-Carleton Hospital','Hopital Montfort']
 sites=[dict(id=r['SNum'],name=r['Name']) for name in wanted for r in directory if r['Name']==name]
 assert len(sites)==6 and len({s['id'] for s in sites})==6
 def load(item):
  site,metric=item
  params={'ResultType':metric,'org_ID':site['id'],'showOnlyLatestPeriod':'false','lang':'en'}
  url=ER_API+'GetWaitTimesEDData?'+urlencode(params)
  name=f'er-{site["id"]}-{metric}.json'
  result=json.loads(fetch(name,url).read_text())
  out=[]
  for i,r in enumerate(result):
   if r['Org_ID']!=site['id']:continue  # API also returns the Ontario comparator.
   out.append(dict(month=r['Key'],site_id=site['id'],site=site['name'],metric=metric,mean_hours=number(r['WaitTime_mean']),p90_hours=number(r['WaitTime_90percentile']),visits=number(r['number_of_cases']),percent_within_target=number(r['WaitTime_percent_within_target']),target_hours=r['Target'],definition=r['PriorityDescription'],source_file=name,source_index=i,source_url=url))
  return out
 er=[row for batch in ThreadPoolExecutor(max_workers=4).map(load,[(s,m) for s in sites for m in ['PIA','A','NAH','L']]) for row in batch]
 er.sort(key=lambda r:(r['site_id'],r['metric'],r['month']))
 assert len({(r['month'],r['site_id'],r['metric']) for r in er})==len(er)
 # Historical annual series from the FAO's accessible tables. Preserve partial endpoint.
 soup=BeautifulSoup(fetch('fao-er-history.html',FAO).read_text(encoding='utf-8'),'html.parser')
 history=[]
 for table_id,group in [('fig20','Admitted patients'),('fig21','All patients')]:
  t=soup.find('table',id=table_id);assert t
  for tr in t.select('tr'):
   cells=[td.get_text(' ',strip=True) for td in tr.select('td')]
   if len(cells)!=2:continue
   period,hours=cells
   history.append(dict(fiscal_start=int(period[:4]),period=period,group=group,mean_hours=float(hours),partial=period=='2022-23',coverage='April–November 2022 only' if period=='2022-23' else 'Full fiscal year',source_url=FAO+'#'+table_id,source_table=table_id))
 assert len(history)==30
 # Retain source rows (including confidence limits and flags) rather than rounded charts.
 z=zipfile.ZipFile(fetch('cchs-historical.zip',CCHS));stream=z.open('13100113.csv')
 header=next(csv.reader([stream.readline().decode('utf-8-sig')]))
 source_rows=[]
 for line in stream:
  if b'Ontario' not in line or b'Has a regular healthcare provider' not in line:continue
  row=dict(zip(header,next(csv.reader([line.decode('utf-8-sig')]))))
  if row['GEO'] in ['Ontario','City of Ottawa Health Unit, Ontario'] and row['Age group']=='Total, 12 years and over' and row['Sex']=='Both sexes':source_rows.append(row)
 meta=z.read('13100113_MetaData.csv').decode('utf-8-sig')
 metadata='\n'.join(line for line in meta.splitlines() if any(term in line.lower() for term in ['regular','redesign','denominator','confidence interval','2020','2021/2022']))
 (DATA/'provider-source-notes.txt').write_text(metadata+'\n',encoding='utf-8')
 export('provider-source-rows.csv',source_rows)
 provider=[]
 for geo in ['Ontario','City of Ottawa Health Unit, Ontario']:
  for period in sorted({r['REF_DATE'] for r in source_rows}):
   group=[r for r in source_rows if r['GEO']==geo and r['REF_DATE']==period]
   def select(characteristic):return next(r for r in group if r['Characteristics']==characteristic)
   estimate=select('Percent');lo=select('Low 95% confidence interval, percent');hi=select('High 95% confidence interval, percent')
   have=number(estimate['VALUE']);low=number(lo['VALUE']);high=number(hi['VALUE'])
   provider.append(dict(series='Historical Ottawa comparison',geography='Ottawa' if geo.startswith('City') else 'Ontario',source_geography=geo,period=period,period_start=int(period[:4]),period_end=int(period[-4:]),age='12 years and older',has_percent=have,has_low=low,has_high=high,without_percent=round(100-have,10) if have is not None else None,without_low=round(100-high,10) if high is not None else None,without_high=round(100-low,10) if low is not None else None,has_people=number(select('Number of persons')['VALUE']),status=estimate['STATUS'],definition='Regular healthcare provider; not family-doctor-only',break_before=period=='2021/2022',source_table='13-10-0113-01',source_vector=estimate['VECTOR'],source_coordinate=estimate['COORDINATE'],source_url='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1310011301'))
 assert len(provider)==8
 # Current adult snapshots have a distinct age group and changed questions each year.
 w=openpyxl.load_workbook(fetch('cihi-primary-care.xlsx',CIHI),read_only=True,data_only=True)
 rows=list(w['Table 1'].iter_rows(max_col=30,values_only=True))
 for i,r in enumerate(rows[2:],3):
  if r[2]!='Ontario' or r[9]!='Adults' or r[12]!='Not applicable':continue
  year=int(r[11]);have,low,high=r[14:17]
  provider.append(dict(series='Recent Ontario adults',geography='Ontario',source_geography='Ontario',period=str(year),period_start=year,period_end=year,age='18 years and older',has_percent=have,has_low=low,has_high=high,without_percent=round(100-have,10),without_low=round(100-high,10),without_high=round(100-low,10),has_people=r[26],status='' if r[18] in ['–','—',None] else str(r[18]),definition={2023:'Regular provider includes medical specialists',2024:'Regular provider; medical specialists removed from listed categories',2025:'Primary-care professional/team; private-pay model excluded'}[year],break_before=True,source_table='CIHI indicator 880',source_vector='',source_coordinate=f'Table 1!O{i}:Q{i}',source_url=CIHI))
 assert len(provider)==11
 output={'reviewed':'2026-11-02','er':er,'er_sites':sites,'er_history':history,'provider':provider,'er_coverage_note':'December 2025 refresh expanded reporting by 43 sites and revised historical results; do not splice with older exports. This snapshot uses one current export vintage.'}
 export('er-monthly.csv',er);export('er-history.csv',history);export('provider-access.csv',provider)
 (DATA/'access.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (DATA/'access-data.js').write_text('window.HEALTHCARE_ACCESS = '+json.dumps(output,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
 (DATA/'access-source-manifest.json').write_text(json.dumps(sorted(manifest,key=lambda r:r['file']),indent=2)+'\n',encoding='utf-8')
 print(f'Built {len(er)} monthly ER records, {len(history)} annual ER observations and {len(provider)} provider-access estimates.')
if __name__=='__main__':build()

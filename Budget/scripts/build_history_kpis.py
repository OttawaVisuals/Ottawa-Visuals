"""Build sourced history and KPI snapshots. PDFs stay in the OS temp directory.
Requires pypdf. Chart-image housing labels are reviewed in housing-reviewed.csv.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import tempfile
import urllib.request
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'data'
TEMP=Path(tempfile.gettempdir())
SPECS={
 'budget2024':('ottawa-budget-2024.pdf','https://documents.ottawa.ca/sites/default/files/2024%20Adopted%20Budget%20Book%20English%20Condensed-AODA.pdf'),
 'budget2026':('ottawa-budget-2026.pdf','https://documents.ottawa.ca/sites/default/files/2026%20Adopted%20Budget%20Book%20English%20Condensed.pdf'),
 'paramedics':('ottawa-paramedic-2025.pdf','https://pub-ottawa.escribemeetings.com/filestream.ashx?DocumentId=318696'),
 'infrastructure':('ottawa-transportation-amp.pdf','https://documents.ottawa.ca/sites/default/files/2025_transportation_amp_en.pdf'),
 'housing':('ottawa-housing-hna.pdf','https://documents.ottawa.ca/sites/default/files/2024-HNA_EN.pdf')}
readers={};sources={};excerpts=[]
for key,(filename,url) in SPECS.items():
 p=TEMP/filename
 if not p.exists():
  try:p.write_bytes(urllib.request.urlopen(url,timeout=90).read())
  except Exception as e:raise RuntimeError(f'Download {url} in a browser and cache at {p}; source not substituted') from e
 readers[key]=PdfReader(p)
 sources[key]={'url':url,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def page(key,n):
 t=readers[key].pages[n-1].extract_text()
 excerpts.append(f'{key} | PDF page {n}\n{t}')
 return ' '.join(t.split())

def row(text,label,count):
 found=re.search(re.escape(label)+r'\s+'+r'\s+'.join([r'(-?[\d,]+(?:\.\d+)?%?)']*count),text)
 if not found:raise ValueError(f'Cannot locate {label!r}; review source')
 return [float(x.replace(',','').replace('%','')) for x in found.groups()]

categories=['General government','Protection to persons and property','Roads, traffic and parking','Transit','Environmental services','Health services','Social and family services','Social housing','Recreation and cultural services','Planning and development']
history={'reviewed':'2026-10-23','unit':'CAD thousands','basis':'Full-accrual consolidated budget expenses by function; nominal dollars; not actual spending','years':[2023,2024,2025,2026],'sources':{},'totals':{},'rows':[{'name':name,'values':{}} for name in categories]}
for key,p,years in [('budget2024',14,[2024,2023]),('budget2026',15,[2026,2025])]:
 text=page(key,p).split('Expenses',1)[1]
 for category in history['rows']:
  values=row(text,category['name'],2)
  for year,value in zip(years,values):category['values'][str(year)]=int(value)
 totals=row(text,'Total Expenses',2)
 for year,total in zip(years,totals):
  history['totals'][str(year)]=int(total)
  history['sources'][str(year)]={**sources[key],'pdf_page':p,'locator':'Table 1: Full Accrual Budget, expenses; '+('current-year budget' if year==years[0] else 'prior-year budget comparator')}
  assert abs(sum(r['values'][str(year)] for r in history['rows'])-total)<=3
(DEST/'history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (DEST/'history.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['function','year','budget_cad_thousands','basis','source_url','pdf_page'])
 for record in history['rows']+[{'name':'Total expenses','values':history['totals']}]:
  for year,value in sorted(record['values'].items()):w.writerow([record['name'],year,value,'full-accrual budget',history['sources'][year]['url'],history['sources'][year]['pdf_page']])

kpis={'reviewed':'2026-10-23','sources':sources,'groups':{}}
def metric(key,name,unit,direction,definition,values,source,pdf_page,target=None,note='',region=None):
 return {'id':key,'name':name,'unit':unit,'direction':direction,'definition':definition,'values':{str(y):v for y,v in values.items()},'source':source,'pdf_page':pdf_page,'target':target,'note':note,'region':region}

para={'name':'Paramedics','note':'2025 annual report, published June 2026. Response clock starts when a crew is notified, not when 9-1-1 answers. Dispatch changed in April 2024; call mix and triage can affect comparisons.','metrics':[]}
pt=page('paramedics',18)
regional={region:page('paramedics',20).split('Table '+str(n)+':')[1].split('Table ')[0] for region,n in [('urban',6),('rural',7)]}
for i,minutes in enumerate([8,10,15,20,25],1):
 label='CTAS '+str(i)+(' (life threatening)' if i==1 else ' (urgent)' if i==2 else '')
 values=row(pt,label+' '+str(minutes)+':00',6)
 assert values[0]==75
 for region,series,pnum in [('city',values[1:],18)]+[(r,row(t,label,5),20) for r,t in regional.items()]:
  para['metrics'].append(metric(f'ctas{i}-{region}',f'CTAS {i} · '+('life-threatening calls' if i==1 else 'urgent calls' if i==2 else 'response performance'),'percent','higher',f'Percent of CTAS {i} calls reached within {minutes} minutes of crew notification.',dict(zip(range(2021,2026),series)),'paramedics',pnum,target=75,region=region))
cardiac=page('paramedics',19)
v=row(cardiac,'6:00',6);assert v[0]==65
para['metrics'].append(metric('cardiac','Sudden cardiac arrest','percent','higher','Percent reached within 6 minutes of crew notification by any person with an automated external defibrillator, not necessarily a paramedic.',dict(zip(range(2021,2026),v[1:])),'paramedics',19,target=65,note='Arrival of any person with an AED; not the same responder definition as CTAS.'))
zero=page('paramedics',22)
zero_values={year:row(zero,str(year),2)[0] for year in range(2021,2026)}
para['metrics'].append(metric('level-zero','Time with no ambulance available','minutes','lower','Total minutes at Level Zero: no ambulance available to respond to a call in the community.',zero_values,'paramedics',22,note='The report states there should never be time at Level Zero; no numeric performance target is plotted.'))
kpis['groups']['paramedics']=para

it=page('infrastructure',16)
infra={'name':'Infrastructure conditions','note':'Transportation assets only. Trend values refer to 2019 and 2023, published in the 2025 plan; they are not annual 2025/2026 inspections. Targets are not extracted here.','metrics':[]}
infra_specs=[
 ('pavement','Paved-road condition','index','(PQI on a scale of 0 to 100)*','Pavement Quality Index, 0–100; higher means better pavement.'),
 ('bridges','Bridge condition','index','(BCI on a scale of 0 to 100)*','Average Bridge Condition Index, 0–100; higher means better condition.'),
 ('culverts','Bridge-culvert condition','index','For Bridge Culverts (structural culverts), the average bridge condition index value (BCI on a scale of 0 to 100)*','Average Bridge Condition Index for structural culverts, 0–100.'),
 ('active','Walking & cycling assets in fair or better condition','percent','Percent of Active Transportation assets in fair or better condition','Percent of active transportation assets reported in fair or better condition.'),
 ('fleet','Roads & traffic fleet in fair or better condition','percent','Percent of Roads and Traffc Services Fleet assets in fair or better condition','Percent of roads and traffic services fleet assets in fair or better condition.')]
for key,name,unit,label,definition in infra_specs:
 vals=row(it,label,2)
 infra['metrics'].append(metric(key,name,unit,'higher',definition,dict(zip([2019,2023],vals)),'infrastructure',16,note='Two dated observations; no annual values are interpolated. Targets not extracted.'))
page('infrastructure',11)
infra['condition_snapshot']={'name':'All transportation assets, by replacement cost','source':'infrastructure','pdf_page':11,'period':'2025 plan snapshot; inspection dates vary','categories':[{'name':n,'value':v} for n,v in [('Very good',12),('Good',32),('Fair',41),('Poor',11),('Very poor',4)]],'note':'Replacement-cost weighted, not a count of assets or kilometres. Excludes streetlights and flashers. The condition snapshot is separate from the dated 2019/2023 measures.'}
kpis['groups']['infrastructure']=infra

house={'name':'Housing','note':'2019–2024 official assessment figures. The 2024 wait-list snapshot is December 10. Wait-list placements are not all affordable homes built, and shelter use is not all homelessness. Targets are not extracted here.','metrics':[]}
with (DEST/'housing-reviewed.csv').open(encoding='utf-8',newline='') as f:reviewed=list(csv.DictReader(f))
for key,name,direction,definition,pnum in [('waitlist','Households waiting for subsidized housing','lower','Active households on the Centralized Wait List; a stock of applications, not all households needing housing.',117),('placements','Households housed from the wait list','higher','Households placed from the Centralized Wait List during the year; not newly built housing units.',123)]:
 page('housing',pnum)
 house['metrics'].append(metric(key,name,'households',direction,definition,{int(r['year']):int(r['value']) for r in reviewed if r['metric']==key},'housing',pnum,note='Chart-image labels manually transcribed and visually checked against Figure '+('57; 2024 wait list is as of December 10.' if key=='waitlist' else '62. No published annual target extracted.')))
shelter=page('housing',215)
for key,name,label,unit,definition in [('shelter-users','People using overnight shelters','T otal people','people','People using an overnight emergency shelter in the year. Not a count of all people experiencing homelessness.'),('shelter-nights','Nights spent in emergency shelters','T o tal nights','nights','Total overnight emergency-shelter nights during the year.')]:
 vals=row(shelter,label,6)
 house['metrics'].append(metric(key,name,unit,'context',definition,dict(zip(range(2019,2025),vals)),'housing',215,note='Demand/context measure; a decrease alone does not establish that housing access improved.'))
kpis['groups']['housing']=house
(DEST/'kpis.json').write_text(json.dumps(kpis,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (DEST/'kpis.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['group','metric','region','year','value','unit','target','source_url','pdf_page','note'])
 for group,g in kpis['groups'].items():
  for m in g['metrics']:
   for year,value in m['values'].items():w.writerow([group,m['name'],m['region'] or 'all',year,value,m['unit'],m['target'],sources[m['source']]['url'],m['pdf_page'],m['note']])
  if 'condition_snapshot' in g:
   s=g['condition_snapshot']
   for c in s['categories']:w.writerow([group,'Condition snapshot: '+c['name'],'transportation',s['period'],c['value'],'percent of replacement cost','',sources[s['source']]['url'],s['pdf_page'],s['note']])
(DEST/'history-kpi-source-excerpts.txt').write_text('\n'.join(line.rstrip() for line in '\n\n'.join(dict.fromkeys(excerpts)).splitlines())+'\n',encoding='utf-8')
print('Built 2023–2026 budget history and',sum(len(g['metrics']) for g in kpis['groups'].values()),'KPI series.')

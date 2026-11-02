"""Reviewed transcription of audited statement lines, preserving original scope."""
from build_data import ROOT,DATA,RAW,write_csv
import json,re

# Each pair is current year then prior-year comparator, in source $000 except Montfort.
# government main line, expense subtotal, salaries+benefits, separately shown building
# expenses, parking expenses, separately shown retroactive wage expenses.
PAIRS={
 'toh':{
  2020:([937252,915580],[1245181,1152364],[752051,719111],[29502,29050],[8894,9859],[0,0]),
  2022:([1114884,1081810],[1456096,1383318],[832507,802655],[30949,30438],[5210,8533],[0,0]),
  2024:([1267501,1167598],[1715705,1555549],[976656,886678],[35318,33002],[7614,5588],[0,0]),
  2026:([1392382,1340846],[1898729,1830845],[1081188,1027062],[38480,36770],[11115,8969],[0,0])},
 'cheo':{
  2020:([164900,161358],[320591,310960],[164764,157151],[5174,4948],[0,0],[0,0]),
  2022:([198835,191379],[369782,337123],[192618,179776],[5530,5309],[0,0],[0,0]),
  2024:([280627,223035],[502177,417735],[264134,202680],[5402,5699],[0,0],[4019,10253]),
  2026:([323486,307801],[574098,551399],[299051,288573],[8455,6290],[0,0],[0,0])},
 'qch':{
  2020:([171100,167097],[211522,203314],[150342,146521],[9597,9355],[0,0],[0,0]),
  2022:([214173,208703],[251863,242796],[181170,171183],[10119,10065],[0,0],[0,0]),
  2024:([240535,223629],[294237,266048],[207484,187536],[10858,10609],[0,0],[2750,7038]),
  2026:([267979,257401],[324209,312934],[229826,221092],[10909,10957],[0,0],[0,0])},
 'montfort':{
  2024:([227646066,202116064],[300084704,270313629],[180280915,160284580],[0,0],[0,0],[0,0]),
  2026:([247112174,239451086],[320839206,314878664],[194127983,190576807],[0,0],[0,0],[0,0])}}
NAMES={'toh':'The Ottawa Hospital','cheo':'CHEO','qch':'Queensway Carleton','montfort':'Hôpital Montfort'}
manifest={r['file']:r for r in json.loads((DATA/'source-manifest.json').read_text())}
excerpts=[];data=[]
for key,pairs in PAIRS.items():
 records=[]
 for end,vals in pairs.items():
  filename=f'{key}-{end}.pdf';txt=(RAW/filename.replace('.pdf','.txt')).read_text(encoding='utf-8')
  pages=txt.split('PDF PAGE ')
  page=next(p for p in pages if re.search(r'(?:statement of operations)',p,re.I) and re.search(r'Salaries',p,re.I) and 'Table of Contents' not in p)
  pdf_page=int(page.split('\n')[0]);excerpts.append(f'{filename} | PDF page {pdf_page}\n{page}')
  factor=1 if key=='montfort' else 1000
  for offset,y in enumerate([end,end-1]):
   gov,subtotal,comp,building,parking,retro=[a[offset]*factor for a in vals]
   # Verify directly transcribed main funding and expense subtotals occur in source.
   for v in [vals[0][offset],vals[1][offset]]:assert f'{v:,}' in page,(filename,v)
   records.append(dict(fiscal_end=y,fiscal_year=f'{y-1}–{str(y)[2:]}',government_funding_line_cad=gov,expense_subtotal_cad=subtotal,building_expense_cad=building,parking_expense_cad=parking,separate_retro_wage_expense_cad=retro,expenses_cad=subtotal+building+parking+retro,compensation_line_cad=comp,source_url=manifest[filename]['url'],source_file=filename,source_pdf_page=pdf_page,source_column='Current year' if offset==0 else 'Prior-year comparator'))
 records.sort(key=lambda x:x['fiscal_end'])
 notes={
  'toh':'Non-consolidated hospital finances. Expense totals add separately reported building amortization and parking expenses. Employee counts below also include the University of Ottawa Heart Institute; the financial and staffing scopes differ.',
  'cheo':'CHEO–Ottawa Children’s Treatment Centre. Expenses include other funded programs and separately reported building amortization and retroactive wage costs. The compensation line excludes compensation embedded in other funded programs.',
  'qch':'Hospital-only statements. Expense totals add separately reported building amortization and retroactive wage costs. OHIP revenue is a separate line and is not included in the government-funding line shown here.',
  'montfort':'Non-consolidated hospital statements, total column. Expenses include capital amortization. Net prior-years adjustments reported below expenses in 2023 and 2024 are kept separate and not assigned to expense or funding totals.'}[key]
 staffing=[]
 if key=='toh':
  for start in range(2020,2026):
   fn=f'toh-annual-{start}';p=RAW/(fn+'.txt');s=p.read_text(encoding='utf-8')
   if start>=2024:s=s[s.index('Fast Facts - People'):]
   emp=re.search(r'([\d,]+)\s*\*?\s*Employees',s);nurse=re.search(r'([\d,]+)\s*Nurses',s)
   assert emp and nurse
   url=manifest[fn+('.html' if start>=2024 else '.docx')]['url']
   staffing.append(dict(fiscal_end=start+1,fiscal_year=f'{start}–{str(start+1)[2:]}',employees=int(emp[1].replace(',','')),nurses=int(nurse[1].replace(',','')),scope='Active employees of The Ottawa Hospital and University of Ottawa Heart Institute; headcount, not FTE',source_url=url))
   excerpt=s[max(0,emp.start()-100):emp.start()+1400]
   excerpts.append(f'{fn} | Fast facts\n{excerpt}')
 data.append(dict(id=key,name=NAMES[key],note=notes,financials=records,staffing=staffing,funding_label='Ministry of Health / Ontario Health allocations' if key in ['cheo','montfort'] else 'Funding from governments'))
flat=[dict(hospital=h['name'],**r) for h in data for r in h['financials']]
write_csv('ottawa-hospitals.csv',flat)
write_csv('ottawa-staffing.csv',[dict(hospital=h['name'],**r) for h in data for r in h['staffing']])
(DATA/'ottawa-hospitals.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(DATA/'hospital-source-excerpts.txt').write_text('\n\n'.join(excerpts),encoding='utf-8')
print('Built',len(flat),'hospital financial years and',sum(len(h['staffing']) for h in data),'staffing years.')

"""Build traceable Ontario series from the CIHI 2025 workbooks. No interpolation."""
from pathlib import Path
import csv,json,re
import openpyxl

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; RAW=DATA/'raw'
def rows(file,sheet):
    w=openpyxl.load_workbook(RAW/file,read_only=True,data_only=True)
    return list(w[sheet].iter_rows(max_col=20,values_only=True))
def year(v):
    m=re.match(r'(\d{4})',str(v));return int(m[1]) if m else None
def num(v):return v if isinstance(v,(int,float)) else None
def write_csv(name,records):
    with (DATA/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
def build():
    app=openpyxl.load_workbook(RAW/'nhex-appendices-a-d.xlsx',read_only=True,data_only=True)
    pop=list(app[next(x for x in app.sheetnames if x.startswith('D '))].iter_rows(max_col=17,values_only=True))
    price=list(app[next(x for x in app.sheetnames if x.startswith('B '))].iter_rows(max_col=15,values_only=True))
    populations={year(r[0]):r[6]*1000 for r in pop[3:54]}
    fiscal_pop={year(r[0]):r[6]*1000 for r in pop[113:165] if year(r[0])}
    # B.3: common total-health implicit price index, not all-items consumer CPI.
    prices={year(r[0]):r[6] for r in price[223:274]}
    assert set(prices)==set(range(1975,2026))
    spending=[]
    excerpts=[]
    for sector,label in [('d4','Ontario government'),('d3','All public sources'),('d2','Private sources')]:
        rr=rows(f'nhex-series-{sector}.xlsx','Ont.')
        assert rr[2][1]=='Hospitals' and rr[2][3]=='Physicians' and rr[2][13]=='Total'
        for i,r in enumerate(rr[3:54],4):
            y=year(r[0]); assert y in populations
            for category,col in [('Hospitals',1),('Physicians',3),('All health care',13)]:
                value=num(r[col]);assert value is not None and value>=0
                spending.append(dict(year=y,category=category,funding=label,million_cad=value,population=populations[y],per_resident_cad=value*1e6/populations[y],health_price_index=prices[y],real_2023_million_cad=value*prices[2023]/prices[y],status='Forecast' if 'f' in str(r[0]) else 'Actual',source_file=f'nhex-series-{sector}.xlsx',source_sheet='Ont.',source_cell=f'{openpyxl.utils.get_column_letter(col+1)}{i}'))
        excerpts.append({'file':f'nhex-series-{sector}.xlsx','sheet':'Ont.','table':rr[1][0],'header':rr[2][:14],'notes':[r[0] for r in rr[-15:] if r[0]]})
    workforce=[]
    ftes=rows('hospital-workforce.xlsx','FTE data')
    beds=rows('hospital-workforce.xlsx','tbD data')
    for i,r in enumerate(ftes[1:],2):
        if r[4]!='ON' or r[2]!='Calculated FTEs' or r[5:7]!=('Hospital','All'):continue
        y=r[3];b=next(b for b in beds[1:] if b[1]==y and b[2]=='ON' and str(b[0]).startswith('Beds staffed'))
        assert r[19]>0 and b[7]>0 and b[12]>=b[7]
        workforce.append(dict(fiscal_start=y,fiscal_year=f'{y}–{str(y+1)[2:]}',population=fiscal_pop[y],fte=r[19],fte_per_1000=r[19]/fiscal_pop[y]*1000,acute_beds=b[7],acute_beds_per_1000=b[7]/fiscal_pop[y]*1000,all_beds=b[12],all_beds_per_1000=b[12]/fiscal_pop[y]*1000,reporting_organizations=r[1],fte_source_row=i,beds_source_row=beds.index(b)+1))
    assert len(workforce)==10 and len(spending)==459
    for y in range(1975,2026):
        for c in ['Hospitals','Physicians','All health care']:
            rr=[r for r in spending if r['year']==y and r['category']==c]
            assert rr[0]['million_cad']<=rr[1]['million_cad']+0.01
    write_csv('ontario-spending.csv',spending);write_csv('ontario-workforce.csv',workforce)
    (DATA/'cihi-excerpts.json').write_text(json.dumps(excerpts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    data={'reviewed':'2026-11-02','spending':spending,'workforce':workforce}
    if (DATA/'ottawa-hospitals.json').exists():data['hospitals']=json.loads((DATA/'ottawa-hospitals.json').read_text(encoding='utf-8'))
    (DATA/'healthcare.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (DATA/'page-data.js').write_text('window.HEALTHCARE_DATA = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print(f'Built {len(spending)} spending rows and {len(workforce)} workforce years.')
if __name__=='__main__':build()

"""Deliberately refresh OPS aggregates; no individual records are saved.

Run manually, review snapshot/labels, then rebuild. Not part of normal page builds.
"""
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
BASE='https://services7.arcgis.com/2vhcNzw0NfUwAD3d/arcgis/rest/services'
LAYER=BASE+'/CrimeMap_YE/FeatureServer/16'
CATEGORIES=['Assaults','Robbery','Break and Enter','Theft $5000 and Under']
WHERE="Neighbourhood = 'Byward Market' AND Offence_Category IN ("+','.join("'"+c+"'" for c in CATEGORIES)+')'


def request(url,params):
    full=url+'?'+urlencode({'f':'json',**params})
    raw=urlopen(full,timeout=40).read()
    d=json.loads(raw)
    if 'error' in d:raise ValueError(d['error'])
    return d,{'url':full,'sha256':hashlib.sha256(raw).hexdigest()}


def fetch():
    stats,p1=request(LAYER+'/query',{'where':WHERE,'groupByFieldsForStatistics':'Reported_Year,Offence_Category','outStatistics':json.dumps([{'statisticType':'count','onStatisticField':'OBJECTID','outStatisticFieldName':'n'}]),'returnGeometry':'false','orderByFields':'Reported_Year,Offence_Category'})
    assert not stats.get('exceededTransferLimit')
    rows=[{'year':f['attributes']['Reported_Year'],'category':f['attributes']['Offence_Category'],'count':f['attributes']['n']} for f in stats['features']]
    assert {r['year'] for r in rows}==set(range(2018,2026)), 'Published cutoff changed; review before updating'
    assert len(rows)==32 and all(r['count']>0 for r in rows)
    counts=Counter();seen=set();duplicates=0;offset=0;pages=0
    while True:
        d,_=request(LAYER+'/query',{'where':WHERE,'outFields':'Reported_Year,Offence_Category,GO_Number','returnGeometry':'false','resultRecordCount':2000,'resultOffset':offset})
        pages+=1
        for f in d['features']:
            a=f['attributes'];key=(a['Reported_Year'],a['Offence_Category']);counts[key]+=1
            go=(*key,a['GO_Number']);duplicates+=go in seen;seen.add(go)
        if not d.get('exceededTransferLimit'):break
        assert d['features'];offset+=len(d['features'])
    assert duplicates==0
    assert dict(counts)=={(r['year'],r['category']):r['count'] for r in rows}
    boundary,p2=request(BASE+'/ONS_2017/FeatureServer/0/query',{'where':"UPPER(namese2016) LIKE '%BYWARD%'",'outFields':'namese2016,ONS_ID','outSR':4326})
    assert len(boundary['features'])==1
    snapshot={'retrieved':date.today().isoformat(),'neighbourhood_filter':"Neighbourhood = 'Byward Market'",'year_field':'Reported_Year','categories':CATEGORIES,'observations':rows,'provenance':[p1,p2],'verification':{'independent_record_rows':sum(counts.values()),'record_query_pages':pages,'duplicate_year_category_go':duplicates,'all_32_aggregates_match':True},'boundary':boundary['features'][0]}
    (ROOT/'data/market-safety.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'OPS snapshot: 32 aggregates reconcile with {sum(counts.values())} record rows; no record-level data saved.')


if __name__=='__main__':fetch()

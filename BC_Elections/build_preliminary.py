"""Build the 2026 initial-count snapshot; does not fetch or imply a live feed.
Run: python BC_Elections/build_preliminary.py
Refresh both retained source HTML files together before rebuilding.
"""
from pathlib import Path
from collections import Counter, defaultdict
from bs4 import BeautifulSoup
import csv
import hashlib
import html
import json
import re

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'data'
PARTY_URL='https://results.elections.bc.ca/'
CANDIDATE_URL='https://results.elections.bc.ca/Results_11684_GE-2026-10-24_Candidate.html'

def norm(s):
    return re.sub(r'[^a-z0-9]','',s.lower())

def write_js(path,var,obj):
    (ROOT/path).write_text(f'window.{var} = '+json.dumps(obj,separators=(',',':'))+';\n',encoding='utf-8')

def build():
    previous=json.loads((RAW/'results-2024.json').read_text(encoding='utf-8'))
    parties=dict(previous['parties'])
    parties.update({'CWP':{'name':'CWP','color':'#8B6C55'},'CENTRE':{'name':'CentreBC','color':'#7865A1'},'ONE':{'name':'OneBC','color':'#9B5066'}})
    code={v['name']:k for k,v in parties.items()}
    code['BC NDP']='NDP'
    code['Christian Heritage Party of BC']='CHP'
    code['']='UNA'
    names={norm(r['name']):r for r in previous['ridings']}
    party=BeautifulSoup((RAW/'preliminary-2026.html').read_text(encoding='utf-8'),'html.parser')
    candidate=BeautifulSoup((RAW/'preliminary-2026-candidates.html').read_text(encoding='utf-8'),'html.parser')
    assert '2026 Provincial General Election' in party.get_text()
    stamp=re.search(r'As of\s+October 26, 2026 10:34 PST',party.get_text(' ',strip=True)).group()
    assert stamp in candidate.get_text(' ',strip=True)
    assert 'November 6 to 10, 2026' in party.get_text(' ',strip=True)
    totals,leaders={},{}
    for tr in party.find_all('table')[0].find_all('tr')[1:]:
        cells=[c.get_text(' ',strip=True) for c in tr.find_all('td')]
        if len(cells)>=4 and cells[0] in code:
            k=code[cells[0]]
            nums=[x for x in cells[1:] if re.fullmatch(r'[\d,]+',x)]
            assert len(nums)==2,cells
            leaders[k],totals[k]=[int(x.replace(',','')) for x in nums]
    assert len(totals)==12
    summaries={}
    for tr in party.find_all('table')[1].find_all('tr')[1:]:
        cells=[c.get_text(' ',strip=True) for c in tr.find_all('td')]
        assert len(cells)==10,cells
        name=cells[0]
        nums=[int(x.replace(',','')) for x in cells[1:8]]
        assert nums[4]+nums[5]==nums[6],name
        summaries[norm(name)]=(name,nums,cells[8:])
    assert len(summaries)==93 and set(summaries)==set(names)
    by_district=defaultdict(list)
    for tr in candidate.find_all('table')[1].find_all('tr')[1:]:
        if not tr.find('td',attrs={'data-canname':True}):continue
        cells=[html.unescape(c.get_text(' ',strip=True)) for c in tr.find_all('td')]
        assert len(cells)==5,cells
        name=html.unescape(tr['data-ed'])
        by_district[norm(name)].append({'district_id':names[norm(name)]['id'],'district':name,
             'candidate':html.unescape(tr.find('td',attrs={'data-canname':True})['data-canname']),
             'party':code[cells[2]],'votes':int(cells[3].replace(',',''))})
    assert set(by_district)==set(summaries)
    ridings=[];aggregate=Counter();seat_counts=Counter();majority=Counter();candidates=[]
    for key,(name,a,boxes) in summaries.items():
        cs=by_district[key];votes=dict.fromkeys(parties,0)
        for c in cs:votes[c['party']]+=c['votes']
        assert [votes['GP'],votes['NDP'],votes['CP'],sum(v for k,v in votes.items() if k not in ('GP','NDP','CP'))]==a[:4],name
        assert sum(votes.values())==a[4]
        top=max(cs,key=lambda c:c['votes'])
        assert len([c for c in cs if c['votes']==top['votes']])==1,name
        for c in cs:c['leading']=c is top
        seat_counts[top['party']]+=1
        if top['votes']*2>a[4]:majority[top['party']]+=1
        aggregate.update(votes);candidates.extend(cs)
        ridings.append({'id':names[key]['id'],'name':name,'votes':votes,'candidates':cs,'valid':a[4],
                       'rejected':a[5],'ballots':a[6],'registered':None,'boxes_reported':boxes})
    assert dict(aggregate)==totals,(aggregate,totals)
    assert all(seat_counts[k]==v for k,v in leaders.items())
    assert sum(r['ballots'] for r in ridings)==1799550
    assert sum(aggregate.values())+sum(r['rejected'] for r in ridings)==1799550
    meta={'title':'British Columbia — 2026 preliminary initial count','source':'Elections BC — 2026 preliminary initial count',
          'year':2026,'preliminary':True,'retrieved':'2026-11-01','source_as_of':stamp,'final_count':'November 6–10, 2026',
          'sources':{'party':PARTY_URL,'candidate':CANDIDATE_URL},'snapshot':True}
    data={'meta':meta,'parties':parties,'ridings':sorted(ridings,key=lambda r:r['name'])}
    write_js('data.js','ELECTION_DATA',data)
    (RAW/'results.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    with (RAW/'candidates.csv').open('w',encoding='utf-8',newline='') as f:
        export_rows=[{'election_year':2026,'count_status':'preliminary','source_as_of':stamp,**c} for c in candidates]
        w=csv.DictWriter(f,fieldnames=list(export_rows[0]));w.writeheader();w.writerows(export_rows)
    # Provincial denominator is published as of Oct 14; no riding denominators are inferred.
    history_js=(ROOT/'turnout-2024.js').read_text(encoding='utf-8')
    history=json.loads(history_js.split(' = ',1)[1].rstrip(';\n'))['provinceAll']
    history.append({'year':2026,'turnoutPct':48.14,'turnout':1799550,'registered':3738182,'preliminary':True})
    write_js('turnout.js','TURNOUT_DATA',{'provinceAll':history,'province':history[-3:],'districts':{},'preliminary':True})
    audit={'meta':meta,'candidates':len(candidates),'ridings':len(ridings),'party_votes':aggregate,'seats':seat_counts,
           'majority_seats':majority,'valid_votes':sum(aggregate.values()),'ballots':1799550,'rejected':sum(r['rejected'] for r in ridings),
           'registered':3738182,'registered_as_of':'2026-10-14','turnout_pct':48.14,'riding_registered_voters_available':False,
           'checks':'All candidate sums reconcile with each of 93 party-report riding rows and provincial party totals/leads.',
           'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [RAW/'preliminary-2026.html',RAW/'preliminary-2026-candidates.html']}}
    (RAW/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k not in ('meta','sha256')},indent=2))

if __name__=='__main__':build()

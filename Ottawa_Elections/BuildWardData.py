"""Build page data and CSV exports from reconciled City workbook extracts.

Run ReconcileSources.py first to refresh the extracts. Run this file from any cwd.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
YEARS = [2010, 2014, 2018, 2022, 2026]


def pct(numerator, denominator):
    return round(numerator / denominator * 100, 1) if numerator is not None and denominator else None


def main():
    source = json.loads((ROOT/'reconciliation/source_results.json').read_text(encoding='utf8'))
    races = {(r['year'], r['ward'], r['office']): r for r in source['races']}
    # 2026: the City's official Statement of Votes Cast (FetchOfficial2026.py) when present, else the
    # unofficial election-night feed (FetchResults2026.py). Ward totals only either way, so there is
    # no ward-by-ward mayor split.
    official = ROOT/'reconciliation/results_2026_official.json'
    r26 = json.loads((official if official.exists() else ROOT/'reconciliation/results_2026.json').read_text(encoding='utf8'))
    for r in r26['races']:
        races[(2026, r['ward'], r['office'])] = r
    # Names identify the 2022 map, not a claim about historical boundaries.
    with (ROOT/'reconciliation/legacy_ward_results.csv').open(encoding='utf-8-sig',newline='') as f:
        legacy = list(csv.DictReader(f))
    names = {int(r['ward']):r['name'].strip() for r in legacy if int(r['year']) == 2022}
    city = []
    elected = {}
    citywide = list(source['citywide'])
    m26 = races[(2026, None, 'mayor')]
    citywide.append({'year':2026, 'registered':m26['registered'], 'ballots':m26['ballots'],
                     'valid_votes':m26['valid_votes'], 'candidates':m26['candidates'],
                     'certification':m26['certification']})
    for r in citywide:
        ranking = sorted(r['candidates'].items(), key=lambda v:v[1], reverse=True)
        winner, runner = ranking[:2]
        elected[r['year']] = winner[0]
        city.append({'year':r['year'], 'registered':r['registered'], 'votes':r['ballots'],
                     'validVotes':r['valid_votes'], 'votesMayor':winner[1], 'winnerName':winner[0],
                     'runnerUp':runner[1], 'runnerUpName':runner[0],
                     'turnout':pct(r['ballots'],r['registered']), 'certification':r['certification'],
                     'unallocatedMayorBallots':(races.get((r['year'],99,'mayor')) or {}).get('ballots',0)})

    def council(ward, year):
        r = races.get((year,ward,'councillor'))
        if r is None:
            return None
        if r.get('acclaimed'):
            name = next(iter(r['candidates']))
            return {'name':name, 'share':100.0, 'source_conflict':False, 'acclaimed':True,
                    'participation':None, 'valid_participation':None, 'registered':r['registered'],
                    'ballots':None, 'valid_votes':None, 'winner_votes':None, 'certification':r['certification']}
        winner, count = max(r['candidates'].items(),key=lambda v:v[1])
        conflicts = [i for i in source['source_issues'] if i['year']==year and i['ward']==ward and i['office']=='councillor']
        return {'name':winner, 'share':pct(count,r['valid_votes']), 'source_conflict':bool(conflicts),
                'participation':pct(r['ballots'],r['registered']),
                'valid_participation':pct(r['valid_votes'],r['registered']),
                'registered':r['registered'], 'ballots':r['ballots'], 'valid_votes':r['valid_votes'],
                'winner_votes':count, 'certification':r['certification']}

    def mayor(ward, year):
        r = races.get((year,ward,'mayor'))
        if r is None:
            return None
        name, count = max(r['candidates'].items(),key=lambda v:v[1])
        return {'top_name':name, 'top_share':pct(count,r['valid_votes']),
                'top_is_mayor':name==elected[year], 'registered':r['registered'], 'valid_votes':r['valid_votes'],
                'top_votes':count, 'ballots':r['ballots'], 'coverage':r['coverage'],
                'certification':r['certification']}

    data = {}
    for ward in range(1,25):
        councils = [council(ward,y) for y in YEARS]
        mayors = [mayor(ward,y) for y in YEARS]
        last_c, last_m = councils[-1], mayors[YEARS.index(2022)]
        caveat = ('Ward 24 was created in 2022. There are no pre-2022 results for this ward; '
                  'the previous 60/40 estimates have been removed.') if ward==24 else (
                  'Historical entries describe the original election-year ward number, not the 2022 territory. '
                  'The 2022 map is a locator only for earlier years. No comparison across the 2022 boundary review is shown.')
        data[str(ward)] = {'name':names[ward], 'change_type':'new' if ward==24 else 'historical',
                          'caveat':caveat,
                          'mayor':{'participation':None, 'winner_pct':last_m['top_share'], 'winner_name':last_m['top_name']},
                          'councillor':dict(last_c, winner_pct=last_c['share'], winner_name=last_c['name']),
                          'history':{'years':YEARS,
                              'mayor':[None]*len(YEARS),
                              'councillor':[r['participation'] if r else None for r in councils],
                              'councillor_valid':[r['valid_participation'] if r else None for r in councils],
                              'mayor_race':mayors, 'councillor_race':councils}}
    (ROOT/'ward_data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (ROOT/'mayor_history.json').write_text(json.dumps(city,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    rows=[]
    for y in YEARS:
        for ward in range(1,25 if y>=2022 else 24):
            row={'ward':ward,'name':names[ward],'year':y}
            for office,prefix in [('mayor','Mayor'),('councillor','Council')]:
                r = races.get((y,ward,office))
                if r:
                    name,count=max(r['candidates'].items(),key=lambda v:v[1])
                    row.update({prefix+'_Registered':r['registered'],prefix+'_Votes':r['valid_votes'],
                                prefix+'_Ballots_Cast':r['ballots'],prefix+'_Winner':count,
                                prefix+'_Win_Name':name,prefix+'_Coverage':r['coverage'],
                                prefix+'_Certification':r['certification'],prefix+'_Source':r.get('source_total','City official 2026 Statement of Votes Cast' if r.get('certification')=='official' else 'City unofficial results feed')})
            rows.append(row)
    with (ROOT/'ward_results.csv').open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    with (ROOT/'Ottawa_Summary.csv').open('w',encoding='utf8',newline='') as f:
        writer=csv.writer(f,delimiter='\t')
        writer.writerow(['Year','Registered','BallotsCast','ValidMayorVotes','MayorWinnerVotes','RunnerUpVotes','Certification'])
        for r in city:
            writer.writerow([r['year'],r['registered'],r['votes'],r['validVotes'],r['votesMayor'],r['runnerUp'],r['certification']])
    page=ROOT/'ottawa_ward_elections.html'
    html=page.read_text(encoding='utf8')
    html,n = re.subn(r'const wardData = .*?;\n',lambda _: 'const wardData = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',html,count=1)
    assert n==1
    html,n=re.subn(r'const MAYOR_HISTORY = \[.*?\n\];',lambda _: 'const MAYOR_HISTORY = '+json.dumps(city,ensure_ascii=False,indent=2)+';',html,count=1,flags=re.S)
    assert n==1
    page.write_text(html,encoding='utf8')
    print(f'Built 24 ward records, {len(rows)} ward-year CSV rows, {len(city)} citywide mayor records, and embedded page data.')


if __name__=='__main__':
    main()

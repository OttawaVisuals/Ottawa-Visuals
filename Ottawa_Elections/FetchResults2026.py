"""Fetch the City of Ottawa's 2026 unofficial results feed and normalize mayor + councillor totals.

Source: https://app06.ottawa.ca/election/2026_en.html loads electionevent.xml (candidates, wards,
electors) and results.xml (votes). The feed has citywide and ward totals only (no poll-level or
ward-by-ward mayor split). Writes reconciliation/results_2026.json. Run from any cwd.
"""
import hashlib
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = 'https://app06.ottawa.ca/election/2026/'
PAGE = 'https://app06.ottawa.ca/election/2026_en.html'


def get(name):
    req = urllib.request.Request(BASE + name, headers={'User-Agent': 'Mozilla/5.0 (OttawaVisuals)'})
    return urllib.request.urlopen(req, timeout=60).read()


def main():
    ev_raw, res_raw = get('electionevent.xml'), get('results.xml')
    ev, res = ET.fromstring(ev_raw), ET.fromstring(res_raw)
    wards = {a.get('id'): a for a in ev.iter('area') if a.get('atid') == '2'}
    contests = {c.get('id'): c for c in ev.iter('contest')}
    votes = {c.get('id'): int(c.get('vot')) for c in res.iter('choice')}
    stats = {c.get('id'): c for c in res.iter('contest')}
    cands = {}
    for c in ev.iter('choice'):
        cands.setdefault(c.get('conid'), []).append(c.get('nm'))
    by_name = {c.get('id'): c.get('nm') for c in ev.iter('choice')}
    by_contest = {}
    for c in ev.iter('choice'):
        by_contest.setdefault(c.get('conid'), []).append(c)

    def race(cid, office, ward):
        con, st = contests[cid], stats[cid]
        acclaimed = con.get('acc') == '1'
        rows = {c.get('nm'): votes.get(c.get('id'), 0) for c in by_contest.get(cid, [])}
        return {'year': 2026, 'ward': ward, 'office': office, 'registered': int(con.get('el')),
                'ballots': None if acclaimed else int(st.get('bal')),
                'valid_votes': None if acclaimed else int(st.get('sum')),
                'acclaimed': acclaimed, 'candidates': rows,
                'coverage': 'ward_totals', 'certification': 'unofficial'}

    races = [race('1', 'mayor', None)]
    for cid, con in contests.items():
        if con.get('oid') == '2':
            races.append(race(cid, 'councillor', int(wards[con.get('aid')].get('ab'))))
    out = {'source': PAGE, 'feed_timestamp': res.get('ts'), 'final_flag': res.get('fin'),
           'tabulators': f"{res.get('cltab')}/{res.get('tab')}", 'registered': int(ev.get('el')),
           'sha256': {'electionevent.xml': hashlib.sha256(ev_raw).hexdigest(),
                      'results.xml': hashlib.sha256(res_raw).hexdigest()},
           'note': 'Unofficial City results. Mayor total is citywide; the feed has no ward-level mayor split.',
           'races': races}
    mayor = races[0]
    assert mayor['ballots'] == int(res.get('bal'))
    assert len([r for r in races if r['office'] == 'councillor']) == 24
    (ROOT / 'reconciliation/results_2026.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(f"{res.get('ts')} fin={res.get('fin')} tabulators {out['tabulators']}; "
          f"mayor ballots {mayor['ballots']}; {len(races) - 1} council races")


if __name__ == '__main__':
    main()

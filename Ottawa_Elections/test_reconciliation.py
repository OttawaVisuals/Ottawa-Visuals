"""Regression checks for independent controls and distinctions lost in the old page."""
import csv
import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent


class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((ROOT/'reconciliation/source_results.json').read_text(encoding='utf8'))
        cls.wards=json.loads((ROOT/'ward_data.json').read_text(encoding='utf8'))
        cls.city=json.loads((ROOT/'mayor_history.json').read_text(encoding='utf8'))
        cls.races={(r['year'],r['ward'],r['office']):r for r in cls.source['races']}
        r26=json.loads((ROOT/'reconciliation/results_2026.json').read_text(encoding='utf8'))
        cls.races.update({(r['year'],r['ward'],r['office']):r for r in r26['races'] if r['office']=='councillor'})

    def test_independent_city_controls(self):
        # Independent published summary controls, not re-summed page outputs.
        expected={2010:(607357,None,269640,131323,64862),
                  2014:(632385,252464,248369,189253,46341),
                  2018:(633946,269772,266024,188960,59156),
                  2022:(722227,316254,314754,161677,119235),
                  2026:(868248,314393,312125,139354,105819)}
        for r in self.city:
            self.assertEqual(tuple(r[k] for k in ('registered','votes','validVotes','votesMayor','runnerUp')),expected[r['year']])

    def test_2026_unofficial_feed_matches_city_page(self):
        # Ward controls read from the City's results page (app06.ottawa.ca/election/2026_en.html).
        w=self.wards
        self.assertEqual(w['1']['history']['councillor_race'][4]['name'],'Matt Luloff')
        self.assertEqual(w['1']['history']['councillor_race'][4]['ballots'],17557)
        self.assertEqual(w['1']['history']['councillor'][4],39.8)
        for ward in ('16','21'):
            self.assertTrue(w[ward]['history']['councillor_race'][4]['acclaimed'])
        self.assertTrue(all(v['history']['mayor_race'][4] is None for v in w.values()))
        self.assertEqual(sum(1 for v in w.values() if v['history']['councillor_race'][4].get('acclaimed')),2)

    def test_special_votes_are_preserved_without_home_ward_assignment(self):
        for year,ballots,valid in [(2014,7633,7556),(2018,15857,15653),(2022,27560,27376)]:
            special=self.races[(year,99,'mayor')]
            self.assertEqual((special['ballots'],special['valid_votes']),(ballots,valid))
            city=next(c for c in self.source['citywide'] if c['year']==year)
            mayor=[r for r in self.source['races'] if r['year']==year and r['office']=='mayor']
            for name,votes in city['candidates'].items():
                self.assertEqual(sum(r['candidates'][name] for r in mayor),votes)
            for r in mayor:
                self.assertEqual(r['coverage'],'unallocated_citywide_polls' if r['ward']==99 else 'ward_coded_polls_only')

    def test_ward_special_poll_voters_reconcile(self):
        # Council ballots - ward-coded mayor ballots = the ward's special-poll voters.
        for year,special in [(2018,15857),(2022,27560)]:
            gaps=[self.races[(year,w,'councillor')]['ballots']-self.races[(year,w,'mayor')]['ballots']
                  for w in range(1,25 if year==2022 else 24)]
            self.assertTrue(all(g>=0 for g in gaps))
            self.assertEqual(sum(gaps),special)
        for ward in self.wards.values():
            for c,m in zip(ward['history']['councillor_race'],ward['history']['mayor_race']):
                if c and m:
                    self.assertEqual(c['registered'],m['registered'])

    def test_denominator_and_registered_typo(self):
        r=self.races[(2022,1,'councillor')]
        self.assertEqual((r['registered'],r['ballots'],r['valid_votes'],r['candidates']['Matthew Luloff']),
                         (38618,16426,16069,11918))
        self.assertEqual(self.wards['1']['history']['councillor_race'][3]['share'],74.2)
        self.assertEqual(self.wards['1']['history']['councillor'][3],42.5)
        self.assertEqual(self.wards['1']['history']['councillor_valid'][3],41.6)
        for office in ('mayor','councillor'):
            self.assertEqual(self.races[(2014,4,office)]['registered'],22578)

    def test_missing_and_conflicting_data_are_not_invented(self):
        for ward in ('7','15'):
            self.assertIsNone(self.wards[ward]['history']['councillor_race'][0])
        for ward in self.wards.values():
            self.assertEqual(ward['history']['councillor'][:2],[None,None])
        for key in ('mayor_race','councillor_race','councillor','councillor_valid'):
            self.assertEqual(self.wards['24']['history'][key][:3],[None]*3)
        self.assertTrue(self.wards['6']['history']['councillor_race'][0]['source_conflict'])
        issue=self.source['source_issues']
        self.assertEqual(len(issue),1)
        self.assertEqual((issue[0]['detail_sum'],issue[0]['published_total']),(6571,7185))

    def test_ballots_and_valid_votes_stay_distinct_for_every_race(self):
        self.assertEqual(len(self.source['races']),187)
        self.assertEqual(len(self.wards),24)
        for r in self.source['races']:
            self.assertEqual(sum(r['candidates'].values()),r['valid_votes'])
            if r['year'] in (2018,2022):
                self.assertEqual(r['ballots'],r['valid_votes']+r['undervotes']+r['overvotes'])
            if r['year']==2010:
                self.assertIsNone(r['ballots'])
                self.assertEqual(r['certification'],'not_certified')

    def test_audit_coverage_and_generated_page(self):
        with (ROOT/'reconciliation/field_comparison.csv').open(encoding='utf8',newline='') as f:
            audit=list(csv.DictReader(f))
        self.assertEqual(Counter(r['comparison'] for r in audit),
                         Counter(match=640,ballots_used_as_valid_votes=94,different=2))
        with (ROOT/'ward_results.csv').open(encoding='utf8',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),117)
        for row in rows:
            y,w=int(row['year']),int(row['ward'])
            for office,prefix in [('mayor','Mayor'),('councillor','Council')]:
                r=self.races.get((y,w,office))
                if r is None:
                    self.assertEqual(row[prefix+'_Votes'],'')
                else:
                    self.assertEqual(row[prefix+'_Votes'],'' if r['valid_votes'] is None else str(r['valid_votes']))
                    self.assertEqual(row[prefix+'_Ballots_Cast'],'' if r['ballots'] is None else str(r['ballots']))
        html=(ROOT/'ottawa_ward_elections.html').read_text(encoding='utf8')
        self.assertEqual(json.loads(re.search(r'const wardData = (.*?);\n',html)[1]),self.wards)
        self.assertEqual(json.loads(re.search(r'const MAYOR_HISTORY = (\[.*?\n\]);',html,re.S)[1]),self.city)
        self.assertNotIn('"pop":',html)
        self.assertNotIn('"under18":',html)
        self.assertNotIn('<option value="mayor">',html)
        topo=json.loads((ROOT/'Ottawa_Election_Wards_Only.json').read_text(encoding='utf8'))
        geometries=topo['objects']['Ottawa_Election_Map_2022']['geometries']
        self.assertEqual({int(g['properties']['Ward']) for g in geometries},set(range(1,25)))


if __name__=='__main__':
    unittest.main()

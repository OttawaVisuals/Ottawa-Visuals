"""Regression checks of source values, aggregation, joins and distance units."""
import csv, io, json, math, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'data/spending.json').read_text(encoding='utf-8'))

class SpendingChecks(unittest.TestCase):
    def test_federal_exports_match_original_csv(self):
        for p in DATA['periods']:
            if p['level']!='federal':continue
            raw=list(csv.DictReader(io.StringIO((ROOT/'data/sources'/f"{p['id']}.csv").read_text(encoding='utf-8-sig'))))
            self.assertEqual(len(raw),len(p['rows']))
            for source,row in zip(raw,p['rows']):
                for key in ['Salaries','Travel','Hospitality','Contracts']:
                    self.assertEqual(float(source[key]),row['categories'][key.lower()])
                self.assertAlmostEqual(sum(row['categories'].values()),row['total'],places=2)

    def test_ontario_source_transcriptions_and_no_double_count(self):
        p=DATA['periods'][-1];by_name={r['name']:r for r in p['rows']}
        # Independently read from PDF pages 2, 5, 10, 13.
        examples={'ALLSOPP, TYLER':(194610,13107,385846),
                  'BLAIS, STEPHEN':(301777,0,513455),
                  'MAMAKWA, SOL':(340783,5738,602070),
                  'MCKENNEY, CATHERINE':(331569,0,514262),
                  'MACLEOD, LISA':(920,0,14282)}
        for name,(staff,overage,total) in examples.items():
            r=by_name[name]
            self.assertEqual(r['categories']['salaries'],staff)
            self.assertEqual(r['toronto_overage'],overage)
            self.assertEqual(r['total'],total)
            self.assertEqual(r['categories']['accommodation'],r['toronto_base']+overage)
        self.assertEqual(len(p['rows']),142)
        self.assertTrue(all(r['riding'] and r['distance_km'] is not None for r in p['rows']))
        for r in p['rows']:
            self.assertLessEqual(abs(sum(r['categories'].values())-r['total']),4)
            self.assertEqual(r['total'],r['office_total']+r['travel_accommodation_total'])

    def test_ontario_column_reconciliation(self):
        r=json.loads((ROOT/'data/ontario-reconciliation.json').read_text())
        self.assertEqual(r['published_office_total'],53656360)
        self.assertEqual(r['published_travel_accommodation_total'],3651861)
        self.assertLessEqual(max(abs(c['rounding_difference']) for c in r['columns']),8)

    def test_distances_independent_spherical_check(self):
        for p in DATA['periods']:
            lat2,lon2=(45.4218,-75.7009) if p['level']=='federal' else (43.6624,-79.3917)
            for r in p['rows']:
                if r['distance_km'] is None:continue
                a,b,c,d=map(math.radians,[r['latitude'],r['longitude'],lat2,lon2])
                h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
                spherical=6371.0088*2*math.asin(math.sqrt(h))
                self.assertLess(abs(spherical-r['distance_km']),max(.2,spherical*.006))
                self.assertGreaterEqual(r['distance_km'],0)
                self.assertLessEqual(r['distance_km'],6000)

    def test_transition_quarter_is_not_given_new_boundaries(self):
        p=next(p for p in DATA['periods'] if p['id']=='federal-2026-q1')
        self.assertTrue(all(r['distance_km'] is None for r in p['rows']))

    def test_ids_and_export_completeness(self):
        ids=[r['id'] for p in DATA['periods'] for r in p['rows']]
        self.assertEqual(len(ids),len(set(ids)))
        exported=list(csv.DictReader(io.StringIO((ROOT/'data/spending.csv').read_text(encoding='utf-8-sig'))))
        self.assertEqual(len(exported),sum(len(p['rows'])*len(p['categories']) for p in DATA['periods']))

if __name__=='__main__':unittest.main()

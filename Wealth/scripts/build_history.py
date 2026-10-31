"""Pull SFS national net-worth rows and package checked historical transcriptions.

Standard library only. No digitized chart estimates: PBO figures have numeric
text descriptions, and the older studies have published numeric tables.
"""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data'
URL = 'https://www150.statcan.gc.ca/n1/en/tbl/csv/11100049-eng.zip'
GROUPS = ['Lowest net worth quintile', 'Second net worth quintile', 'Middle net worth quintile',
          'Fourth net worth quintile', 'Highest net worth quintile']
LABELS = ['Lowest 20%', 'Second 20%', 'Middle 20%', 'Fourth 20%', 'Wealthiest 20%']


def main():
    raw = urllib.request.urlopen(URL, timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(raw))
    rows = list(csv.DictReader(io.StringIO(z.read('11100049.csv').decode('utf-8-sig'))))
    selected = [r for r in rows if r['GEO'] == 'Canada'
                and r['Assets and debts'] == 'Net worth (total assets less total debt)']
    lookup = {(r['REF_DATE'], r['Net worth quintiles'], r['Statistics'], r['Confidence intervals']): r
              for r in selected}

    def get(year, group, stat, confidence='Estimate'):
        row = lookup[(year, group, stat, confidence)]
        if row['VALUE'] == '':
            return None
        assert row['STATUS'] in ('', 'E'), row
        if stat == 'Total values':
            assert row['SCALAR_FACTOR'] == 'millions'
        return float(row['VALUE'])

    survey = []
    for year in sorted(set(r['REF_DATE'] for r in selected)):
        total = get(year, 'Total, all net worth quintiles', 'Total values')
        groups = []
        for group, label in zip(GROUPS, LABELS):
            amount = get(year, group, 'Total values')
            groups.append(dict(label=label, share=100 * amount / total, total_millions=amount,
                               median_2023_dollars=get(year, group, 'Median value for those holding asset or debt'),
                               average_2023_dollars=get(year, group, 'Average value for those holding asset or debt')))
        assert abs(sum(g['total_millions'] for g in groups) - total) <= 5
        survey.append(dict(year=int(year), groups=groups, top20=groups[4]['share'],
                           middle40=sum(g['share'] for g in groups[2:4]),
                           bottom40=sum(g['share'] for g in groups[:2])))
    assert [d['year'] for d in survey] == [1999, 2005, 2012, 2016, 2019, 2023]
    assert round(survey[-1]['top20'], 1) == 63.5
    with (OUT / 'sfs-source-rows.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(selected)
    with (OUT / 'survey.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['year', 'wealth_group', 'share_percent', 'net_worth_millions_2023_cad', 'median_net_worth_2023_cad', 'mean_net_worth_2023_cad'])
        for d in survey:
            for g in d['groups']:
                writer.writerow([d['year'], g['label'], g['share'], g['total_millions'], g['median_2023_dollars'], g['average_2023_dollars']])
    history = json.loads((OUT / 'historical-transcription.json').read_text(encoding='utf-8'))
    # Dimensional checks preserve missing values rather than manufacturing points.
    for key in ['pbo_history_2021', 'pbo_history_2025']:
        d = history[key]
        for variant in set(d) - {'years', 'groups'}:
            assert len(d[variant]) == len(d['groups'])
            assert all(len(v) == len(d['years']) for v in d[variant])
            assert all(v is None or 0 <= v <= 100 for a in d[variant] for v in a)
    for snapshot in history['snapshots']:
        assert all(len(snapshot[k]) == 9 for k in ['shares', 'threshold_millions', 'families_thousands', 'wealth_billions'])
        assert abs(sum(snapshot['shares'][6:]) - 100) <= .11
        assert snapshot['shares'][:7] == sorted(snapshot['shares'][:7])
    for study in history['historical_studies']:
        assert len(study['years']) == len(study['decile_shares']) == len(study['gini'])
        assert all(len(a) == 10 and abs(sum(a) - 100) <= .21 for a in study['decile_shares'])
    history.update(survey=survey, sfs_source_url=URL,
                   sfs_sha256=hashlib.sha256(raw).hexdigest(),
                   retrieved_utc=datetime.now(timezone.utc).isoformat())
    normalized = []
    for edition in ['2021', '2025']:
        d = history['pbo_history_' + edition]
        for variant in set(d) - {'years', 'groups'}:
            for i, group in enumerate(d['groups']):
                for year, value in zip(d['years'], d[variant][i]):
                    locator = 'Table 3-1, p.10' if edition == '2021' else ('Figure 1, p.11' if group == 'Top 1%' else 'Figure 2, p.12')
                    normalized.append([f'pbo{edition}', locator, year, group, variant, 'share_percent', value, 'estimate'])
    for s in history['snapshots']:
        for i, group in enumerate(history['percentile_groups']):
            for metric in ['shares', 'threshold_millions', 'families_thousands', 'wealth_billions']:
                normalized.append([s['source'], s['locator'], s['year'], group, 'HFD', metric, s[metric][i], s['kind']])
    for year in ['2019', '2023']:
        d = history['thresholds'][year]
        for i, group in enumerate(history['thresholds']['labels']):
            for metric in ['shares', 'families_thousands', 'wealth_billions']:
                normalized.append([d['source'], d['locator'], year, group, 'HFD threshold', metric, d[metric][i], 'estimate'])
    for study in history['historical_studies']:
        for i, year in enumerate(study['years']):
            for j, value in enumerate(study['decile_shares'][i]):
                normalized.append([study['id'], 'Table 1', year, f'Decile {j+1}', 'all family units', 'share_percent', value, 'estimate'])
                if 'decile_medians_2005_dollars' in study:
                    normalized.append([study['id'], 'Table 1', year, f'Decile {j+1}', 'all family units', 'median_2005_dollars', study['decile_medians_2005_dollars'][i][j], 'estimate'])
            normalized.append([study['id'], 'Gini', year, 'All units', 'all family units', 'gini', study['gini'][i], 'estimate'])
    units = {'share_percent':'percent', 'shares':'percent',
             'threshold_millions':'millions of nominal CAD (cutoff/range)',
             'families_thousands':'thousands of families',
             'wealth_billions':'billions of nominal CAD',
             'median_2005_dollars':'2005 constant CAD', 'gini':'coefficient (0–1)'}
    with (OUT / 'historical.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['source_id', 'locator', 'year', 'wealth_group', 'variant', 'metric', 'value', 'unit', 'kind'])
        writer.writerows([r[:7] + [units[r[5]], r[7]] for r in normalized])
    (OUT / 'history.json').write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
    (OUT / 'history-data.js').write_text('window.WEALTH_HISTORY = ' + json.dumps(history) + ';\n', encoding='utf-8')
    print(f'Validated {len(survey)} survey years, {len(selected)} SFS rows; {len(normalized)} historical records (including explicit missing values).')


if __name__ == '__main__':
    main()

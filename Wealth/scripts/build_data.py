"""Rebuild the Canada wealth snapshot from StatCan 36-10-0660-01.

Retains all available periods; Q4 annual views use the same season. No interpolation.
Retains the exact source rows, vectors, status flags and source archive hash.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www150.statcan.gc.ca/n1/en/tbl/csv/36100660-eng.zip'
GROUPS = ['Lowest wealth quintile', 'Second wealth quintile', 'Third wealth quintile',
          'Fourth wealth quintile', 'Highest wealth quintile']
LABELS = ['Lowest 20%', 'Second 20%', 'Middle 20%', 'Fourth 20%', 'Wealthiest 20%']


def main():
    raw = urllib.request.urlopen(URL, timeout=90).read()
    archive = zipfile.ZipFile(io.BytesIO(raw))
    rows = list(csv.DictReader(io.StringIO(archive.read('36100660.csv').decode('utf-8-sig'))))
    selected = [r for r in rows if r['GEO'] == 'Canada'
                and r['Characteristics'] in GROUPS + ['All households']
                and r['Wealth'] == 'Net worth (wealth)'
                and r['VALUE'] != '']
    lookup = {(r['REF_DATE'], r['Characteristics'], r['Statistics']): r for r in selected}

    def value(period, group, stat):
        row = lookup[(period, group, stat)]
        assert row['STATUS'] in ('', 'r', 'p'), row
        assert row['SCALAR_FACTOR'] == ('millions' if stat == 'Value' else 'units')
        return float(row['VALUE'])

    observations = []
    for period in sorted(set(r['REF_DATE'] for r in selected)):
        total = value(period, 'All households', 'Value')
        groups = []
        for group, label in zip(GROUPS, LABELS):
            amount = value(period, group, 'Value')
            share = value(period, group, 'Distribution of value')
            # Published shares are rounded independently; retain them as published.
            assert abs(100 * amount / total - share) <= .051
            groups.append(dict(label=label, share=share, total_millions=amount,
                               average_dollars=value(period, group, 'Value per household')))
        assert abs(sum(g['total_millions'] for g in groups) - total) <= 5
        assert abs(sum(g['share'] for g in groups) - 100) <= .21
        # Combine unrounded totals first, then round, avoiding compounded rounding.
        bottom = round(100 * sum(g['total_millions'] for g in groups[:2]) / total, 1)
        middle = round(100 * sum(g['total_millions'] for g in groups[2:4]) / total, 1)
        quarter = (int(period[5:7]) - 1) // 3 + 1
        observations.append(dict(year=int(period[:4]), quarter=quarter,
                          time=int(period[:4]) + (quarter - 1) / 4,
                          label=f'{period[:4]} Q{quarter}', period=period, groups=groups,
                          top20=groups[-1]['share'], middle40=middle, bottom40=bottom,
                          gap=round(groups[-1]['share'] - bottom, 1)))
    years = [d for d in observations if d['quarter'] == 4]
    assert len(years) == years[-1]['year'] - years[0]['year'] + 1
    if years[-1]['year'] == 2025:
        assert (years[-1]['top20'], years[-1]['bottom40'], years[-1]['gap']) == (65.7, 3.0, 62.7)
        assert [g['average_dollars'] for g in years[-1]['groups']] == [-4608, 167907, 526185, 1160145, 3543579]
    data = dict(table='36-10-0660-01', source_url=URL,
                retrieved_utc=datetime.now(timezone.utc).isoformat(),
                source_sha256=hashlib.sha256(raw).hexdigest(), years=years,
                observations=observations)
    out = ROOT / 'data'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'wealth.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    # Bundled fallback also supports opening wealth.html directly from disk.
    (out / 'wealth-data.js').write_text('window.WEALTH_DATA = ' + json.dumps(data) + ';\n', encoding='utf-8')
    with (out / 'statcan-source-rows.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(selected)
    with (out / 'wealth.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['year', 'period', 'wealth_group', 'share_percent', 'average_net_worth_nominal_cad', 'total_net_worth_millions_cad'])
        for y in observations:
            for g in y['groups']:
                writer.writerow([y['year'], f"Q{y['quarter']}", g['label'], g['share'], int(g['average_dollars']), int(g['total_millions'])])
    print(f"Validated {len(observations)} observations ({len(years)} Q4), {years[0]['year']}–{years[-1]['year']}; {len(selected)} source rows.")
    print('Latest:', {k: years[-1][k] for k in ['top20', 'bottom40', 'gap']})


if __name__ == '__main__':
    main()

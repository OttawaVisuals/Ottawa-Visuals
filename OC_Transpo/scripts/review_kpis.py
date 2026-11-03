"""Reproduce the Nov 2026 targeted source review; no collector files are edited.

Needs openpyxl and pypdf, plus the scraper's local PDF archive. Downloads four
staff presentations to ignored data/kpi_review/ unless --source-dir is supplied.
Writes source_review.json and recent_publications.csv alongside the history.
"""
import argparse
import csv
import hashlib
import json
import re
import tempfile
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
from pypdf import PdfReader
import extract_kpis

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'kpi_history'
SOURCES = [
    ('2026-02-12-update', 'https://glengower.ca/wp-content/uploads/2026/02/5.1-OC-Transpo-Update-Feb-12-2026-TC_EN.pdf',
     '9a2bd92303543b66a71f1680f821ec814bfe0e5a9258b685b27656e8daa545b8', 28, '2026-01', 87.8),
    ('2026-03-12-update', 'https://glengower.ca/wp-content/uploads/2026/03/4.1-OC-Transpo-Update-March-12-2026-TC_EN.pdf',
     'a16ff34583e2c5328c09870e6a86dcbecab5889a6038b3f58b6bdb0e05c1d0b9', 31, '2026-02', 67.2),
    ('2026-04-09-update', 'https://glengower.ca/wp-content/uploads/2026/04/6.1-OC-Transpo-Update-EN.pdf',
     '10997904c01a6901dd62f489f886a374e4cc5da4445c0b4836addc8239b00644', 42, '2026-03', 61.8),
    ('2026-10-14-kpis', 'https://glengower.ca/wp-content/uploads/2026/10/Transit-KPIs-October-2026.pdf',
     '8896a4e0dc1070be53d4e49c7a7b4e2c79fc7c1015fbfa2940efd587c63c54c5', None, None, None),
]
KEY = ['metric', 'mode', 'breakdown', 'period', 'period_type']
DECISIONS = {
    ('bus_operator_availability', 'bus'): 'Unresolved source disagreement: latest scorecard retained (85%); reliability narrative says 88%.',
    ('info_open_data_api_calls', 'info'): 'Later table retained; reason for the changed value is not stated.',
    ('info_website_pageviews', 'info'): 'Later table retained; reason for the changed value is not stated.',
    ('service_availability', 'line1'): 'Unresolved table/chart disagreement. Later rounded 95% agrees with 95.2% under the existing rounding rule; 95.6% remains an alternative.',
    ('service_availability', 'system'): 'Unresolved disagreement within one report; table retained ahead of chart by the existing method priority.',
    ('survey_review_meetings', 'org'): 'Explicit correction: the 2025 scorecard footnote says 132 was erroneous and the correct number is 32.',
}


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data/kpi_review')
    parser.add_argument('--check-current', action='store_true', help='Download and hash the current Open Ottawa workbook (does not alter retained snapshots)')
    args = parser.parse_args()
    args.source_dir.mkdir(parents=True, exist_ok=True)
    obs = read_csv(HISTORY / 'kpi_observations.csv')
    series = read_csv(HISTORY / 'kpi_series.csv')
    keys = [tuple(r[k] for k in KEY) for r in series]
    require(len(keys) == len(set(keys)), 'Duplicate series keys')
    # Percentage changes can be negative; shares cannot.
    require(all(0 <= float(r['value']) <= 100 for r in series if r['unit'] == '%' and r['metric'] != 'ridership_change_vs_prior_year'), 'Service percentage outside 0–100')
    require(all(float(r['value']) >= 0 for r in series if r['metric'] != 'ridership_change_vs_prior_year'), 'Negative level observation')
    with tempfile.TemporaryDirectory() as tmp:
        extract_kpis.OUT = Path(tmp)
        extract_kpis.main()
        for name in ['kpi_observations.csv', 'kpi_series.csv', 'extract_log.txt']:
            require((Path(tmp) / name).read_bytes() == (HISTORY / name).read_bytes(), f'Non-reproducible {name}')

    # Independent cell-level comparison: fixed sheet/column positions verified
    # against workbook headers, not the extractor's column mapping or parser.
    mappings = [
        ('01_otp_conventional', 3, 'regularity', 'regularity_frequent_routes', 'bus', '%', 1),
        ('01_otp_conventional', 4, 'punctuality', 'punctuality_less_frequent_routes', 'bus', '%', 1),
        ('02_otp_para_transpo', 2, 'overall', 'para_on_time', 'para', '%', 1),
        ('03_ridership', 2, 'ridership', 'ridership', 'system', 'linked trips', 1000000),
        ('04_ridership_paratranspo', 2, 'paratranspo-ridership', 'para_trips', 'para', 'trips', 1000),
        ('05_otrain_service_delivery', 3, 'o-train-line-1', 'trips_delivered', 'line1', '%', 1),
        ('05_otrain_service_delivery', 4, 'o-train-line-2-4', 'trips_delivered', 'line2_4', '%', 1),
        ('06_bus_service_delivery', 3, 'bus_service_delivery', 'trips_delivered', 'bus', '%', 1),
    ]
    checked = 0
    snapshot_evidence = []
    for path in sorted((ROOT / 'rt_data/kpi_snapshots').glob('service_ridership_kpis_*.xlsx')):
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        source = path.relative_to(ROOT).as_posix()
        actual = [r for r in obs if r['source_file'] == source]
        expected = []
        for sheet, col, header, metric, mode, unit, scale in mappings:
            ws = wb[sheet]
            require(ws.cell(1, col).value == header, f'Changed header {sheet}/{col}')
            for cells in list(ws.rows)[1:]:
                if cells[0].value is None:
                    continue
                period = datetime.strptime(cells[0].value, '%b %y').strftime('%Y-%m')
                expected.append((metric, mode, period, unit, round(float(cells[col-1].value) * scale, 6)))
        got = [(r['metric'], r['mode'], r['period'], r['unit'], round(float(r['value']), 6)) for r in actual]
        require(sorted(expected) == sorted(got), f'Workbook/CSV mismatch: {path.name}')
        checked += len(expected)
        snapshot_evidence.append({'path': source, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'cells_checked': len(expected)})
        wb.close()

    if args.check_current:
        url = 'https://www.arcgis.com/sharing/rest/content/items/31d7a151c8394d1a8656ea3d08f00f46/data'
        with urllib.request.urlopen(url, timeout=60) as response:
            body = response.read()
        require(body.startswith(b'PK'), 'Current source response is not an XLSX ZIP')
        digest = hashlib.sha256(body).hexdigest()
        check = dict(checked_utc=datetime.now(timezone.utc).isoformat(), source_url=url, download_sha256=digest,
                     matches_retained=[s['path'] for s in snapshot_evidence if s['sha256'] == digest])
        (HISTORY / 'workbook_source_check.json').write_text(json.dumps(check, indent=2) + '\n', encoding='utf-8')

    manifest = read_csv(ROOT / 'data/manifest.csv')
    urls = {Path(r['local_path'].replace('\\', '/')).as_posix().removeprefix('data/'): r['download_url'] for r in manifest}
    grouped = defaultdict(list)
    for r in obs:
        grouped[tuple(r[k] for k in KEY)].append(r)
    conflicts = []
    readers = {}
    for row in series:
        if not row['other_values']:
            continue
        evidence = []
        for r in grouped[tuple(row[k] for k in KEY)]:
            source = r['source_file']
            path = ROOT / 'data' / source
            if source not in readers:
                readers[source] = PdfReader(path)
            text = readers[source].pages[int(r['page']) - 1].extract_text()
            # Verify the recorded number exists on its claimed source page.
            # Column/metric placement was separately reviewed (KPI_REVIEW.md).
            val = float(r['value'])
            tokens = [f'{val:g}', f'{val:,.0f}']
            require(any(t in text.replace('\u00a0', ' ') for t in tokens), f'Missing source value: {r}')
            if row['metric'] == 'survey_review_meetings' and r['meeting_date'] == '2025-04-10':
                require('erroneously' in text and 'correct number is 32' in text, 'Correction footnote changed')
            evidence.append({'value': val, 'date': r['meeting_date'], 'file': source, 'page': int(r['page']),
                             'url': urls[source], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        conflicts.append({k: row[k] for k in KEY} | {'value': float(row['value']), 'alternatives': row['other_values'],
                         'decision': DECISIONS[(row['metric'], row['mode'])], 'sources': evidence})

    pdfs, sources, line1 = {}, [], []
    for name, url, sha, page, period, value in SOURCES:
        path = args.source_dir / (name + '.pdf')
        if not path.exists():
            request = urllib.request.Request(url, headers={'User-Agent': 'OttawaVisuals source review'})
            with urllib.request.urlopen(request, timeout=60) as response:
                path.write_bytes(response.read())
        require(hashlib.sha256(path.read_bytes()).hexdigest() == sha, f'Source changed: {url}; review before updating hash')
        reader = PdfReader(path)
        pdfs[name] = reader
        sources.append({'id': name, 'url': url, 'sha256': sha})
        if page:
            text = reader.pages[page-1].extract_text()
            require(f'{value}%' in text, f'Missing Line 1 data label {period}')
            r = next(r for r in series if r['metric'] == 'trips_delivered' and r['mode'] == 'line1' and r['period'] == period)
            require(float(r['value']) == value, f'Line 1 CSV disagrees {period}')
            line1.append({'period': period, 'value': value, 'source_id': name, 'page': page})

    # Read only printed labels, never estimate intermediate curve values.
    reader = pdfs['2026-10-14-kpis']
    text = reader.pages[1].extract_text()
    labels = [float(v) for v in re.findall(r'(\d+\.\d+)%', text.split('0.0%')[0])]
    require(len(labels) == 39, 'Expected 13 component pairs and 13 totals')
    not_delivered, late, totals = labels[:13], labels[13:26], labels[26:]
    require(all(abs(a+b-c) <= .100001 for a,b,c in zip(not_delivered,late,totals)), 'Missed-trip labels do not reconcile within rounding')
    recent = []
    url = SOURCES[-1][1]
    def add(metric, mode, period, value, page):
        recent.append(dict(metric=metric, mode=mode, period=period, value=value, unit='%',
                           publication_date='2026-10-14', source_url=url, page=page))
    for i in range(13):
        month = 9 + i
        period = f'{2025 + (month-1)//12}-{(month-1)%12+1:02d}'
        for metric, values in [('bus_missed_trips', totals), ('bus_trips_not_delivered_new', not_delivered), ('bus_trips_over_20min_late', late)]:
            add(metric, 'bus', period, values[i], 2)
    otp = [float(v) for v in re.findall(r'(\d+\.\d+)%', reader.pages[0].extract_text())]
    require(len(otp) == 6, 'Unexpected bus OTP endpoint labels')
    add('bus_on_time_trip_starts', 'bus', '2025-09', otp[4], 1)
    add('bus_on_time_trip_starts', 'bus', '2026-09', otp[5], 1)
    para = re.findall(r'(\d+)%', reader.pages[3].extract_text().split('0%')[0])
    require(len(para) == 2, 'Unexpected Para endpoint labels')
    for period, value in zip(['2025-09', '2026-09'], para):
        add('para_eligible_pickups_on_time', 'para', period, float(value), 4)
    review = dict(review_date='2026-11-03', observations=len(obs), series_points=len(series),
                  snapshot_cells_checked=checked, snapshots=snapshot_evidence, conflicts=conflicts,
                  sources=sources, line1_corroboration=line1,
                  scope='Targeted source review of all snapshot cells, all six differing series keys, and three Line 1 anomalies; deterministic rebuild and integrity checks of the full archive. Not a fresh cell-by-cell audit of all historical PDF observations.')
    (HISTORY / 'source_review.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf-8')
    with (HISTORY / 'recent_publications.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(recent[0]))
        w.writeheader()
        w.writerows(recent)
    print(f'Review passed: {checked} workbook cells; {len(conflicts)} differing keys; 3 Line 1 confirmations; {len(recent)} separate recent observations')


if __name__ == '__main__':
    main()

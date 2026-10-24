"""Fetch Ottawa all-items CPI; retain inputs and hashes for the reviewed snapshot."""
import hashlib
import json
import statistics
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = 'https://www150.statcan.gc.ca/t1/wds/rest/getDataFromCubePidCoordAndLatestNPeriods'
COORD = '15.2.0.0.0.0.0.0.0.0'


def fetch(pid, periods):
    request = urllib.request.Request(API, data=json.dumps([
        {'productId': pid, 'coordinate': COORD, 'latestN': periods}
    ]).encode(), headers={'Content-Type': 'application/json'})
    raw = urllib.request.urlopen(request, timeout=45).read()
    result = json.loads(raw)[0]
    assert result['status'] == 'SUCCESS', result['status']
    return result['object']['vectorDataPoint'], hashlib.sha256(raw).hexdigest()


if __name__ == '__main__':
    annual, annual_hash = fetch(18100005, 20)
    monthly, monthly_hash = fetch(18100004, 36)
    indices = {int(r['refPer'][:4]): r['value'] for r in annual
               if 2012 <= int(r['refPer'][:4]) <= 2025 and r['value'] is not None}
    assert set(indices) == set(range(2012, 2026)), 'Missing annual baseline or observation'
    months = {r['refPer'][:7]: r['value'] for r in monthly
              if r['refPer'][:4] in ['2025', '2026'] and r['value'] is not None}
    assert sorted(k for k in months if k.startswith('2026')) == [f'2026-{m:02}' for m in range(1, 10)], 'Review the fixed September 2026 cutoff before refreshing'
    current = {f'2026-{m:02}': months[f'2026-{m:02}'] for m in range(1, 10)}
    previous = {f'2025-{m:02}': months[f'2025-{m:02}'] for m in range(1, 10)}
    rates = {str(y): round((indices[y] / indices[y - 1] - 1) * 100, 6) for y in range(2013, 2026)}
    rates['2026'] = round((statistics.mean(current.values()) / statistics.mean(previous.values()) - 1) * 100, 6)
    result = {
        'reviewed': '2026-10-24', 'geography': 'Ottawa-Gatineau, Ontario part, Ontario/Quebec',
        'product': 'All-items CPI, not seasonally adjusted', 'index_base': '2002=100',
        'coordinate': COORD, 'annual_indices': indices,
        'monthly_2026_jan_sep': current, 'monthly_2025_jan_sep': previous,
        'inflation_pct': rates, 'provisional_years': [2026],
        'formula': '2013–2025: (annual average CPI / previous annual average CPI - 1) × 100. 2026: (Jan–Sep 2026 average / Jan–Sep 2025 average - 1) × 100.',
        'annual_source': 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000501',
        'monthly_source': 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401',
        'annual_response_sha256': annual_hash, 'monthly_response_sha256': monthly_hash,
        'note': '2026 is a matched-period YTD comparison, not annual inflation or a forecast. CPI measures consumer prices, not municipal input costs. Same-year inflation was not fully known when budgets were adopted.'
    }
    (ROOT / 'data/inflation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(rates, indent=2))

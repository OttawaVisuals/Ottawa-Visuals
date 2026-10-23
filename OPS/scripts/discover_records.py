"""Find OPS directory candidates for manual review; never change curated outcomes.

Usage: python OPS/scripts/discover_records.py
Requires requests and beautifulsoup4. A failed source remains an error, not zero rows.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'LECA': 'https://leca.ca/results-hearings/?wbdisable=true',
    'OPAAC discipline': 'https://www.policearbitration.gov.on.ca/police-discipline-decisions-rights-2/',
    'OPAAC appeals': 'https://www.policearbitration.gov.on.ca/en/',
    'OPS': 'https://www.ottawapolice.ca/en/newsroom/disciplinary-hearings-and-decisions/',
}

def extract(source, url, html):
    soup = BeautifulSoup(html, 'html.parser')
    if source == 'OPS':
        # OPS's main also contains site navigation: keep decision PDF links only.
        main = soup.find('main') or soup
        return {'decision_links': [{'label': a.get_text(' ', strip=True), 'url': urljoin(url, a['href'])}
                for a in main.select('a[href]') if '.pdf' in a['href'].lower() and 'decision' in a.get_text().lower()],
                'schedule_text': next((t.get_text(' ', strip=True) for t in main.select('table') if 'Patterson' in t.get_text() or 'Reesor' in t.get_text()),
                                      'Inspect the live OPS hearing schedule manually; no schedule table identified.')}
    rows = []
    for tr in soup.select('tr'):
        cells = tr.find_all('td', recursive=False)
        if cells and any('Ottawa' in c.get_text() for c in cells):
            rows.append({'cells': [c.get_text(' ', strip=True) for c in cells],
                         'links': [{'label': a.get_text(' ', strip=True), 'url': urljoin(url, a['href'])} for a in tr.select('a[href]')]})
    if not rows:
        raise ValueError('No Ottawa rows identified; inspect for a page-format or access change.')
    return rows

def main():
    audit = {'attempted_at_utc': datetime.now(timezone.utc).isoformat(), 'sources': []}
    for source, url in SOURCES.items():
        result = {'name': source, 'url': url}
        try:
            response = requests.get(url, timeout=35, headers={'User-Agent': 'OttawaVisuals-OPS-source-review/1.0'})
            response.raise_for_status()
            result.update(status='ok', candidates=extract(source, url, response.content))
        except (requests.RequestException, ValueError) as exc:
            result.update(status='error', error=str(exc))
        audit['sources'].append(result)
        print(source + ': ' + result['status'])
    target = ROOT / '.cache' / 'discovery.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Saved discovery candidates to ' + str(target))
    print('Review new records AND later appeals before editing data/records.json. No curated data changed.')
    return int(any(s['status'] == 'error' for s in audit['sources']))

if __name__ == '__main__':
    raise SystemExit(main())

"""Download official sources into ignored raw cache; retain URL/hash manifest."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib, json, re
import requests
import truststore
truststore.inject_into_ssl()
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
RAW.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'OttawaVisuals/1.0 (official public data research)'
def get(url):
    r = SESSION.get(url, timeout=90); r.raise_for_status(); return r
def fetch(item):
    name,url = item
    p = RAW/name
    if not p.exists(): p.write_bytes(get(url).content)
    b=p.read_bytes()
    return dict(file=name,url=url,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

if __name__ == '__main__':
    items=[(f'nhex-{s}.xlsx',f'https://www.cihi.ca/sites/default/files/document/nhex-{s}-2025-en.xlsx') for s in ['series-d2','series-d3','series-d4','appendices-a-d']]
    items += [('hospital-workforce.xlsx','https://www.cihi.ca/sites/default/files/document/spending-trends-health-service-delivery-2014-2023-data-tables-en.xlsx')]
    pages={
      'toh':'https://www.ottawahospital.on.ca/en/who-we-are/annual-reports/',
      'cheo':'https://www.cheo.on.ca/en/about-us/about-cheo/reporting-and-statistics/',
      'qch':'https://www.qch.on.ca/ReportsPublications',
      'montfort':'https://hopitalmontfort.com/en/corp/our-publications-and-reports'}
    from urllib.parse import urljoin
    links={}
    for key,url in pages.items():
        try:
            html=get(url).text
            (RAW/f'{key}-index.html').write_text(html,encoding='utf-8')
            soup=BeautifulSoup(html,'html.parser')
            links[key]=[{'text':a.get_text(' ',strip=True),'url':urljoin(url,a.get('href',''))} for a in soup.select('a[href]') if re.search(r'financial|consolidated|annual report|rapport annuel|statement',a.get_text(' ',strip=True)+' '+a.get('href',''),re.I)]
            if key=='toh':
                (RAW/'toh-links.json').write_text(json.dumps(links[key],indent=2),encoding='utf-8')
        except Exception as e: print(key, str(e))
    (RAW/'hospital-links.json').write_text(json.dumps(links,indent=2),encoding='utf-8')
    results=list(ThreadPoolExecutor(max_workers=5).map(fetch,items))
    (ROOT/'data'/'source-manifest.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,indent=2))

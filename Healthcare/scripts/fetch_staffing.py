from fetch_sources import *
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
base='https://www.ottawahospital.on.ca'
items=[(f'toh-annual-{y}.docx',base+f'/sites/default/files/{"2026-06" if y==2023 else "2025-08"}/Accessible%20Annual%20Report_{y}-{y+1}.docx') for y in range(2018,2024)]
items += [(f'toh-annual-{y}.html',base+f'/en/who-we-are/annual-reports/{y}-{y+1}-annual-report/fast-facts') for y in [2024,2025]]
def job(item):
 try:
    result=fetch(item);p=RAW/item[0]
    if p.suffix=='.docx':
        root=ET.fromstring(ZipFile(p).read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        txt='\n'.join(''.join(t.itertext()) for t in root.findall('.//w:p',ns))
    else:txt=BeautifulSoup(p.read_bytes(),'html.parser').get_text(' ',strip=True)
    (RAW/(p.stem+'.txt')).write_text(txt,encoding='utf-8');print(item[0],flush=True)
    return result
 except Exception as e:print(item[0],e,flush=True)
results=[r for r in ThreadPoolExecutor(max_workers=5).map(job,items) if r]
path=ROOT/'data'/'source-manifest.json';prior=json.loads(path.read_text())
prior=[r for r in prior if not r['file'].startswith('toh-annual')]
path.write_text(json.dumps(prior+results,indent=2)+'\n',encoding='utf-8')

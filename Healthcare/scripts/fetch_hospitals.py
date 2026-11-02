from fetch_sources import *
import pymupdf

links=json.loads((RAW/'hospital-links.json').read_text(encoding='utf-8'))
links['toh']=json.loads((RAW/'toh-links.json').read_text(encoding='utf-8'))
items=[]
for key in ['cheo','qch']:
    for a in links[key]:
        m=re.search(r'20\d\d',a['text'])
        if m and int(m[0]) in [2020,2022,2024,2026] and a['url'].lower().endswith('.pdf') and 'accessible version' not in a['text']:
            items.append((f'{key}-{m[0]}.pdf',a['url']))
for a in links['toh']:
    if 'non' in a['text'].lower():
        years=re.findall(r'20\d\d',a['url'])
        year=years[-1] if years else None
        if year in ['2020','2022','2024','2026']: items.append((f'toh-{year}.pdf',a['url']))
items += [('montfort-2026.pdf','https://hopitalmontfort.com/sites/default/files/2026-06/20260331%20Financial%20Statements%20ML%20Signed%20%28Ho%CC%82pital%20Montfort%29.pdf'),('montfort-2024.pdf','https://hopitalmontfort.com/sites/default/files/2024-06/Ho%CC%82pital%20Montfort%2012312024%20Final%20FS%20%28English%29.pdf')]
def job(item):
    try:
        result=fetch(item)
        with pymupdf.open(RAW/item[0]) as pdf:
            text='\n\n'.join(f'PDF PAGE {i+1}\n'+p.get_text(sort=True) for i,p in enumerate(pdf))
            (RAW/item[0].replace('.pdf','.txt')).write_text(text,encoding='utf-8')
        print(item[0],len(text),flush=True)
        return result
    except Exception as e: print(item[0],e,flush=True)
results=[r for r in ThreadPoolExecutor(max_workers=6).map(job,items) if r]
path=ROOT/'data'/'source-manifest.json'
prior=json.loads(path.read_text()); prior=[r for r in prior if not r['file'].endswith('.pdf')]
path.write_text(json.dumps(prior+results,indent=2)+'\n',encoding='utf-8')

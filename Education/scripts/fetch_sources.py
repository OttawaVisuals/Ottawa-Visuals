"""Cache official sources; large workbooks stay out of Git. Run from any directory."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib, json, urllib.request, zipfile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
RAW.mkdir(parents=True, exist_ok=True)

def fetch(url, path):
    if not path.exists():
        with urllib.request.urlopen(url, timeout=180) as response:
            path.write_bytes(response.read())
    return path

catalogue = fetch('https://data.ontario.ca/api/3/action/package_show?id=elementary-class-size', RAW / 'class-catalogue.json')
resources = json.loads(catalogue.read_text(encoding='utf-8'))['result']['resources']
jobs = [(r['url'], RAW / r['url'].rsplit('/', 1)[-1]) for r in resources]
for table in ('37100066', '37100067', '18100005'):
    jobs.append((f'https://www150.statcan.gc.ca/n1/tbl/csv/{table}-eng.zip', RAW / f'{table}-eng.zip'))
with ThreadPoolExecutor(max_workers=4) as pool:
    files = list(pool.map(lambda job: fetch(*job), jobs))
for file in files:
    if file.suffix == '.zip':
        with zipfile.ZipFile(file) as archive:
            for name in archive.namelist():
                if '/' not in name and name.endswith('.csv'):
                    (RAW / name).write_bytes(archive.read(name))
manifest = [{'file': path.relative_to(ROOT).as_posix(), 'url': url, 'bytes': path.stat().st_size,
             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for url, path in jobs]
(ROOT / 'data/source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(f'Cached and hashed {len(files)} official downloads.')

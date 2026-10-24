"""Build a static map and project evidence without converting plans into openings."""
import csv
import json
import math
from html import escape as e
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def build():
    d=json.loads((ROOT/'data/dog-parks.json').read_text(encoding='utf-8'))
    m=json.loads((ROOT/'data/dog-parks-map.json').read_text(encoding='utf-8'))
    def link(key,label='Source ↗'):
        return f'<a href="{e(d["sources"][key]["url"],quote=True)}">{e(label)}</a>'
    fields=['id','name','area','ward','geography','status','opening_date','ceremony_date','evidence_as_of','date_label','note','source_url']
    with (ROOT/'data/dog-parks.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        w.writerows({**{k:r[k] for k in fields if k!='source_url'},'source_url':d['sources'][r['source']]['url']} for r in d['parks'])
    with (ROOT/'data/dog-parks-milestones.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['park_id','date','text','source_url']);w.writeheader()
        w.writerows({'park_id':p['id'],'date':r['date'],'text':r['text'],'source_url':d['sources'][r['source']]['url']} for p in d['parks'] for r in p['history'])
    projection=lambda lon,lat:(math.radians(lon),-math.log(math.tan(math.pi/4+math.radians(lat)/2)))
    corners=[projection(-76.03,45.40),projection(-75.45,45.13)]
    xmin,ymin=corners[0];xmax,ymax=corners[1]
    scale=min(740/(xmax-xmin),440/(ymax-ymin))
    def xy(lon,lat):
        x,y=projection(lon,lat)
        return 30+(740-(xmax-xmin)*scale)/2+(x-xmin)*scale,25+(440-(ymax-ymin)*scale)/2+(y-ymin)*scale
    svg=['<svg class="dog-map" viewBox="0 0 800 500" role="img" aria-labelledby="dog-map-title dog-map-desc"><title id="dog-map-title">Selected dog-park projects in west and south Ottawa</title><desc id="dog-map-desc">Five numbered site markers match the project cards. Filled circle means opening ceremony confirmed; hollow circle means public use reported; diamonds show other project stages. Approximate locations, not entrances.</desc><defs><clipPath id="dog-map-clip"><rect x="20" y="20" width="760" height="450"/></clipPath></defs><g clip-path="url(#dog-map-clip)">']
    for ward in m['wards']:
        path=' '.join('M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in [xy(*p) for p in ring])+' Z' for ring in ward['rings'])
        svg.append(f'<path class="dog-ward" d="{path}"><title>Ward {ward["ward"]}</title></path>')
    svg.append('</g>')
    cards=[]
    for i,p in enumerate(d['parks'],1):
        loc=next(l for l in m['locations'] if l['id']==p['id']);x,y=xy(loc['longitude'],loc['latitude'])
        shape=(f'<path class="dog-marker context" d="M{x},{y-24} L{x+24},{y} L{x},{y+24} L{x-24},{y} Z"/>' if p['kind']=='context' else f'<circle class="dog-marker {p["kind"]}" cx="{x}" cy="{y}" r="24"/>')
        svg.append(f'<a href="#dog-{p["id"]}" aria-label="{i}. {e(p["name"])}: {e(p["status"])}"><title>{e(p["name"])} · {e(p["area"])}</title><circle class="dog-hit" cx="{x}" cy="{y}" r="56"/>{shape}<text class="dog-number {p["kind"]}" x="{x}" y="{y}" dominant-baseline="central" text-anchor="middle">{i}</text></a>')
        history=''.join(f'<li><strong>{e(r["date"] or "Date unavailable")}</strong> · {e(r["text"])} {link(r["source"])}</li>' for r in p['history'])
        cards.append(f'<article class="dog-project" id="dog-{p["id"]}" aria-labelledby="dog-{p["id"]}-title"><p class="eyebrow">{i:02d} · {e(p["area"])} · Ward {p["ward"]}</p><h3 id="dog-{p["id"]}-title">{e(p["name"])}</h3><p class="dog-status {p["kind"]}">{e(p["status"])}</p><p><strong>{e(p["date_label"])}</strong></p><p>{e(p["note"])}</p><p class="small">{e(p["geography"].capitalize())} · {link(p["source"])}</p><details><summary>Project milestones</summary><ul class="dog-milestones">{history}</ul></details></article>')
    svg.append('<text class="dog-map-note" x="30" y="488">North ↑ · west/south Ottawa · ward outlines · approximate sites</text></svg>')
    sources=''.join(f'<li>{link(k,s["title"])}<br><small>{e(s["note"])}</small></li>' for k,s in d['sources'].items())
    return f'''<section id="dog-parks" class="card" aria-labelledby="dog-title"><p class="eyebrow">06 · Parks and recreation</p><h2 id="dog-title">New dog parks: openings and other milestones</h2>
<div class="promise"><p><strong>The original 2022 commitment</strong></p><p>At least <strong>three new dog parks in the suburbs</strong>.</p><p class="small">{link('campaign','October 2022 election coverage')} · No precise deadline verified in this source.</p></div>
<p class="verdict"><strong>One suburban opening ceremony confirmed; another new suburban site reported in use.</strong></p><p>Morgan’s Grant and McKenna Casey have public-use evidence. Shea Woods, Andy Shields and Richmond are shown separately because acquisition, construction and rural-village locations do not establish additional suburban openings.</p>
<h3>Where the projects are</h3><div class="legend dog-legend"><span>● Opening ceremony confirmed</span><span>○ Public use reported</span><span>◇ Other project stage</span></div>
{''.join(svg)}<p class="small">Select a numbered marker to jump to its project. Locations show the site or a nearby reference address, not entrances. <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> / Mapcarta, City of Ottawa and Esri geocoding; <a href="data/dog-parks-map.json">location methods and sources</a>.</p>
<div class="dog-projects">{''.join(cards)}</div>
<details><summary>Why this differs from the reported four new parks</summary><p>CBC’s August 20, 2026 review reports four new dog parks citywide, but the reviewed text does not name all four or establish that all are suburban. That reported total is not substituted for verified, named openings here. {link('reported_four')}</p><p>Shea Woods had informal dog use long before this term. The February 2026 update confirms acquisition, with park plans still to be finalized. Andy Shields is in Greely and its certificate establishes substantial construction performance, not a public-opening date. Richmond’s October 2026 update explicitly says it is not open. These distinctions prevent counting different milestones as the same result.</p></details>
<details><summary>Sources, dates and counting method</summary><p>{e(d['method'])}</p><p>Reviewed October 24, 2026. Status dates are source-specific. A ceremony is not necessarily the first day of use. McKenna Casey’s public-use statement has no exact publication date available; October 24 is the observation date, not its opening date. The mayor’s statement is identified as interested-party evidence. Gregory Casey and McKenna Casey are one project, not two; small/large-dog enclosures are not counted separately.</p><p>Geography uses the named communities: Kanata North, Barrhaven and Stittsville are suburban; Greely and Richmond are rural villages, shown for context. This is an analytical scope rule, not a verified campaign definition of suburbs. No annual citywide totals, missing-year zeros, completion percentage or attribution of all work to the mayor are inferred. Original archived platform not obtained.</p><p>Map: retained 2022 ward geometry, cropped to west/south Ottawa; approximate site markers from the documented sources. The Richmond point uses City polygon geometry because the latitude/longitude attributes are inconsistent with the site. Map creation/modification timestamps are not opening dates.</p><ol class="source-list">{sources}</ol></details>
<div class="downloads"><a href="data/dog-parks.csv" download>Project evidence CSV ↓</a><a href="data/dog-parks-milestones.csv" download>Milestones CSV ↓</a><a href="data/dog-parks.json" download>Reviewed data &amp; sources ↓</a></div></section>'''

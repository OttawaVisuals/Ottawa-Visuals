"""Render reviewed OPS neighbourhood aggregates; ordinary builds stay offline."""
import csv
import json
import math
from html import escape as e
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NAMES={'Assaults':'Assaults','Robbery':'Robberies','Break and Enter':'Break and enters','Theft $5000 and Under':'Theft · $5,000 and under'}
IDS=['assaults','robbery','break-enter','theft-under']


def build():
    d=json.loads((ROOT/'data/market-safety.json').read_text(encoding='utf-8'))
    evidence=json.loads((ROOT/'data/market-safety-sources.json').read_text(encoding='utf-8'))
    def link(key,label='Source ↗'):
        return f'<a href="{e(evidence["sources"][key]["url"],quote=True)}">{e(label)}</a>'
    with (ROOT/'data/market-safety.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['neighbourhood','reported_year','category','count','source_url','snapshot_date']);w.writeheader()
        w.writerows({'neighbourhood':'Byward Market','reported_year':r['year'],'category':r['category'],'count':r['count'],'source_url':evidence['sources']['api']['url'],'snapshot_date':d['retrieved']} for r in d['observations'])
    charts=[]
    for i,category in enumerate(d['categories']):
        rows=sorted((r for r in d['observations'] if r['category']==category),key=lambda r:r['year'])
        step=50 if max(r['count'] for r in rows)<400 else 200
        maximum=math.ceil(max(r['count'] for r in rows)/step)*step
        x=lambda j:65+(j+.5)*85
        y=lambda value:320-value/maximum*245
        base=next(r['count'] for r in rows if r['year']==2022);latest=rows[-1]['count']
        title=NAMES[category]
        bits=[f'<svg class="market-svg" viewBox="0 0 850 395" role="img" aria-labelledby="market-{IDS[i]}-title market-{IDS[i]}-desc"><title id="market-{IDS[i]}-title">{e(title)}: OPS Byward Market neighbourhood, 2018–2025</title><desc id="market-{IDS[i]}-desc">Annual counts by report year in the current preliminary snapshot. Bars start at zero. 2022 is outlined as election-year context; 2023–2025 are the first full calendar years of the term. OPS cautions against relying on time comparisons.</desc><rect class="market-term" x="490" y="55" width="255" height="265"/><text class="market-tick" x="65" y="23">{e(title)} · recorded incidents</text>']
        for v in range(0,maximum+1,step):
            bits.append(f'<line class="market-gridline" x1="65" x2="745" y1="{y(v)}" y2="{y(v)}"/><text class="market-tick" x="54" y="{y(v)+4}" text-anchor="end">{v:,}</text>')
        for j,r in enumerate(rows):
            cls='term' if r['year']>=2023 else 'baseline' if r['year']==2022 else 'history'
            bits.append(f'<rect class="market-bar {cls}" x="{x(j)-23}" y="{y(r["count"]):.2f}" width="46" height="{320-y(r["count"]):.2f}"><title>{r["year"]}: {r["count"]:,} {e(title.lower())}</title></rect><text class="market-value" x="{x(j)}" y="{y(r["count"])-9:.2f}" text-anchor="middle">{r["count"]:,}</text><text class="market-tick" x="{x(j)}" y="345" text-anchor="middle">{r["year"]}</text>')
        bits.append('<text class="market-tick" x="745" y="378" text-anchor="end">2023–2025 shaded · first full calendar years of term</text></svg>')
        charts.append(f'<div class="market-chart" data-market-metric="{IDS[i]}"'+(' hidden' if i else '')+f'><p class="market-comparison"><strong>{e(title)}</strong> · 2022: {base:,} · 2025: {latest:,}</p><div class="chart-scroll" tabindex="0" role="region" aria-label="{e(title)} annual chart; scroll sideways on small screens">'+''.join(bits)+'</div></div>')
    options=''.join(f'<option value="{id}">{e(NAMES[category])}</option>' for id,category in zip(IDS,d['categories']))
    table=[]
    for year in range(2018,2026):
        cells=''.join(f'<td>{next(r["count"] for r in d["observations"] if r["year"]==year and r["category"]==category):,}</td>' for category in d['categories'])
        table.append(f'<tr><th scope="row">{year}</th>{cells}</tr>')
    source_list=''.join(f'<li>{link(k,s["title"])}<br><small>{e(s["locator"])}. {e(s["note"])}</small></li>' for k,s in evidence['sources'].items())
    limits=''.join(f'<li>{e(t)}</li>' for t in evidence['limits'])
    # Only neighbourhood outline is displayed, never incident locations.
    geom=d['boundary']['geometry'];polygons=geom['rings'] if 'rings' in geom else []
    coords=[pt for ring in polygons for pt in ring]
    if coords:
        xmin,xmax=min(p[0] for p in coords),max(p[0] for p in coords)
        ymin,ymax=min(p[1] for p in coords),max(p[1] for p in coords)
        scale=min(260/(xmax-xmin),160/(ymax-ymin))
        path=' '.join('M'+' L'.join(f'{20+(x-xmin)*scale:.2f},{190-(y-ymin)*scale:.2f}' for x,y in ring)+' Z' for ring in polygons)
        outline=f'<svg class="market-boundary" viewBox="0 0 300 220" role="img" aria-labelledby="market-boundary-title"><title id="market-boundary-title">OPS Byward Market neighbourhood boundary</title><path d="{path}"/><text x="20" y="20">North ↑ · neighbourhood outline</text></svg>'
    else:raise ValueError('Expected ArcGIS polygon rings')
    return f'''<section id="market-safety" class="card" aria-labelledby="market-title"><p class="eyebrow">06 · ByWard Market</p><h2 id="market-title">Safety: what police recorded</h2>
<div class="promise"><p><strong>The 2022 commitment</strong></p><p>Address ByWard Market safety, including a dedicated neighbourhood team and a storefront operations centre, working with police and community agencies.</p><p class="small">{link('campaign','October 3, 2022 platform coverage')} · No numerical crime-reduction target verified.</p></div>
<p class="verdict"><strong>OPS reports the operations centre opened in June 2024.</strong> That confirms one promised action; it does not establish that the Market is safer. {link('core')}</p>
<h3>Reported incidents · 2018–2025</h3><p>Four selected categories, using the same <strong>OPS Byward Market neighbourhood</strong> field for every year. Counts are by the year reported, not necessarily the year an event occurred.</p>
<p class="market-caution"><strong>Preliminary snapshot:</strong> OPS cautions against relying on these figures for comparisons over time. Counts can be revised and do not capture all crime or how safe people feel. This chart describes published records, without a safety verdict. {link('portal','OPS definitions and caution')}</p>
<div class="market-controls" hidden><label for="market-metric">Incident category</label><select id="market-metric">{options}</select></div>
<div class="legend"><span><i class="key historical"></i>2018–2021 context</span><span><i class="key market-baseline-key"></i>2022 election year</span><span><i class="key"></i>2023–2025</span></div>
{''.join(charts)}<p class="small">Bars start at zero; each category has its own labelled scale. 2022 includes the final weeks after taking office. No 2026 annual result in this dataset. On small screens, the chart opens at recent years; scroll left for earlier history. Without JavaScript, assaults and all exact values remain available.</p>
<details><summary>Exact annual counts · all four categories</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Byward Market selected incident counts"><table style="min-width:620px"><thead><tr><th scope="col">Report year</th>{''.join(f'<th scope="col">{e(NAMES[c])}</th>' for c in d['categories'])}</tr></thead><tbody>{''.join(table)}</tbody></table></div><p class="small">These categories are not summed into a total-crime or violent-crime measure.</p></details>
<details><summary>Which area, and what changed in policing?</summary>{outline}<p>The boundary is the OPS/ONS 2017 <strong>Byward Market neighbourhood</strong>. It is not all of Ward 12, Lowertown, the BMDA district or the wider CORE policing zone. {link('boundary')}</p><p>OPS confirms the Neighbourhood Operations Centre and CORE strategy launched in June 2024. CORE also covers the Rideau Street corridor and Sandy Hill north. Its hotspot and calls-for-service results use different measures and geography, so they are not inserted into these annual neighbourhood counts. {link('core')}</p><p>The full 2022 platform also mentions CCTV, a single reporting contact and a mental-health task force. Their complete delivery is not established by this crime series or the centre opening. No whole-promise score is assigned.</p></details>
<details><summary>Sources, methodology and limits</summary><p>Snapshot retrieved {e(d['retrieved'])}; reviewed October 24, 2026. Query the OPS year-end layer by its existing neighbourhood field; group by Reported_Year and offence category. No individual addresses or incident locations are published here. The 32 grouped counts reconcile independently with 7,893 paged source records; no duplicate year/category/GO identifiers in that check.</p><p>OPS records founded incidents by their most serious violation. These four categories were selected to show different kinds of reported harm, with annual observations available throughout 2018–2025. They are not a comprehensive safety index. Data can change, so downloaded snapshots may differ from later portal results.</p><ul>{limits}</ul><ol class="source-list">{source_list}</ol><p class="small">Contains information licensed under the <a href="https://www.ontario.ca/page/open-government-licence-ontario">Open Government Licence – Ontario</a>. Information provider: Ottawa Police Service. Independent analysis; no OPS endorsement.</p></details>
<div class="downloads"><a href="data/market-safety.csv" download>Annual counts CSV ↓</a><a href="data/market-safety.json" download>Counts, query provenance &amp; boundary ↓</a><a href="data/market-safety-sources.json" download>Sources &amp; evidence limits ↓</a></div></section>'''

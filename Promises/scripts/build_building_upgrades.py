"""Build static evidence for the additional municipal-building retrofit pledge."""
import csv
import json
from html import escape as e
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def build():
    d=json.loads((ROOT/'data/building-upgrades.json').read_text(encoding='utf-8'))
    def link(key,label='Source ↗'):
        return f'<a href="{e(d["sources"][key]["url"],quote=True)}">{e(label)}</a>'
    with (ROOT/'data/building-upgrades-projects.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['site','work','status','as_of','source_url']);w.writeheader()
        w.writerows({**{k:r[k] for k in ['site','work','status','as_of']},'source_url':d['sources'][r['source']]['url']} for r in d['projects'])
    with (ROOT/'data/building-upgrades-plan-2024.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['measure','amount_cad','type','page','source_url']);w.writeheader()
        w.writerows({**r,'source_url':d['sources']['plan']['url']} for r in d['plan_2024'])
    chart=['<svg class="building-svg" viewBox="0 0 800 340" role="img" aria-labelledby="building-chart-title building-chart-desc"><title id="building-chart-title">Selected 2024 energy upgrade costs and allocations</title><desc id="building-chart-desc">Horizontal bars start at zero. These are estimated costs or approved allocations in the 2024 plan, not actual spending or a complete pledge total.</desc>']
    for i,r in enumerate(d['plan_2024']):
        y=35+i*43
        chart.append(f'<text class="building-tick" x="202" y="{y+17}" text-anchor="end">{e(r["measure"])}</text><rect class="building-bar" x="220" y="{y}" width="{r["amount_cad"]/1000000*450:.2f}" height="25"><title>{e(r["measure"])}: ${r["amount_cad"]:,}; {e(r["type"])}</title></rect><text class="building-value" x="{228+r["amount_cad"]/1000000*450:.2f}" y="{y+17}">${r["amount_cad"]/1000000:.3f}M</text>')
    for v in [0,.5,1]:
        x=220+v*450
        chart.append(f'<text class="building-tick" x="{x}" y="322" text-anchor="middle">${v:g}M</text>')
    chart.append('<line class="building-axis" x1="220" x2="670" y1="300" y2="300"/></svg>')
    table=''.join(f'<tr><th scope="row">{e(r["measure"])}</th><td>${r["amount_cad"]:,}</td><td>{e(r["type"])}</td><td>{link("plan","PDF p. "+str(r["page"]))}</td></tr>' for r in d['plan_2024'])
    lanes=[]
    for completed,title in [(True,'Reported complete · April 2025'),(False,'Planned / ongoing · June 2026')]:
        items=''.join(f'<li><strong>{e(r["site"])}</strong><br>{e(r["work"])}</li>' for r in d['projects'] if r['status'].startswith('Completed')==completed)
        lanes.append(f'<article class="building-lane"><h3>{title}</h3><ul>{items}</ul></article>')
    sources=''.join(f'<li>{link(k,s["title"])}<br><small>{e(s["locator"])}. {e(s["note"])}</small></li>' for k,s in d['sources'].items())
    limits=''.join(f'<li>{e(t)}</li>' for t in d['limitations'])
    return f'''<section id="building-upgrades" class="card" aria-labelledby="building-title"><p class="eyebrow">06 · Municipal buildings</p><h2 id="building-title">Energy upgrades: projects and spending evidence</h2>
<div class="promise"><p><strong>The 2022 commitment</strong></p><p>An <strong>additional $100 million over four years</strong> in energy upgrades and retrofits to City buildings, with support from federal/provincial programs and Hydro Ottawa.</p><p class="small">{link('campaign','August 17, 2022 platform coverage')}</p></div>
<p class="verdict"><strong>Projects are documented. The additional $100M total cannot yet be verified from the sources reviewed.</strong></p>
<div class="building-facts"><article><strong>$3.5–4M / year</strong><p>City-reported efficiency investment since 2023.</p><small>Reported June 19, 2026 · {link('latest')}</small></article><article><strong>Term total unavailable</strong><p>No comparable ledger or baseline for the promised additional investment.</p><small>Missing data does not mean zero spending.</small></article></div>
<p class="small">The annual range is not a year-by-year breakdown. It is not extrapolated into a four-year total or used to calculate pledge completion.</p>
<h3>What the 2024 plan priced</h3><p>Selected energy measures in the City’s plan: estimated costs and approved allocations, <strong>not actual expenditures</strong>. This is one documented planning snapshot, not all building spending.</p>
<div class="chart-scroll" tabindex="0" role="region" aria-label="Selected 2024 building energy measures; scroll horizontally on small screens">{''.join(chart)}</div>
<p class="small">Bars start at zero. “Building automation” and “Building envelope” are allocations; other bars are cost estimates. Scroll sideways on small screens. {link('plan','2024 energy plan · PDF pp. 4–7')}</p>
<h3>Named projects: what is confirmed?</h3><div class="building-projects">{''.join(lanes)}</div>
<p class="small">Selected examples, not a complete inventory. “Complete” means reported complete by April 22, 2025; exact installation dates and individual costs are not given. June 19, 2026 plans remain planned/ongoing in this snapshot; later completion has not been verified. {link('completed','April report')} · {link('latest','June report')}</p>
<details><summary>Exact 2024 figures</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Selected 2024 energy measure amounts"><table><thead><tr><th scope="col">Measure</th><th scope="col">Amount</th><th scope="col">Evidence type</th><th scope="col">Source</th></tr></thead><tbody>{table}</tbody></table></div></details>
<details><summary>Why the reported totals cannot be combined</summary><p>The mayor’s current retrospective claim is more than $100M for building retrofits and renewals. That broader scope includes facility usability; the page does not supply a project-level bridge to the original additional energy-upgrade pledge. {link('claim','Read the record claim')}</p><p>The 2024 plan notes that projects can draw on asset-management and facility budgets. Its historical 2019–2023 totals span the previous term. Neither those totals nor the selected 2024 amounts can be added to the later annual range.</p><p>A defensible comparison needs dated actual expenditures, eligible energy work, funding sources and a pre-promise baseline identifying what was additional. The $100M commitment is retained without assigning a pass/fail status.</p></details>
<details><summary>Sources, methodology and gaps</summary><p>Reviewed October 24, 2026. Latest retained project update: June 19, 2026. City-owned buildings only; household retrofit loans, buses and general climate spending are excluded. Original coverage specifies four years; exact calendar endpoints and baseline accounting remain unverified.</p><ul>{limits}</ul><ol class="source-list">{sources}</ol></details>
<div class="downloads"><a href="data/building-upgrades-plan-2024.csv" download>2024 plan amounts CSV ↓</a><a href="data/building-upgrades-projects.csv" download>Project evidence CSV ↓</a><a href="data/building-upgrades.json" download>Reviewed data &amp; sources ↓</a></div></section>'''

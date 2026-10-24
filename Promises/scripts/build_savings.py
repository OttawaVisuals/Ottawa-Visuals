"""Render the reviewed City efficiency ledger without interpreting it as audited savings."""
import csv
import json
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    d = json.loads((ROOT / 'data/savings.json').read_text(encoding='utf-8'))
    years = d['years']
    def link(key, label='Source ↗'):
        return f'<a href="{e(d["sources"][key]["url"], quote=True)}">{e(label)}</a>'
    fields = ['year', 'operating_cad_thousands', 'capital_cad_thousands', 'total_cad_thousands', 'evidence_status', 'recurrence', 'source_url', 'locator']
    with (ROOT / 'data/savings.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in years:
            w.writerow({**{k: r[k] for k in fields if k in r}, 'source_url': d['sources']['city_table']['url'], 'locator': 'PDF page 38, Table 5'})
    with (ROOT / 'data/savings-2026-items.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['year', 'group', 'item', 'operating_cad_thousands', 'recurrence', 'evidence_status', 'source_url', 'classification', 'explanation', 'remaining_gap', 'detail_source_url', 'evidence_basis'])
        for r in d['items_2026']:
            w.writerow([2026, r['group'], r['item'], r['operating_cad_thousands'], 'Unknown', 'Identified in draft budget; realization not verified', d['sources']['city_table']['url'], r['classification'], r['explanation'], r['remaining_gap'], d['sources'][r['detail_source']]['url'], r['evidence_basis']])
    # Values are thousands of CAD in the source; chart divides by 1,000 for millions.
    y = lambda n: 330 - n / 1000 * 2.5
    svg = ['<svg class="savings-svg" viewBox="0 0 800 410" role="img" aria-labelledby="savings-chart-title savings-chart-desc"><title id="savings-chart-title">City-reported budget efficiencies, 2023–2026</title><desc id="savings-chart-desc">Stacked annual bars separate operating and capital amounts. 2026 is identified in a draft budget, not verified realized savings. Exact amounts and status follow in the table.</desc><text class="axis-title" x="58" y="20">CAD millions · nominal</text>']
    for n in range(0, 101, 20):
        sy = y(n * 1000)
        svg.append(f'<line class="gridline" x1="58" x2="780" y1="{sy}" y2="{sy}"/><text class="tick" x="48" y="{sy+4}" text-anchor="end">{n}</text>')
    rows = []
    for i, r in enumerate(years):
        x = 112 + i * 175
        op, cap, total = (r[k] for k in ['operating_cad_thousands', 'capital_cad_thousands', 'total_cad_thousands'])
        draft = ' draft' if r['year'] == 2026 else ''
        for value, base, cls, label in [(op, 0, 'operating', 'Operating'), (cap, op, 'capital', 'Capital')]:
            if not value:
                continue
            svg.append(f'<rect class="savings-column {cls}{draft}" x="{x}" y="{y(base+value)}" width="80" height="{value/1000*2.5}"><title>{r["year"]} · {label}: ${value/1000:.3f}M · {e(r["evidence_status"])}</title></rect>')
        svg.append(f'<text class="savings-label" x="{x+40}" y="{y(total)-12}" text-anchor="middle">${total/1000:.2f}M</text><text class="tick" x="{x+40}" y="355" text-anchor="middle">{r["year"]}</text>')
        if draft:
            svg.append(f'<text class="tick" x="{x+40}" y="375" text-anchor="middle">Draft identified</text>')
        rows.append(f'<tr><th scope="row">{r["year"]}</th><td>{op/1000:.3f}</td><td>{cap/1000:.3f}</td><td>{total/1000:.3f}</td><td>{e(r["evidence_status"])}</td></tr>')
    svg.append('</svg>')
    details = ''.join(f'<tr><th scope="row">{e(r["item"])}<br><small>{r["operating_cad_thousands"]/1000:.3f}M · {e(r["classification"])}</small></th><td>{e(r["explanation"])}<br>{link(r["detail_source"])}<br><small>{e(r["evidence_basis"])}</small></td><td>{e(r["remaining_gap"])}</td></tr>' for r in d['items_2026'])
    sources = ''.join(f'<li>{link(k, s["title"])}<br><small>{e(s["locator"])}. {e(s["note"])}</small></li>' for k, s in d['sources'].items())
    return f'''<section id="savings" class="card" aria-labelledby="savings-title">
<p class="eyebrow">05 · City finances</p><h2 id="savings-title">Find $35 million in municipal savings</h2>
<div class="promise"><p><strong>The 2022 commitment</strong></p><p>Review City spending and find <strong>at least $35 million in savings</strong>.</p><p class="small">Paraphrase of contemporary campaign coverage. {link('campaign', '2022 reporting ↗')} · {link('campaign_floor', '$35M cross-check ↗')}</p></div>
<p class="verdict"><strong>Under review: the headline totals need a fuller breakdown.</strong> We have not established a comparable net savings total or judged this promise fulfilled.</p>
<p>The City publishes budget explanations, but its summary mixes cost changes, revenue and funding measures. Lower costs than forecast can coexist with a growing budget. We need the baseline, offsetting costs, service effects and actual result to judge each measure.</p>
<h3>Transit: what the documents actually establish</h3>
<div class="table-wrap"><table><caption>Separate scopes — do not add these figures together.</caption><thead><tr><th>Record</th><th>Amount</th><th>What it establishes</th></tr></thead><tbody>
<tr><th scope="row">Magazine transit headline</th><td>$14.031M</td><td>One broad draft operating total. A complete item-by-item bridge is missing. {link('city_table')}</td></tr>
<tr><th scope="row">Adopted budget savings column</th><td>$2.363M</td><td>Transit Committee’s “Service Initiatives / Savings” reduction. Adoption confirmed for this subtotal; actual delivery unverified. {link('adopted_transit')}</td></tr>
<tr><th scope="row">Detailed draft notes</th><td>$2.200M + $0.163M</td><td>Station electricity and administration; sum to $2.363M. Indexed official text, direct PDF access blocked. These are not a complete explanation of $14.031M. {link('transit_notes')}</td></tr>
</tbody></table></div>
<p><strong>Electric-bus costs:</strong> less diesel spending alone does not establish net savings. Charging/electricity, maintenance, batteries, the purchase premium over replacement diesel buses, infrastructure, financing and grants need reconciliation. The financing model recognizes the purchase premium; we have not verified its treatment in the $14.031M. {link('cib_bus', 'Financing explanation ↗')}</p>
<h3>2026 measures: what the labels mean, and what is missing</h3>
<p class="small">Amounts below are the 14 magazine entries, totalling $44.924M. Categories and plain-language explanations are our reading of source labels unless a more specific record is linked. They are not verified net savings. Recurrence and actual realization remain unknown.</p>
<details id="savings-item-evidence"><summary>Review all 14 measures, explanations and gaps</summary>
<div class="table-wrap savings-evidence"><table><caption>CAD millions · 2026 draft snapshot. Every item retains an explicit evidence gap.</caption><thead><tr><th>Measure / amount</th><th>Explanation and evidence</th><th>Still needed</th></tr></thead><tbody>{details}</tbody></table></div>
</details>
<details id="savings-aggregate-context"><summary>City-reported annual totals — context only, reconciliation incomplete</summary>
<p class="small">The 2023–2025 rows remain aggregate claims: a full measure-by-measure bridge has not been verified for any of these years. This chart is not a promise score.</p>
<h3>What the City reports by budget year</h3>
<div class="legend"><span><i class="key"></i>Operating</span><span><i class="key savings-capital-key"></i>Capital</span><span>Outlined bar: 2026 draft amount</span></div>
<p class="small">Scroll sideways on small screens to see all four years.</p><div class="chart-scroll">{''.join(svg)}</div>
<p class="small">Source: City of Ottawa, Draft Budget 2026 magazine, Table 5 (p. 38). Earlier years are retrospective City-reported figures; 2026 is identified in the draft, with adoption reconciliation and actual delivery unverified. No annual $35M target is inferred. {link('city_table', 'View table ↗')}</p>
<div class="savings-totals"><div><strong>$207.748M</strong><span>2023–2025 reported total</span></div><div><strong>+$44.924M</strong><span>2026 draft identified</span></div><div><strong>$252.672M</strong><span>Combined City headline scope</span></div></div>
<p class="small">Combined scope: $137.648M operating + $115.024M capital. This adds each source-year allocation once. It is not a verified cash saving over the term or an annual recurring run rate.</p>
<details><summary>Exact annual figures</summary><div class="table-wrap"><table><caption>CAD millions; source precision retained. Recurring/one-time split: unknown for every aggregate.</caption><thead><tr><th>Budget year</th><th>Operating</th><th>Capital</th><th>Total</th><th>Evidence status</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>
</details>
<details><summary>Method, sources and gaps</summary><ul><li><strong>Promise scope:</strong> 2022 reporting supports the $35M floor; one account gives a $35–60M range and another $35–65M. The original framework archive and exact timing/recurrence conditions were not recovered. No annual target or completion percentage is assigned.</li><li><strong>Budget scope:</strong> operating and capital are separate accounting categories, not recurring/one-time categories. Capital changes can span years; operating includes revenue measures. No recurring or one-time dollar split can be calculated from this table.</li><li><strong>Evidence:</strong> the City describes earlier amounts as achieved; this page attributes that claim and does not independently audit it. The 2026 row is a proposal snapshot, not a verified adopted or realized amount. Zero capital means zero in this source table, not proof of no other capital savings.</li><li><strong>Arithmetic:</strong> source thousands ÷ 1,000 = chart millions. Annual rows are summed once; 2026 detail is a breakdown, never added again. No repeated carry-forward, inflation adjustment or tax-bill conversion.</li></ul><ol class="source-list">{sources}</ol></details>
<p class="downloads"><a href="data/savings.csv" download>Annual CSV ↓</a><a href="data/savings-2026-items.csv" download>2026 items CSV ↓</a><a href="data/savings.json" download>Sources &amp; data JSON ↓</a></p></section>'''

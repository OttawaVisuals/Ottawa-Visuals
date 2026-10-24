"""Generate the transit-fare section and exact exports from reviewed prices."""
import csv
import json
import math
import statistics
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    data = json.loads((ROOT / 'data/transit-fares.json').read_text(encoding='utf-8'))
    cpi = json.loads((ROOT / 'data/inflation.json').read_text(encoding='utf-8'))
    annual = cpi['annual_indices']
    base_cpi = annual['2022']
    records = []
    for product in data['products']:
        baseline = data['years'][0][product['field']]
        previous = None
        for r in data['years']:
            price = r[product['field']]
            endpoint = statistics.mean(cpi['monthly_2026_jan_sep'].values()) if r['year'] == 2026 else annual[str(r['year'])]
            records.append({'product': product['id'], 'product_label': product['label'], 'year': r['year'],
                            'price_cad': price, 'change_cad': None if previous is None else round(price - previous, 2),
                            'annual_increase_pct': None if previous is None else (price / previous - 1) * 100,
                            'cumulative_fare_pct': (price / baseline - 1) * 100,
                            'annual_cpi_pct': None if previous is None else cpi['inflation_pct'][str(r['year'])],
                            'cumulative_cpi_pct': (endpoint / base_cpi - 1) * 100,
                            'cpi_period': 'Jan–Sep average (provisional)' if r['year'] == 2026 else 'Annual average',
                            'source_url': data['sources'][r['source']]['url']})
            previous = price
    export = {'baseline_year': 2022, 'reviewed': data['reviewed'], 'records': records,
              'method': 'Annual fare change = current price / previous price - 1. Cumulative = price / late-2022 price - 1. CPI cumulative uses endpoint index / 2022 annual CPI - 1. All percentage results ×100; 2026 CPI endpoint is Jan–Sep, not a full year.'}
    (ROOT / 'data/transit-fares-series.json').write_text(json.dumps(export, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (ROOT / 'data/transit-fares.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows([{k: round(v, 6) if isinstance(v, float) else v for k, v in r.items()} for r in records])

    def chart(product, mode):
        series = [r for r in records if r['product'] == product['id'] and (mode == 'price' or r['year'] >= 2023)]
        field = {'price': 'price_cad', 'annual': 'annual_increase_pct', 'cumulative': 'cumulative_fare_pct'}[mode]
        inflation_field = 'annual_cpi_pct' if mode == 'annual' else 'cumulative_cpi_pct'
        values = [r[field] for r in series]
        if mode != 'price':
            values += [r[inflation_field] for r in series]
        tick = (25 if product['id'] == 'monthly' else 1) if mode == 'price' else (1 if mode == 'annual' else 2)
        maximum = max(tick, math.ceil(max(values) / tick) * tick)
        w, h, left, right, top, bottom = 740, 410, 60, 30, 40, 62
        pw, ph = w-left-right, h-top-bottom
        step = pw/len(series)
        x = lambda i: left + step*(i+.5)
        y = lambda v: top+ph*(1-v/maximum)
        name = f'fare-{product["id"]}-{mode}'
        axis = ('Price (CAD ' + product['unit'] + ')') if mode == 'price' else 'Annual increase (%)' if mode == 'annual' else 'Cumulative increase since 2022 (%)'
        bits = [f'<svg class="fare-svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{name}-title {name}-desc"><title id="{name}-title">{escape(product["label"])} · {axis}</title><desc id="{name}-desc">Bars show published adult fare prices or calculated increases. Exact amounts are in the table. CPI is an optional line in percentage views; its 2026 endpoint is partial-year.</desc><text class="axis-title" x="{left}" y="18">{axis}</text>']
        for v in range(0, maximum+1, tick):
            label = f'${v}' if mode == 'price' else f'{v}%'
            bits.append(f'<line class="gridline" x1="{left}" x2="{w-right}" y1="{y(v):.2f}" y2="{y(v):.2f}"/><text class="tick" x="{left-9}" y="{y(v)+4:.2f}" text-anchor="end">{label}</text>')
        for i,r in enumerate(series):
            value = r[field]
            label = f'${value:.2f}' if mode == 'price' else f'{value:.2f}%'
            colour = 'fare-column baseline' if r['year'] == 2022 else 'fare-column'
            bits.append(f'<rect class="{colour}" x="{x(i)-step*.25:.2f}" y="{y(value):.2f}" width="{step*.5:.2f}" height="{max(0,y(0)-y(value)):.2f}"><title>{r["year"]}: {label}</title></rect><text class="fare-label" x="{x(i):.2f}" y="{y(value)-9:.2f}" text-anchor="middle">{label}</text><text class="tick" x="{x(i):.2f}" y="{y(0)+24:.2f}" text-anchor="middle">{r["year"]}</text>')
        if mode != 'price':
            points = ' '.join(f'{x(i):.2f},{y(r[inflation_field]):.2f}' for i,r in enumerate(series) if r['year'] < 2026)
            bits.append(f'<g class="fare-inflation"><polyline class="inflation-line" points="{points}"/>')
            i = len(series)-1
            bits.append(f'<line class="inflation-line provisional" x1="{x(i-1):.2f}" y1="{y(series[i-1][inflation_field]):.2f}" x2="{x(i):.2f}" y2="{y(series[i][inflation_field]):.2f}"/>')
            for i,r in enumerate(series):
                value = r[inflation_field]
                bits.append(f'<circle class="inflation-point {"provisional" if r["year"]==2026 else ""}" cx="{x(i):.2f}" cy="{y(value):.2f}" r="4"><title>Ottawa CPI {r["year"]}: {value:.2f}%'+(' · Jan–Sep endpoint, provisional' if r['year']==2026 else '')+'</title></circle>')
            bits.append('</g>')
        bits.append('</svg>')
        hidden = '' if product['id'] == 'card' and mode == 'price' else ' hidden'
        return f'<div class="fare-chart chart-scroll" data-product="{product["id"]}" data-fare-view="{mode}"{hidden} tabindex="0" role="region" aria-label="{escape(product["label"])} {mode} chart; scroll horizontally on small screens">'+''.join(bits)+'</div>'

    charts = ''.join(chart(p, mode) for p in data['products'] for mode in ['price','annual','cumulative'])
    table = []
    for r in data['years']:
        links = data['sources'][r['source']]
        table.append(f'<tr><th scope="row">{r["year"]}</th><td>${r["adult_card"]:.2f}</td><td>${r["adult_cash"]:.2f}</td><td>${r["adult_monthly"]:.2f}</td><td><a href="{escape(links["url"],quote=True)}">Source ↗</a><br><small>{escape(r["note"])}</small></td></tr>')
    changes = []
    for r in records:
        if r['year'] == 2022:
            continue
        changes.append(f'<tr><th scope="row">{escape(r["product_label"])}</th><td>{r["year"]}</td><td>${r["change_cad"]:.2f}</td><td>{r["annual_increase_pct"]:.2f}%</td><td>{r["cumulative_fare_pct"]:.2f}%</td><td>{r["annual_cpi_pct"]:.2f}%</td><td>{r["cumulative_cpi_pct"]:.2f}%'+(' (Jan–Sep)' if r['year']==2026 else '')+'</td></tr>')
    sources = ''.join(f'<li><a href="{escape(s["url"],quote=True)}">{escape(s["title"])}</a><br><small>{escape(s["locator"])}. {escape(s["note"])}</small></li>' for s in data['sources'].values())
    options = ''.join(f'<option value="{p["id"]}">{escape(p["label"])}</option>' for p in data['products'])
    return f'''<section id="transit-fares" class="card" aria-labelledby="fares-title"><p class="eyebrow">02 · Transit affordability</p><h2 id="fares-title">Transit fares</h2>
<div class="promise"><p><strong>The 2022 commitment</strong></p><p>Freeze transit fares for <strong>2023</strong>.</p><p class="small"><a href="{escape(data['sources']['campaign']['url'],quote=True)}">October 2022 campaign coverage ↗</a></p></div>
<p class="verdict"><strong>The 2023 freeze was implemented.</strong> Adult card, cash and monthly-pass prices stayed unchanged. Later increases are shown as context for a one-year commitment.</p>
<div class="fare-controls" hidden><label for="fare-product">Fare product<select id="fare-product">{options}</select></label><div class="range-buttons" role="group" aria-label="Fare chart measure"><button type="button" data-fare-mode="price" aria-pressed="true">Price</button><button type="button" data-fare-mode="annual" aria-pressed="false">Annual increase</button><button type="button" data-fare-mode="cumulative" aria-pressed="false">Cumulative</button></div><label class="fare-inflation-control"><input type="checkbox" id="fare-inflation" checked disabled> Show Ottawa inflation</label></div>
<p id="fare-summary" class="small" aria-live="polite">Adult card fare: $3.70 in late 2022 and 2023; $4.10 in 2026.</p>
<div class="legend"><span><i class="key"></i>Adult fare</span><span class="fare-baseline-legend"><i class="key historical"></i>Late-2022 baseline</span><span class="fare-inflation-legend" hidden><i class="key inflation"></i>Ottawa CPI inflation</span></div>
{charts}
<p class="small">On small screens, scroll the chart sideways to see all years.</p>
<p class="small" id="fare-view-note">Prices in Canadian dollars. The 2022 bar is the late-year fare schedule, not an annual average. Card and cash fares are separate products. Use the percentage views to compare with inflation.</p>
<p class="small"><strong>2026 CPI is partial-year.</strong> Annual mode compares Jan–Sep 2026 with Jan–Sep 2025. Cumulative mode compares the Jan–Sep 2026 average with the 2022 annual average. Fare prices apply to the 2026 schedule; inflation is not yet a full-year figure.</p>
<details><summary>Exact fare prices and sources</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Adult fare prices"><table style="min-width:640px"><caption>Adult prices by fare-validity year; 2022 is the baseline schedule.</caption><thead><tr><th scope="col">Year</th><th scope="col">Single · card</th><th scope="col">Single · cash</th><th scope="col">Monthly pass</th><th scope="col">Evidence</th></tr></thead><tbody>{''.join(table)}</tbody></table></div></details>
<details><summary>Annual and cumulative increases</summary><p class="small">Percentage changes use exact published prices, not the rounded budget-wide increase. Cumulative baseline: late 2022. CPI: Ottawa-Gatineau, Ontario part, all-items; same inputs as the property-tax section.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Fare changes and inflation"><table style="min-width:850px"><thead><tr><th scope="col">Product</th><th scope="col">Year</th><th scope="col">Dollar increase</th><th scope="col">Annual increase</th><th scope="col">Cumulative fare</th><th scope="col">Annual CPI</th><th scope="col">Cumulative CPI</th></tr></thead><tbody>{''.join(changes)}</tbody></table></div></details>
<details><summary>Fare methodology and evidence limits</summary><p>Annual increase = (current price / previous price − 1) × 100. Cumulative increase = (current price / late-2022 price − 1) × 100. This equals compounding the exact annual price changes. No 2022 annual increase is inferred; no earlier continuous fare history is asserted.</p><p>The fare schedule is not a rider’s total spending. Free-service periods, transfers, fare caps, changes in payment availability and number of trips are not modelled. Adult card means the published card/e-purse fare, without implying every card payment method was available throughout the period. Monthly passes use the year they are valid, even when sold the preceding December.</p><p>This first comparison covers standard adult fares. Seniors, youth, EquiPass, Community Pass, Access Pass, U-Pass and Para Transpo products need separate review. The adult series is not a comprehensive audit of every fare category. Operator pages returned 403 on automated opening; indexed official content, the adopted 2026 schedule, operator announcements republished by councillors and contemporary reporting were reconciled.</p><ol class="source-list">{sources}</ol><p>CPI sources and retained inputs: <a href="data/inflation.json">Ottawa CPI data</a> · <a href="#method">Sources &amp; method</a>.</p></details>
<div class="downloads"><a href="data/transit-fares.csv" download>Fares &amp; changes CSV ↓</a><a href="data/transit-fares.json" download>Prices &amp; source notes ↓</a><a href="data/transit-fares-series.json" download>Calculated series JSON ↓</a></div><script id="fare-series-data" type="application/json">{json.dumps(export, ensure_ascii=False).replace('<', '&lt;')}</script></section>'''


if __name__ == '__main__':
    build()
    print('Built transit-fare exports; run build_property_tax.py to update the complete page.')

"""Build static, offline-readable promise comparison and downloadable CSV. Stdlib only."""
import csv
import json
import math
import statistics
from html import escape as e
from pathlib import Path
from build_transit_fares import build as build_transit_fares
from build_bus_reliability import build as build_bus_reliability
from build_housing import build as build_housing
from build_ev_charging import build as build_ev_charging
from build_savings import build as build_savings

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'data/property-tax.json').read_text(encoding='utf-8'))
promise = data['promise']
upper = promise['upper_pct']
sources = data['sources']
inflation = json.loads((ROOT / 'data/inflation.json').read_text(encoding='utf-8'))

def source_link(key, label=None):
    s = sources[key]
    return f'<a href="{e(s["url"], quote=True)}">{e(label or s["title"])}</a>'

def cumulative_values(records):
    baseline = records[0]['year'] - 1
    factor = 1
    result = {}
    for r in records:
        year = r['year']
        factor *= 1 + r['increase_pct'] / 100
        index = (statistics.mean(inflation['monthly_2026_jan_sep'].values()) if year == 2026
                 else inflation['annual_indices'][str(year)])
        result[year] = {'tax': (factor - 1) * 100,
                        'cpi': (index / inflation['annual_indices'][str(baseline)] - 1) * 100}
    return result


def svg_chart(records, chart_id, cumulative=False):
    """Native SVG with a common percent axis; no second axis or chart library."""
    width, height = (990, 460) if len(records) > 4 else (720, 430)
    left, right, top, bottom = 52, 80, 55, 75
    pw, ph = width - left - right, height - top - bottom
    totals = cumulative_values(records)
    tax_value = lambda r: totals[r['year']]['tax'] if cumulative else r['increase_pct']
    cpi_value = lambda r: totals[r['year']]['cpi'] if cumulative else inflation['inflation_pct'][str(r['year'])]
    tick_step = 10 if cumulative and len(records) > 4 else 2 if cumulative else 1
    maximum = math.ceil(max(8, *(tax_value(r) for r in records), *(cpi_value(r) for r in records)) / tick_step) * tick_step
    step = pw / len(records)
    x = lambda i: left + step * (i + .5)
    y = lambda v: top + ph * (1 - v / maximum)
    measure = f'Cumulative increase since {records[0]["year"]-1} (%)' if cumulative else 'Annual increase (%)'
    parts = [f'<svg class="tax-chart" data-measure="{"cumulative" if cumulative else "annual"}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{chart_id}-title {chart_id}-desc"><title id="{chart_id}-title">Ottawa {measure}, {records[0]["year"]}–2026</title><desc id="{chart_id}-desc">Vertical bars show tax increases. A line shows Ottawa CPI inflation, with a hollow point and dashed segment for the partial 2026 year. Exact values are in the downloadable tables.</desc>']
    start = next(i for i, r in enumerate(records) if r['year'] == 2023)
    sx = left + step * start
    parts.append(f'<rect class="term-shade" x="{sx:.2f}" y="{top}" width="{pw-step*start:.2f}" height="{ph}"/>')
    for tick in range(0, maximum + 1, tick_step):
        parts.append(f'<line class="gridline" x1="{left}" x2="{width-right}" y1="{y(tick):.2f}" y2="{y(tick):.2f}"/><text class="tick" x="{left-10}" y="{y(tick)+4:.2f}" text-anchor="end">{tick}%</text>')
    parts.append(f'<text class="axis-title" x="{left}" y="20">{measure}</text>')
    for i, r in enumerate(records):
        rate = tax_value(r)
        label = f'{rate:.1f}' if cumulative else f'{rate:g}'
        bw = step * .52
        cname = 'tax-column' if r['year'] >= 2023 else 'tax-column historical'
        parts.append(f'<rect class="{cname}" x="{x(i)-bw/2:.2f}" y="{y(rate):.2f}" width="{bw:.2f}" height="{y(0)-y(rate):.2f}"><title>{r["year"]}: {"cumulative " if cumulative else ""}tax increase {label}%; inflation {cpi_value(r):.1f}%'+(' (Jan–Sep endpoint, provisional)' if r['year']==2026 else '')+'</title></rect>')
        parts.append(f'<text class="tax-label" x="{x(i):.2f}" y="{y(rate)-8:.2f}" text-anchor="middle">{label}%</text><text class="tick" x="{x(i):.2f}" y="{y(0)+22:.2f}" text-anchor="middle">{r["year"]}</text>')
    # References apply only to the campaign years, never to historical budgets.
    for value, dash in ([] if cumulative else [(2, '2 4'), (2.5, '7 4')]):
        parts.append(f'<line class="promise-line" x1="{sx:.2f}" x2="{width-right}" y1="{y(value):.2f}" y2="{y(value):.2f}" stroke-dasharray="{dash}"/><text class="reference-label" x="{width-right+8}" y="{y(value)+4:.2f}">{value:g}%</text>')
    annual_points = [(x(i), y(cpi_value(r))) for i,r in enumerate(records) if r['year'] <= 2025]
    points = ' '.join(f'{a:.2f},{b:.2f}' for a,b in annual_points)
    parts.append(f'<g class="inflation-series"><polyline class="inflation-line" points="{points}"/>')
    lastx, lasty = annual_points[-1]
    endx, endy = x(len(records)-1), y(cpi_value(records[-1]))
    parts.append(f'<line class="inflation-line provisional" x1="{lastx:.2f}" y1="{lasty:.2f}" x2="{endx:.2f}" y2="{endy:.2f}"/>')
    for i,r in enumerate(records):
        rate = cpi_value(r)
        provisional = r['year'] == 2026
        period = (f' · Jan–Sep endpoint versus {records[0]["year"]-1} annual average, provisional' if cumulative else ' · Jan–Sep versus Jan–Sep 2025, provisional') if provisional else (' · change from baseline annual average' if cumulative else ' · annual average change')
        parts.append(f'<circle class="inflation-point {"provisional" if provisional else ""}" cx="{x(i):.2f}" cy="{y(rate):.2f}" r="4"><title>{r["year"]} Ottawa CPI: {rate:.1f}%{period}</title></circle>')
    parts.append('</g>')
    if start:
        parts.append(f'<text class="era-label" x="{left+(sx-left)/2:.2f}" y="{height-20}" text-anchor="middle">Before Sutcliffe’s first budget</text>')
    parts.append(f'<text class="era-label" x="{sx+(width-right-sx)/2:.2f}" y="{height-20}" text-anchor="middle">Sutcliffe budgets · 2023–2026</text></svg>')
    return ''.join(parts)


rows = []
for row in data['years']:
    year, rate = row['year'], row['increase_pct']
    gap = round(rate - upper, 2)
    firm = row['commitment'] == 'Firm commitment'
    historical = year < 2023
    assessment = 'Historical context' if historical else 'Within promised range' if firm and gap <= 0 else 'Above later target' if gap > 0 else 'Within later target'
    delta = 'Outside promise period' if historical else 'At 2.5% upper limit' if gap == 0 else f'+{gap:g} percentage points'
    benchmark = '—' if historical else f'2–2.5%<br><small>{e(row["commitment"])}</small>'
    cpi_rate = inflation['inflation_pct'][str(year)]
    cpi_period = 'Jan–Sep, provisional' if year == 2026 else 'Annual average change'
    rows.append(f'''<tr><th scope="row">{year}</th><td>{rate:g}%</td><td>{cpi_rate:.1f}%<br><small>{cpi_period}</small></td><td>{benchmark}</td><td>{assessment}<br><small>{delta}</small></td><td>{source_link(row['source'], 'Tax source ↗')} · {source_link('monthly_cpi' if year == 2026 else 'annual_cpi', 'CPI ↗')}<br><small>{e(row['note'])}</small></td></tr>''')

with (ROOT / 'data/property-tax.csv').open('w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['year', 'adopted_overall_increase_pct', 'campaign_lower_pct', 'campaign_upper_pct', 'commitment_type', 'gap_to_upper_percentage_points', 'source_url', 'note', 'ottawa_inflation_pct', 'inflation_period', 'cpi_source_url'])
    for r in data['years']:
        historical = r['year'] < 2023
        partial = r['year'] == 2026
        writer.writerow([r['year'], r['increase_pct'], '' if historical else promise['lower_pct'], '' if historical else upper, r['commitment'], '' if historical else round(r['increase_pct'] - upper, 2), sources[r['source']]['url'], r['note'], inflation['inflation_pct'][str(r['year'])], 'Jan–Sep vs Jan–Sep previous year (provisional)' if partial else 'Annual average vs previous annual average', inflation['monthly_source'] if partial else inflation['annual_source']])

term_records = [r for r in data['years'] if r['year'] >= 2023]
cumulative_rows, cumulative_summaries = [], []
with (ROOT / 'data/property-tax-cumulative.csv').open('w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['baseline_year', 'year', 'compounded_tax_increase_pct', 'cumulative_ottawa_cpi_pct', 'cpi_endpoint', 'method'])
    for scope, records in [('all', data['years']), ('term', term_records)]:
        baseline = records[0]['year'] - 1
        totals = cumulative_values(records)
        final = totals[2026]
        cumulative_summaries.append(f'<div class="cumulative-summary" data-summary="{scope}" hidden><p><strong>Since {baseline}</strong> · through the 2026 budget / latest CPI</p><p><strong>Tax index: +{final["tax"]:.1f}%</strong><span class="inflation-summary"> · <strong>Consumer prices: +{final["cpi"]:.1f}%*</strong></span></p><p class="small">*CPI ends at the Jan–Sep 2026 average; baseline is the {baseline} annual average. Tax index compounds published budget increases; it is not an individual bill.</p></div>')
        for r in records:
            year = r['year']
            values = totals[year]
            endpoint = 'Jan–Sep average (provisional)' if year == 2026 else 'Annual average'
            writer.writerow([baseline, year, round(values['tax'], 6), round(values['cpi'], 6), endpoint, 'Tax: product of (1 + annual rate/100) minus 1; CPI: endpoint index / baseline annual index minus 1; both × 100'])
            cumulative_rows.append(f'<tr><td>{baseline}</td><th scope="row">{year}</th><td>{values["tax"]:.2f}%</td><td>{values["cpi"]:.2f}%</td><td>{endpoint}</td></tr>')

source_items = ''.join(f'<li>{source_link(k)} · {e(s["date"])}<br><small>Location: {e(s["locator"])}. {e(s["review_note"])}</small></li>' for k, s in sources.items())
# Savings is withheld from the public page; preserve its builder and exports for research.
build_savings()
# EV charging is also withheld; retain its analysis and exports for research.
build_ev_charging()
page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sutcliffe’s 2022 promises · Ottawa Visuals</title>
<meta name="description" content="Sutcliffe’s 2022 commitments and results: property taxes, transit fares, bus reliability and housing delivery, with historical trends and source notes.">
<link rel="icon" href="../assets/img/avatar.png"><script>try{{document.documentElement.dataset.theme=localStorage.getItem('ov-theme')||'light'}}catch(e){{document.documentElement.dataset.theme='light'}}</script>
<link rel="stylesheet" href="promises.css"><link rel="stylesheet" href="../assets/site-theme.css"><script defer src="../assets/site-theme.js"></script><script defer src="promises.js"></script><script defer src="transit-fares.js"></script><script defer src="bus-reliability.js"></script><script defer src="housing.js"></script>
</head><body><a class="skip" href="#main">Skip to report</a>
<header class="topbar"><a class="brand" href="../index.html"><span>Ottawa Visuals <small>2022 commitments</small></span></a><a href="../index.html">All reports ↗</a></header>
<main id="main"><header><p class="eyebrow">Mark Sutcliffe · First term, 2022–2026</p><h1>The promises.<br>The years since.</h1><p class="lede">Track the original 2022 campaign commitments against Ottawa’s published results, one topic at a time.</p><p class="small">Reviewed October 24, 2026 · Taxes, fares, bus reliability &amp; housing</p></header>
<nav aria-label="On this page"><a href="#property-tax">Property taxes</a><a href="#transit-fares">Transit fares</a><a href="#bus-reliability">Bus reliability</a><a href="#housing">Housing</a><a href="#method">Sources &amp; method</a><a href="../Budget/budget.html">Explore the budget ↗</a></nav>
<section id="property-tax" class="card" aria-labelledby="tax-title"><p class="eyebrow">01 · Affordability</p><h2 id="tax-title">Property-tax increases</h2>
<div class="promise"><p><strong>The 2022 commitment</strong></p><p>Limit increases to <strong>2–2.5% in 2023 and 2024</strong>; <strong>target the same range in 2025 and 2026</strong>.</p><p class="small">Paraphrase of the October 5, 2022 financial framework. {source_link('campaign', 'Read the campaign coverage ↗')}</p></div>
<p class="verdict"><strong>The 2023–24 commitment was met.</strong> Both years came in at 2.5%. Increases of 3.9% in 2025 and 3.75% in 2026 exceeded the later-year target.</p>
<p>These are the published <strong>overall municipal increases</strong> in Council-approved budgets. The comparison preserves the distinction between a firm commitment and a later target.</p>
<div class="chart-controls" hidden><div class="range-buttons" role="group" aria-label="Chart years"><button type="button" data-range="all" aria-pressed="true">2013–2026</button><button type="button" data-range="term" aria-pressed="false">Sutcliffe · 2023–2026</button></div><div class="range-buttons" role="group" aria-label="Chart measure"><button type="button" data-measure="annual" aria-pressed="true">Annual</button><button type="button" data-measure="cumulative" aria-pressed="false">Cumulative</button></div><label><input type="checkbox" id="show-inflation" checked> Show Ottawa inflation</label></div>
{''.join(cumulative_summaries)}
<div class="legend"><span><i class="key"></i>Municipal tax increase</span><span><i class="key historical"></i>Before this term</span><span class="inflation-legend"><i class="key inflation"></i>Ottawa CPI inflation</span><span class="reference-legend"><i class="key reference"></i>2% and 2.5% references</span></div>
<div class="chart-scroll" id="chart-all" tabindex="0" role="region" aria-label="Tax and inflation chart, 2013–2026; scroll horizontally on small screens">{svg_chart(data['years'], 'history')}</div>
<div class="chart-scroll term-view" id="chart-term" hidden tabindex="0" role="region" aria-label="Tax and inflation chart, 2023–2026; scroll horizontally on small screens">{svg_chart([r for r in data['years'] if r['year'] >= 2023], 'term')}</div>
<div class="chart-scroll" id="chart-all-cumulative" hidden tabindex="0" role="region" aria-label="Cumulative tax and inflation since 2012; scroll horizontally on small screens">{svg_chart(data['years'], 'history-cumulative', True)}</div>
<div class="chart-scroll term-view" id="chart-term-cumulative" hidden tabindex="0" role="region" aria-label="Cumulative tax and inflation since 2022; scroll horizontally on small screens">{svg_chart(term_records, 'term-cumulative', True)}</div>
<p class="small annual-note">Years run horizontally; increases (%) run vertically. Bars start at zero. The shaded 2023–2026 period contains the 2% and 2.5% reference lines: a firm range in 2023–24, a target in 2025–26. Earlier budgets are context only. Scroll the chart sideways on small screens.</p>
<p class="small cumulative-note" hidden>Cumulative tax increases are compounded, not added. The baseline is 2012 for the full history or 2022 for Sutcliffe’s budgets. CPI compares each endpoint index directly with that baseline’s annual average. Annual 2% and 2.5% references apply only in Annual view. Scroll sideways on small screens.</p>
<p class="small inflation-note annual-note"><strong>Inflation:</strong> Ottawa-Gatineau, Ontario part, all-items CPI. 2013–2025 use annual-average changes. The hollow 2026 point and dashed segment show <strong>Jan–Sep 2026 versus Jan–Sep 2025 ({inflation['inflation_pct']['2026']:.1f}%, provisional)</strong>, not full-year inflation. CPI measures consumer prices, not the City’s operating costs.</p>
<p class="small cumulative-note" hidden><strong>CPI’s 2026 endpoint is partial-year:</strong> Jan–Sep 2026 average versus the baseline annual average. We do not compound the annual-mode 2026 year-to-date rate onto the full 2025 average. Taxes include the full 2026 budget increase. CPI measures consumer prices, not municipal costs.</p>
<details><summary>Exact annual values and evidence</summary><p class="small">On narrow screens, scroll the table horizontally. The table and CSV always include all years, regardless of chart controls.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Annual property-tax comparison table"><table style="min-width:900px"><caption>Published municipal increases, Ottawa inflation and the original 2022 benchmark.</caption><thead><tr><th scope="col">Year</th><th scope="col">Tax increase</th><th scope="col">Ottawa CPI</th><th scope="col">2022 benchmark</th><th scope="col">Comparison</th><th scope="col">Evidence &amp; context</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>
<details><summary>Cumulative values and baselines</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Cumulative tax and inflation table"><table style="min-width:620px"><caption>Both cumulative periods; tax rates compounded, CPI measured directly from baseline.</caption><thead><tr><th scope="col">Baseline year</th><th scope="col">Year</th><th scope="col">Tax index increase</th><th scope="col">CPI increase</th><th scope="col">CPI endpoint</th></tr></thead><tbody>{''.join(cumulative_rows)}</tbody></table></div><p><a href="data/property-tax-cumulative.csv" download>Download cumulative CSV ↓</a></p></details>
<p><strong>Why 3.9% in 2025?</strong> The citywide and police levies rose 2.9%, while the transit levy rose 8%. Their weighted overall impact was published as 3.9%. Transit fare increases are a separate charge and are not added to this property-tax comparison.</p>
<p class="small">Your own bill can change differently because of property assessment, location, tax class and applicable levies. Water, wastewater, stormwater, garbage fees and provincial education taxes are outside this municipal increase comparison. These figures do not measure growth in the City’s total tax revenue.</p>
<div class="downloads"><a href="data/property-tax.csv" download>Download CSV ↓</a><a href="data/property-tax.json" download>Tax data &amp; sources ↓</a><a href="data/inflation.json" download>CPI inputs &amp; formula ↓</a></div></section>
{build_transit_fares()}
{build_bus_reliability()}
{build_housing()}
<section id="method" class="card"><h2>Sources &amp; method</h2><details open><summary>What is being compared?</summary><p>For 2023–2026, each budget year’s published overall municipal property-tax increase is compared with the upper end of the original campaign range, 2.5%. The gap equals adopted increase minus 2.5, in percentage points. The 2013–2022 bars are historical context and receive no promise assessment.</p><p>Inflation = (annual-average CPI / previous annual-average CPI − 1) × 100. For the incomplete 2026 year, both averages use January–September. Inflation is rounded to one decimal in tax chart titles and the tax table; the CSV retains six decimals. Fare changes use two decimals in the display. No inflation adjustment or cumulative household bill estimate is applied. Same-year inflation was not fully known when budgets were adopted.</p><p>Council approves budgets; this page evaluates the campaign commitment without attributing every budget decision solely to the mayor. Historical rates follow the City’s own published comparison series; individual bills and separate fees can differ. Transit-fare methodology and source notes are in the <a href="#transit-fares">fare section</a>.</p></details>
<details><summary>Evidence limits and review process</summary><p>The campaign benchmark comes from reporting published during the 2022 campaign; an archived original platform has not yet been obtained. The campaign article’s opening paragraph contains a conflicting number, while its headline and detailed framework agree on 2–2.5% and distinguish the later target.</p><p>2013–2023 tax increases come from the City’s historical comparison table. The 2024 and 2025 adoption figures are supported by contemporary councillor accounts; 2026 uses the City’s adoption announcement. CPI is retrieved from Statistics Canada tables 18-10-0005-01 and 18-10-0004-01; inputs and response hashes are retained. These are reviewed snapshots, not an automatic feed or independently audited household tax bills. No 2026 reelection promises are included.</p></details>
<details><summary>Documents and source locations</summary><ol class="source-list">{source_items}</ol><p><a href="README.md">Review and rebuild notes</a></p></details></section>
</main><footer>Ottawa Visuals · Independent reporting · <a href="../index.html">All reports</a></footer></body></html>'''
(ROOT / 'promises.html').write_text(page, encoding='utf-8')
print('Built Promises/promises.html and tax, fare, bus KPI, housing and retained EV/savings research exports')

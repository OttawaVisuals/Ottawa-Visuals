"""Build static, offline-readable promise comparison and downloadable CSV. Stdlib only."""
import csv
import json
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'data/property-tax.json').read_text(encoding='utf-8'))
promise = data['promise']
upper = promise['upper_pct']
sources = data['sources']

def source_link(key, label=None):
    s = sources[key]
    return f'<a href="{e(s["url"], quote=True)}">{e(label or s["title"])}</a>'

chart, rows = [], []
for row in data['years']:
    year, rate = row['year'], row['increase_pct']
    gap = round(rate - upper, 2)
    firm = row['commitment'] == 'Firm commitment'
    assessment = 'Within promised range' if firm and gap <= 0 else 'Above later target' if gap > 0 else 'Within later target'
    delta = 'At 2.5% upper limit' if gap == 0 else f'+{gap:g} percentage points'
    chart.append(f'''<div class="chart-row {'' if firm else 'target'}"><div class="year">{year}<small>{e(row['commitment'])}</small></div><div class="plot" aria-hidden="true"><span class="band"></span><span class="bar" style="width:{rate / 5 * 100:g}%"></span><span class="marker"></span></div><div class="result"><strong>{rate:g}%</strong><small>{delta}</small></div></div>''')
    rows.append(f'''<tr><th scope="row">{year}</th><td>{rate:g}%</td><td>2–2.5%<br><small>{e(row['commitment'])}</small></td><td>{assessment}<br><small>{delta}</small></td><td>{source_link(row['source'], 'Source ↗')}<br><small>{e(row['note'])}</small></td></tr>''')

with (ROOT / 'data/property-tax.csv').open('w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['year', 'adopted_overall_increase_pct', 'campaign_lower_pct', 'campaign_upper_pct', 'commitment_type', 'gap_to_upper_percentage_points', 'source_url', 'note'])
    for r in data['years']:
        writer.writerow([r['year'], r['increase_pct'], promise['lower_pct'], upper, r['commitment'], round(r['increase_pct'] - upper, 2), sources[r['source']]['url'], r['note']])

source_items = ''.join(f'<li>{source_link(k)} · {e(s["date"])}<br><small>Location: {e(s["locator"])}. {e(s["review_note"])}</small></li>' for k, s in sources.items())
page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sutcliffe’s 2022 promises · Ottawa Visuals</title>
<meta name="description" content="Compare Ottawa’s annual property-tax increases in 2023–2026 with Mark Sutcliffe’s original 2022 campaign commitment and later-year target.">
<link rel="icon" href="../assets/img/avatar.png"><script>try{{document.documentElement.dataset.theme=localStorage.getItem('ov-theme')||'light'}}catch(e){{document.documentElement.dataset.theme='light'}}</script>
<link rel="stylesheet" href="promises.css"><link rel="stylesheet" href="../assets/site-theme.css"><script defer src="../assets/site-theme.js"></script>
</head><body><a class="skip" href="#main">Skip to report</a>
<header class="topbar"><a class="brand" href="../index.html"><span>Ottawa Visuals <small>2022 commitments</small></span></a><a href="../index.html">All reports ↗</a></header>
<main id="main"><header><p class="eyebrow">Mark Sutcliffe · First term, 2022–2026</p><h1>The promises.<br>The years since.</h1><p class="lede">Track the original 2022 campaign commitments against Ottawa’s published results, one topic at a time.</p><p class="small">Reviewed October 24, 2026 · First topic: property taxes</p></header>
<nav aria-label="On this page"><a href="#property-tax">Property taxes</a><a href="#method">Sources &amp; method</a><a href="../Budget/budget.html">Explore the budget ↗</a></nav>
<section id="property-tax" class="card" aria-labelledby="tax-title"><p class="eyebrow">01 · Affordability</p><h2 id="tax-title">Property-tax increases</h2>
<div class="promise"><p><strong>The 2022 commitment</strong></p><p>Limit increases to <strong>2–2.5% in 2023 and 2024</strong>; <strong>target the same range in 2025 and 2026</strong>.</p><p class="small">Paraphrase of the October 5, 2022 financial framework. {source_link('campaign', 'Read the campaign coverage ↗')}</p></div>
<p class="verdict"><strong>The 2023–24 commitment was met.</strong> Both years came in at 2.5%. Increases of 3.9% in 2025 and 3.75% in 2026 exceeded the later-year target.</p>
<p>These are the published <strong>overall municipal increases</strong> in Council-approved budgets. The comparison preserves the distinction between a firm commitment and a later target.</p>
<div class="legend"><span><i class="key"></i>Adopted increase</span><span><i class="key range"></i>2023–24 promised range</span><span><i class="key target"></i>2025–26 target range</span></div>
<div role="img" aria-label="Annual municipal property-tax increases: 2023, 2.5 percent; 2024, 2.5 percent; 2025, 3.9 percent; 2026, 3.75 percent. The campaign range was 2 to 2.5 percent, firm for the first two years and a target for the final two.">
{''.join(chart)}<div class="axis" aria-hidden="true"><span></span><div class="ticks"><span>0%</span><span>1%</span><span>2%</span><span>3%</span><span>4%</span><span>5%</span></div><span></span></div></div>
<p class="small">Each bar starts at zero. Shading marks 2–2.5%; the vertical line marks 2.5%. Differences are percentage points, not percent changes.</p>
<details><summary>Exact annual values and evidence</summary><p class="small">On narrow screens, scroll the table horizontally.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Annual property-tax comparison table"><table style="min-width:760px"><caption>Published overall municipal increases, compared with the original 2022 benchmark.</caption><thead><tr><th scope="col">Year</th><th scope="col">Adopted</th><th scope="col">2022 benchmark</th><th scope="col">Comparison</th><th scope="col">Evidence &amp; context</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>
<p><strong>Why 3.9% in 2025?</strong> The citywide and police levies rose 2.9%, while the transit levy rose 8%. Their weighted overall impact was published as 3.9%. Transit fare increases are a separate charge and are not added to this property-tax comparison.</p>
<p class="small">Your own bill can change differently because of property assessment, location, tax class and applicable levies. Water, wastewater, stormwater, garbage fees and provincial education taxes are outside this municipal increase comparison. These figures do not measure growth in the City’s total tax revenue.</p>
<div class="downloads"><a href="data/property-tax.csv" download>Download CSV ↓</a><a href="data/property-tax.json" download>Data &amp; source notes ↓</a></div></section>
<section id="method" class="card"><h2>Sources &amp; method</h2><details open><summary>What is being compared?</summary><p>Each budget year’s published overall municipal property-tax increase is compared with the upper end of the original campaign range, 2.5%. The gap equals adopted increase minus 2.5, in percentage points. No inflation adjustment or cumulative household bill estimate is applied.</p><p>The 2022 budget predates this term and is excluded. The four annual budgets shown are 2023–2026. Council approves budgets; this page evaluates the campaign commitment without attributing every budget decision solely to the mayor.</p></details>
<details><summary>Evidence limits and review process</summary><p>The campaign benchmark comes from reporting published during the 2022 campaign; an archived original platform has not yet been obtained. The campaign article’s opening paragraph contains a conflicting number, while its headline and detailed framework agree on 2–2.5% and distinguish the later target.</p><p>2023 adoption is confirmed by CBC’s retrospective review and cross-checked against the City’s draft. The 2024 and 2025 adoption figures are supported by contemporary councillor accounts; 2026 uses the City’s adoption announcement. These are manually reviewed sources, not an automatic feed or independently audited household tax bills. No 2026 reelection promises are included.</p></details>
<details><summary>Documents and source locations</summary><ol class="source-list">{source_items}</ol><p><a href="README.md">Review and rebuild notes</a></p></details></section>
</main><footer>Ottawa Visuals · Independent reporting · <a href="../index.html">All reports</a></footer></body></html>'''
(ROOT / 'promises.html').write_text(page, encoding='utf-8')
print('Built Promises/promises.html and data/property-tax.csv')

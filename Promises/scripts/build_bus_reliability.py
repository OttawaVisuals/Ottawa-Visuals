"""Reuse the audited official KPI archive; never rebuild or change collector data."""
import csv
import hashlib
import json
from datetime import date
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
INPUT = REPO / 'OC_Transpo/kpi_history/kpi_series.csv'
METRICS = [
    ('trips_delivered', 'Service delivered', 'Share of scheduled bus trips that operated. This does not measure punctuality or the amount of service scheduled.', 90),
    ('punctuality_less_frequent_routes', 'Punctuality · less-frequent routes', 'Departures at major stops between 1 minute early and 5 minutes late, on routes running every 16 minutes or less often. The archive does not provide a consistent early/late split.', 60),
    ('regularity_frequent_routes', 'Regularity · frequent routes', 'Share meeting the official spacing measure on frequent routes. This measures headway regularity, not whether each departure matched its timetable.', 70)
]
CAMPAIGN = 'https://ottawa.citynews.ca/2022/09/22/sutcliffe-vows-to-equally-respect-motorists-cyclists-and-pedestrians-with-transportation-plan-5855497/'


def build():
    with INPUT.open(encoding='utf-8-sig', newline='') as f:
        raw = list(csv.DictReader(f))
    source_links = json.loads((ROOT / 'data/bus-source-links.json').read_text(encoding='utf-8'))
    # Public URL lookup retained from the existing scraper manifest; no dependency
    # on its ignored local archive or the original PDF downloads when rebuilding.
    def source_url(r):
        url = source_links[r['source_file']]
        return url + '#page=' + r['page'] if url.startswith('https:') else url

    records, targets = [], {}
    for metric, label, definition, minimum in METRICS:
        target = next(r for r in raw if r['metric'] == metric and r['mode'] == 'bus' and r['breakdown'] == 'target' and r['period'] == 'edition 2026')
        targets[metric] = {**target, 'value': float(target['value']), 'source_url': source_url(target)}
        for r in raw:
            if r['metric'] == metric and r['mode'] == 'bus' and not r['breakdown'] and (r['period_type'] == 'year' or r['period_type'] == 'month' and r['period'] >= '2022-01'):
                records.append({**r, 'value': float(r['value']), 'source_url': source_url(r)})
    data = {'reviewed': '2026-10-24', 'archive_sha256': hashlib.sha256(INPUT.read_bytes()).hexdigest(),
            'archive_path': 'OC_Transpo/kpi_history/kpi_series.csv', 'promise_source': CAMPAIGN,
            'scope': 'Official published bus KPIs only; no live predictions. Annual and monthly periods are separate. Latest monthly observation in this archive is April 2026; no full-year 2026 result inferred.',
            'metrics': [{'metric': m, 'label': l, 'definition': d} for m,l,d,_ in METRICS], 'targets': targets, 'records': records}
    (ROOT / 'data/bus-reliability.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    with (ROOT / 'data/bus-reliability.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    def chart(metric, label, minimum, mode):
        monthly = mode == 'monthly'
        points = [r for r in records if r['metric'] == metric and r['period_type'] == ('month' if monthly else 'year')]
        lookup = {r['period']:r for r in points}
        if monthly:
            periods = [f'{y}-{m:02}' for y in range(2022,2027) for m in range(1,13) if '2022-08' <= f'{y}-{m:02}' <= '2026-04']
        else:
            periods = ['2023','2024','2025']
        w,h,left,right,top,bottom = (1050 if monthly else 680), 380, 55, 75, 42, 60
        pw,ph = w-left-right,h-top-bottom
        low = minimum if monthly else 0
        x = lambda i:left+pw/len(periods)*(i+.5)
        y = lambda v:top+ph*(1-(v-low)/(100-low))
        target = targets[metric]['value']
        name = metric+'-'+mode
        bits = [f'<svg class="bus-svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{name}-title {name}-desc"><title id="{name}-title">{e(label)} · {mode}</title><desc id="{name}-desc">Official bus KPI percentages. Missing observations are left blank. {"Monthly line uses a narrowed vertical scale of "+str(low)+" to 100 percent." if monthly else "Annual bars start at zero."} The dashed reference is the May 2026 scorecard target, not a numerical campaign promise.</desc><text class="axis-title" x="{left}" y="18">Share (%)'+(f' · scale {low}–100' if monthly else '')+'</text>']
        for tick in range(low,101,5 if monthly else 20):
            bits.append(f'<line class="gridline" x1="{left}" x2="{w-right}" y1="{y(tick):.2f}" y2="{y(tick):.2f}"/><text class="tick" x="{left-8}" y="{y(tick)+4:.2f}" text-anchor="end">{tick}%</text>')
        bits.append(f'<line class="bus-target" x1="{left}" x2="{w-right}" y1="{y(target):.2f}" y2="{y(target):.2f}"/><text class="tick" x="{w-right+6}" y="{y(target)+4:.2f}">{target:g}%</text>')
        previous = None
        for i, period in enumerate(periods):
            r = lookup.get(period)
            if not monthly or period.endswith(('-01','-07')) or i in (0,len(periods)-1):
                label_period = period if not monthly else date.fromisoformat(period+'-01').strftime('%b %y')
                bits.append(f'<text class="tick" x="{x(i):.2f}" y="{y(low)+24:.2f}" text-anchor="middle">{label_period}</text>')
            if r is None:
                previous = None
                if not monthly:
                    bits.append(f'<text class="tick" x="{x(i):.2f}" y="{y(0)-12:.2f}" text-anchor="middle">Not available</text>')
                continue
            value = r['value']
            title = f'{period}: {value:g}%; source: {r["source_file"]}, location {r["page"]}'
            if monthly:
                if previous is not None:
                    bits.append(f'<line class="bus-line" x1="{previous[0]:.2f}" y1="{previous[1]:.2f}" x2="{x(i):.2f}" y2="{y(value):.2f}"/>')
                bits.append(f'<circle class="bus-point" cx="{x(i):.2f}" cy="{y(value):.2f}" r="3.5"><title>{e(title)}</title></circle>')
                previous = (x(i),y(value))
            else:
                bw = pw/len(periods)*.48
                bits.append(f'<rect class="bus-column" x="{x(i)-bw/2:.2f}" y="{y(value):.2f}" width="{bw:.2f}" height="{y(0)-y(value):.2f}"><title>{e(title)}</title></rect><text class="bus-label" x="{x(i):.2f}" y="{y(value)-9:.2f}" text-anchor="middle">{value:g}%</text>')
        if monthly:
            bits.append(f'<text class="tick" x="{left}" y="{h-7}">Blank periods = no observation in this archive; gaps are not connected.</text>')
        bits.append('</svg>')
        hidden = '' if metric == METRICS[0][0] and not monthly else ' hidden'
        return f'<div class="bus-chart chart-scroll" data-bus-metric="{metric}" data-bus-period="{mode}"{hidden} tabindex="0" role="region" aria-label="{e(label)} {mode} chart; scroll horizontally on small screens">'+''.join(bits)+'</div>'

    charts = ''.join(chart(m,l,minimum,mode) for m,l,_,minimum in METRICS for mode in ['annual','monthly'])
    rows = ''.join(f'<tr><th scope="row">{e(next(l for m,l,_,_ in METRICS if m==r["metric"]))}</th><td>{r["period"]}</td><td>{r["period_type"]}</td><td>{r["value"]:g}%</td><td><a href="{e(r["source_url"],quote=True)}">Source ↗</a><br><small>{e(r["source_file"])} · {"sheet" if "kpi_snapshots/" in r["source_file"] else "PDF page"} {e(r["page"])}</small></td></tr>' for r in sorted(records,key=lambda r:(r['metric'],r['period_type'],r['period'])))
    definitions = ''.join(f'<li><strong>{e(label)}:</strong> {e(definition)}</li>' for _,label,definition,_ in METRICS)
    target_notes = ''.join(f'<li><strong>{e(label)}:</strong> {targets[m]["value"]:g}%. {e(targets[m]["note"] or "No completion date extracted for this metric.")} <a href="{e(targets[m]["source_url"],quote=True)}">May 2026 scorecard · PDF p. {targets[m]["page"]}</a></li>' for m,label,_,_ in METRICS)
    options = ''.join(f'<option value="{m}">{e(l)}</option>' for m,l,_,_ in METRICS)
    first = [r for r in records if r['metric']=='trips_delivered' and r['period_type']=='year']
    first.sort(key=lambda r:r['period'])
    delivery_change = first[-1]['value']-first[0]['value']
    assert round(delivery_change,1)==-.8, 'Review narrative after KPI archive changes'
    assert next(r['value'] for r in records if r['metric']=='punctuality_less_frequent_routes' and r['period']=='2023')==74.5
    assert next(r['value'] for r in records if r['metric']=='punctuality_less_frequent_routes' and r['period']=='2025')==72
    assert {(r['metric'],r['period']):r['value'] for r in records if r['period_type']=='year'} == {
        ('trips_delivered','2023'):97.8, ('trips_delivered','2024'):98, ('trips_delivered','2025'):97,
        ('punctuality_less_frequent_routes','2023'):74.5, ('punctuality_less_frequent_routes','2024'):74, ('punctuality_less_frequent_routes','2025'):72,
        ('regularity_frequent_routes','2024'):82, ('regularity_frequent_routes','2025'):82
    }, 'Review the annual summary when observations change'
    return f'''<section id="bus-reliability" class="card" aria-labelledby="bus-title"><p class="eyebrow">03 · Transit service</p><h2 id="bus-title">Bus reliability</h2>
<div class="promise"><p><strong>The 2022 commitment</strong></p><p>Improve bus service reliability and modernize routing and schedules for post-pandemic travel.</p><p class="small">Paraphrase of the September 22, 2022 transportation platform coverage. <a href="{CAMPAIGN}">Read the source ↗</a></p></div>
<p class="verdict"><strong>The available annual KPIs show no sustained improvement.</strong> Service delivered fell from 97.8% in 2023 to 97% in 2025; punctuality fell from 74.5% to 72%. Frequent-route regularity was 82% in both 2024 and 2025.</p>
<p class="small">This is a performance comparison, not a pass/fail verdict on the whole transit promise. The 2022 commitment did not specify a numerical threshold. These KPIs do not establish the effect of the mayor’s decisions or assess the routing changes themselves.</p>
<div class="bus-controls" hidden><label for="bus-metric">Measure<select id="bus-metric">{options}</select></label><div class="range-buttons" role="group" aria-label="Bus KPI reporting period"><button type="button" data-bus-mode="annual" aria-pressed="true">Annual · 2023–25</button><button type="button" data-bus-mode="monthly" aria-pressed="false">Monthly history</button></div></div>
<p id="bus-summary" class="small" aria-live="polite">Service delivered: 97.8% (2023) → 97% (2025), down 0.8 percentage points.</p>
<div class="legend"><span><i class="key"></i>Official bus KPI</span><span><i class="key reference"></i>May 2026 scorecard target</span></div>{charts}
<p class="small" id="bus-definition">{METRICS[0][2]}</p><p class="small">Scroll charts sideways on small screens. Annual bars start at zero; monthly lines use a clearly labelled narrower vertical scale to show variation.</p>
<p class="small"><strong>Coverage matters:</strong> annual observations cover 2023–2025 (regularity starts in 2024); no complete 2022 annual baseline or 2026 annual result is present. Monthly observations in this archive end in <strong>April 2026</strong>. Delivery also has Aug 2022–Aug 2023 observations; punctuality resumes in Jan 2025 and regularity starts in Apr 2025. Missing months stay blank. This is the existing archive, not a claim that no newer publication exists.</p>
<details><summary>Definitions and targets</summary><ul>{definitions}</ul><p>Targets below are references from the latest scorecard edition in this archive (May 2026), not promises made in the 2022 campaign or assumed historical deadlines.</p><ul>{target_notes}</ul></details>
<details><summary>Exact observations and source locations</summary><p class="small">Annual and monthly values are separate records. They are not averaged together. Source notes, publication dates, revisions and extraction methods are retained in the JSON/CSV.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Official bus KPI observations"><table style="min-width:850px"><thead><tr><th scope="col">Measure</th><th scope="col">Period</th><th scope="col">Type</th><th scope="col">Value</th><th scope="col">Source location</th></tr></thead><tbody>{rows}</tbody></table></div></details>
<details><summary>Methodology and limits</summary><p>Reuses <a href="../OC_Transpo/kpi_history/kpi_series.csv">the existing reconciled official KPI series</a>. Latest-publication selection and precision/revision handling follow the <a href="../OC_Transpo/README.md#kpi-history-extracted-from-the-pdfs">existing extraction methodology</a>; conflicting source values remain in the export’s other_values field. No input observations or collector files are changed. The input SHA-256 is retained for reproducibility.</p><p>Monthly time gaps are not connected and no annual or year-to-date values are reconstructed from incomplete months. Pandemic-era punctuality observations from 2020–21 remain on the full KPI page; they are not a clean 2022 baseline. The scorecard and monthly file can differ in precision; monthly averages do not replace published annual results. The snapshot source_file column uses a legacy .pdf suffix for spreadsheet extracts; links here resolve to the actual committed .xlsx, with its worksheet identified.</p><p>Live GTFS predictions are excluded because their sampling, early-departure handling and definitions differ from official KPIs. The archive does not support a consistent early/on-time/late split for this period. Service delivered is a percentage of the timetable, not service hours, route coverage or customer satisfaction. Regularity is a distinct measure on frequent routes.</p></details>
<div class="downloads"><a href="data/bus-reliability.csv" download>Bus KPI CSV ↓</a><a href="data/bus-reliability.json" download>Data, targets &amp; source notes ↓</a><a href="../OC_Transpo/octranspo_kpis.html">Full OC Transpo dashboard ↗</a></div><script id="bus-series-data" type="application/json">{json.dumps(data,ensure_ascii=False).replace('<','&lt;')}</script></section>'''

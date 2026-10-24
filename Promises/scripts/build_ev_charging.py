"""Build EV context from the retained locator snapshot, not a pledge score."""
import csv
import json
import math
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    d = json.loads((ROOT / 'data/ev-charging.json').read_text(encoding='utf-8'))
    evidence = json.loads((ROOT / 'data/ev-charging-sources.json').read_text(encoding='utf-8'))
    stations = d['stations']
    def link(key, label='Source ↗'):
        return f'<a href="{e(evidence["sources"][key]["url"], quote=True)}">{e(label)}</a>'
    fields = ['id', 'station_name', 'street_address', 'city', 'ward', 'latitude', 'longitude', 'hydro_named', 'open_date', 'date_last_confirmed', 'updated_at', 'status_code', 'access_code', 'restricted_access', 'access_days_time', 'owner_type_code', 'ev_network', 'ev_level1_evse_num', 'ev_level2_evse_num', 'ev_dc_fast_num', 'ports']
    with (ROOT / 'data/ev-charging.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: s[k] for k in fields} for s in stations)
    projection = lambda lon, lat: (math.radians(lon), -math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))
    all_xy = [projection(*pt) for w in d['wards'] for ring in w['rings'] for pt in ring]
    xmin, xmax = min(p[0] for p in all_xy), max(p[0] for p in all_xy)
    ymin, ymax = min(p[1] for p in all_xy), max(p[1] for p in all_xy)
    scale = min(740 / (xmax - xmin), 480 / (ymax - ymin))
    def xy(lon, lat):
        x, y = projection(lon, lat)
        return 30 + (740 - (xmax - xmin) * scale) / 2 + (x - xmin) * scale, 25 + (480 - (ymax - ymin) * scale) / 2 + (y - ymin) * scale
    outlines = ''
    for ward in d['wards']:
        path = ' '.join('M' + ' L'.join(f'{x:.2f},{y:.2f}' for x, y in [xy(*pt) for pt in ring]) + ' Z' for ring in ward['rings'])
        outlines += f'<path class="ev-ward" d="{path}"><title>Ward {ward["ward"]}</title></path>'
    charts, summaries, exports = [], [], []
    for scope in ['hydro', 'all']:
        selected = [s for s in stations if s['hydro_named'] or scope == 'all']
        label = 'Hydro-named subset' if scope == 'hydro' else 'All retained public records'
        hidden = ' hidden' if scope == 'all' else ''
        ports = sum(s['ports'] or 0 for s in selected)
        recent = sum(bool(s['open_date'] and '2023-01-01' <= s['open_date'] <= d['reviewed']) for s in selected)
        restricted = sum(bool(s['restricted_access']) for s in selected)
        summaries.append(f'<div class="ev-summary" data-ev-group="{scope}"{hidden}><strong>{len(selected)} station records · {ports} listed ports</strong><p class="small">{label} · {recent} records have dates in 2023–2026 · {restricted} carry a restricted-access flag. Counts describe the current snapshot.</p></div>')
        dots = ''
        for s in sorted(selected, key=lambda s: s['hydro_named']):
            x, y = xy(s['longitude'], s['latitude'])
            dots += f'<circle class="ev-dot {"hydro" if s["hydro_named"] else "other"}" cx="{x:.2f}" cy="{y:.2f}" r="{4.5 if s["hydro_named"] else 2.8}"><title>{e(s["station_name"])} · {e(s["street_address"])} · {s["ports"] if s["ports"] is not None else "unknown"} ports · listed date {s["open_date"] or "unknown"}</title></circle>'
        map_svg = f'<svg class="ev-map" viewBox="0 0 800 540" role="img" aria-labelledby="ev-map-title-{scope}"><title id="ev-map-title-{scope}">{label}, within Ottawa’s 2022 wards; exact addresses and access notes in the table</title>{outlines}{dots}<text x="30" y="528" class="ev-tick">North ↑ · current locator records, not live availability</text></svg>'
        values = [sum(bool(s['open_date'] and s['open_date'] <= f'{year}-12-31') for s in selected) for year in range(2022, 2027)]
        ymax_chart = max(5, math.ceil(max(values) / 5) * 5)
        sy = lambda n: 250 - n / ymax_chart * 190
        svg = [f'<svg class="ev-chart" viewBox="0 0 800 325" role="img" aria-labelledby="ev-chart-title-{scope}"><title id="ev-chart-title-{scope}">Cumulative locator-reported dates among current {label.lower()}; not verified installation history</title><text class="ev-tick" x="55" y="22">Station records · cumulative listed dates</text>']
        for v in [0, ymax_chart / 2, ymax_chart]:
            svg.append(f'<line class="ev-grid" x1="55" x2="775" y1="{sy(v)}" y2="{sy(v)}"/><text class="ev-tick" x="43" y="{sy(v)+4}" text-anchor="end">{v:g}</text>')
        svg.append('<polyline class="ev-line" points="' + ' '.join(f'{110+i*155},{sy(v)}' for i, v in enumerate(values)) + '"/>')
        for i, (year, value) in enumerate(zip(range(2022, 2027), values)):
            x = 110 + i * 155
            svg.append(f'<circle class="ev-dot hydro" cx="{x}" cy="{sy(value)}" r="4"/><text class="ev-value" x="{x}" y="{sy(value)-12}" text-anchor="middle">{value}</text><text class="ev-tick" x="{x}" y="277" text-anchor="middle">{year}{"*" if year==2026 else ""}</text>')
            exports.append({'scope': scope, 'year': year, 'cumulative_current_records_with_listed_date': value, 'endpoint': d['reviewed'] if year == 2026 else f'{year}-12-31', 'not_installation_history': True})
        svg.append('</svg>')
        charts.append(f'<div data-ev-group="{scope}"{hidden}><div class="ev-map-frame">{map_svg}</div><h3>When current records were listed as opening</h3><div class="chart-scroll">{"".join(svg)}</div></div>')
    with (ROOT / 'data/ev-charging-timeline.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(exports[0]))
        w.writeheader()
        w.writerows(exports)
    rows = ''.join(f'<tr data-ev-hydro="{str(s["hydro_named"]).lower()}"><th scope="row">{e(s["station_name"])}<br><small>ID {s["id"]} · {"Hydro-named" if s["hydro_named"] else "Other name"}</small></th><td>{e(s["street_address"])}<br><small>Ward {s["ward"]} · {e(s["city"])}</small></td><td>{s["ports"] if s["ports"] is not None else "Unknown"}<br><small>L1 {s["ev_level1_evse_num"] or 0} / L2 {s["ev_level2_evse_num"] or 0} / DC {s["ev_dc_fast_num"] or 0}</small></td><td>{s["open_date"] or "Unknown"}<br><small>Locator field, possibly first listing</small></td><td>{e(s["access_days_time"] or "Hours not reported")}<br><small>Restricted flag: {"yes" if s["restricted_access"] else "no"}; owner code: {e(s["owner_type_code"] or "unknown")}; network: {e(s["ev_network"] or "unknown")}</small></td></tr>' for s in stations)
    sources = ''.join(f'<li>{link(k, s["title"])}<br><small>{e(s["locator"])}. {e(s["note"])}</small></li>' for k, s in evidence['sources'].items())
    return f'''<section id="ev-charging" class="card" aria-labelledby="ev-title"><p class="eyebrow">05 · Climate &amp; transport</p><h2 id="ev-title">200 EV charging stations</h2>
<div class="promise"><p><strong>The original 2022 commitment</strong></p><p>Enable <strong>Hydro Ottawa to install 200 EV charging stations across Ottawa on a cost-recovery basis</strong>.</p><p class="small">Paraphrase of August 17, 2022 campaign coverage. This is not a promise to count every charger installed by every provider. {link('campaign', '2022 wording ↗')}</p></div>
<p class="verdict"><strong>Installations are documented; the exact pledge count is not established.</strong> The records below show where charging is listed today. They do not establish how many of the promised 200 have been delivered.</p>
<details><summary>Why the different totals cannot be treated as pledge progress</summary><p>Hydro Ottawa’s regulatory filing reports <strong>1,047 ports supported by its ZEVIP program</strong>, completed in Q4 2024. That program began in 2021, covers the greater Ottawa region and includes residential and workplace charging. It is not a count of 200 new stations since taking office, and cost recovery is not established by that number. {link('hydro_program')}</p><p>The campaign report does not define a station-versus-port counting rule or an exact deadline. We do not assign a completion percentage. Bus-depot, fleet-only and e-bike equipment are not silently added to public-car charging.</p></details>
<h3>Where chargers are listed</h3><div class="ev-controls" hidden><label for="ev-scope">Map and timeline scope</label><select id="ev-scope"><option value="hydro">Hydro-named subset</option><option value="all">All listed public records</option></select></div>
<p class="small"><strong>Hydro-named</strong> means the station name contains “Hydro Ottawa” or “Envari”. It is an incomplete locator subset, not verified installation responsibility or ownership. “Public” follows the source field and can include customer-only or time restrictions.</p>
{''.join(summaries)}<div class="legend"><span><i class="key"></i>Hydro-named</span><span><i class="key historical"></i>Other records</span></div>{''.join(charts)}
<p class="small"><strong>Timeline limitation:</strong> the same current records are grouped by the locator’s opening-date field; dates may be approximate or first-listing dates. Retired/missing stations are absent, and current port capacity is not historical capacity. 2022 includes all dates before 2023; *2026 ends October 24. This is not a verified annual installation series or historical network size. {link('api_docs', 'Date definitions ↗')}</p>
<p class="small"><strong>Cross-check:</strong> Riverain Park’s locator date is September 23, 2026, while the councillor reported its two Level 2 chargers operational by July 10. City Hall’s four Level 2 and one Level 3 chargers were also reported operational by then. These seven chargers are examples, not a complete term total, and are not added again to the locator. {link('operational', 'Dated installation report ↗')}</p>
<details><summary>Exact locator records and access notes</summary><p class="small">With JavaScript, rows follow the scope selector. Without it, all retained records are shown. Scroll sideways for all columns. Multiple source records can describe the same physical site.</p><div class="table-wrap" tabindex="0" role="region" aria-label="EV charging locator records"><table class="ev-table"><thead><tr><th>Station record</th><th>Address</th><th>Current ports</th><th>Listed opening date</th><th>Access / source metadata</th></tr></thead><tbody>{rows}</tbody></table></div></details>
<details><summary>Method, exclusions and sources</summary><p>Snapshot: October 24, 2026. Query all Ontario electric records from the NLR/AFDC API; spatially match the existing simplified 2022 Ottawa ward polygons. Retain available status, public access and records not flagged unverified; exclude future listed dates. {d['in_boundary_records']} records fall inside the boundary; {sum(d['excluded_sequentially'].values())} are excluded by those rules. Coordinates and ward-edge simplification can affect boundary cases.</p><p>Counts are unique source IDs, not deduplicated physical sites. Ports sum the source’s L1/L2/DC counts; connectors are not counted again. Unknown all-level capacity remains unknown. Ownership codes: T utility, P private, LG municipal, SG provincial, FG federal, J joint. A Hydro name can coexist with a private ownership code. No causal attribution, real-time availability, cost-recovery verification or total-programme coverage is inferred. Normal builds use retained data without network calls.</p><ol class="source-list">{sources}</ol></details>
<p class="downloads"><a href="data/ev-charging.csv" download>Locator CSV ↓</a><a href="data/ev-charging-timeline.csv" download>Timeline CSV ↓</a><a href="data/ev-charging.json" download>Snapshot JSON ↓</a><a href="data/ev-charging-sources.json" download>Evidence &amp; sources ↓</a></p></section>'''

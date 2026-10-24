"""Render the reviewed Stage 2 chronology and evidence export; no network access."""
import csv
import json
from html import escape as e
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    d = json.loads((ROOT / 'data/lrt-stage2.json').read_text(encoding='utf-8'))

    def link(key, label='Source ↗'):
        return f'<a href="{e(d["sources"][key]["url"], quote=True)}">{e(label)}</a>'

    cards, rows, exports = [], [], []
    labels = {'forecast': 'Forecast', 'actual': 'Completed milestone', 'update': 'Status update'}
    for extension in d['extensions']:
        items = []
        for r in extension['events']:
            items.append(f'<li class="lrt-event {r["kind"]}"><span class="lrt-event-kind">{labels[r["kind"]]}</span><p class="lrt-event-date">{e(r["date_label"])}</p><p>{e(r["text"])}</p><small>{link(r["source"])}</small></li>')
            rows.append(f'<tr><th scope="row">{e(extension["name"])}</th><td>{e(r["date_label"])}</td><td>{labels[r["kind"]]}<br><small>{e(r["stage"].replace("_", " "))}</small></td><td>{e(r["target"] or r["actual_date"] or "No date stated")}</td><td>{link(r["source"])}</td></tr>')
            exports.append({'extension': extension['name'], **{k: r[k] for k in ['update_date', 'date_label', 'kind', 'stage', 'target', 'actual_date', 'text']}, 'source_url': d['sources'][r['source']]['url'], 'source_locator': d['sources'][r['source']]['locator']})
        cards.append(f'<article class="lrt-extension" aria-labelledby="lrt-{extension["id"]}-title"><h3 id="lrt-{extension["id"]}-title">{e(extension["name"])}</h3><p class="small lrt-route">{e(extension["route"])}</p><p class="lrt-status {extension["status_kind"]}">{e(extension["status"])}</p><p class="small">{e(extension["summary"])}</p><p class="small">Status evidence: {e(extension["status_as_of"])} · {link(extension["status_source"])}</p><ol class="lrt-timeline">{"".join(items)}</ol></article>')
    with (ROOT / 'data/lrt-stage2.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(exports[0]))
        writer.writeheader()
        writer.writerows(exports)
    sources = ''.join(f'<li>{link(k,s["title"])}<br><small>{e(s["type"])} · {e(s["locator"])}. {e(s["note"])}</small></li>' for k,s in d['sources'].items())
    return f'''<section id="lrt-stage2" class="card" aria-labelledby="lrt-title"><p class="eyebrow">05 · Rail expansion</p><h2 id="lrt-title">Stage 2: what opened, what shifted</h2>
<div class="promise"><p><strong>The 2022 commitment</strong></p><p>Deliver Phase 2 of LRT.</p><p class="small">{link('campaign','September 22, 2022 platform coverage')} · No explicit delivery deadline in the campaign source reviewed.</p></div>
<p class="verdict"><strong>South is open; east and west remain pending in the latest dated evidence.</strong></p>
<p>These timelines separate the schedules inherited near the start of the term from later forecasts and completed milestones. Construction completion and testing do not mean passengers can ride.</p>
<div class="legend lrt-legend"><span>○ Forecast</span><span>● Completed milestone</span><span>◇ Status update</span></div>
<p class="small">Read each timeline from top to bottom. Dates identify the update or actual event; forecast dates appear in the text. Spacing is not elapsed time. Selected milestones, not every schedule revision.</p>
<div class="lrt-grid">{''.join(cards)}</div>
<p class="cumulative-summary"><strong>November 2026 is an east testing forecast.</strong> The October 2 memo concerns pre-trial running, not a confirmed passenger opening. {link('east_october')}</p>
<details><summary>Exact milestones and forecast dates</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Stage 2 milestone evidence"><table style="min-width:700px"><thead><tr><th scope="col">Extension</th><th scope="col">Update / event</th><th scope="col">Milestone type</th><th scope="col">Forecast / actual date</th><th scope="col">Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>
<details><summary>Sources, scope and limits</summary><p>{e(d['method'])}</p><p>The original archived campaign platform has not been obtained. Its contemporary coverage supplies the commitment; the early November 2022 municipal-update reporting supplies inherited completion forecasts. They are not an additional mayoral promise.</p><p>The operator’s undated overview still lists east in 2026 and west in 2027. These are broad planning years: the October east memo and September west update leave opening uncertainty unresolved. No precise opening date or delay duration is inferred. Stage 3 funding, Stage 1 repairs and system reliability are separate questions.</p><p>Reviewed October 24, 2026. Latest dated status evidence: south March 16, 2025; east October 2, 2026; west September 10, 2026. No later opening is assumed. Council, contractors and staff share delivery roles; this chronology does not assign responsibility for each delay.</p><ol class="source-list">{sources}</ol></details>
<div class="downloads"><a href="data/lrt-stage2.csv" download>Milestones CSV ↓</a><a href="data/lrt-stage2.json" download>Reviewed evidence &amp; sources ↓</a></div></section>'''

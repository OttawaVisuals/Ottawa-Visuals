"""Build housing charts from the reviewed snapshot; no downloads during page build."""
import csv
import json
from html import escape as e
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def build():
    data=json.loads((ROOT/'data/housing.json').read_text(encoding='utf-8'))
    annual=data['annual_completions']
    community=data['affordable_supportive']
    cumulative=[]
    total=0
    for r in annual:
        if r['year']<2023:continue
        total+=r['completions']
        cumulative.append({'year':r['year'],'months':r['months'],'completions':total,'illustrative_pace':10000*((r['year']-2023)+r['months']/12)})
    result={'analysis_start':'2023-01-01','cutoff':'2026-08-31','cumulative_completions':cumulative,'affordable_supportive_2023_2025':sum(r['completed'] for r in community),
            'method':'Cumulative construction starts January 2023, the first full calendar year after taking office. Linear 10,000/year pace is 100,000÷10, an illustration, not a promised interim milestone. Affordable/supportive report totals are not a verified exact match for the community/affordable campaign scope.'}
    (ROOT/'data/housing-progress.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def link(key,label='Source ↗'):
        return f'<a href="{e(data["sources"][key]["url"],quote=True)}">{e(label)}</a>'

    exports=[]
    for r in annual:
        exports.append({'metric':'all_housing_completions','period':str(r['year']),'period_type':'year' if r['months']==12 else 'Jan–Aug YTD','value':r['completions'],'unit':'dwellings','source_url':data['sources'][r['source']]['url'],'locator':r['locator'],'note':'Ottawa city; gross new-construction completions, not net housing stock growth.'})
    for r in data['monthly_completions']:
        exports.append({'metric':'all_housing_completions','period':r['period'],'period_type':'month','value':r['completions'],'unit':'dwellings','source_url':data['sources'][r['source']]['url'],'locator':r['locator'],'note':'Councillor-office compilation of CMHC CSD data; annual/YTD records must not be added to monthly records.'})
    for r in community:
        for key in ['affordable','supportive','completed','under_construction']:
            exports.append({'metric':'city_report_'+key,'period':str(r['year']),'period_type':'year-end stock' if key=='under_construction' else 'year','value':r[key],'unit':'units','source_url':data['sources'][r['source']]['url'],'locator':r['locator'],'note':'Reported affordable/supportive program scope; not established as exact campaign community-housing scope. completed = affordable + supportive.'})
    for r in data['pipeline']:
        for key in ['starts','under_construction']:
            exports.append({'metric':'all_housing_'+key,'period':r['stock_date'] if key=='under_construction' else str(r['year']),'period_type':'month-end stock' if key=='under_construction' else 'year' if r['months']==12 else 'Jan–Aug YTD','value':r[key],'unit':'dwellings','source_url':data['sources'][r['source']]['url'],'locator':r['locator'],'note':'Do not add starts or stock to completions.'})
    with (ROOT/'data/housing.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(exports[0]));writer.writeheader();writer.writerows(exports)

    def chart(rows,name,cumulative_mode=False,community_mode=False):
        w=1050 if len(rows)>10 else 760
        h,left,right,top,bottom=410,60,85,45,65
        pw,ph=w-left-right,h-top-bottom
        maximum=40000 if cumulative_mode else 1200 if community_mode else 12000
        tick=10000 if cumulative_mode else 200 if community_mode else 2000
        x=lambda i:left+pw/len(rows)*(i+.5)
        y=lambda v:top+ph*(1-v/maximum)
        title='Affordable and supportive housing completed' if community_mode else 'Cumulative housing completions since January 2023' if cumulative_mode else 'Annual housing completions in Ottawa'
        bits=[f'<svg class="housing-svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{name}-title {name}-desc"><title id="{name}-title">{title}</title><desc id="{name}-desc">Bars start at zero. '+('Stacked bars distinguish affordable and supportive units in City program reports. The campaign community-housing reference has a different, unconfirmed scope.' if community_mode else 'The outlined 2026 bar is January–August only. A dashed line shows an illustrative even pace derived from 100,000 over ten years, not promised interim milestones.')+f'</desc><text class="axis-title" x="{left}" y="19">'+('Units completed' if community_mode else 'Dwellings completed')+'</text>']
        for value in range(0,maximum+1,tick):
            bits.append(f'<line class="gridline" x1="{left}" x2="{w-right}" y1="{y(value):.2f}" y2="{y(value):.2f}"/><text class="tick" x="{left-9}" y="{y(value)+4:.2f}" text-anchor="end">{value:,}</text>')
        for i,r in enumerate(rows):
            value=r['completed'] if community_mode else r['completions']
            bw=pw/len(rows)*.52
            if community_mode:
                for key,base in [('affordable',0),('supportive',r['affordable'])]:
                    bits.append(f'<rect class="housing-column {key}" x="{x(i)-bw/2:.2f}" y="{y(base+r[key]):.2f}" width="{bw:.2f}" height="{ph*r[key]/maximum:.2f}"><title>{r["year"]}: {key}, {r[key]} completed units</title></rect>')
            else:
                cls='housing-column'+(' historical' if r['year']<2023 else '')+(' partial' if r['months']<12 else '')
                bits.append(f'<rect class="{cls}" x="{x(i)-bw/2:.2f}" y="{y(value):.2f}" width="{bw:.2f}" height="{ph*value/maximum:.2f}"><title>{r["year"]}: {value:,}'+(' cumulative' if cumulative_mode else '')+' completions'+(' · January–August only' if r['months']<12 else '')+'</title></rect>')
            bits.append(f'<text class="housing-label" x="{x(i):.2f}" y="{y(value)-9:.2f}" text-anchor="middle">{value:,}</text><text class="tick" x="{x(i):.2f}" y="{y(0)+24:.2f}" text-anchor="middle">{r["year"]}'+('*' if r.get('months',12)<12 else '')+'</text>')
        if cumulative_mode:
            points=' '.join(f'{x(i):.2f},{y(r["illustrative_pace"]):.2f}' for i,r in enumerate(rows))
            bits.append(f'<polyline class="housing-reference" points="{points}"><title>Illustrative even pace from January 2023: 10,000/year; 2026 endpoint prorated to eight months. Not a promised interim milestone.</title></polyline>')
        else:
            ref=1000 if community_mode else 10000
            start=left if community_mode else left+next((i for i,r in enumerate(rows) if r['year']>=2023),0)*pw/len(rows)
            end=w-right if community_mode else w-right-(pw/len(rows) if rows[-1]['months']<12 else 0)
            bits.append(f'<line class="housing-reference" x1="{start:.2f}" x2="{end:.2f}" y1="{y(ref):.2f}" y2="{y(ref):.2f}"/><text class="tick" x="{end+6:.2f}" y="{y(ref)+4:.2f}">{ref:,}/yr</text>')
        bits.append('</svg>')
        hidden='' if name in ['housing-recent','housing-community'] else ' hidden'
        return f'<div id="{name}" class="housing-chart chart-scroll"{hidden} tabindex="0" role="region" aria-label="{title}; scroll horizontally on small screens">'+''.join(bits)+'</div>'

    charts=chart([r for r in annual if r['year']>=2019],'housing-recent')+chart(annual,'housing-history-chart')+chart(cumulative,'housing-cumulative',True)
    annual_rows=''.join(f'<tr><th scope="row">{r["year"]}</th><td>{"Full year" if r["months"]==12 else "Jan–Aug only"}</td><td>{r["completions"]:,}</td><td>{link(r["source"])}<br><small>{e(r["locator"])}</small></td></tr>' for r in annual)
    community_rows=''.join(f'<tr><th scope="row">{r["year"]}</th><td>{r["affordable"]}</td><td>{r["supportive"]}</td><td>{r["completed"]}</td><td>{r["under_construction"]}</td><td>{link(r["source"])} · {e(r["locator"])}</td></tr>' for r in community)
    pipeline_rows=''.join(f'<tr><th scope="row">{r["year"]}</th><td>{"Full year" if r["months"]==12 else "Jan–Aug"}</td><td>{r["starts"]:,}</td><td>{r["completions"]:,}</td><td>{r["under_construction"]:,}<br><small>{r["stock_date"]}</small></td></tr>' for r in data['pipeline'])
    cumulative_rows=''.join(f'<tr><th scope="row">{r["year"]}</th><td>{r["completions"]:,}</td><td>{r["illustrative_pace"]:,.1f}</td><td>{"December" if r["months"]==12 else "August"}</td></tr>' for r in cumulative)
    context_rows=''.join(f'<tr><th scope="row">{r["year"]}</th><td>{r["year_end_waitlist"] if r["year_end_waitlist"] is not None else "Not verified here"}</td><td>{r["placements"]:,}</td><td>{link(r["source"])}</td></tr>' for r in data['context'])
    source_list=''.join(f'<li>{link(k,s["title"])}<br><small>{e(s["locator"])}. {e(s["note"])}</small></li>' for k,s in data['sources'].items())
    options_notes=''.join(f'<li>{e(n)}</li>' for n in data['reconciliation_notes'])
    return f'''<section id="housing" class="card" aria-labelledby="housing-title"><p class="eyebrow">04 · Housing delivery</p><h2 id="housing-title">Homes built, and homes still needed</h2>
<div class="promise"><p><strong>The 2022 commitment</strong></p><p>100,000 new homes over ten years, including 10,000 affordable/community homes. The September platform coverage also specified 1,000 community units per year.</p><p class="small">{link('campaign_ad','Original October 2022 campaign advertisement · PDF p. 34')} · {link('campaign_news','September 2022 platform coverage')}</p></div>
<p class="verdict"><strong>{total:,} new-construction completions recorded since January 2023</strong>, through August 2026. This uses the first full calendar year after taking office; the campaign’s exact calendar baseline is unverified.</p>
<p class="small">The ten-year commitment is still a long-term target. Completions are not permits, starts, net housing-stock growth or proof of the mayor’s impact. The 2023+ count excludes late 2022 and includes projects initiated before this term.</p>
<div class="housing-controls" hidden><div class="range-buttons" role="group" aria-label="Housing chart measure"><button type="button" data-housing-mode="annual" aria-pressed="true">Annual completions</button><button type="button" data-housing-mode="cumulative" aria-pressed="false">Cumulative · since 2023</button></div><label><input type="checkbox" id="housing-history"> Show history since 2006</label></div>
<div class="legend"><span><i class="key"></i>New-construction completions</span><span><i class="key historical"></i>Before 2023</span><span><i class="key reference"></i>Illustrative even pace · 10,000/year</span></div>
{charts}<p class="small" id="housing-chart-note">*2026 is January–August only; compare it with the same months in prior years, not full-year bars. The 10,000/year reference is 100,000 ÷ 10, not a promised annual milestone. Scroll sideways on small screens.</p>
<p class="small"><strong>Matched-period comparison:</strong> Jan–Aug 2026 had 5,559 completions versus 4,514 in Jan–Aug 2025. 2025 full-year completions were 7,797. The compilation cutoff is August 2026; no later months are assumed.</p>
<h3>Affordable and supportive housing</h3><p><strong>{result['affordable_supportive_2023_2025']:,} reported completions in 2023–2025:</strong> 106 in 2023, 393 in 2024 and 79 in 2025. These are the City’s program-report categories; their exact correspondence to the campaign’s affordable/community wording is not established, so no pledge-completion percentage is assigned.</p>
<div class="legend"><span><i class="key"></i>Affordable</span><span><i class="key housing-supportive-key"></i>Supportive</span><span><i class="key reference"></i>Campaign community reference · 1,000/year*</span></div>
{chart(community,'housing-community',community_mode=True)}<p class="small">*Campaign reference shown for context, with a different/unconfirmed scope. No 2026 program-completion count is available in the sources reviewed. Housing benefits, acquisitions and people housed are not added to these new-unit completions; the campaign’s inclusion of acquisitions is unverified.</p>
<details><summary>Exact completions and cumulative comparison</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Housing completion history"><table style="min-width:650px"><thead><tr><th scope="col">Year</th><th scope="col">Coverage</th><th scope="col">Completions</th><th scope="col">Source</th></tr></thead><tbody>{annual_rows}</tbody></table></div><h3>Cumulative from January 2023</h3><div class="table-wrap" tabindex="0" role="region" aria-label="Cumulative housing completions"><table><thead><tr><th scope="col">Year</th><th scope="col">Completions</th><th scope="col">Illustrative even pace</th><th scope="col">Endpoint</th></tr></thead><tbody>{cumulative_rows}</tbody></table></div></details>
<details><summary>Affordable/supportive completions and pipeline</summary><p class="small">Under-construction figures are year-end stocks, not additional completed homes. Do not sum stocks across years or add this table to total CMHC completions.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Affordable and supportive housing delivery"><table style="min-width:750px"><thead><tr><th scope="col">Year</th><th scope="col">Affordable</th><th scope="col">Supportive</th><th scope="col">Total completed</th><th scope="col">Under construction at year-end</th><th scope="col">Source</th></tr></thead><tbody>{community_rows}</tbody></table></div></details>
<details><summary>Starts and construction pipeline · separate stages</summary><p>Starts are new work begun; completions are finished dwellings; under construction is the stock at the stated date. They are not the same project cohort and must not be added together. This first build does not import permits or planning approvals.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Ottawa housing construction stages"><table style="min-width:600px"><thead><tr><th scope="col">Year</th><th scope="col">Coverage</th><th scope="col">Starts</th><th scope="col">Completions</th><th scope="col">Under construction</th></tr></thead><tbody>{pipeline_rows}</tbody></table></div><p class="small">{link('ward','Source: councillor-office CMHC CSD compilation')} · By type rollup sheets, total row 7. August 2026 stock: 16,446 dwellings.</p></details>
<details><summary>Housing pressure · wait lists and placements</summary><p>Households waiting or housed are not newly built housing units. These contextual figures use year-end annual reports; they do not change the completion counts.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Housing pressure context"><table style="min-width:550px"><thead><tr><th scope="col">Year</th><th scope="col">Wait list at Dec 31</th><th scope="col">Households placed</th><th scope="col">Source</th></tr></thead><tbody>{context_rows}</tbody></table></div><p class="small">For 2024, the HNA reports a different December 10 snapshot (15,140) and 1,089 placements, while the annual report gives 14,721 at December 31 and 1,077 placements. Dates and discrepancies are preserved; the reason for the placement difference is not established. <a href="../Budget/budget.html#performance">Longer housing-pressure series on the budget page ↗</a></p></details>
<details><summary>Sources, assumptions and reconciliation</summary><p>Geography: City of Ottawa / Ottawa census subdivision, not Ottawa–Gatineau CMA or the Ontario portion of that CMA. History through 2023 comes from the City HNA’s CMHC table; recent data comes from the councillor-office CMHC compilation. The overlap (2020–2023) reconciles exactly. Direct CMHC automated access was blocked, so recent figures have not been independently re-downloaded from CMHC.</p><p>The original campaign advertisement says affordable homes; contemporary platform reporting says community housing. Neither source reviewed fixes a calendar baseline. January 2023 is our analytical convention. No final target deadline or official interim milestones are invented, and the later provincial 151,000-home pledge is not substituted for the 2022 campaign promise.</p><ul>{options_notes}</ul><ol class="source-list">{source_list}</ol></details>
<div class="downloads"><a href="data/housing.csv" download>Housing observations CSV ↓</a><a href="data/housing.json" download>Sources &amp; reviewed data ↓</a><a href="data/housing-progress.json" download>Cumulative calculations ↓</a></div></section>'''

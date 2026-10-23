/* Static report: only local JSON/CSV at runtime; no Power BI or ArcGIS queries. */
'use strict';
const BASE = 'data/derived/stops_report/';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = value => value == null ? '—' : Number(value).toLocaleString('en-CA', {maximumFractionDigits:1});
const sum = values => values.reduce((a, b) => a + b, 0);
const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const outcomes = ['Charged','Warning (T-Stop)','Final','Data Quality'];
const outcomeLabel = x => x === 'Warning (T-Stop)' ? 'Warning' : x;
const params = new URLSearchParams(location.search);
const sections = ['summary','collisions','where','stops','drivers','speed','redlight'];
let section = sections.includes(params.get('section')) ? params.get('section') : 'summary';
const initialSection = section;
let data, audit, charts = [], maps = [], exports = [], generation = 0;
const settings = {}, collisionCache = new Map();
const css = token => getComputedStyle(document.documentElement).getPropertyValue(token).trim();
function colours() { return [css('--accent-2'), css('--amber'), css('--green'), css('--ink-3'), css('--purple'), css('--red'), '#56B4E9', '#CC79A7', '#009E73', '#8A6D3B']; }
const all = (year, selected) => selected === 'all' || Number(year) === Number(selected);
const matchesOutcome = (outcome, selected) => selected === 'all' || outcome === selected;
function aggregate(rows, key, value) {
  const result = new Map();
  rows.forEach(row => { const k = key(row); result.set(k, (result.get(k) || 0) + value(row)); });
  return result;
}
function select(id, label, options, value) {
  return `<label for="${id}">${label}<select id="${id}">${options.map(([v,t]) => `<option value="${esc(v)}" ${String(v) === String(value) ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select></label>`;
}
function yearsOptions(years, withAll = true) {
  return [...(withAll ? [['all','All years']] : []), ...[...years].sort((a,b)=>b-a).map(y=>[String(y),String(y)])];
}
function stat(value, label) { return `<div class="stat"><div class="stat-val">${value}</div><div class="stat-label">${label}</div></div>`; }
function panel(id, title, note, wide = false, tall = false) {
  return `<article class="card ${wide ? 'wide' : ''}"><h3>${title}</h3><p class="note">${note}</p><div class="chart-box ${tall ? 'tall' : ''}"><canvas id="${id}" role="img" aria-label="${esc(title)}; values in the data table below"></canvas></div><div id="${id}-data"></div></article>`;
}
function mapPanel(title, note, tableTitle = 'Most recorded locations') {
  return `<article class="card wide"><h3>${title}</h3><p class="note">${note}</p><div id="map" class="map" role="region" aria-label="${esc(title)}"></div><p class="map-note">Larger circles indicate more records; sizes are capped for readability. Select a point for its count. The location table provides a text alternative.</p><div class="table-wrap" id="locations"><p>${tableTitle}</p></div></article>`;
}
function table(headers, rows, caption = '') {
  return `<table>${caption ? `<caption>${esc(caption)}</caption>` : ''}<thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((c,i)=>`<td class="${i ? 'num' : ''}">${esc(typeof c === 'number' && i ? fmt(c) : c ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function chart(id, type, labels, series, opts = {}) {
  const rows = labels.map((label, i) => [label, ...series.map(s=>s.data[i] ?? null)]);
  $(`${id}-data`).innerHTML = `<details class="chart-data" ${typeof Chart === 'undefined' ? 'open' : ''}><summary>View chart data</summary><div class="table-wrap">${table(['Period / category',...series.map(s=>s.label)],rows)}</div></details>`;
  if (typeof Chart === 'undefined') {
    $(id).parentNode.innerHTML = '<p class="empty">Chart library unavailable. All values remain available in the table below.</p>';
    return;
  }
  const palette = colours();
  const datasets = series.map((s, i)=>({
    borderColor:palette[i % palette.length], backgroundColor:palette[i % palette.length], borderWidth:type === 'line' ? 2 : 0,
    pointRadius:labels.length > 30 ? 0 : 2, pointHitRadius:10, spanGaps:false,
    borderDash:type === 'line' && i ? [i*3, 2] : [], ...s,
  }));
  const config = {
    type, data:{labels,datasets}, options:{responsive:true,maintainAspectRatio:false,animation:false,
      indexAxis:opts.horizontal ? 'y' : 'x',
      interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:series.length > 1,position:'bottom',labels:{color:css('--ink-2'),boxWidth:10,padding:13}},
        tooltip:{callbacks:{label:opts.label || (ctx=>`${ctx.dataset.label}: ${fmt(ctx.raw)}${opts.percent ? '%' : ''}`)}}},
      scales:{x:{stacked:!!opts.stacked,grid:{display:!!opts.horizontal,color:css('--line')},ticks:{color:css('--ink-2'),maxTicksLimit:opts.horizontal ? 12 : 11,autoSkip:true},...(opts.horizontal ? {beginAtZero:true} : {}),...opts.x},
        y:{stacked:!!opts.stacked,beginAtZero:true,...(opts.percent && !opts.horizontal ? {max:100} : {}),grid:{color:css('--line'),display:!opts.horizontal},ticks:{color:css('--ink-2'),precision:opts.percent ? 1 : 0,...(opts.percent ? {callback:v=>`${v}%`} : {})},...opts.y}}},
    plugins:opts.plugins || [],
  };
  charts.push(new Chart($(id), config));
}
// Same OSM tiles as rto.html; CARTO now serves an "API key required" placeholder. Dark mode filters them in CSS.
const basemap = () => L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:18,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'});
function mapPoints(points, period) {
  // points: {name,lat,lon,n,detail}; no source HTML is inserted unescaped.
  const sorted = [...points].sort((a,b)=>b.n-a.n);
  $('locations').innerHTML = table(['Location','Records'], sorted.slice(0,15).map(p=>[p.name,p.n]), `Top 15 locations · ${period}`);
  if (!points.length) { $('map').innerHTML = '<p class="empty">No mapped records for this selection.</p>'; return; }
  if (typeof L === 'undefined') { $('map').innerHTML = '<p class="empty">Map library unavailable. Use the location table below.</p>'; return; }
  const map = L.map('map', {scrollWheelZoom:false,preferCanvas:true}).setView([45.33,-75.76],10);
  maps.push(map);
  basemap().addTo(map).on('tileerror',()=>{ if (!$('map-tile-error')) $('map').insertAdjacentHTML('afterend','<p class="note" id="map-tile-error">Basemap could not load. Points and the location table remain available.</p>'); });
  points.forEach(p=>L.circleMarker([p.lat,p.lon],{radius:Math.min(23,2+Math.sqrt(p.n)*.35),weight:1,color:css('--accent-2'),fillColor:css('--accent-2'),fillOpacity:.42})
    .bindPopup(`<strong>${esc(p.name)}</strong><br>${fmt(p.n)} records · ${esc(period)}${p.detail ? '<br>'+esc(p.detail) : ''}`).addTo(map));
  // Keep the Ottawa view: erroneous source coordinates must not zoom the map out.
  if (points.length === 1) map.setView([points[0].lat,points[0].lon],13);
}
function saveState() {
  const next = new URLSearchParams({section,...settings[section]});
  history.replaceState(null,'',`${location.pathname}?${next}${location.hash}`);
}
function initState(name) {
  if (settings[name]) return settings[name];
  if (name === 'where') return settings[name] = {};
  const initial = name === 'collisions' ? {year:String(Math.max(...data.collisions.map(r=>r.year))),ward:'all'} : name === 'speed' || name === 'redlight' ? {year:String(Math.max(...data[name].months.map(r=>r[0]))),site:'all',metric:'total',...(name==='speed'?{monitor:''}:{})} : {year:'all',outcome:'all'};
  if (name === initialSection) Object.keys(initial).forEach(k=>{if(params.has(k)) initial[k] = params.get(k);});
  const years = name === 'collisions' ? [...new Set(data.collisions.map(r=>r.year))] : data.police.years;
  if (name === 'stops' || name === 'drivers' || name === 'collisions') {
    if (!yearsOptions(years,name !== 'collisions').some(([v])=>v === initial.year)) initial.year = name === 'collisions' ? String(Math.max(...years)) : 'all';
    if (initial.outcome && !['all',...outcomes].includes(initial.outcome)) initial.outcome = 'all';
  } else {
    const years = [...new Set(data[name].months.map(r=>r[0]))];
    if (!yearsOptions(years).some(([v])=>v === initial.year)) initial.year = String(Math.max(...years));
    if (initial.site !== 'all' && !data[name].sites.some((_,i)=>String(i) === initial.site)) initial.site = 'all';
    if (!['total','per-camera'].includes(initial.metric)) initial.metric = 'total';
  }
  settings[name] = initial;
  return initial;
}
function policeFilters(state) {
  $('filters').innerHTML = select('year','Stop year',yearsOptions(data.police.years),state.year)+select('outcome','Recorded outcome',[['all','All outcomes'],...outcomes.map(x=>[x,outcomeLabel(x)])],state.outcome);
}
function policeChartRows(rows, state, yearIndex, outcomeIndex) {
  return rows.filter(r=>all(r[yearIndex],state.year)&&matchesOutcome(r[outcomeIndex],state.outcome));
}
function renderStops(state) {
  const p = data.police;
  const firstYear=p.years[0], lastYear=p.years.at(-1), period=`${firstYear}–${lastYear}`;
  policeFilters(state);
  $('section-kicker').textContent = '03 · Police enforcement';
  $('section-title').textContent = 'Fewer stops. What were the outcomes?';
  $('section-description').textContent = `Follow traffic-stop records from ${firstYear} to ${lastYear}, with every source outcome retained.`;
  $('filter-scope').textContent = 'Year and outcome filter the summary, monthly chart, weekday chart and neighbourhoods. The annual chart keeps all years for context. The location map is all years and all outcomes.';
  const selected = policeChartRows(p.annual,state,0,1), n = sum(selected.map(r=>r[2]));
  const allSelectedYear = p.annual.filter(r=>all(r[0],state.year));
  const charged = sum(allSelectedYear.filter(r=>r[1]==='Charged').map(r=>r[2]));
  const denominator = sum(allSelectedYear.map(r=>r[2]));
  const first = sum(p.annual.filter(r=>r[0]===firstYear&&r[1]==='Charged').map(r=>r[2]));
  const last = sum(p.annual.filter(r=>r[0]===lastYear&&r[1]==='Charged').map(r=>r[2]));
  $('stats').innerHTML = stat(fmt(n),`Stop records · ${state.year === 'all' ? period : state.year} · ${esc(state.outcome==='all'?'all outcomes':outcomeLabel(state.outcome))}`)+stat(fmt(denominator ? charged/denominator*100 : null)+'%','Charged share of all outcomes in selected year(s)')+stat(`${fmt((last/first-1)*100)}%`,`Change in stops resulting in a charge · ${lastYear} vs ${firstYear}`);
  $('panels').innerHTML = '<div class="grid">'+panel('annual','Traffic stops by year','All years for context. Counts by recorded outcome; not a count of tickets.',true)+panel('monthly','Traffic stops by month','Selected year(s) and outcome. Gaps remain missing; no smoothing.',true)+panel('weekday','Day of the week','Selected year(s) and outcome. Totals, not a daily average.')+panel('areas','Neighbourhoods with the most stops','Top 12 source neighbourhoods in the selection. Counts are not adjusted for traffic or population.',false,true)+mapPanel('Where stops were recorded',`All years (${period}), all outcomes. Small locations with fewer than 3 stops are grouped out of the map. ${fmt(p.unmapped_stops)} records have no mapped point. This map does not respond to the filters above.`)+'</div>';
  const activeOutcomes = outcomes.filter(o=>matchesOutcome(o,state.outcome));
  chart('annual','bar',p.years,activeOutcomes.map(o=>({label:outcomeLabel(o),data:p.years.map(y=>sum(p.annual.filter(r=>r[0]===y&&r[1]===o).map(r=>r[2])))})),{stacked:true});
  const months = [...new Set(p.monthly.filter(r=>all(r[0],state.year)).map(r=>`${r[0]}-${String(r[1]).padStart(2,'0')}`))].sort();
  chart('monthly','line',months,activeOutcomes.map(o=>({label:outcomeLabel(o),data:months.map(m=>{
    const rows = p.monthly.filter(r=>`${r[0]}-${String(r[1]).padStart(2,'0')}`===m&&r[2]===o);
    return rows.length ? sum(rows.map(r=>r[3])) : null;
  })})));
  const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const week = policeChartRows(p.weekdays,state,0,2);
  chart('weekday','bar',days,[{label:'Stops',data:days.map(d=>sum(week.filter(r=>r[1]===d).map(r=>r[3])))}]);
  const area = [...aggregate(policeChartRows(p.areas,state,0,2),r=>r[1],r=>r[3])].sort((a,b)=>b[1]-a[1]).slice(0,12);
  chart('areas','bar',area.map(r=>r[0]),[{label:'Stops',data:area.map(r=>r[1])}],{horizontal:true});
  mapPoints(p.locations.map(r=>({name:r[0],lat:r[1],lon:r[2],n:r[3],detail:`${fmt(r[4])} resulted in a charge`})), period);
  exports = [['year','month','recorded_outcome','stop_records'],...policeChartRows(p.monthly,state,0,2)];
}
function renderDrivers(state) {
  policeFilters(state);
  $('section-kicker').textContent = '04 · Driver demographics';
  $('section-title').textContent = 'Who appears in the stop records?';
  $('section-description').textContent = 'Recorded race, age and gender categories. A person can appear more than once, and unknown values remain in the denominator.';
  $('filter-scope').textContent = 'Filters affect the summary and category charts. The race-share trend retains all years, filtered by outcome. No population or driving-exposure denominator is available here.';
  const rows = policeChartRows(data.police.drivers,state,0,4);
  const total = sum(rows.map(r=>r[5]));
  const unknown = sum(rows.filter(r=>/unknown|data quality/i.test(r[3])).map(r=>r[5]));
  $('stats').innerHTML = stat(fmt(total),'Stop records in the selection')+stat(`${fmt(total ? unknown/total*100 : null)}%`,'Recorded race unknown / data quality')+stat(state.year === 'all' ? `${data.police.years[0]}–${data.police.years.at(-1)}` : state.year,'Selected stop year(s)');
  $('panels').innerHTML = '<div class="notice">These are shares of recorded stops, not the chance that a member of a demographic group will be stopped. Population composition, driving exposure and missing data are not controlled for.</div><div class="grid">'+panel('race','Recorded race','Counts in the selected year(s) and outcome.',false,true)+panel('race-trend','Race share over time','All years, selected outcome. Percent of all stop records each year, including unknown values.',false,true)+panel('age','Recorded age range','Counts in the selected year(s) and outcome.')+panel('gender','Recorded gender','Source categories: M, F and D (data quality). Missing values are Unknown.')+panel('hourly','Hour of the day','Selected year(s) and outcome. Source hour, 24-hour clock; missing hours are shown separately. Counts, not hourly rates.',true)+'</div>';
  const groups = i=>[...aggregate(rows,r=>r[i],r=>r[5])].sort((a,b)=>b[1]-a[1]);
  for (const [id,i] of [['race',3],['age',1],['gender',2]]) {
    const g = groups(i);
    if (id==='age') g.sort((a,b)=>a[0].localeCompare(b[0],undefined,{numeric:true}));
    chart(id,'bar',g.map(r=>r[0]),[{label:'Stop records',data:g.map(r=>r[1])}],{horizontal:true});
  }
  const trend = data.police.drivers.filter(r=>matchesOutcome(r[4],state.outcome));
  const races = [...new Set(trend.map(r=>r[3]))].sort();
  chart('race-trend','bar',data.police.years,races.map(race=>({label:race,data:data.police.years.map(y=>{
    const yr = trend.filter(r=>r[0]===y), total=sum(yr.map(r=>r[5]));
    return total ? sum(yr.filter(r=>r[3]===race).map(r=>r[5]))/total*100 : null;
  })})),{stacked:true,percent:true});
  const hours=Array.from({length:24},(_,i)=>String(i));
  const byHour=policeChartRows(data.police.hourly,state,0,2);
  chart('hourly','bar',[...hours.map(h=>h.padStart(2,'0')+':00'),'Unknown'],[{label:'Stop records',data:[...hours,'Unknown'].map(h=>sum(byHour.filter(r=>r[1]===h).map(r=>r[3])))}]);
  exports = [['year','age_range','recorded_gender','recorded_race','recorded_outcome','stop_records'],...rows];
}
function snapshots() {
  return `<article class="card wide"><p class="eyebrow">Newer data · separate OPS publications</p><h3>Beyond the detailed records</h3><p class="note">These summaries use different definitions from the City’s detailed collision files. They are not added to the charts below.</p>${[...data.snapshots].reverse().map(s=>`<div class="snapshot"><h3>${esc(s.label)}</h3><p class="note">${esc(s.period)} · <a href="${esc(s.source)}" target="_blank" rel="noopener">Official OPS summary</a></p><div class="stats">${Object.entries(s.metrics).slice(0,3).map(([label, v])=>stat(fmt(v[1]),`${esc(label)} · ${esc(s.labels[1])}<br>${fmt(v[0])} in ${esc(s.labels[0])}`)).join('')}</div><p class="note">${esc(s.note)}</p><details class="chart-data"><summary>View all published comparison values</summary><div class="table-wrap">${table(['Measure',...s.labels],Object.entries(s.metrics).map(([k,v])=>[k,...v]))}</div></details></div>`).join('')}</article>`;
}
// Crash news log: two CSVs the hourly collect.yml pollers rewrite, read as-is so the
// block is current without a rebuild. See Traffic/README.md for how rows are tagged.
const newsFiles = ['data/ops_collision_releases.csv','data/ctv_crash_headlines.csv'];
const crashTypes = [['pedestrian','Pedestrian'],['cyclist','Cyclist'],['motorcycle','Motorcycle'],['multi_vehicle','Multi-vehicle'],['single_vehicle','Single vehicle'],['off_road','Off-road vehicle'],['building','Into a building'],['train','Train'],['unknown','Not stated']];
const crashType = key => (crashTypes.find(t=>t[0]===key) || crashTypes.at(-1))[1];
const severityGroups = [['Fatal',['fatal'],'--red'],['Critical or serious injury',['critical','serious'],'--amber'],['Injury',['injury'],'--accent-2'],['Not stated in headline',['unknown','none',''],'--ink-3']];
const severityGroup = key => (severityGroups.find(g=>g[1].includes(key)) || severityGroups.at(-1))[0];
let newsTask;
function parseCSV(text) {
  const rows = []; let row = [], field = '', quoted = false;
  text = text.replace(/^﻿/, '');
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) { if (c === '"') { if (text[i+1] === '"') { field += '"'; i++; } else quoted = false; } else field += c; }
    else if (c === '"') quoted = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else if (c !== '\r') field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const [head, ...body] = rows;
  return body.filter(r=>r.length === head.length).map(r=>Object.fromEntries(head.map((h,i)=>[h,r[i]])));
}
async function loadCSV(file) {
  const response = await fetch(file, {cache:'no-cache'});
  if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
  return parseCSV(await response.text());
}
const link = (url, text) => /^https:\/\//.test(url || '') ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)}</a>` : esc(text);
const headline = slug => slug.replace(/-/g,' ').replace(/^./, c=>c.toUpperCase());
function subPanel(id, title, note, tall = false) {
  return `<div><p class="eyebrow">${title}</p><p class="note">${note}</p><div class="chart-box ${tall ? 'tall' : ''}"><canvas id="${id}" role="img" aria-label="${esc(title)}; values in the data table below"></canvas></div><div id="${id}-data"></div></div>`;
}
function newsCard() {
  return `<article class="card wide" id="news"><p class="eyebrow">Live · news releases and headlines since December 2025 · updated hourly</p><h3>Serious crashes in the news</h3><p class="note">A sample, not a complete record: Ottawa Police issue releases mostly for fatal and serious crashes, and CTV Ottawa covers the crashes it chooses. One crash can produce several stories. Nothing here is added to the City records below, and the year and ward filters do not apply. Counts are of releases and stories, not a collision rate.</p><div id="news-body"><p class="note">Loading the news log…</p></div></article>`;
}
function storyRows(rows) {
  return `<div class="table-wrap"><table><thead><tr><th scope="col">Date</th><th scope="col">CTV headline</th><th scope="col">Type</th><th scope="col">Severity</th><th scope="col">OPS release</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.sitemap_date)}</td><td>${link(r.url, headline(r.slug))}</td><td>${esc(crashType(r.collision_type))}</td><td>${esc(severityGroup(r.severity))}</td><td>${r.matched_ops_url ? link(r.matched_ops_url, r.match_basis === 'road' ? 'Yes' : 'Probably') : 'None matched'}</td></tr>`).join('')}</tbody></table></div>`;
}
async function renderNews(token) {
  try {
    newsTask ??= Promise.all(newsFiles.map(loadCSV)).catch(e=>{ newsTask = null; throw e; });
    const [ops, ctv] = await newsTask;
    if (token !== generation) return;
    const releases = ops.filter(r=>r.kind === 'collision' && r.follow_up === '0').sort((a,b)=>b.release_utc.localeCompare(a.release_utc));
    const stories = ctv.filter(r=>r.in_ottawa_ops === '1' && r.story_kind === 'incident').sort((a,b)=>b.lastmod_utc.localeCompare(a.lastmod_utc));
    const serious = stories.filter(r=>['fatal','critical','serious'].includes(r.severity));
    const matched = serious.filter(r=>r.matched_ops_url).length;
    const dates = [...stories.map(r=>r.sitemap_date), ...releases.map(r=>r.release_utc.slice(0,10))].sort();
    const months = [];
    for (let [y, m] = dates[0].split('-').map(Number); `${y}-${String(m).padStart(2,'0')}` <= dates.at(-1).slice(0,7); m === 12 ? (y++, m = 1) : m++) months.push(`${y}-${String(m).padStart(2,'0')}`);
    const monthLabel = ym => `${monthNames[Number(ym.slice(5))-1]} ${ym.slice(0,4)}`;
    const year = dates.at(-1).slice(0,4), cutoff = new Date(Date.now() - 30*864e5).toISOString().slice(0,10);
    const yearReleases = releases.filter(r=>r.release_utc.startsWith(year)), yearStories = stories.filter(r=>r.sitemap_date.startsWith(year));
    const vulnerable = yearReleases.filter(r=>r.pedestrian === '1' || r.cyclist === '1').length;
    const recent = [stories.filter(r=>r.sitemap_date >= cutoff).length, releases.filter(r=>r.release_utc.slice(0,10) >= cutoff).length];
    $('news-body').innerHTML = `<div class="stats">${stat(fmt(yearReleases.length),`OPS collision releases in ${year} so far · ${yearReleases.filter(r=>r.severity==='fatal').length} fatal · ${vulnerable} involving a pedestrian or cyclist`)}${stat(fmt(yearStories.length),`CTV Ottawa crash stories in ${year} so far, inside the city on roads OPS patrols`)}${stat(fmt(recent[0]),`CTV stories in the last 30 days · ${recent[1]} OPS release${recent[1] === 1 ? '' : 's'}`)}${stat(`${matched} of ${serious.length}`,'Fatal, critical or serious CTV stories since December 2025 with a matched OPS release')}</div><p class="note">Stories are matched to releases automatically by road, crash type and date, and the matching misses some pairs. A hand check of March 1 to October 19, 2026 found an OPS release for 14 of 18 fatal crashes but only 8 of 28 serious or critical ones. <a href="README.md#ctv-ottawa-crash-headlines-hourly">How rows are tagged and matched</a>.</p><div class="grid">${subPanel('news-monthly','CTV crash stories by month',`Stories, not crashes. ${monthLabel(months.at(-1))} is partial.`)}${subPanel('news-types','By type of crash','CTV stories and original OPS releases. Types come from headlines and release text.',true)}</div><p class="eyebrow">Latest stories</p>${storyRows(stories.slice(0,10))}<details class="chart-data"><summary>All ${fmt(stories.length)} CTV stories</summary>${storyRows(stories)}</details><details class="chart-data"><summary>All ${fmt(releases.length)} OPS collision releases</summary><div class="table-wrap"><table><thead><tr><th scope="col">Released</th><th scope="col">Title</th><th scope="col">Type</th><th scope="col">Severity</th><th scope="col">Location</th></tr></thead><tbody>${releases.map(r=>`<tr><td>${esc(r.release_utc.slice(0,10))}</td><td>${link(r.url, r.title)}</td><td>${esc(crashType(r.collision_type))}</td><td>${esc(r.severity || '—')}</td><td>${esc(r.location || '—')}</td></tr>`).join('')}</tbody></table></div></details><p class="note"><a href="${newsFiles[0]}" download>Download OPS releases (CSV)</a> · <a href="${newsFiles[1]}" download>Download CTV headlines (CSV)</a></p>`;
    chart('news-monthly','bar',months.map(monthLabel),severityGroups.map(([label,,colour])=>({label,backgroundColor:css(colour),data:months.map(m=>stories.filter(r=>r.sitemap_date.startsWith(m)&&severityGroup(r.severity)===label).length)})),{stacked:true});
    chart('news-types','bar',crashTypes.map(t=>t[1]),[{label:'CTV stories',data:crashTypes.map(([k])=>stories.filter(r=>(r.collision_type||'unknown')===k).length)},{label:'OPS releases',data:crashTypes.map(([k])=>releases.filter(r=>(r.collision_type||'unknown')===k).length)}],{horizontal:true});
  } catch(e) {
    if (token === generation) $('news-body').innerHTML = '<p class="empty">The news log could not load. The City records below are unaffected.</p>';
  }
}
async function renderCollisions(state, token) {
  const years = [...new Set(data.collisions.map(r=>r.year))].sort();
  const wards = [...new Set(data.collisions.map(r=>r.ward))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
  if (state.ward !== 'all' && !wards.includes(state.ward)) state.ward='all';
  $('filters').innerHTML = select('year','Detailed record year',yearsOptions(years,false),state.year)+select('ward','Ward (2022–2026 boundaries)',[['all','All wards'],...wards.map(w=>[w,w])],state.ward);
  $('section-kicker').textContent = '01 · Reported collisions';
  $('section-title').textContent = 'Where collisions happen, and who is involved';
  $('section-description').textContent = 'Detailed City records cover 2017–2022 and 2024. Newer OPS summaries are shown separately below.';
  $('filter-scope').textContent = 'Year and ward affect the detailed summary, severity, impact types, parties and map. The trend retains all years for the selected ward. The OPS summaries are citywide and do not respond to these filters.';
  const wardRows = data.collisions.filter(r=>state.ward === 'all'||r.ward === state.ward);
  const selected = wardRows.filter(r=>r.year===Number(state.year));
  const total = sum(selected.map(r=>r.total));
  const severity = aggregate(selected.flatMap(r=>Object.entries(r.severity)),r=>r[0],r=>r[1]);
  const fatal = severity.get('Fatal injury')||0, injury = severity.get('Non-fatal injury')||0;
  $('stats').innerHTML = stat(fmt(total),`Collision records · ${esc(state.year)} · selected ward(s)`)+stat(fmt(injury),'Non-fatal injury collisions')+stat(fmt(fatal),'Fatal collisions · not people killed');
  $('panels').innerHTML = '<div class="grid">'+newsCard()+snapshots()+panel('collision-trend','Detailed collision records over time','Selected ward(s). 2023 is missing at source; the gap is not zero.',true)+panel('fatal-trend','Fatal collisions by year','Selected ward(s), all available detailed years. Counts collisions, not people killed.')+panel('injury-trend','Non-fatal injury collisions by year','Selected ward(s), all available detailed years. Counts collisions, not injured people.')+panel('severity','Collision severity','Collision records classified by their most severe outcome.')+panel('impact','How collisions occurred','Top 10 recorded impact types.',false,true)+panel('parties','Parties involved','Sum of recorded vehicles and road users. These categories can overlap; motorcycles may also be included in vehicles. Blank fields are omitted.',true)+mapPanel('Collision locations',`${esc(state.year)} · ${esc(state.ward==='all'?'all wards':state.ward)}. Counts at reported coordinates, not a measure of road risk or traffic exposure.`)+'</div>';
  const range = Array.from({length:Math.max(...years)-Math.min(...years)+1},(_,i)=>Math.min(...years)+i);
  chart('collision-trend','line',range,[{label:'Collision records',data:range.map(y=>years.includes(y) ? sum(wardRows.filter(r=>r.year===y).map(r=>r.total)) : null)}]);
  for(const [id,kind] of [['fatal-trend','Fatal injury'],['injury-trend','Non-fatal injury']]) {
    chart(id,'line',range,[{label:kind==='Fatal injury'?'Fatal collisions':'Non-fatal injury collisions',data:range.map(y=>years.includes(y)?sum(wardRows.filter(r=>r.year===y).map(r=>r.severity[kind]||0)):null)}]);
  }
  const severityRows = [...severity].sort((a,b)=>b[1]-a[1]);
  chart('severity','bar',severityRows.map(r=>r[0]),[{label:'Collisions',data:severityRows.map(r=>r[1])}],{horizontal:true});
  const impact = [...aggregate(selected.flatMap(r=>Object.entries(r.impact)),r=>r[0],r=>r[1])].sort((a,b)=>b[1]-a[1]).slice(0,10);
  chart('impact','bar',impact.map(r=>r[0]),[{label:'Collisions',data:impact.map(r=>r[1])}],{horizontal:true});
  const participants = ['vehicles','pedestrians','bicycles','motorcycles'];
  chart('parties','bar',['Vehicles','Pedestrians','Bicycles','Motorcycles'],[{label:'Recorded parties',data:participants.map(k=>sum(selected.map(r=>r.participants[k]||0)))}]);
  const news = renderNews(token);
  $('locations').innerHTML = '<p class="note">Loading selected year’s locations…</p>';
  exports = [['year','ward','collision_records','non_fatal_injury_collisions','fatal_collisions'],...selected.map(r=>[r.year,r.ward,r.total,r.severity['Non-fatal injury']||0,r.severity['Fatal injury']||0])];
  try {
    if (!collisionCache.has(state.year)) collisionCache.set(state.year,loadJSON(`collisions-${state.year}.json`).catch(e=>{collisionCache.delete(state.year);throw e;}));
    const points = (await collisionCache.get(state.year)).filter(r=>state.ward==='all'||r[3]===state.ward);
    if (token !== generation) return;
    mapPoints(points.map(r=>({name:r[0],lat:r[1],lon:r[2],n:r[4],detail:r[3]})),state.year);
  } catch(e) {
    if (token === generation) $('map').innerHTML = '<p class="empty">Location data could not load. Change the year to retry. Summary charts remain available.</p>';
  }
  await news;
}
// Where it happens (formerly roads.html): neighbourhood stops-vs-harm map, riskiest busy
// intersections and traffic volume, from build_stories.py's weekly stories.json.
const divTokens = ['--div-w3','--div-w2','--div-w1','--div-0','--div-c1','--div-c2','--div-c3'];
const titleCase = s => String(s || '').toLowerCase().replace(/(^|[\s/(@-])([a-z])/g, (m, p, c) => p + c.toUpperCase());
let storiesTask, areasTask;
const loadStories = () => storiesTask ??= fetchJSON('data/derived/stories.json').catch(e=>{ storiesTask = null; throw e; });
const loadAreas = () => areasTask ??= fetchJSON('data/derived/neighbourhoods.geojson').catch(e=>{ areasTask = null; throw e; });
async function fetchJSON(file) {
  const response = await fetch(file);
  if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
  return response.json();
}
// log2 index -> one of 7 diverging classes (¼×, ½×, ~1×, 2×, 4×).
function divColor(index) {
  const l = Math.log2(index), cuts = [-1.5,-.75,-.2,.2,.75,1.5];
  let i = 0; while (i < cuts.length && l > cuts[i]) i++;
  return css(divTokens[i]);
}
const popRow = (label, value) => `<div class="pop-row"><span>${label}</span><b>${value}</b></div>`;
function areaPopup(a) {
  if (!a) return '<strong>No data</strong>';
  return `<strong>${esc(a.neighbourhood)}</strong>${popRow('Stops vs harm', a.index ? `${a.index.toFixed(2)}×` : 'no index (under 20 injury crashes)')}${popRow('Share of injury crashes', `${a.share_injury_pct.toFixed(2)}%`)}${popRow('Share of police stops', `${a.share_stops_pct.toFixed(2)}%`)}${popRow('Injury crashes', fmt(a.injury_collisions))}${popRow('Police stops', fmt(a.police_stops))}${a.charged_pct != null ? popRow('Stops ending in a charge', `${a.charged_pct}%`) : ''}`;
}
function whereMap(stories, areas) {
  const byName = Object.fromEntries(stories.enforcement_vs_harm.areas.map(a => [a.neighbourhood, a]));
  if (typeof L === 'undefined') { $('where-map').innerHTML = '<p class="empty">Map library unavailable. The neighbourhood table below has every value.</p>'; return; }
  const map = L.map('where-map', {scrollWheelZoom:false,zoomSnap:.5}).setView([45.33,-75.72],10);
  maps.push(map);
  basemap().addTo(map);
  const areaLayer = L.geoJSON(areas, {
    style: f => { const a = byName[f.properties.name]; return a && a.index
      ? {color:css('--bg-2'),weight:1,fillColor:divColor(a.index),fillOpacity:.72}
      : {color:css('--ink-3'),weight:1,dashArray:'3 3',fillColor:css('--bg-3'),fillOpacity:.25}; },
    onEachFeature: (f, layer) => {
      layer.bindPopup(areaPopup(byName[f.properties.name]));
      layer.on('mouseover', () => layer.setStyle({weight:2.5,color:css('--ink')}));
      layer.on('mouseout', () => areaLayer.resetStyle(layer));
    },
  }).addTo(map);
  // Fit once the container has a size; a hidden pane measures 0 px and Leaflet would max-zoom.
  const fit = () => { const size = map.getSize(); if (!size.x || !size.y) return false; const b = areaLayer.getBounds(); map.setView(b.getCenter(), Math.min(12, map.getBoundsZoom(b, false, L.point(16,16))), {animate:false}); return true; };
  if (!fit()) { const ro = new ResizeObserver(() => { map.invalidateSize(); if (fit()) ro.disconnect(); }); ro.observe($('where-map')); }
  // Solid dots = riskiest intersections; hollow rings = cameras.
  const dot = (r, radius, colour, html) => L.circleMarker([r.lat,r.lon], {radius,color:css('--bg-2'),weight:2,fillColor:colour,fillOpacity:.95}).bindPopup(html);
  const ring = (r, colour, html) => L.circleMarker([r.lat,r.lon], {radius:5,color:colour,weight:2.5,fillColor:css('--bg-2'),fillOpacity:.9}).bindPopup(html);
  const layers = {
    danger: L.layerGroup(stories.danger_intersections.rows.slice(0,30).map((r,i) => dot(r, 5+Math.min(5,r.per_mev*1.3), css('--ink'), `<strong>#${i+1} ${esc(titleCase(r.name))}</strong>${popRow('Collisions 2017–24', fmt(r.collisions))}${popRow(`Vehicles / day (${esc(r.aadt_year)})`, fmt(r.aadt))}${popRow('Per million vehicles', r.per_mev.toFixed(2))}${popRow('Police stops here', fmt(r.police_stops))}`))),
    rlc: L.layerGroup(stories.camera_sites.red_light.map(c => ring(c, css('--ink'), `<strong>Red-light camera</strong><br>${esc(titleCase(c.name))}${popRow('Installed', esc(c.installed || '?'))}${popRow('Violations since 2015', fmt(c.violations))}`))),
    ase: L.layerGroup(stories.camera_sites.photo_radar.map(c => ring(c, css('--ink-3'), `<strong>Photo radar ${esc(c.site_id)}</strong><br>${esc(c.name)}${popRow('Installed', esc(c.installed || '?'))}${popRow('Tickets until Nov 2025', fmt(c.tickets))}`))),
  };
  const sync = () => Object.entries(layers).forEach(([key, layer]) => { if ($(`lyr-${key}`).checked) layer.addTo(map); else map.removeLayer(layer); });
  Object.keys(layers).forEach(key => $(`lyr-${key}`).addEventListener('change', sync));
  sync();
}
// Shaded p25–p75 band per series, drawn behind the median lines.
const bandPlugin = bands => ({id:'band', beforeDatasetsDraw(c) {
  const {ctx, scales:{x, y}} = c; ctx.save();
  for (const b of bands) {
    const pts = b.rows.map((r,i) => r && {x:x.getPixelForValue(i), lo:y.getPixelForValue(r.p25), hi:y.getPixelForValue(r.p75)}).filter(Boolean);
    if (pts.length < 2) continue;
    ctx.beginPath(); pts.forEach((p,i) => i ? ctx.lineTo(p.x,p.hi) : ctx.moveTo(p.x,p.hi)); [...pts].reverse().forEach(p => ctx.lineTo(p.x,p.lo)); ctx.closePath();
    ctx.fillStyle = b.colour; ctx.globalAlpha = .12; ctx.fill();
  }
  ctx.restore();
}});
const refLine = value => ({id:'ref', beforeDatasetsDraw(c) {
  const {ctx, chartArea:{left, right}, scales:{y}} = c, yy = y.getPixelForValue(value);
  ctx.save(); ctx.setLineDash([4,4]); ctx.strokeStyle = css('--ink-3'); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(left,yy); ctx.lineTo(right,yy); ctx.stroke(); ctx.restore();
}});
async function renderWhere(token) {
  $('filters').innerHTML = '';
  $('section-kicker').textContent = '02 · Where it happens';
  $('section-title').textContent = 'Where people get hurt, and where police stop drivers';
  $('section-description').textContent = 'City collision records and police traffic stops, joined on the City’s own road network and rolled up to the police’s neighbourhoods. Camera locations and traffic counts add context.';
  $('filter-scope').textContent = 'No filters on this tab: each view uses every available year. Collisions are 2017–2024 without 2023; police stops end in 2024.';
  $('stats').innerHTML = '';
  $('panels').innerHTML = '<p class="note">Loading neighbourhood data…</p>';
  exports = [['neighbourhood','police_stops','injury_collisions','share_stops_pct','share_injury_pct','stops_vs_harm_index','charged_pct']];
  let stories, areas;
  try {
    [stories, areas] = await Promise.all([loadStories(), loadAreas()]);
  } catch(e) {
    if (token === generation) $('panels').innerHTML = `<p class="empty">Neighbourhood data could not load (${esc(e.message)}). Switch tabs and back to retry.</p>`;
    return;
  }
  if (token !== generation) return;
  const e = stories.enforcement_vs_harm, d = stories.danger_intersections;
  const idx = e.areas.filter(a=>a.index).sort((a,b)=>b.index-a.index), top = idx.slice(0,10), bottom = idx.slice(-10);
  const share = (rows, k, digits) => sum(rows.map(a=>a[k])).toFixed(digits);
  $('stats').innerHTML = stat(`${share(top,'share_stops_pct',0)}% / ${share(top,'share_injury_pct',0)}%`,'Share of stops vs share of injury crashes in the 10 neighbourhoods with the most stops relative to harm')
    + stat(`${share(bottom,'share_stops_pct',1)}% / ${share(bottom,'share_injury_pct',1)}%`,'The same shares in the 10 neighbourhoods with the fewest')
    + stat(`${idx[0].index.toFixed(1)}× · ${idx.at(-1).index.toFixed(2)}×`,`Highest and lowest: ${esc(idx[0].neighbourhood)} · ${esc(idx.at(-1).neighbourhood)}`);
  const scale = divTokens.map(t=>`<span style="background:${css(t)}"></span>`).join('');
  const dangerRows = d.rows.slice(0,15).map((r,i)=>`<tr><td class="num">${i+1}</td><td>${esc(titleCase(r.name))}<span class="muted">${esc(r.neighbourhood || '')}</span></td><td class="num">${fmt(r.collisions)}<span class="muted">${fmt(r.injury_collisions)} injury</span></td><td class="num">${fmt(r.aadt)}<span class="muted">${esc(r.aadt_year)}</span></td><td class="num"><b>${r.per_mev.toFixed(2)}</b></td><td class="num">${fmt(r.police_stops)}</td></tr>`).join('');
  const v = stories.volume_index.by_year, last = v.at(-1);
  $('panels').innerHTML = `<div class="grid">
    <article class="card wide"><h3>Enforcement vs harm, by neighbourhood</h3><p class="note">Each neighbourhood’s share of the city’s ${fmt(e.total_police_stops)} police traffic stops, divided by its share of the city’s ${fmt(e.total_injury_collisions)} injury collisions (${esc(e.years[0])}–${esc(e.years.at(-1))}, without 2023). 1× means stops match harm. Select a neighbourhood for its numbers.</p>
      <div class="chips" role="group" aria-label="Map layers"><label class="chip"><input type="checkbox" id="lyr-danger" checked><span class="dot dot-solid"></span>Riskiest busy intersections</label><label class="chip"><input type="checkbox" id="lyr-rlc"><span class="dot"></span>Red-light cameras</label><label class="chip"><input type="checkbox" id="lyr-ase"><span class="dot dot-muted"></span>Photo-radar sites (off since Nov 2025)</label></div>
      <div id="where-map" class="map tall-map" role="region" aria-label="Map of Ottawa neighbourhoods shaded by police stops relative to injury collisions"></div>
      <div class="scale" aria-hidden="true"><div><div class="scale-bar">${scale}</div><div class="scale-ends"><span>¼×</span><span>1×</span><span>4×</span></div></div><span>← fewer stops than its share of injury crashes · more →</span><span class="scale-none"><span></span>under 20 injury crashes, no index</span></div>
      <details class="chart-data"><summary>All ${fmt(e.areas.length)} neighbourhoods</summary><div class="table-wrap">${table(['Neighbourhood','Stops vs harm (×)','Share of stops %','Share of injury crashes %','Police stops','Injury crashes'],[...e.areas].sort((a,b)=>(b.index ?? -1)-(a.index ?? -1)).map(a=>[a.neighbourhood,a.index == null ? 'no index' : Number(a.index.toFixed(2)),a.share_stops_pct,a.share_injury_pct,a.police_stops,a.injury_collisions]))}</div></details></article>
    <article class="card wide"><h3>The biggest gaps</h3><p class="note">The 10 neighbourhoods with the most stops relative to injury crashes, and the 10 with the fewest. Bars run from 1× (stops exactly match harm), on a doubling scale. Stops include every reason an officer pulls a driver over; collisions are those reported to police. Population plays no part: a low-population area on a highway corridor can carry many crashes.</p><div class="chart-box xtall"><canvas id="extremes" role="img" aria-label="Neighbourhoods with the highest and lowest ratio of police-stop share to injury-collision share; values in the data table below"></canvas></div><div id="extremes-data"></div></article>
    <article class="card wide"><h3>Riskiest busy intersections</h3><p class="note">Collisions per million vehicles entering the intersection, so a busy intersection isn’t ranked high just for being busy. Only intersections with at least ${fmt(d.min_aadt)} vehicles a day and ${esc(d.min_collisions)}+ collisions (${fmt(d.candidates)} qualify); top 15 shown, top 30 on the map. Vehicles per day is the latest City count there, with its year.</p><div class="table-wrap"><table><thead><tr><th scope="col" class="num">#</th><th scope="col">Intersection</th><th scope="col" class="num">Collisions 2017–24</th><th scope="col" class="num">Vehicles / day</th><th scope="col" class="num">Per million vehicles</th><th scope="col" class="num">Police stops</th></tr></thead><tbody>${dangerRows}</tbody></table></div></article>
    <article class="card wide"><p class="eyebrow">Context · traffic volume</p><h3>Is traffic back to pre-pandemic levels?</h3><p class="note">Each intersection the City counted is compared with its own 2015–2019 average, because the City counts different intersections each year. Lines are medians; bands hold the middle half. Counts are short studies scaled to 24 hours, and 2025 uses a slightly different City method: read the trend, not the decimal.</p>
      <div class="stats">${stat(`${last.city.median}%`,`City-wide, ${esc(last.year)} (${fmt(last.city.n)} intersections)`)}${stat(last.core ? `${last.core.median}%` : '—',`Downtown core (within 4 km of Parliament), ${esc(last.year)}`)}${stat(`${last.outside_core.median}%`,`Rest of the city, ${esc(last.year)}`)}</div>
      <div class="grid"><div><p class="eyebrow">Median volume vs 2015–19</p><div class="chart-box"><canvas id="volume" role="img" aria-label="Median intersection traffic volume as a percentage of 2015 to 2019, downtown core versus the rest of the city; values in the data table below"></canvas></div><div id="volume-data"></div></div><div><p class="eyebrow">2020–22 · monthly pandemic monitoring</p><div class="chart-box"><canvas id="covid" role="img" aria-label="Monthly traffic as a percentage of normal, 2020 to 2022; values in the data table below"></canvas></div><div id="covid-data"></div></div></div></article>
  </div>`;
  exports.push(...e.areas.map(a=>[a.neighbourhood,a.police_stops,a.injury_collisions,a.share_stops_pct,a.share_injury_pct,a.index ?? '',a.charged_pct ?? '']));
  const ext = top.concat(bottom);
  chart('extremes','bar',ext.map(r=>r.neighbourhood),[{label:'Stops vs harm',data:ext.map(r=>Math.log2(r.index)),backgroundColor:ext.map(r=>css(r.index >= 1 ? '--div-c3' : '--div-w3')),barThickness:14}],
    {horizontal:true, x:{min:-2,max:2,ticks:{color:css('--ink-2'),stepSize:1,callback:t=>({'-2':'¼×','-1':'½×','0':'1×','1':'2×','2':'4×'})[t] ?? ''}}, y:{ticks:{color:css('--ink-2'),autoSkip:false,callback(t) { const name = this.getLabelForValue(t), max = innerWidth < 640 ? 16 : 40; return name.length > max ? name.slice(0,max-1).trimEnd()+'…' : name; }}},
     label:ctx=>{ const r = ext[ctx.dataIndex]; return [`${r.index.toFixed(2)}× its share`,`${r.share_stops_pct.toFixed(2)}% of stops · ${r.share_injury_pct.toFixed(2)}% of injury crashes`]; }});
  $('extremes-data').innerHTML = `<details class="chart-data"><summary>View chart data</summary><div class="table-wrap">${table(['Neighbourhood','Stops vs harm (×)','Share of stops %','Share of injury crashes %'],ext.map(r=>[r.neighbourhood,Number(r.index.toFixed(2)),r.share_stops_pct,r.share_injury_pct]))}</div></details>`;
  const series = (key, label, colour) => ({label, borderColor:css(colour), backgroundColor:css(colour), data:v.map(r=>r[key] ? r[key].median : null), spanGaps:true, tension:.25});
  chart('volume','line',v.map(r=>String(r.year)),[series('core','Downtown core %','--accent'),series('outside_core','Rest of the city %','--accent-2')],
    {y:{beginAtZero:false,suggestedMin:50,suggestedMax:120,ticks:{color:css('--ink-2'),callback:t=>`${t}%`}}, plugins:[refLine(100), bandPlugin([{rows:v.map(r=>r.core),colour:css('--accent')},{rows:v.map(r=>r.outside_core),colour:css('--accent-2')}])],
     label:ctx=>{ const r = v[ctx.dataIndex][ctx.datasetIndex ? 'outside_core' : 'core'], name = ctx.dataset.label.slice(0,-2); return r ? `${name}: ${r.median}% (middle half ${r.p25}–${r.p75}%, n=${r.n})` : `${name}: too few counts`; }});
  const c = stories.covid_monthly;
  chart('covid','line',c.map(m=>`${monthNames[Number(m.month.slice(5,7))-1]} ${m.month.slice(0,4)}`),[{label:'Monitored intersections %',data:c.map(m=>m.intersections),borderColor:css('--accent-2'),pointRadius:0,spanGaps:true},{label:'Macdonald-Cartier Bridge %',data:c.map(m=>m.bridge),borderColor:css('--accent'),pointRadius:0,spanGaps:true,borderDash:[]}],
    {y:{max:110,ticks:{color:css('--ink-2'),callback:t=>`${t}%`}}, plugins:[refLine(100)]});
  whereMap(stories, areas);
}
function cameraPeriod(rows) {
  if (!rows.length) return 'No reported months';
  const months = [...new Set(rows.map(r=>`${r[0]}-${String(r[1]).padStart(2,'0')}`))].sort();
  return `${months[0]} to ${months.at(-1)}`;
}
function renderCameras(state, token) {
  const speed = section==='speed', c = data[section];
  const years = [...new Set(c.months.map(r=>r[0]))].sort();
  const options = c.sites.map((s,i)=>[String(i),`${speed ? s.id+' · ' : ''}${s.name}${s.direction ? ' · '+s.direction : ''}`]).sort((a,b)=>a[1].localeCompare(b[1]));
  $('filters').innerHTML = select('year','Violation year',yearsOptions(years),state.year)+select('site',speed?'Camera site':'Camera approach',[['all','All locations'],...options],state.site)+select('metric','Monthly chart measure',[['total','Total violations'],['per-camera','Per reporting camera']],state.metric);
  $('section-kicker').textContent = speed ? '05 · Speed cameras' : '06 · Red-light cameras';
  $('section-title').textContent = speed ? 'Speed-camera violations, through the program’s end' : 'Red-light violations at monitored approaches';
  $('section-description').textContent = speed ? 'Monthly automated speed enforcement records through November 2025. Enforcement ended November 14, 2025.' : 'Monthly recorded violations, including the available 2026 months. More cameras can increase the total even if driver behaviour is unchanged.';
  $('filter-scope').textContent = 'Year and location affect the summary, monthly chart and map. The annual chart retains all years for the selected location. “Per reporting camera” changes the monthly chart only. Missing months are not treated as zero.';
  const atSite = c.months.filter(r=>state.site==='all'||String(r[2])===state.site);
  const rows = atSite.filter(r=>all(r[0],state.year));
  const total = sum(rows.map(r=>r[3])), reporters = new Set(rows.map(r=>r[2])).size;
  $('stats').innerHTML = stat(fmt(total),'Reported violations · selected year(s) and location')+stat(fmt(reporters),speed?'Sites with at least one published month':'Approaches with at least one published month')+stat(rows.length ? cameraPeriod(rows).split(' to ').at(-1) : '—','Latest published month in this selection');
  const caveat = speed ? '<div class="notice">The speed-camera program ended November 14, 2025. November covers a shortened operating period. There is no 2026 ticket series to extend. <a href="https://ottawa.ca/en/city-hall/city-news/newsroom/changes-coming-automated-speed-enforcement">City announcement</a>.</div>' : `<div class="notice">Published months in this selection: ${esc(cameraPeriod(rows))}. Each line follows only months with a reported value; an incomplete year is not comparable to a full-year total.</div>`;
  $('panels').innerHTML = caveat+'<div class="grid">'+panel('camera-monthly','Monthly violations',`${state.metric==='total'?'Total violations':'Violations per reporting camera approach/site (including reported zeroes)'}. Each year is a separate line. Missing months stay blank.`,true)+panel('camera-annual','Annual totals and coverage','All years for the selected location. Month coverage is shown in the labels. Latest periods can be partial.',true)+(speed?panel('speed-stats','Recorded speeds and compliance','Select a single camera site to see its average speed, 85th-percentile speed and compliance. No traffic-volume weighting is available.',true):'')+mapPanel(speed?'Speed-camera sites':'Red-light-camera approaches',`${esc(state.year==='all'?'All available years':state.year)} · selected location(s). Counts reflect enforcement and camera coverage, not all driving violations.`)+'</div>';
  chart('camera-monthly','line',monthNames,years.filter(y=>all(y,state.year)).map(y=>({label:String(y),data:monthNames.map((_,i)=>{
    const month = rows.filter(r=>r[0]===y&&r[1]===i+1);
    return month.length ? sum(month.map(r=>r[3]))/(state.metric==='per-camera'?month.length:1) : null;
  })})));
  const annualLabels = years.map(y=>{
    const reported = [...new Set(atSite.filter(r=>r[0]===y).map(r=>r[1]))].sort((a,b)=>a-b);
    return `${y} · ${reported.length}/12 months`;
  });
  chart('camera-annual','bar',annualLabels,[{label:'Violations',data:years.map(y=>{const yr=atSite.filter(r=>r[0]===y);return yr.length?sum(yr.map(r=>r[3])):null;})}]);
  if (speed) {
    if (state.site==='all') {
      $('speed-stats').parentNode.innerHTML = '<p class="empty">Choose one camera site above to inspect speed and compliance data. An unweighted citywide average could be misleading.</p>';
    } else {
      const site = c.sites[Number(state.site)], readings = data.speeds.filter(r=>r[0]===site.id&&all(r[1].slice(0,4),state.year)).sort((a,b)=>a[1].localeCompare(b[1]));
      if (!readings.length) $('speed-stats').parentNode.innerHTML = '<p class="empty">No published speed readings for this site and year selection.</p>';
      else {
        // Keep speed and percentage in separate series/units. The percentage is
        // available in the data table, not drawn on a misleading km/h axis.
        chart('speed-stats','line',readings.map(r=>r[1].slice(0,7)),[{label:'Average speed (km/h)',data:readings.map(r=>r[2])},{label:'85th percentile (km/h)',data:readings.map(r=>r[3])}]);
        $('speed-stats-data').insertAdjacentHTML('beforeend',`<details class="chart-data"><summary>View speed-limit compliance (%)</summary><div class="table-wrap">${table(['Month','Compliance (%)'],readings.map(r=>[r[1].slice(0,7),r[4]]))}</div></details>`);
      }
    }
  }
  const points = [...aggregate(rows,r=>r[2],r=>r[3])].map(([i,n])=>({...c.sites[i],n})).filter(s=>s.lat!=null&&s.lon!=null).map(s=>({...s,name:s.name+(s.direction?' · '+s.direction:'')}));
  mapPoints(points,cameraPeriod(rows));
  if (speed) { renderAseSummary(); renderMonitoring(state); }
  $('panels').insertAdjacentHTML('beforeend','<div id="camera-stories"></div>');
  exports = [['year','month','site_or_approach','location','direction','violations'],...rows.map(r=>[r[0],r[1],c.sites[r[2]].id,c.sites[r[2]].name,c.sites[r[2]].direction,r[3]])];
  return renderCameraStories(speed, token);
}
// All monitored sites by program stage (formerly the photo-radar card on Vehicles/road-safety.html).
function renderAseSummary() {
  const obs = data.monitoring, pre = obs.filter(r=>r.stage==='Pre ASE Installation');
  const staged = obs.filter(r=>r.month && r.stage!=='Pre ASE Installation');
  const avgOf = a => a.length ? +(sum(a)/a.length).toFixed(1) : null;
  const sorted = staged.map(r=>r.month).sort(), months = [];
  for (let [y, m] = sorted[0].split('-').map(Number); `${y}-${String(m).padStart(2,'0')}` <= sorted.at(-1); m === 12 ? (y++, m = 1) : m++) months.push(`${y}-${String(m).padStart(2,'0')}`);
  const at = (stage, month, k) => avgOf(staged.filter(r=>r.stage===stage && r.month===month && r[k]!=null).map(r=>r[k]));
  const series = (stage, k) => months.map(m=>at(stage, m, k));
  const lastOf = stage => staged.filter(r=>r.stage===stage).map(r=>r.month).sort().at(-1);
  const lastOn = lastOf('ASE Active'), lastOff = lastOf('ASE Removed');
  const preC = avgOf(pre.map(r=>r.pct_compliance)), preH = avgOf(pre.map(r=>r.pct_high_end_speeders));
  const sites = new Set(obs.map(r=>r.site_id)).size, label = ym => `${monthNames[Number(ym.slice(5))-1]} ${ym.slice(0,4)}`;
  $('panels').insertAdjacentHTML('beforeend',`<section class="card"><p class="eyebrow">All ${sites} monitored school-zone sites</p><h3>Photo radar: on, then off</h3><p class="note">Monthly averages across the ${sites} sites the City measured before, during and after camera operation. Ontario’s Bill 56 switched every camera off on November 14, 2025; the City kept measuring speeds afterwards. Dashed line: before the cameras (one reading per site). Sampled speeds, not tickets, and not a causal estimate.</p><div class="stats">${stat(`${preC}%`,'Compliance before cameras')}${stat(lastOn ? `${at('ASE Active',lastOn,'pct_compliance')}%` : '—',`With cameras (${lastOn ? label(lastOn) : 'no reading'})`)}${stat(lastOff ? `${at('ASE Removed',lastOff,'pct_compliance')}%` : '—',`Cameras off (${lastOff ? label(lastOff) : 'no reading'})`)}</div><div class="grid">${panel('ase-compliance','Compliance with the speed limit','Average share of observed drivers at or under the limit.')}${panel('ase-highend','High-end speeding','Average share more than 15 km/h over the limit.')}</div></section>`);
  const off = series('ASE Removed','pct_high_end_speeders'), on = series('ASE Active','pct_high_end_speeders');
  const peak = Math.max(preH, ...on.concat(off).filter(v=>v!=null));
  chart('ase-compliance','line',months.map(label),[{label:'Cameras on',data:series('ASE Active','pct_compliance')},{label:'Cameras off',data:series('ASE Removed','pct_compliance')}],{percent:true,plugins:[refLine(preC)]});
  chart('ase-highend','line',months.map(label),[{label:'Cameras on',data:on},{label:'Cameras off',data:off}],{percent:true,y:{max:Math.ceil(peak/5)*5},plugins:[refLine(preH)]});
}
// Camera effects on collisions, from stories.json (formerly on Vehicles/road-safety.html).
async function renderCameraStories(speed, token) {
  let stories;
  try { stories = await loadStories(); }
  catch(e) { if (token === generation) $('camera-stories').innerHTML = '<p class="empty">Camera before/after data could not load. The violation records above are unaffected.</p>'; return; }
  if (token !== generation) return;
  const signed = p => `${p > 0 ? '+' : ''}${p}%`;
  if (speed) {
    const c = stories.ase_collisions;
    $('camera-stories').innerHTML = `<section class="card"><p class="eyebrow">Collisions at camera sites</p><h3>Did crashes drop where photo radar went in?</h3><div class="stats">${stat(c.before_rate,'Collisions per site per year before installation')}${stat(c.after_rate,'Collisions per site per year after installation')}${stat(fmt(c.after_site_years),`Site-years of after data, across ${fmt(c.sites)} sites`)}</div><p class="note">Too early to call: most cameras went in during 2023–24 and the City’s 2023 collision file is missing, so only ${fmt(c.after_site_years)} site-years of post-installation data exist, against ${fmt(c.before_site_years)} before.</p></section>`;
    return;
  }
  const ba = stories.rlc_before_after, types = ba.by_type, ages = stories.rlc_by_years_since.filter(a=>a.camera_months >= 250);
  const angle = types.find(t=>t.type.startsWith('Angle')), rear = types.find(t=>t.type==='Rear end');
  $('camera-stories').innerHTML = `<section class="card"><p class="eyebrow">Collisions before and after a camera</p><h3>Red-light cameras: the trade-off</h3><p class="note">Collisions per intersection per year at the ${fmt(ba.intersections)} intersections that got their first red-light camera in ${esc(String(ba.install_years).replace('-','–'))}: ${fmt(ba.before_site_years)} intersection-years before installation vs ${fmt(ba.after_site_years)} after. Angle and turning crashes, the kind red-light running causes, changed ${signed(angle.change_pct)}; rear-end crashes changed ${signed(rear.change_pct)} as drivers brake harder for yellows. A before/after comparison, not a controlled estimate.</p><div class="grid">${panel('rlc-before-after','Collisions per intersection-year, by type','Before vs after the first camera at the same intersections.')}${panel('rlc-age','Violations per camera per month, by camera age','Unlike photo radar, violations barely fade as cameras age. Ages with fewer than 250 camera-months are left out.')}</div></section>`;
  chart('rlc-before-after','bar',types.map(t=>t.type),[{label:'Before camera',data:types.map(t=>t.before_rate),backgroundColor:css('--ink-3')},{label:'After camera',data:types.map(t=>t.after_rate)}],
    {label:ctx=>{ const t = types[ctx.dataIndex]; return `${ctx.dataset.label}: ${ctx.raw.toFixed(2)} per year (${fmt(ctx.datasetIndex ? t.after : t.before)} collisions)${ctx.datasetIndex ? ` · ${signed(t.change_pct)}` : ''}`; }});
  $('rlc-before-after-data').innerHTML = `<details class="chart-data"><summary>View chart data</summary><div class="table-wrap">${table(['Collision type','Before, per year','After, per year','Change','Collisions before','Collisions after'],types.map(t=>[t.type,t.before_rate,t.after_rate,signed(t.change_pct),t.before,t.after]))}</div></details>`;
  chart('rlc-age','line',ages.map(a=>a.years_since_install ? `Year ${a.years_since_install}` : 'Install year'),[{label:'Violations per camera per month',data:ages.map(a=>a.avg_monthly)}],
    {label:ctx=>`${ctx.raw.toFixed(1)} per camera per month (${fmt(ages[ctx.dataIndex].camera_months)} camera-months)`});
}
function renderMonitoring(state) {
  const observations=data.monitoring;
  const sites=[...new Map(observations.map(r=>[r.site_id,r.location])).entries()].sort((a,b)=>a[0].localeCompare(b[0]));
  if (!sites.some(([id])=>id===state.monitor)) state.monitor=sites[0][0];
  const rows=observations.filter(r=>r.site_id===state.monitor);
  const dated=rows.filter(r=>r.month).sort((a,b)=>a.month.localeCompare(b.month));
  $('panels').insertAdjacentHTML('beforeend',`<section class="card"><p class="eyebrow">New data · after camera removal</p><h3>What happened to speeds at former camera sites?</h3><p class="note">Separate City monitoring observations through ${esc([...observations].filter(r=>r.month).map(r=>r.month).sort().at(-1))}. These are sampled speeds, not violations. The site selector below is independent of the ticket filters above. Sparse observations do not establish that removal caused a change.</p><div class="filters">${select('monitor','Monitoring site',sites.map(([id,name])=>[id,id+' · '+name]),state.monitor)}</div><div class="grid">${panel('monitor-speed','Speed observations','Average and 85th-percentile speed in km/h. Dates are month precision; the labels retain the published program stage.')}${panel('monitor-compliance','Speed-limit compliance','Percent of observed vehicles complying with the speed limit. Observations, not a continuous monitoring series.')}</div><details class="chart-data"><summary>View all observations, including undated baselines</summary><div class="table-wrap">${table(['Month','Stage','Average km/h','85th percentile km/h','Compliance %','High-end speeders %'],rows.map(r=>[r.month||'Undated',r.stage,r.avg_speed,r.pct85_speed,r.pct_compliance,r.pct_high_end_speeders]))}</div></details><p class="note"><a href="https://open.ottawa.ca/search?q=Automated%20Speed%20Enforcement%20Camera%20Removal">Official monitoring dataset</a> · <a href="data/city/ase_removal_monitoring.csv" download>Download all monitoring observations</a></p></section>`);
  const labels=dated.map(r=>`${r.month} · ${r.stage}`);
  chart('monitor-speed','line',labels,[{label:'Average (km/h)',data:dated.map(r=>r.avg_speed),showLine:false,pointRadius:3},{label:'85th percentile (km/h)',data:dated.map(r=>r.pct85_speed),showLine:false,pointRadius:3}]);
  chart('monitor-compliance','bar',labels,[{label:'Compliance (%)',data:dated.map(r=>r.pct_compliance)}],{percent:true});
}
async function render() {
  const token = ++generation;
  charts.forEach(c=>c.destroy()); charts=[];
  maps.forEach(m=>m.remove()); maps=[];
  document.querySelectorAll('[data-section]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.section===section)));
  $('summary').hidden = section!=='summary';
  $('report').hidden = section==='summary';
  if (section==='summary') { saveState(); return; }
  const state=initState(section);
  let mapTask;
  if (section==='stops') renderStops(state);
  else if (section==='drivers') renderDrivers(state);
  else if (section==='collisions') mapTask=renderCollisions(state,token);
  else if (section==='where') mapTask=renderWhere(token);
  else mapTask=renderCameras(state,token);
  if (token !== generation) return;
  document.querySelectorAll('#filters select, #monitor').forEach(input=>input.addEventListener('change',()=>{
    state[input.id]=input.value;
    const id=input.id;
    saveState(); render().then(()=>$(id)?.focus({preventScroll:true})).catch(reportError);
  }));
  saveState();
  if(mapTask) await mapTask;
}
function reportError(error) {
  $('load-status').hidden=false;
  $('load-status').className='error';
  $('load-status').replaceChildren(document.createTextNode(`Report could not load: ${error.message}. `));
  const retry=document.createElement('button'); retry.type='button'; retry.textContent='Retry'; retry.onclick=()=>location.reload();
  $('load-status').append(retry);
}
async function loadJSON(file) {
  const response=await fetch(BASE+file);
  if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
  return response.json();
}
window.setTheme=function(mode) {
  document.documentElement.setAttribute('data-theme',mode);
  try {localStorage.setItem('ov-theme',mode);} catch(e) { /* optional storage */ }
  if(data) render().catch(reportError);
};
document.querySelectorAll('[data-section]').forEach(button=>button.addEventListener('click',()=>{
  if(!data) return;
  section=button.dataset.section;
  render().then(()=>$(section==='summary'?'summary-title':'section-title').focus({preventScroll:true})).catch(reportError);
}));
$('download').addEventListener('click',()=>{
  // Keep source text from being interpreted as a spreadsheet formula.
  const csv=exports.map(row=>row.map(value=>{
    let text=String(value??'');
    if(typeof value==='string' && /^[=+@\-\t\r]/.test(text)) text="'"+text;
    return '"'+text.replace(/"/g,'""')+'"';
  }).join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download=`ottawa-${section}-${settings[section].year || 'all-years'}.csv`;a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
Promise.all([loadJSON('report.json'),loadJSON('sources.json')]).then(async result=>{
  [data,audit]=result;
  $('coverage').textContent=`Stops: ${data.police.years[0]}–${data.police.years.at(-1)} · Detailed collisions: 2017–2024, excluding 2023 · Speed cameras: through Nov 2025 · Red-light cameras: through ${cameraPeriod(data.redlight.months).split(' to ').at(-1)} · Crash news log: Dec 2025 to now, hourly`;
  $('update-note').innerHTML='Newer OPS summaries are available: <strong>2025 year-end</strong> and <strong>2026 through September 19</strong>. See the Collisions section. Detailed police-stop records still end in 2024.';
  $('checked').textContent=`Official catalogues and detailed record totals checked ${audit.checked_utc.slice(0,10)}. Report rebuilt ${data.built_utc.slice(0,10)}.`;
  const sourceRows=[
    ['Ottawa Police — traffic stops',audit.police.url,'2014–2024','No 2025 or 2026 stop records in the checked public layer.'],
    ['City — detailed collisions',audit.collisions.url,'2017–2022, 2024','2023 absent. No 2025/2026 detailed layer found in the checked catalogue.'],
    ['City — speed-camera violations','https://open.ottawa.ca/search?q=Automated%20Speed%20Enforcement',cameraPeriod(data.speed.months),'Program ended November 14, 2025.'],
    ['City — red-light violations','https://open.ottawa.ca/search?q=Red%20Light%20Camera',cameraPeriod(data.redlight.months),'Latest year is incomplete. Some sites have fewer months.'],
    ['City — monitoring after ASE removal','https://open.ottawa.ca/search?q=Automated%20Speed%20Enforcement%20Camera%20Removal','Dated observations through '+data.monitoring.filter(r=>r.month).map(r=>r.month).sort().at(-1),'Separate speed samples, not ticket counts. Undated baselines retained in the table.'],
    ['OPS — 2025 year-end summary',data.snapshots[0].source,'2025 vs 2024','Incidents, not people; separate reporting definitions.'],
    ['OPS — 2026 YTD summary',data.snapshots[1].source,'Through September 19 in both years','Partial year; citywide totals only.'],
    ['OPS — collision news releases','https://www.ottawapolice.ca/en/news/','December 2025 to now, checked hourly','Mostly fatal and serious crashes. Fields parsed from release text.'],
    ['CTV Ottawa — crash headlines','https://www.ctvnews.ca/ottawa/','December 2025 to now, checked hourly','Headlines only. One crash can have several stories.'],
  ];
  $('source-rows').innerHTML=sourceRows.map(r=>`<tr><td><a href="${esc(r[1])}" target="_blank" rel="noopener">${esc(r[0])}</a></td><td>${esc(r[2])}</td><td>${esc(r[3])}</td></tr>`).join('');
  $('load-status').hidden=true;
  await render();
}).catch(reportError);

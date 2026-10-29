'use strict';
window.setTheme = mode => {
  document.documentElement.dataset.theme = mode;
  try { localStorage.setItem('ov-theme', mode); } catch (_) { /* optional */ }
};
const el = id => document.getElementById(id);
const escapeText = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = value => Number(value).toLocaleString('en-CA', {maximumFractionDigits:1});
async function source(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
function table(id, headings, rows) {
  el(id).innerHTML = `<table><thead><tr>${headings.map(x=>`<th scope="col">${escapeText(x)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(x=>`<td>${escapeText(x)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function lineChart(rows, {title, max, step, unit='', width=600, height=300, yearGap=false}) {
  const left=46, right=width-30, top=30, bottom=height-34;
  const first=rows[0], last=rows.at(-1);
  const x = year => left+(year-first[0])/(last[0]-first[0])*(right-left);
  const y = value => bottom-value/max*(bottom-top);
  const points=rows.map(([year,value],i)=>`${!i || (yearGap && year!==rows[i-1][0]+1) ? 'M' : 'L'}${x(year).toFixed(1)},${y(value).toFixed(1)}`).join(' ');
  let grid='';
  for(let value=0;value<=max;value+=step) grid+=`<line class="chart-grid" x1="${left}" x2="${right}" y1="${y(value)}" y2="${y(value)}"/><text x="${left-10}" y="${y(value)+4}" text-anchor="end">${value>=1000 ? value/1000+'k' : value+unit}</text>`;
  const tickYears=[first[0],Math.round((first[0]+last[0])/2),last[0]];
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeText(title)}"><title>${escapeText(title)}</title>${grid}<path class="series" d="${points}"/>${[first,last].map(([year,value])=>`<circle class="dot" cx="${x(year)}" cy="${y(value)}" r="4"/><text class="point-label" x="${x(year)}" y="${y(value)-13}" text-anchor="${year===first[0]?'start':'end'}">${number(value)}${unit}</text>`).join('')}${tickYears.map(year=>`<text x="${x(year)}" y="${height-9}" text-anchor="${year===first[0]?'start':year===last[0]?'end':'middle'}">${year}</text>`).join('')}</svg>`;
}
function failure(id, link) {
  el(id).innerHTML=`<p>Preview data could not load. <a href="${link}">Open the report</a> for sources and available data.</p>`;
}
source('../Traffic/data/derived/stops_report/report.json').then(data=>{
  const rows=data.police.annual.filter(r=>r[1]==='Charged').map(r=>[r[0],r[2]]).sort((a,b)=>a[0]-b[0]);
  const first=rows[0],last=rows.at(-1),change=(last[1]/first[1]-1)*100;
  el('traffic-change').textContent=`${number(Math.abs(change))}%`;
  el('traffic-period').textContent=`${change<0?'fewer':'more'} stops resulting in a charge · ${last[0]} vs ${first[0]}`;
  el('traffic-preview').innerHTML=lineChart(rows,{title:`Stops resulting in a charge, ${first[0]} to ${last[0]}. ${number(first[1])} in ${first[0]}; ${number(last[1])} in ${last[0]}.`,max:Math.ceil(Math.max(...rows.map(r=>r[1]))/5000)*5000,step:5000,height:300});
  el('traffic-caption').textContent=`${first[0]}–${last[0]} · Annual stop records, not number of charges`;
  table('traffic-table',['Year','Stops resulting in a charge'],rows.map(([y,n])=>[y,number(n)]));
}).catch(()=>{failure('traffic-preview','stops.html');el('traffic-period').textContent='Preview unavailable';});
source('../Ottawa_Elections/ward_data.json').then(data=>{
  const sorted=Object.values(data).filter(w=>Number.isFinite(w.councillor?.participation)).sort((a,b)=>b.councillor.participation-a.councillor.participation);
  const rows=[...sorted.slice(0,3),...sorted.slice(-3)];
  const width=560,left=205,right=500;
  el('ward-preview').innerHTML=`<svg viewBox="0 0 ${width} 270" role="img" aria-label="2022 ballot turnout for the three highest and three lowest Ottawa wards; exact values in the source table"><title>Selected wards: 2022 ballot turnout</title>${[0,30,60].map(v=>`<line class="chart-grid" x1="${left+v/60*(right-left)}" x2="${left+v/60*(right-left)}" y1="10" y2="235"/><text x="${left+v/60*(right-left)}" y="260" text-anchor="middle">${v}%</text>`).join('')}${rows.map((w,i)=>{const y=20+i*36+(i>=3?10:0);return `<text x="${left-12}" y="${y+15}" text-anchor="end">${escapeText(w.name)}</text><rect class="${i<3?'bar':'bar-alt'}" x="${left}" y="${y}" width="${w.councillor.participation/60*(right-left)}" height="23" rx="2"/><text class="point-label" x="${left+w.councillor.participation/60*(right-left)+7}" y="${y+16}">${number(w.councillor.participation)}%</text>`;}).join('')}</svg>`;
  table('ward-table',['Ward','Ballot turnout (2022)'],rows.map(w=>[w.name,number(w.councillor.participation)+'%']));
}).catch(()=>failure('ward-preview','../Ottawa_Elections/ottawa_ward_elections.html'));
source('../Weather/data/weather_indices.json').then(data=>{
  const rows=data.years.filter(r=>r.complete&&Number.isFinite(r.mean_temp)).map(r=>[r.year,r.mean_temp]).sort((a,b)=>a[0]-b[0]);
  const max=Math.ceil(Math.max(...rows.map(r=>r[1]))/2)*2;
  el('weather-preview').innerHTML=lineChart(rows,{title:`Ottawa annual mean temperature, complete years ${rows[0][0]} to ${rows.at(-1)[0]}.`,max,step:2,unit:'°',width:560,height:270,yearGap:true});
  table('weather-table',['Year','Annual mean (°C)'],rows.map(([y,t])=>[y,number(t)]));
}).catch(()=>failure('weather-preview','../Weather/weather.html'));
document.querySelectorAll('[data-topic] button, button[data-topic]').forEach(button=>button.addEventListener('click',()=>{
  const topic=button.dataset.topic;
  document.querySelectorAll('button[data-topic]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  let count=0;
  document.querySelectorAll('[data-report]').forEach(report=>{report.hidden=topic!=='all'&&report.dataset.topic!==topic;if(!report.hidden)count++;});
  document.querySelector('.visual-stories').hidden=![...document.querySelectorAll('.story')].some(r=>!r.hidden);
  document.querySelector('.report-list').hidden=![...document.querySelectorAll('.report-list>a')].some(r=>!r.hidden);
  el('filter-count').textContent=`${count} report${count===1?'':'s'}${topic==='all'?'':' · '+button.textContent}`;
}));

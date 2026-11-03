/* Buildless, source-linked education explorer. Suppressed counts stay bounded. */
(() => {
'use strict';
const D=window.EDUCATION_DATA,$=id=>document.getElementById(id);
if(!D){$('error').hidden=false;return;}
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(n,d=1)=>n===null||n===undefined?'Unavailable':n.toLocaleString('en-CA',{minimumFractionDigits:d,maximumFractionDigits:d});
const schoolYear=y=>`${y}–${String(y+1).slice(2)}`;
const colour=i=>getComputedStyle(document.documentElement).getPropertyValue(['--blue','--teal','--orange'][i%3]).trim();
const boardLabels={ocdsb:'OCDSB · English public',ocsb:'OCSB · English Catholic',cepeo:'CEPEO · French public',cecce:'CECCE · French Catholic'};
const groups={all:'All reported classes',kindergarten:'Kindergarten-only classes',primary:'Grades 1–3-only classes',upper:'Grades 4–8-only classes',mixed:'Classes across grade bands'};
function range(low,high,d=1){
 if(low===null||low===undefined||!Number.isFinite(low))return 'Unavailable';
 if(low===high)return fmt(low,d);
 const scale=10**d;return `${fmt(Math.floor((low+1e-10)*scale)/scale,d)}–${fmt(Math.ceil((high-1e-10)*scale)/scale,d)}`;
}
function table(id,heads,rows){$(id).innerHTML=`<table><thead><tr>${heads.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((v,i)=>`<${i?'td':'th scope="row"'}>${v}</${i?'td':'th'}>`).join('')}</tr>`).join('')}</tbody></table>`;}
function stats(id,items){$(id).innerHTML=items.map(([label,value,note])=>`<article class="stat"><p>${esc(label)}</p><strong class="value">${esc(value)}</strong><p>${esc(note)}</p></article>`).join('');}
function legend(id,names){$(id).innerHTML=names.map((name,i)=>`<span><i class="key" style="background:${colour(i)}"></i>${esc(name)}</span>`).join('');}
function chart(id,series,{readout,unit,format=n=>fmt(n),title,integerAxis=false,reference=null}){
 const el=$(id),valid=series.flatMap(s=>s.points).filter(p=>Number.isFinite(p.low));
 if(!valid.length){el.innerHTML='<div class="empty"><strong>No comparable records for this selection</strong>Try another selection. Missing records are not zero.</div>';$(readout).textContent='';return;}
 const width=Math.max(240,Math.round(el.getBoundingClientRect().width)),height=width>650?300:245,m={l:53,r:18,t:20,b:40},pw=width-m.l-m.r,ph=height-m.t-m.b;
 const years=[...new Set(valid.map(p=>p.year))].sort((a,b)=>a-b),first=years[0],last=years.at(-1);
 const max=Math.max(...valid.map(p=>p.high),reference?.value||0,.1)*1.13,raw=max/4,pow=10**Math.floor(Math.log10(raw)),niceStep=[1,2,2.5,5,10].find(v=>v*pow>=raw)*pow,step=integerAxis?Math.max(1,niceStep):niceStep,ymax=Math.ceil(max/step)*step;
 const x=y=>m.l+(first===last?.5:(y-first)/(last-first))*pw,y=v=>m.t+ph*(1-v/ymax);
 const tickYears=years.filter((v,i)=>i===0||i===years.length-1||((i%Math.ceil((years.length-1)/(width<600?3:5)))===0&&x(last)-x(v)>65));
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="${esc(title)}"><title>${esc(title)}</title>`;
 const tickDecimals=Number.isInteger(step)?0:Math.max(1,-Math.floor(Math.log10(step)));
 for(let v=0;v<=ymax+step/10;v+=step)svg+=`<line class="grid" x1="${m.l}" x2="${width-m.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${m.l-8}" y="${y(v)+4}" text-anchor="end">${fmt(v,tickDecimals)}</text>`;
 tickYears.forEach(v=>{const label=width<600?`${String(v).slice(-2)}–${String(v+1).slice(-2)}`:schoolYear(v);svg+=`<text x="${x(v)}" y="${height-12}" text-anchor="${v===first?'start':v===last?'end':'middle'}">${label}</text>`;});
 if(reference)svg+=`<line class="reference-line" x1="${m.l}" x2="${width-m.r}" y1="${y(reference.value)}" y2="${y(reference.value)}" stroke="var(--ink-2)" stroke-dasharray="5 5"/><text x="${m.l+3}" y="${y(reference.value)-6}">${esc(reference.label)}</text>`;
 let initial,lookup=[];
 series.forEach((s,i)=>{
  let previous=null;
  for(const p of s.points){
   if(!Number.isFinite(p.low)){previous=null;continue;}
   const cc=colour(i);
   if(previous&&!p.breakBefore&&p.year===previous.year+1){
    svg+=`<path class="data-line" stroke="${cc}" d="M${x(previous.year)},${y(previous.low)}L${x(p.year)},${y(p.low)}"/>`;
    if(p.high!==p.low||previous.high!==previous.low)svg+=`<path class="range-area" fill="${cc}" d="M${x(previous.year)},${y(previous.low)}L${x(p.year)},${y(p.low)}L${x(p.year)},${y(p.high)}L${x(previous.year)},${y(previous.high)}Z"/>`;
   }
   const text=`${schoolYear(p.year)} · ${s.name}: ${p.label||range(p.low,p.high)} ${unit}${p.note?' · '+p.note:''}`;
   if(p.low!==p.high)svg+=`<path class="range" stroke="${cc}" fill="none" d="M${x(p.year)},${y(p.low)}V${y(p.high)}M${x(p.year)-4},${y(p.low)}h8M${x(p.year)-4},${y(p.high)}h8"/>`;
   svg+=`<circle class="point" tabindex="0" role="button" aria-label="${esc(text)}" data-point="${lookup.length}" cx="${x(p.year)}" cy="${y(p.low)}" r="3.5" fill="${cc}" style="stroke:${cc}"><title>${esc(text)}</title></circle>`;
   lookup.push(text);if(i===0)initial=text;previous=p;
  }
 });
 el.innerHTML=svg+'</svg>';
 const show=t=>$(readout).textContent=t;
 el.querySelectorAll('[data-point]').forEach(p=>{const showPoint=()=>show(lookup[Number(p.dataset.point)]);['pointerenter','focus','click'].forEach(e=>p.addEventListener(e,showPoint));p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();showPoint();}});});
 show(initial||lookup.at(-1));
}

let currentFinance=[];
function finances(){
 const view=$('finance-view').value,real=$('prices').value==='real',start=Number($('finance-start').value),key=real?'real_cad':'cad';
 const select=(table,category)=>D.finance.filter(r=>r.table===table&&r.category===category&&r.year>=start);
 let series;
 if(view==='province')series=[{name:'Provincial government funding',rows:select('37100067','provincial government sources')}];
 if(view==='schools')series=[{name:'Public education expenditure',rows:select('37100066','Public elementary and secondary education expenditures')},{name:'Private-school expenditure',rows:select('37100066','Private elementary and secondary school expenditures')}];
 if(view==='funders'){
  const fees=select('37100067','student and other school fees'),other=select('37100067','other private sector sources');
  const combined=fees.map(a=>{const b=other.find(b=>b.year===a.year);return {...a,category:'Fees + other private-sector sources',cad:b&&a.cad!==null&&b.cad!==null?a.cad+b.cad:null,real_cad:b&&a.real_cad!==null&&b.real_cad!==null?a.real_cad+b.real_cad:null,vector:a.vector+' + '+b.vector,coordinate:a.coordinate+' + '+b.coordinate,status:[a.status,b.status].filter(Boolean).join(' / ')};});
  series=[{name:'All government funding',rows:select('37100067',"all governments' sources")},{name:'Private funding · fees + other',rows:combined}];
 }
 $('finance-definition').textContent=view==='province'?'Direct provincial-government funding for Ontario elementary and secondary education. It excludes funding recorded under local and federal sources. This source-of-funds measure is broader than one Ministry budget line and does not show a payment split between public and private schools.':view==='funders'?'Financing sources across public and private education. All government sources include provincial, local and federal funding. Fees and other private-sector funding can also support public education.':'Spending by education sector, from all funding sources. Public education includes school boards and other public components, including direct government spending and federal schools. This is broader than public school-board expenditure alone.';
 const prepared=series.map(s=>({...s,points:s.rows.map(r=>({year:r.year,low:r[key]===null?null:r[key]/1e9,high:r[key]===null?null:r[key]/1e9,label:r[key]===null?'Unavailable':'$'+fmt(r[key]/1e9,2),breakBefore:r.year===2012||(r.private_estimate&&r.year===2006),note:[r.private_estimate?'Private-school estimate':'',r.status?'Source flag '+r.status:''].filter(Boolean).join(' · ')}))}));
 const valid=prepared[0].points.filter(p=>p.low!==null),first=valid[0],last=valid.at(-1);
 $('finance-chart-title').textContent=view==='schools'?'Public and private education spending':view==='funders'?'Public and private financing':'Provincial education funding';
 stats('finance-stats',[[`${schoolYear(last.year)} · ${real?'adjusted':'nominal'}`,'$'+fmt(last.low,2)+'B',series[0].name],[`${schoolYear(first.year)} → ${schoolYear(last.year)}`,`${last.low>=first.low?'+':''}${fmt((last.low/first.low-1)*100)}%`,start<2012?'Spans a methodology change':'Change in selected dollar basis'],['Latest financial year',schoolYear(last.year),'Reported history; no budget forecasts']]);
 chart('finance-chart',prepared,{readout:'finance-readout',unit:'CAD billions',title:$('finance-chart-title').textContent});legend('finance-legend',series.map(s=>s.name));
 $('finance-note').textContent=real?'Adjusted to 2023–24 purchasing power using Ontario all-items CPI, averaging the two calendar years. This is a consumer-price proxy, not an education cost measure. Earlier than 1979–80: adjustment unavailable; nominal history remains downloadable.':'Nominal dollars of each year. Dollar growth includes price changes. Source values are rounded to thousands; components can differ from published totals through rounding.';
 currentFinance=series.flatMap(s=>s.rows.map(r=>({...r,display_series:s.name,selected_cad:r[key],dollar_basis:real?'2023-24 CPI proxy dollars':'Nominal dollars'})));
 table('finance-table',['School year','Series','Selected CAD','Source CAD','Status / estimate','Source'],currentFinance.map(r=>[schoolYear(r.year),esc(r.display_series),r.selected_cad===null?'Unavailable':'$'+fmt(r.selected_cad,0),r.cad===null?'Unavailable':'$'+fmt(r.cad,0),esc([r.private_estimate?'Estimated private-school spending':'',r.status].filter(Boolean).join(' · ')||'No source flag'),`<a href="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=${r.table}01">${r.table}</a> · ${esc(r.vector)} · ${esc(r.coordinate)}`]));
}

const values=(r,measure)=>measure==='count'?[r.classes,r.classes]:measure==='over25'?[100*r.over25_low/r.classes,100*r.over25_high/r.classes]:[r.students_low/r.classes,r.students_high/r.classes];
function point(r,measure='average'){const [low,high]=values(r,measure);return {year:r.year,low,high,label:range(low,high,measure==='count'?0:1),note:r.suppressed_classes?`${fmt(r.suppressed_classes,0)} classes contain suppressed cells`:''};}
function classTable(id,rows,withSchool=false){
 table(id,['School year',withSchool?'Source / status':'Area','Reported classes','Students · lower','Students · upper','Average range','Classes >25 · range','Suppressed classes'],rows.map(r=>[schoolYear(r.year),withSchool?`<a href="${esc(D.coverage.find(c=>c.year===r.year).url)}">Source workbook</a>${r.ambiguous_name?' · Ambiguous name/class keys':''}`:esc(r.geo==='ontario'?'Ontario':boardLabels[r.geo]),fmt(r.classes,0),fmt(r.students_low,0),fmt(r.students_high,0),range(...values(r,'average')),range(r.over25_low,r.over25_high,0),fmt(r.suppressed_classes,0)]));
}
function classHistory(){
 const geo=$('class-board').value,group=$('class-group').value,measure=$('class-measure').value;
 const rows=D.classes.filter(r=>r.group===group&&[geo,'ontario'].includes(r.geo));
 const own=rows.filter(r=>r.geo===geo),last=own.at(-1),[low,high]=values(last,measure);
 const unit=measure==='count'?'reported classes':measure==='over25'?'% of reported classes':'students per class';
 const name=boardLabels[geo];
 $('class-scope').textContent=`${D.boards[geo]} · Entire board territory. Ontario includes all boards in the class-size workbook. ${group==='all'||group==='upper'?'This comparison starts in 2014–15 because the early files omit grades-4–8-only classes.':'Earlier files cover kindergarten/primary and mixed classes, not all elementary grades.'} Class groups describe every grade present in a class.`;
 stats('class-stats',[[`${schoolYear(last.year)} · ${name}`,range(low,high,measure==='count'?0:1),unit],['Selected classes',fmt(last.classes,0),groups[group]],['Suppressed class rows',fmt(last.suppressed_classes,0),'Their missing cell values remain ranges']]);
 $('class-chart-title').textContent=groups[group];$('class-unit').textContent=unit;
 const series=[geo,'ontario'].map(g=>({name:g==='ontario'?'Ontario':name,points:rows.filter(r=>r.geo===g).map(r=>point(r,measure))}));
 chart('class-chart',series,{readout:'class-readout',unit,title:`${groups[group]} · ${unit} · ${name} and Ontario`});legend('class-legend',[name,'Ontario']);classTable('class-table',rows);
}
function schoolOptions(){
 const geo=$('school-board').value,query=$('school-search').value.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase(),previous=$('school-name').value;
 const names=[...new Set(D.schools.filter(r=>r.geo===geo).map(r=>r.school))].sort((a,b)=>a.localeCompare(b));
 const matches=names.filter(n=>n.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().includes(query));
 $('school-name').innerHTML=matches.map(n=>`<option>${esc(n)}</option>`).join('');
 if(matches.includes(previous))$('school-name').value=previous;
 $('school-search-note').textContent=`${matches.length} school names match. Schools with missing years or ambiguous names are not silently joined.`;
 schoolHistory();
}
function schoolHistory(){
 const geo=$('school-board').value,name=$('school-name').value,group=$('school-group').value;
 const own=D.schools.filter(r=>r.geo===geo&&r.school===name&&r.group===group),good=own.filter(r=>!r.ambiguous_name),latest=own.at(-1),last=good.at(-1);
 const board=D.classes.filter(r=>r.geo===geo&&r.group===group);
 $('school-scope').textContent=`${D.boards[geo]} · ${groups[group]}. ${own.some(r=>r.ambiguous_name)?'Some years contain repeated name/class keys. Those years are listed below but excluded from the school chart.':'Source names are used as published; this is not a verified school-ID history.'}`;
 $('school-chart-title').textContent=name||'No matching school';
 stats('school-stats',latest?[[`${schoolYear(latest.year)} · school`,latest.ambiguous_name?'Unavailable':range(...values(latest,'average')),latest.ambiguous_name?'Repeated name/class keys':groups[group]],['Reported classes',latest.ambiguous_name?'Unavailable':fmt(latest.classes,0),'Latest year for this source name'],['Last unambiguous year',last?schoolYear(last.year):'Unavailable','Missing and ambiguous years stay disconnected']]:[['School data','Unavailable','Try a different school name or class group']]);
 const byYear=new Map(own.map(r=>[r.year,r]));
 const schoolPoints=board.map(b=>{const r=byYear.get(b.year);return r&&!r.ambiguous_name?point(r):{year:b.year,low:null,high:null};});
 const series=[{name:name||'School',points:schoolPoints},{name:boardLabels[geo],points:name?board.map(r=>point(r)):[]}];
 chart('school-chart',series,{readout:'school-readout',unit:'students per class',title:`${name} · reported average class-size range`});
 if(!good.length)$('school-readout').textContent='No unambiguous school history for this selection. Board data, where shown, are a separate comparison.';
 legend('school-legend',[name||'School',boardLabels[geo]]);classTable('school-table',own,true);
}
function downloadFinance(){
 const keys=['period','display_series','selected_cad','dollar_basis','cad','status','private_estimate','table','vector','coordinate'],quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
 const text=[keys,...currentFinance.map(r=>keys.map(k=>r[k]))].map(r=>r.map(quote).join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob(['\uFEFF'+text],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='ontario-education-selected-view.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
const T=window.EDUCATION_THRESHOLDS;
function thresholds(){
 if(!T){$('threshold-error').hidden=false;return;}
 const geo=$('threshold-board').value,year=Number($('threshold-year').value),rule=T.rules.find(r=>r.id===$('threshold-rule').value),share=$('threshold-measure').value==='share',oecd=rule.family==='oecd',scope=$('threshold-scope').value;
 $('threshold-scope-control').hidden=!oecd;
 const rows=T.counts.filter(r=>r.geo===geo&&r.rule===rule.id&&r.year<=year&&r.scope===(oecd?scope:'rule')),last=rows.at(-1),area=geo==='ontario'?'Ontario combined':boardLabels[geo];
 const percent=r=>r.classes?[100*r.above_low/r.classes,100*r.above_high/r.classes]:[null,null];
 const [pl,ph]=percent(last);
 $('threshold-definition').textContent=`${rule.kind}. ${rule.note} ${oecd?'Ontario comparison scope: '+T.scopes[scope]+'. ':''}${geo==='ontario'?'Ontario totals combine boards; a combined share or average cannot establish board-level compliance.':D.boards[geo]+' · Entire board territory.'}`;
 stats('threshold-stats',[[`${schoolYear(year)} · above ${rule.limit}`,range(last.above_low,last.above_high,0),'Classes certainly above → possibly above'],[oecd?'Comparison classes':'Eligible reported classes',fmt(last.classes,0),last.classes?range(pl,ph)+'% above reference':'No eligible rows in this selection'],[oecd?'OECD published average':'Reference',`${rule.limit} students`,rule.kind]]);
 const unit=share?'% of eligible reported classes':'reported classes';
 $('threshold-chart-title').textContent=rule.label;$('threshold-unit').textContent=unit;
 chart('threshold-chart',[{name:area,points:rows.map(r=>{const [low,high]=share?percent(r):[r.above_low,r.above_high];return {year:r.year,low,high,label:range(low,high,share?1:0)};})}],{readout:'threshold-readout',unit,title:`${rule.label} · ${area} · fixed reference`,integerAxis:!share,reference:share&&rule.share_limit&&geo!=='ontario'?{value:rule.share_limit,label:'10% board-share reference'}:null});
 $('threshold-share-note').textContent=oecd?'Descriptive comparison only. Above the OECD average does not mean above a recommended maximum or a legal limit.':rule.share_limit?`Board-share reference: no more than ${rule.share_limit}% above ${rule.limit}. ${rule.id==='k29'?'That allowance requires specified exception conditions, and never permits a JK/K-only class above 32.':'Classes of 21–23 can be allowed within the board-share rule.'} No compliance verdict is calculated from these source rows.`:'An above-reference count is a source-data flag for review. Union proposal counts are not legal violations.';
 const all=T.counts.filter(r=>r.geo===geo&&r.year===year&&(r.scope==='rule'||r.scope===scope));
 table('threshold-table',['Reference','Type / class scope','Eligible classes','Above · count range','Above · share range'],T.rules.map(r=>{const a=all.find(a=>a.rule===r.id);return [esc(r.label),esc(r.kind+(r.family==='oecd'?' · '+T.scopes[scope]:'')),fmt(a.classes,0),a.classes?range(a.above_low,a.above_high,0):'Unavailable',a.classes?range(...percent(a))+'%':'Unavailable'];}));
 $('threshold-oecd-note').textContent=`OECD rows use ${T.scopes[scope]}. The OECD primary average covers grades 1–6; lower secondary covers grades 7–9. Ontario combines grades 4–8, so these counts compare with fixed published averages rather than matching the OECD grade populations. The 2024 averages are held fixed across this history; they are not each year's OECD average.`;
 const avgs=T.averages.filter(r=>r.geo===geo&&r.year===year);
 table('average-reference-table',['Population','Reported class rows','Average · range','Board-average reference','Comparison scope'],avgs.map(r=>[r.group==='kindergarten'?'All classes containing JK/K · fractional denominator':'All classes containing grades 4–8',fmt(r.classes,0),range(r.average_low,r.average_high),fmt(r.reference),geo==='ontario'?'Combined boards · descriptive only':'Source rows only · not a compliance verdict']));
}
function alberta(){
 const A=window.ALBERTA_CLASSES;if(!A)return;
 const geo=$('alberta-area').value,group=$('alberta-group').value,limit=Number($('alberta-reference').value),row=A.counts.find(r=>r.geo===geo&&r.group===group),above=row['above'+limit],share=row.classes?100*above/row.classes:null;
 $('alberta-scope').textContent=`${A.areas[geo]} · ${A.groups[group]} · 2025–26 only. Counts are published classroom rows, not unique pupils. The 2024 OECD average is held fixed for this comparison.`;
 stats('alberta-stats',[[`Classes above ${limit}`,fmt(above,0),row.classes?fmt(share)+'% of published classrooms':'No published rows for this band'],['Published classrooms',fmt(row.classes,0),fmt(row.suppressed,0)+' have suppressed sizes below 10'],['OECD published average',limit+' students','Observed average · 2024; not a maximum']]);
 $('alberta-bar-title').textContent=`Share above ${limit} students · ${A.groups[group]}`;
 $('alberta-bars').innerHTML=row.classes?`<div class="ab-track" role="img" aria-label="${esc(fmt(share))}% above ${limit}; ${esc(fmt(100-share))}% at or below"><span style="width:${share}%"></span></div><p class="small">${fmt(share)}% above · ${fmt(100-share)}% at or below</p>`:'<p>No published classroom rows for this band.</p>';
 const rows=A.counts.filter(r=>r.geo===geo);
 table('alberta-table',['Grade band','Published classes','Above 21 · count (%)','Above 23 · count (%)','Suppressed <10'],rows.map(r=>[esc(A.groups[r.group]),fmt(r.classes,0),r.classes?`${fmt(r.above21,0)} (${fmt(100*r.above21/r.classes)}%)`:'Unavailable',r.classes?`${fmt(r.above23,0)} (${fmt(100*r.above23/r.classes)}%)`:'Unavailable',fmt(r.suppressed,0)]));
}
function render(){finances();classHistory();schoolHistory();thresholds();alberta();}
try{
 for(const id of ['class-board','school-board'])$(id).innerHTML=Object.entries(boardLabels).map(([v,n])=>`<option value="${v}">${esc(n)}</option>`).join('');
 ['finance-view','prices','finance-start'].forEach(id=>$(id).addEventListener('change',finances));
 ['class-board','class-group','class-measure'].forEach(id=>$(id).addEventListener('change',classHistory));
 $('school-board').addEventListener('change',()=>{$('school-search').value='';schoolOptions();});$('school-search').addEventListener('input',schoolOptions);
 ['school-name','school-group'].forEach(id=>$(id).addEventListener('change',schoolHistory));$('download-finance').addEventListener('click',downloadFinance);
 if(T){
  $('threshold-board').innerHTML=Object.entries(boardLabels).map(([v,n])=>`<option value="${v}">${esc(n)}</option>`).join('')+'<option value="ontario">Ontario combined · descriptive</option>';
  $('threshold-year').innerHTML=T.years.map(y=>`<option value="${y}">${schoolYear(y)}</option>`).join('');$('threshold-year').value=String(T.years.at(-1));
  $('threshold-scope').innerHTML=Object.entries(T.scopes).map(([v,n])=>`<option value="${v}">${esc(n)}</option>`).join('');
  const shortRules={primary23:'Primary >23 · hard cap',primary20:'Primary >20 · 90% rule',mixed23:'Mixed primary/upper >23',k29:'Kindergarten >29 · exceptions',k32:'Kindergarten >32 · ceiling',etfo24:'Grades 4–8 >24 · ETFO proposal',etfo26:'Kindergarten >26 · ETFO proposal',oecd21:'OECD primary average · 21',oecd23:'OECD lower-secondary average · 23'};
  $('threshold-rule').innerHTML=T.rules.map(r=>`<option value="${r.id}">${esc(shortRules[r.id])}</option>`).join('');
  ['threshold-board','threshold-year','threshold-rule','threshold-measure','threshold-scope'].forEach(id=>$(id).addEventListener('change',thresholds));
 }
 if(window.ALBERTA_CLASSES){
  const A=window.ALBERTA_CLASSES;
  $('alberta-area').innerHTML=Object.entries(A.areas).sort(([a,x],[b,y])=>a==='alberta'?-1:b==='alberta'?1:x.localeCompare(y)).map(([v,n])=>`<option value="${esc(v)}">${esc(n)}</option>`).join('');
  $('alberta-group').innerHTML=Object.entries(A.groups).map(([v,n])=>`<option value="${v}">${esc(n)}</option>`).join('');$('alberta-group').value='G4-6';
  ['alberta-area','alberta-group','alberta-reference'].forEach(id=>$(id).addEventListener('change',alberta));
 }
 window.setTheme=mode=>{document.documentElement.dataset.theme=mode;localStorage.setItem('ov-theme',mode);render();};
 let timer;window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(render,100);});
 schoolOptions();render();
}catch(error){$('error').hidden=false;console.error(error);}
})();

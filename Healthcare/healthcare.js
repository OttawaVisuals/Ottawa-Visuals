/* No external chart dependency. Original values and source references stay downloadable. */
(() => {
'use strict';
const D=window.HEALTHCARE_DATA,A=window.HEALTHCARE_ACCESS,$=id=>document.getElementById(id);
if(!D){$('error').hidden=false;return;}
const nf=new Intl.NumberFormat('en-CA',{maximumFractionDigits:1}),integer=new Intl.NumberFormat('en-CA',{maximumFractionDigits:0});
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(n,d=1)=>Number(n).toLocaleString('en-CA',{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=(a,b)=>`${b>=a?'+':''}${fmt((b/a-1)*100)}%`;
const colours=()=>{const s=getComputedStyle(document.documentElement);return [s.getPropertyValue('--blue').trim(),s.getPropertyValue('--teal').trim(),s.getPropertyValue('--orange').trim()];};
function table(id,heads,rows){$(id).innerHTML=`<table><thead><tr>${heads.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((v,i)=>i===0?`<th scope="row">${v}</th>`:`<td>${v}</td>`).join('')}</tr>`).join('')}</tbody></table>`;}
function stats(id,items){$(id).innerHTML=items.map(([label,value,note])=>`<article class="stat"><p>${esc(label)}</p><strong class="value">${esc(value)}</strong><p>${esc(note)}</p></article>`).join('');}
function chart(id,series,{readout,unit,format=n=>nf.format(n),label='Chart',ceiling}={}){
 const el=$(id),width=Math.max(290,Math.round(el.getBoundingClientRect().width)),height=width>650?300:245;
 const margin={l:width>650?66:57,r:18,t:18,b:38},pw=width-margin.l-margin.r,ph=height-margin.t-margin.b;
 const pts=series.flatMap(s=>s.points).filter(p=>p.value!==null&&Number.isFinite(p.value));
 if(!pts.length){el.innerHTML='<div class="empty"><strong>Not available in this release</strong>No comparable historical series has been established. Missing values are not zero.</div>';if(readout)$(readout).textContent='';return;}
 const xs=[...new Set(pts.map(p=>p.x))].sort((a,b)=>a-b),lo=xs[0],hi=xs.at(-1);
 let ymax=Math.max(...pts.flatMap(p=>[p.value,p.high].filter(Number.isFinite)),0.1)*1.13;const raw=ymax/4,pow=10**Math.floor(Math.log10(raw));let step=[1,2,2.5,5,10].find(v=>v*pow>=raw)*pow;ymax=Math.ceil(ymax/step)*step;if(ceiling&&ymax>ceiling){ymax=ceiling;step=ceiling/4;}
 const x=v=>margin.l+(hi===lo?.5:(v-lo)/(hi-lo))*pw,y=v=>margin.t+ph*(1-v/ymax);
 const ticks=width<480?4:6,every=Math.ceil((xs.length-1)/(ticks-1)),selected=xs.filter((_,i)=>i===0||i===xs.length-1||(i%every===0&&xs.length-1-i>=every*.6));
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="${esc(label)}"><title>${esc(label)}</title>`;
 for(let v=0;v<=ymax+step/10;v+=step){svg+=`<line class="grid" x1="${margin.l}" x2="${width-margin.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${margin.l-10}" y="${y(v)+4}" text-anchor="end">${esc(nf.format(v))}</text>`;}
 selected.forEach(v=>{const p=pts.find(p=>p.x===v);svg+=`<text x="${x(v)}" y="${height-12}" text-anchor="middle">${esc(p.short||v)}</text>`;});
 let pointIndex=0,initial;const lookup=[];
 series.forEach((s,si)=>{
  const cc=colours()[si%3];let last=null;
  s.points.forEach(p=>{
   if(p.value===null||!Number.isFinite(p.value)){last=null;return;}
   if(p.breakBefore)last=null;
   if(last)svg+=`<path class="data-line" stroke="${cc}" ${p.forecast||last.forecast||p.partial||last.partial?'stroke-dasharray="6 5"':''} d="M${x(last.x)},${y(last.value)} L${x(p.x)},${y(p.value)}"/>`;
   last=p;
  });
  s.points.forEach(p=>{
   if(p.value===null||!Number.isFinite(p.value))return;
   const hasCI=Number.isFinite(p.low)&&Number.isFinite(p.high);
   const text=`${p.label||p.x} · ${s.name}: ${format(p.value)}${unit?' '+unit:''}${hasCI?` · 95% CI ${format(p.low)}–${format(p.high)}`:''}${p.forecast?' · Forecast':''}${p.partial?' · Partial period':''}${p.note?' · '+p.note:''}`;
   if(hasCI)svg+=`<path class="confidence" stroke="${cc}" fill="none" d="M${x(p.x)},${y(p.low)}V${y(p.high)} M${x(p.x)-5},${y(p.low)}H${x(p.x)+5} M${x(p.x)-5},${y(p.high)}H${x(p.x)+5}"/>`;
   svg+=`<circle class="point" tabindex="0" role="button" aria-label="${esc(text)}" data-point="${pointIndex++}" cx="${x(p.x)}" cy="${y(p.value)}" r="3.6" fill="${p.forecast||p.partial?'var(--bg-2)':cc}" style="stroke:${cc}"><title>${esc(text)}</title></circle>`;
   lookup.push(text);if(si===0)initial=text;
  });
 });
 el.innerHTML=svg+'</svg>';
 const show=t=>{if(readout)$(readout).textContent=t;};
 el.querySelectorAll('[data-point]').forEach(p=>{const fn=()=>show(lookup[Number(p.dataset.point)]);['pointerenter','focus','click'].forEach(e=>p.addEventListener(e,fn));p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fn();}});});
 if(readout)show(initial??lookup.at(-1));
}
let currentView=[];
function spending(){
 const category=$('category').value,split=$('funding').value==='split',real=$('prices').value==='real',resident=$('measure').value==='resident',forecast=$('forecasts').checked,start=Number($('start').value);
 const sources=split?['All public sources','Private sources']:['Ontario government'];
 const rows=D.spending.filter(r=>r.category===category&&sources.includes(r.funding)&&r.year>=start&&(forecast||r.status==='Actual'));
 const value=r=>(real?r.real_2023_million_cad:r.million_cad)*(resident?1e6/r.population:1/1000);
 const unit=resident?'CAD per resident':'CAD billions';
 const series=sources.map(name=>({name,points:rows.filter(r=>r.funding===name).map(r=>({x:r.year,value:value(r),forecast:r.status==='Forecast',label:r.year}))}));
 const primary=rows.filter(r=>r.funding===sources[0]),first=primary[0],last=primary.at(-1);
 $('funding-definition').textContent=split?'Public includes provincial, federal and other public sources. Private includes household and insurance funding. These financing groups do not identify who owns the hospital or clinic.':'Provincial government expenditure only. This excludes other public sources and private funding; it can include payments to privately operated providers.';
 $('spending-title').textContent=`${category} · ${real?'adjusted for health-price inflation':'dollars of each year'}`;
 $('spending-unit').textContent=unit;
 stats('spending-stats',[[`${last.year} · ${last.status}`,`$${fmt(value(last),resident?0:1)}${resident?'':'B'}`,`${sources[0]} · ${resident?'per resident':'total'}`],[`${first.year} → ${last.year}`,pct(value(first),value(last)),`${sources[0]} · ${real?'after price adjustment':'nominal change'}`],['Funding scope',split?'Public / private':'Ontario gov’t',split?'Two separate financing sources':'Provincial government only']]);
 chart('spending-chart',series,{readout:'spending-readout',unit,format:n=>'$'+fmt(n,resident?2:3),label:`Ontario ${category.toLowerCase()} funding in ${unit}, ${first.year} to ${last.year}`});
 $('spending-legend').innerHTML=sources.map((s,i)=>`<span><i class="key" style="background:${colours()[i]}"></i>${esc(s)}</span>`).join('')+(forecast?'<span>┄ Forecasts: 2024–25</span>':'');
 currentView=rows.map(r=>({year:r.year,funding:r.funding,category:r.category,value:value(r),unit,dollar_basis:real?'2023 total-health implicit-price dollars':'Nominal CAD',status:r.status,source_file:r.source_file,source_sheet:r.source_sheet,source_cell:r.source_cell}));
 table('spending-table',['Year','Funding','Selected value','Units','Status','Source cell'],currentView.map(r=>[r.year,esc(r.funding),'$'+fmt(r.value,resident?2:4),esc(unit),r.status,`${r.source_file} · ${r.source_sheet}!${r.source_cell}`]));
}
function capacity(){
 const rate=$('capacity-measure').value==='rate',acute=$('bed-type').value==='acute';
 const staffKey=rate?'fte_per_1000':'fte',bedKey=(acute?'acute_beds':'all_beds')+(rate?'_per_1000':'');
 const points=k=>D.workforce.map(r=>({x:r.fiscal_start,value:r[k],label:r.fiscal_year,short:String(r.fiscal_start).slice(-2)+'–'+String(r.fiscal_start+1).slice(-2)}));
 $('staff-unit').textContent=rate?'FTE per 1,000 residents':'Calculated FTE';$('beds-unit').textContent=rate?'Beds per 1,000 residents':'Staffed beds';$('beds-title').textContent=acute?'Acute-care beds':'All hospital beds';
 chart('staff-chart',[{name:'Hospital staffing',points:points(staffKey)}],{readout:'staff-readout',unit:rate?'FTE per 1,000 residents':'calculated FTE',format:n=>fmt(n,rate?2:1),label:'Ontario hospital staffing by fiscal year'});
 chart('beds-chart',[{name:acute?'Acute-care beds':'All hospital beds',points:points(bedKey)}],{readout:'beds-readout',unit:rate?'beds per 1,000 residents':'staffed beds',format:n=>fmt(n,rate?2:0),label:'Ontario staffed hospital beds by fiscal year'});
 table('capacity-table',['Fiscal year','Calculated FTE','FTE / 1,000','Acute beds','Acute / 1,000','All beds','All / 1,000','Organizations'],D.workforce.map(r=>[r.fiscal_year,fmt(r.fte),fmt(r.fte_per_1000,3),integer.format(r.acute_beds),fmt(r.acute_beds_per_1000,3),integer.format(r.all_beds),fmt(r.all_beds_per_1000,3),r.reporting_organizations]));
}
function hospital(){
 const h=D.hospitals.find(h=>h.id===$('hospital').value),metric=$('hospital-metric').value,staff=$('hospital-staff').value;
 const title={expenses_cad:'Statement expenses',government_funding_line_cad:'Government funding line',compensation_line_cad:'Salaries & benefits line'}[metric],last=h.financials.at(-1),first=h.financials[0];
 $('hospital-note').textContent=h.note;
 $('hospital-chart-title').textContent=title;
 const staffingLast=h.staffing.at(-1);
 stats('hospital-stats',[[`${last.fiscal_year} · ${title}`,`$${fmt(last[metric]/1e6)}M`,'Nominal dollars'],[`${first.fiscal_year} → ${last.fiscal_year}`,pct(first[metric],last[metric]),'Nominal change; scope notes apply'],[staff==='employees'?'Reported employees':'Reported nurses',staffingLast?integer.format(staffingLast[staff]):'Unavailable',staffingLast?`${staffingLast.fiscal_year} · TOH + Heart Institute`:'Comparable history not established']]);
 const p=r=>({x:r.fiscal_end,value:r[metric]/1e6,label:r.fiscal_year,short:String(r.fiscal_end-1).slice(-2)+'–'+String(r.fiscal_end).slice(-2)});
 chart('hospital-chart',[{name:title,points:h.financials.map(p)}],{readout:'hospital-readout',unit:'',format:n=>'$'+fmt(n)+'M',label:`${h.name}: ${title} by fiscal year`});
 $('hospital-staff-title').textContent=staff==='employees'?'Reported employee headcount':'Reported nurse headcount';
 chart('hospital-staff-chart',[{name:staff==='employees'?'Employees':'Nurses',points:h.staffing.map(r=>({x:r.fiscal_end,value:r[staff],label:r.fiscal_year,short:String(r.fiscal_end-1).slice(-2)+'–'+String(r.fiscal_end).slice(-2)}))}],{readout:'hospital-staff-readout',unit:'people · TOH + Heart Institute',format:n=>integer.format(n),label:`${h.name}: reported ${staff} headcount`});
 if(!h.staffing.length)$('hospital-staff-readout').textContent='Staff counts are not inferred from salaries or funding.';
 $('hospital-finance-definition').textContent=metric==='government_funding_line_cad'?`Source line: “${h.funding_label}”. This is not every public dollar received; other public revenue can be recorded separately.`:metric==='compensation_line_cad'?'The named salaries and benefits line(s), before separately reported wage adjustments. This does not count employees or include all contracted services.':'Statement expense subtotal plus separately reported expense lines (buildings, parking and explicit retroactive wages), as retained in the CSV. Montfort’s net prior-years adjustment remains separate.';
 table('hospital-table',['Fiscal year','Government funding line','Statement expenses','Salaries & benefits line','Audited source'],h.financials.map(r=>[r.fiscal_year,'$'+integer.format(r.government_funding_line_cad),'$'+integer.format(r.expenses_cad),'$'+integer.format(r.compensation_line_cad),`<a href="${esc(r.source_url)}#page=${r.source_pdf_page}">PDF p. ${r.source_pdf_page}</a> · ${esc(r.source_column)}`]));
 if(h.staffing.length)table('hospital-staff-table',['Fiscal year','Employees','Nurses','Scope','Source'],h.staffing.map(r=>[r.fiscal_year,integer.format(r.employees),integer.format(r.nurses),'TOH + Heart Institute',`<a href="${esc(r.source_url)}">Annual report</a>`]));
 else $('hospital-staff-table').innerHTML='<p>Comparable historical staffing data not established for this hospital in this release.</p>';
}
function legend(id,names,extra=''){$(id).innerHTML=names.map((name,i)=>`<span><i class="key" style="background:${colours()[i]}"></i>${esc(name)}</span>`).join('')+extra;}
const optional=(v,places=1)=>v===null||v===undefined?'Unavailable':fmt(v,places);
// Display names only; the downloads keep Ontario Health's site names.
const siteNames={'Ottawa Hospital (The)-Civic Site':'The Ottawa Hospital – Civic','Ottawa Hospital (The)-General Site':'The Ottawa Hospital – General',"Children's Hospital Of Eastern Ontario":'CHEO','Queensway-Carleton Hospital':'Queensway Carleton','Hopital Montfort':'Hôpital Montfort'};
const siteName=name=>siteNames[name]||name;
const monthLabel=month=>new Date(Date.UTC(Number(month.slice(0,4)),Number(month.slice(4))-1,1)).toLocaleDateString('en-CA',{month:'short',year:'numeric',timeZone:'UTC'});
function emergency(){
 if(!A){$('access-error').hidden=false;return;}
 const siteId=Number($('er-site').value),site={...A.er_sites.find(s=>s.id===siteId)},stat=$('er-statistic').value,group=$('er-group').value;
 const groups={A:'admitted patients',NAH:'high urgency · not admitted',L:'low urgency · not admitted'};
 site.name=siteName(site.name);
 const months=[...new Set(A.er.map(r=>r.month))].sort();
 const points=(id,metric)=>months.map(month=>{const r=A.er.find(r=>r.site_id===id&&r.metric===metric&&r.month===month);return {x:Number(month.slice(0,4))*12+Number(month.slice(4)),value:r?r[stat]:null,label:monthLabel(month),short:monthLabel(month).replace(' 20',' ’')};});
 const series=metric=>[{name:site.name,points:points(siteId,metric)},{name:'Ontario',points:points(-354,metric)}];
 const last=months.at(-1),latest=metric=>A.er.find(r=>r.site_id===siteId&&r.metric===metric&&r.month===last);
 const assessment=latest('PIA'),stay=latest(group),name=stat==='mean_hours'?'Average':'90th percentile';
 $('er-period').textContent=`${monthLabel(months[0])}–${monthLabel(last)} · ${months.length} monthly periods · current reporting vintage · reviewed ${A.reviewed}`;
 stats('er-stats',[[`${name} · first assessment`,assessment&&assessment[stat]!==null?`${fmt(assessment[stat])} h`:'Unavailable',`${site.name} · ${monthLabel(last)}`],[`${name} · full ER stay`,stay&&stay[stat]!==null?`${fmt(stay[stat])} h`:'Unavailable',`${groups[group]} · ${monthLabel(last)}`]]);
 $('er-stay-title').textContent=`Full ER stay · ${groups[group]}`;
 chart('er-assessment-chart',series('PIA'),{readout:'er-assessment-readout',unit:'hours',format:n=>fmt(n),label:`${name} time to first assessment: ${site.name} and Ontario`});
 chart('er-stay-chart',series(group),{readout:'er-stay-readout',unit:'hours',format:n=>fmt(n),label:`${name} full ER stay, ${groups[group]}: ${site.name} and Ontario`});
 legend('er-legend',[site.name,'Ontario']);
 $('er-statistic-note').textContent=stat==='mean_hours'?'Average = total eligible time divided by eligible visits. Averages can be influenced by very long stays. No average is calculated by averaging hospital averages.':'90th percentile = 90% of eligible visits took this long or less; 10% took longer. It is not the average or a maximum, and it is not calculated from monthly averages.';
 const rows=A.er.filter(r=>[siteId,-354].includes(r.site_id)&&['PIA',group].includes(r.metric));
 table('er-table',['Month','Site','Measure','Average hours','90th percentile hours','Visits','Source'],rows.map(r=>[monthLabel(r.month),esc(siteName(r.site)),r.metric==='PIA'?'First assessment':esc(groups[r.metric]),optional(r.mean_hours),optional(r.p90_hours),optional(r.visits,0),`<a href="${esc(r.source_url)}">Source JSON</a> · row ${r.source_index+1}`]));
 emergencyHistory();
}
function emergencyHistory(){
 if(!A||!$('er-history-details').open)return;
 const group=$('er-history-group').value,rows=A.er_history.filter(r=>r.group===group);
 $('er-history-title').textContent=`Ontario · average full ER stay · ${group.toLowerCase()}`;
 chart('er-history-chart',[{name:group,points:rows.map(r=>({x:r.fiscal_start,value:r.mean_hours,label:r.period.replace('-','–'),short:r.period.slice(2).replace('-','–'),partial:r.partial,note:r.coverage}))}],{readout:'er-history-readout',unit:'hours',format:n=>fmt(n),label:`FAO 2023 vintage: Ontario average ER length of stay for ${group.toLowerCase()}`});
 table('er-history-table',['Fiscal year','Average hours','Period coverage','Source'],rows.map(r=>[r.period,fmt(r.mean_hours),esc(r.coverage),`<a href="${esc(r.source_url)}">FAO ${r.source_table}</a>`]));
}
function primaryCare(){
 if(!A)return;
 const recent=$('provider-series').value==='recent',measure=$('provider-measure').value,without=measure==='without';
 const rows=A.provider.filter(r=>r.series===(recent?'Recent Ontario adults':'Historical Ottawa comparison')),geos=recent?['Ontario']:['Ottawa','Ontario'];
 const lastPeriod=rows.map(r=>r.period).sort().at(-1),last=geos.map(g=>rows.find(r=>r.geography===g&&r.period===lastPeriod));
 const percent=r=>r[measure+'_percent'];
 stats('provider-stats',recent?[[`Ontario · ${lastPeriod}`,`${fmt(percent(last[0]))}%`,without?'Without a primary-care provider':'With a primary-care provider'],['Survey population','Ages 18+','Adults · household survey'],['Definitions','Changed','2023, 2024 and 2025 remain separate']]:[[`Ottawa · ${lastPeriod}`,`${fmt(percent(last[0]))}%`,without?'Without a regular provider':'With a regular provider'],[`Ontario · ${lastPeriod}`,`${fmt(percent(last[1]))}%`,'Same age group and survey period'],['Survey population','Ages 12+','Two calendar years pooled per point']]);
 $('provider-definition').textContent=recent?'Separate snapshots: adults aged 18+. The listed provider categories changed in 2024; 2025 asks about a primary-care professional/team and excludes private-pay models. Points are deliberately unconnected. These are not directly comparable with the older ages-12+ Ottawa series.':'Historical comparison: ages 12+, two calendar years per estimate. Pandemic collection disruption affects 2019/20. The 2021/22 point combines different collection methods and response rates; the line breaks before it. The latest Ottawa estimate shown is 2021/22, not a current estimate.';
 $('provider-chart-title').textContent=without?'People without a regular / primary-care provider':'People with a regular / primary-care provider';
 const series=geos.map(name=>({name,points:rows.filter(r=>r.geography===name).map(r=>({x:r.period_start,value:percent(r),low:r[measure+'_low'],high:r[measure+'_high'],label:r.period,short:recent?r.period:r.period.replace('/20','/'),breakBefore:r.break_before,note:recent?r.definition:(r.status?`Source flag ${r.status}`:'')}))}));
 chart('provider-chart',series,{readout:'provider-readout',unit:'%',format:n=>fmt(n),ceiling:100,label:`${without?'Without':'With'} a regular or primary-care provider; ${recent?'Ontario adults 2023–2025, separate definitions':'Ottawa versus Ontario, ages 12+, pooled survey periods'}`});
 legend('provider-legend',geos,'<span>┤ 95% confidence intervals</span>');
 table('provider-table',['Period','Geography','Age','With %','95% CI · with','Without %','95% CI · without','Source flag','Source'],rows.map(r=>[r.period,r.geography,esc(r.age),optional(r.has_percent),`${optional(r.has_low)}–${optional(r.has_high)}`,optional(r.without_percent),`${optional(r.without_low)}–${optional(r.without_high)}`,esc(r.status||'None'),`<a href="${esc(r.source_url)}">${esc(r.source_table)}</a> · ${esc(r.source_vector||r.source_coordinate)}`]));
}
function download(){
 const keys=Object.keys(currentView[0]),quote=x=>'"'+String(x??'').replace(/"/g,'""')+'"';
 const csv=[keys,...currentView.map(r=>keys.map(k=>r[k]))].map(r=>r.map(quote).join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='ontario-healthcare-selected-view.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function render(){spending();capacity();hospital();emergency();primaryCare();}
try{
 $('hospital').innerHTML=D.hospitals.map(h=>`<option value="${esc(h.id)}">${esc(h.name)}</option>`).join('');
 ['category','funding','measure','prices','start','forecasts'].forEach(id=>$(id).addEventListener('change',spending));
 ['capacity-measure','bed-type'].forEach(id=>$(id).addEventListener('change',capacity));
 ['hospital','hospital-metric','hospital-staff'].forEach(id=>$(id).addEventListener('change',hospital));
 if(A){
  $('er-site').innerHTML=A.er_sites.filter(s=>s.id!==-354).map(s=>`<option value="${s.id}">${esc(siteName(s.name))}</option>`).join('');
  $('er-site').value=String(A.er_sites.find(s=>s.name.includes('General Site')).id);
  ['er-site','er-statistic','er-group'].forEach(id=>$(id).addEventListener('change',emergency));
  ['provider-series','provider-measure'].forEach(id=>$(id).addEventListener('change',primaryCare));
  $('er-history-group').addEventListener('change',emergencyHistory);
  $('er-history-details').addEventListener('toggle',emergencyHistory);
 }
 $('download-view').addEventListener('click',download);
 window.setTheme=mode=>{document.documentElement.dataset.theme=mode;localStorage.setItem('ov-theme',mode);render();};
 let timer;window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(render,100);});
 render();
}catch(e){$('error').hidden=false;console.error(e);}
})();

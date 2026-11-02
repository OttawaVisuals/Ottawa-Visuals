/* No external chart dependency. Original values and source references stay downloadable. */
(() => {
'use strict';
const D=window.HEALTHCARE_DATA,$=id=>document.getElementById(id);
if(!D){$('error').hidden=false;return;}
const nf=new Intl.NumberFormat('en-CA',{maximumFractionDigits:1}),integer=new Intl.NumberFormat('en-CA',{maximumFractionDigits:0});
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(n,d=1)=>Number(n).toLocaleString('en-CA',{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=(a,b)=>`${b>=a?'+':''}${fmt((b/a-1)*100)}%`;
const colours=()=>{const s=getComputedStyle(document.documentElement);return [s.getPropertyValue('--blue').trim(),s.getPropertyValue('--teal').trim(),s.getPropertyValue('--orange').trim()];};
function table(id,heads,rows){$(id).innerHTML=`<table><thead><tr>${heads.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((v,i)=>i===0?`<th scope="row">${v}</th>`:`<td>${v}</td>`).join('')}</tr>`).join('')}</tbody></table>`;}
function stats(id,items){$(id).innerHTML=items.map(([label,value,note])=>`<article class="stat"><p>${esc(label)}</p><strong class="value">${esc(value)}</strong><p>${esc(note)}</p></article>`).join('');}
function chart(id,series,{readout,unit,format=n=>nf.format(n),label='Chart'}={}){
 const el=$(id),width=Math.max(290,Math.round(el.getBoundingClientRect().width)),height=width>650?300:245;
 const margin={l:width>650?66:57,r:18,t:18,b:38},pw=width-margin.l-margin.r,ph=height-margin.t-margin.b;
 const pts=series.flatMap(s=>s.points).filter(p=>p.value!==null&&Number.isFinite(p.value));
 if(!pts.length){el.innerHTML='<div class="empty"><strong>Not available in this release</strong>No comparable historical series has been established. Missing values are not zero.</div>';if(readout)$(readout).textContent='';return;}
 const xs=[...new Set(pts.map(p=>p.x))].sort((a,b)=>a-b),lo=xs[0],hi=xs.at(-1);
 let ymax=Math.max(...pts.map(p=>p.value))*1.13;const raw=ymax/4,pow=10**Math.floor(Math.log10(raw)),step=[1,2,2.5,5,10].find(v=>v*pow>=raw)*pow;ymax=Math.ceil(ymax/step)*step;
 const x=v=>margin.l+(hi===lo?.5:(v-lo)/(hi-lo))*pw,y=v=>margin.t+ph*(1-v/ymax);
 const ticks=width<480?4:6,selected=xs.filter((_,i)=>i===0||i===xs.length-1||i%Math.ceil((xs.length-1)/(ticks-1))===0);
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="${esc(label)}"><title>${esc(label)}</title>`;
 for(let v=0;v<=ymax+step/10;v+=step){svg+=`<line class="grid" x1="${margin.l}" x2="${width-margin.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${margin.l-10}" y="${y(v)+4}" text-anchor="end">${esc(nf.format(v))}</text>`;}
 selected.forEach(v=>{const p=pts.find(p=>p.x===v);svg+=`<text x="${x(v)}" y="${height-12}" text-anchor="middle">${esc(p.short||v)}</text>`;});
 let pointIndex=0;const lookup=[];
 series.forEach((s,si)=>{
  const cc=colours()[si%3];let last=null;
  s.points.forEach(p=>{
   if(p.value===null||!Number.isFinite(p.value)){last=null;return;}
   if(last)svg+=`<path class="data-line" stroke="${cc}" ${p.forecast||last.forecast?'stroke-dasharray="6 5"':''} d="M${x(last.x)},${y(last.value)} L${x(p.x)},${y(p.value)}"/>`;
   last=p;
  });
  s.points.forEach(p=>{
   if(p.value===null||!Number.isFinite(p.value))return;
   const text=`${p.label||p.x} · ${s.name}: ${format(p.value)} ${unit||''}${p.forecast?' · Forecast':''}`;
   svg+=`<circle class="point" tabindex="0" role="button" aria-label="${esc(text)}" data-point="${pointIndex++}" cx="${x(p.x)}" cy="${y(p.value)}" r="3.6" fill="${p.forecast?'var(--bg-2)':cc}" style="stroke:${cc}"><title>${esc(text)}</title></circle>`;
   lookup.push(text);
  });
 });
 el.innerHTML=svg+'</svg>';
 const show=t=>{if(readout)$(readout).textContent=t;};
 el.querySelectorAll('[data-point]').forEach(p=>{const fn=()=>show(lookup[Number(p.dataset.point)]);['pointerenter','focus','click'].forEach(e=>p.addEventListener(e,fn));p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fn();}});});
 if(readout)show(lookup.at(-1));
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
 chart('staff-chart',[{name:'Hospital staffing',points:points(staffKey)}],{readout:'staff-readout',unit:$('staff-unit').textContent,format:n=>fmt(n,rate?2:1),label:'Ontario hospital staffing by fiscal year'});
 chart('beds-chart',[{name:acute?'Acute-care beds':'All hospital beds',points:points(bedKey)}],{readout:'beds-readout',unit:$('beds-unit').textContent,format:n=>fmt(n,rate?2:0),label:'Ontario staffed hospital beds by fiscal year'});
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
 chart('hospital-chart',[{name:title,points:h.financials.map(p)}],{readout:'hospital-readout',unit:'CAD million',format:n=>'$'+fmt(n,3),label:`${h.name}: ${title} by fiscal year`});
 $('hospital-staff-title').textContent=staff==='employees'?'Reported employee headcount':'Reported nurse headcount';
 chart('hospital-staff-chart',[{name:staff==='employees'?'Employees':'Nurses',points:h.staffing.map(r=>({x:r.fiscal_end,value:r[staff],label:r.fiscal_year,short:String(r.fiscal_end-1).slice(-2)+'–'+String(r.fiscal_end).slice(-2)}))}],{readout:'hospital-staff-readout',unit:'people · TOH + Heart Institute',format:n=>integer.format(n),label:`${h.name}: reported ${staff} headcount`});
 if(!h.staffing.length)$('hospital-staff-readout').textContent='Staff counts are not inferred from salaries or funding.';
 $('hospital-finance-definition').textContent=metric==='government_funding_line_cad'?`Source line: “${h.funding_label}”. This is not every public dollar received; other public revenue can be recorded separately.`:metric==='compensation_line_cad'?'The named salaries and benefits line(s), before separately reported wage adjustments. This does not count employees or include all contracted services.':'Statement expense subtotal plus separately reported expense lines (buildings, parking and explicit retroactive wages), as retained in the CSV. Montfort’s net prior-years adjustment remains separate.';
 table('hospital-table',['Fiscal year','Government funding line','Statement expenses','Salaries & benefits line','Audited source'],h.financials.map(r=>[r.fiscal_year,'$'+integer.format(r.government_funding_line_cad),'$'+integer.format(r.expenses_cad),'$'+integer.format(r.compensation_line_cad),`<a href="${esc(r.source_url)}#page=${r.source_pdf_page}">PDF p. ${r.source_pdf_page}</a> · ${esc(r.source_column)}`]));
 if(h.staffing.length)table('hospital-staff-table',['Fiscal year','Employees','Nurses','Scope','Source'],h.staffing.map(r=>[r.fiscal_year,integer.format(r.employees),integer.format(r.nurses),'TOH + Heart Institute',`<a href="${esc(r.source_url)}">Annual report</a>`]));
 else $('hospital-staff-table').innerHTML='<p>Comparable historical staffing data not established for this hospital in this release.</p>';
}
function download(){
 const keys=Object.keys(currentView[0]),quote=x=>'"'+String(x??'').replace(/"/g,'""')+'"';
 const csv=[keys,...currentView.map(r=>keys.map(k=>r[k]))].map(r=>r.map(quote).join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='ontario-healthcare-selected-view.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function render(){spending();capacity();hospital();}
try{
 $('hospital').innerHTML=D.hospitals.map(h=>`<option value="${esc(h.id)}">${esc(h.name)}</option>`).join('');
 ['category','funding','measure','prices','start','forecasts'].forEach(id=>$(id).addEventListener('change',spending));
 ['capacity-measure','bed-type'].forEach(id=>$(id).addEventListener('change',capacity));
 ['hospital','hospital-metric','hospital-staff'].forEach(id=>$(id).addEventListener('change',hospital));
 $('download-view').addEventListener('click',download);
 window.setTheme=mode=>{document.documentElement.dataset.theme=mode;localStorage.setItem('ov-theme',mode);render();};
 let timer;window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(render,100);});
 render();
}catch(e){$('error').hidden=false;console.error(e);}
})();

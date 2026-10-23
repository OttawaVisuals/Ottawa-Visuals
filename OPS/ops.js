/* Counts are computed from reviewed records, never from PDF/document totals. */
(function(){
'use strict';
const labels={finding:'Misconduct found / admitted',no_finding:'Not guilty / charges dismissed'};
const unique=(rows,key)=>new Set(rows.map(r=>r[key])).size;
const amount=(n,word)=>`${n} ${word}${n===1?'':'s'}`;
function published(rows){return rows.filter(r=>r.outcome!=='scheduled');}
function totals(rows){const decided=published(rows);return {officers:unique(decided,'officer_id'),findings:unique(decided.filter(r=>r.outcome==='finding'),'officer_id'),cases:unique(decided,'case_id'),scheduled:unique(rows.filter(r=>r.outcome==='scheduled'),'officer_id')};}
function filter(rows,{search='',year='',outcome=''}={}){const q=search.toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');return published(rows).filter(r=>(!year||r.decision_date.startsWith(year))&&(!outcome||r.outcome===outcome)&&(!q||[r.officer,r.category,r.summary,r.penalty].join(' ').toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').includes(q)));}
function annual(rows){const groups=new Map();published(rows).forEach(r=>{const year=r.decision_date.slice(0,4);if(!groups.has(year))groups.set(year,{finding:new Set(),no_finding:new Set()});groups.get(year)[r.outcome].add(r.officer_id)});return [...groups].sort(([a],[b])=>a.localeCompare(b)).map(([year,g])=>({year,finding:g.finding.size,no_finding:g.no_finding.size}));}
function csv(rows){const fields=['officer','case_id','decision_date','outcome','category','summary','penalty','incident_period','appeal_status','notes','sources'];const quote=x=>'"'+String(x??'').replace(/"/g,'""')+'"';return '\ufeff'+[fields.map(quote).join(','),...rows.map(r=>fields.map(k=>quote(k==='sources'?r.sources.map(s=>s.url+' ['+s.pages+']').join(' | '):r[k])).join(','))].join('\r\n');}
if(typeof module!=='undefined')module.exports={totals,filter,annual,csv,published};
if(typeof document==='undefined')return;
// Shared theme controls call this hook; CSS bars follow the theme tokens directly.
window.setTheme=mode=>{document.documentElement.dataset.theme=mode;};
const $=id=>document.getElementById(id);let data;
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function link(text,url){const a=el('a',text);a.href=url;return a;}
function criteria(){return {search:$('search').value,year:$('year').value,outcome:$('outcome').value};}
function render(){
 const c=criteria(), rows=filter(data.records,c).sort((a,b)=>b.decision_date.localeCompare(a.decision_date)||a.officer.localeCompare(b.officer));
 const params=new URLSearchParams();Object.entries(c).forEach(([k,v])=>{if(v)params.set(k,v)});try{history.replaceState(null,'',location.pathname+(params.size?'?'+params:'')+location.hash)}catch(e){}
 $('result-count').textContent=`${amount(unique(rows,'officer_id'),'officer')} · ${amount(unique(rows,'case_id'),'case')} · ${rows.length} officer–case ${rows.length===1?'entry':'entries'}. Totals above describe the full collection.`;
 $('rows').replaceChildren();$('empty').hidden=rows.length>0;
 for(const r of rows){const tr=el('tr');tr.append(el('td',r.officer),el('td',r.decision_date));const status=el('td');status.append(el('span',labels[r.outcome],'badge'+(r.outcome==='no_finding'?' no-finding':'')));tr.append(status);
  const content=el('td');content.append(el('p',r.category,'subject'),el('p',r.penalty,'penalty'));const details=el('details');details.append(el('summary','Details & sources'),el('p',r.summary));if(r.incident_period)details.append(el('p','Incident period: '+r.incident_period));details.append(el('p','Appeal / later review: '+r.appeal_status));if(r.notes)details.append(el('p',r.notes));const ul=el('ul');r.sources.forEach(s=>{const li=el('li');li.append(link(s.label,s.url),el('span',s.pages,'source-pages'));ul.append(li)});details.append(ul);content.append(details);tr.append(content);$('rows').append(tr);
 }
 const counts=annual(rows), all=annual(data.records),lookup=new Map(counts.map(r=>[r.year,r])),coverage=new Set(all.map(r=>r.year));const max=Math.max(1,...counts.map(r=>r.finding+r.no_finding));$('chart').replaceChildren();
 const years=c.year?[Number(c.year)]:Array.from({length:Number(all.at(-1).year)-Number(all[0].year)+1},(_,i)=>Number(all[0].year)+i);
 for(const year of years){const v=lookup.get(String(year));const row=el('div',undefined,'year-row');row.append(el('span',String(year)));if(!v){row.classList.add('gap');row.append(el('span',coverage.has(String(year))?'No matches for these filters':'No reviewed decision · collection gap','gap-label'),el('span','—','count'));}else{const track=el('div',undefined,'track');for(const key of ['finding','no_finding']){const bar=el('span',undefined,key);bar.style.width=(100*v[key]/max)+'%';bar.title=labels[key]+': '+v[key];track.append(bar)}row.append(track,el('span',`${v.finding} / ${v.no_finding}`,'count'));row.setAttribute('aria-label',`${year}: ${v.finding} officers with findings; ${v.no_finding} officers not guilty or charges dismissed`)}$('chart').append(row)}
}
async function init(){try{const response=await fetch('data/records.json');if(!response.ok)throw Error(response.status);data=await response.json();const t=totals(data.records);for(const [k,v] of Object.entries(t))$(k).textContent=v;
 const decided=published(data.records), years=annual(decided),without=decided.filter(r=>r.outcome==='no_finding'),found=new Set(decided.filter(r=>r.outcome==='finding').map(r=>r.officer_id));const overlap=new Set(without.filter(r=>found.has(r.officer_id)).map(r=>r.officer_id)).size;
 $('stamp').textContent=`Sources reviewed ${data.checked_on} · Latest decisions in this collection: ${years[0].year}–${years.at(-1).year} · Manual snapshot`;
 $('totals-note').textContent=`Full collection: ${decided.length} officer–case entries; ${without.length} ended without a misconduct finding. ${amount(overlap,'officer')} ${overlap===1?'has':'have'} both a finding and a separate case without a finding. Filters affect only the chart and table.`;
 $('year').replaceChildren(el('option','All years'));$('year').firstChild.value='';annual(data.records).reverse().forEach(r=>{const option=el('option',r.year);option.value=r.year;$('year').append(option)});
 const params=new URLSearchParams(location.search);for(const k of ['search','year','outcome']){const value=params.get(k)||'';$(k).value=value;if($(k).value!==value)$(k).value=''}
 $('pending').replaceChildren();data.records.filter(r=>r.outcome==='scheduled').forEach(r=>{const article=el('article');article.append(el('h3',r.officer),el('p',r.notes),el('p','No disciplinary finding recorded in this collection.'),link('OPS hearing schedule',r.sources[0].url));$('pending').append(article)});
 $('sources').replaceChildren();data.sources.forEach(s=>{const li=el('li');li.append(link(s.name,s.url),el('span',' — '+s.coverage));$('sources').append(li)});$('error').hidden=true;$('download').disabled=false;render();
 }catch(error){$('error').hidden=false;$('stamp').textContent='Data unavailable — retry or open the source links below.';}}
 for(const k of ['search','year','outcome'])$(k).addEventListener(k==='search'?'input':'change',()=>{if(data)render()});
 $('reset').addEventListener('click',()=>{for(const k of ['search','year','outcome'])$(k).value='';if(data)render()});$('retry').addEventListener('click',init);
 $('download').addEventListener('click',()=>{const blob=new Blob([csv(filter(data.records,criteria()))],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=link('',url);a.download='ops-published-disciplinary-records.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)});
 init();
})();

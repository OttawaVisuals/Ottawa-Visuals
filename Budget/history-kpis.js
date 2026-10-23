'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=n=>n.toLocaleString('en-CA',{maximumFractionDigits:1});
  const million=n=>'$'+(n/1000).toLocaleString('en-CA',{minimumFractionDigits:1,maximumFractionDigits:1})+'M';
  const sign=n=>n>0?'+':n<0?'−':'';
  const pct=(a,b)=>(b-a)/a*100;
  const signedPercent=n=>sign(n)+Math.abs(n).toFixed(1)+'%';
  const signedMoney=n=>sign(n)+million(Math.abs(n));
  const price=(value,year)=>window.OVBudgetPrices?.convert(value,year)??value;
  const basis=()=>window.OVBudgetPrices?.basis||'nominal dollars';
  const p=new URLSearchParams(location.search);
  let historyData,kpiData;
  const state={from:p.get('from')||'2023',to:p.get('to')||'2026',rank:p.get('rank')==='percent'?'percent':'dollars',group:['paramedics','infrastructure','housing'].includes(p.get('kpi'))?p.get('kpi'):'paramedics',metric:p.get('metric')||'ctas1-city',region:['city','urban','rural'].includes(p.get('region'))?p.get('region'):'city'};
  function url(){if(location.protocol==='file:')return;const q=new URLSearchParams(location.search);Object.entries({from:state.from,to:state.to,rank:state.rank,kpi:state.group,metric:state.metric,region:state.region}).forEach(([k,v])=>q.set(k,v));history.replaceState(null,'',location.pathname+'?'+q+location.hash);}
  async function get(name){
    if(location.protocol==='file:' && window.OTTAWA_BUDGET_DATA?.[name])return window.OTTAWA_BUDGET_DATA[name];
    const response=await fetch('data/'+name+'.json');if(!response.ok)throw Error('Data unavailable');return response.json();
  }
  function renderHistory(){
    if(!historyData)return;
    const years=historyData.years.map(String);
    if(!years.includes(state.from)||state.from==='2026')state.from='2023';
    if(!years.includes(state.to)||Number(state.to)<=Number(state.from))state.to=String(Number(state.from)+1);
    $('history-from').value=state.from;
    $('history-to').innerHTML=years.filter(y=>Number(y)>Number(state.from)).map(y=>`<option${y===state.to?' selected':''}>${y}</option>`).join('');
    $('history-unit').value=state.rank;
    const totals=Object.fromEntries(Object.entries(historyData.totals).map(([y,v])=>[y,price(v,y)])),maxTotal=Math.max(...Object.values(totals));
    $('annual-totals').innerHTML=years.map((y,i)=>`<div><span>${y} budget${window.OVBudgetPrices?.real?' · 2025$':''}</span><strong>$${(totals[y]/1e6).toFixed(2)}B</strong><div class="annual-track" aria-hidden="true"><i style="width:${totals[y]/maxTotal*100}%"></i></div><small>${i?signedPercent(pct(totals[years[i-1]],totals[y]))+' vs '+years[i-1]:'First year in this series'}${window.OVBudgetPrices?.real&&y==='2026'?' · provisional':''}</small></div>`).join('');
    const adjustedRows=historyData.rows.map(r=>({...r,values:Object.fromEntries(Object.entries(r.values).map(([y,v])=>[y,price(v,y)]))}));
    const rows=adjustedRows.map(r=>({...r,delta:r.values[state.to]-r.values[state.from],percent:pct(r.values[state.from],r.values[state.to])}));
    rows.sort((a,b)=>b[state.rank==='percent'?'percent':'delta']-a[state.rank==='percent'?'percent':'delta']);
    const scale=Math.max(...rows.map(r=>Math.abs(state.rank==='percent'?r.percent:r.delta)),1);
    const delta=totals[state.to]-totals[state.from];
    $('history-summary').textContent=`${state.from} → ${state.to}: ${signedMoney(delta)} (${signedPercent(pct(totals[state.from],totals[state.to]))}) total · ${rows.filter(r=>r.delta>0).length} categories increased · ${rows.filter(r=>r.delta<0).length} decreased · ${basis()}${window.OVBudgetPrices?.real&&state.to==='2026'?' · 2026 provisional':''}`;
    $('change-chart').innerHTML=rows.map(r=>{
      const v=state.rank==='percent'?r.percent:r.delta,width=Math.abs(v)/scale*49;
      return `<details class="change-row"><summary><span class="change-name">${esc(r.name)}</span><span class="delta-track" aria-hidden="true"><i class="zero-line"></i><i class="delta-bar ${v<0?'decrease':'increase'}" style="width:${width}%;left:${v<0?50-width:50}%"></i></span><span class="change-value">${state.rank==='percent'?signedPercent(r.percent):signedMoney(r.delta)}<small>${state.rank==='percent'?signedMoney(r.delta):signedPercent(r.percent)}</small></span></summary><div class="annual-detail">${years.map(y=>`<div><span>${y}${window.OVBudgetPrices?.real&&y==='2026'?' (provisional)':''}</span><strong>${million(r.values[y])}</strong></div>`).join('')}</div><p class="small">${state.from}: ${million(r.values[state.from])} → ${state.to}: ${million(r.values[state.to])}. Budget expenses in ${basis()}.</p></details>`;
    }).join('');
    $('history-rows').innerHTML=adjustedRows.concat([{name:'Total budget expenses',values:totals}]).map(r=>`<tr><th scope="row">${esc(r.name)}</th>${years.map(y=>`<td>${(r.values[y]/1000).toLocaleString('en-CA',{minimumFractionDigits:3,maximumFractionDigits:3})}</td>`).join('')}</tr>`).join('');
    document.querySelector('#history table caption').textContent=`Budget expenses in millions of ${basis()}, full-accrual basis.${window.OVBudgetPrices?.real?' 2026 uses provisional January–September CPI.':''}`;
    const download=document.querySelector('#history .download');download.href=window.OVBudgetPrices?.real?'data/budget-inflation-adjusted.csv':'data/history.csv';download.textContent=window.OVBudgetPrices?.real?'Adjusted CSV ↓':'History CSV ↓';
    $('history-sources').innerHTML=`<a href="${historyData.sources['2023'].url}#page=14">2024 adopted book, Table 1 ↗</a> · <a href="${historyData.sources['2026'].url}#page=15">2026 adopted book, Table 1 ↗</a>`;
    url();
  }
  function selectedMetric(){
    const metrics=kpiData.groups[state.group].metrics;
    let metric=metrics.find(m=>m.id===state.metric)||metrics[0];
    if(metric.region){const base=metric.id.split('-')[0];metric=metrics.find(m=>m.id===base+'-'+state.region)||metric;}
    state.metric=metric.id;
    return metric;
  }
  function kpiValue(value,m){return num(value)+(m.unit==='percent'?'%':m.unit==='index'?' / 100':' '+m.unit);}
  function renderKpis(){
    if(!kpiData)return;
    const group=kpiData.groups[state.group],m=selectedMetric();
    document.querySelectorAll('[data-kpi]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.kpi===state.group)));
    $('kpi-metric').innerHTML=group.metrics.filter(x=>!x.region||x.region==='city').map(x=>`<option value="${x.id}"${x.id===m.id||x.region&&x.id.split('-')[0]===m.id.split('-')[0]?' selected':''}>${esc(x.name)}</option>`).join('');
    $('kpi-region-label').hidden=!m.region;$('kpi-region').value=state.region;
    $('kpi-definition').textContent=m.definition;
    $('kpi-note').textContent=group.note;
    const entries=Object.entries(m.values).sort(([a],[b])=>Number(a)-Number(b));
    const [latestYear,latest]=entries[entries.length-1],[priorYear,prior]=entries[entries.length-2];
    const change=latest-prior;
    const changeLabel=m.unit==='percent'?sign(change)+Math.abs(change).toFixed(1)+' percentage points':m.unit==='index'?sign(change)+num(Math.abs(change))+' index points':sign(change)+num(Math.abs(change))+' '+m.unit;
    const targetLabel=m.target===null?'No target shown':`Target: ${num(m.target)}%${m.region&&m.region!=='city'?' · citywide reference':''}`;
    const targetDiff=m.target===null?'':`${Math.abs(latest-m.target).toFixed(1)} points ${latest>=m.target?'above':'below'} ${m.region&&m.region!=='city'?'citywide reference':'target'}`;
    const headlineValue=['percent','index'].includes(m.unit)?kpiValue(latest,m):num(latest);
    const headlineUnit=['percent','index'].includes(m.unit)?'':m.unit+' · ';
    $('kpi-headline').innerHTML=`<div><strong>${headlineValue}</strong><span>${headlineUnit}${latestYear}${m.id==='waitlist'?' · December 10':''}${m.region?' · '+({city:'citywide',urban:'urban',rural:'rural'})[m.region]:''}</span></div><div><strong>${changeLabel}</strong><span>vs ${priorYear}</span></div><div><strong>${esc(targetLabel)}</strong><span>${esc(targetDiff||({higher:'Higher usually indicates better performance',lower:'Lower usually indicates less pressure or better availability',context:'Demand measure; no better/worse rating'})[m.direction])}</span></div>`;
    const scale=m.unit==='percent'||m.unit==='index'?100:Math.max(...entries.map(([,v])=>v));
    $('kpi-chart').innerHTML=entries.map(([year,value])=>`<div class="kpi-year"><span>${year}${m.id==='waitlist'&&year==='2024'?'*':''}</span><span class="kpi-track" aria-hidden="true"><i class="kpi-fill" style="width:${value/scale*100}%"></i>${m.target!==null?`<i class="target-line" style="left:${m.target}%"></i>`:''}</span><strong>${kpiValue(value,m)}</strong></div>`).join('');
    const source=kpiData.sources[m.source];
    $('kpi-source').innerHTML=`<a href="${source.url}#page=${m.pdf_page}">Official ${m.source==='paramedics'?'2025 paramedic report':m.source==='infrastructure'?'2025 transportation asset plan':'2024 Housing Needs Assessment'} · PDF p. ${m.pdf_page} ↗</a>${m.target!==null?' · Dashed line: '+esc(targetLabel):''}${m.id==='waitlist'?' · *2024 snapshot is December 10, not December 31.':''}`;
    $('kpi-rows').innerHTML=entries.map(([year,value])=>`<tr><th scope="row">${year}${m.id==='waitlist'&&year==='2024'?' · Dec 10':''}</th><td>${kpiValue(value,m)}</td><td>${m.target===null?'Not included':m.target+'%'+(m.region&&m.region!=='city'?' citywide reference':'')}</td></tr>`).join('');
    $('kpi-caption').textContent=m.name+' · '+m.definition;
    $('kpi-coverage').textContent=m.note||group.note;
    $('condition-snapshot').hidden=state.group!=='infrastructure';
    if(state.group==='infrastructure'){
      const s=group.condition_snapshot;
      $('condition-snapshot').innerHTML=`<h3>Transportation condition snapshot</h3><p class="small">${esc(s.period)} · ${esc(s.name)}</p><div class="condition-bar" aria-hidden="true">${s.categories.map((c,i)=>`<span class="condition-${i}" style="width:${c.value}%"></span>`).join('')}</div><div class="condition-labels">${s.categories.map((c,i)=>`<span><i class="condition-${i}"></i>${esc(c.name)} ${c.value}%</span>`).join('')}</div><p class="small"><strong>15% in poor or very poor condition</strong>, weighted by replacement cost. ${esc(s.note)} <a href="${kpiData.sources[s.source].url}#page=${s.pdf_page}">Source: PDF p. ${s.pdf_page} ↗</a></p>`;
    }
    url();
  }
  async function loadHistory(){try{historyData=await get('history');$('history-error').hidden=true;renderHistory();}catch(e){$('history-error').hidden=false;$('history-summary').textContent='History unavailable; source downloads remain available.';}}
  async function loadKpis(){try{kpiData=await get('kpis');$('kpi-error').hidden=true;renderKpis();}catch(e){$('kpi-error').hidden=false;}}
  $('history-from').addEventListener('change',e=>{state.from=e.target.value;renderHistory();});
  $('history-to').addEventListener('change',e=>{state.to=e.target.value;renderHistory();});
  $('history-unit').addEventListener('change',e=>{state.rank=e.target.value;renderHistory();});
  document.querySelectorAll('[data-kpi]').forEach(b=>b.addEventListener('click',()=>{state.group=b.dataset.kpi;state.metric=kpiData?.groups[state.group].metrics[0].id||'';renderKpis();}));
  $('kpi-metric').addEventListener('change',e=>{state.metric=e.target.value;renderKpis();});
  $('kpi-region').addEventListener('change',e=>{state.region=e.target.value;renderKpis();});
  $('history-retry').addEventListener('click',loadHistory);$('kpi-retry').addEventListener('click',loadKpis);
  window.addEventListener('budget-prices-change',renderHistory);
  loadHistory();loadKpis();
})();

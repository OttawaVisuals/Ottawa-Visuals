/* Traffic-court view: reuse the audited OCJ snapshot and shared outcome model. */
(function(){
  'use strict';
  const M=typeof module==='undefined'?window.CourtOutcomes:require('../Ontario_Trials/model.js');
  const HTA='statute:highway-traffic-act',SPEED='hta:s-128-speeding',RED='hta:s-144-red-light-proceed-before-green';
  const calendarSources=d=>M.sources(d,'poa').filter(s=>s.period.calendar_year);
  // Prepayment and unknown trial verdicts stay separate from recorded guilt.
  const outcomeDefinitions=[
    ['paid','Prepaid',['prepaid']],
    ['guilty','Guilty (pleas / default)',['guilty_before','guilty_at','no_response','no_attendance']],
    ['withdrawn','Withdrawn',['withdrawn_before','withdrawn_at']],
    ['other','Other',['other_before','other_at']],
    ['trial','Completed after trial · outcome not reported',['following_trial']]
  ];
  const groupedOutcomes=values=>outcomeDefinitions.map(([key,label,fields])=>({key,label,value:fields.reduce((n,k)=>n+values[k],0)}));
  function selected(d,source,key){
    if(key==='all')return M.record(d,source.id,HTA);
    if(key!=='other')return M.record(d,source.id,key);
    const total=M.record(d,source.id,HTA),speed=M.record(d,source.id,SPEED),red=M.record(d,source.id,RED);
    if(!total||!speed||!red)return null;
    const values=Object.fromEntries(Object.keys(total.values).map(k=>[k,total.values[k]-speed.values[k]-red.values[k]]));
    if(Object.values(values).some(v=>v<0))throw Error('HTA components exceed their parent total.');
    return {key:'other',label:'All other HTA offences combined',values,source_row:[total.source_row,speed.source_row,red.source_row].join(' minus '),derived:true};
  }
  function composition(d,source){
    const all=M.record(d,source.id,HTA),speed=M.record(d,source.id,SPEED),red=M.record(d,source.id,RED);
    return all&&speed&&red?{total:all.values.disposed,speed:speed.values.disposed,red:red.values.disposed,other:all.values.disposed-speed.values.disposed-red.values.disposed}:null;
  }
  function cameraYear(report,series,year){
    const rows=report[series].months.filter(r=>r[0]===year);
    return {count:rows.length?rows.reduce((n,r)=>n+r[3],0):null,months:new Set(rows.map(r=>r[1])).size};
  }
  function exportRows(d,source,key,report){
    const row=selected(d,source,key),mix=composition(d,source),speed=cameraYear(report,'speed',source.period.calendar_year),red=cameraYear(report,'redlight',source.period.calendar_year);
    const groups=outcomeDefinitions.map(([k])=>k),metrics=Object.keys(d.records.find(r=>r.source_id===source.id).values);
    const header=['calendar_year','period','offence','unit','availability','hta_completed','speeding_completed','red_light_completed','other_hta_completed',...groups.flatMap(k=>[k+'_count',k+'_share']),...metrics,'speed_camera_violations_issued','speed_camera_months','red_light_camera_violations_issued','red_light_camera_months','source_url','source_locator','source_row'];
    const buckets=row?groupedOutcomes(row.values):[];
    return [header,[source.period.calendar_year,source.period.label,row?.label||key,'charges',row?'available':'unavailable',mix?.total,mix?.speed,mix?.red,mix?.other,...groups.flatMap(k=>{const b=buckets.find(x=>x.key===k);return [b?.value,row?M.share(b.value,row.values.disposed):null];}),...metrics.map(k=>row?.values[k]),speed.count,speed.months,red.count,red.months,source.url,source.locator,row?.source_row]];
  }
  function exportHistory(d,key,report){
    const rows=calendarSources(d).map(s=>exportRows(d,s,key,report));
    return [rows[0][0],...rows.map(r=>r[1])];
  }
  const api={HTA,SPEED,RED,calendarSources,selected,composition,cameraYear,exportRows,exportHistory,outcomeDefinitions,groupedOutcomes};
  if(typeof module!=='undefined'){module.exports=api;return;}
  window.TrafficCourt=api;
  let task;
  function load(){
    task??=fetch('../Ontario_Trials/data/outcomes.json').then(r=>{if(!r.ok)throw Error('Court data: HTTP '+r.status);return r.json();}).catch(e=>{task=null;throw e;});
    return task;
  }
  function exactTable(id,labels,series,totals,note){
    const rows=labels.map((label,i)=>[label,...series.map(s=>s.values[i]==null?'Unavailable':`${fmt(s.values[i])} (${M.formatShare(s.values[i],totals[i])})`)]);
    $(id+'-data').innerHTML=`<details class="chart-data" ${typeof Chart==='undefined'?'open':''}><summary>View chart data</summary><div class="table-wrap">${table(['Period',...series.map(s=>s.label)],rows,note+' · count (share)')}</div></details>`;
  }
  window.renderTrafficCourt=async function(state,token){
    $('section-kicker').textContent='Traffic offences · Court outcomes';
    $('section-title').textContent='Traffic charges: speeding, red lights and the rest';
    $('section-description').textContent='Ottawa City Highway Traffic Act charges completed in provincial-offence court. Charges, not drivers, police stops or newly issued tickets.';
    $('filters').innerHTML='';$('stats').innerHTML='';$('panels').innerHTML='<p class="note">Loading the audited court snapshot…</p>';
    $('download').disabled=true;exports=[];
    let court;
    try{court=await load();}catch(e){
      if(token!==generation)return;
      $('filter-scope').textContent='Court data is unavailable. Other report tabs remain available.';
      $('panels').innerHTML='<div class="notice">Court data could not load. <button type="button" id="court-retry">Retry court data</button> · <a href="../Ontario_Trials/courts.html">Full court report</a></div>';
      $('court-retry').addEventListener('click',()=>render().catch(reportError));return;
    }
    if(token!==generation)return;
    const sources=calendarSources(court),last=sources.at(-1);
    delete state.year; // Old shared links now use the same latest-year KPI snapshot.
    const source=last;
    const details=M.catalog(court,'poa').filter(r=>r.kind==='offence'&&r.group==='Highway Traffic Act'&&![SPEED,RED].includes(r.key));
    const options=[['all','All Highway Traffic Act charges'],[SPEED,'Speeding'],[RED,'Red-light offences'],['other','All other HTA offences combined'],...details.map(r=>[r.key,r.key==='hta:other-highway-traffic-act-charges'?'Other HTA charges (source catch-all)':r.label])];
    if(!options.some(([k])=>k===state.offence))state.offence='all';
    if(!['count','share'].includes(state.metric))state.metric='count';
    $('filters').innerHTML=select('offence','Traffic offence',options,state.offence)+`<div class="court-measure"><span>Chart measure</span><div role="group" aria-label="Chart measure">${[['count','Number completed'],['share','Share of completions']].map(([key,label])=>`<button type="button" data-court-metric="${key}" aria-pressed="${state.metric===key}">${label}</button>`).join('')}</div></div>`;
    document.querySelectorAll('[data-court-metric]').forEach(button=>button.addEventListener('click',()=>{
      if(state.metric===button.dataset.courtMetric)return;
      state.metric=button.dataset.courtMetric;
      render().then(()=>document.querySelector(`[data-court-metric="${state.metric}"]`)?.focus({preventScroll:true})).catch(reportError);
    }));
    $('filter-scope').textContent=`Selected offence: KPIs and detail table show ${last.period.calendar_year}, the latest calendar year. The first chart and CSV cover all calendar years. Measure buttons change the first two charts; the context chart retains all HTA offences.`;
    const row=selected(court,source,state.offence),v=row?.values;
    $('stats').innerHTML=stat(fmt(v?.disposed),`Charges completed · ${last.period.calendar_year}`)+stat(fmt(v?.prepaid),`Prepaid · ${last.period.calendar_year}`)+stat(fmt(v?groupedOutcomes(v).find(b=>b.key==='guilty').value:null),`Guilty: pleas / default · ${last.period.calendar_year}`);
    const outcomesRows=row?groupedOutcomes(v).map(b=>[b.label,b.value,M.formatShare(b.value,v.disposed)]):[];
    const note=`<div class="notice">Camera and officer-issued charges are combined in the court tables. The speeding/red-light pattern is consistent with automated enforcement, but these data cannot identify the exact camera share. Tickets issued and charges completed can fall in different years.</div>`;
    const groupingNote='Guilty combines pleas and guilt after no response / attendance. Prepaid fines stay separate. Completed after trial means a trial took place, but its outcome is not reported in these statistics. This is not a complete conviction rate. Raw categories remain in the CSV.';
    const selectedPanel=`<article class="card"><h3>${esc(row?.label||'Selected offence')} · ${esc(source.period.label)}</h3>${row?`<div class="table-wrap">${table(['Completion category','Charges','Share of completed'],outcomesRows)}</div><p class="note">${row.derived?'Derived':'Published'} completed total: ${fmt(v.disposed)}. Received: ${fmt(v.received)}; pending: ${fmt(v.pending)}. Shares use completed charges only.</p>`:'<p class="empty">No published row for this offence and year. Unavailable does not mean zero.</p>'}<p class="note"><a href="${esc(source.url)}" target="_blank" rel="noopener">Original court ${esc(source.format.toUpperCase())}</a> · ${esc(source.locator)}${row?' · '+(row.derived?'derived by subtracting table rows ':'source row ')+esc(row.source_row):''}. Snapshot reviewed ${esc(court.reviewed_on)}.</p><p class="note">${groupingNote}</p></article>`;
    $('panels').innerHTML='<div class="grid">'+panel('court-outcomes',`${esc(row?.label||'Selected offence')}: how the charges ended`,groupingNote+' Missing rows remain unavailable.',true)+'</div>'+selectedPanel+note+'<div class="grid">'+panel('court-mix','Context: speeding, red lights and all other HTA offences','All HTA charges completed, all calendar years. “All other” is the HTA total minus speeding and red lights, including the source’s catch-all category. These three parts add to the HTA total.',true)+'</div>'+`<p class="note">Only calendar-year provincial-offence publications are used here (${sources[0].period.calendar_year}–${last.period.calendar_year}). The file indexed as 2026 covers April 2025–March 2026 and is excluded to avoid overlapping years. <a href="../Ontario_Trials/courts.html?series=poa&period=${esc(source.id)}&offence=${encodeURIComponent(state.offence==='all'?HTA:state.offence==='other'?HTA:state.offence)}&mode=${state.metric}">Explore the full court report</a> · <a href="../Ontario_Trials/README.md">Definitions and source audit</a> · <a href="?section=speed">Speed-camera detail</a> · <a href="?section=redlight">Red-light-camera detail</a></p>`;
    const years=sources.map(s=>s.period.calendar_year),mix=sources.map(s=>composition(court,s)),totals=mix.map(r=>r?.total||0);
    const parts=[['speed','Speeding'],['red','Red lights'],['other','All other HTA offences']].map(([key,label])=>({label,values:mix.map(r=>r?.[key]??null)}));
    const asChart=(series,denominators)=>series.map(s=>({label:s.label,data:s.values.map((v,i)=>v==null?null:state.metric==='share'?(denominators[i]?v/denominators[i]*100:null):v)}));
    chart('court-mix','bar',years,asChart(parts,totals),{stacked:true,percent:state.metric==='share',label:ctx=>`${parts[ctx.datasetIndex].label}: ${fmt(parts[ctx.datasetIndex].values[ctx.dataIndex])} (${M.formatShare(parts[ctx.datasetIndex].values[ctx.dataIndex],totals[ctx.dataIndex])})`});
    exactTable('court-mix',years,parts,totals,'All HTA completions');
    const selectedRows=sources.map(s=>selected(court,s,state.offence)),selectedTotals=selectedRows.map(r=>r?.values.disposed||0);
    const outcomeSeries=outcomeDefinitions.map(([key,label])=>({label,values:selectedRows.map(r=>r?groupedOutcomes(r.values).find(b=>b.key===key).value:null)}));
    chart('court-outcomes','bar',years,asChart(outcomeSeries,selectedTotals),{stacked:true,percent:state.metric==='share',label:ctx=>{const series=outcomeSeries[ctx.datasetIndex],i=ctx.dataIndex;return `${series.label}: ${fmt(series.values[i])} (${M.formatShare(series.values[i],selectedTotals[i])})`;}});
    exactTable('court-outcomes',years,outcomeSeries,selectedTotals,'Selected offence completions');
    exports=exportHistory(court,state.offence,data);$('download').disabled=false;
  };
})();

(function(){
  'use strict';
  const M=window.CourtOutcomes,$=id=>document.getElementById(id);
  const nf=new Intl.NumberFormat('en-CA');
  let data,state={series:'crim',period:'',offence:'all',mode:'share',rolling:false};
  window.setTheme=mode=>{document.documentElement.dataset.theme=mode;};
  function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function link(text,url){const a=el('a',text);a.href=url;return a;}
  function count(value){return value===null||value===undefined?'—':nf.format(value);}
  function percent(value,total){return total>0?M.formatShare(value,total)+' of completions':'Percentage unavailable: no completions';}
  function option(label,value){const o=el('option',label);o.value=value;return o;}
  function currentSource(){return data.sources.find(s=>s.id===state.period);}
  function writeURL(){
    const params=new URLSearchParams({series:state.series,period:state.period,offence:state.offence,mode:state.mode});
    if(state.rolling)params.set('rolling','1');
    try{history.replaceState(null,'',location.pathname+'?'+params+location.hash);}catch(e){}
  }
  function filters(){
    $('period').replaceChildren();
    M.sources(data,state.series).reverse().forEach(s=>$('period').append(option(s.period.label,s.id)));
    $('period').value=state.period;
    $('offence').replaceChildren(option(state.series==='crim'?'All criminal cases':'All provincial offences','all'));
    const groups=new Map();
    for(const item of M.catalog(data,state.series).filter(r=>r.kind!=='total')){
      const label=item.kind==='group'?'Offence groups':item.kind==='statute'?'Statutes':item.group+' · specific offences';
      if(!groups.has(label)){const g=el('optgroup');g.label=label;groups.set(label,g);}
      groups.get(label).append(option(item.label,item.key));
    }
    groups.forEach(g=>$('offence').append(g));$('offence').value=state.offence;
    $('rolling').checked=state.rolling;
    for(const series of ['crim','poa'])$(series).setAttribute('aria-pressed',String(state.series===series));
    for(const mode of ['share','count'])$(mode).setAttribute('aria-pressed',String(state.mode===mode));
  }
  function selected(){
    const s=currentSource(),r=M.record(data,s.id,state.offence), criminal=state.series==='crim',unit=criminal?'cases':'charges';
    const item=M.catalog(data,state.series).find(c=>c.key===state.offence);
    $('selected-title').textContent=item?.label||'Selected subject';$('selected-period').textContent=s.period.label;
    $('scope').textContent=criminal?'Criminal cases include adult and youth cases. One case can contain several charges; the most serious charge sets its offence type.':'Provincial offences count individual charges, not people or criminal cases. Includes Highway Traffic Act and other statutes; excludes Part II parking matters.';
    $('period-note').textContent=s.period.calendar_year?'Calendar-year reporting period. Shares use the completed total for this subject and period.':'Non-calendar reporting period. It overlaps other publications; its totals must not be added to calendar-year totals.';
    $('completed-label').textContent=criminal?'Cases completed in OCJ':'Charges completed';
    $('withdrawal-label').textContent=criminal?'Withdrawn / stayed before trial':'Withdrawn before / at trial date';
    $('history-title').textContent=criminal?'How cases were completed':'How charges were completed';
    $('chart-note').textContent=`Bars show ${state.mode==='share'?'the share of completed '+unit:'the number of completed '+unit}, for the selected offence or group. Select a period label to inspect it above. No totals are added across years.`;
    $('unavailable').hidden=!!r;
    const v=r?.values,b=r?M.buckets(state.series,v):[];
    $('completed').textContent=count(v?.disposed);
    $('pleas').textContent=count(r?b.find(x=>x.key==='pleas').value:null);
    $('withdrawals').textContent=count(r?(criminal?v.withdrawn_stayed_before:v.withdrawn_before+v.withdrawn_at):null);
    $('trials').textContent=count(v?.following_trial);
    $('completed-note').textContent=r?`Published ${unit} completed · not unique people`:'No published row in this period';
    $('pleas-note').textContent=r?percent(v.guilty_before+v.guilty_at,v.disposed)+' · not all guilty outcomes':'Unavailable';
    $('withdrawals-note').textContent=r?percent(criminal?v.withdrawn_stayed_before:v.withdrawn_before+v.withdrawn_at,v.disposed)+' · reasons not reported':'Unavailable';
    $('trials-note').textContent=r?percent(v.following_trial,v.disposed)+' · result not split':'Unavailable';
    $('selected-details').replaceChildren();
    if(r){
      const table=el('table');table.append(el('caption',`${s.period.label} · ${r.label} · ${unit}`));
      const body=el('tbody');
      for(const bucket of b){const tr=el('tr');tr.append(el('th',bucket.label),el('td',count(bucket.value)+' · '+M.formatShare(bucket.value,v.disposed)));body.append(tr);}
      const total=el('tr');total.append(el('th','Published completed total'),el('td',count(v.disposed)));body.append(total);table.append(body);$('selected-details').append(table);
      $('selected-details').append(el('p',`Received: ${count(v.received)}. Pending: ${count(v.pending)}. These are different measures and are excluded from the outcome-share denominator.`));
      $('selected-details').append(el('p',`Source: ${s.locator}; ${s.format==='pdf'?'extracted table row':'worksheet row'} ${r.source_row}.`));
      if(s.hierarchy_differences.length)$('selected-details').append(el('p','Source discrepancy: some printed subtotals do not add to the printed overall totals. This view retains the source’s printed row; see the extraction audit below.','notice'));
    }
    $('selected-details').append(link('Open original '+s.format.toUpperCase()+' publication',s.url));
  }
  function draw(){
    const rows=M.timeline(data,state.series,state.offence,state.rolling), defs=M.definitions[state.series];
    $('legend').replaceChildren();
    for(const [key,label] of defs){const item=el('span');const swatch=el('i',undefined,'swatch');swatch.dataset.cat=key;item.append(swatch,el('span',label));$('legend').append(item);}
    $('overlap-note').hidden=!state.rolling;
    $('chart').replaceChildren();
    const max=Math.max(1,...rows.map(r=>r.record?.values.disposed||0));
    for(const row of rows){
      const line=el('div',undefined,'chart-row'+(row.id===state.period?' active':'')+(!row.source?' gap-row':'')+(row.source&&!row.source.period.calendar_year?' rolling-row':''));
      const label=row.source?el('button',row.source.period.calendar_year?String(row.source.period.calendar_year):row.source.period.label,'period-pick'):el('span',row.label);
      if(row.source){label.type='button';label.setAttribute('aria-label','Show '+row.source.period.label);label.addEventListener('click',()=>{state.period=row.id;render();});if(!row.source.period.calendar_year)label.append(el('small','Overlapping period'));}
      line.append(label);
      if(!row.record){line.classList.add('gap-row');line.append(el('span',row.source?'No published row for this subject':'No calendar-year source indexed','missing'),el('span','—','chart-total'));}
      else{
        const total=row.record.values.disposed,b=M.buckets(state.series,row.record.values),bar=el('div',undefined,'bar-track');
        bar.setAttribute('role','img');bar.setAttribute('aria-label',`${row.source.period.label}: `+b.map(x=>x.label+' '+count(x.value)).join('; '));
        for(const bucket of b){
          if(!bucket.value)continue;
          const segment=el('span',undefined,'segment');segment.dataset.cat=bucket.key;
          segment.style.width=(100*bucket.value/(state.mode==='share'?(total||1):max))+'%';
          segment.title=`${bucket.label}: ${count(bucket.value)} (${total?M.formatShare(bucket.value,total):'percentage unavailable'})`;bar.append(segment);
        }
        line.append(bar,el('span',count(total),'chart-total'));
      }
      $('chart').append(line);
    }
    $('chart').append(el('p',state.mode==='share'?'Bar length = 100% of completions. Right-hand numbers are completed totals.':'Bar lengths use a common count scale. Right-hand numbers are completed totals.','axis-note'));
    const table=$('table');table.replaceChildren();
    table.append(el('caption',`${state.series==='crim'?'Cases':'Charges'} completed · ${state.mode==='share'?'percent of each period’s completed total':'counts'} · no cross-period total`));
    const head=el('thead'),headrow=el('tr');
    for(const label of ['Reporting period',...defs.map(x=>x[1]),'Completed total']){const th=el('th',label);th.scope='col';headrow.append(th);}head.append(headrow);table.append(head);
    const body=el('tbody');
    for(const row of rows){
      const tr=el('tr'),label=row.source?.period.label||row.label;const th=el('th',label);th.scope='row';tr.append(th);
      if(!row.record){const td=el('td','Unavailable');td.colSpan=defs.length+1;tr.append(td);}
      else{const total=row.record.values.disposed;for(const b of M.buckets(state.series,row.record.values))tr.append(el('td',state.mode==='share'?M.formatShare(b.value,total):count(b.value)));tr.append(el('td',count(total),'total'));}
      body.append(tr);
    }
    table.append(body);
  }
  function audit(){
    const sources=M.sources(data,state.series),calendar=sources.filter(s=>s.period.calendar_year);
    $('coverage-details').textContent=`${state.series==='crim'?'Criminal':'Provincial-offence'} publications indexed ${Math.min(...sources.map(s=>s.publication_year))}–${Math.max(...sources.map(s=>s.publication_year))}. Latest available calendar-year publication: ${calendar.at(-1).period.calendar_year}. Snapshot reviewed ${data.reviewed_on}. This page is refreshed manually from the source index.`;
    $('sources').replaceChildren();
    for(const series of ['crim','poa']){
      const li=el('li',undefined,'source-group');li.append(el('strong',series==='crim'?'Criminal publications: ':'Provincial-offence publications: '));
      for(const s of M.sources(data,series))li.append(link(String(s.publication_year)+(s.period.calendar_year?'':' (non-calendar)'),s.url));
      $('sources').append(li);
    }
    $('audit-summary').replaceChildren(el('p',`${data.records.length} extracted rows from ${data.sources.length} publications. Each row’s outcome components reconcile to its printed totals.`));
    for(const s of data.sources.filter(s=>s.hierarchy_differences.length)){
      const p=el('p',`${s.id} (${s.locator}): `,'audit-row');p.append(el('span',s.hierarchy_differences.map(d=>`${d.level} ${d.metric}: subtotals ${count(d.sum_of_children)}; printed total ${count(d.published_total)}`).join('. ')));$('audit-summary').append(p);
    }
  }
  function render(){filters();selected();draw();audit();writeURL();}
  function reset(series=state.series){state={series,period:M.latestCalendar(data,series).id,offence:'all',mode:'share',rolling:false};render();}
  async function init(){
    try{
      const response=await fetch('data/outcomes.json');if(!response.ok)throw Error(response.status);data=await response.json();
      const params=new URLSearchParams(location.search),series=params.get('series')==='poa'?'poa':'crim';
      const period=M.sources(data,series).find(s=>s.id===params.get('period'))||M.latestCalendar(data,series);
      const offence=M.catalog(data,series).some(r=>r.key===params.get('offence'))?params.get('offence'):'all';
      state={series,period:period.id,offence,mode:params.get('mode')==='count'?'count':'share',rolling:params.get('rolling')==='1'||!period.period.calendar_year};
      const range=series=>{const years=M.sources(data,series).map(s=>s.publication_year);return Math.min(...years)+'–'+Math.max(...years);};
      const cYear=M.latestCalendar(data,'crim').period.calendar_year,pYear=M.latestCalendar(data,'poa').period.calendar_year;
      $('coverage').textContent=`Criminal publications ${range('crim')} · Provincial-offence publications ${range('poa')} · Reviewed ${data.reviewed_on} · Latest calendar year: ${cYear===pYear?cYear:'criminal '+cYear+', provincial '+pYear}`;
      $('download').disabled=false;$('error').hidden=true;render();
    }catch(e){$('error').hidden=false;$('coverage').textContent='Data unavailable. Retry or open the official statistics.';}
  }
  for(const series of ['crim','poa'])$(series).addEventListener('click',()=>{if(data)reset(series);});
  for(const mode of ['share','count'])$(mode).addEventListener('click',()=>{if(data){state.mode=mode;render();}});
  $('period').addEventListener('change',()=>{state.period=$('period').value;if(!currentSource().period.calendar_year)state.rolling=true;render();});
  $('offence').addEventListener('change',()=>{state.offence=$('offence').value;render();});
  $('rolling').addEventListener('change',()=>{state.rolling=$('rolling').checked;render();});
  $('reset').addEventListener('click',()=>{if(data)reset();});$('retry').addEventListener('click',init);
  $('download').addEventListener('click',()=>{
    const text=M.csv(data,M.timeline(data,state.series,state.offence,state.rolling),state.series);
    const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'})),a=link('',url);
    a.download='ottawa-court-outcomes-'+state.series+'.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  init();
})();

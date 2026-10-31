'use strict';
(() => {
  const H = window.WEALTH_HISTORY, $ = id => document.getElementById(id);
  if (!H) { $('survey-chart').textContent = 'Historical data could not load. Use the CSV downloads.'; return; }
  const colors = ['var(--accent)', 'var(--accent-2)', 'var(--green)', 'var(--purple)', 'var(--red)'];
  const dashes = ['', '8 4', '2 4', '10 3 2 3', '4 3'];
  const num = n => n == null ? 'Not available' : Number(n).toLocaleString('en-CA', {maximumFractionDigits:1});
  const percent = n => n == null ? 'Not available' : `${Number(n).toFixed(1).replace('-', '−')}%`;
  const dollars = n => n == null ? 'Not available' : (n < 0 ? '−' : '') + '$' + Math.abs(n).toLocaleString('en-CA', {maximumFractionDigits:0});
  const text = (x,y,t,extra='') => `<text x="${x}" y="${y}" font-size="12" ${extra}>${t}</text>`;
  const svg = (w,h,title,body) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${title}"><title>${title}</title>${body}</svg>`;
  const table = (headers,rows,caption) => `<table><caption>${caption}</caption><thead><tr>${headers.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((v,i)=>i===0?`<th scope="row">${v}</th>`:`<td>${v}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const options = (el,items,preferred) => {
    const current = preferred ?? el.value;
    el.innerHTML = items.map(i => `<option value="${i.value}">${i.label}</option>`).join('');
    if (items.some(i=>i.value===current)) el.value=current;
  };
  const source = id => `<a href="${H.sources[id].url}">${H.sources[id].title}</a> · ${H.sources[id].locator}`;

  // Each series keeps its own nulls: no line crosses an unavailable observation.
  function plot(id,legendId,years,series,title,unit='percent') {
    const el=$(id), w=Math.max(240,el.clientWidth), h=290, left=unit==='dollars'?60:40, right=w-14, top=18, bottom=h-38;
    const values=series.flatMap(s=>s.values.filter(v=>v!=null));
    const target=Math.max(...values)/4||1, magnitude=10**Math.floor(Math.log10(target));
    const step=unit==='gini'?.25:([1,2,5,10].find(n=>n*magnitude>=target)||10)*magnitude;
    let low=Math.min(0,Math.min(...values)*1.15);
    let high=unit==='gini'?1:Math.ceil(Math.max(...values)/step)*step;
    if(high===low)high=low+1;
    const x=year=>left+(year-years[0])/(years.at(-1)-years[0]||1)*(right-left);
    const y=v=>bottom-(v-low)/(high-low)*(bottom-top);
    const axisFormat=v=>unit==='percent'?`${num(v)}%`:unit==='gini'?v.toFixed(2):`${v<0?'−':''}$${Math.abs(v)>=1e6?(Math.abs(v)/1e6).toFixed(1)+'m':Math.round(Math.abs(v)/1000)+'k'}`;
    const format=v=>unit==='percent'?percent(v):unit==='gini'?v.toFixed(3):dollars(v);
    let body='';
    for(let i=Math.ceil(low/step);i<=Math.round(high/step);i++){const v=step*i||0;body+=`<line class="axis" x1="${left}" x2="${right}" y1="${y(v)}" y2="${y(v)}"/>`+text(left-7,y(v)+4,axisFormat(v),'text-anchor="end"');}
    // Tick spacing uses rendered width; preserve endpoints and every plotted dot.
    let lastLabelX=-Infinity;
    years.forEach((year,i)=>{
      if(i!==0&&i!==years.length-1&&(x(year)-lastLabelX<54||right-x(year)<54))return;
      body+=text(x(year),h-11,year,`text-anchor="${i===0?'start':i===years.length-1?'end':'middle'}"`);
      lastLabelX=x(year);
    });
    series.forEach((s,k)=>{
      let segment=[];
      const flush=()=>{if(segment.length>1)body+=`<polyline points="${segment.join(' ')}" fill="none" stroke="${colors[k]}" stroke-width="3" stroke-dasharray="${dashes[k]}"/>`;segment=[];};
      s.values.forEach((v,i)=>{if(v==null){flush();return;}segment.push(`${x(years[i])},${y(v)}`);});flush();
      s.values.forEach((v,i)=>{if(v==null)return;body+=`<circle cx="${x(years[i])}" cy="${y(v)}" r="4" fill="${colors[k]}"><title>${years[i]} · ${s.name}: ${format(v)}</title></circle>`;});
    });
    el.innerHTML=svg(w,h,title+' Exact values in the table below.',body);
    $(legendId).innerHTML=series.map((s,k)=>`<span><i style="border-color:${colors[k]};border-top-style:${k===1?'dashed':k===2?'dotted':'solid'}"></i>${s.name}</span>`).join('');
  }

  function survey(){
    const metric=$('survey-metric').value;
    const series=H.survey[0].groups.map((g,i)=>({name:g.label,values:H.survey.map(d=>d.groups[i][metric])}));
    plot('survey-chart','survey-legend',H.survey.map(d=>d.year),series,'Survey of Financial Security, 1999–2023',metric==='share'?'percent':'dollars');
    $('survey-table').innerHTML=table(['Year / wealth group','Share','Median (2023 CAD)','Mean (2023 CAD)'],H.survey.flatMap(d=>d.groups.map(g=>[`${d.year} · ${g.label}`,percent(g.share),dollars(g.median_2023_dollars),dollars(g.average_2023_dollars)])),'All six survey years and five wealth quintiles. Mean and median are the published values for those holding net worth.');
  }

  function pbo(reset=false){
    const edition=$('pbo-edition').value, d=H['pbo_history_'+edition];
    if(reset||!$('pbo-group').options.length)options($('pbo-group'),d.groups.map(g=>({value:g,label:g})),$('pbo-group').value||'Top 1%');
    const index=d.groups.indexOf($('pbo-group').value);
    $('pbo-history-title').textContent=`How much does the ${$('pbo-group').value.toLowerCase()} own?`;
    const series=edition==='2021'?[{name:'SFS + Forbes',values:d.forbes[index]},{name:'SFS + Canadian Business',values:d.cb[index]}]:[{name:'SFS + Forbes',values:d.forbes[index]},{name:'SFS only',values:d.survey[index]},{name:'SFS + Forbes + CB/Maclean’s',values:d.enriched[index]}];
    plot('pbo-history-chart','pbo-history-legend',d.years,series,`${$('pbo-group').value} wealth share, PBO ${edition} report`);
    $('pbo-history-note').textContent=H.sources['pbo'+edition].note+' Missing observations are not connected. Lines between available survey years are visual guides, not annual estimates.';
    $('pbo-history-table').innerHTML=table(['Year',...series.map(s=>s.name)],d.years.map((year,i)=>[year,...series.map(s=>percent(s.values[i]))]),`${$('pbo-group').value}: percentage of family net wealth. Report editions are separate.`);
    $('pbo-history-source').innerHTML=source('pbo'+edition);
  }

  function bars(id,labels,values,title){
    const el=$(id),w=Math.max(240,el.clientWidth),h=labels.length*48+32,left=10,right=w-14,max=80;
    const x=v=>left+v/max*(right-left);let body='';
    [0,20,40,60,80].forEach(v=>{body+=`<line class="axis" x1="${x(v)}" x2="${x(v)}" y1="16" y2="${h-30}"/>`+text(x(v),h-8,`${v}%`,`text-anchor="${v===0?'start':v===80?'end':'middle'}"`);});
    labels.forEach((label,i)=>{const top=12+i*48;body+=text(left,top,label,'class="chart-label"')+text(right,top,percent(values[i]),'text-anchor="end" class="chart-label"');body+=`<rect class="bar ${label==='Top 1%'?'top':''}" x="${left}" y="${top+8}" width="${x(values[i])-left}" height="19"><title>${label}: ${percent(values[i])}</title></rect>`;});
    el.innerHTML=svg(w,h,title,body);
  }

  function snapshot(reset=false){
    const view=$('pbo-view').value;
    if(reset||!$('pbo-snapshot').options.length){
      options($('pbo-snapshot'),view==='percentile'?H.snapshots.map(s=>({value:s.id,label:s.label})):[{value:'2019',label:'2019 · 2021 report'},{value:'2023',label:'2023 · 2025 report'}],view==='percentile'?'2023-estimate':'2023');
    }
    const d=view==='percentile'?H.snapshots.find(s=>s.id===$('pbo-snapshot').value):H.thresholds[$('pbo-snapshot').value];
    const labels=view==='percentile'?H.percentile_groups:H.thresholds.labels.map(t=>'Above '+t);
    bars('pbo-snapshot-chart',labels,d.shares,`PBO wealth shares, ${$('pbo-snapshot').selectedOptions[0].text}`);
    $('pbo-snapshot-note').textContent=d.kind==='projection'?'Projection, not a new survey observation. '+H.sources[d.source].note: 'Modelled estimate. '+H.sources[d.source].note;
    const rows=labels.map((label,i)=>[label,percent(d.shares[i]),...(view==='percentile'?[d.threshold_millions[i]]:[]),num(d.families_thousands[i]),num(d.wealth_billions[i])]);
    $('pbo-snapshot-table').innerHTML=table(['Group','Wealth share',...(view==='percentile'?['Net-worth cutoff / range ($m)']:[]),'Families (thousands)','Net wealth ($bn)'],rows,'Nominal CAD at the reference date. Groups overlap and must not be summed. Family counts and wealth totals are published rounded values.');
    $('pbo-snapshot-source').innerHTML=source(d.source)+' · Selected table: '+d.locator;
  }

  function early(reset=false){
    const d=H.historical_studies.find(s=>s.id===$('early-study').value);
    const medianAvailable=!!d.decile_medians_2005_dollars;
    $('early-metric').querySelector('option[value="median"]').disabled=!medianAvailable;
    if(!medianAvailable&&$('early-metric').value==='median')$('early-metric').value='share';
    const metric=$('early-metric').value;
    if(reset||!$('early-group').options.length)options($('early-group'),[{value:'all',label:'All deciles'},...Array.from({length:10},(_,i)=>({value:String(i),label:i===9?'Top 10%':i===0?'Bottom 10%':`Decile ${i+1}`}))],$('early-group').value||'9');
    $('early-group').disabled=metric==='gini';
    const indices=$('early-group').value==='all'?Array.from({length:10},(_,i)=>i):[Number($('early-group').value)];
    // All-decile mode uses two panels, avoiding ten overlapping lines.
    const series=metric==='gini'?[{name:'Gini',values:d.gini}]:indices.map(i=>({name:i===9?'Top 10%':i===0?'Bottom 10%':`Decile ${i+1}`,values:d.years.map((_,j)=>metric==='median'?d.decile_medians_2005_dollars[j][i]:d.decile_shares[j][i])}));
    if(series.length>5){
      $('early-chart').innerHTML='<div id="early-low"></div><div id="early-high"></div>';
      $('early-legend').innerHTML='<div id="early-low-legend" class="legend"></div><div id="early-high-legend" class="legend"></div>';
      plot('early-low','early-low-legend',d.years,series.slice(0,5),'Lower five wealth deciles',metric==='median'?'dollars':'percent');
      plot('early-high','early-high-legend',d.years,series.slice(5),'Upper five wealth deciles',metric==='median'?'dollars':'percent');
    }else plot('early-chart','early-legend',d.years,series,d.label,metric==='gini'?'gini':metric==='median'?'dollars':'percent');
    $('early-note').textContent=H.sources[d.id].note+' These are three survey observations, not an annual series. The two studies’ 1984 values differ; they are not joined.'+(series.length>5?' Lower- and upper-decile panels use separate vertical scales.':'');
    $('early-table').innerHTML=table(['Year / wealth decile','Share',...(medianAvailable?['Median (2005 CAD)']:[])],d.years.flatMap((year,j)=>d.decile_shares[j].map((v,i)=>[`${year} · ${i===9?'Top 10%':i===0?'Bottom 10%':`Decile ${i+1}`}`,percent(v),...(medianAvailable?[dollars(d.decile_medians_2005_dollars[j][i])]:[])])),'All family units; unadjusted published decile shares. Rounding may affect sums.')+table(['Year','Gini'],d.years.map((year,i)=>[year,d.gini[i].toFixed(3)]),'Within-study Gini estimates; a higher value indicates more concentration.');
    $('early-source').innerHTML=source(d.id)+(H.sources[d.id].table_url?` · <a href="${H.sources[d.id].table_url}">Numeric table</a>`:'');
  }

  $('survey-metric').addEventListener('change',survey);
  $('pbo-edition').addEventListener('change',()=>pbo(true));$('pbo-group').addEventListener('change',()=>pbo());
  $('pbo-view').addEventListener('change',()=>snapshot(true));$('pbo-snapshot').addEventListener('change',()=>snapshot());
  ['early-study','early-metric','early-group'].forEach(id=>$(id).addEventListener('change',()=>early(true)));
  function render(){survey();pbo();snapshot();early();}
  let frame;new ResizeObserver(()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(render);}).observe($('survey-section'));
  render();
})();

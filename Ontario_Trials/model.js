/* Pure transformations shared by the page and its data checks. */
(function(root){
  'use strict';
  const definitions={
    crim:[
      ['pleas','Guilty pleas',['guilty_before','guilty_at']],
      ['stayed','Withdrawn / stayed before trial',['withdrawn_stayed_before']],
      ['withdrawn','Withdrawn at trial date',['withdrawn_at']],
      ['other','Other before / at trial date',['other_before','other_at']],
      ['trial','Following a trial · result not split',['following_trial']]
    ],
    poa:[
      ['paid','Prepaid fines',['prepaid']],
      ['pleas','Guilty pleas',['guilty_before','guilty_at']],
      ['default','Guilty: no response / attendance',['no_response','no_attendance']],
      ['withdrawn','Withdrawn',['withdrawn_before','withdrawn_at']],
      ['other','Other before / at trial date',['other_before','other_at']],
      ['trial','Following a trial · result not split',['following_trial']]
    ]
  };
  function buckets(series,values){
    return definitions[series].map(([key,label,fields])=>({key,label,value:fields.reduce((a,f)=>a+values[f],0)}));
  }
  function share(value,total){return total>0?value/total:null;}
  function formatShare(value,total){
    const p=share(value,total);
    return p===null?'n/a':p>0&&p<0.001?'<0.1%':new Intl.NumberFormat('en-CA',{style:'percent',maximumFractionDigits:1}).format(p);
  }
  function sources(data,series){return data.sources.filter(s=>s.series===series).sort((a,b)=>a.period.end.localeCompare(b.period.end));}
  function latestCalendar(data,series){return sources(data,series).filter(s=>s.period.calendar_year).at(-1);}
  function record(data,sourceId,key){return data.records.find(r=>r.source_id===sourceId&&r.key===key)||null;}
  function catalog(data,series){
    const ids=new Set(sources(data,series).map(s=>s.id)), result=new Map();
    data.records.filter(r=>ids.has(r.source_id)).sort((a,b)=>a.source_id.localeCompare(b.source_id)).forEach(r=>result.set(r.key,{key:r.key,label:r.label,group:r.group,kind:r.kind}));
    return [...result.values()].sort((a,b)=>a.group.localeCompare(b.group)||a.label.localeCompare(b.label));
  }
  function timeline(data,series,key,includeOverlapping=false){
    const selected=sources(data,series), yearly=selected.filter(s=>s.period.calendar_year);
    const first=Math.min(...yearly.map(s=>s.period.calendar_year)),last=Math.max(...yearly.map(s=>s.period.calendar_year));
    const rows=[];
    for(let year=first;year<=last;year++){
      const source=yearly.find(s=>s.period.calendar_year===year);
      rows.push({id:source?.id||'gap-'+year,key,label:String(year),sort:year+'-12-31',source:source||null,record:source?record(data,source.id,key):null});
    }
    if(includeOverlapping)for(const s of selected.filter(s=>!s.period.calendar_year))rows.push({id:s.id,key,label:s.period.label,sort:s.period.end,source:s,record:record(data,s.id,key)});
    return rows.sort((a,b)=>a.sort.localeCompare(b.sort)||a.id.localeCompare(b.id));
  }
  function csv(data,rows,series){
    const metrics=[...new Set(data.records.filter(r=>r.source_id.startsWith(series+'-')).flatMap(r=>Object.keys(r.values)))];
    const grouped=definitions[series].flatMap(([key])=>[key+'_count',key+'_share']);
    const fields=['series','unit','period','period_start','period_end','calendar_year','subject','subject_key','availability',...grouped,...metrics,'source_url','source_locator','source_row'];
    const quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
    return '\ufeff'+[fields.map(quote).join(','),...rows.map(row=>{
      const r=row.record,s=row.source;
      const entry={series,unit:series==='crim'?'cases':'charges',period:s?.period.label||row.label,period_start:s?.period.start,period_end:s?.period.end,calendar_year:s?.period.calendar_year,
        subject:r?.label||catalog(data,series).find(c=>c.key===row.key)?.label,subject_key:row.key,availability:r?'available':'unavailable',...r?.values,source_url:s?.url,source_locator:s?.locator,source_row:r?.source_row};
      if(r)for(const b of buckets(series,r.values)){entry[b.key+'_count']=b.value;entry[b.key+'_share']=share(b.value,r.values.disposed);}
      return fields.map(f=>quote(entry[f])).join(',');
    })].join('\r\n');
  }
  const api={definitions,buckets,share,formatShare,sources,latestCalendar,record,catalog,timeline,csv};
  if(typeof module!=='undefined')module.exports=api;else root.CourtOutcomes=api;
})(typeof window==='undefined'?{}:window);

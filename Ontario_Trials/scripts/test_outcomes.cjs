const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const M=require('../model.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/outcomes.json'),'utf8'));

test('all published rows reconcile exactly to completed totals and have provenance',()=>{
  assert.equal(data.sources.length,27);assert.equal(data.records.length,903);
  const seen=new Set();
  for(const r of data.records){
    const source=data.sources.find(s=>s.id===r.source_id);assert.ok(source);
    const identity=r.source_id+'|'+r.key;assert.ok(!seen.has(identity));seen.add(identity);
    assert.equal(M.buckets(source.series,r.values).reduce((sum,b)=>sum+b.value,0),r.values.disposed,identity);
    for(const n of Object.values(r.values))assert.ok(Number.isSafeInteger(n)&&n>=0);
    assert.ok(r.source_row>0&&source.locator&&source.url&&source.sha256.length===64);
    assert.ok(source.period.start<source.period.end);
  }
});
test('latest complete calendar-year totals match directly inspected 2025 workbook rows',()=>{
  assert.equal(M.latestCalendar(data,'crim').id,'crim-2025');
  assert.equal(M.latestCalendar(data,'poa').id,'poa-2025');
  const c=M.record(data,'crim-2025','all'),p=M.record(data,'poa-2025','all');
  assert.equal(c.values.disposed,11005);assert.equal(c.values.guilty_before+c.values.guilty_at,5413);
  assert.equal(c.values.withdrawn_stayed_before,4119);assert.equal(c.values.following_trial,458);
  assert.equal(p.values.disposed,436729);assert.equal(p.values.prepaid,254268);
  assert.equal(p.values.no_response+p.values.no_attendance,157755);
});
test('calendar history never silently treats rolling source filenames as years',()=>{
  const history=M.timeline(data,'crim','all');
  const gap=history.find(r=>r.label==='2020');assert.equal(gap.source,null);assert.equal(gap.record,null);
  assert.ok(!history.some(r=>r.id==='crim-2026'||r.id==='crim-2020'));
  const expanded=M.timeline(data,'crim','all',true);
  assert.equal(expanded.find(r=>r.id==='crim-2020').source.period.label,'October 2019 to September 2020');
  assert.equal(expanded.find(r=>r.id==='crim-2026').source.period.label,'April 2025 to March 2026');
  assert.equal(M.timeline(data,'poa','all').find(r=>r.label==='2020').source.period.calendar_year,2020);
});
test('offence selection uses its own row rather than mixing totals with detail',()=>{
  const key='offence:sexual-assault';const rows=M.timeline(data,'crim',key);
  const selected=rows.find(r=>r.id==='crim-2025').record;
  assert.equal(selected.values.disposed,146);assert.equal(selected.values.following_trial,54);
  assert.ok(rows.every(r=>!r.record||r.record.key===key));
  const parent=M.record(data,'crim-2025','group:crimes-against-the-person');
  const leaves=data.records.filter(r=>r.source_id==='crim-2025'&&r.kind==='offence'&&r.group===parent.group);
  assert.equal(leaves.reduce((n,r)=>n+r.values.disposed,0),parent.values.disposed);
});
test('missing rows and zero completed totals remain distinct',()=>{
  assert.equal(M.record(data,'poa-2016','statute:dog-owners-liability-act'),null);
  assert.equal(M.share(0,0),null);assert.equal(M.share(0,10),0);
  assert.equal(M.formatShare(1,10000),'<0.1%');assert.equal(M.formatShare(0,10000),'0%');assert.equal(M.formatShare(0,0),'n/a');
  assert.ok(data.records.some(r=>r.values.disposed===0));
  const other='offence:other-federal-statutes-including-the-federal-cannabis-act';
  assert.equal(M.record(data,'crim-2012',other),null);
});
test('source hierarchy discrepancies are preserved without invented allocation',()=>{
  const flagged=data.sources.filter(s=>s.hierarchy_differences.length);
  assert.deepEqual(flagged.map(s=>s.id),['poa-2016']);assert.equal(flagged[0].hierarchy_differences.length,5);
  const overall=M.record(data,'poa-2016','all');
  const parents=data.records.filter(r=>r.source_id==='poa-2016'&&r.kind==='statute');
  assert.equal(overall.values.disposed,78536);assert.equal(parents.reduce((sum,r)=>sum+r.values.disposed,0),78535);
  assert.ok(flagged[0].excluded_empty_rows.some(r=>r.label==="Dog Owners' Liability Act"));
});
test('chart shares use completed totals and never assume trial results are guilty',()=>{
  const row=M.record(data,'crim-2025','all');
  const b=M.buckets('crim',row.values);assert.equal(b.find(x=>x.key==='pleas').value,5413);
  assert.equal(b.find(x=>x.key==='trial').value,458);
  assert.ok(Math.abs(b.reduce((sum,x)=>sum+M.share(x.value,row.values.disposed),0)-1)<1e-12);
  assert.notEqual(M.share(5413,row.values.disposed),M.share(5413,row.values.received));
});
test('CSV includes full reporting periods, gaps, raw counts and original source locations',()=>{
  const csv=M.csv(data,M.timeline(data,'crim','all',true),'crim');
  assert.ok(csv.startsWith('\ufeff"series"'));assert.ok(csv.includes('"October 2019 to September 2020"'));
  assert.ok(csv.includes('"unavailable"'));assert.ok(csv.includes('"5413"'));assert.ok(csv.includes('"pleas_share"'));
  assert.ok(csv.includes('"4864"'));assert.ok(csv.includes('2025-Offence-Based-Criminal.xlsx'));
  assert.ok(csv.includes('"Sheet: Ottawa"'));
});

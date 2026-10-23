const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const C=require('../court.js'),M=require('../../Ontario_Trials/model.js');
const d=JSON.parse(fs.readFileSync(path.join(__dirname,'../../Ontario_Trials/data/outcomes.json'),'utf8'));
const cameras=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/derived/stops_report/report.json'),'utf8'));
const latest=C.calendarSources(d).at(-1);

test('HTA details exhaust their parent for every metric in every publication',()=>{
  for(const source of M.sources(d,'poa')){
    const total=M.record(d,source.id,C.HTA);
    const children=d.records.filter(r=>r.source_id===source.id&&r.group==='Highway Traffic Act'&&r.kind==='offence');
    assert.equal(children.length,15);
    for(const key of Object.keys(total.values))assert.equal(children.reduce((n,r)=>n+r.values[key],0),total.values[key],source.id+' '+key);
  }
});

test('annual mix excludes overlapping windows and matches inspected 2025 totals',()=>{
  assert.equal(latest.id,'poa-2025');assert.equal(C.calendarSources(d).length,11);
  assert.ok(!C.calendarSources(d).some(s=>s.id==='poa-2026'));
  assert.deepEqual(C.composition(d,latest),{total:417143,speed:353345,red:47309,other:16489});
});

test('combined other offences includes the catch-all and reconciles every outcome',()=>{
  for(const source of C.calendarSources(d)){
    const other=C.selected(d,source,'other');
    const children=d.records.filter(r=>r.source_id===source.id&&r.group==='Highway Traffic Act'&&r.kind==='offence'&&![C.SPEED,C.RED].includes(r.key));
    for(const key of Object.keys(other.values))assert.equal(other.values[key],children.reduce((n,r)=>n+r.values[key],0));
    assert.equal(M.buckets('poa',other.values).reduce((n,b)=>n+b.value,0),other.values.disposed);
  }
  assert.notEqual(C.selected(d,latest,'other').values.disposed,M.record(d,latest.id,'hta:other-highway-traffic-act-charges').values.disposed);
});

test('camera comparison preserves missing years and shortened coverage',()=>{
  assert.deepEqual(C.cameraYear(cameras,'speed',2019),{count:null,months:0});
  assert.deepEqual(C.cameraYear(cameras,'speed',2025),{count:279595,months:11});
  assert.deepEqual(C.cameraYear(cameras,'redlight',2025),{count:44601,months:12});
  assert.deepEqual(C.cameraYear({speed:{months:[[2025,1,0,0]]}},'speed',2025),{count:0,months:1});
});

test('selected-year CSV preserves counts, fractional shares, units and provenance',()=>{
  const rows=C.exportRows(d,latest,'other',cameras);
  assert.equal(rows.length,2);assert.equal(rows[0].length,rows[1].length);
  const r=Object.fromEntries(rows[0].map((h,i)=>[h,rows[1][i]]));
  assert.equal(r.calendar_year,2025);assert.equal(r.unit,'charges');assert.equal(r.disposed,16489);
  assert.equal(r.hta_completed,r.speeding_completed+r.red_light_completed+r.other_hta_completed);
  assert.equal(r.pleas_share,r.pleas_count/r.disposed);
  assert.equal(r.source_url,latest.url);assert.match(r.source_row,/minus/);
  const missing=C.exportRows(d,latest,'nonexistent',cameras);
  assert.equal(missing[0].length,missing[1].length);
  assert.equal(missing[1][4],'unavailable');
});

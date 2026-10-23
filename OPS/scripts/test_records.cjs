const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {totals,filter,annual,csv,published}=require('../ops.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/records.json'),'utf8'));
test('unique respondents, proceedings and scheduled matters reconcile',()=>{
 assert.deepEqual(totals(data.records),{officers:23,findings:18,cases:20,scheduled:2});
 assert.equal(published(data.records).length,24);
 assert.equal(filter(data.records,{outcome:'no_finding'}).length,6);
 assert.equal(data.sources.length,4);
});
test('shared proceedings and separate Batson outcomes are preserved',()=>{
 const batson=filter(data.records,{search:'Kirk Batson'});
 assert.equal(batson.length,2);assert.equal(new Set(batson.map(r=>r.case_id)).size,2);
 assert.deepEqual(new Set(batson.map(r=>r.outcome)),new Set(['finding','no_finding']));
 assert.equal(new Set(data.records.filter(r=>r.case_id==='kraljevic-neglect').map(r=>r.officer_id)).size,3);
 const hart=filter(data.records,{search:'Andre Hart'});assert.equal(hart.length,1);assert.equal(hart[0].sources.length,2);
});
test('appeals use decision dates and never create extra cases',()=>{
 assert.equal(data.records.find(r=>r.id==='fournier').decision_date,'2025-06-06');
 assert.equal(data.records.find(r=>r.id==='svidran').decision_date,'2017-12-29');
 assert.equal(data.records.find(r=>r.id==='alden').decision_date,'2013-11-18');
 assert.equal(data.records.find(r=>r.id==='thomson').decision_date,'2018-05-24');
});
test('annual groups deduplicate same officer, exclude scheduled, leave gaps absent',()=>{
 const rows=annual([...data.records,data.records.find(r=>r.id==='hart')]);
 assert.equal(rows.find(r=>r.year==='2026').finding,4);
 assert.equal(rows.find(r=>r.year==='2018').no_finding,2);
 assert.equal(rows.find(r=>r.year==='2020'),undefined);
 assert.equal(rows.find(r=>r.year==='2027'),undefined);
});
test('combined filtering and quoted CSV preserve source evidence',()=>{
 const rows=filter(data.records,{search:'driving',year:'2025',outcome:'finding'});
 assert.deepEqual(new Set(rows.map(r=>r.id)),new Set(['jay','fortin']));
 const text=csv(rows);assert.ok(text.startsWith('\ufeff"officer"'));assert.ok(text.includes('OPAAC-ADJ25-007.pdf'));assert.equal(text.split('\r\n').length,3);
 assert.equal(filter(data.records,{search:'nothing matches'}).length,0);
});
test('each curated entry has unique identity, valid dates, explicit outcome and evidence',()=>{
 assert.equal(new Set(data.records.map(r=>r.id)).size,data.records.length);
 assert.equal(new Set(data.records.map(r=>r.officer_id+'|'+r.case_id)).size,data.records.length);
 for(const r of data.records){
  assert.ok(['finding','no_finding','scheduled'].includes(r.outcome));
  assert.ok(r.sources.length>0);assert.ok(r.officer&&r.appeal_status&&r.summary);
  if(r.outcome==='scheduled'){assert.equal(r.decision_date,'');assert.match(r.hearing_date,/^\d{4}-\d{2}-\d{2}$/);}
  else{assert.match(r.decision_date,/^\d{4}-\d{2}-\d{2}$/);assert.ok(r.decision_date<=data.checked_on);}
  for(const s of r.sources){assert.ok(s.pages);assert.match(s.url,/^https:\/\/(leca\.ca|www\.policearbitration\.gov\.on\.ca|www\.ottawapolice\.ca)\//);}
 }
});

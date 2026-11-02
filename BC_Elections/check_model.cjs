// Run: node BC_Elections/check_model.cjs. Tests the model extracted from the actual page.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
for(const year of [2024,2026]){
const html=fs.readFileSync(path.join(__dirname,year===2024?'BCelections-2024.html':'BCelections.html'),'utf8');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,year===2024?'data/results-2024.json':'data/results.json'),'utf8'));
for(const m of html.matchAll(/^<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gm)) new vm.Script(m[1]);
const ctx={P:data.parties,CODE_PC:'CP',CODE_LIB:null,CODE_NDP:'NDP',CODE_GRN:'GP',
  MERGE_CODES:['NDP','GP'],OTHER_CODES:Object.keys(data.parties).filter(c=>!['CP','NDP','GP'].includes(c)),OTHERS_COLOR:'#888',
  winnerOf:v=>({party:Object.keys(v).sort((a,b)=>v[b]-v[a])[0]})};
vm.createContext(ctx);vm.runInContext(html.match(/  function computeCoordRow\(r, pct\)\{[\s\S]*?\n  \}/)[0]+'\nthis.compute=computeCoordRow;',ctx);
const compute=ctx.compute,actualSeats={},thresholds=[];
for(const r of data.ridings){
  const official=r.candidates.find(c=>c.elected||c.leading).party;
  actualSeats[official]=(actualSeats[official]||0)+1;
  assert.equal(compute(r,0).hypoCode,official,r.name+' at zero transfer');
  assert.equal(compute(r,0).flipped,false);
  assert.equal(r.candidates.reduce((s,c)=>s+c.votes,0),r.valid);
  const lead=Math.max(r.votes.NDP,r.votes.GP),drop=Math.min(r.votes.NDP,r.votes.GP);
  for(let pct=0;pct<=100;pct++){
    const c=compute(r,pct/100);
    assert.ok(Math.abs(c.coordinated-(lead+pct/100*drop))<1e-7);
    const candidateVotes=r.candidates.filter(c=>!['NDP','GP'].includes(c.party)).map(c=>c.votes).concat(c.coordinated).sort((a,b)=>b-a);
    assert.equal(c.tied,Math.abs(candidateVotes[0]-candidateVotes[1])<1e-8);
    if(official==='GP')assert.equal(c.hypoCode,'GP','Green winner retained');
    if(c.pctNeeded!==null && c.pctNeeded<1){
      assert.equal(c.flipped,!c.tied && c.coordinated>r.votes.CP,r.name+' at '+pct);
    }
  }
  const c=compute(r,1);
  if(c.pctNeeded!==null && c.pctNeeded<1){
    assert.equal(compute(r,c.pctNeeded).tied,true,r.name+' at exact boundary');
    assert.equal(compute(r,c.pctNeeded).flipped,false);
    thresholds.push({riding:r.name,boundary:c.pctNeeded*100,firstWinningSliderPercent:Math.floor(c.pctNeeded*100+1e-8)+1});
  }
}
assert.deepEqual(actualSeats,year===2024?{CP:44,NDP:47,GP:2}:{CP:63,NDP:28,GP:2});
const fake={name:'Tie',votes:{CP:100,NDP:90,GP:20},candidates:[]};
assert.equal(compute(fake,.5).tied,true);assert.equal(compute(fake,.5).flipped,false);assert.equal(compute(fake,.51).hypoCode,'NDP');
const other={name:'Separate independents',votes:{CP:100,NDP:90,GP:0,IND:120},candidates:[{party:'IND',votes:60},{party:'IND',votes:60}]};
assert.equal(compute(other,1).hypoCode,'CP');
const scenarios=[];
for(const pct of [0,65,100]){
  const rows=data.ridings.map(r=>compute(r,pct/100)),seats={};rows.forEach(c=>{seats[c.hypoLabel]=(seats[c.hypoLabel]||0)+1});
  scenarios.push({transfer:pct,seats,flips:rows.filter(c=>c.flipped).map(c=>c.r.name)});
}
const report={scenarios,thresholds:thresholds.sort((a,b)=>a.boundary-b.boundary)};
fs.writeFileSync(path.join(__dirname,year===2024?'data/scenario-checks-2024.json':'data/scenario-checks.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({year,scenarios,reachable:thresholds.length},null,2));
console.log(`PASS ${year}: inline JS syntax; 93 zero-transfer leaders; 9,393 whole-percent cases; exact ties; Green-held seats; separate independents.`);
}

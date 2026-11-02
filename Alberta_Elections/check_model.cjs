// Run: node Alberta_Elections/check_model.cjs. Tests the actual page model function.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = __dirname;
const html = fs.readFileSync(path.join(root, 'ABelections.html'), 'utf8');
const data = JSON.parse(fs.readFileSync(path.join(root, 'data/results.json'), 'utf8'));
// Syntax-check every inline script without executing UI code.
for(const m of html.matchAll(/^<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gm)) new vm.Script(m[1]);
const model = html.match(/  function computeCoordRow\(r, pct\)\{[\s\S]*?\n  \}/)[0];
const ctx = {P:data.parties,CODE_PC:'UCP',CODE_LIB:'LIB',CODE_NDP:'NDP',CODE_GRN:'GPA',
  MERGE_CODES:['LIB','NDP','GPA'], OTHER_CODES:Object.keys(data.parties).filter(c=>!['UCP','LIB','NDP','GPA'].includes(c)),OTHERS_COLOR:'#888',
  winnerOf:v=>({party:Object.keys(v).sort((a,b)=>v[b]-v[a])[0]})};
vm.createContext(ctx);
vm.runInContext(model+'\nthis.compute=computeCoordRow;',ctx);
const compute = ctx.compute;
const winners = {};
for(const r of data.ridings){
  const actual = ctx.winnerOf(r.votes).party;
  assert.equal(compute(r,0).hypoCode,actual,`${r.name} at zero transfer`);
  assert.equal(compute(r,0).flipped,false);
  assert.equal(r.candidates.reduce((s,c)=>s+c.votes,0), r.valid);
  winners[actual] = (winners[actual]||0)+1;
  const selected = ['NDP','LIB','GPA'].map(c=>r.votes[c]).sort((a,b)=>b-a);
  for(let pct=0;pct<=100;pct++){
    const c=compute(r,pct/100);
    assert.ok(Math.abs(c.coordinated-(selected[0]+pct/100*(selected[1]+selected[2])))<1e-7);
    if(c.pctNeeded!==null && c.pctNeeded<1){
      assert.equal(c.coordinated>c.ucp, pct/100>c.pctNeeded);
    }
  }
}
assert.deepEqual(winners,{UCP:49,NDP:38});
const fake = {name:'Tie check',votes:{UCP:100,NDP:90,LIB:20,GPA:0,AP:0},candidates:[]};
assert.equal(compute(fake,.5).tied,true);
assert.equal(compute(fake,.5).flipped,false);
assert.equal(compute(fake,.51).hypoCode,'NDP');
const other = {name:'Other candidates stay separate',votes:{UCP:100,NDP:90,LIB:0,GPA:0,IND:120},candidates:[{party:'IND',votes:60},{party:'IND',votes:60}]};
assert.equal(compute(other,1).hypoCode,'UCP');
for(const pct of [0,65,100]){
  const rows=data.ridings.map(r=>compute(r,pct/100));
  const seats={}; rows.forEach(c=>{seats[c.hypoLabel]=(seats[c.hypoLabel]||0)+1});
  console.log(JSON.stringify({transfer:pct,seats,flips:rows.filter(c=>c.flipped).map(c=>c.r.name)}));
}
console.log('PASS: inline JS syntax; 87 zero-transfer winners; 8,787 scenario rows; strict ties; individual other candidates.');

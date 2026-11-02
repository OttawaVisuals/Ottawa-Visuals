/* Saved official reports; no remote data fetch is required to open the page. */
(()=>{'use strict';
const data=window.MEMBER_SPENDING,$=id=>document.getElementById(id);
window.setTheme=mode=>{if(!['light','dark','cb'].includes(mode))return;document.documentElement.dataset.theme=mode;try{localStorage.setItem('ov-theme',mode);localStorage.setItem('theme',mode);}catch(e){}};
$('theme-toggle').addEventListener('click',()=>window.setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark'));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD',maximumFractionDigits:0}).format(v);
const exact=v=>new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD',minimumFractionDigits:2}).format(v);
const km=v=>v==null?'Unavailable':Math.round(v).toLocaleString('en-CA')+' km';
const palette=['#3677aa','#9b6931','#648b73','#9277aa','#b45a47','#69979e','#7e8050'];
let period,rows=[],selected=null;
const read=()=>data.periods.filter(p=>p.level===$('level').value);
function populatePeriods(){ $('period').innerHTML=read().map(p=>`<option value="${p.id}">${esc(p.label)}</option>`).join('');changePeriod(); }
function changePeriod(){
 period=read().find(p=>p.id===$('period').value)||read()[0];
 $('province-control').hidden=period.level==='ontario';
 const provinces=[...new Set(period.rows.map(r=>r.province))].sort();
 $('province').innerHTML='<option value="">All provinces / territories</option>'+provinces.map(s=>`<option>${esc(s)}</option>`).join('');
 $('metric').innerHTML='<option value="total">Total spending</option>'+period.categories.map(([k,l])=>`<option value="${k}">${esc(l)}</option>`).join('');
 const travels=period.level==='federal'?[['travel','All reported travel']]:[['commute_travel','Residence ↔ Queen’s Park'],['travel','Separately reported travel'],['accommodation','Toronto accommodation']];
 $('travel-metric').innerHTML=travels.map(([k,l])=>`<option value="${k}">${esc(l)}</option>`).join('');
 $('period-note').textContent=period.level==='federal'?'Single quarter · employee salaries, travel, hospitality and contracts. Records can include former MPs and vacancies.':'Full fiscal year · office, support staff, travel and accommodation. Former-member closing costs are retained.';
 $('category-note').textContent=period.level==='federal'?'Staff salaries are employees’ pay. Contracts includes leases, advertising, services and office costs.':'Hospitality and some travel are bundled in office operations. Toronto accommodation includes the overage once.';
 $('official-source').href=period.source;selected=null;filter();
}
const value=(r,key)=>key==='total'?r.total:(r.categories[key]??r[key]??0);
function filter(){
 const q=$('search').value.trim().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase(),prov=$('province').value;
 rows=period.rows.filter(r=>(!prov||r.province===prov)&&(!q||`${r.name} ${r.riding}`.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().includes(q)));
 if(!rows.some(r=>r.id===selected))selected=[...rows].sort((a,b)=>b.total-a.total)[0]?.id;
 $('count').textContent=rows.length.toLocaleString('en-CA');$('total').textContent=money(rows.reduce((s,r)=>s+r.total,0));
 const totals=rows.map(r=>r.total).sort((a,b)=>a-b),m=Math.floor(totals.length/2);
 $('median').textContent=totals.length?money(totals.length%2?totals[m]:(totals[m-1]+totals[m])/2):'—';
 $('member').innerHTML=rows.length?[...rows].sort((a,b)=>a.name.localeCompare(b.name)).map(r=>`<option value="${r.id}">${esc(r.name)} · ${esc(r.riding)}</option>`).join(''):'<option>No matching records</option>';
 $('member').disabled=!rows.length;render();
}
function render(){ranking();detail();scatter();table();}
function ranking(){
 const key=$('metric').value,ordered=[...rows].sort((a,b)=>value(b,key)-value(a,key)||a.name.localeCompare(b.name));
 const limit=$('limit').value==='all'?ordered.length:Number($('limit').value),shown=ordered.slice(0,limit),max=Math.max(1,...ordered.map(r=>Math.abs(value(r,key))));
 $('rank-title').textContent=`${key==='total'?'Total spending':period.categories.find(c=>c[0]===key)?.[1]} · ${shown.length} of ${rows.length} records`;
 $('ranking').innerHTML=shown.length?shown.map(r=>{
 const hasCredit=Object.values(r.categories).some(v=>v<0),v=value(r,key);
 const segments=key==='total'&&!hasCredit?period.categories.map(([k,l],i)=>`<i style="width:${Math.max(0,r.categories[k])/max*100}%;background:${palette[i]}" title="${esc(l)}: ${exact(r.categories[k])}"></i>`).join(''):`<i style="width:${Math.abs(v)/max*100}%;background:${v<0?'#b45a47':'var(--accent-2)'}"></i>`;
 return `<button class="rank-row" data-id="${r.id}" aria-pressed="${r.id===selected}" aria-label="${esc(r.name)}, ${esc(r.riding)}, ${money(v)}"><span class="rank-info"><span class="rank-name">${esc(r.name)}</span><span class="rank-value">${money(v)}</span></span><span class="rank-riding">${esc(r.riding)}</span><span class="rank-bar">${segments}</span></button>`;
 }).join(''):'<p class="empty">No matching records. Clear the search or reset the filters.</p>';
 $('ranking').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>choose(b.dataset.id)));
 $('legend').innerHTML=key==='total'?period.categories.map(([,l],i)=>`<span><i style="background:${palette[i]}"></i>${esc(l)}</span>`).join(''):'';
 $('ranking-note').textContent='Amounts on charts are rounded to dollars; exact source amounts are in the table and downloads. Rows with credits use a single net-amount bar.';
}
function choose(id){selected=id;render();}
function detail(){
 const r=rows.find(r=>r.id===selected);$('member').value=selected||'';
 if(!r){$('member-detail').innerHTML='<p class="empty">No matching member.</p>';return;}
 const max=Math.max(1,...Object.values(r.categories).map(Math.abs));
 $('member-detail').innerHTML=`<h3>${esc(r.name)}</h3><p>${esc(r.riding)}</p><p class="small">${esc([r.party,r.status].filter(Boolean).join(' · '))}</p><p class="member-total">${money(r.total)}</p><p class="small">${esc(period.label)} · ${km(r.distance_km)} to ${period.level==='federal'?'Parliament Hill':'Queen’s Park'}</p>`+period.categories.map(([k,l],i)=>`<div class="detail-row"><span>${esc(l)}</span><strong>${exact(r.categories[k])}</strong><span class="detail-track"><i style="width:${Math.abs(r.categories[k])/max*100}%;background:${palette[i]}"></i></span></div>`).join('')+(r.rounding?`<p class="small">Published total differs from category sum by ${exact(r.rounding)} due to source rounding.</p>`:'')+`<p class="small"><a href="${esc(r.source)}${r.office_page?'#page='+r.office_page:''}">Official record ↗</a>${r.office_page?' · Office PDF p. '+r.office_page+(r.travel_page?' · Travel PDF p. '+r.travel_page:''):''}</p>`;
}
function nice(n){if(n<=0)return 1;const magnitude=10**Math.floor(Math.log10(n));return Math.ceil(n/magnitude)*magnitude;}
function scatter(){
 const key=$('travel-metric').value,fed=period.level==='federal',capital=fed?'Parliament Hill':'Queen’s Park';
 $('travel-definition').textContent=fed?'Federal travel includes transport, accommodation and meals for eligible parliamentary travel—not only journeys to Ottawa.':key==='commute_travel'?'Ontario: travel between residence and Queen’s Park, including committee travel. This is the closest available measure of travel to the legislature.':key==='travel'?'Ontario: residence–Queen’s Park, Assembly, family and separately reported within-riding travel. Some northern and staff travel remains within office operations.':'Ontario: Toronto accommodation allowance plus the accommodation overage charged to the office budget.';
 const dots=rows.filter(r=>r.distance_km!=null&&r.status!=='Vacant'&&r.status!=='Former member / closing costs');
 $('coverage').textContent=`${dots.length} of ${rows.length} filtered records plotted. ${period.distance_note}`;
 if(!dots.length){$('scatter').innerHTML='<p class="empty">No distance comparison available for this selection.</p>';$('point-detail').textContent='Use another period or clear the filters.';return;}
 const W=Math.max(280,$('scatter').clientWidth),H=W<500?330:400,L=W<500?56:70,R=17,T=20,B=66,pw=W-L-R,ph=H-T-B;
 const xmax=nice(Math.max(...dots.map(r=>r.distance_km))*1.04),ymax=nice(Math.max(...dots.map(r=>value(r,key)))*1.06),ymin=Math.min(0,...dots.map(r=>value(r,key))),x=v=>L+v/xmax*pw,y=v=>T+(ymax-v)/(ymax-ymin)*ph;
 let svg=`<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="${esc($('travel-metric').selectedOptions[0].textContent)} versus riding distance to ${capital}">`;
 for(let i=0;i<=4;i++){const xx=L+pw*i/4,yy=T+ph*i/4;svg+=`<line class="grid" x1="${xx}" x2="${xx}" y1="${T}" y2="${T+ph}"/><text x="${xx}" y="${H-B+22}" text-anchor="middle">${Math.round(xmax*i/4).toLocaleString('en-CA')}</text><line class="grid" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"/><text x="${L-9}" y="${yy+4}" text-anchor="end">${money((ymax-(ymax-ymin)*i/4)/1000)}k</text>`;}
 svg+=`<text x="${L+pw/2}" y="${H-12}" text-anchor="middle">Distance to ${capital} · km one way</text><text x="${L}" y="11">Reported spending · CAD</text>`;
 for(const r of [...dots].sort((a,b)=>(a.id===selected)-(b.id===selected))){const label=`${r.name} · ${r.riding} · ${km(r.distance_km)} · ${exact(value(r,key))}`;svg+=`<circle class="dot${r.id===selected?' selected':''}" data-id="${r.id}" cx="${x(r.distance_km)}" cy="${y(value(r,key))}" r="${r.id===selected?7:5}" tabindex="0" role="button" aria-label="${esc(label)}"><title>${esc(label)}</title></circle>`;}
 $('scatter').innerHTML=svg+'</svg>';
 const inspect=id=>{const r=dots.find(r=>r.id===id);$('point-detail').textContent=`${r.name} · ${r.riding} · ${km(r.distance_km)} · ${exact(value(r,key))} · ${period.label}`;};
 $('scatter').querySelectorAll('.dot').forEach(c=>{c.addEventListener('mouseenter',()=>inspect(c.dataset.id));c.addEventListener('focus',()=>inspect(c.dataset.id));c.addEventListener('click',()=>{choose(c.dataset.id);inspect(c.dataset.id);});c.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(c.dataset.id);inspect(c.dataset.id);}});});
 if(dots.some(r=>r.id===selected))inspect(selected);else $('point-detail').textContent='Select a dot for its member, riding, distance and spending.';
}
function table(){
 $('table-caption').textContent=`${period.label} · ${rows.length} filtered records · CAD`;
 $('exact').querySelector('thead').innerHTML='<tr>'+['Member','Riding','Status',...period.categories.map(c=>c[1]),'Total','Distance'].map(l=>`<th scope="col">${esc(l)}</th>`).join('')+'</tr>';
 $('exact').querySelector('tbody').innerHTML=[...rows].sort((a,b)=>a.name.localeCompare(b.name)).map(r=>'<tr>'+[esc(r.name),esc(r.riding),esc(r.status),...period.categories.map(([k])=>exact(r.categories[k])),exact(r.total),km(r.distance_km)].map(t=>`<td>${t}</td>`).join('')+'</tr>').join('');
}
for(const id of ['level','period','province','metric','limit','travel-metric','member'])$(id).addEventListener('change',()=>{if(id==='level')populatePeriods();else if(id==='period')changePeriod();else if(id==='province')filter();else if(id==='member')choose($('member').value);else render();});
 $('search').addEventListener('input',filter);$('reset').addEventListener('click',()=>{$('search').value='';$('level').value='federal';$('limit').value='10';populatePeriods();});
 let timer;window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(scatter,100);});
 const query=new URLSearchParams(location.search);if(['federal','ontario'].includes(query.get('level')))$('level').value=query.get('level');populatePeriods();
})();

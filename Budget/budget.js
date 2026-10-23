'use strict';
window.setTheme = mode => { document.documentElement.dataset.theme = mode; };
(() => {
  const $ = id => document.getElementById(id);
  const allowed = { view: ['operating', 'capital', 'revenue'], year: ['2025', '2026'], funding: ['all', 'tax', 'rate'], unit: ['dollars', 'share'] };
  const params = new URLSearchParams(location.search);
  const state = Object.fromEntries(Object.entries(allowed).map(([key, options]) => [key, options.includes(params.get(key)) ? params.get(key) : options[0]]));
  state.year = allowed.year.includes(params.get('year')) ? params.get('year') : '2026';
  state.compare = params.get('compare') === '1';
  let data;
  const price=(value,year)=>window.OVBudgetPrices?.convert(value,year)??value;
  const basis=()=>window.OVBudgetPrices?.basis||'nominal dollars';
  const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = n => n.toLocaleString('en-CA');
  const million = n => '$' + (n / 1000).toLocaleString('en-CA', {minimumFractionDigits:1, maximumFractionDigits:1}) + 'M';
  const billion = n => '$' + (n / 1e6).toFixed(2) + 'B';
  const percent = n => n.toFixed(1) + '%';
  const change = (a,b) => a === 0 ? (b === 0 ? '0.0%' : 'No base') : (b-a>=0?'+':'') + percent((b-a)/a*100);
  const titles = {operating:'Operating services',capital:'New capital approvals',revenue:'Operating funding'};
  const explanations = {
    operating:'Spending on services and operating costs, after internal recoveries but before program revenue. Expand a service group for detail. These amounts are not the property-tax levy.',
    capital:'New permission to spend on projects, grouped by the approving committee. Work can span multiple years. Transit-related projects also appear under Public Works and Finance; these are not service-wide totals.',
    revenue:'How operating costs are funded: property taxes, fees, government transfers and other sources. Capital financing is separate. These are approved revenues, not collections to date.'
  };
  function selectedRows() { return data[state.view].filter(r => state.view !== 'operating' || state.funding === 'all' || r.funding === state.funding).map(r=>({...r,budget_2025:price(r.budget_2025,2025),budget_2026:price(r.budget_2026,2026),children:r.children?.map(c=>({...c,budget_2025:price(c.budget_2025,2025),budget_2026:price(c.budget_2026,2026)}))})); }
  function totalFor(year, rows) {
    if(state.view === 'operating' && state.funding !== 'all') return price(state.funding === 'tax' ? ({2025:4404824,2026:4686328})[year] : ({2025:499172,2026:532102})[year],year);
    return price(data.totals[state.view === 'capital' ? 'capital' : 'operating'][year],year);
  }
  function render() {
    if(!data) return;
    $('operating-total').textContent = billion(price(data.totals.operating['2026'],2026));
    $('capital-total').textContent = billion(price(data.totals.capital['2026'],2026));
    $('tax-total').textContent = billion(price(data.revenue.filter(r=>['Property Taxes','Payment-in-lieu of taxation'].includes(r.name)).reduce((n,r)=>n+r.budget_2026,0),2026));
    ['year','funding','unit'].forEach(key => $(key).value = state[key]);
    document.querySelectorAll('[data-view]').forEach(b => b.setAttribute('aria-pressed',String(b.dataset.view === state.view)));
    $('funding-label').hidden = state.view !== 'operating';
    $('compare').disabled = state.year === '2025';
    $('compare').checked = state.compare && state.year === '2026';
    $('view-explanation').textContent = explanations[state.view]+' Amounts in '+basis()+'.'+(window.OVBudgetPrices?.real?' 2026 adjustment is provisional.':'');
    const rows = selectedRows().sort((a,b) => b['budget_'+state.year]-a['budget_'+state.year]);
    const total = totalFor(state.year, rows), priorTotal = totalFor('2025', rows);
    const compare = state.compare && state.year === '2026';
    const value = (n,year) => state.unit === 'share' ? n/totalFor(year,rows)*100 : n;
    const max = Math.max(...rows.flatMap(r => [value(r['budget_'+state.year],state.year), ...(compare ? [value(r.budget_2025,'2025')] : [])]));
    const displayed = (n,year) => state.unit === 'share' ? percent(value(n,year)) : million(n);
    $('chart-total').textContent = `${state.year} ${titles[state.view].toLowerCase()} · ${billion(total)}${state.view==='operating'&&state.funding!=='all'?' · selected programs':''} · ${basis()}`;
    $('legend').textContent = compare ? `Blue: ${state.year} · Grey: 2025${state.unit==='share'?' · each year’s own total':''}` : `${state.unit==='share'?'Share of':'Amounts within'} the selected ${state.year} total`;
    $('chart-help').textContent = state.view !== 'revenue' ? 'Open a group marked + to see what it includes. Exact figures and source pages are below.' : 'Bars are sorted by the selected year. Exact figures and document pages are below.';
    $('chart').innerHTML = rows.map(r => {
      const n = r['budget_'+state.year];
      const expandable = r.children?.length > 1;
      const bar = `<div class="row-main"><span class="row-name">${escape(r.name)}</span><div class="bar-lanes" aria-hidden="true"><div class="lane"><div class="bar" style="width:${value(n,state.year)/max*100}%"></div></div>${compare?`<div class="lane prior"><div class="bar" style="width:${value(r.budget_2025,'2025')/max*100}%"></div></div>`:''}</div><span class="row-value">${displayed(n,state.year)}${compare?`<small>2025: ${displayed(r.budget_2025,'2025')}</small>`:''}</span></div>`;
      const source = `<p class="source-note"><a href="${data.source_url}#page=${r.pdf_page}">Adopted book · PDF p. ${r.pdf_page} ↗</a></p>`;
      let children = '';
      if(expandable) children = '<div class="children">'+r.children.map(c=>`<div class="child"><span>${escape(c.name)}</span><span>${million(c['budget_'+state.year])}</span></div>`).join('')+source+'</div>';
      return expandable ? `<details class="budget-row"><summary>${bar}</summary>${children}</details>` : `<div class="budget-row">${bar}</div>`;
    }).join('');
    $('rounding').textContent = state.view === 'capital' ? 'New authority, not annual cash spending. Rounded committee rows differ from the 2026 printed total by $0.001M.' : state.view === 'operating' ? 'Includes tax- and rate-supported services when “All services” is selected. Small differences between row sums and printed totals reflect source rounding.' : 'Revenue amounts are shown as positive funding sources. Own funds are internal funding. Rounded categories may not sum exactly to the printed total.';
    $('table-caption').textContent = titles[state.view]+' · amounts in thousands of '+basis()+'. Changes compare budgets, not actual spending.'+(window.OVBudgetPrices?.real?' 2026 CPI is provisional.':'');
    const download=document.querySelector('#money .download');download.href=window.OVBudgetPrices?.real?'data/budget-inflation-adjusted.csv':'data/budget.csv';download.textContent=window.OVBudgetPrices?.real?'Adjusted CSV ↓':'Download CSV ↓';
    $('data-rows').innerHTML = rows.map(r=>`<tr><th scope="row">${escape(r.name)}</th><td>${number(r.budget_2025)}</td><td>${number(r.budget_2026)}</td><td>${change(r.budget_2025,r.budget_2026)}</td><td><a href="${data.source_url}#page=${r.pdf_page}">PDF p. ${r.pdf_page} ↗</a></td></tr>`).join('');
    const query = new URLSearchParams(location.search);
    Object.entries(state).forEach(([key,val]) => { if(key !== 'compare') query.set(key,val); else if(val) query.set(key,'1'); else query.delete(key); });
    if(location.protocol!=='file:') history.replaceState(null,'',`${location.pathname}?${query}${location.hash}`);
  }
  function renderProject(project) {
    const list = items => items.map(r=>`<div class="mini-row"><span>${escape(r.name)}<small>${escape(r.note)}</small></span><strong>$${r.amount.toFixed(1)}M</strong></div>`).join('');
    $('project-scope').innerHTML = list(project.scope);
    $('project-funding').innerHTML = list(project.financing);
    ['progress','finance','approval'].forEach(key => $(key+'-source').href = project.sources[key].url);
    document.querySelectorAll('#source-list .project-source').forEach(el=>el.remove());
    $('source-list').innerHTML += Object.values(project.sources).map(s=>`<li class="project-source"><a href="${escape(s.url)}">${escape(s.title)} ↗</a> · ${escape(s.locator)}</li>`).join('');
  }
  async function load() {
    $('error').hidden = true;
    try {
      let budget,project;
      if(location.protocol==='file:' && window.OTTAWA_BUDGET_DATA) {
        ({budget,lansdowne:project}=window.OTTAWA_BUDGET_DATA);
      } else {
        const responses = await Promise.all([fetch('data/budget.json'),fetch('data/lansdowne.json')]);
        if(responses.some(r=>!r.ok)) throw new Error('Data request failed');
        [budget,project] = await Promise.all(responses.map(r=>r.json()));
      }
      data = budget;
      $('operating-total').textContent = billion(data.totals.operating['2026']);
      $('capital-total').textContent = billion(data.totals.capital['2026']);
      $('tax-total').textContent = billion(data.revenue.filter(r=>['Property Taxes','Payment-in-lieu of taxation'].includes(r.name)).reduce((n,r)=>n+r.budget_2026,0));
      render(); renderProject(project);
    } catch(e) { $('error').hidden = false; $('view-explanation').textContent = 'Data could not be loaded. The source files remain available below.'; }
  }
  document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{state.view=b.dataset.view;render();}));
  ['year','funding','unit'].forEach(key=>$(key).addEventListener('change',e=>{state[key]=e.target.value;render();}));
  $('compare').addEventListener('change',e=>{state.compare=e.target.checked;render();});
  $('retry').addEventListener('click',load);
  window.addEventListener('budget-prices-change',render);
  load();
})();

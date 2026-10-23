'use strict';
(() => {
  const data=window.OTTAWA_BUDGET_DATA?.inflation;
  const control=document.getElementById('price-basis');
  let adjusted=new URLSearchParams(location.search).get('prices')==='real' && !!data;
  window.OVBudgetPrices={
    convert:(amount,year)=>adjusted?amount*data.factors[String(year)]:amount,
    get real(){return adjusted;},
    get basis(){return adjusted?'2025 dollars':'nominal dollars';}
  };
  function apply(){
    control.value=adjusted?'real':'nominal';
    document.getElementById('inflation-note').innerHTML=data?`<strong>${adjusted?'Showing 2025 dollars. 2026 is provisional.':'Showing nominal dollars.'}</strong> ${adjusted?'2023–2025 use annual Ottawa all-items CPI. 2026 uses the January–September CPI average; full-year CPI is not yet available.':'Choose inflation-adjusted to compare purchasing power using Ottawa CPI.'} <a href="${data.annual_source}">Annual CPI ↗</a> · <a href="${data.monthly_source}">Monthly CPI ↗</a>`:'CPI data unavailable; amounts are shown in nominal dollars.';
    if(!data)control.disabled=true;
    const q=new URLSearchParams(location.search);q.set('prices',adjusted?'real':'nominal');
    if(location.protocol!=='file:')history.replaceState(null,'',location.pathname+'?'+q+location.hash);
    window.dispatchEvent(new Event('budget-prices-change'));
  }
  control.addEventListener('change',()=>{adjusted=control.value==='real'&&!!data;apply();});
  apply();
})();

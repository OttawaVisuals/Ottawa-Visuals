/* Local static charts; preserve other topics' query parameters and anchor. */
(()=>{
  const section=document.getElementById('market-safety');
  if(!section)return;
  const select=section.querySelector('#market-metric');
  const charts=[...section.querySelectorAll('[data-market-metric]')];
  const valid=new Set(charts.map(c=>c.dataset.marketMetric));
  function render(value){
    select.value=valid.has(value)?value:'assaults';
    charts.forEach(c=>c.hidden=c.dataset.marketMetric!==select.value);
    const scroller=charts.find(c=>!c.hidden).querySelector('.chart-scroll');
    scroller.scrollLeft=scroller.scrollWidth-scroller.clientWidth;
  }
  function restore(){render(new URL(location.href).searchParams.get('marketmetric'));}
  restore();section.querySelector('.market-controls').hidden=false;
  select.addEventListener('change',()=>{
    render(select.value);
    const url=new URL(location.href);
    if(select.value==='assaults')url.searchParams.delete('marketmetric');
    else url.searchParams.set('marketmetric',select.value);
    history.replaceState(null,'',url);
  });
  window.addEventListener('popstate',restore);
})();

'use strict';
(() => {
  const root = document.getElementById('bus-reliability');
  const data = JSON.parse(document.getElementById('bus-series-data').textContent);
  const select = document.getElementById('bus-metric');
  const params = new URLSearchParams(location.search);
  select.value = data.metrics.some(m => m.metric === params.get('busmetric')) ? params.get('busmetric') : data.metrics[0].metric;
  let mode = params.get('busperiod') === 'monthly' ? 'monthly' : 'annual';
  function render() {
    const metric = data.metrics.find(m => m.metric === select.value);
    root.querySelectorAll('.bus-chart').forEach(el => { el.hidden = el.dataset.busMetric !== select.value || el.dataset.busPeriod !== mode; });
    root.querySelectorAll('[data-bus-mode]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.busMode === mode)));
    const records = data.records.filter(r => r.metric === select.value && r.period_type === (mode === 'monthly' ? 'month' : 'year')).sort((a,b) => a.period.localeCompare(b.period));
    const first = records[0], last = records[records.length-1];
    const delta = last.value - first.value;
    document.getElementById('bus-summary').textContent = mode === 'monthly'
      ? `${metric.label}: latest month in this archive ${last.period}, ${last.value}%. May 2026 scorecard reference: ${data.targets[select.value].value}%. Gaps are not connected.`
      : `${metric.label}: ${first.value}% (${first.period}) → ${last.value}% (${last.period}); ${Math.abs(delta).toFixed(1)} percentage points ${delta < 0 ? 'lower' : delta > 0 ? 'higher' : 'change'}.`;
    document.getElementById('bus-definition').textContent = metric.definition;
    if (location.protocol !== 'file:') {
      const query = new URLSearchParams(location.search);
      if (select.value !== data.metrics[0].metric) query.set('busmetric', select.value); else query.delete('busmetric');
      if (mode === 'monthly') query.set('busperiod',mode); else query.delete('busperiod');
      const search = query.toString();
      history.replaceState(null,'',location.pathname+(search ? '?' + search : '')+location.hash);
    }
  }
  select.addEventListener('change',render);
  root.querySelectorAll('[data-bus-mode]').forEach(el => el.addEventListener('click',()=>{mode=el.dataset.busMode;render();}));
  root.querySelector('.bus-controls').hidden=false;
  render();
})();

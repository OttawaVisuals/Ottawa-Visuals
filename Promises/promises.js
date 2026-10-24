'use strict';
(() => {
  const controls = document.querySelector('.chart-controls');
  const buttons = [...document.querySelectorAll('[data-range]')];
  const measures = [...document.querySelectorAll('button[data-measure]')];
  const inflation = document.getElementById('show-inflation');
  const params = new URLSearchParams(location.search);
  let range = params.get('range') === 'term' ? 'term' : 'all';
  let measure = params.get('measure') === 'cumulative' ? 'cumulative' : 'annual';
  inflation.checked = params.get('inflation') !== '0';
  function render() {
    const cumulative = measure === 'cumulative';
    ['all', 'term'].forEach(scope => {
      document.getElementById('chart-' + scope).hidden = range !== scope || cumulative;
      document.getElementById('chart-' + scope + '-cumulative').hidden = range !== scope || !cumulative;
    });
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.range === range)));
    measures.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.measure === measure)));
    document.querySelectorAll('[data-summary]').forEach(el => { el.hidden = !cumulative || el.dataset.summary !== range; });
    document.querySelectorAll('.annual-note,.reference-legend').forEach(el => { el.hidden = cumulative; });
    document.querySelectorAll('.cumulative-note').forEach(el => { el.hidden = !cumulative; });
    document.querySelectorAll('.inflation-series,.inflation-legend,.inflation-summary').forEach(el => {
      el.style.display = inflation.checked ? '' : 'none';
    });
    document.querySelectorAll('.tax-chart desc').forEach(el => {
      const total = el.closest('svg').dataset.measure === 'cumulative';
      el.textContent = `Vertical bars show ${total ? 'compounded' : 'annual'} municipal property-tax increases. ${inflation.checked ? 'The line shows Ottawa CPI inflation; the dashed segment and hollow 2026 point use a provisional January–September endpoint. ' : 'Inflation is hidden. '}${total ? 'CPI growth is measured directly from the baseline annual index.' : 'Horizontal references at 2 and 2.5 percent apply to 2023–2026.'} Exact values and baselines are in the tables below.`;
    });
    if (location.protocol !== 'file:') {
      const query = new URLSearchParams(location.search);
      if (range === 'term') query.set('range', range); else query.delete('range');
      if (cumulative) query.set('measure', measure); else query.delete('measure');
      if (!inflation.checked) query.set('inflation', '0'); else query.delete('inflation');
      const search = query.toString();
      history.replaceState(null, '', location.pathname + (search ? '?' + search : '') + location.hash);
    }
  }
  buttons.forEach(b => b.addEventListener('click', () => { range = b.dataset.range; render(); }));
  measures.forEach(b => b.addEventListener('click', () => { measure = b.dataset.measure; render(); }));
  inflation.addEventListener('change', render);
  controls.hidden = false;
  render();
})();

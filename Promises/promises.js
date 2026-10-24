'use strict';
(() => {
  const controls = document.querySelector('.chart-controls');
  const buttons = [...document.querySelectorAll('[data-range]')];
  const inflation = document.getElementById('show-inflation');
  const params = new URLSearchParams(location.search);
  let range = params.get('range') === 'term' ? 'term' : 'all';
  inflation.checked = params.get('inflation') !== '0';
  function render() {
    document.getElementById('chart-all').hidden = range !== 'all';
    document.getElementById('chart-term').hidden = range !== 'term';
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.range === range)));
    document.querySelectorAll('.inflation-series,.inflation-legend').forEach(el => {
      el.style.display = inflation.checked ? '' : 'none';
    });
    document.querySelectorAll('.tax-chart desc').forEach(el => {
      el.textContent = `Vertical bars show municipal property-tax increases. ${inflation.checked ? 'The line shows Ottawa CPI inflation; the dashed segment and hollow 2026 point are provisional January–September data. ' : 'Inflation is hidden. '}Horizontal references at 2 and 2.5 percent apply to 2023–2026. Exact values are in the table below.`;
    });
    if (location.protocol !== 'file:') {
      const query = new URLSearchParams(location.search);
      if (range === 'term') query.set('range', range); else query.delete('range');
      if (!inflation.checked) query.set('inflation', '0'); else query.delete('inflation');
      const search = query.toString();
      history.replaceState(null, '', location.pathname + (search ? '?' + search : '') + location.hash);
    }
  }
  buttons.forEach(b => b.addEventListener('click', () => { range = b.dataset.range; render(); }));
  inflation.addEventListener('change', render);
  controls.hidden = false;
  render();
})();

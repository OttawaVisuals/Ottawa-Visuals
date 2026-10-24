'use strict';
(() => {
  const root = document.getElementById('housing');
  const historyToggle = document.getElementById('housing-history');
  const params = new URLSearchParams(location.search);
  let mode = params.get('housingview') === 'cumulative' ? 'cumulative' : 'annual';
  historyToggle.checked = params.get('housinghistory') === '1';
  function render() {
    const cumulative = mode === 'cumulative';
    document.getElementById('housing-recent').hidden = cumulative || historyToggle.checked;
    document.getElementById('housing-history').disabled = cumulative;
    document.getElementById('housing-history-chart').hidden = cumulative || !historyToggle.checked;
    document.getElementById('housing-cumulative').hidden = !cumulative;
    root.querySelector('.legend .historical').parentElement.hidden = cumulative;
    root.querySelectorAll('[data-housing-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.housingMode === mode)));
    document.getElementById('housing-chart-note').textContent = cumulative
      ? 'Cumulative completions start in January 2023 by analytical convention. The dashed line is an illustrative 10,000/year pace, prorated to August for 2026; it is not a promised interim milestone. *2026 ends in August. Scroll sideways on small screens.'
      : '*2026 is January–August only; compare it with the same months in prior years, not full-year bars. The 10,000/year reference is 100,000 ÷ 10, not a promised annual milestone. Scroll sideways on small screens.';
    if (location.protocol !== 'file:') {
      const query = new URLSearchParams(location.search);
      if (cumulative) query.set('housingview',mode); else query.delete('housingview');
      if (historyToggle.checked) query.set('housinghistory','1'); else query.delete('housinghistory');
      const search = query.toString();
      history.replaceState(null,'',location.pathname+(search ? '?' + search : '')+location.hash);
    }
  }
  root.querySelectorAll('[data-housing-mode]').forEach(b => b.addEventListener('click',()=>{ mode=b.dataset.housingMode;render(); }));
  historyToggle.addEventListener('change',render);
  root.querySelector('.housing-controls').hidden=false;
  render();
})();

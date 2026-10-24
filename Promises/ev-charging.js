'use strict';
(() => {
  const root = document.getElementById('ev-charging');
  if (!root) return;
  const selector = root.querySelector('#ev-scope');
  selector.value = new URLSearchParams(location.search).get('evscope') === 'all' ? 'all' : 'hydro';
  function render() {
    const scope = selector.value;
    root.querySelectorAll('[data-ev-group]').forEach(node => { node.hidden = node.dataset.evGroup !== scope; });
    root.querySelectorAll('[data-ev-hydro]').forEach(row => { row.hidden = scope === 'hydro' && row.dataset.evHydro !== 'true'; });
    if (location.protocol !== 'file:') {
      const params = new URLSearchParams(location.search);
      if (scope === 'all') params.set('evscope', 'all'); else params.delete('evscope');
      const query = params.toString();
      history.replaceState(null, '', location.pathname + (query ? '?' + query : '') + location.hash);
    }
  }
  root.querySelector('.ev-controls').hidden = false;
  selector.addEventListener('change', render);
  render();
})();

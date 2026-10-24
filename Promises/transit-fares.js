'use strict';
(() => {
  const root = document.getElementById('transit-fares');
  const records = JSON.parse(document.getElementById('fare-series-data').textContent).records;
  const product = document.getElementById('fare-product');
  const inflation = document.getElementById('fare-inflation');
  const params = new URLSearchParams(location.search);
  product.value = ['card','cash','monthly'].includes(params.get('fare')) ? params.get('fare') : 'card';
  let mode = ['price','annual','cumulative'].includes(params.get('fareview')) ? params.get('fareview') : 'price';
  inflation.checked = params.get('farecpi') !== '0';
  function render() {
    root.querySelectorAll('.fare-chart').forEach(el => { el.hidden = el.dataset.product !== product.value || el.dataset.fareView !== mode; });
    root.querySelectorAll('[data-fare-mode]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.fareMode === mode)));
    const showCPI = mode !== 'price' && inflation.checked;
    inflation.disabled = mode === 'price';
    root.querySelector('.fare-baseline-legend').hidden = mode !== 'price';
    root.querySelector('.fare-inflation-legend').hidden = !showCPI;
    root.querySelectorAll('.fare-inflation').forEach(el => { el.style.display = showCPI ? '' : 'none'; });
    root.querySelectorAll('.fare-svg desc').forEach(el => {
      el.textContent = `Bars show ${mode === 'price' ? 'adult fare prices in Canadian dollars' : mode === 'annual' ? 'annual fare increases' : 'cumulative fare increases since the late-2022 schedule'}. ${showCPI ? 'The line shows Ottawa CPI; the dashed segment and hollow 2026 point use partial January–September data.' : 'No inflation line is shown.'} Exact values and formulas are in the fare tables.`;
    });
    const series = records.filter(r => r.product === product.value);
    const first = series[0], last = series[series.length-1];
    document.getElementById('fare-summary').textContent = `${last.product_label}: $${first.price_cad.toFixed(2)} in late 2022 and 2023 → $${last.price_cad.toFixed(2)} in 2026. Total increase: ${last.cumulative_fare_pct.toFixed(2)}%.`;
    document.getElementById('fare-view-note').textContent = mode === 'price'
      ? 'Prices in Canadian dollars. The 2022 bar is the late-year fare schedule, not an annual average. Card and cash fares are separate products. Use the percentage views to compare with inflation.'
      : mode === 'annual'
        ? 'Annual percentage changes are calculated from each product’s published price, including rounding. The 2023 fare freeze appears as 0%. CPI uses annual-average changes through 2025 and matched Jan–Sep changes for 2026.'
        : 'Cumulative increases use the late-2022 fare schedule as the baseline. CPI uses the 2022 annual index as baseline; the 2026 endpoint is the Jan–Sep average. Fare schedules and CPI have different timing; this is not a rider-spending estimate.';
    if (location.protocol !== 'file:') {
      const query = new URLSearchParams(location.search);
      if (product.value !== 'card') query.set('fare', product.value); else query.delete('fare');
      if (mode !== 'price') query.set('fareview', mode); else query.delete('fareview');
      if (!inflation.checked) query.set('farecpi','0'); else query.delete('farecpi');
      const search = query.toString();
      history.replaceState(null, '', location.pathname + (search ? '?' + search : '') + location.hash);
    }
  }
  root.querySelectorAll('[data-fare-mode]').forEach(el => el.addEventListener('click', () => { mode = el.dataset.fareMode; render(); }));
  product.addEventListener('change', render);
  inflation.addEventListener('change', render);
  root.querySelector('.fare-controls').hidden = false;
  render();
})();

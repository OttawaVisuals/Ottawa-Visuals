/* Keyboard-readable values from the same data used to draw each chart.
   Tables are built only when opened and refreshed after chart updates. */
(() => {
  const entries = new Map();
  let nextId = 0;
  const text = value => value == null ? 'Unavailable' :
    typeof value === 'object' ? JSON.stringify(value) : String(value);

  function titleFor(canvas) {
    const heading = canvas.closest('article,.card,.section,.chart-panel,.rcard')?.querySelector('h2,h3,.card-title')?.cloneNode(true);
    heading?.querySelectorAll('.tip-btn,.tip-box,.info-pop').forEach(e => e.remove());
    return canvas.getAttribute('aria-label') ||
      heading?.textContent.trim() ||
      window.Chart?.getChart?.(canvas)?.data.datasets.map(series => series.label).filter(Boolean).join(' / ') ||
      canvas.id?.replaceAll('-', ' ') || 'Chart';
  }
  function chartValues(chart) {
    const rows = [];
    chart.data.datasets.forEach((series, index) => {
      if (!chart.isDatasetVisible(index)) return;
      series.data.forEach((value, point) => {
        const object = value !== null && typeof value === 'object' && !Array.isArray(value);
        rows.push([
          series.label || `Series ${index + 1}`,
          object ? value.x ?? chart.data.labels?.[point] ?? point + 1 : chart.data.labels?.[point] ?? point + 1,
          object ? value.y ?? value : value,
          object && value.r != null ? value.r : ''
        ]);
      });
    });
    const radius = rows.some(row => row[3] !== '');
    return { headers: ['Series', 'Label / x', 'Value / y', ...(radius ? ['Radius'] : [])],
      rows: rows.map(row => radius ? row : row.slice(0, 3)) };
  }
  function render(entry) {
    const title = titleFor(entry.element);
    if (title !== entry.title) {
      entry.title = title; entry.summary.textContent = `View chart values: ${title}`;
      entry.wrap.setAttribute('aria-label', `${title} values`);
    }
    if (!entry.details.open) return;
    if (entry.controls && (!entry.chart || entry.chart.data.datasets.length <= 1)) {
      entry.controls.remove(); entry.controls = null; entry.seriesInputs = null;
    }
    if (entry.chart && entry.chart.data.datasets.length > 1) {
      if (!entry.controls) {
        entry.controls = document.createElement('fieldset');
        const legend = document.createElement('legend');
        legend.textContent = 'Visible series'; entry.controls.append(legend);
        entry.details.insertBefore(entry.controls, entry.wrap);
        entry.seriesInputs = new Map();
      }
      entry.chart.data.datasets.forEach((series, index) => {
        let control = entry.seriesInputs.get(index);
        if (!control) {
          const label = document.createElement('label');
          const input = document.createElement('input'); input.type = 'checkbox';
          const name = document.createTextNode('');
          label.append(input, name); entry.controls.append(label);
          control = { label, input, name }; entry.seriesInputs.set(index, control);
          input.addEventListener('change', () => {
            entry.chart.setDatasetVisibility(index, input.checked); entry.chart.update();
          });
        }
        control.input.checked = entry.chart.isDatasetVisible(index);
        const name = series.label || `Series ${index + 1}`;
        if (control.name.textContent !== name) control.name.textContent = name;
      });
      entry.seriesInputs.forEach((control, index) => {
        if (index >= entry.chart.data.datasets.length) { control.label.remove(); entry.seriesInputs.delete(index); }
      });
    }
    const data = entry.read();
    const table = document.createElement('table');
    const caption = table.createCaption();
    caption.textContent = entry.title;
    const head = table.createTHead().insertRow();
    data.headers.forEach(label => {
      const cell = document.createElement('th');
      cell.scope = 'col'; cell.textContent = label; head.append(cell);
    });
    const body = table.createTBody();
    data.rows.forEach(row => {
      const tr = body.insertRow();
      row.forEach(value => { tr.insertCell().textContent = text(value); });
    });
    if (!data.rows.length) {
      const cell = body.insertRow().insertCell();
      cell.colSpan = data.headers.length; cell.textContent = 'No visible chart values.';
    }
    entry.wrap.replaceChildren(table);
  }
  function ensure(element, read) {
    let entry = entries.get(element);
    if (entry) { entry.read = read; return entry; }
    const title = titleFor(element);
    const details = document.createElement('details');
    details.className = 'ov-chart-values';
    details.id = `ov-chart-values-${++nextId}`;
    const summary = document.createElement('summary');
    summary.textContent = `View chart values: ${title}`;
    const wrap = document.createElement('div');
    wrap.className = 'ov-chart-table'; wrap.tabIndex = 0;
    wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', `${title} values`);
    details.append(summary, wrap);
    // Keep the disclosure outside fixed-height Chart.js sizing containers.
    const parent = element.parentElement;
    const container = element.ovChartContainer || (parent && parent.querySelectorAll('canvas,svg.chart,svg.spark').length === 1 &&
      /chart|canvas|cw|donut/.test(parent.className) ? parent : element);
    container.after(details);
    element.setAttribute('role', 'img');
    if (!element.hasAttribute('aria-label')) element.setAttribute('aria-label', title);
    entry = { element, summary, details, wrap, title, read };
    entries.set(element, entry);
    details.addEventListener('toggle', () => {
      if (details.open && typeof element.ovPauseChart === 'function') element.ovPauseChart();
      render(entry);
    });
    return entry;
  }
  function scan() {
    entries.forEach((entry, element) => {
      if (!element.isConnected) { entry.details.remove(); entries.delete(element); }
    });
    if (window.Chart?.instances) {
      Object.values(Chart.instances).forEach(chart => {
        if (!chart.canvas?.isConnected) return;
        // The traffic report already supplies its own matching data table.
        if (document.getElementById(`${chart.canvas.id}-data`)?.querySelector('table')) return;
        const entry = ensure(chart.canvas, () => chartValues(chart));
        entry.chart = chart;
      });
      if (!Chart.registry.plugins.get('ov-chart-values')) Chart.register({
        id: 'ov-chart-values',
        afterUpdate(chart) {
          queueMicrotask(() => {
            if (!chart.canvas?.isConnected) return;
            const entry = entries.get(chart.canvas);
            if (entry) { entry.chart = chart; entry.read = () => chartValues(chart); render(entry); }
            else schedule();
          });
        }
      });
    }
    // Leaflet's bitmap duplicates its named map region and location tables.
    document.querySelectorAll('.leaflet-overlay-pane canvas').forEach(canvas => canvas.setAttribute('aria-hidden', 'true'));
    document.querySelectorAll('svg.chart,svg.spark,canvas[data-ov-chart-table]').forEach(svg => {
      if (svg.ovChartTable) {
        const entry = ensure(svg, () => svg.ovChartTable);
        if (entry.lastData !== svg.ovChartTable) { entry.lastData = svg.ovChartTable; render(entry); }
      }
    });
  }
  let timer;
  function schedule() { clearTimeout(timer); timer = setTimeout(scan, 100); }
  function start() {
    const main = document.querySelector('main,[role="main"],.main') ||
      [...document.querySelectorAll('.wrap,.layout,.report')].find(e => !e.closest('header,footer,.topbar'));
    if (main && main.tagName !== 'MAIN' && !main.hasAttribute('role')) main.setAttribute('role', 'main');
    if (main) main.tabIndex = -1;
    const existingSkip = document.querySelector('a.skip,a.skip-link,a.ov-skip');
    if (existingSkip) document.body.prepend(existingSkip);
    if (main && !existingSkip) {
      main.id ||= 'ov-main';
      main.tabIndex = -1;
      const skip = document.createElement('a');
      skip.className = 'ov-skip'; skip.href = `#${main.id}`;
      skip.textContent = 'Skip to main content'; document.body.prepend(skip);
    }
    document.querySelector('a.skip,a.skip-link,a.ov-skip')?.addEventListener('click', event => {
      const link = event.currentTarget;
      if (link.origin !== location.origin || link.pathname !== location.pathname) return;
      const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
      if (!target) return;
      event.preventDefault(); target.tabIndex = -1;
      target.focus({ preventScroll: true }); target.scrollIntoView({ block: 'start' });
    });
    scan();
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    // Some reports fetch Chart.js/data after DOMContentLoaded.
    let attempts = 0;
    const initial = setInterval(() => { scan(); if (++attempts === 20) clearInterval(initial); }, 500);
    document.addEventListener('change', schedule);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();

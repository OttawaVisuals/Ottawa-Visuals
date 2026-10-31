'use strict';
(() => {
  const data = window.WEALTH_DATA;
  const $ = id => document.getElementById(id);
  if (!data || !data.years.length) {
    $('distribution').textContent = 'Data could not load. Use the CSV download below.';
    return;
  }
  const years = data.years;
  const fmt = n => n.toFixed(1).replace('-', '−');
  const pct = n => `${fmt(n)}%`;
  const money = n => (n < 0 ? '−' : '') + new Intl.NumberFormat('en-CA', {style: 'currency', currency: 'CAD', maximumFractionDigits: 0}).format(Math.abs(n));
  const options = years.slice().reverse().map(y => `<option value="${y.year}">${y.year}</option>`).join('');
  $('year').innerHTML = options;
  const svg = (w, h, title, body) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${title}"><title>${title}</title>${body}</svg>`;
  const text = (x, y, label, extra = '') => `<text x="${x}" y="${y}" font-size="12" ${extra}>${label}</text>`;

  function distribution(y) {
    const w = Math.max(260, $('distribution').clientWidth), h = 328;
    const left = 10, right = w - 14, min = -2, max = 70;
    const x = n => left + (n - min) / (max - min) * (right - left);
    let body = '';
    [0, 20, 40, 60].forEach(v => {
      body += `<line class="${v === 0 ? 'zero' : 'axis'}" x1="${x(v)}" x2="${x(v)}" y1="20" y2="298"/>`;
      body += text(x(v), 320, `${v}%`, 'text-anchor="middle"');
    });
    y.groups.forEach((g, i) => {
      const top = 12 + i * 57;
      body += text(left, top, g.label, 'class="chart-label"');
      body += text(right, top, pct(g.share), 'text-anchor="end" class="chart-label"');
      body += `<rect class="bar ${i === 4 ? 'top' : ''} ${g.share < 0 ? 'negative' : ''}" x="${Math.min(x(0), x(g.share))}" y="${top + 9}" width="${Math.abs(x(g.share) - x(0))}" height="23"><title>${g.label}: ${pct(g.share)} of net wealth</title></rect>`;
    });
    $('distribution').innerHTML = svg(w, h, `Wealth shares in Q4 ${y.year}. ` + y.groups.map(g => `${g.label}: ${pct(g.share)}`).join('; '), body);
  }

  function trend() {
    const points = $('trend-frequency').value === 'all' ? data.observations : years;
    const w = Math.max(260, $('trend').clientWidth), h = 290;
    const left = 38, right = w - 12, top = 16, bottom = h - 36;
    const x = time => left + (time - points[0].time) / (points.at(-1).time - points[0].time) * (right - left);
    const y = value => bottom - value / 80 * (bottom - top);
    let body = '';
    [0, 20, 40, 60, 80].forEach(v => {
      body += `<line class="axis" x1="${left}" x2="${right}" y1="${y(v)}" y2="${y(v)}"/>` + text(left - 8, y(v) + 4, `${v}%`, 'text-anchor="end"');
    });
    const ticks = w < 480 ? [2010, 2015, 2020, 2025] : [2010, 2013, 2016, 2019, 2022, 2025];
    ticks.filter(t => t >= years[0].year && t <= years.at(-1).year).forEach(t => {
      body += text(x(t+.75), h - 10, t, `text-anchor="${t === years[0].year ? 'start' : t === years.at(-1).year ? 'end' : 'middle'}"`);
    });
    const selected = Number($('year').value) + .75;
    body += `<line x1="${x(selected)}" x2="${x(selected)}" y1="${top}" y2="${bottom}" stroke="var(--ink-2)" stroke-dasharray="2 4" opacity=".5"/>`;
    [['top20', 'var(--accent)', ''], ['middle40', 'var(--accent-2)', '8 4'], ['bottom40', 'var(--green)', '2 4']].forEach(([key, color, dash]) => {
      body += `<polyline points="${points.map(d => `${x(d.time)},${y(d[key])}`).join(' ')}" fill="none" stroke="${color}" stroke-width="3" stroke-dasharray="${dash}"/>`;
      points.forEach(d => {
        body += `<circle cx="${x(d.time)}" cy="${y(d[key])}" r="${d.time === selected ? 5 : 3}" fill="${color}"><title>${d.label}: ${key === 'top20' ? 'wealthiest 20%' : key === 'middle40' ? 'middle 40%' : 'bottom 40%'} held ${pct(d[key])}</title></circle>`;
      });
    });
    $('trend').innerHTML = svg(w, h, `Wealth shares from ${years[0].year} to ${years.at(-1).year}. Exact values are in the annual table below.`, body);
  }

  function render() {
    const d = years.find(y => y.year === Number($('year').value));
    document.querySelectorAll('.selected-year').forEach(el => {el.textContent = d.year;});
    $('top-stat').textContent = pct(d.top20);
    $('bottom-stat').textContent = pct(d.bottom40);
    $('gap-stat').textContent = fmt(d.gap);
    $('values').innerHTML = d.groups.map(g => `<tr><th scope="row">${g.label}</th><td>${pct(g.share)}</td><td>${money(g.average_dollars)}</td></tr>`).join('');
    const lowest = d.groups[0];
    $('negative-note').textContent = lowest.average_dollars < 0
      ? `The lowest 20% had average net worth of ${money(lowest.average_dollars)} in ${d.year}: their debts exceeded their assets. The negative bar can be very small at this scale; its label gives the published share.`
      : `The lowest 20% had average net worth of ${money(lowest.average_dollars)} in ${d.year}. A small wealth share can be difficult to see at this scale; its label gives the published value.`;
    distribution(d);
    trend();
  }
  const first = years[0], last = years.at(-1), change = Math.round((last.gap - first.gap) * 10) / 10;
  $('trend-note').textContent = `The gap between the top 20% and bottom 40% was ${fmt(first.gap)} percentage points in ${first.year} and ${fmt(last.gap)} in ${last.year} — ${change > 0 ? 'up' : change < 0 ? 'down' : 'unchanged by'} ${fmt(Math.abs(change))} points. The groups contain different numbers of households.`;
  $('annual-values').innerHTML = data.observations.map(d => `<tr><th scope="row">${d.label}</th><td>${pct(d.top20)}</td><td>${pct(d.middle40)}</td><td>${pct(d.bottom40)}</td><td>${fmt(d.gap)}</td></tr>`).join('');
  $('retrieved').textContent = `Source downloaded ${data.retrieved_utc.slice(0,10)} (UTC).`;
  $('year').addEventListener('change', render);
  $('trend-frequency').addEventListener('change', trend);
  window.setTheme = mode => { document.documentElement.dataset.theme = mode; try {localStorage.setItem('ov-theme', mode);} catch(e) {} };
  let frame;
  new ResizeObserver(() => {cancelAnimationFrame(frame); frame = requestAnimationFrame(render);}).observe($('distribution'));
  render();
})();

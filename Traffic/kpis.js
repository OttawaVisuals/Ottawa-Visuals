/* Headline indicators for the top of the page. Reads only local files; each card fails on its own. */
'use strict';
(function () {
  const $ = id => document.getElementById(id);
  const get = (file, text) => fetch(file, {cache: 'no-cache'}).then(r => {
    if (!r.ok) throw new Error(file + ' ' + r.status);
    return text ? r.text() : r.json();
  });
  const fmt = n => Number(n).toLocaleString('en-CA', {maximumFractionDigits: 1});
  const signed = n => (n > 0 ? '+' : n < 0 ? '−' : '±') + fmt(Math.abs(n));
  const median = xs => { const s = [...xs].sort((a, b) => a - b), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  function parseCsv(text) {
    const rows = []; let row = [], cell = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
        else if (c === '"') quoted = false;
        else cell += c;
      } else if (c === '"') quoted = true;
      else if (c === ',') { row.push(cell); cell = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(cell); cell = ''; rows.push(row); row = [];
      } else cell += c;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    const head = rows.shift().map(h => h.replace(/^﻿/, ''));
    return rows.filter(r => r.length === head.length).map(r => Object.fromEntries(head.map((h, i) => [h, r[i]])));
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  // tone: 'bad' | 'good' | 'flat' (words always carry the meaning; colour only reinforces it)
  function fill(id, {label, value, delta, tone, notes}) {
    const card = $(id);
    card.replaceChildren(el('h3', 'kpi-label', label), el('div', 'stat-val', value), el('p', 'kpi-delta ' + tone, delta));
    notes.forEach(n => card.append(typeof n === 'string' ? el('p', 'kpi-note', n) : n));
  }
  function unavailable(id, label, err) {
    fill(id, {label, value: '—', delta: 'Not available right now', tone: 'flat', notes: [String(err.message || err)]});
  }

  async function fatalities() {
    const label = 'Fatal collisions · 2026 so far';
    const [report, releases, annual] = await Promise.all([
      get('data/derived/stops_report/report.json'), get('data/ops_collision_releases.csv', true), get('data/ops_annual_report_traffic.csv', true)]);
    const snap = report.snapshots.find(s => /year to date/i.test(s.label));
    const [prev, cur] = snap.metrics['Fatal collisions'];
    const m = /([A-Za-z]+) (\d{1,2}): *\d{4}/.exec(snap.period);
    const cut = m ? `${String(snap.labels[1]).match(/\d{4}/)[0]}-${String(months.indexOf(m[1]) + 1).padStart(2, '0')}-${m[2].padStart(2, '0')}` : null;
    const full = parseCsv(annual).find(r => r.year === '2025' && r.metric === 'fatal_collisions');
    const sameDates = `January 1 to ${m ? m[0].replace(/: .*/, '') : 'the cutoff'}`;
    const base = full ? Number(full.value) : prev;
    const notes = [`${sameDates} this year, against ${full ? 'all of 2025' : 'the same dates in 2025'}.` + (full ? ` Same dates in 2025: ${prev}.` : '') +
      ' OPS officer-attended collisions with a fatal injury; not a count of people.'];
    if (cut) {
      const since = parseCsv(releases).filter(r => r.kind === 'collision' && r.severity === 'fatal' && r.follow_up === '0' &&
        (r.incident_date || r.release_utc.slice(0, 10)) > cut).length;
      if (since) notes.push(`OPS has reported at least ${since} more fatal crashes since then. Our news log is a floor and is not yet in the official count.`);
    }
    fill('kpi-fatal', {label, value: fmt(cur), delta: `${signed(cur - base)} vs ${fmt(base)} in ${full ? 'all of 2025' : '2025'}`, tone: cur > base ? 'bad' : cur < base ? 'good' : 'flat', notes});
  }

  async function congestion() {
    const label = 'Congestion · worst hour of the day';
    const days = (await get('data/history/city_daily.json')).filter(d => d.peak_congestion_pct != null && d.weekday < 5);
    const recent = days.slice(-7), now = median(recent.map(d => d.peak_congestion_pct)), usual = median(days.map(d => d.peak_congestion_pct));
    const diff = now - usual;
    const word = diff <= -3 ? 'Lighter than usual' : diff >= 3 ? 'Heavier than usual' : 'About usual';
    const notes = [`Median of the last ${recent.length} weekdays. Share of free-flow speed lost, averaged over our sampled road points, at the worst sample of each day. Typical = every weekday since ${days[0].date}. A sample, not the whole network.`];
    try {
      const tt = parseCsv(await get('data/tomtom_ottawa_hourly.csv', true)).sort((a, b) => a.update_utc.localeCompare(b.update_utc)).at(-1);
      const when = new Date(tt.update_utc).toLocaleString('en-CA', {month: 'short', day: 'numeric', hour: 'numeric', timeZone: 'America/Toronto'});
      const src = el('a', null, 'TomTom Traffic Index'); src.href = 'https://www.tomtom.com/traffic-index/city/ottawa/'; src.rel = 'noopener';
      const p = el('p', 'kpi-note'); p.append('Whole-city check from the ', src, ` (© TomTom), ${when}: ${fmt(tt.congestion_pct)}% against ${fmt(tt.congestion_usual_pct)}% usual for that hour. Updated daily.`);
      notes.push(p);
    } catch (e) { /* TomTom log is optional */ }
    fill('kpi-traffic', {label, value: fmt(now) + '%', delta: `${word} (typical weekday ${fmt(usual)}%)`, tone: diff >= 3 ? 'bad' : diff <= -3 ? 'good' : 'flat', notes});
  }

  async function transit() {
    const label = 'OC Transpo · buses on time';
    const [obs, daily] = await Promise.all([get('../OC_Transpo/kpi_history/kpi_observations.csv', true), get('../OC_Transpo/rt_data/history/transit_daily.json')]);
    const rows = parseCsv(obs).filter(r => r.metric === 'punctuality_less_frequent_routes' && r.mode === 'bus');
    const official = rows.filter(r => r.period_type === 'month' && !r.breakdown).sort((a, b) => a.period.localeCompare(b.period)).at(-1);
    const target = rows.filter(r => r.period_type === 'target').sort((a, b) => a.meeting_date.localeCompare(b.meeting_date)).at(-1);
    const [y, mo] = official.period.split('-');
    const gap = Number(official.value) - Number(target.value);
    const live = daily.filter(d => d.n >= 100 && d.punctuality_pct != null).slice(-7);
    const notes = [`Official punctuality for ${months[Number(mo) - 1]} ${y}, the latest published, against the ${fmt(target.value)}% target in the ${target.meeting_date.slice(0, 4)} scorecard.`];
    if (live.length) {
      const avg = live.reduce((a, d) => a + d.punctuality_pct, 0) / live.length;
      notes.push(`Our live tracker, last ${live.length} days: ${fmt(avg)}%. It checks each bus at its next stop, not at timepoints, so it reads lower than the official figure.`);
    }
    fill('kpi-transit', {label, value: fmt(official.value) + '%', delta: `${signed(gap)} points vs ${fmt(target.value)}% target`, tone: gap < 0 ? 'bad' : 'good', notes});
  }

  async function latestEnforcement() {
    const rows = parseCsv(await get('data/ops_collision_releases.csv', true)).filter(r => r.kind === 'enforcement')
      .sort((a, b) => b.release_utc.localeCompare(a.release_utc));
    if (!rows.length) return;
    const r = rows[0], p = el('p', 'kpi-latest');
    const a = el('a', null, r.title);
    if (/^https:\/\/(www\.)?ottawapolice\.ca\//.test(r.url)) { a.href = r.url; a.rel = 'noopener'; }
    p.append(document.createTextNode('Latest OPS enforcement release, ' +
      new Date(r.release_utc).toLocaleDateString('en-CA', {month: 'short', day: 'numeric', timeZone: 'America/Toronto'}) + ': '), a);
    $('kpi-latest').replaceChildren(p);
  }

  [['kpi-fatal', 'Fatal collisions · 2026 so far', fatalities], ['kpi-traffic', 'Congestion · worst hour of the day', congestion],
   ['kpi-transit', 'OC Transpo · buses on time', transit]].forEach(([id, label, run]) => run().catch(err => unavailable(id, label, err)));
  latestEnforcement().catch(() => {});
})();

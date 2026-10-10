// Shared plumbing for every PWHL page: header + section nav + team-logo
// strip, theme switching, the JSON loader, the season picker and the
// Chart.js helpers. Page-specific rendering lives in pwhl-sections.js (the
// dashboard sections) or in the page itself (team.html, player.html).
// Load order: Chart.js, pwhl-teams.js, pwhl-core.js, [pwhl-sections.js].

const DATA_BASE = 'data/json/';
// Data globals, filled by PWHL.load(). Pages only fetch what they use.
let META = null, STANDINGS = null, LEADERS = null, GAMES = null, SHOTMAP = null,
    EVENTS = null, BRACKET = null, TXN = null, AWARDS = null, XG = null, RATINGS = null,
    ELO = null, GOALIES = null, RAPSHEET = null, ROSTERS = null, LINES = null, PINDEX = null,
    MOVEMENT = null;
const CHARTS = [];
let currentSeasonId = null;

function cssVar(name){ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function fmt(n){ return n == null || isNaN(n) ? '—' : Number(n).toLocaleString(); }
function esc(s){ return (s == null ? '' : String(s)).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
const plLink = (id, name) => id ? `<a class="pl-link" href="${playerHref(id)}">${esc(name)}</a>` : esc(name);
const teamDot = code => `<span class="team-dot" style="background:${teamColor(code)}"></span>`;
const teamHref = code => 'team.html?code=' + encodeURIComponent(code);
const teamLink = (code, label) => code ? `<a class="pl-link" href="${teamHref(code)}">${esc(label || code)}</a>` : esc(label || '');
const seasonName = sid => ((META && META.seasons.find(s => s.season_id === sid)) || {}).name || ('Season ' + sid);

const PWHL = {};

// ---------------------------------------------------------------- header
PWHL.PAGES = [
  ['home', 'pwhl.html', 'Home'],
  ['forecast', 'forecast.html', 'Forecast'],
  ['teams', 'teams.html', 'Teams'],
  ['players', 'players.html', 'Players'],
  ['superlatives', 'superlatives.html', 'Superlatives'],
  ['movement', 'movement.html', 'Movement'],
  ['method', 'methodology.html', 'How it works'],
];

// Writes the site top bar, the PWHL section nav, an (initially empty) team
// logo strip and the "data through" bar into #pwhl-header. Call it from an
// inline script right after the placeholder so the theme switch (which looks
// for #theme-toggle on DOMContentLoaded) finds its button.
PWHL.header = function (active) {
  const el = document.getElementById('pwhl-header');
  el.innerHTML = `
    <header class="topbar">
      <a href="../index.html" class="brand">
        <span class="brand-logo"><img src="../assets/img/avatar.png" alt=""></span>
        <span>Ottawa Visuals<small>data, charted simply</small></span>
      </a>
      <nav>
        <a href="../index.html#reports">Reports</a>
        <a href="pwhl.html" class="active">PWHL</a>
        <a href="../index.html#about">About</a>
      </nav>
      <span class="spacer"></span>
      <button class="icon-btn" id="theme-toggle" title="Toggle theme" aria-label="Toggle theme"></button>
    </header>
    <nav class="pwhl-nav" aria-label="PWHL pages">
      <span class="pwhl-nav-brand">PWHL</span>
      ${PWHL.PAGES.map(([k, href, label]) => `<a href="${href}"${k === active ? ' class="active" aria-current="page"' : ''}>${label}</a>`).join('')}
      <span class="spacer"></span>
      <span class="data-through" id="data-through"></span>
    </nav>
    <div class="logo-strip" id="logo-strip" aria-label="Teams"></div>`;
  // Inside the homepage iframe the site bar is redundant.
  if (window.self !== window.top) el.querySelector('.topbar').style.display = 'none';
  const t = document.getElementById('theme-toggle');
  t.addEventListener('click', () => setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'));
};

// Fills the logo strip (current league teams) and the "data through" bar.
// Needs META; uses ELO's team list when loaded, since it is the season ahead.
PWHL.fillHeader = function (activeCode) {
  if (!META) return;
  let teams = ELO && ELO.teams ? ELO.teams.map(t => ({ code: t.code, name: t.name, logo: t.logo })) : null;
  if (!teams) {
    const tb = META.teams_by_season || {};
    const latest = Object.keys(tb).sort((a, b) => Number(b) - Number(a))[0];
    teams = (tb[latest] || []).filter(t => t.code !== 'TBD');
  }
  teams = teams.slice().sort((a, b) => a.code.localeCompare(b.code));
  document.getElementById('logo-strip').innerHTML = teams.map(t => `
    <a href="${teamHref(t.code)}" title="${esc(t.name)}" class="${t.code === activeCode ? 'active' : ''}" style="--tc:${teamColor(t.code)}">
      ${t.logo ? `<img src="${esc(t.logo)}" alt="${esc(t.code)}" loading="lazy">` : `<span>${esc(t.code)}</span>`}
    </a>`).join('');
  const d = META.last_game_date;
  const nice = d ? new Date(d + 'T12:00:00').toLocaleDateString('en-CA', { day: 'numeric', month: 'short', year: 'numeric' }) : null;
  document.getElementById('data-through').textContent =
    (nice ? `Data through ${nice}` : '') + ` · refreshed ${META.generated_at.slice(0, 10)}`;
};

// ----------------------------------------------------------------- theme
// Called by the site theme pill (window.setTheme) and the hidden toggle.
// Pages register a re-render with PWHL.onTheme(fn).
const _themeHooks = [];
PWHL.onTheme = fn => _themeHooks.push(fn);
function setTheme(mode) {
  document.documentElement.setAttribute('data-theme', mode);
  try { localStorage.setItem('ov-theme', mode); } catch (e) {}
  refreshChartColors();
  _themeHooks.forEach(fn => fn(mode));
}
window.setTheme = setTheme;

// ---------------------------------------------------------------- loader
const _DATA_VARS = {
  meta: v => META = v, standings: v => STANDINGS = v, leaders: v => LEADERS = v, games: v => GAMES = v,
  shot_map: v => SHOTMAP = v, events: v => EVENTS = v, bracket: v => BRACKET = v, transactions: v => TXN = v,
  awards: v => AWARDS = v, xg: v => XG = v, ratings: v => RATINGS = v, elo: v => ELO = v,
  goalies: v => GOALIES = v, rapsheet: v => RAPSHEET = v, rosters: v => ROSTERS = v, lines: v => LINES = v,
  players_index: v => PINDEX = v,
  movement: v => MOVEMENT = v,
};
// Model outputs and other extras may be missing; the core files may not.
const _OPTIONAL = new Set(['xg', 'ratings', 'elo', 'goalies', 'rapsheet', 'rosters', 'lines', 'players_index']);
PWHL.load = function (names, versions = {}) {
  return Promise.all(names.map(n => fetch(DATA_BASE + 'pwhl_' + n + '.json'
    + (versions[n] ? '?v=' + encodeURIComponent(versions[n]) : ''))
    .then(r => { if (!r.ok) throw new Error(n + ': HTTP ' + r.status); return r.json(); })
    .then(v => _DATA_VARS[n](v))
    .catch(err => { if (_OPTIONAL.has(n)) { _DATA_VARS[n](null); } else { throw err; } })));
};
PWHL.fail = function (err) {
  console.error(err);
  const e = document.getElementById('load-error');
  if (e) e.style.display = 'block';
};

// --------------------------------------------------------- season picker
// The chosen season follows you between pages (URL ?season=, then the last
// pick, then the current regular season).
PWHL.initialSeason = function (valid) {
  const fromUrl = new URLSearchParams(location.search).get('season');
  let saved = null;
  try { saved = localStorage.getItem('pwhl-season'); } catch (e) {}
  for (const s of [fromUrl, saved, META.current_season_id]) if (s && valid.includes(s)) return s;
  return valid[valid.length - 1];
};
PWHL.seasonSelect = function (selectEl, seasonIds, onChange) {
  selectEl.innerHTML = seasonIds.slice().sort((a, b) => Number(b) - Number(a))
    .map(s => `<option value="${s}">${esc(seasonName(s))}</option>`).join('');
  currentSeasonId = PWHL.initialSeason(seasonIds);
  selectEl.value = currentSeasonId;
  selectEl.addEventListener('change', () => {
    currentSeasonId = selectEl.value;
    try { localStorage.setItem('pwhl-season', currentSeasonId); } catch (e) {}
    const u = new URL(location.href); u.searchParams.set('season', currentSeasonId); history.replaceState(null, '', u);
    onChange(currentSeasonId);
  });
  return currentSeasonId;
};
// Seasons that have regular-season standings or skater lines.
PWHL.statSeasons = () => META.seasons.map(s => s.season_id)
  .filter(s => (STANDINGS && STANDINGS[s] && STANDINGS[s].length) || (AWARDS && AWARDS[s]));

// --------------------------------------------------------- player search
PWHL.playerSearch = function (form) {
  const input = form.querySelector('input');
  const list = form.querySelector('datalist');
  let byLabel = {};
  fetch(DATA_BASE + 'pwhl_players_index.json').then(r => r.ok ? r.json() : []).then(rows => {
    PINDEX = rows;
    list.innerHTML = rows.map(p => {
      const label = `${p.name} (${p.team || '—'}${p.pos ? ', ' + p.pos : ''})`;
      byLabel[label.toLowerCase()] = p.id;
      byLabel[p.name.toLowerCase()] = byLabel[p.name.toLowerCase()] || p.id;
      return `<option value="${esc(label)}"></option>`;
    }).join('');
  }).catch(() => { form.style.display = 'none'; });
  form.addEventListener('submit', e => {
    e.preventDefault();
    const q = input.value.trim().toLowerCase();
    const id = byLabel[q] || (Object.entries(byLabel).find(([k]) => k.includes(q)) || [])[1];
    if (q && id) window.location.href = playerHref(id);
  });
  input.addEventListener('change', () => { if (byLabel[input.value.trim().toLowerCase()]) form.requestSubmit(); });
};

// --------------------------------------------------------- chart helpers
function baseOptions(overrides = {}) {
  const base = {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: cssVar('--ink-2'), font: { family: 'Inter', size: 11 }, boxWidth: 12, usePointStyle: true } },
      tooltip: { backgroundColor: cssVar('--bg-3'), titleColor: cssVar('--ink'), bodyColor: cssVar('--ink-2'), borderColor: cssVar('--line'), borderWidth: 1 },
    },
    scales: {
      x: { ticks: { color: cssVar('--ink-3'), font: { size: 10 } }, grid: { color: cssVar('--line') } },
      y: { ticks: { color: cssVar('--ink-3'), font: { size: 10 } }, grid: { color: cssVar('--line') } },
    },
  };
  // Merge `plugins` one level deep so a chart that only hides its legend keeps
  // the themed tooltip.
  const { plugins, ...rest } = overrides;
  Object.assign(base, rest);
  if (plugins) Object.assign(base.plugins, plugins);
  return base;
}
function trackChart(chart) { CHARTS.push(chart); return chart; }
function refreshChartColors() {
  CHARTS.forEach(chart => {
    if (!chart.options.plugins) return;
    chart.options.plugins.legend.labels.color = cssVar('--ink-2');
    chart.options.plugins.tooltip.backgroundColor = cssVar('--bg-3');
    chart.options.plugins.tooltip.titleColor = cssVar('--ink');
    chart.options.plugins.tooltip.bodyColor = cssVar('--ink-2');
    chart.options.plugins.tooltip.borderColor = cssVar('--line');
    Object.values(chart.options.scales || {}).forEach(s => { if (s.ticks) s.ticks.color = cssVar('--ink-3'); if (s.grid && s.grid.display !== false) s.grid.color = cssVar('--line'); });
    chart.update('none');
  });
}
function destroyChart(id) {
  const idx = CHARTS.findIndex(c => c.canvas && c.canvas.id === id);
  if (idx >= 0) { CHARTS[idx].destroy(); CHARTS.splice(idx, 1); }
}
// Legend for "team colour, solid vs. faded" bar pairs: neutral swatches,
// since each bar's actual colour is its team's.
function pairedLegend() {
  return { labels: { color: cssVar('--ink-2'), font: { family: 'Inter', size: 11 }, boxWidth: 12,
    generateLabels: chart => chart.data.datasets.map((ds, i) => ({
      text: ds.label, datasetIndex: i, hidden: !chart.isDatasetVisible(i), fontColor: cssVar('--ink-2'),
      fillStyle: i === 0 ? cssVar('--ink-2') : 'transparent', strokeStyle: cssVar('--ink-2'), lineWidth: 1,
    })) } };
}
// Tab buttons: wires a .tabs container so clicking sets .active and calls fn(value).
PWHL.tabs = function (wrap, attr, fn) {
  wrap.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
    wrap.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
    fn(btn.dataset[attr]);
  }));
};

// Small formatters shared by several pages.
const signed2 = v => v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(2);
const signedCell = v => `<span style="color:${v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'inherit'}">${signed2(v)}</span>`;
const mmss = secs => Math.floor(secs / 60) + ':' + String(Math.round(secs % 60)).padStart(2, '0');
const pctFmt = v => v == null ? '—' : v >= 0.995 ? '>99%' : v > 0 && v < 0.005 ? '<1%' : Math.round(v * 100) + '%';
// "2026-12-05" -> "Dec 5" (parsed as a local date, not UTC midnight).
const shortDate = iso => { if (!iso) return ''; const [y, m, d] = iso.split('-').map(Number); return new Date(y, m - 1, d).toLocaleDateString('en-CA', { month: 'short', day: 'numeric' }); };
function emptyTable(id, msg) {
  const table = typeof id === 'string' ? document.getElementById(id) : id;
  table.innerHTML = `<tbody><tr><td style="text-align:left;color:var(--ink-3)">${esc(msg)}</td></tr></tbody>`;
  collapseRows(table, 1);  // drops a stale "show all" button from the previous season
}
function teamLogo(seasonId, code) {
  const t = ((META.teams_by_season || {})[seasonId] || []).find(t => t.code === code);
  return t && t.logo ? `<img src="${esc(t.logo)}" alt="">` : '';
}
// Click-to-sort for a table built from `rows`: columns = [{key, label, get, fmt, num}].
PWHL.sortableTable = function (table, columns, rows, opts = {}) {
  let sortKey = opts.sortKey || columns.find(c => c.num).key, dir = -1;
  const draw = () => {
    const col = columns.find(c => c.key === sortKey);
    const sorted = rows.slice().sort((a, b) => {
      const va = col.get(a), vb = col.get(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return (typeof va === 'string' ? va.localeCompare(vb) : va - vb) * dir;
    });
    table.innerHTML = `<thead><tr><th>#</th>${columns.map(c => `<th data-k="${c.key}" class="sortable${c.key === sortKey ? ' sorted' : ''}" title="${esc(c.title || '')}">${esc(c.label)}${c.key === sortKey ? (dir < 0 ? ' ▾' : ' ▴') : ''}</th>`).join('')}</tr></thead>
      <tbody>${sorted.map((r, i) => `<tr><td class="rank-badge">${i + 1}</td>${columns.map(c => `<td${c.key === sortKey ? ' class="pts-cell"' : ''}>${c.fmt ? c.fmt(c.get(r), r) : esc(c.get(r))}</td>`).join('')}</tr>`).join('')}</tbody>`;
    table.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', () => {
      const k = th.dataset.k;
      const c = columns.find(c => c.key === k);
      dir = k === sortKey ? -dir : (c.num ? -1 : 1);
      sortKey = k; draw();
    }));
    collapseRows(table, opts.show || 25, opts.noun || 'rows');
  };
  draw();
};

// Team colours and small chart helpers shared by pwhl.html and player.html.
// Each team's dominant brand colour (approximate -- the league publishes colour
// names, not hex codes). Keyed by the feed's team code; MON is the 2024
// preseason code for Montréal. Expansion teams (2026-27) use the announced
// palettes until their identities are revealed.
const PWHL_TEAM_COLORS = {
  BOS: '#17513D', // Fleet green
  MIN: '#4B2E83', // Frost midnight purple
  MTL: '#862633', MON: '#862633', // Victoire burgundy
  NY:  '#14A0AE', // Sirens teal
  OTT: '#C8102E', // Charge red
  TOR: '#2F62CF', // Sceptres blue
  SEA: '#5B8A7E', // Torrent slate green
  VAN: '#0E4D73', // Goldeneyes Pacific blue
  DET: '#8E9399', // Detroit silver (primary black is invisible on dark theme)
  HAM: '#D4A017', // Hamilton gold
  VEG: '#2E7048', VGS: '#2E7048', // Las Vegas green
  SJ:  '#F26B21', // San Jose orange
};

function pwhlHexToRgb(hex) {
  hex = hex.replace('#', '');
  if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
  const n = parseInt(hex, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function pwhlLuminance(hex) {
  const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const [r, g, b] = pwhlHexToRgb(hex).map(lin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function pwhlMix(hex, toward, t) {
  const a = pwhlHexToRgb(hex), b = pwhlHexToRgb(toward);
  return '#' + a.map((v, i) => Math.round(v + (b[i] - v) * t).toString(16).padStart(2, '0')).join('');
}

// Team colour for the current theme: the darkest brand colours (Fleet green,
// Frost purple, Victoire burgundy) are lifted a little on the dark theme so the
// bars don't disappear into the background.
function teamColor(code) {
  const base = PWHL_TEAM_COLORS[code] || '#8A93A3';
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  return dark && pwhlLuminance(base) < 0.09 ? pwhlMix(base, '#ffffff', 0.3) : base;
}
function teamColorA(code, alpha) {
  const [r, g, b] = pwhlHexToRgb(teamColor(code));
  return `rgba(${r},${g},${b},${alpha})`;
}
// Readable text colour on top of a filled bar.
function inkOn(hex) { return pwhlLuminance(hex) > 0.35 ? '#15181E' : '#FFFFFF'; }

// Diagonal-stripe fill, used to set takeover games apart from home games
// while keeping the team colour.
const _stripeCache = {};
function stripedFill(hex) {
  if (_stripeCache[hex]) return _stripeCache[hex];
  const c = document.createElement('canvas');
  c.width = c.height = 8;
  const x = c.getContext('2d');
  x.fillStyle = hex; x.globalAlpha = 0.45; x.fillRect(0, 0, 8, 8);
  x.globalAlpha = 1; x.strokeStyle = hex; x.lineWidth = 3;
  x.beginPath(); x.moveTo(-2, 10); x.lineTo(10, -2); x.moveTo(-2, 2); x.lineTo(2, -2); x.moveTo(6, 10); x.lineTo(10, 6); x.stroke();
  return (_stripeCache[hex] = x.createPattern(c, 'repeat'));
}

// Chart.js plugin: writes each bar's value inside the bar (or just past its
// end when the bar is too short). Configure per chart with
//   options.plugins.barLabels = { format: (value, index, datasetIndex) => 'text', datasets: [0] }
// `datasets` limits which datasets get labels (default: the last visible one,
// i.e. the end of a stacked bar). `outside: true` always writes past the end.
const BarLabelsPlugin = {
  id: 'barLabels',
  afterDatasetsDraw(chart, _args, opts) {
    if (!opts || !opts.format) return;
    const { ctx } = chart;
    const horizontal = chart.options.indexAxis === 'y';
    const visible = chart.data.datasets.map((_, i) => i).filter(i => chart.isDatasetVisible(i));
    const which = opts.datasets || visible.slice(-1);
    const ink = getComputedStyle(document.documentElement).getPropertyValue('--ink').trim() || '#222';
    ctx.save();
    ctx.font = `600 ${opts.size || 11}px Inter, system-ui, sans-serif`;
    which.forEach(di => {
      if (!chart.isDatasetVisible(di)) return;
      const ds = chart.data.datasets[di];
      chart.getDatasetMeta(di).data.forEach((bar, i) => {
        const text = opts.format(ds.data[i], i, di);
        if (text == null || text === '') return;
        const w = ctx.measureText(text).width;
        const { x, y, base } = bar.getProps(['x', 'y', 'base'], true);
        const start = base;
        const fill = Array.isArray(ds.backgroundColor) ? ds.backgroundColor[i] : ds.backgroundColor;
        const solid = typeof fill === 'string' && fill.startsWith('#') ? fill : null;
        if (horizontal) {
          const len = Math.abs(x - start), neg = x < start;
          const inside = !opts.outside && len > w + 12;
          ctx.textBaseline = 'middle';
          ctx.textAlign = inside ? (neg ? 'left' : 'right') : (neg ? 'right' : 'left');
          ctx.fillStyle = inside && solid ? inkOn(solid) : ink;
          ctx.fillText(text, inside ? (neg ? x + 6 : x - 6) : (neg ? x - 5 : x + 5), y);
        } else {
          const len = Math.abs(start - y);
          const inside = !opts.outside && len > 18 && bar.width > w + 4;
          ctx.textAlign = 'center';
          ctx.textBaseline = inside ? 'top' : 'bottom';
          ctx.fillStyle = inside && solid ? inkOn(solid) : ink;
          ctx.fillText(text, x, inside ? y + 4 : y - 3);
        }
      });
    });
    ctx.restore();
  },
};
if (window.Chart) Chart.register(BarLabelsPlugin);

// Show the first `n` body rows of a table, with a button to expand the rest
// in place (instead of a scroll box inside the card).
// Also works on a plain list element (its children are the rows).
function collapseRows(table, n, noun) {
  const isTable = table.tagName === 'TABLE';
  const rows = isTable ? Array.from(table.tBodies[0] ? table.tBodies[0].rows : []) : Array.from(table.children);
  const anchor = isTable ? table.parentElement : table;
  let btn = anchor.nextElementSibling;
  if (btn && btn.classList && btn.classList.contains('more-btn')) btn.remove();
  if (rows.length <= n) return;
  let open = false;
  btn = document.createElement('button');
  btn.className = 'more-btn';
  const sync = () => {
    rows.forEach((r, i) => { r.style.display = open || i < n ? '' : 'none'; });
    btn.textContent = open ? 'Show fewer' : `Show all ${rows.length} ${noun || 'rows'}`;
  };
  btn.addEventListener('click', () => { open = !open; sync(); });
  anchor.after(btn);
  sync();
}

function playerHref(id) { return 'player.html?id=' + encodeURIComponent(id); }

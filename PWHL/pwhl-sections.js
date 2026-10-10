// Render functions for the dashboard sections, shared by the PWHL pages
// (home, forecast, teams, players, superlatives, how it works). Each page
// includes the markup for the sections it shows and calls their render
// functions; see the init block at the bottom of each page.
// Needs pwhl-teams.js and pwhl-core.js loaded first.

let currentLeaderStat = 'points';
let currentAwardsMode = 'total';
let currentBracketSeasonId = null;
let currentRatingsGroup = 'all';

function renderOverview() {
  const gp = Object.values(GAMES).reduce((a, arr) => a + arr.length, 0);
  const goals = Object.values(GAMES).reduce((a, arr) => a + arr.reduce((s, g) => s + (g.home_score||0) + (g.away_score||0), 0), 0);
  const totalShots = Object.values(EVENTS.event_counts).length ? (EVENTS.event_counts.shot || 0) + (EVENTS.event_counts.goal || 0) : 0;
  document.getElementById('overview-sub').textContent =
    `${META.seasons.length} recorded seasons (including preseason/playoffs) · last updated ${META.generated_at.slice(0,10)}`;
  const stats = [
    [fmt(gp), 'GAMES RECORDED'],
    [fmt(goals), 'TOTAL GOALS'],
    [fmt(totalShots), 'TOTAL SHOT ATTEMPTS'],
    [(goals/Math.max(gp,1)).toFixed(2), 'GOALS PER GAME'],
  ];
  const row = document.getElementById('overview-stats');
  row.innerHTML = stats.map(([num, lbl]) => `<div class="stat"><div class="num">${num}</div><div class="lbl">${lbl}</div></div>`).join('');
}

function renderStandingsTable(seasonId) {
  const teams = STANDINGS[seasonId] || [];
  const table = document.getElementById('standings-table');
  table.innerHTML = `
    <thead><tr>
      <th>#</th><th>Team</th><th>GP</th><th>W</th><th>L</th><th>OTL</th><th>SOL</th><th>PTS</th><th>GF</th><th>GA</th>
    </tr></thead>
    <tbody>
      ${teams.map(t => `
        <tr>
          <td class="rank-badge">${t.rank ?? '—'}</td>
          <td class="team-stripe" style="--tc:${teamColor(t.code)}"><a href="${teamHref(t.code)}" class="team-cell">${t.logo ? `<img src="${esc(t.logo)}" alt="">` : ''}<span>${esc(t.name || t.code)}</span></a></td>
          <td>${fmt(t.gp)}</td><td>${fmt(t.w)}</td><td>${fmt(t.l)}</td>
          <td>${fmt((t.otl||0))}</td><td>${fmt((t.sol||0))}</td>
          <td class="pts-cell">${fmt(t.pts)}</td><td>${fmt(t.gf)}</td><td>${fmt(t.ga)}</td>
        </tr>`).join('')}
    </tbody>`;
}

function renderGoalsChart(seasonId) {
  const teams = (STANDINGS[seasonId] || []).slice().sort((a,b) => (b.pts||0) - (a.pts||0));
  destroyChart('chart-goals');
  const ctx = document.getElementById('chart-goals').getContext('2d');
  trackChart(new Chart(ctx, {
    type: 'bar',
    data: {
      labels: teams.map(t => t.code || t.name),
      datasets: [
        { label: 'Goals for', data: teams.map(t => t.gf), backgroundColor: teams.map(t => teamColor(t.code)) },
        { label: 'Goals against', data: teams.map(t => t.ga), backgroundColor: teams.map(t => teamColorA(t.code, 0.35)),
          borderColor: teams.map(t => teamColor(t.code)), borderWidth: 1 },
      ],
    },
    options: baseOptions({ plugins: { legend: pairedLegend() } }),
  }));
}
function renderSpecialTeamsChart(seasonId) {
  const teams = (STANDINGS[seasonId] || []).slice().sort((a,b) => (b.pts||0) - (a.pts||0));
  const pct = v => v ? parseFloat(String(v).replace('%','')) : 0;
  destroyChart('chart-special-teams');
  const ctx = document.getElementById('chart-special-teams').getContext('2d');
  trackChart(new Chart(ctx, {
    type: 'bar',
    data: {
      labels: teams.map(t => t.code || t.name),
      datasets: [
        { label: 'Power play %', data: teams.map(t => pct(t.pp_pct)), backgroundColor: teams.map(t => teamColor(t.code)) },
        { label: 'Penalty kill %', data: teams.map(t => pct(t.pk_pct)), backgroundColor: teams.map(t => teamColorA(t.code, 0.35)),
          borderColor: teams.map(t => teamColor(t.code)), borderWidth: 1 },
      ],
    },
    options: baseOptions({ plugins: { legend: pairedLegend() }, scales: { x: { ticks: { color: cssVar('--ink-3'), font: { size: 10 } }, grid: { color: cssVar('--line') } }, y: { beginAtZero: true, ticks: { color: cssVar('--ink-3'), font: { size: 10 }, callback: v => v + '%' }, grid: { color: cssVar('--line') } } } }),
  }));
}

// ================================================================
// PLAYER LEADERS
// ================================================================
const LEADER_STATS = [
  { key: 'points', label: 'Points' },
  { key: 'goals', label: 'Goals' },
  { key: 'assists', label: 'Assists' },
  { key: 'shots', label: 'Shots' },
  { key: 'hits', label: 'Hits' },
  { key: 'faceoff_pct', label: 'Faceoff %' },
];
function buildLeaderTabs() {
  const wrap = document.getElementById('leader-tabs');
  wrap.innerHTML = LEADER_STATS.map(s => `<button class="tab-btn${s.key==='points'?' active':''}" data-stat="${s.key}">${s.label}</button>`).join('');
  wrap.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
    wrap.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentLeaderStat = btn.dataset.stat;
    renderLeaders(currentSeasonId, currentLeaderStat);
  }));
}
function renderLeaders(seasonId, statKey) {
  const spec = LEADER_STATS.find(s => s.key === statKey) || LEADER_STATS[0];
  const rows = ((LEADERS[seasonId] || {})[statKey] || []);
  document.getElementById('leaders-chart-title').textContent = spec.label + ' leaders';

  // One chart instead of chart + duplicate table: bars in team colour, with
  // the value and games played written inside each bar.
  destroyChart('chart-leaders');
  const ctx = document.getElementById('chart-leaders').getContext('2d');
  const isPct = statKey === 'faceoff_pct';
  const valueText = v => v == null ? '—' : isPct ? v.toFixed(1) + '%' : fmt(v);
  trackChart(new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map((r, i) => `${i + 1}. ${r.name} · ${r.team_code || ''}`),
      datasets: [{ label: spec.label, data: rows.map(r => r[statKey]),
        backgroundColor: rows.map(r => teamColor(r.team_code)), borderRadius: 3, barPercentage: 0.82 }],
    },
    options: baseOptions({
      indexAxis: 'y',
      onClick: (_e, els) => { if (els.length) window.location.href = playerHref(rows[els[0].index].player_id); },
      onHover: (e, els) => { e.native.target.style.cursor = els.length ? 'pointer' : 'default'; },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => `${spec.label}: ${valueText(c.raw)} · ${rows[c.dataIndex].gp} GP` } },
        barLabels: { format: (v, i) => `${valueText(v)}  ·  ${rows[i].gp} GP`, size: 11 },
      },
      scales: {
        x: { beginAtZero: !isPct, ticks: { color: cssVar('--ink-3'), font: { size: 10 } }, grid: { color: cssVar('--line') } },
        y: { ticks: { color: cssVar('--ink-2'), font: { size: 11.5 } }, grid: { display: false } },
      },
    }),
  }));
}

// ================================================================
// SUPERLATIVES / AWARDS
// ================================================================
// Each award ranks the season's skaters two ways: raw totals, and the same
// stat per 60 minutes of ice time. The rate view is the point of the section
// -- totals mostly re-rank the minutes leaders, rates surface depth players.
// Rate-mode minimums keep a 4-game call-up off the top of every list. They
// scale to the season's length so a 10-game playoff run isn't held to the same
// bar as an 30-game regular season.
const AW_TOP_N = 5;
function awardsThresholds(rows) {
  const maxGp = rows.reduce((m, r) => Math.max(m, r.gp), 0);
  const minGp = Math.max(3, Math.min(8, Math.round(maxGp * 0.3)));
  // Volume minimums (shots taken, faceoffs taken) scale off a 30-game season.
  const scale = Math.max(0.25, Math.min(1, maxGp / 30));
  return {
    minGp, minMin: minGp * 15,
    minShots: Math.max(8, Math.round(25 * scale)),
    minFaceoffs: Math.max(25, Math.round(100 * scale)),
  };
}

const per60 = (v, r) => r.toi > 0 ? v * 3600 / r.toi : 0;
const int0 = v => fmt(Math.round(v));
const dec0 = v => v.toFixed(0);
const dec1 = v => v.toFixed(1);
const dec2 = v => v.toFixed(2);
const signed = v => (v > 0 ? '+' : '') + (Number.isInteger(v) ? v : v.toFixed(2));

const AWARDS_DEFS = [
  { key:'goon', emoji:'🥊', title:'The Goon',
    blurb:'Most penalty minutes. The box is a second home.',
    val: r => r.pim, fmt: int0, unit:'PIM', rateUnit:'PIM/60' },
  { key:'fairplay', emoji:'😇', title:'The Fair-Play Award',
    blurb:'Highest share of games played without taking a single penalty.',
    filter: (r, th) => r.log_gp >= th.minGp, val: r => 100 * r.clean_gp / r.log_gp,
    // Plenty of players finish at 100%; the one who did it over more games ranks first.
    tie: r => r.log_gp * 1e7 + r.toi,
    fmt: (v, r) => `${dec0(v)}% · ${r.clean_gp}/${r.log_gp} GP`,
    noRate:true, sub: th => `Penalty-free games ÷ games played · min. ${th.minGp} GP` },
  { key:'impact_high', emoji:'📈', title:'Plus/Minus Leader',
    blurb:'Highest plus/minus: goals for minus goals against while on the ice.',
    val: r => r.plus_minus, fmt: signed, rateFmt: signed, unit:'+/−', rateUnit:'+/−/60' },
  { key:'impact_low', emoji:'📉', title:'Rough Nights',
    blurb:'Worst plus/minus. Often a good player on a bad night shift.',
    asc:true, val: r => r.plus_minus, fmt: signed, rateFmt: signed, unit:'+/−', rateUnit:'+/−/60' },
  { key:'ironwoman', emoji:'🧱', title:'The Iron Woman',
    blurb:'Most games played — never missed a night.',
    val: r => r.gp, fmt: int0, unit:'GP', noRate:true, tie: r => r.toi },
  { key:'workhorse', emoji:'🐴', title:'The Workhorse',
    blurb:'Most total ice time; in rate mode, most minutes per game.',
    val: r => r.toi / 60, fmt: v => int0(v) + ' min',
    rate: r => r.toi / Math.max(r.gp, 1), rateFmt: mmss, rateUnit:'per game' },
  { key:'hammer', emoji:'💥', title:'The Hammer',
    blurb:'Most hits thrown. Finishes every check.',
    val: r => r.hits, fmt: int0, unit:'hits', rateUnit:'hits/60' },
  { key:'shield', emoji:'🛡️', title:'The Human Shield',
    blurb:'Most shots blocked — the willingly-bruised.',
    val: r => r.blocks, fmt: int0, unit:'blocks', rateUnit:'blocks/60' },
  { key:'trigger', emoji:'🔫', title:'Trigger Finger',
    blurb:'Most shots on goal. Shoot first, ask later.',
    val: r => r.shots, fmt: int0, unit:'shots', rateUnit:'shots/60' },
  { key:'sniper', emoji:'🎯', title:'The Sniper',
    blurb:'Best shooting percentage among the season\'s volume shooters. Ruthless efficiency.',
    filter: (r, th) => r.shots >= th.minShots, val: r => 100 * r.goals / r.shots,
    fmt: v => dec1(v) + '%', noRate:true, sub: th => `Min. ${th.minShots} shots` },
  { key:'hardluck', emoji:'🪫', title:'Hard Luck',
    blurb:'Lowest shooting percentage among those same volume shooters. The pucks simply will not go in.',
    filter: (r, th) => r.shots >= th.minShots, asc:true, val: r => 100 * r.goals / r.shots,
    fmt: v => dec1(v) + '%', noRate:true, sub: th => `Min. ${th.minShots} shots` },
  { key:'value', emoji:'💸', title:'The Point Producer', rateTitle:'Bang For The Buck',
    blurb:'Most points scored this season.',
    rateBlurb:'Most points per 60 minutes of ice time.',
    val: r => r.points, fmt: int0, unit:'PTS', rateFmt: dec2, rateUnit:'PTS/60' },
  { key:'playmaker', emoji:'🎩', title:'The Playmaker',
    blurb:'Most assists. Would rather set it up than shoot it.',
    val: r => r.assists, fmt: int0, unit:'A', rateFmt: dec2, rateUnit:'A/60' },
  { key:'closer', emoji:'🔒', title:'The Closer',
    blurb:'Most game-winning goals — shows up when it decides the night.',
    val: r => r.gwg, fmt: int0, unit:'GWG', rateFmt: dec2, rateUnit:'GWG/60' },
  { key:'icebreaker', emoji:'🧊', title:'The Ice Breaker',
    blurb:'Most goals that opened the scoring. Sets the tone.',
    val: r => r.first_goals, fmt: int0, unit:'1st goals', rateFmt: dec2, rateUnit:'/60' },
  { key:'lonewolf', emoji:'🐺', title:'The Lone Wolf',
    blurb:'Most unassisted goals — did the whole thing herself.',
    val: r => r.unassisted_goals, fmt: int0, unit:'UA goals', rateFmt: dec2, rateUnit:'/60' },
  { key:'faceoff', emoji:'⚪', title:'The Draw Master',
    blurb:'Best faceoff percentage among the regular centres.',
    filter: (r, th) => r.fo_attempts >= th.minFaceoffs, val: r => 100 * r.fo_wins / r.fo_attempts,
    fmt: v => dec1(v) + '%', noRate:true, sub: th => `Min. ${th.minFaceoffs} faceoffs` },
  { key:'pk', emoji:'⚡', title:'Shorthanded Menace',
    blurb:'Most goals scored while down a skater.',
    val: r => r.shg, fmt: int0, unit:'SHG', rateFmt: dec2, rateUnit:'SHG/60' },
  { key:'vulture', emoji:'🦅', title:'The Vulture',
    blurb:'Most empty-net goals. The other goalie is on the bench and somebody always happens to be standing there.',
    val: r => r.en_goals || 0, fmt: int0, unit:'EN goals', rateFmt: dec2, rateUnit:'EN goals/60' },
  { key:'shinpad', emoji:'🦵', title:'The Shin-Pad Shooter',
    blurb:'Highest share of shot attempts that hit a defender instead of reaching the net.',
    filter: (r, th) => r.shots + (r.blocked_att || 0) >= th.minShots * 1.5,
    val: r => 100 * (r.blocked_att || 0) / (r.shots + (r.blocked_att || 0)),
    fmt: (v, r) => `${dec1(v)}% · ${r.blocked_att}/${r.shots + r.blocked_att}`,
    noRate:true, sub: th => `Blocked ÷ (on goal + blocked) · min. ${Math.round(th.minShots * 1.5)} attempts` },
];

const AWARD_GROUPS = [
  { id:'scoring', title:'Scoring & playmaking', keys:['trigger','sniper','hardluck','value','playmaker','closer','icebreaker','lonewolf'] },
  { id:'workload', title:'Workload & on-ice results', keys:['impact_high','impact_low','ironwoman','workhorse'] },
  { id:'physical', title:'Physical play & discipline', keys:['goon','fairplay','hammer','shield','faceoff','shinpad'] },
  { id:'situational', title:'Special situations', keys:['pk','vulture'] },
];

// Inline the local SVGs so their colours follow the site's light, dark, and
// colour-blind themes. A missing icon falls back to its original emoji.
const AWARD_ICONS = new Map();
const AWARD_ICON_COLORS = {
  '#283447': 'var(--ink)',
  '#9ea8b7': 'var(--ink-3)',
  '#697a8d': 'var(--ink-2)',
  '#c9542f': 'var(--accent)',
  '#c93436': 'var(--red)',
  '#22885f': 'var(--green)',
  '#fff': 'var(--bg-2)',
};
function awardIcon(def, className = 'aw-icon') {
  const svg = AWARD_ICONS.get(def.key);
  return svg ? `<span class="${className}" aria-hidden="true">${svg}</span>`
    : `<span class="aw-emoji" aria-hidden="true">${def.emoji}</span>`;
}
function loadAwardIcons() {
  return Promise.all(AWARDS_DEFS.map(async def => {
    const filename = def.key.replaceAll('_', '-');
    try {
      const response = await fetch(`icon-concepts/${filename}.svg`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const doc = new DOMParser().parseFromString(await response.text(), 'image/svg+xml');
      const svg = doc.documentElement;
      if (svg.localName !== 'svg') throw new Error('Invalid SVG');
      svg.querySelector('title')?.remove();
      svg.removeAttribute('role');
      svg.removeAttribute('aria-labelledby');
      svg.setAttribute('aria-hidden', 'true');
      svg.setAttribute('focusable', 'false');
      const themed = svg.outerHTML.replace(/#[0-9a-f]{3,8}\b/gi,
        color => AWARD_ICON_COLORS[color.toLowerCase()] || color);
      AWARD_ICONS.set(def.key, themed);
    } catch (err) {
      console.warn(`Award icon ${filename} unavailable:`, err);
    }
  }));
}

function awardRanking(def, rows, mode, th) {
  const useRate = mode === 'rate' && !def.noRate;
  let pool = rows;
  if (def.filter) pool = pool.filter(r => def.filter(r, th));
  if (useRate) pool = pool.filter(r => r.gp >= th.minGp && r.toi >= th.minMin * 60);
  const value = useRate
    ? (def.rate ? def.rate : r => per60(def.val(r), r))
    : def.val;
  const sign = def.asc ? 1 : -1;
  const tie = def.tie || (r => r.toi);
  const scored = pool.map(r => ({ r, v: value(r) }))
    .filter(x => isFinite(x.v))
    .sort((a, b) => sign * (a.v - b.v) || sign * (tie(a.r) - tie(b.r)));
  // Everyone at zero is tied and uninteresting -- don't pad a list with them.
  const trimmed = def.asc ? scored : scored.filter(x => x.v !== 0);
  const list = (trimmed.length ? trimmed : scored).slice(0, AW_TOP_N);
  const formatter = useRate ? (def.rateFmt || dec1) : def.fmt;
  const unit = useRate ? (def.rateUnit || '') : (def.unit || '');
  return { list, formatter, unit, useRate, qualified: pool.length };
}

const AWARD_DETAIL_GP = new Set([
  'value', 'playmaker', 'closer', 'icebreaker', 'lonewolf',
  'impact_high', 'impact_low', 'workhorse',
]);
const AWARD_DETAIL_MIN = new Set([
  'trigger', 'value', 'playmaker', 'lonewolf',
  'impact_high', 'impact_low', 'ironwoman',
]);
function awardRowDetail(def, r, useRate) {
  const parts = [];
  if (useRate) {
    const total = def.fmt(def.val(r), r);
    parts.push(def.rate ? total : `${total} ${def.unit || 'total'}`);
  }
  if (AWARD_DETAIL_GP.has(def.key)) parts.push(`${int0(r.gp)} GP`);
  if ((useRate && !def.rate) || AWARD_DETAIL_MIN.has(def.key))
    parts.push(`${int0(r.toi / 60)} min played`);
  if (def.key === 'sniper' || def.key === 'hardluck') parts.push(`${int0(r.shots)} shots taken`);
  if (def.key === 'shinpad') parts.push(`${int0(r.shots)} shots on goal`);
  return parts.join(' · ');
}

function renderAwards(seasonId, mode) {
  const grid = document.getElementById('awards-grid');
  const note = document.getElementById('awards-note');
  const rows = (AWARDS && AWARDS[seasonId]) || [];
  if (!rows.length) {
    grid.innerHTML = '';
    note.textContent = 'No superlatives for this season — the feed carries no ice-time data for it '
      + '(the 2024 preseason is logged with zero minutes for every player).';
    return;
  }
  const th = awardsThresholds(rows);
  const cards = new Map(AWARDS_DEFS.map(def => {
    const { list, formatter, unit, useRate } = awardRanking(def, rows, mode, th);
    // Awards with a custom rate (e.g. minutes per game) label themselves via
    // rateUnit -- don't tack "per 60 min" onto those.
    const ownSub = typeof def.sub === 'function' ? def.sub(th) : (def.sub || '');
    const sub = useRate
      ? `${def.rate ? '' : 'Per 60 min · '}min. ${th.minGp} GP, ${th.minMin} min`
      : ownSub;
    const hasTies = list.some((x, i) => i > 0 && x.v === list[i - 1].v);
    const body = list.length
      ? list.map((x, i) => {
        const detail = awardRowDetail(def, x.r, useRate);
        return `
          <div class="aw-row">
            <span class="rk">${list.some((y, j) => j !== i && y.v === x.v) ? 'T' : ''}${list.findIndex(y => y.v === x.v) + 1}</span>
            <span class="nm">${plLink(x.r.player_id, x.r.name)}<span class="tm">${teamDot(x.r.team_code)}${esc(x.r.team_code || '')}${x.r.traded ? '*' : ''}</span></span>
            <span class="vl">${esc(formatter(x.v, x.r))}</span>
            ${detail ? `<span class="aw-row-detail">${esc(detail)}</span>` : ''}
          </div>`;
      }).join('')
      : '<div class="aw-sub">Not enough qualifying players.</div>';
    return [def.key, `
      <div class="aw-card">
        <div class="aw-head">${awardIcon(def)}<span class="aw-title">${esc(useRate && def.rateTitle ? def.rateTitle : def.title)}</span></div>
        <div class="aw-blurb">${esc(useRate && def.rateBlurb ? def.rateBlurb : def.blurb)}</div>
        <div class="aw-list">${body}</div>
        <div class="aw-sub">${esc(unit ? unit + (sub ? ' · ' + sub : '') : sub)}</div>
        ${hasTies ? `<div class="aw-tie-note">Equal values share a rank; listed by ${def.key === 'fairplay' ? 'games played, then ice time' : 'ice time'}.</div>` : ''}
      </div>`];
  }));
  grid.innerHTML = AWARD_GROUPS.map(group => `
    <section class="award-group" id="award-${group.id}" aria-labelledby="award-${group.id}-title">
      <h3 id="award-${group.id}-title">${group.title}</h3>
      <div class="awards-grid">${group.keys.map(key => cards.get(key)).join('')}</div>
    </section>`).join('');
  note.textContent = `${rows.length} skaters with at least one game played. `
    + (mode === 'rate'
       ? `Rate stats are per 60 minutes of ice time, restricted to players with ${th.minGp}+ games and ${th.minMin}+ minutes.`
       : 'Equal values share a rank. Awards that are already rates or eligibility-based (fair play %, sniper, hard luck, draw master, iron woman) stay on their own scale in both views.')
    + ' * = played for more than one team this season; stats are combined.';
}

// ---- Rap sheet: most penalties for each infraction ----------------------
function renderRapSheet(seasonId) {
  const grid = document.getElementById('rapsheet-grid');
  const rows = (RAPSHEET && RAPSHEET[seasonId]) || [];
  grid.innerHTML = rows.length ? rows.map(r => `
    <div class="aw-card rap-card">
      <div class="aw-head"><span class="aw-title">${esc(r.infraction)}</span><span class="aw-sub" style="margin-left:auto">${fmt(r.total)} called</span></div>
      <div class="aw-list">${r.top.map((p, i) => `
        <div class="aw-row"><span class="rk">${i + 1}</span>
          <span class="nm">${plLink(p.player_id, p.name)}<span class="tm">${teamDot(p.team_code)}${esc(p.team_code || '')}</span></span>
          <span class="vl">${p.n}</span></div>`).join('')}</div>
    </div>`).join('') : '<p class="note">No penalty data in the play-by-play for this season.</p>';
  collapseRows(grid, 9, 'infractions');
}

// ---- Hall of Sustained Quirk: outright winners of the same award in two or
// more regular seasons (totals view; a tie at the top doesn't count).
function renderHall() {
  const wrap = document.getElementById('hall-list');
  const regular = META.seasons.filter(s => /Regular/.test(s.name) && AWARDS[s.season_id]).map(s => s.season_id);
  const wins = {};   // `${pid}|${award}` -> {r, def, seasons:[]}
  regular.forEach(sid => {
    const rows = AWARDS[sid];
    const th = awardsThresholds(rows);
    AWARDS_DEFS.forEach(def => {
      const { list } = awardRanking(def, rows, 'total', th);
      if (!list.length || list[0].v === 0 || (list[1] && list[1].v === list[0].v)) return;
      const key = list[0].r.player_id + '|' + def.key;
      const w = wins[key] = wins[key] || { def, seasons: [] };
      w.seasons.push(sid);
      w.r = list[0].r;  // seasons run oldest first, so this ends on the latest title
    });
  });
  const hall = Object.values(wins).filter(w => w.seasons.length >= 2)
    .sort((a, b) => b.seasons.length - a.seasons.length || a.r.name.localeCompare(b.r.name));
  wrap.innerHTML = hall.length ? hall.map(w => `
    <div class="aw-row hall-row">
      ${awardIcon(w.def, 'aw-hall-icon')}
      <span class="nm">${plLink(w.r.player_id, w.r.name)}<span class="tm">${teamDot(w.r.team_code)}${esc(w.r.team_code || '')}</span></span>
      <span class="vl">${esc(w.def.title)} · ${w.seasons.map(s => esc(seasonName(s).replace(' Regular Season', ''))).join(', ')}</span>
    </div>`).join('') : '<p class="note">Nobody has won the same award outright twice yet.</p>';
  document.getElementById('hall-note').textContent =
    `Across ${regular.length} regular seasons. Team shown is the player's most recent title season.`;
}

function buildAwardsTabs() {
  const wrap = document.getElementById('awards-mode-tabs');
  wrap.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
    wrap.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentAwardsMode = btn.dataset.mode;
    renderAwards(currentSeasonId, currentAwardsMode);
  }));
}

// ================================================================
// SHOT MAP / EVENTS (season-independent -- see methodology note)
// ================================================================
function renderShotSections() {
  drawRink();
  renderPeriodChart();
  renderEventsChart();
  const total = SHOTMAP.cells.reduce((a,c) => a + c.shots, 0);
  const goals = SHOTMAP.cells.reduce((a,c) => a + c.goals, 0);
  document.getElementById('shot-map-note').textContent =
    `${fmt(total)} shot attempts plotted (${fmt(goals)} goals) across all recorded games, all seasons.`;
}
function drawRink() {
  if (!SHOTMAP) return;
  const canvas = document.getElementById('rink-canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const pad = 14;
  const rinkW = W - pad*2, rinkH = H - pad*2;

  // Rink outline (rounded rect) + markings, for orientation only.
  ctx.strokeStyle = cssVar('--line-2');
  ctx.lineWidth = 2;
  roundRect(ctx, pad, pad, rinkW, rinkH, 28);
  ctx.stroke();
  // Center red line
  ctx.strokeStyle = cssVar('--accent');
  ctx.globalAlpha = 0.5;
  ctx.beginPath(); ctx.moveTo(W/2, pad); ctx.lineTo(W/2, H-pad); ctx.stroke();
  // Blue lines (~25% and 75% across, roughly matching real blue-line spacing)
  ctx.strokeStyle = cssVar('--blue');
  [0.28, 0.72].forEach(f => { ctx.beginPath(); ctx.moveTo(pad + rinkW*f, pad); ctx.lineTo(pad + rinkW*f, H-pad); ctx.stroke(); });
  ctx.globalAlpha = 1;
  // Center faceoff circle
  ctx.strokeStyle = cssVar('--line-2');
  ctx.beginPath(); ctx.arc(W/2, H/2, 28, 0, Math.PI*2); ctx.stroke();

  // Density grid, coords span x:[-100,100] y:[-45,45] mapped to the rink box.
  const gx = SHOTMAP.grid_x, gy = SHOTMAP.grid_y;
  const maxShots = Math.max(1, ...SHOTMAP.cells.map(c => c.shots));
  const cellW = rinkW / gx, cellH = rinkH / gy;
  const accentRgb = hexToRgbArr(cssVar('--accent'));
  SHOTMAP.cells.forEach(c => {
    const t = c.shots / maxShots;
    const alpha = Math.min(0.92, Math.pow(t, 0.45) * 0.9 + (c.shots ? 0.06 : 0));
    if (!alpha) return;
    ctx.fillStyle = `rgba(${accentRgb[0]},${accentRgb[1]},${accentRgb[2]},${alpha.toFixed(3)})`;
    ctx.fillRect(pad + c.bx*cellW, pad + c.by*cellH, cellW+0.5, cellH+0.5);
  });
}
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x+r, y);
  ctx.arcTo(x+w, y, x+w, y+h, r);
  ctx.arcTo(x+w, y+h, x, y+h, r);
  ctx.arcTo(x, y+h, x, y, r);
  ctx.arcTo(x, y, x+w, y, r);
  ctx.closePath();
}
function hexToRgbArr(hex) {
  hex = hex.replace('#','');
  if (hex.length === 3) hex = hex.split('').map(c=>c+c).join('');
  const n = parseInt(hex, 16);
  return [(n>>16)&255, (n>>8)&255, n&255];
}
function renderPeriodChart() {
  const order = ['1','2','3','OT1','OT2'];
  const labels = order.filter(p => EVENTS.goals_by_period[p] != null);
  destroyChart('chart-period');
  const ctx = document.getElementById('chart-period').getContext('2d');
  trackChart(new Chart(ctx, {
    type: 'bar',
    data: { labels: labels.map(p => p.startsWith('OT') ? 'OT' + p.slice(2) : 'P' + p),
      datasets: [{ label: 'Goals', data: labels.map(p => EVENTS.goals_by_period[p]), backgroundColor: cssVar('--accent') }] },
    options: baseOptions({ plugins: { legend: { display: false } } }),
  }));
}
function renderEventsChart() {
  const order = ['shot','faceoff','hit','blocked_shot','penalty','goal'];
  const labelMap = { shot: 'Shots', faceoff: 'Faceoffs', hit: 'Hits', blocked_shot: 'Blocked shots', penalty: 'Penalties', goal: 'Goals' };
  const colors = ['--blue','--ink-3','--amber','--purple','--red','--accent'];
  destroyChart('chart-events');
  const ctx = document.getElementById('chart-events').getContext('2d');
  trackChart(new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: order.map(k => labelMap[k]),
      datasets: [{ data: order.map(k => EVENTS.event_counts[k] || 0), backgroundColor: colors.map(cssVar) }],
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: cssVar('--ink-2'), font: { size: 10 }, boxWidth: 10 } } } },
  }));
}

// ================================================================
// PLAYOFF BRACKET
// ================================================================
function buildBracketTabs() {
  const seasons = Object.keys(BRACKET).sort((a,b) => Number(a)-Number(b));
  const nameOf = sid => (META.seasons.find(s => s.season_id === sid) || {}).name || sid;
  const wrap = document.getElementById('bracket-tabs');
  wrap.innerHTML = seasons.map(sid => `<button class="tab-btn${sid===currentBracketSeasonId?' active':''}" data-season="${sid}">${esc(nameOf(sid))}</button>`).join('');
  wrap.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
    wrap.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderBracket(btn.dataset.season);
  }));
}
function renderBracket(seasonId) {
  currentBracketSeasonId = seasonId;
  const rows = BRACKET[seasonId] || [];
  // Group by round -> series_letter, keep the last game row per series for the final score.
  const rounds = {};
  rows.forEach(r => {
    rounds[r.round] = rounds[r.round] || {};
    const s = rounds[r.round][r.series_letter] = rounds[r.round][r.series_letter] || {
      round_name: r.round_name, team1_name: r.team1_name, team2_name: r.team2_name,
      team1_id: r.team1_id, team2_id: r.team2_id,
      team1_wins: r.team1_series_wins, team2_wins: r.team2_series_wins, games: 0,
    };
    s.games++;
  });
  const wrap = document.getElementById('bracket-rounds');
  const roundKeys = Object.keys(rounds).sort((a,b) => Number(a)-Number(b));
  wrap.innerHTML = roundKeys.map(rk => {
    const series = Object.values(rounds[rk]);
    return `<div class="bracket-round">
      <div class="bracket-round-title">${esc(series[0].round_name || ('Round ' + rk))}</div>
      ${series.map(s => {
        const w1 = Number(s.team1_wins) > Number(s.team2_wins);
        const teams = (META.teams_by_season || {})[seasonId] || [];
        const dot = id => { const t = teams.find(t => t.team_id === id); return t ? teamDot(t.code) : ''; };
        return `<div class="series-card">
          <div class="series-row${w1?' winner':''}"><span class="nm">${dot(s.team1_id)}${esc(s.team1_name)}</span><span class="sc">${fmt(s.team1_wins)}</span></div>
          <div class="series-row${!w1?' winner':''}"><span class="nm">${dot(s.team2_id)}${esc(s.team2_name)}</span><span class="sc">${fmt(s.team2_wins)}</span></div>
          <div class="series-meta">${s.games} game${s.games===1?'':'s'} played</div>
        </div>`;
      }).join('')}
    </div>`;
  }).join('') || '<p class="note">No playoff data for this season yet.</p>';
}

// ================================================================
// FORECAST: Elo ratings, game predictions, playoff odds
// ================================================================
let currentEloConf = null;

function renderForecast() {
  const sec = document.getElementById('forecast');
  if (!ELO) { sec.style.display = 'none'; return; }
  document.getElementById('forecast-title').textContent = `${ELO.season_name.replace(' Regular Season', '')} forecast`;
  document.getElementById('forecast-sub').textContent = ELO.started
    ? `Team strength ratings (Elo), win chances for upcoming games, and playoff odds from simulating the rest of the season ${fmt(ELO.n_sims)} times.`
    : `The season starts ${ELO.upcoming.length ? shortDate(ELO.upcoming[0].date) : 'soon'}. Opening Elo ratings carry over from last season, pulled part of the way back to average, and playoff odds come from simulating the whole season ${fmt(ELO.n_sims)} times.`;

  // Playoff odds, one table per conference (or one league table).
  const confs = ELO.format ? Object.keys(ELO.format.conferences) : [null];
  const cols = ELO.format
    ? [['pts', 'Pts'], ['playoffs', 'Playoffs'], ['conf_final', 'Conf F'], ['final', 'Final'], ['cup', 'Cup']]
    : [['pts', 'Proj. pts'], ['rank', 'Avg. rank']];
  document.getElementById('odds-grid').innerHTML = confs.map(conf => {
    const teams = ELO.teams.filter(t => conf == null || t.conference === conf)
      .sort((a, b) => ELO.format ? (b.playoffs - a.playoffs) || (b.cup - a.cup) : a.rank - b.rank);
    return `<div class="card">
      <div class="card-title">${conf ? esc(conf) + 'ern Conference' : 'League'}${ELO.format ? ` · top ${ELO.format.per_conference} make the playoffs` : ''}</div>
      <div style="overflow-x:auto;"><table class="tbl">
        <thead><tr><th>#</th><th>Team</th><th>Elo</th>${cols.map(c => `<th>${c[1]}</th>`).join('')}</tr></thead>
        <tbody>${teams.map((t, i) => `<tr>
          <td class="rank-badge">${i + 1}</td>
          <td class="team-stripe" style="--tc:${teamColor(t.code)}"><a href="${teamHref(t.code)}" class="team-cell">${t.logo ? `<img src="${esc(t.logo)}" alt="">` : ''}<span>${esc(t.name)}</span></a></td>
          <td>${Math.round(t.elo)}</td>
          ${cols.map(([k]) => `<td class="pct-cell${k === 'playoffs' ? ' pts-cell' : ''}">${k === 'pts' || k === 'rank' ? (t[k] != null ? t[k].toFixed(1) : '—') : pctFmt(t[k])}</td>`).join('')}
        </tr>`).join('')}</tbody>
      </table></div>
    </div>`;
  }).join('');

  // Upcoming games, plus how recent predictions fared once the season is on.
  const gameRow = g => {
    const homeFav = g.p_home >= 0.5;
    return `<div class="game-row">
      <span class="game-date">${esc(shortDate(g.date))}</span>
      <div class="game-teams">
        <span class="${homeFav ? '' : 'fav'}">${teamDot(g.away)}${teamLink(g.away)} ${Math.round((1 - g.p_home) * 100)}%</span>
        <span class="${homeFav ? 'fav' : ''}">${Math.round(g.p_home * 100)}% @ ${teamLink(g.home)}${teamDot(g.home)}</span>
      </div>
      <div class="prob-bar"><span style="width:${(1 - g.p_home) * 100}%;background:${teamColor(g.away)}"></span><span style="width:${g.p_home * 100}%;background:${teamColor(g.home)}"></span></div>
    </div>`;
  };
  const recentRow = g => {
    const hit = (g.p_home >= 0.5) === (g.home_score > g.away_score);
    return `<div class="game-row">
      <span class="game-date">${esc(shortDate(g.date))}</span>
      <div class="game-teams"><span>${esc(g.away)} ${g.away_score} @ ${esc(g.home)} ${g.home_score}${g.late ? ' (OT/SO)' : ''}</span>
        <span>home ${Math.round(g.p_home * 100)}%<span class="result-tag ${hit ? 'hit' : 'miss'}">${hit ? '✓ called' : '✗ missed'}</span></span></div>
    </div>`;
  };
  document.getElementById('upcoming-title').textContent = `Upcoming games: win chances (away · home)`;
  const up = document.getElementById('upcoming-list');
  up.innerHTML = ELO.upcoming.length ? ELO.upcoming.map(gameRow).join('') : '<p class="note">No games left on the schedule.</p>';
  collapseRows(up, 8, 'upcoming games');
  const recent = document.getElementById('recent-list');
  recent.closest('.card').style.display = ELO.recent.length ? '' : 'none';
  recent.innerHTML = ELO.recent.map(recentRow).join('');
  collapseRows(recent, 8, 'results');
  renderScorecardStrip();

  currentEloConf = confs[0];
  renderEloChart();

  const p = ELO.params, sc = ELO.scorecard, bt = sc.backtest;
  const now = sc.this_season
    ? ` This season so far: ${Math.round(sc.this_season.accuracy * 100)}% of ${sc.this_season.games} winners called.` : '';
  document.getElementById('forecast-note').textContent =
    `Pts = average final points across the simulations; Conf F = reaches the conference final. `
    + `Elo: K=${p.k}, home ice worth ${p.hfa} points, ratings pulled ${Math.round(p.regress * 100)}% back to 1500 between seasons, `
    + `margin of victory ${p.mov ? 'counted' : 'ignored'}, expansion teams start ${-p.expansion} below average (based on only two teams: Seattle and Vancouver in 2025-26). `
    + `Settings tuned on ${bt.games} games (${sc.backtest_seasons.join(', ')}): picked the winner ${Math.round(bt.accuracy * 100)}% of the time `
    + `(home teams win ${Math.round(ELO.home_win_rate * 100)}%), log loss ${bt.log_loss} vs ${bt.baseline_log_loss} for always guessing the home-win rate. `
    + `Hockey is close to a coin flip game to game, so treat single-game numbers as leanings.${now} `
    + `Simulations: ${Math.round(ELO.ot_rate * 100)}% of games go to OT/SO (3-2-1-0 points), ties broken by regulation wins, `
    + `the top seed picks the lower-rated of 3rd/4th, and playoff games are played at neutral strength.`;
}

// Day-by-day strip: how many winners the model called on each past game day,
// then how many games are on each coming day.
function renderScorecardStrip() {
  const strip = document.getElementById('scorecard-strip');
  if (!strip) return;
  const past = {}, next = {};
  ELO.recent.forEach(g => {
    const d = past[g.date] = past[g.date] || { n: 0, hit: 0 };
    d.n++; d.hit += (g.p_home >= 0.5) === (g.home_score > g.away_score) ? 1 : 0;
  });
  ELO.upcoming.forEach(g => { next[g.date] = (next[g.date] || 0) + 1; });
  const pastDays = Object.keys(past).sort().slice(-7);
  const nextDays = Object.keys(next).sort().slice(0, 10);
  const day = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-CA', { weekday: 'short' }).toUpperCase();
  strip.innerHTML = pastDays.map(d => `<div class="sc-day past${past[d].hit / past[d].n >= 0.5 ? ' good' : ''}">
      <span class="dw">${day(d)}</span><span class="dd">${shortDate(d)}</span><b>${past[d].hit}/${past[d].n} ✓</b></div>`).join('')
    + nextDays.map((d, i) => `<div class="sc-day${i === 0 ? ' next' : ''}">
      <span class="dw">${day(d)}</span><span class="dd">${shortDate(d)}</span><b>${next[d]} game${next[d] === 1 ? '' : 's'}</b></div>`).join('');
  const sc = ELO.scorecard;
  document.getElementById('scorecard-sum').textContent = sc.this_season
    ? `${Math.round(sc.this_season.accuracy * 100)}% of ${sc.this_season.games} winners called this season`
    : `Season not started · back-tested at ${Math.round(sc.backtest.accuracy * 100)}% on ${sc.backtest.games} past games`;
}

function renderEloChart() {
  const confs = ELO.format ? Object.keys(ELO.format.conferences) : [null];
  const teams = ELO.teams.filter(t => currentEloConf == null || t.conference === currentEloConf);
  destroyChart('chart-elo');
  const ctx = document.getElementById('chart-elo').getContext('2d');
  trackChart(new Chart(ctx, {
    type: 'line',
    data: {
      datasets: teams.map((t, i) => ({
        label: t.code,
        data: (ELO.history[t.code] || []).map(([d, v]) => ({ x: d, y: v })),
        borderColor: teamColor(t.code), backgroundColor: teamColor(t.code),
        // Expansion teams have a single opening-day point until they play.
        borderWidth: 1.5, pointRadius: (ELO.history[t.code] || []).length < 2 ? 3 : 0, tension: 0.2,
      })),
    },
    options: baseOptions({
      parsing: false,
      scales: {
        x: { type: 'category', labels: [...new Set(teams.flatMap(t => (ELO.history[t.code] || []).map(h => h[0])))].sort(),
             ticks: { color: cssVar('--ink-3'), font: { size: 10 }, maxTicksLimit: 8 }, grid: { color: cssVar('--line') } },
        y: { ticks: { color: cssVar('--ink-3'), font: { size: 10 } }, grid: { color: cssVar('--line') } },
      },
    }),
  }));
  // Conference toggle lives in the chart card's title row.
  const title = document.querySelector('#chart-elo').closest('.card').querySelector('.card-title');
  if (confs.length > 1) {
    title.innerHTML = `Elo rating over time · ${confs.map(c => `<button class="tab-btn${c === currentEloConf ? ' active' : ''}" data-conf="${esc(c)}" style="padding:2px 8px;margin-left:4px;">${esc(c)}</button>`).join('')}`;
    title.querySelectorAll('button').forEach(b => b.addEventListener('click', () => { currentEloConf = b.dataset.conf; renderEloChart(); }));
  }
}

// ================================================================
// EXPECTED GOALS (season-dependent tables + all-season model charts)
// ================================================================
function renderXg(seasonId) {
  const s = XG && XG.by_season[seasonId];
  destroyChart('chart-gsax');
  if (!s) {
    ['gsax-table', 'skater-xg-table'].forEach(id => emptyTable(id, 'No play-by-play for this season.'));
    return;
  }

  // Goalies: chart the regulars, table everyone with a meaningful sample.
  const maxShots = Math.max(1, ...s.goalies.map(g => g.shots));
  const regulars = s.goalies.filter(g => g.shots >= Math.max(50, maxShots * 0.15));
  const ctx = document.getElementById('chart-gsax').getContext('2d');
  trackChart(new Chart(ctx, {
    type: 'bar',
    data: {
      labels: regulars.map(g => `${g.name} (${g.team_code})`),
      datasets: [{ label: 'GSAx', data: regulars.map(g => g.gsax),
        backgroundColor: regulars.map(g => teamColor(g.team_code)), borderRadius: 3 }],
    },
    options: baseOptions({ indexAxis: 'y',
      onClick: (_e, els) => { if (els.length) window.location.href = playerHref(regulars[els[0].index].player_id); },
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: c => `GSAx ${signed2(c.raw)}` } },
        barLabels: { format: v => signed2(v), size: 10.5 } } }),
  }));
  document.getElementById('gsax-table').innerHTML = `
    <thead><tr><th>#</th><th>Goalie</th><th>Team</th><th>Shots</th><th>GA</th><th>SV%</th><th>xSV%</th><th>GSAx</th></tr></thead>
    <tbody>${s.goalies.filter(g => g.shots >= 20).map((g, i) => `<tr>
      <td class="rank-badge">${i+1}</td><td>${plLink(g.player_id, g.name)}</td><td>${teamDot(g.team_code)}${esc(g.team_code)}</td>
      <td>${fmt(g.shots)}</td><td>${fmt(g.goals_against)}</td>
      <td>${g.sv_pct != null ? g.sv_pct.toFixed(3) : '—'}</td><td>${g.xsv_pct != null ? g.xsv_pct.toFixed(3) : '—'}</td>
      <td class="pts-cell">${signedCell(g.gsax)}</td></tr>`).join('')}</tbody>`;



  document.getElementById('skater-xg-table').innerHTML = `
    <thead><tr><th>#</th><th>Player</th><th>Shots</th><th>Goals</th><th>xG</th><th>G − xG</th></tr></thead>
    <tbody>${s.skaters.slice(0, 25).map((p, i) => `<tr>
      <td class="rank-badge">${i+1}</td><td>${plLink(p.player_id, p.name)}</td><td>${fmt(p.shots)}</td><td>${fmt(p.goals)}</td>
      <td class="pts-cell">${p.ixg.toFixed(1)}</td><td>${signedCell(p.g_minus_xg)}</td></tr>`).join('')}</tbody>`;
  collapseRows(document.getElementById('gsax-table'), 10, 'goalies');
  collapseRows(document.getElementById('skater-xg-table'), 10, 'shooters');
}

// Team share of expected goals (teams page).
function renderTeamXg(seasonId) {
  const s = XG && XG.by_season[seasonId];
  if (!s) { emptyTable('team-xg-table', 'No play-by-play for this season.'); return; }
  document.getElementById('team-xg-table').innerHTML = `
    <thead><tr><th>#</th><th>Team</th><th>xGF</th><th>xGA</th><th>xGF%</th><th>GF</th><th>GA</th></tr></thead>
    <tbody>${s.teams.map((t, i) => `<tr>
      <td class="rank-badge">${i+1}</td>
      <td class="team-stripe" style="--tc:${teamColor(t.code)}"><a href="${teamHref(t.code)}" class="team-cell">${teamLogo(seasonId, t.code)}<span>${esc(t.name)}</span></a></td>
      <td>${t.xgf.toFixed(1)}</td><td>${t.xga.toFixed(1)}</td>
      <td class="pts-cell">${t.xgf_pct.toFixed(1)}%</td><td>${fmt(t.gf)}</td><td>${fmt(t.ga)}</td></tr>`).join('')}</tbody>`;
}

function renderXgModelCharts() {
  if (!XG) {
    document.getElementById('xg-note').textContent = 'Expected-goals model output not found (run scripts/build_models.py).';
    return;
  }
  drawDangerMap();
  const m = XG.model;
  destroyChart('chart-calibration');
  const ctx = document.getElementById('chart-calibration').getContext('2d');
  const maxP = Math.max(...m.calibration.map(c => Math.max(c.pred, c.actual))) * 1.1;
  trackChart(new Chart(ctx, {
    type: 'scatter',
    data: { datasets: [
      { label: 'Held-out shots, grouped into tenths by predicted xG',
        data: m.calibration.map(c => ({ x: c.pred * 100, y: c.actual * 100 })),
        backgroundColor: cssVar('--accent'), pointRadius: 5 },
      { label: 'Perfect calibration', type: 'line', data: [{ x: 0, y: 0 }, { x: maxP * 100, y: maxP * 100 }],
        borderColor: cssVar('--ink-3'), borderDash: [4, 4], pointRadius: 0, borderWidth: 1 },
    ] },
    options: baseOptions({
      plugins: { tooltip: { callbacks: { label: c => `predicted ${c.raw.x.toFixed(1)}% · actual ${c.raw.y.toFixed(1)}%` } },
                 legend: { labels: { color: cssVar('--ink-2'), font: { family: 'Inter', size: 11 }, boxWidth: 12, usePointStyle: true } } },
      scales: {
        x: { title: { display: true, text: 'Predicted goal %', color: cssVar('--ink-3') }, min: 0, ticks: { color: cssVar('--ink-3'), font: { size: 10 } }, grid: { color: cssVar('--line') } },
        y: { title: { display: true, text: 'Actual goal %', color: cssVar('--ink-3') }, min: 0, ticks: { color: cssVar('--ink-3'), font: { size: 10 } }, grid: { color: cssVar('--line') } },
      },
    }),
  }));
  const h = m.holdout;
  document.getElementById('xg-note').textContent =
    `Model fitted on ${fmt(m.shots)} shots on goal (${fmt(m.goals)} goals). On held-out games: ` +
    `AUC ${h.auc} (0.5 = coin flip), log loss ${h.log_loss} vs ${h.baseline_log_loss} for a flat league-average guess. ` +
    `Danger map pools all seasons.`;
}

function drawDangerMap() {
  if (!XG) return;
  const canvas = document.getElementById('danger-canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height, pad = 8;
  const w = W - pad * 2, h = H - pad * 2;
  const px = x => pad + x / 100 * w;              // feet from centre ice -> canvas x
  const py = y => pad + (y + 42.5) / 85 * h;       // feet from centre width -> canvas y
  ctx.clearRect(0, 0, W, H);

  const dm = XG.danger_map;
  const cw = w / dm.grid_x, ch = h / dm.grid_y;
  const rates = dm.cells.map(c => c.xg / c.shots);
  const maxRate = Math.min(0.35, Math.max(...rates));
  const rgb = hexToRgbArr(cssVar('--accent'));
  dm.cells.forEach(c => {
    const a = Math.min(0.95, Math.pow(Math.min(1, (c.xg / c.shots) / maxRate), 0.8) * 0.95);
    ctx.fillStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${a.toFixed(3)})`;
    ctx.fillRect(pad + c.bx * cw, pad + c.by * ch, cw + 0.5, ch + 0.5);
  });

  // Offensive half: boards, blue line, goal line, crease, net, faceoff circles.
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = cssVar('--line-2');
  ctx.beginPath();
  const r = 28 / 100 * w;
  ctx.moveTo(px(0), py(-42.5));
  ctx.arcTo(px(100), py(-42.5), px(100), py(42.5), r);
  ctx.arcTo(px(100), py(42.5), px(0), py(42.5), r);
  ctx.lineTo(px(0), py(42.5));
  ctx.stroke();
  ctx.strokeStyle = cssVar('--blue');
  ctx.beginPath(); ctx.moveTo(px(25), py(-42.5)); ctx.lineTo(px(25), py(42.5)); ctx.stroke();
  ctx.strokeStyle = cssVar('--red');
  ctx.beginPath(); ctx.moveTo(px(89), py(-40)); ctx.lineTo(px(89), py(40)); ctx.stroke();
  ctx.strokeRect(px(89), py(-3), px(93) - px(89), py(3) - py(-3));
  ctx.beginPath(); ctx.arc(px(89), py(0), 6 / 100 * w, Math.PI / 2, Math.PI * 1.5); ctx.stroke();
  ctx.strokeStyle = cssVar('--line-2');
  [-22, 22].forEach(fy => { ctx.beginPath(); ctx.arc(px(69), py(fy), 15 / 100 * w, 0, Math.PI * 2); ctx.stroke(); });
}

// ================================================================
// PLAYER IMPACT RATINGS
// ================================================================
const RATING_COMPONENTS = {
  ev_offense:      { label: 'EV offence',      color: '--blue' },
  ev_defense:      { label: 'EV defence',      color: '--purple' },
  shot_generation: { label: 'Shot generation', color: '--blue' },
  playmaking:      { label: 'Playmaking',      color: '--purple' },
  finishing:       { label: 'Finishing',       color: '--accent' },
  // Not --amber: the site theme maps it to the same colour as --accent.
  penalties:       { label: 'Penalties',       color: '--red' },
  faceoffs:        { label: 'Faceoffs',        color: '--green' },
};

function buildRatingsTabs() {
  const wrap = document.getElementById('ratings-tabs');
  wrap.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
    wrap.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentRatingsGroup = btn.dataset.group;
    renderRatings(currentSeasonId, currentRatingsGroup);
  }));
}

function renderRatings(seasonId, group) {
  const s = RATINGS && RATINGS.by_season[seasonId];
  const note = document.getElementById('ratings-note');
  destroyChart('chart-ratings');
  if (!s) {
    emptyTable('ratings-table', 'No ratings for this season (it needs play-by-play and ice-time data).');
    note.textContent = '';
    return;
  }
  const ctx = document.getElementById('chart-ratings').getContext('2d');
  const table = document.getElementById('ratings-table');

  if (group === 'G') {
    const maxShots = Math.max(1, ...s.goalies.map(g => g.shots));
    const rows = s.goalies.filter(g => g.shots >= Math.max(30, maxShots * 0.1));
    const top = rows.slice(0, 15);
    document.getElementById('ratings-chart-title').textContent = 'Goalies: goals saved above expected';
    trackChart(new Chart(ctx, {
      type: 'bar',
      data: { labels: top.map(g => g.name), datasets: [{ label: 'GSAx', data: top.map(g => g.gsax),
        backgroundColor: top.map(g => g.gsax >= 0 ? cssVar('--green') : cssVar('--red')) }] },
      options: baseOptions({ indexAxis: 'y', plugins: { legend: { display: false } } }),
    }));
    table.innerHTML = `
      <thead><tr><th>#</th><th>Goalie</th><th>Team</th><th>Shots</th><th>GSAx</th></tr></thead>
      <tbody>${rows.map((g, i) => `<tr><td class="rank-badge">${i+1}</td><td>${plLink(g.player_id, g.name)}</td>
        <td>${teamDot(g.team_code)}${esc(g.team_code)}</td><td>${fmt(g.shots)}</td><td class="pts-cell">${signedCell(g.gsax)}</td></tr>`).join('')}</tbody>`;
    collapseRows(table, 15, 'goalies');
    note.textContent = 'Goalie ratings are GSAx from the expected-goals model. Minimum 10% of the season\'s top shot load.';
    return;
  }

  const th = awardsThresholds(s.skaters);
  const rows = s.skaters.filter(r => r.gp >= th.minGp && (group === 'all' || r.pos === group));
  const keys = Object.keys(RATING_COMPONENTS).filter(k => s.skaters.length && k in s.skaters[0].components);
  const top = rows.slice(0, 15);
  document.getElementById('ratings-chart-title').textContent = 'Top 15: where the value comes from (goals)';
  trackChart(new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top.map(r => `${r.name} (${r.team_code})`),
      datasets: keys.map(k => ({ label: RATING_COMPONENTS[k].label, data: top.map(r => r.components[k]),
        backgroundColor: cssVar(RATING_COMPONENTS[k].color) })),
    },
    options: baseOptions({
      indexAxis: 'y',
      scales: {
        x: { stacked: true, ticks: { color: cssVar('--ink-3'), font: { size: 10 } }, grid: { color: cssVar('--line') } },
        y: { stacked: true, ticks: { color: cssVar('--ink-3'), font: { size: 10 } }, grid: { color: cssVar('--line') } },
      },
    }),
  }));
  table.innerHTML = `
    <thead><tr><th>#</th><th>Player</th><th>Team</th><th>Pos</th><th>GP</th>
      ${keys.map(k => `<th>${esc(RATING_COMPONENTS[k].label)}</th>`).join('')}<th>Total</th><th>Per 30 GP</th></tr></thead>
    <tbody>${rows.map((r, i) => `<tr><td class="rank-badge">${i+1}</td><td>${plLink(r.player_id, r.name)}</td>
      <td>${teamDot(r.team_code)}${esc(r.team_code)}</td><td>${esc(r.pos)}</td><td>${fmt(r.gp)}</td>
      ${keys.map(k => `<td>${signed2(r.components[k])}</td>`).join('')}
      <td class="pts-cell">${signedCell(r.total)}</td><td>${signed2(r.per30)}</td></tr>`).join('')}</tbody>`;
  collapseRows(table, 15, 'players');

  note.textContent = s.model === 'full'
    ? `Full model: on-ice lists cover ${(s.onice_coverage * 100).toFixed(0)}% of this season's shots, so even-strength `
      + `offence/defence come from a regression on every skater on the ice. Minimum ${th.minGp} GP. `
      + `A power-play goal was worth ${s.pp_goals_per_minor} per minor penalty this season.`
    : `Box-score estimate: the feed has no on-ice lists for this season, so shot generation and playmaking `
      + `stand in for on-ice impact. Not directly comparable with full-model seasons. Minimum ${th.minGp} GP.`;
}

function renderAttendance(seasonId) {
  const all = GAMES[seasonId] || [];
  const games = all.filter(g => g.attendance);
  const home = games.filter(g => !g.takeover), tko = games.filter(g => g.takeover);
  const sum = (arr, f) => arr.reduce((a, g) => a + (f(g) || 0), 0);
  const capPct = arr => { const c = arr.filter(g => g.capacity); const cap = sum(c, g => g.capacity); return cap ? 100 * sum(c, g => g.attendance) / cap : null; };
  const pctTxt = v => v == null ? '—' : Math.round(v) + '%';
  const city = g => (g.venue || '').split('|')[1]?.trim() || (g.venue || '').split(' - ')[0];
  const shortDay = d => (d || '').replace(/^\w+,\s*/, '').replace(/\s+/g, ' ');
  const gameTip = g => `${shortDay(g.date)} · ${g.away_code || g.away} @ ${g.home_code || g.home} · ${g.venue}: `
    + `${fmt(g.attendance)}${g.capacity ? ` (${pctTxt(100 * g.attendance / g.capacity)} of ${fmt(g.capacity)})` : ''}`;

  const biggest = games.reduce((b, g) => !b || g.attendance > b.attendance ? g : b, null);
  document.getElementById('attendance-stats').innerHTML = [
    [fmt(sum(games, g => g.attendance)), `TOTAL ATTENDANCE · ${games.length} GAMES`],
    [home.length ? fmt(Math.round(sum(home, g => g.attendance) / home.length)) : '—', `AVG HOME-MARKET GAME · ${pctTxt(capPct(home))} FULL`],
    [tko.length ? fmt(Math.round(sum(tko, g => g.attendance) / tko.length)) : '—', `AVG TAKEOVER / NEUTRAL GAME · ${tko.length} GAMES`],
    [biggest ? fmt(biggest.attendance) : '—', biggest ? `BIGGEST CROWD · ${city(biggest).toUpperCase()}` : 'BIGGEST CROWD'],
  ].map(([num, lbl]) => `<div class="stat"><div class="num">${num}</div><div class="lbl">${esc(lbl)}</div></div>`).join('');

  // Per team (credited to the home team).
  const codes = [...new Set(games.map(g => g.home_code).filter(Boolean))];
  const teams = codes.map(code => {
    const h = home.filter(g => g.home_code === code), t = tko.filter(g => g.home_code === code);
    return { code, home: sum(h, g => g.attendance), tko: sum(t, g => g.attendance), nHome: h.length,
             avgHome: h.length ? sum(h, g => g.attendance) / h.length : null, pct: capPct(h) };
  });
  const byTotal = teams.slice().sort((a, b) => (b.home + b.tko) - (a.home + a.tko));
  const intAxis = { ticks: { color: cssVar('--ink-3'), font: { size: 10 }, callback: v => v >= 1000 ? (v / 1000) + 'k' : v }, grid: { color: cssVar('--line') } };
  const catAxis = { ticks: { color: cssVar('--ink-2'), font: { size: 11 } }, grid: { display: false } };

  destroyChart('chart-att-total');
  trackChart(new Chart(document.getElementById('chart-att-total').getContext('2d'), {
    type: 'bar',
    data: {
      labels: byTotal.map(t => t.code),
      datasets: [
        { label: 'Home market', data: byTotal.map(t => t.home), backgroundColor: byTotal.map(t => teamColor(t.code)) },
        { label: 'Takeover / neutral site', data: byTotal.map(t => t.tko), backgroundColor: byTotal.map(t => stripedFill(teamColor(t.code))) },
      ],
    },
    options: baseOptions({
      indexAxis: 'y',
      plugins: { legend: pairedLegend(),
        tooltip: { callbacks: { footer: items => 'Total ' + fmt(byTotal[items[0].dataIndex].home + byTotal[items[0].dataIndex].tko) } },
        barLabels: { format: (_v, i) => fmt(byTotal[i].home + byTotal[i].tko), outside: true, size: 10.5 } },
      scales: { x: { stacked: true, ...intAxis, grace: '12%' }, y: { stacked: true, ...catAxis } },
    }),
  }));

  const byPct = teams.filter(t => t.pct != null).sort((a, b) => b.pct - a.pct);
  destroyChart('chart-att-capacity');
  trackChart(new Chart(document.getElementById('chart-att-capacity').getContext('2d'), {
    type: 'bar',
    data: {
      labels: byPct.map(t => t.code),
      datasets: [{ label: '% of capacity', data: byPct.map(t => t.pct), backgroundColor: byPct.map(t => teamColor(t.code)), borderRadius: 3 }],
    },
    options: baseOptions({
      indexAxis: 'y',
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: c => `${pctTxt(c.raw)} full · avg ${fmt(Math.round(byPct[c.dataIndex].avgHome))} over ${byPct[c.dataIndex].nHome} games` } },
        barLabels: { format: (v, i) => `${pctTxt(v)} · avg ${fmt(Math.round(byPct[i].avgHome))}`, size: 10.5 } },
      scales: { x: { min: 0, suggestedMax: 100, ticks: { color: cssVar('--ink-3'), font: { size: 10 }, callback: v => v + '%' }, grid: { color: cssVar('--line') } }, y: catAxis },
    }),
  }));

  document.getElementById('att-home-title').textContent = `Home-market games, in schedule order (${home.length})`;
  destroyChart('chart-attendance');
  trackChart(new Chart(document.getElementById('chart-attendance').getContext('2d'), {
    type: 'bar',
    data: {
      labels: home.map(g => `${g.away_code || g.away} @ ${g.home_code || g.home}`),
      datasets: [{ label: 'Attendance', data: home.map(g => g.attendance), backgroundColor: home.map(g => teamColor(g.home_code)) }],
    },
    options: baseOptions({
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: () => '', label: c => gameTip(home[c.dataIndex]) } } },
      scales: { x: { display: false }, y: intAxis },
    }),
  }));

  // One bar per takeover game; the card grows with the game count so the
  // labels never need a scroll box.
  document.getElementById('att-takeover-title').textContent = `Takeover Tour & neutral-site games (${tko.length})`;
  document.getElementById('att-takeover-wrap').style.height = Math.max(120, tko.length * 24 + 40) + 'px';
  destroyChart('chart-att-takeover');
  trackChart(new Chart(document.getElementById('chart-att-takeover').getContext('2d'), {
    type: 'bar',
    data: {
      labels: tko.map(g => `${city(g)} · ${g.away_code || g.away} @ ${g.home_code || g.home}`),
      datasets: [{ label: 'Attendance', data: tko.map(g => g.attendance), backgroundColor: tko.map(g => teamColor(g.home_code)), borderRadius: 3 }],
    },
    options: baseOptions({
      indexAxis: 'y',
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: () => '', label: c => gameTip(tko[c.dataIndex]) } },
        barLabels: { format: (v, i) => tko[i].capacity ? `${fmt(v)} · ${pctTxt(100 * v / tko[i].capacity)}` : fmt(v), size: 10.5 } },
      scales: { x: { ...intAxis, grace: '5%' }, y: { ticks: { color: cssVar('--ink-2'), font: { size: 10.5 } }, grid: { display: false } } },
    }),
  }));

  const noAtt = all.length - games.length;
  const noCap = games.filter(g => !g.capacity).length;
  document.getElementById('attendance-note').textContent =
    `Attendance is credited to the home team. % of capacity uses home-market games at venues with a listed capacity.`
    + (noAtt ? ` ${noAtt} game${noAtt === 1 ? '' : 's'} with no reported attendance left out.` : '')
    + (noCap ? ` ${noCap} game${noCap === 1 ? '' : 's'} at a venue with no listed capacity.` : '');
}

// ================================================================
// TRANSACTIONS
// ================================================================
function renderTransactions() {
  const types = Object.entries(TXN.by_type).slice(0, 10);
  destroyChart('chart-txn-type');
  const ctx = document.getElementById('chart-txn-type').getContext('2d');
  trackChart(new Chart(ctx, {
    type: 'bar',
    data: { labels: types.map(t => t[0]), datasets: [{ label: 'Count', data: types.map(t => t[1]), backgroundColor: cssVar('--purple') }] },
    options: baseOptions({ indexAxis: 'y', plugins: { legend: { display: false } } }),
  }));

  const list = document.getElementById('txn-list');
  list.innerHTML = TXN.recent.map(t => {
    const isAdd = (t.ttype_text || '').toUpperCase() === 'ADD';
    return `<div class="txn-row">
      <span class="txn-date">${esc((t.transaction_date||'').slice(0,10))}</span>
      <span class="txn-tag ${isAdd?'add':'del'}">${esc(t.detail || t.ttype_text || '')}</span>
      <span>${esc(t.player_name || '')} — ${esc(t.team_name || '')}</span>
    </div>`;
  }).join('');
  collapseRows(list, 8, 'transactions');
}

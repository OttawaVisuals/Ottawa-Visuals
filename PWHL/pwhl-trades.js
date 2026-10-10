// Team-to-team movements confirmed by paired transaction records.
let tradeSeasonId = 'all';
let tradeSelection = null;
const TRADE_TEAM_ORDER = ['SEA', 'BOS', 'NY', 'MTL', 'TOR', 'OTT', 'VAN', 'MIN'];

function tradeMoves() {
  const moves = TXN.trade_moves || [];
  return tradeSeasonId === 'all' ? moves : moves.filter(m => m.season_id === tradeSeasonId);
}

function tradeTeams(moves) {
  const seasons = [...new Set(moves.map(m => m.season_id))].sort((a, b) => Number(a) - Number(b));
  const teams = new Map();
  seasons.forEach(sid => (META.teams_by_season[sid] || []).forEach(t => teams.set(t.code, t)));
  moves.forEach(m => [m.from, m.to].forEach(code => {
    if (!teams.has(code)) teams.set(code, { code, name: code });
  }));
  return [...teams.values()].sort((a, b) => {
    const ai = TRADE_TEAM_ORDER.indexOf(a.code), bi = TRADE_TEAM_ORDER.indexOf(b.code);
    return (ai < 0 ? 100 : ai) - (bi < 0 ? 100 : bi) || a.code.localeCompare(b.code);
  });
}

function tradeCurve(a, b, paired) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const length = Math.hypot(dx, dy);
  const ux = dx / length, uy = dy / length;
  const sx = a.x + ux * 35, sy = a.y + uy * 35;
  const ex = b.x - ux * 40, ey = b.y - uy * 40;
  const bend = paired ? 48 : 0;
  const cx = (sx + ex) / 2 - uy * bend;
  const cy = (sy + ey) / 2 + ux * bend;
  return {
    path: `M ${sx.toFixed(1)} ${sy.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`,
    labelX: ((sx + 2 * cx + ex) / 4).toFixed(1),
    labelY: ((sy + 2 * cy + ey) / 4).toFixed(1),
  };
}

function renderTradeNetwork() {
  const host = document.getElementById('trade-network');
  const detail = document.getElementById('trade-details');
  if (!host || !detail) return;
  const moves = tradeMoves();
  if (!moves.length) {
    host.innerHTML = '<p class="trade-empty">No matched team-to-team trades for this season.</p>';
    detail.innerHTML = '';
    return;
  }
  const teams = tradeTeams(moves);
  const positions = new Map(teams.map((t, i) => {
    const angle = -Math.PI / 2 + i * 2 * Math.PI / teams.length;
    return [t.code, { x: 460 + 330 * Math.cos(angle), y: 220 + 157 * Math.sin(angle) }];
  }));
  const flows = new Map();
  moves.forEach(m => {
    const key = `${m.from}|${m.to}`;
    if (!flows.has(key)) flows.set(key, { from: m.from, to: m.to, count: 0 });
    flows.get(key).count++;
  });
  const flowList = [...flows.values()];
  const activeCodes = new Set(moves.flatMap(m => [m.from, m.to]));
  const selectedTeam = tradeSelection?.type === 'team' ? tradeSelection.code : null;
  const selectedFlow = tradeSelection?.type === 'flow' ? `${tradeSelection.from}|${tradeSelection.to}` : null;
  const defs = [...new Set(flowList.map(f => f.from))].map(code =>
    `<marker id="trade-arrow-${esc(code)}" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><path d="M 0 0 L 12 6 L 0 12 Z" fill="${teamColor(code)}"/></marker>`).join('');
  const edges = flowList.map(f => {
    const key = `${f.from}|${f.to}`;
    const curve = tradeCurve(positions.get(f.from), positions.get(f.to), flows.has(`${f.to}|${f.from}`));
    const muted = (selectedTeam && f.from !== selectedTeam && f.to !== selectedTeam)
      || (selectedFlow && key !== selectedFlow);
    return `<g class="trade-flow${muted ? ' muted' : ''}${selectedFlow === key ? ' selected' : ''}" data-trade-flow="${esc(key)}">
      <title>${esc(f.from)} → ${esc(f.to)}: ${f.count} player ${f.count === 1 ? 'move' : 'moves'}</title>
      <path class="trade-hit" d="${curve.path}"/>
      <path class="trade-line" d="${curve.path}" stroke="${teamColor(f.from)}" stroke-width="${Math.min(7, 2.5 + f.count)}" marker-end="url(#trade-arrow-${esc(f.from)})"/>
      <g class="trade-flow-control" role="button" tabindex="0" aria-label="${esc(f.from)} to ${esc(f.to)}, ${f.count} player ${f.count === 1 ? 'move' : 'moves'}">
        <circle class="trade-count-bg" cx="${curve.labelX}" cy="${curve.labelY}" r="12"/>
        <text class="trade-count" x="${curve.labelX}" y="${curve.labelY}">${f.count}</text>
      </g>
    </g>`;
  }).join('');
  const nodes = teams.map(t => {
    const p = positions.get(t.code), active = activeCodes.has(t.code);
    const muted = (selectedTeam && t.code !== selectedTeam) || (selectedFlow && !selectedFlow.split('|').includes(t.code));
    return `<g class="trade-node${active ? '' : ' inactive'}${muted ? ' muted' : ''}${selectedTeam === t.code ? ' selected' : ''}" role="button" tabindex="0" data-trade-team="${esc(t.code)}" aria-label="${esc(t.name || t.code)}${active ? '' : ', no matched trades'}" transform="translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})">
      <title>${esc(t.name || t.code)}${active ? '' : ' · no matched trades'}</title>
      <circle r="29" fill="${teamColor(t.code)}"/>
      <text fill="${inkOn(teamColor(t.code))}">${esc(t.code)}</text>
    </g>`;
  }).join('');
  host.innerHTML = `<svg viewBox="0 0 920 440" role="group" aria-label="${moves.length} verified player moves between ${teams.length} teams">
    <defs>${defs}</defs>
    <ellipse class="trade-rink" cx="460" cy="220" rx="377" ry="200"/>
    <circle class="trade-centre-ring" cx="460" cy="220" r="59"/>
    <text class="trade-centre-number" x="460" y="216">${moves.length}</text>
    <text class="trade-centre-label" x="460" y="237">PLAYER ${moves.length === 1 ? 'MOVE' : 'MOVES'}</text>
    ${edges}${nodes}
  </svg>`;

  const shown = selectedTeam ? moves.filter(m => m.from === selectedTeam || m.to === selectedTeam)
    : selectedFlow ? moves.filter(m => `${m.from}|${m.to}` === selectedFlow) : moves;
  const label = selectedTeam ? `${selectedTeam} trades` : selectedFlow ? selectedFlow.replace('|', ' → ') : 'All verified trades';
  detail.innerHTML = `<div class="trade-detail-head"><div><strong>${esc(label)}</strong><span>${shown.length} player ${shown.length === 1 ? 'move' : 'moves'}</span></div>${tradeSelection ? '<button type="button" class="more-btn" data-trade-reset>Show all</button>' : ''}</div>
    <div class="trade-moves">${shown.map(m => `<div class="trade-move">
      <time datetime="${esc(m.date)}">${esc(m.date)}</time>
      <span class="trade-route">${teamDot(m.from)}${teamLink(m.from)} <span aria-hidden="true">→</span> ${teamDot(m.to)}${teamLink(m.to)}</span>
      ${plLink(m.player_id, m.player_name)}
    </div>`).join('')}</div>`;
}

function initTradeNetwork() {
  const select = document.getElementById('trade-season-select');
  const seasons = [...new Set((TXN.trade_moves || []).map(m => m.season_id))]
    .sort((a, b) => Number(b) - Number(a));
  select.innerHTML = '<option value="all">All seasons</option>'
    + seasons.map(sid => `<option value="${esc(sid)}">${esc(seasonName(sid))}</option>`).join('');
  select.addEventListener('change', () => {
    tradeSeasonId = select.value;
    tradeSelection = null;
    renderTradeNetwork();
  });
  const network = document.getElementById('trade-network');
  const choose = (target, refocus = false) => {
    const flow = target.closest('[data-trade-flow]');
    const team = target.closest('[data-trade-team]');
    if (flow) {
      const [from, to] = flow.dataset.tradeFlow.split('|');
      tradeSelection = { type: 'flow', from, to };
    } else if (team) {
      tradeSelection = { type: 'team', code: team.dataset.tradeTeam };
    } else return;
    renderTradeNetwork();
    if (refocus) {
      const controls = [...network.querySelectorAll('.trade-flow-control, .trade-node')];
      const selected = controls.find(el => flow
        ? el.closest('[data-trade-flow]')?.dataset.tradeFlow === `${tradeSelection.from}|${tradeSelection.to}`
        : el.dataset.tradeTeam === tradeSelection.code);
      selected?.focus();
    }
  };
  network.addEventListener('click', e => choose(e.target));
  network.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(e.target, true); }
  });
  document.getElementById('trade-details').addEventListener('click', e => {
    if (e.target.closest('[data-trade-reset]')) { tradeSelection = null; renderTradeNetwork(); }
  });
  renderTradeNetwork();
}

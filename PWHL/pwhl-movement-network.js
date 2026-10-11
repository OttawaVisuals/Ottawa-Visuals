let movementSelection = { type:'all' };
const MOVEMENT_ORDER = ['BOS','NY','MTL','TOR','OTT','MIN','VAN','SEA','DET','HAM','VGS','SJ'];
const MOVEMENT_ROLES = new Set(['Played','Signed']);

function movementTeam(code) { return MOVEMENT.teams.find(t => t.code === code) || { code, name:code }; }
function movementPlayer(id) { return MOVEMENT.players.find(p => p.id === id); }
function movementMembership(player, code) {
  return player.teams.find(m => m.team === code && MOVEMENT_ROLES.has(m.role));
}
function movementTeamPlayers(code) {
  return MOVEMENT.players.filter(p => movementMembership(p, code));
}
function movementHash(value) {
  let hash = 2166136261;
  for (const character of value) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}
function movementPositions(teams) {
  const dots = new Map(), centres = new Map();
  teams.forEach((team, teamIndex) => {
    const angle = -Math.PI / 2 + teamIndex * 2 * Math.PI / teams.length;
    const centre = { x:900 + 650 * Math.cos(angle), y:455 + 335 * Math.sin(angle) };
    centres.set(team.code, centre);
    const players = movementTeamPlayers(team.code);
    const rotation = movementHash(team.code) / 0xffffffff * 2 * Math.PI;
    players.forEach((player, index) => {
      const jitter = movementHash(`${team.code}|${player.id}`) / 0xffffffff;
      const radius = Math.sqrt((index + .5) / players.length) * 68 + (jitter - .5) * 4;
      const theta = index * 2.3999632297 + rotation + (jitter - .5) * .18;
      dots.set(`${team.code}|${player.id}`, {
        x:centre.x + radius * Math.cos(theta), y:centre.y + radius * Math.sin(theta),
      });
    });
  });
  return { dots, centres };
}
function movementShownMoves() {
  const s = movementSelection;
  return MOVEMENT.moves.map((move, index) => ({ move, index })).filter(({ move }) =>
    s.type === 'all' || s.type === 'team' && (move.from === s.code || move.to === s.code)
    || s.type === 'player' && move.player_id === s.id);
}
function movementArrow(from, to, move, index, chosen) {
  const dx = to.x - from.x, dy = to.y - from.y, length = Math.hypot(dx, dy);
  if (length < 20) return '';
  const ux = dx / length, uy = dy / length;
  const sx = from.x + ux * 7, sy = from.y + uy * 7;
  const ex = to.x - ux * 10, ey = to.y - uy * 10;
  const mx = sx + (ex - sx) * .5, my = sy + (ey - sy) * .5;
  const start = `M ${sx.toFixed(1)} ${sy.toFixed(1)} L ${mx.toFixed(1)} ${my.toFixed(1)}`;
  const finish = `M ${mx.toFixed(1)} ${my.toFixed(1)} L ${ex.toFixed(1)} ${ey.toFixed(1)}`;
  const path = `${start} L ${ex.toFixed(1)} ${ey.toFixed(1)}`;
  const player = movementPlayer(move.player_id);
  const label = `${player?.name || 'Player'}: ${move.from} to ${move.to}, ${move.kind === 'trade' ? 'recorded trade' : 'season roster change'}, ${move.date || move.period}`;
  return `<g class="mv-move${move.kind === 'trade' ? ' mv-trade' : ''}${chosen ? ' chosen' : ''}" role="button" tabindex="0" data-mv-move="${index}" aria-label="${esc(label)}">
    <title>${esc(label)}</title><path class="mv-move-hit" d="${path}"/>
    <path class="mv-move-line mv-move-from" d="${start}" stroke="${teamColor(move.from)}"/>
    <path class="mv-move-line mv-move-to" d="${finish}" stroke="${teamColor(move.to)}"/>
  </g>`;
}
function renderMovementNetwork() {
  const teams = [...MOVEMENT.teams].sort((a, b) => MOVEMENT_ORDER.indexOf(a.code) - MOVEMENT_ORDER.indexOf(b.code));
  const { dots, centres } = movementPositions(teams);
  const shownMoves = movementShownMoves();
  const activeTeams = new Set(shownMoves.flatMap(({ move }) => [move.from, move.to]));
  if (movementSelection.type === 'team') activeTeams.add(movementSelection.code);
  if (movementSelection.type === 'player') {
    movementPlayer(movementSelection.id)?.teams.filter(m => MOVEMENT_ROLES.has(m.role)).forEach(m => activeTeams.add(m.team));
  }
  const arrows = shownMoves.map(({ move, index }) => {
    const from = dots.get(`${move.from}|${move.player_id}`);
    const to = dots.get(`${move.to}|${move.player_id}`);
    return from && to ? movementArrow(from, to, move, index, movementSelection.moveIndex === index) : '';
  }).join('');
  const clusters = teams.map(team => {
    const centre = centres.get(team.code);
    const angle = Math.atan2((centre.y - 455) / 335, (centre.x - 900) / 650);
    const labelX = centre.x + 102 * Math.cos(angle);
    const labelY = centre.y + 102 * Math.sin(angle) + 7;
    const dim = movementSelection.type !== 'all' && !activeTeams.has(team.code);
    const points = movementTeamPlayers(team.code).map(player => {
      const point = dots.get(`${team.code}|${player.id}`);
      const selected = movementSelection.type === 'player' && movementSelection.id === player.id;
      return `<circle class="mv-player-dot${selected ? ' active' : ''}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="${selected ? 7 : 5}" fill="${teamColor(team.code)}" role="button" tabindex="0" data-mv-player="${esc(player.id)}" aria-label="${esc(player.name)}, ${esc(team.name)}"><title>${esc(player.name)} · ${esc(team.name)}</title></circle>`;
    }).join('');
    return `<g class="mv-team${dim ? ' dim' : ''}" data-mv-cluster="${esc(team.code)}">${points}
      <text class="mv-team-label" x="${labelX.toFixed(1)}" y="${labelY.toFixed(1)}" fill="${teamColor(team.code)}" role="button" tabindex="0" data-mv-team="${esc(team.code)}" aria-label="Show ${esc(team.name)} players">${esc(team.code)}</text>
    </g>`;
  }).join('');
  document.getElementById('movement-network').innerHTML = `<svg viewBox="0 0 1800 1000" role="group" aria-label="One dot per player who played or signed for a team; one line per team move, dotted at the source and solid at the destination">${arrows}${clusters}</svg>`;
}
function movementPersonButton(player, meta = '') {
  return `<button type="button" class="mv-person" data-mv-player="${esc(player.id)}"><span>${esc(player.name)}</span><small>${esc(meta)}</small></button>`;
}
function renderMovementDetail() {
  const box = document.getElementById('movement-detail');
  const title = document.getElementById('movement-detail-title');
  const sub = document.getElementById('movement-detail-sub');
  const s = movementSelection;
  if (s.type === 'team') {
    const team = movementTeam(s.code), players = movementTeamPlayers(s.code);
    const related = MOVEMENT.moves.filter(m => m.from === s.code || m.to === s.code);
    title.textContent = team.name;
    sub.textContent = `${players.length} players who played or signed · ${related.length} moves connected to this team`;
    box.innerHTML = `<div class="mv-people">${players.map(player => {
      const membership = movementMembership(player, s.code);
      return movementPersonButton(player, `${membership.periods.join(', ')} · ${membership.role}`);
    }).join('')}</div>`;
  } else if (s.type === 'player') {
    const player = movementPlayer(s.id);
    if (!player) return;
    const memberships = player.teams.filter(m => MOVEMENT_ROLES.has(m.role));
    const moves = MOVEMENT.moves.map((move, index) => ({ move, index })).filter(({ move }) => move.player_id === player.id);
    title.textContent = player.name;
    sub.textContent = s.moveIndex == null ? `${memberships.length} team${memberships.length === 1 ? '' : 's'} played or signed for`
      : `${MOVEMENT.moves[s.moveIndex].from} → ${MOVEMENT.moves[s.moveIndex].to} · ${MOVEMENT.moves[s.moveIndex].kind === 'trade' ? 'Recorded trade' : 'Season roster change'}`;
    box.innerHTML = `<h3>Teams</h3><div class="mv-journey">${memberships.map(m => `<div>${teamDot(m.team)}<strong>${esc(movementTeam(m.team).name)}</strong><span>${m.periods.map(esc).join(', ')} · ${esc(m.role)}</span></div>`).join('')}</div>
      <h3>Moves</h3><div class="mv-journey">${moves.map(({ move, index }) => `<div class="${s.moveIndex === index ? 'mv-selected-move' : ''}"><strong>${esc(move.from)} → ${esc(move.to)}</strong><span>${esc(move.date || move.period)} · ${move.kind === 'trade' ? 'Recorded trade' : 'Change between season rosters'}</span></div>`).join('') || '<p class="note">No team-to-team move is confirmed by the available records.</p>'}</div>`;
  } else {
    title.textContent = 'All teams';
    sub.textContent = 'Select a player dot or line to see her path. Select a team name to focus its moves.';
    box.innerHTML = `<div class="mv-team-list">${MOVEMENT.teams.map(team => `<button type="button" data-mv-team="${esc(team.code)}" style="--tc:${teamColor(team.code)}"><strong>${esc(team.name)}</strong><span>${movementTeamPlayers(team.code).length} players</span></button>`).join('')}</div>`;
  }
}
function renderMovementPage() {
  const visiblePlayers = MOVEMENT.players.filter(p => p.teams.some(m => MOVEMENT_ROLES.has(m.role)));
  const memberships = visiblePlayers.reduce((n, p) => n + p.teams.filter(m => MOVEMENT_ROLES.has(m.role)).length, 0);
  document.getElementById('movement-stats').innerHTML = [
    [visiblePlayers.length, 'PLAYED OR SIGNED'], [memberships, 'PLAYER DOTS'],
    [MOVEMENT.moves.length, 'PLAYER MOVES'],
    [MOVEMENT.moves.filter(m => m.kind === 'trade').length, 'RECORDED TRADES'],
  ].map(([n, label]) => `<div class="stat"><div class="num">${n}</div><div class="lbl">${label}</div></div>`).join('');
  document.getElementById('movement-team-select').value = movementSelection.type === 'team' ? movementSelection.code : 'all';
  renderMovementNetwork();
  renderMovementDetail();
}
function initMovementPage() {
  const select = document.getElementById('movement-team-select');
  select.innerHTML = '<option value="all">All teams</option>' + MOVEMENT.teams.map(team => `<option value="${esc(team.code)}">${esc(team.name)}</option>`).join('');
  document.getElementById('movement-search-list').innerHTML = MOVEMENT.players.filter(p => p.teams.some(m => MOVEMENT_ROLES.has(m.role))).map(p => `<option value="${esc(p.name)}"></option>`).join('');
  select.addEventListener('change', () => {
    movementSelection = select.value === 'all' ? { type:'all' } : { type:'team', code:select.value };
    renderMovementPage();
  });
  document.getElementById('movement-show-all').addEventListener('click', () => {
    movementSelection = { type:'all' }; renderMovementPage();
  });
  const choose = (target, keyboard = false) => {
    const player = target.closest('[data-mv-player]');
    const arrow = target.closest('[data-mv-move]');
    const team = target.closest('[data-mv-team]');
    if (player) movementSelection = { type:'player', id:player.dataset.mvPlayer };
    else if (arrow) {
      const moveIndex = Number(arrow.dataset.mvMove);
      movementSelection = { type:'player', id:MOVEMENT.moves[moveIndex].player_id, moveIndex };
    } else if (team) movementSelection = { type:'team', code:team.dataset.mvTeam };
    else return;
    renderMovementPage();
    if (keyboard) {
      const focus = movementSelection.moveIndex != null ? `[data-mv-move="${movementSelection.moveIndex}"]`
        : movementSelection.type === 'player' ? `[data-mv-player="${movementSelection.id}"]`
        : `[data-mv-team="${movementSelection.code}"]`;
      document.querySelector('#movement-network ' + focus)?.focus();
    }
  };
  const network = document.getElementById('movement-network');
  network.addEventListener('click', e => choose(e.target));
  network.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(e.target, true); }
  });
  document.getElementById('movement-detail').addEventListener('click', e => choose(e.target));
  document.getElementById('movement-search').addEventListener('submit', e => {
    e.preventDefault();
    const input = document.getElementById('movement-search-input');
    const query = input.value.trim().toLocaleLowerCase();
    const players = MOVEMENT.players.filter(p => p.teams.some(m => MOVEMENT_ROLES.has(m.role)));
    const match = players.find(p => p.name.toLocaleLowerCase() === query) || players.find(p => p.name.toLocaleLowerCase().includes(query));
    if (match) { movementSelection = { type:'player', id:match.id }; renderMovementPage(); }
    else { input.setCustomValidity('Choose a player from the list.'); input.reportValidity(); }
  });
  document.getElementById('movement-search-input').addEventListener('input', e => e.target.setCustomValidity(''));
  renderMovementPage();
}

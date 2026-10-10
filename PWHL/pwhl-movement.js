let movementSelection = { type:'team', code:'OTT' };
const MOVEMENT_ORDER = ['BOS','NY','MTL','TOR','OTT','MIN','VAN','SEA','DET','HAM','VGS','SJ'];
const MOVEMENT_CENTRE = { x:650, y:350 };
const MOVEMENT_EXIT = { x:1220, y:650 };

function movementTeam(code) {
  return MOVEMENT.teams.find(t => t.code === code) || { code, name:code };
}
function movementPlayer(id) {
  return MOVEMENT.players.find(p => p.id === id);
}
function movementTeamCount(code) {
  return MOVEMENT.players.filter(p => p.teams.some(t => t.team === code)).length;
}
function movementVisibleRows() {
  const s = movementSelection;
  const match = row => s.type === 'all' || s.type === 'team' && (row.from === s.code || row.to === s.code)
    || s.type === 'player' && row.player_id === s.id
    || s.type === 'flow' && s.kind === 'move' && row.from === s.from && row.to === s.to;
  return {
    entries: MOVEMENT.entries.filter(e => s.type === 'pool' || s.type === 'all'
      || s.type === 'team' && e.to === s.code || s.type === 'player' && e.player_id === s.id
      || s.type === 'flow' && s.kind === 'entry' && e.to === s.to),
    moves: MOVEMENT.moves.filter(m => s.type !== 'pool' && s.type !== 'retired' && match(m)),
    retirements: MOVEMENT.retirements.filter(r => s.type === 'retired' || s.type === 'all'
      || s.type === 'team' && r.from === s.code || s.type === 'player' && r.player_id === s.id
      || s.type === 'flow' && s.kind === 'retired' && r.from === s.from),
  };
}
function movementGroups(rows, key) {
  const grouped = new Map();
  rows.forEach(row => {
    const k = key(row);
    if (!grouped.has(k)) grouped.set(k, []);
    grouped.get(k).push(row);
  });
  return grouped;
}
function movementPath(a, b, fromRadius, toRadius, bend = 0) {
  const dx = b.x - a.x, dy = b.y - a.y, distance = Math.hypot(dx, dy);
  const ux = dx / distance, uy = dy / distance;
  const sx = a.x + ux * fromRadius, sy = a.y + uy * fromRadius;
  const ex = b.x - ux * toRadius, ey = b.y - uy * toRadius;
  const cx = (sx + ex) / 2 - uy * bend, cy = (sy + ey) / 2 + ux * bend;
  return {
    d:`M ${sx.toFixed(1)} ${sy.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`,
    x:((sx + 2 * cx + ex) / 4).toFixed(1),
    y:((sy + 2 * cy + ey) / 4).toFixed(1),
  };
}
function movementFlow(path, kind, key, count, label, color, marker) {
  const identity = `${esc(kind)}|${esc(key)}`;
  return { count, edge:`<g class="mv-flow mv-${kind}" data-mv-flow="${identity}">
    <title>${esc(label)}: ${count} player${count === 1 ? '' : 's'}</title>
    <path class="mv-hit" d="${path.d}"/>
    <path class="mv-line" d="${path.d}" stroke="${color}" stroke-width="${Math.min(8, 2.4 + Math.sqrt(count))}" marker-end="url(#${marker})"/>
  </g>`, control:`<g class="mv-count-control" role="button" tabindex="0" data-mv-flow="${identity}" aria-label="${esc(label)}, ${count} player${count === 1 ? '' : 's'}">
      <circle class="mv-count-bg" cx="${path.x}" cy="${path.y}" r="13"/>
      <text class="mv-count" x="${path.x}" y="${path.y}">${count}</text>
    </g>` };
}

function renderMovementNetwork() {
  const host = document.getElementById('movement-network');
  const teams = [...MOVEMENT.teams].sort((a, b) => MOVEMENT_ORDER.indexOf(a.code) - MOVEMENT_ORDER.indexOf(b.code));
  const positions = new Map(teams.map((t, i) => {
    const angle = -Math.PI / 2 + i * 2 * Math.PI / teams.length;
    return [t.code, { x:650 + 470 * Math.cos(angle), y:350 + 250 * Math.sin(angle) }];
  }));
  const shown = movementVisibleRows();
  const entryGroups = movementGroups(shown.entries, e => e.to);
  const moveGroups = movementGroups(shown.moves, m => `${m.from}|${m.to}`);
  const retireGroups = movementGroups(shown.retirements, r => r.from);
  const highlighted = new Set([...shown.entries.map(e => e.to),
    ...shown.moves.flatMap(m => [m.from, m.to]), ...shown.retirements.map(r => r.from)]);
  const defs = `<marker id="mv-entry-arrow" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0 L12 6 L0 12 Z" fill="var(--purple)"/></marker>
    <marker id="mv-retired-arrow" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0 L12 6 L0 12 Z" fill="var(--ink-3)"/></marker>
    ${[...new Set(shown.moves.map(m => m.from))].map(code => `<marker id="mv-arrow-${esc(code)}" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0 L12 6 L0 12 Z" fill="${teamColor(code)}"/></marker>`).join('')}`;
  const entries = [...entryGroups].map(([code, rows]) => movementFlow(
    movementPath(MOVEMENT_CENTRE, positions.get(code), 70, 45), 'entry', `POOL|${code}`,
    rows.length, `New to PWHL to ${code}`, 'var(--purple)', 'mv-entry-arrow'));
  const moves = [...moveGroups].map(([key, rows]) => {
    const [from, to] = key.split('|');
    const bend = moveGroups.has(`${to}|${from}`) ? 60 : 35;
    return movementFlow(movementPath(positions.get(from), positions.get(to), 44, 49, bend),
      'move', key, rows.length, `${from} to ${to}`, teamColor(from), `mv-arrow-${from}`);
  });
  const retired = [...retireGroups].map(([code, rows]) => movementFlow(
    movementPath(positions.get(code), MOVEMENT_EXIT, 44, 56, 30), 'retired', `${code}|EXIT`,
    rows.length, `${code} retirement recorded`, 'var(--ink-3)', 'mv-retired-arrow'));
  const flows = [...entries, ...moves, ...retired];
  const nodes = teams.map(t => {
    const p = positions.get(t.code), count = movementTeamCount(t.code);
    const dim = movementSelection.type !== 'all' && !highlighted.has(t.code);
    return `<g class="mv-team${dim ? ' dim' : ''}${movementSelection.type === 'team' && movementSelection.code === t.code ? ' selected' : ''}" role="button" tabindex="0" data-mv-team="${esc(t.code)}" aria-label="${esc(t.name)}, ${count} roster-listed players" transform="translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})">
      <title>${esc(t.name)} · ${count} roster-listed players</title>
      <circle r="43" fill="${teamColor(t.code)}"/>
      <text class="mv-team-code" fill="${inkOn(teamColor(t.code))}" y="-5">${esc(t.code)}</text>
      <text class="mv-team-count" fill="${inkOn(teamColor(t.code))}" y="16">${count}</text>
    </g>`;
  }).join('');
  const badgeFlows = movementSelection.type === 'all' ? flows.filter(f => f.count >= 5) : flows;
  host.innerHTML = `<svg class="${movementSelection.type === 'all' ? 'mv-overview' : ''}" viewBox="0 0 1360 770" role="group" aria-label="Movement among ${teams.length} PWHL team rosters">
    <defs>${defs}</defs>
    <ellipse class="mv-ring" cx="650" cy="350" rx="520" ry="305"/>
    ${flows.map(f => f.edge).join('')}${nodes}${badgeFlows.map(f => f.control).join('')}
    <g class="mv-pool${movementSelection.type === 'pool' ? ' selected' : ''}" role="button" tabindex="0" data-mv-pool aria-label="New to PWHL, ${MOVEMENT.entries.length} first roster entries" transform="translate(650 350)">
      <title>Draft, signing, and other first roster entries</title>
      <circle r="68"/><text y="-13" class="mv-pool-number">${MOVEMENT.entries.length}</text><text y="10">NEW TO PWHL</text><text y="27">DRAFT · SIGNING · OTHER</text>
    </g>
    <g class="mv-exit${movementSelection.type === 'retired' ? ' selected' : ''}" role="button" tabindex="0" data-mv-retired aria-label="${MOVEMENT.retirements.length} recorded retirement events" transform="translate(1220 650)">
      <title>Recorded retirement events; later roster appearances are flagged below</title>
      <circle r="54"/><text y="-6" class="mv-exit-number">${MOVEMENT.retirements.length}</text><text y="15">RETIRED</text>
    </g>
  </svg>`;
}

function movementPersonButton(p, meta = '') {
  return `<button type="button" class="mv-person" data-mv-player="${esc(p.id)}"><span>${esc(p.name)}</span><small>${esc(meta)}</small></button>`;
}
function renderMovementDetail() {
  const box = document.getElementById('movement-detail');
  const title = document.getElementById('movement-detail-title');
  const sub = document.getElementById('movement-detail-sub');
  const s = movementSelection;
  if (s.type === 'team') {
    const team = movementTeam(s.code);
    const players = MOVEMENT.players.filter(p => p.teams.some(m => m.team === s.code));
    const related = MOVEMENT.moves.filter(m => m.from === s.code || m.to === s.code);
    title.textContent = `${team.name} roster history`;
    sub.textContent = `${players.length} roster-listed players · ${related.length} recorded or inferred team moves`;
    box.innerHTML = `<div class="mv-people">${players.map(p => {
      const m = p.teams.find(x => x.team === s.code);
      return movementPersonButton(p, `${m.periods.join(', ')} · ${m.role}`);
    }).join('')}</div>`;
  } else if (s.type === 'player') {
    const p = movementPlayer(s.id);
    if (!p) return;
    const entries = MOVEMENT.entries.filter(e => e.player_id === p.id);
    const moves = MOVEMENT.moves.filter(m => m.player_id === p.id);
    const retirements = MOVEMENT.retirements.filter(r => r.player_id === p.id);
    title.textContent = p.name;
    sub.textContent = `${p.teams.length} team roster${p.teams.length === 1 ? '' : 's'} recorded`;
    box.innerHTML = `<h3>Teams listed</h3><div class="mv-journey">${p.teams.map(m => `<div>${teamDot(m.team)}<strong>${esc(movementTeam(m.team).name)}</strong><span>${m.periods.map(esc).join(', ')} · ${esc(m.role)}</span></div>`).join('')}</div>
      <h3>Movement evidence</h3><div class="mv-journey">${[
        ...entries.map(e => `<div><strong>New to PWHL → ${esc(e.to)}</strong><span>${esc(e.period)} · ${esc(e.kind === 'draft' ? 'Draftee' : e.kind === 'signing' ? 'Signing' : 'Other roster entry')}</span></div>`),
        ...moves.map(m => `<div><strong>${esc(m.from)} → ${esc(m.to)}</strong><span>${esc(m.date || m.period)} · ${m.kind === 'trade' ? 'Recorded trade' : 'Change between season rosters'}</span></div>`),
        ...retirements.map(r => `<div><strong>${esc(r.from)} → Retirement recorded</strong><span>${esc(r.date)}${r.later_roster ? ' · later roster appearance' : ''}</span></div>`),
      ].join('') || '<p class="note">No directional move is confirmed by the available records.</p>'}</div>`;
  } else if (s.type === 'flow') {
    let rows, heading;
    if (s.kind === 'entry') {
      rows = MOVEMENT.entries.filter(e => e.to === s.to);
      heading = `New to PWHL → ${s.to}`;
    } else if (s.kind === 'retired') {
      rows = MOVEMENT.retirements.filter(r => r.from === s.from);
      heading = `${s.from} → Retirement recorded`;
    } else {
      rows = MOVEMENT.moves.filter(m => m.from === s.from && m.to === s.to);
      heading = `${s.from} → ${s.to}`;
    }
    title.textContent = heading;
    sub.textContent = `${rows.length} player${rows.length === 1 ? '' : 's'}`;
    box.innerHTML = `<div class="mv-people">${rows.map(r => {
      const p = movementPlayer(r.player_id);
      const meta = s.kind === 'retired' ? `${r.date} · Retirement${r.later_roster ? ' (later roster)' : ''}`
        : s.kind === 'entry' ? `${r.period} · ${r.kind === 'draft' ? 'Draft' : r.kind === 'signing' ? 'Signing' : 'Other entry'}`
        : `${r.date || r.period} · ${r.kind === 'trade' ? 'Trade' : 'Roster change'}`;
      return p ? movementPersonButton(p, meta) : '';
    }).join('')}</div>`;
  } else if (s.type === 'pool') {
    title.textContent = 'New to the PWHL';
    sub.textContent = `${MOVEMENT.entries.length} first roster entries; source labels follow the league feed`;
    const counts = { draft:0, signing:0, roster:0 };
    MOVEMENT.entries.forEach(e => counts[e.kind]++);
    box.innerHTML = `<div class="mv-category-counts"><span>${counts.draft} Drafted</span><span>${counts.signing} Signed</span><span>${counts.roster} Other roster entries</span></div>
      <div class="mv-people">${MOVEMENT.entries.map(e => {
        const p = movementPlayer(e.player_id);
        return p ? movementPersonButton(p, `${e.period} → ${e.to} · ${e.kind}`) : '';
      }).join('')}</div>`;
  } else if (s.type === 'retired') {
    title.textContent = 'Retirement recorded';
    sub.textContent = `${MOVEMENT.retirements.length} distinct events in the transaction feed`;
    box.innerHTML = `<div class="mv-people">${MOVEMENT.retirements.map(r => {
      const p = movementPlayer(r.player_id);
      return p ? movementPersonButton(p, `${r.date} · ${r.from}${r.later_roster ? ' · later roster appearance' : ''}`) : '';
    }).join('')}</div>`;
  } else {
    title.textContent = 'All team clusters';
    sub.textContent = 'Select a team to see every player in its roster history.';
    box.innerHTML = `<div class="mv-team-list">${MOVEMENT.teams.map(t => `<button type="button" data-mv-team="${esc(t.code)}" style="--tc:${teamColor(t.code)}"><strong>${esc(t.name)}</strong><span>${movementTeamCount(t.code)} players</span></button>`).join('')}</div>`;
  }
}

function renderMovementPage() {
  document.getElementById('movement-stats').innerHTML = [
    [MOVEMENT.players.length, 'PLAYERS ROSTER-LISTED'],
    [MOVEMENT.moves.length, 'TEAM-TO-TEAM MOVES'],
    [MOVEMENT.entries.length, 'FIRST ROSTER ENTRIES'],
    [MOVEMENT.retirements.length, 'RETIREMENT EVENTS'],
  ].map(([n, label]) => `<div class="stat"><div class="num">${n}</div><div class="lbl">${label}</div></div>`).join('');
  document.getElementById('movement-team-select').value = movementSelection.type === 'team' ? movementSelection.code : 'all';
  renderMovementNetwork();
  renderMovementDetail();
}

function initMovementPage() {
  const select = document.getElementById('movement-team-select');
  select.innerHTML = '<option value="all">All teams</option>'
    + MOVEMENT.teams.map(t => `<option value="${esc(t.code)}">${esc(t.name)}</option>`).join('');
  const list = document.getElementById('movement-search-list');
  list.innerHTML = MOVEMENT.players.map(p => `<option value="${esc(p.name)}"></option>`).join('');
  select.addEventListener('change', () => {
    movementSelection = select.value === 'all' ? { type:'all' } : { type:'team', code:select.value };
    renderMovementPage();
  });
  document.getElementById('movement-show-all').addEventListener('click', () => {
    movementSelection = { type:'all' }; renderMovementPage();
  });
  const choose = (target, keyboard = false) => {
    const team = target.closest('[data-mv-team]');
    const flow = target.closest('[data-mv-flow]');
    if (team) movementSelection = { type:'team', code:team.dataset.mvTeam };
    else if (target.closest('[data-mv-pool]')) movementSelection = { type:'pool' };
    else if (target.closest('[data-mv-retired]')) movementSelection = { type:'retired' };
    else if (flow) {
      const [kind, from, to] = flow.dataset.mvFlow.split('|');
      movementSelection = { type:'flow', kind, from, to };
    } else return;
    renderMovementPage();
    if (keyboard) {
      const focus = movementSelection.type === 'team' ? `[data-mv-team="${movementSelection.code}"]`
        : movementSelection.type === 'pool' ? '[data-mv-pool]'
        : movementSelection.type === 'retired' ? '[data-mv-retired]'
        : `.mv-count-control[data-mv-flow="${movementSelection.kind}|${movementSelection.from}|${movementSelection.to}"]`;
      document.querySelector('#movement-network ' + focus)?.focus();
    }
  };
  const network = document.getElementById('movement-network');
  network.addEventListener('click', e => choose(e.target));
  network.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(e.target, true); }
  });
  document.getElementById('movement-detail').addEventListener('click', e => {
    const player = e.target.closest('[data-mv-player]');
    const team = e.target.closest('[data-mv-team]');
    if (player) movementSelection = { type:'player', id:player.dataset.mvPlayer };
    else if (team) movementSelection = { type:'team', code:team.dataset.mvTeam };
    else return;
    renderMovementPage();
  });
  document.getElementById('movement-search').addEventListener('submit', e => {
    e.preventDefault();
    const query = document.getElementById('movement-search-input').value.trim().toLocaleLowerCase();
    const match = MOVEMENT.players.find(p => p.name.toLocaleLowerCase() === query)
      || MOVEMENT.players.find(p => p.name.toLocaleLowerCase().includes(query));
    if (match) { movementSelection = { type:'player', id:match.id }; renderMovementPage(); }
    else {
      const input = document.getElementById('movement-search-input');
      input.setCustomValidity('Choose a player from the list.');
      input.reportValidity();
    }
  });
  document.getElementById('movement-search-input').addEventListener('input', e => e.target.setCustomValidity(''));
  renderMovementPage();
}

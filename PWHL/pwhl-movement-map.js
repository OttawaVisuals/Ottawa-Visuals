// Geographic companion to the player-level team network. City coordinates are
// approximate centres; Natural Earth outlines are loaded from a local file.
let MOVEMENT_GEO = null;
const MOVEMENT_CITIES = {
  BOS:[-71.06,42.36], NY:[-73.94,40.73], MTL:[-73.56,45.50],
  TOR:[-79.38,43.65], OTT:[-75.69,45.42], MIN:[-93.09,44.95],
  VAN:[-123.12,49.28], SEA:[-122.33,47.61], DET:[-83.05,42.35],
  HAM:[-79.87,43.26], VGS:[-115.14,36.17], SJ:[-121.89,37.34],
};
const MOVEMENT_MAPS = {
  continent:{ width:1000, height:405, bounds:[-125,35,-69,51], padding:10, alignTop:true },
};
const movementMapBase = {};

function movementMercator(lat) {
  return Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360));
}
function movementProjection(config) {
  const [west,south,east,north] = config.bounds;
  const x0 = west * Math.PI / 180, x1 = east * Math.PI / 180;
  const y0 = movementMercator(south), y1 = movementMercator(north);
  const scale = Math.min((config.width - 2 * config.padding) / (x1 - x0), (config.height - 2 * config.padding) / (y1 - y0));
  const left = (config.width - (x1 - x0) * scale) / 2;
  const top = config.alignTop ? config.padding : (config.height - (y1 - y0) * scale) / 2;
  return ([lon,lat]) => ({ x:left + (lon * Math.PI / 180 - x0) * scale, y:top + (y1 - movementMercator(lat)) * scale });
}
function movementGeoPath(rings, project, close = true) {
  return rings.map(ring => ring.map((point,index) => {
    const p = project(point);
    return `${index ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
  }).join(' ') + (close ? ' Z' : '')).join(' ');
}
function movementBaseMap(id) {
  if (movementMapBase[id]) return movementMapBase[id];
  const config = MOVEMENT_MAPS[id], project = movementProjection(config);
  const countries = MOVEMENT_GEO.countries.map(country => `<path class="mv-geo-land mv-geo-${country.code.toLowerCase()}" d="${movementGeoPath(country.rings,project)}" fill-rule="evenodd"/>`).join('');
  const borders = `<path class="mv-geo-border" d="${movementGeoPath(MOVEMENT_GEO.borders,project,false)}"/>`;
  const lakes = `<path class="mv-geo-lake" d="${movementGeoPath(MOVEMENT_GEO.lakes,project)}" fill-rule="evenodd"/>`;
  movementMapBase[id] = `<g class="mv-geo-base">${countries}${borders}${lakes}</g>`;
  return movementMapBase[id];
}
function movementMapRoutes() {
  const grouped = new Map();
  MOVEMENT.moves.forEach(move => {
    const key = `${move.from}|${move.to}`;
    if (!grouped.has(key)) grouped.set(key,{ from:move.from, to:move.to, moves:[] });
    grouped.get(key).moves.push(move);
  });
  return [...grouped.values()].sort((a,b) => a.moves.length - b.moves.length || a.from.localeCompare(b.from));
}
function movementMapPoints(project) {
  const points = {};
  Object.entries(MOVEMENT_CITIES).forEach(([code,coordinates]) => {
    points[code] = project(coordinates);
  });
  // The Toronto and Hamilton city centres overlap at this scale.
  points.TOR = { x:points.TOR.x + 7, y:points.TOR.y - 7 };
  points.HAM = { x:points.HAM.x - 7, y:points.HAM.y + 7 };
  return points;
}
function movementMapRouteSvg(route, index, points, id) {
  const from = points[route.from], to = points[route.to];
  if (!from || !to) return '';
  const dx = to.x - from.x, dy = to.y - from.y, distance = Math.hypot(dx,dy);
  if (distance < 20) return '';
  const normal = { x:-dy / distance, y:dx / distance };
  const bend = Math.min(42,Math.max(8,distance * .11));
  const control = { x:(from.x + to.x) / 2 + normal.x * bend, y:(from.y + to.y) / 2 + normal.y * bend };
  const trim = Math.min(.22,Math.max(.025,10 / distance));
  const point = progress => {
    const t = trim + progress * (1 - 2 * trim), a = 1 - t;
    return { x:a*a*from.x + 2*a*t*control.x + t*t*to.x, y:a*a*from.y + 2*a*t*control.y + t*t*to.y };
  };
  const tangent = progress => {
    const t = trim + progress * (1 - 2 * trim);
    const vx = 2*(1-t)*(control.x-from.x) + 2*t*(to.x-control.x);
    const vy = 2*(1-t)*(control.y-from.y) + 2*t*(to.y-control.y);
    const length = Math.hypot(vx,vy) || 1;
    return { x:-vy/length, y:vx/length };
  };
  const count = route.moves.length;
  const dots = [];
  const approximateLength = distance * .93;
  for (let travelled = 0; travelled <= approximateLength * .58; ) {
    const progress = travelled / (approximateLength * .58);
    const p = point(progress * .58);
    const radius = (.28 + .42 * progress) * count;
    dots.push(`M ${(p.x+radius).toFixed(1)} ${p.y.toFixed(1)} A ${radius.toFixed(2)} ${radius.toFixed(2)} 0 1 0 ${(p.x-radius).toFixed(1)} ${p.y.toFixed(1)} A ${radius.toFixed(2)} ${radius.toFixed(2)} 0 1 0 ${(p.x+radius).toFixed(1)} ${p.y.toFixed(1)} Z`);
    travelled += 11 * Math.pow(1-progress,1.35) + 1.1;
  }
  const left = [], right = [];
  for (let step = 0; step <= 18; step++) {
    const progress = .55 + .45 * step / 18;
    const p = point(progress), n = tangent(progress);
    // Full stroke width grows from 1.3px to 3.3px per player.
    const width = (.65 + step / 18) * count;
    left.push(`${(p.x+n.x*width).toFixed(1)} ${(p.y+n.y*width).toFixed(1)}`);
    right.push(`${(p.x-n.x*width).toFixed(1)} ${(p.y-n.y*width).toFixed(1)}`);
  }
  const solid = `M ${left.join(' L ')} L ${right.reverse().join(' L ')} Z`;
  const hitStart = point(0), hitMid = point(.5), hitEnd = point(1);
  const hitControl = { x:2*hitMid.x - (hitStart.x + hitEnd.x)/2, y:2*hitMid.y - (hitStart.y + hitEnd.y)/2 };
  const hit = `M ${hitStart.x.toFixed(1)} ${hitStart.y.toFixed(1)} Q ${hitControl.x.toFixed(1)} ${hitControl.y.toFixed(1)} ${hitEnd.x.toFixed(1)} ${hitEnd.y.toFixed(1)}`;
  const selected = movementSelection.type === 'route' && movementSelection.from === route.from && movementSelection.to === route.to;
  const relevant = movementSelection.type === 'all' || selected
    || movementSelection.type === 'team' && (route.from === movementSelection.code || route.to === movementSelection.code)
    || movementSelection.type === 'player' && route.moves.some(move => move.player_id === movementSelection.id);
  const title = `${movementTeam(route.from).name} → ${movementTeam(route.to).name}: ${count} player move${count === 1 ? '' : 's'}`;
  const gradientId = `mv-map-flow-${id}-${index}`;
  return `<g class="mv-map-route${selected ? ' chosen' : ''}${relevant ? '' : ' dim'}" role="button" tabindex="0" data-mv-route-from="${esc(route.from)}" data-mv-route-to="${esc(route.to)}" aria-label="${esc(title)}">
    <defs><linearGradient id="${gradientId}" gradientUnits="userSpaceOnUse" x1="${from.x.toFixed(1)}" y1="${from.y.toFixed(1)}" x2="${to.x.toFixed(1)}" y2="${to.y.toFixed(1)}"><stop offset="0%" stop-color="${teamColor(route.from)}"/><stop offset="100%" stop-color="${teamColor(route.to)}"/></linearGradient></defs>
    <title>${esc(title)}</title><path class="mv-map-hit" d="${hit}"/><path class="mv-map-flow" d="${dots.join(' ')} ${solid}" fill="url(#${gradientId})" stroke="url(#${gradientId})"/>
  </g>`;
}
function movementMapMarkers(points, project) {
  const labelOffsets = {
    VAN:[-13,-12], SEA:[13,21], SJ:[13,18], VGS:[13,19], MIN:[12,-13],
    BOS:[13,-13], NY:[14,18], MTL:[13,-13], TOR:[14,-17], OTT:[14,-13],
    DET:[-13,-12], HAM:[-13,24],
  };
  return MOVEMENT.teams.map(team => {
    const p = points[team.code], original = project(MOVEMENT_CITIES[team.code]);
    const [offsetX,offsetY] = labelOffsets[team.code];
    const anchor = offsetX < 0 ? 'end' : 'start';
    const radius = 6.5;
    const leader = team.code === 'TOR' || team.code === 'HAM'
      ? `<path class="mv-map-leader" d="M ${original.x.toFixed(1)} ${original.y.toFixed(1)} L ${p.x.toFixed(1)} ${p.y.toFixed(1)}"/>` : '';
    const active = movementSelection.type === 'all' || movementSelection.type === 'team' && movementSelection.code === team.code
      || movementSelection.type === 'route' && (movementSelection.from === team.code || movementSelection.to === team.code)
      || movementSelection.type === 'player' && movementMembership(movementPlayer(movementSelection.id), team.code);
    const label = `<text class="mv-map-label" x="${(p.x+offsetX).toFixed(1)}" y="${(p.y+offsetY).toFixed(1)}" text-anchor="${anchor}">${esc(team.code)}</text>`;
    return `<g class="mv-map-team${active ? '' : ' dim'}" data-mv-team="${esc(team.code)}" role="button" tabindex="0" aria-label="Show ${esc(team.name)} players">${leader}
      <circle class="mv-map-halo" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${radius + 4}"/>
      <circle class="mv-map-pin" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${radius}" fill="${teamColor(team.code)}"/>
      ${label}
      <title>${esc(team.name)} · ${movementTeamPlayers(team.code).length} players</title></g>`;
  }).join('');
}
function renderMovementMapSvg(routes) {
  const main = MOVEMENT_MAPS.continent;
  const project = movementProjection(main);
  const points = movementMapPoints(project);
  const flows = routes.map((route,index) => movementMapRouteSvg(route,index,points,'continent')).join('');
  return `<svg viewBox="0 0 ${main.width} ${main.height}" role="group" aria-label="PWHL team movement across North America">
    <defs><clipPath id="mv-map-clip-continent"><rect width="${main.width}" height="${main.height}"/></clipPath></defs>
    <g clip-path="url(#mv-map-clip-continent)">${movementBaseMap('continent')}${flows}</g>
    ${movementMapMarkers(points,project)}
  </svg>`;
}
function renderMovementMap() {
  if (!MOVEMENT_GEO) return;
  const routes = movementMapRoutes();
  document.getElementById('movement-map-views').innerHTML = renderMovementMapSvg(routes);
  document.getElementById('movement-map-count').textContent = `${routes.length} directional routes · ${MOVEMENT.moves.length} player moves`;
}
function initMovementMap(geography) {
  MOVEMENT_GEO = geography;
  const maps = document.getElementById('movement-map-views');
  const choose = (target,keyboard = false) => {
    const team = target.closest('[data-mv-team]');
    const route = target.closest('[data-mv-route-from]');
    if (team) movementSelection = { type:'team', code:team.dataset.mvTeam };
    else if (route) movementSelection = { type:'route', from:route.dataset.mvRouteFrom, to:route.dataset.mvRouteTo };
    else return;
    renderMovementPage();
    if (keyboard) {
      const selector = team ? `[data-mv-team="${team.dataset.mvTeam}"]`
        : `[data-mv-route-from="${route.dataset.mvRouteFrom}"][data-mv-route-to="${route.dataset.mvRouteTo}"]`;
      maps.querySelector(selector)?.focus();
    }
  };
  maps.addEventListener('click', event => choose(event.target));
  maps.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(event.target,true); }
  });
  renderMovementMap();
}

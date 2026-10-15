// Static 2025–26 team itineraries. The animation shows a model, not GPS traces.
const travelNS = 'http://www.w3.org/2000/svg';
let travelAllData, travelData, travelGeography, travelTeamCode;
let travelPaths = [], travelMarker;
const TRAVEL_DURATION_MS = 10000;
let travelIndex = 0, travelProgress = 0, travelPlaying = false, travelLastFrame = 0, travelRunId = 0;

function travelProject([lon, lat]) {
  const west = -126, east = -60, north = 55, south = 31;
  const mercator = value => Math.log(Math.tan(Math.PI / 4 + value * Math.PI / 360));
  const yNorth = mercator(north), ySouth = mercator(south);
  const scale = Math.min(1040 / ((east - west) * Math.PI / 180), 460 / (yNorth - ySouth));
  return {x:30 + (lon - west) * Math.PI / 180 * scale,
          y:30 + (yNorth - mercator(lat)) * scale};
}

function travelRingPath(rings, close = true) {
  return rings.map(ring => ring.map((coords, i) => {
    const p = travelProject(coords);
    return `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }).join(' ') + (close ? 'Z' : '')).join(' ');
}

function travelSvgNode(tag, attributes = {}) {
  const node = document.createElementNS(travelNS, tag);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function travelSegmentPath(segment) {
  const a = travelProject(segment.from), b = travelProject(segment.to);
  if (segment.mode !== 'air') return `M${a.x.toFixed(1)},${a.y.toFixed(1)} L${b.x.toFixed(1)},${b.y.toFixed(1)}`;
  const dx = b.x - a.x, dy = b.y - a.y, distance = Math.hypot(dx, dy) || 1;
  const bend = Math.min(45, distance * .12);
  const cx = (a.x + b.x) / 2 + (-dy / distance) * bend;
  const cy = (a.y + b.y) / 2 + (dx / distance) * bend;
  return `M${a.x.toFixed(1)},${a.y.toFixed(1)} Q${cx.toFixed(1)},${cy.toFixed(1)} ${b.x.toFixed(1)},${b.y.toFixed(1)}`;
}

function travelBaseMap(svg, geography) {
  const base = travelSvgNode('g');
  geography.countries.forEach(country => base.append(travelSvgNode('path', {
    class:'travel-land', d:travelRingPath(country.rings), 'fill-rule':'evenodd'
  })));
  base.append(travelSvgNode('path', {class:'travel-border', d:travelRingPath(geography.borders, false)}));
  base.append(travelSvgNode('path', {class:'travel-lake', d:travelRingPath(geography.lakes), 'fill-rule':'evenodd'}));
  svg.append(base);
}

function travelPlaces(svg) {
  const labels = {
    Ottawa:[-12,-21,'end'], Toronto:[-10,26,'end'], Vancouver:[-8,-14,'end'],
    Seattle:[-8,23,'end'], Chicago:[10,18,'start'], Halifax:[10,-13,'start'],
    Laval:[14,-24,'start'], Newark:[14,22,'start'], 'St. Paul':[11,-13,'start'],
    Winnipeg:[11,-13,'start'], Calgary:[11,-13,'start'], Lowell:[12,-11,'start'],
    Boston:[12,-13,'start'], Montréal:[13,-19,'start'], 'Quebec City':[10,-15,'start'],
    'New York':[10,-16,'start'], Washington:[10,19,'start'], Dallas:[10,-12,'start'],
    Detroit:[10,-14,'start'], Denver:[10,-13,'start'], Hamilton:[-9,22,'end'],
    Edmonton:[10,-13,'start'],
  };
  const cities = new Map();
  travelData.legs.forEach(leg => {
    if (!cities.has(leg.from_city)) cities.set(leg.from_city,leg.segments[0].from);
    if (!cities.has(leg.to_city)) cities.set(leg.to_city,leg.segments.at(-1).to);
  });
  const placed = [];
  cities.forEach((coords,city) => {
    const p = travelProject(coords);
    const group = travelSvgNode('g',{class:'travel-place'});
    const title = travelSvgNode('title');
    title.textContent = city;
    group.append(title);
    group.append(travelSvgNode('circle',{cx:p.x.toFixed(1),cy:p.y.toFixed(1),r:4.5}));
    const preferred = labels[city] || [10,-10,'start'];
    const choices = [preferred,[10,-13,'start'],[-10,-13,'end'],[10,20,'start'],[-10,20,'end']];
    for (let [dx,dy,anchor] of choices) {
      if (p.x < 95) {dx = 10; anchor = 'start';}
      if (p.x > 1010) {dx = -10; anchor = 'end';}
      if (p.y + dy < 20) dy = 20;
      if (p.y + dy > 500) dy = -12;
      const x = p.x + dx, y = p.y + dy, width = city.length * 7.2;
      const box = {left:anchor === 'end' ? x-width : x, right:anchor === 'end' ? x : x+width,
                   top:y-12, bottom:y+3};
      if (box.left < 3 || box.right > 1097 || placed.some(other =>
        box.left < other.right+4 && box.right > other.left-4 && box.top < other.bottom+3 && box.bottom > other.top-3)) continue;
      placed.push(box);
      const text = travelSvgNode('text',{x:x.toFixed(1),y:y.toFixed(1),'text-anchor':anchor});
      text.textContent = city;
      group.append(text);
      break;
    }
    svg.append(group);
  });
}

function travelRenderMap(geography) {
  const svg = document.getElementById('travel-map');
  svg.replaceChildren();
  travelPaths = [];
  travelBaseMap(svg, geography);
  const routes = travelSvgNode('g');
  svg.append(routes);
  travelData.legs.forEach((leg, legIndex) => leg.segments.forEach((segment, segmentIndex) => {
    const path = travelSvgNode('path', {
      class:`travel-route ${segment.mode} future`, d:travelSegmentPath(segment)
    });
    routes.append(path);
    travelPaths.push({path, length:path.getTotalLength(), legIndex, segmentIndex});
  }));
  travelPlaces(svg);
  travelMarker = travelSvgNode('circle',{class:'travel-marker',r:6});
  svg.append(travelMarker);
}

function travelNumber(value) { return Math.round(value).toLocaleString(); }
function travelHours(value) {
  let minutes = Math.round(value * 60);
  const hours = Math.floor(minutes / 60);
  minutes %= 60;
  return `${hours}h ${String(minutes).padStart(2,'0')}m`;
}
function travelDate(date) {
  return new Date(`${date}T12:00:00`).toLocaleDateString('en-CA',{month:'short',day:'numeric',year:'numeric'});
}
function travelRoute(leg) {
  if (leg.from_city !== leg.to_city) return `${leg.from_city} → ${leg.to_city}`;
  return `${leg.from.split(' | ')[0]} → ${leg.to.split(' | ')[0]}`;
}

function travelRenderSummary() {
  const totals = travelData.totals;
  const stats = [
    [travelNumber(totals.km)+' km','ESTIMATED TOTAL'],
    [travelNumber(totals.bus_km)+' km','BUS / ROAD'],
    [travelNumber(totals.air_km)+' km','FLIGHT DISTANCE'],
    [travelNumber(totals.airport_drive_km)+' km','AIRPORT DRIVES'],
    [travelHours(totals.hours),'ESTIMATED TRAVEL TIME'],
  ];
  document.getElementById('travel-stats').innerHTML = stats.map(([value,label]) =>
    `<div class="stat"><div class="num">${esc(value)}</div><div class="lbl">${esc(label)}</div></div>`).join('');
  const tbody = document.querySelector('#travel-table tbody');
  tbody.innerHTML = travelData.legs.map((leg,i) => {
    const detail = leg.mode === 'air'
      ? `${leg.segments[1].label} · ${travelNumber(leg.segments[1].km)} km air + ${travelNumber(leg.segments[0].km+leg.segments[2].km)} km road`
      : `${travelNumber(leg.km)} km road`;
    return `<tr data-index="${i}" tabindex="0" aria-label="Select leg ${i+1}: ${esc(leg.from_city)} to ${esc(leg.to_city)}">
      <td>${esc(travelDate(leg.date))}</td><td>${esc(travelRoute(leg))}</td>
      <td>${leg.reason === 'Game' ? 'Game' : 'Return home'}</td>
      <td><span class="travel-mode ${leg.mode}">${leg.mode === 'bus' ? 'Bus' : 'Air + drives'}</span></td>
      <td>${travelNumber(leg.km)}</td><td>${travelHours(leg.hours)}</td><td>${esc(detail)}</td></tr>`;
  }).join('');
  document.getElementById('travel-scrub').max = String(travelData.legs.length - 1);
}

function travelRenderRanking() {
  const teams = Object.entries(travelAllData.teams).sort((a,b) => b[1].totals.km-a[1].totals.km);
  const maxKm = teams[0][1].totals.km;
  document.getElementById('travel-ranking').innerHTML = teams.map(([code,team]) =>
    `<button type="button" class="travel-rank${code === travelTeamCode ? ' active' : ''}" data-team="${code}" aria-pressed="${code === travelTeamCode}">
      <span class="travel-rank-top"><strong>${esc(team.team)}</strong><span>${travelNumber(team.totals.km)} km</span></span>
      <span class="travel-rank-track"><span class="travel-rank-fill" style="width:${(team.totals.km/maxKm*100).toFixed(1)}%;background:${teamColor(code)}"></span></span>
    </button>`).join('');
}

function travelSetTeam(code) {
  if (!travelAllData.teams[code]) return;
  travelPlaying = false;
  travelRunId++;
  travelLastFrame = 0;
  travelIndex = 0;
  travelProgress = 0;
  travelTeamCode = code;
  travelData = travelAllData.teams[code];
  document.getElementById('travel-team-select').value = code;
  document.getElementById('travel-page-title').textContent = `${travelData.team} on the road`;
  document.title = `${travelData.team} travel — Ottawa Visuals`;
  const url = new URL(location.href);
  url.searchParams.set('team',code);
  history.replaceState(null,'',url);
  travelRenderSummary();
  travelRenderMap(travelGeography);
  travelRenderRanking();
  travelRenderInfo();
  travelFrame();
}

function travelRenderInfo() {
  const leg = travelData.legs[travelIndex];
  document.getElementById('travel-position').textContent = `${travelIndex+1} / ${travelData.legs.length}`;
  document.getElementById('travel-scrub').value = String(travelIndex);
  document.getElementById('travel-current').innerHTML = `<div><strong>${esc(travelRoute(leg))}</strong> · ${esc(travelDate(leg.date))} · ${leg.reason === 'Game' ? 'Game travel' : 'Assumed return home'}</div><span>${leg.mode === 'bus' ? 'Bus' : 'Flight + airport drives'} · ${travelNumber(leg.km)} km · ${travelHours(leg.hours)}</span>`;
  document.querySelectorAll('#travel-table tbody tr').forEach((row,i) => row.classList.toggle('active',i === travelIndex));
  document.getElementById('travel-play').textContent = travelPlaying ? 'Pause' :
    travelIndex === travelData.legs.length-1 && travelProgress >= 1 ? 'Replay' : 'Play';
}

function travelFrame() {
  const segmentCount = travelData.legs[travelIndex].segments.length;
  let markerPath = null, markerDistance = 0;
  travelPaths.forEach(({path,length,legIndex,segmentIndex}) => {
    path.classList.remove('past','now','future');
    path.style.strokeDasharray = '';
    if (legIndex < travelIndex) path.classList.add('past');
    else if (legIndex > travelIndex) path.classList.add('future');
    else {
      const fraction = travelProgress * segmentCount - segmentIndex;
      if (fraction <= 0) path.classList.add('future');
      else {
        path.classList.add('now');
        if (fraction < 1) path.style.strokeDasharray = `${length*fraction} ${length+1}`;
      }
      if (fraction >= 0 && fraction <= 1) { markerPath = path; markerDistance = length * fraction; }
      if (travelProgress === 1 && segmentIndex === segmentCount-1) { markerPath = path; markerDistance = length; }
    }
  });
  if (!markerPath) {
    const first = travelPaths.find(item => item.legIndex === travelIndex);
    markerPath = first.path;
  }
  const p = markerPath.getPointAtLength(markerDistance);
  travelMarker.setAttribute('cx',p.x.toFixed(1));
  travelMarker.setAttribute('cy',p.y.toFixed(1));
}

function travelSeek(index) {
  travelPlaying = false;
  travelRunId++;
  travelIndex = Math.max(0,Math.min(travelData.legs.length-1,index));
  travelProgress = 0;
  travelRenderInfo(); travelFrame();
}

function travelTick(timestamp, runId) {
  if (!travelPlaying || runId !== travelRunId) return;
  if (travelLastFrame) {
    const speed = Number(document.getElementById('travel-speed').value);
    const oldIndex = travelIndex;
    const position = travelIndex + travelProgress
      + (timestamp-travelLastFrame)*speed*travelData.legs.length/TRAVEL_DURATION_MS;
    if (position >= travelData.legs.length) {
      travelIndex = travelData.legs.length-1;
      travelProgress = 1;
      travelPlaying = false;
    } else {
      travelIndex = Math.floor(position);
      travelProgress = position-travelIndex;
    }
    if (travelIndex !== oldIndex || !travelPlaying) travelRenderInfo();
    travelFrame();
  }
  travelLastFrame = timestamp;
  if (travelPlaying) requestAnimationFrame(next => travelTick(next, runId));
}

function travelControls() {
  document.getElementById('travel-team-select').addEventListener('change',event => travelSetTeam(event.target.value));
  document.getElementById('travel-ranking').addEventListener('click',event => {
    const button = event.target.closest('button[data-team]');
    if (button) travelSetTeam(button.dataset.team);
  });
  const tbody = document.querySelector('#travel-table tbody');
  tbody.addEventListener('click', event => {
    const row = event.target.closest('tr[data-index]');
    if (row) travelSeek(Number(row.dataset.index));
  });
  tbody.addEventListener('keydown', event => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const row = event.target.closest('tr[data-index]');
    if (row) { event.preventDefault(); travelSeek(Number(row.dataset.index)); }
  });
  document.getElementById('travel-play').addEventListener('click',() => {
    if (travelPlaying) { travelPlaying = false; travelRunId++; travelRenderInfo(); return; }
    if (travelIndex === travelData.legs.length-1 && travelProgress >= 1) { travelIndex = 0; travelProgress = 0; travelFrame(); }
    travelPlaying = true; travelLastFrame = 0; travelRunId++; travelRenderInfo();
    const runId = travelRunId;
    requestAnimationFrame(timestamp => travelTick(timestamp, runId));
  });
  document.getElementById('travel-prev').addEventListener('click',() => travelSeek(travelIndex-1));
  document.getElementById('travel-next').addEventListener('click',() => travelSeek(travelIndex+1));
  document.getElementById('travel-scrub').addEventListener('input',event => travelSeek(Number(event.target.value)));
  document.addEventListener('visibilitychange',() => {
    if (document.hidden && travelPlaying) { travelPlaying = false; travelRunId++; travelRenderInfo(); }
  });
}

Promise.all([
  PWHL.load(['meta']),
  fetch('data/json/pwhl_travel_2025_26.json?v=travel-3').then(r => {if(!r.ok) throw Error(`Travel HTTP ${r.status}`);return r.json()}),
  fetch('data/json/pwhl_movement_geography.json?v=movement-9').then(r => {if(!r.ok) throw Error(`Map HTTP ${r.status}`);return r.json()}),
]).then(([,data,geography]) => {
  travelAllData = data;
  travelGeography = geography;
  PWHL.fillHeader();
  document.getElementById('data-through').textContent = '2025–26 travel estimate';
  document.getElementById('travel-loading').remove();
  document.getElementById('travel-app').hidden = false;
  const select = document.getElementById('travel-team-select');
  select.innerHTML = Object.entries(data.teams).sort((a,b) => a[1].team.localeCompare(b[1].team))
    .map(([code,team]) => `<option value="${code}">${esc(team.team)}</option>`).join('');
  travelControls();
  const requested = new URLSearchParams(location.search).get('team')?.toUpperCase();
  travelSetTeam(data.teams[requested] ? requested : 'OTT');
  PWHL.onTheme(() => travelRenderRanking());
}).catch(error => {
  console.error(error);
  document.getElementById('travel-loading').textContent = 'Could not load the travel estimate. Try refreshing this page.';
});

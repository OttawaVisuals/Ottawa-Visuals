// Regular-season replay. Numbers are built by scripts/build_pwhl_recap.py.
const recapNS = 'http://www.w3.org/2000/svg';
const recapDuration = 30000;
let recapData, recapGeography, recapSeason, recapDays = [], recapIndex = -1;
let recapPosition = 0, recapPlaying = false, recapLastFrame = 0, recapFocus = null;
let recapCurrentPaths = [], recapMarkers = [], recapFrameId = 0;
let recapRecentPaths = [], recapChartState = {}, recapBounds;

const recapEl = id => document.getElementById(id);
const recapSvg = (tag, attrs = {}) => {
  const el = document.createElementNS(recapNS, tag);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
  return el;
};
function recapProject([lon, lat]) {
  const merc = value => Math.log(Math.tan(Math.PI / 4 + value * Math.PI / 360));
  const {west,east,north,south} = recapBounds;
  return [30 + (lon - west) / (east - west) * 1040,
          20 + (merc(north) - merc(lat)) / (merc(north) - merc(south)) * 300];
}
function recapRingPath(rings, close = true) {
  return rings.map(ring => ring.map((point, i) => {
    const [x, y] = recapProject(point);
    return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ') + (close ? 'Z' : '')).join(' ');
}
function recapRoutePath(route) {
  const [x1, y1] = recapProject(route.from), [x2, y2] = recapProject(route.to);
  const dx = x2 - x1, dy = y2 - y1, length = Math.hypot(dx, dy) || 1;
  const bend = Math.min(48, length * .12);
  const cx = (x1 + x2) / 2 - dy / length * bend;
  const cy = (y1 + y2) / 2 + dx / length * bend;
  return `M${x1.toFixed(1)},${y1.toFixed(1)} Q${cx.toFixed(1)},${cy.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`;
}
function recapFormatDate(date) {
  return new Date(`${date}T12:00:00`).toLocaleDateString('en-CA', {weekday:'short', month:'short', day:'numeric', year:'numeric'});
}
function recapMapBase() {
  const svg = recapEl('recap-map');
  svg.replaceChildren();
  const base = recapSvg('g');
  recapGeography.countries.forEach(country => base.append(recapSvg('path', {
    class:'recap-map-land', d:recapRingPath(country.rings), 'fill-rule':'evenodd'
  })));
  base.append(recapSvg('path', {class:'recap-map-border', d:recapRingPath(recapGeography.borders, false)}));
  base.append(recapSvg('path', {class:'recap-map-lake', d:recapRingPath(recapGeography.lakes), 'fill-rule':'evenodd'}));
  svg.append(base);
  recapSeason.teams.forEach(code => {
    const [x,y] = recapProject(recapSeason.bases[code]);
    const dot = recapSvg('circle', {class:'recap-base',cx:x.toFixed(1),cy:y.toFixed(1),r:5,fill:teamColor(code)});
    const title = recapSvg('title'); title.textContent = `${code} home rink`; dot.append(title); svg.append(dot);
  });
  svg.append(recapSvg('g', {id:'recap-routes'}));
}
function recapMapDay(index) {
  const layer = recapEl('recap-routes');
  layer.replaceChildren();
  recapCurrentPaths = []; recapMarkers = []; recapRecentPaths = [];
  for (let prior = Math.max(0, index - 5); prior < index; prior++) {
    recapDays[prior].routes.forEach(route => {
      const path = recapSvg('path', {
      class:'recap-route prior',d:recapRoutePath(route),stroke:teamColor(route.team)
      });
      layer.append(path);
      if (prior === index-1) recapRecentPaths.push(path);
    });
  }
  recapDays[index].routes.forEach(route => {
    const path = recapSvg('path', {
      class:'recap-route',d:recapRoutePath(route),stroke:teamColor(route.team)
    });
    const title = recapSvg('title');
    title.textContent = `${route.team}: ${route.from_name} → ${route.to_name}`;
    path.append(title);
    layer.append(path);
    const marker = recapSvg('circle', {class:'recap-comet',r:5,fill:teamColor(route.team)});
    layer.append(marker);
    recapCurrentPaths.push({path,length:path.getTotalLength(),team:route.team});
    recapMarkers.push(marker);
  });
  recapDays[index].games.forEach(game => {
    const [x,y] = recapProject(game.venue);
    const marker = recapSvg('circle', {class:'recap-venue',cx:x.toFixed(1),cy:y.toFixed(1),r:3.5});
    const title = recapSvg('title'); title.textContent = `${game.away} @ ${game.home}`;
    marker.append(title); layer.append(marker);
  });
}
function recapMapProgress(progress) {
  recapRecentPaths.forEach(path => {
    path.style.opacity = String(1 - .84 * Math.min(1, progress * 2));
  });
  recapCurrentPaths.forEach(({path,length,team}, i) => {
    path.style.strokeDasharray = `${Math.max(0.01, length * progress)} ${length + 2}`;
    path.style.opacity = recapFocus && team !== recapFocus ? '.2' : '1';
    const point = path.getPointAtLength(length * progress);
    recapMarkers[i].setAttribute('cx', point.x.toFixed(1));
    recapMarkers[i].setAttribute('cy', point.y.toFixed(1));
    recapMarkers[i].style.opacity = recapFocus && team !== recapFocus ? '.2' : '1';
  });
}
function recapTeamSwatch(code) {
  return `<span class="team-swatch" style="background:${teamColor(code)}"></span>`;
}
function recapTables(day) {
  recapEl('recap-standings').tBodies[0].innerHTML = day.standings.map(row => {
    const status = row.status === 'in' ? '<span class="recap-status in" title="Playoff berth certain">✓ IN</span>' :
      row.status === 'out' ? '<span class="recap-status out" title="Eliminated from playoff contention">× OUT</span>' : '';
    return `<tr data-team="${esc(row.team)}" class="${row.status === 'in' ? 'clinched' : row.status === 'out' ? 'eliminated' : ''}"><td>${row.rank}</td><td>${recapTeamSwatch(row.team)}${esc(row.team)}</td><td>${row.gp}</td><td><strong>${row.p}</strong></td><td>${row.gd > 0 ? '+' : ''}${row.gd}</td><td>${status}</td></tr>`;
  }).join('');
  recapEl('recap-leaders').tBodies[0].innerHTML = day.leaders.map((row,i) =>
    `<tr data-team="${esc(row.team)}"><td>${i+1}</td><td class="player-name" title="${esc(row.name)}">${esc(row.name)}</td><td>${recapTeamSwatch(row.team)}${esc(row.team)}</td><td><strong>${row.points}</strong></td></tr>`).join('');
  recapEl('recap-standings').querySelectorAll('tr[data-team]').forEach(row => {
    row.addEventListener('click', () => recapSetFocus(row.dataset.team));
  });
  recapEl('recap-leaders').querySelectorAll('tr[data-team]').forEach(row => {
    row.addEventListener('click', () => recapSetFocus(row.dataset.team));
  });
  recapUpdateFocusStyles();
}
function recapCounters(index, progress) {
  const previous = index ? recapDays[index-1].counters :
    {travel_hours:0,clock_minutes:0,goals:0,pim:0,extra_games:0};
  const current = recapDays[index].counters;
  const value = key => previous[key] + (current[key] - previous[key]) * progress;
  recapEl('recap-counter-travel').textContent = `${value('travel_hours').toFixed(1)} h`;
  recapEl('recap-counter-clock').textContent = `${(value('clock_minutes')/60).toFixed(1)} h`;
  recapEl('recap-counter-goals').textContent = Math.round(value('goals')).toLocaleString();
  recapEl('recap-counter-pim').textContent = Math.round(value('pim')).toLocaleString();
  recapEl('recap-counter-extra').textContent = String(Math.round(value('extra_games')));
}
function recapBuildChart(key) {
  const svg = recapEl('recap-chart-' + key);
  svg.replaceChildren();
  const W = 500, H = 200, left = 38, right = 10, top = 10, bottom = 18;
  const series = Object.fromEntries(recapSeason.teams.map(code =>
    [code, recapDays.map(day => day.standings.find(row => row.team === code)[key])]
  ));
  const values = Object.values(series).flat();
  const min = Math.min(0,...values), max = Math.max(0,...values);
  const span = max - min || 1, width = W - left - right, height = H - top - bottom;
  const x = i => left + i / Math.max(1,recapDays.length-1) * width;
  const y = value => top + (max-value) / span * height;
  for (const value of [min,max]) {
    svg.append(recapSvg('line',{class:'recap-chart-grid',x1:left,y1:y(value),x2:W-right,y2:y(value)}));
    const label = recapSvg('text',{class:'recap-chart-label',x:0,y:y(value)+3});
    label.textContent = value > 0 ? `+${value}` : String(value); svg.append(label);
  }
  if (min < 0 && max > 0) svg.append(recapSvg('line',{class:'recap-chart-zero',x1:left,y1:y(0),x2:W-right,y2:y(0)}));
  const defs = recapSvg('defs'), clip = recapSvg('clipPath',{id:`recap-clip-${key}`});
  const rect = recapSvg('rect',{x:left,y:0,width:0,height:H});
  clip.append(rect); defs.append(clip); svg.append(defs);
  const paths = {}, dots = {};
  recapSeason.teams.forEach(code => {
    const d = series[code].map((value,i) =>
      `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(value).toFixed(1)}`).join(' ');
    const path = recapSvg('path',{class:'recap-chart-line',d,stroke:teamColor(code),
      'clip-path':`url(#recap-clip-${key})`});
    svg.append(path); paths[code] = path;
  });
  const cursor = recapSvg('line',{class:'recap-chart-grid',x1:x(0),y1:top,x2:x(0),y2:H-bottom});
  svg.append(cursor);
  recapSeason.teams.forEach(code => {
    const dot = recapSvg('circle',{class:'recap-chart-dot',r:3.7,fill:teamColor(code)});
    svg.append(dot); dots[code] = dot;
  });
  const seasonLabel = recapSvg('text',{class:'recap-chart-label',x:left,y:H-3});
  seasonLabel.textContent = recapSeason.label; svg.append(seasonLabel);
  recapChartState[key] = {rect,cursor,paths,dots,series,x,y,left};
}
function recapBuildCharts() {
  recapChartState = {};
  ['p','gd'].forEach(recapBuildChart);
}
function recapChartProgress(index, progress) {
  const partial = index === 0 ? 0 : index - 1 + progress;
  Object.values(recapChartState).forEach(chart => {
    const px = chart.x(partial);
    chart.rect.setAttribute('width',(px-chart.left+3).toFixed(1));
    chart.cursor.setAttribute('x1',px.toFixed(1));
    chart.cursor.setAttribute('x2',px.toFixed(1));
    recapSeason.teams.forEach(code => {
      const values = chart.series[code];
      const previous = values[Math.max(0,index-1)];
      const current = values[index];
      const py = chart.y(previous+(current-previous)*progress);
      chart.dots[code].setAttribute('cx',px.toFixed(1));
      chart.dots[code].setAttribute('cy',py.toFixed(1));
    });
  });
}
function recapChartsFocus() {
  Object.values(recapChartState).forEach(chart => recapSeason.teams.forEach(code => {
    chart.paths[code].classList.toggle('focused',code === recapFocus);
    chart.paths[code].classList.toggle('dimmed',!!recapFocus && code !== recapFocus);
    chart.dots[code].style.opacity = recapFocus && code !== recapFocus ? '.12' : '1';
  }));
}
function recapUpdateFocusStyles() {
  document.querySelectorAll('.recap-board tr[data-team]').forEach(row => {
    row.classList.toggle('focused',row.dataset.team === recapFocus);
    row.classList.toggle('dimmed',!!recapFocus && row.dataset.team !== recapFocus);
  });
  document.querySelectorAll('#recap-team-legend button').forEach(button => {
    button.classList.toggle('focused',button.dataset.team === recapFocus);
    button.classList.toggle('dimmed',!!recapFocus && button.dataset.team !== recapFocus);
    button.setAttribute('aria-pressed',String(button.dataset.team === recapFocus));
  });
  recapEl('recap-clear').hidden = !recapFocus;
}
function recapSetFocus(code) {
  recapFocus = code === recapFocus ? null : code;
  recapUpdateFocusStyles();
  recapChartsFocus();
  recapMapProgress(recapPlaying ? recapPosition - Math.floor(recapPosition) : 1);
}
function recapRender(index, progress = 1) {
  index = Math.max(0,Math.min(recapDays.length-1,index));
  if (index !== recapIndex) {
    recapIndex = index;
    const day = recapDays[index];
    recapEl('recap-date').textContent = recapFormatDate(day.date);
    recapEl('recap-counter').textContent = `GAME DATE ${index+1} / ${recapDays.length}`;
    recapEl('recap-position').textContent = `${index+1} / ${recapDays.length}`;
    recapEl('recap-scrub').value = String(index);
    recapEl('recap-score').innerHTML = day.games.map(game =>
      `<span>${esc(game.away)} ${game.as} – ${game.hs} ${esc(game.home)}${game.ot ? ` (${esc(game.ot)})` : ''}</span>`).join('');
    recapTables(day);
    recapMapDay(index);
  }
  recapMapProgress(progress);
  recapChartProgress(index,progress);
  recapCounters(index,progress);
}
function recapStop() {
  recapPlaying = false;
  cancelAnimationFrame(recapFrameId);
  recapLastFrame = 0;
  recapEl('recap-play').textContent = recapIndex >= recapDays.length-1 ? 'Replay' : 'Play';
}
function recapTick(now) {
  if (!recapPlaying) return;
  if (recapLastFrame) {
    const speed = Number(recapEl('recap-speed').value);
    recapPosition += (now - recapLastFrame) / recapDuration * recapDays.length * speed;
  }
  recapLastFrame = now;
  if (recapPosition >= recapDays.length) {
    recapPosition = recapDays.length;
    recapRender(recapDays.length-1,1);
    recapStop();
    return;
  }
  recapRender(Math.floor(recapPosition),Math.max(.01,recapPosition % 1));
  recapFrameId = requestAnimationFrame(recapTick);
}
function recapPlay() {
  if (recapPlaying) { recapStop(); recapRender(recapIndex,1); return; }
  if (recapIndex >= recapDays.length-1) recapPosition = 0;
  else recapPosition = Math.max(0,recapPosition);
  recapPlaying = true;
  recapLastFrame = 0;
  recapEl('recap-play').textContent = 'Pause';
  recapFrameId = requestAnimationFrame(recapTick);
}
function recapSeek(index) {
  recapStop();
  recapPosition = Math.max(0,Math.min(recapDays.length-1,index));
  recapRender(recapPosition,1);
  recapEl('recap-play').textContent = recapPosition === recapDays.length-1 ? 'Replay' : 'Play';
}
function recapSetSeason(sid) {
  recapStop();
  recapSeason = recapData.seasons[sid];
  recapDays = recapSeason.days;
  recapIndex = -1; recapPosition = 0; recapFocus = null;
  const places = [...Object.values(recapSeason.bases),
    ...recapDays.flatMap(day => day.games.map(game => game.venue))];
  const lons = places.map(point => point[0]), lats = places.map(point => point[1]);
  recapBounds = {west:Math.min(...lons)-2,east:Math.max(...lons)+2,
                 south:Math.min(...lats)-1.2,north:Math.max(...lats)+1.2};
  recapEl('recap-scrub').max = String(recapDays.length-1);
  recapEl('recap-team-legend').innerHTML = recapSeason.teams.map(code =>
    `<button type="button" data-team="${esc(code)}" style="--team:${teamColor(code)}" aria-pressed="false">${esc(code)}</button>`).join('');
  recapEl('recap-team-legend').querySelectorAll('button').forEach(button =>
    button.addEventListener('click',() => recapSetFocus(button.dataset.team)));
  recapMapBase();
  recapBuildCharts();
  recapRender(0,1);
  recapEl('recap-play').textContent = 'Play';
}
async function recapToggleFullscreen() {
  if (document.fullscreenElement) { await document.exitFullscreen(); return; }
  recapStop();
  await recapEl('recap-app').requestFullscreen();
  recapPosition = 0; recapIndex = -1;
  recapRender(0,1);
  recapPlay();
}

Promise.all([
  PWHL.load(['meta']),
  fetch('data/json/pwhl_season_recap.json?v=recap-3').then(r => {if(!r.ok) throw Error(`Recap HTTP ${r.status}`);return r.json()}),
  fetch('data/json/pwhl_movement_geography.json?v=movement-9').then(r => {if(!r.ok) throw Error(`Map HTTP ${r.status}`);return r.json()}),
]).then(([,data,geography]) => {
  recapData = data; recapGeography = geography;
  PWHL.fillHeader();
  const selected = PWHL.seasonSelect(recapEl('recap-season'),Object.keys(recapData.seasons),recapSetSeason);
  recapEl('recap-app').hidden = false;
  recapEl('recap-loading').hidden = true;
  recapSetSeason(selected);
  recapEl('recap-play').addEventListener('click',recapPlay);
  recapEl('recap-back').addEventListener('click',() => recapSeek(recapIndex-1));
  recapEl('recap-forward').addEventListener('click',() => recapSeek(recapIndex+1));
  recapEl('recap-scrub').addEventListener('input',e => recapSeek(Number(e.target.value)));
  recapEl('recap-fullscreen').addEventListener('click',recapToggleFullscreen);
  recapEl('recap-watch').addEventListener('click',recapToggleFullscreen);
  document.addEventListener('fullscreenchange',() => {
    recapEl('recap-fullscreen').textContent = document.fullscreenElement ? 'Exit full screen' : 'Watch full screen';
  });
  recapEl('recap-clear').addEventListener('click',() => recapSetFocus(recapFocus));
  PWHL.onTheme(() => { PWHL.fillHeader(); recapSetSeason(currentSeasonId); });
}).catch(err => {
  console.error(err);
  recapEl('recap-loading').textContent = 'Could not load the season replay. Refresh the page or rebuild the recap data.';
});

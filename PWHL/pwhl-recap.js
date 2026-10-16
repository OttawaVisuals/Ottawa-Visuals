// Regular-season replay. Numbers are built by scripts/build_pwhl_recap.py.
const recapNS = 'http://www.w3.org/2000/svg';
const recapDuration = 75000;
let recapData, recapGeography, recapSeason, recapSeasonId, recapDays = [], recapRegularDays = [], recapIndex = -1;
let recapPosition = 0, recapPlaying = false, recapLastFrame = 0, recapFocus = null;
let recapCurrentPaths = [], recapMarkers = [], recapFrameId = 0;
let recapRecentPaths = [], recapChartState = {}, recapBounds, recapProjection;
let recapDefaultBounds, recapMapBoundsKey = '';
let recapRenderedEventCount = 0;

const recapEl = id => document.getElementById(id);
const recapSvg = (tag, attrs = {}) => {
  const el = document.createElementNS(recapNS, tag);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
  return el;
};
function recapProject([lon, lat]) {
  const merc = value => Math.log(Math.tan(Math.PI / 4 + value * Math.PI / 360));
  const {westX,northY,scale,left,top} = recapProjection;
  return [left + (lon * Math.PI / 180 - westX) * scale,
          top + (northY - merc(lat)) * scale];
}
function recapSetProjection() {
  const merc = value => Math.log(Math.tan(Math.PI / 4 + value * Math.PI / 360));
  const {west,east,north,south} = recapBounds;
  const westX = west * Math.PI / 180, eastX = east * Math.PI / 180;
  const northY = merc(north), southY = merc(south);
  const scale = Math.min(944 / (eastX - westX), 324 / (northY - southY));
  recapProjection = {westX,northY,scale,
    left:(1000 - (eastX - westX) * scale) / 2,
    top:(380 - (northY - southY) * scale) / 2};
}
function recapZoomForDay(day) {
  let next = recapDefaultBounds;
  if (day.phase === 'playoff' && day.bracket?.length) {
    const live = new Set();
    day.bracket.forEach(series => {
      if (Math.max(...series.wins) < 3) series.teams.forEach(code => live.add(code));
      else live.add(series.teams[series.wins[0] > series.wins[1] ? 0 : 1]);
    });
    const points = [...live].map(code => recapSeason.bases[code]).filter(Boolean);
    if (points.length >= 2 && live.size < recapSeason.teams.length) {
      const lons = points.map(p => p[0]), lats = points.map(p => p[1]);
      next = {west:Math.min(...lons)-2,east:Math.max(...lons)+2,
              south:Math.min(...lats)-1.2,north:Math.max(...lats)+1.2};
    }
  }
  const key = JSON.stringify(next);
  if (key !== recapMapBoundsKey) {
    recapBounds = next; recapMapBoundsKey = key;
    recapSetProjection(); recapMapBase();
  }
}
function recapTeamLogoUrl(code) {
  const teams = (META.teams_by_season || {})[recapSeasonId] || [];
  const team = teams.find(row => row.code === code);
  return team && team.logo || '';
}
function recapTeamCity(code) {
  const teams = (META.teams_by_season || {})[recapSeasonId] || [];
  const team = teams.find(row => row.code === code);
  return code === 'MTL' ? 'Montréal' : team && team.city || code;
}
function recapLogoBadge(code, size = 24) {
  const g = recapSvg('g', {class:'recap-logo-badge'});
  const half = size / 2;
  g.append(recapSvg('circle', {r:half,fill:'var(--bg-2)',stroke:teamColor(code),'stroke-width':2}));
  const url = recapTeamLogoUrl(code);
  if (url) g.append(recapSvg('image', {href:url,x:-half+2,y:-half+2,width:size-4,height:size-4,
    preserveAspectRatio:'xMidYMid meet'}));
  else {
    const label = recapSvg('text', {class:'recap-logo-fallback','text-anchor':'middle',y:3});
    label.textContent = code; g.append(label);
  }
  const title = recapSvg('title'); title.textContent = code; g.append(title);
  return g;
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
    const marker = recapLogoBadge(route.team,24);
    marker.classList.add('recap-moving-logo');
    layer.append(marker);
    recapCurrentPaths.push({path,length:path.getTotalLength(),team:route.team});
    recapMarkers.push(marker);
  });
  const placed = [];
  recapDays[index].games.forEach(game => {
    const [x,y] = recapProject(game.venue);
    let badgeY = y - 23;
    while (placed.some(point => Math.abs(point.x-x) < 62 && Math.abs(point.y-badgeY) < 34)) badgeY += 35;
    badgeY = Math.max(24,Math.min(350,badgeY));
    placed.push({x,y:badgeY});
    layer.append(recapSvg('line', {class:'recap-venue-stem',x1:x,y1:y,x2:x,y2:badgeY}));
    const marker = recapSvg('g', {class:'recap-matchup',transform:`translate(${x.toFixed(1)} ${badgeY.toFixed(1)})`});
    marker.append(recapSvg('rect', {x:-29,y:-15,width:58,height:30,rx:15}));
    const away = recapLogoBadge(game.away,24), home = recapLogoBadge(game.home,24);
    away.setAttribute('transform','translate(-14 0)');
    home.setAttribute('transform','translate(14 0)');
    marker.append(away,home);
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
    recapMarkers[i].setAttribute('transform',`translate(${point.x.toFixed(1)} ${point.y.toFixed(1)})`);
    recapMarkers[i].style.opacity = recapFocus && team !== recapFocus ? '.2' : String(Math.min(1,(1-progress)*5));
  });
}
function recapTeamSwatch(code) {
  return `<span class="team-swatch" style="background:${teamColor(code)}"></span>`;
}
function recapTables(day) {
  recapEl('recap-standings').tBodies[0].innerHTML = day.standings.map(row => {
    const status = row.status === 'in' ? '<span class="recap-status in" title="Clinched playoff spot" aria-label="Clinched playoff spot">✓</span>' :
      row.status === 'out' ? '<span class="recap-status out" title="Eliminated from playoff contention" aria-label="Eliminated from playoff contention">×</span>' : '';
    return `<tr data-team="${esc(row.team)}" class="${row.status === 'in' ? 'clinched' : row.status === 'out' ? 'eliminated' : ''}"><td>${row.rank}</td><td>${recapTeamSwatch(row.team)}${esc(row.team)}${status}</td><td>${row.gp}</td><td><strong>${row.p}</strong></td><td>${row.gd > 0 ? '+' : ''}${row.gd}</td></tr>`;
  }).join('');
  recapEl('recap-leaders').tBodies[0].innerHTML = day.leaders.map((row,i) =>
    `<tr data-team="${esc(row.team)}"><td>${i+1}</td><td class="player-name" title="${esc(row.name)}">${esc(row.name)}</td><td>${recapTeamSwatch(row.team)}${esc(row.team)}</td><td><strong>${row.points}</strong></td></tr>`).join('');
  recapEl('recap-goalies').tBodies[0].innerHTML = day.goalies.map((row,i) =>
    `<tr data-team="${esc(row.team)}"><td>${i+1}</td><td class="player-name" title="${esc(row.name)}">${esc(row.name)}</td><td>${recapTeamSwatch(row.team)}${esc(row.team)}</td><td><strong>${row.wins}</strong></td><td>${row.save_pct === null ? '—' : (row.save_pct * 100).toFixed(1)}</td></tr>`).join('');
  document.querySelectorAll('.recap-board tr[data-team]').forEach(row => {
    row.addEventListener('click', () => recapSetFocus(row.dataset.team));
  });
  recapUpdateFocusStyles();
}
function recapCounters(index, progress) {
  const previous = index ? recapDays[index-1].counters :
    {travel_hours:0,clock_minutes:0,goals:0,pim:0,extra_games:0,attendance:0};
  const current = recapDays[index].counters;
  const value = key => previous[key] + (current[key] - previous[key]) * progress;
  recapEl('recap-counter-travel').textContent = `${value('travel_hours').toFixed(1)} h`;
  recapEl('recap-counter-clock').textContent = `${(value('clock_minutes')/60).toFixed(1)} h`;
  recapEl('recap-counter-goals').textContent = Math.round(value('goals')).toLocaleString();
  recapEl('recap-counter-attendance').textContent = Math.round(value('attendance')).toLocaleString();
  recapEl('recap-counter-pim').textContent = Math.round(value('pim')).toLocaleString();
  recapEl('recap-counter-extra').textContent = String(Math.round(value('extra_games')));
}
function recapBuildChart(key) {
  const svg = recapEl('recap-chart-' + key);
  svg.replaceChildren();
  const W = 500, H = 260, left = 38, right = 32, top = 15, bottom = 24;
  const series = Object.fromEntries(recapSeason.teams.map(code =>
    [code, recapRegularDays.map(day => day.standings.find(row => row.team === code)[key])]
  ));
  let runningMin = 0, runningMax = 0;
  const domains = recapRegularDays.map((_, index) => {
    recapSeason.teams.forEach(code => {
      runningMin = Math.min(runningMin, series[code][index]);
      runningMax = Math.max(runningMax, series[code][index]);
    });
    return {min:key === 'p' ? 0 : -recapNiceAxis(-runningMin+1),
            max:recapNiceAxis(runningMax+1)};
  });
  const gridMin = recapSvg('line',{class:'recap-chart-grid',x1:left,x2:W-right});
  const gridMax = recapSvg('line',{class:'recap-chart-grid',x1:left,x2:W-right});
  const zero = recapSvg('line',{class:'recap-chart-zero',x1:left,x2:W-right});
  const minLabel = recapSvg('text',{class:'recap-chart-label',x:0});
  const maxLabel = recapSvg('text',{class:'recap-chart-label',x:0});
  const startLabel = recapSvg('text',{class:'recap-chart-label',x:left,y:H-3});
  startLabel.textContent = recapDays[0].date.slice(5);
  const endLabel = recapSvg('text',{class:'recap-chart-label','text-anchor':'end',x:W-right,y:H-3});
  svg.append(gridMin,gridMax,zero,minLabel,maxLabel,startLabel,endLabel);
  const paths = {}, logos = {}, connectors = {};
  recapSeason.teams.forEach(code => {
    const path = recapSvg('path',{class:'recap-chart-line',stroke:teamColor(code)});
    svg.append(path); paths[code] = path;
  });
  recapSeason.teams.forEach(code => {
    const connector = recapSvg('line',{class:'recap-chart-connector',stroke:teamColor(code)});
    const logo = recapLogoBadge(code,13);
    logo.classList.add('recap-chart-logo');
    svg.append(connector,logo); connectors[code] = connector; logos[code] = logo;
  });
  recapChartState[key] = {key,W,H,left,right,top,bottom,series,domains,paths,logos,connectors,
    gridMin,gridMax,zero,minLabel,maxLabel,endLabel};
}
function recapBuildCharts() {
  recapChartState = {};
  ['p','gd'].forEach(recapBuildChart);
}
function recapNiceAxis(value) {
  const step = value <= 10 ? 2 : value <= 30 ? 5 : 10;
  return Math.ceil(Math.max(1,value) / step) * step;
}
function recapChartProgress(index, progress) {
  Object.values(recapChartState).forEach(chart => {
    const {W,H,left,right,top,bottom,series,key,domains} = chart;
    const previousDomain = domains[Math.max(0,index-1)], currentDomain = domains[index];
    const min = previousDomain.min + (currentDomain.min-previousDomain.min)*progress;
    const max = previousDomain.max + (currentDomain.max-previousDomain.max)*progress;
    const y = value => top + (max-value) / (max-min) * (H-top-bottom);
    const domain = Math.max(4,index+progress);
    const x = i => left + i / domain * (W-left-right);
    const px = x(index === 0 ? 0 : index-1+progress);
    const label = value => {
      const rounded = Math.round(value);
      return `${key === 'gd' && rounded > 0 ? '+' : ''}${rounded}`;
    };
    [[chart.gridMin,min],[chart.gridMax,max]].forEach(([line,value]) => {
      line.setAttribute('y1',y(value).toFixed(1)); line.setAttribute('y2',y(value).toFixed(1));
    });
    [[chart.minLabel,min],[chart.maxLabel,max]].forEach(([text,value]) => {
      text.setAttribute('y',(y(value)+3).toFixed(1)); text.textContent = label(value);
    });
    chart.zero.style.display = min < 0 ? '' : 'none';
    chart.zero.setAttribute('y1',y(0).toFixed(1)); chart.zero.setAttribute('y2',y(0).toFixed(1));
    chart.endLabel.textContent = index ? recapDays[index].date.slice(5) : '';
    const endpoints = [];
    recapSeason.teams.forEach(code => {
      const values = series[code];
      const previous = values[Math.max(0,index-1)];
      const current = values[index];
      const value = index === 0 ? current : previous+(current-previous)*progress;
      const d = values.slice(0,index).map((v,i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
      chart.paths[code].setAttribute('d',d + `${index ? ' L' : 'M'}${px.toFixed(1)},${y(value).toFixed(1)}`);
      endpoints.push({code,y:y(value)});
    });
    // When teams tie, fan the logos out while the line ends stay at the true value.
    endpoints.sort((a,b) => a.y-b.y || a.code.localeCompare(b.code));
    const gap = 16, minY = top+8, maxY = H-bottom-8;
    endpoints.forEach((entry,i) => {
      const lower = minY + i*gap, upper = maxY - (endpoints.length-1-i)*gap;
      entry.labelY = Math.max(lower,Math.min(upper,entry.y));
      if (i) entry.labelY = Math.max(entry.labelY,endpoints[i-1].labelY+gap);
    });
    endpoints.forEach(({code,y:actualY,labelY}) => {
      const logoX = Math.min(W-10,px+12);
      chart.logos[code].setAttribute('transform',`translate(${logoX.toFixed(1)} ${labelY.toFixed(1)})`);
      const line = chart.connectors[code];
      line.setAttribute('x1',px.toFixed(1)); line.setAttribute('y1',actualY.toFixed(1));
      line.setAttribute('x2',(logoX-6).toFixed(1)); line.setAttribute('y2',labelY.toFixed(1));
    });
  });
}
function recapChartsFocus() {
  Object.values(recapChartState).forEach(chart => recapSeason.teams.forEach(code => {
    chart.paths[code].classList.toggle('focused',code === recapFocus);
    chart.paths[code].classList.toggle('dimmed',!!recapFocus && code !== recapFocus);
    chart.logos[code].style.opacity = recapFocus && code !== recapFocus ? '.15' : '1';
    chart.connectors[code].style.opacity = recapFocus && code !== recapFocus ? '.15' : '.65';
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
    recapEl('recap-phase').textContent = day.phase === 'playoff' ?
      (day.round === 2 ? 'FINAL' : 'PLAYOFF') : 'REGULAR SEASON';
    recapEl('recap-position').textContent = `${index+1} / ${recapDays.length}`;
    recapEl('recap-scrub').value = String(index);
    recapEl('recap-score').innerHTML = day.games.map(game =>
      `<span>${esc(game.away)} ${game.as} – ${game.hs} ${esc(game.home)}${game.ot ? ` (${esc(game.ot)})` : ''}</span>`).join('');
    const postseason = day.phase === 'playoff';
    recapEl('recap-standings-chart').hidden = postseason;
    recapEl('recap-playoff-visual').hidden = !postseason;
    recapEl('recap-standings-board').hidden = postseason;
    recapEl('recap-playoff-board').hidden = !postseason;
    if (postseason) {
      const playedPlayoffGames = recapDays.slice(0,index+1)
        .filter(frame => frame.phase === 'playoff')
        .flatMap(frame => (frame.games || []).map(game => ({...game,date:frame.date})));
      recapRenderGameRecap(playedPlayoffGames, day.round_name || '');
      recapRenderPlayoffVisual(day.bracket || []);
    }
    else recapTables(day);
    recapZoomForDay(day);
    recapMapDay(index);
    recapUpdateEventStrip(index,day);
  }
  recapMapProgress(progress);
  let regularIndex = -1;
  for (let i=0;i<=index;i++) if (!recapDays[i].phase || recapDays[i].phase === 'regular') regularIndex = i;
  regularIndex = Math.min(regularIndex,recapRegularDays.length-1);
  if (regularIndex >= 0) recapChartProgress(regularIndex,regularIndex === index ? progress : 1);
  recapCounters(index,progress);
}
function recapRenderPlayoffVisual(series) {
  const svg = recapEl('recap-playoff-series');
  svg.replaceChildren();
  const semis = series.filter(item => item.round === 1)
    .sort((a,b) => a.series.localeCompare(b.series)).slice(0,2);
  const final = series.find(item => item.round === 2);
  const winner = item => item && (item.wins[0] >= 3 ? item.teams[0] :
    item.wins[1] >= 3 ? item.teams[1] : null);
  const finalists = semis.map(item => {
    const team = winner(item);
    const finalIndex = final?.teams.indexOf(team) ?? -1;
    return {team,wins:finalIndex >= 0 ? final.wins[finalIndex] : null};
  });
  // Each semifinal feeds its own row in the centre final.
  svg.append(recapSvg('path',{class:'playoff-graphic-connector',
    d:'M153 90 H164 V160 H174 M347 90 H336 V198 H326'}));
  const card = (x,y,w,rows) => {
    svg.append(recapSvg('rect',{class:'playoff-graphic-card',x,y,width:w,height:76,rx:7}));
    svg.append(recapSvg('line',{class:'playoff-graphic-separator',x1:x+7,x2:x+w-7,y1:y+38,y2:y+38}));
    rows.forEach((row,i) => {
      const yy = y + 19 + i*38;
      const won = row.team && row.wins >= 3;
      if (won) svg.append(recapSvg('rect',{class:'playoff-graphic-winner',
        x:x+3,y:yy-16,width:w-6,height:33,rx:4,fill:teamColor(row.team)}));
      if (row.team) {
        const logo = recapTeamLogoUrl(row.team);
        if (logo) svg.append(recapSvg('image',{href:logo,x:x+8,y:yy-10,width:20,height:20}));
        else svg.append(recapSvg('circle',{cx:x+18,cy:yy,r:7,fill:teamColor(row.team)}));
      }
      const name = recapSvg('text',{class:`playoff-graphic-team${row.team ? '' : ' pending'}`,
        x:x+33,y:yy+4});
      name.textContent = row.team ? recapTeamCity(row.team) : 'TBD';
      svg.append(name);
      const wins = recapSvg('text',{class:'playoff-graphic-wins','text-anchor':'end',
        x:x+w-8,y:yy+4});
      wins.textContent = row.wins == null ? '–' : row.wins;
      svg.append(wins);
    });
  };
  semis.forEach((item,i) => card(i ? 347 : 7,52,146,
    item.teams.map((team,j) => ({team,wins:item.wins[j]}))));
  card(174,141,152,finalists);
}
function recapRenderGameRecap(games, roundName) {
  recapEl('recap-round-label').textContent = roundName
    .replace(/^PWHL\s+Walter Cup\s+/i,'')
    .replace(/\s+presented by\s+.+$/i,'')
    .trim();
  recapEl('recap-game-list').innerHTML = games.map(game => {
    const status = game.ot === 'SO' ? 'SO' : game.ot ? 'OT' : 'REG';
    const seconds = Number(game.duration_seconds) || 0;
    const duration = seconds ? `${Math.floor(seconds / 3600)}h ${String(Math.floor(seconds % 3600 / 60)).padStart(2,'0')}m` : '';
    const label = [duration, status === 'REG' ? 'REG' : status].filter(Boolean).join(' · ');
    const date = new Date(`${game.date}T12:00:00`).toLocaleDateString('en-CA',{month:'short',day:'numeric'});
    return `<div class="recap-game-row"><time datetime="${esc(game.date)}">${esc(date)}</time><span class="recap-game-matchup">${recapTeamSwatch(game.away)}${esc(game.away)} <b>${esc(game.as)}–${esc(game.hs)}</b> ${recapTeamSwatch(game.home)}${esc(game.home)}</span><span class="recap-game-status ${status.toLowerCase()}">${label || status}</span></div>`;
  }).join('') || '<p class="recap-game-empty">No playoff games on this date.</p>';
}
function recapUpdateEventStrip(index, day) {
  const strip = recapEl('recap-event-strip'), track = recapEl('recap-event-track');
  const events = recapDays.slice(0,index+1).flatMap(frame =>
    (frame.games || []).flatMap(game => (game.events || []).map(event => ({...event,date:frame.date,gameId:game.id}))));
  const icons = {
    'hat-trick':'<svg viewBox="0 0 64 64" focusable="false"><path d="m15 34 5-24h24l5 24M7 34h50M18 25h28"/><g class="recap-icon-accent" fill="currentColor" stroke="none"><path d="M7 48c0-5 14-5 14 0v5c0 5-14 5-14 0ZM25 48c0-5 14-5 14 0v5c0 5-14 5-14 0ZM43 48c0-5 14-5 14 0v5c0 5-14 5-14 0Z"/></g></svg>',
    shutout:'<svg viewBox="0 0 64 64" focusable="false"><path d="M12 8h18l6 10-3 23-12 13L9 41 6 18Z"/><path d="M11 21h20M13 31h16M17 19v13M25 19v13M17 41h8"/><ellipse class="recap-icon-accent" cx="50" cy="38" rx="9" ry="15"/></svg>',
    'game-misconduct':'<svg viewBox="0 0 64 64" focusable="false"><path d="M34 33h10v11H33a13 13 0 1 1-12-18h5v7Z"/><circle cx="20" cy="40" r="5"/><path d="M20 26v-7h9v7"/><path class="recap-icon-accent" d="M36 17h21m-7-7 7 7-7 7M58 7v20"/></svg>',
    suspension:'<svg viewBox="0 0 64 64" focusable="false"><rect x="9" y="13" width="46" height="43" rx="4"/><path d="M9 25h46M21 7v12M43 7v12"/><g class="recap-icon-accent"><circle cx="32" cy="40" r="10"/><path d="m25 33 14 14"/></g></svg>',
    'short-handed-goal':'<svg viewBox="0 0 64 64" focusable="false"><path d="M19 10 7 28h16M19 10v27M55 10H42v12h6c12 0 12 15 0 15h-6"/><path class="recap-icon-accent" d="m27 21 6 11 6-11M11 51h21m-6-6 7 6-7 6"/><path d="M41 49c0-5 16-5 16 0v5c0 5-16 5-16 0Z" fill="currentColor" stroke="none"/></svg>',
  };
  const labels = {'hat-trick':'Hat trick',shutout:'Shutout','game-misconduct':'Misconduct',suspension:'Suspension','short-handed-goal':'Short-handed goal'};
  track.innerHTML = events.map((event,i) => `<div class="recap-event-box ${esc(event.type)}${i >= recapRenderedEventCount ? ' is-new' : ''}" title="${esc(event.player)} · game ${esc(event.gameId || '—')} · ${esc(event.date)}"><span class="recap-event-icon" aria-hidden="true">${icons[event.type] || ''}</span><span><strong>${esc(labels[event.type] || event.type)}</strong><small>${esc(event.player)}${event.team ? ` · ${esc(event.team)}` : ''}</small></span></div>`).join('');
  strip.hidden = events.length === 0;
  if (events.length < recapRenderedEventCount) strip.scrollLeft = 0;
  else if (events.length > recapRenderedEventCount) requestAnimationFrame(() => strip.scrollTo({left:strip.scrollWidth,behavior:'smooth'}));
  recapRenderedEventCount = events.length;
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
  if (recapPlaying) {
    recapStop();
    recapRender(recapIndex,1);
    recapPosition = Math.min(recapDays.length,recapIndex+1);
    return;
  }
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
  recapPosition = Math.min(recapDays.length,recapPosition+1);
  recapEl('recap-play').textContent = recapIndex === recapDays.length-1 ? 'Replay' : 'Play';
}
function recapSetSeason(sid) {
  recapStop();
  recapRenderedEventCount = 0;
  recapSeasonId = sid;
  recapSeason = recapData.seasons[sid];
  recapRegularDays = recapSeason.days;
  recapDays = [...recapSeason.days, ...(recapSeason.playoffs || [])];
  recapIndex = -1; recapPosition = 0; recapFocus = null;
  const places = [...Object.values(recapSeason.bases),
    ...recapDays.flatMap(day => day.games.map(game => game.venue))];
  const lons = places.map(point => point[0]), lats = places.map(point => point[1]);
  recapBounds = {west:Math.min(...lons)-2,east:Math.max(...lons)+2,
                 south:Math.min(...lats)-1.2,north:Math.max(...lats)+1.2};
  recapDefaultBounds = recapBounds;
  recapMapBoundsKey = '';
  recapSetProjection();
  recapEl('recap-scrub').max = String(recapDays.length-1);
  recapEl('recap-team-legend').innerHTML = recapSeason.teams.map(code =>
    `<button type="button" data-team="${esc(code)}" style="--team:${teamColor(code)}" aria-label="Highlight ${esc(recapTeamCity(code))}" aria-pressed="false"><img src="${esc(recapTeamLogoUrl(code))}" alt=""/><span>${esc(recapTeamCity(code))}</span></button>`).join('');
  recapEl('recap-team-legend').querySelectorAll('button').forEach(button =>
    button.addEventListener('click',() => recapSetFocus(button.dataset.team)));
  recapMapBase();
  recapBuildCharts();
  recapRender(0,1);
  recapPosition = 1;
  recapEl('recap-play').textContent = 'Play';
}
async function recapToggleFullscreen() {
  if (document.fullscreenElement) { await document.exitFullscreen(); return; }
  recapStop();
  await recapEl('recap-app').requestFullscreen();
  recapPosition = 0; recapIndex = -1;
  recapRender(0,1);
  recapPosition = 1;
  recapPlay();
}

Promise.all([
  PWHL.load(['meta']),
  fetch('data/json/pwhl_season_recap.json?v=recap-19').then(r => {if(!r.ok) throw Error(`Recap HTTP ${r.status}`);return r.json()}),
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
  document.addEventListener('fullscreenchange',() => {
    recapEl('recap-fullscreen').textContent = document.fullscreenElement ? 'Exit full screen' : 'Watch full screen';
  });
  recapEl('recap-clear').addEventListener('click',() => recapSetFocus(recapFocus));
  PWHL.onTheme(() => PWHL.fillHeader());
}).catch(err => {
  console.error(err);
  recapEl('recap-loading').textContent = 'Could not load the season replay. Refresh the page or rebuild the recap data.';
});

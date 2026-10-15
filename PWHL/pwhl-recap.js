// Regular-season replay. Numbers are built by scripts/build_pwhl_recap.py.
const recapNS = 'http://www.w3.org/2000/svg';
const recapDuration = 45000;
let recapData, recapGeography, recapSeason, recapSeasonId, recapDays = [], recapRegularDays = [], recapIndex = -1;
let recapPosition = 0, recapPlaying = false, recapLastFrame = 0, recapFocus = null;
let recapCurrentPaths = [], recapMarkers = [], recapFrameId = 0;
let recapRecentPaths = [], recapChartState = {}, recapBounds, recapProjection;
let recapBirthDays = [];
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
  if ((day.phase === 'playoff' || day.phase === 'final') && day.bracket?.length) {
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
    recapEl('recap-phase').textContent = day.phase === 'final' ? 'FINAL' : day.phase === 'playoff' ? 'PLAYOFFS' : 'REGULAR SEASON';
    recapEl('recap-position').textContent = `${index+1} / ${recapDays.length}`;
    recapEl('recap-scrub').value = String(index);
    recapEl('recap-score').innerHTML = day.games.map(game =>
      `<span>${esc(game.away)} ${game.as} – ${game.hs} ${esc(game.home)}${game.ot ? ` (${esc(game.ot)})` : ''}</span>`).join('');
    const postseason = day.phase === 'playoff' || day.phase === 'final';
    recapEl('recap-standings-chart').hidden = postseason;
    recapEl('recap-playoff-visual').hidden = !postseason;
    recapEl('recap-standings-board').hidden = postseason;
    recapEl('recap-playoff-board').hidden = !postseason;
    if (postseason) {
      recapRenderBracket(day.bracket || [], day.round_name || '');
      recapRenderPlayoffVisual(day.bracket || []);
    }
    else recapTables(day);
    recapZoomForDay(day);
    recapMapDay(index);
    recapBirthplaces(Math.min(index,recapRegularDays.length-1));
    recapUpdateEventStrip(index,day);
    if (day.phase === 'final') recapShowChampion(day.champion);
    else recapEl('recap-champion-toast').hidden = true;
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
  const semis = series.filter(item => item.round === 1).slice(0,2);
  const final = series.find(item => item.round === 2);
  const byTeam = new Map();
  semis.forEach(item => {
    const winner = item.wins[0] >= 3 ? item.teams[0] : item.wins[1] >= 3 ? item.teams[1] : null;
    if (winner) byTeam.set(winner,{won:true});
  });
  const finalLines = final ? final.teams.map((team,i) => {
    const appears = series.some(item => item.round === 1 && item.teams.includes(team) && byTeam.has(team));
    return appears ? {team,wins:final.wins[i]} : {team:null,wins:null};
  }) : [{team:null,wins:null},{team:null,wins:null}];
  const card = (x,y,w,h,title,rows) => {
    svg.append(recapSvg('rect',{class:'playoff-graphic-card',x,y,width:w,height:h,rx:9}));
    const heading = recapSvg('text',{class:'playoff-graphic-heading',x:x+9,y:y+16}); heading.textContent = title; svg.append(heading);
    rows.forEach((row,i) => {
      const yy=y+31+i*30;
      if (i === 0) svg.append(recapSvg('line',{class:'playoff-graphic-separator',x1:x+8,x2:x+w-8,y1:yy-8,y2:yy-8}));
      const name=recapSvg('text',{class:'playoff-graphic-team',x:x+10,y:yy+12}); name.textContent=row.team || 'TBD'; svg.append(name);
      const wins=recapSvg('text',{class:'playoff-graphic-wins','text-anchor':'end',x:x+w-10,y:yy+12}); wins.textContent=row.wins == null ? '—' : `${row.wins} W`; svg.append(wins);
    });
  };
  semis.forEach((item,i) => {
    const rows=item.teams.map((team,j)=>({team,wins:item.wins[j]}));
    card(i === 0 ? 8 : 347,78,145,100,`SEMI-FINAL ${String.fromCharCode(65+i)}`,rows);
  });
  const finalParticipants=finalLines.map((row,i)=>({team:row.team,wins:row.wins}));
  card(175,78,150,100,'CHAMPIONSHIP FINAL',finalParticipants);
  [[153,128,175,128],[325,128,347,128]].forEach(([x1,y1,x2,y2])=>svg.append(recapSvg('path',{class:'playoff-graphic-connector',d:`M${x1} ${y1} L${x2} ${y2}`})));
  const label=recapSvg('text',{class:'playoff-graphic-note','text-anchor':'middle',x:250,y:238});
  label.textContent='Series wins update after each completed game';svg.append(label);
}
function recapRenderBracket(series, roundName) {
  recapEl('recap-round-label').textContent = roundName;
  recapEl('recap-bracket').innerHTML = series.map(item => {
    const [a,b] = item.teams;
    return `<div class="recap-series"><span>${esc(item.round_name)} · ${esc(item.series)}</span><strong>${esc(a)} ${item.wins[0]} – ${item.wins[1]} ${esc(b)}</strong></div>`;
  }).join('') || '<span>Playoff results unavailable</span>';
}
function recapUpdateEventStrip(index, day) {
  const strip = recapEl('recap-event-strip'), track = recapEl('recap-event-track');
  const events = recapDays.slice(0,index+1).filter(frame => frame.phase !== 'final').flatMap(frame =>
    (frame.games || []).flatMap(game => (game.events || []).map(event => ({...event,date:frame.date,gameId:game.id}))));
  const icons = {'hat-trick':'📯',shutout:'🧱','game-misconduct':'📣',suspension:'🚫'};
  const labels = {'hat-trick':'Hat trick',shutout:'Shutout','game-misconduct':'Misconduct',suspension:'Suspension'};
  track.innerHTML = events.map((event,i) => `<div class="recap-event-box ${esc(event.type)}${i >= recapRenderedEventCount ? ' is-new' : ''}" title="${esc(event.player)} · game ${esc(event.gameId || '—')} · ${esc(event.date)}"><span class="recap-event-icon" aria-hidden="true">${icons[event.type] || '•'}</span><span><strong>${esc(labels[event.type] || event.type)}</strong><small>${esc(event.player)}${event.team ? ` · ${esc(event.team)}` : ''}</small></span></div>`).join('');
  strip.hidden = day.phase === 'final' || events.length === 0;
  if (events.length < recapRenderedEventCount) strip.scrollLeft = 0;
  else if (events.length > recapRenderedEventCount) requestAnimationFrame(() => strip.scrollTo({left:strip.scrollWidth,behavior:'smooth'}));
  recapRenderedEventCount = events.length;
}
function recapShowChampion(code) {
  if (!code) return;
  const toast = recapEl('recap-champion-toast');
  toast.innerHTML = `<span>🏆 ${esc(recapTeamCity(code))} win the championship</span><img alt="${esc(code)} logo" src="${esc(recapTeamLogoUrl(code))}"/>`;
  toast.hidden = false;
  toast.classList.add('champion');
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
function recapBirthplaceBars(rows, region = false) {
  return rows.map(row => {
    const country = region ? row.country : row.name;
    const shade = country === 'Canada' ? 'canada' : country === 'United States' ? 'us' :
      country === 'Unknown' ? 'unknown' : 'other';
    const name = region ? `${row.name}, ${country === 'United States' ? 'US' : 'Canada'}` : row.name;
    return `<div class="recap-birth-row ${shade}"><span title="${esc(name)}">${esc(name)}</span><div class="recap-birth-track" aria-hidden="true"><i></i></div><strong>0</strong></div>`;
  }).join('');
}
const recapRegionCoords = {
  'Alberta':[-114.5,53.5],'British Columbia':[-125.0,54.5],'Manitoba':[-98.5,55.0],'New Brunswick':[-66.5,46.5],
  'Newfoundland and Labrador':[-58.0,53.0],'Nova Scotia':[-63.5,45.0],'Ontario':[-85.0,50.5],'Prince Edward Island':[-63.2,46.3],
  'Quebec':[-71.5,53.0],'Québec':[-71.5,53.0],'Saskatchewan':[-106.0,53.5],
  'Massachusetts':[-71.8,42.3],'Minnesota':[-94.5,46.0],'Wisconsin':[-89.5,44.5],'New York':[-75.5,43.0],
  'Ohio':[-82.8,40.3],'Illinois':[-89.0,40.0],'Michigan':[-85.5,44.0],'Connecticut':[-72.7,41.6],
  'Pennsylvania':[-77.8,41.0],'California':[-119.5,36.5],'Colorado':[-105.5,39.0],'Washington':[-120.5,47.4],
  'New Hampshire':[-71.6,43.8],'Maine':[-69.0,45.3],'Texas':[-99.0,31.0],'Florida':[-82.0,28.0],
  'North Dakota':[-100.5,47.5],'South Dakota':[-100.0,44.5],'Iowa':[-93.5,42.0],'Indiana':[-86.0,40.0],
  'New Jersey':[-74.5,40.2],'Virginia':[-79.0,37.5],'Oregon':[-120.5,44.0],'Arizona':[-111.5,34.0],
  'Missouri':[-92.5,38.5],'Vermont':[-72.7,44.0],'Rhode Island':[-71.6,41.6],'Georgia':[-83.5,32.5],
};
const recapCountryCoords = {
  'United States':[-98,39],'Canada':[-103,57],'Sweden':[15,62],'Finland':[26,64],'Czechia':[15,49.8],
  'Czech Republic':[15,49.8],'Switzerland':[8,47],'Germany':[10,51],'France':[2,46],'Russia':[90,60],
  'Japan':[138,37],'China':[105,35],'Norway':[10,62],'Denmark':[10,56],'Slovakia':[19,48.7],
  'Austria':[14,47.5],'Netherlands':[5,52],'Italy':[12,42.5],'Unknown':[0,0]
};
function recapBirthplaceMap(index) {
  const svg = recapEl('recap-birth-map');
  svg.replaceChildren();
  const project = ([lon,lat]) => [40+(lon+180)/360*920, 20+(82-lat)/145*370];
  const continents = [
    [[-168,72],[-140,70],[-120,55],[-98,50],[-82,25],[-104,15],[-118,32],[-130,50]],
    [[-80,12],[-68,10],[-50,-5],[-44,-25],[-58,-55],[-75,-35],[-82,-5]],
    [[-12,72],[35,68],[52,48],[35,35],[44,10],[30,-35],[15,-35],[-5,5],[-18,35]],
    [[35,70],[90,72],[145,60],[170,45],[140,25],[115,5],[100,-5],[75,8],[55,30]],
    [[112,-10],[154,-12],[150,-40],[122,-38]],
  ];
  continents.forEach(points => {
    const coords = points.map(project).map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
    svg.append(recapSvg('polygon',{class:'birth-land',points:coords}));
  });
  // A quiet global coordinate grid keeps markers legible without implying street-level precision.
  for (let lon=-120;lon<=120;lon+=60) { const [x]=project([lon,0]); svg.append(recapSvg('line',{class:'birth-grid',x1:x,x2:x,y1:20,y2:390})); }
  for (let lat=-40;lat<=80;lat+=30) { const [,y]=project([0,lat]); svg.append(recapSvg('line',{class:'birth-grid',x1:40,x2:960,y1:y,y2:y})); }
  const snapshot = recapBirthDays[index] || recapBirthDays.at(-1);
  const regions = snapshot.regions;
  const countryTotals = snapshot.countries;
  const placedCountries = new Set();
  Object.entries(regions).forEach(([key,count]) => {
    const [country,name] = key.split('|');
    let point = recapRegionCoords[name];
    if (!point && (country === 'United States' || country === 'Canada')) point = recapCountryCoords[country];
    if (!point) return;
    placedCountries.add(country);
    const [x,y] = project(point), r = Math.min(26,5+Math.sqrt(count)*3.4);
    const marker = recapSvg('g');
    const bubble = recapSvg('circle',{class:'birth-dot',cx:x,cy:y,r});
    const cityList = Object.entries(snapshot.places).filter(([place]) => place.endsWith(`${name}, ${country}`))
      .sort((a,b) => b[1]-a[1]).slice(0,5).map(([place,n]) => `${place.split(',')[0]} (${n})`).join(', ');
    const title = recapSvg('title'); title.textContent = `${name}, ${country}: ${count} players${cityList ? `\n${cityList}` : ''}`; bubble.append(title);
    marker.append(bubble);
    if (count >= 3) { const label = recapSvg('text',{class:'birth-count',x,y:y+3,'text-anchor':'middle'}); label.textContent = count; marker.append(label); }
    svg.append(marker);
  });
  Object.entries(countryTotals).forEach(([country,count]) => {
    if (!count || country === 'Unknown' || (placedCountries.has(country) && ['United States','Canada'].includes(country))) return;
    const point = recapCountryCoords[country];
    if (!point) return;
    const [x,y] = project(point), r = Math.min(26,5+Math.sqrt(count)*3.4);
    const marker = recapSvg('g');
    const bubble = recapSvg('circle',{class:'birth-dot birth-dot-international',cx:x,cy:y,r});
    const cityList = Object.entries(snapshot.places).filter(([place]) => place.endsWith(country))
      .sort((a,b) => b[1]-a[1]).slice(0,5).map(([place,n]) => `${place.split(',')[0]} (${n})`).join(', ');
    const title = recapSvg('title'); title.textContent = `${country}: ${count} players${cityList ? `\n${cityList}` : ''}`; bubble.append(title); marker.append(bubble);
    if (count >= 3) { const label = recapSvg('text',{class:'birth-count',x,y:y+3,'text-anchor':'middle'}); label.textContent = count; marker.append(label); }
    svg.append(marker);
  });
}
function recapBuildBirthplaces() {
  const birth = recapSeason.birthplaces;
  recapEl('recap-birth-countries').innerHTML = recapBirthplaceBars(birth.countries);
  recapEl('recap-birth-regions').innerHTML = recapBirthplaceBars(birth.regions,true);
  const countries = {}, regions = {}, places = {};
  let players = 0;
  recapBirthDays = recapDays.map(day => {
    day.birth_debuts.forEach(({country,region,place}) => {
      players++;
      countries[country] = (countries[country] || 0) + 1;
      if (place && place !== 'Unknown') places[place] = (places[place] || 0) + 1;
      if (region) {
        const key = `${country}|${region}`;
        regions[key] = (regions[key] || 0) + 1;
      }
    });
    return {players,countries:{...countries},regions:{...regions},places:{...places}};
  });
  if (players !== birth.players) throw Error(`Birthplace debut count mismatch for ${recapSeasonId}`);
}
function recapBirthplaces(index) {
  const birth = recapSeason.birthplaces, snapshot = recapBirthDays[index];
  const unknown = snapshot.countries.Unknown || 0;
  recapEl('recap-birth-summary').textContent = `${snapshot.players} players appeared · ${snapshot.players-unknown} with known birth country · ${unknown} unknown · hover for birthplace names`;
  const update = (id,rows,counts,key) => {
    const max = Math.max(1,...rows.map(row => row.count));
    [...recapEl(id).children].forEach((el,i) => {
      const count = counts[key(rows[i])] || 0;
      el.querySelector('i').style.width = `${(count / max * 100).toFixed(1)}%`;
      el.querySelector('strong').textContent = count;
    });
  };
  update('recap-birth-countries',birth.countries,snapshot.countries,row => row.name);
  update('recap-birth-regions',birth.regions,snapshot.regions,row => `${row.country}|${row.name}`);
  recapBirthplaceMap(index);
}
function recapSetSeason(sid) {
  recapStop();
  recapRenderedEventCount = 0;
  recapSeasonId = sid;
  recapSeason = recapData.seasons[sid];
  recapRegularDays = recapSeason.days;
  recapDays = [...recapSeason.days, ...(recapSeason.playoffs || []), ...(recapSeason.champion ? [{
    date:recapSeason.playoffs?.at(-1)?.date || recapSeason.days.at(-1).date,
    phase:'final', games:[], routes:[], bracket:recapSeason.playoffs?.at(-1)?.bracket || [], champion:recapSeason.champion,
    standings:[], leaders:[], goalies:[], birth_debuts:[], counters:recapSeason.days.at(-1).counters,
  }] : [])];
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
  recapBuildBirthplaces();
  recapMapBase();
  recapBuildCharts();
  recapRender(0,1);
  recapPosition = 1;
  recapEl('recap-play').textContent = 'Play';
  recapEl('recap-champion-toast').hidden = true;
  recapSetView('replay');
}
function recapSetView(view) {
  const birth = view === 'birth';
  recapEl('recap-replay-view').hidden = birth;
  recapEl('recap-birth-view').hidden = !birth;
  recapEl('recap-view-replay').classList.toggle('active',!birth);
  recapEl('recap-view-replay').setAttribute('aria-selected',String(!birth));
  recapEl('recap-view-birth').classList.toggle('active',birth);
  recapEl('recap-view-birth').setAttribute('aria-selected',String(birth));
  recapBirthplaceMap(Math.min(recapIndex,recapBirthDays.length-1));
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
  fetch('data/json/pwhl_season_recap.json?v=recap-15').then(r => {if(!r.ok) throw Error(`Recap HTTP ${r.status}`);return r.json()}),
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
  recapEl('recap-view-replay').addEventListener('click',() => recapSetView('replay'));
  recapEl('recap-view-birth').addEventListener('click',() => recapSetView('birth'));
  PWHL.onTheme(() => { PWHL.fillHeader(); recapSetSeason(currentSeasonId); });
}).catch(err => {
  console.error(err);
  recapEl('recap-loading').textContent = 'Could not load the season replay. Refresh the page or rebuild the recap data.';
});

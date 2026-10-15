let originsData, originsMap, originsMarkers;

function originsRender(seasonId) {
  const season = originsData.seasons[seasonId];
  originsMarkers.clearLayers();
  const grouped = new Map();
  let mappedPlayers = 0;
  for (const place of season.birthplaces.places) {
    const coords = place.coordinates;
    if (!coords || coords.length !== 2 || !coords.every(Number.isFinite)) continue;
    mappedPlayers += Number(place.count || 1);
    const [lon, lat] = coords;
    const key = `${lat.toFixed(4)}|${lon.toFixed(4)}`;
    const row = grouped.get(key) || {lat,lon,count:0,names:[]};
    row.count += Number(place.count || 1);
    if (!row.names.includes(place.name)) row.names.push(place.name);
    grouped.set(key,row);
  }
  const points = [...grouped.values()];
  points.forEach(point => {
    const names = point.names.sort((a,b) => a.localeCompare(b));
    const size = Math.max(20,Math.min(34,18+Math.sqrt(point.count)*4));
    const markerIcon = L.divIcon({className:'',html:`<span class="origin-marker" style="width:${size}px;height:${size}px">${point.count}</span>`,iconSize:[size,size],iconAnchor:[size/2,size/2]});
    const marker = L.marker([point.lat,point.lon],{icon:markerIcon});
    const details = document.createElement('div');
    details.textContent = `${names.join(' · ')} — ${point.count} ${point.count === 1 ? 'player' : 'players'}`;
    marker.bindPopup(details);
    marker.addTo(originsMarkers);
  });
  if (points.length) {
    const bounds = L.latLngBounds(points.map(point => [point.lat,point.lon]));
    originsMap.fitBounds(bounds,{padding:[34,34],maxZoom:5});
  } else {
    originsMap.setView([45,-90],3);
  }
  const missing = season.birthplaces.players-mappedPlayers;
  originsMap.invalidateSize();
  document.getElementById('origins-summary').textContent = `${season.label} · ${mappedPlayers} of ${season.birthplaces.players} player origins mapped · ${points.length} mapped places${missing ? ` · ${missing} unknown or unmatched` : ''}`;
  document.getElementById('origins-status').hidden = false;
  document.getElementById('origins-status').textContent = 'Select a marker for birthplace names and player count. Zoom in to separate nearby locations.';
}

Promise.all([
  PWHL.load(['meta']),
  fetch('data/json/pwhl_season_recap.json?v=origins-1').then(r => {if(!r.ok) throw Error(`Origins data HTTP ${r.status}`);return r.json()}),
]).then(([,data]) => {
  originsData = data;
  PWHL.fillHeader();
  const seasonSelect = document.getElementById('origins-season');
  const selected = PWHL.seasonSelect(seasonSelect,Object.keys(originsData.seasons),originsRender);
  originsMap = L.map('origins-map',{worldCopyJump:true,minZoom:2,maxZoom:16});
  const tileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
    minZoom:2,maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
  }).addTo(originsMap);
  tileLayer.on('tileerror',() => {
    const status = document.getElementById('origins-status');
    status.hidden = false;
    status.textContent = 'Map tiles could not load. Check your internet connection.';
  });
  originsMarkers = L.layerGroup().addTo(originsMap);
  originsRender(selected);
  PWHL.onTheme(() => PWHL.fillHeader());
}).catch(err => {
  console.error(err);
  document.getElementById('origins-summary').textContent = 'Could not load birthplace data.';
});

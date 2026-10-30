'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const paths = {
    close:'M4 17l7-12 7 12H4zM11 9v3m0 2v.1M19 7l2-2m-1 7h2',
    eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
    walk:'M14 4a2 2 0 1 1-4 0 2 2 0 0 1 4 0M8 22l3-7-2-4m2 4l5 7M5 13l4-5h4l3 5h4M13 8l-2 7',
    bike:'M9 17a4 4 0 1 1-8 0 4 4 0 0 1 8 0m14 0a4 4 0 1 1-8 0 4 4 0 0 1 8 0M5 17l5-9 5 9H5m14 0L15 5h-3M8 8h5',
    mobility:'M14 4a2 2 0 1 1-4 0 2 2 0 0 1 4 0M10 8v7h7l3 6M10 11h7M8 12a6 6 0 1 0 8 7',
    scooter:'M3 17h13l4-11h-4M5 20a2 2 0 1 1-4 0 2 2 0 0 1 4 0m16 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0',
    car:'M3 16V9l3-5h12l3 5v7H3zM3 10h18M6 14h2m8 0h2M5 16v4m14-4v4',
    truck:'M2 6h12v12H2V6zm12 5h5l3 4v3h-8M8 19a2 2 0 1 1-4 0 2 2 0 0 1 4 0m12 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0',
    suv:'M2 17V9l3-5h12l5 7v6H2zM3 10h17M9 4v6m6-6v6M7 19a2 2 0 1 1-4 0 2 2 0 0 1 4 0m14 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0',
    bus:'M4 3h16v16H4V3zm0 9h16M12 3v9M7 16h1m8 0h1M6 19v3m12-3v3',
    other:'M12 5v14M5 12h14'
  };
  const icon = key => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[key] || paths.other}"/></svg>`;
  const types = [['close_call','close','Close call','A collision nearly happened to me.'],['witness','eye','Unsafe behaviour witnessed','I saw something unsafe, without a close call to me.']];
  const modes = [['walking','walk','Walking'],['cycling','bike','Cycling'],['mobility_aid','mobility','Mobility aid'],['scooter','scooter','Scooter'],['vehicle','car','In a vehicle'],['other','other','Other']];
  const vehicles = [['car','car','Car'],['suv','suv','SUV'],['pickup','truck','Pickup'],['van','truck','Van / delivery'],['heavy_truck','truck','Heavy truck'],['bus','bus','Bus'],['motorcycle','scooter','Motorcycle'],['bicycle','bike','Bike'],['scooter','scooter','Scooter'],['other','other','Other'],['unknown','other','Not sure']];
  const behaviours = [['close_pass','Passed too closely'],['failed_yield','Failed to yield'],['turn_across_path','Turned across someone’s path'],['phone_use','Using a phone'],['blocked_bike_lane','Blocked bike lane'],['blocked_crossing','Blocked sidewalk / crossing'],['perceived_speeding','Seemed to be speeding'],['red_light','Ran a red light'],['stop_sign','Didn’t stop at stop sign'],['wrong_way','Travelled the wrong way'],['opened_door','Opened door into someone’s path'],['other','Other'],['unknown','Not sure']];
  const outcomes = [['evasive_action','I stopped, swerved or moved away'],['no_action','I didn’t take evasive action'],['unsure','Not sure / prefer not to say']];
  const render = (id, rows, name, type, withIcons) => {
    $(id).innerHTML = rows.map(row => {
      const [value, a, b, desc] = row;
      const label = withIcons ? b : a;
      return `<label class="option"><input type="${type}" name="${name}" value="${value}"><span class="tile">${withIcons ? icon(a) : ''}${desc ? `<strong>${label}</strong><small>${desc}</small>` : `<span>${label}</span>`}</span></label>`;
    }).join('');
  };
  render('report-types',types,'report_type','radio',true);
  render('modes',modes,'mode','radio',true);
  render('vehicles',vehicles,'vehicles','checkbox',true);
  render('behaviours',behaviours,'behaviours','checkbox',false);
  render('outcomes',outcomes,'outcome','radio',false);
  let step = 0, map, marker, pin = null, locationSource = null, accuracy = null, geoRequest = 0, finished = false;
  const values = name => [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(el => el.value);
  const single = name => values(name)[0] || null;
  const localDate = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  function setNow() { const d = new Date(); $('date').value = localDate(d); $('date').max = localDate(d); $('time').value = ''; }
  setNow();
  function pinAt(lat,lng,source,precision = null) {
    geoRequest++; $('locate').disabled = false;
    pin = {latitude:Number(lat.toFixed(6)),longitude:Number(lng.toFixed(6))}; locationSource=source;accuracy=precision;
    $('confirm-location').checked=false; $('confirm-location-row').hidden=false; $('clear-pin').hidden=false;
    $('pin-status').textContent=`Selected point: ${pin.latitude}, ${pin.longitude}. Confirm or adjust it below.`;
    if(map){ if(marker) marker.setLatLng([lat,lng]); else {marker=L.marker([lat,lng],{draggable:true,alt:'Incident location. Drag to adjust.'}).addTo(map);marker.on('dragend',()=>{const p=marker.getLatLng();pinAt(p.lat,p.lng,'map');});} }
  }
  function initMap() {
    if(map) {setTimeout(()=>map.invalidateSize(),0);return;}
    if(!window.L){$('map').innerHTML='<p class="map-fallback">The map could not load. You can still enter a street or intersection above, or use your location.</p>';return;}
    map=L.map('map').setView(pin?[pin.latitude,pin.longitude]:[45.4215,-75.6972],13);
    const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
    let tileWarned=false;tiles.on('tileerror',()=>{if(!tileWarned){$('geo-status').textContent='Map tiles could not load. Enter an intersection, or use your location.';tileWarned=true;}});
    map.on('click',e=>{pinAt(e.latlng.lat,e.latlng.lng,'map');$('geo-status').textContent='Map point selected. Adjust it if needed.';});
    if(pin) pinAt(pin.latitude,pin.longitude,locationSource,accuracy);
    setTimeout(()=>map.invalidateSize(),0);
  }
  $('locate').addEventListener('click',()=>{
    if(!navigator.geolocation){$('geo-status').textContent='Location is unavailable. Enter an intersection or choose a map point.';return;}
    const request=++geoRequest; $('locate').disabled=true;$('geo-status').textContent='Waiting for location permission…';
    navigator.geolocation.getCurrentPosition(p=>{
      if(request!==geoRequest||finished)return;
      pinAt(p.coords.latitude,p.coords.longitude,'device',Math.round(p.coords.accuracy));
      if(map) map.setView([p.coords.latitude,p.coords.longitude],17);
      $('geo-status').textContent=`Device accuracy: approximately ${Math.round(p.coords.accuracy)} m. This is your current location; move the pin if the incident happened elsewhere.`;
    },e=>{if(request!==geoRequest)return;$('locate').disabled=false;$('geo-status').textContent=e.code===1?'Location permission was declined. Enter an intersection or choose a map point.':'Could not find your location. Enter an intersection or choose a map point.';},{enableHighAccuracy:true,timeout:12000,maximumAge:0});
  });
  $('clear-pin').addEventListener('click',()=>{geoRequest++;pin=null;accuracy=null;locationSource=null;if(marker){marker.remove();marker=null;}$('confirm-location-row').hidden=true;$('confirm-location').checked=false;$('clear-pin').hidden=true;$('pin-status').textContent='No point selected. Tap the map to place a pin.';$('geo-status').textContent='';$('locate').disabled=false;});
  $('unknown-time').addEventListener('change',()=>{$('time').disabled=$('unknown-time').checked;if($('time').disabled)$('time').value='';});
  $('report-form').addEventListener('change',e=>{
    if(['vehicles','behaviours'].includes(e.target.name)) {
      const group=e.target.name;
      if(e.target.checked && e.target.value==='unknown') document.querySelectorAll(`input[name="${group}"]`).forEach(i=>{if(i!==e.target)i.checked=false;});
      else if(e.target.checked) document.querySelector(`input[name="${group}"][value="unknown"]`).checked=false;
    }
    if(e.target.name==='report_type') {const witness=single('report_type')==='witness';$('role-field').hidden=witness;$('outcome-field').hidden=witness;}
  });
  function record() {
    const witness=single('report_type')==='witness';
    return {schema_version:1,demo:true,report_type:single('report_type'),location:{description:$('address').value.trim()||null,point:pin,point_source:locationSource,device_accuracy_metres:accuracy,point_confirmed:pin?$('confirm-location').checked:null},incident_date:$('date').value,incident_time:$('unknown-time').checked?null:($('time').value||null),time_basis:'Ottawa local time (America/Toronto)',travel_mode:witness?null:single('mode'),vehicles:values('vehicles'),behaviours:values('behaviours'),evasive_action:witness?null:single('outcome'),notes:$('notes').value.trim()||null};
  }
  const lookup=(rows,selected,icons=false)=>selected.map(v=>{const r=rows.find(r=>r[0]===v);return r?(icons?r[2]:r[1]):v;}).join(', ');
  function review() {
    const r=record(); const lines=[['Report',lookup(types,[r.report_type],true)],['Location',r.location.description||'Map point'],['Map point',pin?`${pin.latitude}, ${pin.longitude} (confirmed)`:'Not provided'],['When',`${r.incident_date} · ${r.incident_time||'Time not specified'} · Ottawa local time`]];
    if(r.travel_mode) lines.push(['Travelling',lookup(modes,[r.travel_mode],true)]);
    lines.push(['Involved',lookup(vehicles,r.vehicles,true)],['Observed',lookup(behaviours,r.behaviours)]);
    if(r.evasive_action)lines.push(['Your action',lookup(outcomes,[r.evasive_action])]);
    if(r.notes)lines.push(['Optional note',r.notes]);
    $('review').replaceChildren();for(const [label,value] of lines){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;$('review').append(dt,dd);}
    $('record').textContent=JSON.stringify(r,null,2);
  }
  function show(next,focus=true) {
    step=next;$('error').hidden=true;
    document.querySelectorAll('[data-step]').forEach((el,i)=>{el.hidden=i!==step;});
    document.querySelectorAll('.steps li').forEach((el,i)=>{el.removeAttribute('aria-current');el.classList.toggle('complete',i<step);if(i===step)el.setAttribute('aria-current','step');});
    $('back').hidden=step===0;$('next').textContent=step===3?'Finish demo':'Continue →';
    if(step===1)initMap();if(step===3)review();
    if(focus){$('title-'+step).focus();$('app').scrollIntoView({block:'start'});}
  }
  function validation() {
    if(step===0&&!single('report_type'))return 'Choose a close call or unsafe behaviour witnessed.';
    if(step===1){if(!pin&&!$('address').value.trim())return 'Enter a street or intersection, or choose a map point.';if(pin&&!$('confirm-location').checked)return 'Confirm that the pin marks the incident location, or clear the map point.';if(!$('date').value||$('date').value>localDate(new Date()))return 'Choose an incident date that is today or earlier.';}
    if(step===2){if(single('report_type')==='close_call'&&!single('mode'))return 'Choose how you were travelling.';if(!values('vehicles').length)return 'Choose what was involved, or select Not sure.';if(!values('behaviours').length)return 'Choose what you observed, or select Not sure.';if(single('report_type')==='close_call'&&!single('outcome'))return 'Choose what happened to you, or select Not sure / prefer not to say.';}
    return null;
  }
  $('report-form').addEventListener('submit',e=>{e.preventDefault();const error=validation();if(error){$('error').textContent=error;$('error').hidden=false;$('error').scrollIntoView({block:'center'});return;}if(step<3)show(step+1);else{finished=true;geoRequest++;$('report-form').hidden=true;document.querySelector('.steps').hidden=true;$('done').hidden=false;$('done').querySelector('h2').focus();$('done').scrollIntoView({block:'center'});$('record').textContent='';$('review').replaceChildren();$('report-form').reset();pin=null;locationSource=null;accuracy=null;if(marker){marker.remove();marker=null;}}});
  $('back').addEventListener('click',()=>show(step-1));
  $('restart').addEventListener('click',()=>{finished=false;$('report-form').reset();setNow();$('time').disabled=false;$('done').hidden=true;$('report-form').hidden=false;document.querySelector('.steps').hidden=false;$('role-field').hidden=false;$('outcome-field').hidden=false;$('clear-pin').click();show(0);});
  $('example').addEventListener('click',()=>{document.querySelector('[name="report_type"][value="close_call"]').click();document.querySelector('[name="mode"][value="cycling"]').click();document.querySelector('[name="vehicles"][value="car"]').click();document.querySelector('[name="behaviours"][value="close_pass"]').click();document.querySelector('[name="outcome"][value="evasive_action"]').click();$('address').value='Fictional example: Bank Street at Laurier Avenue';$('notes').value='Fictional demonstration only. No actual incident.';$('time').value='09:00';show(1);});
  $('app').hidden=false;show(0,false);
})();

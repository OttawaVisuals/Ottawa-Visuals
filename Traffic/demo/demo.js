'use strict';
(() => {
  const $ = id => document.getElementById(id);
  // Each answer row is [stored value, icon file in icons/, label, optional description].
  const types = [['close_call','close-call','Close call','A collision nearly happened to me.'],['witness','witnessed','Unsafe behaviour witnessed','I saw something unsafe, without a close call to me.']];
  const modes = [['walking','walking','Walking'],['cycling','cycling','Cycling'],['mobility_aid','mobility-aid','Mobility aid'],['scooter','scooter','Scooter'],['vehicle','driver','In a vehicle'],['other','other-behaviour','Other']];
  // Vehicle, direction, movement, evasive-action and injury categories mirror the Vision Zero Ottawa close-call form.
  const vehicles = [['car','car','Car'],['suv','suv','SUV'],['truck','pickup','Pickup truck'],['light_commercial','van','Van / delivery truck'],['heavy_commercial','semi','Semi / heavy truck'],['other','other-behaviour','Other'],['unknown','not-sure','Not sure']];
  const directions = [['northbound','north','North'],['southbound','south','South'],['eastbound','east','East'],['westbound','west','West'],['unknown','not-sure','Not sure']];
  const movements = [['left_turn','turn-left','Turning left'],['straight','straight','Going straight'],['right_turn','turn-right','Turning right'],['other','other-behaviour','Something else'],['unknown','not-sure','Not sure']];
  const behaviours = [['red_light','ran-red-light','Ran a red light'],['rolling_stop','did-not-stop','Rolling stop / didn’t stop at stop sign'],['perceived_speeding','seemed-to-be-speeding','Seemed to be speeding'],['distracted','distracted-driving','Distracted / using a phone'],['failed_yield','failed-to-yield','Failed to yield'],['turn_across_path','turned-across-path','Turned across someone’s path'],['close_pass','passed-too-closely','Passed too closely'],['blocked_bike_lane','blocked-bike-lane','Blocked bike lane'],['blocked_crossing','blocked-crossing','Blocked sidewalk / crossing'],['wrong_way','wrong-way','Travelled the wrong way'],['opened_door','opened-car-door','Opened door into someone’s path'],['other','other-behaviour','Other'],['unknown','not-sure','Not sure']];
  const evaders = [['you','me','I did'],['them','driver','The driver did'],['both','both','We both did'],['neither','neither','Neither of us'],['unknown','not-sure','Not sure']];
  const yourActions = [['step_back','step-back','Stepped back'],['halt','stopped','Stopped'],['speed_up','sped-up','Sped up'],['swerve','swerved','Swerved'],['other','other-behaviour','Something else']];
  const driverActions = [['swerve','swerved','Swerved'],['brake','braked','Braked'],['heavy_braking','braked-hard','Braked hard'],['unknown','not-sure','Not sure']];
  const injuries = [['yes','injured','Yes'],['no','not-injured','No']];
  const render = (id, rows, name, type) => {
    $(id).innerHTML = rows.map(([value, file, label, desc]) =>
      `<label class="option"><input type="${type}" name="${name}" value="${value}"><span class="tile"><img class="scene-icon" src="icons/${file}.svg" width="56" height="56" alt="" aria-hidden="true">${desc ? `<strong>${label}</strong><small>${desc}</small>` : `<span>${label}</span>`}</span></label>`
    ).join('');
  };
  render('report-types',types,'report_type','radio');
  render('modes',modes,'mode','radio');
  render('your-direction',directions,'your_direction','radio');
  render('vehicles',vehicles,'vehicle','radio');
  render('vehicle-direction',directions,'vehicle_direction','radio');
  render('movements',movements,'movement','radio');
  render('behaviours',behaviours,'behaviours','checkbox');
  render('evaders',evaders,'evader','radio');
  render('your-actions',yourActions,'your_actions','checkbox');
  render('driver-actions',driverActions,'driver_action','radio');
  render('injuries',injuries,'injured','radio');
  let map, marker, pin = null, locationSource = null, accuracy = null, geoRequest = 0, previewing = false;
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
      if(request!==geoRequest||previewing)return;
      pinAt(p.coords.latitude,p.coords.longitude,'device',Math.round(p.coords.accuracy));
      if(map) map.setView([p.coords.latitude,p.coords.longitude],17);
      $('geo-status').textContent=`Device accuracy: approximately ${Math.round(p.coords.accuracy)} m. This is your current location; move the pin if the incident happened elsewhere.`;
    },e=>{if(request!==geoRequest)return;$('locate').disabled=false;$('geo-status').textContent=e.code===1?'Location permission was declined. Enter an intersection or choose a map point.':'Could not find your location. Enter an intersection or choose a map point.';},{enableHighAccuracy:true,timeout:12000,maximumAge:0});
  });
  $('clear-pin').addEventListener('click',()=>{geoRequest++;pin=null;accuracy=null;locationSource=null;if(marker){marker.remove();marker=null;}$('confirm-location-row').hidden=true;$('confirm-location').checked=false;$('clear-pin').hidden=true;$('pin-status').textContent='No point selected. Tap the map to place a pin.';$('geo-status').textContent='';$('locate').disabled=false;});
  $('unknown-time').addEventListener('change',()=>{$('time').disabled=$('unknown-time').checked;if($('time').disabled)$('time').value='';});
  $('report-form').addEventListener('change',e=>{
    if(e.target.name==='behaviours') {
      if(e.target.checked && e.target.value==='unknown') document.querySelectorAll('input[name="behaviours"]').forEach(i=>{if(i!==e.target)i.checked=false;});
      else if(e.target.checked) document.querySelector('input[name="behaviours"][value="unknown"]').checked=false;
    }
    if(e.target.name==='evader') sync();
    if(e.target.name==='report_type') show(false,false);
  });
  // Follow-up questions appear only when the answer above makes them relevant.
  function sync() {
    const witness=single('report_type')==='witness',who=single('evader');
    document.querySelectorAll('.reporter-only').forEach(el=>{el.hidden=witness;});
    $('your-action-field').hidden=witness||!['you','both'].includes(who);
    $('driver-action-field').hidden=witness||!['them','both'].includes(who);
  }
  function record() {
    const witness=single('report_type')==='witness',who=witness?null:single('evader');
    return {schema_version:2,demo:true,report_type:single('report_type'),location:{description:$('address').value.trim()||null,point:pin,point_source:locationSource,device_accuracy_metres:accuracy,point_confirmed:pin?$('confirm-location').checked:null},incident_date:$('date').value,incident_time:$('unknown-time').checked?null:($('time').value||null),time_basis:'Ottawa local time (America/Toronto)',travel_mode:witness?null:single('mode'),your_direction:witness?null:single('your_direction'),origin_and_destination:witness?null:($('route').value.trim()||null),vehicle_type:single('vehicle'),vehicle_direction:single('vehicle_direction'),driver_movement:single('movement'),behaviours:values('behaviours'),evasive_action_by:who,your_evasive_actions:['you','both'].includes(who)?values('your_actions'):[],driver_evasive_action:['them','both'].includes(who)?single('driver_action'):null,injured:witness?null:single('injured'),notes:$('notes').value.trim()||null};
  }
  const lookup=(rows,selected)=>selected.map(v=>{const r=rows.find(r=>r[0]===v);return r?r[2]:v;}).join(', ');
  function review() {
    const r=record(); const lines=[['Report',lookup(types,[r.report_type])],['Location',r.location.description||'Map point'],['Map point',pin?`${pin.latitude}, ${pin.longitude} (confirmed)`:'Not provided'],['When',`${r.incident_date} · ${r.incident_time||'Time not specified'} · Ottawa local time`]];
    if(r.travel_mode) lines.push(['Travelling',lookup(modes,[r.travel_mode])]);
    if(r.your_direction) lines.push(['Your direction',lookup(directions,[r.your_direction])]);
    if(r.origin_and_destination) lines.push(['Coming from / going to',r.origin_and_destination]);
    lines.push(['Vehicle',lookup(vehicles,[r.vehicle_type])],['Vehicle direction',lookup(directions,[r.vehicle_direction])],['Driver was',lookup(movements,[r.driver_movement])],['Driving behaviour',lookup(behaviours,r.behaviours)]);
    if(r.evasive_action_by)lines.push(['Evasive action by',lookup(evaders,[r.evasive_action_by])]);
    if(r.your_evasive_actions.length)lines.push(['Your evasive action',lookup(yourActions,r.your_evasive_actions)]);
    if(r.driver_evasive_action)lines.push(['Driver’s evasive action',lookup(driverActions,[r.driver_evasive_action])]);
    if(r.injured)lines.push(['Injured',lookup(injuries,[r.injured])]);
    if(r.notes)lines.push(['Optional note',r.notes]);
    $('review').replaceChildren();for(const [label,value] of lines){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;$('review').append(dt,dd);}
    $('record').textContent=JSON.stringify(r,null,2);
  }
  function show(preview,focus=true) {
    previewing=preview;$('error').hidden=true;
    const selected=!!single('report_type'),witness=single('report_type')==='witness';
    document.querySelectorAll('[data-step]').forEach((el,i)=>{el.hidden=preview?i!==3:(i===3||(i>0&&!selected));});
    sync();
    $('back').hidden=!preview;$('restart').hidden=!preview;$('next').hidden=preview||!selected;
    if(preview){geoRequest++;$('locate').disabled=false;review();}else if(selected)initMap();
    if(focus){const heading=$('title-'+(preview?3:0));heading.focus();heading.scrollIntoView({block:'start'});}
  }
  function validation() {
    if(!single('report_type'))return ['Choose a close call or unsafe behaviour witnessed.','report-types'];
    if(!pin&&!$('address').value.trim())return ['Enter a street or intersection, or choose a map point.','address'];
    if(pin&&!$('confirm-location').checked)return ['Confirm that the pin marks the incident location, or clear the map point.','confirm-location'];
    if(!$('date').value||$('date').value>localDate(new Date()))return ['Choose an incident date that is today or earlier.','date'];
    const close=single('report_type')==='close_call',who=single('evader');
    if(close&&!single('mode'))return ['Choose how you were travelling.','modes'];
    if(close&&!single('your_direction'))return ['Choose which way you were heading, or select Not sure.','your-direction'];
    if(!single('vehicle'))return ['Choose the type of vehicle, or select Not sure.','vehicles'];
    if(!single('vehicle_direction'))return ['Choose which way the vehicle was heading, or select Not sure.','vehicle-direction'];
    if(!single('movement'))return ['Choose what the driver was doing, or select Not sure.','movements'];
    if(!values('behaviours').length)return ['Choose the driving behaviour you saw, or select Not sure.','behaviours'];
    if(close&&!who)return ['Choose who took evasive action, or select Not sure.','evaders'];
    if(close&&['you','both'].includes(who)&&!values('your_actions').length)return ['Choose what you did to avoid a collision.','your-actions'];
    if(close&&['them','both'].includes(who)&&!single('driver_action'))return ['Choose what the driver did, or select Not sure.','driver-actions'];
    if(close&&!single('injured'))return ['Choose whether you were injured.','injuries'];
    return null;
  }
  $('report-form').addEventListener('submit',e=>{
    e.preventDefault();if(previewing)return;
    const error=validation();
    if(error){const target=$(error[1]);const parent=target.closest('fieldset')||target.closest('section');const legend=parent.querySelector(':scope > legend');if(legend)legend.after($('error'));else parent.prepend($('error'));$('error').textContent=error[0];$('error').hidden=false;$('error').focus();$('error').scrollIntoView({block:'center'});return;}
    show(true);
  });
  $('back').addEventListener('click',()=>show(false));
  $('restart').addEventListener('click',()=>{$('report-form').reset();setNow();$('time').disabled=false;$('record').textContent='';$('review').replaceChildren();$('clear-pin').click();show(false);});
  $('example').addEventListener('click',()=>{document.querySelector('[name="report_type"][value="close_call"]').click();[['mode','cycling'],['your_direction','northbound'],['vehicle','car'],['vehicle_direction','southbound'],['movement','left_turn'],['evader','you'],['injured','no']].forEach(([n,v])=>document.querySelector(`[name="${n}"][value="${v}"]`).click());document.querySelectorAll('[name="behaviours"],[name="your_actions"]').forEach(i=>{i.checked=(i.name==='behaviours'&&i.value==='turn_across_path')||(i.name==='your_actions'&&i.value==='halt');});$('route').value='Fictional example: from Laurier and Bank towards Somerset';$('address').value='Fictional example: Bank Street at Laurier Avenue';$('notes').value='Fictional demonstration only. No actual incident.';$('time').disabled=false;$('unknown-time').checked=false;$('time').value='09:00';show(false,false);$('title-1').scrollIntoView({block:'start'});});
  $('app').hidden=false;show(false,false);
})();

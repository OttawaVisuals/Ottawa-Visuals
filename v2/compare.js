'use strict';
const pages = {home:['../index.html','index.html'],traffic:['../Traffic/stops.html','stops.html']};
const query = new URLSearchParams(location.search);
let selected = query.get('page') === 'traffic' ? 'traffic' : 'home';
let mode = ['v1','v2','split'].includes(query.get('view')) ? query.get('view') : (innerWidth < 700 ? 'v2' : 'split');
function showPage() {
  document.getElementById('page').value=selected;
  ['v1','v2'].forEach((version,i)=>{
    const frame=document.getElementById('frame-'+version);
    if(frame.getAttribute('src')!==pages[selected][i]) frame.src=pages[selected][i];
    document.getElementById('open-'+version).href=pages[selected][i];
  });
  save();
}
function showMode(){
  document.querySelector('.frames').classList.toggle('single',mode!=='split');
  ['v1','v2'].forEach(version=>document.getElementById('pane-'+version).hidden=mode!=='split'&&mode!==version);
  document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));
  save();
}
function save(){history.replaceState(null,'',`${location.pathname}?page=${selected}&view=${mode}`);}
document.getElementById('page').addEventListener('change',e=>{selected=e.target.value;showPage();});
document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.mode;showMode();}));
showPage();showMode();

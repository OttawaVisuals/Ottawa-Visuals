// Run instructions and limitations: SITE_AUDIT.md
const fs=require('fs'),path=require('path'),cp=require('child_process');
const root=path.resolve(__dirname,'..'),out=path.join(root,'output/site-audit');
fs.mkdirSync(out,{recursive:true});
const {chromium}=require(require.resolve('playwright',{paths:[out]}));
const origin=process.env.AUDIT_ORIGIN||'http://127.0.0.1:8767';
const files=cp.execFileSync('git',['ls-files','*.html'],{cwd:root,encoding:'utf8'}).trim().split('\n').map(s=>s.trim()).filter(s=>!s.includes('/data/'));
const selected=process.env.AUDIT_PAGES?.split(',');
const pages=files.filter(f=>!selected||selected.includes(f)).filter(f=>!/<meta[^>]+http-equiv=["']refresh/i.test(fs.readFileSync(path.join(root,f),'utf8')));
const axe=fs.readFileSync(require.resolve('axe-core/axe.min.js',{paths:[out]}),'utf8');
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
const jobs=pages.flatMap(file=>process.env.AUDIT_ALL_THEMES ? [320,1280].flatMap(width=>['light','dark','cb'].map(theme=>({file,width,theme}))) : [{file,width:1280,theme:'light'},...['light','dark','cb'].map(theme=>({file,width:320,theme}))]);
const results=[];let n=0;
async function worker(){while(jobs.length){const job=jobs.shift();const ctx=await browser.newContext({viewport:{width:job.width,height:900}});const page=await ctx.newPage();let errors=[],failed=[];
page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failed.push({url:r.url(),status:r.status()})});
await page.addInitScript(theme=>{localStorage.setItem('ov-theme',theme);localStorage.setItem('theme',theme)},job.theme);
try{const route=job.file==='PWHL/player.html'?job.file+'?id=1':job.file==='PWHL/team.html'?job.file+'?code=OTT':job.file;
for(let attempt=0;;attempt++){try{await page.goto(origin+'/'+route,{waitUntil:'load',timeout:30000});break;}catch(error){if(attempt>=2)throw error;await page.waitForTimeout(500);}}
await page.waitForTimeout(1200);
// Retry incomplete local assets before reporting a layout defect.
for(let retry=0;retry<2;retry++){const incomplete=await page.evaluate(()=>[...document.querySelectorAll('link[rel=stylesheet]')].some(l=>l.href.startsWith(location.origin)&&!l.sheet)||[...document.images].some(i=>i.src.startsWith(location.origin)&&i.complete&&!i.naturalWidth));if(!incomplete)break;await page.reload({waitUntil:'load'});await page.waitForTimeout(1200);}
const state=await page.evaluate(()=>({title:document.title,url:location.href,theme:document.documentElement.dataset.theme,scroll:document.documentElement.scrollWidth,
overflow:[...document.querySelectorAll('body *')].filter(e=>{let r=e.getBoundingClientRect();return r.width>0&&r.right>innerWidth+2&&!e.closest('.leaflet-container')&&!['hidden','clip','auto','scroll'].includes(getComputedStyle(e.parentElement||e).overflowX)}).slice(0,15).map(e=>({tag:e.tagName,id:e.id,cls:typeof e.className==='string'?e.className:'',right:Math.round(e.getBoundingClientRect().right)})),
brokenImages:[...document.images].filter(e=>e.getBoundingClientRect().width&&e.complete&&!e.naturalWidth).map(e=>e.src),
displayedErrors:[...document.querySelectorAll('#load-status.error,[role=alert]')].filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height).map(e=>e.textContent.trim()).filter(Boolean),
unlabelledCharts:[...document.querySelectorAll('canvas')].filter(e=>e.getBoundingClientRect().width&&!e.closest('[aria-hidden="true"]')&&!e.hasAttribute('aria-label')&&!e.hasAttribute('aria-labelledby')).map(e=>e.id),
links:[...document.querySelectorAll('a[href]')].map(e=>e.href),h1:document.querySelectorAll('h1').length}));
let violations=[];if(true){await page.addScriptTag({content:axe});violations=(await page.evaluate(async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}))).violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,html:n.html,summary:n.failureSummary}))}));}
results.push({...job,requestedTheme:job.theme,...state,errors,failed,violations});
if(state.scroll>job.width+2||errors.length||job.width===1280)await page.screenshot({path:path.join(out,job.file.replaceAll('/','-')+'-'+job.width+'-'+job.theme+'.png'),fullPage:false});
}catch(e){results.push({...job,error:e.message})}finally{await ctx.close();n++;if(n%10===0)console.log(n+' cases checked');fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));}}}
await Promise.all(Array.from({length:Number(process.env.AUDIT_WORKERS||2)},worker));await browser.close();
const links=[];for(const r of results)for(const href of r.links||[]){const u=new URL(href);if(u.origin!==origin)continue;let p=decodeURIComponent(u.pathname).replace(/^\//,'');let full=path.join(root,p);if(fs.existsSync(full)&&fs.statSync(full).isDirectory())full=path.join(full,'index.html');if(!fs.existsSync(full))links.push({file:r.file,href,reason:'missing file'});else if(u.hash&&full.endsWith('.html')){let html=fs.readFileSync(full,'utf8'),id=decodeURIComponent(u.hash.slice(1));if(!html.includes('id="'+id+'"')&&!html.includes("id='"+id+"'")&&!html.includes('name="'+id+'"'))links.push({file:r.file,href,reason:'fragment not in static HTML (may be generated)'});}}
fs.writeFileSync(path.join(out,'links.json'),JSON.stringify([...new Map(links.map(l=>[JSON.stringify(l),l])).values()],null,2));
console.log(JSON.stringify({pages:pages.length,cases:results.length,overflow:results.filter(r=>r.scroll>r.width+2).map(r=>({file:r.file,width:r.width,theme:r.theme,scroll:r.scroll})),errors:results.filter(r=>r.errors?.length||r.error||r.displayedErrors?.length).map(r=>({file:r.file,errors:r.errors,error:r.error,displayedErrors:r.displayedErrors})),accessibility:results.filter(r=>r.violations?.length).map(r=>({file:r.file,issues:r.violations.map(v=>({id:v.id,count:v.nodes.length}))}))},null,2));
})();

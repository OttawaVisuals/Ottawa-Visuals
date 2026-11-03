// Local functional checks. Start: python -m http.server 8768 --bind 127.0.0.1
// Uses the same temporary Playwright install as scripts/audit_site.cjs.
const fs = require('fs'), path = require('path'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..'), out = path.join(root, 'output/chart-sharing');
fs.mkdirSync(out, {recursive:true});
const {chromium} = require(require.resolve('playwright', {paths:[path.join(root, 'output/site-audit')]}));
const origin = process.env.SHARE_ORIGIN || 'http://127.0.0.1:8768';
const cases = [
  ['Healthcare/healthcare.html', '#spending-chart svg'],
  ['Education/education.html', 'svg[role=group]'],
  ['Tax/tax.html', '#c-rates'],
  ['govcontracts.html', '#c-proc'],
  ['Promises/promises.html', 'svg.tax-chart'],
  ['Traffic/stops.html?section=stops', 'canvas[role=img]'],
  ['Weather/weather.html', 'canvas[role=img]'],
  ['PWHL/pwhl.html', 'canvas[role=img]']
].filter(([file])=>!process.env.SHARE_PAGES||process.env.SHARE_PAGES.split(',').includes(file));
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const results = [];
  try {
    for (const width of (process.env.SHARE_WIDTHS||'1280,390').split(',').map(Number)) for (const theme of (process.env.SHARE_THEMES||'light,dark,cb').split(',')) for (const [file, selector] of cases) {
      const ctx = await browser.newContext({viewport:{width,height:900}, permissions:['clipboard-read','clipboard-write']});
      const page = await ctx.newPage(), errors = [];
      page.setDefaultTimeout(15000); page.setDefaultNavigationTimeout(30000);
      page.on('pageerror', e => errors.push(e.message));
      try {
        await page.addInitScript(theme => {localStorage.setItem('ov-theme',theme);localStorage.setItem('theme',theme)}, theme);
        await page.goto(`${origin}/${file}`, {waitUntil:'networkidle'});
        const chart = page.locator(selector).filter({visible:true}).first();
        // Some reports have no chart in the default tab; record that coverage gap.
        if (!(await chart.count())) { results.push({file,width,theme,skip:'No chart in default view'}); continue; }
        await chart.waitFor({state:'visible'});
        const chartId = await chart.getAttribute('id');
        await page.waitForFunction(id => [...document.querySelectorAll('.ov-chart-share button')].some(b=>b.getAttribute('aria-label')?.includes('Share chart:')) && document.getElementById(id), chartId);
        const trigger = page.getByRole('button',{name:'Share chart: '+await chart.evaluate(el=>(el.dataset.shareTitle||el.getAttribute('aria-label')||el.querySelector('title')?.textContent||el.closest('article,section,.card,.panel,.rcard')?.querySelector('h3,h2')?.textContent||'Chart').replace(/[.;]?\s*(A data table follows|values in the data table below|Values follow the chart)\.?$/i,'')),exact:true}).first();
        await trigger.click();
        await page.locator('.ov-share-download').waitFor({state:'visible'});
        await page.locator('.ov-share-preview').evaluate(img=>img.decode());
        const state = await page.evaluate(() => ({
          width:document.documentElement.scrollWidth,
          imageWidth:document.querySelector('.ov-share-preview').naturalWidth,
          imageHeight:document.querySelector('.ov-share-preview').naturalHeight,
          link:document.querySelector('.ov-share-link').value,
          statusText:document.querySelector('.ov-share-dialog [role=status]').textContent
        }));
        assert.equal(state.imageWidth,1200); assert.ok(state.imageHeight>300);
        assert.ok(state.width<=width+2, `Overflow: ${state.width}`);
        assert.ok(state.link.startsWith('https://ottawavisuals.github.io/Ottawa-Visuals/'));
        assert.ok(new URL(state.link).hash);
        await page.getByRole('button',{name:'Copy link',exact:true}).click();
        assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),state.link);
        await page.getByRole('button',{name:'Copy image',exact:true}).click();
        await page.waitForFunction(()=>document.querySelector('.ov-share-dialog [role=status]').textContent.startsWith('Image'));
        assert.equal(await page.locator('.ov-share-dialog [role=status]').textContent(),'Image copied.');
        assert.ok(await page.evaluate(async()=>(await navigator.clipboard.read()).some(item=>item.types.includes('image/png'))));
        if (width===1280 && theme==='light') {
          const event = page.waitForEvent('download'); await page.locator('.ov-share-download').click();
          await (await event).saveAs(path.join(out,file.replace(/[/?=]/g,'-')+'.png'));
          await page.screenshot({path:path.join(out,file.replace(/[/?=]/g,'-')+'-preview.png')});
        }
        if (file.startsWith('Healthcare') && width===390 && theme==='dark') await page.screenshot({path:path.join(out,'phone-dark-preview.png')});
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('.ov-share-dialog').evaluate(d=>d.open),false);
        assert.equal(await trigger.evaluate(el=>document.activeElement===el),true);
        assert.deepEqual(errors,[]);
        results.push({file,width,theme,...state,pass:true});
      } catch (error) { results.push({file,width,theme,error:error.message,errors}); }
      finally { await ctx.close(); }
      fs.writeFileSync(path.join(out,process.env.SHARE_RESULTS||'checks.json'),JSON.stringify(results,null,2));
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify({passed:results.filter(r=>r.pass).length,skipped:results.filter(r=>r.skip),failed:results.filter(r=>!r.pass&&!r.skip)},null,2));
  if (results.some(r=>!r.pass&&!r.skip)) process.exitCode=1;
})();

/* Local PNG snapshots of native charts. No uploads or third-party dependencies.
   Optional data-share-title/source/note on a chart override its nearby context. */
(() => {
  'use strict';
  const scriptURL = document.currentScript.src;
  const css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = new URL('chart-sharing.css?v=20261103', scriptURL);
  document.head.append(css);
  const entries = new Map();
  const clean = value => (value || '').replace(/\s+/g, ' ').trim();
  const visible = el => !!el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const ignored = '.ov-chart-share,.ov-chart-values,dialog,header,nav,footer,button,.leaflet-container,[aria-hidden="true"]';
  let dialog, preview, status, download, copyImage, copyLink, current, returnFocus, imageURL, request = 0;

  function chartTitle(el) {
    return clean(el.dataset.shareTitle || el.getAttribute('aria-label') ||
      el.querySelector('title')?.textContent || el.closest('article,section,.card,.panel,.rcard')?.querySelector('h3,h2')?.textContent || 'Chart')
      .replace(/[.;]?\s*(A data table follows|values in the data table below)\.?$/i, '');
  }
  function chartLink(el) {
    const url = new URL(location.href);
    url.hash = el.id;
    // Local previews should still produce a usable public report link.
    if (['localhost', '127.0.0.1'].includes(url.hostname)) {
      const base = new URL('../', scriptURL).pathname;
      url.pathname = '/Ottawa-Visuals/' + url.pathname.slice(base.length);
      url.protocol = 'https:'; url.host = 'ottawavisuals.github.io'; url.port = '';
    }
    return url.href;
  }
  function context(el) {
    const local = el.closest('article,figure,.chart-panel,.rcard,.card,section') || el.parentElement;
    const scope = el.closest('section') || local;
    const paragraphs = [...scope.querySelectorAll('p,.notice,.inset,.callout,.section-note,.chart-sub')]
      .filter(p => visible(p) && !p.closest('details,.stats,.stat,.ov-chart-share,.readout') &&
        !p.querySelector('p') && !p.matches('.eyebrow,.q,.readout'));
    const controls = [...new Set([...scope.querySelectorAll('select,input[type=checkbox],input[type=radio],input[type=range],input[type=number],input[type=search],button[aria-pressed=true]'),
      ...document.querySelectorAll('#season-select')])]
      .filter(c => visible(c) && !c.closest(ignored));
    const choices = controls.map(c => {
      if (c.tagName === 'BUTTON') return clean(c.textContent);
      const labelNode = c.labels?.[0]?.cloneNode(true);
      labelNode?.querySelectorAll('select,input,button').forEach(node => node.remove());
      const label = clean(labelNode?.textContent || c.getAttribute('aria-label') || c.id);
      const name = c.tagName === 'SELECT' ? clean(c.selectedOptions[0]?.textContent) :
        ['checkbox','radio'].includes(c.type) ? (c.checked ? 'Yes' : 'No') : c.value;
      return `${label}: ${name}`;
    });
    // Legends live outside the canvas in several reports. Retain their colours.
    let legendNodes = [...local.querySelectorAll('.legend,.chart-legend,[id^="lg-"]')];
    if (!legendNodes.length) legendNodes = [...scope.querySelectorAll('.legend,.chart-legend,[id^="lg-"]')];
    if (legendNodes.length > 1) {
      let node = el.parentElement?.querySelectorAll('canvas,svg').length === 1 ? el.parentElement : el;
      let nearest;
      while ((node = node.previousElementSibling)) {
        if (node.matches('.legend,.chart-legend,[id^="lg-"]')) { nearest = node; break; }
        if (node.matches('canvas,svg') || node.querySelector('canvas,svg[viewBox]')) break;
      }
      legendNodes = nearest ? [nearest] : [];
    }
    const legends = legendNodes
      .filter(visible).flatMap(legend => [...legend.children].map(item => {
        const swatch = item.querySelector('i,.key,.swatch');
        return { text: clean(item.textContent), color: swatch ? getComputedStyle(swatch).backgroundColor : null };
      })).filter(item => item.text);
    const heading = local.querySelector('.chart-heading');
    const notes = [...new Set([
      heading ? [...heading.children].map(child => clean(child.textContent)).join(' · ') : '',
      ...paragraphs.map(p => clean(p.textContent)),
      clean(el.dataset.shareNote)
    ].filter(Boolean))];
    const explicitSource = el.dataset.shareSource;
    const source = explicitSource || paragraphs.map(p => clean(p.textContent)).find(t => /^(historical )?sources?:/i.test(t));
    if (source) { const i = notes.indexOf(source); if (i >= 0) notes.splice(i, 1); }
    return { choices: [...new Set(choices)].join(' · '), legends, notes, source };
  }
  function lines(ctx, value, width) {
    // Split long URLs and tokens as well as ordinary prose; never crop notes.
    const result = []; let line = '';
    for (const word of String(value).split(/\s+/)) {
      if (ctx.measureText(line + (line ? ' ' : '') + word).width <= width) { line += (line ? ' ' : '') + word; continue; }
      if (line) result.push(line); line = '';
      for (const char of word) {
        if (ctx.measureText(line + char).width > width) { result.push(line); line = ''; }
        line += char;
      }
    }
    if (line) result.push(line);
    return result;
  }
  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image(); img.onload = () => resolve(img); img.onerror = () => reject(new Error('Could not prepare this chart.'));
      img.src = url;
    });
  }
  async function chartImage(el) {
    if (el.tagName.toLowerCase() === 'canvas') {
      // Pause animated custom charts before capturing a complete frame.
      el.ovPauseChart?.();
      const chart = window.Chart?.getChart?.(el);
      if (!chart) {
        const layers = el.ovChartContainer?.querySelectorAll('canvas');
        if (layers?.length > 1) {
          const rect = el.ovChartContainer.getBoundingClientRect();
          const composite = document.createElement('canvas');
          composite.width = Math.round(rect.width * 2); composite.height = Math.round(rect.height * 2);
          const ctx = composite.getContext('2d'); ctx.scale(2, 2);
          layers.forEach(layer => {
            if (!visible(layer)) return;
            const box = layer.getBoundingClientRect();
            ctx.drawImage(layer, box.left - rect.left, box.top - rect.top, box.width, box.height);
          });
          const year = el.ovChartContainer.querySelector('.spiral-year');
          if (year) {
            const box = year.getBoundingClientRect(), style = getComputedStyle(year);
            ctx.fillStyle = style.color; ctx.font = `${style.fontWeight} ${style.fontSize} Arial, sans-serif`;
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText(year.textContent, box.left - rect.left + box.width / 2, box.top - rect.top + box.height / 2);
          }
          return loadImage(composite.toDataURL('image/png'));
        }
        return loadImage(el.toDataURL('image/png'));
      }
      const ratio = chart.options.devicePixelRatio;
      try {
        chart.stop();
        chart.options.devicePixelRatio = Math.min(4, Math.max(ratio || 1, 2208 / chart.width));
        chart.resize(); chart.update('none');
        return loadImage(el.toDataURL('image/png'));
      } finally {
        chart.options.devicePixelRatio = ratio;
        chart.resize(); chart.update('none');
      }
    }
    const clone = el.cloneNode(true);
    const originals = [el, ...el.querySelectorAll('*')], copies = [clone, ...clone.querySelectorAll('*')];
    const properties = ['fill','fill-opacity','stroke','stroke-width','stroke-opacity','stroke-dasharray','stroke-dashoffset','stroke-linecap','stroke-linejoin','opacity','color','font-family','font-size','font-weight','font-style','text-anchor','dominant-baseline','letter-spacing','display','visibility','paint-order'];
    originals.forEach((node, i) => {
      const style = getComputedStyle(node);
      copies[i].removeAttribute('class');
      copies[i].removeAttribute('style');
      properties.forEach(name => copies[i].style.setProperty(name, style.getPropertyValue(name)));
    });
    clone.querySelectorAll('script,foreignObject').forEach(node => node.remove());
    const box = el.viewBox.baseVal, rect = el.getBoundingClientRect();
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', box.width || rect.width); clone.setAttribute('height', box.height || rect.height);
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], {type:'image/svg+xml'}));
    try { return await loadImage(url); } finally { URL.revokeObjectURL(url); }
  }
  async function snapshot(el) {
    await document.fonts.ready;
    const title = chartTitle(el), meta = context(el), url = chartLink(el);
    const image = await chartImage(el);
    const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d');
    const width = 1200, pad = 48, contentWidth = width - pad * 2;
    const style = getComputedStyle(document.documentElement);
    const background = style.getPropertyValue('--bg-2').trim() || '#fff';
    const ink = style.getPropertyValue('--ink').trim() || '#1c2b3a';
    const muted = style.getPropertyValue('--ink-2').trim() || '#536579';
    const blocks = []; let y = pad;
    function add(value, size = 20, colour = muted, weight = 'normal', gap = 12) {
      if (!value) return;
      ctx.font = `${weight} ${size}px Arial, sans-serif`;
      const wrapped = lines(ctx, value, contentWidth);
      blocks.push({wrapped,size,colour,weight,y}); y += wrapped.length * size * 1.4 + gap;
    }
    add('OTTAWA VISUALS', 19, ink, 'bold');
    add(title, 32, ink, 'bold', 16);
    add(meta.choices, 19);
    const chartY = y, chartHeight = contentWidth * image.height / image.width;
    y += chartHeight + 20;
    // Keep a label beside every swatch so colour is never the only key.
    for (const item of meta.legends) {
      ctx.font = '20px Arial, sans-serif';
      const wrapped = lines(ctx, item.text, contentWidth - 34);
      blocks.push({wrapped,size:20,colour:ink,weight:'normal',y,swatch:item.color});
      y += wrapped.length * 28 + 8;
    }
    y += meta.legends.length ? 10 : 0;
    meta.notes.forEach(note => add(note));
    add(meta.source || 'Sources, definitions and limitations: see the full report.', 19);
    add(url, 18);
    add('Ottawa Visuals · Current chart view', 18, ink, 'bold', 0);
    canvas.width = width; canvas.height = Math.ceil(y + pad);
    ctx.fillStyle = background; ctx.fillRect(0, 0, width, canvas.height);
    ctx.drawImage(image, pad, chartY, contentWidth, chartHeight);
    blocks.forEach(block => {
      ctx.font = `${block.weight} ${block.size}px Arial, sans-serif`;
      ctx.fillStyle = block.colour; ctx.textBaseline = 'top';
      const offset = 'swatch' in block ? 34 : 0;
      block.wrapped.forEach((line, i) => ctx.fillText(line, pad + offset, block.y + i * block.size * 1.4));
      if (block.swatch && !['transparent','rgba(0, 0, 0, 0)'].includes(block.swatch)) {
        ctx.fillStyle = block.swatch; ctx.fillRect(pad, block.y + 4, 20, 16);
      }
    });
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error('Could not prepare this image.');
    return {blob,title,url};
  }
  function button(label, action) {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = label; b.addEventListener('click', action); return b;
  }
  function buildDialog() {
    dialog = document.createElement('dialog'); dialog.className = 'ov-share-dialog';
    dialog.setAttribute('aria-labelledby', 'ov-share-heading');
    const head = document.createElement('div'); head.className = 'ov-share-head';
    const heading = document.createElement('h2'); heading.id = 'ov-share-heading'; heading.textContent = 'Share chart';
    const close = button('Close', () => dialog.close()); head.append(heading, close);
    const help = document.createElement('p');
    help.textContent = 'The image captures this view. The link opens the chart; filters may reset. Source notes stay in the image.';
    const actions = document.createElement('div'); actions.className = 'ov-share-actions';
    download = document.createElement('a'); download.textContent = 'Download PNG'; download.className = 'ov-share-download';
    copyImage = button('Copy image', async () => {
      try { await navigator.clipboard.write([new ClipboardItem({'image/png':current.blob})]); status.textContent = 'Image copied.'; }
      catch { status.textContent = 'Image copy is unavailable. Use Download PNG.'; }
    });
    copyLink = button('Copy link', async () => {
      try { await navigator.clipboard.writeText(current.url); status.textContent = 'Chart link copied. Filters may reset when opened.'; }
      catch { status.textContent = 'Link copy is unavailable. Select the link below and copy it.'; }
    });
    actions.append(download, copyImage, copyLink);
    status = document.createElement('p'); status.setAttribute('role','status');
    const link = document.createElement('input'); link.type = 'text'; link.readOnly = true;
    link.className = 'ov-share-link'; link.setAttribute('aria-label','Chart link');
    link.addEventListener('click', () => link.select());
    preview = document.createElement('img'); preview.className = 'ov-share-preview';
    dialog.append(head, help, actions, status, link, preview); document.body.append(dialog);
    dialog.addEventListener('close', () => {
      request++;
      if (imageURL) URL.revokeObjectURL(imageURL);
      imageURL = null; current = null; preview.removeAttribute('src');
      returnFocus?.focus();
    });
  }
  async function open(el, trigger) {
    if (!dialog) buildDialog();
    returnFocus = trigger; current = null;
    const pending = ++request;
    preview.hidden = true; download.hidden = true; copyImage.disabled = copyLink.disabled = true;
    dialog.querySelector('input').value = chartLink(el);
    status.textContent = 'Preparing image…'; dialog.showModal();
    try {
      const result = await snapshot(el);
      if (!dialog.open || pending !== request) return;
      current = result;
      imageURL = URL.createObjectURL(current.blob);
      preview.src = imageURL; preview.alt = `Snapshot: ${current.title}`; preview.hidden = false;
      download.href = imageURL; download.download = `ottawa-visuals-${el.id}.png`; download.hidden = false;
      copyImage.disabled = !(window.isSecureContext && navigator.clipboard?.write && window.ClipboardItem);
      copyLink.disabled = !navigator.clipboard?.writeText;
      status.textContent = copyImage.disabled ? 'Image ready. Use Download PNG to save it.' : 'Image ready to copy or download.';
    } catch (error) { if (dialog.open && pending === request) status.textContent = 'Could not create this chart image. Try again after the chart finishes loading.'; }
  }
  function scan() {
    entries.forEach((entry, el) => {
      if (!el.isConnected) { entry.remove(); entries.delete(el); }
      else entry.hidden = !visible(el);
    });
    const charts = document.querySelectorAll('canvas[role="img"],canvas[data-ov-chart-table],svg.chart,svg.spark,svg[role="img"],svg[role="group"][aria-label]');
    charts.forEach(el => {
      if (el.closest(ignored) || !visible(el)) return;
      const parent = el.parentElement;
      const container = el.ovChartContainer || el.closest('.spiral-wrap') || (parent && /chart|canvas|cw|donut/.test(parent.className) && parent.querySelectorAll('canvas,svg').length === 1 ? parent : el);
      if (entries.has(el)) {
        const bar = entries.get(el);
        if (bar.previousElementSibling !== container) container.after(bar);
        bar.querySelector('button').setAttribute('aria-label', `Share chart: ${chartTitle(el)}`);
        return;
      }
      if (el.tagName.toLowerCase() === 'svg' && !el.querySelector('text')) return;
      if (el.tagName.toLowerCase() === 'canvas' && !el.width) return;
      // Prefer an existing chart wrapper ID for a durable deep link.
      if (!el.id) el.id = container !== el && container.id ? `ov-share-${container.id}` :
        `ov-share-${el.closest('[id]')?.id || 'chart'}-${[...charts].indexOf(el) + 1}`;
      const bar = document.createElement('div'); bar.className = 'ov-chart-share';
      const trigger = button('Share chart', () => open(el, trigger));
      trigger.setAttribute('aria-haspopup','dialog');
      trigger.setAttribute('aria-label', `Share chart: ${chartTitle(el)}`);
      bar.append(trigger); container.after(bar); entries.set(el, bar);
      el.style.scrollMarginTop = '90px';
    });
    if (location.hash) {
      let id;
      try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
      if (id.startsWith('ov-share-')) {
        const target = document.getElementById(id);
        if (target && visible(target) && !target.dataset.shareLinked) { target.dataset.shareLinked = 'true'; target.scrollIntoView(); }
      }
    }
  }
  let timer;
  function schedule() { clearTimeout(timer); timer = setTimeout(scan, 150); }
  function start() {
    scan(); new MutationObserver(schedule).observe(document.body, {childList:true,subtree:true});
    document.addEventListener('change', schedule);
    // Charts in tabs/details become visible without DOM children changing.
    document.addEventListener('click', schedule); document.addEventListener('toggle', schedule, true);
    let tries = 0; const interval = setInterval(() => { scan(); if (++tries >= 20) clearInterval(interval); }, 500);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();

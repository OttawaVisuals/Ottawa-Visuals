/* Shared author credit. Included with the site theme; URLs resolve from this asset,
   so root, report, detail and nested preview pages use the same destinations. */
(() => {
  const home = new URL('../index.html', document.currentScript.src);
  const contact = new URL('#contact', home);
  const css = document.createElement('style');
  css.textContent = `
    .ov-author-button{flex:none;white-space:nowrap;font:12px/1.4 system-ui,sans-serif!important;color:#fff!important;background:transparent!important;border:1px solid #8799ad!important;border-radius:999px!important;padding:4px 9px!important;margin:0 6px!important;cursor:pointer}
    .ov-author-button[hidden]{display:none!important}
    .ov-author-button:focus-visible,.ov-author-panel a:focus-visible,.ov-author-close:focus-visible{outline:2px solid #E8A124;outline-offset:3px}
    .ov-author-line{display:flex!important;flex-wrap:wrap;justify-content:center;align-items:center;gap:6px 12px;box-sizing:border-box;max-width:1280px;margin:16px auto 0!important;padding:12px 16px!important;background:var(--bg-2,#fff);color:var(--ink,#1C2B3A);border:1px solid var(--line,#D2D8E3);border-radius:8px;font:12px/1.5 system-ui,sans-serif!important;text-align:center;flex-shrink:0}
    .ov-author-line a{color:inherit!important;text-decoration:underline!important;font:inherit!important}
    .ov-author-panel{position:fixed;top:64px;right:16px;width:340px;max-width:calc(100vw - 32px);max-height:calc(100dvh - 88px);overflow:auto;box-sizing:border-box;z-index:10000;background:var(--bg-2,#fff);color:var(--ink,#1C2B3A);border:1px solid var(--line,#D2D8E3);border-radius:12px;box-shadow:0 8px 28px #0004;padding:20px;font:14px/1.6 system-ui,sans-serif;text-align:left}
    .ov-author-panel[hidden]{display:none!important}
    .ov-author-panel p{margin:0 0 12px}
    .ov-author-panel h2{margin:0 24px 12px 0;font:600 19px/1.3 system-ui,sans-serif;color:inherit}
    .ov-author-panel a{color:var(--accent,#A86E0F);text-decoration:underline}
    .ov-author-close{position:absolute;top:10px;right:12px;background:transparent;color:inherit;border:0;font:24px/1 system-ui,sans-serif;cursor:pointer;padding:4px}
  `;
  document.head.append(css);

  function link(text, href) {
    const a = document.createElement('a');
    a.textContent = text;
    a.href = href;
    return a;
  }
  function build() {
    if (document.querySelector('.ov-author-line')) return;
    const line = document.createElement('div');
    line.className = 'ov-author-line';
    const credit = document.createElement('span');
    credit.textContent = 'Built by Simon';
    line.append(credit, link('All reports', home), link('Get in touch', contact));
    let footer = document.querySelector('footer');
    if (!footer) {
      footer = document.createElement('footer');
      // This calculator scrolls its results independently of the fixed-height shell.
      (document.querySelector('main.results-col') || document.querySelector('main') || document.body).append(footer);
    }
    footer.append(line);

    const header = document.querySelector('.topbar') || document.querySelector('header');
    if (!header) return;
    const baselineOverflow = Math.max(0, header.scrollWidth - header.clientWidth);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ov-author-button';
    button.textContent = 'Built by Simon';
    button.setAttribute('aria-label', 'Built by Simon');
    button.setAttribute('aria-haspopup', 'dialog');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', 'ov-author-panel');
    const theme = header.querySelector('.ov-theme-toggle');
    if (theme) theme.before(button);
    else (header.querySelector('.topbar-inner') || header).append(button);

    const panel = document.createElement('div');
    panel.id = 'ov-author-panel';
    panel.className = 'ov-author-panel';
    panel.hidden = true;
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-labelledby', 'ov-author-title');
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'ov-author-close';
    close.textContent = '×';
    close.setAttribute('aria-label', 'Close author information');
    const title = document.createElement('h2');
    title.id = 'ov-author-title';
    title.textContent = 'Simon · Ottawa, ON';
    const bio = document.createElement('p');
    bio.textContent = 'I turn public data into interactive charts, maps and tools about Ottawa, Ontario and Canada—making complex topics easier to explore and understand.';
    const note = document.createElement('p');
    note.textContent = 'Ottawa Visuals is a personal project. Each report explains its sources, methods and limitations. Views are my own. Built with AI as a coding assistant.';
    const links = document.createElement('p');
    links.append(link('All reports', home), ' · ', link('Get in touch', contact));
    panel.append(close, title, bio, note, links);
    document.body.append(panel);
    function hide(restoreFocus = false) {
      panel.hidden = true;
      button.setAttribute('aria-expanded', 'false');
      if (restoreFocus) button.focus();
    }
    button.addEventListener('click', () => {
      if (!panel.hidden) return hide(true);
      panel.hidden = false;
      button.setAttribute('aria-expanded', 'true');
      close.focus();
    });
    close.addEventListener('click', () => hide(true));
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !panel.hidden) hide(true);
    });
    document.addEventListener('click', e => {
      if (!panel.hidden && !panel.contains(e.target) && !button.contains(e.target)) hide();
    });
    function fit() {
      button.hidden = false;
      button.textContent = 'Built by Simon';
      if (header.scrollWidth > header.clientWidth + baselineOverflow + 1) button.textContent = 'Simon';
      if (header.scrollWidth > header.clientWidth + baselineOverflow + 1) {
        button.hidden = true;
        hide();
      }
    }
    fit();
    window.addEventListener('resize', fit);
    window.addEventListener('load', fit);
    if (document.fonts) document.fonts.ready.then(fit);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();

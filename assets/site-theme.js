/* Ottawa Visuals shared theme: light / dark / colour-blind switch.
   Pair with assets/site-theme.css. Include right after the page's own
   pre-render theme script in <head> (it runs synchronously, so it can
   still correct data-theme before first paint).

   - Storage: pages read 'ov-theme'. The Energy site (Retrofit Explorer, same
     github.io origin) reads 'theme'. Both are written so a choice made on
     either site carries over; on first visit an Energy choice is adopted.
   - The page's own #theme-toggle stays in the DOM (hidden by the CSS) because
     several pages bind their chart re-render to it. The pill drives the page
     through window.setTheme() where the page exposes one; otherwise through
     that hidden button (light <-> dark) or a reload (to/from colour-blind),
     since a reload makes every chart re-read the CSS tokens. */
(function () {
  var MODES = ['light', 'dark', 'cb'];
  var root = document.documentElement;
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(m) { try { localStorage.setItem('ov-theme', m); localStorage.setItem('theme', m); } catch (e) {} }

  // First visit here but a choice exists from the Energy site: adopt it.
  var ov = get('ov-theme'), en = get('theme');
  if (!ov && MODES.indexOf(en) >= 0) { root.setAttribute('data-theme', en); try { localStorage.setItem('ov-theme', en); } catch (e) {} }
  if (MODES.indexOf(root.getAttribute('data-theme')) < 0) root.setAttribute('data-theme', 'light');

  // Fraunces for display type (Inter is already loaded by every page).
  var f = document.createElement('link');
  f.rel = 'stylesheet';
  f.href = 'https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;1,9..144,300&display=swap';
  document.head.appendChild(f);

  var ICONS = {
    light: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.4v2.3M12 19.3v2.3M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.4 12h2.3M19.3 12h2.3M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6"/></svg>',
    dark: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 14.6A8.6 8.6 0 019.4 3.5a8.6 8.6 0 1011.1 11.1z"/></svg>',
    cb: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M1.9 12S5.6 5.3 12 5.3 22.1 12 22.1 12 18.4 18.7 12 18.7 1.9 12 1.9 12z"/><circle cx="12" cy="12" r="2.9"/></svg>'
  };
  var LABELS = { light: 'Light theme', dark: 'Dark theme', cb: 'Colour-blind friendly theme' };

  function apply(mode) {
    var cur = root.getAttribute('data-theme');
    if (mode === cur) return;
    put(mode);
    if (typeof window.setTheme === 'function') { window.setTheme(mode); put(mode); return; }
    var old = document.getElementById('theme-toggle');
    if (old && mode !== 'cb' && cur !== 'cb') { old.click(); put(mode); return; }
    root.setAttribute('data-theme', mode);
    location.reload();
  }

  function build() {
    var old = document.getElementById('theme-toggle');
    if (!old || document.querySelector('.ov-theme-toggle')) return;
    var pill = document.createElement('div');
    pill.className = 'ov-theme-toggle';
    pill.setAttribute('role', 'group');
    pill.setAttribute('aria-label', 'Colour theme');
    MODES.forEach(function (m) {
      var b = document.createElement('button');
      b.type = 'button'; b.dataset.mode = m; b.title = LABELS[m]; b.setAttribute('aria-label', LABELS[m]);
      b.innerHTML = ICONS[m];
      b.addEventListener('click', function () { apply(m); sync(); });
      pill.appendChild(b);
    });
    old.parentNode.insertBefore(pill, old.nextSibling);
    sync();
    new MutationObserver(sync).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
  }
  function sync() {
    var cur = root.getAttribute('data-theme');
    document.querySelectorAll('.ov-theme-toggle button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.mode === cur));
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();

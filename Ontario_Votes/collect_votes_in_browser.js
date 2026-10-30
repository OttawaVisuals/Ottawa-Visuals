// Run in YOUR browser console on any https://www.ola.org page (same origin).
// Reads the Votes search listing (all sessions), then each vote's detail page,
// slowly, and downloads ontario_votes.json. ola.org blocks scripts outside a
// browser, so this runs in your own session. Stops on the first 403/429.
//
// Output: [{url, title, movedBy, parliament, date, outcome, ayes, nays,
//           members: [{vote, name, party, riding, profile}]}]
(async () => {
  const DELAY_MS = 2000, LISTING_PAGES = 16;           // 317 results, 20 per page
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const base = 'https://www.ola.org/en/legislative-business/votes-search';
  const qs = 'title=&field_parliament_sessions_target_id=All&field_date_time_after=&field_date_time_before=' +
    '&field_business_type_target_id=All&field_type_target_id=All&field_vote_outcome_target_id=All&page=';
  const get = async url => {
    const r = await fetch(url, { credentials: 'same-origin' });
    if (r.status === 403 || r.status === 429) throw new Error('Blocked: HTTP ' + r.status + ' at ' + url);
    if (!r.ok) throw new Error('HTTP ' + r.status + ' at ' + url);
    return new DOMParser().parseFromString(await r.text(), 'text/html');
  };
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();

  const links = new Set();
  for (let p = 0; p < LISTING_PAGES; p++) {
    const doc = await get(base + '?' + qs + p);
    doc.querySelectorAll('a[href*="/votes-search/parliament-"]').forEach(a => links.add(new URL(a.getAttribute('href'), base).href.split('#')[0]));
    console.log('listing page', p + 1, '/', LISTING_PAGES, '-> votes so far:', links.size);
    await sleep(DELAY_MS);
  }

  const parse = (doc, url) => {
    const head = doc.querySelector('.votes-detail-header-container');
    const text = clean(head && head.textContent);
    const counts = text.match(/Ayes\s*(\d+)\s*Nays\s*(\d+)/);
    const members = [], seen = new Set();
    let vote = '';
    doc.querySelectorAll('.view-content h3.lao-heading, .view-content .photo-card-pattern').forEach(el => {
      if (el.matches('h3')) { vote = clean(el.textContent); return; }
      const a = el.querySelector('a.photo-card-link'), profile = a ? a.getAttribute('href') : '';
      const m = { vote, name: clean(el.querySelector('h4') && el.querySelector('h4').textContent),
                  party: clean(el.querySelector('.card-heading') && el.querySelector('.card-heading').textContent),
                  riding: clean(el.querySelector('.card-subheading') && el.querySelector('.card-subheading').textContent), profile };
      const k = vote + '|' + (profile || m.name);
      if (!seen.has(k)) { seen.add(k); members.push(m); }
    });
    const rel = doc.querySelector('.votes-meta a');
    return {
      url, title: clean(doc.querySelector('h1') && doc.querySelector('h1').textContent),
      movedBy: clean(doc.querySelector('.votes-meta h2') && doc.querySelector('.votes-meta h2').textContent),
      parliament: clean(doc.querySelector('.vote-meta-parliament') && doc.querySelector('.vote-meta-parliament').textContent),
      date: (doc.querySelector('time.divisions-meta-date') || {}).getAttribute ? doc.querySelector('time.divisions-meta-date').getAttribute('datetime') : '',
      outcome: (text.match(/Outcome\s*(Carried|Lost)/) || [])[1] || '',
      ayes: counts ? +counts[1] : null, nays: counts ? +counts[2] : null,
      motionUrl: rel ? rel.getAttribute('href') : '', members,
    };
  };

  const out = [], list = [...links];
  try {
    for (let i = 0; i < list.length; i++) {
      out.push(parse(await get(list[i]), list[i]));
      if ((i + 1) % 10 === 0) console.log('vote pages', i + 1, '/', list.length);
      await sleep(DELAY_MS);
    }
  } catch (e) { console.error(e.message, '- saving what was collected so far'); }

  const blob = new Blob([JSON.stringify(out)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'ontario_votes.json'; a.click();
  console.log('Done:', out.length, 'of', list.length, 'votes. Check your Downloads folder.');
})();

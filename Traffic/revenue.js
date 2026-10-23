/* "Ticket revenue" tab: scenario estimates, not published revenue. Uses stops.js helpers (stat, panel, chart, $, fmt). */
'use strict';
const REV_FILE = 'data/ops_annual_report_traffic.csv';
const REV_DEFAULTS = {fine: '150', paid: '80', share: '75', conv: '50'};
const REV_SLIDERS = [
  ['fine', 'Average fine per ticket', 50, 400, 5, v => `$${v}`],
  ['paid', 'Share of tickets actually paid', 40, 100, 5, v => `${v}%`],
  ['share', 'Share of paid fines the City keeps', 50, 100, 5, v => `${v}%`],
  ['conv', 'Share of warnings that would have been tickets', 0, 100, 5, v => `${v}%`],
];
let revTickets;

async function loadRevTickets() {
  if (revTickets) return revTickets;
  const response = await fetch(REV_FILE);
  if (!response.ok) throw new Error(`${REV_FILE}: HTTP ${response.status}`);
  revTickets = window.ovParseCsv(await response.text())
    .filter(r => r.metric === 'poa_part1_tickets_total' && r.value !== '' && Number(r.year) <= 2024)
    .map(r => [Number(r.year), Number(r.value)]).sort((a, b) => a[0] - b[0]);
  return revTickets;
}

async function renderRevenue(state, token) {
  const tickets = await loadRevTickets();
  if (token !== generation) return;
  const p = data.police;
  $('section-kicker').textContent = '06 · Enforcement revenue';
  $('section-title').textContent = 'What are the tickets worth?';
  $('section-description').textContent = 'Ticket counts fell far faster than warnings. This puts a dollar range on that, using assumptions you can change.';
  $('filter-scope').textContent = 'Scenario estimates, not published revenue: the City does not report fine revenue by ticket or by police service. The defaults are placeholders. Move the sliders to test your own.';
  $('filters').innerHTML = REV_SLIDERS.map(([id, label, min, max, step, show]) =>
    `<label for="${id}">${label}: <strong id="${id}-out">${show(state[id])}</strong><input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${state[id]}"></label>`).join('');
  REV_SLIDERS.forEach(([id, , , , , show]) => $(id).addEventListener('input', () => {
    state[id] = $(id).value;
    $(`${id}-out`).textContent = show(state[id]);
    saveState();
    drawRevenue(state, tickets, p);
  }));
  $('panels').innerHTML = '<div class="grid">' +
    panel('rev-tickets', 'Estimated fine revenue from OPS Part I tickets', 'Annual-report ticket totals, 2019 to 2024 (2022 to 2024 are the reports’ rounded “nearly” figures). Millions of dollars. Excludes speed and red-light cameras, which are City tickets.', true) +
    panel('rev-warn', 'Fines not collected because the stop ended in a warning', 'Warnings recorded in traffic stops, 2014 to 2024, times the share you choose, at the same fine and paid share. A floor: warnings given outside recorded traffic stops are not counted. Millions of dollars.', true) +
    panel('rev-index', 'Charges and warnings, indexed to 2019 = 100', 'Traffic-stop outcomes. “Charged” counts stops that ended in a charge, not the number of charges.', true) + '</div>';
  drawRevenue(state, tickets, p);
}

function drawRevenue(state, tickets, p) {
  charts.forEach(c => c.destroy()); charts = [];
  const fine = Number(state.fine), paid = Number(state.paid) / 100, share = Number(state.share) / 100, conv = Number(state.conv) / 100;
  const m = n => Math.round(n / 1e4) / 100;
  const stopsBy = outcome => p.years.map(y => sum(p.annual.filter(r => r[0] === y && r[1] === outcome).map(r => r[2])));
  const warnings = stopsBy('Warning (T-Stop)'), charged = stopsBy('Charged');
  const gross = tickets.map(([, n]) => n * fine * paid);
  const lost = warnings.map(n => n * conv * fine * paid);
  const dollars = {label: ctx => `${ctx.dataset.label}: $${fmt(ctx.raw)}M`};
  const last = tickets.length - 1, first = tickets[0][0], lastYear = tickets[last][0];
  $('stats').innerHTML =
    stat(`$${fmt(m(gross[last]))}M`, `Estimated fines paid on OPS Part I tickets, ${lastYear}`) +
    stat(`$${fmt(m(gross[last] * share))}M`, `Of that, the City’s estimated share, ${lastYear}`) +
    stat(`$${fmt(m(gross[0] - gross[last]))}M`, `Fewer fines paid per year than in ${first}, at today’s fine and paid share`);
  chart('rev-tickets', 'bar', tickets.map(t => t[0]), [
    {label: 'Fines paid ($M)', data: gross.map(m)}, {label: 'City’s share ($M)', data: gross.map(g => m(g * share))}], dollars);
  chart('rev-warn', 'bar', p.years, [{label: 'Not collected on warnings ($M)', data: lost.map(m)}], dollars);
  const i19 = p.years.indexOf(2019);
  chart('rev-index', 'line', p.years, [
    {label: 'Charged', data: charged.map(n => Math.round(n / charged[i19] * 100))},
    {label: 'Warning', data: warnings.map(n => Math.round(n / warnings[i19] * 100))}]);
  exports = [['year', 'part1_tickets_annual_report', 'fines_paid_usd', 'city_share_usd', 'warnings_in_stops', 'uncollected_on_warnings_usd'],
    ...p.years.map((y, i) => { const t = tickets.findIndex(r => r[0] === y); return [y, t < 0 ? '' : tickets[t][1], t < 0 ? '' : Math.round(gross[t]), t < 0 ? '' : Math.round(gross[t] * share), warnings[i], Math.round(lost[i])]; })];
}

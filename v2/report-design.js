/* Presentation defaults only; stops.js owns data, filters and calculations. */
'use strict';
document.addEventListener('DOMContentLoaded', () => {
  if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.pointStyle = 'rectRounded';
  }
  // Preserve the selected section and filters when comparing with the original.
  document.getElementById('original-report').addEventListener('click', event => {
    event.currentTarget.href = '../Traffic/stops.html' + location.search + location.hash;
  });
});

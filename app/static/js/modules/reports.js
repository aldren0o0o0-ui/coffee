/**
 * Reports date filter helpers.
 */
function setDateFilterRange(days) {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - days);

  const format = d => d.toISOString().split('T')[0];
  document.getElementById('report-start-date').value = format(start);
  document.getElementById('report-end-date').value = format(end);
}

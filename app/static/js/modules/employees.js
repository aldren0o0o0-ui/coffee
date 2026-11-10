/**
 * Employee clock-in/out confirmation and kiosk scripts.
 */
function confirmClockAction(action) {
  return confirm(`Are you ready to ${action} now?`);
}

/**
 * Client-side validation utilities.
 */
function validateRequired(value) {
  return value !== null && value !== undefined && String(value).trim() !== '';
}

function validatePositiveNumber(value) {
  const num = parseFloat(value);
  return !isNaN(num) && num > 0;
}

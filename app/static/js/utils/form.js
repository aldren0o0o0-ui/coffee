/**
 * Form serialization helper.
 */
function serializeForm(formElement) {
  const formData = new FormData(formElement);
  const data = {};
  for (const [key, value] of formData.entries()) {
    if (data[key]) {
      if (!Array.isArray(data[key])) {
        data[key] = [data[key]];
      }
      data[key].push(value);
    } else {
      data[key] = value;
    }
  }
  return data;
}

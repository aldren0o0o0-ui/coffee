/**
 * API Fetch wrapper handling CSRF tokens and JSON payloads.
 */
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

async function apiRequest(url, method = 'GET', data = null) {
  const headers = {
    'Accept': 'application/json',
    'X-CSRFToken': getCsrfToken()
  };

  const options = { method, headers };

  if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(data);
  }

  try {
    const res = await fetch(url, options);
    const result = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(result.message || `Request failed with status ${res.status}`);
    }
    return result;
  } catch (err) {
    console.error('API Error:', err);
    throw err;
  }
}

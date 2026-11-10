/**
 * Toast notifications.
 */
function showToast(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  if (type === 'success') toast.style.borderLeftColor = 'var(--success)';
  if (type === 'danger' || type === 'error') toast.style.borderLeftColor = 'var(--danger)';
  if (type === 'warning') toast.style.borderLeftColor = 'var(--warning)';

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

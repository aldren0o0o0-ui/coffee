/**
 * Inventory stock adjustment modal trigger.
 */
function openMovementModal(ingredientId, ingredientName, unit) {
  const form = document.getElementById('movement-modal-form');
  if (form) {
    form.action = `/inventory/${ingredientId}/movement`;
  }
  const title = document.getElementById('movement-modal-title');
  if (title) {
    title.textContent = `Adjust Stock: ${ingredientName} (${unit})`;
  }
  openModal('movement-modal');
}

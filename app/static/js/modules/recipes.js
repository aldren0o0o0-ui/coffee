/**
 * Dynamic recipe item addition and row removal.
 */
function addRecipeIngredientRow() {
  const container = document.getElementById('recipe-items-container');
  const template = document.getElementById('recipe-row-template');
  if (!container || !template) return;

  const clone = template.content.cloneNode(true);
  container.appendChild(clone);
}

function removeRecipeRow(btn) {
  const row = btn.closest('.recipe-item-row');
  if (row) {
    row.remove();
  }
}

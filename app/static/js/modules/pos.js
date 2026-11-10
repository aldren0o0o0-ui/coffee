/**
 * Coffee Shop SME Management System - POS Terminal Engine (Phase 6)
 * Real-time dynamic order builder with variants, modifiers, cash management & idempotency.
 */

// Currency symbol — set by the POS template via window.CURRENCY_SYMBOL; fallback to ₱
const CURRENCY_SYMBOL = window.CURRENCY_SYMBOL || '₱';

let cart = [];
let activeCategory = 'all';
let catalogProducts = [];
let catalogOptions = [];
let currentCustomizingProduct = null;
let currentDiscountType = 'none';
let currentDiscountValue = 0;
let currentCalculatedDiscount = 0;
let currentOrderType = 'Dine-In';

// Initialize embedded catalog data on page load
document.addEventListener('DOMContentLoaded', () => {
  const prodScript = document.getElementById('pos-products-data');
  const optScript = document.getElementById('pos-options-data');

  if (prodScript) {
    try {
      catalogProducts = JSON.parse(prodScript.textContent || '[]');
    } catch (e) {
      console.error('Failed to parse catalog products data', e);
    }
  }

  if (optScript) {
    try {
      catalogOptions = JSON.parse(optScript.textContent || '[]');
    } catch (e) {
      console.error('Failed to parse catalog options data', e);
    }
  }

  renderCart();
});

// Category Filter Tabs
function filterCategory(catId, btnEl) {
  activeCategory = catId;
  document.querySelectorAll('.pos-cat-pill').forEach(p => p.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');

  document.querySelectorAll('.pos-product-card').forEach(card => {
    if (catId === 'all' || card.dataset.category === String(catId)) {
      card.style.display = 'flex';
    } else {
      card.style.display = 'none';
    }
  });
}

// Product Card Click Handler
function handleProductClick(productId) {
  const product = catalogProducts.find(p => p.id === Number(productId));
  if (!product) return;

  const hasVariants = product.variants && product.variants.length > 0;
  const hasOptions = catalogOptions && catalogOptions.length > 0;

  if (hasVariants || hasOptions) {
    openCustomizationModal(product);
  } else {
    // Add simple item directly
    addCartLineItem({
      productId: product.id,
      productName: product.name,
      variantId: null,
      variantName: null,
      options: [],
      notes: '',
      unitPrice: Number(product.base_price),
      quantity: 1
    });
  }
}

// Open Item Customization Modal
function openCustomizationModal(product) {
  currentCustomizingProduct = product;
  document.getElementById('cust-modal-title').textContent = `Customize ${product.name}`;
  document.getElementById('cust-product-id').value = product.id;
  document.getElementById('cust-item-notes').value = '';

  // 1. Render Variants Section
  const variantsSection = document.getElementById('cust-variants-section');
  const variantsContainer = document.getElementById('cust-variants-container');
  variantsContainer.innerHTML = '';

  if (product.variants && product.variants.length > 0) {
    variantsSection.style.display = 'block';
    product.variants.forEach((v, idx) => {
      const isSelected = idx === 0;
      const vCard = document.createElement('label');
      vCard.className = `variant-pill ${isSelected ? 'active' : ''}`;
      vCard.style.display = 'flex';
      vCard.style.flexDirection = 'column';
      vCard.style.alignItems = 'center';
      vCard.style.padding = '0.65rem 0.5rem';
      vCard.style.border = '1px solid var(--border-color)';
      vCard.style.borderRadius = 'var(--radius-sm)';
      vCard.style.cursor = 'pointer';
      vCard.style.background = isSelected ? 'rgba(217, 119, 6, 0.15)' : 'var(--bg-surface)';
      vCard.style.borderColor = isSelected ? 'var(--accent)' : 'var(--border-color)';

      vCard.innerHTML = `
        <input type="radio" name="selected_variant" value="${v.id}" data-price="${v.price}" data-name="${v.name}" ${isSelected ? 'checked' : ''} style="display:none;" onchange="onVariantSelectionChange(this)">
        <span style="font-weight: 600; font-size: 0.9rem; color: var(--text-main);">${v.name}</span>
        <span style="font-size: 0.8rem; color: var(--accent); font-weight: 700;">${CURRENCY_SYMBOL}${Number(v.price).toFixed(2)}</span>
      `;
      variantsContainer.appendChild(vCard);
    });
  } else {
    variantsSection.style.display = 'none';
  }

  // 2. Render Options Groups Section
  const optionsSection = document.getElementById('cust-options-section');
  const optionsContainer = document.getElementById('cust-options-container');
  optionsContainer.innerHTML = '';

  if (catalogOptions && catalogOptions.length > 0) {
    optionsSection.style.display = 'block';
    catalogOptions.forEach(group => {
      const gBox = document.createElement('div');
      gBox.style.background = 'var(--bg-surface)';
      gBox.style.border = '1px solid var(--border-subtle)';
      gBox.style.borderRadius = 'var(--radius-sm)';
      gBox.style.padding = '0.65rem 0.85rem';

      let optionsHtml = `<div style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 0.4rem;">${group.name}</div>`;
      optionsHtml += `<div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">`;

      (group.options || []).forEach(opt => {
        const adjText = opt.price_adjustment > 0 ? ` (+${CURRENCY_SYMBOL}${Number(opt.price_adjustment).toFixed(2)})` : '';
        optionsHtml += `
          <label style="display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.85rem; cursor: pointer; background: var(--bg-card); padding: 0.3rem 0.6rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
            <input type="checkbox" name="selected_option" value="${opt.id}" data-name="${opt.name}" data-price="${opt.price_adjustment}" onchange="updateCustomizationPricePreview()">
            <span>${opt.name}${adjText}</span>
          </label>
        `;
      });
      optionsHtml += `</div>`;
      gBox.innerHTML = optionsHtml;
      optionsContainer.appendChild(gBox);
    });
  } else {
    optionsSection.style.display = 'none';
  }

  updateCustomizationPricePreview();
  openModal('pos-customize-modal');
}

function onVariantSelectionChange(radioInput) {
  document.querySelectorAll('#cust-variants-container .variant-pill').forEach(pill => {
    pill.style.background = 'var(--bg-surface)';
    pill.style.borderColor = 'var(--border-color)';
  });
  const parent = radioInput.closest('label');
  if (parent) {
    parent.style.background = 'rgba(217, 119, 6, 0.15)';
    parent.style.borderColor = 'var(--accent)';
  }
  updateCustomizationPricePreview();
}

function updateCustomizationPricePreview() {
  if (!currentCustomizingProduct) return;

  let basePrice = Number(currentCustomizingProduct.base_price);
  const selectedVariantRadio = document.querySelector('input[name="selected_variant"]:checked');
  if (selectedVariantRadio) {
    basePrice = Number(selectedVariantRadio.dataset.price || basePrice);
  }

  let optionsTotal = 0;
  document.querySelectorAll('input[name="selected_option"]:checked').forEach(chk => {
    optionsTotal += Number(chk.dataset.price || 0);
  });

  const finalPrice = basePrice + optionsTotal;
  const previewEl = document.getElementById('cust-modal-price-preview');
  if (previewEl) {
    previewEl.textContent = `${CURRENCY_SYMBOL}${finalPrice.toFixed(2)}`;
  }
}

function confirmItemCustomization() {
  if (!currentCustomizingProduct) return;

  const product = currentCustomizingProduct;
  let variantId = null;
  let variantName = null;
  let unitPrice = Number(product.base_price);

  const selectedVariantRadio = document.querySelector('input[name="selected_variant"]:checked');
  if (selectedVariantRadio) {
    variantId = parseInt(selectedVariantRadio.value);
    variantName = selectedVariantRadio.dataset.name;
    unitPrice = Number(selectedVariantRadio.dataset.price);
  }

  const selectedOptions = [];
  document.querySelectorAll('input[name="selected_option"]:checked').forEach(chk => {
    const optId = parseInt(chk.value);
    const optName = chk.dataset.name;
    const optPrice = Number(chk.dataset.price || 0);
    unitPrice += optPrice;
    selectedOptions.push({
      id: optId,
      name: optName,
      price_adjustment: optPrice
    });
  });

  const notes = (document.getElementById('cust-item-notes')?.value || '').trim();

  addCartLineItem({
    productId: product.id,
    productName: product.name,
    variantId: variantId,
    variantName: variantName,
    options: selectedOptions,
    notes: notes,
    unitPrice: unitPrice,
    quantity: 1
  });

  closeModal('pos-customize-modal');
  currentCustomizingProduct = null;
}

// Add line item to cart (combining identical configurations)
function addCartLineItem(item) {
  // Check for exact matching configuration
  const optIds = item.options.map(o => o.id).sort().join(',');
  const existing = cart.find(i => 
    i.productId === item.productId &&
    i.variantId === item.variantId &&
    i.notes === item.notes &&
    i.options.map(o => o.id).sort().join(',') === optIds
  );

  if (existing) {
    existing.quantity += item.quantity;
  } else {
    item.lineId = 'line_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
    cart.push(item);
  }

  renderCart();
}

// Modify Line Quantity
function updateCartQuantity(lineId, delta) {
  const item = cart.find(i => i.lineId === lineId);
  if (!item) return;

  item.quantity += delta;
  if (item.quantity <= 0) {
    cart = cart.filter(i => i.lineId !== lineId);
  }
  renderCart();
}

function removeCartLine(lineId) {
  cart = cart.filter(i => i.lineId !== lineId);
  renderCart();
}

function clearCart() {
  cart = [];
  currentDiscountType = 'none';
  currentDiscountValue = 0;
  currentCalculatedDiscount = 0;
  const discountSelect = document.getElementById('pos-discount-select');
  if (discountSelect) discountSelect.value = 'none';
  const customInput = document.getElementById('pos-custom-discount-input');
  if (customInput) {
    customInput.value = '';
    customInput.style.display = 'none';
  }
  renderCart();
}

// Order Type Selection (Dine-In vs Takeout)
function setOrderType(type) {
  currentOrderType = type;
  const hiddenInput = document.getElementById('checkout-order-type');
  if (hiddenInput) hiddenInput.value = type;

  const dineInBtn = document.getElementById('btn-type-dinein');
  const takeoutBtn = document.getElementById('btn-type-takeout');

  if (dineInBtn && takeoutBtn) {
    if (type === 'Dine-In') {
      dineInBtn.className = 'btn btn-primary btn-sm';
      takeoutBtn.className = 'btn btn-secondary btn-sm';
    } else {
      dineInBtn.className = 'btn btn-secondary btn-sm';
      takeoutBtn.className = 'btn btn-primary btn-sm';
    }
  }
}

// Discount Controls
function handleDiscountChange(val) {
  currentDiscountType = val;
  const customInput = document.getElementById('pos-custom-discount-input');

  if (val === 'custom') {
    if (customInput) {
      customInput.style.display = 'inline-block';
      customInput.focus();
      currentDiscountValue = parseFloat(customInput.value || '0') || 0;
    }
  } else {
    if (customInput) customInput.style.display = 'none';
    if (val === 'senior_pwd') {
      currentDiscountValue = 0.20;
    } else if (val === 'promo_10') {
      currentDiscountValue = 0.10;
    } else {
      currentDiscountValue = 0;
    }
  }
  renderCart();
}

function handleCustomDiscountInput(val) {
  currentDiscountValue = Math.max(0, parseFloat(val || '0') || 0);
  renderCart();
}

// Render Cart Lines and Totals
function renderCart() {
  const listEl = document.getElementById('pos-cart-items');
  const subtotalEl = document.getElementById('pos-cart-subtotal');
  const taxEl = document.getElementById('pos-cart-tax');
  const totalEl = document.getElementById('pos-cart-total');
  const payBtn = document.getElementById('pos-pay-btn');
  const discountRow = document.getElementById('pos-discount-row');
  const discountEl = document.getElementById('pos-cart-discount');

  if (!listEl) return;

  if (cart.length === 0) {
    listEl.innerHTML = `
      <div style="text-align: center; color: var(--text-dim); padding: 3rem 1rem;">
        <span style="font-size: 2.5rem; display: block; margin-bottom: 0.5rem;">☕</span>
        Cart is empty.<br>Tap any drink or item to add.
      </div>`;
    if (subtotalEl) subtotalEl.textContent = `${CURRENCY_SYMBOL}0.00`;
    if (discountRow) discountRow.style.display = 'none';
    if (taxEl) taxEl.textContent = `${CURRENCY_SYMBOL}0.00`;
    if (totalEl) totalEl.textContent = `${CURRENCY_SYMBOL}0.00`;
    if (payBtn) payBtn.disabled = true;
    currentCalculatedDiscount = 0;
    return;
  }

  let subtotal = 0;
  listEl.innerHTML = '';

  cart.forEach(item => {
    const lineTotal = item.unitPrice * item.quantity;
    subtotal += lineTotal;

    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.flexDirection = 'column';
    row.style.padding = '0.75rem 0';
    row.style.borderBottom = '1px solid var(--border-subtle)';

    let optionsBadges = '';
    if (item.options && item.options.length > 0) {
      optionsBadges = item.options.map(o => `<span style="font-size: 0.72rem; color: var(--text-muted); display: block;">+ ${o.name}${o.price_adjustment > 0 ? ' (+' + CURRENCY_SYMBOL + o.price_adjustment.toFixed(2) + ')' : ''}</span>`).join('');
    }

    row.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div style="flex: 1; min-width: 0; padding-right: 0.5rem;">
          <div style="font-weight: 600; font-size: 0.95rem; color: var(--text-main);">${item.productName}</div>
          ${item.variantName ? `<span style="font-size: 0.75rem; background: rgba(217,119,6,0.2); color: var(--accent); padding: 0.1rem 0.35rem; border-radius: 3px; font-weight: 600;">${item.variantName}</span>` : ''}
          ${optionsBadges}
          ${item.notes ? `<span style="font-size: 0.75rem; font-style: italic; color: #aaa; display: block;">"${item.notes}"</span>` : ''}
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.15rem;">${CURRENCY_SYMBOL}${item.unitPrice.toFixed(2)} each</div>
        </div>
        <div style="font-weight: 700; font-size: 1.05rem; color: var(--accent); min-width: 60px; text-align: right;">
          ${CURRENCY_SYMBOL}${lineTotal.toFixed(2)}
        </div>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <button type="button" class="btn btn-secondary btn-sm" style="min-width: 32px; height: 32px; padding: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 1.1rem; font-weight: 700;" onclick="updateCartQuantity('${item.lineId}', -1)" aria-label="Decrease quantity">-</button>
          <span style="font-weight: 700; width: 1.8rem; text-align: center; color: var(--text-main); font-size: 1rem;">${item.quantity}</span>
          <button type="button" class="btn btn-secondary btn-sm" style="min-width: 32px; height: 32px; padding: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 1.1rem; font-weight: 700;" onclick="updateCartQuantity('${item.lineId}', 1)" aria-label="Increase quantity">+</button>
        </div>
        <button type="button" style="background: none; border: none; color: var(--danger); font-size: 0.8rem; cursor: pointer; text-decoration: underline; padding: 0.3rem;" onclick="removeCartLine('${item.lineId}')">
          Remove
        </button>
      </div>
    `;
    listEl.appendChild(row);
  });

  // Calculate discount
  let discountAmount = 0;
  if (currentDiscountType === 'senior_pwd' || currentDiscountType === 'promo_10') {
    discountAmount = Math.round(subtotal * currentDiscountValue * 100) / 100;
  } else if (currentDiscountType === 'custom') {
    discountAmount = Math.min(currentDiscountValue, subtotal);
  }
  currentCalculatedDiscount = discountAmount;

  const taxableAmount = Math.max(subtotal - discountAmount, 0);
  const taxRate = parseFloat(document.getElementById('pos-tax-rate')?.value || '0.08');
  const tax = Math.round(taxableAmount * taxRate * 100) / 100;
  const total = Math.round((taxableAmount + tax) * 100) / 100;

  if (subtotalEl) subtotalEl.textContent = `${CURRENCY_SYMBOL}${subtotal.toFixed(2)}`;
  if (discountRow && discountEl) {
    if (discountAmount > 0) {
      discountRow.style.display = 'flex';
      discountEl.textContent = `-${CURRENCY_SYMBOL}${discountAmount.toFixed(2)}`;
    } else {
      discountRow.style.display = 'none';
    }
  }
  if (taxEl) taxEl.textContent = `${CURRENCY_SYMBOL}${tax.toFixed(2)}`;
  if (totalEl) totalEl.textContent = `${CURRENCY_SYMBOL}${total.toFixed(2)}`;
  if (payBtn) payBtn.disabled = false;
}

// Open Checkout Modal
function openCheckoutModal() {
  if (cart.length === 0) return;

  const totalEl = document.getElementById('pos-cart-total');
  const totalVal = parseFloat((totalEl?.textContent || `${CURRENCY_SYMBOL}0.00`).replace(CURRENCY_SYMBOL, '')) || 0;

  document.getElementById('checkout-modal-due-amount').textContent = `${CURRENCY_SYMBOL}${totalVal.toFixed(2)}`;
  document.getElementById('checkout-cash-tendered').value = totalVal.toFixed(2);
  togglePaymentMethodFields();
  calculateChange();
  openModal('checkout-modal');
}

function togglePaymentMethodFields() {
  const method = document.getElementById('checkout-payment-method').value;
  const cashSection = document.getElementById('cash-tendered-section');
  if (cashSection) {
    cashSection.style.display = method === 'Cash' ? 'block' : 'none';
  }
}

function setQuickCash(amount) {
  const totalVal = parseFloat((document.getElementById('checkout-modal-due-amount')?.textContent || `${CURRENCY_SYMBOL}0.00`).replace(CURRENCY_SYMBOL, '')) || 0;
  const input = document.getElementById('checkout-cash-tendered');
  if (!input) return;

  if (amount === 'exact') {
    input.value = totalVal.toFixed(2);
  } else {
    input.value = Number(amount).toFixed(2);
  }
  calculateChange();
}

function calculateChange() {
  const totalVal = parseFloat((document.getElementById('checkout-modal-due-amount')?.textContent || `${CURRENCY_SYMBOL}0.00`).replace(CURRENCY_SYMBOL, '')) || 0;
  const tenderedVal = parseFloat(document.getElementById('checkout-cash-tendered')?.value || '0') || 0;
  const changeDueEl = document.getElementById('checkout-change-due');
  const changeContainer = document.getElementById('checkout-change-container');
  const confirmBtn = document.getElementById('confirm-checkout-btn');

  const method = document.getElementById('checkout-payment-method').value;
  if (method !== 'Cash') {
    if (confirmBtn) confirmBtn.disabled = false;
    return;
  }

  const change = tenderedVal - totalVal;
  if (change >= 0) {
    if (changeDueEl) changeDueEl.textContent = `${CURRENCY_SYMBOL}${change.toFixed(2)}`;
    if (changeContainer) {
      changeContainer.style.background = 'rgba(16, 185, 129, 0.1)';
      changeContainer.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      changeContainer.querySelector('span').textContent = 'Change to Return:';
      changeDueEl.style.color = '#34d399';
    }
    if (confirmBtn) confirmBtn.disabled = false;
  } else {
    const shortfall = Math.abs(change);
    if (changeDueEl) changeDueEl.textContent = `-${CURRENCY_SYMBOL}${shortfall.toFixed(2)}`;
    if (changeContainer) {
      changeContainer.style.background = 'rgba(239, 68, 68, 0.15)';
      changeContainer.style.borderColor = 'rgba(239, 68, 68, 0.4)';
      changeContainer.querySelector('span').textContent = 'Shortfall:';
      changeDueEl.style.color = '#f87171';
    }
    if (confirmBtn) confirmBtn.disabled = true;
  }
}

// Process Checkout with Idempotency & Stock Rollback Safety
async function processCheckout() {
  if (cart.length === 0) return;

  const confirmBtn = document.getElementById('confirm-checkout-btn');
  const paymentMethod = document.getElementById('checkout-payment-method').value;
  const customerName = (document.getElementById('checkout-customer-name')?.value || 'Guest').trim();
  const cashTendered = parseFloat(document.getElementById('checkout-cash-tendered')?.value || '0');
  const orderType = document.getElementById('checkout-order-type')?.value || currentOrderType || 'Dine-In';

  // Format customer reference with order type for baristas
  const customerReference = `[${orderType}] ${customerName}`;

  // Generate unique idempotency key for this payment attempt
  const idempotencyKey = (typeof crypto !== 'undefined' && crypto.randomUUID) 
    ? crypto.randomUUID() 
    : 'pos_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

  const payload = {
    items: cart.map(i => ({
      product_id: i.productId,
      variant_id: i.variantId,
      options: (i.options || []).map(o => o.id),
      quantity: i.quantity,
      notes: i.notes || ''
    })),
    payment_method: paymentMethod,
    customer_name: customerReference,
    cash_tendered: cashTendered,
    discount_amount: currentCalculatedDiscount,
    notes: `Type: ${orderType}`,
    idempotency_key: idempotencyKey
  };

  try {
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Processing...';
    }

    const res = await apiRequest('/pos/checkout', 'POST', payload);
    showToast(res.message || 'Order completed successfully!', 'success');
    closeModal('checkout-modal');
    clearCart();

    // Launch printable thermal receipt
    if (res.data && res.data.id) {
      window.open(`/pos/receipt/${res.data.id}`, '_blank', 'width=420,height=650');
    }
  } catch (err) {
    // Show descriptive stock/validation error to cashier without losing cart
    showToast(err.message, 'danger');
  } finally {
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Confirm & Print Receipt';
    }
  }
}

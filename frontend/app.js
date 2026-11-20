/**
 * app.js - IronMate Frontend Application Controller
 * Pure Vanilla JavaScript (No frameworks) connected to Flask REST API
 * Replicating reference screenshots with zero-cost RAG AI assistant.
 */

// =============================================================================
// 1. CONFIGURATION & STATE MANAGEMENT
// =============================================================================
// Relative /api path so all endpoints resolve cleanly on any live domain (e.g. PythonAnywhere)
const API_BASE = window.location.protocol === 'file:'
  ? 'http://127.0.0.1:5000/api'
  : '/api';

const FALLBACK_IMAGE = 'https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?auto=format&fit=crop&w=800&q=80';

// Global Application State
const state = {
  products: [],
  filteredProducts: [],
  cart: { items: [], total: 0, item_count: 0 },
  token: localStorage.getItem('ironmate_token') || null,
  user: JSON.parse(localStorage.getItem('ironmate_user') || 'null'),
  
  // Filters State
  filters: {
    category: 'all',
    categories: new Set(),
    subcat: 'all',
    search: '',
    goals: new Set(),
    experience: new Set(),
    space: new Set(),
    priceRange: 'all', // 'all', '0-2000', '2000-5000', '5000-15000', '15000-35000', '35000-999999'
    sort: 'recommended'
  },

  // "Find Your Fit" Box Temporary Selection State
  fitFilters: {
    goal: null,
    experience: null,
    space: null,
    budget: null
  },

  // AI Assistant State
  ai: {
    activeTab: 'chat',
    chatHistory: [],
    finderStep: 0,
    finderAnswers: {},
    isTyping: false
  }
};

// =============================================================================
// 2. CURRENCY & FORMATTING HELPERS
// =============================================================================
/** Safely attaches an event listener to an element ID or node if it exists */
function safeAddListener(target, event, handler) {
  const el = typeof target === 'string' ? document.getElementById(target) : target;
  if (el) {
    el.addEventListener(event, handler);
    return true;
  }
  return false;
}

/** Formats backend price into standard Indian Rupee (₹) format */
function formatINR(price) {
  const num = Number(price);
  const inr = isNaN(num) || num < 0 ? 0 : Math.round(num);
  return '₹' + inr.toLocaleString('en-IN');
}

/** Computes realistic strikethrough MRP from product.mrp or fallback to product.price */
function formatMRP(item) {
  let mrpVal = 0;
  if (typeof item === 'object' && item !== null) {
    if (item.mrp !== undefined && item.mrp !== null && !isNaN(Number(item.mrp)) && Number(item.mrp) > 0) {
      mrpVal = Number(item.mrp);
    } else if (item.price !== undefined && item.price !== null && !isNaN(Number(item.price))) {
      mrpVal = Number(item.price) * 1.5;
    }
  } else if (typeof item === 'number' || typeof item === 'string') {
    const num = Number(item);
    mrpVal = isNaN(num) ? 0 : num;
  }
  if (isNaN(mrpVal) || mrpVal <= 0) {
    mrpVal = 0;
  }
  return '₹' + Math.round(mrpVal).toLocaleString('en-IN');
}

/** Formats calculated discount badge percent from product.mrp and product.price */
function getDiscountPercent(item) {
  if (typeof item === 'object' && item !== null) {
    const price = Number(item.price || 0);
    const mrp = (item.mrp !== undefined && item.mrp !== null && !isNaN(Number(item.mrp)) && Number(item.mrp) > 0)
      ? Number(item.mrp)
      : (price * 1.5);
    if (!isNaN(mrp) && !isNaN(price) && mrp > price && mrp > 0) {
      const discount = Math.round(((mrp - price) / mrp) * 100);
      return `${discount}% OFF`;
    }
  }
  return `35% OFF`;
}

// =============================================================================
// 3. API CLIENT CALLS
// =============================================================================
async function apiCall(endpoint, method = 'GET', body = null, requiresAuth = false) {
  const headers = { 'Content-Type': 'application/json' };
  if (requiresAuth && state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  const options = { method, headers };
  if (body) {
    options.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, options);
    const data = await response.json();
    return { ok: response.ok, status: response.status, data };
  } catch (error) {
    console.error(`API Error on ${endpoint}:`, error);
    return { ok: false, status: 500, data: { message: 'Network connection failed' } };
  }
}

// =============================================================================
// 4. INITIALIZATION & DATA LOADING
// =============================================================================
document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

async function initApp() {
  // 1. Register ALL UI event listeners FIRST so user interactions work immediately
  try {
    setupEventListeners();
  } catch (err) {
    console.error('Error during setupEventListeners:', err);
  }

  // 2. Setup auth state
  try {
    updateAuthUI();
  } catch (err) {
    console.error('Error during updateAuthUI:', err);
  }

  // 3. Load product catalog wrapped in try/catch so a rendering error never freezes the UI
  try {
    await fetchProducts();
  } catch (err) {
    console.error('Error in fetchProducts():', err);
    const container = document.getElementById('productsGrid');
    if (container) {
      container.innerHTML = `
        <div class="grid-loading-placeholder">
          <p style="color:#DC2626; font-weight:700;">Could not display products catalog.</p>
          <p style="font-size:0.85rem; color:#6B7280; margin-top:6px;">Please refresh or verify API connection.</p>
        </div>`;
    }
  }

  // 4. Load shopping cart if user has active session
  if (state.token) {
    try {
      await loadCart();
    } catch (err) {
      console.error('Error loading cart:', err);
    }
  }

  // 5. Initialize Finder quiz flow
  try {
    initFinderFlow();
  } catch (err) {
    console.error('Error initializing Finder flow:', err);
  }
}

/** Fetches full product catalog from backend (alias for loadProducts) */
async function fetchProducts() {
  await loadProducts();
}

/** Loads full product catalog from backend */
async function loadProducts() {
  const res = await apiCall('/products');
  if (res.ok && res.data && res.data.products) {
    state.products = res.data.products;
    applyAllFilters();
    updateFitLiveCount();
  } else {
    const container = document.getElementById('productsGrid');
    if (container) {
      container.innerHTML = `
        <div class="grid-loading-placeholder">
          <p style="color:#DC2626; font-weight:700;">Could not connect to Flask API (${API_BASE}).</p>
          <p style="font-size:0.85rem; color:#6B7280; margin-top:6px;">Please ensure the Flask backend server is running.</p>
        </div>`;
    }
  }
}

/** Loads current user's cart from backend */
async function loadCart() {
  if (!state.token) return;
  const res = await apiCall('/cart', 'GET', null, true);
  if (res.ok && res.data) {
    state.cart = res.data;
    updateCartUI();
  }
}

// =============================================================================
// 5. PRODUCT FILTERING & RENDERING ENGINE
// =============================================================================
function applyAllFilters() {
  let list = [...state.products];

  // 1. Equipment Category Filter (Sidebar checkboxes or Tabs/Navbar category)
  if (state.filters.categories.size > 0) {
    const activeCats = Array.from(state.filters.categories).map(c => c.toLowerCase());
    list = list.filter(p => activeCats.some(c => p.category.toLowerCase().includes(c)));
  } else if (state.filters.category && state.filters.category !== 'all') {
    const cats = state.filters.category.split(',').map(c => c.trim().toLowerCase()).filter(Boolean);
    list = list.filter(p => cats.some(c => p.category.toLowerCase().includes(c)));
  }

  // 2. Subcategory Pill Filter (All, Treadmill, Bike, Bicycle, Mats, Rope, Shaker, Weight)
  if (state.filters.subcat && state.filters.subcat !== 'all') {
    const sub = state.filters.subcat.toLowerCase();
    list = list.filter(p => p.category.toLowerCase().includes(sub) || p.name.toLowerCase().includes(sub));
  }

  // 3. Search Query
  if (state.filters.search) {
    const q = state.filters.search.toLowerCase();
    list = list.filter(p => 
      p.name.toLowerCase().includes(q) || 
      p.description.toLowerCase().includes(q) || 
      p.category.toLowerCase().includes(q)
    );
  }

  // 4. Sidebar Goals (OR logic within goals)
  if (state.filters.goals.size > 0) {
    list = list.filter(p => {
      const tags = (p.goal_tags || []).map(t => String(t).toLowerCase());
      for (const g of state.filters.goals) {
        if (tags.some(t => t.includes(g))) return true;
      }
      return false;
    });
  }

  // 5. Sidebar Experience Level
  if (state.filters.experience.size > 0) {
    list = list.filter(p => state.filters.experience.has(p.experience_level.toLowerCase()));
  }

  // 6. Sidebar Space Needed
  if (state.filters.space.size > 0) {
    list = list.filter(p => state.filters.space.has(p.space_needed.toLowerCase()));
  }

  // 7. Sidebar Price Range
  if (state.filters.priceRange !== 'all') {
    const [minStr, maxStr] = state.filters.priceRange.split('-');
    const minINR = Number(minStr);
    const maxINR = Number(maxStr);
    list = list.filter(p => {
      const inr = Math.round(p.price);
      return inr >= minINR && inr <= maxINR;
    });
  }

  // 8. Sorting
  if (state.filters.sort === 'price_asc') {
    list.sort((a, b) => a.price - b.price);
  } else if (state.filters.sort === 'price_desc') {
    list.sort((a, b) => b.price - a.price);
  } else if (state.filters.sort === 'name') {
    list.sort((a, b) => a.name.localeCompare(b.name));
  }

  state.filteredProducts = list;
  renderProductsGrid(list);
  renderActiveFilterTags();
  document.getElementById('catalogCountNumber').textContent = list.length;
}

/** Renders product cards matching Screenshot 2, 3, 4, 6 */
function renderProductsGrid(products) {
  const container = document.getElementById('productsGrid');

  if (products.length === 0) {
    container.innerHTML = `
      <div class="grid-loading-placeholder">
        <p style="font-weight:700; font-size:1.1rem; color:#111827;">No matching fitness gear found.</p>
        <p style="font-size:0.875rem; color:#6B7280; margin-top:6px;">Try clearing some filters or searching for dumbbells, treadmills, or supplements.</p>
        <button class="btn btn-primary btn-sm btn-pill" style="margin-top:16px;" onclick="resetAllFilters()">Reset All Filters</button>
      </div>`;
    return;
  }

  container.innerHTML = products.map(product => {
    const inStock = product.stock > 0;
    const discount = getDiscountPercent(product);
    const inrPrice = formatINR(product.price);
    const strikethrough = formatMRP(product);

    return `
      <div class="product-card" data-id="${product.id}">
        <!-- Media Container -->
        <div class="product-card-media" onclick="openProductModal(${product.id})">
          <span class="product-discount-badge">${discount}</span>
          ${product.price >= 20000 ? '<span class="product-3d-badge">PRO GRADE</span>' : ''}
          <img 
            src="${product.image_url}" 
            alt="${escapeHtml(product.name)}" 
            class="product-card-img"
            loading="lazy"
            onerror="this.onerror=null; this.src='${FALLBACK_IMAGE}';"
          >
        </div>

        <!-- Details Container -->
        <div class="product-card-content">
          <div class="product-card-category">${escapeHtml(product.category)}</div>
          <h4 class="product-card-title" onclick="openProductModal(${product.id})" title="${escapeHtml(product.name)}">
            ${escapeHtml(product.name)}
          </h4>

          <div class="product-card-price-row">
            <span class="product-current-price">${inrPrice}</span>
            <span class="product-strikethrough-mrp">${strikethrough}</span>
          </div>

          <div class="product-delivery-tag">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm13.5-9l1.96 2.5H17V9.5h2.5zm-1.5 9c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/>
            </svg>
            <span>Free Delivery</span>
          </div>

          <div class="product-card-actions">
            ${inStock ? `
              <button class="product-add-cart-btn" onclick="handleAddToCart(${product.id}, event)">
                Add to cart
              </button>
            ` : `
              <button class="product-add-cart-btn out-of-stock" disabled>
                Out of Stock
              </button>
            `}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

/** Renders active filter tags above grid with instant removal */
function renderActiveFilterTags() {
  const container = document.getElementById('activeFilterTagsStrip');
  const tags = [];

  if (state.filters.search) {
    tags.push({ label: `Search: "${state.filters.search}"`, clear: () => { state.filters.search = ''; document.getElementById('globalSearchInput').value = ''; } });
  }
  if (state.filters.categories.size > 0) {
    for (const c of state.filters.categories) {
      tags.push({ label: `Category: ${c}`, clear: () => { state.filters.categories.delete(c); uncheckSidebarBox('catFilter', c); } });
    }
  } else if (state.filters.category && state.filters.category !== 'all') {
    tags.push({ label: `Category: ${state.filters.category}`, clear: () => { setCategory('all'); } });
  }
  for (const g of state.filters.goals) {
    tags.push({ label: `Goal: ${g.replace('_', ' ')}`, clear: () => { state.filters.goals.delete(g); uncheckSidebarBox('goalFilter', g); } });
  }
  for (const exp of state.filters.experience) {
    tags.push({ label: `Level: ${exp}`, clear: () => { state.filters.experience.delete(exp); uncheckSidebarBox('expFilter', exp); } });
  }
  for (const sp of state.filters.space) {
    tags.push({ label: `Space: ${sp}`, clear: () => { state.filters.space.delete(sp); uncheckSidebarBox('spaceFilter', sp); } });
  }
  if (state.filters.priceRange !== 'all') {
    tags.push({ label: `Price Filter Active`, clear: () => { state.filters.priceRange = 'all'; document.querySelector('input[name="priceRangeRadio"][value="all"]').checked = true; } });
  }

  container.innerHTML = tags.map((t, idx) => `
    <span class="filter-badge-tag">
      <span>${t.label}</span>
      <button class="remove-tag-btn" onclick="removeTag(${idx})">✕</button>
    </span>
  `).join('');

  window._activeTags = tags;
}

function removeTag(index) {
  if (window._activeTags && window._activeTags[index]) {
    window._activeTags[index].clear();
    applyAllFilters();
  }
}

function uncheckSidebarBox(name, val) {
  const box = document.querySelector(`input[name="${name}"][value="${val}"]`);
  if (box) box.checked = false;
}

// =============================================================================
// 6. "FIND YOUR FIT" INTERACTIVE FILTER BOX LOGIC (SCREENSHOT 2 STYLE)
// =============================================================================
function handleFitPillClick(e) {
  const pill = e.currentTarget;
  const type = pill.dataset.type;
  const val = pill.dataset.value;

  if (pill.classList.contains('active')) {
    pill.classList.remove('active');
    state.fitFilters[type] = null;
  } else {
    // Only 1 active per row for clean guided fit selection
    const container = pill.parentElement;
    container.querySelectorAll('.fit-pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    state.fitFilters[type] = val;
  }

  updateFitLiveCount();
}

/** Calculates live matching product count inside "Find your fit" box */
function updateFitLiveCount() {
  let count = state.products.length;
  let matches = [...state.products];

  if (state.fitFilters.goal) {
    const g = state.fitFilters.goal.toLowerCase();
    matches = matches.filter(p => {
      const tags = (p.goal_tags || []).map(t => String(t).toLowerCase());
      return tags.some(t => t.includes(g));
    });
  }

  if (state.fitFilters.experience) {
    matches = matches.filter(p => p.experience_level.toLowerCase() === state.fitFilters.experience.toLowerCase());
  }

  if (state.fitFilters.space) {
    matches = matches.filter(p => p.space_needed.toLowerCase() === state.fitFilters.space.toLowerCase());
  }

  if (state.fitFilters.budget) {
    const budget = Number(state.fitFilters.budget);
    matches = matches.filter(p => {
      const inr = Math.round(p.price);
      if (budget === 2000) return inr <= 2000;
      if (budget === 5000) return inr >= 2000 && inr <= 5000;
      if (budget === 15000) return inr >= 5000 && inr <= 15000;
      if (budget === 15001) return inr >= 15000;
      return true;
    });
  }

  document.getElementById('fitLiveProductCount').textContent = matches.length;
}

/** Applies "Find your fit" selections to main catalog grid and scrolls to it */
function applyFitFiltersToCatalog() {
  resetAllFilters(false);

  if (state.fitFilters.goal) {
    state.filters.goals.add(state.fitFilters.goal);
    const box = document.querySelector(`input[name="goalFilter"][value="${state.fitFilters.goal}"]`);
    if (box) box.checked = true;
  }

  if (state.fitFilters.experience) {
    state.filters.experience.add(state.fitFilters.experience);
    const box = document.querySelector(`input[name="expFilter"][value="${state.fitFilters.experience}"]`);
    if (box) box.checked = true;
  }

  if (state.fitFilters.space) {
    state.filters.space.add(state.fitFilters.space);
    const box = document.querySelector(`input[name="spaceFilter"][value="${state.fitFilters.space}"]`);
    if (box) box.checked = true;
  }

  if (state.fitFilters.budget) {
    const b = state.fitFilters.budget;
    let rangeVal = 'all';
    if (b === '2000') rangeVal = '0-2000';
    else if (b === '5000') rangeVal = '2000-5000';
    else if (b === '15000') rangeVal = '5000-15000';
    else if (b === '15001') rangeVal = '15000-35000';

    state.filters.priceRange = rangeVal;
    const radio = document.querySelector(`input[name="priceRangeRadio"][value="${rangeVal}"]`);
    if (radio) radio.checked = true;
  }

  applyAllFilters();
  scrollToCatalog();
}

function clearFitBox() {
  document.querySelectorAll('.fit-pill.active').forEach(p => p.classList.remove('active'));
  state.fitFilters = { goal: null, experience: null, space: null, budget: null };
  updateFitLiveCount();
}

function resetAllFilters(scroll = true) {
  state.filters.category = 'all';
  state.filters.categories.clear();
  state.filters.subcat = 'all';
  state.filters.search = '';
  state.filters.goals.clear();
  state.filters.experience.clear();
  state.filters.space.clear();
  state.filters.priceRange = 'all';
  state.filters.sort = 'recommended';

  document.getElementById('globalSearchInput').value = '';
  document.querySelectorAll('.cat-tab-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.category === 'all'));
  document.querySelectorAll('.subcat-pill').forEach(btn => btn.classList.toggle('active', btn.dataset.sub === 'all'));
  document.querySelectorAll('.sidebar-filter-group input[type="checkbox"]').forEach(c => c.checked = false);
  const defaultRadio = document.querySelector('input[name="priceRangeRadio"][value="all"]');
  if (defaultRadio) defaultRadio.checked = true;
  document.getElementById('catalogSortSelect').value = 'recommended';

  applyAllFilters();
  if (scroll) scrollToCatalog();
}

function scrollToCatalog() {
  const el = document.getElementById('catalog');
  if (el) el.scrollIntoView({ behavior: 'smooth' });
}

// =============================================================================
// 7. CART SYSTEM & DRAWERS
// =============================================================================
async function handleAddToCart(productId, event) {
  if (event) event.stopPropagation();

  // If not logged in, prompt user with Auth Modal
  if (!state.token) {
    showToast('Please sign in or use 1-Click Demo Login to manage your cart.', 'error');
    openAuthModal();
    return;
  }

  const res = await apiCall('/cart/add', 'POST', { product_id: productId, quantity: 1 }, true);
  if (res.ok) {
    showToast('Added product to your cart!', 'success');
    await loadCart();
    openCartDrawer();
  } else {
    showToast(res.data.message || 'Could not add to cart.', 'error');
  }
}

async function handleUpdateCartQty(productId, newQty) {
  const res = await apiCall('/cart/update', 'PUT', { product_id: productId, quantity: newQty }, true);
  if (res.ok) {
    await loadCart();
  } else {
    showToast(res.data.message || 'Could not update quantity.', 'error');
  }
}

async function handleRemoveFromCart(productId) {
  const res = await apiCall(`/cart/remove/${productId}`, 'DELETE', null, true);
  if (res.ok) {
    showToast('Item removed from cart.', 'success');
    await loadCart();
  }
}

function updateCartUI() {
  const badge = document.getElementById('cartBadgeCount');
  const drawerCount = document.getElementById('cartDrawerCount');
  const itemsList = document.getElementById('cartItemsList');
  const grandTotal = document.getElementById('cartGrandTotal');

  const count = state.cart.item_count || 0;
  badge.textContent = count;
  drawerCount.textContent = `(${count} items)`;

  if (!state.cart.items || state.cart.items.length === 0) {
    itemsList.innerHTML = `
      <div class="cart-empty-state">
        <div class="empty-icon">🛒</div>
        <h4>Your Cart is Empty</h4>
        <p style="font-size:0.875rem; color:#6B7280; margin-top:6px;">Browse our strength and cardio gear to build your setup.</p>
        <button class="btn btn-primary btn-sm btn-pill" style="margin-top:16px;" onclick="closeCartDrawer(); scrollToCatalog();">Explore Products</button>
      </div>`;
    grandTotal.textContent = '₹0';
    return;
  }

  let totalINR = 0;
  itemsList.innerHTML = state.cart.items.map(item => {
    const p = item.product || {};
    const unitPriceINR = Math.round(Number(p.price || 0));
    const lineTotalINR = unitPriceINR * item.quantity;
    totalINR += lineTotalINR;

    return `
      <div class="cart-item-row" data-id="${p.id}">
        <div class="cart-item-thumb">
          <img src="${p.image_url || FALLBACK_IMAGE}" alt="${escapeHtml(p.name || '')}" onerror="this.src='${FALLBACK_IMAGE}';">
        </div>
        <div class="cart-item-details">
          <div class="cart-item-title">${escapeHtml(p.name || 'Equipment')}</div>
          <div class="cart-item-price">₹${lineTotalINR.toLocaleString('en-IN')} <span style="font-size:0.75rem; color:#9CA3AF; font-weight:normal;">(₹${unitPriceINR.toLocaleString('en-IN')} each)</span></div>
          <div class="cart-item-qty-row">
            <div class="qty-controls">
              <button class="qty-btn" onclick="handleUpdateCartQty(${p.id}, ${item.quantity - 1})">-</button>
              <span class="qty-number">${item.quantity}</span>
              <button class="qty-btn" onclick="handleUpdateCartQty(${p.id}, ${item.quantity + 1})">+</button>
            </div>
            <button class="remove-cart-item-btn" onclick="handleRemoveFromCart(${p.id})" title="Remove item">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  grandTotal.textContent = `₹${totalINR.toLocaleString('en-IN')}`;
}

// Slide-Over Cart Controls
function openCartDrawer() {
  document.getElementById('cartDrawer').classList.add('active');
  document.getElementById('cartOverlay').classList.add('active');
}

function closeCartDrawer() {
  document.getElementById('cartDrawer').classList.remove('active');
  document.getElementById('cartOverlay').classList.remove('active');
}

// =============================================================================
// 8. CHECKOUT & ORDERS ENGINE
// =============================================================================
async function handleCheckout() {
  if (!state.token) {
    showToast('Please sign in to place order.', 'error');
    openAuthModal();
    return;
  }

  if (!state.cart.items || state.cart.items.length === 0) {
    showToast('Your cart is empty!', 'error');
    return;
  }

  const btn = document.getElementById('proceedCheckoutBtn');
  btn.disabled = true;
  btn.textContent = 'Processing Checkout...';

  const res = await apiCall('/orders/checkout', 'POST', {}, true);
  btn.disabled = false;
  btn.textContent = 'Proceed to Mock Checkout →';

  if (res.ok && res.data.order) {
    closeCartDrawer();
    await loadCart();
    await loadProducts(); // Refresh live stock numbers
    showReceiptModal(res.data.order);
  } else {
    showToast(res.data.message || 'Checkout failed.', 'error');
  }
}

function showReceiptModal(order) {
  const box = document.getElementById('receiptDetailsBox');
  const items = order.items || [];
  const inrTotal = Math.round(order.total);

  box.innerHTML = `
    <div class="receipt-row">
      <span style="color:#6B7280;">Order ID:</span>
      <strong>#IM-${order.id.toString().padStart(6, '0')}</strong>
    </div>
    <div class="receipt-row">
      <span style="color:#6B7280;">Order Status:</span>
      <strong style="color:#16A34A;">${order.status} (Stock Decremented)</strong>
    </div>
    <div class="receipt-row">
      <span style="color:#6B7280;">Payment Method:</span>
      <strong>Mock COD / Instant Approval</strong>
    </div>
    <div class="receipt-row" style="border-top:1px dashed #E5E7EB; padding-top:8px; margin-top:8px;">
      <span style="color:#6B7280;">Total Paid:</span>
      <strong style="color:#E31E24; font-size:1.1rem;">₹${inrTotal.toLocaleString('en-IN')}</strong>
    </div>
    <div style="margin-top:12px;">
      <span style="font-size:0.75rem; font-weight:700; color:#6B7280; text-transform:uppercase;">Items Purchased:</span>
      <ul style="list-style:none; margin-top:4px; font-size:0.85rem;">
        ${items.map(i => `<li>• ${escapeHtml(i.product_name)} (x${i.quantity}) - ₹${Math.round(i.price_at_purchase * i.quantity).toLocaleString('en-IN')}</li>`).join('')}
      </ul>
    </div>
  `;

  document.getElementById('checkoutReceiptBackdrop').classList.add('active');
}

async function openOrdersModal() {
  if (!state.token) {
    openAuthModal();
    return;
  }

  const container = document.getElementById('ordersListContainer');
  container.innerHTML = '<div class="spinner"></div>';
  document.getElementById('ordersModalBackdrop').classList.add('active');

  const res = await apiCall('/orders', 'GET', null, true);
  if (res.ok && res.data.orders) {
    if (res.data.orders.length === 0) {
      container.innerHTML = '<p style="text-align:center; padding:30px; color:#6B7280;">No past orders found. Add items to cart and try our Mock Checkout!</p>';
      return;
    }

    container.innerHTML = res.data.orders.map(order => {
      const inrTotal = Math.round(order.total);
      const date = new Date(order.created_at).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' });
      return `
        <div class="order-history-card">
          <div class="order-card-header">
            <div>
              <strong>Order #IM-${order.id}</strong>
              <span style="color:#6B7280; margin-left:8px;">${date}</span>
            </div>
            <div style="font-weight:700; color:#E31E24;">₹${inrTotal.toLocaleString('en-IN')}</div>
          </div>
          <table class="order-items-table">
            ${(order.items || []).map(i => `
              <tr>
                <td style="padding:4px 0;">${escapeHtml(i.product_name)}</td>
                <td style="text-align:center; color:#6B7280;">x${i.quantity}</td>
                <td style="text-align:right; font-weight:600;">₹${Math.round(i.price_at_purchase * i.quantity).toLocaleString('en-IN')}</td>
              </tr>
            `).join('')}
          </table>
        </div>
      `;
    }).join('');
  }
}

// =============================================================================
// 9. PRODUCT DETAIL MODAL
// =============================================================================
function openProductModal(productId) {
  const p = state.products.find(item => item.id === productId);
  if (!p) return;

  const inrPrice = formatINR(p.price);
  const strikethrough = formatMRP(p);
  const discount = getDiscountPercent(p);
  const inStock = p.stock > 0;

  const body = document.getElementById('productModalBody');
  body.innerHTML = `
    <div class="modal-prod-media">
      <img src="${p.image_url || FALLBACK_IMAGE}" alt="${escapeHtml(p.name)}" onerror="this.src='${FALLBACK_IMAGE}';">
    </div>
    <div class="modal-prod-info">
      <span class="modal-prod-category">${escapeHtml(p.category)}</span>
      <h3 class="modal-prod-title">${escapeHtml(p.name)}</h3>
      
      <div class="product-card-price-row" style="margin-bottom:12px;">
        <span class="product-current-price" style="font-size:1.4rem;">${inrPrice}</span>
        <span class="product-strikethrough-mrp">${strikethrough}</span>
        <span class="product-discount-badge" style="position:static; margin-left:6px;">${discount}</span>
      </div>

      <p class="modal-prod-desc">${escapeHtml(p.description)}</p>

      <div class="modal-meta-grid">
        <div class="modal-meta-item">
          <strong>Experience Level</strong>
          <span>${escapeHtml(p.experience_level.toUpperCase())}</span>
        </div>
        <div class="modal-meta-item">
          <strong>Space Needed</strong>
          <span>${escapeHtml(p.space_needed.toUpperCase())}</span>
        </div>
        <div class="modal-meta-item">
          <strong>Inventory Stock</strong>
          <span>${inStock ? `<span style="color:#16A34A; font-weight:700;">${p.stock} units left</span>` : '<span style="color:#DC2626; font-weight:700;">Out of Stock</span>'}</span>
        </div>
        <div class="modal-meta-item">
          <strong>Training Focus</strong>
          <span>${(p.goal_tags || []).join(', ') || 'Fitness'}</span>
        </div>
      </div>

      <div style="margin-top:auto;">
        ${inStock ? `
          <button class="btn btn-primary btn-full btn-pill" onclick="handleAddToCart(${p.id}); closeModals();">
            Add to Cart (${inrPrice})
          </button>
        ` : `
          <button class="btn btn-primary btn-full btn-pill" disabled style="background:#EF4444; opacity:0.7;">
            Out of Stock
          </button>
        `}
      </div>
    </div>
  `;

  document.getElementById('productModalBackdrop').classList.add('active');
}

// =============================================================================
// 10. AUTHENTICATION (SIGNIN, SIGNUP & 1-CLICK DEMO LOGIN)
// =============================================================================
function updateAuthUI() {
  const label = document.getElementById('accountBtnLabel');
  const dropdown = document.getElementById('userDropdownCard');

  if (state.token && state.user) {
    label.textContent = state.user.name.split(' ')[0];
    document.getElementById('dropdownUserName').textContent = state.user.name;
    document.getElementById('dropdownUserEmail').textContent = state.user.email;
    document.getElementById('userAvatarLetter').textContent = state.user.name.charAt(0).toUpperCase();
  } else {
    label.textContent = 'Account';
    dropdown.classList.remove('active');
  }
}

async function handleLogin(email, password) {
  const errorEl = document.getElementById('loginErrorMsg');
  errorEl.textContent = '';

  const res = await apiCall('/auth/login', 'POST', { email, password });
  if (res.ok && res.data.token) {
    state.token = res.data.token;
    state.user = res.data.user;
    localStorage.setItem('ironmate_token', state.token);
    localStorage.setItem('ironmate_user', JSON.stringify(state.user));
    updateAuthUI();
    closeModals();
    showToast(`Welcome back, ${state.user.name}!`, 'success');
    await loadCart();
  } else {
    errorEl.textContent = res.data.message || 'Invalid credentials.';
  }
}

async function handleSignup(name, email, password) {
  const errorEl = document.getElementById('signupErrorMsg');
  errorEl.textContent = '';

  const res = await apiCall('/auth/signup', 'POST', { name, email, password });
  if (res.ok && res.data.token) {
    state.token = res.data.token;
    state.user = res.data.user;
    localStorage.setItem('ironmate_token', state.token);
    localStorage.setItem('ironmate_user', JSON.stringify(state.user));
    updateAuthUI();
    closeModals();
    showToast(`Account created! Welcome, ${state.user.name}!`, 'success');
    await loadCart();
  } else {
    errorEl.textContent = res.data.message || 'Registration failed.';
  }
}

/** 1-Click Demo Login button for College Viva */
async function demoLoginAuto() {
  await handleLogin('demo@ironmate.com', 'demo1234');
}

function handleLogout() {
  state.token = null;
  state.user = null;
  state.cart = { items: [], total: 0, item_count: 0 };
  localStorage.removeItem('ironmate_token');
  localStorage.removeItem('ironmate_user');
  updateAuthUI();
  updateCartUI();
  showToast('Logged out successfully.', 'success');
}

function openAuthModal() {
  document.getElementById('authModalBackdrop').classList.add('active');
}

// =============================================================================
// 11. FLOATING AI SHOPPING ASSISTANT CONTROLLER (3 MODES)
// =============================================================================
function toggleAiWindow() {
  const win = document.getElementById('aiChatWindow');
  win.classList.toggle('active');
  if (win.classList.contains('active')) {
    // If opening, ensure active pane is refreshed
    if (state.ai.activeTab === 'cart') {
      loadCartAdvisorContent();
    }
  }
}

function switchAiTab(tabName) {
  state.ai.activeTab = tabName;
  document.querySelectorAll('.ai-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabName));
  document.querySelectorAll('.ai-tab-pane').forEach(p => p.classList.remove('active'));

  if (tabName === 'chat') {
    document.getElementById('paneChat').classList.add('active');
  } else if (tabName === 'finder') {
    document.getElementById('paneFinder').classList.add('active');
    initFinderFlow();
  } else if (tabName === 'cart') {
    document.getElementById('paneCart').classList.add('active');
    loadCartAdvisorContent();
  }

  // Ensure window is open
  document.getElementById('aiChatWindow').classList.add('active');
}

// --- Mode 1: General RAG Chat ---
async function handleSendChatMessage(text) {
  if (!text || state.ai.isTyping) return;

  const container = document.getElementById('chatMessagesContainer');
  
  // Render user message
  container.insertAdjacentHTML('beforeend', `
    <div class="ai-msg user">
      <div class="msg-bubble">${escapeHtml(text)}</div>
    </div>
  `);
  container.scrollTop = container.scrollHeight;

  // Render typing indicator
  state.ai.isTyping = true;
  const typingId = `typing-${Date.now()}`;
  container.insertAdjacentHTML('beforeend', `
    <div class="ai-msg bot" id="${typingId}">
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>
  `);
  container.scrollTop = container.scrollHeight;

  const res = await apiCall('/chat', 'POST', { message: text, history: state.ai.chatHistory }, !!state.token);
  state.ai.isTyping = false;
  const typingEl = document.getElementById(typingId);
  if (typingEl) typingEl.remove();

  if (res.ok && res.data.reply) {
    const reply = res.data.reply;
    const sources = res.data.sources || [];

    // Parse simple markdown formatting (bold, bullet points)
    let formattedReply = escapeHtml(reply)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n•/g, '<br>•')
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n/g, '<br>');

    // Check if any product is referenced to show mini cards
    let matchedProductsHtml = '';
    state.products.forEach(prod => {
      if (reply.toLowerCase().includes(prod.name.toLowerCase().substring(0, 15))) {
        matchedProductsHtml += `
          <div class="chat-product-card">
            <img src="${prod.image_url}" class="chat-product-img" onerror="this.src='${FALLBACK_IMAGE}';">
            <div class="chat-product-info">
              <div class="chat-product-name">${escapeHtml(prod.name)}</div>
              <div class="chat-product-price">${formatINR(prod.price)}</div>
            </div>
            <button class="btn btn-primary btn-sm chat-product-add-btn" onclick="handleAddToCart(${prod.id})">+ Add</button>
          </div>
        `;
      }
    });

    const sourcesHtml = sources.length > 0 ? `
      <div class="msg-sources-list">
        ${sources.map(s => `<span class="source-badge">📚 ${escapeHtml(s.category)}</span>`).join('')}
      </div>
    ` : '';

    container.insertAdjacentHTML('beforeend', `
      <div class="ai-msg bot">
        <div class="msg-bubble">
          ${formattedReply}
          ${matchedProductsHtml}
          ${sourcesHtml}
        </div>
      </div>
    `);

    state.ai.chatHistory.push({ role: 'user', content: text });
    state.ai.chatHistory.push({ role: 'bot', content: reply });
  } else {
    container.insertAdjacentHTML('beforeend', `
      <div class="ai-msg bot">
        <div class="msg-bubble" style="color:#DC2626;">
          ${res.data.message || 'I had trouble answering that right now. Please try again!'}
        </div>
      </div>
    `);
  }

  container.scrollTop = container.scrollHeight;
}

// Helper to open AI from outside with prefilled prompt
function openAiWithQuery(query) {
  switchAiTab('chat');
  handleSendChatMessage(query);
}

// --- Mode 2: Guided Product Finder (4-Step Flow) ---
async function initFinderFlow() {
  state.ai.finderStep = 0;
  state.ai.finderAnswers = {};
  await fetchFinderStep(0, {});
}

async function fetchFinderStep(step, answers) {
  const body = document.getElementById('finderBody');
  const progress = document.getElementById('finderProgressFill');
  body.innerHTML = '<div class="spinner"></div>';

  const res = await apiCall('/plan-finder', 'POST', { step, answers });
  if (res.ok) {
    const data = res.data;
    if (!data.completed) {
      // Show question
      const current = data.current_step;
      progress.style.width = `${(current / 4) * 100}%`;

      body.innerHTML = `
        <div class="finder-step-tag">Step ${current} of 4</div>
        <h4 class="finder-question-title">${escapeHtml(data.question)}</h4>
        <div class="finder-options-list">
          ${data.options.map(opt => `
            <button class="finder-opt-card" onclick="selectFinderOption('${data.field}', '${opt.value}', ${step + 1})">
              ${escapeHtml(opt.label)}
            </button>
          `).join('')}
        </div>
      `;
    } else {
      // Completed! Show recommendations
      progress.style.width = '100%';
      const recs = data.recommendations || [];

      body.innerHTML = `
        <div class="finder-step-tag" style="color:#16A34A;">MATCH FOUND ✨</div>
        <h4 class="finder-question-title">Your Tailored Fitness Recommendations</h4>
        <p style="font-size:0.85rem; color:#6B7280; margin-bottom:16px;">${escapeHtml(data.summary)}</p>

        <div style="display:flex; flex-direction:column; gap:12px;">
          ${recs.map(r => `
            <div class="chat-product-card" style="padding:12px;">
              <img src="${r.image_url}" class="chat-product-img" style="width:64px; height:64px;" onerror="this.src='${FALLBACK_IMAGE}';">
              <div class="chat-product-info">
                <div class="chat-product-name" style="font-size:0.875rem;">${escapeHtml(r.name)}</div>
                <div class="chat-product-price" style="font-size:0.9375rem; margin:2px 0;">${formatINR(r.price)}</div>
                <p style="font-size:0.75rem; color:#6B7280; line-height:1.3;">${escapeHtml(r.reason)}</p>
              </div>
              <button class="btn btn-primary btn-sm chat-product-add-btn" onclick="handleAddToCart(${r.id})">Add to Cart</button>
            </div>
          `).join('')}
        </div>

        <button class="btn btn-outline btn-full btn-sm btn-pill" style="margin-top:18px;" onclick="initFinderFlow()">
          🔄 Retake Product Finder Quiz
        </button>
      `;
    }
  }
}

function selectFinderOption(field, value, nextStep) {
  state.ai.finderAnswers[field] = value;
  fetchFinderStep(nextStep, state.ai.finderAnswers);
}

// --- Mode 3: Cart-Aware Assistant ---
async function loadCartAdvisorContent(userMessage = '') {
  const body = document.getElementById('cartAdvisorBody');
  body.innerHTML = '<div class="spinner"></div>';

  if (!state.token) {
    body.innerHTML = `
      <div style="text-align:center; padding:30px 10px;">
        <p style="font-weight:700;">Please Sign In to Access Cart Advisor</p>
        <p style="font-size:0.85rem; color:#6B7280; margin-top:6px;">The AI reads your actual shopping cart to recommend matching lifting accessories.</p>
        <button class="btn btn-primary btn-sm btn-pill" style="margin-top:14px;" onclick="demoLoginAuto()">1-Click Demo Login</button>
      </div>`;
    return;
  }

  const payload = userMessage ? { message: userMessage } : {};
  const res = await apiCall('/chat/cart-aware', 'POST', payload, true);
  if (res.ok && res.data) {
    const data = res.data;
    const suggestions = data.suggested_products || [];

    body.innerHTML = `
      <div class="ai-msg bot" style="max-width:100%; margin-bottom:12px;">
        <div class="msg-bubble" style="background:#F5F6F8;">
          ${escapeHtml(data.reply).replace(/\n/g, '<br>')}
        </div>
      </div>

      ${suggestions.length > 0 ? `
        <div style="margin-top:14px;">
          <span style="font-size:0.75rem; font-weight:800; color:#E31E24; text-transform:uppercase;">Recommended Add-Ons:</span>
          ${suggestions.map(s => `
            <div class="chat-product-card">
              <img src="${s.image_url}" class="chat-product-img" onerror="this.src='${FALLBACK_IMAGE}';">
              <div class="chat-product-info">
                <div class="chat-product-name">${escapeHtml(s.name)}</div>
                <div class="chat-product-price">${formatINR(s.price)}</div>
                <div style="font-size:0.72rem; color:#6B7280;">${escapeHtml(s.reason)}</div>
              </div>
              <button class="btn btn-primary btn-sm chat-product-add-btn" onclick="handleAddToCart(${s.id})">+ Add</button>
            </div>
          `).join('')}
        </div>
      ` : ''}
    `;
  }
}

// =============================================================================
// 12. EVENT LISTENERS & NAVIGATION HOOKS
// =============================================================================
function setupEventListeners() {
  // Brand Logo Click -> Reset to top
  safeAddListener('logoBtn', 'click', (e) => {
    e.preventDefault();
    resetAllFilters(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // Search input & button
  const searchInput = document.getElementById('globalSearchInput');
  const executeSearch = () => {
    if (searchInput) {
      state.filters.search = searchInput.value.trim();
      applyAllFilters();
      scrollToCatalog();
    }
  };
  safeAddListener('searchSubmitBtn', 'click', executeSearch);
  safeAddListener('globalSearchInput', 'keydown', (e) => {
    if (e.key === 'Enter') executeSearch();
  });

  // Search bar AI Pill
  safeAddListener('searchAiPillBtn', 'click', () => {
    switchAiTab('finder');
  });

  // Account dropdown toggle / Auth modal
  safeAddListener('accountBtn', 'click', () => {
    if (state.token) {
      const dd = document.getElementById('userDropdownCard');
      if (dd) dd.classList.toggle('active');
    } else {
      openAuthModal();
    }
  });

  // User Dropdown Items
  safeAddListener('navMyOrdersBtn', 'click', () => {
    const dd = document.getElementById('userDropdownCard');
    if (dd) dd.classList.remove('active');
    openOrdersModal();
  });
  safeAddListener('navLogoutBtn', 'click', () => {
    handleLogout();
  });

  // Cart Drawer triggers
  safeAddListener('openCartBtn', 'click', openCartDrawer);
  safeAddListener('closeCartBtn', 'click', closeCartDrawer);
  safeAddListener('cartOverlay', 'click', closeCartDrawer);
  safeAddListener('proceedCheckoutBtn', 'click', handleCheckout);
  safeAddListener('cartAskAiBtn', 'click', () => {
    closeCartDrawer();
    switchAiTab('cart');
  });

  // Tier 2 Dropdown Links & Direct Links
  document.querySelectorAll('.dropdown-link').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const cat = link.dataset.filterCat;
      const search = link.dataset.search;
      const deal = link.dataset.filterDeal;

      // Clear conflicting filters
      state.filters.categories.clear();
      document.querySelectorAll('input[name="catFilter"]').forEach(b => b.checked = false);
      state.filters.subcat = 'all';
      document.querySelectorAll('.subcat-pill').forEach(b => b.classList.toggle('active', b.dataset.sub === 'all'));

      if (deal) {
        state.filters.category = 'all';
        state.filters.search = '';
        if (searchInput) searchInput.value = '';
        if (deal === 'under2000') {
          state.filters.priceRange = '0-2000';
          const r = document.querySelector('input[name="priceRangeRadio"][value="0-2000"]');
          if (r) r.checked = true;
        } else if (deal === 'bestsellers') {
          state.filters.priceRange = 'all';
          state.filters.sort = 'price_desc';
          const sortSel = document.getElementById('catalogSortSelect');
          if (sortSel) sortSel.value = 'price_desc';
        } else if (deal === 'homegym') {
          state.filters.goals.clear();
          state.filters.goals.add('home_gym');
          const box = document.querySelector('input[name="goalFilter"][value="home_gym"]');
          if (box) box.checked = true;
        }
      } else if (cat && cat !== 'all') {
        state.filters.category = cat;
        const isSingleCat = !cat.includes(',');
        document.querySelectorAll('.cat-tab-btn').forEach(b => {
          if (isSingleCat) {
            b.classList.toggle('active', b.dataset.category.toLowerCase() === cat.toLowerCase());
          } else {
            b.classList.toggle('active', b.dataset.category === 'all');
          }
        });
        if (isSingleCat) {
          document.querySelectorAll('.subcat-pill').forEach(b => {
            b.classList.toggle('active', b.dataset.sub.toLowerCase() === cat.toLowerCase());
          });
        }
      } else {
        state.filters.category = 'all';
        document.querySelectorAll('.cat-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.category === 'all'));
      }

      if (search) {
        state.filters.search = search;
        if (searchInput) searchInput.value = search;
      } else if (!deal) {
        state.filters.search = '';
        if (searchInput) searchInput.value = '';
      }

      applyAllFilters();
      scrollToCatalog();
    });
  });

  // "Find your fit" Pills
  document.querySelectorAll('.fit-pill').forEach(pill => {
    pill.addEventListener('click', handleFitPillClick);
  });
  safeAddListener('clearFitFiltersBtn', 'click', clearFitBox);
  safeAddListener('fitBrowseBtn', 'click', applyFitFiltersToCatalog);

  // 3 Feature Cards
  safeAddListener('featureCardSetup', 'click', () => {
    state.filters.goals.clear();
    state.filters.goals.add('home_gym');
    uncheckSidebarBox('goalFilter', 'home_gym');
    const box = document.querySelector('input[name="goalFilter"][value="home_gym"]');
    if (box) box.checked = true;
    applyAllFilters();
    scrollToCatalog();
  });

  safeAddListener('featureCardAiChat', 'click', () => {
    switchAiTab('chat');
  });

  safeAddListener('featureCardFinder', 'click', () => {
    switchAiTab('finder');
  });

  // Category Tabs (All, Strength, Cardio, Apparel, Accessories, Nutrition)
  document.querySelectorAll('.cat-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      setCategory(btn.dataset.category);
    });
  });

  // Sub-category Pills (Screenshot 6 Style)
  document.querySelectorAll('.subcat-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.subcat-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.filters.subcat = btn.dataset.sub;
      applyAllFilters();
    });
  });

  // Sidebar Category Checkboxes & Radios
  document.querySelectorAll('input[name="catFilter"]').forEach(box => {
    box.addEventListener('change', () => {
      if (box.checked) {
        state.filters.categories.add(box.value);
      } else {
        state.filters.categories.delete(box.value);
      }
      if (state.filters.categories.size > 0) {
        state.filters.category = 'all';
        document.querySelectorAll('.cat-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.category === 'all'));
      }
      applyAllFilters();
    });
  });

  // Footer Category Links
  document.querySelectorAll('.footer-links a[data-filter-cat]').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const cat = link.dataset.filterCat;
      setCategory(cat);
    });
  });

  document.querySelectorAll('input[name="goalFilter"]').forEach(box => {
    box.addEventListener('change', () => {
      if (box.checked) state.filters.goals.add(box.value);
      else state.filters.goals.delete(box.value);
      applyAllFilters();
    });
  });

  document.querySelectorAll('input[name="expFilter"]').forEach(box => {
    box.addEventListener('change', () => {
      if (box.checked) state.filters.experience.add(box.value);
      else state.filters.experience.delete(box.value);
      applyAllFilters();
    });
  });

  document.querySelectorAll('input[name="spaceFilter"]').forEach(box => {
    box.addEventListener('change', () => {
      if (box.checked) state.filters.space.add(box.value);
      else state.filters.space.delete(box.value);
      applyAllFilters();
    });
  });

  document.querySelectorAll('input[name="priceRangeRadio"]').forEach(radio => {
    radio.addEventListener('change', () => {
      state.filters.priceRange = radio.value;
      applyAllFilters();
    });
  });

  safeAddListener('resetSidebarFiltersBtn', 'click', () => {
    resetAllFilters(false);
  });

  // Catalog Sort Select
  safeAddListener('catalogSortSelect', 'change', (e) => {
    state.filters.sort = e.target.value;
    applyAllFilters();
  });

  // Hero CTAs & Safe Slider Fallbacks
  safeAddListener('heroTryAiBtn', 'click', () => {
    switchAiTab('finder');
  });
  safeAddListener('heroPrevBtn', 'click', () => {});
  safeAddListener('heroNextBtn', 'click', () => {});

  // Modals Close handlers
  document.querySelectorAll('.modal-close-btn').forEach(btn => {
    btn.addEventListener('click', closeModals);
  });
  document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) closeModals();
    });
  });

  // Auth Tabs (SignIn vs SignUp)
  const tabLogin = document.getElementById('tabLoginBtn');
  const tabSignup = document.getElementById('tabSignupBtn');
  const formLogin = document.getElementById('loginForm');
  const formSignup = document.getElementById('signupForm');

  safeAddListener('tabLoginBtn', 'click', () => {
    if (tabLogin) tabLogin.classList.add('active');
    if (tabSignup) tabSignup.classList.remove('active');
    if (formLogin) formLogin.classList.remove('hidden');
    if (formSignup) formSignup.classList.add('hidden');
  });

  safeAddListener('tabSignupBtn', 'click', () => {
    if (tabSignup) tabSignup.classList.add('active');
    if (tabLogin) tabLogin.classList.remove('active');
    if (formSignup) formSignup.classList.remove('hidden');
    if (formLogin) formLogin.classList.add('hidden');
  });

  // Auth Forms Submission
  safeAddListener('loginForm', 'submit', (e) => {
    e.preventDefault();
    const emailEl = document.getElementById('loginEmail');
    const passEl = document.getElementById('loginPassword');
    if (emailEl && passEl) {
      handleLogin(emailEl.value, passEl.value);
    }
  });

  safeAddListener('signupForm', 'submit', (e) => {
    e.preventDefault();
    const nameEl = document.getElementById('signupName');
    const emailEl = document.getElementById('signupEmail');
    const passEl = document.getElementById('signupPassword');
    if (nameEl && emailEl && passEl) {
      handleSignup(nameEl.value, emailEl.value, passEl.value);
    }
  });

  safeAddListener('quickDemoLoginBtn', 'click', demoLoginAuto);

  // Receipt Modal Continue
  safeAddListener('receiptContinueBtn', 'click', () => {
    closeModals();
    scrollToCatalog();
  });

  // Floating AI Assistant Trigger & Tabs
  safeAddListener('floatingAiTrigger', 'click', toggleAiWindow);
  safeAddListener('closeAiWindowBtn', 'click', toggleAiWindow);

  safeAddListener('aiTabChat', 'click', () => switchAiTab('chat'));
  safeAddListener('aiTabFinder', 'click', () => switchAiTab('finder'));
  safeAddListener('aiTabCart', 'click', () => switchAiTab('cart'));

  // Chat Input
  safeAddListener('chatInputForm', 'submit', (e) => {
    e.preventDefault();
    const input = document.getElementById('chatInputText');
    if (input) {
      const msg = input.value.trim();
      if (msg) {
        input.value = '';
        handleSendChatMessage(msg);
      }
    }
  });

  // Quick prompt chips
  document.querySelectorAll('.chip-btn').forEach(chip => {
    chip.addEventListener('click', () => {
      handleSendChatMessage(chip.dataset.prompt);
    });
  });

  // Cart Advisor input
  safeAddListener('cartAdvisorInputForm', 'submit', (e) => {
    e.preventDefault();
    const input = document.getElementById('cartAdvisorInputText');
    if (input) {
      const msg = input.value.trim();
      if (msg) {
        input.value = '';
        loadCartAdvisorContent(msg);
      }
    }
  });
}

function setCategory(catName) {
  // Clear conflicting subcat or specific search
  state.filters.subcat = 'all';
  state.filters.search = '';
  const searchInput = document.getElementById('globalSearchInput');
  if (searchInput) searchInput.value = '';
  state.filters.categories.clear();
  document.querySelectorAll('input[name="catFilter"]').forEach(b => b.checked = false);
  document.querySelectorAll('.subcat-pill').forEach(b => b.classList.toggle('active', b.dataset.sub === 'all'));

  state.filters.category = catName;
  document.querySelectorAll('.cat-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.category.toLowerCase() === (catName || 'all').toLowerCase());
  });
  applyAllFilters();
  scrollToCatalog();
}

function closeModals() {
  document.querySelectorAll('.modal-backdrop').forEach(m => m.classList.remove('active'));
}

// =============================================================================
// 13. TOAST NOTIFICATIONS & SANITIZATION
// =============================================================================
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : 'ℹ️'}</span>
    <span>${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

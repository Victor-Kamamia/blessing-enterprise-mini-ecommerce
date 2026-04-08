let cart = JSON.parse(localStorage.getItem("cart")) || [];

let productsRendered = false;
let activeCategory = sessionStorage.getItem("activeCategory") || "All";
let searchQuery = sessionStorage.getItem("productSearchQuery") || "";
let sortOption = sessionStorage.getItem("productSortOption") || "featured";
let visibleProductCount = 6;
let toastTimeoutId = null;
let favorites = JSON.parse(localStorage.getItem("favorites")) || [];

function getVisibleOverlayCount() {
  return document.querySelectorAll(
    "#cart-modal:not(.hidden), #product-details-modal:not(.hidden), #checkout-modal:not(.hidden)"
  ).length;
}

function syncBodyScrollLock() {
  document.body.classList.toggle("modal-open", getVisibleOverlayCount() > 0);
}

function openOverlay(modal) {
  if (!modal) return;
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  syncBodyScrollLock();
}

function closeOverlay(modal) {
  if (!modal) return;
  modal.classList.add("hidden");
  modal.classList.remove("flex");
  syncBodyScrollLock();
}

function setFieldError(fieldId, message) {
  const field = document.getElementById(fieldId);
  const error = document.getElementById(`${fieldId.replace("customer-", "")}-error`);
  if (!field || !error) return;

  field.classList.toggle("field-error", Boolean(message));
  error.textContent = message;
  error.classList.toggle("hidden", !message);
}

function setCheckoutStatus(message, type) {
  const status = document.getElementById("checkout-status");
  if (!status) return;

  if (!message) {
    status.className = "hidden";
    status.innerHTML = "";
    return;
  }

  const isSuccess = type === "success";
  status.className = isSuccess
    ? "status-chip bg-green-50 text-green-700"
    : "status-chip bg-rose-50 text-rose-700";
  status.innerHTML = isSuccess
    ? "<span class='inline-flex h-2.5 w-2.5 rounded-full bg-green-500'></span>Order details ready. Opening WhatsApp..."
    : `<span class='inline-flex h-2.5 w-2.5 rounded-full bg-rose-500'></span>${message}`;
}

function clearCheckoutFeedback() {
  setFieldError("customer-name", "");
  setFieldError("customer-phone", "");
  setFieldError("customer-address", "");
  setCheckoutStatus("", "");
}

function showToast(message) {
  const toast = document.getElementById("cart-toast");
  const text = document.getElementById("cart-toast-text");
  if (!toast || !text) return;

  text.innerText = message;
  toast.classList.remove("translate-y-24", "opacity-0", "pointer-events-none");
  toast.classList.add("translate-y-0", "opacity-100");

  if (toastTimeoutId) {
    clearTimeout(toastTimeoutId);
  }

  toastTimeoutId = setTimeout(() => {
    toast.classList.add("translate-y-24", "opacity-0", "pointer-events-none");
    toast.classList.remove("translate-y-0", "opacity-100");
  }, 2200);
}

function getFilteredProducts() {
  const filtered = products.filter((product) => {
    const matchesCategory =
      activeCategory === "All" ||
      (activeCategory === "Offers" && Boolean(product.offer)) ||
      (activeCategory === "Favorites" && favorites.includes(product.id)) ||
      product.category === activeCategory;
    const searchableText = `${product.name} ${product.category} ${product.description}`.toLowerCase();
    const matchesSearch = !searchQuery || searchableText.includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const sorted = [...filtered];

  switch (sortOption) {
    case "name-asc":
      sorted.sort((a, b) => a.name.localeCompare(b.name));
      break;
    case "name-desc":
      sorted.sort((a, b) => b.name.localeCompare(a.name));
      break;
    case "price-asc":
      sorted.sort((a, b) => a.price - b.price);
      break;
    case "price-desc":
      sorted.sort((a, b) => b.price - a.price);
      break;
    default:
      break;
  }

  return sorted;
}

function setActiveCategory(category) {
  activeCategory =
    category === "Favorites" ||
    category === "Offers" ||
    productCategories.includes(category)
      ? category
      : "All";
  sessionStorage.setItem("activeCategory", activeCategory);
  visibleProductCount = 6;
}

function setSearchQuery(query) {
  searchQuery = query.trim();
  sessionStorage.setItem("productSearchQuery", searchQuery);
  visibleProductCount = 6;
}

function setSortOption(option) {
  const allowed = ["featured", "name-asc", "name-desc", "price-asc", "price-desc"];
  sortOption = allowed.includes(option) ? option : "featured";
  sessionStorage.setItem("productSortOption", sortOption);
  visibleProductCount = 6;
}

function openCategory(category) {
  setActiveCategory(category);
  loadPage("pages/products.html");
}

function isFavorite(id) {
  return favorites.includes(id);
}

function toggleFavorite(id) {
  const product = products.find((item) => item.id === id);
  if (!product) return;

  if (isFavorite(id)) {
    favorites = favorites.filter((favoriteId) => favoriteId !== id);
    showToast(`${product.name} removed from wishlist`);
  } else {
    favorites.push(id);
    showToast(`${product.name} added to wishlist`);
  }

  localStorage.setItem("favorites", JSON.stringify(favorites));
  updateFavoritesUI();
  productsRendered = false;
  renderProducts();
}

function renderCategoryFilters() {
  const container = document.getElementById("category-filters");
  if (!container) return;

  const categories = [...productCategories, "Offers", "Favorites"];

  container.innerHTML = categories.map((category) => {
    const activeClasses = category === activeCategory
      ? "bg-gradient-to-r from-fuchsia-500 to-violet-600 text-white shadow-soft"
      : "bg-white text-violet-700 border border-fuchsia-100";

    return `
      <button
        onclick="filterProducts('${category}')"
        class="rounded-full px-4 py-2 text-sm font-medium transition hover:-translate-y-0.5 ${activeClasses}">
        ${category}
      </button>
    `;
  }).join("");
}

function getFavoriteButtonMarkup(id, variant = "card") {
  const saved = isFavorite(id);
  const baseClasses =
    variant === "modal"
      ? "inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-medium transition"
      : "inline-flex h-11 w-11 items-center justify-center rounded-full text-xl leading-none transition";

  const stateClasses = saved
    ? "bg-violet-600 text-white shadow-md shadow-violet-200"
    : "bg-violet-100 text-violet-700 hover:bg-violet-200";

  const icon = saved ? "♥" : "♡";
  const label = saved ? "Saved" : "Save";
  const srLabel = saved ? "Remove from wishlist" : "Add to wishlist";

  if (variant === "modal") {
    return `
      <button
        onclick="toggleFavorite(${id}); openProductDetails(${id});"
        class="${baseClasses} ${stateClasses}"
        aria-label="${srLabel}">
        <span aria-hidden="true" class="text-base">${icon}</span>
        <span>${label}</span>
      </button>
    `;
  }

  return `
    <button
      onclick="event.stopPropagation(); toggleFavorite(${id})"
      class="${baseClasses} ${stateClasses}"
      aria-label="${srLabel}"
      title="${srLabel}">
      <span aria-hidden="true">${icon}</span>
    </button>
  `;
}

function getPriceMarkup(product, compact = false) {
  if (!product.offer) {
    return compact
      ? `<span class="rounded-full bg-rose-50 px-3 py-1 text-sm font-semibold text-rose-700">$${product.price}</span>`
      : `<p class="mt-5 text-xl font-semibold text-rose-700">$${product.price}</p>`;
  }

  const original = product.offer.originalPrice;

  if (compact) {
    return `
      <div class="flex flex-col items-end">
        <span class="rounded-full bg-rose-50 px-3 py-1 text-sm font-semibold text-rose-700">$${product.price}</span>
        <span class="mt-1 text-xs font-medium text-gray-400 line-through">$${original}</span>
      </div>
    `;
  }

  return `
    <div class="mt-5 flex items-center gap-3">
      <p class="text-xl font-semibold text-rose-700">$${product.price}</p>
      <p class="text-sm font-medium text-gray-400 line-through">$${original}</p>
      <span class="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">${product.offer.label}</span>
    </div>
  `;
}

function updateSearchUI(resultsCount) {
  const searchInput = document.getElementById("product-search");
  const clearButton = document.getElementById("clear-search");
  const resultsCountLabel = document.getElementById("product-results-count");
  const sortSelect = document.getElementById("product-sort");

  if (searchInput) {
    searchInput.value = searchQuery;
  }

  if (sortSelect) {
    sortSelect.value = sortOption;
  }

  if (clearButton) {
    clearButton.disabled = !searchQuery;
    clearButton.classList.toggle("opacity-60", !searchQuery);
  }

  if (resultsCountLabel) {
    const label = resultsCount === 1 ? "product" : "products";
    resultsCountLabel.innerText = `${resultsCount} ${label}`;
  }
}

function updateFavoritesUI() {
  const favoritesCount = document.getElementById("favorites-count");
  if (favoritesCount) {
    favoritesCount.innerText = favorites.length;
  }
}

function attachSearchListeners() {
  const searchInput = document.getElementById("product-search");
  const clearButton = document.getElementById("clear-search");
  const sortSelect = document.getElementById("product-sort");
  const loadMoreButton = document.getElementById("load-more-products");

  if (searchInput && !searchInput.dataset.bound) {
    searchInput.dataset.bound = "true";
    searchInput.addEventListener("input", (event) => {
      setSearchQuery(event.target.value);
      productsRendered = false;
      renderProducts();
    });
  }

  if (clearButton && !clearButton.dataset.bound) {
    clearButton.dataset.bound = "true";
    clearButton.addEventListener("click", () => {
      setSearchQuery("");
      productsRendered = false;
      renderProducts();
    });
  }

  if (sortSelect && !sortSelect.dataset.bound) {
    sortSelect.dataset.bound = "true";
    sortSelect.addEventListener("change", (event) => {
      setSortOption(event.target.value);
      productsRendered = false;
      renderProducts();
    });
  }

  if (loadMoreButton && !loadMoreButton.dataset.bound) {
    loadMoreButton.dataset.bound = "true";
    loadMoreButton.addEventListener("click", () => {
      visibleProductCount += 6;
      productsRendered = false;
      renderProducts();
    });
  }
}

function updateLoadMoreButton(totalCount, shownCount) {
  const loadMoreButton = document.getElementById("load-more-products");
  if (!loadMoreButton) return;

  if (shownCount < totalCount) {
    loadMoreButton.classList.remove("hidden");
    loadMoreButton.innerText = `Load More Products (${totalCount - shownCount} left)`;
  } else {
    loadMoreButton.classList.add("hidden");
  }
}

function filterProducts(category) {
  setActiveCategory(category);
  productsRendered = false;
  renderProducts();
}

function openProductDetails(id) {
  const product = products.find((item) => item.id === id);
  const modal = document.getElementById("product-details-modal");
  const body = document.getElementById("product-details-body");

  if (!product || !modal || !body) return;

  body.innerHTML = `
    <div class="grid gap-6 md:grid-cols-[0.95fr_1.05fr]">
      <div class="overflow-hidden rounded-[1.6rem] bg-gradient-to-br from-pink-50 to-violet-100 p-4">
        <img src="${product.image}" alt="${product.name}" class="h-80 w-full rounded-[1.3rem] object-cover">
      </div>
      <div class="flex flex-col justify-center">
        <div class="mb-3 flex flex-wrap gap-2">
          <span class="inline-flex w-fit rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-rose-600">${product.category}</span>
          ${product.offer ? `<span class="inline-flex w-fit rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">${product.offer.label}</span>` : ""}
        </div>
        <h3 class="text-3xl text-[var(--ink)]">${product.name}</h3>
        <p class="mt-4 text-base leading-8 text-gray-600">${product.description}</p>
        <div class="mt-5 grid gap-4">
          <div class="rounded-[1.25rem] bg-white p-4 backdrop-blur-sm">
            <p class="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">Benefits</p>
            <ul class="mt-3 space-y-2 text-sm leading-7 text-gray-600">
              ${product.benefits.map((benefit) => `<li>- ${benefit}</li>`).join("")}
            </ul>
          </div>
          <div class="rounded-[1.25rem] bg-white p-4 backdrop-blur-sm">
            <p class="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">How to Use</p>
            <p class="mt-3 text-sm leading-7 text-gray-600">${product.usage}</p>
          </div>
          <div class="rounded-[1.25rem] bg-white p-4 backdrop-blur-sm">
            <p class="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">Hero Ingredients</p>
            <p class="mt-3 text-sm leading-7 text-gray-600">${product.ingredients.join(", ")}</p>
          </div>
        </div>
        <div class="sticky bottom-0 mt-6 rounded-[1.5rem] border border-rose-100/70 bg-white p-4 shadow-[0_-10px_24px_rgba(244,114,182,0.12)] backdrop-blur">
          ${getPriceMarkup(product)}
          <div class="mt-4 flex flex-wrap gap-3">
          <button onclick="addToCart(${product.id}); closeProductDetails();" class="btn-primary min-w-[10rem] rounded-full px-6 py-3 text-sm font-medium text-white">Add to Cart</button>
          ${getFavoriteButtonMarkup(product.id, "modal")}
          <button onclick="closeProductDetails()" class="btn-secondary rounded-full px-6 py-3 text-sm font-medium">Close</button>
          </div>
        </div>
      </div>
    </div>
  `;

  openOverlay(modal);
}

function closeProductDetails() {
  const modal = document.getElementById("product-details-modal");
  closeOverlay(modal);
}

function renderProducts() {
  const grid = document.getElementById("product-grid");
  if (!grid || productsRendered) return;

  productsRendered = true;
  updateFavoritesUI();
  renderCategoryFilters();
  attachSearchListeners();

  const fragment = document.createDocumentFragment();
  const filteredProducts = getFilteredProducts();
  updateSearchUI(filteredProducts.length);

  if (filteredProducts.length === 0) {
    updateLoadMoreButton(0, 0);
    grid.innerHTML = '<div class="col-span-full rounded-[1.5rem] bg-white px-6 py-10 text-center text-gray-500 backdrop-blur-sm">No products match your current search and category filter.</div>';
    return;
  }

  const productsToShow = filteredProducts.slice(0, visibleProductCount);
  updateLoadMoreButton(filteredProducts.length, productsToShow.length);

  productsToShow.forEach((p) => {
    const div = document.createElement("div");
    div.className = "interactive-card product-card group overflow-hidden rounded-[1.75rem] bg-white p-4 shadow-soft backdrop-blur-sm";
    div.innerHTML = `
      <div class="mb-3 flex items-center justify-between">
        <div class="flex flex-wrap gap-2">
          <span class="inline-flex rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-rose-600">${p.category}</span>
          ${p.offer ? `<span class="inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">${p.offer.label}</span>` : ""}
        </div>
        ${getFavoriteButtonMarkup(p.id)}
      </div>
      <button onclick="openProductDetails(${p.id})" class="block w-full text-left">
      <div class="relative overflow-hidden rounded-[1.4rem] bg-gradient-to-b from-pink-50 to-violet-100 p-4">
        <img src="${p.image}"
             class="h-64 w-full rounded-[1.2rem] object-cover transition duration-500 group-hover:scale-105"
             loading="lazy"
             onerror="this.src='imag/placeholder.png'"
             alt="${p.name}">
      </div>
      <div class="px-2 pb-2 pt-5">
        <div class="mb-3 flex items-start justify-between gap-3">
          <div>
            <h3 class="text-xl font-semibold text-rose-700">${p.name}</h3>
            <p class="mt-2 text-sm leading-6 text-gray-500">${p.description}</p>
          </div>
          ${getPriceMarkup(p, true)}
        </div>
      </div>
      </button>
      <button onclick="addToCart(${p.id})"
        class="btn-primary w-full rounded-2xl px-4 py-3 text-sm font-medium text-white">
        Add to Cart
      </button>
    `;
    fragment.appendChild(div);
  });

  grid.replaceChildren(fragment);
}

function addToCart(id) {
  const product = products.find(p => p.id === id);
  const existing = cart.find(item => item.id === id);

  if (existing) {
    existing.quantity += 1;
  } else {
    cart.push({ ...product, quantity: 1 });
  }

  saveCart();
  showToast(`${product.name} added to cart`);
}

function saveCart() {
  localStorage.setItem("cart", JSON.stringify(cart));
  updateCartUI();
}

function updateCartUI() {
  const cartCount = document.getElementById("cart-count");
  const cartCountMobile = document.getElementById("cart-count-mobile");
  if (cartCount) {
    const totalItems = cart.reduce((total, item) => total + item.quantity, 0);
    cartCount.innerText = totalItems;
    if (cartCountMobile) {
      cartCountMobile.innerText = totalItems;
    }
  }
}

function openCart() {
  const modal = document.getElementById("cart-modal");
  if (modal) {
    openOverlay(modal);
    renderCart();
  } else {
    console.error("Cart modal not found");
    alert("Cart is not available right now");
  }
}

function closeCart() {
  const modal = document.getElementById("cart-modal");
  closeOverlay(modal);
}

function openCheckoutModal() {
  const modal = document.getElementById("checkout-modal");
  const checkoutTotal = document.getElementById("checkout-total");
  const form = document.getElementById("checkout-form");

  if (!modal || !checkoutTotal) return;

  const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  checkoutTotal.innerText = total.toFixed(2);
  clearCheckoutFeedback();
  if (form) {
    form.reset();
  }
  openOverlay(modal);
}

function closeCheckoutModal() {
  const modal = document.getElementById("checkout-modal");
  closeOverlay(modal);
}

function renderCart() {
  const container = document.getElementById("cart-items");
  if (!container) return;
  
  let total = 0;

  if (cart.length === 0) {
    container.innerHTML = '<p class="rounded-2xl bg-white px-4 py-6 text-center text-gray-500 backdrop-blur-sm">Your cart is empty</p>';
    document.getElementById("cart-total").innerText = "0";
    return;
  }

  container.innerHTML = cart.map(item => {
    const itemTotal = item.price * item.quantity;
    total += itemTotal;
    return `
      <div class="mb-4 flex items-center justify-between gap-4 rounded-[1.5rem] bg-white p-4 backdrop-blur-sm">
        <div class="flex-1">
          <h4 class="font-semibold text-gray-800">${item.name}</h4>
          <p class="text-sm text-gray-600">$${item.price} x ${item.quantity}</p>
          <p class="text-sm font-semibold text-rose-700">$${itemTotal.toFixed(2)}</p>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="changeQty(${item.id}, -1)" class="rounded-full bg-white px-3 py-2 text-sm shadow backdrop-blur-sm">-</button>
          <button onclick="changeQty(${item.id}, 1)" class="rounded-full bg-white px-3 py-2 text-sm shadow backdrop-blur-sm">+</button>
          <button onclick="removeItem(${item.id})" class="ml-1 text-xs font-semibold uppercase tracking-[0.2em] text-red-500 hover:text-red-700">Delete</button>
        </div>
      </div>
    `;
  }).join("");

  document.getElementById("cart-total").innerText = total.toFixed(2);
}

function changeQty(id, delta) {
  const item = cart.find(i => i.id === id);
  if (item) {
    item.quantity += delta;
    if (item.quantity <= 0) {
      cart = cart.filter(i => i.id !== id);
    }
    saveCart();
    renderCart();
  }
}

function removeItem(id) {
  cart = cart.filter(i => i.id !== id);
  saveCart();
  renderCart();
}

// WHATSAPP CHECKOUT
function checkout() {
  if (cart.length === 0) {
    return;
  }

  openCheckoutModal();
}

function submitCheckoutForm(event) {
  event.preventDefault();

  if (cart.length === 0) {
    closeCheckoutModal();
    return;
  }

  const form = event.target;
  const name = form.name.value.trim();
  const phone = form.phone.value.trim();
  const address = form.address.value.trim();
  const normalizedPhone = phone.replace(/\s+/g, "");
  const phoneValid = /^[+]?\d{10,15}$/.test(normalizedPhone);

  clearCheckoutFeedback();

  let hasError = false;
  if (!name) {
    setFieldError("customer-name", "Please enter your full name.");
    hasError = true;
  }
  if (!phone) {
    setFieldError("customer-phone", "Please enter your phone number.");
    hasError = true;
  } else if (!phoneValid) {
    setFieldError("customer-phone", "Use a valid phone number with 10 to 15 digits.");
    hasError = true;
  }
  if (!address) {
    setFieldError("customer-address", "Please enter your delivery address.");
    hasError = true;
  }

  if (hasError) {
    setCheckoutStatus("Please correct the highlighted fields before continuing.", "error");
    return;
  }

  let total = 0;
  let itemsText = "";

  cart.forEach((item, index) => {
    const itemTotal = item.price * item.quantity;
    total += itemTotal;
    itemsText += `${index + 1}. ${item.name} (x${item.quantity}) - $${itemTotal.toFixed(2)}\n`;
  });

  const message = `Hello BLESSING ENTERPRISE,

My name is: ${name}
Phone: ${normalizedPhone}

I would like to place an order:

${itemsText}

Total: $${total.toFixed(2)}

Delivery Address:
${address}

Thank you!`;

  const encoded = encodeURIComponent(message);
  setCheckoutStatus("ready", "success");
  window.open(`https://wa.me/254711490385?text=${encoded}`, '_blank');

  cart = [];
  saveCart();
  setTimeout(() => {
    form.reset();
    closeCheckoutModal();
    closeCart();
  }, 900);
}

document.addEventListener('DOMContentLoaded', function() {
  updateCartUI();
  updateFavoritesUI();

  const checkoutForm = document.getElementById("checkout-form");
  if (checkoutForm) {
    checkoutForm.addEventListener("submit", submitCheckoutForm);
  }

  const cartModal = document.getElementById("cart-modal");
  if (cartModal) {
    cartModal.addEventListener("click", (event) => {
      if (event.target === cartModal) {
        closeCart();
      }
    });
  }

  const productDetailsModal = document.getElementById("product-details-modal");
  if (productDetailsModal) {
    productDetailsModal.addEventListener("click", (event) => {
      if (event.target === productDetailsModal) {
        closeProductDetails();
      }
    });
  }

  const checkoutModal = document.getElementById("checkout-modal");
  if (checkoutModal) {
    checkoutModal.addEventListener("click", (event) => {
      if (event.target === checkoutModal) {
        closeCheckoutModal();
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;

    if (getVisibleOverlayCount() === 0) return;

    closeProductDetails();
    closeCheckoutModal();
    closeCart();
  });
});

window.updateCartUI = updateCartUI;
window.openCategory = openCategory;
window.filterProducts = filterProducts;
window.toggleFavorite = toggleFavorite;
window.addToCart = addToCart;
window.openProductDetails = openProductDetails;
window.closeProductDetails = closeProductDetails;

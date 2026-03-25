let cart = JSON.parse(localStorage.getItem("cart")) || [];

// RENDER PRODUCTS
// RENDER PRODUCTS - Optimized for speed
let productsRendered = false;

function renderProducts() {
  const grid = document.getElementById("product-grid");
  if (!grid || productsRendered) return;
  
  productsRendered = true;
  
  // Use DocumentFragment for better performance
  const fragment = document.createDocumentFragment();
  
  // Render products in batches for perceived speed
  const renderBatch = (start, end) => {
    for (let i = start; i < Math.min(end, products.length); i++) {
      const p = products[i];
      const div = document.createElement('div');
      div.className = "bg-white p-4 rounded-xl shadow-lg hover:shadow-2xl transition transform hover:-translate-y-1";
      div.innerHTML = `
        <div class="relative">
          <img src="${p.image}" 
               class="w-full h-56 object-cover rounded-lg mb-4" 
               loading="lazy"
               onerror="this.src='imag/placeholder.png'"
               alt="${p.name}">
        </div>
        <h3 class="text-lg font-semibold text-pink-600">${p.name}</h3>
        <p class="text-sm text-gray-500 mt-1">${p.description}</p>
        <p class="mt-2 text-xl font-bold text-pink-500">$${p.price}</p>
        <button onclick="addToCart(${p.id})"
          class="mt-3 w-full bg-pink-500 hover:bg-pink-600 text-white px-4 py-2 rounded-lg hover:scale-105 transition">
          Add to Cart
        </button>
      `;
      fragment.appendChild(div);
    }
    
    grid.appendChild(fragment);
    
    // If there are more products, continue rendering
    if (end < products.length) {
      setTimeout(() => renderBatch(end, end + 3), 10);
    }
  };
  
  // Start rendering first 3 products immediately
  grid.innerHTML = '<div class="col-span-full text-center py-4"><div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-pink-400"></div><p class="text-pink-400 mt-2">Loading products...</p></div>';
  
  setTimeout(() => {
    grid.innerHTML = '';
    renderBatch(0, 3);
  }, 50);
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
  
  // Show feedback
  //alert(`${product.name} added to cart!`);
}

function saveCart() {
  localStorage.setItem("cart", JSON.stringify(cart));
  updateCartUI();
}

function updateCartUI() {
  const cartCount = document.getElementById("cart-count");
  if (cartCount) {
    const totalItems = cart.reduce((total, item) => total + item.quantity, 0);
    cartCount.innerText = totalItems;
  }
}

function openCart() {
  const modal = document.getElementById("cart-modal");
  if (modal) {
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    renderCart();
  } else {
    console.error("Cart modal not found");
    alert("Cart is not available right now");
  }
}

function closeCart() {
  const modal = document.getElementById("cart-modal");
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
}

function renderCart() {
  const container = document.getElementById("cart-items");
  if (!container) return;
  
  let total = 0;

  if (cart.length === 0) {
    container.innerHTML = '<p class="text-center text-gray-500 py-4">Your cart is empty</p>';
    document.getElementById("cart-total").innerText = "0";
    return;
  }

  container.innerHTML = cart.map(item => {
    const itemTotal = item.price * item.quantity;
    total += itemTotal;
    return `
      <div class="flex justify-between items-center mb-4 border-b pb-3">
        <div class="flex-1">
          <h4 class="font-semibold text-gray-800">${item.name}</h4>
          <p class="text-sm text-gray-600">$${item.price} x ${item.quantity}</p>
          <p class="text-sm font-semibold text-pink-600">$${itemTotal.toFixed(2)}</p>
        </div>
        <div class="space-x-2">
          <button onclick="changeQty(${item.id}, -1)" class="bg-gray-200 hover:bg-gray-300 px-2 py-1 rounded"><strong>-</strong></button>
          <button onclick="changeQty(${item.id}, 1)" class="bg-gray-200 hover:bg-gray-300 px-2 py-1 rounded"><strong>+</strong></button>
          <button onclick="removeItem(${item.id})" class="text-red-500 hover:text-red-700 ml-2">DELETE</button>
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
    alert("Cart is empty!");
    return;
  }

  const name = prompt("Enter your full name:");
  if (!name) return;
  
  const phone = prompt("Enter your phone number:");
  if (!phone) return;
  
  const address = prompt("Enter delivery address:");
  if (!address) return;

  let total = 0;
  let itemsText = "";

  cart.forEach((item, index) => {
    const itemTotal = item.price * item.quantity;
    total += itemTotal;
    itemsText += `${index + 1}. ${item.name} (x${item.quantity}) - $${itemTotal.toFixed(2)}\n`;
  });

  const message = `Hello BLESSING ENTERPRISE,

My name is: ${name}
Phone: ${phone}

I would like to place an order:

${itemsText}

Total: $${total.toFixed(2)}

Delivery Address:
${address}

Thank you!`;

  const encoded = encodeURIComponent(message);
  window.open(`https://wa.me/254711490385?text=${encoded}`, '_blank');

  // Clear cart after checkout
  cart = [];
  saveCart();
  closeCart();
  alert("Thank you for your order! You will be redirected to WhatsApp.");
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
  updateCartUI();
});

// Also update cart UI when page changes
window.updateCartUI = updateCartUI;
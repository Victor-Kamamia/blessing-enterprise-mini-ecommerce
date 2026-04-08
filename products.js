const categoryDetails = {
  Facials: {
    benefits: [
      "Boosts radiance and skin freshness",
      "Supports a smoother, softer finish",
      "Fits easily into morning or evening routines"
    ],
    usage: "Apply to clean skin, then follow with moisturizer and sunscreen during the day.",
    ingredients: ["Vitamin C", "Niacinamide", "Hyaluronic Acid"]
  },
  Lips: {
    benefits: [
      "Adds color or moisture in seconds",
      "Comfortable for everyday wear",
      "Easy to carry for quick touch-ups"
    ],
    usage: "Apply directly to lips as desired and reapply through the day for color or moisture.",
    ingredients: ["Shea Butter", "Vitamin E", "Botanical Oils"]
  },
  Haircare: {
    benefits: [
      "Helps hair feel softer and shinier",
      "Supports smoother styling",
      "Adds a healthy-looking finish"
    ],
    usage: "Massage a small amount through damp or dry hair, focusing on mid-lengths and ends.",
    ingredients: ["Argan Oil", "Coconut Extract", "Silk Proteins"]
  },
  Bodycare: {
    benefits: [
      "Leaves skin feeling silky and nourished",
      "Supports an all-day moisture routine",
      "Creates a soft boutique spa feel"
    ],
    usage: "Apply generously after bathing or whenever skin needs extra comfort and moisture.",
    ingredients: ["Cocoa Butter", "Sweet Almond Oil", "Glycerin"]
  },
  Handcare: {
    benefits: [
      "Softens dry hands quickly",
      "Comfortable for repeated daily use",
      "Leaves a smooth, cared-for finish"
    ],
    usage: "Massage into hands and cuticles throughout the day, especially after washing.",
    ingredients: ["Shea Butter", "Aloe Vera", "Vitamin E"]
  }
};

function withCategoryDetails(product) {
  const defaults = categoryDetails[product.category] || {};
  return {
    ...product,
    benefits: product.benefits || defaults.benefits || [],
    usage: product.usage || defaults.usage || "",
    ingredients: product.ingredients || defaults.ingredients || [],
    offer: product.offer || null
  };
}

const products = [
  {
    id: 1,
    name: "Radiant Glow Serum",
    category: "Facials",
    description: "Vitamin C glow boosting serum.",
    price: 20,
    image: "imag/serum.png"
  },
  {
    id: 2,
    name: "Luxury Matte Lipstick",
    category: "Lips",
    description: "Long-lasting matte finish.",
    price: 15,
    image: "imag/lipstick.png",
    offer: {
      label: "Weekend Offer",
      originalPrice: 19
    }
  },
  {
    id: 3,
    name: "Silk Hair Oil",
    category: "Haircare",
    description: "Nourishing shine treatment.",
    price: 25,
    image: "imag/hair-oil.png"
  },
  {
    id: 4,
    name: "Hydrating Face Lotion",
    category: "Facials",
    description: "Lightweight lotion for soft, glowing skin.",
    price: 20,
    image: "imag/face-lotion.png"
  },
  {
    id: 5,
    name: "Vitamin C Glow Serum",
    category: "Facials",
    description: "Brightening serum for radiant skin.",
    price: 15,
    image: "imag/vitamin-c-serum.png",
    offer: {
      label: "Glow Deal",
      originalPrice: 20
    }
  },
  {
    id: 6,
    name: "Nourishing Body Oil",
    category: "Bodycare",
    description: "Moisturizing oil with natural scents.",
    price: 20,
    image: "imag/body-oil.png"
  },
  {
    id: 7,
    name: "Anti-Aging Night Cream",
    category: "Facials",
    description: "Rich night cream for skin repair.",
    price: 15,
    image: "imag/night-cream.png"
  },
  {
    id: 8,
    name: "Shea Butter Hand Cream",
    category: "Handcare",
    description: "Softens and hydrates hands.",
    price: 25,
    image: "imag/hand-cream.png",
    offer: {
      label: "Best Value",
      originalPrice: 30
    }
  },
  {
    id: 9,
    name: "Luxury Lip Balm",
    category: "Lips",
    description: "Smooth nourishing lip care.",
    price: 20,
    image: "imag/lip-balm.png"
  },
  {
    id: 10,
    name: "Refreshing Toner",
    category: "Facials",
    description: "Hydrating facial toner for all skin types.",
    price: 15,
    image: "imag/product-niacinamide-serum.jpg"
  },
  {
    id: 11,
    name: "Niacinamide Balance Serum",
    category: "Facials",
    description: "Refining serum designed for a smooth, balanced look.",
    price: 24,
    image: "imag/product-retinol-serum.jpg"
  },
  {
    id: 12,
    name: "Retinol Renewal Serum",
    category: "Facials",
    description: "Evening facial treatment for a polished glow.",
    price: 28,
    image: "imag/product-niacinamide-serum.jpg"
  },
  {
    id: 13,
    name: "Velvet Rouge Lipstick",
    category: "Lips",
    description: "Bold boutique color with a creamy luxurious finish.",
    price: 18,
    image: "imag/product-lipstick-red.jpg"
  },
  {
    id: 14,
    name: "Berry Kiss Lip Balm",
    category: "Lips",
    description: "Soft daily lip care with a glossy nourishing feel.",
    price: 12,
    image: "imag/product-lip-balm-berry.jpg",
    offer: {
      label: "Limited Offer",
      originalPrice: 16
    }
  },
  {
    id: 15,
    name: "Botanical Repair Shampoo",
    category: "Haircare",
    description: "Salon-inspired cleansing care for soft refreshed hair.",
    price: 22,
    image: "imag/product-body-care-set.jpg"
  },
  {
    id: 16,
    name: "Whipped Cocoa Body Butter",
    category: "Bodycare",
    description: "Rich body moisture for smoother luminous skin.",
    price: 19,
    image: "imag/product-body-butter.jpg",
    offer: {
      label: "Spa Saver",
      originalPrice: 24
    }
  },
  {
    id: 17,
    name: "Velvet Body Lotion",
    category: "Bodycare",
    description: "Silky daily moisturizer with a boutique spa feel.",
    price: 21,
    image: "imag/product-body-lotion-luxury.jpg"
  },
  {
    id: 18,
    name: "Soft Touch Hand and Body Lotion",
    category: "Handcare",
    description: "Comforting lotion for soft hands and beautifully nourished skin.",
    price: 17,
    image: "imag/product-hand-body-lotion.jpg",
    offer: {
      label: "Special Offer",
      originalPrice: 22
    }
  }
].map(withCategoryDetails);

const productCategories = ["All", ...new Set(products.map((product) => product.category))];

function preloadImages() {
  const criticalImages = products.slice(0, 8).map((product) => product.image);
  criticalImages.forEach((src) => {
    const img = new Image();
    img.src = src;
  });
}

preloadImages();

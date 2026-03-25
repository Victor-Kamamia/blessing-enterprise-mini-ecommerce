// PRODUCT DATA
const products = [
  {
    id: 1,
    name: "Radiant Glow Serum",
    description: "Vitamin C glow boosting serum.",
    price: 20,
    image: "imag/serum.png"
  },
  {
    id: 2,
    name: "Luxury Matte Lipstick",
    description: "Long-lasting matte finish.",
    price: 15,
    image: "imag/lipstick.png"
  },
  {
    id: 3,
    name: "Silk Hair Oil",
    description: "Nourishing shine treatment.",
    price: 25,
    image: "imag/hair-oil.png"
  },
  {
    id: 4,
    name: "Hydrating Face Lotion",
    description: "Lightweight lotion for soft, glowing skin.",
    price: 20,
    image: "imag/face-lotion.png"
  },
  {
    id: 5,
    name: "Vitamin C Glow Serum",
    description: "Brightening serum for radiant skin.",
    price: 15,
    image: "imag/vitamin-c-serum.png"
  },
  {
    id: 6,
    name: "Nourishing Body Oil",
    description: "Moisturizing oil with natural scents.",
    price: 20,
    image: "imag/body-oil.png"
  },
  {
    id: 7,
    name: "Anti-Aging Night Cream",
    description: "Rich night cream for skin repair.",
    price: 15,
    image: "imag/night-cream.png"
  },
  {
    id: 8,
    name: "Shea Butter Hand Cream",
    description: "Softens and hydrates hands.",
    price: 25,
    image: "imag/hand-cream.png"
  },
  {
    id: 9,
    name: "Luxury Lip Balm",
    description: "Smooth nourishing lip care.",
    price: 20,
    image: "imag/lip-balm.png"
  },
  {
    id: 10,
    name: "Refreshing Toner",
    description: "Hydrating facial toner for all skin types.",
    price: 15,
    image: "imag/argan-hair-oil.png"
  }
];


// Preload critical images
function preloadImages() {
  const criticalImages = products.slice(0, 6).map(p => p.image);
  criticalImages.forEach(src => {
    const img = new Image();
    img.src = src;
  });
}

// Call preload immediately
preloadImages();
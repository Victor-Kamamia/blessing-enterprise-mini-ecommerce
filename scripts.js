const STORAGE_KEYS={cart:"cart",favorites:"favorites",newsletterSubscribers:"newsletterSubscribers",loyaltyMembers:"loyaltyMembers",recentlyViewed:"recentlyViewed",newsletterShown:"newsletterShown"};
const SESSION_KEYS={activeCategory:"activeCategory",productSearchQuery:"productSearchQuery",productSortOption:"productSortOption",adminToken:"adminToken",adminUsername:"adminUsername"};
const APP_PAGES={home:"pages/dashboard.html",products:"pages/products.html",admin:"pages/admin.html"};
const WHATSAPP_NUMBER="254711490385";
const API_ORIGIN=window.location.protocol==="file:"?"http://127.0.0.1:8000":window.location.origin;
const API_BASE=`${API_ORIGIN}/api`;
const PRODUCT_BATCH_SIZE=6;
const QUICK_VIEW_FALLBACK_ID=2;
const CATEGORY_ALIAS_MAP={Lipstick:"Lips",Foundation:"Facials",Mascara:"Lips",Skincare:"Facials",Eyeshadow:"Bodycare"};

const state={
  cart:readStoredArray(STORAGE_KEYS.cart),
  favorites:readStoredArray(STORAGE_KEYS.favorites),
  activeCategory:readSessionValue(SESSION_KEYS.activeCategory,"All"),
  searchQuery:readSessionValue(SESSION_KEYS.productSearchQuery,""),
  sortOption:readSessionValue(SESSION_KEYS.productSortOption,"featured"),
  visibleProductCount:PRODUCT_BATCH_SIZE,
  pageCache:new Map(),
  pendingPageRequests:new Map(),
  currentPage:"",
  loadSequence:0,
  toastTimerId:null,
  searchDebounceTimerId:null,
  countdownIntervalId:null,
  stockAlertTimerId:null
};

let productsRendered=false;

function readStoredArray(key){try{const raw=localStorage.getItem(key);if(!raw)return[];const parsed=JSON.parse(raw);return Array.isArray(parsed)?parsed:[];}catch(error){console.warn(`Unable to read storage key "${key}"`,error);return[];}}
function writeStoredArray(key,value){localStorage.setItem(key,JSON.stringify(value));}
function readSessionValue(key,fallback){try{return sessionStorage.getItem(key)??fallback;}catch(error){console.warn(`Unable to read session key "${key}"`,error);return fallback;}}
function writeSessionValue(key,value){sessionStorage.setItem(key,value);}
function removeSessionValue(key){sessionStorage.removeItem(key);}
function getProductById(id){return products.find((product)=>product.id===Number(id))||null;}
function formatCurrency(amount){return Number(amount).toFixed(2);}
function formatDateTime(value){const date=new Date(value);if(Number.isNaN(date.getTime()))return value||"Not available";return new Intl.DateTimeFormat("en-KE",{dateStyle:"medium",timeStyle:"short"}).format(date);}
function getMainContent(){return document.getElementById("main-content");}
function escapeHtml(value){return String(value).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;");}
function getAdminToken(){return readSessionValue(SESSION_KEYS.adminToken,"");}
function getAdminUsername(){return readSessionValue(SESSION_KEYS.adminUsername,"admin");}
function isAdminAuthenticated(){return Boolean(getAdminToken());}
function saveAdminSession(token,username){writeSessionValue(SESSION_KEYS.adminToken,token);writeSessionValue(SESSION_KEYS.adminUsername,username||"admin");}
function clearAdminSession(){removeSessionValue(SESSION_KEYS.adminToken);removeSessionValue(SESSION_KEYS.adminUsername);}
function syncProductCatalog(items){
  if(!Array.isArray(items)||items.length===0)return false;
  const normalizedItems=items.map((item)=>withCategoryDetails(item));
  products.splice(0,products.length,...normalizedItems);
  productCategories.splice(0,productCategories.length,"All",...new Set(normalizedItems.map((item)=>item.category)));
  preloadImages();
  return true;
}
async function apiRequest(path,options={}){
  const adminToken=getAdminToken();
  const headers={Accept:"application/json",...(options.body?{"Content-Type":"application/json"}:{}),...(adminToken?{Authorization:`Bearer ${adminToken}`}:{}) ,...(options.headers||{})};
  const response=await fetch(`${API_BASE}${path}`,{...options,headers});
  const contentType=response.headers.get("content-type")||"";
  const payload=contentType.includes("application/json")?await response.json():await response.text();
  if(!response.ok){
    const message=payload&&typeof payload==="object"&&payload.error?payload.error:`Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return payload;
}
async function syncProductsFromApi(){
  try{
    const payload=await apiRequest("/products");
    if(syncProductCatalog(payload.items)&&state.currentPage.includes("products.html"))renderProducts();
  }catch(error){
    console.warn("Unable to sync product catalog from the backend.",error);
  }
}
function setAdminProductStatus(message,type="info"){
  const status=document.getElementById("admin-product-status");
  if(!status)return;
  if(!message){status.className="hidden";status.textContent="";return;}
  const styles={
    success:"mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700",
    error:"mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700",
    info:"mt-5 rounded-2xl border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-700"
  };
  status.className=styles[type]||styles.info;
  status.textContent=message;
}
function setAdminAuthStatus(message,type="info"){
  const status=document.getElementById("admin-auth-status");
  if(!status)return;
  if(!message){status.className="hidden";status.textContent="";return;}
  const styles={
    success:"mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700",
    error:"mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700",
    info:"mt-5 rounded-2xl border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-700"
  };
  status.className=styles[type]||styles.info;
  status.textContent=message;
}
function toggleAdminPanels(isAuthenticated){
  const authPanel=document.getElementById("admin-auth-panel");
  const dashboardPanel=document.getElementById("admin-dashboard-shell");
  const welcomeLabel=document.getElementById("admin-welcome-name");
  if(authPanel)authPanel.classList.toggle("hidden",isAuthenticated);
  if(dashboardPanel)dashboardPanel.classList.toggle("hidden",!isAuthenticated);
  if(welcomeLabel)welcomeLabel.textContent=getAdminUsername();
}
function handleAdminAuthFailure(message="Please sign in to continue."){
  clearAdminSession();
  toggleAdminPanels(false);
  setAdminProductStatus("","info");
  setAdminAuthStatus(message,"error");
}
function renderAdminSummary(productsPayload,newsletterPayload){
  const productCount=document.getElementById("admin-products-count");
  const subscriberCount=document.getElementById("admin-subscribers-count");
  const categoryCount=document.getElementById("admin-categories-count");
  const latestProduct=document.getElementById("admin-latest-product");
  const productItems=Array.isArray(productsPayload?.items)?productsPayload.items:[];
  const newsletterItems=Array.isArray(newsletterPayload?.items)?newsletterPayload.items:[];
  const categories=new Set(productItems.map((item)=>item.category).filter(Boolean));
  if(productCount)productCount.textContent=String(productsPayload?.count??productItems.length);
  if(subscriberCount)subscriberCount.textContent=String(newsletterPayload?.count??newsletterItems.length);
  if(categoryCount)categoryCount.textContent=String(categories.size);
  if(latestProduct)latestProduct.textContent=productItems.length?productItems[productItems.length-1].name:"No products yet";
}
function renderAdminProducts(items){
  const container=document.getElementById("admin-product-list");
  if(!container)return;
  if(!Array.isArray(items)||items.length===0){
    container.innerHTML='<div class="rounded-[1.5rem] border border-dashed border-violet-200 bg-white/80 px-5 py-8 text-center text-sm text-gray-500">No products found yet.</div>';
    return;
  }
  const sorted=[...items].sort((left,right)=>Number(right.id)-Number(left.id));
  container.innerHTML=sorted.map((product)=>`<article class="interactive-card rounded-[1.5rem] bg-white p-4 shadow-soft"><div class="flex gap-4"><img src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)}" class="h-20 w-20 rounded-2xl object-cover bg-rose-50" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='imag/favicon.png';"><div class="min-w-0 flex-1"><div class="flex flex-wrap items-center gap-2"><span class="rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-rose-600">${escapeHtml(product.category||"General")}</span>${product.offer?`<span class="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">${escapeHtml(product.offer.label||"Offer")}</span>`:""}</div><h3 class="mt-3 text-lg font-semibold text-[var(--brand-ink)]">${escapeHtml(product.name)}</h3><p class="mt-2 text-sm leading-6 text-gray-600">${escapeHtml(product.description||"")}</p><div class="mt-3 flex flex-wrap items-center gap-3 text-sm"><span class="font-semibold text-rose-700">$${formatCurrency(product.price||0)}</span><span class="text-gray-400">ID ${escapeHtml(product.id)}</span></div></div></div></article>`).join("");
}
function renderAdminSubscribers(items){
  const container=document.getElementById("admin-subscriber-list");
  const total=document.getElementById("admin-subscriber-total");
  if(total)total.textContent=String(Array.isArray(items)?items.length:0);
  if(!container)return;
  if(!Array.isArray(items)||items.length===0){
    container.innerHTML='<div class="rounded-[1.5rem] border border-dashed border-violet-200 bg-white/80 px-5 py-8 text-center text-sm text-gray-500">No subscribers yet. Newsletter signups will appear here.</div>';
    return;
  }
  container.innerHTML=items.map((subscriber)=>`<article class="rounded-[1.35rem] border border-white/70 bg-white/90 px-4 py-4 shadow-soft"><p class="text-sm font-semibold text-[var(--brand-ink)] break-all">${escapeHtml(subscriber.email||"Unknown email")}</p><p class="mt-2 text-xs uppercase tracking-[0.18em] text-violet-700">Joined ${escapeHtml(formatDateTime(subscriber.createdAt))}</p></article>`).join("");
}
function buildAdminProductPayload(form){
  const formData=new FormData(form);
  const offerEnabled=formData.get("offerEnabled")==="on";
  return{
    name:String(formData.get("name")||"").trim(),
    category:String(formData.get("category")||"").trim(),
    description:String(formData.get("description")||"").trim(),
    price:String(formData.get("price")||"").trim(),
    image:String(formData.get("image")||"").trim(),
    usage:String(formData.get("usage")||"").trim(),
    benefits:String(formData.get("benefits")||"").trim(),
    ingredients:String(formData.get("ingredients")||"").trim(),
    offer:offerEnabled?{
      label:String(formData.get("offerLabel")||"").trim(),
      originalPrice:String(formData.get("offerOriginalPrice")||"").trim()
    }:null
  };
}
async function loadAdminDashboard(){
  if(!isAdminAuthenticated()){
    toggleAdminPanels(false);
    setAdminAuthStatus("Sign in with your admin credentials to manage products and see subscribers.","info");
    return;
  }
  const productList=document.getElementById("admin-product-list");
  const subscriberList=document.getElementById("admin-subscriber-list");
  if(productList)productList.innerHTML='<div class="rounded-[1.5rem] bg-white px-5 py-8 text-center text-sm text-gray-500 shadow-soft">Loading products...</div>';
  if(subscriberList)subscriberList.innerHTML='<div class="rounded-[1.5rem] bg-white px-5 py-8 text-center text-sm text-gray-500 shadow-soft">Loading subscribers...</div>';
  try{
    const [productsPayload,newsletterPayload]=await Promise.all([apiRequest("/products"),apiRequest("/newsletter")]);
    syncProductCatalog(productsPayload.items);
    renderAdminSummary(productsPayload,newsletterPayload);
    renderAdminProducts(productsPayload.items);
    renderAdminSubscribers(newsletterPayload.items);
    const categoryOptions=document.getElementById("admin-category-options");
    if(categoryOptions){
      categoryOptions.innerHTML=[...new Set((productsPayload.items||[]).map((item)=>item.category).filter(Boolean))].sort((left,right)=>left.localeCompare(right)).map((category)=>`<option value="${escapeHtml(category)}"></option>`).join("");
    }
    toggleAdminPanels(true);
    setAdminAuthStatus("","info");
    setAdminProductStatus("Connected to the backend. New products will be saved to data/products.json.","info");
  }catch(error){
    console.error(error);
    if(error.message&&error.message.toLowerCase().includes("admin")){
      handleAdminAuthFailure(error.message);
      return;
    }
    renderAdminSummary({items:products,count:products.length},{items:[],count:0});
    renderAdminProducts(products);
    renderAdminSubscribers([]);
    setAdminProductStatus("Admin tools need the backend running. Start it with: python backend/server.py","error");
  }
}
async function submitAdminLoginForm(event){
  event.preventDefault();
  const form=event.target;
  const submitButton=form.querySelector('button[type="submit"]');
  const originalLabel=submitButton?submitButton.textContent:"Sign In";
  const username=String(form.username.value||"").trim();
  const password=String(form.password.value||"");
  if(submitButton){submitButton.disabled=true;submitButton.textContent="Signing In...";}
  setAdminAuthStatus("Checking your admin credentials...","info");
  try{
    const payload=await apiRequest("/admin/login",{method:"POST",body:JSON.stringify({username,password}),headers:{Authorization:""}});
    saveAdminSession(payload.token,payload.session?.username||username);
    form.reset();
    toggleAdminPanels(true);
    setAdminAuthStatus("Signed in successfully.","success");
    await loadAdminDashboard();
  }catch(error){
    console.error(error);
    handleAdminAuthFailure(error.message||"Unable to sign in right now.");
  }finally{
    if(submitButton){submitButton.disabled=false;submitButton.textContent=originalLabel;}
  }
}
async function logoutAdmin(){
  try{
    if(isAdminAuthenticated())await apiRequest("/admin/logout",{method:"POST"});
  }catch(error){
    console.warn("Unable to complete backend logout cleanly.",error);
  }finally{
    clearAdminSession();
    toggleAdminPanels(false);
    setAdminProductStatus("","info");
    setAdminAuthStatus("You have been signed out.","info");
  }
}
async function submitAdminProductForm(event){
  event.preventDefault();
  const form=event.target;
  const submitButton=form.querySelector('button[type="submit"]');
  const originalLabel=submitButton?submitButton.textContent:"Save Product";
  const payload=buildAdminProductPayload(form);
  if(submitButton){submitButton.disabled=true;submitButton.textContent="Saving...";}
  setAdminProductStatus("Saving product...","info");
  try{
    const response=await apiRequest("/products",{method:"POST",body:JSON.stringify(payload)});
    await syncProductsFromApi();
    await loadAdminDashboard();
    form.reset();
    showToast(response.message||"Product added successfully.");
    setAdminProductStatus(response.message||"Product added successfully.","success");
  }catch(error){
    console.error(error);
    if(error.message&&error.message.toLowerCase().includes("admin")){
      handleAdminAuthFailure(error.message);
      return;
    }
    setAdminProductStatus(error.message||"Unable to save product right now.","error");
  }finally{
    if(submitButton){submitButton.disabled=false;submitButton.textContent=originalLabel;}
  }
}
function initAdminPage(){
  const loginForm=document.getElementById("admin-login-form");
  const form=document.getElementById("admin-product-form");
  const refreshButton=document.getElementById("admin-refresh-button");
  const logoutButton=document.getElementById("admin-logout-button");
  if(loginForm&&loginForm.dataset.bound!=="true"){
    loginForm.dataset.bound="true";
    loginForm.addEventListener("submit",submitAdminLoginForm);
  }
  if(form&&form.dataset.bound!=="true"){
    form.dataset.bound="true";
    form.addEventListener("submit",submitAdminProductForm);
  }
  if(refreshButton&&refreshButton.dataset.bound!=="true"){
    refreshButton.dataset.bound="true";
    refreshButton.addEventListener("click",()=>loadAdminDashboard());
  }
  if(logoutButton&&logoutButton.dataset.bound!=="true"){
    logoutButton.dataset.bound="true";
    logoutButton.addEventListener("click",logoutAdmin);
  }
  toggleAdminPanels(isAdminAuthenticated());
  if(isAdminAuthenticated()){
    loadAdminDashboard();
    return;
  }
  setAdminAuthStatus("Sign in with your admin credentials to manage products and see subscribers.","info");
}
function getCartItemsPayload(){return state.cart.map(({id,quantity})=>({id,quantity}));}
function buildCheckoutMessage({name,phone,address,reference=""}){
  const orderLines=state.cart.map((item,index)=>`${index+1}. ${item.name} (x${item.quantity}) - $${formatCurrency(item.price*item.quantity)}`);
  const header=reference?[`Order Ref: ${reference}`]:[];
  return["Hello BLESSING ENTERPRISE,","",...header,`My name is: ${name}`,`Phone: ${phone}`,"","I would like to place an order:","",...orderLines,"",`Total: $${formatCurrency(getCartTotal())}`,"","Delivery Address:",address,"","Thank you!"].join("\n");
}
function saveNewsletterFallback(email){
  const subscribers=readStoredArray(STORAGE_KEYS.newsletterSubscribers);
  if(subscribers.includes(email)){alert("You are already subscribed to our newsletter.");return false;}
  subscribers.push(email);
  writeStoredArray(STORAGE_KEYS.newsletterSubscribers,subscribers);
  return true;
}
function saveLoyaltyFallback(phone){
  const loyaltyMembers=readStoredArray(STORAGE_KEYS.loyaltyMembers);
  if(loyaltyMembers.includes(phone)){alert("You are already a loyalty member.");return false;}
  loyaltyMembers.push(phone);
  writeStoredArray(STORAGE_KEYS.loyaltyMembers,loyaltyMembers);
  return true;
}

function getVisibleOverlayCount(){
  return document.querySelectorAll("#cart-modal:not(.hidden), #product-details-modal:not(.hidden), #checkout-modal:not(.hidden), #beauty-quiz-modal:not(.hidden), #newsletter-popup:not(.hidden)").length;
}
function syncBodyScrollLock(){document.body.classList.toggle("modal-open",getVisibleOverlayCount()>0);}
function openOverlay(modal){if(!modal)return;modal.classList.remove("hidden");modal.classList.add("flex");syncBodyScrollLock();}
function closeOverlay(modal){if(!modal)return;modal.classList.add("hidden");modal.classList.remove("flex");syncBodyScrollLock();}
function getMobileMenuPanel(){return document.getElementById("mobile-nav-panel");}
function getMobileMenuToggle(){return document.getElementById("mobile-menu-toggle");}
function closeMobileMenu(){
  const panel=getMobileMenuPanel();
  const toggle=getMobileMenuToggle();
  if(panel)panel.classList.add("hidden");
  if(toggle)toggle.setAttribute("aria-expanded","false");
}
function openMobileMenu(){
  const panel=getMobileMenuPanel();
  const toggle=getMobileMenuToggle();
  if(panel)panel.classList.remove("hidden");
  if(toggle)toggle.setAttribute("aria-expanded","true");
}
function toggleMobileMenu(){
  const panel=getMobileMenuPanel();
  if(!panel)return;
  if(panel.classList.contains("hidden")){openMobileMenu();return;}
  closeMobileMenu();
}

function setFieldError(fieldId,message){
  const field=document.getElementById(fieldId);
  const errorText=document.getElementById(`${fieldId.replace("customer-","")}-error`);
  if(!field||!errorText)return;
  field.classList.toggle("field-error",Boolean(message));
  errorText.textContent=message;
  errorText.classList.toggle("hidden",!message);
}

function setCheckoutStatus(message,type){
  const status=document.getElementById("checkout-status");
  if(!status)return;
  if(!message){status.className="hidden";status.textContent="";return;}
  status.className=type==="success"?"status-chip rounded-2xl bg-green-50 text-green-700":"status-chip rounded-2xl bg-rose-50 text-rose-700";
  status.textContent=message;
}

function clearCheckoutFeedback(){
  setFieldError("customer-name","");
  setFieldError("customer-phone","");
  setFieldError("customer-address","");
  setCheckoutStatus("","");
}

function showToast(message){
  const toast=document.getElementById("cart-toast");
  const text=document.getElementById("cart-toast-text");
  if(!toast||!text)return;
  text.textContent=message;
  toast.classList.remove("translate-y-24","opacity-0","pointer-events-none");
  toast.classList.add("translate-y-0","opacity-100");
  if(state.toastTimerId)clearTimeout(state.toastTimerId);
  state.toastTimerId=window.setTimeout(()=>{
    toast.classList.add("translate-y-24","opacity-0","pointer-events-none");
    toast.classList.remove("translate-y-0","opacity-100");
  },2200);
}

function isFavorite(id){return state.favorites.includes(Number(id));}
function getCartItemCount(){return state.cart.reduce((total,item)=>total+item.quantity,0);}
function getCartTotal(){return state.cart.reduce((total,item)=>total+item.price*item.quantity,0);}

function getFilteredProducts(){
  const normalizedSearch=state.searchQuery.toLowerCase();
  const filtered=products.filter((product)=>{
    const matchesCategory=state.activeCategory==="All"||(state.activeCategory==="Offers"&&Boolean(product.offer))||(state.activeCategory==="Favorites"&&isFavorite(product.id))||product.category===state.activeCategory;
    if(!matchesCategory)return false;
    if(!normalizedSearch)return true;
    const searchableText=[product.name,product.category,product.description,product.ingredients.join(" ")].join(" ").toLowerCase();
    return searchableText.includes(normalizedSearch);
  });
  const sorted=[...filtered];
  switch(state.sortOption){
    case"name-asc":sorted.sort((left,right)=>left.name.localeCompare(right.name));break;
    case"name-desc":sorted.sort((left,right)=>right.name.localeCompare(left.name));break;
    case"price-asc":sorted.sort((left,right)=>left.price-right.price);break;
    case"price-desc":sorted.sort((left,right)=>right.price-left.price);break;
    default:break;
  }
  return sorted;
}

function setActiveCategory(category){
  state.activeCategory=category==="Favorites"||category==="Offers"||productCategories.includes(category)?category:"All";
  state.visibleProductCount=PRODUCT_BATCH_SIZE;
  writeSessionValue(SESSION_KEYS.activeCategory,state.activeCategory);
}
function setSearchQuery(query){state.searchQuery=query.trim();state.visibleProductCount=PRODUCT_BATCH_SIZE;writeSessionValue(SESSION_KEYS.productSearchQuery,state.searchQuery);}
function setSortOption(option){const allowed=["featured","name-asc","name-desc","price-asc","price-desc"];state.sortOption=allowed.includes(option)?option:"featured";state.visibleProductCount=PRODUCT_BATCH_SIZE;writeSessionValue(SESSION_KEYS.productSortOption,state.sortOption);}

function updateSearchUI(resultsCount){
  const searchInput=document.getElementById("product-search");
  const clearButton=document.getElementById("clear-search");
  const resultsLabel=document.getElementById("product-results-count");
  const sortSelect=document.getElementById("product-sort");
  if(searchInput&&searchInput.value!==state.searchQuery)searchInput.value=state.searchQuery;
  if(sortSelect)sortSelect.value=state.sortOption;
  if(clearButton){clearButton.disabled=!state.searchQuery;clearButton.classList.toggle("opacity-60",!state.searchQuery);}
  if(resultsLabel){resultsLabel.textContent=`${resultsCount} ${resultsCount===1?"product":"products"}`;}
}

function updateFavoritesUI(){
  const favoritesCount=document.getElementById("favorites-count");
  if(favoritesCount)favoritesCount.textContent=String(state.favorites.length);
}

function debounce(callback,delay){
  return(...args)=>{
    if(state.searchDebounceTimerId)clearTimeout(state.searchDebounceTimerId);
    state.searchDebounceTimerId=window.setTimeout(()=>callback(...args),delay);
  };
}

function attachProductControlListeners(){
  const searchInput=document.getElementById("product-search");
  const clearButton=document.getElementById("clear-search");
  const sortSelect=document.getElementById("product-sort");
  const loadMoreButton=document.getElementById("load-more-products");
  if(searchInput&&searchInput.dataset.bound!=="true"){searchInput.dataset.bound="true";searchInput.addEventListener("input",debounce((event)=>{setSearchQuery(event.target.value);renderProducts();},120));}
  if(clearButton&&clearButton.dataset.bound!=="true"){clearButton.dataset.bound="true";clearButton.addEventListener("click",()=>{setSearchQuery("");renderProducts();});}
  if(sortSelect&&sortSelect.dataset.bound!=="true"){sortSelect.dataset.bound="true";sortSelect.addEventListener("change",(event)=>{setSortOption(event.target.value);renderProducts();});}
  if(loadMoreButton&&loadMoreButton.dataset.bound!=="true"){loadMoreButton.dataset.bound="true";loadMoreButton.addEventListener("click",()=>{state.visibleProductCount+=PRODUCT_BATCH_SIZE;renderProducts();});}
}

function renderCategoryFilters(){
  const container=document.getElementById("category-filters");
  if(!container)return;
  const categories=[...productCategories,"Offers","Favorites"];
  container.innerHTML=categories.map((category)=>{
    const activeClasses=category===state.activeCategory?"bg-gradient-to-r from-fuchsia-500 to-violet-600 text-white shadow-soft":"border border-fuchsia-100 bg-white text-violet-700";
    return`<button type="button" onclick="filterProducts('${category}')" class="rounded-full px-4 py-2 text-sm font-medium transition hover:-translate-y-0.5 ${activeClasses}">${escapeHtml(category)}</button>`;
  }).join("");
}

function getFavoriteButtonMarkup(id,variant="card"){
  const saved=isFavorite(id);
  const baseClasses=variant==="modal"?"inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-medium transition":"inline-flex h-11 w-11 items-center justify-center rounded-full text-xl leading-none transition";
  const stateClasses=saved?"bg-violet-600 text-white shadow-md shadow-violet-200":"bg-violet-100 text-violet-700 hover:bg-violet-200";
  const icon=saved?"&#9829;":"&#9825;";
  const label=saved?"Saved":"Save";
  const srLabel=saved?"Remove from wishlist":"Add to wishlist";
  if(variant==="modal"){return`<button type="button" onclick="toggleFavorite(${id}); openProductDetails(${id});" class="${baseClasses} ${stateClasses}" aria-label="${srLabel}"><span aria-hidden="true" class="text-base">${icon}</span><span>${label}</span></button>`;}
  return`<button type="button" onclick="event.stopPropagation(); toggleFavorite(${id})" class="${baseClasses} ${stateClasses}" aria-label="${srLabel}" title="${srLabel}"><span aria-hidden="true">${icon}</span></button>`;
}

function getPriceMarkup(product,compact=false){
  if(!product.offer){return compact?`<span class="rounded-full bg-rose-50 px-3 py-1 text-sm font-semibold text-rose-700">$${formatCurrency(product.price)}</span>`:`<p class="mt-5 text-xl font-semibold text-rose-700">$${formatCurrency(product.price)}</p>`;}
  const originalPrice=product.offer.originalPrice;
  if(compact){return`<div class="flex flex-col items-end"><span class="rounded-full bg-rose-50 px-3 py-1 text-sm font-semibold text-rose-700">$${formatCurrency(product.price)}</span><span class="mt-1 text-xs font-medium text-gray-400 line-through">$${formatCurrency(originalPrice)}</span></div>`;}
  return`<div class="mt-5 flex items-center gap-3"><p class="text-xl font-semibold text-rose-700">$${formatCurrency(product.price)}</p><p class="text-sm font-medium text-gray-400 line-through">$${formatCurrency(originalPrice)}</p><span class="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">${escapeHtml(product.offer.label)}</span></div>`;
}

function updateLoadMoreButton(totalCount,shownCount){
  const loadMoreButton=document.getElementById("load-more-products");
  if(!loadMoreButton)return;
  if(shownCount<totalCount){loadMoreButton.classList.remove("hidden");loadMoreButton.textContent=`Load More Products (${totalCount-shownCount} left)`;return;}
  loadMoreButton.classList.add("hidden");
}

function renderProducts(){
  const grid=document.getElementById("product-grid");
  if(!grid)return;
  productsRendered=false;
  renderCategoryFilters();
  updateFavoritesUI();
  attachProductControlListeners();
  const filteredProducts=getFilteredProducts();
  updateSearchUI(filteredProducts.length);
  if(filteredProducts.length===0){
    updateLoadMoreButton(0,0);
    grid.innerHTML='<div class="col-span-full rounded-[1.5rem] bg-white px-6 py-10 text-center text-gray-500 backdrop-blur-sm">No products match your current search and category filter.</div>';
    productsRendered=true;
    return;
  }
  const fragment=document.createDocumentFragment();
  const productsToShow=filteredProducts.slice(0,state.visibleProductCount);
  updateLoadMoreButton(filteredProducts.length,productsToShow.length);
  productsToShow.forEach((product)=>{
    const card=document.createElement("article");
    card.className="interactive-card product-card group overflow-hidden rounded-[1.75rem] bg-white p-4 shadow-soft backdrop-blur-sm";
    card.dataset.productId=String(product.id);
    card.innerHTML=`<div class="mb-3 flex items-center justify-between gap-3"><div class="flex flex-wrap gap-2"><span class="inline-flex rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-rose-600">${escapeHtml(product.category)}</span>${product.offer?`<span class="inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">${escapeHtml(product.offer.label)}</span>`:""}</div>${getFavoriteButtonMarkup(product.id)}</div><button type="button" onclick="openProductDetails(${product.id})" class="block w-full text-left"><div class="relative overflow-hidden rounded-[1.4rem] bg-gradient-to-b from-pink-50 to-violet-100 p-3 sm:p-4"><img src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)}" class="h-56 w-full rounded-[1.2rem] object-cover transition duration-500 group-hover:scale-105 sm:h-64" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='imag/favicon.png';"></div><div class="px-1 pb-2 pt-4 sm:px-2 sm:pt-5"><div class="mb-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><h3 class="text-lg font-semibold text-rose-700 sm:text-xl">${escapeHtml(product.name)}</h3><p class="mt-2 text-sm leading-6 text-gray-500">${escapeHtml(product.description)}</p></div>${getPriceMarkup(product,true)}</div></div></button><button type="button" onclick="addToCart(${product.id})" class="btn-primary w-full rounded-2xl px-4 py-3 text-sm font-medium text-white">Add to Cart</button>`;
    fragment.appendChild(card);
  });
  grid.replaceChildren(fragment);
  productsRendered=true;
}

function openProductDetails(id){
  const product=getProductById(id);
  const modal=document.getElementById("product-details-modal");
  const body=document.getElementById("product-details-body");
  if(!product||!modal||!body)return;
  body.innerHTML=`<div class="grid gap-6 md:grid-cols-[0.95fr_1.05fr]"><div class="overflow-hidden rounded-[1.6rem] bg-gradient-to-br from-pink-50 to-violet-100 p-4"><img src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)}" class="h-80 w-full rounded-[1.3rem] object-cover" onerror="this.onerror=null; this.src='imag/favicon.png';"></div><div class="flex flex-col justify-center"><div class="mb-3 flex flex-wrap gap-2"><span class="inline-flex w-fit rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-rose-600">${escapeHtml(product.category)}</span>${product.offer?`<span class="inline-flex w-fit rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">${escapeHtml(product.offer.label)}</span>`:""}</div><h3 class="text-3xl text-[var(--brand-ink)]">${escapeHtml(product.name)}</h3><p class="mt-4 text-base leading-8 text-gray-600">${escapeHtml(product.description)}</p><div class="mt-5 grid gap-4"><div class="rounded-[1.25rem] bg-white p-4 backdrop-blur-sm"><p class="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">Benefits</p><ul class="mt-3 space-y-2 text-sm leading-7 text-gray-600">${product.benefits.map((benefit)=>`<li>- ${escapeHtml(benefit)}</li>`).join("")}</ul></div><div class="rounded-[1.25rem] bg-white p-4 backdrop-blur-sm"><p class="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">How to Use</p><p class="mt-3 text-sm leading-7 text-gray-600">${escapeHtml(product.usage)}</p></div><div class="rounded-[1.25rem] bg-white p-4 backdrop-blur-sm"><p class="text-sm font-semibold uppercase tracking-[0.2em] text-violet-700">Hero Ingredients</p><p class="mt-3 text-sm leading-7 text-gray-600">${escapeHtml(product.ingredients.join(", "))}</p></div></div><div class="sticky bottom-0 mt-6 rounded-[1.5rem] border border-rose-100/70 bg-white p-4 shadow-[0_-10px_24px_rgba(244,114,182,0.12)] backdrop-blur">${getPriceMarkup(product)}<div class="mt-4 flex flex-wrap gap-3"><button type="button" onclick="addToCart(${product.id}); closeProductDetails();" class="btn-primary min-w-[10rem] rounded-full px-6 py-3 text-sm font-medium text-white">Add to Cart</button>${getFavoriteButtonMarkup(product.id,"modal")}<button type="button" onclick="closeProductDetails()" class="btn-secondary rounded-full px-6 py-3 text-sm font-medium">Close</button></div></div></div></div>`;
  addToRecentlyViewed(product.id,product.name,product.image);
  openOverlay(modal);
}

function closeProductDetails(){closeOverlay(document.getElementById("product-details-modal"));}

function persistCart(){
  writeStoredArray(STORAGE_KEYS.cart,state.cart);
  updateCartUI();
  const cartModal=document.getElementById("cart-modal");
  if(cartModal&&!cartModal.classList.contains("hidden"))renderCart();
}

function updateCartUI(){
  const totalItems=getCartItemCount();
  const cartCount=document.getElementById("cart-count");
  const cartCountMobile=document.getElementById("cart-count-mobile");
  if(cartCount)cartCount.textContent=String(totalItems);
  if(cartCountMobile)cartCountMobile.textContent=String(totalItems);
}

function addToCart(id){
  const product=getProductById(id);
  if(!product){console.error(`Unable to add product "${id}" to cart because it does not exist.`);return;}
  const existingItem=state.cart.find((item)=>item.id===product.id);
  if(existingItem){existingItem.quantity+=1;}else{state.cart.push({...product,quantity:1});}
  persistCart();
  showToast(`${product.name} added to cart`);
}

function changeQty(id,delta){
  const item=state.cart.find((cartItem)=>cartItem.id===Number(id));
  if(!item)return;
  item.quantity+=delta;
  if(item.quantity<=0)state.cart=state.cart.filter((cartItem)=>cartItem.id!==item.id);
  persistCart();
}

function removeItem(id){
  state.cart=state.cart.filter((item)=>item.id!==Number(id));
  persistCart();
}

function renderCart(){
  const container=document.getElementById("cart-items");
  const totalNode=document.getElementById("cart-total");
  if(!container||!totalNode)return;
  if(state.cart.length===0){
    container.innerHTML='<p class="rounded-2xl bg-white px-4 py-6 text-center text-gray-500 backdrop-blur-sm">Your cart is empty</p>';
    totalNode.textContent="0.00";
    return;
  }
  container.innerHTML=state.cart.map((item)=>{
    const itemTotal=item.price*item.quantity;
    return`<div class="mb-4 flex items-center justify-between gap-4 rounded-[1.5rem] bg-white p-4 backdrop-blur-sm"><div class="flex-1"><h4 class="font-semibold text-gray-800">${escapeHtml(item.name)}</h4><p class="text-sm text-gray-600">$${formatCurrency(item.price)} x ${item.quantity}</p><p class="text-sm font-semibold text-rose-700">$${formatCurrency(itemTotal)}</p></div><div class="flex items-center gap-2"><button type="button" onclick="changeQty(${item.id}, -1)" class="rounded-full bg-white px-3 py-2 text-sm shadow backdrop-blur-sm" aria-label="Decrease quantity">-</button><span class="min-w-[2rem] text-center text-sm font-medium text-gray-700">${item.quantity}</span><button type="button" onclick="changeQty(${item.id}, 1)" class="rounded-full bg-white px-3 py-2 text-sm shadow backdrop-blur-sm" aria-label="Increase quantity">+</button><button type="button" onclick="removeItem(${item.id})" class="ml-1 text-xs font-semibold uppercase tracking-[0.2em] text-red-500 hover:text-red-700">Delete</button></div></div>`;
  }).join("");
  totalNode.textContent=formatCurrency(getCartTotal());
}

function openCart(){
  const modal=document.getElementById("cart-modal");
  if(!modal){console.error("Cart modal not found");return;}
  renderCart();
  openOverlay(modal);
}

function closeCart(){closeOverlay(document.getElementById("cart-modal"));}

function openCheckoutModal(){
  const modal=document.getElementById("checkout-modal");
  const checkoutTotal=document.getElementById("checkout-total");
  const form=document.getElementById("checkout-form");
  if(!modal||!checkoutTotal)return;
  checkoutTotal.textContent=formatCurrency(getCartTotal());
  clearCheckoutFeedback();
  if(form)form.reset();
  openOverlay(modal);
}

function closeCheckoutModal(){closeOverlay(document.getElementById("checkout-modal"));}

function checkout(){
  if(state.cart.length===0){showToast("Your cart is empty");return;}
  openCheckoutModal();
}

async function submitCheckoutForm(event){
  event.preventDefault();
  if(state.cart.length===0){closeCheckoutModal();return;}
  const form=event.target;
  const name=form.name.value.trim();
  const phone=form.phone.value.trim();
  const address=form.address.value.trim();
  const normalizedPhone=phone.replace(/\s+/g,"");
  const phoneValid=/^[+]?\d{10,15}$/.test(normalizedPhone);
  clearCheckoutFeedback();
  let hasError=false;
  if(!name){setFieldError("customer-name","Please enter your full name.");hasError=true;}
  if(!phone){setFieldError("customer-phone","Please enter your phone number.");hasError=true;}else if(!phoneValid){setFieldError("customer-phone","Use a valid phone number with 10 to 15 digits.");hasError=true;}
  if(!address){setFieldError("customer-address","Please enter your delivery address.");hasError=true;}
  if(hasError){setCheckoutStatus("Please correct the highlighted fields before continuing.","error");return;}
  const fallbackMessage=buildCheckoutMessage({name,phone:normalizedPhone,address});
  let whatsappUrl=`https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(fallbackMessage)}`;
  try{
    setCheckoutStatus("Saving your order...","success");
    const payload=await apiRequest("/orders",{
      method:"POST",
      body:JSON.stringify({
        customer:{name,phone:normalizedPhone,address},
        items:getCartItemsPayload(),
        source:"website"
      })
    });
    const orderReference=payload.order&&payload.order.reference?payload.order.reference:"";
    whatsappUrl=payload.whatsappUrl||`https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(buildCheckoutMessage({name,phone:normalizedPhone,address,reference:orderReference}))}`;
    setCheckoutStatus(orderReference?`Order ${orderReference} saved. Opening WhatsApp...`:"Order saved. Opening WhatsApp...","success");
  }catch(error){
    console.error(error);
    setCheckoutStatus("Backend unavailable, opening WhatsApp checkout instead.","error");
  }
  window.open(whatsappUrl,"_blank");
  state.cart=[];
  persistCart();
  window.setTimeout(()=>{form.reset();closeCheckoutModal();closeCart();},900);
}

function toggleFavorite(id){
  const product=getProductById(id);
  if(!product)return;
  if(isFavorite(product.id)){state.favorites=state.favorites.filter((favoriteId)=>favoriteId!==product.id);showToast(`${product.name} removed from wishlist`);}else{state.favorites=[...state.favorites,product.id];showToast(`${product.name} added to wishlist`);}
  writeStoredArray(STORAGE_KEYS.favorites,state.favorites);
  updateFavoritesUI();
  renderProducts();
}

function filterProducts(category){setActiveCategory(category);renderProducts();}
function openCategory(category){setActiveCategory(category);loadPage(APP_PAGES.products);}

function normalizeCategory(category){return CATEGORY_ALIAS_MAP[category]||category;}
function filterByCategory(category){openCategory(normalizeCategory(category));}

function quickAddToCart(productId){
  const product=getProductById(productId);
  if(!product){console.error(`Quick add failed. Product "${productId}" was not found.`);return;}
  addToCart(product.id);
}

function addBundleToCart(){
  const bundleProducts=[2,5,8,16].map(getProductById).filter(Boolean);
  if(bundleProducts.length===0)return;
  bundleProducts.forEach((product)=>{
    const existingItem=state.cart.find((item)=>item.id===product.id);
    if(existingItem){existingItem.quantity+=1;}else{state.cart.push({...product,quantity:1});}
  });
  persistCart();
  const standardTotal=bundleProducts.reduce((sum,product)=>sum+(product.offer?.originalPrice||product.price),0);
  const bundleTotal=bundleProducts.reduce((sum,product)=>sum+product.price,0);
  const savings=Math.max(0,standardTotal-bundleTotal);
  showToast(savings>0?`Bundle added to cart. You saved $${formatCurrency(savings)}.`:"Bundle added to cart.");
}

function getBeautyQuizRecommendation(answers){
  if(answers.goal==="hydrate"){return getProductById(4)||getProductById(17)||products[0];}
  if(answers.goal==="repair"){return getProductById(7)||getProductById(16)||products[0];}
  if(answers.goal==="bold"){return getProductById(13)||getProductById(2)||products[0];}
  if(answers.routine==="evening"){return getProductById(12)||getProductById(7)||products[0];}
  if(answers.category==="hair"){return getProductById(3)||getProductById(15)||products[0];}
  return getProductById(5)||getProductById(1)||products[0];
}

function closeBeautyQuiz(){
  closeOverlay(document.getElementById("beauty-quiz-modal"));
}

function startBeautyQuiz(){
  const modal=document.getElementById("beauty-quiz-modal");
  const form=document.getElementById("beauty-quiz-form");
  const results=document.getElementById("beauty-quiz-results");
  if(!modal)return;
  localStorage.setItem("quizStarted","true");
  if(form)form.reset();
  if(results){
    results.innerHTML="";
    results.classList.add("hidden");
  }
  openOverlay(modal);
}

function submitBeautyQuiz(event){
  event.preventDefault();
  const form=event.target;
  const results=document.getElementById("beauty-quiz-results");
  if(!results)return;
  const answers={
    goal:form.goal.value,
    routine:form.routine.value,
    category:form.category.value
  };
  const recommendation=getBeautyQuizRecommendation(answers);
  if(!recommendation){
    results.innerHTML='<p class="text-sm text-rose-600">We could not find a match right now. Please try again.</p>';
    results.classList.remove("hidden");
    return;
  }
  results.innerHTML=`<div class="rounded-2xl bg-white p-4 shadow-soft"><p class="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700">Recommended for you</p><div class="mt-3 flex items-center gap-4"><img src="${escapeHtml(recommendation.image)}" alt="${escapeHtml(recommendation.name)}" class="h-20 w-20 rounded-2xl object-cover" onerror="this.onerror=null; this.src='imag/favicon.png';"><div><h4 class="text-lg font-semibold text-[var(--brand-ink)]">${escapeHtml(recommendation.name)}</h4><p class="mt-1 text-sm text-gray-600">${escapeHtml(recommendation.description)}</p><p class="mt-2 text-sm font-semibold text-rose-700">$${formatCurrency(recommendation.price)}</p></div></div><div class="mt-4 flex flex-wrap gap-3"><button type="button" onclick="closeBeautyQuiz(); quickView(${recommendation.id});" class="btn-primary rounded-full px-5 py-2 text-sm font-medium text-white">View Match</button><button type="button" onclick="addToCart(${recommendation.id})" class="btn-secondary rounded-full px-5 py-2 text-sm font-medium">Add to Cart</button></div></div>`;
  results.classList.remove("hidden");
}

async function signupLoyalty(){
  const phone=prompt("Enter your phone number to join our loyalty program:");
  if(!phone)return;
  const normalizedPhone=phone.replace(/[^\d+]/g,"").trim();
  const digitsOnly=normalizedPhone.replace(/\D/g,"");
  if(digitsOnly.length<10||digitsOnly.length>15){alert("Please enter a valid phone number with 10 to 15 digits.");return;}
  try{
    const payload=await apiRequest("/loyalty/join",{method:"POST",body:JSON.stringify({phone:normalizedPhone})});
    if(payload.alreadyMember){alert(payload.message);return;}
    showToast(payload.message||"You have joined the loyalty program.");
  }catch(error){
    console.error(error);
    if(!saveLoyaltyFallback(normalizedPhone))return;
    showToast("Saved locally. Start the backend to sync loyalty members centrally.");
  }
}

function scrollToProduct(productId){
  const card=document.querySelector(`[data-product-id="${productId}"]`);
  if(card)card.scrollIntoView({behavior:"smooth",block:"center"});
}

function quickView(productId=QUICK_VIEW_FALLBACK_ID){
  loadPage(APP_PAGES.products).then(()=>{
    scrollToProduct(productId);
    window.setTimeout(()=>openProductDetails(productId),250);
  });
}

function addToRecentlyViewed(productId,productName,productImage){
  const product=getProductById(productId);
  let recentItems=readStoredArray(STORAGE_KEYS.recentlyViewed);
  recentItems=recentItems.filter((item)=>item.id!==productId);
  recentItems.unshift({id:productId,name:productName,image:productImage||product?.image||"imag/favicon.png"});
  recentItems=recentItems.slice(0,6);
  writeStoredArray(STORAGE_KEYS.recentlyViewed,recentItems);
  displayRecentlyViewed();
}

function displayRecentlyViewed(){
  const recentItems=readStoredArray(STORAGE_KEYS.recentlyViewed);
  const section=document.getElementById("recently-viewed");
  const container=document.getElementById("recently-viewed-products");
  if(!section||!container)return;
  if(recentItems.length===0){section.style.display="none";container.innerHTML="";return;}
  section.style.display="block";
  container.innerHTML=recentItems.map((item)=>`<article class="product-card rounded-xl bg-white p-3 shadow-soft transition hover:scale-[1.02]"><button type="button" onclick="quickView(${item.id})" class="block w-full text-left"><img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}" class="h-32 w-full rounded-lg object-cover" loading="lazy" decoding="async" onerror="this.onerror=null; this.src='imag/favicon.png';"><p class="mt-2 truncate text-sm font-semibold">${escapeHtml(item.name)}</p></button><button type="button" onclick="quickAddToCart(${item.id})" class="mt-2 w-full rounded-lg bg-pink-500 px-2 py-2 text-xs font-semibold text-white transition hover:bg-pink-600">Quick Buy</button></article>`).join("");
}

function clearRecentlyViewed(){
  localStorage.removeItem(STORAGE_KEYS.recentlyViewed);
  displayRecentlyViewed();
}

function closeNewsletterPopup(){closeOverlay(document.getElementById("newsletter-popup"));}

async function handleNewsletterSubmit(email){
  const normalizedEmail=email.trim().toLowerCase();
  if(!normalizedEmail)return;
  const emailValid=/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail);
  if(!emailValid){alert("Please enter a valid email address.");return;}
  try{
    const payload=await apiRequest("/newsletter/subscribe",{method:"POST",body:JSON.stringify({email:normalizedEmail})});
    if(payload.alreadySubscribed){alert(payload.message);return;}
    showToast(payload.message||"Thanks for subscribing. Your welcome offer is on the way.");
  }catch(error){
    console.error(error);
    if(!saveNewsletterFallback(normalizedEmail))return;
    showToast("Saved locally. Start the backend to keep newsletter signups in one place.");
  }
}

function showStockAlert(){
  const stockAlert=document.getElementById("stock-alert");
  if(!stockAlert)return;
  stockAlert.classList.remove("hidden");
  if(state.stockAlertTimerId)clearTimeout(state.stockAlertTimerId);
  state.stockAlertTimerId=window.setTimeout(()=>stockAlert.classList.add("hidden"),7000);
}

function stopHomepageTimers(){
  if(state.countdownIntervalId){clearInterval(state.countdownIntervalId);state.countdownIntervalId=null;}
  if(state.stockAlertTimerId){clearTimeout(state.stockAlertTimerId);state.stockAlertTimerId=null;}
}

function startCountdown(){
  const daysElement=document.getElementById("days");
  const hoursElement=document.getElementById("hours");
  const minutesElement=document.getElementById("minutes");
  const secondsElement=document.getElementById("seconds");
  if(!daysElement||!hoursElement||!minutesElement||!secondsElement)return;
  stopHomepageTimers();
  const targetDate=new Date();
  targetDate.setDate(targetDate.getDate()+7);
  const updateCountdown=()=>{
    const safeDistance=Math.max(targetDate.getTime()-Date.now(),0);
    daysElement.textContent=String(Math.floor(safeDistance/86400000)).padStart(2,"0");
    hoursElement.textContent=String(Math.floor((safeDistance%86400000)/3600000)).padStart(2,"0");
    minutesElement.textContent=String(Math.floor((safeDistance%3600000)/60000)).padStart(2,"0");
    secondsElement.textContent=String(Math.floor((safeDistance%60000)/1000)).padStart(2,"0");
  };
  updateCountdown();
  state.countdownIntervalId=window.setInterval(updateCountdown,1000);
}

function initHomepageFeatures(){
  displayRecentlyViewed();
  startCountdown();
  state.stockAlertTimerId=window.setTimeout(showStockAlert,3500);
}

function extractPageContent(html){
  const parser=new DOMParser();
  const doc=parser.parseFromString(html,"text/html");
  return doc.body&&doc.body.innerHTML.trim()?doc.body.innerHTML:html;
}

function showPageLoadingState(){
  const mainContent=getMainContent();
  if(!mainContent)return;
  mainContent.innerHTML='<div class="py-20 text-center"><div class="inline-block h-12 w-12 animate-spin rounded-full border-b-2 border-pink-400"></div><p class="mt-4 text-pink-400">Loading...</p></div>';
}

function fetchPageContent(page){
  if(state.pageCache.has(page))return Promise.resolve(state.pageCache.get(page));
  if(state.pendingPageRequests.has(page))return state.pendingPageRequests.get(page);
  const request=fetch(page).then((response)=>{if(!response.ok)throw new Error(`Failed to load ${page}`);return response.text();}).then((html)=>{const content=extractPageContent(html);state.pageCache.set(page,content);state.pendingPageRequests.delete(page);return content;}).catch((error)=>{state.pendingPageRequests.delete(page);throw error;});
  state.pendingPageRequests.set(page,request);
  return request;
}

function handlePageReady(page){
  state.currentPage=page;
  const isProductsPage=page.includes("products.html");
  const isAdminPage=page.includes("admin.html");
  const stockAlert=document.getElementById("stock-alert");
  if(!isProductsPage)productsRendered=false;
  if(isProductsPage)renderProducts();
  if(isAdminPage)initAdminPage();
  if(page===APP_PAGES.home){initHomepageFeatures();}else{stopHomepageTimers();if(stockAlert)stockAlert.classList.add("hidden");}
  updateCartUI();
  updateFavoritesUI();
  if(!isAdminPage)displayRecentlyViewed();
}

function loadPage(page){
  const mainContent=getMainContent();
  if(!mainContent)return Promise.resolve();
  const nextPage=page||APP_PAGES.home;
  const requestId=++state.loadSequence;
  if(state.pageCache.has(nextPage)){
    mainContent.innerHTML=state.pageCache.get(nextPage);
    window.scrollTo({top:0,behavior:"auto"});
    handlePageReady(nextPage);
    return Promise.resolve();
  }
  showPageLoadingState();
  return fetchPageContent(nextPage).then((content)=>{
    if(requestId!==state.loadSequence)return;
    mainContent.innerHTML=content;
    window.scrollTo({top:0,behavior:"auto"});
    handlePageReady(nextPage);
  }).catch((error)=>{
    console.error(error);
    if(requestId!==state.loadSequence)return;
    mainContent.innerHTML="<p class='py-10 text-center text-red-500'>Failed to load page. Please try again.</p>";
  });
}

function bindStaticEvents(){
  const checkoutForm=document.getElementById("checkout-form");
  if(checkoutForm&&checkoutForm.dataset.bound!=="true"){checkoutForm.dataset.bound="true";checkoutForm.addEventListener("submit",submitCheckoutForm);}
  const beautyQuizForm=document.getElementById("beauty-quiz-form");
  if(beautyQuizForm&&beautyQuizForm.dataset.bound!=="true"){beautyQuizForm.dataset.bound="true";beautyQuizForm.addEventListener("submit",submitBeautyQuiz);}
  const mobileMenuToggle=getMobileMenuToggle();
  if(mobileMenuToggle&&mobileMenuToggle.dataset.bound!=="true"){
    mobileMenuToggle.dataset.bound="true";
    mobileMenuToggle.addEventListener("click",toggleMobileMenu);
  }
  [{id:"cart-modal",close:closeCart},{id:"product-details-modal",close:closeProductDetails},{id:"checkout-modal",close:closeCheckoutModal},{id:"beauty-quiz-modal",close:closeBeautyQuiz},{id:"newsletter-popup",close:closeNewsletterPopup}].forEach(({id,close})=>{
    const modal=document.getElementById(id);
    if(!modal||modal.dataset.bound==="true")return;
    modal.dataset.bound="true";
    modal.addEventListener("click",(event)=>{if(event.target===modal)close();});
  });
  document.addEventListener("keydown",(event)=>{
    if(event.key!=="Escape")return;
    closeMobileMenu();
    if(getVisibleOverlayCount()===0)return;
    closeNewsletterPopup();closeBeautyQuiz();closeProductDetails();closeCheckoutModal();closeCart();
  });
  document.addEventListener("click",(event)=>{
    const panel=getMobileMenuPanel();
    const toggle=getMobileMenuToggle();
    if(!panel||panel.classList.contains("hidden"))return;
    if(panel.contains(event.target)||toggle&&toggle.contains(event.target))return;
    closeMobileMenu();
  });
  document.addEventListener("click",(event)=>{const anchor=event.target.closest('a[href="#"]');if(anchor)event.preventDefault();});
  document.addEventListener("submit",(event)=>{
    const form=event.target;
    if(!(form instanceof HTMLFormElement))return;
    if(form.id==="footer-newsletter"||form.id==="popup-newsletter"||form.id==="newsletter-form"){
      event.preventDefault();
      const emailInput=form.querySelector('input[type="email"]');
      handleNewsletterSubmit(emailInput?emailInput.value:"");
      form.reset();
      if(form.id==="popup-newsletter")closeNewsletterPopup();
    }
  });
  document.addEventListener("mouseleave",(event)=>{
    if(event.clientY>0||state.currentPage!==APP_PAGES.home||localStorage.getItem(STORAGE_KEYS.newsletterShown))return;
    const popup=document.getElementById("newsletter-popup");
    if(!popup)return;
    openOverlay(popup);
    localStorage.setItem(STORAGE_KEYS.newsletterShown,"true");
  });
  window.addEventListener("resize",()=>{if(window.innerWidth>=768)closeMobileMenu();});
}

async function initApp(){
  bindStaticEvents();
  updateCartUI();
  updateFavoritesUI();
  displayRecentlyViewed();
  closeMobileMenu();
  await syncProductsFromApi();
  loadPage(APP_PAGES.home);
}

document.addEventListener("DOMContentLoaded",initApp);

window.loadPage=loadPage;
window.openCategory=openCategory;
window.filterProducts=filterProducts;
window.toggleFavorite=toggleFavorite;
window.addToCart=addToCart;
window.changeQty=changeQty;
window.removeItem=removeItem;
window.openCart=openCart;
window.closeCart=closeCart;
window.checkout=checkout;
window.startBeautyQuiz=startBeautyQuiz;
window.closeBeautyQuiz=closeBeautyQuiz;
window.openProductDetails=openProductDetails;
window.closeProductDetails=closeProductDetails;
window.closeCheckoutModal=closeCheckoutModal;
window.closeNewsletterPopup=closeNewsletterPopup;
window.quickAddToCart=quickAddToCart;
window.addBundleToCart=addBundleToCart;
window.filterByCategory=filterByCategory;
window.quickView=quickView;
window.scrollToProduct=scrollToProduct;
window.signupLoyalty=signupLoyalty;
window.clearRecentlyViewed=clearRecentlyViewed;
window.updateCartUI=updateCartUI;
window.closeMobileMenu=closeMobileMenu;

// Kanaat QR Menü – çevrimdışı/yavaş internette hızlı açılma
const V="76 · 10.11.2026";const C="kanaat-menu-v1";
self.addEventListener("install",e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(["./","img/logo.jpg","img/logo-lacivert.png","img/sef.jpg"]).catch(()=>{})));self.skipWaiting()});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith("kanaat-menu-")&&k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
const timeout=(p,ms)=>new Promise((res,rej)=>{const t=setTimeout(()=>rej(0),ms);p.then(r=>{clearTimeout(t);res(r)},x=>{clearTimeout(t);rej(x)})});
self.addEventListener("fetch",e=>{
  const r=e.request;if(r.method!=="GET")return;const u=new URL(r.url);
  const font=/fonts\.(googleapis|gstatic)\.com$/.test(u.hostname);
  if(u.origin!==location.origin&&!font)return;
  if(u.pathname.includes("/istatistik/"))return;
  // Sayfa ve kurlar: önce internet (en güncel fiyatlar), 4 sn'de gelmezse kayıtlı kopya
  if(r.mode==="navigate"||u.pathname.endsWith("/menu/")||u.pathname.endsWith("index.html")||u.pathname.endsWith("fx.json")){
    const key=r.mode==="navigate"?new Request(u.origin+u.pathname):r;
    e.respondWith(timeout(fetch(r),4000).then(res=>{if(res.ok){const cp=res.clone();caches.open(C).then(c=>c.put(key,cp))}return res}).catch(()=>caches.match(key).then(m=>m||fetch(r))));return}
  // Fotoğraflar, simgeler, yazı tipleri: önce kayıtlı kopya, arkada yenile
  e.respondWith(caches.open(C).then(c=>c.match(r).then(m=>{const n=fetch(r).then(res=>{if(res.ok||res.type==="opaque")c.put(r,res.clone());return res}).catch(()=>m);return m||n})));
});

/* Kanaat POS: uygulama olarak yüklenebilmek için. Önbellek YOK — her açılışta en güncel sürüm internetten gelir. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(fetch(e.request).catch(() => new Response('<meta charset="utf-8"><body style="font:20px sans-serif;padding:24px">İnternet bağlantısı yok. Bağlantı gelince sayfayı yenileyin.</body>', {headers: {'Content-Type': 'text/html; charset=utf-8'}})));
});

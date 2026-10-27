/* Kanaat Personel: uygulama olarak yüklenebilmesi için. Önbellek yok; sayfa her zaman internetten gelir. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});

/* ChaqmoqApp minimal service worker — PWA o'rnatish uchun */
const CACHE = 'chaqmoq-pwa-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(['/static/pwa/icon-192.png'])));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  // Network-first: sayt har doim serverdan
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

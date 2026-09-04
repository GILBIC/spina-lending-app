const CACHE_NAME = 'spina-company-shell-v3';
const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/assets/app.css',
  '/assets/app.js',
  '/assets/api.js',
  '/assets/config.js',
  '/assets/session.js',
  '/assets/roles.js',
  '/assets/ui.js',
  '/assets/presenters.js',
  '/assets/collector-contract.js',
  '/assets/staff-invite.js',
  '/assets/management-devices.js',
  '/assets/roles/client.js',
  '/assets/roles/employee.js',
  '/assets/roles/collector.js',
  '/assets/roles/management.js',
  '/assets/spina-icon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  const { pathname } = url;

  if (
    request.method !== 'GET' ||
    url.origin !== self.location.origin ||
    pathname.startsWith('/api/') ||
    pathname.startsWith('/health/')
  ) {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put('/index.html', copy));
          }
          return response;
        })
        .catch(() => caches.match('/index.html')),
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    }),
  );
});

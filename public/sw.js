const CACHE_NAME = 'cut-tracker-v1'
const ASSETS = ['/', '/manifest.json', '/icon-192.svg', '/icon-512.svg']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)))
})

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request).then((response) => {
      if (event.request.method === 'GET' && event.request.url.startsWith(self.location.origin)) {
        const clone = response.clone()
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone))
      }
      return response
    }).catch(() => cached)),
  )
})

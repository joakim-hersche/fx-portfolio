const CACHE_NAME = "market-dashboard-v2";
const PRECACHE = ["/"];

// Paths that must never be served from cache (sensitive / auth routes)
const NO_CACHE_PATHS = ["/admin", "/stripe/", "/reset", "/pricing", "/_nicegui_ws/"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((c) => c.addAll(PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // Never cache sensitive endpoints — always go to network
  if (NO_CACHE_PATHS.some((p) => url.pathname.startsWith(p))) {
    e.respondWith(fetch(e.request));
    return;
  }

  // Network-first for everything else: try fresh data, fall back to cache
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        // Only cache successful GET responses
        if (e.request.method === "GET" && res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
        }
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});

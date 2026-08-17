const CACHE_NAME = "wikipelago-shell-2026-08-17-03";

const PRECACHE_URLS = [
  "/",
  "/manifest.webmanifest",
  "/static/app.js?v=20260817-03",
  "/static/style.css?v=20260817-03",
  "/static/i18n.js?v=20260817-03",
  "/icons/icon-192_placeholder.png",
  "/icons/icon-512_placeholder.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.all(PRECACHE_URLS.map(async (url) => {
      try {
        await cache.add(url);
      } catch (error) {
        console.warn("Precache failed for", url, error);
      }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter((name) => name.startsWith("wikipelago-shell-") && name !== CACHE_NAME)
        .map((name) => caches.delete(name))
    );
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  // Never cache API/health/SW itself — stale shell was hiding deploys.
  if (
    url.pathname.startsWith("/api/")
    || url.pathname === "/health"
    || url.pathname === "/service-worker.js"
  ) {
    return;
  }

  const isNavigate = request.mode === "navigate" || url.pathname === "/";

  event.respondWith((async () => {
    // HTML shell: network-first so branch/version badge updates after deploy.
    if (isNavigate) {
      try {
        const response = await fetch(request);
        if (response && response.ok) {
          const cache = await caches.open(CACHE_NAME);
          cache.put("/", response.clone());
        }
        return response;
      } catch (error) {
        const fallback = await caches.match("/");
        if (fallback) return fallback;
        throw error;
      }
    }

    const cached = await caches.match(request);
    if (cached) return cached;

    try {
      const response = await fetch(request);
      if (response && response.ok && url.pathname.startsWith("/static/")) {
        const cache = await caches.open(CACHE_NAME);
        cache.put(request, response.clone());
      }
      return response;
    } catch (error) {
      throw error;
    }
  })());
});

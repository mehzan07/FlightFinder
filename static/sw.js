const CACHE_NAME = "flightfinder-v1";
const OFFLINE_URL = "/offline"; // Ensure you have a route in your Flask app for this

// 1. Install - Cache the offline page
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([OFFLINE_URL]);
    }),
  );
});

// 2. Fetch - If network fails, show the offline page
self.addEventListener("fetch", (event) => {
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(OFFLINE_URL);
      }),
    );
  }
});

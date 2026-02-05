self.addEventListener("install", (e) => {
  console.log("FlightFinder Service Worker Installed");
});

self.addEventListener("fetch", (e) => {
  // This allows the app to load normally
  e.respondWith(fetch(e.request));
});

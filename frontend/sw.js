// Service worker: estrategia network-first (los cambios se ven al instante
// estando online) con respaldo en caché para uso sin conexión.
const CACHE = "chessmaster-v3";
const SHELL = [
  "/", "/index.html", "/styles.css", "/app.js", "/manifest.webmanifest", "/icon.svg",
  "/pieces/cburnett/wK.svg", "/pieces/cburnett/wQ.svg", "/pieces/cburnett/wR.svg",
  "/pieces/cburnett/wB.svg", "/pieces/cburnett/wN.svg", "/pieces/cburnett/wP.svg",
  "/pieces/cburnett/bK.svg", "/pieces/cburnett/bQ.svg", "/pieces/cburnett/bR.svg",
  "/pieces/cburnett/bB.svg", "/pieces/cburnett/bN.svg", "/pieces/cburnett/bP.svg",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) return;      // la API siempre va a la red
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});

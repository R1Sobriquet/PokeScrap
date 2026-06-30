/* PokéAlpha service worker — coquille offline minimale + push. */
const CACHE = "pokealpha-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

// Network-first pour les navigations (HTML), avec repli cache hors-ligne.
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || req.mode !== "navigate") return;
  e.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(req).then((m) => m || caches.match("/")))
  );
});

// Push serveur (nécessite un backend VAPID) → notification système.
self.addEventListener("push", (e) => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch { data = { body: e.data && e.data.text() }; }
  e.waitUntil(
    self.registration.showNotification(data.title || "PokéAlpha", {
      body: data.body || "Nouveau signal sur le marché.",
      icon: "/icon.svg",
      badge: "/icon.svg",
      data: { url: data.url || "/cockpit" },
    })
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/cockpit";
  e.waitUntil(
    self.clients.matchAll({ type: "window" }).then((cls) => {
      const hit = cls.find((c) => "focus" in c);
      return hit ? hit.focus() : self.clients.openWindow(url);
    })
  );
});

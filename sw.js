/* Service worker d'Arpagon : l'app s'ouvre même sans réseau.
   Stratégie : on sert la copie en cache tout de suite, et on la met à jour
   en arrière-plan quand le réseau répond. Le serveur Premium n'est jamais
   mis en cache (requêtes vers un autre domaine). */
var CACHE = "arpagon-v1";
var SHELL = ["./", "./index.html", "./manifest.json", "./logo/arpagon-180.png", "./logo/arpagon-192.png", "./logo/arpagon-512.png"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith(caches.open(CACHE).then(function (c) {
    return c.match(req, { ignoreSearch: true }).then(function (hit) {
      var net = fetch(req).then(function (res) {
        if (res && res.ok) c.put(req, res.clone());
        return res;
      }).catch(function () { return hit; });
      return hit || net;
    });
  }));
});

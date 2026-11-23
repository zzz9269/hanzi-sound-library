// Offline support. The app shell is precached; dictionary shards are cached
// the first time they are read (or all at once from Saved → "Use offline").
// Data URLs carry ?v=<build> so a new dataset never mixes with an old one.
// Audio and Wiktionary are left to the network.
const BUILD = "__BUILD__";              // stamped with the commit by the deploy workflow
const SHELL = `hz-shell-${BUILD}`;
const DATA = "hz-data";
const FONTS = "hz-fonts";
const SHELL_FILES = [
  "./", "index.html", "manifest.webmanifest", "css/app.css",
  "js/app.js", "js/data.js", "js/audio.js", "js/wikt.js", "js/tree.js", "js/notation.js",
  "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png",
];

self.addEventListener("install", (ev) => {
  // cache: "reload" skips the browser's HTTP cache (GitHub Pages sends
  // max-age=600), so a new build never precaches the previous build's files
  ev.waitUntil(caches.open(SHELL)
    .then((c) => c.addAll(SHELL_FILES.map((u) => new Request(u, { cache: "reload" }))))
    .then(() => self.skipWaiting()));
});

self.addEventListener("activate", (ev) => {
  ev.waitUntil((async () => {
    for (const k of await caches.keys()) {
      if (k.startsWith("hz-shell-") && k !== SHELL) await caches.delete(k);
    }
    await self.clients.claim();
  })());
});

let dataVersion = null;
async function purgeOldData(v) {
  if (v === dataVersion) return;
  dataVersion = v;
  const c = await caches.open(DATA);
  for (const req of await c.keys()) {
    if (new URL(req.url).searchParams.get("v") !== v) await c.delete(req);
  }
}

async function cacheFirst(cacheName, req) {
  const c = await caches.open(cacheName);
  const hit = await c.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok || res.type === "opaque") c.put(req, res.clone());
  return res;
}

async function networkFirst(cacheName, req) {
  const c = await caches.open(cacheName);
  try {
    const res = await fetch(req, { cache: "no-cache" });
    if (res.ok) c.put(req, res.clone());
    return res;
  } catch (e) {
    const hit = await c.match(req);
    if (hit) return hit;
    throw e;
  }
}

async function staleWhileRevalidate(cacheName, req) {
  const c = await caches.open(cacheName);
  const hit = await c.match(req, { ignoreSearch: true });
  const fresh = fetch(req, { cache: "no-cache" }).then((res) => { if (res.ok) c.put(req, res.clone()); return res; });
  if (hit) { fresh.catch(() => {}); return hit; }
  return fresh;
}

self.addEventListener("fetch", (ev) => {
  const req = ev.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  if (url.origin === location.origin) {
    const rel = url.pathname.slice(new URL(self.registration.scope).pathname.length);
    if (rel === "data/meta.json") { ev.respondWith(networkFirst(DATA, req)); return; }
    if (rel.startsWith("data/")) {
      const v = url.searchParams.get("v");
      if (v) ev.waitUntil(purgeOldData(v));
      ev.respondWith(cacheFirst(DATA, req));
      return;
    }
    if (req.mode === "navigate") {
      ev.respondWith(staleWhileRevalidate(SHELL, new Request("index.html")).catch(() => caches.match("./")));
      return;
    }
    ev.respondWith(staleWhileRevalidate(SHELL, req));
    return;
  }
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    ev.respondWith(cacheFirst(FONTS, req));
  }
});

// "Use offline": the page posts the list of data files; cache what's missing.
self.addEventListener("message", (ev) => {
  const msg = ev.data || {};
  if (msg.type === "clear-offline") { ev.waitUntil(caches.delete(DATA)); return; }
  if (msg.type !== "prefetch") return;
  ev.waitUntil((async () => {
    const c = await caches.open(DATA);
    let done = 0;
    const urls = msg.urls.slice();
    const report = () => ev.source?.postMessage({ type: "prefetch-progress", done, total: msg.urls.length });
    const worker = async () => {
      while (urls.length) {
        const u = urls.shift();
        try {
          if (!(await c.match(u))) {
            const res = await fetch(u);
            if (res.ok) await c.put(u, res);
          }
        } catch { /* keep going; a retry later fills gaps */ }
        if (++done % 10 === 0 || done === msg.urls.length) report();
      }
    };
    await Promise.all(Array.from({ length: 6 }, worker));
  })());
});

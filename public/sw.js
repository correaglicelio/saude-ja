// Saúde Já — service worker: faz o app abrir sem internet com os últimos dados vistos.
// Estratégia: app e listas fixas em cache na instalação; dados por estado ficam em cache
// quando abertos (rede primeiro, cache se estiver offline); mapa de ruas guardado aos poucos.
const VERSAO = "saudeja-v9";
const BASE = ["./", "index.html", "manifest.webmanifest", "icon.svg", "icon-maskable.svg", "icon-192.png", "icon-512.png", "apple-touch-icon.png",
  "data/municipios.json", "data/estados.geojson", "data/meta.json", "data/vacinas/calendario.json", "data/sangue.json", "data/transparencia/meta.json", "data/arboviroses/meta.json", "data/srag/meta.json",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSAO).then(c => c.addAll(BASE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSAO).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function redePrimeiro(req){
  const c = await caches.open(VERSAO);
  // arquivos do próprio site: sempre confere com o servidor se há versão nova (o GitHub Pages
  // manda guardar por 10 min); se nada mudou, a resposta é curta (304) e vem do cache do navegador
  const mesma = new URL(req.url).origin === location.origin;
  const pedido = !mesma ? req : req.mode === "navigate"
    ? new Request(req.url, {cache: "no-cache", credentials: "same-origin"})
    : new Request(req, {cache: "no-cache"});
  try { const r = await fetch(pedido); if (r.ok) c.put(req, r.clone()); return r; }
  catch { const r = await c.match(req); if (r) return r; throw new Error("offline"); }
}
async function cachePrimeiro(req, limite){
  const c = await caches.open(VERSAO);
  const r = await c.match(req); if (r) return r;
  const n = await fetch(req);
  if (n.ok || n.type === "opaque"){ c.put(req, n.clone()); if (limite) podar(c, limite); }
  return n;
}
async function podar(c, max){
  const ks = (await c.keys()).filter(k => k.url.includes("tile.openstreetmap.org"));
  for (const k of ks.slice(0, Math.max(0, ks.length - max))) await c.delete(k);
}

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (url.hostname === "tile.openstreetmap.org") return e.respondWith(cachePrimeiro(e.request, 600));
  if (url.origin === location.origin && url.pathname.includes("/data/")) return e.respondWith(redePrimeiro(e.request));
  if (url.origin === location.origin || url.hostname.endsWith("cloudflare.com") || url.hostname.endsWith("gstatic.com") || url.hostname.endsWith("googleapis.com"))
    return e.respondWith(redePrimeiro(e.request));
});

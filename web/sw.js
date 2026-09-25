/* 厦大统一门户 · Service Worker（只服务"静态托管"的手机版）
   策略：
     · 应用外壳（HTML/CSS/JS/图标/字体）——缓存优先，断网也能开
     · portal.json——网络优先，拿到新的就更新缓存；断网回落到缓存
     · /api/* 一律不碰：那是桌面版本地后端的接口，缓存了会出事
   桌面版不会注册它（注册代码里有"只在非本机地址时注册"的判断）。 */

const CACHE = 'xmuhub-v2';   // 改名 + 改版后把版本号抬一位：activate 时会把旧缓存删掉
const SHELL = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './portal.json',
  './manifest.json',
  './assets/logo/favicon.ico',
  './assets/logo/logo-128.png',
  './assets/logo/logo-256.png',
  './assets/logo/logo-512.png',
  './assets/logo/logo-256-mark.png',
  './assets/xmu-emblem.png',
  './assets/informatics-emblem.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      // 逐个 add：某一个 404 不至于让整次安装失败
      .then((cache) => Promise.all(SHELL.map((url) => cache.add(url).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;   // 外部资源不插手
  if (url.pathname.includes('/api/')) return;        // 桌面版本地后端接口，绝不能缓存

  const fresh = fetch(request)
    .then((response) => {
      if (response && response.ok) {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy));
      }
      return response;
    })
    .catch(() => null);

  // 目录数据：先网络后缓存（保证看到最新收录）
  if (url.pathname.endsWith('portal.json')) {
    event.respondWith(fresh.then((response) => response || caches.match(request)));
    return;
  }
  // 其余外壳：先缓存后网络（打开快，断网也能用）
  event.respondWith(caches.match(request).then((hit) => hit || fresh));
});

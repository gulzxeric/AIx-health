/**
 * Service Worker - 家属端 PWA
 * 
 * 缓存策略：
 * - 静态资源（HTML/CSS/JS）：Cache First
 * - 简报数据（API /briefs）：Network First with cache fallback
 * - 其他 API 请求：Network Only
 */

const CACHE_NAME = 'caregiver-cache-v1';
const STATIC_CACHE_NAME = 'caregiver-static-v1';

// 预缓存的核心资源（相对路径，匹配任意部署根目录）
const PRECACHE_URLS = [
  './',
  'index.html',
  'css/caregiver.css',
  'js/main.js',
  'js/mock-api.js',
  'js/api.js',
  'manifest.json'
];

// VAPID 公钥占位（后续由后端生成）
const VAPID_PUBLIC_KEY = '';

// ================================================================
// 安装事件：预缓存核心资源（单项失败不阻塞安装）
// ================================================================
self.addEventListener('install', (event) => {
  console.log('[SW] Install 事件触发');
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME).then((cache) => {
      console.log('[SW] 预缓存核心资源');
      return Promise.allSettled(
        PRECACHE_URLS.map((url) => cache.add(url))
      );
    }).then(() => {
      // 跳过等待，立即激活
      return self.skipWaiting();
    })
  );
});

// ================================================================
// 激活事件：清理旧缓存
// ================================================================
self.addEventListener('activate', (event) => {
  console.log('[SW] Activate 事件触发');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== STATIC_CACHE_NAME && cacheName !== CACHE_NAME) {
            console.log('[SW] 清理旧缓存:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      // 接管所有客户端
      return self.clients.claim();
    })
  );
});

// ================================================================
// 请求拦截：缓存策略分发
// ================================================================
self.addEventListener('fetch', (event) => {
  const requestUrl = new URL(event.request.url);
  const pathname = requestUrl.pathname;

  // 静态资源策略：Cache First
  if (
    pathname.endsWith('.css') ||
    pathname.endsWith('.js') ||
    pathname === '/' ||
    pathname === '/index.html' ||
    pathname === '/manifest.json'
  ) {
    event.respondWith(cacheFirstStrategy(event.request));
    return;
  }

  // 简报 API：Network First with cache fallback
  if (pathname.includes('/api/v1/briefs/') || pathname.includes('/api/v1/briefs/latest')) {
    event.respondWith(networkFirstStrategy(event.request));
    return;
  }

  // 其余请求：Network Only
  // 不拦截默认行为
});

/**
 * Cache First 策略
 * 先从缓存中查找，找不到再从网络获取并缓存
 */
async function cacheFirstStrategy(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    console.log('[SW] Cache HIT:', request.url);
    return cachedResponse;
  }
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('[SW] 网络请求失败，返回离线页面:', request.url);
    // 返回缓存的首页作为降级
    return caches.match('./');
  }
}

/**
 * Network First 策略
 * 先从网络获取，失败（离线）时回退到缓存
 */
async function networkFirstStrategy(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('[SW] Network First 回退到缓存:', request.url);
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    // 无缓存可用时返回离线提示
    return new Response(
      JSON.stringify({ error: 'offline', message: '当前无网络连接，数据可能不是最新的' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

// ================================================================
// 推送事件：接收 Web Push 并显示通知
// ================================================================
self.addEventListener('push', (event) => {
  console.log('[SW] Push 事件触发');
  
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = {
        title: 'AIX Health',
        body: event.data.text()
      };
    }
  }

  const title = data.title || 'AIX Health 家属助手';
  const options = {
    body: data.body || '患者有新动态，请查看',
    icon: data.icon || '/icons/icon-192.png',
    badge: '/icons/icon-96.png',
    tag: data.tag || 'caregiver-notification',
    data: {
      url: data.url || '/'
    },
    vibrate: [200, 100, 200],
    requireInteraction: true,
    actions: [
      { action: 'open', title: '查看详情' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// ================================================================
// 通知点击事件
// ================================================================
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification click 事件触发');
  
  event.notification.close();

  const urlToOpen = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // 如果有已打开的窗口，聚焦到它
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          // 导航到目标 URL
          client.navigate(urlToOpen);
          return client.focus();
        }
      }
      // 没有打开窗口，打开新窗口
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});

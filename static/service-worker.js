// Cache shell assets and wire up client notifications for offline/online changes.
const CACHE_NAME = "youtube-scheduler-cache-v1";
const ASSETS_TO_PRE_CACHE = ["/", "/static/style.css", "/static/offline.js"];
const CLIENT_MESSAGES = Object.freeze({
  ONLINE: "network-ok",
  NETWORK_ERROR: "network-error",
  SERVER_ERROR: "server-error",
  STATUS_REQUEST: "status-request"
});

let lastBroadcastType = CLIENT_MESSAGES.ONLINE;

// Notify all controlled windows about connectivity status shifts.
const broadcastToClients = (type) => {
  lastBroadcastType = type;
  return self.clients
    .matchAll({ type: "window", includeUncontrolled: true })
    .then((clients) => clients.forEach((client) => client.postMessage({ type })))
    .catch(() => undefined);
};

// Serve cached content when the network or server fails, signaling status for navigations.
const handleOfflineFallback = (event, statusType = CLIENT_MESSAGES.NETWORK_ERROR) =>
  caches.match(event.request).then((cachedResponse) => {
    if (cachedResponse) {
      if (event.request.mode === "navigate") {
        broadcastToClients(statusType);
      }
      return cachedResponse;
    }

    if (event.request.mode === "navigate") {
      return caches.match("/").then((rootResponse) => {
        if (rootResponse) {
          broadcastToClients(statusType);
          return rootResponse;
        }
        broadcastToClients(statusType);
        return Response.error();
      });
    }

    return Response.error();
  });

self.addEventListener("install", (event) => {
  // Pre-cache core assets so the UI is available offline immediately.
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_PRE_CACHE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Clean up old caches and take control of existing clients ASAP.
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("message", (event) => {
  // Respond to status requests so new pages know whether they are offline.
  const { type } = event.data || {};
  if (type === CLIENT_MESSAGES.STATUS_REQUEST && event.source && typeof event.source.postMessage === "function") {
    event.source.postMessage({ type: lastBroadcastType });
  }
});

self.addEventListener("fetch", (event) => {
  // Network-first strategy for same-origin GETs, with cache fallback for navigations.
  if (event.request.method !== "GET") {
    return;
  }

  const requestUrl = new URL(event.request.url);
  const isSameOrigin = requestUrl.origin === self.location.origin;

  if (!isSameOrigin) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (!response || !response.ok) {
          if (event.request.mode === "navigate") {
            throw new Error("Server responded with an error", { cause: CLIENT_MESSAGES.SERVER_ERROR });
          }
          throw new Error("Network response not ok");
        }

        if (event.request.mode === "navigate") {
          broadcastToClients(CLIENT_MESSAGES.ONLINE);
        }

        const responseClone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
        return response;
      })
      .catch((error) => {
        const statusType = error?.cause === CLIENT_MESSAGES.SERVER_ERROR ? CLIENT_MESSAGES.SERVER_ERROR : CLIENT_MESSAGES.NETWORK_ERROR;
        return handleOfflineFallback(event, statusType);
      })
  );
});

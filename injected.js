<script>
(() => {
  const WS_URL     = "ws://localhost:5678";
  const MIN_DELAY  = 250;      // ms
  const MAX_DELAY  = 8000;     // ms
  const RELOAD_KEY = "livereload:reloads";

  let ws = null;
  let attempts = 0;
  let timer = null;
  let everConnected = false;   // been connected at least once during this page load
  let unloading = false;       // page is going away; do not reconnect

  // ---- reload with a loop fuse (survives reloads via sessionStorage) ----
  function safeReload() {
    const now = Date.now();
    let log = [];
    try { log = JSON.parse(sessionStorage.getItem(RELOAD_KEY) || "[]"); } catch (_) {}
    log = log.filter(t => now - t < 5000);
    if (log.length >= 4) {
      console.warn("[livereload] too many reloads in 5s — disabled until manual refresh");
      return;
    }
    log.push(now);
    sessionStorage.setItem(RELOAD_KEY, JSON.stringify(log));
    location.reload();
  }

  function scheduleReconnect() {
    attempts += 1;
    const ceiling = Math.min(MAX_DELAY, MIN_DELAY * 2 ** (attempts - 1));
    const delay = ceiling / 2 + Math.random() * (ceiling / 2);   // jitter
    console.log(`[livereload] disconnected — retry in ${Math.round(delay)} ms`);
    clearTimeout(timer);
    timer = setTimeout(connect, delay);
  }

  function connect() {
    clearTimeout(timer);
    timer = null;
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      attempts = 0;
      // Reconnect (not the initial connect) => we may have missed a reload.
      if (everConnected) {
        console.log("[livereload] reconnected — refreshing");
        safeReload();
        return;
      }
      everConnected = true;
    };

    ws.onmessage = (e) => {
      if (e.data === "reload") safeReload();
    };

    // onerror is always followed by onclose; reconnect logic lives there only.
    ws.onclose = () => {
      ws = null;
      if (unloading) return;
      scheduleReconnect();
    };
  }

  // Stop reconnecting when the document is being replaced.
  addEventListener("beforeunload", () => {
    unloading = true;
    clearTimeout(timer);
    if (ws) { try { ws.close(1000, "page unload"); } catch (_) {} }
  });

  // Coming back from a background tab or a suspended laptop: retry immediately
  // instead of waiting out the backoff.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && !ws && !unloading) {
      attempts = 0;
      connect();
    }
  });
  addEventListener("online", () => {
    if (!ws && !unloading) { attempts = 0; connect(); }
  });

  connect();
})();
</script>

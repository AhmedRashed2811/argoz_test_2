/* Argoz CRM — global resilience utilities (idempotency, retry, spinners).
   Loaded on every authenticated page via base.html, BEFORE page scripts.

   Exposes window.CRM:
     CRM.uuidv4()                         -> RFC4122 v4 string
     CRM.fetchWithRetry(url, opts, cfg)   -> fetch with exponential backoff,
                                             auto idempotency key + CSRF + spinner
     CRM.showOverlay() / CRM.hideOverlay()-> global blocking spinner
     CRM.withSpinner(container, promise)  -> per-container loader for GET fetches

   It also auto-protects every <form method="post">: injects a persistent
   idempotency_key, disables the submit button, and shows the overlay so a
   double-click or impatient retry can't fire the write twice. */
(function () {
  const CFG = window.LAYOUT_CFG || {};

  /* ── UUID v4 ── */
  function uuidv4() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return ('10000000-1000-4000-8000-100000000000').replace(/[018]/g, c =>
      (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
  }

  /* ── CSRF (from layout cfg, falling back to cookie) ── */
  function csrfToken() {
    if (CFG.csrf) return CFG.csrf;
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  /* ── Injected styles (one file, no extra <link>) ── */
  const css = `
  .crm-overlay{position:fixed;inset:0;z-index:9999;display:none;align-items:center;
    justify-content:center;background:rgba(255,255,255,.55);backdrop-filter:blur(1px)}
  .crm-overlay.show{display:flex}
  .crm-spinner{width:42px;height:42px;border:4px solid rgba(224,123,32,.25);
    border-top-color:#e07b20;border-radius:50%;animation:crm-spin .8s linear infinite}
  .crm-container-loader{display:flex;align-items:center;justify-content:center;
    min-height:120px;padding:24px}
  @keyframes crm-spin{to{transform:rotate(360deg)}}`;
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  /* ── Global blocking overlay ── */
  let overlay;
  function ensureOverlay() {
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'crm-overlay';
      overlay.innerHTML = '<div class="crm-spinner" role="status" aria-label="Loading"></div>';
      document.body.appendChild(overlay);
    }
    return overlay;
  }
  function showOverlay() { ensureOverlay().classList.add('show'); }
  function hideOverlay() { if (overlay) overlay.classList.remove('show'); }

  /* ── Per-container loader for GET fetches ── */
  function spinnerNode() {
    const n = document.createElement('div');
    n.className = 'crm-container-loader';
    n.innerHTML = '<div class="crm-spinner" role="status" aria-label="Loading"></div>';
    return n;
  }
  function withSpinner(container, promise) {
    const el = typeof container === 'string' ? document.querySelector(container) : container;
    if (!el) return promise;
    const prev = el.getAttribute('aria-busy');
    el.setAttribute('aria-busy', 'true');
    el.innerHTML = '';
    el.appendChild(spinnerNode());
    const done = () => { if (prev) el.setAttribute('aria-busy', prev); else el.removeAttribute('aria-busy'); };
    return Promise.resolve(promise).then(
      v => { done(); return v; },
      e => { done(); throw e; }
    );
  }

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const WRITE = /^(POST|PUT|PATCH|DELETE)$/i;
  const nativeFetch = window.fetch.bind(window);

  /* ── fetch with exponential backoff ── */
  /* cfg: { retries=3, baseDelay=1000, overlay=true, container=null,
            idempotencyKey=auto } */
  async function fetchWithRetry(url, opts = {}, cfg = {}) {
    const retries = cfg.retries ?? 3;
    const baseDelay = cfg.baseDelay ?? 1000;
    const method = (opts.method || 'GET').toUpperCase();

    opts.headers = new Headers(opts.headers || {});
    opts.credentials = opts.credentials || 'same-origin';
    if (WRITE.test(method)) {
      if (!opts.headers.has('X-CSRFToken')) opts.headers.set('X-CSRFToken', csrfToken());
      // Stable across retries so the server replays instead of re-running.
      const key = cfg.idempotencyKey || uuidv4();
      if (!opts.headers.has('X-Idempotency-Key')) opts.headers.set('X-Idempotency-Key', key);
    }

    const useOverlay = cfg.overlay !== false && WRITE.test(method);
    const run = async () => {
      let lastErr;
      for (let attempt = 0; attempt <= retries; attempt++) {
        try {
          const res = await nativeFetch(url, opts);
          // Retry only on transient server failures, not 4xx client errors.
          if (res.status >= 500 && attempt < retries) {
            await sleep(baseDelay * 2 ** attempt);
            continue;
          }
          return res;
        } catch (err) {            // network drop / DNS / abort
          lastErr = err;
          if (attempt < retries) { await sleep(baseDelay * 2 ** attempt); continue; }
          throw lastErr;
        }
      }
      throw lastErr;
    };

    if (useOverlay) showOverlay();
    try {
      const p = run();
      return cfg.container ? await withSpinner(cfg.container, p) : await p;
    } finally {
      if (useOverlay) hideOverlay();
    }
  }

  /* ── Auto-protect plain POST forms ── */
  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if ((form.method || '').toLowerCase() !== 'post') return;
    if (form.dataset.noIdempotency !== undefined) return;

    // Persist the key on the form so a retry (browser back, re-submit without
    // reload) reuses it and the server replays rather than duplicating.
    let input = form.querySelector('input[name="idempotency_key"]');
    if (!input) {
      input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'idempotency_key';
      form.appendChild(input);
    }
    if (!input.value) input.value = uuidv4();

    const btn = form.querySelector('[type="submit"]');
    if (btn && !btn.disabled) {
      btn.disabled = true;
      btn.dataset.origText = btn.textContent;
      if (btn.tagName === 'BUTTON') btn.textContent = 'Please wait…';
      // Re-enable if the browser restores the page from bfcache.
      window.addEventListener('pageshow', () => {
        btn.disabled = false;
        if (btn.dataset.origText) btn.textContent = btn.dataset.origText;
      }, { once: true });
    }
    showOverlay();
  }, true);

  /* ── Transparently upgrade every existing write fetch() in the app ──
     Adds CSRF + a stable idempotency key, retries on transient failure, and
     shows the overlay — so legacy AJAX writes get protected with no per-file
     edits. Reads (GET/HEAD) pass straight through (no spinner flash on polls).
     Opt out per-call with init.__crmRaw = true (e.g. SSE-adjacent calls). */
  window.fetch = function (input, init = {}) {
    const method = (init.method ||
      (typeof input !== 'string' && input && input.method) || 'GET').toUpperCase();
    // Only intercept simple (url, opts) write calls; leave Request objects alone.
    if (init.__crmRaw || !WRITE.test(method) || typeof input !== 'string') {
      return nativeFetch(input, init);
    }
    return fetchWithRetry(input, init, {});
  };

  window.CRM = { uuidv4, fetchWithRetry, withSpinner, showOverlay, hideOverlay, csrfToken };
})();

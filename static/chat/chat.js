/* Argoz CRM — direct chat widget. AJAX for lists/history, WebSocket for live
   send + receive + read-receipts. Markup is server-rendered in base.html; this
   only wires behaviour. No page reloads. */
(function () {
  const CFG = (window.LAYOUT_CFG || {}).chat;
  const chatBtn = document.getElementById('chatBtn');
  if (!CFG || !chatBtn) return;

  const $ = (id) => document.getElementById(id);
  const panel = $('chatPanel'), backdrop = $('chatBackdrop'), badge = $('chatBadge');
  const listBody = $('chatListBody'), usersBody = $('chatUsersBody'), messagesEl = $('chatMessages');
  const meId = String(CFG.meId);

  let convos = [];        // conversation summaries
  let users = [];         // directory for "new chat"
  let unreadTotal = 0;
  let current = null;     // { id, other } of the open thread
  let ws = null, wsRetry = 2000;

  /* ── helpers ── */
  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const headers = () => ({ 'X-CSRFToken': CFG && window.LAYOUT_CFG.csrf || '' });
  function fmtTime(iso) {
    if (!iso) return '';
    const d = new Date(iso); if (isNaN(d)) return '';
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
  function fmtDay(iso) {
    const d = new Date(iso); if (isNaN(d)) return '';
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return 'Today';
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }
  const fetchJSON = (url, opts) =>
    fetch(url, Object.assign({ credentials: 'same-origin', headers: headers() }, opts)).then(r => r.json());

  /* ── badge ── */
  function renderBadge() {
    if (unreadTotal > 0) { badge.textContent = unreadTotal > 99 ? '99+' : unreadTotal; badge.classList.remove('hidden'); }
    else badge.classList.add('hidden');
  }
  function recomputeUnread() {
    unreadTotal = convos.reduce((s, c) => s + (c.unread || 0), 0);
    renderBadge();
  }

  /* ── conversation list ── */
  async function loadList() {
    const d = await fetchJSON(CFG.listUrl).catch(() => null);
    if (!d) return;
    convos = d.conversations || [];
    unreadTotal = d.unread_total || 0;
    renderBadge();
    renderList();
  }
  function renderList() {
    const q = ($('chatSearch').value || '').trim().toLowerCase();
    const rows = convos.filter(c => c.other &&
      (!q || c.other.name.toLowerCase().includes(q) ||
        (c.last_message && (c.last_message.body || '').toLowerCase().includes(q))));
    if (!rows.length) {
      listBody.innerHTML = emptyState('No conversations yet',
        'Start a new chat with the + button above.');
      return;
    }
    listBody.innerHTML = rows.map(c => {
      const lm = c.last_message || {};
      const preview = (lm.from_me ? 'You: ' : '') + (lm.body || '');
      const badgeHtml = c.unread > 0 ? `<span class="chat-row-badge">${c.unread > 99 ? '99+' : c.unread}</span>` : '';
      return `
        <div class="chat-row ${c.unread > 0 ? 'unread' : ''}" data-id="${c.id}">
          <div class="chat-avatar">${esc(c.other.initials)}</div>
          <div class="chat-row-main">
            <div class="chat-row-top">
              <span class="chat-row-name">${esc(c.other.name)}</span>
              <span class="chat-row-time">${lm.created_at ? fmtTime(lm.created_at) : ''}</span>
            </div>
            <div class="chat-row-preview">${esc(preview)}</div>
          </div>
          ${badgeHtml}
        </div>`;
    }).join('');
    listBody.querySelectorAll('.chat-row').forEach(el =>
      el.addEventListener('click', () => openConversation(el.dataset.id)));
  }

  /* ── new chat (user directory) ── */
  async function loadUsers() {
    setView('users');
    usersBody.innerHTML = '<div class="chat-empty"><p>Loading…</p></div>';
    const d = await fetchJSON(CFG.usersUrl).catch(() => null);
    users = (d && d.users) || [];
    renderUsers();
    $('chatUserSearch').focus();
  }
  function renderUsers() {
    const q = ($('chatUserSearch').value || '').trim().toLowerCase();
    const rows = users.filter(u => !q || u.name.toLowerCase().includes(q));
    if (!rows.length) { usersBody.innerHTML = emptyState('No people found', ''); return; }
    usersBody.innerHTML = rows.map(u => `
      <div class="chat-row" data-uid="${u.id}">
        <div class="chat-avatar">${esc(u.initials)}</div>
        <div class="chat-row-main"><div class="chat-row-top"><span class="chat-row-name">${esc(u.name)}</span></div></div>
      </div>`).join('');
    usersBody.querySelectorAll('.chat-row').forEach(el =>
      el.addEventListener('click', () => startConversation(el.dataset.uid)));
  }
  async function startConversation(uid) {
    const fd = new FormData(); fd.append('user_id', uid);
    const d = await fetchJSON(CFG.openUrl, { method: 'POST', body: fd }).catch(() => null);
    if (!d || !d.ok) return;
    upsertConvoSummary(d.conversation);
    showThread(d);
  }

  /* ── thread ── */
  async function openConversation(id) {
    const url = CFG.historyTmpl.replace('00000000-0000-0000-0000-000000000000', id);
    const d = await fetchJSON(url).catch(() => null);
    if (!d || !d.ok) return;
    // history endpoint already marked messages read server-side; tell the
    // sender too so their ticks flip to read without a refresh.
    const c = convos.find(x => x.id === id);
    if (c) { c.unread = 0; recomputeUnread(); renderList(); }
    sendRead(id);
    showThread(d);
  }
  function showThread(d) {
    const c = d.conversation;
    current = { id: c.id, other: c.other };
    $('chatThreadAvatar').textContent = c.other ? c.other.initials : '';
    $('chatThreadName').textContent = c.other ? c.other.name : '';
    $('chatThreadStatus').textContent = '';
    renderMessages(d.messages || []);
    clearStaged();
    setView('thread');
    $('chatInput').focus();
  }
  function renderMessages(msgs) {
    let lastDay = '';
    messagesEl.innerHTML = msgs.map(m => {
      const day = fmtDay(m.created_at);
      const sep = day !== lastDay ? `<div class="chat-day-sep">${esc(day)}</div>` : '';
      lastDay = day;
      return sep + msgBubble(m);
    }).join('');
    scrollToBottom();
  }
  function fmtSize(n) {
    if (!n) return '';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(0) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }
  function attachmentHtml(a) {
    if (a.kind === 'image') {
      return `<a class="chat-att-img" href="${esc(a.url)}" target="_blank" rel="noopener">
        <img src="${esc(a.thumb_url || a.url)}" alt="${esc(a.name)}" loading="lazy"></a>`;
    }
    return `<a class="chat-att-file" href="${esc(a.url)}" target="_blank" rel="noopener" download="${esc(a.name)}">
      <span class="chat-att-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></span>
      <span class="chat-att-meta"><span class="chat-att-name">${esc(a.name)}</span><span class="chat-att-size">${fmtSize(a.size)}</span></span></a>`;
  }
  function msgBubble(m) {
    const mine = String(m.sender.id) === meId;
    const tick = mine ? `<span class="chat-msg-tick ${m.is_read ? 'read' : ''}">${m.is_read ? '✓✓' : '✓'}</span>` : '';
    const atts = (m.attachments || []).map(attachmentHtml).join('');
    const bodyHtml = m.body ? `<div class="chat-msg-bubble">${esc(m.body)}</div>` : '';
    return `
      <div class="chat-msg ${mine ? 'me' : 'them'}" data-mid="${m.id}">
        ${atts}${bodyHtml}
        <div class="chat-msg-meta">${fmtTime(m.created_at)} ${tick}</div>
      </div>`;
  }
  function appendMessage(m) {
    const day = fmtDay(m.created_at);
    const last = messagesEl.querySelector('.chat-day-sep:last-of-type');
    if (!last || last.textContent !== day) {
      messagesEl.insertAdjacentHTML('beforeend', `<div class="chat-day-sep">${esc(day)}</div>`);
    }
    messagesEl.insertAdjacentHTML('beforeend', msgBubble(m));
    scrollToBottom();
  }
  function scrollToBottom() { messagesEl.scrollTop = messagesEl.scrollHeight; }

  /* ── conversation summary upkeep (no full refetch per message) ── */
  function upsertConvoSummary(summary) {
    const i = convos.findIndex(c => c.id === summary.id);
    if (i === -1) convos.unshift(summary);
    else convos[i] = Object.assign(convos[i], summary);
  }
  function applyIncoming(m) {
    const fromMe = String(m.sender.id) === meId;
    const cid = m.conversation_id;
    let c = convos.find(x => x.id === cid);
    if (!c) {
      // First message of a brand-new thread started by the other person.
      c = { id: cid, other: fromMe ? null : m.sender, unread: 0, last_message: null };
      convos.unshift(c);
    }
    c.last_message = { body: m.body, from_me: fromMe, created_at: m.created_at };
    // bump conversation to top
    convos = [c, ...convos.filter(x => x.id !== cid)];
    const viewing = current && current.id === cid && panel.classList.contains('open');
    if (!fromMe && !viewing) c.unread = (c.unread || 0) + 1;
    recomputeUnread();
    renderList();
    if (viewing) {
      appendMessage(m);
      if (!fromMe) sendRead(cid);           // we're looking at it → read instantly
    }
  }
  function applyRead(cid, readerId) {
    if (readerId === meId) {                // our own read on another device
      const c = convos.find(x => x.id === cid);
      if (c) { c.unread = 0; recomputeUnread(); renderList(); }
      return;
    }
    // the other party read our messages → flip ticks if we're viewing the thread
    if (current && current.id === cid) {
      messagesEl.querySelectorAll('.chat-msg.me .chat-msg-tick').forEach(t => {
        t.classList.add('read'); t.textContent = '✓✓';
      });
    }
  }

  /* ── WebSocket ── */
  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}${CFG.wsPath}`);
    ws.onopen = () => { wsRetry = 2000; };
    ws.onmessage = (e) => {
      let data; try { data = JSON.parse(e.data); } catch (_) { return; }
      if (data.type === 'message') applyIncoming(data.message);
      else if (data.type === 'read') applyRead(data.conversation_id, String(data.reader_id));
    };
    ws.onclose = () => { wsRetry = Math.min(wsRetry * 1.5, 15000); setTimeout(connect, wsRetry); };
    ws.onerror = () => { try { ws.close(); } catch (_) {} };
  }
  function wsSend(obj) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj)); }
  function sendRead(cid) { wsSend({ action: 'read', conversation_id: cid }); }

  /* ── composer ── */
  const input = $('chatInput'), composer = $('chatComposer');
  const fileInput = $('chatFileInput'), tray = $('chatAttachTray'), sendBtn = composer.querySelector('.chat-send-btn');
  let staged = [];      // File objects pending upload
  let uploading = false;

  function autoGrow() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 120) + 'px'; }
  input.addEventListener('input', autoGrow);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); composer.requestSubmit(); }
  });

  $('chatAttachBtn').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    staged = staged.concat(Array.from(fileInput.files || [])).slice(0, 10);
    fileInput.value = '';
    renderTray();
  });
  function clearStaged() { staged = []; renderTray(); }
  function renderTray() {
    if (!staged.length) { tray.classList.add('hidden'); tray.innerHTML = ''; return; }
    tray.classList.remove('hidden');
    tray.innerHTML = staged.map((f, i) => {
      const isImg = /^image\//.test(f.type);
      const thumb = isImg ? `<img src="${URL.createObjectURL(f)}" alt="">` :
        `<span class="chat-tray-doc"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></span>`;
      return `<div class="chat-tray-item" title="${esc(f.name)}">${thumb}
        <button type="button" class="chat-tray-rm" data-i="${i}">&times;</button>
        <span class="chat-tray-name">${esc(f.name)}</span></div>`;
    }).join('');
    tray.querySelectorAll('.chat-tray-rm').forEach(b =>
      b.addEventListener('click', () => { staged.splice(+b.dataset.i, 1); renderTray(); }));
  }

  async function uploadStaged(body) {
    if (uploading || !current) return;
    uploading = true; sendBtn.disabled = true;
    const fd = new FormData();
    fd.append('conversation_id', current.id);
    fd.append('body', body);
    staged.forEach(f => fd.append('files', f));
    try {
      const d = await fetchJSON(CFG.uploadUrl, { method: 'POST', body: fd });
      if (d && d.ok) { input.value = ''; autoGrow(); clearStaged(); }
      // rendering happens via the WS echo, same path as text messages
    } catch (_) {} finally { uploading = false; sendBtn.disabled = false; }
  }

  composer.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!current) return;
    const body = input.value.trim();
    if (staged.length) { uploadStaged(body); return; }
    if (!body) return;
    wsSend({ action: 'send', conversation_id: current.id, body });
    input.value = ''; autoGrow();
  });

  /* ── view + panel control ── */
  function setView(v) { panel.setAttribute('data-view', v); }
  function open() {
    const nbP = $('nbPanel'), nbB = $('nbBackdrop');     // one bottom-right panel at a time
    if (nbP) nbP.classList.remove('open');
    if (nbB) nbB.classList.remove('open');
    panel.classList.add('open'); backdrop.classList.add('open');
    setView('list'); current = null;
    loadList();
  }
  function close() { panel.classList.remove('open'); backdrop.classList.remove('open'); }
  chatBtn.addEventListener('click', (e) => { e.stopPropagation(); panel.classList.contains('open') ? close() : open(); });
  backdrop.addEventListener('click', close);
  panel.querySelectorAll('[data-chat-close]').forEach(b => b.addEventListener('click', close));
  panel.querySelectorAll('[data-chat-back]').forEach(b => b.addEventListener('click', () => { setView('list'); current = null; renderList(); }));
  $('chatNewBtn').addEventListener('click', loadUsers);
  $('chatSearch').addEventListener('input', renderList);
  $('chatUserSearch').addEventListener('input', renderUsers);

  function emptyState(title, sub) {
    return `<div class="chat-empty">
      <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      <h4>${esc(title)}</h4>${sub ? `<p>${esc(sub)}</p>` : ''}</div>`;
  }

  /* ── Lightbox ── */
  function openLightbox(url) {
    let lightbox = document.getElementById('chatLightbox');
    if (!lightbox) {
      lightbox = document.createElement('div');
      lightbox.id = 'chatLightbox';
      lightbox.className = 'chat-lightbox';
      lightbox.innerHTML = `
        <span class="chat-lightbox-close">&times;</span>
        <img class="chat-lightbox-content" src="" alt="Enlarged image">
      `;
      document.body.appendChild(lightbox);
      
      lightbox.addEventListener('click', (e) => {
        if (e.target !== lightbox.querySelector('.chat-lightbox-content')) {
          lightbox.classList.remove('open');
        }
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && lightbox.classList.contains('open')) {
          lightbox.classList.remove('open');
        }
      });
    }
    lightbox.querySelector('.chat-lightbox-content').src = url;
    lightbox.classList.add('open');
  }

  messagesEl.addEventListener('click', event => {
    const imgLink = event.target.closest('.chat-att-img');
    if (imgLink) {
      event.preventDefault();
      openLightbox(imgLink.href);
    }
  });

  /* ── boot ── */
  connect();
  loadList();   // prime badge on page load even before the panel is opened
})();

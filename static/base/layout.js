/* Argoz CRM — shell behaviour (header dropdown, sidebar, live notifications).
   Markup is server-rendered by base.html; this only wires interactions and
   pulls notifications from the backend (no localStorage). */
(function () {
  const CFG = window.LAYOUT_CFG || {};
  const $ = (id) => document.getElementById(id);

  /* ── User dropdown ── */
  const userBtn = $('userBtn'), dropdown = $('dropdown');
  if (userBtn && dropdown) {
    userBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = dropdown.classList.toggle('open');
      userBtn.setAttribute('aria-expanded', open);
    });
    document.addEventListener('click', (e) => {
      if (!dropdown.contains(e.target) && e.target !== userBtn) {
        dropdown.classList.remove('open');
        userBtn.setAttribute('aria-expanded', false);
      }
    });
  }

  /* ── Logout (confirm, then hit Django logout) ── */
  const logoutBtn = $('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const go = () => { window.location.href = CFG.logoutUrl; };
      if (window.Swal) {
        Swal.fire({
          title: 'Sign Out?', text: 'Are you sure you want to logout?', icon: 'warning',
          showCancelButton: true, confirmButtonText: 'Yes, sign out', cancelButtonText: 'Cancel',
          reverseButtons: true, focusCancel: true,
        }).then((r) => { if (r.isConfirmed) go(); });
      } else if (confirm('Sign out?')) { go(); }
    });
  }

  /* ── Sidebar ── */
  const menuBtn = $('menuBtn'), sidebar = $('sidebar'), overlay = $('sidebarOverlay'), closeBtn = $('sidebarClose');
  const openSidebar = () => { sidebar.classList.add('open'); overlay.classList.add('show'); };
  const closeSidebar = () => { sidebar.classList.remove('open'); overlay.classList.remove('show'); };
  if (menuBtn) menuBtn.addEventListener('click', () => sidebar.classList.contains('open') ? closeSidebar() : openSidebar());
  if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
  if (overlay) overlay.addEventListener('click', closeSidebar);

  /* ── Notifications (backend-driven) ── */
  const notifBtn = $('notifBtn'), notifPanel = $('notifPanel'), notifBackdrop = $('notifBackdrop'),
        notifBadge = $('notifBadge'), notifBody = $('notifBody'), notifPanelSub = $('notifPanelSub');
  if (!notifBtn) return;

  const headers = () => ({ 'Content-Type': 'application/json', 'X-CSRFToken': CFG.csrf || '' });
  let NOTIFS = [];
  let unreadCount = 0;
  let activeCat = 'all';

  function fmtDate(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) +
        ' at ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    } catch (e) { return iso; }
  }

  function iconClass(n) {
    if ((n.priority || '').toUpperCase() === 'HIGH') return 'overdue';
    if (/APPROVE|FINANCE|CAMPAIGN/i.test(n.code || '')) return 'today-mtg';
    if (/FOLLOW|MEETING/i.test(n.code || '')) return 'followup';
    return 'meeting';
  }

  function getCategory(item) {
    const code = (item.code || '').toUpperCase();
    if (code.startsWith('LEAD_') || code === 'FOLLOWUP_DUE' || code === 'MEETING_DUE' || code === 'STAGE_CHANGED' || code === 'WALKIN_WAITING') {
      return 'leads';
    }
    if (code.startsWith('CAMPAIGN_') || code === 'BUDGET_CHANGED') {
      return 'campaigns';
    }
    return 'system';
  }

  async function fetchNotifs() {
    try {
      const r = await fetch(CFG.notifListUrl, { headers: { 'X-CSRFToken': CFG.csrf || '' }, credentials: 'same-origin' });
      if (r.ok) {
        const d = await r.json();
        NOTIFS = d.items || [];
        unreadCount = d.unread || 0;
      }
    } catch (e) { console.error('notif fetch failed', e); }
    renderPanel();
  }

  async function post(url) {
    try { await fetch(url, { method: 'POST', headers: headers(), credentials: 'same-origin' }); }
    catch (e) { console.error('notif post failed', e); }
  }

  function renderPanel() {
    // Render unread badge count
    if (unreadCount > 0) {
      notifBadge.textContent = unreadCount > 99 ? '99+' : unreadCount;
      notifBadge.classList.remove('hidden');
    } else {
      notifBadge.classList.add('hidden');
    }

    notifPanelSub.textContent = unreadCount
      ? unreadCount + ' pending notification' + (unreadCount > 1 ? 's' : '')
      : 'All caught up';

    const filtered = NOTIFS.filter(item => {
      if (activeCat === 'all') return true;
      return getCategory(item) === activeCat;
    });

    if (!filtered.length) {
      notifBody.innerHTML = `
        <div class="notif-empty">
          <div class="notif-empty-icon"><svg viewBox="0 0 24 24"><path d="M5.5 10.5C5.5 7.19 8.19 4.5 11.5 4.5H12.5C15.81 4.5 18.5 7.19 18.5 10.5V16L20 17.5H4L5.5 16V10.5Z" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
          <h4>All caught up!</h4><p>You have no notifications in this category.</p>
        </div>`;
      return;
    }

    notifBody.innerHTML = `<div class="notif-group-label">${activeCat.toUpperCase()}</div>` + filtered.map((item) => {
      const readClass = item.is_read ? 'read' : 'unread';
      const markReadBtn = !item.is_read
        ? `<button class="notif-del" data-id="${item.id}" title="Mark as Read"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg></button>`
        : '';

      return `
        <div class="notif-item ${readClass}" data-id="${item.id}">
          <div class="notif-icon-wrap ${iconClass(item)}">
            <svg viewBox="0 0 24 24"><path d="M5.5 10.5C5.5 7.19 8.19 4.5 11.5 4.5H12.5C15.81 4.5 18.5 7.19 18.5 10.5V16L20 17.5H4L5.5 16V10.5Z"/><path d="M10 19.5C10 20.6 10.9 21.5 12 21.5C13.1 21.5 14 20.6 14 19.5H10Z"/></svg>
          </div>
          <div class="notif-content">
            <div class="notif-title">${escapeHtml(item.title)}</div>
            ${item.type ? `<div class="notif-type-row"><span class="notif-type-label">${escapeHtml(item.type)}</span></div>` : ''}
            ${item.body ? `<div class="notif-rep-row">${escapeHtml(item.body)}</div>` : ''}
            <div class="notif-date-row"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>${fmtDate(item.created_at)}</div>
          </div>
          ${markReadBtn}
        </div>`;
    }).join('');

    notifBody.querySelectorAll('.notif-del').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        await post(CFG.notifReadTmpl.replace('00000000-0000-0000-0000-000000000000', id));
        const item = NOTIFS.find(x => x.id === id);
        if (item) {
          item.is_read = true;
          unreadCount = Math.max(0, unreadCount - 1);
        }
        renderPanel();
      });
    });
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  const openPanel = () => { notifPanel.classList.add('open'); notifBackdrop.classList.add('open'); };
  const closePanel = () => { notifPanel.classList.remove('open'); notifBackdrop.classList.remove('open'); };
  notifBtn.addEventListener('click', (e) => { e.stopPropagation(); notifPanel.classList.contains('open') ? closePanel() : openPanel(); });
  notifBackdrop.addEventListener('click', closePanel);
  $('notifClose').addEventListener('click', closePanel);
  $('notifClearAll').addEventListener('click', async () => {
    await post(CFG.notifReadAllUrl);
    NOTIFS.forEach(x => { x.is_read = true; });
    unreadCount = 0;
    renderPanel();
  });

  const catContainer = $('notifCategories');
  if (catContainer) {
    catContainer.querySelectorAll('.notif-cat-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        catContainer.querySelectorAll('.notif-cat-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeCat = tab.dataset.cat;
        renderPanel();
      });
    });
  }

  fetchNotifs();
  setInterval(fetchNotifs, 60000);
})();

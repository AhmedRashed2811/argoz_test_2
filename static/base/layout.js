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
        notifBadge = $('notifBadge'), notifBody = $('notifBody'), notifPanelSub = $('notifPanelSub'),
        notifSearch = $('notifSearch');
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

  function cardClass(n) {
    const priority = (n.priority || '').toUpperCase();
    const code = (n.code || '').toUpperCase();
    let cls = '';
    if (priority === 'HIGH') {
      cls += ' notif-priority-high';
    } else if (priority === 'LOW') {
      cls += ' notif-priority-low';
    }
    
    if (code === 'SLA_WARNING' || code === 'MANUAL_DISTRIBUTION_REQUIRED') {
      cls += ' notif-sla-warning';
    } else if (code === 'SLA_BREACHED') {
      cls += ' notif-sla-breached';
    } else if (code.startsWith('LEAD_') || code.startsWith('SLA_') || code.startsWith('FROZEN_') || code.startsWith('BROKER_') ||
        code === 'FOLLOWUP_DUE' || code === 'MEETING_DUE' || code === 'STAGE_CHANGED' || code === 'WALKIN_WAITING') {
      cls += ' notif-type-lead';
    } else if (code.startsWith('CAMPAIGN_') || code === 'BUDGET_CHANGED') {
      cls += ' notif-type-campaign';
    } else {
      cls += ' notif-type-system';
    }
    return cls;
  }

  function matchCategory(item, cat) {
    const code = (item.code || '').toUpperCase();
    const isLeadCat = code.startsWith('LEAD_') || code.startsWith('SLA_') || code.startsWith('FROZEN_') || code.startsWith('BROKER_') ||
        code === 'FOLLOWUP_DUE' || code === 'MEETING_DUE' || code === 'STAGE_CHANGED' || code === 'WALKIN_WAITING' || code === 'MANUAL_DISTRIBUTION_REQUIRED';
    
    if (cat === 'all') return true;
    if (cat === 'campaigns') return code.startsWith('CAMPAIGN_') || code === 'BUDGET_CHANGED';
    if (cat === 'system') return !isLeadCat && !code.startsWith('CAMPAIGN_') && code !== 'BUDGET_CHANGED';
    
    // Leads category: contains all lead-related notifications
    if (cat === 'leads') return isLeadCat;
    
    // Tasks: reminders and lead assigned
    const isReminder = code === 'FOLLOWUP_DUE' || code === 'MEETING_DUE' || code === 'SLA_WARNING' || code === 'FROZEN_LEAD_RETURN';
    const isAssigned = code === 'LEAD_ASSIGNED' || code === 'LEAD_REASSIGNED_SLA';
    if (cat === 'tasks') return isReminder || isAssigned;
    
    // Reminders: only reminders
    if (cat === 'reminders') return isReminder;
    
    // Meetings: only meetings
    if (cat === 'meetings') return code.includes('MEETING');
    
    // Followups: only followups
    if (cat === 'followups') return code.includes('FOLLOWUP');
    
    return false;
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
    try { await fetch(url, { method: 'POST', headers: headers(), credentials: 'same-origin', keepalive: true }); }
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

    // Hide campaigns filter button if there are no notifications for it
    const hasCampaigns = NOTIFS.some(item => matchCategory(item, 'campaigns'));
    const campaignsTab = catContainer ? catContainer.querySelector('[data-cat="campaigns"]') : null;
    if (campaignsTab) {
      if (hasCampaigns) {
        campaignsTab.style.display = '';
      } else {
        campaignsTab.style.display = 'none';
        if (activeCat === 'campaigns') {
          activeCat = 'all';
          catContainer.querySelectorAll('.notif-cat-tab').forEach(t => t.classList.remove('active'));
          const allTab = catContainer.querySelector('[data-cat="all"]');
          if (allTab) allTab.classList.add('active');
        }
      }
    }

    const searchVal = notifSearch ? notifSearch.value.trim().toLowerCase() : '';
    const filtered = NOTIFS.filter(item => {
      if (!matchCategory(item, activeCat)) return false;
      if (searchVal) {
        const titleMatch = (item.title || '').toLowerCase().includes(searchVal);
        const bodyMatch = (item.body || '').toLowerCase().includes(searchVal);
        const typeMatch = (item.type || '').toLowerCase().includes(searchVal);
        const leadNameMatch = (item.lead_name || '').toLowerCase().includes(searchVal);
        const leadPhoneMatch = (item.lead_phone || '').toLowerCase().includes(searchVal);
        return titleMatch || bodyMatch || typeMatch || leadNameMatch || leadPhoneMatch;
      }
      return true;
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
        ? `<button class="notif-mark-read" data-id="${item.id}" title="Mark as Read"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg></button>`
        : '';
      const deleteBtn = `<button class="notif-delete-btn" data-id="${item.id}" title="Delete Notification"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg></button>`;

      let actionUrl = '';
      if (item.code !== 'SLA_BREACHED') {
        if (item.code === 'MANUAL_DISTRIBUTION_REQUIRED') {
          actionUrl = `/leads/manual-distribution/?search=${item.related_id}`;
        } else if (item.related_type === 'Lead') {
          actionUrl = `/leads/?search=${item.related_id}`;
        } else if (item.related_type === 'Campaign') {
          actionUrl = (CFG.canReviewFinance)
            ? `/finance/approvals/?search=${item.related_id}`
            : `/marketing/?search=${item.related_id}`;
        }
      }
      const actionBtn = actionUrl
        ? `<a href="${actionUrl}" class="notif-action-btn">View ${escapeHtml(item.related_type)}</a>`
        : '';
      const leadInfo = (item.lead_name || item.lead_phone)
        ? `<div class="notif-lead-info">
             <div class="notif-lead-badge">
               <svg class="notif-lead-icon" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
               <span class="notif-lead-name">${escapeHtml(item.lead_name)}</span>
             </div>
             ${item.lead_phone ? `<div class="notif-lead-phone">📞 ${escapeHtml(item.lead_phone)}</div>` : ''}
           </div>`
        : '';

      return `
        <div class="notif-item ${readClass}${cardClass(item)}" data-id="${item.id}" tabindex="0">
          <div class="notif-icon-wrap ${iconClass(item)}">
            <svg viewBox="0 0 24 24"><path d="M5.5 10.5C5.5 7.19 8.19 4.5 11.5 4.5H12.5C15.81 4.5 18.5 7.19 18.5 10.5V16L20 17.5H4L5.5 16V10.5Z"/><path d="M10 19.5C10 20.6 10.9 21.5 12 21.5C13.1 21.5 14 20.6 14 19.5H10Z"/></svg>
          </div>
          <div class="notif-content">
            <div class="notif-title">${escapeHtml(item.title)}</div>
            ${item.type ? `<div class="notif-type-row"><span class="notif-type-label">${escapeHtml(item.type)}</span></div>` : ''}
            ${item.body ? `<div class="notif-rep-row">${escapeHtml(item.body)}</div>` : ''}
            <div class="notif-date-row"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>${fmtDate(item.created_at)}</div>
            ${leadInfo}
            ${actionBtn}
          </div>
          <div class="notif-actions-panel">
            ${markReadBtn}
            ${deleteBtn}
          </div>
        </div>`;
    }).join('');

    const markAsRead = async (id) => {
      const item = NOTIFS.find(x => x.id === id);
      if (!item || item.is_read) return;
      try {
        await post(CFG.notifReadTmpl.replace('00000000-0000-0000-0000-000000000000', id));
        item.is_read = true;
        unreadCount = Math.max(0, unreadCount - 1);
        renderPanel();
      } catch (err) {
        console.error("Failed to mark notification as read", err);
      }
    };

    const deleteNotif = async (id) => {
      try {
        await post(CFG.notifDeleteTmpl.replace('00000000-0000-0000-0000-000000000000', id));
        const idx = NOTIFS.findIndex(x => x.id === id);
        if (idx !== -1) {
          if (!NOTIFS[idx].is_read) {
            unreadCount = Math.max(0, unreadCount - 1);
          }
          NOTIFS.splice(idx, 1);
        }
        renderPanel();
      } catch (err) {
        console.error("Failed to delete notification", err);
      }
    };

    notifBody.querySelectorAll('.notif-item').forEach((itemEl) => {
      itemEl.addEventListener('click', async (e) => {
        const id = itemEl.dataset.id;
        if (e.target.closest('.notif-delete-btn')) {
          e.stopPropagation();
          await deleteNotif(id);
          return;
        }
        const item = NOTIFS.find(x => x.id === id);
        if (item && !item.is_read) {
          await markAsRead(id);
        }
      });

      const triggerRead = async () => {
        const id = itemEl.dataset.id;
        const item = NOTIFS.find(x => x.id === id);
        if (item && !item.is_read) {
          await markAsRead(id);
        }
      };
      itemEl.addEventListener('keydown', triggerRead);
      itemEl.addEventListener('input', triggerRead);
    });
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  const openPanel = () => { notifPanel.classList.add('open'); notifBackdrop.classList.add('open'); if (notifSearch) notifSearch.focus(); };
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

  if (notifSearch) {
    notifSearch.addEventListener('input', renderPanel);
  }

  fetchNotifs();

  /* ── SSE: push new notifications without polling ── */
  if (CFG.sseUrl && typeof EventSource !== 'undefined') {
    let sse;
    let retryTimer = null;
    let retryDelay = 2000;

    function connectSSE() {
      if (sse) { sse.close(); sse = null; }
      sse = new EventSource(CFG.sseUrl, { withCredentials: true });

      sse.onopen = () => { retryDelay = 2000; };

      sse.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          if (!payload.id) return;
          if (NOTIFS.some(n => n.id === payload.id)) return;
          NOTIFS.unshift({
            id: payload.id,
            title: payload.title || '',
            body: payload.body || '',
            code: payload.code || '',
            type: payload.type || payload.code || '',
            priority: payload.priority || 'NORMAL',
            related_type: payload.related_type || null,
            related_id: payload.related_id || null,
            lead_name: payload.lead_name || '',
            lead_phone: payload.lead_phone || '',
            created_at: payload.created_at || new Date().toISOString(),
            is_read: false,
          });
          unreadCount += 1;
          renderPanel();
        } catch (_) {}
      };

      sse.onerror = () => {
        sse.close();
        sse = null;
        retryDelay = Math.min(retryDelay * 1.5, 15000);
        if (retryTimer) clearTimeout(retryTimer);
        retryTimer = setTimeout(connectSSE, retryDelay);
      };
    }

    connectSSE();

    // Re-establish on tab focus in case connection silently dropped
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && (!sse || sse.readyState === EventSource.CLOSED)) {
        retryDelay = 2000;
        connectSSE();
      }
    });
  } else {
    setInterval(fetchNotifs, 60000);
  }
 })();

/* ════════════════════════════════════════
   DATA STORE — server-backed (replaces mock)
════════════════════════════════════════ */
const CFG = window.USER_CFG || {};
let ROLES = [];
let PERMISSIONS = [];
let USERS = [];
let nextId = 1;
let currentPage = 1;
let totalPages = 1;
let PER_PAGE = 10;
let sortField = null, sortAscMap = {};
let activeNameFilters = new Set(), activeRoleFilters = new Set(), activeTeamFilters = new Set(), activeOverridesFilters = new Set(), activeStatusFilters = new Set();
let filterNameOpen = false, filterRoleOpen = false, filterTeamOpen = false, filterOverridesOpen = false, filterStatusOpen = false;

function withId(tmpl, id) { return (tmpl || '').replace('/0/', '/' + id + '/'); }
function _headers() { return { 'Content-Type': 'application/json', 'X-CSRFToken': CFG.csrf || '' }; }

/* ════════════════════════════════════════
   API (AJAX → Django)
════════════════════════════════════════ */
async function fetchUsers() {
  try {
    const r = await fetch(CFG.listUrl, { headers: { 'X-CSRFToken': CFG.csrf || '' }, credentials: 'same-origin' });
    if (r.ok) { const d = await r.json(); USERS = d.users || []; ROLES = d.roles || []; }
  } catch (e) { console.error('fetchUsers failed:', e); }
  return USERS;
}
async function apiPost(url) {
  const r = await fetch(url, { method: 'POST', headers: _headers(), credentials: 'same-origin' });
  let data = {}; try { data = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(data.error || ('Request failed (' + r.status + ')'));
  return data;
}
// Create/Edit happen on the dedicated form page; modal helpers are retained but dormant.
async function apiCreateUser() { throw new Error('Use the create form'); }
async function apiEditUser() { throw new Error('Use the edit form'); }
async function apiDeactivate(id) { await apiPost(withId(CFG.deactivateTmpl, id)); await fetchUsers(); }
async function apiActivate(id) { await apiPost(withId(CFG.activateTmpl, id)); await fetchUsers(); }

/* ════════════════════════════════════════
   KPIs
════════════════════════════════════════ */
function renderKPIs() {
  document.getElementById('kpiTotal').textContent    = USERS.length;
  document.getElementById('kpiActive').textContent   = USERS.filter(u => u.is_active).length;
  document.getElementById('kpiInactive').textContent = USERS.filter(u => !u.is_active).length;
  document.getElementById('kpiOverrides').textContent = USERS.filter(u => u.permission_overrides_count > 0).length;
}

/* ════════════════════════════════════════
   RENDER TABLE
════════════════════════════════════════ */
function renderUsers() {
  renderKPIs();
  const q = (document.getElementById('searchInput').value || '').toLowerCase();
  let filtered = USERS.filter(u => {
    if (q && ![u.first_name, u.last_name, u.email, u.profile?.job_title, u.profile?.department].some(v => (v||'').toLowerCase().includes(q))) return false;
    if (activeNameFilters.size && !activeNameFilters.has(`${u.first_name} ${u.last_name}`)) return false;
    if (activeRoleFilters.size && !activeRoleFilters.has(u.profile?.default_role?.name || 'None')) return false;
    if (activeTeamFilters.size && !u.team_memberships?.some(m => activeTeamFilters.has(m.team.name))) return false;
    if (activeOverridesFilters.size) {
      const key = u.permission_overrides_count > 0 ? 'has' : 'none';
      if (!activeOverridesFilters.has(key)) return false;
    }
    if (activeStatusFilters.size && !activeStatusFilters.has(u.is_active ? 'active' : 'inactive')) return false;
    return true;
  });

  // Sort
  if (sortField && sortAscMap[sortField] != null) {
    const asc = sortAscMap[sortField];
    filtered = [...filtered].sort((a, b) => {
      let va, vb;
      if (sortField === 'name') { va = `${a.first_name} ${a.last_name}`; vb = `${b.first_name} ${b.last_name}`; }
      else if (sortField === 'role') { va = a.profile?.default_role?.name || ''; vb = b.profile?.default_role?.name || ''; }
      else if (sortField === 'overrides') { va = a.permission_overrides_count; vb = b.permission_overrides_count; return asc ? va - vb : vb - va; }
      else { va = ''; vb = ''; }
      return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }

  const hint = document.getElementById('searchHint');
  hint.textContent = (q || activeNameFilters.size || activeRoleFilters.size || activeTeamFilters.size || activeOverridesFilters.size || activeStatusFilters.size)
    ? `${filtered.length} result${filtered.length !== 1 ? 's' : ''} found` : '';

  const total = filtered.length;
  totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  if (currentPage > totalPages) currentPage = totalPages;
  const slice = filtered.slice((currentPage - 1) * PER_PAGE, currentPage * PER_PAGE);

  const tbody = document.getElementById('tableBody');
  if (!slice.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><h3>No users found</h3><p>Try a different search term.</p></div></td></tr>`;
    document.getElementById('pgInfo').textContent = 'No results';
    renderPagination(0);
    return;
  }

  tbody.innerHTML = slice.map(u => {
    const roleName = u.profile?.default_role?.name || '<span style="color:var(--clr-gray);font-style:italic">None Assigned</span>';
    const statusCls = u.is_active ? 'active' : 'inactive';
    const statusLabel = u.is_active ? 'Active' : 'Inactive';
    const overrideCls = u.permission_overrides_count > 0 ? 'has' : 'none';
    const overrideLabel = u.permission_overrides_count > 0
      ? `⚡ ${u.permission_overrides_count} custom`
      : '0 overrides';
    const teamHtml = u.team_memberships?.length
      ? u.team_memberships.map(m => `<span class="team-badge">${m.team.name}</span>`).join('')
      : `<span style="color:var(--clr-gray);font-size:.82rem">No Active Teams</span>`;
    const toggleBtn = u.is_active
      ? (CFG.canDelete ? `<button class="action-btn deactivate" onclick="openConfirm(${u.id},'deactivate')"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>Deactivate</button>` : '')
      : (CFG.canUpdate ? `<button class="action-btn activate" onclick="openConfirm(${u.id},'activate')"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>Activate</button>` : '');

    return `<tr>
      <td>
        <div class="user-identity">
          <div>
            <div class="user-name">${u.first_name} ${u.last_name}</div>
            <div class="user-email">${u.email}</div>
            ${u.phone ? `<div class="user-job">📞 ${u.phone}</div>` : ''}
          </div>
        </div>
      </td>
      <td><span class="role-badge">${roleName}</span></td>
      <td><div style="display:flex;flex-wrap:wrap;gap:2px;justify-content:center">${teamHtml}</div></td>
      <td><span class="overrides-badge ${overrideCls}">${overrideLabel}</span></td>
      <td><span class="status-badge ${statusCls}"><span class="dot"></span>${statusLabel}</span></td>
      <td>
        <div class="action-btns">
          ${CFG.canUpdate ? `<button class="action-btn edit" onclick="openEdit(${u.id})"><svg viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>Edit</button>` : ''}
          ${CFG.canManageRoles ? `<button class="action-btn matrix" onclick="goMatrix(${u.id})"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>Matrix</button>` : ''}
          ${CFG.canManageRoles ? `<button class="action-btn preview" onclick="goPreview(${u.id})"><svg viewBox="0 0 24 24"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/></svg>Preview</button>` : ''}
          ${toggleBtn}
        </div>
      </td>
    </tr>`;
  }).join('');

  document.getElementById('pgInfo').textContent = total
    ? `Showing ${(currentPage - 1) * PER_PAGE + 1}–${Math.min(currentPage * PER_PAGE, total)} of ${total}`
    : 'No results';
  renderPagination(total);
}

function renderPagination(total) {
  totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  if (currentPage > totalPages) currentPage = totalPages;
  const bar = document.getElementById('paginationBar');
  bar.style.display = totalPages <= 1 ? 'none' : 'flex';
  document.getElementById('pgFirst').disabled = currentPage === 1;
  document.getElementById('pgPrev').disabled  = currentPage === 1;
  document.getElementById('pgNext').disabled  = currentPage === totalPages;
  document.getElementById('pgLast').disabled  = currentPage === totalPages;
  const nums = document.getElementById('pgNumbers'); nums.innerHTML = '';
  let s = Math.max(1, currentPage - 2), e = Math.min(totalPages, s + 4); s = Math.max(1, e - 4);
  if (s > 1) { addPgNum(nums, 1); if (s > 2) nums.insertAdjacentHTML('beforeend', '<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>'); }
  for (let i = s; i <= e; i++) addPgNum(nums, i);
  if (e < totalPages) { if (e < totalPages - 1) nums.insertAdjacentHTML('beforeend', '<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>'); addPgNum(nums, totalPages); }
}
function addPgNum(container, n) {
  const b = document.createElement('button');
  b.className = 'pg-btn' + (n === currentPage ? ' active' : '');
  b.textContent = n;
  b.onclick = () => goPage(n);
  container.appendChild(b);
}
function goPage(p) {
  if (p < 1 || p > totalPages) return;
  currentPage = p; renderUsers();
}
function changePerPage(val) {
  PER_PAGE = parseInt(val, 10);
  currentPage = 1;
  renderUsers();
}

/* ════════════════════════════════════════
   SEARCH
════════════════════════════════════════ */
document.getElementById('searchInput').addEventListener('input', () => { currentPage = 1; renderUsers(); });

/* ════════════════════════════════════════
   SORT
════════════════════════════════════════ */
const SORT_BTNS = { sortNameBtn: 'name', sortRoleBtn: 'role', sortOverridesBtn: 'overrides' };
function applySortBtn(field, btnId) {
  const prev = sortAscMap[field];
  if (prev == null) sortAscMap[field] = true;
  else if (prev === true) sortAscMap[field] = false;
  else { delete sortAscMap[field]; }
  sortField = sortAscMap[field] != null ? field : null;
  Object.keys(SORT_BTNS).forEach(id => {
    const b = document.getElementById(id); if (!b) return;
    b.classList.remove('active-sort');
    b.querySelector('svg').innerHTML = '<path d="M3 6h18M7 12h10M11 18h2"/>';
  });
  if (sortField) {
    const b = document.getElementById(btnId);
    if (b) {
      b.classList.add('active-sort');
      b.querySelector('svg').innerHTML = sortAscMap[field]
        ? '<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 4 20 7 17 10" style="stroke-width:1.8"/>'
        : '<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 14 20 17 17 20" style="stroke-width:1.8"/>';
    }
  }
  currentPage = 1; renderUsers();
}
Object.entries(SORT_BTNS).forEach(([btnId, field]) => document.getElementById(btnId)?.addEventListener('click', () => applySortBtn(field, btnId)));

/* ════════════════════════════════════════
   FILTERS
════════════════════════════════════════ */
function closeAllFilters() {
  filterNameOpen = filterRoleOpen = filterTeamOpen = filterOverridesOpen = filterStatusOpen = false;
  ['filterNameDropdown','filterRoleDropdown','filterTeamDropdown','filterOverridesDropdown','filterStatusDropdown'].forEach(id => document.getElementById(id)?.classList.remove('open'));
}
function positionDropdown(ddId, btnId) {
  const dd = document.getElementById(ddId), r = document.getElementById(btnId).getBoundingClientRect();
  dd.classList.add('open');
  dd.style.top = r.bottom + 4 + 'px';
  dd.style.left = Math.min(r.left, window.innerWidth - dd.offsetWidth - 8) + 'px';
}

function renderNameFilterList() {
  const q = (document.getElementById('filterNameSearch')?.value || '').toLowerCase();
  const names = [...new Set(USERS.map(u => `${u.first_name} ${u.last_name}`))].sort().filter(n => n.toLowerCase().includes(q));
  document.getElementById('filterNameList').innerHTML = names.map(n =>
    `<label class="filter-item"><input type="checkbox" value="${n}" ${activeNameFilters.has(n)?'checked':''} onchange="if(this.checked)activeNameFilters.add(this.value);else activeNameFilters.delete(this.value);currentPage=1;renderUsers()"><span style="font-size:.83rem;color:var(--clr-text)">${n}</span></label>`).join('');
}
function renderRoleFilterList() {
  const roles = [...new Set(USERS.map(u => u.profile?.default_role?.name || 'None'))].sort();
  document.getElementById('filterRoleList').innerHTML = roles.map(r =>
    `<label class="filter-item"><input type="checkbox" value="${r}" ${activeRoleFilters.has(r)?'checked':''} onchange="if(this.checked)activeRoleFilters.add(this.value);else activeRoleFilters.delete(this.value);currentPage=1;renderUsers()"><span style="font-size:.83rem;color:var(--clr-text)">${r}</span></label>`).join('');
}
function renderTeamFilterList() {
  const teams = [...new Set(USERS.flatMap(u => u.team_memberships?.map(m => m.team.name) || []))].sort();
  document.getElementById('filterTeamList').innerHTML = teams.map(t =>
    `<label class="filter-item"><input type="checkbox" value="${t}" ${activeTeamFilters.has(t)?'checked':''} onchange="if(this.checked)activeTeamFilters.add(this.value);else activeTeamFilters.delete(this.value);currentPage=1;renderUsers()"><span style="font-size:.83rem;color:var(--clr-text)">${t}</span></label>`).join('');
}
function renderOverridesFilterList() {
  const opts = [{val:'has',label:'Has Overrides'},{val:'none',label:'No Overrides'}];
  document.getElementById('filterOverridesList').innerHTML = opts.map(o =>
    `<label class="filter-item"><input type="checkbox" value="${o.val}" ${activeOverridesFilters.has(o.val)?'checked':''} onchange="if(this.checked)activeOverridesFilters.add(this.value);else activeOverridesFilters.delete(this.value);currentPage=1;renderUsers()"><span style="font-size:.83rem;color:var(--clr-text)">${o.label}</span></label>`).join('');
}
function renderStatusFilterList() {
  const opts = [{val:'active',label:'Active'},{val:'inactive',label:'Inactive'}];
  document.getElementById('filterStatusList').innerHTML = opts.map(o =>
    `<label class="filter-item"><input type="checkbox" value="${o.val}" ${activeStatusFilters.has(o.val)?'checked':''} onchange="if(this.checked)activeStatusFilters.add(this.value);else activeStatusFilters.delete(this.value);currentPage=1;renderUsers()"><span style="font-size:.83rem;color:var(--clr-text)">${o.label}</span></label>`).join('');
}

// Wire filter buttons
document.getElementById('filterNameBtn').addEventListener('click', e => { e.stopPropagation(); const c=filterNameOpen; closeAllFilters(); if(c)return; filterNameOpen=true; positionDropdown('filterNameDropdown','filterNameBtn'); renderNameFilterList(); });
document.getElementById('filterNameSearch').addEventListener('input', () => renderNameFilterList());
document.getElementById('filterNameSelectAll').addEventListener('click', e => { e.stopPropagation(); USERS.forEach(u=>activeNameFilters.add(`${u.first_name} ${u.last_name}`)); renderNameFilterList(); currentPage=1; renderUsers(); });
document.getElementById('filterNameClearAll').addEventListener('click', e => { e.stopPropagation(); activeNameFilters.clear(); renderNameFilterList(); currentPage=1; renderUsers(); });

document.getElementById('filterRoleBtn').addEventListener('click', e => { e.stopPropagation(); const c=filterRoleOpen; closeAllFilters(); if(c)return; filterRoleOpen=true; positionDropdown('filterRoleDropdown','filterRoleBtn'); renderRoleFilterList(); });
document.getElementById('filterRoleSelectAll').addEventListener('click', e => { e.stopPropagation(); [...new Set(USERS.map(u=>u.profile?.default_role?.name||'None'))].forEach(r=>activeRoleFilters.add(r)); renderRoleFilterList(); currentPage=1; renderUsers(); });
document.getElementById('filterRoleClearAll').addEventListener('click', e => { e.stopPropagation(); activeRoleFilters.clear(); renderRoleFilterList(); currentPage=1; renderUsers(); });

document.getElementById('filterTeamBtn').addEventListener('click', e => { e.stopPropagation(); const c=filterTeamOpen; closeAllFilters(); if(c)return; filterTeamOpen=true; positionDropdown('filterTeamDropdown','filterTeamBtn'); renderTeamFilterList(); });
document.getElementById('filterTeamSelectAll').addEventListener('click', e => { e.stopPropagation(); USERS.flatMap(u=>u.team_memberships?.map(m=>m.team.name)||[]).forEach(t=>activeTeamFilters.add(t)); renderTeamFilterList(); currentPage=1; renderUsers(); });
document.getElementById('filterTeamClearAll').addEventListener('click', e => { e.stopPropagation(); activeTeamFilters.clear(); renderTeamFilterList(); currentPage=1; renderUsers(); });

document.getElementById('filterOverridesBtn').addEventListener('click', e => { e.stopPropagation(); const c=filterOverridesOpen; closeAllFilters(); if(c)return; filterOverridesOpen=true; positionDropdown('filterOverridesDropdown','filterOverridesBtn'); renderOverridesFilterList(); });
document.getElementById('filterOverridesSelectAll').addEventListener('click', e => { e.stopPropagation(); ['has','none'].forEach(v=>activeOverridesFilters.add(v)); renderOverridesFilterList(); currentPage=1; renderUsers(); });
document.getElementById('filterOverridesClearAll').addEventListener('click', e => { e.stopPropagation(); activeOverridesFilters.clear(); renderOverridesFilterList(); currentPage=1; renderUsers(); });

document.getElementById('filterStatusBtn').addEventListener('click', e => { e.stopPropagation(); const c=filterStatusOpen; closeAllFilters(); if(c)return; filterStatusOpen=true; positionDropdown('filterStatusDropdown','filterStatusBtn'); renderStatusFilterList(); });
document.getElementById('filterStatusSelectAll').addEventListener('click', e => { e.stopPropagation(); ['active','inactive'].forEach(v=>activeStatusFilters.add(v)); renderStatusFilterList(); currentPage=1; renderUsers(); });
document.getElementById('filterStatusClearAll').addEventListener('click', e => { e.stopPropagation(); activeStatusFilters.clear(); renderStatusFilterList(); currentPage=1; renderUsers(); });

// Close dropdowns on outside click
document.addEventListener('click', e => {
  const ids = ['filterNameBtn','filterNameDropdown','filterRoleBtn','filterRoleDropdown','filterTeamBtn','filterTeamDropdown','filterOverridesBtn','filterOverridesDropdown','filterStatusBtn','filterStatusDropdown'];
  if (!ids.some(id => document.getElementById(id)?.contains(e.target))) closeAllFilters();
});

/* ════════════════════════════════════════
   MODAL HELPERS (retained; create/edit live on the form page)
════════════════════════════════════════ */
function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }
let editUserId = null;

/* ════════════════════════════════════════
   NAVIGATION → Django pages
════════════════════════════════════════ */
function openEdit(id) { window.location.href = withId(CFG.editTmpl, id); }
function goMatrix(id) { window.location.href = withId(CFG.matrixTmpl, id); }
function goPreview(id) { window.location.href = withId(CFG.previewTmpl, id); }

/* ════════════════════════════════════════
   CONFIRM ACTION (SweetAlert2)
════════════════════════════════════════ */
async function openConfirm(id, action) {
  const u = USERS.find(u => u.id === id);
  if (!u) return;
  const isDeactivate = action === 'deactivate';

  const result = await Swal.fire({
    title: isDeactivate ? `Deactivate ${u.first_name}?` : `Activate ${u.first_name}?`,
    text: isDeactivate
      ? `${u.email} will lose access to the system immediately.`
      : `${u.email} will regain full access based on their role.`,
    icon: isDeactivate ? 'warning' : 'question',
    showCancelButton: true,
    confirmButtonText: isDeactivate ? 'Deactivate' : 'Activate',
    cancelButtonText: 'Cancel',
    reverseButtons: true,
    confirmButtonColor: isDeactivate ? '#c0392b' : '#27ae60',
    cancelButtonColor: '#9a958f',
  });

  if (!result.isConfirmed) return;

  try {
    if (isDeactivate) {
      await apiDeactivate(id);
      renderUsers();
      showToast('info', 'User Deactivated', `${u.email} has been deactivated.`);
    } else {
      await apiActivate(id);
      renderUsers();
      showToast('success', 'User Activated', `${u.email} is now active.`);
    }
  } catch(e) {
    showToast('error', 'Error', e.message || 'Action failed. Please try again.');
  }
}

/* ════════════════════════════════════════
   TOAST
════════════════════════════════════════ */
function showToast(type, title, msg) {
  const container = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = {
    success: `<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`,
    error:   `<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
    info:    `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
  };
  el.innerHTML = `<div class="toast-icon">${icons[type]||icons.info}</div><div class="toast-body"><div class="toast-title">${title}</div><div class="toast-msg">${msg}</div></div>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

/* ════════════════════════════════════════
   EVENT WIRING
════════════════════════════════════════ */
document.getElementById('closeConfirmBtn').addEventListener('click', () => closeModal('confirmModal'));
document.getElementById('cancelConfirmBtn').addEventListener('click', () => closeModal('confirmModal'));
['confirmModal'].forEach(id => {
  document.getElementById(id).addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(id); });
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeModal('confirmModal'); } });

/* ════════════════════════════════════════
   INIT
════════════════════════════════════════ */
fetchUsers().then(renderUsers);
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') fetchUsers().then(renderUsers); });

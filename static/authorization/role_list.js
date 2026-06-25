// JavaScript for Roles list page
let ROLES_DATA = [];

// Sort and Filter States
let sortField = null;
let sortAscMap = {};
let activeNameFilters = new Set();
let activeTypeFilters = new Set();
let activeStatusFilters = new Set();

let filterNameOpen = false;
let filterTypeOpen = false;
let filterStatusOpen = false;

async function loadRoles() {
  const container = document.getElementById('role-table-body');
  if (!container) return;

  try {
    const res = await fetch(window.API_LIST_URL);
    if (!res.ok) throw new Error('Failed to load roles');
    const data = await res.json();
    ROLES_DATA = data.roles || [];
    renderRoles();
  } catch (err) {
    console.error('Failed to load roles list', err);
    showToast('error', 'Error', 'Failed to retrieve roles list.');
    container.innerHTML = `<tr><td colspan="6" class="empty-state"><h3>Failed to Load</h3><p>Could not communicate with the server.</p></td></tr>`;
  }
}

function renderRoles() {
  const container = document.getElementById('role-table-body');
  if (!container) return;

  let filtered = [...ROLES_DATA];

  // Apply filters
  if (activeNameFilters.size) {
    filtered = filtered.filter(r => activeNameFilters.has(r.name));
  }
  if (activeTypeFilters.size) {
    filtered = filtered.filter(r => {
      const typeStr = r.is_system_default ? 'System' : 'Custom';
      return activeTypeFilters.has(typeStr);
    });
  }
  if (activeStatusFilters.size) {
    filtered = filtered.filter(r => activeStatusFilters.has(r.is_active ? 'active' : 'inactive'));
  }

  // Apply Sorting
  if (sortField && sortAscMap[sortField] != null) {
    const asc = sortAscMap[sortField];
    filtered.sort((a, b) => {
      let va, vb;
      if (sortField === 'name') {
        va = a.name || '';
        vb = b.name || '';
      } else if (sortField === 'member') {
        va = a.member_count ?? 0;
        vb = b.member_count ?? 0;
        return asc ? va - vb : vb - va;
      } else {
        va = ''; vb = '';
      }
      return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }

  if (filtered.length === 0) {
    container.innerHTML = `<tr><td colspan="6" class="empty-state"><h3>No Roles Found</h3><p>No matching roles found.</p></td></tr>`;
    return;
  }

  container.innerHTML = filtered.map(role => {
    const typeBadge = role.is_system_default
      ? `<span class="badge badge-system">System</span>`
      : `<span class="badge badge-custom">Custom</span>`;

    const statusBadge = role.is_active
      ? `<span class="status-badge active"><span class="dot"></span> Active</span>`
      : `<span class="status-badge inactive"><span class="dot"></span> Inactive</span>`;

    const actions = [];
    if (window.PERMS.can_manage) {
      actions.push(`<a href="${window.URLS.edit.replace('00000000-0000-0000-0000-000000000000', role.id)}" class="action-btn edit">Edit</a>`);
      
      if (!role.is_system_default) {
        if (role.is_active) {
          actions.push(`<button onclick="confirmToggle('${role.id}', 'deactivate', 'Deactivate role &quot;${role.name}&quot;?')" class="action-btn deactivate">Deactivate</button>`);
        } else {
          actions.push(`<button onclick="confirmToggle('${role.id}', 'activate', 'Activate role &quot;${role.name}&quot;?')" class="action-btn activate">Activate</button>`);
        }
      }
    }

    const actionsHtml = `<div class="action-btns">${actions.join('')}</div>`;

    return `
      <tr>
        <td>
          <div class="role-name">${role.name}</div>
          <div class="role-code">${role.code}</div>
        </td>
        <td><div class="role-desc">${role.description || '—'}</div></td>
        <td>${typeBadge}</td>
        <td>
          <div class="member-count">${role.member_count}</div>
          <div class="member-label">active user${role.member_count !== 1 ? 's' : ''}</div>
        </td>
        <td>${statusBadge}</td>
        <td>${actionsHtml}</td>
      </tr>
    `;
  }).join('');
}

function confirmToggle(id, action, message) {
  Swal.fire({
    title: 'Are you sure?',
    text: message,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#e07b20',
    cancelButtonColor: '#9a9590',
    confirmButtonText: 'Yes, proceed!'
  }).then((result) => {
    if (result.isConfirmed) {
      executeToggle(id, action);
    }
  });
}

async function executeToggle(id, action) {
  const url = window.URLS.api_toggle.replace('00000000-0000-0000-0000-000000000000', id);

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.LAYOUT_CFG.csrf
      }
    });

    const data = await res.json();
    if (res.ok && data.ok) {
      showToast('success', 'Success', `Role was successfully ${action === 'deactivate' ? 'deactivated' : 'activated'}.`);
      loadRoles();
    } else {
      showToast('error', 'Error', data.error || 'Failed to toggle role state.');
    }
  } catch (err) {
    console.error('Failed to toggle role status', err);
    showToast('error', 'Error', 'Failed to communicate with server.');
  }
}

function showToast(type, title, msg) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = {
    success: `<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`,
    error: `<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  };
  el.innerHTML = `<div class="toast-icon">${icons[type]}</div><div><div class="toast-title">${title}</div><div class="toast-msg">${msg}</div></div>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

/* Sorting Buttons click handler */
const SORT_BTNS = { sortNameBtn: 'name', sortMemberBtn: 'member' };
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
  renderRoles();
}

/* Filters Dropdowns Helper functions */
function closeAllFilters() {
  filterNameOpen = filterTypeOpen = filterStatusOpen = false;
  ['filterNameDropdown','filterTypeDropdown','filterStatusDropdown'].forEach(id => document.getElementById(id)?.classList.remove('open'));
}

function positionDropdown(ddId, btnId) {
  const dd = document.getElementById(ddId), r = document.getElementById(btnId).getBoundingClientRect();
  dd.classList.add('open');
  dd.style.top = r.bottom + window.scrollY + 4 + 'px';
  dd.style.left = Math.min(r.left + window.scrollX, window.innerWidth - dd.offsetWidth - 8) + 'px';
}

function getFilteredRoles(excludeField) {
  return ROLES_DATA.filter(r => {
    if (excludeField !== 'name' && activeNameFilters.size && !activeNameFilters.has(r.name)) return false;
    if (excludeField !== 'type' && activeTypeFilters.size) {
      const typeStr = r.is_system_default ? 'System' : 'Custom';
      if (!activeTypeFilters.has(typeStr)) return false;
    }
    if (excludeField !== 'status' && activeStatusFilters.size && !activeStatusFilters.has(r.is_active ? 'active' : 'inactive')) return false;
    return true;
  });
}

function renderNameFilterList() {
  const q = (document.getElementById('filterNameSearch')?.value || '').toLowerCase();
  const source = getFilteredRoles('name');
  const names = [...new Set(source.map(r => r.name))].sort().filter(n => n.toLowerCase().includes(q));
  document.getElementById('filterNameList').innerHTML = names.map(n =>
    `<label class="filter-item"><input type="checkbox" value="${n}" ${activeNameFilters.has(n)?'checked':''} onchange="if(this.checked)activeNameFilters.add(this.value);else activeNameFilters.delete(this.value);renderRoles()"><span style="font-size:.83rem;color:var(--clr-text)">${n}</span></label>`).join('');
}

function renderTypeFilterList() {
  const source = getFilteredRoles('type');
  const hasSystem = source.some(r => r.is_system_default);
  const hasCustom = source.some(r => !r.is_system_default);
  const opts = [];
  if (hasSystem) opts.push('System');
  if (hasCustom) opts.push('Custom');
  document.getElementById('filterTypeList').innerHTML = opts.map(t =>
    `<label class="filter-item"><input type="checkbox" value="${t}" ${activeTypeFilters.has(t)?'checked':''} onchange="if(this.checked)activeTypeFilters.add(this.value);else activeTypeFilters.delete(this.value);renderRoles()"><span style="font-size:.83rem;color:var(--clr-text)">${t}</span></label>`).join('');
}

function renderStatusFilterList() {
  const source = getFilteredRoles('status');
  const hasActive = source.some(r => r.is_active);
  const hasInactive = source.some(r => !r.is_active);
  const opts = [];
  if (hasActive) opts.push({val:'active',label:'Active'});
  if (hasInactive) opts.push({val:'inactive',label:'Inactive'});
  document.getElementById('filterStatusList').innerHTML = opts.map(o =>
    `<label class="filter-item"><input type="checkbox" value="${o.val}" ${activeStatusFilters.has(o.val)?'checked':''} onchange="if(this.checked)activeStatusFilters.add(this.value);else activeStatusFilters.delete(this.value);renderRoles()"><span style="font-size:.83rem;color:var(--clr-text)">${o.label}</span></label>`).join('');
}

document.addEventListener("DOMContentLoaded", () => {
  // Wire sorting buttons
  Object.entries(SORT_BTNS).forEach(([btnId, field]) => {
    document.getElementById(btnId)?.addEventListener('click', () => applySortBtn(field, btnId));
  });

  // Wire filter dropdown triggers
  document.getElementById('filterNameBtn')?.addEventListener('click', e => {
    e.stopPropagation();
    const c = filterNameOpen;
    closeAllFilters();
    if (c) return;
    filterNameOpen = true;
    positionDropdown('filterNameDropdown', 'filterNameBtn');
    renderNameFilterList();
  });
  document.getElementById('filterNameSearch')?.addEventListener('input', () => renderNameFilterList());
  document.getElementById('filterNameSelectAll')?.addEventListener('click', e => {
    e.stopPropagation();
    const q = (document.getElementById('filterNameSearch')?.value || '').toLowerCase();
    const source = getFilteredRoles('name');
    const names = [...new Set(source.map(r => r.name))].filter(n => n.toLowerCase().includes(q));
    names.forEach(n => activeNameFilters.add(n));
    renderNameFilterList();
    renderRoles();
  });
  document.getElementById('filterNameClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeNameFilters.clear();
    renderNameFilterList();
    renderRoles();
  });

  document.getElementById('filterTypeBtn')?.addEventListener('click', e => {
    e.stopPropagation();
    const c = filterTypeOpen;
    closeAllFilters();
    if (c) return;
    filterTypeOpen = true;
    positionDropdown('filterTypeDropdown', 'filterTypeBtn');
    renderTypeFilterList();
  });
  document.getElementById('filterTypeSelectAll')?.addEventListener('click', e => {
    e.stopPropagation();
    const source = getFilteredRoles('type');
    const hasSystem = source.some(r => r.is_system_default);
    const hasCustom = source.some(r => !r.is_system_default);
    if (hasSystem) activeTypeFilters.add('System');
    if (hasCustom) activeTypeFilters.add('Custom');
    renderTypeFilterList();
    renderRoles();
  });
  document.getElementById('filterTypeClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeTypeFilters.clear();
    renderTypeFilterList();
    renderRoles();
  });

  document.getElementById('filterStatusBtn')?.addEventListener('click', e => {
    e.stopPropagation();
    const c = filterStatusOpen;
    closeAllFilters();
    if (c) return;
    filterStatusOpen = true;
    positionDropdown('filterStatusDropdown', 'filterStatusBtn');
    renderStatusFilterList();
  });
  document.getElementById('filterStatusSelectAll')?.addEventListener('click', e => {
    e.stopPropagation();
    const source = getFilteredRoles('status');
    const hasActive = source.some(r => r.is_active);
    const hasInactive = source.some(r => !r.is_active);
    if (hasActive) activeStatusFilters.add('active');
    if (hasInactive) activeStatusFilters.add('inactive');
    renderStatusFilterList();
    renderRoles();
  });
  document.getElementById('filterStatusClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeStatusFilters.clear();
    renderStatusFilterList();
    renderRoles();
  });

  document.addEventListener('click', e => {
    const ids = [
      'filterNameBtn', 'filterNameDropdown',
      'filterTypeBtn', 'filterTypeDropdown',
      'filterStatusBtn', 'filterStatusDropdown'
    ];
    if (!ids.some(id => document.getElementById(id)?.contains(e.target))) {
      closeAllFilters();
    }
  });

  function repositionOpenDropdown() {
    const openDd = document.querySelector('.filter-dropdown.open');
    if (!openDd) return;
    const btnId = openDd.id.replace('Dropdown', 'Btn');
    const btn = document.getElementById(btnId);
    if (btn) {
      const r = btn.getBoundingClientRect();
      openDd.style.top = r.bottom + window.scrollY + 4 + 'px';
      openDd.style.left = Math.min(r.left + window.scrollX, window.innerWidth - openDd.offsetWidth - 8) + 'px';
    }
  }

  window.addEventListener('scroll', repositionOpenDropdown, { passive: true });
  document.querySelectorAll('.table-scroll-wrap').forEach(el => {
    el.addEventListener('scroll', repositionOpenDropdown, { passive: true });
  });

  loadRoles();
});

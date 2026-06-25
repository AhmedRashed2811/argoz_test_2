// JavaScript for Sales Teams list page
let TEAMS_DATA = [];

// Sort and Filter States
let sortField = null;
let sortAscMap = {};
let activeNameFilters = new Set();
let activeHeadFilters = new Set();
let activeMemberFilters = new Set();
let activeStatusFilters = new Set();

let filterNameOpen = false;
let filterHeadOpen = false;
let filterMemberOpen = false;
let filterStatusOpen = false;

async function loadTeams() {
  const container = document.getElementById('team-table-body');
  if (!container) return;

  try {
    const res = await fetch(window.API_LIST_URL);
    if (!res.ok) throw new Error('Failed to load teams');
    const data = await res.json();
    TEAMS_DATA = data.teams || [];
    renderTeams();
  } catch (err) {
    console.error('Failed to load teams list', err);
    showToast('error', 'Error', 'Failed to retrieve teams list.');
    container.innerHTML = `<tr><td colspan="6" class="empty-state"><h3>Failed to Load</h3><p>Could not communicate with the server.</p></td></tr>`;
  }
}

function renderTeams() {
  const container = document.getElementById('team-table-body');
  if (!container) return;

  let filtered = [...TEAMS_DATA];

  // Apply filters
  if (activeNameFilters.size) {
    filtered = filtered.filter(t => activeNameFilters.has(t.name));
  }
  if (activeHeadFilters.size) {
    filtered = filtered.filter(t => {
      if (t.heads.length === 0) {
        return activeHeadFilters.has("Unassigned");
      }
      return t.heads.some(h => activeHeadFilters.has(h.full_name || h.email));
    });
  }
  if (activeMemberFilters.size) {
    filtered = filtered.filter(t => {
      if (t.members.length === 0) {
        return activeMemberFilters.has("No Members");
      }
      return t.members.some(m => activeMemberFilters.has(m.full_name || m.email));
    });
  }
  if (activeStatusFilters.size) {
    filtered = filtered.filter(t => activeStatusFilters.has(t.is_active ? 'active' : 'inactive'));
  }

  // Apply Sorting
  if (sortField && sortAscMap[sortField] != null) {
    const asc = sortAscMap[sortField];
    filtered.sort((a, b) => {
      let va, vb;
      if (sortField === 'name') {
        va = a.name || '';
        vb = b.name || '';
      } else if (sortField === 'head') {
        va = a.heads.map(h => h.full_name || h.email).join(', ') || '';
        vb = b.heads.map(h => h.full_name || h.email).join(', ') || '';
      } else if (sortField === 'order') {
        va = a.order_index ?? 0;
        vb = b.order_index ?? 0;
        return asc ? va - vb : vb - va;
      } else {
        va = ''; vb = '';
      }
      return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }

  if (filtered.length === 0) {
    container.innerHTML = `<tr><td colspan="6" class="empty-state"><h3>No Teams Found</h3><p>No matching sales teams found.</p></td></tr>`;
    return;
  }

  container.innerHTML = filtered.map(team => {
    const heads = team.heads.map(h => `<span class="head-badge">${h.full_name || h.email}</span>`).join(' ') || '<span class="unassigned">Unassigned</span>';
    const memberCount = team.members.length;
    const memberText = `${memberCount} member${memberCount !== 1 ? 's' : ''}`;
    const membersHtml = memberCount > 0
      ? `<span class="member-count">${memberText}</span>
         <div class="member-list">
           ${team.members.slice(0, 4).map(m => `<span class="member-pill">${m.full_name || m.email}</span>`).join('')}
           ${memberCount > 4 ? `<span class="member-pill" style="color:var(--clr-text-sub);">+${memberCount - 4} more</span>` : ''}
         </div>`
      : '<span class="unassigned">No Members</span>';

    const statusBadge = team.is_active
      ? `<span class="status-badge active"><span class="dot"></span> Active</span>`
      : `<span class="status-badge inactive"><span class="dot"></span> Inactive</span>`;

    const actions = [];
    if (window.PERMS.can_update) {
      actions.push(`<a href="${window.URLS.edit.replace('00000000-0000-0000-0000-000000000000', team.id)}" class="action-btn edit">Edit</a>`);
    }

    if (team.is_active) {
      if (window.PERMS.can_delete) {
        actions.push(`<button onclick="confirmAction('${team.id}', 'delete', 'Delete team &quot;${team.name}&quot;?')" class="action-btn delete">Delete</button>`);
      }
    } else {
      if (window.PERMS.can_update) {
        actions.push(`<button onclick="confirmAction('${team.id}', 'activate', 'Activate team &quot;${team.name}&quot;?')" class="action-btn activate">Activate</button>`);
      }
    }

    const actionsHtml = `<div class="action-btns">${actions.join('')}</div>`;

    return `
      <tr>
        <td>
          <div class="team-name">${team.name}</div>
          ${team.region ? `<div class="team-region">${team.region}</div>` : ''}
        </td>
        <td>${heads}</td>
        <td>${membersHtml}</td>
        <td><span style="font-weight: 500;">${team.order_index}</span></td>
        <td>${statusBadge}</td>
        <td>${actionsHtml}</td>
      </tr>
    `;
  }).join('');
}

function confirmAction(id, action, message) {
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
      executeAction(id, action);
    }
  });
}

async function executeAction(id, action) {
  let url = '';
  if (action === 'delete') {
    url = window.URLS.api_delete.replace('00000000-0000-0000-0000-000000000000', id);
  } else if (action === 'activate') {
    url = window.URLS.api_activate.replace('00000000-0000-0000-0000-000000000000', id);
  }

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
      showToast('success', 'Success', `Team was successfully ${action === 'delete' ? 'deleted' : 'activated'}.`);
      loadTeams();
    } else {
      showToast('error', 'Error', data.error || 'Failed to complete action.');
    }
  } catch (err) {
    console.error('Failed to perform team action', err);
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
const SORT_BTNS = { sortNameBtn: 'name', sortHeadBtn: 'head', sortOrderBtn: 'order' };
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
  renderTeams();
}

/* Filters Dropdowns Helper functions */
function closeAllFilters() {
  filterNameOpen = filterHeadOpen = filterMemberOpen = filterStatusOpen = false;
  ['filterNameDropdown','filterHeadDropdown','filterMemberDropdown','filterStatusDropdown'].forEach(id => document.getElementById(id)?.classList.remove('open'));
}

function positionDropdown(ddId, btnId) {
  const dd = document.getElementById(ddId), r = document.getElementById(btnId).getBoundingClientRect();
  dd.classList.add('open');
  dd.style.top = r.bottom + window.scrollY + 4 + 'px';
  dd.style.left = Math.min(r.left + window.scrollX, window.innerWidth - dd.offsetWidth - 8) + 'px';
}

function getFilteredTeams(excludeField) {
  return TEAMS_DATA.filter(t => {
    if (excludeField !== 'name' && activeNameFilters.size && !activeNameFilters.has(t.name)) return false;
    if (excludeField !== 'head' && activeHeadFilters.size) {
      if (t.heads.length === 0) {
        if (!activeHeadFilters.has("Unassigned")) return false;
      } else if (!t.heads.some(h => activeHeadFilters.has(h.full_name || h.email))) return false;
    }
    if (excludeField !== 'member' && activeMemberFilters.size) {
      if (t.members.length === 0) {
        if (!activeMemberFilters.has("No Members")) return false;
      } else if (!t.members.some(m => activeMemberFilters.has(m.full_name || m.email))) return false;
    }
    if (excludeField !== 'status' && activeStatusFilters.size && !activeStatusFilters.has(t.is_active ? 'active' : 'inactive')) return false;
    return true;
  });
}

function renderNameFilterList() {
  const q = (document.getElementById('filterNameSearch')?.value || '').toLowerCase();
  const source = getFilteredTeams('name');
  const names = [...new Set(source.map(t => t.name))].sort().filter(n => n.toLowerCase().includes(q));
  document.getElementById('filterNameList').innerHTML = names.map(n =>
    `<label class="filter-item"><input type="checkbox" value="${n}" ${activeNameFilters.has(n)?'checked':''} onchange="if(this.checked)activeNameFilters.add(this.value);else activeNameFilters.delete(this.value);renderTeams()"><span style="font-size:.83rem;color:var(--clr-text)">${n}</span></label>`).join('');
}

function renderHeadFilterList() {
  const q = (document.getElementById('filterHeadSearch')?.value || '').toLowerCase();
  const source = getFilteredTeams('head');
  const heads = [...new Set(source.flatMap(t => t.heads.map(h => h.full_name || h.email)))].sort().filter(h => h.toLowerCase().includes(q));
  if (source.some(t => t.heads.length === 0)) heads.push("Unassigned");
  document.getElementById('filterHeadList').innerHTML = heads.map(h =>
    `<label class="filter-item"><input type="checkbox" value="${h}" ${activeHeadFilters.has(h)?'checked':''} onchange="if(this.checked)activeHeadFilters.add(this.value);else activeHeadFilters.delete(this.value);renderTeams()"><span style="font-size:.83rem;color:var(--clr-text)">${h}</span></label>`).join('');
}

function renderMemberFilterList() {
  const q = (document.getElementById('filterMemberSearch')?.value || '').toLowerCase();
  const source = getFilteredTeams('member');
  const members = [...new Set(source.flatMap(t => t.members.map(m => m.full_name || m.email)))].sort().filter(m => m.toLowerCase().includes(q));
  if (source.some(t => t.members.length === 0)) members.push("No Members");
  document.getElementById('filterMemberList').innerHTML = members.map(m =>
    `<label class="filter-item"><input type="checkbox" value="${m}" ${activeMemberFilters.has(m)?'checked':''} onchange="if(this.checked)activeMemberFilters.add(this.value);else activeMemberFilters.delete(this.value);renderTeams()"><span style="font-size:.83rem;color:var(--clr-text)">${m}</span></label>`).join('');
}

function renderStatusFilterList() {
  const source = getFilteredTeams('status');
  const hasActive = source.some(t => t.is_active);
  const hasInactive = source.some(t => !t.is_active);
  const opts = [];
  if (hasActive) opts.push({val:'active',label:'Active'});
  if (hasInactive) opts.push({val:'inactive',label:'Inactive'});
  document.getElementById('filterStatusList').innerHTML = opts.map(o =>
    `<label class="filter-item"><input type="checkbox" value="${o.val}" ${activeStatusFilters.has(o.val)?'checked':''} onchange="if(this.checked)activeStatusFilters.add(this.value);else activeStatusFilters.delete(this.value);renderTeams()"><span style="font-size:.83rem;color:var(--clr-text)">${o.label}</span></label>`).join('');
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
    const source = getFilteredTeams('name');
    const names = [...new Set(source.map(t => t.name))].filter(n => n.toLowerCase().includes(q));
    names.forEach(n => activeNameFilters.add(n));
    renderNameFilterList();
    renderTeams();
  });
  document.getElementById('filterNameClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeNameFilters.clear();
    renderNameFilterList();
    renderTeams();
  });

  document.getElementById('filterHeadBtn')?.addEventListener('click', e => {
    e.stopPropagation();
    const c = filterHeadOpen;
    closeAllFilters();
    if (c) return;
    filterHeadOpen = true;
    positionDropdown('filterHeadDropdown', 'filterHeadBtn');
    renderHeadFilterList();
  });
  document.getElementById('filterHeadSearch')?.addEventListener('input', () => renderHeadFilterList());
  document.getElementById('filterHeadSelectAll')?.addEventListener('click', e => {
    e.stopPropagation();
    const q = (document.getElementById('filterHeadSearch')?.value || '').toLowerCase();
    const source = getFilteredTeams('head');
    const heads = [...new Set(source.flatMap(t => t.heads.map(h => h.full_name || h.email)))].filter(h => h.toLowerCase().includes(q));
    if (source.some(t => t.heads.length === 0)) heads.push("Unassigned");
    heads.forEach(h => activeHeadFilters.add(h));
    renderHeadFilterList();
    renderTeams();
  });
  document.getElementById('filterHeadClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeHeadFilters.clear();
    renderHeadFilterList();
    renderTeams();
  });

  document.getElementById('filterMemberBtn')?.addEventListener('click', e => {
    e.stopPropagation();
    const c = filterMemberOpen;
    closeAllFilters();
    if (c) return;
    filterMemberOpen = true;
    positionDropdown('filterMemberDropdown', 'filterMemberBtn');
    renderMemberFilterList();
  });
  document.getElementById('filterMemberSearch')?.addEventListener('input', () => renderMemberFilterList());
  document.getElementById('filterMemberSelectAll')?.addEventListener('click', e => {
    e.stopPropagation();
    const q = (document.getElementById('filterMemberSearch')?.value || '').toLowerCase();
    const source = getFilteredTeams('member');
    const members = [...new Set(source.flatMap(t => t.members.map(m => m.full_name || m.email)))].filter(m => m.toLowerCase().includes(q));
    if (source.some(t => t.members.length === 0)) members.push("No Members");
    members.forEach(m => activeMemberFilters.add(m));
    renderMemberFilterList();
    renderTeams();
  });
  document.getElementById('filterMemberClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeMemberFilters.clear();
    renderMemberFilterList();
    renderTeams();
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
    const source = getFilteredTeams('status');
    const hasActive = source.some(t => t.is_active);
    const hasInactive = source.some(t => !t.is_active);
    if (hasActive) activeStatusFilters.add('active');
    if (hasInactive) activeStatusFilters.add('inactive');
    renderStatusFilterList();
    renderTeams();
  });
  document.getElementById('filterStatusClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeStatusFilters.clear();
    renderStatusFilterList();
    renderTeams();
  });

  document.addEventListener('click', e => {
    const ids = [
      'filterNameBtn', 'filterNameDropdown',
      'filterHeadBtn', 'filterHeadDropdown',
      'filterMemberBtn', 'filterMemberDropdown',
      'filterStatusBtn', 'filterStatusDropdown'
    ];
    if (!ids.some(id => document.getElementById(id)?.contains(e.target))) {
      closeAllFilters();
    }
  });

  loadTeams();
});

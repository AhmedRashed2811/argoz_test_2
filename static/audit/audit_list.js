// Paginated & Filtered Audit Logs loader via AJAX
let currentPage = 1;
let totalPages = 1;
let PER_PAGE = 100;
let auditLogs = [];

// Sort and filter states
let sortField = null;
let sortAscMap = {};
let activeActionFilters = new Set();
let activeEntityFilters = new Set();
let activeActorFilters = new Set();

let filterActionOpen = false;
let filterEntityOpen = false;
let filterActorOpen = false;

async function fetchAuditLogs() {
  const tableBody = document.getElementById("audit-tbody");
  const searchHint = document.getElementById('searchHint');
  
  if (tableBody) tableBody.innerHTML = `<tr><td colspan="6" style="padding:2rem;color:var(--clr-gray);text-align:center">Loading audit records…</td></tr>`;

  const action = document.getElementById("id_action")?.value || "";
  const entityType = document.getElementById("id_entity_type")?.value.trim() || "";
  
  // Build query URL
  let queryUrl = `${window.API_DATA_URL}?page=${currentPage}&limit=${PER_PAGE}`;
  if (action) queryUrl += `&action=${encodeURIComponent(action)}`;
  if (entityType) queryUrl += `&entity_type=${encodeURIComponent(entityType)}`;
  
  // If target user_id filter is passed from parent template (for permission audit page)
  if (window.TARGET_USER_ID) {
    queryUrl += `&user_id=${encodeURIComponent(window.TARGET_USER_ID)}`;
  }

  try {
    const res = await fetch(queryUrl);
    if (!res.ok) throw new Error("Failed to load audit logs");
    const data = await res.json();
    
    auditLogs = data.logs || [];
    totalPages = data.num_pages || 1;
    currentPage = data.current_page || 1;
    
    // Render KPIs
    if (data.kpis) {
      document.getElementById('kpiTotal').textContent = data.kpis.total ?? 0;
      document.getElementById('kpiCreate').textContent = data.kpis.create ?? 0;
      document.getElementById('kpiDelete').textContent = data.kpis.delete ?? 0;
      document.getElementById('kpiSecurity').textContent = data.kpis.security ?? 0;
    }

    if (searchHint) {
      searchHint.textContent = (action || entityType) ? `${data.total} result${data.total !== 1 ? 's' : ''} found` : '';
    }

    renderTable(data.total);
  } catch (err) {
    console.error("Failed to load audit logs", err);
    if (tableBody) tableBody.innerHTML = `<tr><td colspan="6" style="padding:2rem;color:var(--clr-error);text-align:center">Error loading audit records. Check connection.</td></tr>`;
  }
}

/* Helper functions for cell renderers */
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function timeSince(iso) {
  if (!iso) return "";
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  const units = [["year", 31536000], ["month", 2592000], ["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [label, secs] of units) {
    const val = Math.floor(seconds / secs);
    if (val >= 1) return `${val} ${label}${val > 1 ? "s" : ""}`;
  }
  return "moments";
}

function actionBadgeKey(action) {
  switch (action) {
    case "CREATE": return "create";
    case "UPDATE": return "update";
    case "DELETE": return "delete";
    case "PERMISSION_CHANGE": return "permission";
    case "POLICY_CHANGE": return "policy";
    default: return "default";
  }
}

function renderEntityCell(log) {
  if (log.entity_type === "UserPermissionOverride" || log.entity_type === "UserRole") {
    const name = (log.after_json && log.after_json.user) || (log.before_json && log.before_json.user) || log.entity_display;
    const tagLabel = log.entity_type === "UserPermissionOverride" ? "Override" : "Role";
    return `
      <div class="entity-name">${escapeHtml(name)}</div>
      <div class="entity-meta">
        <span class="entity-code">${escapeHtml(log.entity_type)}</span>
        <span class="team-badge">${tagLabel}</span>
      </div>`;
  } else if (log.entity_type === "User") {
    const email = (log.after_json && log.after_json.email) || (log.before_json && log.before_json.email) || log.entity_display;
    return `
      <div class="entity-name">${escapeHtml(email)}</div>
      <div class="entity-meta"><span class="entity-code">${escapeHtml(log.entity_type)} #${escapeHtml(log.entity_id)}</span></div>`;
  } else {
    return `
      <div class="entity-name">${escapeHtml(log.entity_display || log.entity_type)}</div>
      <div class="entity-meta"><span class="entity-code">${escapeHtml(log.entity_type)} #${escapeHtml(log.entity_id)}</span></div>`;
  }
}

function renderActorCell(log) {
  const actor = log.actor;
  const name = (actor && (actor.full_name || actor.email)) || "System";
  const email = (actor && actor.email) || "";
  return `
    <div class="user-identity">
      <div>
        <div class="user-name">${escapeHtml(name)}</div>
        ${email ? `<div class="user-email">${escapeHtml(email)}</div>` : `<div class="user-email" style="font-style:italic">Automated process</div>`}
      </div>
    </div>`;
}

function renderDetailsCell(log) {
  let html = "";

  if (log.entity_type === "UserPermissionOverride") {
    const isOldFormat = (log.after_json && log.after_json.user) || (log.before_json && log.before_json.user);
    if (isOldFormat) {
      let badge, label;
      if (!log.after_json) { badge = "delete"; label = "Override Removed"; }
      else if (log.after_json.effect === "ALLOW") { badge = "create"; label = "Gained"; }
      else { badge = "delete"; label = "Taken"; }
      const perm = (log.after_json && log.after_json.permission) || (log.before_json && log.before_json.permission) || "";
      html += `
        <div style="margin-bottom:8px;display:flex;align-items:center;gap:8px">
          <span class="audit-badge ${badge}">${label}</span>
          <span class="entity-code" style="font-weight:600;color:var(--clr-text)">${escapeHtml(perm)}</span>
        </div>`;
    } else {
      const fields = Object.entries(log.changed_fields || {});
      if (fields.length === 0) {
        html += `<span style="color:var(--clr-text-sub);font-size:.83rem">No overrides changed</span>`;
      } else {
        html += `<div style="display:flex;flex-direction:column;gap:6px;margin-bottom:6px">`;
        for (const [field, val] of fields) {
          let badge, label;
          if (val.new === "ALLOW") { badge = "create"; label = "Gained"; }
          else if (val.new === "DENY") { badge = "delete"; label = "Blocked"; }
          else { badge = "default"; label = "Cleared"; }
          html += `
            <div style="display:flex;align-items:center;gap:8px">
              <span class="audit-badge ${badge}">${label}</span>
              <span class="entity-code" style="font-weight:600;color:var(--clr-text)">${escapeHtml(field)}</span>
            </div>`;
        }
        html += `</div>`;
      }
    }
  } else if (log.entity_type === "UserRole") {
    const removed = !log.after_json || !log.after_json.is_active;
    const badge = removed ? "delete" : "create";
    const label = removed ? "Role Removed" : "Role Assigned";
    const role = (log.after_json && log.after_json.role) || (log.before_json && log.before_json.role) || "";
    html += `
      <div style="margin-bottom:8px;display:flex;align-items:center;gap:8px">
        <span class="audit-badge ${badge}">${label}</span>
        <span style="font-weight:600;color:var(--clr-text);font-size:.85rem">${escapeHtml(role)}</span>
      </div>`;
  }

  if (log.changed_fields && log.entity_type !== "UserPermissionOverride") {
    const entries = Object.entries(log.changed_fields).filter(
      ([field]) => !["user", "permission", "role", "user_id"].includes(field)
    );
    if (entries.length > 0) {
      html += `<div class="diff-wrapper">`;
      for (const [field, val] of entries) {
        html += `
          <div class="diff-line">
            <span class="diff-field">${escapeHtml(field)}:</span>
            <span class="diff-old">${escapeHtml(val.old ?? "None")}</span>
            <span class="diff-arrow">→</span>
            <span class="diff-new">${escapeHtml(val.new ?? "None")}</span>
          </div>`;
      }
      html += `</div>`;
    }
  }

  if (log.reason) {
    html += `<div class="reason-box"><strong>Reason:</strong> ${escapeHtml(log.reason)}</div>`;
  }

  const hasChangedFields = log.changed_fields && Object.keys(log.changed_fields).length > 0;
  if (!hasChangedFields && !log.reason && log.entity_type !== "UserPermissionOverride" && log.entity_type !== "UserRole") {
    html += `<span style="color:var(--clr-gray);font-size:.83rem">—</span>`;
  }

  return html;
}

function renderMetaCell(log) {
  if (!log.request_meta) {
    return `<span style="color:var(--clr-gray);font-size:.83rem">—</span>`;
  }
  const meta = log.request_meta;
  let html = `
    <div class="metadata-box">
      <div class="metadata-item">
        <span>IP Address</span>
        <span class="metadata-val">${escapeHtml(meta.ip || "-")}</span>
      </div>
      <div class="metadata-item">
        <span>Method/Path</span>
        <span class="metadata-val">${escapeHtml(meta.method || "-")} ${escapeHtml(meta.path || "-")}</span>
      </div>`;
  if (meta.user_agent) {
    html += `<div class="metadata-ua">${escapeHtml(meta.user_agent)}</div>`;
  }
  html += `</div>`;
  return html;
}

function renderRow(log) {
  return `
    <tr>
      <td>
        <div class="timestamp-text">${formatDate(log.created_at)}</div>
        <div class="timestamp-sub">${timeSince(log.created_at)} ago</div>
      </td>
      <td><span class="audit-badge ${actionBadgeKey(log.action)}">${escapeHtml(log.action)}</span></td>
      <td style="text-align:left">${renderEntityCell(log)}</td>
      <td style="text-align:left">${renderActorCell(log)}</td>
      <td style="text-align:left">${renderDetailsCell(log)}</td>
      <td style="text-align:left">${renderMetaCell(log)}</td>
    </tr>`;
}

function renderTable(total) {
  const tbody = document.getElementById("audit-tbody");
  if (!tbody) return;

  let filtered = [...auditLogs];

  // Apply column filters
  if (activeActionFilters.size) {
    filtered = filtered.filter(log => activeActionFilters.has(log.action));
  }
  if (activeEntityFilters.size) {
    filtered = filtered.filter(log => activeEntityFilters.has(log.entity_display || log.entity_type));
  }
  if (activeActorFilters.size) {
    filtered = filtered.filter(log => {
      const actorName = log.actor ? (log.actor.full_name || log.actor.email) : "System";
      return activeActorFilters.has(actorName);
    });
  }

  // Apply column sorting
  if (sortField && sortAscMap[sortField] != null) {
    const asc = sortAscMap[sortField];
    filtered.sort((a, b) => {
      let va, vb;
      if (sortField === 'timestamp') {
        va = new Date(a.created_at).getTime();
        vb = new Date(b.created_at).getTime();
        return asc ? va - vb : vb - va;
      } else if (sortField === 'action') {
        va = a.action || '';
        vb = b.action || '';
      } else if (sortField === 'entity') {
        va = a.entity_display || a.entity_type || '';
        vb = b.entity_display || b.entity_type || '';
      } else if (sortField === 'actor') {
        va = a.actor ? (a.actor.full_name || a.actor.email) : 'System';
        vb = b.actor ? (b.actor.full_name || b.actor.email) : 'System';
      } else {
        va = ''; vb = '';
      }
      return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><h3>No matching audit log entries</h3><p>Try a different filter combination.</p></div></td></tr>`;
    document.getElementById('pgInfo').textContent = 'No results';
    renderPagination(0);
    return;
  }

  tbody.innerHTML = filtered.map(renderRow).join("");

  const start = (currentPage - 1) * PER_PAGE;
  document.getElementById('pgInfo').textContent = `Showing ${start + 1}–${Math.min(start + PER_PAGE, total)} of ${total}`;
  renderPagination(total);
}

function renderPagination(total) {
  totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  const bar = document.getElementById('paginationBar');
  if (!bar) return;
  bar.style.display = total === 0 ? 'none' : 'flex';
  document.getElementById('pgControlsWrap').style.display = totalPages <= 1 ? 'none' : 'flex';
  document.getElementById('pgFirst').disabled = currentPage === 1;
  document.getElementById('pgPrev').disabled  = currentPage === 1;
  document.getElementById('pgNext').disabled  = currentPage === totalPages;
  document.getElementById('pgLast').disabled  = currentPage === totalPages;
  const nums = document.getElementById('pgNumbers'); 
  if (nums) {
    nums.innerHTML = '';
    let s = Math.max(1, currentPage - 2), e = Math.min(totalPages, s + 4); s = Math.max(1, e - 4);
    if (s > 1) { addPgNum(nums, 1); if (s > 2) nums.insertAdjacentHTML('beforeend', '<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>'); }
    for (let i = s; i <= e; i++) addPgNum(nums, i);
    if (e < totalPages) { if (e < totalPages - 1) nums.insertAdjacentHTML('beforeend', '<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>'); addPgNum(nums, totalPages); }
  }
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
  currentPage = p;
  fetchAuditLogs();
}

function changePerPage(val) {
  PER_PAGE = parseInt(val, 10);
  currentPage = 1;
  fetchAuditLogs();
}

function applyFilters() {
  currentPage = 1;
  fetchAuditLogs();
}

function resetFilters() {
  const actionEl = document.getElementById("id_action");
  const entityEl = document.getElementById("id_entity_type");
  if (actionEl) actionEl.value = "";
  if (entityEl) entityEl.value = "";
  
  const searchHint = document.getElementById('searchHint');
  if (searchHint) searchHint.textContent = '';
  
  currentPage = 1;
  fetchAuditLogs();
}

/* Sorting Click Handlers */
const SORT_BTNS = { sortTimeBtn: 'timestamp', sortActionBtn: 'action', sortEntityBtn: 'entity', sortActorBtn: 'actor' };
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
  renderTable(auditLogs.length);
}

/* Filters Dropdowns Helper functions */
function closeAllFilters() {
  filterActionOpen = filterEntityOpen = filterActorOpen = false;
  ['filterActionDropdown','filterEntityDropdown','filterActorDropdown'].forEach(id => document.getElementById(id)?.classList.remove('open'));
}

function positionDropdown(ddId, btnId) {
  const dd = document.getElementById(ddId), r = document.getElementById(btnId).getBoundingClientRect();
  dd.classList.add('open');
  dd.style.top = r.bottom + window.scrollY + 4 + 'px';
  dd.style.left = Math.min(r.left + window.scrollX, window.innerWidth - dd.offsetWidth - 8) + 'px';
}

function getFilteredLogs(excludeField) {
  return auditLogs.filter(log => {
    if (excludeField !== 'action' && activeActionFilters.size && !activeActionFilters.has(log.action)) return false;
    if (excludeField !== 'entity' && activeEntityFilters.size && !activeEntityFilters.has(log.entity_display || log.entity_type)) return false;
    if (excludeField !== 'actor' && activeActorFilters.size) {
      const actorName = log.actor ? (log.actor.full_name || log.actor.email) : "System";
      if (!activeActorFilters.has(actorName)) return false;
    }
    return true;
  });
}

function renderActionFilterList() {
  const source = getFilteredLogs('action');
  const actions = [...new Set(source.map(l => l.action))].sort();
  document.getElementById('filterActionList').innerHTML = actions.map(act =>
    `<label class="filter-item"><input type="checkbox" value="${act}" ${activeActionFilters.has(act)?'checked':''} onchange="if(this.checked)activeActionFilters.add(this.value);else activeActionFilters.delete(this.value);renderTable(auditLogs.length)"><span style="font-size:.83rem;color:var(--clr-text)">${act}</span></label>`).join('');
}

function renderEntityFilterList() {
  const q = (document.getElementById('filterEntitySearch')?.value || '').toLowerCase();
  const source = getFilteredLogs('entity');
  const entities = [...new Set(source.map(l => l.entity_display || l.entity_type))].sort().filter(e => e.toLowerCase().includes(q));
  document.getElementById('filterEntityList').innerHTML = entities.map(ent =>
    `<label class="filter-item"><input type="checkbox" value="${ent}" ${activeEntityFilters.has(ent)?'checked':''} onchange="if(this.checked)activeEntityFilters.add(this.value);else activeEntityFilters.delete(this.value);renderTable(auditLogs.length)"><span style="font-size:.83rem;color:var(--clr-text)">${ent}</span></label>`).join('');
}

function renderActorFilterList() {
  const q = (document.getElementById('filterActorSearch')?.value || '').toLowerCase();
  const source = getFilteredLogs('actor');
  const actors = [...new Set(source.map(l => l.actor ? (l.actor.full_name || l.actor.email) : "System"))].sort().filter(a => a.toLowerCase().includes(q));
  document.getElementById('filterActorList').innerHTML = actors.map(act =>
    `<label class="filter-item"><input type="checkbox" value="${act}" ${activeActorFilters.has(act)?'checked':''} onchange="if(this.checked)activeActorFilters.add(this.value);else activeActorFilters.delete(this.value);renderTable(auditLogs.length)"><span style="font-size:.83rem;color:var(--clr-text)">${act}</span></label>`).join('');
}

document.addEventListener("DOMContentLoaded", () => {
  const applyBtn = document.getElementById('apply-filters');
  const resetBtn = document.getElementById('reset-filters');
  if (applyBtn) applyBtn.addEventListener('click', applyFilters);
  if (resetBtn) resetBtn.addEventListener('click', resetFilters);
  
  // Wire sorting buttons
  Object.entries(SORT_BTNS).forEach(([btnId, field]) => {
    document.getElementById(btnId)?.addEventListener('click', () => applySortBtn(field, btnId));
  });

  // Wire filter dropdown triggers
  document.getElementById('filterActionBtn')?.addEventListener('click', e => {
    e.stopPropagation();
    const c = filterActionOpen;
    closeAllFilters();
    if (c) return;
    filterActionOpen = true;
    positionDropdown('filterActionDropdown', 'filterActionBtn');
    renderActionFilterList();
  });
  document.getElementById('filterActionSelectAll')?.addEventListener('click', e => {
    e.stopPropagation();
    const source = getFilteredLogs('action');
    source.forEach(l => activeActionFilters.add(l.action));
    renderActionFilterList();
    renderTable(auditLogs.length);
  });
  document.getElementById('filterActionClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeActionFilters.clear();
    renderActionFilterList();
    renderTable(auditLogs.length);
  });

  document.getElementById('filterEntityBtn')?.addEventListener('click', e => {
    e.stopPropagation();
    const c = filterEntityOpen;
    closeAllFilters();
    if (c) return;
    filterEntityOpen = true;
    positionDropdown('filterEntityDropdown', 'filterEntityBtn');
    renderEntityFilterList();
  });
  document.getElementById('filterEntitySearch')?.addEventListener('input', () => renderEntityFilterList());
  document.getElementById('filterEntitySelectAll')?.addEventListener('click', e => {
    e.stopPropagation();
    const q = (document.getElementById('filterEntitySearch')?.value || '').toLowerCase();
    const source = getFilteredLogs('entity');
    const entities = [...new Set(source.map(l => l.entity_display || l.entity_type))].filter(ent => ent.toLowerCase().includes(q));
    entities.forEach(ent => activeEntityFilters.add(ent));
    renderEntityFilterList();
    renderTable(auditLogs.length);
  });
  document.getElementById('filterEntityClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeEntityFilters.clear();
    renderEntityFilterList();
    renderTable(auditLogs.length);
  });

  document.getElementById('filterActorBtn')?.addEventListener('click', e => {
    e.stopPropagation();
    const c = filterActorOpen;
    closeAllFilters();
    if (c) return;
    filterActorOpen = true;
    positionDropdown('filterActorDropdown', 'filterActorBtn');
    renderActorFilterList();
  });
  document.getElementById('filterActorSearch')?.addEventListener('input', () => renderActorFilterList());
  document.getElementById('filterActorSelectAll')?.addEventListener('click', e => {
    e.stopPropagation();
    const q = (document.getElementById('filterActorSearch')?.value || '').toLowerCase();
    const source = getFilteredLogs('actor');
    const actors = [...new Set(source.map(l => l.actor ? (l.actor.full_name || l.actor.email) : "System"))].filter(act => act.toLowerCase().includes(q));
    actors.forEach(act => activeActorFilters.add(act));
    renderActorFilterList();
    renderTable(auditLogs.length);
  });
  document.getElementById('filterActorClearAll')?.addEventListener('click', e => {
    e.stopPropagation();
    activeActorFilters.clear();
    renderActorFilterList();
    renderTable(auditLogs.length);
  });

  document.addEventListener('click', e => {
    const ids = [
      'filterActionBtn', 'filterActionDropdown',
      'filterEntityBtn', 'filterEntityDropdown',
      'filterActorBtn', 'filterActorDropdown'
    ];
    if (!ids.some(id => document.getElementById(id)?.contains(e.target))) {
      closeAllFilters();
    }
  });

  fetchAuditLogs();
});

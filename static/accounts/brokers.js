/* ═══════════════════════════════════
   DATA
   Preserve sorting, filtering, and table rendering from the original,
   but load and save via dynamic Django AJAX endpoints instead of localStorage.
   ═══════════════════════════════════ */
const csrfToken = window.BROKERS_CFG.csrf;

let brokers = [];

let sortField = null;
let sortAscMap = {};
let searchQuery = '';
let editingIndex = null;
let cPasswordTypedByUser = false;
let edPasswordTypedByUser = false;

// Filter states
let activeNameFilters   = new Set();
let activeAgencyFilters = new Set();
let activeStartFilters  = new Set();
let activeEndFilters    = new Set();
let activeStatusFilters = new Set();

// Filter open flags
let filterNameOpen   = false;
let filterAgencyOpen = false;
let filterStartOpen  = false;
let filterEndOpen    = false;
let filterCommOpen   = false;
let filterLeadsOpen  = false;
let filterStatusOpen = false;

/* ═══════════════════════════════════
   API OPERATIONS
   ═══════════════════════════════════ */
async function loadBrokers() {
  try {
    const response = await fetch(window.BROKERS_CFG.listUrl);
    if (!response.ok) throw new Error('Network response was not ok');
    const data = await response.json();
    brokers = data.brokers || [];
    renderTable();
    renderNameFilterList();
    renderAgencyFilterList();
  } catch (error) {
    showToast('error', 'Error', 'Failed to load brokers from database.');
    console.error('Error loading brokers:', error);
  }
}

/* ═══════════════════════════════════
   HELPERS
   ═══════════════════════════════════ */
function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function getStatus(b) {
  const today = new Date().toISOString().slice(0,10);
  if (!b.endDate)   return 'upcoming';
  if (b.endDate < today) return 'expired';
  if (b.startDate && b.startDate > today) return 'upcoming';
  return 'active';
}

function fmtDate(d) {
  if (!d) return '—';
  const [y,m,day] = d.split('-');
  const mNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${mNames[parseInt(m)-1]} ${parseInt(day)}, ${y}`;
}

function fmtMonth(d) {
  if (!d) return '—';
  const [y,m] = d.split('-');
  const mNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${mNames[parseInt(m)-1]} ${y}`;
}

/* ═══════════════════════════════════
   RENDER TABLE
   ═══════════════════════════════════ */
function getDisplayList() {
  let list = brokers.map((b, i) => ({ b, origIndex: i }));

  if (activeNameFilters.size)   list = list.filter(d => activeNameFilters.has(d.b.name));
  if (activeAgencyFilters.size) list = list.filter(d => activeAgencyFilters.has(d.b.agency||''));
  if (activeStartFilters.size)  list = list.filter(d => activeStartFilters.has((d.b.startDate||'').slice(0,7)));
  if (activeEndFilters.size)    list = list.filter(d => activeEndFilters.has((d.b.endDate||'').slice(0,7)));
  if (activeStatusFilters.size) list = list.filter(d => activeStatusFilters.has(getStatus(d.b)));

  // Commission range filter
  const cMin = parseFloat(document.getElementById('commMin')?.value); 
  const cMax = parseFloat(document.getElementById('commMax')?.value);
  if (!isNaN(cMin)) list = list.filter(d => Number(d.b.commission||0) >= cMin);
  if (!isNaN(cMax)) list = list.filter(d => Number(d.b.commission||0) <= cMax);

  // Leads range filter
  const lMin = parseFloat(document.getElementById('leadsMin')?.value);
  const lMax = parseFloat(document.getElementById('leadsMax')?.value);
  if (!isNaN(lMin)) list = list.filter(d => Number(d.b.leads||0) >= lMin);
  if (!isNaN(lMax)) list = list.filter(d => Number(d.b.leads||0) <= lMax);

  if (searchQuery.trim()) {
    const q = searchQuery.trim().toLowerCase();
    list = list.filter(d =>
      (d.b.name||'').toLowerCase().includes(q) ||
      (d.b.agency||'').toLowerCase().includes(q) ||
      (d.b.location||'').toLowerCase().includes(q)
    );
  }

  if (sortField && sortAscMap[sortField] != null) {
    const asc = sortAscMap[sortField];
    list.sort((a, b) => {
      if (sortField === 'commission' || sortField === 'leads') {
        return asc ? Number(a.b[sortField]||0) - Number(b.b[sortField]||0)
                   : Number(b.b[sortField]||0) - Number(a.b[sortField]||0);
      }
      const va = String(a.b[sortField]||''), vb = String(b.b[sortField]||'');
      return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }
  return list;
}

function renderTable() {
  const tbody = document.getElementById('tableBody');
  const list  = getDisplayList();
  const hint  = document.getElementById('searchHint');

  // KPIs
  document.getElementById('kpiTotal').textContent = brokers.length;
  const activeCount = brokers.filter(b => getStatus(b) === 'active').length;
  const commissions = brokers.map(b => Number(b.commission||0)).filter(c => c > 0);
  const avgComm     = commissions.length ? (commissions.reduce((s,c)=>s+c,0)/commissions.length).toFixed(1) : '0';
  const totalLeads  = brokers.reduce((s, b) => s + Number(b.leads||0), 0);
  document.getElementById('kpiActive').textContent       = activeCount;
  document.getElementById('kpiAvgCommission').textContent = avgComm + '%';
  document.getElementById('kpiTotalLeads').textContent   = totalLeads;

  const isFiltered = searchQuery.trim() || activeNameFilters.size || activeAgencyFilters.size || activeStartFilters.size || activeEndFilters.size || activeStatusFilters.size;
  hint.textContent = isFiltered
    ? `${list.length} result${list.length !== 1 ? 's' : ''} found`
    : `${brokers.length} broker${brokers.length !== 1 ? 's' : ''}`;

  if (!list.length) {
    tbody.innerHTML = `<tr class="no-results-row"><td colspan="8"><div class="no-results-icon"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span>No brokers found</span></div></td></tr>`;
    return;
  }

  const statusLabels = { active: 'Active', expired: 'Expired', upcoming: 'Upcoming' };
  tbody.innerHTML = list.map(({ b, origIndex }) => {
    const status = getStatus(b);
    return `<tr>
      <td><span class="broker-name-text">${escHtml(b.name)}</span></td>
      <td style="color:var(--clr-text-sub)">${escHtml(b.agency||'—')}</td>
      <td style="font-size:.84rem">${fmtDate(b.startDate)}</td>
      <td style="font-size:.84rem">${fmtDate(b.endDate)}</td>
      <td>${b.commission ? `<span class="commission-chip">${b.commission}%</span>` : '—'}</td>
      <td><span class="leads-chip">${Number(b.leads||0)}</span></td>
      <td><span class="status-badge ${status}">${statusLabels[status]}</span></td>
      <td>
        <div class="action-btns">
          <button class="action-btn view"   title="View Details" onclick="openView(${origIndex})"><svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>
          ${window.BROKERS_CFG.canCreate ? `
          <button class="action-btn edit"   title="Edit"         onclick="openEdit(${origIndex})"><svg viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
          <button class="action-btn delete" title="Delete"       onclick="deleteBroker(${origIndex})"><svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg></button>
          ` : ''}
        </div>
      </td>
    </tr>`;
  }).join('');
}

/* ═══════════════════════════════════
   SEARCH
   ═══════════════════════════════════ */
document.getElementById('searchInput').addEventListener('input', e => {
  searchQuery = e.target.value;
  renderTable();
});

/* ═══════════════════════════════════
   SORT
   ═══════════════════════════════════ */
const SORT_BTNS = {
  sortNameBtn:  'name',
  sortAgencyBtn:'agency',
  sortStartBtn: 'startDate',
  sortEndBtn:   'endDate',
  sortCommBtn:  'commission',
  sortLeadsBtn: 'leads',
};

function applySortBtn(field, btnId) {
  const prev = sortAscMap[field];
  if (prev === undefined || prev === null) sortAscMap[field] = true;
  else if (prev === true)  sortAscMap[field] = false;
  else { sortAscMap[field] = null; delete sortAscMap[field]; }
  sortField = sortAscMap[field] != null ? field : null;

  Object.entries(SORT_BTNS).forEach(([id]) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.classList.remove('active-sort');
    btn.querySelector('svg').innerHTML = '<path d="M3 6h18M7 12h10M11 18h2"/>';
  });
  if (sortField) {
    const btn = document.getElementById(btnId);
    if (btn) {
      btn.classList.add('active-sort');
      btn.querySelector('svg').innerHTML = sortAscMap[field]
        ? '<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 4 20 7 17 10" style="stroke-width:1.8"/>'
        : '<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 14 20 17 17 20" style="stroke-width:1.8"/>';
    }
  }
  renderTable();
}
Object.entries(SORT_BTNS).forEach(([btnId, field]) => {
  const btn = document.getElementById(btnId);
  if (btn) btn.addEventListener('click', () => applySortBtn(field, btnId));
});

/* ═══════════════════════════════════
   FILTER UTILITIES
   ═══════════════════════════════════ */
const ALL_FILTER_DROPDOWNS = ['filterNameDropdown','filterAgencyDropdown','filterStartDropdown','filterEndDropdown','filterCommDropdown','filterLeadsDropdown','filterStatusDropdown'];

function closeAllFilters() {
  filterNameOpen = filterAgencyOpen = filterStartOpen = filterEndOpen = filterCommOpen = filterLeadsOpen = filterStatusOpen = false;
  ALL_FILTER_DROPDOWNS.forEach(id => document.getElementById(id)?.classList.remove('open'));
}

function openFilterDropdown(ddId, btnId, isOpen) {
  const currently = isOpen;
  closeAllFilters();
  if (currently) return;
  const dd  = document.getElementById(ddId);
  const btn = document.getElementById(btnId);
  dd.classList.add('open');
  const r = btn.getBoundingClientRect();
  dd.style.top  = (r.bottom + window.scrollY + 4) + 'px';
  dd.style.left = Math.min(r.left + window.scrollX, window.innerWidth - parseInt(dd.style.width||'248')) + 'px';
}

function makeCheckboxFilter(opts) {
  const list = document.getElementById(opts.listId);
  const q = opts.searchId ? (document.getElementById(opts.searchId)?.value||'').toLowerCase() : '';
  list.innerHTML = opts.values
    .filter(v => !q || v.toLowerCase().includes(q))
    .map(v => `
      <label class="filter-item">
        <input type="checkbox" value="${escHtml(v)}" ${opts.activeSet.has(v)?'checked':''}
          onchange="(function(el){if(el.checked) ${opts.varName}.add(el.value); else ${opts.varName}.delete(el.value); renderTable();})(this)">
        <span style="font-size:.83rem;color:var(--clr-text)">${escHtml(opts.labelFn ? opts.labelFn(v) : v)}</span>
      </label>`).join('');
}

// ── Name filter ──
function renderNameFilterList(q='') {
  const list = document.getElementById('filterNameList');
  const ql = q.toLowerCase();
  list.innerHTML = brokers.map(b=>b.name).filter(n=>n.toLowerCase().includes(ql)).map(name=>`
    <label class="filter-item">
      <input type="checkbox" value="${escHtml(name)}" ${activeNameFilters.has(name)?'checked':''}
        onchange="toggleSetFilter(activeNameFilters,'${escHtml(name)}',this.checked)">
      <span style="font-size:.83rem;color:var(--clr-text)">${escHtml(name)}</span>
    </label>`).join('');
}

// ── Agency filter ──
function renderAgencyFilterList(q='') {
  const list = document.getElementById('filterAgencyList');
  const ql = q.toLowerCase();
  const agencies = [...new Set(brokers.map(b=>b.agency||'').filter(Boolean))].sort();
  list.innerHTML = agencies.filter(a=>a.toLowerCase().includes(ql)).map(ag=>`
    <label class="filter-item">
      <input type="checkbox" value="${escHtml(ag)}" ${activeAgencyFilters.has(ag)?'checked':''}
        onchange="toggleSetFilter(activeAgencyFilters,'${escHtml(ag)}',this.checked)">
      <span style="font-size:.83rem;color:var(--clr-text)">${escHtml(ag)}</span>
    </label>`).join('');
}

// ── Date filter tree (year → months) ──
const _dateTreeOpen = { start: new Set(), end: new Set() };
const _activeDateFilters = { start: activeStartFilters, end: activeEndFilters };
const _MONTH_NAMES = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function buildDateTree(field) {
  const key = field === 'start' ? 'startDate' : 'endDate';
  const map = {};
  brokers.forEach(b => {
    const d = b[key] || '';
    if (!d) return;
    const year  = d.slice(0,4);
    const month = d.slice(0,7);
    if (!map[year]) map[year] = new Set();
    map[year].add(month);
  });
  return map;
}

function renderDateFilter(field) {
  const containerId = 'filter' + (field === 'start' ? 'Start' : 'End') + 'List';
  const container   = document.getElementById(containerId);
  const tree        = buildDateTree(field);
  const activeSet   = _activeDateFilters[field];
  const openSet     = _dateTreeOpen[field];

  container.innerHTML = '';
  Object.keys(tree).sort().reverse().forEach(year => {
    const months     = [...tree[year]].sort();
    const allChecked = months.every(m => activeSet.has(m));
    const someChecked= months.some(m  => activeSet.has(m));
    const isOpen     = openSet.has(year);

    const wrapper  = document.createElement('div');
    const yearRow  = document.createElement('div');
    yearRow.className = 'date-tree-year';

    const lbl = document.createElement('label');
    lbl.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:pointer;flex:1';
    lbl.onclick = e => e.stopPropagation();

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.style.accentColor = 'var(--clr-orange)';
    cb.checked = allChecked;
    cb.indeterminate = !allChecked && someChecked;
    cb.onchange = () => {
      months.forEach(m => { if (cb.checked) activeSet.add(m); else activeSet.delete(m); });
      renderDateFilter(field); renderTable();
    };

    const yearSpan = document.createElement('span');
    yearSpan.textContent = year;
    lbl.appendChild(cb); lbl.appendChild(yearSpan);

    const chevron = document.createElement('span');
    chevron.className = 'date-tree-chevron' + (isOpen ? ' open' : '');
    chevron.innerHTML = '&#9658;';

    yearRow.appendChild(lbl); yearRow.appendChild(chevron);
    yearRow.onclick = () => {
      if (openSet.has(year)) openSet.delete(year); else openSet.add(year);
      monthsDiv.classList.toggle('open', openSet.has(year));
      chevron.classList.toggle('open', openSet.has(year));
    };

    const monthsDiv = document.createElement('div');
    monthsDiv.className = 'date-tree-months' + (isOpen ? ' open' : '');

    months.forEach(ym => {
      const mIdx  = parseInt(ym.slice(5)) - 1;
      const mName = _MONTH_NAMES[mIdx] || ym;
      const mLabel = document.createElement('label');
      mLabel.className = 'filter-item';
      const mCb = document.createElement('input');
      mCb.type = 'checkbox';
      mCb.style.accentColor = 'var(--clr-orange)';
      mCb.checked = activeSet.has(ym);
      mCb.onchange = () => {
        if (mCb.checked) activeSet.add(ym); else activeSet.delete(ym);
        cb.checked = months.every(m => activeSet.has(m));
        cb.indeterminate = !cb.checked && months.some(m => activeSet.has(m));
        renderTable();
      };
      const mSpan = document.createElement('span');
      mSpan.style.cssText = 'font-size:.83rem;color:var(--clr-text)';
      mSpan.textContent = mName;
      mLabel.appendChild(mCb); mLabel.appendChild(mSpan);
      monthsDiv.appendChild(mLabel);
    });

    wrapper.appendChild(yearRow); wrapper.appendChild(monthsDiv);
    container.appendChild(wrapper);
  });

  if (!Object.keys(tree).length)
    container.innerHTML = '<div style="padding:10px 14px;font-size:.82rem;color:var(--clr-text-sub)">No dates available</div>';
}

// ── Status filter ──
function renderStatusFilterList() {
  const list = document.getElementById('filterStatusList');
  const statuses = ['active','expired','upcoming'];
  const labels   = { active: 'Active', expired: 'Expired', upcoming: 'Upcoming' };
  list.innerHTML = statuses.map(s=>`
    <label class="filter-item">
      <input type="checkbox" value="${s}" ${activeStatusFilters.has(s)?'checked':''}
        onchange="toggleSetFilter(activeStatusFilters,'${s}',this.checked)">
      <span style="font-size:.83rem;color:var(--clr-text)">${labels[s]}</span>
    </label>`).join('');
}

function toggleSetFilter(set, val, checked) {
  if (checked) set.add(val); else set.delete(val);
  renderTable();
}

// Wire up filter buttons
document.getElementById('filterNameBtn').addEventListener('click', e => {
  e.stopPropagation();
  const was = filterNameOpen;
  openFilterDropdown('filterNameDropdown','filterNameBtn', was);
  filterNameOpen = !was;
  if (filterNameOpen) { renderNameFilterList(); document.getElementById('filterNameSearch').focus(); }
});
document.getElementById('filterNameSearch').addEventListener('input', e => renderNameFilterList(e.target.value));
document.getElementById('filterNameSelectAll').addEventListener('click', e => { e.stopPropagation(); brokers.forEach(b=>activeNameFilters.add(b.name)); renderNameFilterList(); renderTable(); });
document.getElementById('filterNameClearAll').addEventListener('click',  e => { e.stopPropagation(); activeNameFilters.clear(); renderNameFilterList(); renderTable(); });

document.getElementById('filterAgencyBtn').addEventListener('click', e => {
  e.stopPropagation();
  const was = filterAgencyOpen;
  openFilterDropdown('filterAgencyDropdown','filterAgencyBtn', was);
  filterAgencyOpen = !was;
  if (filterAgencyOpen) { renderAgencyFilterList(); document.getElementById('filterAgencySearch').focus(); }
});
document.getElementById('filterAgencySearch').addEventListener('input', e => renderAgencyFilterList(e.target.value));
document.getElementById('filterAgencySelectAll').addEventListener('click', e => { e.stopPropagation(); [...new Set(brokers.map(b=>b.agency||'').filter(Boolean))].forEach(a=>activeAgencyFilters.add(a)); renderAgencyFilterList(); renderTable(); });
document.getElementById('filterAgencyClearAll').addEventListener('click',  e => { e.stopPropagation(); activeAgencyFilters.clear(); renderAgencyFilterList(); renderTable(); });

document.getElementById('filterStartBtn').addEventListener('click', e => {
  e.stopPropagation();
  const was = filterStartOpen;
  openFilterDropdown('filterStartDropdown','filterStartBtn', was);
  filterStartOpen = !was;
  if (filterStartOpen) renderDateFilter('start');
});
document.getElementById('filterStartSelectAll').addEventListener('click', e => { e.stopPropagation(); const t=buildDateTree('start'); Object.values(t).forEach(s=>s.forEach(m=>activeStartFilters.add(m))); renderDateFilter('start'); renderTable(); });
document.getElementById('filterStartClearAll').addEventListener('click',  e => { e.stopPropagation(); activeStartFilters.clear(); renderDateFilter('start'); renderTable(); });

document.getElementById('filterEndBtn').addEventListener('click', e => {
  e.stopPropagation();
  const was = filterEndOpen;
  openFilterDropdown('filterEndDropdown','filterEndBtn', was);
  filterEndOpen = !was;
  if (filterEndOpen) renderDateFilter('end');
});
document.getElementById('filterEndSelectAll').addEventListener('click', e => { e.stopPropagation(); const t=buildDateTree('end'); Object.values(t).forEach(s=>s.forEach(m=>activeEndFilters.add(m))); renderDateFilter('end'); renderTable(); });
document.getElementById('filterEndClearAll').addEventListener('click',  e => { e.stopPropagation(); activeEndFilters.clear(); renderDateFilter('end'); renderTable(); });

document.getElementById('filterCommBtn').addEventListener('click', e => {
  e.stopPropagation();
  const was = filterCommOpen;
  openFilterDropdown('filterCommDropdown','filterCommBtn', was);
  filterCommOpen = !was;
  if (!was) {
    const vals = brokers.map(b => Number(b.commission||0)).filter(v => !isNaN(v));
    if (vals.length) {
      document.getElementById('commMin').placeholder = Math.min(...vals);
      document.getElementById('commMax').placeholder = Math.max(...vals);
    }
  }
});
document.getElementById('filterCommClear').addEventListener('click', e => {
  e.stopPropagation();
  document.getElementById('commMin').value = '';
  document.getElementById('commMax').value = '';
  renderTable();
});

document.getElementById('filterLeadsBtn').addEventListener('click', e => {
  e.stopPropagation();
  const was = filterLeadsOpen;
  openFilterDropdown('filterLeadsDropdown','filterLeadsBtn', was);
  filterLeadsOpen = !was;
  if (!was) {
    const vals = brokers.map(b => Number(b.leads||0)).filter(v => !isNaN(v));
    if (vals.length) {
      document.getElementById('leadsMin').placeholder = Math.min(...vals);
      document.getElementById('leadsMax').placeholder = Math.max(...vals);
    }
  }
});
document.getElementById('filterLeadsClear').addEventListener('click', e => {
  e.stopPropagation();
  document.getElementById('leadsMin').value = '';
  document.getElementById('leadsMax').value = '';
  renderTable();
});

document.getElementById('filterStatusBtn').addEventListener('click', e => {
  e.stopPropagation();
  const was = filterStatusOpen;
  openFilterDropdown('filterStatusDropdown','filterStatusBtn', was);
  filterStatusOpen = !was;
  if (filterStatusOpen) renderStatusFilterList();
});
document.getElementById('filterStatusSelectAll').addEventListener('click', e => { e.stopPropagation(); ['active','expired','upcoming'].forEach(s=>activeStatusFilters.add(s)); renderStatusFilterList(); renderTable(); });
document.getElementById('filterStatusClearAll').addEventListener('click',  e => { e.stopPropagation(); activeStatusFilters.clear(); renderStatusFilterList(); renderTable(); });

document.addEventListener('click', e => {
  const filterEls = ALL_FILTER_DROPDOWNS.map(id=>document.getElementById(id));
  const filterBtns = ['filterNameBtn','filterAgencyBtn','filterStartBtn','filterEndBtn','filterCommBtn','filterLeadsBtn','filterStatusBtn'].map(id=>document.getElementById(id));
  if (![...filterEls, ...filterBtns].some(el=>el?.contains(e.target))) closeAllFilters();
});

/* ═══════════════════════════════════
   TOAST
   ═══════════════════════════════════ */
function showToast(type, title, msg) {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const ok  = `<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`;
  const err = `<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
  t.innerHTML = `<div class="toast-icon">${type==='success'?ok:err}</div><div class="toast-body"><div class="toast-title">${escHtml(title)}</div><div class="toast-msg">${escHtml(msg)}</div></div><button class="toast-dismiss" onclick="dismissToast(this.parentElement)">✕</button>`;
  c.appendChild(t);
  setTimeout(() => dismissToast(t), 4500);
}
function dismissToast(el) {
  if (!el || el.classList.contains('toast-out')) return;
  el.classList.add('toast-out');
  setTimeout(() => el.remove(), 320);
}

/* ═══════════════════════════════════
   CREATE
   ═══════════════════════════════════ */
function resetCreateForm() {
  ['c_name','c_email','c_password','c_agency_id','c_phone','c_location','c_commission','c_startDate','c_endDate','c_notes'].forEach(id => {
    const el = document.getElementById(id); if (el) el.value = '';
  });
  cPasswordTypedByUser = false;
}
function openCreate() {
  resetCreateForm();
  populateAgencySelect('c_agency_id');
  document.getElementById('createModal').classList.add('open');

  clearBrowserRestoredFieldsSoon(false);
}

function closeCreate() { document.getElementById('createModal').classList.remove('open'); }

if (document.getElementById('btnCreate')) {
  document.getElementById('btnCreate').addEventListener('click', openCreate);
}
document.getElementById('createModalClose').addEventListener('click', closeCreate);
document.getElementById('createCancel').addEventListener('click', closeCreate);
document.getElementById('createModal').addEventListener('click', e => { if (e.target === e.currentTarget) closeCreate(); });

document.getElementById('createSave').addEventListener('click', async () => {
  const name = document.getElementById('c_name').value.trim();
  if (!name) { highlight('c_name'); return; }
  const email = document.getElementById('c_email').value.trim();
  if (!email) { highlight('c_email'); return; }
  const password = document.getElementById('c_password').value;
  if (!password) { highlight('c_password'); return; }

  const payload = {
    name,
    email,
    password,
    agencyId:   document.getElementById('c_agency_id').value || '',
    agency:     agencyNameById(document.getElementById('c_agency_id').value),
    phone:      document.getElementById('c_phone').value.trim(),
    location:   document.getElementById('c_location').value.trim(),
    commission: document.getElementById('c_commission').value.trim(),
    startDate:  document.getElementById('c_startDate').value,
    endDate:    document.getElementById('c_endDate').value,
    notes:      document.getElementById('c_notes').value.trim(),
  };

  try {
    const response = await fetch(window.BROKERS_CFG.createUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Failed to create broker');
    
    // Add to local array and re-render
    const broker = {
      id:         result.broker_id,
      name:       payload.name,
      email:      payload.email,
      agency:     payload.agency,
      agencyId:   payload.agencyId || null,
      phone:      payload.phone,
      location:   payload.location,
      commission: payload.commission,
      startDate:  payload.startDate,
      endDate:    payload.endDate,
      notes:      payload.notes,
      leads:      0,
    };
    brokers.push(broker);
    closeCreate();
    renderTable(); 
    renderNameFilterList();
    renderAgencyFilterList();
    showToast('success', 'Broker Created', `"${payload.name}" has been added with 0 leads.`);
  } catch (error) {
    showToast('error', 'Error', error.message || 'An error occurred while creating broker.');
  }
});

/* ═══════════════════════════════════
   EDIT
   ═══════════════════════════════════ */
function openEdit(index) {
  editingIndex = index;
  edPasswordTypedByUser = false;
  const b = brokers[index];
  document.getElementById('editModalSub').textContent = b.agency ? `${b.agency}` : 'Independent Broker';
  document.getElementById('editModalBody').innerHTML = `
    <div class="form-desc-banner">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <p>Update this broker's information. You can also manually adjust the <strong>leads count</strong> if needed.</p>
    </div>
    <div class="form-group"><label class="form-label">Broker Name *</label><input type="text" class="form-input" id="ed_name" value="${escHtml(b.name)}"></div>
    <div class="form-row">
      <div><label class="form-label">Login Email</label><input type="email" class="form-input" id="ed_email" value="${escHtml(b.email||'')}"></div>
      <div><label class="form-label">New Password</label>
      <input
  type="password"
  class="form-input"
  id="ed_password"
  name="broker_edit_password_no_autofill"
  placeholder="Leave blank to keep current"
  value=""
  autocomplete="new-password"
  autocorrect="off"
  autocapitalize="off"
  spellcheck="false"
  readonly
  data-autofill-guard="clear"
  data-lpignore="true"
  data-1p-ignore="true"
>

      </div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Agency</label><select class="form-input" id="ed_agency_id">${agencyOptions(b.agencyId)}</select></div>
      <div><label class="form-label">Phone</label><input type="tel" class="form-input" id="ed_phone" value="${escHtml(b.phone||'')}"></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Location / Area</label><input type="text" class="form-input" id="ed_location" value="${escHtml(b.location||'')}"></div>
      <div><label class="form-label">Commission (%)</label><input type="number" class="form-input" id="ed_commission" value="${b.commission||''}" min="0" max="100" step="0.1"></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Contract Start</label><input type="date" class="form-input" id="ed_startDate" value="${b.startDate||''}"></div>
      <div><label class="form-label">Contract End</label><input type="date" class="form-input" id="ed_endDate" value="${b.endDate||''}"></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Number of Leads</label><input type="number" class="form-input" id="ed_leads" value="${Number(b.leads||0)}" min="0"></div>
      <div></div>
    </div>
    <div class="form-group"><label class="form-label">Notes</label><textarea class="form-textarea" id="ed_notes">${escHtml(b.notes||'')}</textarea></div>`;
  document.getElementById('editModal').classList.add('open');
  clearBrowserRestoredFieldsSoon(false);
}
function closeEdit() { document.getElementById('editModal').classList.remove('open'); editingIndex = null; }

document.getElementById('editModalClose').addEventListener('click', closeEdit);
document.getElementById('editCancel').addEventListener('click', closeEdit);
document.getElementById('editModal').addEventListener('click', e => { if (e.target === e.currentTarget) closeEdit(); });

document.getElementById('editSave').addEventListener('click', async () => {
  if (editingIndex === null) return;
  const name = document.getElementById('ed_name').value.trim();
  if (!name) { highlight('ed_name'); return; }

  const b = brokers[editingIndex];
  const oldName = b.name;
  
  const payload = {
    name,
    email:      document.getElementById('ed_email').value.trim(),
    password:   document.getElementById('ed_password').value,
    agencyId:   document.getElementById('ed_agency_id').value || '',
    agency:     agencyNameById(document.getElementById('ed_agency_id').value),
    phone:      document.getElementById('ed_phone').value.trim(),
    location:   document.getElementById('ed_location').value.trim(),
    commission: document.getElementById('ed_commission').value.trim(),
    startDate:  document.getElementById('ed_startDate').value,
    endDate:    document.getElementById('ed_endDate').value,
    leads:      Math.max(0, parseInt(document.getElementById('ed_leads').value)||0),
    notes:      document.getElementById('ed_notes').value.trim(),
  };

  const editUrl = window.BROKERS_CFG.editTmplUrl.replace('00000000-0000-0000-0000-000000000000', b.id);

  try {
    const response = await fetch(editUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Failed to update broker');

    b.name       = payload.name;
    b.email      = payload.email;
    b.agency     = payload.agency;
    b.agencyId   = payload.agencyId || null;
    b.phone      = payload.phone;
    b.location   = payload.location;
    b.commission = payload.commission;
    b.startDate  = payload.startDate;
    b.endDate    = payload.endDate;
    b.leads      = payload.leads;
    b.notes      = payload.notes;

    if (activeNameFilters.has(oldName)) { activeNameFilters.delete(oldName); activeNameFilters.add(payload.name); }
    closeEdit();
    renderTable(); 
    renderNameFilterList();
    renderAgencyFilterList();
    showToast('success', 'Broker Updated', `"${payload.name}" has been updated.`);
  } catch (error) {
    showToast('error', 'Error', error.message || 'An error occurred while updating broker.');
  }
});

/* ═══════════════════════════════════
   VIEW
   ═══════════════════════════════════ */
function openView(index) {
  const b      = brokers[index];
  const status = getStatus(b);
  const statusLabels = { active: 'Active Contract', expired: 'Expired Contract', upcoming: 'Upcoming Contract' };
  document.getElementById('viewTitle').textContent = b.name;
  document.getElementById('viewSub').textContent   = b.agency || 'Independent Broker';

  document.getElementById('viewModalBody').innerHTML = `
    <div class="view-hero">
      <div class="view-hero-icon">
        <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      </div>
      <div>
        <div class="view-hero-name">${escHtml(b.name)}</div>
        <div class="view-hero-meta">${escHtml(b.agency||'Independent')} · <span class="status-badge ${status}" style="font-size:.68rem;padding:2px 8px">${statusLabels[status]}</span></div>
      </div>
      ${b.commission ? `<div class="view-hero-commission"><div class="view-hero-commission-val">${b.commission}%</div><div class="view-hero-commission-lbl">Commission</div></div>` : ''}
    </div>
    <div class="view-stat-row">
      <div class="view-stat">
        <div class="view-stat-val" style="color:var(--clr-orange-dk)">${fmtDate(b.startDate)}</div>
        <div class="view-stat-lbl">Contract Start</div>
      </div>
      <div class="view-stat">
        <div class="view-stat-val" style="color:var(--clr-orange-dk)">${fmtDate(b.endDate)}</div>
        <div class="view-stat-lbl">Contract End</div>
      </div>
      <div class="view-stat">
        <div class="view-stat-val" style="color:#8e44ad">${Number(b.leads||0)}</div>
        <div class="view-stat-lbl">Total Leads</div>
      </div>
    </div>
    <div class="view-sub-card">
      <div class="view-sub-card-title">Contact & Location</div>
      <div class="view-kv-grid">
        <div><div class="view-kv-label">Phone</div><div class="view-kv-val">${escHtml(b.phone||'—')}</div></div>
        <div><div class="view-kv-label">Location / Area</div><div class="view-kv-val">${escHtml(b.location||'—')}</div></div>
        <div style="grid-column:1/-1"><div class="view-kv-label">Notes</div><div class="view-kv-val">${escHtml(b.notes||'—')}</div></div>
      </div>
    </div>`;
  document.getElementById('viewModal').classList.add('open');
}
function closeView() { document.getElementById('viewModal').classList.remove('open'); }
document.getElementById('viewModalClose').addEventListener('click', closeView);
document.getElementById('viewClose').addEventListener('click', closeView);
document.getElementById('viewModal').addEventListener('click', e => { if (e.target === e.currentTarget) closeView(); });

/* ═══════════════════════════════════
   DELETE
   ═══════════════════════════════════ */
function deleteBroker(index) {
  const b = brokers[index];
  const name = b.name;
  Swal.fire({
    title: 'Delete Broker?',
    html: `Are you sure you want to delete <strong>${name}</strong>?<br>This action cannot be undone.`,
    icon: 'question',
    showCancelButton: true,
    confirmButtonText: 'Yes, delete',
    cancelButtonText: 'Cancel',
    reverseButtons: true,
    focusCancel: true,
  }).then(async result => {
    if (result.isConfirmed) {
      const deleteUrl = window.BROKERS_CFG.deleteTmplUrl.replace('00000000-0000-0000-0000-000000000000', b.id);
      try {
        const response = await fetch(deleteUrl, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
          },
        });
        const res = await response.ok ? await response.json() : null;
        if (!response.ok) throw new Error((res && res.error) || 'Failed to delete broker');

        activeNameFilters.delete(name);
        brokers.splice(index, 1);
        renderTable(); 
        renderNameFilterList();
        renderAgencyFilterList();
        showToast('success', 'Broker Deleted', `"${name}" has been removed.`);
      } catch (error) {
        showToast('error', 'Error', error.message || 'An error occurred while deleting broker.');
      }
    }
  });
}

/* ═══════════════════════════════════
   HIGHLIGHT
   ═══════════════════════════════════ */
function highlight(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('error');
  el.focus();
  setTimeout(() => el.classList.remove('error'), 1500);
}

/* ═══════════════════════════════════
   AGENCIES (task 1)
   ═══════════════════════════════════ */
let agencies = [];
let editingAgencyId = null;

function _agHeaders() { return { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }; }
function agencyNameById(id) { const a = agencies.find(a => a.id === id); return a ? a.name : ''; }
function agencyOptions(selectedId) {
  return ['<option value="">— Independent (no agency) —</option>']
    .concat(agencies.map(a =>
      `<option value="${a.id}" ${a.id === selectedId ? 'selected' : ''}>${escHtml(a.name)}</option>`
    )).join('');
}
function populateAgencySelect(selectId, selectedId) {
  const el = document.getElementById(selectId);
  if (el) el.innerHTML = agencyOptions(selectedId);
}
async function loadAgencies() {
  try {
    const r = await fetch(window.BROKERS_CFG.agencyListUrl);
    if (r.ok) agencies = (await r.json()).agencies || [];
  } catch (e) { console.error('loadAgencies failed', e); }
}

function renderAgencyList() {
  const wrap = document.getElementById('agencyList');
  if (!wrap) return;
  if (!agencies.length) { wrap.innerHTML = '<p style="color:var(--clr-text-sub);font-size:.84rem">No agencies yet.</p>'; return; }
  wrap.innerHTML = agencies.map(a => `
    <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px;border:1px solid var(--clr-border);border-radius:8px;margin-bottom:8px">
      <div>
        <div style="font-weight:600">${escHtml(a.name)}</div>
        <div style="font-size:.76rem;color:var(--clr-text-sub)">${escHtml(a.location||'—')} · ${a.brokerCount} broker(s)${a.commission!=null?' · '+a.commission+'%':''}</div>
      </div>
      <div style="display:flex;gap:6px">
        <button class="action-btn edit" onclick="startEditAgency('${a.id}')">Edit</button>
        <button class="action-btn deactivate" onclick="deleteAgency('${a.id}')">Delete</button>
      </div>
    </div>`).join('');
}

function _agFormVals() {
  const c = document.getElementById('a_commission').value.trim();
  return {
    name: document.getElementById('a_name').value.trim(),
    phone: document.getElementById('a_phone').value.trim(),
    email: document.getElementById('a_email').value.trim(),
    location: document.getElementById('a_location').value.trim(),
    commission: c === '' ? '' : c,
    status: document.getElementById('a_status').value,
    startDate: document.getElementById('a_startDate').value,
    endDate: document.getElementById('a_endDate').value,
    notes: document.getElementById('a_notes').value.trim(),
  };
}
function resetAgencyForm() {
  editingAgencyId = null;
  ['a_name','a_phone','a_email','a_location','a_commission','a_startDate','a_endDate','a_notes']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  document.getElementById('a_status').value = 'ACTIVE';
  document.getElementById('agencySave').textContent = 'Add Agency';
  document.getElementById('agencyFormReset').style.display = 'none';
}
function startEditAgency(id) {
  const a = agencies.find(a => a.id === id); if (!a) return;
  editingAgencyId = id;
  document.getElementById('a_name').value = a.name || '';
  document.getElementById('a_phone').value = a.phone || '';
  document.getElementById('a_email').value = a.email || '';
  document.getElementById('a_location').value = a.location || '';
  document.getElementById('a_commission').value = a.commission != null ? a.commission : '';
  document.getElementById('a_status').value = a.status || 'ACTIVE';
  document.getElementById('a_startDate').value = a.startDate || '';
  document.getElementById('a_endDate').value = a.endDate || '';
  document.getElementById('a_notes').value = a.notes || '';
  document.getElementById('agencySave').textContent = 'Save Changes';
  document.getElementById('agencyFormReset').style.display = 'inline-flex';
}
async function deleteAgency(id) {
  const a = agencies.find(a => a.id === id); if (!a) return;
  if (window.Swal) {
    const res = await Swal.fire({ icon: 'warning', title: `Delete "${a.name}"?`,
      text: 'Brokers in this agency become independent; their leads are unchanged.',
      showCancelButton: true, confirmButtonColor: '#c0392b', confirmButtonText: 'Delete' });
    if (!res.isConfirmed) return;
  }
  const url = window.BROKERS_CFG.agencyDeleteTmplUrl.replace('00000000-0000-0000-0000-000000000000', id);
  try {
    const r = await fetch(url, { method: 'POST', headers: _agHeaders() });
    if (!r.ok) throw new Error((await r.json()).error || 'Delete failed');
    await loadAgencies(); renderAgencyList(); await loadBrokers();
    showToast('success', 'Agency Deleted', `"${a.name}" removed.`);
  } catch (e) { showToast('error', 'Error', e.message); }
}

async function saveAgency() {
  const vals = _agFormVals();
  if (!vals.name) { highlight('a_name'); return; }
  const isEdit = !!editingAgencyId;
  const url = isEdit
    ? window.BROKERS_CFG.agencyEditTmplUrl.replace('00000000-0000-0000-0000-000000000000', editingAgencyId)
    : window.BROKERS_CFG.agencyCreateUrl;
  try {
    const r = await fetch(url, { method: 'POST', headers: _agHeaders(), body: JSON.stringify(vals) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Save failed');
    await loadAgencies(); renderAgencyList(); resetAgencyForm(); await loadBrokers();
    showToast('success', isEdit ? 'Agency Updated' : 'Agency Created', `"${vals.name}" saved.`);
  } catch (e) { showToast('error', 'Error', e.message); }
}

function openAgencyModal() { resetAgencyForm(); renderAgencyList(); document.getElementById('agencyModal').classList.add('open'); }
function closeAgencyModal() { document.getElementById('agencyModal').classList.remove('open'); }

if (document.getElementById('btnAgencies')) {
  document.getElementById('btnAgencies').addEventListener('click', openAgencyModal);
  document.getElementById('agencyModalClose').addEventListener('click', closeAgencyModal);
  document.getElementById('agencyModal').addEventListener('click', e => { if (e.target === e.currentTarget) closeAgencyModal(); });
  document.getElementById('agencySave').addEventListener('click', saveAgency);
  document.getElementById('agencyFormReset').addEventListener('click', resetAgencyForm);
}

/* ═══════════════════════════════════
   INIT
   ═══════════════════════════════════ */

const AUTOFILL_CLEAR_IDS = [
  'searchInput',
  'filterNameSearch',
  'filterAgencySearch',
  'commMin',
  'commMax',
  'leadsMin',
  'leadsMax',
  'c_password',
  'ed_password'
];

function clearBrowserRestoredFields(shouldRender = false) {
  AUTOFILL_CLEAR_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;

    el.value = '';
    el.defaultValue = '';
  });

  searchQuery = '';

  if (shouldRender && typeof renderTable === 'function') {
    renderTable();
  }
}

function clearBrowserRestoredFieldsSoon(shouldRender = false) {
  clearBrowserRestoredFields(shouldRender);

  requestAnimationFrame(() => clearBrowserRestoredFields(shouldRender));
  setTimeout(() => clearBrowserRestoredFields(shouldRender), 50);
  setTimeout(() => clearBrowserRestoredFields(shouldRender), 250);
  setTimeout(() => clearBrowserRestoredFields(shouldRender), 750);
}

// Clear immediately.
clearBrowserRestoredFieldsSoon(false);

// Handles normal load and browser back/forward cache restores.
window.addEventListener('load', () => clearBrowserRestoredFieldsSoon(true));
window.addEventListener('pageshow', () => clearBrowserRestoredFieldsSoon(true));



/* ═══════════════════════════════════
   STRONG AUTOFILL / HISTORY GUARD
   ═══════════════════════════════════ */

const GUARDED_EMPTY_FIELDS = [
  'searchInput',
  'c_password',
  'ed_password'
];

let searchWasTypedByUser = false;

function clearFieldById(id) {
  const el = document.getElementById(id);
  if (!el) return;

  el.value = '';
  el.defaultValue = '';

  if (id === 'searchInput') {
    searchQuery = '';
  }
}

function clearGuardedEmptyFields() {
  GUARDED_EMPTY_FIELDS.forEach(clearFieldById);

  if (typeof renderTable === 'function') {
    renderTable();
  }
}

function clearGuardedEmptyFieldsSoon() {
  clearGuardedEmptyFields();

  requestAnimationFrame(clearGuardedEmptyFields);
  setTimeout(clearGuardedEmptyFields, 50);
  setTimeout(clearGuardedEmptyFields, 150);
  setTimeout(clearGuardedEmptyFields, 400);
  setTimeout(clearGuardedEmptyFields, 900);
}

function unlockGuardedField(el) {
  if (!el) return;

  el.removeAttribute('readonly');

  // Chrome/password managers sometimes inject exactly on focus,
  // so clear shortly after unlocking.
  setTimeout(() => {
    if (el.id === 'searchInput' && searchWasTypedByUser) return;
    if (el.id === 'c_password' && cPasswordTypedByUser) return;
    if (el.id === 'ed_password' && edPasswordTypedByUser) return;
    el.value = '';
    el.defaultValue = '';

    if (el.id === 'searchInput') {
      searchQuery = '';
      renderTable();
    }
  }, 80);
}

document.addEventListener('focusin', e => {
  const el = e.target;
  if (!el || !el.matches('[data-autofill-guard="clear"]')) return;

  unlockGuardedField(el);
});

document.addEventListener('mousedown', e => {
  const el = e.target;
  if (!el || !el.matches('[data-autofill-guard="clear"]')) return;

  unlockGuardedField(el);
});

document.addEventListener('input', e => {
  if (e.target) {
    if (e.target.id === 'searchInput') {
      searchWasTypedByUser = true;
    } else if (e.target.id === 'c_password') {
      cPasswordTypedByUser = true;
    } else if (e.target.id === 'ed_password') {
      edPasswordTypedByUser = true;
    }
  }
});

document.addEventListener('change', e => {
  if (e.target) {
    if (e.target.id === 'c_password') {
      cPasswordTypedByUser = true;
    } else if (e.target.id === 'ed_password') {
      edPasswordTypedByUser = true;
    }
  }
});

// Some autofill/history injections happen after random clicks/actions.
document.addEventListener('click', () => {
  setTimeout(() => {
    const searchInput = document.getElementById('searchInput');

    if (searchInput && !searchWasTypedByUser && searchInput.value) {
      clearFieldById('searchInput');
      renderTable();
    }

    ['c_password', 'ed_password'].forEach(id => {
      const el = document.getElementById(id);
      if (el && el.value && document.activeElement !== el) {
        if (id === 'c_password' && cPasswordTypedByUser) return;
        if (id === 'ed_password' && edPasswordTypedByUser) return;
        clearFieldById(id);
      }
    });
  }, 120);
}, true);

window.addEventListener('load', clearGuardedEmptyFieldsSoon);
window.addEventListener('pageshow', clearGuardedEmptyFieldsSoon);


// Load data, then clear again in case browser autofill ran late.
loadAgencies()
  .then(loadBrokers)
  .then(() => clearBrowserRestoredFieldsSoon(true));
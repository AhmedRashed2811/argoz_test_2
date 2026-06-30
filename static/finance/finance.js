/* ─── Server-backed data layer (replaces the static mock; see finance views) ── */
function _cfg() { return window.FINANCE_CFG || {}; }
function _headers() { return {'Content-Type':'application/json','X-CSRFToken':_cfg().csrf||''}; }
function _decideUrl(id) { return _cfg().decideTmpl.replace('00000000-0000-0000-0000-000000000000', id); }
async function fetchQueue() {
  try {
    const r = await fetch(_cfg().listUrl, {headers:{'X-CSRFToken':_cfg().csrf||''}, credentials:'same-origin'});
    if (r.ok) { const data = await r.json(); campaigns = data.campaigns||[]; kpis = data.kpis||kpis; }
  } catch(e) { console.error('fetchQueue failed:', e); }
  return campaigns;
}
async function apiSend(url, body) {
  const r = await fetch(url, {method:'POST', headers:_headers(), credentials:'same-origin',
    body: body ? JSON.stringify(body) : undefined});
  let data = {}; try { data = await r.json(); } catch(e) {}
  if (!r.ok) throw new Error(data.error || ('Request failed (' + r.status + ')'));
  return data;
}

/* ─── State ─── */
let campaigns = [];
let kpis = { approvedToday: 0, rejectedToday: 0 };
let currentPage = 1;
let totalPages = 1;
const PER_PAGE = 5;
let activeReviewId = null;
let searchQuery = (new URLSearchParams(window.location.search)).get('search') || '';
let sortField = null, sortAscMap = {};
let activeNameFilters = new Set(), activeTypeFilters = new Set(), activeApprovalFilters = new Set(), activeDateFilters = new Set();
let filterNameOpen=false, filterTypeOpen=false, filterBudgetOpen=false, filterDateOpen=false, filterApprovalOpen=false;

/* ─── Helpers ─── */
function fmtBudget(n){ return 'EGP ' + Number(n).toLocaleString('en-EG'); }
function fmtNumber(n){ return Number(n).toLocaleString('en-EG'); }
function fmtDate(d){
  if(!d) return '—';
  const [y,m,day] = d.split('-');
  return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][parseInt(m)-1]+' '+parseInt(day)+', '+y;
}
function approvalBadge(status){
  const map = { pending:'pending', approved:'approved', semi:'semi', 'not-approved':'not-approved' };
  const labels = { pending:'Pending', approved:'Approved', semi:'Semi Approved', 'not-approved':'Not Approved' };
  const cls = map[status] || 'pending';
  return `<span class="approval-badge ${cls}"><span class="dot"></span>${labels[status]||status}</span>`;
}
function typeChips(types){ return types.map(t=>`<span class="type-chip">${t}</span>`).join(''); }

/* ─── KPI Render ─── */
function renderKPIs(){
  const pending = campaigns.filter(c=>c.approval==='pending').length;
  const pendingBudget = campaigns.filter(c=>c.approval==='pending').reduce((s,c)=>s+c.budget,0);
  document.getElementById('kpiPending').textContent = pending;
  document.getElementById('kpiBudgetPending').textContent = fmtBudget(pendingBudget);
  document.getElementById('kpiApprovedToday').textContent = kpis.approvedToday;
  document.getElementById('kpiRejectedToday').textContent = kpis.rejectedToday;
}

/* ─── Table Render ─── */
function getFiltered(){
  const q = searchQuery.toLowerCase();
  let list = campaigns.filter(c=>{
    if(q && !c.name.toLowerCase().includes(q) && !c.submittedBy.toLowerCase().includes(q) && String(c.id).toLowerCase() !== q) return false;
    if(activeNameFilters.size && !activeNameFilters.has(c.name)) return false;
    if(activeApprovalFilters.size && !activeApprovalFilters.has(c.approval)) return false;
    if(activeTypeFilters.size && !c.types.some(t=>activeTypeFilters.has(t))) return false;
    if(activeDateFilters.size && !activeDateFilters.has(c.submittedDate.slice(0,7))) return false;
    return true;
  });
  const bMin = Number(document.getElementById('budgetMin')?.value||0), bMax = Number(document.getElementById('budgetMax')?.value||0);
  if(bMin>0) list = list.filter(c=>c.budget>=bMin);
  if(bMax>0) list = list.filter(c=>c.budget<=bMax);
  if(sortField && sortAscMap[sortField]!=null){
    const asc = sortAscMap[sortField];
    list = [...list].sort((a,b)=>{
      if(sortField==='budget') return asc ? a.budget-b.budget : b.budget-a.budget;
      if(sortField==='submittedDate') return asc ? a.submittedDate.localeCompare(b.submittedDate) : b.submittedDate.localeCompare(a.submittedDate);
      const va = String(a[sortField]||''), vb = String(b[sortField]||'');
      return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }
  return list;
}
function renderTable(){
  const filtered = getFiltered();
  const total = filtered.length;
  totalPages = Math.max(1, Math.ceil(total/PER_PAGE));
  if(currentPage > totalPages) currentPage = totalPages;
  const slice = filtered.slice((currentPage-1)*PER_PAGE, currentPage*PER_PAGE);
  const tbody = document.getElementById('tableBody');
  if(!slice.length){
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:48px;color:var(--clr-text-sub);font-size:.9rem">No campaigns match your filters.</td></tr>`;
  } else {
    tbody.innerHTML = slice.map((c)=>`
      <tr>
        <td style="text-align:left"><span class="campaign-name-text">${c.name}</span><div style="font-size:.75rem;color:var(--clr-text-sub);margin-top:2px">${c.target}</div></td>
        <td><div class="type-chips">${typeChips(c.types)}</div></td>
        <td><span class="budget-val">${fmtNumber(c.budget)}</span></td>
        <td><span class="budget-val">${fmtNumber(c.approvedBudget||0)}</span></td>
        <td style="font-size:.83rem;color:var(--clr-text-sub)">${fmtDate(c.submittedDate)}</td>
        <td>${approvalBadge(c.approval)}</td>
        <td>
          <div class="action-btns">
            <button class="action-btn review" onclick="openReview('${c.id}')">
              <svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              Review
            </button>
          </div>
        </td>
      </tr>
    `).join('');
  }
  document.getElementById('pgInfo').textContent = total ? `Showing ${(currentPage-1)*PER_PAGE+1}–${Math.min(currentPage*PER_PAGE,total)} of ${total}` : 'No results';
  renderPagination(total);
  document.getElementById('searchHint').textContent = searchQuery.trim() ? `${total} result${total!==1?'s':''}` : '';
}
function renderPagination(total){
  totalPages = Math.max(1, Math.ceil(total/PER_PAGE));
  if(currentPage > totalPages) currentPage = totalPages;
  const bar = document.getElementById('paginationBar');
  bar.style.display = totalPages<=1 ? 'none' : 'flex';
  document.getElementById('pgFirst').disabled = currentPage===1;
  document.getElementById('pgPrev').disabled = currentPage===1;
  document.getElementById('pgNext').disabled = currentPage===totalPages;
  document.getElementById('pgLast').disabled = currentPage===totalPages;
  const nums = document.getElementById('pgNumbers'); nums.innerHTML = '';
  let s = Math.max(1, currentPage-2), e = Math.min(totalPages, s+4); s = Math.max(1, e-4);
  if(s>1){ addPgNum(nums,1); if(s>2) nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>'); }
  for(let i=s;i<=e;i++) addPgNum(nums,i);
  if(e<totalPages){ if(e<totalPages-1) nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>'); addPgNum(nums,totalPages); }
}
function addPgNum(container,n){
  const b = document.createElement('button'); b.className = 'pg-btn'+(n===currentPage?' active':''); b.textContent = n; b.onclick = ()=>goPage(n); container.appendChild(b);
}
function goPage(p){
  if(p<1||p>totalPages) return;
  currentPage=p; renderTable();
}
document.getElementById('searchInput').addEventListener('input', (e)=>{ searchQuery=e.target.value; currentPage=1; renderTable(); });

/* ─── Sort ─── */
const SORT_BTNS = { sortNameBtn:'name', sortBudgetBtn:'budget', sortDateBtn:'submittedDate' };
function applySortBtn(field, btnId){
  const prev = sortAscMap[field];
  if(prev==null) sortAscMap[field]=true; else if(prev===true) sortAscMap[field]=false; else { delete sortAscMap[field]; }
  sortField = sortAscMap[field]!=null ? field : null;
  Object.keys(SORT_BTNS).forEach(id=>{ const b=document.getElementById(id); if(!b) return; b.classList.remove('active-sort'); b.querySelector('svg').innerHTML='<path d="M3 6h18M7 12h10M11 18h2"/>'; });
  if(sortField){ const b=document.getElementById(btnId); if(b){ b.classList.add('active-sort'); b.querySelector('svg').innerHTML = sortAscMap[field] ? '<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 4 20 7 17 10" style="stroke-width:1.8"/>' : '<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 14 20 17 17 20" style="stroke-width:1.8"/>'; } }
  currentPage=1; renderTable();
}
Object.entries(SORT_BTNS).forEach(([btnId,field])=>document.getElementById(btnId)?.addEventListener('click',()=>applySortBtn(field,btnId)));

/* ─── Filters ─── */
function closeAllFilters(){
  filterNameOpen=filterTypeOpen=filterBudgetOpen=filterDateOpen=filterApprovalOpen=false;
  ['filterNameDropdown','filterTypeDropdown','filterBudgetDropdown','filterDateDropdown','filterApprovalDropdown'].forEach(id=>document.getElementById(id)?.classList.remove('open'));
}
function positionDropdown(ddId, btnId){
  const dd = document.getElementById(ddId), r = document.getElementById(btnId).getBoundingClientRect();
  dd.classList.add('open'); dd.style.top = r.bottom+4+'px'; dd.style.left = Math.min(r.left, window.innerWidth-dd.offsetWidth-8)+'px';
}
function renderNameFilterList(){
  const q = (document.getElementById('filterNameSearch')?.value||'').toLowerCase();
  const names = [...new Set(campaigns.map(c=>c.name))].sort().filter(n=>n.toLowerCase().includes(q));
  document.getElementById('filterNameList').innerHTML = names.map(n=>`<label class="filter-item"><input type="checkbox" value="${n}" ${activeNameFilters.has(n)?'checked':''} onchange="toggleFilter('name','${n.replace(/'/g,"\\'")}',this.checked)"><span style="font-size:.83rem;color:var(--clr-text)">${n}</span></label>`).join('');
}
function renderTypeFilterList(){
  const types = [...new Set(campaigns.flatMap(c=>c.types))].sort();
  document.getElementById('filterTypeList').innerHTML = types.map(t=>`<label class="filter-item"><input type="checkbox" value="${t}" ${activeTypeFilters.has(t)?'checked':''} onchange="toggleFilter('type','${t}',this.checked)"><span style="font-size:.83rem;color:var(--clr-text)">${t}</span></label>`).join('');
}
const APPROVAL_OPTIONS = [{val:'approved',label:'Approved'},{val:'semi',label:'Semi Approved'},{val:'pending',label:'Pending'},{val:'not-approved',label:'Not Approved'}];
function renderApprovalFilterList(){
  document.getElementById('filterApprovalList').innerHTML = APPROVAL_OPTIONS.map(({val,label})=>`<label class="filter-item"><input type="checkbox" value="${val}" ${activeApprovalFilters.has(val)?'checked':''} onchange="toggleFilter('approval','${val}',this.checked)"><span style="font-size:.83rem;color:var(--clr-text)">${label}</span></label>`).join('');
}
/* ─── Date Filter Tree (year + month) ─── */
const _dateTreeOpen = new Set();
function buildDateTree(){
  const map = {};
  campaigns.forEach(c=>{
    const d = c.submittedDate||''; if(!d) return;
    const year = d.slice(0,4), month = d.slice(0,7);
    if(!map[year]) map[year] = new Set();
    map[year].add(month);
  });
  return map;
}
function renderDateFilterList(){
  const container = document.getElementById('filterDateList');
  const tree = buildDateTree();
  const activeSet = activeDateFilters;
  const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const openSet = _dateTreeOpen;
  container.innerHTML = '';
  Object.keys(tree).sort().reverse().forEach(year=>{
    const months = [...tree[year]].sort();
    const allChecked = months.every(m=>activeSet.has(m));
    const someChecked = months.some(m=>activeSet.has(m));
    const isOpen = openSet.has(year);
    const wrapper = document.createElement('div');
    const yearRow = document.createElement('div');
    yearRow.className = 'date-tree-year';
    const lbl = document.createElement('label');
    lbl.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:pointer;flex:1';
    lbl.onclick = e=>e.stopPropagation();
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.style.accentColor = 'var(--clr-orange)';
    cb.checked = allChecked; cb.indeterminate = !allChecked && someChecked;
    cb.onchange = ()=>{ months.forEach(m=>{ if(cb.checked) activeSet.add(m); else activeSet.delete(m); }); renderDateFilterList(); currentPage=1; renderTable(); };
    const yearSpan = document.createElement('span'); yearSpan.textContent = year;
    lbl.appendChild(cb); lbl.appendChild(yearSpan);
    const chevron = document.createElement('span');
    chevron.className = 'date-tree-chevron'+(isOpen?' open':''); chevron.innerHTML = '&#9658;';
    yearRow.appendChild(lbl); yearRow.appendChild(chevron);
    yearRow.onclick = ()=>{ if(openSet.has(year)) openSet.delete(year); else openSet.add(year); monthsDiv.classList.toggle('open', openSet.has(year)); chevron.classList.toggle('open', openSet.has(year)); };
    const monthsDiv = document.createElement('div');
    monthsDiv.className = 'date-tree-months'+(isOpen?' open':'');
    months.forEach(ym=>{
      const mIdx = parseInt(ym.slice(5))-1, mName = monthNames[mIdx]||ym;
      const mLabel = document.createElement('label'); mLabel.className = 'filter-item';
      const mCb = document.createElement('input'); mCb.type = 'checkbox'; mCb.style.accentColor = 'var(--clr-orange)';
      mCb.checked = activeSet.has(ym);
      mCb.onchange = ()=>{ if(mCb.checked) activeSet.add(ym); else activeSet.delete(ym); cb.checked = months.every(m=>activeSet.has(m)); cb.indeterminate = !cb.checked && months.some(m=>activeSet.has(m)); currentPage=1; renderTable(); };
      const mSpan = document.createElement('span'); mSpan.style.cssText = 'font-size:.83rem;color:var(--clr-text)'; mSpan.textContent = mName;
      mLabel.appendChild(mCb); mLabel.appendChild(mSpan);
      monthsDiv.appendChild(mLabel);
    });
    wrapper.appendChild(yearRow); wrapper.appendChild(monthsDiv);
    container.appendChild(wrapper);
  });
  if(!Object.keys(tree).length) container.innerHTML = '<div style="padding:10px 14px;font-size:.82rem;color:var(--clr-text-sub)">No dates available</div>';
}
function toggleFilter(type, val, checked){
  if(type==='name'){ if(checked) activeNameFilters.add(val); else activeNameFilters.delete(val); }
  else if(type==='type'){ if(checked) activeTypeFilters.add(val); else activeTypeFilters.delete(val); }
  else if(type==='approval'){ if(checked) activeApprovalFilters.add(val); else activeApprovalFilters.delete(val); }
  currentPage=1; renderTable();
}
document.getElementById('filterNameBtn').addEventListener('click', e=>{ e.stopPropagation(); const c=filterNameOpen; closeAllFilters(); if(c) return; filterNameOpen=true; positionDropdown('filterNameDropdown','filterNameBtn'); renderNameFilterList(); });
document.getElementById('filterNameSearch').addEventListener('input', ()=>renderNameFilterList());
document.getElementById('filterNameSelectAll').addEventListener('click', e=>{ e.stopPropagation(); campaigns.forEach(c=>activeNameFilters.add(c.name)); renderNameFilterList(); currentPage=1; renderTable(); });
document.getElementById('filterNameClearAll').addEventListener('click', e=>{ e.stopPropagation(); activeNameFilters.clear(); renderNameFilterList(); currentPage=1; renderTable(); });
document.getElementById('filterTypeBtn').addEventListener('click', e=>{ e.stopPropagation(); const c=filterTypeOpen; closeAllFilters(); if(c) return; filterTypeOpen=true; positionDropdown('filterTypeDropdown','filterTypeBtn'); renderTypeFilterList(); });
document.getElementById('filterTypeSelectAll').addEventListener('click', e=>{ e.stopPropagation(); [...new Set(campaigns.flatMap(c=>c.types))].forEach(t=>activeTypeFilters.add(t)); renderTypeFilterList(); currentPage=1; renderTable(); });
document.getElementById('filterTypeClearAll').addEventListener('click', e=>{ e.stopPropagation(); activeTypeFilters.clear(); renderTypeFilterList(); currentPage=1; renderTable(); });
function openBudgetFilter(){
  const currently = filterBudgetOpen; closeAllFilters(); if(currently) return;
  filterBudgetOpen=true;
  const dd = document.getElementById('filterBudgetDropdown'); dd.classList.add('open');
  const r = document.getElementById('filterBudgetBtn').getBoundingClientRect();
  dd.style.top = r.bottom+4+'px'; dd.style.left = Math.min(r.left, window.innerWidth-228)+'px';
  const budgets = campaigns.map(c=>c.budget).filter(b=>b>0);
  if(budgets.length){
    document.getElementById('budgetMin').placeholder = Math.min(...budgets).toLocaleString('en-EG');
    document.getElementById('budgetMax').placeholder = Math.max(...budgets).toLocaleString('en-EG');
  }
}
document.getElementById('filterBudgetBtn').addEventListener('click', e=>{ e.stopPropagation(); openBudgetFilter(); });
document.getElementById('filterBudgetClear').addEventListener('click', e=>{ e.stopPropagation(); document.getElementById('budgetMin').value=''; document.getElementById('budgetMax').value=''; currentPage=1; renderTable(); });
document.getElementById('filterDateBtn').addEventListener('click', e=>{ e.stopPropagation(); const c=filterDateOpen; closeAllFilters(); if(c) return; filterDateOpen=true; const dd=document.getElementById('filterDateDropdown'); dd.classList.add('open'); const r=document.getElementById('filterDateBtn').getBoundingClientRect(); dd.style.top=r.bottom+4+'px'; dd.style.left=Math.min(r.left, window.innerWidth-248)+'px'; renderDateFilterList(); });
document.getElementById('filterDateSelectAll').addEventListener('click', e=>{ e.stopPropagation(); [...new Set(campaigns.map(c=>c.submittedDate.slice(0,7)))].forEach(m=>activeDateFilters.add(m)); renderDateFilterList(); currentPage=1; renderTable(); });
document.getElementById('filterDateClearAll').addEventListener('click', e=>{ e.stopPropagation(); activeDateFilters.clear(); renderDateFilterList(); currentPage=1; renderTable(); });
document.getElementById('filterApprovalBtn').addEventListener('click', e=>{ e.stopPropagation(); const c=filterApprovalOpen; closeAllFilters(); if(c) return; filterApprovalOpen=true; positionDropdown('filterApprovalDropdown','filterApprovalBtn'); renderApprovalFilterList(); });
document.getElementById('filterApprovalSelectAll').addEventListener('click', e=>{ e.stopPropagation(); APPROVAL_OPTIONS.forEach(o=>activeApprovalFilters.add(o.val)); renderApprovalFilterList(); currentPage=1; renderTable(); });
document.getElementById('filterApprovalClearAll').addEventListener('click', e=>{ e.stopPropagation(); activeApprovalFilters.clear(); renderApprovalFilterList(); currentPage=1; renderTable(); });
document.addEventListener('click', e=>{
  const ids = ['filterNameBtn','filterNameDropdown','filterTypeBtn','filterTypeDropdown','filterBudgetBtn','filterBudgetDropdown','filterDateBtn','filterDateDropdown','filterApprovalBtn','filterApprovalDropdown'];
  if(!ids.some(id=>document.getElementById(id)?.contains(e.target))) closeAllFilters();
});

/* ─── Review Panel ─── */
function openReview(id){
  const c = campaigns.find(x=>x.id===id);
  if(!c) return;
  activeReviewId = id;
  document.getElementById('reviewTitle').textContent = c.name;
  document.getElementById('reviewSub').textContent = `Submitted ${fmtDate(c.submittedDate)}`;

  // Build body
  let html = `
    <div style="margin-bottom:4px">${approvalBadge(c.approval)}</div>
    <p class="review-section-title">Campaign Info</p>
    <div class="review-info-grid">
      <div class="review-kv"><div class="review-kv-label">Campaign</div><div class="review-kv-val">${c.name}</div></div>
      <div class="review-kv"><div class="review-kv-label">Target</div><div class="review-kv-val">${c.target}</div></div>
      <div class="review-kv"><div class="review-kv-label">Date Range</div><div class="review-kv-val">${c.dateRange}</div></div>
    </div>
    <p class="review-section-title">Budget Breakdown</p>
    <div class="breakdown-wrap" style="margin-bottom:8px">
  `;
    const showCheckboxes = (c.approval === 'pending' || c.approval === 'semi') && _cfg().canApprove;
    let grandTotal = 0;
    c.budgetBreakdown.forEach(section=>{
      html += `<div class="breakdown-section"><div class="breakdown-section-type">${section.type}</div>`;
      let subListOpen = false;
      section.items.forEach(item=>{
        const isSub = item.label.startsWith('↳');
        const isRejected = c.rejectedBudgets && c.rejectedBudgets.includes(item.key);
        const isChecked = !isRejected;
        if(!isSub){
          if(subListOpen) html += `</div>`; // close previous item's sub-list
          html += `<div class="breakdown-item-row" style="display:flex;align-items:center;">
            ${showCheckboxes ? `<input type="checkbox" class="reject-budget-cb" value="${item.key}" style="accent-color:var(--clr-orange);margin-right:8px;" ${isChecked ? 'checked' : ''} title="Check to approve this item">` : ''}
            <div class="breakdown-item-name">${item.label}</div>
            <div class="breakdown-item-amount">${fmtBudget(item.amount)}</div>
          </div><div class="breakdown-sub-list">`;
          subListOpen = true;
        } else {
          html += `<div class="breakdown-sub-row" style="display:flex;align-items:center;">
            ${showCheckboxes ? `<input type="checkbox" class="reject-budget-cb" value="${item.key}" style="accent-color:var(--clr-orange);margin-right:8px;margin-left:12px;" ${isChecked ? 'checked' : ''} title="Check to approve this item">` : ''}
            <div class="breakdown-sub-name">${item.label}</div>
            <div class="breakdown-sub-amount">${fmtBudget(item.amount)}</div>
          </div>`;
        }
      });
      if(subListOpen) html += `</div>`; // close last item's sub-list
      grandTotal += section.subtotal;
      html += `<div class="breakdown-subtotal-row">
        <div class="breakdown-subtotal-label">Subtotal</div>
        <div class="breakdown-subtotal-amount">${fmtBudget(section.subtotal)}</div>
      </div>`;
      html += `</div>`; // close breakdown-section
    });
    html += `<div class="breakdown-grand-total">
      <div class="breakdown-grand-total-label">💰 Grand Total</div>
      <div class="breakdown-grand-total-amount">${fmtBudget(grandTotal)}</div>
    </div>`;
    html += `</div>`; // close breakdown-wrap

  // History
  html += `<p class="review-section-title">Approval History</p><div class="approval-history">`;
  if(!c.history.length) html += `<div style="font-size:.82rem;color:var(--clr-text-sub);padding:4px 2px">No decisions recorded yet.</div>`;
  c.history.forEach(h=>{
    html += `<div class="history-item">
      <div class="history-content">
        <div class="history-action">${approvalBadge(h.status)} ${h.action}</div>
        <div class="history-meta">${h.name} · ${h.date}</div>
        ${h.note ? `<div class="history-note">"${h.note}"</div>` : ''}
      </div>
    </div>`;
  });
  html += `</div>`;
  document.getElementById('reviewBody').innerHTML = html;

  // Footer buttons (gated by the approve permission; read-only users see none)
  const isPending = c.approval === 'pending' || c.approval === 'semi';
  if(!_cfg().canApprove){
    document.getElementById('reviewFooter').innerHTML = '';
  } else if(isPending){
    document.getElementById('reviewFooter').innerHTML = `
      <button class="btn-approve" onclick="doApproval('${id}','approved')">✓ Approve</button>
      <button class="btn-semi" onclick="doApproval('${id}','semi')">◐ Semi-Approve</button>
      <button class="btn-reject" onclick="doApproval('${id}','not-approved')">✕ Reject</button>
    `;
  } else {
    document.getElementById('reviewFooter').innerHTML = `
      <button class="btn-semi" onclick="doApproval('${id}','pending')" style="background:var(--clr-orange)">↩ Reset to Pending</button>
    `;
  }
  document.getElementById('reviewOverlay').classList.add('open');
}
function closeReview(){
  document.getElementById('reviewOverlay').classList.remove('open');
  activeReviewId = null;
}
document.getElementById('reviewOverlay').addEventListener('click', e=>{ if(e.target===e.currentTarget) closeReview(); });

/* ─── Approval Action ─── */
async function doApproval(id, action){
  const labels = { approved:'Approve', semi:'Semi-Approve', 'not-approved':'Reject', pending:'Reset to Pending' };
  const requireNote = action === 'semi' || action === 'not-approved';

  if(requireNote){
    const rejected = [];
    if (action === 'semi') {
      document.querySelectorAll('.reject-budget-cb:not(:checked)').forEach(cb => {
        rejected.push(cb.value);
      });
      if (rejected.length === 0) {
        Swal.fire({
          title: 'Rejected Budget Required',
          text: 'Please uncheck at least one budget item to reject/exclude it before semi-approving.',
          icon: 'warning',
          confirmButtonColor: 'var(--clr-orange)'
        });
        return;
      }
    }

    const { value: note, isConfirmed } = await Swal.fire({
      title: `${labels[action]} Campaign`,
      html: `<div style="text-align:left"><label style="font-size:.85rem;font-weight:700;color:var(--clr-text);display:block;margin-bottom:6px">Reason / Note <span style="color:#c0392b">*</span></label>
      <textarea id="swal-note" style="width:100%;padding:10px;border:1px solid #e0ddd8;border-radius:6px;font-family:inherit;font-size:.9rem;min-height:90px;resize:vertical;outline:none" placeholder="Enter reason / note (required)…"></textarea></div>`,
      showCancelButton: true,
      confirmButtonText: labels[action],
      cancelButtonText: 'Cancel',
      reverseButtons: true,
      preConfirm: ()=>{
        const note = document.getElementById('swal-note').value.trim();
        if(!note){ Swal.showValidationMessage('Please enter a reason.'); return false; }
        return note;
      }
    });
    if(!isConfirmed) return;
    applyApproval(id, action, note, rejected);
  } else {
    const result = await Swal.fire({
      title: `${labels[action]} Campaign?`,
      text: action === 'approved' ? 'The campaign budget will be marked as Approved.' : 'This will reset the approval status to Pending.',
      showCancelButton: true,
      confirmButtonText: labels[action],
      cancelButtonText: 'Cancel',
      reverseButtons: true,
    });
    if(result.isConfirmed) applyApproval(id, action, null, null);
  }
}
async function applyApproval(id, action, note, rejected_budgets){
  const c = campaigns.find(x=>x.id===id);
  const labels = { approved:'Approved', semi:'Semi-Approved', 'not-approved':'Rejected', pending:'Reset to Pending' };
  try {
    await apiSend(_decideUrl(id), { status: action, reason: note, rejected_budgets: rejected_budgets });
    await fetchQueue();
    closeReview();
    renderTable();
    renderKPIs();
    showToast('success','Decision Recorded', `"${c ? c.name : 'Campaign'}" marked as ${labels[action]}.`);
  } catch(e) {
    showToast('error','Could not record decision', e.message || 'Server error.');
  }
}

/* ─── Toast ─── */
function showToast(type, title, msg){
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
  setTimeout(()=>el.remove(), 4500);
}

/* ─── Init ─── */
if (searchQuery) {
  const searchInput = document.getElementById('searchInput');
  if (searchInput) searchInput.value = searchQuery;
}
fetchQueue().then(()=>{ renderKPIs(); renderTable(); });
document.addEventListener('visibilitychange', ()=>{ if(document.visibilityState==='visible'){ fetchQueue().then(()=>{ renderKPIs(); renderTable(); }); } });
window.addEventListener('focus', ()=>{ fetchQueue().then(()=>{ renderKPIs(); renderTable(); }); });

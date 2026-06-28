/* ═══════════════════════════════════════════════════
   Manual Distribution — dynamic, AJAX-backed (no localStorage).
   CFG (URLs + CSRF) is injected by the template. Assignable
   salesmen are scoped server-side by manual_all / team_manual.
═══════════════════════════════════════════════════ */
const CFG = window.MANUAL_DIST_CFG || {};
let leads = [];
/* SALESMEN: [{id,name,team,team_id,count}] — the people THIS user may assign to. */
let SALESMEN = [];

function ajaxGet(url){ return fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'}}).then(r=>r.json()); }
function ajaxPost(url,body){
  return fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':CFG.csrf,'X-Requested-With':'XMLHttpRequest'},body:JSON.stringify(body)})
    .then(async r=>{ const d=await r.json().catch(()=>({})); if(!r.ok||d.ok===false) throw new Error(d.error||'Request failed'); return d; });
}
function loadLeadsFromServer(){ return ajaxGet(CFG.urls.leads).then(d=>{ leads=(d.leads||[]); }).catch(()=>{ leads=[]; }); }
function loadSalesmenFromServer(){ return ajaxGet(CFG.urls.salesmen).then(d=>{ SALESMEN=(d.salesmen||[]); }).catch(()=>{ SALESMEN=[]; }); }

/* ── Avatar / team helpers (display only) ── */
const AGENT_COLORS = ['#e07b20','#2980b9','#8e44ad','#27ae60','#c0392b','#1abc9c','#d68910','#7f8c8d'];
function agentColor(name){ let h=0;for(const c of (name||''))h=(h*31+c.charCodeAt(0))%AGENT_COLORS.length; return AGENT_COLORS[h]; }
function agentInitials(name){ return (name||'?').split(' ').map(w=>w[0]||'').join('').slice(0,2).toUpperCase(); }
function teamColor(name){ return name?agentColor(name):'#aaa'; }
/* Group the assignable salesmen by team name for the combobox. */
function salesmenByTeam(){
  const map={};
  SALESMEN.forEach(s=>{ const t=s.team||'—'; (map[t]=map[t]||[]).push(s); });
  return map;
}
function salesmanById(id){ return SALESMEN.find(s=>s.id===id)||null; }

/* ── Source icons ── */
const SRC_ICONS={
  'Event':          '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  'Social Media Ad':'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/>',
  'TV Ad':          '<rect x="2" y="7" width="20" height="15" rx="2"/><polyline points="17 2 12 7 7 2"/>',
  'Street Ad':      '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
  'Exhibition':     '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>',
  'Campaign':       '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  'Broker':         '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  'Referral':       '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  'Walk-in':        '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  'Call Center':    '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/>',
  'Other':          '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
};
const SPEC_LABEL={'Event':'Event Name','Exhibition':'Exhibition Name','TV Ad':'Ad Name','Street Ad':'Location / Ad Name','Social Media Ad':'Ad / Post Name','Campaign':'Event / Ad Name','Other':'Details'};

function renderSourceTag(l){
  const srcLabel=l.broker?'Broker':l.campaign?'Campaign':(l.source||'—');
  const srcIconKey=l.broker?'Broker':l.campaign?'Campaign':(l.source||'Other');
  return `<span class="source-tag" onclick="openSrcPopover('${l.id}',event)"><svg viewBox="0 0 24 24">${SRC_ICONS[srcIconKey]||SRC_ICONS['Other']}</svg>${escHtml(srcLabel)}</span>`;
}

/* ═══════════════════════════════════════════════════
   PHONE POPOVER
═══════════════════════════════════════════════════ */
let _phoneDigits='';
function openPhoneModal(id,evt){
  const l=leads.find(x=>x.id===id);if(!l||!l.phone)return;
  if(evt)evt.stopPropagation();
  _phoneDigits=String(l.phone).replace(/\D/g,'');
  document.getElementById('phoneModalNumber').textContent=l.phone;
  const btn=document.getElementById('phoneModalCopyBtn');btn.classList.remove('copied');
  document.getElementById('phoneModalCopyLabel').textContent='Copy Number';
  const pop=document.getElementById('phoneModal');pop.classList.add('open');
  if(evt&&evt.currentTarget){
    const r=evt.currentTarget.getBoundingClientRect(),pw=198,ph=80;
    let left=r.left,top=r.bottom+6;
    if(left+pw>window.innerWidth-8)left=window.innerWidth-pw-8;
    if(top+ph>window.innerHeight-8)top=r.top-ph-6;
    pop.style.left=left+'px';pop.style.top=top+'px';
  }
}
function closePhoneModal(){document.getElementById('phoneModal').classList.remove('open');}
document.addEventListener('click',e=>{if(document.getElementById('phoneModal').classList.contains('open')&&!document.getElementById('phoneModal').contains(e.target)&&!e.target.closest('.phone-link'))closePhoneModal();});
document.addEventListener('scroll',closePhoneModal,true);
function copyPhoneFromModal(){
  const text=document.getElementById('phoneModalNumber').textContent;
  const done=()=>{const btn=document.getElementById('phoneModalCopyBtn');btn.classList.add('copied');document.getElementById('phoneModalCopyLabel').textContent='Copied!';setTimeout(()=>{btn.classList.remove('copied');document.getElementById('phoneModalCopyLabel').textContent='Copy Number';},1500);};
  if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(text).then(done).catch(()=>{fallbackCopy(text);done();});
  else{fallbackCopy(text);done();}
}
function fallbackCopy(t){const ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();try{document.execCommand('copy');}catch(e){}ta.remove();}
function sendWhatsappFromModal(){if(_phoneDigits)window.open('https://wa.me/'+_phoneDigits,'_blank');}

/* ═══════════════════════════════════════════════════
   SOURCE POPOVER
═══════════════════════════════════════════════════ */
function openSrcPopover(id,evt){
  const l=leads.find(x=>x.id===id);if(!l)return;
  if(evt)evt.stopPropagation();
  const pop=document.getElementById('srcPopover');
  const campName=(l.campaign||'').trim(),brokerName=(l.broker||'').trim(),specSrc=(l.specificSource||'').trim(),srcType=l.source||'Other';
  const isBroker=!!brokerName,isCampaign=!!campName&&!isBroker;
  const iconKey=isBroker?'Broker':isCampaign?'Campaign':srcType;
  document.getElementById('srcPopIcon').innerHTML=`<svg viewBox="0 0 24 24" style="width:15px;height:15px;stroke:var(--clr-orange);fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round">${SRC_ICONS[iconKey]||SRC_ICONS['Other']}</svg>`;
  if(isBroker){
    document.getElementById('srcPopTitle').textContent=brokerName;
    document.getElementById('srcPopType').textContent='Broker Referral';
    document.getElementById('srcPopBody').innerHTML=`<div class="src-pop-row"><span class="src-pop-label">Broker Name</span><span class="src-pop-value">${escHtml(brokerName)}</span></div>`;
  }else if(isCampaign){
    document.getElementById('srcPopTitle').textContent=campName;
    document.getElementById('srcPopType').textContent='Campaign · '+srcType;
    let b=`<div class="src-pop-row"><span class="src-pop-label">Campaign Name</span><span class="src-pop-value">${escHtml(campName)}</span></div>`;
    b+=`<div class="src-pop-row"><span class="src-pop-label">Campaign Type</span><span class="src-pop-value">${escHtml(srcType)}</span></div>`;
    if(specSrc)b+=`<div class="src-pop-row"><span class="src-pop-label">${escHtml(SPEC_LABEL[srcType]||'Details')}</span><span class="src-pop-value">${escHtml(specSrc)}</span></div>`;
    document.getElementById('srcPopBody').innerHTML=b;
  }else{
    document.getElementById('srcPopTitle').textContent=specSrc||srcType;
    document.getElementById('srcPopType').textContent=srcType;
    document.getElementById('srcPopBody').innerHTML=specSrc?`<div class="src-pop-row"><span class="src-pop-label">${escHtml(SPEC_LABEL[srcType]||'Name')}</span><span class="src-pop-value">${escHtml(specSrc)}</span></div>`:`<div style="font-size:.78rem;color:var(--clr-gray);font-style:italic">No details saved.</div>`;
  }
  pop.classList.add('open');
  const target=evt&&(evt.currentTarget||evt.target.closest('.source-tag'));
  if(target){
    const r=target.getBoundingClientRect(),pw=250;
    pop.style.visibility='hidden';pop.style.display='block';
    const ph=pop.offsetHeight||150;pop.style.visibility='';pop.style.display='';
    let left=r.left,top=r.bottom+6;
    if(left+pw>window.innerWidth-8)left=window.innerWidth-pw-8;
    if(top+ph>window.innerHeight-8)top=r.top-ph-6;
    pop.style.left=left+'px';pop.style.top=top+'px';
  }
}
function closeSrcPopover(){document.getElementById('srcPopover').classList.remove('open');}
document.addEventListener('click',e=>{if(document.getElementById('srcPopover').classList.contains('open')&&!document.getElementById('srcPopover').contains(e.target)&&!e.target.closest('.source-tag'))closeSrcPopover();});
document.addEventListener('scroll',closeSrcPopover,true);

/* ── Helpers ── */
function escHtml(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function fmtDate(ts){ if(!ts)return '—'; const d=new Date(ts); return d.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}); }
function fmtDatetime(ts){ if(!ts)return '—'; const d=new Date(ts); return d.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})+' '+d.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}); }
/* SLA is the server-provided deadline (epoch ms). */
function getSlaMs(l){ if(!l.slaDeadline) return -1; return l.slaDeadline-Date.now(); }
function fmtSla(ms){
  if(ms<=0) return {html:'<span class="sla-expired">-</span>',cls:'expired'};
  const h=Math.floor(ms/3600000),m=Math.floor((ms%3600000)/60000);
  const txt=h>0?`${h}h ${m}m`:`${m}m`;
  if(ms<3600000)   return {html:`<span class="sla-urgent">${txt}</span>`,cls:'urgent'};
  if(ms<14400000)  return {html:`<span class="sla-warn">${txt}</span>`,cls:'warn'};
  return {html:`<span class="sla-ok">${txt}</span>`,cls:'ok'};
}
const STAGE_CLASS={
  'Fresh':'stage-fresh','Follow-up':'stage-followup','Meeting':'stage-meeting',
  'Interested':'stage-interested','Not Interested':'stage-notinterested',
  'Not Reached':'stage-notreached','Frozen':'stage-frozen'
};

/* ═══════════════════════════════════════════════════
   STATE
═══════════════════════════════════════════════════ */
let searchQuery='', currentPage=1, totalPages=1, PAGE_SIZE=100;
let kpiFilterMode='all';
let sortField=null, sortAscMap={};
let openFilterKey=null;
let filterDateOpen=false;
const _dateTreeOpenYears=new Set();
let detailLeadId=null, detailTab='all';
let assignLeadId=null, selectedAgent=null;

const activeFilters={
  name:new Set(), phone:new Set(), source:new Set(), stage:new Set(), assigned:new Set(), team:new Set(),
};
const activeDateFilter=new Set();

const FILTER_CFG={
  name:     {dd:'filterNameDropdown',    btn:'filterNameBtn',     list:'filterNameList',     search:'filterNameSearch',     getValue:l=>l.name||''},
  phone:    {dd:'filterPhoneDropdown',   btn:'filterPhoneBtn',    list:'filterPhoneList',    search:'filterPhoneSearch',    getValue:l=>l.phone||'No Phone'},
  source:   {dd:'filterSourceDropdown',  btn:'filterSourceBtn',   list:'filterSourceList',   search:null,                   getValue:l=>l.source||''},
  stage:    {dd:'filterStageDropdown',   btn:'filterStageBtn',    list:'filterStageList',    search:null,                   getValue:l=>l.stage||'Fresh'},
  assigned: {dd:'filterAssignedDropdown',btn:'filterAssignedBtn', list:'filterAssignedList', search:'filterAssignedSearch', getValue:l=>l.assignedTo||'Unassigned'},
  team:     {dd:'filterTeamDropdown',    btn:'filterTeamBtn',     list:'filterTeamList',     search:null,                   getValue:l=>l.team||'Unassigned'},
};

function getFilteredLeads(excludeKey=null){
  let base=leads.filter(l=>l.active!==false);
  if(kpiFilterMode==='unassigned') base=base.filter(l=>!l.assignedTo);
  else if(kpiFilterMode==='assigned') base=base.filter(l=>!!l.assignedTo);
  else if(kpiFilterMode==='sla-breach') base=base.filter(l=>getSlaMs(l)<=0);
  else if(kpiFilterMode==='today') base=base.filter(l=>new Date(l.createdAt).toDateString()===new Date().toDateString());
  if(searchQuery){ const q=searchQuery.toLowerCase(); base=base.filter(l=>(l.name||'').toLowerCase().includes(q)||(l.phone||'').includes(q)||(l.source||'').toLowerCase().includes(q)); }
  Object.keys(activeFilters).forEach(key=>{
    if(key===excludeKey) return;
    const s=activeFilters[key]; if(!s.size) return;
    const cfg=FILTER_CFG[key];
    base=base.filter(l=>s.has(cfg.getValue(l)));
  });
  if(activeDateFilter.size){
    base=base.filter(l=>{ if(!l.createdAt)return false; const d=new Date(l.createdAt); const ym=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'); return activeDateFilter.has(ym); });
  }
  return base;
}

function getDisplayList(){
  let list=getFilteredLeads();
  if(sortField){
    const asc=sortAscMap[sortField]!==false;
    list=[...list].sort((a,b)=>{
      let av='',bv='';
      if(sortField==='name'){av=a.name||'';bv=b.name||'';}
      else if(sortField==='source'){av=a.source||'';bv=b.source||'';}
      else if(sortField==='stage'){av=a.stage||'';bv=b.stage||'';}
      else if(sortField==='assigned'){av=a.assignedTo||'';bv=b.assignedTo||'';}
      else if(sortField==='team'){av=a.team||'';bv=b.team||'';}
      else if(sortField==='date'){av=a.createdAt||0;bv=b.createdAt||0;}
      if(typeof av==='string') return asc?av.localeCompare(bv):bv.localeCompare(av);
      return asc?av-bv:bv-av;
    });
  }
  return list;
}

/* ── Dependent filter rendering ── */
function renderFilterList(key){
  const cfg=FILTER_CFG[key];
  const possible=getFilteredLeads(key);
  let values=[...new Set(possible.map(l=>cfg.getValue(l)))].sort();
  if(cfg.search){
    const q=(document.getElementById(cfg.search)?.value||'').toLowerCase();
    if(q) values=values.filter(v=>v.toLowerCase().includes(q));
  }
  const el=document.getElementById(cfg.list);
  if(!values.length){ el.innerHTML='<div style="padding:12px 14px;font-size:.8rem;color:var(--clr-gray);font-style:italic">No values found</div>'; return; }
  el.innerHTML=values.map(v=>{
    const checked=activeFilters[key].has(v);
    return `<label class="filter-item"><input type="checkbox" ${checked?'checked':''} onchange="toggleFilter('${key}','${v.replace(/'/g,"\\'")}',this.checked)"><label style="cursor:pointer;font-size:.82rem">${escHtml(v)}</label></label>`;
  }).join('');
}
function toggleFilter(key,val,checked){
  if(checked) activeFilters[key].add(val); else activeFilters[key].delete(val);
  currentPage=1; renderTable();
  Object.keys(FILTER_CFG).forEach(k=>{ if(k!==key && activeFilters[k].size) renderFilterList(k); });
}
function selectAllFilter(key){ getFilteredLeads(key).forEach(l=>activeFilters[key].add(FILTER_CFG[key].getValue(l))); currentPage=1; renderTable(); renderFilterList(key); }
function clearAllFilter(key){ activeFilters[key].clear(); currentPage=1; renderTable(); renderFilterList(key); }

/* ── Dropdown open/close ── */
function openFilter(key, btnId){
  if(openFilterKey===key){ closeAllFilters(); return; }
  closeAllFilters();
  openFilterKey=key;
  renderFilterList(key);
  const cfg=FILTER_CFG[key];
  document.getElementById(cfg.dd).classList.add('open');
  const btn=document.getElementById(btnId||cfg.btn);
  const r=btn.getBoundingClientRect();
  const dd=document.getElementById(cfg.dd);
  dd.style.top=(r.bottom+4)+'px';
  dd.style.left=Math.min(r.left,window.innerWidth-250)+'px';
  if(cfg.search){ const si=document.getElementById(cfg.search); if(si){ si.value=''; setTimeout(()=>si.focus(),0); } }
}
function closeAllFilters(){ document.querySelectorAll('.filter-dropdown.open').forEach(d=>d.classList.remove('open')); openFilterKey=null; filterDateOpen=false; }
document.addEventListener('click',e=>{ if(!e.target.closest('.filter-dropdown')&&!e.target.closest('.th-icon-btn')) closeAllFilters(); });

document.getElementById('filterNameBtn')    .addEventListener('click',e=>{e.stopPropagation();openFilter('name','filterNameBtn');});
document.getElementById('filterPhoneBtn')   .addEventListener('click',e=>{e.stopPropagation();openFilter('phone','filterPhoneBtn');});
document.getElementById('filterSourceBtn')  .addEventListener('click',e=>{e.stopPropagation();openFilter('source','filterSourceBtn');});
document.getElementById('filterStageBtn')   .addEventListener('click',e=>{e.stopPropagation();openFilter('stage','filterStageBtn');});
document.getElementById('filterAssignedBtn').addEventListener('click',e=>{e.stopPropagation();openFilter('assigned','filterAssignedBtn');});
document.getElementById('filterTeamBtn')    .addEventListener('click',e=>{e.stopPropagation();openFilter('team','filterTeamBtn');});
document.getElementById('filterDateBtn')    .addEventListener('click',e=>{ e.stopPropagation(); const isOpen=filterDateOpen; closeAllFilters(); filterDateOpen=!isOpen; if(filterDateOpen){ const dd=document.getElementById('filterDateDropdown'); const r=document.getElementById('filterDateBtn').getBoundingClientRect(); dd.classList.add('open'); dd.style.top=r.bottom+4+'px'; dd.style.left=Math.min(r.left,window.innerWidth-270)+'px'; renderDateFilter(); } });

/* ── Date tree filter (Created Date) ── */
function buildDateTree(){
  let base=leads.filter(l=>l.active!==false);
  if(kpiFilterMode==='unassigned') base=base.filter(l=>!l.assignedTo);
  else if(kpiFilterMode==='assigned') base=base.filter(l=>!!l.assignedTo);
  else if(kpiFilterMode==='sla-breach') base=base.filter(l=>getSlaMs(l)<=0);
  else if(kpiFilterMode==='today') base=base.filter(l=>new Date(l.createdAt).toDateString()===new Date().toDateString());
  if(searchQuery){ const q=searchQuery.toLowerCase(); base=base.filter(l=>(l.name||'').toLowerCase().includes(q)||(l.phone||'').includes(q)||(l.source||'').toLowerCase().includes(q)); }
  Object.keys(activeFilters).forEach(key=>{ const s=activeFilters[key]; if(!s.size)return; const cfg=FILTER_CFG[key]; base=base.filter(l=>s.has(cfg.getValue(l))); });
  const map={};
  base.forEach(l=>{
    if(!l.createdAt)return;
    const d=new Date(l.createdAt), year=String(d.getFullYear()), month=year+'-'+String(d.getMonth()+1).padStart(2,'0');
    if(!map[year])map[year]=new Set();
    map[year].add(month);
  });
  return map;
}
function renderDateFilter(){
  const container=document.getElementById('filterDateList'); if(!container)return;
  const tree=buildDateTree();
  const monthNames=['January','February','March','April','May','June','July','August','September','October','November','December'];
  container.innerHTML='';
  Object.keys(tree).sort().reverse().forEach(year=>{
    const months=[...tree[year]].sort();
    const allChecked=months.every(m=>activeDateFilter.has(m));
    const isOpen=_dateTreeOpenYears.has(year);
    const wrapper=document.createElement('div');
    const yearRow=document.createElement('div'); yearRow.className='date-tree-year';
    const cb=document.createElement('input'); cb.type='checkbox'; cb.style.cssText='accent-color:var(--clr-orange);width:14px;height:14px;cursor:pointer;margin-right:6px;flex-shrink:0';
    cb.checked=allChecked; cb.indeterminate=!allChecked&&months.some(m=>activeDateFilter.has(m));
    cb.onchange=()=>{ if(cb.checked)months.forEach(m=>activeDateFilter.add(m)); else months.forEach(m=>activeDateFilter.delete(m)); currentPage=1;renderTable();renderDateFilter(); if(openFilterKey)renderFilterList(openFilterKey); };
    const chev=document.createElement('span'); chev.className='date-tree-chevron'+(isOpen?' open':''); chev.textContent='▶';
    yearRow.addEventListener('click',e=>{ if(e.target===cb)return; if(_dateTreeOpenYears.has(year))_dateTreeOpenYears.delete(year); else _dateTreeOpenYears.add(year); renderDateFilter(); });
    yearRow.appendChild(cb); const label=document.createElement('span'); label.textContent=year; label.style.flex='1'; yearRow.appendChild(label); yearRow.appendChild(chev);
    const monthsDiv=document.createElement('div'); monthsDiv.className='date-tree-months'+(isOpen?' open':'');
    months.forEach(ym=>{
      const mLabel=document.createElement('label'); mLabel.className='filter-item';
      const mCb=document.createElement('input'); mCb.type='checkbox'; mCb.checked=activeDateFilter.has(ym); mCb.style.cssText='accent-color:var(--clr-orange);width:14px;height:14px;cursor:pointer;flex-shrink:0';
      mCb.onchange=()=>{ if(mCb.checked)activeDateFilter.add(ym); else activeDateFilter.delete(ym); cb.checked=months.every(m=>activeDateFilter.has(m)); cb.indeterminate=!cb.checked&&months.some(m=>activeDateFilter.has(m)); currentPage=1;renderTable(); if(openFilterKey)renderFilterList(openFilterKey); renderDateFilter(); };
      const mNum=parseInt(ym.split('-')[1])-1;
      const mSpan=document.createElement('span'); mSpan.style.cssText='font-size:.83rem;color:var(--clr-text)'; mSpan.textContent=monthNames[mNum];
      mLabel.appendChild(mCb); mLabel.appendChild(mSpan); monthsDiv.appendChild(mLabel);
    });
    wrapper.appendChild(yearRow); wrapper.appendChild(monthsDiv); container.appendChild(wrapper);
  });
  if(!Object.keys(tree).length)container.innerHTML='<div style="padding:10px 14px;font-size:.82rem;color:var(--clr-text-sub)">No dates available</div>';
}
function selectAllDateFilter(){ const tree=buildDateTree(); Object.values(tree).forEach(s=>s.forEach(m=>activeDateFilter.add(m))); currentPage=1;renderTable();renderDateFilter(); if(openFilterKey)renderFilterList(openFilterKey); }
function clearAllDateFilter(){ activeDateFilter.clear(); currentPage=1;renderTable();renderDateFilter(); if(openFilterKey)renderFilterList(openFilterKey); }

/* ── Sort ── */
function setSort(field,btnId){
  if(sortField===field) sortAscMap[field]=!sortAscMap[field]; else { sortField=field; sortAscMap[field]=true; }
  document.querySelectorAll('.th-icon-btn').forEach(b=>b.classList.remove('active-sort'));
  document.getElementById(btnId).classList.add('active-sort');
  currentPage=1; renderTable();
}
document.getElementById('sortNameBtn')  .addEventListener('click',()=>setSort('name','sortNameBtn'));
document.getElementById('sortSourceBtn').addEventListener('click',()=>setSort('source','sortSourceBtn'));
document.getElementById('sortStageBtn') .addEventListener('click',()=>setSort('stage','sortStageBtn'));
document.getElementById('sortAssignedBtn').addEventListener('click',()=>setSort('assigned','sortAssignedBtn'));
document.getElementById('sortTeamBtn')  .addEventListener('click',()=>setSort('team','sortTeamBtn'));
document.getElementById('sortDateBtn')  .addEventListener('click',()=>setSort('date','sortDateBtn'));

/* ── Search ── */
document.getElementById('searchInput').addEventListener('input',e=>{searchQuery=e.target.value;currentPage=1;renderTable();});

/* ═══════════════════════════════════════════════════
   KPI FILTER
═══════════════════════════════════════════════════ */
function kpiFilter(mode){
  kpiFilterMode=mode;
  document.querySelectorAll('.kpi-card').forEach(c=>c.classList.remove('kpi-active'));
  const map={all:0,unassigned:1,assigned:2,'sla-breach':3,today:4};
  const idx=map[mode];
  if(idx!==undefined) document.querySelectorAll('.kpi-card')[idx]?.classList.add('kpi-active');
  currentPage=1; renderTable();
}

/* ═══════════════════════════════════════════════════
   RENDER TABLE
═══════════════════════════════════════════════════ */
function renderTable(){
  updateKPIs();
  const list=getDisplayList();
  const total=list.length;
  totalPages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  if(currentPage>totalPages) currentPage=totalPages;
  const page=list.slice((currentPage-1)*PAGE_SIZE,currentPage*PAGE_SIZE);

  const hint=document.getElementById('searchHint');
  hint.textContent=searchQuery?`${total} result${total!==1?'s':''} found`:'';

  const body=document.getElementById('tableBody');
  if(!page.length){
    body.innerHTML=`<tr class="no-results-row"><td colspan="9"><div style="text-align:center;padding:40px;color:var(--clr-text-sub)"><svg viewBox="0 0 24 24" style="width:36px;height:36px;stroke:var(--clr-border);fill:none;stroke-width:1.4;display:block;margin:0 auto 10px"><circle cx="12" cy="12" r="10"/><line x1="8" y1="15" x2="16" y2="15"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>No leads match your filters.</div></td></tr>`;
    renderPagination(0); return;
  }
  body.innerHTML=page.map(renderRow).join('');
  renderPagination(total);
  clearInterval(window._slaTick);
  window._slaTick=setInterval(()=>{
    document.querySelectorAll('#tableBody tr[data-id]').forEach(tr=>{
      const l=leads.find(x=>x.id===tr.dataset.id);
      if(!l||l.active===false) return;
      const cell=tr.querySelector('.sla-cell');
      if(cell) cell.innerHTML=fmtSla(getSlaMs(l)).html;
    });
  },1000);
}

function renderRow(l){
  const sla=fmtSla(getSlaMs(l));
  const stageClass=STAGE_CLASS[l.stage]||'stage-fresh';
  const assignedHtml=l.assignedTo
    ?`<span style="font-size:.82rem;color:var(--clr-text)">${escHtml(l.assignedTo)}</span>`
    :`<span class="unassigned-badge">⚠ Unassigned</span>`;
  const tColor=teamColor(l.team);
  const teamHtml=l.team?`<span style="display:inline-flex;align-items:center;gap:5px;font-size:.78rem;font-weight:600;color:${tColor}"><span style="width:8px;height:8px;border-radius:50%;background:${tColor};display:inline-block"></span>${escHtml(l.team)}</span>`:'<span style="color:var(--clr-gray);font-size:.78rem">—</span>';

  return `<tr data-id="${l.id}">
    <td style="text-align:left">
      <div style="font-weight:600;font-size:.87rem">${escHtml(l.name)}</div>
    </td>
    <td style="font-size:.82rem;color:var(--clr-text-sub)">${l.phone?`<span class="phone-link" onclick="openPhoneModal('${l.id}',event)"><svg viewBox="0 0 24 24"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/></svg><span>${escHtml(l.phone)}</span></span>`:'—'}</td>
    <td>${renderSourceTag(l)}</td>
    <td><span class="stage-badge ${stageClass}">${escHtml(l.stage||'Fresh')}</span></td>
    <td class="sla-cell">${l.active===false?'<span style="color:var(--clr-gray);font-size:.78rem">—</span>':sla.html}</td>
    <td>${assignedHtml}</td>
    <td>${teamHtml}</td>
    <td style="font-size:.78rem;color:var(--clr-text-sub)">${fmtDate(l.createdAt)}</td>
    <td>
      <div class="action-btns">
        <button class="action-btn assign-btn" title="Assign Lead" onclick="openAssignModal('${l.id}')">
          <svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>
        </button>
        <button class="action-btn history-btn" title="View Lead History" onclick="openDetailModal('${l.id}')">
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        </button>
      </div>
    </td>
  </tr>`;
}

/* ═══════════════════════════════════════════════════
   UPDATE KPIs
═══════════════════════════════════════════════════ */
function updateKPIs(){
  const active=leads.filter(l=>l.active!==false);
  document.getElementById('kpiTotal').textContent=active.length;
  document.getElementById('kpiUnassigned').textContent=active.filter(l=>!l.assignedTo).length;
  document.getElementById('kpiAssigned').textContent=active.filter(l=>!!l.assignedTo).length;
  document.getElementById('kpiSLABreach').textContent=active.filter(l=>getSlaMs(l)<=0).length;
  const today=new Date().toDateString();
  document.getElementById('kpiToday').textContent=active.filter(l=>new Date(l.createdAt).toDateString()===today).length;
}

/* ═══════════════════════════════════════════════════
   PAGINATION
═══════════════════════════════════════════════════ */
function goPage(p){ if(p<1||p>totalPages)return; currentPage=p; renderTable(); }
function changePageSize(v){ PAGE_SIZE=parseInt(v); currentPage=1; renderTable(); }
function renderPagination(total){
  totalPages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  if(currentPage>totalPages) currentPage=totalPages;
  const bar=document.getElementById('paginationBar');
  bar.style.display='flex';
  const sizeSel=document.getElementById('pgSizeSelect');
  if(sizeSel&&sizeSel.value!==String(PAGE_SIZE)) sizeSel.value=String(PAGE_SIZE);
  const start=total?(currentPage-1)*PAGE_SIZE+1:0, end=Math.min(currentPage*PAGE_SIZE,total);
  document.getElementById('pgInfo').textContent=`Showing ${start}–${end} of ${total} leads`;
  document.getElementById('pgFirst').disabled=currentPage===1;
  document.getElementById('pgPrev').disabled=currentPage===1;
  document.getElementById('pgNext').disabled=currentPage===totalPages;
  document.getElementById('pgLast').disabled=currentPage===totalPages;
  const nums=document.getElementById('pgNumbers'); nums.innerHTML='';
  let s=Math.max(1,currentPage-2),e=Math.min(totalPages,s+4); s=Math.max(1,e-4);
  if(s>1){addPgNum(nums,1);if(s>2)nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>');}
  for(let i=s;i<=e;i++) addPgNum(nums,i);
  if(e<totalPages){if(e<totalPages-1)nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>');addPgNum(nums,totalPages);}
}
function addPgNum(container,n){ const b=document.createElement('button');b.className='pg-btn'+(n===currentPage?' active':'');b.textContent=n;b.onclick=()=>goPage(n);container.appendChild(b); }

/* ═══════════════════════════════════════════════════
   ASSIGN MODAL
═══════════════════════════════════════════════════ */
function openAssignModal(id){
  const l=leads.find(x=>x.id===id); if(!l) return;
  assignLeadId=id; selectedAgent=null;
  document.getElementById('assignLeadId').value=id;
  document.getElementById('assignModalSub').textContent=l.name+' · '+(l.source||'');
  document.getElementById('assignNote').value='';
  document.getElementById('agentComboInput').value='';
  document.getElementById('selectedAgentCardWrap').innerHTML='';
  closeAgentCombo();
  renderAgentCombo('');
  document.getElementById('assignModal').classList.add('open');
}
function closeAssignModal(){ document.getElementById('assignModal').classList.remove('open'); assignLeadId=null; closeAgentCombo(); }
document.getElementById('assignModalClose').addEventListener('click',closeAssignModal);
document.getElementById('assignModalCancel').addEventListener('click',closeAssignModal);
document.getElementById('assignModal').addEventListener('click',e=>{ if(e.target===e.currentTarget) closeAssignModal(); });

/* ── Searchable salesman combobox (scoped list from server) ── */
function openAgentCombo(){ document.getElementById('agentComboWrap').classList.add('open'); renderAgentCombo(document.getElementById('agentComboInput').value); }
function closeAgentCombo(){ document.getElementById('agentComboWrap').classList.remove('open'); }
document.addEventListener('click',e=>{ if(!e.target.closest('#agentComboWrap')) closeAgentCombo(); });
function filterAgentCombo(q){ openAgentCombo(); renderAgentCombo(q); }

function renderAgentCombo(query){
  const q=(query||'').trim().toLowerCase();
  const list=document.getElementById('agentComboList');
  const grouped=salesmenByTeam();
  let html='';
  Object.keys(grouped).sort().forEach(tname=>{
    const matches=grouped[tname].filter(a=>!q||(a.name||'').toLowerCase().includes(q)||tname.toLowerCase().includes(q));
    if(!matches.length) return;
    html+=`<div class="combo-group-label">${escHtml(tname)}</div>`;
    matches.forEach(a=>{
      const initials=agentInitials(a.name);
      const aColor=agentColor(a.name);
      const isSelected=selectedAgent&&selectedAgent.id===a.id;
      html+=`<div class="combo-opt${isSelected?' selected':''}" onclick="selectAgentFromCombo('${a.id}')">
        <div class="combo-opt-avatar" style="background:${aColor}">${initials}</div>
        <div><div class="combo-opt-name">${escHtml(a.name)}</div><div class="combo-opt-meta">${escHtml(tname)}</div></div>
        <span class="combo-opt-count">${a.count||0} leads</span>
      </div>`;
    });
  });
  list.innerHTML=html||'<div class="combo-empty">No salesman matches your search.</div>';
}

function selectAgentFromCombo(id){
  const a=salesmanById(id); if(!a) return;
  selectedAgent=a;
  document.getElementById('agentComboInput').value=a.name;
  renderAgentCombo(a.name);
  closeAgentCombo();
  const initials=agentInitials(a.name), aColor=agentColor(a.name);
  document.getElementById('selectedAgentCardWrap').innerHTML=`<div class="selected-agent-card">
    <div class="agent-avatar" style="background:${aColor}">${initials}</div>
    <div><div class="agent-name">${escHtml(a.name)}</div><div class="agent-meta">Team: ${escHtml(a.team||'—')} · will be filled in automatically</div></div>
    <span class="agent-leads-count">${a.count||0} leads</span>
  </div>`;
}

document.getElementById('assignModalSave').addEventListener('click',()=>{
  const l=leads.find(x=>x.id===assignLeadId); if(!l) return;
  const note=document.getElementById('assignNote').value.trim();
  if(!selectedAgent){ showToast('error','Selection required','Please select a salesman.'); return; }
  const btn=document.getElementById('assignModalSave'); btn.disabled=true;
  // Routed through the backend: ManualAssignmentService handles team resolution,
  // SLA reset, assignment history, audit and notification server-side.
  ajaxPost(CFG.urls.assign,{lead_id:l.id, salesman_id:selectedAgent.id, note:note})
    .then(()=>Promise.all([loadLeadsFromServer(),loadSalesmenFromServer()]))
    .then(()=>{ closeAssignModal(); renderTable(); showToast('success','Lead Assigned',`"${l.name}" assigned to ${selectedAgent?selectedAgent.name:''}.`); })
    .catch(err=>Swal.fire({title:'Assignment failed',text:String(err.message||err),icon:'error',confirmButtonColor:'var(--clr-orange)'}))
    .finally(()=>{ btn.disabled=false; });
});

/* ═══════════════════════════════════════════════════
   DETAIL / HISTORY MODAL
═══════════════════════════════════════════════════ */
function openDetailModal(id){
  const l=leads.find(x=>x.id===id); if(!l) return;
  detailLeadId=id; detailTab='all';
  document.getElementById('detailModalSub').textContent=l.name+' · '+(l.phone||'');
  const tColor=teamColor(l.team);
  const stageClass=STAGE_CLASS[l.stage]||'stage-fresh';
  document.getElementById('detailLeadInfo').innerHTML=`
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Stage</div><span class="stage-badge ${stageClass}">${escHtml(l.stage||'Fresh')}</span></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Status</div>${l.active===false?'<span style="color:#c0392b;font-weight:600;font-size:.82rem">Inactive</span>':'<span style="color:#27ae60;font-weight:600;font-size:.82rem">Active</span>'}</div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">SLA Remaining</div>${l.active===false?'<span style="color:var(--clr-gray);font-size:.82rem">—</span>':fmtSla(getSlaMs(l)).html}</div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Assigned To</div><div style="font-size:.82rem;color:var(--clr-text);font-weight:500">${l.assignedTo?escHtml(l.assignedTo):'<span class="unassigned-badge">⚠ Unassigned</span>'}</div></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Team</div><div style="font-size:.82rem;color:var(--clr-text);font-weight:500">${l.team?`<span style="color:${tColor};font-weight:600">${escHtml(l.team)}</span>`:'—'}</div></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Phone</div><div style="font-size:.82rem;color:var(--clr-text);font-weight:500">${l.phone?`<span class="phone-link" onclick="openPhoneModal('${l.id}',event)"><svg viewBox="0 0 24 24"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/></svg><span>${escHtml(l.phone)}</span></span>`:'—'}</div></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Source</div><div style="font-size:.82rem;color:var(--clr-text);font-weight:500">${renderSourceTag(l)}</div></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Created</div><div style="font-size:.82rem;color:var(--clr-text);font-weight:500">${fmtDate(l.createdAt)}</div></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Last Updated</div><div style="font-size:.82rem;color:var(--clr-text);font-weight:500">${fmtDate(l.updatedAt||l.createdAt)}</div></div>
    </div>`;
  l.history=l.history||[];
  document.querySelectorAll('#detailModal .history-tab').forEach((t,i)=>t.classList.toggle('active',i===0));
  document.getElementById('detailHistory').innerHTML='<div class="history-empty">Loading…</div>';
  document.getElementById('detailModal').classList.add('open');
  // History is built server-side from stage/assignment/follow-up/meeting/note records.
  ajaxGet(CFG.urls.history+'?lead_id='+encodeURIComponent(id))
    .then(d=>{ l.history=d.history||[]; if(detailLeadId===id) renderDetailHistory(l); })
    .catch(()=>{ document.getElementById('detailHistory').innerHTML='<div class="history-empty">Could not load history.</div>'; });
}
function closeDetailModal(){ document.getElementById('detailModal').classList.remove('open'); detailLeadId=null; }
document.getElementById('detailModalClose').addEventListener('click',closeDetailModal);
document.getElementById('detailModalClose2').addEventListener('click',closeDetailModal);
document.getElementById('detailModal').addEventListener('click',e=>{ if(e.target===e.currentTarget) closeDetailModal(); });

function switchDetailTab(tab,el){
  detailTab=tab;
  document.querySelectorAll('#detailModal .history-tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  const l=leads.find(x=>x.id===detailLeadId); if(!l) return;
  renderDetailHistory(l);
}

function renderDetailHistory(l){
  const allH=[...(l.history||[])].sort((a,b)=>(b.ts||0)-(a.ts||0));
  const meetings=allH.filter(h=>h.type==='meeting');
  const followups=allH.filter(h=>h.type==='followup');
  document.getElementById('dtTabAll').textContent=allH.length;
  document.getElementById('dtTabMeeting').textContent=meetings.length;
  document.getElementById('dtTabFollowup').textContent=followups.length;

  const dotIcons={
    created:'<polyline points="20 6 9 17 4 12"/>',
    stage:'<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    meeting:'<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    followup:'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/>',
    assignment:'<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/>',
    note:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
  };

  function bodyOf(h){
    let b='';
    if(h.by) b+=`<div class="history-body" style="margin-top:6px">👤 By: <strong>${escHtml(h.by)}</strong></div>`;
    if(h.type==='meeting'){
      if(h.meetingDate){ let ds=escHtml(h.meetingDate); if(h.meetingTime)ds+=' at '+escHtml(h.meetingTime); b+=`<div class="history-body" style="margin-top:6px">📅 Meeting date: <strong>${ds}</strong></div>`; }
      if(h.meetingLocation) b+=`<div class="history-body" style="margin-top:6px">📍 Location: ${escHtml(h.meetingLocation)}</div>`;
      if(h.feedback) b+=`<div class="history-body" style="margin-top:6px">📝 Notes: ${escHtml(h.feedback)}</div>`;
    } else if(h.type==='followup'){
      if(h.reminderDate){ let ds=escHtml(h.reminderDate); if(h.reminderTime)ds+=' at '+escHtml(h.reminderTime); b+=`<div class="history-body" style="margin-top:6px">⏰ Follow-up date: <strong>${ds}</strong></div>`; }
      if(h.feedback) b+=`<div class="history-body" style="margin-top:6px">📝 Notes: ${escHtml(h.feedback)}</div>`;
    } else {
      if(h.feedback) b+=`<div class="history-body" style="margin-top:6px">📝 ${escHtml(h.feedback)}</div>`;
      if(h.reason)   b+=`<div class="history-body" style="margin-top:6px">🚫 ${escHtml(h.reason)}</div>`;
    }
    return b;
  }

  function itemHtml(h){
    const dc=h.type||'note', ic=dotIcons[dc]||dotIcons.note;
    return `<div class="history-item">
      <div class="history-dot ${dc}"><svg viewBox="0 0 24 24">${ic}</svg></div>
      <div class="history-content">
        <div class="history-label">${escHtml(h.label)}</div>
        <div class="history-meta">${fmtDatetime(h.ts)}</div>
        ${bodyOf(h)}
      </div>
    </div>`;
  }

  let items=allH;
  if(detailTab==='meeting') items=meetings;
  else if(detailTab==='followup') items=followups;

  const cont=document.getElementById('detailHistory');
  if(!items.length){ cont.innerHTML=`<div class="history-empty">No ${detailTab==='all'?'activity':detailTab+' entries'} found.</div>`; return; }
  cont.innerHTML='<div class="history-timeline">'+items.map(itemHtml).join('')+'</div>';
}

/* ═══════════════════════════════════════════════════
   TOAST
═══════════════════════════════════════════════════ */
function showToast(type,title,msg){
  const icons={success:'<polyline points="20 6 9 17 4 12"/>',error:'<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',info:'<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'};
  const t=document.createElement('div'); t.className='toast '+type;
  t.innerHTML=`<div class="toast-icon"><svg viewBox="0 0 24 24">${icons[type]||''}</svg></div><div class="toast-body"><div class="toast-title">${escHtml(title)}</div><div class="toast-msg">${escHtml(msg)}</div></div><button class="toast-dismiss" onclick="this.parentElement.remove()">✕</button>`;
  document.getElementById('toastContainer').appendChild(t);
  setTimeout(()=>{ t.classList.add('toast-out'); setTimeout(()=>t.remove(),300); },3500);
}

/* ═══════════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════════ */
Promise.all([loadLeadsFromServer(),loadSalesmenFromServer()]).then(()=>{
  const urlParams = new URLSearchParams(window.location.search);
  const searchVal = urlParams.get('search');
  if (searchVal) {
    searchQuery = searchVal;
    const input = document.getElementById('searchInput');
    if (input) input.value = searchVal;
  }
  kpiFilter('all');
  renderTable();
});
setInterval(()=>{ loadLeadsFromServer().then(renderTable); }, 60000);

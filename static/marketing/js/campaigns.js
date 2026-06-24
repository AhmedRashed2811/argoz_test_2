/* ═══════════════════════════════════════════════════════
   DATA & STORAGE
═══════════════════════════════════════════════════════ */
const LS_KEY    = 'prometheus_campaigns';
const LS_KEY_ID = 'prometheus_campaigns_nextId';
const LS_KEY_IMGS = 'prometheus_campaigns_images';
const LS_KEY_VERSION = 'prometheus_campaigns_version';
const DATA_VERSION = 'v10';

const _defaults = [
  {
    id:1, name:'Zed Launch Phase1',
    description:'',
    startDate:'2026-06-20', endDate:'2026-07-20',
    campaignTypes:['events','social'], leads:1,
    typeLeads:{events:1,social:1},
    approval:'pending', approvalReason:'Awaiting CFO sign-off. Celebrity fee for Amr Diab exceeds the pre-approved entertainment budget cap. Finance team has requested a revised cost breakdown before final approval.',
    eventsMulti:[{ name: 'Zed East Launch Party', budget: 200000, celebrities:[{name:'Amr Diab',budget:250000}], giveaways:[{name:'Branded Bags',budget:15000}], catering:[{name:'Kempinski',budget:35000}] }],
    socialMulti:[{ adName: 'Social Campaign', platformBudgets:[{platform:'Meta',budget:35000},{platform:'TikTok',budget:20000},{platform:'LinkedIn',budget:25000}], budget:80000 }],
    extraBudget:0, extraNote:'', otherCosts:[{reason:'Photography & Video',value:50000},{reason:'Event Logistics',value:30000}]
  },
  {
    id:2, name:'Badya Ramadan Campaign',
    description:'',
    startDate:'2026-02-15', endDate:'2026-04-10',
    campaignTypes:['tv','street'], leads:2,
    typeLeads:{tv:1,street:1},
    approval:'approved', approvalReason:'Budget reviewed and approved by the Finance Committee on 10 Feb 2026. TV slots and outdoor placements are within the allocated Q1 marketing budget. All vendor contracts have been reviewed.',
    tvMulti:[{ name: 'Ramadan TV Spot', budget: 300000, channels:[{channelName:'CBC Sofra',budget:180000},{channelName:'MBC Masr',budget:120000}] }],
    streetMulti:[{ name: 'Badya Outdoor', budget: 200000, adTypes:[{type:'Billboard',count:5,budget:120000},{type:'LED Screen',count:3,budget:80000}] }],
    extraBudget:0, extraNote:'', otherCosts:[{reason:'Agency Fees',value:100000},{reason:'Production',value:100000}]
  },
  {
    id:3, name:'Sodic Social Summer',
    description:'',
    startDate:'2026-06-14', endDate:'2026-08-31',
    campaignTypes:['social'], leads:2,
    typeLeads:{social:2},
    approval:'semi', approvalReason:'Digital media spend on Meta and Google Ads is approved. TikTok budget is on hold pending legal review of the new influencer content policy. Campaign may proceed with approved platforms in the meantime.',
    socialMulti:[{ adName: 'Summer Campaign', platformBudgets:[{platform:'Meta',budget:80000},{platform:'TikTok',budget:60000},{platform:'Google Ads (Website)',budget:40000}], budget:180000 }],
    extraBudget:0, extraNote:'', otherCosts:[{reason:'Content Creation',value:60000},{reason:'Influencer Fees',value:40000}]
  },
  {
    id:4, name:'New Cairo Billboard Q2',
    description:'',
    startDate:'2026-03-25', endDate:'2026-06-30',
    campaignTypes:['street'], leads:2,
    typeLeads:{street:2},
    approval:'not-approved', approvalReason:'Total campaign budget of EGP 560,000 significantly exceeds the Q2 outdoor advertising ceiling of EGP 350,000. The number of lamp post units (20) was flagged as excessive for the target area. Please revise the scope and resubmit.',
    streetMulti:[{ name: 'New Cairo Outdoor', budget: 380000, adTypes:[{type:'Billboard',count:8,budget:200000},{type:'Banner',count:12,budget:80000},{type:'Lamp Post',count:20,budget:100000}] }],
    extraBudget:0, extraNote:'', otherCosts:[{reason:'Design & Production',value:80000},{reason:'Installation Fees',value:100000}]
  }
];

function stripAndStoreImages(c) {
  const lean = JSON.parse(JSON.stringify(c));
  const imgStore = {};
  function strip(obj, path) {
    if (!obj) return;
    ['logo','images'].forEach(field => {
      if (Array.isArray(obj[field]) && obj[field].length) { imgStore[path+'.'+field]=obj[field]; obj[field]=[]; }
    });
  }
  function stripTvChannels(tvObj, path) {
    if (!tvObj) return;
    strip(tvObj, path);
    (tvObj.channels||[]).forEach((ch,ci) => {
      const chPath=path+'.channels.'+ci;
      if (Array.isArray(ch.media)&&ch.media.length) { imgStore[chPath+'.media']=ch.media; ch.media=[]; }
    });
  }
  strip(lean.events,'events');
  (lean.eventsMulti||[]).forEach((ev,i)=>strip(ev,'eventsMulti.'+i));
  stripTvChannels(lean.tv,'tv');
  (lean.tvMulti||[]).forEach((tv,i)=>stripTvChannels(tv,'tvMulti.'+i));
  strip(lean.street,'street');
  (lean.streetMulti||[]).forEach((st,i)=>strip(st,'streetMulti.'+i));
  strip(lean.social,'social');
  (lean.socialMulti||[]).forEach((sm,i)=>strip(sm,'socialMulti.'+i));
  (lean.exhibitionMulti||[]).forEach((ex,i)=>strip(ex,'exhibitionMulti.'+i));
  return {lean,imgStore};
}

function rehydrateImages(c, imgStore) {
  function rehydrate(obj, path) {
    if (!obj) return;
    ['logo','images'].forEach(field => { const key=path+'.'+field; if(imgStore[key]) obj[field]=imgStore[key]; });
  }
  function rehydrateTv(tvObj, path) {
    if (!tvObj) return;
    rehydrate(tvObj, path);
    (tvObj.channels||[]).forEach((ch,ci)=>{ const key=path+'.channels.'+ci+'.media'; if(imgStore[key]) ch.media=imgStore[key]; });
  }
  rehydrate(c.events,'events');
  (c.eventsMulti||[]).forEach((ev,i)=>rehydrate(ev,'eventsMulti.'+i));
  rehydrateTv(c.tv,'tv');
  (c.tvMulti||[]).forEach((tv,i)=>rehydrateTv(tv,'tvMulti.'+i));
  rehydrate(c.street,'street');
  (c.streetMulti||[]).forEach((st,i)=>rehydrate(st,'streetMulti.'+i));
  rehydrate(c.social,'social');
  (c.socialMulti||[]).forEach((sm,i)=>rehydrate(sm,'socialMulti.'+i));
  (c.exhibitionMulti||[]).forEach((ex,i)=>rehydrate(ex,'exhibitionMulti.'+i));
}

/* ── Server-backed data layer (replaces localStorage; see marketing views) ── */
function _cfg() { return window.CAMPAIGN_CFG || {}; }
function _headers() { return {'Content-Type':'application/json','X-CSRFToken':_cfg().csrf||''}; }
function _campUrl(tmpl, id) { return tmpl.replace('00000000-0000-0000-0000-000000000000', id); }
async function fetchCampaigns() {
  try {
    const r = await fetch(_cfg().listUrl, {headers:{'X-CSRFToken':_cfg().csrf||''}, credentials:'same-origin'});
    if (r.ok) campaigns = await r.json();
  } catch(e) { console.error('fetchCampaigns failed:', e); }
  return campaigns;
}
async function apiSend(url, method, body) {
  const r = await fetch(url, {method, headers:_headers(), credentials:'same-origin',
    body: body ? JSON.stringify(body) : undefined});
  let data = {}; try { data = await r.json(); } catch(e) {}
  if (!r.ok) throw new Error(data.error || ('Request failed (' + r.status + ')'));
  return data;
}
// In-memory list; renderTable's reload hook just returns the current array.
function loadCampaigns() { return campaigns; }
function saveCampaigns() { /* persisted server-side per mutation */ }

function syncSocialAdFromCampaign(c) {
  if (!c.social) return;
  try {
    const smRaw=localStorage.getItem('prometheus_social_media'); if(!smRaw) return;
    const ads=JSON.parse(smRaw); const idx=ads.findIndex(a=>a.campaignId==c.id); if(idx<0) return;
    const ad=ads[idx]; ad.platforms=c.social.platforms||[]; ad.start=c.social.start||''; ad.end=c.social.end||''; ad.budget=Number(c.social.budget||0); ad.leads=Number(c.social.leads||0); ad.audience=c.social.audience||''; ad.campaignName=c.name;
    localStorage.setItem('prometheus_social_media',JSON.stringify(ads));
  } catch(e) {}
}

function getLinkedTvAdFromLS(campaignId) {
  try { const raw=localStorage.getItem('prometheus_tv_ads'); if(!raw) return null; return JSON.parse(raw).find(a=>a.campaignId==campaignId)||null; } catch(e){ return null; }
}
function getLinkedEventsFromLS(campaignId) {
  try { const raw=localStorage.getItem('prometheus_events'); if(!raw) return []; return JSON.parse(raw).filter(e=>e.campaignId==campaignId); } catch(e){ return []; }
}

let campaigns = [];
let nextId = 1;
let sortField=null, sortAscMap={}, searchQuery='', editingIndex=null;
const PAGE_SIZE=5; let currentPage=1, totalPages=1;
let activeNameFilters=new Set(), activeTypeFilters=new Set(), activeStartFilters=new Set(), activeEndFilters=new Set(), activeStatusFilters=new Set(), activeApprovalFilters=new Set();
let filterNameOpen=false, filterTypeOpen=false, filterStartOpen=false, filterEndOpen=false, filterBudgetOpen=false, filterLeadsOpen=false, filterStatusOpen=false, filterApprovalOpen=false;
const _storedImages={};
const _pendingImageReads={};
let _approvalEditIndex=null, _selectedApproval=null;
let _skipNextReload=false;

/* ═══════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════ */
function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function fmtBudget(n) { return n ? Number(n).toLocaleString('en-US') : '—'; }
function fmtDate(d) {
  if (!d) return '—';
  const [y,m,day]=d.split('-');
  return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][parseInt(m)-1]+' '+parseInt(day)+', '+y;
}
function getStatus(c) {
  const today=new Date().toISOString().slice(0,10);
  if (!c.endDate) return 'upcoming';
  if (c.endDate<today) return 'ended';
  if (c.startDate&&c.startDate>today) return 'upcoming';
  return 'active';
}
function calcEvSubBudget(ev) {
  let s=Number(ev.budget||0);
  (ev.celebrities||[]).forEach(x=>{ s+=Number(x.budget||0); });
  (ev.giveaways||[]).forEach(x=>{ s+=Number(x.budget||0); });
  (ev.catering||[]).forEach(x=>{ s+=Number(x.budget||0); });
  return s;
}
function calcBudget(c) {
  let t=0;
  (c.campaignTypes||[]).forEach(ct => {
    if (ct==='events') return;
    if (ct==='exhibition') { (c.exhibitionMulti||[]).forEach(ex=>{ t+=Number(ex.budget||0); }); return; }
    // social: sum per-platform budgets from multi ads
    if (ct==='social') {
      (c.socialMulti||[]).forEach(sm => {
        if (Array.isArray(sm.platformBudgets)) sm.platformBudgets.forEach(pb=>{ t+=Number(pb.budget||0); });
        else t+=Number(sm.budget||0);
      });
      if (!c.socialMulti?.length && c.social?.budget) t+=Number(c.social.budget);
      return;
    }
    if (c[ct]?.budget) t+=Number(c[ct].budget);
    if (ct==='tv') { (c.tvMulti||[]).forEach(tv=>{ if(tv!==c.tv) t+=Number(tv.budget||0); }); }
    if (ct==='street') { (c.streetMulti||[]).forEach(st=>{ if(st!==c.street) t+=Number(st.budget||0); }); }
  });
  // Other costs
  (c.otherCosts||[]).forEach(oc=>{ t+=Number(oc.value||0); });
  t+=Number(c.extraBudget||0);
  // Events from LS (include celebrities/giveaways/catering)
  const linkedEvs=getLinkedEventsFromLS(c.id);
  if (linkedEvs.length) linkedEvs.forEach(ev=>{ t+=calcEvSubBudget(ev); });
  else if ((c.campaignTypes||[]).includes('events')) {
    (c.eventsMulti||(c.events?[c.events]:[])).forEach(ev=>{ t+=calcEvSubBudget(ev); });
  }
  return t;
}
function calcLeads(c) {
  // If typeLeads is present, sum it directly (it IS the total)
  if (c.typeLeads && Object.keys(c.typeLeads).length) {
    return Object.values(c.typeLeads).reduce((s,v)=>s+Number(v||0),0);
  }
  let total=(c.campaignTypes||[]).reduce((s,t)=>{ if(t==='events') return s; return s+Number(c[t]?.leads||0); },0);
  total+=Number(c.leads||0);
  const linkedEvs=getLinkedEventsFromLS(c.id);
  total+=linkedEvs.reduce((s,ev)=>s+Number(ev.leads||0),0);
  if (!linkedEvs.length&&(c.campaignTypes||[]).includes('events')&&c.events?.leads) total+=Number(c.events.leads||0);
  return total;
}
function getTypeLeadsBreakdown(c) {
  const typeLabels={events:'🎪 Events',tv:'📺 TV Ads',street:'🏙️ Street Ads',social:'📱 Social Media',exhibition:'🏛️ Exhibition'};
  const types = c.campaignTypes || [];
  const tl = c.typeLeads || {};
  const result = {};
  types.forEach(t => { result[t] = Number(tl[t]||0); });
  return result;
}
function getTypeLabel(c) {
  const map={events:'Events',tv:'TV Ads',street:'Street Ads',social:'Social Media',exhibition:'Exhibition'};
  return (c.campaignTypes||[]).map(t=>map[t]||t).join(', ');
}

/* ═══════════════════════════════════════════════════════
   RENDER TABLE
═══════════════════════════════════════════════════════ */
function getDisplayList() {
  let list=campaigns.map((c,i)=>({c,origIndex:i}));
  if (activeNameFilters.size) list=list.filter(d=>activeNameFilters.has(d.c.name));
  if (activeTypeFilters.size) list=list.filter(d=>(d.c.campaignTypes||[]).some(t=>activeTypeFilters.has(t)));
  if (activeStartFilters.size) list=list.filter(d=>activeStartFilters.has((d.c.startDate||'').slice(0,7)));
  if (activeEndFilters.size) list=list.filter(d=>activeEndFilters.has((d.c.endDate||'').slice(0,7)));
  if (activeStatusFilters.size) list=list.filter(d=>activeStatusFilters.has(getStatus(d.c)));
  if (activeApprovalFilters.size) list=list.filter(d=>activeApprovalFilters.has(d.c.approval||'pending'));
  const bMin=Number(document.getElementById('budgetMin')?.value||0), bMax=Number(document.getElementById('budgetMax')?.value||0);
  if (bMin>0) list=list.filter(d=>calcBudget(d.c)>=bMin);
  if (bMax>0) list=list.filter(d=>calcBudget(d.c)<=bMax);
  const lMin=Number(document.getElementById('leadsMin')?.value||0), lMax=Number(document.getElementById('leadsMax')?.value||0);
  if (lMin>0) list=list.filter(d=>calcLeads(d.c)>=lMin);
  if (lMax>0) list=list.filter(d=>calcLeads(d.c)<=lMax);
  if (searchQuery.trim()) { const q=searchQuery.trim().toLowerCase(); list=list.filter(d=>d.c.name.toLowerCase().includes(q)); }
  if (sortField&&sortAscMap[sortField]!=null) {
    const asc=sortAscMap[sortField];
    list.sort((a,b)=>{
      if (sortField==='budget') return asc?calcBudget(a.c)-calcBudget(b.c):calcBudget(b.c)-calcBudget(a.c);
      if (sortField==='leads')  return asc?calcLeads(a.c)-calcLeads(b.c):calcLeads(b.c)-calcLeads(a.c);
      const va=String(a.c[sortField]||''),vb=String(b.c[sortField]||'');
      return asc?va.localeCompare(vb):vb.localeCompare(va);
    });
  }
  return list;
}

function goPage(p) { if(p<1||p>totalPages) return; currentPage=p; renderTable(); }
function renderPagination(total) {
  totalPages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  if (currentPage>totalPages) currentPage=totalPages;
  const bar=document.getElementById('paginationBar');
  bar.style.display=totalPages<=1?'none':'flex';
  const start=(currentPage-1)*PAGE_SIZE+1, end=Math.min(currentPage*PAGE_SIZE,total);
  document.getElementById('pgInfo').textContent='Showing '+start+'–'+end+' of '+total+' campaigns';
  document.getElementById('pgFirst').disabled=currentPage===1;
  document.getElementById('pgPrev').disabled=currentPage===1;
  document.getElementById('pgNext').disabled=currentPage===totalPages;
  document.getElementById('pgLast').disabled=currentPage===totalPages;
  const nums=document.getElementById('pgNumbers'); nums.innerHTML='';
  let s=Math.max(1,currentPage-2),e=Math.min(totalPages,s+4); s=Math.max(1,e-4);
  if (s>1) { addPgNum(nums,1); if(s>2) nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>'); }
  for (let i=s;i<=e;i++) addPgNum(nums,i);
  if (e<totalPages) { if(e<totalPages-1) nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>'); addPgNum(nums,totalPages); }
}
function addPgNum(container,n) {
  const b=document.createElement('button'); b.className='pg-btn'+(n===currentPage?' active':''); b.textContent=n; b.onclick=()=>goPage(n); container.appendChild(b);
}

const APPROVAL_LABELS = {approved:'Approved','not-approved':'Not Approved',pending:'Pending',semi:'Semi Approved'};
const APPROVAL_CLASSES = {approved:'approved','not-approved':'not-approved',pending:'pending',semi:'semi'};

function renderTable() {
  if (!_skipNextReload) { const fresh=loadCampaigns(); if(JSON.stringify(fresh)!==JSON.stringify(campaigns)) campaigns=fresh; }
  _skipNextReload=false;
  const tbody=document.getElementById('tableBody'), list=getDisplayList();
  document.getElementById('kpiTotal').textContent=campaigns.length;
  document.getElementById('kpiActive').textContent=campaigns.filter(c=>getStatus(c)==='active').length;
  const typeSet=new Set(); campaigns.forEach(c=>(c.campaignTypes||[]).forEach(t=>typeSet.add(t)));
  document.getElementById('kpiTypes').textContent=typeSet.size;
  document.getElementById('kpiBudget').textContent=campaigns.reduce((s,c)=>s+calcBudget(c),0).toLocaleString('en-US');
  const campaignLeadsFromRecords=(()=>{ try { const all=JSON.parse(localStorage.getItem('prometheus_leads')||'[]'); return all.filter(l=>['event','callcenter','walkin','vip'].includes(l.source)).length+all.filter(l=>l.source==='broker').length; } catch(e){ return 0; } })();
  const campaignLeadsFromData=campaigns.reduce((s,c)=>s+calcLeads(c),0);
  document.getElementById('kpiLeads').textContent=Math.max(campaignLeadsFromRecords,campaignLeadsFromData).toLocaleString('en-US');
  document.getElementById('searchHint').textContent=searchQuery.trim()||activeNameFilters.size?`${list.length} result${list.length!==1?'s':''} found`:`${campaigns.length} campaign${campaigns.length!==1?'s':''}`;
  renderPagination(list.length);
  if (!list.length) { tbody.innerHTML=`<tr class="no-results-row"><td colspan="9"><div class="no-results-icon"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span>No campaigns found</span></div></td></tr>`; return; }
  const pageData=list.slice((currentPage-1)*PAGE_SIZE,currentPage*PAGE_SIZE);
  const statusLabels={active:'Active',ended:'Ended',upcoming:'Upcoming'};
  const statusColors={active:'#27ae60',ended:'#7a7570',upcoming:'#2980b9'};
  const _typeLabels={events:'Events',tv:'TV Ads',street:'Street Ads',social:'Social Media',exhibition:'Exhibition'};
  tbody.innerHTML=pageData.map(({c,origIndex})=>{
    const status=getStatus(c);
    const _ownTypes=(c.campaignTypes||[]);
    const _hasLinkedEvs=getLinkedEventsFromLS(c.id).length>0;
    const _hasLinkedTv=!_ownTypes.includes('tv')&&!!getLinkedTvAdFromLS(c.id);
    let _allChipTypes=(_hasLinkedEvs&&!_ownTypes.includes('events'))?['events',..._ownTypes]:[..._ownTypes];
    if (_hasLinkedTv) _allChipTypes.push('tv');
    const chips=_allChipTypes.map(t=>`<span class="type-chip">${_typeLabels[t]||t}</span>`).join('');
    const leadsVal=calcLeads(c).toLocaleString('en-US');
    const appr=c.approval||'pending';
    const apprLabel=APPROVAL_LABELS[appr]||'Pending';
    const apprClass=APPROVAL_CLASSES[appr]||'pending';
    return `<tr>
      <td><span class="campaign-name-text">${escHtml(c.name)}</span></td>
      <td><div class="type-chips">${chips}</div></td>
      <td style="font-size:.84rem">${fmtDate(c.startDate)}</td>
      <td style="font-size:.84rem">${fmtDate(c.endDate)}</td>
      <td><span class="budget-val"> ${calcBudget(c).toLocaleString('en-US')}</span></td>
      <td><span class="leads-badge">${leadsVal}</span></td>
      <td><span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:600;background:${statusColors[status]}1a;color:${statusColors[status]}">${statusLabels[status]}</span></td>
      <td><span class="approval-badge ${apprClass}" onclick="openApprovalModal(${origIndex})" title="Click to view approval status"><span class="dot"></span>${apprLabel}</span></td>
      <td>
        <div class="action-btns">
          <button class="action-btn view"   title="View details" onclick="openView(${origIndex})"><svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>
          ${_cfg().canUpdate?`<button class="action-btn edit"   title="Edit"         onclick="openEdit(${origIndex})"><svg viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>`:''}
          ${_cfg().canDelete?`<button class="action-btn delete" title="Delete"       onclick="deleteCampaign(${origIndex})"><svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg></button>`:''}
        </div>
      </td>
    </tr>`;
  }).join('');
}

/* ═══════════════════════════════════════════════════════
   APPROVAL MODAL
═══════════════════════════════════════════════════════ */
function openApprovalModal(index) {
  const c=campaigns[index];
  const appr=c.approval||'pending';
  document.getElementById('approvalModalSub').textContent='Campaign: '+c.name;
  // Configure status display
  const statusConfig={
    approved:  {label:'Approved',      icon:'✅', bg:'rgba(39,174,96,.1)',  color:'#1e8449',  border:'rgba(39,174,96,.25)'},
    semi:      {label:'Semi Approved', icon:'🔵', bg:'rgba(41,128,185,.1)', color:'#1a5276',  border:'rgba(41,128,185,.2)'},
    pending:   {label:'Pending',       icon:'⏳', bg:'rgba(243,156,18,.1)', color:'#b7770d',  border:'rgba(243,156,18,.25)'},
    'not-approved':{label:'Not Approved',icon:'❌',bg:'rgba(192,57,43,.08)', color:'#c0392b', border:'rgba(192,57,43,.2)'}
  };
  const cfg=statusConfig[appr]||statusConfig.pending;
  const displayEl=document.getElementById('approvalStatusDisplay');
  displayEl.style.background=cfg.bg; displayEl.style.border='1.5px solid '+cfg.border;
  document.getElementById('approvalStatusIcon').textContent=cfg.icon;
  const labelEl=document.getElementById('approvalStatusLabel');
  labelEl.textContent=cfg.label; labelEl.style.color=cfg.color;
  // Reason
  const reason=(c.approvalReason||'').trim();
  const reasonEl=document.getElementById('approvalReasonDisplay');
  if (reason) {
    reasonEl.textContent=reason; reasonEl.style.color='var(--clr-text)';
  } else {
    reasonEl.textContent='No reason or note provided.'; reasonEl.style.color='var(--clr-text-sub)';
  }
  document.getElementById('approvalModal').classList.add('open');
  document.body.style.overflow='hidden';
}
function closeApprovalModal() { document.getElementById('approvalModal').classList.remove('open'); document.body.style.overflow=''; }
document.getElementById('approvalModal').addEventListener('click',e=>{ if(e.target===e.currentTarget) closeApprovalModal(); });

/* ═══════════════════════════════════════════════════════
   SEARCH & SORT
═══════════════════════════════════════════════════════ */
document.getElementById('searchInput').addEventListener('input',e=>{ searchQuery=e.target.value; currentPage=1; renderTable(); });
const SORT_BTNS={sortNameBtn:'name',sortStartBtn:'startDate',sortEndBtn:'endDate',sortBudgetBtn:'budget',sortLeadsBtn:'leads'};
function applySortBtn(field,btnId) {
  const prev=sortAscMap[field];
  if (prev==null) sortAscMap[field]=true; else if (prev===true) sortAscMap[field]=false; else { delete sortAscMap[field]; }
  sortField=sortAscMap[field]!=null?field:null;
  Object.keys(SORT_BTNS).forEach(id=>{ const b=document.getElementById(id); if(!b) return; b.classList.remove('active-sort'); b.querySelector('svg').innerHTML='<path d="M3 6h18M7 12h10M11 18h2"/>'; });
  if (sortField) { const b=document.getElementById(btnId); if(b){ b.classList.add('active-sort'); b.querySelector('svg').innerHTML=sortAscMap[field]?'<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 4 20 7 17 10" style="stroke-width:1.8"/>':`<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 14 20 17 17 20" style="stroke-width:1.8"/>`; } }
  currentPage=1; renderTable();
}
Object.entries(SORT_BTNS).forEach(([btnId,field])=>document.getElementById(btnId)?.addEventListener('click',()=>applySortBtn(field,btnId)));

/* ═══════════════════════════════════════════════════════
   FILTERS
═══════════════════════════════════════════════════════ */
function closeAllFilters() {
  filterNameOpen=filterTypeOpen=filterStartOpen=filterEndOpen=filterBudgetOpen=filterLeadsOpen=filterStatusOpen=filterApprovalOpen=false;
  ['filterNameDropdown','filterTypeDropdown','filterStartDropdown','filterEndDropdown','filterBudgetDropdown','filterLeadsDropdown','filterStatusDropdown','filterApprovalDropdown'].forEach(id=>document.getElementById(id)?.classList.remove('open'));
}
function positionDropdown(ddId,btnId) {
  const dd=document.getElementById(ddId),r=document.getElementById(btnId).getBoundingClientRect();
  dd.classList.add('open'); dd.style.top=r.bottom+4+'px'; dd.style.left=Math.min(r.left,window.innerWidth-dd.offsetWidth-8)+'px';
}
function renderNameFilterList() {
  const q=(document.getElementById('filterNameSearch')?.value||'').toLowerCase();
  const names=[...new Set(campaigns.map(c=>c.name))].sort().filter(n=>n.toLowerCase().includes(q));
  document.getElementById('filterNameList').innerHTML=names.map(n=>`<label class="filter-item"><input type="checkbox" value="${escHtml(n)}" ${activeNameFilters.has(n)?'checked':''} onchange="toggleFilter('name','${escHtml(n)}',this.checked)"><span style="font-size:.83rem;color:var(--clr-text)">${escHtml(n)}</span></label>`).join('');
}
function toggleFilter(type,val,checked) {
  if(type==='name'){if(checked)activeNameFilters.add(val);else activeNameFilters.delete(val);}
  else if(type==='type'){if(checked)activeTypeFilters.add(val);else activeTypeFilters.delete(val);}
  else if(type==='start'){if(checked)activeStartFilters.add(val);else activeStartFilters.delete(val);}
  else if(type==='end'){if(checked)activeEndFilters.add(val);else activeEndFilters.delete(val);}
  else if(type==='approval'){if(checked)activeApprovalFilters.add(val);else activeApprovalFilters.delete(val);}
  currentPage=1; renderTable();
}
function renderTypeFilterList() {
  const types=[...new Set(campaigns.flatMap(c=>c.campaignTypes||[]))].sort();
  const labels={events:'Events',tv:'TV Ads',street:'Street Ads',social:'Social Media',exhibition:'Exhibition'};
  document.getElementById('filterTypeList').innerHTML=types.map(t=>`<label class="filter-item"><input type="checkbox" value="${t}" ${activeTypeFilters.has(t)?'checked':''} onchange="toggleFilter('type','${t}',this.checked)"><span style="font-size:.83rem;color:var(--clr-text)">${labels[t]||t}</span></label>`).join('');
}
/* ═══════════ DATE FILTER TREE (year+month, matches campaigns page) ═══════════ */
const _dateTreeOpen={start:new Set(),end:new Set()};
const activeDateFilters={start:activeStartFilters,end:activeEndFilters};
function buildDateTree(field) {
  const key=field==='start'?'startDate':'endDate';
  const map={};
  campaigns.forEach(c=>{
    const d=c[key]||''; if(!d) return;
    const year=d.slice(0,4), month=d.slice(0,7);
    if(!map[year]) map[year]=new Set();
    map[year].add(month);
  });
  return map;
}
function renderDateFilter(field) {
  const containerId='filter'+(field==='start'?'Start':'End')+'List';
  const container=document.getElementById(containerId);
  const tree=buildDateTree(field);
  const activeSet=activeDateFilters[field];
  const monthNames=['January','February','March','April','May','June','July','August','September','October','November','December'];
  const openSet=_dateTreeOpen[field];
  container.innerHTML='';
  Object.keys(tree).sort().reverse().forEach(year=>{
    const months=[...tree[year]].sort();
    const allChecked=months.every(m=>activeSet.has(m));
    const someChecked=months.some(m=>activeSet.has(m));
    const isOpen=openSet.has(year);
    const wrapper=document.createElement('div');
    const yearRow=document.createElement('div');
    yearRow.className='date-tree-year';
    const lbl=document.createElement('label');
    lbl.style.cssText='display:flex;align-items:center;gap:8px;cursor:pointer;flex:1';
    lbl.onclick=e=>e.stopPropagation();
    const cb=document.createElement('input');
    cb.type='checkbox'; cb.style.accentColor='var(--clr-orange)';
    cb.checked=allChecked; cb.indeterminate=!allChecked&&someChecked;
    cb.onchange=()=>{ months.forEach(m=>{if(cb.checked)activeSet.add(m);else activeSet.delete(m);}); renderDateFilter(field); currentPage=1; renderTable(); };
    const yearSpan=document.createElement('span'); yearSpan.textContent=year;
    lbl.appendChild(cb); lbl.appendChild(yearSpan);
    const chevron=document.createElement('span');
    chevron.className='date-tree-chevron'+(isOpen?' open':''); chevron.innerHTML='&#9658;';
    yearRow.appendChild(lbl); yearRow.appendChild(chevron);
    yearRow.onclick=()=>{ if(openSet.has(year)) openSet.delete(year); else openSet.add(year); monthsDiv.classList.toggle('open',openSet.has(year)); chevron.classList.toggle('open',openSet.has(year)); };
    const monthsDiv=document.createElement('div');
    monthsDiv.className='date-tree-months'+(isOpen?' open':'');
    months.forEach(ym=>{
      const mIdx=parseInt(ym.slice(5))-1, mName=monthNames[mIdx]||ym;
      const mLabel=document.createElement('label'); mLabel.className='filter-item';
      const mCb=document.createElement('input'); mCb.type='checkbox'; mCb.style.accentColor='var(--clr-orange)';
      mCb.checked=activeSet.has(ym);
      mCb.onchange=()=>{ if(mCb.checked)activeSet.add(ym); else activeSet.delete(ym); cb.checked=months.every(m=>activeSet.has(m)); cb.indeterminate=!cb.checked&&months.some(m=>activeSet.has(m)); currentPage=1; renderTable(); };
      const mSpan=document.createElement('span'); mSpan.style.cssText='font-size:.83rem;color:var(--clr-text)'; mSpan.textContent=mName;
      mLabel.appendChild(mCb); mLabel.appendChild(mSpan);
      monthsDiv.appendChild(mLabel);
    });
    wrapper.appendChild(yearRow); wrapper.appendChild(monthsDiv);
    container.appendChild(wrapper);
  });
  if(!Object.keys(tree).length) container.innerHTML='<div style="padding:10px 14px;font-size:.82rem;color:var(--clr-text-sub)">No dates available</div>';
}
function openDateFilter(field,btnId) {
  const ddId='filter'+(field==='start'?'Start':'End')+'Dropdown';
  const currently=field==='start'?filterStartOpen:filterEndOpen;
  closeAllFilters();
  if(currently) return;
  if(field==='start') filterStartOpen=true; else filterEndOpen=true;
  const dd=document.getElementById(ddId); dd.classList.add('open');
  const r=document.getElementById(btnId).getBoundingClientRect();
  dd.style.top=r.bottom+4+'px'; dd.style.left=Math.min(r.left,window.innerWidth-248)+'px';
  renderDateFilter(field);
}
const STATUS_OPTIONS=[{val:'active',label:'Active'},{val:'upcoming',label:'Upcoming'},{val:'ended',label:'Ended'}];
function renderStatusFilterList() {
  document.getElementById('filterStatusList').innerHTML=STATUS_OPTIONS.map(({val,label})=>`<label class="filter-item"><input type="checkbox" value="${val}" ${activeStatusFilters.has(val)?'checked':''} onchange="toggleStatusFilter('${val}',this.checked)"><span style="font-size:.83rem;color:var(--clr-text)">${label}</span></label>`).join('');
}
function toggleStatusFilter(val,checked){if(checked)activeStatusFilters.add(val);else activeStatusFilters.delete(val);currentPage=1;renderTable();}
const APPROVAL_OPTIONS=[{val:'approved',label:'Approved'},{val:'semi',label:'Semi Approved'},{val:'pending',label:'Pending'},{val:'not-approved',label:'Not Approved'}];
function renderApprovalFilterList() {
  document.getElementById('filterApprovalList').innerHTML=APPROVAL_OPTIONS.map(({val,label})=>`<label class="filter-item"><input type="checkbox" value="${val}" ${activeApprovalFilters.has(val)?'checked':''} onchange="toggleFilter('approval','${val}',this.checked)"><span style="font-size:.83rem;color:var(--clr-text)">${label}</span></label>`).join('');
}
document.getElementById('filterNameBtn').addEventListener('click',e=>{e.stopPropagation();const c=filterNameOpen;closeAllFilters();if(c)return;filterNameOpen=true;positionDropdown('filterNameDropdown','filterNameBtn');renderNameFilterList();});
document.getElementById('filterNameSearch').addEventListener('input',()=>renderNameFilterList());
document.getElementById('filterNameSelectAll').addEventListener('click',e=>{e.stopPropagation();campaigns.forEach(c=>activeNameFilters.add(c.name));renderNameFilterList();currentPage=1;renderTable();});
document.getElementById('filterNameClearAll').addEventListener('click',e=>{e.stopPropagation();activeNameFilters.clear();renderNameFilterList();currentPage=1;renderTable();});
document.getElementById('filterTypeBtn').addEventListener('click',e=>{e.stopPropagation();const c=filterTypeOpen;closeAllFilters();if(c)return;filterTypeOpen=true;positionDropdown('filterTypeDropdown','filterTypeBtn');renderTypeFilterList();});
document.getElementById('filterTypeSelectAll').addEventListener('click',e=>{e.stopPropagation();[...new Set(campaigns.flatMap(c=>c.campaignTypes||[]))].forEach(t=>activeTypeFilters.add(t));renderTypeFilterList();currentPage=1;renderTable();});
document.getElementById('filterTypeClearAll').addEventListener('click',e=>{e.stopPropagation();activeTypeFilters.clear();renderTypeFilterList();currentPage=1;renderTable();});
document.getElementById('filterStartBtn').addEventListener('click',e=>{e.stopPropagation();openDateFilter('start','filterStartBtn');});
document.getElementById('filterStartSelectAll').addEventListener('click',e=>{e.stopPropagation();const tree=buildDateTree('start');Object.values(tree).forEach(s=>s.forEach(m=>activeStartFilters.add(m)));renderDateFilter('start');currentPage=1;renderTable();});
document.getElementById('filterStartClearAll').addEventListener('click',e=>{e.stopPropagation();activeStartFilters.clear();renderDateFilter('start');currentPage=1;renderTable();});
document.getElementById('filterEndBtn').addEventListener('click',e=>{e.stopPropagation();openDateFilter('end','filterEndBtn');});
document.getElementById('filterEndSelectAll').addEventListener('click',e=>{e.stopPropagation();const tree=buildDateTree('end');Object.values(tree).forEach(s=>s.forEach(m=>activeEndFilters.add(m)));renderDateFilter('end');currentPage=1;renderTable();});
document.getElementById('filterEndClearAll').addEventListener('click',e=>{e.stopPropagation();activeEndFilters.clear();renderDateFilter('end');currentPage=1;renderTable();});
function openBudgetFilter() {
  const currently=filterBudgetOpen; closeAllFilters(); if(currently) return;
  filterBudgetOpen=true;
  const dd=document.getElementById('filterBudgetDropdown'); dd.classList.add('open');
  const r=document.getElementById('filterBudgetBtn').getBoundingClientRect();
  dd.style.top=r.bottom+4+'px'; dd.style.left=Math.min(r.left,window.innerWidth-228)+'px';
  const budgets=campaigns.map(c=>calcBudget(c)).filter(b=>b>0);
  if(budgets.length) {
    document.getElementById('budgetMin').placeholder=Math.min(...budgets).toLocaleString('en-US');
    document.getElementById('budgetMax').placeholder=Math.max(...budgets).toLocaleString('en-US');
  }
}
document.getElementById('filterBudgetBtn').addEventListener('click',e=>{e.stopPropagation();openBudgetFilter();});
document.getElementById('filterBudgetClear').addEventListener('click',e=>{e.stopPropagation();document.getElementById('budgetMin').value='';document.getElementById('budgetMax').value='';renderTable();});
function openLeadsFilter() {
  const currently=filterLeadsOpen; closeAllFilters(); if(currently) return;
  filterLeadsOpen=true;
  const dd=document.getElementById('filterLeadsDropdown'); dd.classList.add('open');
  const r=document.getElementById('filterLeadsBtn').getBoundingClientRect();
  dd.style.top=r.bottom+4+'px'; dd.style.left=Math.min(r.left,window.innerWidth-228)+'px';
  const leads=campaigns.map(c=>calcLeads(c)).filter(l=>l>0);
  if(leads.length) {
    document.getElementById('leadsMin').placeholder=Math.min(...leads).toLocaleString('en-US');
    document.getElementById('leadsMax').placeholder=Math.max(...leads).toLocaleString('en-US');
  }
}
document.getElementById('filterLeadsBtn').addEventListener('click',e=>{e.stopPropagation();openLeadsFilter();});
document.getElementById('filterLeadsClear').addEventListener('click',e=>{e.stopPropagation();document.getElementById('leadsMin').value='';document.getElementById('leadsMax').value='';renderTable();});
document.getElementById('filterStatusBtn').addEventListener('click',e=>{e.stopPropagation();const c=filterStatusOpen;closeAllFilters();if(c)return;filterStatusOpen=true;positionDropdown('filterStatusDropdown','filterStatusBtn');renderStatusFilterList();});
document.getElementById('filterStatusSelectAll').addEventListener('click',e=>{e.stopPropagation();STATUS_OPTIONS.forEach(o=>activeStatusFilters.add(o.val));renderStatusFilterList();currentPage=1;renderTable();});
document.getElementById('filterStatusClearAll').addEventListener('click',e=>{e.stopPropagation();activeStatusFilters.clear();renderStatusFilterList();currentPage=1;renderTable();});
document.getElementById('filterApprovalBtn').addEventListener('click',e=>{e.stopPropagation();const c=filterApprovalOpen;closeAllFilters();if(c)return;filterApprovalOpen=true;positionDropdown('filterApprovalDropdown','filterApprovalBtn');renderApprovalFilterList();});
document.getElementById('filterApprovalSelectAll').addEventListener('click',e=>{e.stopPropagation();APPROVAL_OPTIONS.forEach(o=>activeApprovalFilters.add(o.val));renderApprovalFilterList();currentPage=1;renderTable();});
document.getElementById('filterApprovalClearAll').addEventListener('click',e=>{e.stopPropagation();activeApprovalFilters.clear();renderApprovalFilterList();currentPage=1;renderTable();});
document.addEventListener('click',e=>{const ids=['filterNameBtn','filterNameDropdown','filterTypeBtn','filterTypeDropdown','filterStartBtn','filterStartDropdown','filterEndBtn','filterEndDropdown','filterBudgetBtn','filterBudgetDropdown','filterLeadsBtn','filterLeadsDropdown','filterStatusBtn','filterStatusDropdown','filterApprovalBtn','filterApprovalDropdown'];if(!ids.some(id=>document.getElementById(id)?.contains(e.target)))closeAllFilters();});

/* ═══════════════════════════════════════════════════════
   TOAST
═══════════════════════════════════════════════════════ */
function showToast(type,title,msg) {
  const c=document.getElementById('toastContainer'),t=document.createElement('div');
  t.className=`toast ${type}`;
  t.innerHTML=`<div class="toast-icon">${type==='success'?'<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>':'<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'}</div><div class="toast-body"><div class="toast-title">${escHtml(title)}</div><div class="toast-msg">${escHtml(msg)}</div></div><button class="toast-dismiss" onclick="dismissToast(this.parentElement)">✕</button>`;
  c.appendChild(t); setTimeout(()=>dismissToast(t),4500);
}
function dismissToast(el){if(!el||el.classList.contains('toast-out'))return;el.classList.add('toast-out');setTimeout(()=>el.remove(),320);}

/* ═══════════════════════════════════════════════════════
   IMAGE HANDLING
═══════════════════════════════════════════════════════ */
function previewImg(input, previewId) {
  const container=document.getElementById(previewId); if(!container) return;
  container.innerHTML=''; _storedImages[previewId]=[];
  const promises=Array.from(input.files).map(file=>new Promise(resolve=>{
    const reader=new FileReader();
    reader.onload=ev=>{ const img=document.createElement('img'); img.className='img-thumb'; img.src=ev.target.result; container.appendChild(img); _storedImages[previewId].push(ev.target.result); resolve(); };
    reader.onerror=()=>resolve(); reader.readAsDataURL(file);
  }));
  _pendingImageReads[previewId]=Promise.all(promises);
}
function handleCrTvMediaUpload(input,prevId) {
  const container=document.getElementById(prevId); if(!container) return;
  if(!_storedImages[prevId]) _storedImages[prevId]=[];
  const promises=Array.from(input.files).map(file=>new Promise(resolve=>{
    if(file.type.startsWith('image/')){const reader=new FileReader();reader.onload=ev=>{const img=document.createElement('img');img.className='img-thumb';img.src=ev.target.result;container.appendChild(img);_storedImages[prevId].push({type:'image',data:ev.target.result,name:file.name});resolve();};reader.onerror=()=>resolve();reader.readAsDataURL(file);}
    else if(file.type.startsWith('video/')){const span=document.createElement('span');span.style.cssText='display:inline-flex;align-items:center;gap:4px;padding:4px 8px;background:rgba(224,123,32,.1);border:1px solid rgba(224,123,32,.3);border-radius:5px;font-size:.74rem;color:var(--clr-orange-dk)';span.textContent='🎬 '+file.name;container.appendChild(span);_storedImages[prevId].push({type:'video',name:file.name});resolve();}
    else resolve();
  }));
  _pendingImageReads[prevId]=(_pendingImageReads[prevId]?_pendingImageReads[prevId].then(()=>Promise.all(promises)):Promise.all(promises));
}
async function waitForAllImages(){ const pending=Object.values(_pendingImageReads); if(pending.length) await Promise.all(pending); }

// Render already-saved media (URLs from the server) into a preview list so they
// survive an edit and can be removed. Collectors read _storedImages[prevId].
function seedExistingMedia(prevId, items){
  if(!items||!items.length) return;
  const container=document.getElementById(prevId); if(!container) return;
  if(!_storedImages[prevId]) _storedImages[prevId]=[];
  items.forEach(url=>{
    if(!url||typeof url!=='string') return;
    _storedImages[prevId].push(url);
    const wrap=document.createElement('span'); wrap.style.cssText='position:relative;display:inline-block';
    const img=document.createElement('img'); img.className='img-thumb'; img.src=url;
    const btn=document.createElement('button'); btn.type='button'; btn.textContent='×';
    btn.style.cssText='position:absolute;top:-6px;right:-6px;width:18px;height:18px;border-radius:50%;border:none;background:#c0392b;color:#fff;cursor:pointer;font-size:12px;line-height:1';
    btn.onclick=()=>{ const i=_storedImages[prevId].indexOf(url); if(i>=0)_storedImages[prevId].splice(i,1); wrap.remove(); };
    wrap.appendChild(img); wrap.appendChild(btn); container.appendChild(wrap);
  });
}

/* ═══════════════════════════════════════════════════════
   MULTI-ITEM BUILDERS — COUNTERS
═══════════════════════════════════════════════════════ */
let _crEvCtr=0,_crTvCtr=0,_crStCtr=0,_crSmCtr=0,_crExCtr=0,_crOcCtr=0;
let _editCrEvCtr=0,_editCrTvCtr=0,_editCrStCtr=0,_editCrSmCtr=0,_editCrExCtr=0;

/* ── EVENT builder ── */
function addCrEvent(prefill, ctx) {
  const isEdit=ctx==='edit'; const ctr=isEdit?++_editCrEvCtr:++_crEvCtr;
  const n=ctr, id=(isEdit?'edit_':'')+'crev'+n;
  const listId=(isEdit?'edit_':'')+'cr_events_list';
  const el=document.createElement('div');
  el.className='multi-item-card'; el.id=id; el.dataset.cardnum=n;
  el.innerHTML=`
    <div class="multi-item-card-header">
      <span class="multi-item-card-label">🎪 Event #${n}</span>
      <button type="button" class="btn-remove-item" onclick="removeCrItem('${id}','${listId}')" title="Remove this event"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="form-row">
      <div><label class="form-label">Event Name <span style="color:#c0392b">*</span></label><input type="text" class="form-input cr-ev-name" placeholder="e.g. Spring Property Expo" value="${escHtml(prefill?.name||'')}" oninput="refreshSocialEventLinks('${isEdit?'edit_':''}')"></div>
      <div><label class="form-label">Venue / Place</label><input type="text" class="form-input cr-ev-place" placeholder="e.g. Cairo Exhibition Centre" value="${escHtml(prefill?.place||'')}"></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Event Date</label><input type="date" class="form-input cr-ev-date" value="${prefill?.date||''}"></div>
      <div><label class="form-label">Budget <span style="color:#c0392b">*</span></label><input type="number" class="form-input cr-ev-budget" placeholder="e.g. 25,000" min="0" oninput="recalcTotal(ctx='${isEdit?'edit':'create'}')" value="${prefill?.budget||''}"></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Target Attendees</label><input type="number" class="form-input cr-ev-attendees" placeholder="e.g. 500" min="0" value="${prefill?.targetAttendees||''}"></div>
      <div></div>
    </div>
    <div class="form-group"><label class="form-label">Description / Notes <span class="optional">(optional)</span></label><textarea class="form-textarea cr-ev-desc" rows="2" placeholder="Any notes about this event…">${escHtml(prefill?.description||'')}</textarea></div>
    <div class="form-row" style="margin-bottom:10px">
      <div>
        <label class="form-label">Event Logo <span class="optional">(1 image)</span></label>
        <div class="img-upload-zone" onclick="document.getElementById('${id}_logo').click()">
          <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
          <p>Upload event logo</p>
          <input type="file" id="${id}_logo" accept="image/*" style="display:none" onchange="previewImg(this,'${id}_logo_prev')">
        </div>
        <div class="img-preview-list" id="${id}_logo_prev"></div>
      </div>
      <div>
        <label class="form-label">Event Images <span class="optional">(multiple)</span></label>
        <div class="img-upload-zone" onclick="document.getElementById('${id}_imgs').click()">
          <svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
          <p>Upload event photos / banners</p>
          <input type="file" id="${id}_imgs" accept="image/*" multiple style="display:none" onchange="previewImg(this,'${id}_imgs_prev')">
        </div>
        <div class="img-preview-list" id="${id}_imgs_prev"></div>
      </div>
    </div>
    <div class="sub-section-label">⭐ Celebrities</div>
    <div class="cr-ev-celebs-list" id="${id}_celebs"></div>
    <button type="button" class="btn-add-sub" onclick="addCrEvPerson('${id}_celebs','Celebrity',null,'${isEdit?'edit':'create'}')"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Celebrity</button>
    <div class="sub-section-label">🎁 Giveaways <span style="font-size:.7rem;font-weight:400;text-transform:none;color:var(--clr-gray)">(prizes, branded items, etc.)</span></div>
    <div class="cr-ev-giveaways-list" id="${id}_giveaways"></div>
    <button type="button" class="btn-add-sub" onclick="addCrEvPerson('${id}_giveaways','Giveaway',null,'${isEdit?'edit':'create'}')"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Giveaway</button>
    <div class="sub-section-label">🍽️ Catering <span style="font-size:.7rem;font-weight:400;text-transform:none;color:var(--clr-gray)">(food & beverage arrangements)</span></div>
    <div class="cr-ev-catering-list" id="${id}_catering"></div>
    <button type="button" class="btn-add-sub" onclick="addCrEvPerson('${id}_catering','Catering Item',null,'${isEdit?'edit':'create'}')"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Catering Item</button>`;
  document.getElementById(listId).appendChild(el);
  seedExistingMedia(id+'_logo_prev', prefill?.logo);
  seedExistingMedia(id+'_imgs_prev', prefill?.images);
  // Prefill sub-items
  (prefill?.celebrities||[]).forEach(cel=>addCrEvPerson(id+'_celebs','Celebrity',cel,isEdit?'edit':'create'));
  (prefill?.giveaways||[]).forEach(gv=>addCrEvPerson(id+'_giveaways','Giveaway',gv,isEdit?'edit':'create'));
  (prefill?.catering||[]).forEach(ct=>addCrEvPerson(id+'_catering','Catering Item',ct,isEdit?'edit':'create'));
  recalcTotal(isEdit?'edit':'create');
  refreshSocialEventLinks(isEdit?'edit_':'');
}

function addCrEvPerson(listId, label, prefill, ctx) {
  const list=document.getElementById(listId); if(!list) return;
  const div=document.createElement('div'); div.className='person-item';
  div.innerHTML=`
    <div><label class="form-label">${label} Name</label><input type="text" class="form-input cr-person-name" placeholder="e.g. ${label==='Celebrity'?'Ahmed Helmy':'Branded Bags'}" value="${escHtml(prefill?.name||'')}"></div>
    <div><label class="form-label">Budget </label><input type="number" class="form-input cr-person-budget" placeholder="0" min="0" value="${prefill?.budget||''}" oninput="recalcTotal('${ctx||'create'}')"></div>
    <button type="button" class="btn-remove-small" onclick="this.closest('.person-item').remove();recalcTotal('${ctx||'create'}')" title="Remove"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
  list.appendChild(div);
  recalcTotal(ctx||'create');
}

/* ── TV AD builder ── */
function addCrTvAd(prefill, ctx) {
  const isEdit=ctx==='edit'; const ctr=isEdit?++_editCrTvCtr:++_crTvCtr;
  const n=ctr, id=(isEdit?'edit_':'')+'crtv'+n;
  const listId=(isEdit?'edit_':'')+'cr_tv_list';
  const el=document.createElement('div'); el.className='multi-item-card'; el.id=id; el.dataset.cardnum=n;
  el.innerHTML=`
    <div class="multi-item-card-header">
      <span class="multi-item-card-label">📺 TV Ad #${n}</span>
      <button type="button" class="btn-remove-item" onclick="removeCrItem('${id}','${listId}')" title="Remove this TV ad"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="form-row">
      <div><label class="form-label">TV Ad Name <span style="color:#c0392b">*</span></label><input type="text" class="form-input cr-tv-name" placeholder="e.g. Summer TV Spot 30sec" value="${escHtml(prefill?.name||'')}"></div>
      <div><label class="form-label">Total Budget <span style="font-size:.68rem;font-weight:400;text-transform:none;letter-spacing:0;color:var(--clr-gray)">(auto-calculated)</span></label><div class="form-input cr-tv-budget" style="background:rgba(224,123,32,.06);border-color:rgba(224,123,32,.25);color:var(--clr-orange-dk);font-weight:700;cursor:default;display:flex;align-items:center;" data-value="0">—</div></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Start Date</label><input type="date" class="form-input cr-tv-start" value="${prefill?.start||''}"></div>
      <div><label class="form-label">End Date</label><input type="date" class="form-input cr-tv-end" value="${prefill?.end||''}"></div>
    </div>
    <div class="form-group"><label class="form-label">Description / Concept <span class="optional">(optional)</span></label><textarea class="form-textarea cr-tv-desc" rows="2" placeholder="Describe the ad concept, target message, or any notes…">${escHtml(prefill?.description||'')}</textarea></div>
    <div class="sub-section-label">📡 TV Channels</div>
    <div class="cr-tv-channels-list" id="${id}_channels"></div>
    <button type="button" class="btn-add-sub" onclick="addCrTvChannel('${id}_channels')">
      <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Channel
    </button>`;
  document.getElementById(listId).appendChild(el);
  // Add initial channel or prefill channels
  const channelsToPrefill=prefill?.channels||[];
  if (channelsToPrefill.length) channelsToPrefill.forEach(ch=>addCrTvChannel(id+'_channels',ch));
  else addCrTvChannel(id+'_channels');
  // Recalc TV ad total from prefilled channel budgets
  if (channelsToPrefill.length) {
    const dashEl = el.querySelector('.cr-tv-budget');
    if (dashEl) {
      let sum = 0;
      channelsToPrefill.forEach(ch => { sum += Number(ch.budget||0); });
      dashEl.dataset.value = sum;
      dashEl.textContent = sum > 0 ? 'EGP ' + sum.toLocaleString('en-US') : '—';
    }
  }
  recalcTotal(isEdit?'edit':'create');
}

function addCrTvChannel(listId, prefill) {
  const list=document.getElementById(listId); if(!list) return;
  const chN=list.children.length+1, chId=listId+'_ch'+chN;
  const div=document.createElement('div'); div.className='channel-item'; div.id=chId;
  div.innerHTML=`
    <div class="channel-item-header">
      <span class="channel-item-label">📺 Channel #${chN}</span>
      <button type="button" class="btn-remove-small" onclick="(function(btn){const ch=btn.closest('.channel-item');const card=ch&&ch.closest('.multi-item-card');ch&&ch.remove();if(card){const dashEl=card.querySelector('.cr-tv-budget');if(dashEl){let s=0;card.querySelectorAll('.cr-tvc-budget').forEach(i=>s+=Number(i.value||0));dashEl.dataset.value=s;dashEl.textContent=s>0?'EGP '+s.toLocaleString('en-US'):'—';}const list=card.closest('[id$=\\'cr_tv_list\\']');recalcTotal(list&&list.id.startsWith('edit_')?'edit':'create');}})(this)" title="Remove channel"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="form-row">
      <div><label class="form-label">Channel / Network Name</label><input type="text" class="form-input cr-tvc-name" placeholder="e.g. CBC, MBC, ON E, cbc Drama" value="${escHtml(prefill?.channelName||'')}"></div>
      <div><label class="form-label">Budget for this Channel</label><input type="number" class="form-input cr-tvc-budget" placeholder="e.g. 10,000" min="0" value="${escHtml(String(prefill?.budget||''))}" oninput="recalcTvAdTotal(this)"></div>
    </div>
    <div class="form-group">
      <label class="form-label">Images / Video for this channel <span class="optional">(upload the ad creative)</span></label>
      <div class="img-upload-zone" onclick="this.querySelector('input').click()">
        <svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        <p>Click to upload images or video files for this channel</p>
        <input type="file" accept="image/*,video/*" multiple class="cr-tvc-media-input" data-previd="${chId}_prev" style="display:none" onchange="handleCrTvMediaUpload(this,'${chId}_prev')">
      </div>
      <div class="img-preview-list" id="${chId}_prev"></div>
    </div>
    <div class="sub-section-label">🕐 Ad Slots </div>
    <div class="cr-tvc-slots-list" id="${chId}_slots"></div>
    <button type="button" class="btn-add-sub" onclick="addCrTvSlot('${chId}_slots')">
      <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Slot
    </button>`;
  list.appendChild(div);
  seedExistingMedia(chId+'_prev', prefill?.media);
  // Prefill slots
  (prefill?.slots||[]).forEach(sl=>addCrTvSlot(chId+'_slots',sl));
  if (!(prefill?.slots||[]).length) addCrTvSlot(chId+'_slots');
}

function addCrTvSlot(listId, prefill) {
  const list=document.getElementById(listId); if(!list) return;
  const div=document.createElement('div'); div.className='slot-item';
  div.innerHTML=`
    <div><label class="form-label">Number of Times</label><input type="number" class="form-input cr-tvs-count" placeholder="e.g. 5" min="1" value="${prefill?.count||''}"></div>
    <div><label class="form-label">Broadcast Time</label><input type="text" class="form-input cr-tvs-time" placeholder="e.g. 8:00 PM, Prime Time, 7–9 AM" value="${escHtml(prefill?.time||'')}"></div>
    <button type="button" class="btn-remove-small" onclick="this.closest('.slot-item').remove()" title="Remove slot"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
  list.appendChild(div);
}

function recalcTvAdTotal(channelBudgetInput) {
  // Find the parent multi-item-card
  const card = channelBudgetInput.closest('.multi-item-card');
  if (!card) return;
  const dashEl = card.querySelector('.cr-tv-budget');
  if (!dashEl) return;
  let sum = 0;
  card.querySelectorAll('.cr-tvc-budget').forEach(inp => { sum += Number(inp.value || 0); });
  dashEl.dataset.value = sum;
  dashEl.textContent = sum > 0 ? 'EGP ' + sum.toLocaleString('en-US') : '—';
  // Trigger global recalc — detect context from card's parent list id
  const list = card.closest('[id$="cr_tv_list"]');
  const isEdit = list && list.id.startsWith('edit_');
  recalcTotal(isEdit ? 'edit' : 'create');
}

/* ── STREET AD builder ── */
const STREET_AD_TYPES = [
  {val:'Billboard',label:'Billboard',hasLocation:true},
  {val:'Banner',label:'Banner',hasLocation:true},
  {val:'Bus Shelter',label:'Bus Shelter',hasLocation:false},
  {val:'LED Screen',label:'LED Screen',hasLocation:true},
  {val:'Transit / Bus Wrap',label:'Transit / Bus Wrap',hasLocation:false},
  {val:'Wall Mural',label:'Wall Mural',hasLocation:true},
  {val:'Lamp Post',label:'Lamp Post',hasLocation:true},
  {val:'Bridge Banner',label:'Bridge Banner',hasLocation:true},
  {val:'Others',label:'Others',hasLocation:true}
];

function addCrStreetAd(prefill, ctx) {
  const isEdit=ctx==='edit'; const ctr=isEdit?++_editCrStCtr:++_crStCtr;
  const n=ctr, id=(isEdit?'edit_':'')+'crst'+n;
  const listId=(isEdit?'edit_':'')+'cr_street_list';
  const el=document.createElement('div'); el.className='multi-item-card'; el.id=id; el.dataset.cardnum=n;
  el.innerHTML=`
    <div class="multi-item-card-header">
      <span class="multi-item-card-label">🏙️ Street Ad #${n}</span>
      <button type="button" class="btn-remove-item" onclick="removeCrItem('${id}','${listId}')" title="Remove this street ad"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="form-row">
      <div><label class="form-label">Street Ad Name <span style="color:#c0392b">*</span></label><input type="text" class="form-input cr-st-name" placeholder="e.g. Cairo Metro Billboards" value="${escHtml(prefill?.name||'')}"></div>
      <div><label class="form-label">Total Budget <span style="font-size:.68rem;font-weight:400;text-transform:none;letter-spacing:0;color:var(--clr-gray)">(auto-calculated)</span></label><div class="form-input cr-st-budget" style="background:rgba(224,123,32,.06);border-color:rgba(224,123,32,.25);color:var(--clr-orange-dk);font-weight:700;cursor:default;display:flex;align-items:center;" data-value="0">—</div></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Start Date</label><input type="date" class="form-input cr-st-start" value="${prefill?.start||''}"></div>
      <div><label class="form-label">End Date</label><input type="date" class="form-input cr-st-end" value="${prefill?.end||''}"></div>
    </div>
    <div class="form-group"><label class="form-label">Description / Notes <span class="optional">(optional)</span></label><textarea class="form-textarea cr-st-desc" rows="2" placeholder="Any notes about this street ad campaign…">${escHtml(prefill?.description||'')}</textarea></div>
    <div class="sub-section-label">📋 Ad Types </div>
    <div class="ad-types-grid">
      ${STREET_AD_TYPES.map(t=>`<label class="ad-type-item" id="${id}_atype_${t.val.replace(/\W/g,'_')}_wrap">
        <input type="checkbox" class="cr-st-adtype" value="${t.val}" ${(prefill?.adTypes||[]).some(at=>at.type===t.val)?'checked':''} onchange="toggleStreetAdType('${id}','${t.val}',${t.hasLocation},this.checked)" style="accent-color:var(--clr-orange)">
        ${t.label}
      </label>`).join('')}
    </div>
    <div id="${id}_adtype_panels"></div>
    <div class="form-group" style="margin-top:12px">
      <label class="form-label">Ad Design Images <span class="optional">(upload your street ad visuals)</span></label>
      <div class="img-upload-zone" onclick="document.getElementById('${id}_imgs').click()">
        <svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        <p>Upload ad design images</p>
        <input type="file" id="${id}_imgs" accept="image/*" multiple style="display:none" onchange="previewImg(this,'${id}_imgs_prev')">
      </div>
      <div class="img-preview-list" id="${id}_imgs_prev"></div>
    </div>`;
  document.getElementById(listId).appendChild(el);
  seedExistingMedia(id+'_imgs_prev', prefill?.images);
  // Prefill ad types
  (prefill?.adTypes||[]).forEach(at=>{
    const typeInfo=STREET_AD_TYPES.find(t=>t.val===at.type);
    if (typeInfo) { toggleStreetAdType(id,at.type,typeInfo.hasLocation,true,at); }
  });
  // Recalc street ad total from prefilled ad type budgets
  recalcStreetAdTotal(id);
  recalcTotal(isEdit?'edit':'create');
}

function toggleStreetAdType(stId, typeVal, hasLocation, checked, prefill) {
  const panelId=stId+'_adtype_'+typeVal.replace(/\W/g,'_')+'_panel';
  const panels=document.getElementById(stId+'_adtype_panels');
  // Update checkbox visual
  const wrap=document.getElementById(stId+'_atype_'+typeVal.replace(/\W/g,'_')+'_wrap');
  if (wrap) wrap.classList.toggle('checked',checked);
  if (!checked) { document.getElementById(panelId)?.remove(); return; }
  if (document.getElementById(panelId)) return;
  const div=document.createElement('div'); div.className='ad-type-detail'; div.id=panelId; div.dataset.type=typeVal;
  div.innerHTML=`
    <div class="ad-type-detail-header">📍 ${typeVal} — Details</div>
    <div class="form-row">
      <div><label class="form-label">Total Number of ${typeVal}s</label><input type="number" class="form-input cr-at-count" min="1" placeholder="e.g. 10" value="${prefill?.count||''}"></div>
      <div>${hasLocation
        ? `<label class="form-label">Budget for ${typeVal} <span style="font-size:.68rem;font-weight:400;text-transform:none;letter-spacing:0;color:var(--clr-gray)">(auto-calculated)</span></label><div class="form-input cr-at-budget" style="background:rgba(224,123,32,.06);border-color:rgba(224,123,32,.25);color:var(--clr-orange-dk);font-weight:700;cursor:default;display:flex;align-items:center;" data-value="${prefill?.budget||0}">${prefill?.budget?('EGP '+Number(prefill.budget).toLocaleString('en-US')):'—'}</div>`
        : `<label class="form-label">Budget for ${typeVal} </label><input type="number" class="form-input cr-at-budget" min="0" placeholder="e.g. 10,000" value="${prefill?.budget||''}" oninput="recalcStreetAdTotal('${stId}')">`}</div>
    </div>
    ${hasLocation?`
      <div class="sub-section-label">📍 Locations </div>
      <div class="cr-at-locations-list" id="${panelId}_locs"></div>
      <button type="button" class="btn-add-sub" onclick="addCrStLocation('${panelId}_locs')">
        <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Location
      </button>`:''}`;
  panels.appendChild(div);
  (prefill?.locations||[]).forEach(loc=>addCrStLocation(panelId+'_locs',loc));
  if (hasLocation&&!(prefill?.locations?.length)) addCrStLocation(panelId+'_locs');
  if (hasLocation) recalcStreetAdTypeFromPanel(div);
}

function addCrStLocation(listId, prefill) {
  const list=document.getElementById(listId); if(!list) return;
  const div=document.createElement('div'); div.className='location-item';
  div.innerHTML=`
    <div><label class="form-label">Location / Area Name</label><input type="text" class="form-input cr-stloc-name" placeholder="e.g. Tahrir Square, 6th October" value="${escHtml(prefill?.name||'')}"></div>
    <div><label class="form-label">Budget</label><input type="number" class="form-input cr-stloc-budget" placeholder="0" min="0" value="${prefill?.budget||''}" oninput="recalcStreetAdTypeFromPanel(this.closest('.ad-type-detail'))"></div>
    <button type="button" class="btn-remove-small" onclick="(function(b){const p=b.closest('.ad-type-detail');b.closest('.location-item').remove();recalcStreetAdTypeFromPanel(p);})(this)" title="Remove"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
  list.appendChild(div);
  recalcStreetAdTypeFromPanel(div.closest('.ad-type-detail'));
}

// Street ad-type budget = sum of its location budgets (auto-calculated like TV).
function recalcStreetAdTypeFromPanel(panel) {
  if (!panel) return;
  const dash = panel.querySelector('.cr-at-budget');
  if (!dash) return;
  let sum = 0;
  panel.querySelectorAll('.cr-stloc-budget').forEach(i => { sum += Number(i.value || 0); });
  dash.dataset.value = sum;
  if (dash.tagName !== 'INPUT') dash.textContent = sum > 0 ? 'EGP ' + sum.toLocaleString('en-US') : '—';
  const card = panel.closest('.multi-item-card');
  if (card) recalcStreetAdTotal(card.id);
}

function recalcStreetAdTotal(stId) {
  // Sum all ad-type budgets within this street ad card (input value or computed data-value)
  const card = document.getElementById(stId);
  if (!card) return;
  const dashEl = card.querySelector('.cr-st-budget');
  if (!dashEl) return;
  let sum = 0;
  card.querySelectorAll('.cr-at-budget').forEach(el => { sum += Number(el.value || el.dataset.value || 0); });
  dashEl.dataset.value = sum;
  dashEl.textContent = sum > 0 ? 'EGP ' + sum.toLocaleString('en-US') : '—';
  // Also trigger global recalc
  const isEdit = stId.startsWith('edit_');
  recalcTotal(isEdit ? 'edit' : 'create');
}

/* ── SOCIAL MEDIA builder ── */
const SOCIAL_PLATFORMS=['Meta','TikTok','LinkedIn','X (Twitter)','Google Ads (Website)','WhatsApp'];

function addCrSocialAd(prefill, ctx) {
  const isEdit=ctx==='edit'; const ctr=isEdit?++_editCrSmCtr:++_crSmCtr;
  const n=ctr, id=(isEdit?'edit_':'')+'crsm'+n;
  const listId=(isEdit?'edit_':'')+'cr_social_list';
  const el=document.createElement('div'); el.className='multi-item-card'; el.id=id; el.dataset.cardnum=n;
  el.innerHTML=`
    <div class="multi-item-card-header">
      <span class="multi-item-card-label">📱 Social Media Ad #${n}</span>
      <button type="button" class="btn-remove-item" onclick="removeCrItem('${id}','${listId}')" title="Remove"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="form-row">
      <div><label class="form-label">Ad Name <span style="color:#c0392b">*</span></label><input type="text" class="form-input cr-sm-name" placeholder="e.g. Summer Instagram Push" value="${escHtml(prefill?.adName||'')}"></div>
      <div><label class="form-label">Total Budget <span style="font-size:.68rem;font-weight:400;text-transform:none;letter-spacing:0;color:var(--clr-gray)">(auto-calculated)</span></label><div class="form-input cr-sm-budget" style="background:rgba(224,123,32,.06);border-color:rgba(224,123,32,.25);color:var(--clr-orange-dk);font-weight:700;cursor:default;display:flex;align-items:center;" data-value="0">—</div></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Start Date</label><input type="date" class="form-input cr-sm-start" value="${prefill?.start||''}"></div>
      <div><label class="form-label">End Date</label><input type="date" class="form-input cr-sm-end" value="${prefill?.end||''}"></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Target KPI </label><input type="text" class="form-input cr-sm-kpi" placeholder="e.g. 1,000 leads" value="${escHtml(prefill?.targetKpi||'')}"></div>
      <div>
        <label class="form-label">Linked to Event?</label>
        <select class="form-select cr-sm-event-link">
          <option value="">— Not linked to an event —</option>
        </select>
      </div>
    </div>
    <div class="sub-section-label">📲 Platforms & Budgets </div>
    <div class="platforms-grid" style="margin-bottom:10px">
      ${SOCIAL_PLATFORMS.map(p=>{
        const checked=(prefill?.platforms||[]).includes(p);
        const prefillBudget=(prefill?.platformBudgets||[]).find(pb=>pb.platform===p)?.budget||'';
        return `<label class="platform-item ${checked?'checked':''}" id="${id}_plat_${p.replace(/\W/g,'_')}_wrap">
          <input type="checkbox" class="cr-sm-plat" value="${p}" style="accent-color:var(--clr-orange)" ${checked?'checked':''} onchange="toggleSocialPlatform('${id}','${p}',this.checked)">
          ${p}
        </label>`;
      }).join('')}
    </div>
    <div id="${id}_plat_budgets"></div>
    <div class="form-group" style="margin-top:10px">
      <label class="form-label">Creative Images / Videos <span class="optional">(upload ad creatives)</span></label>
      <div class="img-upload-zone" onclick="document.getElementById('${id}_imgs').click()">
        <svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        <p>Upload ad creatives (images, videos)</p>
        <input type="file" id="${id}_imgs" accept="image/*,video/*" multiple style="display:none" onchange="previewImg(this,'${id}_imgs_prev')">
      </div>
      <div class="img-preview-list" id="${id}_imgs_prev"></div>
    </div>`;
  document.getElementById(listId).appendChild(el);
  seedExistingMedia(id+'_imgs_prev', prefill?.images);
  // Populate linked events dropdown from this campaign's events (in-form)
  populateSocialEventLinks(el.querySelector('.cr-sm-event-link'), prefill?.linkedEventId, isEdit?'edit_':'');
  // Prefill platforms
  (prefill?.platforms||[]).forEach(p=>toggleSocialPlatform(id,p,true,(prefill?.platformBudgets||[]).find(pb=>pb.platform===p)?.budget));
  recalcSocialAdCard(id);
  recalcTotal(isEdit?'edit':'create');
}

function currentCampaignEventNames(pfx) {
  const out=[];
  document.querySelectorAll(`#${pfx}cr_events_list .cr-ev-name`).forEach(i=>{ const v=i.value.trim(); if(v) out.push(v); });
  return out;
}
function populateSocialEventLinks(selectEl, selectedName, pfx) {
  if (!selectEl) return;
  const keep = (selectedName!=null && selectedName!=='') ? selectedName : selectEl.value;
  selectEl.innerHTML='<option value="">— Not linked to an event —</option>';
  currentCampaignEventNames(pfx).forEach(name=>{
    const opt=document.createElement('option'); opt.value=name; opt.textContent=name;
    if (name===keep) opt.selected=true;
    selectEl.appendChild(opt);
  });
}
function refreshSocialEventLinks(pfx) {
  document.querySelectorAll(`#${pfx}cr_social_list .cr-sm-event-link`).forEach(sel=>populateSocialEventLinks(sel,null,pfx));
}

// Social ad total budget = sum of its per-platform budgets (auto-calculated like TV).
function recalcSocialAdCard(smId) {
  const card=document.getElementById(smId); if(!card) return;
  const dash=card.querySelector('.cr-sm-budget');
  let sum=0; card.querySelectorAll('.cr-sm-plat-budget').forEach(i=>sum+=Number(i.value||0));
  if (dash) { dash.dataset.value=sum; dash.textContent=sum>0?'EGP '+sum.toLocaleString('en-US'):'—'; }
  recalcTotal(smId.startsWith('edit_')?'edit':'create');
}

function toggleSocialPlatform(smId, platform, checked, prefillBudget) {
  const wrapId=smId+'_plat_'+platform.replace(/\W/g,'_')+'_wrap';
  document.getElementById(wrapId)?.classList.toggle('checked',checked);
  const budgetContainer=document.getElementById(smId+'_plat_budgets');
  const existingRow=budgetContainer?.querySelector(`[data-platform="${platform}"]`);
  if (!checked) { existingRow?.remove(); recalcSocialAdCard(smId); return; }
  if (existingRow) return;
  const row=document.createElement('div'); row.className='platform-budget-row'; row.dataset.platform=platform;
  row.innerHTML=`<span style="flex:1;font-size:.84rem;font-weight:600;color:var(--clr-text)">${platform}</span>
    <div style="width:180px"><label class="form-label" style="margin-bottom:4px">Budget </label><input type="number" class="form-input cr-sm-plat-budget" min="0" placeholder="0" oninput="recalcSocialAdCard('${smId}')" value="${prefillBudget||''}" style="padding:8px 12px"></div>`;
  budgetContainer.appendChild(row);
  recalcSocialAdCard(smId);
}

/* ── EXHIBITION builder ── */
function addCrExhibition(prefill, ctx) {
  const isEdit=ctx==='edit'; const ctr=isEdit?++_editCrExCtr:++_crExCtr;
  const n=ctr, id=(isEdit?'edit_':'')+'crex'+n;
  const listId=(isEdit?'edit_':'')+'cr_exhibition_list';
  const el=document.createElement('div'); el.className='multi-item-card'; el.id=id; el.dataset.cardnum=n;
  el.innerHTML=`
    <div class="multi-item-card-header">
      <span class="multi-item-card-label">🏛️ Exhibition #${n}</span>
      <button type="button" class="btn-remove-item" onclick="removeCrItem('${id}','${listId}')" title="Remove this exhibition"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="form-row">
      <div><label class="form-label">Exhibition Name <span style="color:#c0392b">*</span></label><input type="text" class="form-input cr-ex-name" placeholder="e.g. Cairo Cityscape" value="${escHtml(prefill?.name||'')}"></div>
      <div><label class="form-label">Venue / Place</label><input type="text" class="form-input cr-ex-place" placeholder="e.g. Cairo International Fair, Hall 3" value="${escHtml(prefill?.place||'')}"></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Start Date</label><input type="date" class="form-input cr-ex-start" value="${prefill?.start||''}"></div>
      <div><label class="form-label">End Date</label><input type="date" class="form-input cr-ex-end" value="${prefill?.end||''}"></div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Budget</label><input type="number" class="form-input cr-ex-budget" min="0" placeholder="e.g. 20,000" oninput="recalcTotal('${isEdit?'edit':'create'}')" value="${prefill?.budget||''}"></div>
      <div></div>
    </div>`;
  document.getElementById(listId).appendChild(el);
  recalcTotal(isEdit?'edit':'create');
}

/* ── OTHER COSTS ── */
function toggleOtherCosts() {
  const panel=document.getElementById('otherCostsPanel');
  const wasOpen=panel.classList.contains('open');
  panel.classList.toggle('open');
  // When opening for the first time, auto-add one cost item
  if (!wasOpen && document.getElementById('otherCostsList')?.children.length===0) {
    addOtherCost();
  }
}
function addOtherCost(prefill) {
  const n=++_crOcCtr, id='croc'+n;
  const list=document.getElementById('otherCostsList'); if(!list) return;
  const div=document.createElement('div'); div.className='cost-item'; div.id=id;
  div.innerHTML=`
    <div class="cost-item-header">
      <span class="cost-item-label">Other Cost #${n}</span>
      <button type="button" class="btn-remove-item" onclick="document.getElementById('${id}').remove();recalcTotal()" title="Remove"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="form-row" style="margin-bottom:0">
      <div><label class="form-label">Amount (EGP)</label><input type="number" class="form-input cr-oc-value" min="0" placeholder="e.g. 5,000" oninput="recalcTotal()" value="${prefill?.value||''}"></div>
      <div><label class="form-label">Reason / Description</label><input type="text" class="form-input cr-oc-reason" placeholder="e.g. Agency fees, Printing" value="${escHtml(prefill?.reason||'')}"></div>
    </div>`;
  list.appendChild(div);
  recalcTotal();
}

/* ── HELPERS ── */
function removeCrItem(itemId, listId) { document.getElementById(itemId)?.remove(); recalcTotal(); }
function toggleCampaignType(ct, ctx) {
  const pfx=ctx==='edit'?'edit_':'';
  const cb=document.getElementById(pfx+'ct_'+ct), wrap=document.getElementById(pfx+'ct_'+ct+'_wrap'), panel=document.getElementById(pfx+'details_'+ct);
  if (!cb||!wrap||!panel) return;
  wrap.classList.toggle('checked',cb.checked);
  panel.classList.toggle('visible',cb.checked);
  if(cb.checked) {
    if(ct==='events'&&!document.getElementById(pfx+'cr_events_list').children.length) addCrEvent(null,ctx);
    if(ct==='tv'&&!document.getElementById(pfx+'cr_tv_list').children.length) addCrTvAd(null,ctx);
    if(ct==='street'&&!document.getElementById(pfx+'cr_street_list').children.length) addCrStreetAd(null,ctx);
    if(ct==='social'&&!document.getElementById(pfx+'cr_social_list').children.length) addCrSocialAd(null,ctx);
    if(ct==='exhibition'&&!document.getElementById(pfx+'cr_exhibition_list').children.length) addCrExhibition(null,ctx);
  }
  recalcTotal(ctx);
  const count=['events','tv','street','social','exhibition'].filter(t=>{const el=document.getElementById(pfx+'ct_'+t);return el&&el.checked;}).length;
  const bar=document.getElementById(pfx+'totalBudgetBar'); if(bar) bar.style.display=count>=1?'':'none';
}

function recalcTotal(ctx) {
  const pfx=ctx==='edit'?'edit_':'';
  let total=0; const breakdown={};
  // Events: event budget + celebrities + giveaways + catering
  document.querySelectorAll(`#${pfx}cr_events_list .multi-item-card`).forEach(card=>{
    let evTotal=Number(card.querySelector('.cr-ev-budget')?.value||0);
    card.querySelectorAll('.cr-person-budget').forEach(el=>{ evTotal+=Number(el.value||0); });
    total+=evTotal; breakdown['Events']=(breakdown['Events']||0)+evTotal;
  });
  // TV — read from auto-calculated dash display (data-value)
  document.querySelectorAll(`#${pfx}cr_tv_list .multi-item-card`).forEach(card=>{
    const dashEl=card.querySelector('.cr-tv-budget');
    const val=dashEl ? Number(dashEl.dataset.value||0) : 0;
    total+=val; breakdown['TV Ads']=(breakdown['TV Ads']||0)+val;
  });
  // Street — read from auto-calculated dash display (data-value)
  document.querySelectorAll(`#${pfx}cr_street_list .multi-item-card`).forEach(card=>{
    const dashEl=card.querySelector('.cr-st-budget');
    const val=dashEl ? Number(dashEl.dataset.value||0) : 0;
    total+=val; breakdown['Street Ads']=(breakdown['Street Ads']||0)+val;
  });
  // Social — sum platform budgets
  document.querySelectorAll(`#${pfx}cr_social_list .cr-sm-plat-budget`).forEach(el=>{ total+=Number(el.value||0); breakdown['Social Media']=(breakdown['Social Media']||0)+Number(el.value||0); });
  // Exhibition
  document.querySelectorAll(`#${pfx}cr_exhibition_list .cr-ex-budget`).forEach(el=>{ total+=Number(el.value||0); breakdown['Exhibition']=(breakdown['Exhibition']||0)+Number(el.value||0); });
  // Other costs
  const ocListId=(pfx==='edit_'?'edit_':'')+'otherCostsList';
  document.querySelectorAll(`#${ocListId} .cr-oc-value`).forEach(el=>{ total+=Number(el.value||0); breakdown['Other Costs']=(breakdown['Other Costs']||0)+Number(el.value||0); });
  const valEl=document.getElementById(pfx+'totalBudgetVal');
  if (valEl) valEl.textContent='EGP '+total.toLocaleString('en-US');
  const bdEl=document.getElementById(pfx+'budgetBreakdown');
  if (bdEl) {
    bdEl.innerHTML=Object.entries(breakdown).filter(([,v])=>v>0).map(([k,v])=>`<div class="budget-line"><span class="budget-line-label">${k}</span><span class="budget-line-val"> ${Number(v).toLocaleString('en-US')}</span></div>`).join('')+
    `<div class="budget-line"><span class="budget-line-label" style="color:var(--clr-text);font-weight:700">Grand Total</span><span class="budget-line-val" style="color:var(--clr-orange-dk);font-size:.95rem"> ${total.toLocaleString('en-US')}</span></div>`;
  }
}

/* ═══════════════════════════════════════════════════════
   COLLECT FORM DATA
═══════════════════════════════════════════════════════ */
function collectCrEvents(pfx) {
  return Array.from(document.getElementById(pfx+'cr_events_list').querySelectorAll('.multi-item-card')).map((card,i)=>{
    const n=card.dataset.cardnum||(i+1);
    const id=(pfx?pfx.replace(/_$/,'')+'_':'')+'crev'+n;
    function collectPersonList(listId) {
      return Array.from(document.getElementById(listId)?.querySelectorAll('.person-item')||[]).map(row=>({
        name:row.querySelector('.cr-person-name')?.value.trim()||'',
        budget:Number(row.querySelector('.cr-person-budget')?.value||0)
      }));
    }
    return {
      name:card.querySelector('.cr-ev-name')?.value.trim()||'',
      place:card.querySelector('.cr-ev-place')?.value.trim()||'',
      date:card.querySelector('.cr-ev-date')?.value||'',
      budget:Number(card.querySelector('.cr-ev-budget')?.value||0),
      targetAttendees:Number(card.querySelector('.cr-ev-attendees')?.value||0),
      description:card.querySelector('.cr-ev-desc')?.value.trim()||'',
      logo:_storedImages[id+'_logo_prev']||[],
      images:_storedImages[id+'_imgs_prev']||[],
      celebrities:collectPersonList(id+'_celebs'),
      giveaways:collectPersonList(id+'_giveaways'),
      catering:collectPersonList(id+'_catering')
    };
  });
}

function collectCrTvAds(pfx) {
  return Array.from(document.getElementById(pfx+'cr_tv_list').querySelectorAll('.multi-item-card')).map((card,i)=>{
    const n=card.dataset.cardnum||(i+1);
    const channelListId=((pfx?pfx.replace(/_$/,'')+'_':'')+'crtv'+n)+'_channels';
    const channels=Array.from(document.getElementById(channelListId)?.querySelectorAll('.channel-item')||[]).map((ch,ci)=>{
      const slotListId=ch.id+'_slots';
      const slots=Array.from(document.getElementById(slotListId)?.querySelectorAll('.slot-item')||[]).map(sl=>({
        count:Number(sl.querySelector('.cr-tvs-count')?.value||0),
        time:sl.querySelector('.cr-tvs-time')?.value.trim()||''
      }));
      const prevId=ch.id+'_prev';
      return {channelName:ch.querySelector('.cr-tvc-name')?.value.trim()||'',budget:Number(ch.querySelector('.cr-tvc-budget')?.value||0),media:_storedImages[prevId]||[],slots};
    });
    return {name:card.querySelector('.cr-tv-name')?.value.trim()||'',description:card.querySelector('.cr-tv-desc')?.value.trim()||'',start:card.querySelector('.cr-tv-start')?.value||'',end:card.querySelector('.cr-tv-end')?.value||'',budget:Number(card.querySelector('.cr-tv-budget')?.dataset.value||0),channels,channel:channels.map(c=>c.channelName).filter(Boolean).join(', ')};
  });
}

function collectCrStreetAds(pfx) {
  return Array.from(document.getElementById(pfx+'cr_street_list').querySelectorAll('.multi-item-card')).map((card,i)=>{
    const n=card.dataset.cardnum||(i+1);
    const stId=(pfx?pfx.replace(/_$/,'')+'_':'')+'crst'+n;
    const adTypes=Array.from(card.querySelectorAll('#'+stId+'_adtype_panels .ad-type-detail')).map(panel=>{
      const type=panel.dataset.type;
      const locList=panel.querySelectorAll('.location-item');
      const locations=Array.from(locList).map(loc=>({name:loc.querySelector('.cr-stloc-name')?.value.trim()||'',budget:Number(loc.querySelector('.cr-stloc-budget')?.value||0)}));
      const budgetEl=panel.querySelector('.cr-at-budget');
      return {type,count:Number(panel.querySelector('.cr-at-count')?.value||0),budget:Number(budgetEl?.value||budgetEl?.dataset.value||0),locations};
    });
    return {name:card.querySelector('.cr-st-name')?.value.trim()||'',description:card.querySelector('.cr-st-desc')?.value.trim()||'',start:card.querySelector('.cr-st-start')?.value||'',end:card.querySelector('.cr-st-end')?.value||'',budget:Number(card.querySelector('.cr-st-budget')?.dataset.value||0),adTypes,images:_storedImages[stId+'_imgs_prev']||[]};
  });
}

function collectCrSocialAds(pfx) {
  return Array.from(document.getElementById(pfx+'cr_social_list').querySelectorAll('.multi-item-card')).map((card,i)=>{
    const n=card.dataset.cardnum||(i+1);
    const smId=(pfx?pfx.replace(/_$/,'')+'_':'')+'crsm'+n;
    const platforms=Array.from(card.querySelectorAll('.cr-sm-plat:checked')).map(c=>c.value);
    const platformBudgets=Array.from(card.querySelectorAll('#'+smId+'_plat_budgets .platform-budget-row')).map(row=>({platform:row.dataset.platform,budget:Number(row.querySelector('.cr-sm-plat-budget')?.value||0)}));
    const totalBudget=platformBudgets.reduce((s,pb)=>s+pb.budget,0);
    return {adName:card.querySelector('.cr-sm-name')?.value.trim()||'',platforms,platformBudgets,budget:totalBudget,start:card.querySelector('.cr-sm-start')?.value||'',end:card.querySelector('.cr-sm-end')?.value||'',targetKpi:card.querySelector('.cr-sm-kpi')?.value.trim()||'',linkedEventId:card.querySelector('.cr-sm-event-link')?.value||'',images:_storedImages[smId+'_imgs_prev']||[]};
  });
}

function collectCrExhibitions(pfx) {
  return Array.from(document.getElementById(pfx+'cr_exhibition_list').querySelectorAll('.multi-item-card')).map(card=>({
    name:card.querySelector('.cr-ex-name')?.value.trim()||'',
    place:card.querySelector('.cr-ex-place')?.value.trim()||'',
    start:card.querySelector('.cr-ex-start')?.value||'',
    end:card.querySelector('.cr-ex-end')?.value||'',
    budget:Number(card.querySelector('.cr-ex-budget')?.value||0)
  }));
}

function collectOtherCosts() {
  return Array.from(document.getElementById('otherCostsList')?.querySelectorAll('.cost-item')||[]).map(item=>({
    value:Number(item.querySelector('.cr-oc-value')?.value||0),
    reason:item.querySelector('.cr-oc-reason')?.value.trim()||''
  }));
}

/* ═══════════════════════════════════════════════════════
   CREATE
═══════════════════════════════════════════════════════ */
function resetCreateForm() {
  ['c_name','c_description','c_startDate','c_endDate'].forEach(id=>{ const el=document.getElementById(id); if(el) el.value=''; });
  // Reset project dropdown
  const projDisp=document.getElementById('c_proj_display'); if(projDisp) projDisp.value='';
  const projVal=document.getElementById('c_proj_val'); if(projVal) projVal.value='';
  const projDD=document.getElementById('c_proj_dd'); if(projDD) projDD.classList.remove('open');
  initProjDD('c_proj','');
  ['events','tv','street','social','exhibition'].forEach(ct=>{ const cb=document.getElementById('ct_'+ct),wrap=document.getElementById('ct_'+ct+'_wrap'),panel=document.getElementById('details_'+ct); if(cb)cb.checked=false; if(wrap)wrap.classList.remove('checked'); if(panel)panel.classList.remove('visible'); });
  ['cr_events_list','cr_tv_list','cr_street_list','cr_social_list','cr_exhibition_list'].forEach(id=>{ const el=document.getElementById(id); if(el) el.innerHTML=''; });
  const ocList=document.getElementById('otherCostsList'); if(ocList) ocList.innerHTML='';
  _crEvCtr=0; _crTvCtr=0; _crStCtr=0; _crSmCtr=0; _crExCtr=0; _crOcCtr=0;
  Object.keys(_storedImages).forEach(k=>delete _storedImages[k]);
  Object.keys(_pendingImageReads).forEach(k=>delete _pendingImageReads[k]);
  document.getElementById('totalBudgetBar').style.display='none';
  const ocp=document.getElementById('otherCostsPanel'); if(ocp) ocp.classList.remove('open');
  document.getElementById('totalBudgetVal').textContent=' 0';
  const bd=document.getElementById('budgetBreakdown'); if(bd) bd.innerHTML='';
}

function openCreate() { resetCreateForm(); document.getElementById('createModal').classList.add('open'); document.body.style.overflow='hidden'; }
function closeCreate() { document.getElementById('createModal').classList.remove('open'); document.body.style.overflow=''; }
document.getElementById('btnCreate')?.addEventListener('click', openCreate);
document.getElementById('createModalClose').addEventListener('click', closeCreate);
document.getElementById('createCancel').addEventListener('click', closeCreate);
document.getElementById('createModal').addEventListener('click', e=>{ if(e.target===e.currentTarget) closeCreate(); });

document.getElementById('createSave').addEventListener('click', async()=>{
  const name=document.getElementById('c_name').value.trim();
  if (!name) { highlight('c_name'); return; }
  const ctypes=['events','tv','street','social','exhibition'].filter(t=>document.getElementById('ct_'+t)?.checked);
  if (!ctypes.length) { showToast('error','Campaign Type Required','Select at least one campaign type.'); return; }
  const saveBtn=document.getElementById('createSave');
  saveBtn.disabled=true; saveBtn.textContent='Saving…';
  try { await waitForAllImages(); } catch(e) {}
  saveBtn.disabled=false; saveBtn.textContent='💾 Save Campaign';
  // New campaigns start with 0 leads — updated later via edit
  const _typeLeads={};
  ctypes.forEach(t=>{ _typeLeads[t]=0; });
  const c={id:nextId++,name,description:document.getElementById('c_description').value.trim(),startDate:document.getElementById('c_startDate').value,endDate:document.getElementById('c_endDate').value,campaignTypes:ctypes,leads:0,typeLeads:_typeLeads,approval:'pending',approvalReason:'',interestedProject:document.getElementById('c_proj_val')?.value||'',otherCosts:collectOtherCosts()};
  if(ctypes.includes('events')){ const evs=collectCrEvents(''); if(evs.length){c.events=evs[0];c.eventsMulti=evs;} }
  if(ctypes.includes('tv')){ const tvs=collectCrTvAds(''); if(tvs.length){c.tv=tvs[0];c.tvMulti=tvs;} }
  if(ctypes.includes('street')){ const sts=collectCrStreetAds(''); if(sts.length){c.street=sts[0];c.streetMulti=sts;} }
  if(ctypes.includes('social')){ const sms=collectCrSocialAds(''); if(sms.length){c.social=sms[0];c.socialMulti=sms;} }
  if(ctypes.includes('exhibition')){ const exs=collectCrExhibitions(''); if(exs.length){c.exhibitionMulti=exs;} }
  try {
    await apiSend(_cfg().createUrl, 'POST', c);
    await fetchCampaigns();
    closeCreate(); renderTable(); renderNameFilterList();
    showToast('success','Campaign Created',`"${name}" has been added successfully.`);
  } catch(e) {
    showToast('error','Could not save', e.message || 'Server error.');
  }
});

/* ═══════════════════════════════════════════════════════
   EDIT
═══════════════════════════════════════════════════════ */
function openEdit(index) {
  const c=campaigns[index]; editingIndex=index;
  _editCrEvCtr=0; _editCrTvCtr=0; _editCrStCtr=0; _editCrSmCtr=0; _editCrExCtr=0;
  document.getElementById('editModalSub').textContent='Editing: '+c.name;
  const body=document.getElementById('editModalBody');
  body.innerHTML=`
    <div class="form-group"><label class="form-label">Campaign Name <span style="color:#c0392b">*</span></label><input type="text" class="form-input" id="edit_c_name" value="${escHtml(c.name)}"></div>
    <div class="form-group"><label class="form-label">Description</label><textarea class="form-textarea" id="edit_c_desc" rows="3">${escHtml(c.description||'')}</textarea></div>
    <div class="form-group" style="display:none">
      <label class="form-label">Interested Project <span class="optional">(optional)</span></label>
      <div class="proj-select-wrap" id="edit_proj_wrap">
        <input type="text" class="proj-search-input" id="edit_proj_display" placeholder="— Select a project —" readonly onclick="toggleProjDD('edit_proj')" autocomplete="off">
        <input type="hidden" id="edit_proj_val" value="${escHtml(c.interestedProject||'')}">
        <div class="proj-dropdown" id="edit_proj_dd">
          <div class="proj-dd-search"><input type="text" placeholder="Search projects…" oninput="filterProjDD(this,'edit_proj')" id="edit_proj_search"></div>
          <div class="proj-dd-list" id="edit_proj_list"></div>
        </div>
      </div>
    </div>
    <div class="form-row">
      <div><label class="form-label">Start Date</label><input type="date" class="form-input" id="edit_c_start" value="${c.startDate||''}"></div>
      <div><label class="form-label">End Date</label><input type="date" class="form-input" id="edit_c_end" value="${c.endDate||''}"></div>
    </div>
    <div class="form-group">
      <label class="form-label">Leads by Campaign Type</label>
      <div style="background:#faf9f7;border:1px solid var(--clr-border);border-radius:8px;padding:14px 16px;">
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;" id="edit_type_leads_grid">
          ${(c.campaignTypes||[]).map(t=>{
            const icons={events:'🎪',tv:'📺',street:'🏙️',social:'📱',exhibition:'🏛️'};
            const names={events:'Events',tv:'TV Ads',street:'Street Ads',social:'Social Media',exhibition:'Exhibition'};
            const val=Number((c.typeLeads||{})[t]||0);
            return `<div><label class="form-label" style="font-size:.68rem">${icons[t]||''} ${names[t]||t}</label><input type="number" class="form-input edit-type-lead-input" data-type="${t}" min="0" placeholder="0" value="${val}" oninput="recalcEditLeadsTotal()"></div>`;
          }).join('')}
        </div>
        <div style="margin-top:10px;padding:8px 12px;background:rgba(39,174,96,.07);border:1px solid rgba(39,174,96,.2);border-radius:6px;display:flex;align-items:center;justify-content:space-between">
          <span style="font-size:.72rem;font-weight:600;color:#1e8449;text-transform:uppercase;letter-spacing:.08em">Total Leads</span>
          <span style="font-size:1rem;font-weight:700;color:#1e8449" id="edit_leads_total">${calcLeads(c)}</span>
        </div>
      </div>
    </div>
    <hr class="section-divider">
    <p class="section-heading">Campaign Types</p>
    <div class="campaign-types-grid">
      ${['events','tv','street','social','exhibition'].map(ct=>{
        const labels={events:'🎪 Events',tv:'📺 TV Ads',street:'🏙️ Street Ads',social:'📱 Social Media',exhibition:'🏛️ Exhibition'};
        const checked=(c.campaignTypes||[]).includes(ct);
        return `<label class="ctype-item ${checked?'checked':''}" id="edit_ct_${ct}_wrap"><input type="checkbox" id="edit_ct_${ct}" ${checked?'checked':''} onchange="toggleCampaignType('${ct}','edit')"><span>${labels[ct]}</span></label>`;
      }).join('')}
    </div>
    <div class="ctype-details ${(c.campaignTypes||[]).includes('events')?'visible':''}" id="edit_details_events">
      <div class="ctype-details-title">🎪 Events</div>
      <div id="edit_cr_events_list"></div>
      <button type="button" class="btn-add-item" onclick="addCrEvent(null,'edit')"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Another Event</button>
    </div>
    <div class="ctype-details ${(c.campaignTypes||[]).includes('tv')?'visible':''}" id="edit_details_tv">
      <div class="ctype-details-title">📺 TV Ads</div>
      <div id="edit_cr_tv_list"></div>
      <button type="button" class="btn-add-item" onclick="addCrTvAd(null,'edit')"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Another TV Ad</button>
    </div>
    <div class="ctype-details ${(c.campaignTypes||[]).includes('street')?'visible':''}" id="edit_details_street">
      <div class="ctype-details-title">🏙️ Street Ads</div>
      <div id="edit_cr_street_list"></div>
      <button type="button" class="btn-add-item" onclick="addCrStreetAd(null,'edit')"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Another Street Ad</button>
    </div>
    <div class="ctype-details ${(c.campaignTypes||[]).includes('social')?'visible':''}" id="edit_details_social">
      <div class="ctype-details-title">📱 Social Media Ads</div>
      <div id="edit_cr_social_list"></div>
      <button type="button" class="btn-add-item" onclick="addCrSocialAd(null,'edit')"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Another Social Ad</button>
    </div>
    <div class="ctype-details ${(c.campaignTypes||[]).includes('exhibition')?'visible':''}" id="edit_details_exhibition">
      <div class="ctype-details-title">🏛️ Exhibitions</div>
      <div id="edit_cr_exhibition_list"></div>
      <button type="button" class="btn-add-item" onclick="addCrExhibition(null,'edit')"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Another Exhibition</button>
    </div>
    <div id="edit_totalBudgetBar" style="display:${(c.campaignTypes||[]).length?'':'none'}" class="budget-total-section">
      <hr class="section-divider">
      <p class="section-heading">💰 Total Campaign Budget</p>
      <div class="budget-total-bar"><div class="budget-total-label">Grand Total</div><div class="budget-total-value" id="edit_totalBudgetVal"> 0</div></div>
      <div class="budget-breakdown" id="edit_budgetBreakdown"></div>
      <div class="other-costs-section">
        <button type="button" class="other-costs-toggle" onclick="toggleEditOtherCosts()">
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add Other Costs
        </button>
        <div class="other-costs-panel" id="edit_otherCostsPanel">
          <div id="edit_otherCostsList"></div>
          <button type="button" class="btn-add-sub" onclick="addEditOtherCost()"><svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Add New Cost Item</button>
        </div>
      </div>
    </div>`;
  // Prefill existing data
  (c.eventsMulti||[c.events]).filter(Boolean).forEach(ev=>addCrEvent(ev,'edit'));
  (c.tvMulti||[c.tv]).filter(Boolean).forEach(tv=>addCrTvAd(tv,'edit'));
  (c.streetMulti||[c.street]).filter(Boolean).forEach(st=>addCrStreetAd(st,'edit'));
  (c.socialMulti||[c.social]).filter(Boolean).forEach(sm=>addCrSocialAd(sm,'edit'));
  (c.exhibitionMulti||[]).forEach(ex=>addCrExhibition(ex,'edit'));
  // Init project dropdown
  setTimeout(()=>initProjDD('edit_proj', c.interestedProject||''), 0);
  // Prefill other costs
  _editOcCtr=0;
  (c.otherCosts||[]).forEach(oc=>addEditOtherCost(oc));
  if ((c.otherCosts||[]).length) document.getElementById('edit_otherCostsPanel')?.classList.add('open');
  setTimeout(()=>recalcTotal('edit'),100);
  document.getElementById('editModal').classList.add('open');
  document.body.style.overflow='hidden';
}

function recalcEditLeadsTotal() {
  const inputs = document.querySelectorAll('.edit-type-lead-input');
  let total = 0;
  inputs.forEach(inp => { total += Number(inp.value||0); });
  const el = document.getElementById('edit_leads_total');
  if (el) el.textContent = total;
}

function toggleEditOtherCosts() {
  const panel=document.getElementById('edit_otherCostsPanel');
  const wasOpen=panel.classList.contains('open');
  panel.classList.toggle('open');
  if (!wasOpen && document.getElementById('edit_otherCostsList')?.children.length===0) {
    addEditOtherCost();
  }
}

let _editOcCtr=0;
function addEditOtherCost(prefill) {
  const n=++_editOcCtr, id='editoc'+n;
  const list=document.getElementById('edit_otherCostsList'); if(!list) return;
  const div=document.createElement('div'); div.className='cost-item'; div.id=id;
  div.innerHTML=`<div class="cost-item-header"><span class="cost-item-label">Other Cost #${n}</span><button type="button" class="btn-remove-item" onclick="document.getElementById('${id}').remove();recalcTotal('edit')" title="Remove"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button></div>
    <div class="form-row" style="margin-bottom:0"><div><label class="form-label">Amount (EGP)</label><input type="number" class="form-input cr-oc-value" min="0" placeholder="e.g. 5,000" oninput="recalcTotal('edit')" value="${prefill?.value||''}"></div><div><label class="form-label">Reason</label><input type="text" class="form-input cr-oc-reason" placeholder="e.g. Agency fees" value="${escHtml(prefill?.reason||'')}"></div></div>`;
  list.appendChild(div);
  recalcTotal('edit');
}

function closeEdit() { document.getElementById('editModal').classList.remove('open'); document.body.style.overflow=''; }
document.getElementById('editModalClose').addEventListener('click', closeEdit);
document.getElementById('editCancel').addEventListener('click', closeEdit);
document.getElementById('editModal').addEventListener('click', e=>{ if(e.target===e.currentTarget) closeEdit(); });

document.getElementById('editSave').addEventListener('click', async()=>{
  if (editingIndex===null) return;
  const name=document.getElementById('edit_c_name').value.trim();
  if (!name) { highlight('edit_c_name'); return; }
  const saveBtn=document.getElementById('editSave');
  saveBtn.disabled=true; saveBtn.textContent='Saving…';
  try { await waitForAllImages(); } catch(e) {}
  saveBtn.disabled=false; saveBtn.textContent='Save Changes';
  const c=campaigns[editingIndex];
  c.name=name; c.description=document.getElementById('edit_c_desc').value.trim();
  c.startDate=document.getElementById('edit_c_start').value; c.endDate=document.getElementById('edit_c_end').value;
  c.interestedProject=document.getElementById('edit_proj_val')?.value||'';
  // Collect per-type leads from breakdown inputs
  const typeLeadInputs = document.querySelectorAll('.edit-type-lead-input');
  if (typeLeadInputs.length) {
    const tl = {};
    typeLeadInputs.forEach(inp => { tl[inp.dataset.type] = Number(inp.value||0); });
    c.typeLeads = tl;
    c.leads = 0; // total is now derived from typeLeads
  }
  const ctypes=['events','tv','street','social','exhibition'].filter(t=>document.getElementById('edit_ct_'+t)?.checked);
  c.campaignTypes=ctypes;
  if(ctypes.includes('events')){ const evs=collectCrEvents('edit_'); if(evs.length){c.events=evs[0];c.eventsMulti=evs;} }
  if(ctypes.includes('tv')){ const tvs=collectCrTvAds('edit_'); if(tvs.length){c.tv=tvs[0];c.tvMulti=tvs;} }
  if(ctypes.includes('street')){ const sts=collectCrStreetAds('edit_'); if(sts.length){c.street=sts[0];c.streetMulti=sts;} }
  if(ctypes.includes('social')){ const sms=collectCrSocialAds('edit_'); if(sms.length){c.social=sms[0];c.socialMulti=sms;} }
  if(ctypes.includes('exhibition')){ const exs=collectCrExhibitions('edit_'); if(exs.length){c.exhibitionMulti=exs;} }
  const editOcItems=Array.from(document.getElementById('edit_otherCostsList')?.querySelectorAll('.cost-item')||[]).map(item=>({value:Number(item.querySelector('.cr-oc-value')?.value||0),reason:item.querySelector('.cr-oc-reason')?.value.trim()||''}));
  c.otherCosts=editOcItems;
  try {
    await apiSend(_campUrl(_cfg().updateTmpl, c.id), 'POST', c);
    await fetchCampaigns(); closeEdit(); renderTable(); renderNameFilterList();
    showToast('success','Campaign Updated',`"${name}" has been updated.`);
  } catch(e) {
    showToast('error','Could not save', e.message || 'Server error.');
  }
});

/* ═══════════════════════════════════════════════════════
   VIEW
═══════════════════════════════════════════════════════ */
// Global registry for view-modal images — avoids embedding base64 in onclick attributes
const _viewImgRegistry = [];
function viewImgBlock(label, images) {
  if(!images||!images.length) return '';
  const imgs=images.filter(i=>{const s=typeof i==='string'?i:(i.data||'');return !!s&&(s.startsWith('data:image')||!s.startsWith('data:'));});
  if(!imgs.length) return '';
  return `<div style="margin-top:10px"><div class="view-img-section-label">${label}</div><div class="view-img-grid">${imgs.map(i=>{
    const src=typeof i==='string'?i:(i.data||i);
    const idx=_viewImgRegistry.push(src)-1;
    return `<img class="view-img-thumb" src="${src}" alt="" onclick="_openViewImg(${idx})" style="cursor:zoom-in">`;
  }).join('')}</div></div>`;
}
function _openViewImg(idx) {
  const src=_viewImgRegistry[idx];
  if(src) openLightbox(src);
}
function viewPersonRows(items,icon,label) {
  const f=(items||[]).filter(x=>x.name);
  if(!f.length) return '';
  return `<div style="margin-top:10px;padding:10px 12px;background:#fff;border:1px solid var(--clr-border);border-radius:7px">
    <div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--clr-text-sub);margin-bottom:7px">${icon} ${label}</div>
    ${f.map(x=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px dashed var(--clr-border);font-size:.84rem"><span style="font-weight:500">${escHtml(x.name)}</span><span style="font-weight:700;color:var(--clr-orange-dk)"> ${fmtBudget(x.budget)}</span></div>`).join('')}
    <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;font-size:.8rem;font-weight:700;color:var(--clr-text-sub)"><span>Subtotal</span><span style="color:var(--clr-orange-dk)"> ${fmtBudget(f.reduce((s,x)=>s+Number(x.budget||0),0))}</span></div>
  </div>`;
}
function openView(index) {
  _viewImgRegistry.length=0;
  const c=campaigns[index];
  document.getElementById('viewTitle').textContent=c.name;
  document.getElementById('viewSub').textContent=getTypeLabel(c)+' · '+fmtDate(c.startDate)+' – '+fmtDate(c.endDate);
  const budget=calcBudget(c), leads=calcLeads(c), status=getStatus(c);
  const statusColors={active:'#27ae60',ended:'#7a7570',upcoming:'#2980b9'};
  const statusLabels={active:'🟢 Active',ended:'⚫ Ended',upcoming:'🔵 Upcoming'};
  const apprColors={approved:'rgba(39,174,96,.1)',pending:'rgba(243,156,18,.1)','not-approved':'rgba(192,57,43,.1)',semi:'rgba(41,128,185,.1)'};
  const apprTextColors={approved:'#1a6b35',pending:'#8a5c00','not-approved':'#922b21',semi:'#1a5276'};
  const appr=c.approval||'pending';
  const typeBreakdown = getTypeLeadsBreakdown(c);
  const typeIcons={events:'🎪',tv:'📺',street:'🏙️',social:'📱',exhibition:'🏛️'};
  const typeNames={events:'Events',tv:'TV Ads',street:'Street Ads',social:'Social Media',exhibition:'Exhibition'};

  let html=`
  <!-- Hero bar -->
  <div style="display:flex;align-items:center;gap:16px;padding:16px 20px;background:linear-gradient(135deg,rgba(224,123,32,.09),rgba(224,123,32,.03));border-bottom:1px solid var(--clr-border);margin:-22px -24px 18px;flex-wrap:wrap;">
    <div style="width:46px;height:46px;border-radius:11px;background:rgba(224,123,32,.15);display:flex;align-items:center;justify-content:center;flex-shrink:0">
      <svg viewBox="0 0 24 24" style="width:22px;height:22px;stroke:var(--clr-orange);fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
    </div>
    <div style="flex:1;min-width:0;font-size:.78rem;color:var(--clr-text-sub)">Full breakdown of all campaign costs and activity below</div>
    <div style="text-align:right;flex-shrink:0">
      <div style="font-size:1.3rem;font-weight:700;color:var(--clr-orange-dk)"> ${budget.toLocaleString('en-US')}</div>
      <div style="font-size:.65rem;color:var(--clr-text-sub);text-transform:uppercase;letter-spacing:.08em">Grand Total Budget</div>
      <div style="font-size:.62rem;color:var(--clr-text-sub);margin-top:2px">incl. celebrities, catering, giveaways &amp; other costs</div>
    </div>
  </div>

  <!-- KPI stats row -->
  <div style="display:grid;grid-template-columns:repeat(${c.interestedProject?4:3},1fr);gap:10px;margin-bottom:16px">
    <div style="background:#fff;border:1px solid var(--clr-border);border-radius:9px;padding:12px 14px;text-align:center">
      <div style="font-size:1.1rem;font-weight:700;color:${statusColors[status]}">${statusLabels[status]}</div>
      <div style="font-size:.65rem;color:var(--clr-text-sub);text-transform:uppercase;letter-spacing:.08em;margin-top:3px">Campaign Status</div>
    </div>
    <div style="background:#fff;border:1px solid var(--clr-border);border-radius:9px;padding:12px 14px;text-align:center">
      <div style="font-size:1.1rem;font-weight:700;color:#27ae60">${leads.toLocaleString('en-US')}</div>
      <div style="font-size:.65rem;color:var(--clr-text-sub);text-transform:uppercase;letter-spacing:.08em;margin-top:3px">Total Leads</div>
      ${Object.keys(typeBreakdown).length > 1 ? `<div style="margin-top:6px;display:flex;flex-wrap:wrap;justify-content:center;gap:4px">${Object.entries(typeBreakdown).map(([t,n])=>`<span style="font-size:.62rem;background:rgba(39,174,96,.1);color:#1e8449;padding:2px 6px;border-radius:10px;font-weight:600">${typeIcons[t]||''} ${n}</span>`).join('')}</div>` : ''}
    </div>
    <div style="background:${apprColors[appr]||'#f5f3f0'};border:1px solid var(--clr-border);border-radius:9px;padding:12px 14px;text-align:center">
      <div style="font-size:.9rem;font-weight:700;color:${apprTextColors[appr]||'#555'}">${APPROVAL_LABELS[appr]||'Pending'}</div>
      <div style="font-size:.65rem;color:var(--clr-text-sub);text-transform:uppercase;letter-spacing:.08em;margin-top:3px">Finance Approval</div>
    </div>
    ${c.interestedProject?`<div style="background:rgba(41,128,185,.06);border:1px solid rgba(41,128,185,.18);border-radius:9px;padding:12px 14px;text-align:center">
      <div style="font-size:.85rem;font-weight:700;color:#1a5276">${escHtml(c.interestedProject)}</div>
      <div style="font-size:.65rem;color:var(--clr-text-sub);text-transform:uppercase;letter-spacing:.08em;margin-top:3px">Interested Project</div>
    </div>`:''}
  </div>`;

  if (c.approvalReason) html+=`<div style="margin-bottom:14px;padding:10px 14px;background:rgba(224,123,32,.06);border:1px solid rgba(224,123,32,.2);border-radius:7px;font-size:.83rem;color:var(--clr-text-sub);line-height:1.5"><span style="font-weight:700;color:var(--clr-text)">💬 Approval Note:</span> ${escHtml(c.approvalReason)}</div>`;
  if (c.description) html+=`<div style="margin-bottom:16px;padding:12px 14px;background:#faf9f7;border:1px solid var(--clr-border);border-radius:8px;font-size:.86rem;color:var(--clr-text-sub);line-height:1.65"><span style="font-weight:700;color:var(--clr-text);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;display:block;margin-bottom:5px">📝 Description</span>${escHtml(c.description)}</div>`;

  // Events
  const allEvs=c.eventsMulti||(c.events?[c.events]:[]);
  allEvs.forEach((ev,ei)=>{
    const evTotal=calcEvSubBudget(ev);
    html+=`<div class="view-sub-card">
      <div class="view-sub-card-title">🎪 Event #${ei+1}: ${escHtml(ev.name||'Unnamed Event')}</div>
      <div class="view-kv-grid">
        <div><div class="view-kv-label">📍 Venue</div><div class="view-kv-val">${escHtml(ev.place||'—')}</div></div>
        <div><div class="view-kv-label">📅 Date</div><div class="view-kv-val date-val">${fmtDate(ev.date)}</div></div>
        <div><div class="view-kv-label">💰 Event Budget</div><div class="view-kv-val accent"> ${fmtBudget(ev.budget)}</div></div>
        <div><div class="view-kv-label">👥 Target Attendees</div><div class="view-kv-val">${ev.targetAttendees||'—'}</div></div>
        ${evTotal!==Number(ev.budget||0)?`<div style="grid-column:1/-1"><div class="view-kv-label">🏷️ Total Event Cost (incl. extras)</div><div class="view-kv-val" style="color:var(--clr-orange-dk);font-weight:700;font-size:1rem"> ${fmtBudget(evTotal)}</div></div>`:''}
      </div>
      ${ev.description?`<div style="margin-top:8px;padding:8px 10px;background:#fff;border-radius:6px;font-size:.83rem;color:var(--clr-text-sub);line-height:1.5">${escHtml(ev.description)}</div>`:''}
      ${viewPersonRows(ev.celebrities,'⭐','Celebrities')}
      ${viewPersonRows(ev.giveaways,'🎁','Giveaways')}
      ${viewPersonRows(ev.catering,'🍽️','Catering')}
      ${viewImgBlock('🖼️ Event Logo',(ev.logo||[]))}
      ${viewImgBlock('📸 Event Photos',(ev.images||[]))}
    </div>`;
  });
  // TV Ads
  const allTvs=c.tvMulti||(c.tv?[c.tv]:[]);
  allTvs.forEach((tv,ti)=>{
    html+=`<div class="view-sub-card"><div class="view-sub-card-title">📺 TV Ad #${ti+1}: ${escHtml(tv.name||'TV Ad')}</div>
      <div class="view-kv-grid">
        <div><div class="view-kv-label">📅 Period</div><div class="view-kv-val">${fmtDate(tv.start)} – ${fmtDate(tv.end)}</div></div>
        <div><div class="view-kv-label">💰 Budget</div><div class="view-kv-val accent"> ${fmtBudget(tv.budget)}</div></div>
      </div>
      ${(tv.channels||[]).map((ch,ci)=>`<div style="margin-top:8px;padding:9px 12px;background:#fff;border:1px solid var(--clr-border);border-radius:7px"><div style="font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--clr-orange-dk);margin-bottom:5px">📡 ${escHtml(ch.channelName||'Channel #'+(ci+1))}</div><div style="font-size:.84rem;display:flex;gap:12px;flex-wrap:wrap"><span>Budget: <strong> ${fmtBudget(ch.budget)}</strong></span>${(ch.slots||[]).length?`<span>Slots: ${ch.slots.map(sl=>(sl.count?sl.count+'×':'')+' '+sl.time).join(', ')}</span>`:''}</div>${viewImgBlock('📸 Channel Media',(ch.media||[]))}</div>`).join('')}
    </div>`;
  });
  // Street Ads
  const allSts=c.streetMulti||(c.street?[c.street]:[]);
  allSts.forEach((st,si)=>{
    html+=`<div class="view-sub-card"><div class="view-sub-card-title">🏙️ Street Ad #${si+1}: ${escHtml(st.name||'Street Ad')}</div>
      <div class="view-kv-grid">
        <div><div class="view-kv-label">📅 Period</div><div class="view-kv-val">${fmtDate(st.start)} – ${fmtDate(st.end)}</div></div>
        <div><div class="view-kv-label">💰 Budget</div><div class="view-kv-val accent"> ${fmtBudget(st.budget)}</div></div>
      </div>
      ${(st.adTypes||[]).map(at=>`<div style="margin-top:8px;padding:9px 12px;background:#fff;border:1px solid var(--clr-border);border-radius:7px"><div style="font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--clr-orange-dk);margin-bottom:5px">📋 ${at.type}</div><div style="font-size:.84rem;display:flex;gap:12px;flex-wrap:wrap"><span>Count: <strong>${at.count||'—'}</strong></span><span>Budget: <strong> ${fmtBudget(at.budget)}</strong></span>${(at.locations||[]).length?`<span>Locations: ${at.locations.filter(l=>l.name).map(l=>escHtml(l.name)).join(', ')}</span>`:''}</div></div>`).join('')}
      ${viewImgBlock('📸 Street Ad Photos',(st.images||[]))}
    </div>`;
  });
  // Social Media
  const allSms=c.socialMulti||(c.social?[c.social]:[]);
  allSms.forEach((sm,smi)=>{
    const platBudgets=(sm.platformBudgets||[]).filter(pb=>pb.platform&&pb.budget>0);
    html+=`<div class="view-sub-card"><div class="view-sub-card-title">📱 Social Media Ad #${smi+1}: ${escHtml(sm.adName||sm.name||'Social Ad')}</div>
      <div class="view-kv-grid">
        <div><div class="view-kv-label">🌐 Platforms</div><div class="view-kv-val"><div class="view-chips">${(sm.platforms||[]).map(p=>`<span class="view-chip">${p}</span>`).join('')||'—'}</div></div></div>
        <div><div class="view-kv-label">💰 Total Budget</div><div class="view-kv-val accent"> ${fmtBudget(sm.budget)}</div></div>
        <div><div class="view-kv-label">📅 Period</div><div class="view-kv-val">${fmtDate(sm.start)} – ${fmtDate(sm.end)}</div></div>
        ${sm.targetKpi?`<div><div class="view-kv-label">🎯 Target KPI</div><div class="view-kv-val">${escHtml(sm.targetKpi)}</div></div>`:''}
      </div>
      ${platBudgets.length?`<div style="margin-top:10px;padding:10px 12px;background:#fff;border:1px solid var(--clr-border);border-radius:7px"><div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--clr-text-sub);margin-bottom:7px">Per-Platform Budget</div>${platBudgets.map(pb=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px dashed var(--clr-border);font-size:.84rem"><span style="font-weight:500">${pb.platform}</span><span style="font-weight:700;color:var(--clr-orange-dk)"> ${fmtBudget(pb.budget)}</span></div>`).join('')}</div>`:''}
      ${viewImgBlock('📸 Social Media Assets',(sm.images||[]))}
    </div>`;
  });
  // Exhibitions
  (c.exhibitionMulti||[]).forEach((ex,ei)=>{
    html+=`<div class="view-sub-card"><div class="view-sub-card-title">🏛️ Exhibition #${ei+1}: ${escHtml(ex.name||'Exhibition')}</div>
      <div class="view-kv-grid">
        <div><div class="view-kv-label">📍 Venue</div><div class="view-kv-val">${escHtml(ex.place||'—')}</div></div>
        <div><div class="view-kv-label">💰 Budget</div><div class="view-kv-val accent"> ${fmtBudget(ex.budget)}</div></div>
        <div><div class="view-kv-label">📅 Period</div><div class="view-kv-val">${fmtDate(ex.start)} – ${fmtDate(ex.end)}</div></div>
      </div>
    </div>`;
  });
  // Other costs
  if ((c.otherCosts||[]).length) {
    const ocTotal=(c.otherCosts||[]).reduce((s,oc)=>s+Number(oc.value||0),0);
    html+=`<div class="view-sub-card"><div class="view-sub-card-title">💼 Other Costs</div>
      ${(c.otherCosts||[]).map(oc=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px dashed var(--clr-border);font-size:.84rem"><span style="color:var(--clr-text-sub)">${escHtml(oc.reason||'Other')}</span><strong style="color:var(--clr-text)"> ${fmtBudget(oc.value)}</strong></div>`).join('')}
      <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:.83rem;font-weight:700"><span>Subtotal</span><span style="color:var(--clr-orange-dk)"> ${fmtBudget(ocTotal)}</span></div>
    </div>`;
  }

  document.getElementById('viewModalBody').innerHTML=html;
  document.getElementById('viewModal').classList.add('open');
  document.body.style.overflow='hidden';
}
function closeView(){document.getElementById('viewModal').classList.remove('open');document.body.style.overflow='';}
document.getElementById('viewModalClose').addEventListener('click',closeView);
document.getElementById('viewClose').addEventListener('click',closeView);
document.getElementById('viewModal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeView();});

/* ═══════════════════════════════════════════════════════
   PROJECT DROPDOWN
═══════════════════════════════════════════════════════ */
const PROJECTS_LIST = [
  'Zed East','Badya','Sodic East','Swan Lake','CITYSCAPE Tower','Palm Hills','Madinaty','Mountain View iCity','Hyde Park','Solana West','New Cairo Residences','6th October Plaza','Capital Gardens','Zahraa El Maadi','Sarayat Al Jazeera','Al Rehab Extension','The Crown Compound','Uptown Cairo','O West','Bloomfields'
];

function initProjDD(prefix, currentVal) {
  const list = document.getElementById(prefix+'_list');
  const display = document.getElementById(prefix+'_display');
  if (!list) return;
  list.innerHTML = '';
  PROJECTS_LIST.forEach(p => {
    const div = document.createElement('div');
    div.className = 'proj-dd-item' + (p === currentVal ? ' selected' : '');
    div.dataset.val = p;
    div.innerHTML = `<span class="proj-dd-dot"></span>${p}`;
    div.onclick = () => selectProjItem(prefix, p);
    list.appendChild(div);
  });
  if (display && currentVal) display.value = currentVal;
}

function toggleProjDD(prefix) {
  const dd = document.getElementById(prefix+'_dd');
  const isOpen = dd.classList.contains('open');
  // Close all project dropdowns
  document.querySelectorAll('.proj-dropdown').forEach(d => d.classList.remove('open'));
  if (!isOpen) {
    dd.classList.add('open');
    const searchInput = document.getElementById(prefix+'_search');
    if (searchInput) { searchInput.value = ''; filterProjDD(searchInput, prefix); setTimeout(()=>searchInput.focus(),50); }
  }
}

function filterProjDD(input, prefix) {
  const q = input.value.toLowerCase();
  const list = document.getElementById(prefix+'_list');
  if (!list) return;
  let found = 0;
  Array.from(list.querySelectorAll('.proj-dd-item')).forEach(item => {
    const match = !q || item.dataset.val.toLowerCase().includes(q);
    item.style.display = match ? '' : 'none';
    if (match) found++;
  });
  let empty = list.querySelector('.proj-dd-empty');
  if (!found) {
    if (!empty) { empty = document.createElement('div'); empty.className = 'proj-dd-empty'; list.appendChild(empty); }
    empty.textContent = 'No projects found';
    empty.style.display = '';
  } else if (empty) { empty.style.display = 'none'; }
}

function selectProjItem(prefix, val) {
  const display = document.getElementById(prefix+'_display');
  const hidden = document.getElementById(prefix+'_val');
  const dd = document.getElementById(prefix+'_dd');
  const list = document.getElementById(prefix+'_list');
  if (display) display.value = val;
  if (hidden) hidden.value = val;
  if (dd) dd.classList.remove('open');
  if (list) Array.from(list.querySelectorAll('.proj-dd-item')).forEach(item => item.classList.toggle('selected', item.dataset.val === val));
}

// Close project dropdowns on outside click
document.addEventListener('click', e => {
  if (!e.target.closest('.proj-select-wrap')) {
    document.querySelectorAll('.proj-dropdown').forEach(d => d.classList.remove('open'));
  }
});

// Init create form project dropdown on page load
document.addEventListener('DOMContentLoaded', () => { initProjDD('c_proj', ''); });
// Also call directly since DOMContentLoaded may have already fired
if (document.readyState !== 'loading') { setTimeout(() => initProjDD('c_proj', ''), 0); }


function deleteCampaign(index) {
  const camp=campaigns[index], name=camp.name;
  Swal.fire({title:'Delete Campaign?',html:`Are you sure you want to delete <strong>${escHtml(name)}</strong>?<br>This action cannot be undone.`,icon:'question',showCancelButton:true,confirmButtonText:'Yes, delete',cancelButtonText:'Cancel',reverseButtons:true,focusCancel:true}).then(async r=>{
    if(r.isConfirmed){
      try {
        await apiSend(_campUrl(_cfg().deleteTmpl, camp.id), 'POST');
        activeNameFilters.delete(name);
        await fetchCampaigns(); renderTable(); renderNameFilterList();
        showToast('success','Campaign Deleted',`"${name}" has been removed.`);
      } catch(e) {
        showToast('error','Could not delete', e.message || 'Server error.');
      }
    }
  });
}

/* ═══════════════════════════════════════════════════════
   LIGHTBOX & MISC
═══════════════════════════════════════════════════════ */
function openLightbox(src){document.getElementById('lightboxImg').src=src;document.getElementById('lightbox').style.display='flex';}
function closeLightbox(){document.getElementById('lightbox').style.display='none';}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeLightbox();closeApprovalModal();}});
function highlight(id){const el=document.getElementById(id);if(!el)return;el.classList.add('error');el.focus();setTimeout(()=>el.classList.remove('error'),1500);}

/* ═══════════════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════════════ */
fetchCampaigns().then(()=>{ renderTable(); });

document.addEventListener('visibilitychange',()=>{ if(document.visibilityState==='visible'){ fetchCampaigns().then(renderTable); } });
window.addEventListener('focus',()=>{ fetchCampaigns().then(renderTable); });

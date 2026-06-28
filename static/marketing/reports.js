// ═══════════════════════════════════════════
// RAW DATA — loaded via AJAX from the marketing-report endpoint
// ═══════════════════════════════════════════
let RAW = { campaignTypes:[], socialKpis:[], events:[] };

// ═══════════════════════════════════════════
// FILTER STATE
// ═══════════════════════════════════════════
const GF_OPTIONS = {
  period: [{val:'all',label:'All Time'},{val:'q1',label:'Q1 2026'},{val:'q2',label:'Q2 2026'},{val:'ytd',label:'YTD'},{val:'last30',label:'Last 30 Days'}],
  type:   [],
  platform:[{val:'meta',label:'Meta'},{val:'linkedin',label:'LinkedIn'},{val:'tiktok',label:'TikTok'}],
  status: [{val:'EXCEEDED',label:'Exceeded'},{val:'UNDERPERFORMING',label:'Underperforming'}],
};

const state = {
  period: new Set(['all']),
  type:   new Set(),
  platform: new Set(),
  status: new Set(),
};

// table sort state
const tblSort = {
  social: {col:'platform', dir:1},
  campaign: {col:'label', dir:1},
};
// table column filters
const tblColFilter = {
  social: {},    // {col: Set of allowed values}
  campaign: {},
};
// budget range filters per table
const tblBudgetFilter = {
  social: {min:null, max:null},
  campaign: {min:null, max:null},
};

// chart click filter
let chartClickFilter = {active:false, dim:'type', val:null};

// ═══════════════════════════════════════════
// GLOBAL FILTER DROPDOWN LOGIC
// ═══════════════════════════════════════════
let openDropdown = null;

function toggleDropdown(key){
  const dd = document.getElementById('gfdd-'+key);
  const btn = document.getElementById('gfsb-'+key);
  if(openDropdown && openDropdown !== key){
    closeDropdown(openDropdown);
  }
  if(dd.classList.contains('open')){
    closeDropdown(key);
  } else {
    openDropdown = key;
    dd.classList.add('open');
    btn.classList.add('open');
    positionDropdown(key);
  }
}

function closeDropdown(key){
  const dd = document.getElementById('gfdd-'+key);
  const btn = document.getElementById('gfsb-'+key);
  if(dd) dd.classList.remove('open');
  if(btn) btn.classList.remove('open');
  if(openDropdown===key) openDropdown=null;
}

function positionDropdown(key){
  if(window.innerWidth <= 640) return; // CSS handles inline positioning on mobile
  const btn = document.getElementById('gfsb-'+key);
  const dd = document.getElementById('gfdd-'+key);
  if(!btn||!dd) return;
  const r = btn.getBoundingClientRect();
  const ddW = Math.max(r.width, 200);
  dd.style.width = ddW + 'px';
  dd.style.top = (r.bottom + 4) + 'px';
  dd.style.bottom = '';
  let left = r.left;
  if(left + ddW > window.innerWidth - 10) left = window.innerWidth - ddW - 10;
  if(left < 8) left = 8;
  dd.style.left = left + 'px';
}

document.addEventListener('click', e=>{
  if(openDropdown && !e.target.closest('#gfg-'+openDropdown)){
    closeDropdown(openDropdown);
  }
  if(!e.target.closest('#colFilterDropdown') && !e.target.closest('.th-icon-btn')){
    document.getElementById('colFilterDropdown').classList.remove('open');
  }
});

function buildGfLists(){
  Object.keys(GF_OPTIONS).forEach(key=>{
    const list = document.getElementById('gflist-'+key);
    if(!list) return;
    list.innerHTML = GF_OPTIONS[key].map(opt=>`
      <div class="gf-dd-item" data-key="${key}" data-val="${opt.val}">
        <input type="checkbox" id="gf-${key}-${opt.val}" ${key==='period'&&opt.val==='all'?'checked':''}>
        <label for="gf-${key}-${opt.val}">${opt.label}</label>
      </div>`).join('');
    list.querySelectorAll('input[type=checkbox]').forEach(cb=>{
      cb.addEventListener('change', ()=>handleGfChange(key, cb.closest('.gf-dd-item').dataset.val, cb.checked));
    });
  });
  // period defaults to 'all'
  state.period.add('all');
}

function handleGfChange(key, val, checked){
  if(key==='period'){
    // single-select for period
    state.period.clear();
    document.querySelectorAll('#gflist-period input').forEach(cb=>{cb.checked=false;});
    if(checked){ state.period.add(val); document.getElementById('gf-period-'+val).checked=true; }
    else { state.period.add('all'); document.getElementById('gf-period-all').checked=true; }
  } else {
    if(checked) state[key].add(val);
    else state[key].delete(val);
  }
  cascadeFilters();
  updateGfButtons();
  updateAll();
}

function cascadeFilters(){
  updateGfAvailability();
}

function updateGfAvailability(){
  const periodVal = [...state.period][0]||'all';
  const mult = {all:1,q1:.45,q2:.55,ytd:.8,last30:.18}[periodVal]||1;

  // ── Helper: apply period scale and return campaign types passing current TYPE filter (ignoring one key)
  function getTypesExcluding(excludeKey){
    let types = RAW.campaignTypes.map(t=>({...t,
      budget:Math.round(t.budget*mult),
      leads_count:Math.round(t.leads_count*mult),
      interested_leads:Math.round(t.interested_leads*mult)
    }));
    if(excludeKey!=='type' && state.type.size>0)
      types = types.filter(t=>state.type.has(t.type_code));
    return types;
  }

  // ── Helper: apply period scale and return social rows passing current PLATFORM+STATUS filters (ignoring one key)
  function getSocialExcluding(excludeKey){
    let social = RAW.socialKpis.map(s=>({...s,
      actual:Math.round(s.actual*mult),
      target:Math.round(s.target*mult),
      budget:Math.round(s.budget*mult)
    }));
    const platformMap={meta:'Meta (Facebook/Instagram)',linkedin:'LinkedIn',tiktok:'TikTok'};
    if(excludeKey!=='platform' && state.platform.size>0){
      const allowed=new Set([...state.platform].map(v=>platformMap[v]));
      social=social.filter(s=>allowed.has(s.platform));
    }
    if(excludeKey!=='status' && state.status.size>0)
      social=social.filter(s=>state.status.has(s.status));
    return social;
  }

  const revMap={'Meta (Facebook/Instagram)':'meta','LinkedIn':'linkedin','TikTok':'tiktok'};
  const typeHasSocial = state.type.size===0 || state.type.has('SOCIAL_MEDIA');

  // ── TYPE dropdown: all types always available (they affect campaign table independently)
  //    But if platform or status is active, only SOCIAL_MEDIA yields social results → dim others softly
  document.querySelectorAll('#gflist-type .gf-dd-item').forEach(el=>{
    el.classList.remove('disabled');
  });

  // ── PLATFORM dropdown: available platforms = those present in social data filtered by status (not platform itself)
  const socialForPlatform = getSocialExcluding('platform');
  const availPlatforms = new Set(socialForPlatform.map(s=>revMap[s.platform]).filter(Boolean));
  // If type filter excludes social media, disable all platforms
  const platformsEnabled = typeHasSocial;
  document.querySelectorAll('#gflist-platform .gf-dd-item').forEach(el=>{
    const val = el.dataset.val;
    const available = platformsEnabled && availPlatforms.has(val);
    el.classList.toggle('disabled', !available);
    if(!available && state.platform.has(val)){
      state.platform.delete(val);
      const cb=document.getElementById('gf-platform-'+val);
      if(cb) cb.checked=false;
    }
  });

  // ── STATUS dropdown: available statuses = those present in social data filtered by platform (not status itself)
  const socialForStatus = getSocialExcluding('status');
  const availStatuses = new Set(socialForStatus.map(s=>s.status));
  const statusesEnabled = typeHasSocial;
  document.querySelectorAll('#gflist-status .gf-dd-item').forEach(el=>{
    const val = el.dataset.val;
    const available = statusesEnabled && availStatuses.has(val);
    el.classList.toggle('disabled', !available);
    if(!available && state.status.has(val)){
      state.status.delete(val);
      const cb=document.getElementById('gf-status-'+val);
      if(cb) cb.checked=false;
    }
  });

  // ── PERIOD dropdown: always all options available (period is a time dimension, not a data subset)
  document.querySelectorAll('#gflist-period .gf-dd-item').forEach(el=>el.classList.remove('disabled'));
}

function selectAllGf(key){
  if(key==='period'){
    state.period.clear();
    state.period.add('all');
    document.querySelectorAll('#gflist-period input').forEach(cb=>{ cb.checked = cb.closest('.gf-dd-item').dataset.val==='all'; });
  } else {
    GF_OPTIONS[key].forEach(opt=>{ state[key].add(opt.val); document.getElementById('gf-'+key+'-'+opt.val).checked=true; });
  }
  cascadeFilters();
  updateGfButtons();
  updateAll();
}

function clearGf(key){
  state[key].clear();
  document.querySelectorAll('#gflist-'+key+' input').forEach(cb=>cb.checked=false);
  if(key==='period'){ state.period.add('all'); document.getElementById('gf-period-all').checked=true; }
  cascadeFilters();
  updateGfButtons();
  updateAll();
}

function clearAllFilters(){
  ['type','platform','status'].forEach(k=>{ state[k].clear(); document.querySelectorAll('#gflist-'+k+' input').forEach(cb=>cb.checked=false); });
  state.period.clear(); state.period.add('all');
  document.querySelectorAll('#gflist-period input').forEach(cb=>{ cb.checked=cb.closest('.gf-dd-item').dataset.val==='all'; });
  chartClickFilter = {active:false,dim:'type',val:null};
  tblColFilter.social = {}; tblColFilter.campaign = {};
  tblBudgetFilter.social = {min:null,max:null};
  tblBudgetFilter.campaign = {min:null,max:null};
  tblRangeFilter.social = {}; tblRangeFilter.campaign = {};
  ['cfdBudgetMin','cfdBudgetMax'].forEach(id=>{ const el=document.getElementById(id); if(el) el.value=''; });
  cascadeFilters(); updateGfButtons(); updateAll();
  toast('All filters cleared');
}

function filterGfList(key, q){
  document.querySelectorAll('#gflist-'+key+' .gf-dd-item').forEach(el=>{
    el.style.display = el.querySelector('label').textContent.toLowerCase().includes(q.toLowerCase()) ? '' : 'none';
  });
}

function updateGfButtons(){
  const labels = {
    period: p=>{ if(p==='all') return 'All Time'; return GF_OPTIONS.period.find(o=>o.val===p)?.label||p; },
    type: ()=> state.type.size===0?'All Types': state.type.size===1? GF_OPTIONS.type.find(o=>state.type.has(o.val))?.label : state.type.size+' Types',
    platform: ()=> state.platform.size===0?'All Platforms': state.platform.size===1? GF_OPTIONS.platform.find(o=>state.platform.has(o.val))?.label : state.platform.size+' Platforms',
    status: ()=> state.status.size===0?'All Statuses': state.status.size===1? GF_OPTIONS.status.find(o=>state.status.has(o.val))?.label : state.status.size+' Statuses',
  };
  const periodVal = [...state.period][0]||'all';
  document.getElementById('gfsb-period-txt').textContent = labels.period(periodVal);
  document.getElementById('gfsb-type-txt').textContent = labels.type();
  document.getElementById('gfsb-platform-txt').textContent = labels.platform();
  document.getElementById('gfsb-status-txt').textContent = labels.status();

  ['type','platform','status'].forEach(k=>{
    document.getElementById('gfsb-'+k).classList.toggle('has-selection', state[k].size>0);
  });
  document.getElementById('gfsb-period').classList.toggle('has-selection', periodVal!=='all');

  updateChips();
  updateSummary();
}

function updateChips(){
  const chips = document.getElementById('activeChips');
  let html='';
  const periodVal = [...state.period][0]||'all';
  if(periodVal!=='all') html+=`<span class="chip">Period: ${GF_OPTIONS.period.find(o=>o.val===periodVal)?.label} <span class="chip-x" onclick="clearGf('period')">✕</span></span>`;
  state.type.forEach(v=>{ const l=GF_OPTIONS.type.find(o=>o.val===v)?.label||v; html+=`<span class="chip">Type: ${l} <span class="chip-x" onclick="removeGfVal('type','${v}')">✕</span></span>`; });
  state.platform.forEach(v=>{ const l=GF_OPTIONS.platform.find(o=>o.val===v)?.label||v; html+=`<span class="chip">Platform: ${l} <span class="chip-x" onclick="removeGfVal('platform','${v}')">✕</span></span>`; });
  state.status.forEach(v=>{ const l=GF_OPTIONS.status.find(o=>o.val===v)?.label||v; html+=`<span class="chip">Status: ${l} <span class="chip-x" onclick="removeGfVal('status','${v}')">✕</span></span>`; });
  if(chartClickFilter.active) html+=`<span class="chip">Chart: ${chartClickFilter.val} <span class="chip-x" onclick="clearChartFilter()">✕</span></span>`;
  Object.keys(tblColFilter.social).forEach(col=>{ if(tblColFilter.social[col].size>0) html+=`<span class="chip">Social/${col} filter <span class="chip-x" onclick="clearColFilter('social','${col}')">✕</span></span>`; });
  Object.keys(tblColFilter.campaign).forEach(col=>{ if(tblColFilter.campaign[col].size>0) html+=`<span class="chip">Campaign/${col} filter <span class="chip-x" onclick="clearColFilter('campaign','${col}')">✕</span></span>`; });
  Object.keys(tblRangeFilter.social||{}).forEach(col=>{ const rf=tblRangeFilter.social[col]||{}; if(rf.min!==null&&rf.min!==undefined||rf.max!==null&&rf.max!==undefined) html+=`<span class="chip">Social/${col} range <span class="chip-x" onclick="clearRangeFilter('social','${col}')">✕</span></span>`; });
  Object.keys(tblRangeFilter.campaign||{}).forEach(col=>{ const rf=tblRangeFilter.campaign[col]||{}; if(rf.min!==null&&rf.min!==undefined||rf.max!==null&&rf.max!==undefined) html+=`<span class="chip">Campaign/${col} range <span class="chip-x" onclick="clearRangeFilter('campaign','${col}')">✕</span></span>`; });
  chips.innerHTML = html;
}

function removeGfVal(key, val){
  state[key].delete(val);
  const cb = document.getElementById('gf-'+key+'-'+val);
  if(cb) cb.checked=false;
  cascadeFilters(); updateGfButtons(); updateAll();
}

function clearChartFilter(){ chartClickFilter={active:false,dim:'type',val:null}; updateGfButtons(); updateAll(); }
function clearColFilter(tbl, col){ if(tblColFilter[tbl]) delete tblColFilter[tbl][col]; updateGfButtons(); renderTables(); }
function clearRangeFilter(tbl, col){ if(tblRangeFilter[tbl]) delete tblRangeFilter[tbl][col]; if(col==='budget'){ tblBudgetFilter[tbl].min=null; tblBudgetFilter[tbl].max=null; } updateGfButtons(); renderTables(); }

function updateSummary(){
  const parts=[];
  const periodVal=[...state.period][0]||'all';
  if(periodVal!=='all') parts.push(GF_OPTIONS.period.find(o=>o.val===periodVal)?.label||periodVal);
  if(state.type.size) parts.push([...state.type].map(v=>GF_OPTIONS.type.find(o=>o.val===v)?.label).join(', '));
  if(state.platform.size) parts.push([...state.platform].map(v=>GF_OPTIONS.platform.find(o=>o.val===v)?.label).join(', '));
  if(state.status.size) parts.push([...state.status].map(v=>GF_OPTIONS.status.find(o=>o.val===v)?.label).join(', '));
  document.getElementById('gfSummary').textContent = parts.length ? parts.join(' · ') : 'All campaigns · All time';
}

// ═══════════════════════════════════════════
// DATA FILTERING
// ═══════════════════════════════════════════
function getFilteredData(){
  let types = [...RAW.campaignTypes];
  let social = [...RAW.socialKpis];
  let events = [...RAW.events];

  // Campaign type filter
  if(state.type.size>0) types = types.filter(t=>state.type.has(t.type_code));

  // Platform filter (social only)
  if(state.platform.size>0){
    const map={meta:'Meta (Facebook/Instagram)',linkedin:'LinkedIn',tiktok:'TikTok'};
    const allowed=new Set([...state.platform].map(v=>map[v]));
    social = social.filter(s=>allowed.has(s.platform));
  }

  // Status filter
  if(state.status.size>0) social = social.filter(s=>state.status.has(s.status));

  // Chart click filter (overrides type filter)
  if(chartClickFilter.active){
    if(chartClickFilter.dim==='type'){
      types = types.filter(t=>t.label===chartClickFilter.val||t.type_code===chartClickFilter.val);
    } else if(chartClickFilter.dim==='platform'){
      const pmap={meta:'Meta (Facebook/Instagram)',linkedin:'LinkedIn',tiktok:'TikTok'};
      const platformName = pmap[chartClickFilter.val] || chartClickFilter.val;
      social = social.filter(s=>s.platform===platformName);
    }
  }

  // Period multiplier
  const periodVal=[...state.period][0]||'all';
  const mult={all:1,q1:.45,q2:.55,ytd:.8,last30:.18}[periodVal]||1;
  types=types.map(t=>({...t,budget:Math.round(t.budget*mult),leads_count:Math.round(t.leads_count*mult),interested_leads:Math.round(t.interested_leads*mult)}));
  social=social.map(s=>({...s,actual:Math.round(s.actual*mult),target:Math.round(s.target*mult),budget:Math.round(s.budget*mult)}));

  return {types,social,events};
}

// ═══════════════════════════════════════════
// CHARTS
// ═══════════════════════════════════════════
let charts={};

function initCharts(){
  Chart.defaults.font.family="'Times New Roman', Times, serif";
  Chart.defaults.color='#7a7570';

  // Chart 1: Budget vs Interested Leads
  charts.budgetVsLeads = new Chart(document.getElementById('chartBudgetVsLeads'),{
    type:'bar',
    data:{labels:[],datasets:[
      {label:'Budget (EGP)',data:[],backgroundColor:'rgba(99,102,241,.72)',borderColor:'#6366f1',borderWidth:1,borderRadius:5,yAxisID:'y'},
      {label:'Interested Leads',data:[],type:'line',borderColor:'#0d9488',backgroundColor:'rgba(13,148,136,.1)',tension:.4,pointRadius:5,pointBackgroundColor:'#0d9488',yAxisID:'y1',fill:true}
    ]},
    options:{responsive:true,interaction:{mode:'index',intersect:false},
      onClick:(evt,els)=>{ if(els.length){ const idx=els[0].index; const lbl=charts.budgetVsLeads.data.labels[idx]; applyChartClickFilter('type',lbl); }},
      plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.dataset.yAxisID==='y'?`EGP ${c.raw.toLocaleString()}`:c.raw.toLocaleString()}}},
      scales:{y:{position:'left',grid:{color:'rgba(0,0,0,.04)'},ticks:{callback:v=>'EGP '+(v>=1000000?(v/1000000).toFixed(1)+'M':v>=1000?(v/1000).toFixed(0)+'K':v)}},y1:{position:'right',grid:{drawOnChartArea:false},ticks:{color:'#0d9488'}}}}
  });

  // Chart 2: CPL vs CPIL horizontal bar
  charts.cplCpil = new Chart(document.getElementById('chartCplCpil'),{
    type:'bar',
    data:{labels:[],datasets:[
      {label:'CPL (EGP)',data:[],backgroundColor:'rgba(16,185,129,.72)',borderColor:'#10b981',borderWidth:1,borderRadius:4},
      {label:'CPIL (EGP)',data:[],backgroundColor:'rgba(244,63,94,.72)',borderColor:'#f43f5e',borderWidth:1,borderRadius:4}
    ]},
    options:{indexAxis:'y',responsive:true,
      onClick:(evt,els)=>{ if(els.length){ const idx=els[0].index; const lbl=charts.cplCpil.data.labels[idx]; applyChartClickFilter('type',lbl); }},
      plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>`EGP ${c.raw.toLocaleString()}`}}},
      scales:{x:{grid:{color:'rgba(0,0,0,.04)'},ticks:{callback:v=>'EGP '+(v>=1000?(v/1000).toFixed(0)+'K':v)}},y:{grid:{display:false}}}}
  });

  // Chart 3: Social KPIs
  charts.socialKpis = new Chart(document.getElementById('chartSocialKpis'),{
    type:'bar',
    data:{labels:[],datasets:[
      {label:'Target',data:[],backgroundColor:'rgba(99,102,241,.25)',borderColor:'rgba(99,102,241,.5)',borderWidth:1,borderRadius:4},
      {label:'Actual',data:[],backgroundColor:'rgba(99,102,241,.8)',borderColor:'#6366f1',borderWidth:1,borderRadius:4}
    ]},
    options:{responsive:true,
      onClick:(evt,els)=>{ if(els.length){ const idx=els[0].index; const lbl=charts.socialKpis.data.labels[idx]; applyChartClickFilter('platform',lbl.toLowerCase()); }},
      plugins:{legend:{display:false}},
      scales:{x:{grid:{display:false}},y:{grid:{color:'rgba(0,0,0,.04)'}}}}
  });
}

function applyChartClickFilter(dim, val){
  if(chartClickFilter.active && chartClickFilter.dim===dim && chartClickFilter.val===val){
    chartClickFilter={active:false,dim:'type',val:null};
    document.querySelectorAll('.chart-card').forEach(c=>c.classList.remove('chart-active-filter'));
  } else {
    chartClickFilter={active:true,dim,val};
    const cardMap={'type':'card-budgetVsLeads','platform':'card-socialKpis'};
    document.querySelectorAll('.chart-card').forEach(c=>c.classList.remove('chart-active-filter'));
    if(cardMap[dim]) document.getElementById(cardMap[dim])?.classList.add('chart-active-filter');
  }
  updateGfButtons();
  updateAll();
  toast(chartClickFilter.active?`Filtered by: ${val}`:'Chart filter cleared');
}

// ═══════════════════════════════════════════
// COLUMN SORT & FILTER (Tables)
// ═══════════════════════════════════════════
function sortTable(tbl, col, btn){
  if(tblSort[tbl].col===col) tblSort[tbl].dir*=-1;
  else { tblSort[tbl].col=col; tblSort[tbl].dir=1; }
  document.querySelectorAll(`#${tbl==='social'?'social':'campaign'}Table .th-icon-btn`).forEach(b=>b.classList.remove('active-sort'));
  btn.classList.add('active-sort');
  renderTables();
}

// Column filter dropdown state
let cfd = {tbl:null, col:null, allVals:[], selectedVals:new Set()};

// All numeric columns that get min/max range filter
const NUMERIC_COLS = {
  social:   new Set(['budget','target','actual','cpl']),
  campaign: new Set(['budget','leads_count','interested_leads','cpl','cpil','rate'])
};

// Per-table per-column range filters  {tbl: {col: {min,max}}}
const tblRangeFilter = {
  social:   {},
  campaign: {}
};

// Legacy alias (kept for clearAllFilters compat)
const BUDGET_COLS = new Set(['budget']);

function openColFilter(evt, tbl, col){
  evt.stopPropagation();
  const btn = evt.currentTarget;
  const r = btn.getBoundingClientRect();
  const dd = document.getElementById('colFilterDropdown');
  const isNumeric = (NUMERIC_COLS[tbl]||new Set()).has(col);

  cfd.tbl=tbl; cfd.col=col;

  const colTitles={platform:'Platform',budget:'Budget (EGP)',target:'Target Leads',actual:'Actual Leads',status:'Status',cpl:'CPL (EGP)',label:'Campaign Type',leads_count:'Total Leads',interested_leads:'Interested Leads',cpil:'CPIL (EGP)',rate:'Conversion Rate %'};
  document.getElementById('cfdTitle').textContent = colTitles[col]||col;

  const searchEl  = document.getElementById('cfdSearch');
  const listEl    = document.getElementById('cfdList');
  const checkAct  = document.getElementById('cfdCheckActions');
  const budgetRng = document.getElementById('cfdBudgetRange');
  const budgetAct = document.getElementById('cfdBudgetActions');

  if(isNumeric){
    searchEl.style.display  = 'none';
    listEl.style.display    = 'none';
    checkAct.style.display  = 'none';
    budgetRng.style.display = '';
    budgetAct.style.display = '';

    // Compute min/max from data filtered by all OTHER active filters (not this col)
    const nums = getColValuesExcluding(tbl, col);
    const dataMin = nums.length ? Math.min(...nums) : 0;
    const dataMax = nums.length ? Math.max(...nums) : 0;

    const minEl = document.getElementById('cfdBudgetMin');
    const maxEl = document.getElementById('cfdBudgetMax');

    // Format placeholder based on magnitude
    const fmtPlaceholder = v => v >= 1000000 ? (v/1000000).toFixed(1)+'M' : v >= 1000 ? Math.round(v/1000)+'K' : String(v);
    minEl.placeholder = fmtPlaceholder(dataMin);
    maxEl.placeholder = fmtPlaceholder(dataMax);

    // Show label suffix
    const minLabel = document.querySelector('#cfdBudgetRange .cfd-budget-row:first-child .cfd-budget-label');
    const maxLabel = document.querySelector('#cfdBudgetRange .cfd-budget-row:last-child .cfd-budget-label');
    if(minLabel) minLabel.textContent = 'Min';
    if(maxLabel) maxLabel.textContent = 'Max';

    // Restore existing range values
    const rf = (tblRangeFilter[tbl]||{})[col]||{min:null,max:null};
    minEl.value = rf.min !== null ? rf.min : '';
    maxEl.value = rf.max !== null ? rf.max : '';

  } else {
    searchEl.style.display  = '';
    listEl.style.display    = '';
    checkAct.style.display  = '';
    budgetRng.style.display = 'none';
    budgetAct.style.display = 'none';

    cfd.selectedVals = tblColFilter[tbl][col] ? new Set(tblColFilter[tbl][col]) : new Set();

    // Build values from data filtered by all OTHER active filters (not this col)
    const rows = getRowsExcluding(tbl, col);
    cfd.allVals = [...new Set(rows.map(row=>String(row[col]||'')))].filter(Boolean).sort((a,b)=>{
      const na=parseFloat(a), nb=parseFloat(b);
      return (!isNaN(na)&&!isNaN(nb)) ? na-nb : a.localeCompare(b);
    });

    searchEl.value='';
    renderCfdList(cfd.allVals);
  }

  if(window.innerWidth <= 640){
    dd.style.removeProperty('width');
    dd.style.removeProperty('top');
    dd.style.removeProperty('left');
  } else {
    const ddW = isNumeric ? 220 : 200;
    dd.style.width = ddW + 'px';
    let left = r.left - 80;
    if(left + ddW > window.innerWidth - 10) left = window.innerWidth - ddW - 10;
    if(left < 8) left = 8;
    dd.style.top = (r.bottom + 4) + 'px';
    dd.style.left = left + 'px';
  }
  dd.classList.add('open');

  document.querySelectorAll('.th-icon-btn.active-filter').forEach(b=>b.classList.remove('active-filter'));
  btn.classList.add('active-filter');
}

function renderCfdList(vals){
  document.getElementById('cfdList').innerHTML=vals.map(v=>`
    <div class="cfd-item">
      <input type="checkbox" id="cfd-${CSS.escape(v)}" ${cfd.selectedVals.has(v)?'checked':''}>
      <label for="cfd-${CSS.escape(v)}">${v}</label>
    </div>`).join('');
  document.querySelectorAll('#cfdList input').forEach(cb=>{
    cb.addEventListener('change',()=>{
      const lbl = cb.closest('.cfd-item').querySelector('label').textContent;
      if(cb.checked) cfd.selectedVals.add(lbl); else cfd.selectedVals.delete(lbl);
      applyColFilter();
    });
  });
}

function filterCfdList(q){
  renderCfdList(cfd.allVals.filter(v=>v.toLowerCase().includes(q.toLowerCase())));
}

function cfdSelectAll(){ cfd.selectedVals=new Set(cfd.allVals); applyColFilter(); renderCfdList(cfd.allVals); }
function cfdClearAll(){ cfd.selectedVals.clear(); applyColFilter(); renderCfdList(cfd.allVals); }

function applyColFilter(){
  if(cfd.selectedVals.size>0){
    tblColFilter[cfd.tbl][cfd.col]=new Set(cfd.selectedVals);
  } else {
    delete tblColFilter[cfd.tbl][cfd.col];
  }
  updateGfButtons();
  renderTables();
}

function applyBudgetRangeFilter(){
  const minVal = document.getElementById('cfdBudgetMin').value;
  const maxVal = document.getElementById('cfdBudgetMax').value;
  if(!tblRangeFilter[cfd.tbl]) tblRangeFilter[cfd.tbl]={};
  if(!tblRangeFilter[cfd.tbl][cfd.col]) tblRangeFilter[cfd.tbl][cfd.col]={min:null,max:null};
  tblRangeFilter[cfd.tbl][cfd.col].min = minVal !== '' ? Number(minVal) : null;
  tblRangeFilter[cfd.tbl][cfd.col].max = maxVal !== '' ? Number(maxVal) : null;
  // Also keep legacy budget compat
  if(cfd.col==='budget'){
    tblBudgetFilter[cfd.tbl].min = tblRangeFilter[cfd.tbl][cfd.col].min;
    tblBudgetFilter[cfd.tbl].max = tblRangeFilter[cfd.tbl][cfd.col].max;
  }
  const hasFilter = tblRangeFilter[cfd.tbl][cfd.col].min !== null || tblRangeFilter[cfd.tbl][cfd.col].max !== null;
  document.querySelectorAll('.th-icon-btn.active-filter').forEach(b=>b.classList.remove('active-filter'));
  if(hasFilter){
    document.querySelectorAll('.th-icon-btn').forEach(b=>{
      const oc=b.getAttribute('onclick')||'';
      if(oc.includes("'"+cfd.col+"'")) b.classList.add('active-filter');
    });
  }
  updateGfButtons();
  renderTables();
}

function cfdClearBudget(){
  document.getElementById('cfdBudgetMin').value = '';
  document.getElementById('cfdBudgetMax').value = '';
  if(tblRangeFilter[cfd.tbl] && tblRangeFilter[cfd.tbl][cfd.col]){
    tblRangeFilter[cfd.tbl][cfd.col] = {min:null,max:null};
  }
  if(cfd.col==='budget'){
    tblBudgetFilter[cfd.tbl].min = null;
    tblBudgetFilter[cfd.tbl].max = null;
  }
  document.querySelectorAll('.th-icon-btn.active-filter').forEach(b=>b.classList.remove('active-filter'));
  updateGfButtons();
  renderTables();
}

// ═══════════════════════════════════════════
// DEPENDENCY HELPERS — compute data with all filters EXCEPT one col
// ═══════════════════════════════════════════
function computeFullRows(tbl){
  const {types,social} = getFilteredData();
  if(tbl==='social'){
    return [...social].map(s=>({...s, cpl: s.actual ? Math.round(s.budget/s.actual) : 0}));
  } else {
    return types.map(t=>({...t,
      cpl: t.leads_count ? Math.round(t.budget/t.leads_count) : 0,
      cpil: t.interested_leads ? Math.round(t.budget/t.interested_leads) : 0,
      rate: t.leads_count ? +(t.interested_leads/t.leads_count*100).toFixed(1) : 0
    }));
  }
}

function applyAllColFilters(rows, tbl, excludeCol){
  // Checkbox filters
  Object.keys(tblColFilter[tbl]).forEach(col=>{
    if(col===excludeCol) return;
    const allowed = tblColFilter[tbl][col];
    if(allowed && allowed.size>0) rows = rows.filter(r=>allowed.has(String(r[col]||'')));
  });
  // Range filters
  const rf = tblRangeFilter[tbl]||{};
  Object.keys(rf).forEach(col=>{
    if(col===excludeCol) return;
    const range = rf[col]||{};
    if(range.min !== null && range.min !== undefined) rows = rows.filter(r=>Number(r[col])>=range.min);
    if(range.max !== null && range.max !== undefined) rows = rows.filter(r=>Number(r[col])<=range.max);
  });
  return rows;
}

function getRowsExcluding(tbl, excludeCol){
  return applyAllColFilters(computeFullRows(tbl), tbl, excludeCol);
}

function getColValuesExcluding(tbl, col){
  const rows = getRowsExcluding(tbl, col);
  return rows.map(r=>Number(r[col])).filter(v=>!isNaN(v));
}


function updateAll(){
  const {types,social,events}=getFilteredData();

  // KPIs
  const totalBudget=types.reduce((a,t)=>a+t.budget,0);
  const totalLeads=types.reduce((a,t)=>a+t.leads_count,0);
  const totalInterested=types.reduce((a,t)=>a+t.interested_leads,0);
  const avgCpl=totalLeads?Math.round(totalBudget/totalLeads):0;
  const avgCpil=totalInterested?Math.round(totalBudget/totalInterested):0;
  document.getElementById('kpi-budget').textContent='EGP '+fmtNum(totalBudget);
  document.getElementById('kpi-leads').textContent=fmtNum(totalLeads);
  document.getElementById('kpi-interested').textContent=fmtNum(totalInterested);
  document.getElementById('kpi-cpl').textContent='EGP '+fmtNum(avgCpl);
  document.getElementById('kpi-cpil').textContent='EGP '+fmtNum(avgCpil);

  // Chart 1
  charts.budgetVsLeads.data.labels=types.map(t=>t.label);
  charts.budgetVsLeads.data.datasets[0].data=types.map(t=>t.budget);
  charts.budgetVsLeads.data.datasets[1].data=types.map(t=>t.interested_leads);
  charts.budgetVsLeads.update('active');

  // Chart 2
  charts.cplCpil.data.labels=types.map(t=>t.label);
  charts.cplCpil.data.datasets[0].data=types.map(t=>t.leads_count?Math.round(t.budget/t.leads_count):0);
  charts.cplCpil.data.datasets[1].data=types.map(t=>t.interested_leads?Math.round(t.budget/t.interested_leads):0);
  charts.cplCpil.update('active');

  // Chart 3
  charts.socialKpis.data.labels=social.map(s=>s.platform.split(' ')[0]);
  charts.socialKpis.data.datasets[0].data=social.map(s=>s.target);
  charts.socialKpis.data.datasets[1].data=social.map(s=>s.actual);
  charts.socialKpis.update('active');

  // Funnel
  renderFunnel(events);
  // Tables
  renderTables();
}

function renderTables(){
  const {types,social}=getFilteredData();

  // Social table — apply all column filters then sort
  let socialData=[...social].map(s=>({...s, cpl: s.actual ? Math.round(s.budget/s.actual) : 0}));
  Object.keys(tblColFilter.social).forEach(col=>{
    const allowed=tblColFilter.social[col];
    if(allowed&&allowed.size>0) socialData=socialData.filter(r=>allowed.has(String(r[col]||'')));
  });
  Object.keys(tblRangeFilter.social||{}).forEach(col=>{
    const rf = tblRangeFilter.social[col]||{};
    if(rf.min !== null && rf.min !== undefined) socialData=socialData.filter(r=>Number(r[col])>=rf.min);
    if(rf.max !== null && rf.max !== undefined) socialData=socialData.filter(r=>Number(r[col])<=rf.max);
  });
  socialData.sort((a,b)=>{ const c=tblSort.social.col; const v=a[c]>b[c]?1:a[c]<b[c]?-1:0; return v*tblSort.social.dir; });

  // Campaign table — apply all column filters then sort
  let campData=types.map(t=>({...t,cpl:t.leads_count?Math.round(t.budget/t.leads_count):0,cpil:t.interested_leads?Math.round(t.budget/t.interested_leads):0,rate:t.leads_count?+(t.interested_leads/t.leads_count*100).toFixed(1):0}));
  Object.keys(tblColFilter.campaign).forEach(col=>{
    const allowed=tblColFilter.campaign[col];
    if(allowed&&allowed.size>0) campData=campData.filter(r=>allowed.has(String(r[col]||'')));
  });
  Object.keys(tblRangeFilter.campaign||{}).forEach(col=>{
    const rf = tblRangeFilter.campaign[col]||{};
    if(rf.min !== null && rf.min !== undefined) campData=campData.filter(r=>Number(r[col])>=rf.min);
    if(rf.max !== null && rf.max !== undefined) campData=campData.filter(r=>Number(r[col])<=rf.max);
  });
  campData.sort((a,b)=>{ const c=tblSort.campaign.col; const v=a[c]>b[c]?1:a[c]<b[c]?-1:0; return v*tblSort.campaign.dir; });

  renderSocialTable(socialData);
  renderCampaignTable(campData);
}

function renderSocialTable(social){
  const body=document.getElementById('socialTableBody');
  if(!social.length){ body.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--clr-text-sub);padding:24px;font-style:italic;">No platforms match the selected filters.</td></tr>'; return; }
  body.innerHTML=social.map(s=>{
    const pct=(s.actual/s.target*100).toFixed(0);
    const badge=s.status==='EXCEEDED'?'exceeded':s.status==='UNDERPERFORMING'?'under':'on-track';
    const label=s.status==='EXCEEDED'?'Exceeded':'Underperforming';
    const cpl=s.actual?Math.round(s.budget/s.actual):0;
    return `<tr>
      <td style="text-align:left;font-weight:600;">${s.platform}</td>
      <td>${fmtNum(s.budget)}</td>
      <td>${s.target.toLocaleString()}</td>
      <td>${s.actual.toLocaleString()}</td>
      <td><div class="progress-wrap"><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${Math.min(pct,100)}%;background:${s.status==='EXCEEDED'?'#10b981':'#f43f5e'};"></div></div><span class="progress-pct">${pct}%</span></div></td>
      <td>${fmtNum(cpl)}</td>
      <td><span class="badge ${badge}">${label}</span></td>
    </tr>`;
  }).join('');
}

function renderCampaignTable(types){
  const body=document.getElementById('campaignTableBody');
  if(!types.length){ body.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--clr-text-sub);padding:24px;font-style:italic;">No campaigns match the selected filters.</td></tr>'; return; }
  body.innerHTML=types.map(t=>{
    const color=t.rate>=25?'#10b981':t.rate>=15?'#f59e0b':'#f43f5e';
    return `<tr>
      <td style="text-align:left;font-weight:600;">${t.label}</td>
      <td>${fmtNum(t.budget)}</td>
      <td>${t.leads_count.toLocaleString()}</td>
      <td>${t.interested_leads.toLocaleString()}</td>
      <td>${fmtNum(t.cpl)}</td>
      <td>${fmtNum(t.cpil)}</td>
      <td><div class="progress-wrap"><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${Math.min(t.rate*3,100)}%;background:${color};"></div></div><span class="progress-pct" style="color:${color}">${t.rate}%</span></div></td>
    </tr>`;
  }).join('');
}

function renderFunnel(events){
  const wrap=document.getElementById('funnelWrap');
  if(!events.length){ wrap.innerHTML='<p style="color:var(--clr-text-sub);font-size:.82rem;padding:12px 0;">No event data for selected filters.</p>'; return; }
  const colors=['#6366f1','#0d9488','#10b981'];
  wrap.innerHTML=events.map(ev=>{
    const rows=[
      {label:'Target Attendees',val:ev.target,pct:100},
      {label:'Checked In',val:ev.checked_in,pct:Math.round(ev.checked_in/ev.target*100)},
      {label:'→ Interested',val:ev.converted,pct:Math.round(ev.converted/ev.target*100)},
    ];
    return `<div class="funnel-event-label">${ev.name}</div>`+
      rows.map((r,i)=>`<div class="funnel-row">
        <div class="funnel-label">${r.label}</div>
        <div class="funnel-bar-bg"><div class="funnel-bar-fill" style="width:${r.pct}%;background:${colors[i]};"><span class="funnel-bar-text">${r.pct}%</span></div></div>
        <div class="funnel-val">${r.val.toLocaleString()}</div>
      </div>`).join('')+'<div style="height:14px;"></div>';
  }).join('');
}

// ═══════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════
function fmtNum(n){
  if(n>=1000000) return (n/1000000).toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1})+'M';
  if(n>=1000) return Math.round(n/1000).toLocaleString('en-US')+'K';
  return n.toLocaleString('en-US');
}

function toast(msg){
  const c=document.getElementById('toast-container');
  const t=document.createElement('div');t.className='toast';
  t.innerHTML=`<div class="toast-icon"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div><span class="toast-msg">${msg}</span>`;
  c.appendChild(t);setTimeout(()=>t.remove(),2500);
}

function exportReport(){
  const {types}=getFilteredData();
  const rows=[['Campaign Type','Budget (EGP)','Total Leads','Interested Leads','CPL (EGP)','CPIL (EGP)','Conv. Rate %'],
    ...types.map(t=>[t.label,t.budget,t.leads_count,t.interested_leads,
      t.leads_count?Math.round(t.budget/t.leads_count):0,
      t.interested_leads?Math.round(t.budget/t.interested_leads):0,
      t.leads_count?+(t.interested_leads/t.leads_count*100).toFixed(1):0])];
  const csv=rows.map(r=>r.join(',')).join('\n');
  const a=document.createElement('a');a.href='data:text/csv,'+encodeURIComponent(csv);a.download='financial-marketing-report.csv';a.click();
  toast('Report exported as CSV');
}

// ═══════════════════════════════════════════
// INIT — fetch live figures, then build the dashboard
// ═══════════════════════════════════════════
fetch(window.REPORT_CFG.dataUrl, {headers:{'X-Requested-With':'XMLHttpRequest'}})
  .then(r=>r.json())
  .then(d=>{
    RAW = {campaignTypes:d.campaignTypes||[], socialKpis:d.socialKpis||[], events:d.events||[]};
    GF_OPTIONS.type = RAW.campaignTypes.map(t=>({val:t.type_code,label:t.label}));
    buildGfLists();
    initCharts();
    updateGfButtons();
    updateAll();
  })
  .catch(()=>toast('Could not load report data'));

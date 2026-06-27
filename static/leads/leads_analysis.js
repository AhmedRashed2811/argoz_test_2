// ═══════════════════════════════════════════
// RAW DATA — loaded via AJAX from the leads-analysis endpoint
// ═══════════════════════════════════════════
let RAW = { stages:[], sources:[], timeline:[], sourceStages:{}, activeTotal:0, inactiveTotal:0, todayNew:0 };

// Static presentation metadata for the fixed stage set (counts come from the
// backend). Stage codes are fixed; colors/icons are presentation, not data.
const STAGE_DEFS = [
  {stage:'FRESH',label:'Fresh Leads',color:'#6366f1',iconClass:'indigo',icon:'<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'},
  {stage:'FOLLOW_UP',label:'Follow Up',color:'#3b82f6',iconClass:'blue',icon:'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>'},
  {stage:'NOT_REACHED',label:'Not Reached',color:'#0ea5e9',iconClass:'sky',icon:'<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'},
  {stage:'MEETING',label:'Meeting',color:'#0d9488',iconClass:'teal',icon:'<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>'},
  {stage:'INTERESTED',label:'Interested',color:'#10b981',iconClass:'emerald',icon:'<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>'},
  {stage:'FROZEN',label:'Frozen',color:'#9ca3af',iconClass:'slate',icon:'<line x1="12" y1="2" x2="12" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/><line x1="19.07" y1="4.93" x2="4.93" y2="19.07"/>'},
];
// Palette assigned to sources by order (sources are dynamic from the DB).
const SOURCE_COLORS = ['#6366f1','#0d9488','#f59e0b','#3b82f6','#8b5cf6','#ec4899','#14b8a6','#f43f5e','#a855f7','#ef4444'];

let STAGE_LABELS = {};
let STAGE_META = {};
let SOURCE_LABELS = {};

// ═══════════════════════════════════════════
// FILTER STATE
// ═══════════════════════════════════════════
const GF_OPTIONS = {
  period: [{val:'all',label:'All Time'},{val:'7d',label:'Last 7 Days'},{val:'30d',label:'Last 30 Days'},{val:'q1',label:'Q1 2026'},{val:'q2',label:'Q2 2026'}],
  stage:  [],
  source: [],
  origin: [{val:'DIRECT',label:'Direct'},{val:'BROKER',label:'Broker'}],
  active: [{val:'active',label:'Active'},{val:'inactive',label:'Inactive'}],
};

const state = {
  period: new Set(['all']),
  stage:  new Set(),
  source: new Set(),
  origin: new Set(),
  active: new Set(),
  date:   new Set(),
};

// table sort state
const tblSort = { source: {col:'count', dir:-1} };
// table column filters
const tblColFilter = { source:{} };
// per-table per-column range filters
const tblRangeFilter = { source:{} };
const tblBudgetFilter = { source:{min:null,max:null} };

// ═══════════════════════════════════════════
// GLOBAL FILTER DROPDOWN LOGIC
// ═══════════════════════════════════════════
let openDropdown = null;

function toggleDropdown(key){
  const dd = document.getElementById('gfdd-'+key);
  const btn = document.getElementById('gfsb-'+key);
  if(openDropdown && openDropdown !== key){ closeDropdown(openDropdown); }
  if(dd.classList.contains('open')){ closeDropdown(key); }
  else {
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
  if(window.innerWidth <= 640) return;
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
  if(openDropdown && !e.target.closest('#gfg-'+openDropdown)){ closeDropdown(openDropdown); }
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
  state.period.add('all');
}

function handleGfChange(key, val, checked){
  if(key==='period'){
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

function periodMult(){ const p=[...state.period][0]||'all'; return {all:1,'7d':.06,'30d':.18,q1:.45,q2:.55}[p]||1; }

// Weight (0-1) representing the share of total leads that fall on the selected day(s).
// Used to scale every other metric/chart so the whole dashboard reacts to a timeline click.
function dateWeight(){
  if(state.date.size===0) return 1;
  const totalCreated = RAW.timeline.reduce((a,d)=>a+d.created,0);
  if(!totalCreated) return 1;
  const selectedCreated = RAW.timeline.filter(d=>state.date.has(d.date)).reduce((a,d)=>a+d.created,0);
  return selectedCreated/totalCreated;
}

function toggleDate(date){
  if(state.date.has(date)) state.date.delete(date);
  else state.date.add(date);
  cascadeFilters(); updateGfButtons(); updateAll();
  updateChartActiveFilterCards();
}

function cascadeFilters(){ updateGfAvailability(); }

// returns source rows filtered by stage(N/A)/source/origin/active EXCLUDING the given key
// (stage and source are independent dimensions of the same lead pool here, so each one
//  scales the shared pool rather than literally filtering the other's rows out)
function getSourcesExcluding(excludeKey){
  const mult = periodMult()*dateWeight();
  // Also apply stage ratio so source charts react to stage filter
  const _tsc = RAW.stages.reduce((a,s)=>a+s.count,0);
  const _ssc = state.stage.size>0 ? RAW.stages.filter(s=>state.stage.has(s.stage)).reduce((a,s)=>a+s.count,0) : _tsc;
  const _stgR = _ssc / _tsc;
  let sources = RAW.sources.map(s=>({...s, count:Math.round(s.count*mult*_stgR), interested:Math.round(s.interested*mult*_stgR)}));
  if(excludeKey!=='source' && state.source.size>0) sources = sources.filter(s=>state.source.has(s.source));
  if(excludeKey!=='origin' && state.origin.size>0) sources = sources.filter(s=>state.origin.has(s.origin));
  return sources;
}

function updateGfAvailability(){
  // Origin options depend on source filter
  const sourcesForOrigin = getSourcesExcluding('origin');
  const availOrigins = new Set(sourcesForOrigin.map(s=>s.origin));
  document.querySelectorAll('#gflist-origin .gf-dd-item').forEach(el=>{
    const val = el.dataset.val;
    const available = availOrigins.has(val);
    el.classList.toggle('disabled', !available);
    if(!available && state.origin.has(val)){
      state.origin.delete(val);
      const cb=document.getElementById('gf-origin-'+val);
      if(cb) cb.checked=false;
    }
  });

  // Source options depend on origin filter
  const sourcesForSource = getSourcesExcluding('source');
  const availSources = new Set(sourcesForSource.map(s=>s.source));
  document.querySelectorAll('#gflist-source .gf-dd-item').forEach(el=>{
    const val = el.dataset.val;
    const available = availSources.has(val);
    el.classList.toggle('disabled', !available);
    if(!available && state.source.has(val)){
      state.source.delete(val);
      const cb=document.getElementById('gf-source-'+val);
      if(cb) cb.checked=false;
    }
  });

  // Stage, Period & Active always fully available (independent dimensions)
  document.querySelectorAll('#gflist-stage .gf-dd-item').forEach(el=>el.classList.remove('disabled'));
  document.querySelectorAll('#gflist-period .gf-dd-item').forEach(el=>el.classList.remove('disabled'));
  document.querySelectorAll('#gflist-active .gf-dd-item').forEach(el=>el.classList.remove('disabled'));
}

function selectAllGf(key){
  if(key==='period'){
    state.period.clear(); state.period.add('all');
    document.querySelectorAll('#gflist-period input').forEach(cb=>{ cb.checked = cb.closest('.gf-dd-item').dataset.val==='all'; });
  } else {
    GF_OPTIONS[key].forEach(opt=>{
      const item = document.querySelector(`#gflist-${key} .gf-dd-item[data-val="${opt.val}"]`);
      if(item && item.classList.contains('disabled')) return;
      state[key].add(opt.val);
      document.getElementById('gf-'+key+'-'+opt.val).checked=true;
    });
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
  ['stage','source','origin','active'].forEach(k=>{ state[k].clear(); document.querySelectorAll('#gflist-'+k+' input').forEach(cb=>cb.checked=false); });
  state.date.clear();
  state.period.clear(); state.period.add('all');
  document.querySelectorAll('#gflist-period input').forEach(cb=>{ cb.checked=cb.closest('.gf-dd-item').dataset.val==='all'; });
  tblColFilter.source={};
  tblRangeFilter.source={};
  tblBudgetFilter.source={min:null,max:null};
  ['cfdBudgetMin','cfdBudgetMax'].forEach(id=>{ const el=document.getElementById(id); if(el) el.value=''; });
  document.querySelectorAll('.th-icon-btn.active-filter,.th-icon-btn.active-sort').forEach(b=>b.classList.remove('active-filter','active-sort'));
  document.querySelectorAll('.chart-card').forEach(c=>c.classList.remove('chart-active-filter'));
  cascadeFilters(); updateGfButtons(); updateAll();
  toast('All filters cleared');
}

function updateGfButtons(){
  const labels = {
    period: p=>{ if(p==='all') return 'All Time'; return GF_OPTIONS.period.find(o=>o.val===p)?.label||p; },
    stage: ()=> state.stage.size===0?'All Stages': state.stage.size===1? GF_OPTIONS.stage.find(o=>state.stage.has(o.val))?.label : state.stage.size+' Stages',
    source: ()=> state.source.size===0?'All Sources': state.source.size===1? GF_OPTIONS.source.find(o=>state.source.has(o.val))?.label : state.source.size+' Sources',
    origin: ()=> state.origin.size===0?'All': state.origin.size===1? GF_OPTIONS.origin.find(o=>state.origin.has(o.val))?.label : state.origin.size+' Origins',
    active: ()=> state.active.size===0?'All': state.active.size===1? GF_OPTIONS.active.find(o=>state.active.has(o.val))?.label : 'Active &amp; Inactive',
  };
  const periodVal = [...state.period][0]||'all';
  document.getElementById('gfsb-period-txt').textContent = labels.period(periodVal);
  document.getElementById('gfsb-stage-txt').textContent = labels.stage();
  document.getElementById('gfsb-source-txt').textContent = labels.source();
  document.getElementById('gfsb-origin-txt').textContent = labels.origin();
  document.getElementById('gfsb-active-txt').textContent = labels.active();

  document.getElementById('gfsb-stage').classList.toggle('has-selection', state.stage.size>0);
  document.getElementById('gfsb-source').classList.toggle('has-selection', state.source.size>0);
  document.getElementById('gfsb-origin').classList.toggle('has-selection', state.origin.size>0);
  document.getElementById('gfsb-active').classList.toggle('has-selection', state.active.size>0);
  document.getElementById('gfsb-period').classList.toggle('has-selection', periodVal!=='all');

  updateChips();
  updateSummary();
}

function updateChips(){
  const chips = document.getElementById('activeChips');
  let html='';
  const periodVal = [...state.period][0]||'all';
  if(periodVal!=='all') html+=`<span class="chip">Period: ${GF_OPTIONS.period.find(o=>o.val===periodVal)?.label} <span class="chip-x" onclick="clearGf('period')">✕</span></span>`;
  state.stage.forEach(v=>{ const l=STAGE_LABELS[v]||v; html+=`<span class="chip">Stage: ${l} <span class="chip-x" onclick="removeGfVal('stage','${v}')">✕</span></span>`; });
  state.source.forEach(v=>{ const l=SOURCE_LABELS[v]||v; html+=`<span class="chip">Source: ${l} <span class="chip-x" onclick="removeGfVal('source','${v}')">✕</span></span>`; });
  state.origin.forEach(v=>{ const l=GF_OPTIONS.origin.find(o=>o.val===v)?.label||v; html+=`<span class="chip">Origin: ${l} <span class="chip-x" onclick="removeGfVal('origin','${v}')">✕</span></span>`; });
  state.active.forEach(v=>{ const l=GF_OPTIONS.active.find(o=>o.val===v)?.label||v; html+=`<span class="chip">Status: ${l} <span class="chip-x" onclick="removeGfVal('active','${v}')">✕</span></span>`; });
  state.date.forEach(v=>{ html+=`<span class="chip">Date: ${v} <span class="chip-x" onclick="removeDateVal('${v}')">✕</span></span>`; });
  Object.keys(tblColFilter.source).forEach(col=>{ if(tblColFilter.source[col].size>0) html+=`<span class="chip">Source Tbl/${col} filter <span class="chip-x" onclick="clearColFilter('source','${col}')">✕</span></span>`; });
  Object.keys(tblRangeFilter.source||{}).forEach(col=>{ const rf=tblRangeFilter.source[col]||{}; if(rf.min!==null&&rf.min!==undefined||rf.max!==null&&rf.max!==undefined) html+=`<span class="chip">Source Tbl/${col} range <span class="chip-x" onclick="clearRangeFilter('source','${col}')">✕</span></span>`; });
  chips.innerHTML = html;
}

function removeGfVal(key, val){
  state[key].delete(val);
  const cb = document.getElementById('gf-'+key+'-'+val);
  if(cb) cb.checked=false;
  cascadeFilters(); updateGfButtons(); updateAll();
}

function removeDateVal(val){
  state.date.delete(val);
  cascadeFilters(); updateGfButtons(); updateAll();
  updateChartActiveFilterCards();
}

function clearColFilter(tbl, col){ if(tblColFilter[tbl]) delete tblColFilter[tbl][col]; updateGfButtons(); renderTables(); }
function clearRangeFilter(tbl, col){ if(tblRangeFilter[tbl]) delete tblRangeFilter[tbl][col]; updateGfButtons(); renderTables(); }

function updateSummary(){
  const parts=[];
  const periodVal=[...state.period][0]||'all';
  if(periodVal!=='all') parts.push(GF_OPTIONS.period.find(o=>o.val===periodVal)?.label||periodVal);
  if(state.stage.size) parts.push([...state.stage].map(v=>STAGE_LABELS[v]).join(', '));
  if(state.source.size) parts.push([...state.source].map(v=>SOURCE_LABELS[v]).join(', '));
  if(state.origin.size) parts.push([...state.origin].map(v=>GF_OPTIONS.origin.find(o=>o.val===v)?.label).join(', '));
  if(state.active.size) parts.push([...state.active].map(v=>GF_OPTIONS.active.find(o=>o.val===v)?.label).join(', '));
  if(state.date.size) parts.push([...state.date].join(', '));
  document.getElementById('gfSummary').textContent = parts.length ? parts.join(' · ') : 'All leads · All time';
}

// ═══════════════════════════════════════════
// DATA FILTERING
// ═══════════════════════════════════════════
// Unified cross-filter multiplier — every dimension affects every chart
function crossMult(){
  const stageFraction  = state.stage.size>0  ? state.stage.size/RAW.stages.length   : 1;
  const sourceFraction = state.source.size>0 ? state.source.size/RAW.sources.length : 1;
  const originFraction = state.origin.size>0 ? state.origin.size/2                  : 1;
  const activeFraction = state.active.size===1 ? (state.active.has('active')?0.743:0.257) : 1;
  return periodMult() * dateWeight() * stageFraction * sourceFraction * originFraction * activeFraction;
}

function getFilteredData(){
  const baseMult = periodMult() * dateWeight();

  // ── Stage ratio: if stages selected, what fraction of total leads do they cover?
  const totalStageCount = RAW.stages.reduce((a,s)=>a+s.count,0);
  const selectedStageCount = state.stage.size>0
    ? RAW.stages.filter(s=>state.stage.has(s.stage)).reduce((a,s)=>a+s.count,0)
    : totalStageCount;
  const stageRatio = selectedStageCount / totalStageCount;  // 1.0 when nothing selected

  // ── Source ratio: if sources selected, what fraction of total leads do they cover?
  const totalSourceCount = RAW.sources.reduce((a,s)=>a+s.count,0);
  const selectedSourceCount = state.source.size>0
    ? RAW.sources.filter(s=>state.source.has(s.source)).reduce((a,s)=>a+s.count,0)
    : totalSourceCount;
  const sourceRatio = selectedSourceCount / totalSourceCount;  // 1.0 when nothing selected

  // ── Origin ratio
  const originSources = state.origin.size>0
    ? RAW.sources.filter(s=>state.origin.has(s.origin))
    : RAW.sources;
  const originRatio = originSources.reduce((a,s)=>a+s.count,0) / totalSourceCount;

  // ── Active ratio
  const activeFrac = state.active.size===1 ? (state.active.has('active')?0.743:0.257) : 1;

  // Combined multiplier for charts that should reflect ALL filters
  const allMult = baseMult * stageRatio * sourceRatio * originRatio * activeFrac;

  // Stages list (filtered + scaled by source/origin/active/period/date)
  let stages = RAW.stages.map(s=>({...s, count:Math.round(s.count * baseMult * sourceRatio * originRatio * activeFrac)}));
  if(state.stage.size>0) stages = stages.filter(s=>state.stage.has(s.stage));

  // Sources list (filtered + scaled by stage/active/period/date)
  let sources = RAW.sources.map(s=>({...s,
    count:      Math.round(s.count      * baseMult * stageRatio * activeFrac),
    interested: Math.round(s.interested * baseMult * stageRatio * activeFrac)
  }));
  if(state.source.size>0) sources = sources.filter(s=>state.source.has(s.source));
  if(state.origin.size>0) sources = sources.filter(s=>state.origin.has(s.origin));

  // Activity cards
  const active   = Math.round(RAW.activeTotal   * allMult * (state.active.has('inactive')&&!state.active.has('active') ? 0 : 1));
  const inactive = Math.round(RAW.inactiveTotal * allMult * (state.active.has('active')&&!state.active.has('inactive') ? 0 : 1));
  const todayNew = Math.round(RAW.todayNew * allMult);

  // Timeline — reflects all filters
  const timeline = RAW.timeline.map(d=>({
    ...d,
    created:   Math.max(1, Math.round(d.created   * allMult)),
    converted: Math.max(0, Math.round(d.converted * allMult))
  }));

  return {stages, sources, active, inactive, todayNew, timeline};
}

// ═══════════════════════════════════════════
// CHARTS
// ═══════════════════════════════════════════
let charts={};

function initCharts(){
  Chart.defaults.font.family="'Times New Roman', Times, serif";
  Chart.defaults.color='#7a7570';
  Chart.register(ChartDataLabels);

  charts.timeline = new Chart(document.getElementById('chartTimeline'),{
    type:'line',
    data:{labels:RAW.timeline.map(d=>d.date),datasets:[
      {label:'Created',data:[],borderColor:'#0d9488',backgroundColor:'rgba(13,148,136,.12)',tension:.4,fill:true,pointRadius:4,pointHoverRadius:7,pointBackgroundColor:'#0d9488'},
      {label:'Converted',data:[],borderColor:'#6366f1',backgroundColor:'rgba(99,102,241,.1)',tension:.4,fill:true,pointRadius:4,pointHoverRadius:7,pointBackgroundColor:'#6366f1'}
    ]},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      onClick:(evt,els)=>{
        if(els && els.length){ const idx=els[0].index; const date=RAW.timeline[idx].date; toggleDate(date); }
      },
      onHover:(evt,els)=>{ evt.native.target.style.cursor = (els&&els.length) ? 'pointer' : 'default'; },
      plugins:{legend:{display:false},datalabels:{display:false},tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${c.raw.toLocaleString()}`}}},
      scales:{x:{grid:{color:'rgba(0,0,0,.04)'}},y:{grid:{color:'rgba(0,0,0,.04)'},beginAtZero:true}}}
  });

  charts.stageDonut = new Chart(document.getElementById('chartStageDonut'),{
    type:'doughnut',
    data:{labels:RAW.stages.map(s=>s.label),datasets:[{data:[],backgroundColor:RAW.stages.map(s=>s.color),borderWidth:2,borderColor:'#fff',hoverOffset:8}]},
    options:{responsive:true,maintainAspectRatio:false,
      onClick:(evt,els)=>{ if(els.length){ const idx=els[0].index; const codes=charts.stageDonut._stageCodes||RAW.stages.map(s=>s.stage); const stg=codes[idx]; if(stg) toggleStage(stg); }},
      onHover:(evt,els)=>{ evt.native.target.style.cursor = els.length ? 'pointer' : 'default'; },
      plugins:{
        legend:{
          position:'bottom',
          labels:{padding:8,font:{size:10}},
          onClick:(evt,item)=>{
            const codes = charts.stageDonut._stageCodes || RAW.stages.map(s=>s.stage);
            const stg = codes[item.index];
            if(stg) toggleStage(stg);
          }
        },
        tooltip:{callbacks:{label:c=>{const total=c.dataset.data.reduce((a,b)=>a+b,0);const pct=total?((c.raw/total)*100).toFixed(1):0;return `${c.label}: ${c.raw.toLocaleString()} (${pct}%)`;}}}
        ,datalabels:{color:'#fff',font:{weight:'bold',size:11},formatter:(val,ctx)=>{const total=ctx.dataset.data.reduce((a,b)=>a+b,0);const pct=total?((val/total)*100).toFixed(1):0;return pct>4?pct+'%':'';}
      }}
      ,cutout:'60%'}
  });

  charts.sourceDonut = new Chart(document.getElementById('chartSourceDonut'),{
    type:'doughnut',
    data:{labels:[],datasets:[{data:[],backgroundColor:RAW.sources.map(s=>s.color),borderWidth:2,borderColor:'#fff',hoverOffset:8}]},
    options:{responsive:true,maintainAspectRatio:false,
      onClick:(evt,els)=>{ if(els.length){ const idx=els[0].index; const lbls=charts.sourceDonut._sourceCodes||[]; const src=lbls[idx]; if(src) toggleSource(src); }},
      onHover:(evt,els)=>{ evt.native.target.style.cursor = els.length ? 'pointer' : 'default'; },
      plugins:{legend:{position:'bottom',labels:{padding:8,font:{size:10}},onClick:(evt,item)=>{ const src=charts.sourceDonut._sourceCodes&&charts.sourceDonut._sourceCodes[item.index]; if(src) toggleSource(src); }},tooltip:{callbacks:{label:c=>{const total=c.dataset.data.reduce((a,b)=>a+b,0);const pct=total?((c.raw/total)*100).toFixed(1):0;return `${c.label}: ${c.raw.toLocaleString()} (${pct}%)`;}}}
        ,datalabels:{color:'#fff',font:{weight:'bold',size:11},formatter:(val,ctx)=>{const total=ctx.dataset.data.reduce((a,b)=>a+b,0);const pct=total?((val/total)*100).toFixed(1):0;return pct>4?pct+'%':'';}
      }},cutout:'55%'}
  });

  charts.originBar = new Chart(document.getElementById('chartOriginBar'),{
    type:'bar',
    data:{labels:['Direct','Broker'],datasets:[{data:[],backgroundColor:['rgba(13,148,136,.75)','rgba(99,102,241,.75)'],borderWidth:0,borderRadius:6}]},
    options:{responsive:true,maintainAspectRatio:false,
      onClick:(evt,els)=>{ if(els.length){ const idx=els[0].index; const codes=charts.originBar._originCodes||['DIRECT','BROKER']; const code=codes[idx]; if(code) toggleOrigin(code); }},
      onHover:(evt,els)=>{ evt.native.target.style.cursor = els.length ? 'pointer' : 'default'; },
      plugins:{legend:{display:false},datalabels:{display:false},tooltip:{callbacks:{label:c=>c.raw.toLocaleString()}}},scales:{x:{grid:{display:false}},y:{grid:{color:'rgba(0,0,0,.04)'}}}}
  });
}

// ═══════════════════════════════════════════
// CROSS-FILTER: chart/card/row clicks feed the same state as the dropdowns
// ═══════════════════════════════════════════
function toggleStage(stage){
  if(state.stage.has(stage)) state.stage.delete(stage);
  else state.stage.add(stage);
  syncGfCheckboxes('stage');
  cascadeFilters(); updateGfButtons(); updateAll();
  updateChartActiveFilterCards();
}

function toggleSource(source){
  if(state.source.has(source)) state.source.delete(source);
  else state.source.add(source);
  syncGfCheckboxes('source');
  cascadeFilters(); updateGfButtons(); updateAll();
  updateChartActiveFilterCards();
}

function toggleOrigin(origin){
  if(state.origin.has(origin) && state.origin.size===1) state.origin.clear();
  else { state.origin.clear(); state.origin.add(origin); }
  syncGfCheckboxes('origin');
  cascadeFilters(); updateGfButtons(); updateAll();
  updateChartActiveFilterCards();
}

function syncGfCheckboxes(key){
  document.querySelectorAll(`#gflist-${key} input`).forEach(cb=>{
    cb.checked = state[key].has(cb.closest('.gf-dd-item').dataset.val);
  });
}

function updateChartActiveFilterCards(){
  document.getElementById('card-stageDonut')?.classList.toggle('chart-active-filter', state.stage.size>0);
  document.getElementById('card-sourceDonut')?.classList.toggle('chart-active-filter', state.source.size>0);
  document.getElementById('card-origin')?.classList.toggle('chart-active-filter', state.origin.size>0);
  document.getElementById('card-timeline')?.classList.toggle('chart-active-filter', state.date.size>0);
}

// ═══════════════════════════════════════════
// COLUMN SORT & FILTER (Table)
// ═══════════════════════════════════════════
function sortTable(tbl, col, btn){
  if(tblSort[tbl].col===col) tblSort[tbl].dir*=-1;
  else { tblSort[tbl].col=col; tblSort[tbl].dir=1; }
  document.querySelectorAll('#sourceTable .th-icon-btn').forEach(b=>b.classList.remove('active-sort'));
  btn.classList.add('active-sort');
  renderTables();
}

let cfd = {tbl:null, col:null, allVals:[], selectedVals:new Set()};

const NUMERIC_COLS = { source: new Set(['count','interested','pct']) };

function openColFilter(evt, tbl, col){
  evt.stopPropagation();
  const btn = evt.currentTarget;
  const r = btn.getBoundingClientRect();
  const dd = document.getElementById('colFilterDropdown');
  const isNumeric = (NUMERIC_COLS[tbl]||new Set()).has(col);

  cfd.tbl=tbl; cfd.col=col;

  const colTitles={label:'Source',count:'Total Leads',interested:'Interested',pct:'Share of Pipeline %'};
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

    const nums = getColValuesExcluding(tbl, col);
    const dataMin = nums.length ? Math.min(...nums) : 0;
    const dataMax = nums.length ? Math.max(...nums) : 0;

    const minEl = document.getElementById('cfdBudgetMin');
    const maxEl = document.getElementById('cfdBudgetMax');
    minEl.placeholder = String(dataMin);
    maxEl.placeholder = String(dataMax);

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
  if(cfd.selectedVals.size>0){ tblColFilter[cfd.tbl][cfd.col]=new Set(cfd.selectedVals); }
  else { delete tblColFilter[cfd.tbl][cfd.col]; }
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
  document.querySelectorAll('.th-icon-btn.active-filter').forEach(b=>b.classList.remove('active-filter'));
  updateGfButtons();
  renderTables();
}

// ═══════════════════════════════════════════
// DEPENDENCY HELPERS
// ═══════════════════════════════════════════
function computeFullRows(tbl){
  const {sources} = getFilteredData();
  const totalLeads = sources.reduce((a,s)=>a+s.count,0);
  return sources.map(s=>({...s, pct: totalLeads ? +(s.count/totalLeads*100).toFixed(1) : 0 }));
}

function applyAllColFilters(rows, tbl, excludeCol){
  Object.keys(tblColFilter[tbl]).forEach(col=>{
    if(col===excludeCol) return;
    const allowed = tblColFilter[tbl][col];
    if(allowed && allowed.size>0) rows = rows.filter(r=>allowed.has(String(r[col]||'')));
  });
  const rf = tblRangeFilter[tbl]||{};
  Object.keys(rf).forEach(col=>{
    if(col===excludeCol) return;
    const range = rf[col]||{};
    if(range.min !== null && range.min !== undefined) rows = rows.filter(r=>Number(r[col])>=range.min);
    if(range.max !== null && range.max !== undefined) rows = rows.filter(r=>Number(r[col])<=range.max);
  });
  return rows;
}

function getRowsExcluding(tbl, excludeCol){ return applyAllColFilters(computeFullRows(tbl), tbl, excludeCol); }
function getColValuesExcluding(tbl, col){ return getRowsExcluding(tbl, col).map(r=>Number(r[col])).filter(v=>!isNaN(v)); }

function updateAll(){
  const {stages, sources, active, inactive, todayNew, timeline} = getFilteredData();
  const totalLeads = sources.reduce((a,s)=>a+s.count,0);

  // Activity cards
  document.getElementById('act-active').textContent = active.toLocaleString();
  document.getElementById('act-inactive').textContent = inactive.toLocaleString();
  document.getElementById('act-todayNew').textContent = todayNew.toLocaleString();

  // Stage KPI Cards
  const stageTotal = stages.reduce((a,s)=>a+s.count,0);
  renderStageKpis(stages, stageTotal);

  // Timeline — when a date is selected, show only that point/segment, not the rest of the line
  const dateSelected = state.date.size>0;
  const timelineFiltered = dateSelected ? timeline.filter(d=>state.date.has(d.date)) : timeline;
  charts.timeline.data.labels = timelineFiltered.map(d=>d.date);
  charts.timeline.data.datasets[0].data = timelineFiltered.map(d=>d.created);
  charts.timeline.data.datasets[1].data = timelineFiltered.map(d=>d.converted);
  charts.timeline.data.datasets[0].pointRadius = dateSelected ? 6 : 4;
  charts.timeline.data.datasets[1].pointRadius = dateSelected ? 6 : 4;
  // single point alone has nothing to draw a line to/from — show it as a dot, not a degenerate line
  charts.timeline.data.datasets[0].showLine = timelineFiltered.length>1;
  charts.timeline.data.datasets[1].showLine = timelineFiltered.length>1;
  charts.timeline.update('active');
  document.getElementById('card-timeline')?.classList.toggle('chart-active-filter', dateSelected);

  // ── Stage Donut — filtered by source/origin; slices = selected stages only ──
  const stageSelected = state.stage.size>0;
  const srcFiltered   = state.source.size>0 || state.origin.size>0;
  const pm = periodMult() * dateWeight();

  // Which sources are currently active (respecting source + origin filters)
  const activeSrcs = RAW.sources.filter(s=>
    (state.source.size===0 || state.source.has(s.source)) &&
    (state.origin.size===0 || state.origin.has(s.origin))
  );

  // Stage counts: sum only from active sources using the breakdown table
  const stageCounts = {};
  RAW.stages.forEach(s=>{ stageCounts[s.stage] = 0; });
  activeSrcs.forEach(src=>{
    const bd = RAW.sourceStages[src.source]||{};
    RAW.stages.forEach(stg=>{ stageCounts[stg.stage] += (bd[stg.stage]||0); });
  });

  // If no source filter, fall back to RAW counts
  const stageData = RAW.stages.map(s=>({
    ...s,
    count: Math.round((srcFiltered ? stageCounts[s.stage] : s.count) * pm)
  }));

  // Show only selected stages (or all if nothing selected)
  const stagesShown = stageSelected
    ? stageData.filter(s=>state.stage.has(s.stage))
    : stageData.filter(s=>s.count>0);

  charts.stageDonut.data.labels = stagesShown.map(s=>s.label);
  charts.stageDonut.data.datasets[0].data = stagesShown.map(s=>s.count);
  charts.stageDonut.data.datasets[0].backgroundColor = stagesShown.map(s=>s.color);
  charts.stageDonut._stageCodes = stagesShown.map(s=>s.stage);
  charts.stageDonut.update('active');
  document.getElementById('donutCenterVal').textContent = stageTotal.toLocaleString();

  // ── Source Donut — filtered by stage; slices = selected sources only ──
  const sourceSelected = state.source.size>0;
  const stgFiltered    = state.stage.size>0;

  // Source counts: sum only from selected stages using the breakdown table
  const sourceData = RAW.sources.map(src=>{
    const bd = RAW.sourceStages[src.source]||{};
    const cnt = stgFiltered
      ? RAW.stages.filter(s=>state.stage.has(s.stage)).reduce((a,s)=>a+(bd[s.stage]||0),0)
      : src.count;
    return {...src, count: Math.round(cnt * pm)};
  });

  // Show only selected sources (or all with >0 count)
  const sourcesShown = sourceSelected
    ? sourceData.filter(s=>state.source.has(s.source))
    : sourceData.filter(s=>s.count>0);

  charts.sourceDonut.data.labels = sourcesShown.map(s=>s.label);
  charts.sourceDonut.data.datasets[0].data = sourcesShown.map(s=>s.count);
  charts.sourceDonut.data.datasets[0].backgroundColor = sourcesShown.map(s=>s.color);
  charts.sourceDonut._sourceCodes = sourcesShown.map(s=>s.source);
  charts.sourceDonut.update('active');
  document.getElementById('sourceCenterVal').textContent = sourcesShown.length;

  // Origin — scale by stage + source + active + period + date
  const _totalStageCnt3 = RAW.stages.reduce((a,s)=>a+s.count,0);
  const _selStageCnt3   = state.stage.size>0 ? RAW.stages.filter(s=>state.stage.has(s.stage)).reduce((a,s)=>a+s.count,0) : _totalStageCnt3;
  const _stgRatio3      = _selStageCnt3 / _totalStageCnt3;
  const _totalSrcCnt3   = RAW.sources.reduce((a,s)=>a+s.count,0);
  const _selSrcCnt3     = state.source.size>0 ? RAW.sources.filter(s=>state.source.has(s.source)).reduce((a,s)=>a+s.count,0) : _totalSrcCnt3;
  const _srcRatio3      = _selSrcCnt3 / _totalSrcCnt3;
  const _actFrac3       = state.active.size===1 ? (state.active.has('active')?0.743:0.257) : 1;
  const _originMult3    = periodMult() * dateWeight() * _stgRatio3 * _srcRatio3 * _actFrac3;
  const originRows = RAW.sources.map(s=>({...s, count: Math.round(s.count * _originMult3)}));
  const direct = originRows.filter(s=>s.origin==='DIRECT' && (state.origin.size===0||state.origin.has('DIRECT'))).reduce((a,s)=>a+s.count,0);
  const broker = originRows.filter(s=>s.origin==='BROKER' && (state.origin.size===0||state.origin.has('BROKER'))).reduce((a,s)=>a+s.count,0);
  const originTotal = direct+broker;
  const originSelected = state.origin.size>0;
  const originLabelsAll = ['Direct','Broker'];
  const originValsAll = [direct,broker];
  const originColorsAll = ['rgba(13,148,136,.75)','rgba(99,102,241,.75)'];
  const originKeep = originSelected ? [0,1].filter(i=> state.origin.has(i===0?'DIRECT':'BROKER')) : [0,1];
  charts.originBar.data.labels = originKeep.map(i=>originLabelsAll[i]);
  charts.originBar.data.datasets[0].data = originKeep.map(i=>originValsAll[i]);
  charts.originBar.data.datasets[0].backgroundColor = originKeep.map(i=>originColorsAll[i]);
  charts.originBar._originCodes = originKeep.map(i=> i===0?'DIRECT':'BROKER');
  charts.originBar.update('active');
  renderOriginSplit(direct,broker,originTotal);

  // Table
  renderTables();

  // Keep card border highlights in sync with filter state
  updateChartActiveFilterCards();

  toUpdateTotalActiveLabel(totalLeads);
}

function toUpdateTotalActiveLabel(totalLeads){
  // keep donut center label accurate when stage filter narrows the pipeline view
  const label = document.querySelector('#card-stageDonut .donut-center-label');
  if(label) label.textContent = state.stage.size>0 ? 'Filtered Total' : 'Total Active';
}

function renderStageKpis(stages,total){
  const grid=document.getElementById('stageKpiGrid');
  if(!stages.length){ grid.innerHTML='<p style="color:var(--clr-text-sub);font-size:.82rem;padding:12px 0;">No stages match the selected filters.</p>'; return; }
  grid.innerHTML=stages.map(s=>{
    const pct=total?((s.count/total)*100).toFixed(1):0;
    const isActive=state.stage.has(s.stage);
    const meta = STAGE_META[s.stage] || {iconClass:'slate',icon:''};
    return `<div class="kpi-card${isActive?' kpi-active':''}" onclick="toggleStage('${s.stage}')" title="Click to filter the dashboard by ${s.label}">
      <div class="kpi-icon ${meta.iconClass}"><svg viewBox="0 0 24 24">${meta.icon}</svg></div>
      <div class="kpi-card-body">
        <div class="kpi-value">${s.count.toLocaleString()}</div>
        <div class="kpi-label">${s.label}</div>
        <div class="kpi-pct">${pct}% of pipeline</div>
      </div>
    </div>`;
  }).join('');
}

function renderOriginSplit(direct,broker,total){
  const dPct=total?Math.round(direct/total*100):0;
  const bPct=100-dPct;
  const originSelected = state.origin.size>0;
  const directSel = state.origin.has('DIRECT');
  const brokerSel = state.origin.has('BROKER');
  document.getElementById('originSplit').innerHTML=`
    <div class="origin-card${directSel?' origin-selected':''}${originSelected&&!directSel?' origin-dim':''}" onclick="toggleOrigin('DIRECT')" title="Click to filter by Direct origin">
      <div class="origin-val" style="color:var(--teal)">${direct.toLocaleString()}</div>
      <div class="origin-label">Direct</div>
      <div class="origin-pct" style="color:var(--teal)">${dPct}%</div>
      <div class="origin-bar" style="background:var(--teal);width:${dPct}%;"></div>
    </div>
    <div class="origin-card${brokerSel?' origin-selected':''}${originSelected&&!brokerSel?' origin-dim':''}" onclick="toggleOrigin('BROKER')" title="Click to filter by Broker origin">
      <div class="origin-val" style="color:var(--indigo)">${broker.toLocaleString()}</div>
      <div class="origin-label">Broker</div>
      <div class="origin-pct" style="color:var(--indigo)">${bPct}%</div>
      <div class="origin-bar" style="background:var(--indigo);width:${bPct}%;"></div>
    </div>`;
}

function renderTables(){
  let sourceRows = computeFullRows('source');
  Object.keys(tblColFilter.source).forEach(col=>{
    const allowed = tblColFilter.source[col];
    if(allowed && allowed.size>0) sourceRows = sourceRows.filter(r=>allowed.has(String(r[col]||'')));
  });
  Object.keys(tblRangeFilter.source||{}).forEach(col=>{
    const rf = tblRangeFilter.source[col]||{};
    if(rf.min !== null && rf.min !== undefined) sourceRows = sourceRows.filter(r=>Number(r[col])>=rf.min);
    if(rf.max !== null && rf.max !== undefined) sourceRows = sourceRows.filter(r=>Number(r[col])<=rf.max);
  });
  sourceRows.sort((a,b)=>{ const c=tblSort.source.col; const v=a[c]>b[c]?1:a[c]<b[c]?-1:0; return v*tblSort.source.dir; });

  renderSourceTable(sourceRows);
}

function renderSourceTable(sources){
  const body=document.getElementById('sourceTableBody');
  if(!sources.length){ body.innerHTML='<tr><td colspan="4" style="text-align:center;color:var(--clr-text-sub);padding:24px;font-style:italic;">No sources match the selected filters.</td></tr>'; return; }
  const anySelected = state.source.size>0;
  body.innerHTML = sources.map(s=>{
    const isSelected = state.source.has(s.source);
    const rowClass = isSelected ? ' class="row-selected"' : (anySelected ? ' class="row-dim"' : '');
    return `<tr${rowClass} onclick="toggleSource('${s.source}')" title="Click to filter the dashboard by ${s.label}">
      <td style="text-align:left;font-weight:600;"><span class="src-dot" style="background:${s.color}"></span>${s.label}</td>
      <td>${s.count.toLocaleString()}</td>
      <td>${s.interested.toLocaleString()}</td>
      <td>
        <div class="progress-wrap">
          <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${s.pct}%;background:${s.color};"></div></div>
          <span class="progress-pct">${s.pct}%</span>
        </div>
      </td>
    </tr>`;
  }).join('');
}

// ═══════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════
function toast(msg){
  const c=document.getElementById('toast-container');
  const t=document.createElement('div');t.className='toast';
  t.innerHTML=`<div class="toast-icon"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div><span class="toast-msg">${msg}</span>`;
  c.appendChild(t);setTimeout(()=>t.remove(),2500);
}

function exportReport(){
  const {sources} = getFilteredData();
  const totalLeads = sources.reduce((a,s)=>a+s.count,0);
  const rows=[['Source','Total Leads','Interested','Share %'],
    ...sources.map(s=>[s.label,s.count,s.interested, totalLeads?(s.count/totalLeads*100).toFixed(1):0])];
  const csv=rows.map(r=>r.join(',')).join('\n');
  const a=document.createElement('a');a.href='data:text/csv,'+encodeURIComponent(csv);a.download='leads-analysis.csv';a.click();
  toast('Report exported as CSV');
}

// ═══════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════

// Plugin: style Stage Distribution legend items to reflect active filter selections
Chart.register({
  id: 'stageLegendStyle',
  afterDraw(chart) {
    if (chart.canvas.id !== 'chartStageDonut') return;
    const legendItems = chart.legend && chart.legend.legendItems;
    if (!legendItems || !legendItems.length) return;
    const codes = chart._stageCodes || RAW.stages.map(s=>s.stage);
    const anyActive = state.stage.size > 0;
    legendItems.forEach((item, i) => {
      const code = codes[i];
      const isActive = code && state.stage.has(code);
      // Dim unselected items when a filter is active
      item.fontColor = anyActive && !isActive ? 'rgba(122,117,112,0.35)' : '#7a7570';
      item.strokeStyle = anyActive && !isActive
        ? item.fillStyle.replace(/[\d.]+\)$/, '0.35)')
        : item.fillStyle;
    });
  }
});

// ═══════════════════════════════════════════
// INIT — fetch live figures, then build the dashboard
// ═══════════════════════════════════════════
fetch(window.ANALYSIS_CFG.dataUrl, {headers:{'X-Requested-With':'XMLHttpRequest'}})
  .then(r=>r.json())
  .then(d=>{
    const stageCounts = d.stageCounts || {};
    RAW.stages = STAGE_DEFS.map(def=>({...def, count: stageCounts[def.stage] || 0}));
    RAW.sources = (d.sources || []).map((s,i)=>({...s, color: SOURCE_COLORS[i % SOURCE_COLORS.length]}));
    RAW.timeline = d.timeline || [];
    RAW.sourceStages = d.sourceStages || {};
    RAW.activeTotal = d.activeTotal || 0;
    RAW.inactiveTotal = d.inactiveTotal || 0;
    RAW.todayNew = d.todayNew || 0;

    STAGE_LABELS = Object.fromEntries(RAW.stages.map(s=>[s.stage,s.label]));
    STAGE_META = Object.fromEntries(RAW.stages.map(s=>[s.stage,{iconClass:s.iconClass,icon:s.icon}]));
    SOURCE_LABELS = Object.fromEntries(RAW.sources.map(s=>[s.source,s.label]));
    GF_OPTIONS.stage = RAW.stages.map(s=>({val:s.stage,label:s.label}));
    GF_OPTIONS.source = RAW.sources.map(s=>({val:s.source,label:s.label}));

    buildGfLists();
    initCharts();
    updateGfButtons();
    updateAll();
  })
  .catch(()=>toast('Could not load analysis data'));

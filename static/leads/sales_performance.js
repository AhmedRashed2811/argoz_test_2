// ═══════════════════════════════════════════
// RAW DATA — loaded via AJAX from the sales-performance endpoint
// ═══════════════════════════════════════════
let RAW = { sales:[], teams:[], funnel:[] };

let TEAM_LABELS = {};

// ═══════════════════════════════════════════
// FILTER STATE
// ═══════════════════════════════════════════
const GF_OPTIONS = {
  period: [{val:'all',label:'All Time'},{val:'q1',label:'Q1 2026'},{val:'q2',label:'Q2 2026'},{val:'ytd',label:'YTD'},{val:'last30',label:'Last 30 Days'}],
  team:   [],
  sla:    [{val:'compliant',label:'Compliant ≥90%'},{val:'at-risk',label:'At Risk 75–90%'},{val:'breached',label:'Breached <75%'}],
  perf:   [{val:'all',label:'All'},{val:'top3',label:'Top 3'},{val:'top5',label:'Top 5'}],
};

const state = {
  period: new Set(['all']),
  team:   new Set(),
  sla:    new Set(),
  perf:   new Set(['all']),
  person: new Set(), // cross-filter: set by clicking leaderboard / bar / scatter / table rows
};

// table sort state
const tblSort = {
  team:  {col:'name', dir:1},
  sales: {col:'conv', dir:-1},
};
// table column filters
const tblColFilter = { team:{}, sales:{} };
// per-table per-column range filters
const tblRangeFilter = { team:{}, sales:{} };
// legacy alias
const tblBudgetFilter = { team:{min:null,max:null}, sales:{min:null,max:null} };

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
        <input type="checkbox" id="gf-${key}-${opt.val}" ${(key==='period'||key==='perf')&&opt.val==='all'?'checked':''}>
        <label for="gf-${key}-${opt.val}">${opt.label}</label>
      </div>`).join('');
    list.querySelectorAll('input[type=checkbox]').forEach(cb=>{
      cb.addEventListener('change', ()=>handleGfChange(key, cb.closest('.gf-dd-item').dataset.val, cb.checked));
    });
  });
  state.period.add('all');
  state.perf.add('all');
}

function handleGfChange(key, val, checked){
  if(key==='period' || key==='perf'){
    state[key].clear();
    document.querySelectorAll('#gflist-'+key+' input').forEach(cb=>{cb.checked=false;});
    if(checked){ state[key].add(val); document.getElementById('gf-'+key+'-'+val).checked=true; }
    else { state[key].add('all'); document.getElementById('gf-'+key+'-all').checked=true; }
  } else {
    if(checked) state[key].add(val);
    else state[key].delete(val);
  }
  cascadeFilters();
  updateGfButtons();
  updateAll();
}

function periodMult(){ const p=[...state.period][0]||'all'; return {all:1,q1:.45,q2:.55,ytd:.8,last30:.18}[p]||1; }

function cascadeFilters(){ updateGfAvailability(); }

// returns sales rows with period scaling applied, filtered by team/sla/person EXCLUDING the given key
function getSalesExcluding(excludeKey){
  const mult = periodMult();
  let sales = RAW.sales.map(s=>({...s, assigned:Math.round(s.assigned*mult), interested:Math.round(s.interested*mult)}));
  if(excludeKey!=='team' && state.team.size>0) sales = sales.filter(s=>state.team.has(s.team));
  if(excludeKey!=='sla' && state.sla.size>0){
    sales = sales.filter(s=>{
      const bucket = s.sla>=90?'compliant':s.sla>=75?'at-risk':'breached';
      return state.sla.has(bucket);
    });
  }
  if(excludeKey!=='person' && state.person.size>0) sales = sales.filter(s=>state.person.has(s.id));
  return sales;
}

function updateGfAvailability(){
  // SLA options depend on team/person filter
  const salesForSla = getSalesExcluding('sla');
  const availSla = new Set(salesForSla.map(s=> s.sla>=90?'compliant':s.sla>=75?'at-risk':'breached'));
  document.querySelectorAll('#gflist-sla .gf-dd-item').forEach(el=>{
    const val = el.dataset.val;
    const available = availSla.has(val);
    el.classList.toggle('disabled', !available);
    if(!available && state.sla.has(val)){
      state.sla.delete(val);
      const cb=document.getElementById('gf-sla-'+val);
      if(cb) cb.checked=false;
    }
  });

  // Team options depend on SLA/person filter
  const salesForTeam = getSalesExcluding('team');
  const availTeams = new Set(salesForTeam.map(s=>s.team));
  document.querySelectorAll('#gflist-team .gf-dd-item').forEach(el=>{
    const val = el.dataset.val;
    const available = availTeams.has(val);
    el.classList.toggle('disabled', !available);
    if(!available && state.team.has(val)){
      state.team.delete(val);
      const cb=document.getElementById('gf-team-'+val);
      if(cb) cb.checked=false;
    }
  });

  // If the selected person is no longer in the filtered set (team/sla excluded them), drop it
  if(state.person.size>0){
    const salesForPerson = getSalesExcluding('person');
    const availIds = new Set(salesForPerson.map(s=>s.id));
    [...state.person].forEach(id=>{ if(!availIds.has(id)) state.person.delete(id); });
  }

  // Period & Perf always fully available
  document.querySelectorAll('#gflist-period .gf-dd-item').forEach(el=>el.classList.remove('disabled'));
  document.querySelectorAll('#gflist-perf .gf-dd-item').forEach(el=>el.classList.remove('disabled'));
}

function selectAllGf(key){
  if(key==='period' || key==='perf'){
    state[key].clear(); state[key].add('all');
    document.querySelectorAll('#gflist-'+key+' input').forEach(cb=>{ cb.checked = cb.closest('.gf-dd-item').dataset.val==='all'; });
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
  if(key==='period' || key==='perf'){ state[key].add('all'); document.getElementById('gf-'+key+'-all').checked=true; }
  cascadeFilters();
  updateGfButtons();
  updateAll();
}

function clearAllFilters(){
  ['team','sla'].forEach(k=>{ state[k].clear(); document.querySelectorAll('#gflist-'+k+' input').forEach(cb=>cb.checked=false); });
  state.person.clear();
  updateChartActiveFilterCards();
  ['period','perf'].forEach(k=>{
    state[k].clear(); state[k].add('all');
    document.querySelectorAll('#gflist-'+k+' input').forEach(cb=>{ cb.checked=cb.closest('.gf-dd-item').dataset.val==='all'; });
  });
  tblColFilter.team={}; tblColFilter.sales={};
  tblRangeFilter.team={}; tblRangeFilter.sales={};
  tblBudgetFilter.team={min:null,max:null}; tblBudgetFilter.sales={min:null,max:null};
  ['cfdBudgetMin','cfdBudgetMax'].forEach(id=>{ const el=document.getElementById(id); if(el) el.value=''; });
  document.querySelectorAll('.th-icon-btn.active-filter,.th-icon-btn.active-sort').forEach(b=>b.classList.remove('active-filter','active-sort'));
  cascadeFilters(); updateGfButtons(); updateAll();
  toast('All filters cleared');
}

function updateGfButtons(){
  const labels = {
    period: p=>{ if(p==='all') return 'All Time'; return GF_OPTIONS.period.find(o=>o.val===p)?.label||p; },
    team: ()=> state.team.size===0?'All Teams': state.team.size===1? GF_OPTIONS.team.find(o=>state.team.has(o.val))?.label : state.team.size+' Teams',
    sla: ()=> state.sla.size===0?'All Statuses': state.sla.size===1? GF_OPTIONS.sla.find(o=>state.sla.has(o.val))?.label : state.sla.size+' Statuses',
    perf: p=>{ if(p==='all') return 'All'; return GF_OPTIONS.perf.find(o=>o.val===p)?.label||p; },
  };
  const periodVal = [...state.period][0]||'all';
  const perfVal = [...state.perf][0]||'all';
  document.getElementById('gfsb-period-txt').textContent = labels.period(periodVal);
  document.getElementById('gfsb-team-txt').textContent = labels.team();
  document.getElementById('gfsb-sla-txt').textContent = labels.sla();
  document.getElementById('gfsb-perf-txt').textContent = labels.perf(perfVal);

  document.getElementById('gfsb-team').classList.toggle('has-selection', state.team.size>0);
  document.getElementById('gfsb-sla').classList.toggle('has-selection', state.sla.size>0);
  document.getElementById('gfsb-period').classList.toggle('has-selection', periodVal!=='all');
  document.getElementById('gfsb-perf').classList.toggle('has-selection', perfVal!=='all');

  updateChips();
  updateSummary();
}

function updateChips(){
  const chips = document.getElementById('activeChips');
  let html='';
  const periodVal = [...state.period][0]||'all';
  const perfVal = [...state.perf][0]||'all';
  if(periodVal!=='all') html+=`<span class="chip">Period: ${GF_OPTIONS.period.find(o=>o.val===periodVal)?.label} <span class="chip-x" onclick="clearGf('period')">✕</span></span>`;
  state.team.forEach(v=>{ const l=GF_OPTIONS.team.find(o=>o.val===v)?.label||v; html+=`<span class="chip">Team: ${l} <span class="chip-x" onclick="removeGfVal('team','${v}')">✕</span></span>`; });
  state.sla.forEach(v=>{ const l=GF_OPTIONS.sla.find(o=>o.val===v)?.label||v; html+=`<span class="chip">SLA: ${l} <span class="chip-x" onclick="removeGfVal('sla','${v}')">✕</span></span>`; });
  if(perfVal!=='all') html+=`<span class="chip">Performers: ${GF_OPTIONS.perf.find(o=>o.val===perfVal)?.label} <span class="chip-x" onclick="clearGf('perf')">✕</span></span>`;
  state.person.forEach(id=>{ const p=RAW.sales.find(s=>s.id===id); if(p) html+=`<span class="chip">Rep: ${p.name} <span class="chip-x" onclick="removePerson(${id})">✕</span></span>`; });
  Object.keys(tblColFilter.team).forEach(col=>{ if(tblColFilter.team[col].size>0) html+=`<span class="chip">Team Tbl/${col} filter <span class="chip-x" onclick="clearColFilter('team','${col}')">✕</span></span>`; });
  Object.keys(tblColFilter.sales).forEach(col=>{ if(tblColFilter.sales[col].size>0) html+=`<span class="chip">Sales Tbl/${col} filter <span class="chip-x" onclick="clearColFilter('sales','${col}')">✕</span></span>`; });
  Object.keys(tblRangeFilter.team||{}).forEach(col=>{ const rf=tblRangeFilter.team[col]||{}; if(rf.min!==null&&rf.min!==undefined||rf.max!==null&&rf.max!==undefined) html+=`<span class="chip">Team Tbl/${col} range <span class="chip-x" onclick="clearRangeFilter('team','${col}')">✕</span></span>`; });
  Object.keys(tblRangeFilter.sales||{}).forEach(col=>{ const rf=tblRangeFilter.sales[col]||{}; if(rf.min!==null&&rf.min!==undefined||rf.max!==null&&rf.max!==undefined) html+=`<span class="chip">Sales Tbl/${col} range <span class="chip-x" onclick="clearRangeFilter('sales','${col}')">✕</span></span>`; });
  chips.innerHTML = html;
}

function removeGfVal(key, val){
  state[key].delete(val);
  const cb = document.getElementById('gf-'+key+'-'+val);
  if(cb) cb.checked=false;
  cascadeFilters(); updateGfButtons(); updateAll();
}

// ── Cross-filter: click a chart/leaderboard/row to filter by salesperson ──
function togglePerson(id){
  const wasSelected = state.person.has(id);
  if(wasSelected) state.person.delete(id);
  else { state.person.clear(); state.person.add(id); } // single-select cross-filter
  cascadeFilters(); updateGfButtons(); updateAll();
  updateChartActiveFilterCards();
  const p = RAW.sales.find(s=>s.id===id);
  toast(wasSelected ? 'Salesperson filter cleared' : `Filtered by: ${p?.name||id}`);
}

function removePerson(id){
  state.person.delete(id);
  cascadeFilters(); updateGfButtons(); updateAll();
  updateChartActiveFilterCards();
}

function updateChartActiveFilterCards(){
  const cardIds=['card-leaderboard','card-leaderBar','card-scatter'];
  cardIds.forEach(id=>document.getElementById(id)?.classList.remove('chart-active-filter'));
  if(state.person.size>0) cardIds.forEach(id=>document.getElementById(id)?.classList.add('chart-active-filter'));
}

// ── Cross-filter: click a team row/segment to filter by team (reuses global team filter) ──
function toggleTeam(teamVal){
  if(state.team.has(teamVal) && state.team.size===1) state.team.clear();
  else { state.team.clear(); state.team.add(teamVal); }
  document.querySelectorAll('#gflist-team input').forEach(cb=>{
    cb.checked = state.team.has(cb.closest('.gf-dd-item').dataset.val);
  });
  cascadeFilters(); updateGfButtons(); updateAll();
}

function clearColFilter(tbl, col){ if(tblColFilter[tbl]) delete tblColFilter[tbl][col]; updateGfButtons(); renderTables(); }
function clearRangeFilter(tbl, col){ if(tblRangeFilter[tbl]) delete tblRangeFilter[tbl][col]; updateGfButtons(); renderTables(); }

function updateSummary(){
  const parts=[];
  const periodVal=[...state.period][0]||'all';
  const perfVal=[...state.perf][0]||'all';
  if(periodVal!=='all') parts.push(GF_OPTIONS.period.find(o=>o.val===periodVal)?.label||periodVal);
  if(state.team.size) parts.push([...state.team].map(v=>GF_OPTIONS.team.find(o=>o.val===v)?.label).join(', '));
  if(state.sla.size) parts.push([...state.sla].map(v=>GF_OPTIONS.sla.find(o=>o.val===v)?.label).join(', '));
  if(perfVal!=='all') parts.push(GF_OPTIONS.perf.find(o=>o.val===perfVal)?.label);
  document.getElementById('gfSummary').textContent = parts.length ? parts.join(' · ') : 'All teams · All time';
}

// ═══════════════════════════════════════════
// DATA FILTERING
// ═══════════════════════════════════════════
function getFilteredData(){
  let sales = getSalesExcluding(null);
  let teams = [...RAW.teams];
  if(state.team.size>0) teams = teams.filter(t=>state.team.has(t.team));

  const perfVal=[...state.perf][0]||'all';
  if(perfVal==='top3') sales=[...sales].sort((a,b)=>b.conv-a.conv).slice(0,3);
  else if(perfVal==='top5') sales=[...sales].sort((a,b)=>b.conv-a.conv).slice(0,5);

  const mult = periodMult();
  const funnel = RAW.funnel.map(f=>({...f, val:Math.round(f.val*mult)}));

  return {sales, teams, funnel};
}

// ═══════════════════════════════════════════
// CHARTS
// ═══════════════════════════════════════════
let charts={};

function initCharts(){
  Chart.defaults.font.family="'Times New Roman', Times, serif";
  Chart.defaults.color='#7a7570';

  charts.leaderBar = new Chart(document.getElementById('chartLeaderBar'),{
    type:'bar',
    data:{labels:[],datasets:[
      {label:'Assigned Leads',data:[],backgroundColor:'rgba(224,123,32,.25)',borderColor:'rgba(224,123,32,.5)',borderWidth:1,borderRadius:4},
      {label:'Interested Leads',data:[],backgroundColor:'rgba(224,123,32,.8)',borderColor:'#e07b20',borderWidth:1,borderRadius:4}
    ]},
    options:{
      indexAxis:'y',responsive:true,
      onClick:(evt,elements)=>{
        if(!elements.length) return;
        const idx = elements[0].index;
        const id = charts.leaderBar._rowIds?.[idx];
        if(id!==undefined) togglePerson(id);
      },
      onHover:(evt,elements)=>{ evt.native.target.style.cursor = elements.length ? 'pointer' : 'default'; },
      plugins:{legend:{display:false}},
      scales:{x:{grid:{color:'rgba(0,0,0,.04)'}},y:{grid:{display:false}}}
    }
  });

  charts.scatter = new Chart(document.getElementById('chartScatter'),{
    type:'bubble',
    data:{datasets:[]},
    options:{
      responsive:true,
      onClick:(evt,elements)=>{
        if(!elements.length) return;
        const point = elements[0];
        const id = charts.scatter.data.datasets[point.datasetIndex]?.data?.[point.index]?.id;
        if(id!==undefined) togglePerson(id);
      },
      onHover:(evt,elements)=>{ evt.native.target.style.cursor = elements.length ? 'pointer' : 'default'; },
      plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>`${c.raw.name||c.dataset.label}: ${c.raw.y}% SLA, ${c.raw.x}min resp`}}},
      scales:{x:{title:{display:true,text:'Avg Response Time (mins)',font:{size:11}},grid:{color:'rgba(0,0,0,.04)'},min:0,max:65},y:{title:{display:true,text:'SLA Compliance %',font:{size:11}},grid:{color:'rgba(0,0,0,.04)'},min:60,max:100,ticks:{callback:v=>v+'%'}}}
    }
  });
}

// ═══════════════════════════════════════════
// COLUMN SORT & FILTER (Tables)
// ═══════════════════════════════════════════
function sortTable(tbl, col, btn){
  if(tblSort[tbl].col===col) tblSort[tbl].dir*=-1;
  else { tblSort[tbl].col=col; tblSort[tbl].dir=1; }
  document.querySelectorAll(`#${tbl==='team'?'teamSla':'sales'}Table .th-icon-btn`).forEach(b=>b.classList.remove('active-sort'));
  btn.classList.add('active-sort');
  renderTables();
}

let cfd = {tbl:null, col:null, allVals:[], selectedVals:new Set()};

const NUMERIC_COLS = {
  team:  new Set(['total','completed','breached','comp']),
  sales: new Set(['assigned','interested','conv','sla','response'])
};

function openColFilter(evt, tbl, col){
  evt.stopPropagation();
  const btn = evt.currentTarget;
  const r = btn.getBoundingClientRect();
  const dd = document.getElementById('colFilterDropdown');
  const isNumeric = (NUMERIC_COLS[tbl]||new Set()).has(col);

  cfd.tbl=tbl; cfd.col=col;

  const colTitles={name:tbl==='team'?'Team':'Salesperson',total:'Leads (SLA)',completed:'Completed',breached:'Breached',comp:'Compliance Rate %',status:'Status',teamLabel:'Team',assigned:'Assigned Leads',interested:'Interested Leads',conv:'Conversion Rate %',sla:'SLA Compliance %',response:'Avg. Response (mins)'};
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
  const {sales, teams} = getFilteredData();
  if(tbl==='sales'){
    return sales.map(s=>({...s, teamLabel: TEAM_LABELS[s.team]||s.team}));
  } else {
    return teams.map(t=>{
      const completed = t.total - t.breached;
      const status = t.comp>=90?'Compliant':t.comp>=75?'At Risk':'Breached';
      return {...t, completed, status};
    });
  }
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
  const {sales, teams, funnel} = getFilteredData();

  const totalAssigned = sales.reduce((a,s)=>a+s.assigned,0);
  const totalInterested = sales.reduce((a,s)=>a+s.interested,0);
  const avgSla = sales.length ? (sales.reduce((a,s)=>a+s.sla,0)/sales.length).toFixed(1) : '0.0';
  const velRows = sales.filter(s=>s.velocity>0);
  const avgVel = velRows.length ? (velRows.reduce((a,s)=>a+s.velocity,0)/velRows.length).toFixed(1) : '0.0';

  document.getElementById('kpi-velocity').textContent = avgVel + ' hrs';
  document.getElementById('kpi-sla').textContent = avgSla + '%';
  document.getElementById('kpi-assigned').textContent = totalAssigned.toLocaleString();
  document.getElementById('kpi-interested').textContent = totalInterested.toLocaleString();

  // Bar chart
  charts.leaderBar.data.labels = sales.map(s=>s.name.split(' ')[0]);
  charts.leaderBar.data.datasets[0].data = sales.map(s=>s.assigned);
  charts.leaderBar.data.datasets[1].data = sales.map(s=>s.interested);
  charts.leaderBar._rowIds = sales.map(s=>s.id);
  const barSelected = state.person.size>0;
  charts.leaderBar.data.datasets[0].backgroundColor = sales.map(s=> !barSelected || state.person.has(s.id) ? 'rgba(224,123,32,.25)' : 'rgba(180,175,168,.18)');
  charts.leaderBar.data.datasets[1].backgroundColor = sales.map(s=> !barSelected || state.person.has(s.id) ? 'rgba(224,123,32,.8)' : 'rgba(180,175,168,.45)');
  charts.leaderBar.update('active');

  // Scatter
  const scatterSelected = state.person.size>0;
  const colors = sales.map(s=>{
    const dim = scatterSelected && !state.person.has(s.id);
    if(dim) return 'rgba(180,175,168,.35)';
    if(s.sla>=90&&s.response<=25) return 'rgba(16,185,129,.8)';
    if(s.sla>=90&&s.response>25) return 'rgba(245,158,11,.8)';
    if(s.sla<90&&s.response<=25) return 'rgba(6,182,212,.8)';
    return 'rgba(244,63,94,.8)';
  });
  charts.scatter.data.datasets = [{
    label:'Salesperson',
    data:sales.map(s=>({x:s.response,y:s.sla,r:Math.max(6,s.assigned/12),id:s.id,name:s.name})),
    backgroundColor:colors,
    borderColor:colors.map(c=>c.startsWith('rgba(180')?'rgba(180,175,168,.6)':c.replace('.8','1')),
    borderWidth:1,
  }];
  charts.scatter.update('active');

  renderFunnel(funnel);
  renderLeaderboard(sales);
  renderTables();
}

function renderFunnel(funnel){
  const max = funnel[0]?.val || 1;
  const colors=['#e07b20','#f59e0b','#6366f1','#0d9488','#10b981'];
  const wrap=document.getElementById('stageFunnel');
  if(!funnel.length){ wrap.innerHTML='<p style="color:var(--clr-text-sub);font-size:.82rem;padding:12px 0;">No funnel data for selected filters.</p>'; return; }
  wrap.innerHTML = funnel.map((f,i)=>{
    const pct = Math.round(f.val/max*100);
    return `<div class="funnel-row">
      <div class="funnel-label">${f.stage}</div>
      <div class="funnel-bar-bg"><div class="funnel-bar-fill" style="width:${pct}%;background:${colors[i]};"><span class="funnel-bar-text">${pct}%</span></div></div>
      <div class="funnel-val">${f.val.toLocaleString()}</div>
    </div>`;
  }).join('');
}

function renderLeaderboard(sales){
  const sorted=[...sales].sort((a,b)=>b.conv-a.conv);
  const rankClass=['gold','silver','bronze'];
  const wrap=document.getElementById('leaderboard');
  if(!sorted.length){ wrap.innerHTML='<p style="color:var(--clr-text-sub);font-size:.82rem;padding:12px 0;">No salespersons match the selected filters.</p>'; return; }
  const maxConv = sorted[0]?.conv||1;
  const anySelected = state.person.size>0;
  wrap.innerHTML = sorted.slice(0,7).map((s,i)=>{
    const isSelected = state.person.has(s.id);
    const dimClass = anySelected && !isSelected ? ' lb-dim' : '';
    const selClass = isSelected ? ' lb-selected' : '';
    return `
    <div class="lb-card${dimClass}${selClass}" onclick="togglePerson(${s.id})" title="Click to filter all charts by ${s.name}">
      <div class="lb-rank ${rankClass[i]||''}">${i+1}</div>
      <div class="lb-avatar">${s.initials}</div>
      <div class="lb-info">
        <div class="lb-name">${s.name}</div>
        <div class="lb-team">${TEAM_LABELS[s.team]||s.team}</div>
        <div class="lb-bar-mini"><div class="lb-bar-mini-fill" style="width:${(s.conv/maxConv*100).toFixed(0)}%"></div></div>
      </div>
      <div class="lb-metrics">
        <div class="lb-metric"><div class="lb-metric-val">${s.conv.toFixed(1)}%</div><div class="lb-metric-label">Conv.</div></div>
        <div class="lb-metric"><div class="lb-metric-val">${s.sla.toFixed(0)}%</div><div class="lb-metric-label">SLA</div></div>
        <div class="lb-metric"><div class="lb-metric-val">${s.interested}</div><div class="lb-metric-label">Interested</div></div>
      </div>
    </div>`;
  }).join('');
}

function renderTables(){
  // Sales table
  let salesRows = computeFullRows('sales');
  Object.keys(tblColFilter.sales).forEach(col=>{
    const allowed = tblColFilter.sales[col];
    if(allowed && allowed.size>0) salesRows = salesRows.filter(r=>allowed.has(String(r[col]||'')));
  });
  Object.keys(tblRangeFilter.sales||{}).forEach(col=>{
    const rf = tblRangeFilter.sales[col]||{};
    if(rf.min !== null && rf.min !== undefined) salesRows = salesRows.filter(r=>Number(r[col])>=rf.min);
    if(rf.max !== null && rf.max !== undefined) salesRows = salesRows.filter(r=>Number(r[col])<=rf.max);
  });
  salesRows.sort((a,b)=>{ const c=tblSort.sales.col; const v=a[c]>b[c]?1:a[c]<b[c]?-1:0; return v*tblSort.sales.dir; });

  // Team table
  let teamRows = computeFullRows('team');
  Object.keys(tblColFilter.team).forEach(col=>{
    const allowed = tblColFilter.team[col];
    if(allowed && allowed.size>0) teamRows = teamRows.filter(r=>allowed.has(String(r[col]||'')));
  });
  Object.keys(tblRangeFilter.team||{}).forEach(col=>{
    const rf = tblRangeFilter.team[col]||{};
    if(rf.min !== null && rf.min !== undefined) teamRows = teamRows.filter(r=>Number(r[col])>=rf.min);
    if(rf.max !== null && rf.max !== undefined) teamRows = teamRows.filter(r=>Number(r[col])<=rf.max);
  });
  teamRows.sort((a,b)=>{ const c=tblSort.team.col; const v=a[c]>b[c]?1:a[c]<b[c]?-1:0; return v*tblSort.team.dir; });

  renderSalesTable(salesRows);
  renderTeamTable(teamRows);
}

function renderSalesTable(sales){
  const body=document.getElementById('salesTableBody');
  if(!sales.length){ body.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--clr-text-sub);padding:24px;font-style:italic;">No salespersons match the selected filters.</td></tr>'; return; }
  const anySelected = state.person.size>0;
  body.innerHTML = sales.map(s=>{
    const isSelected = state.person.has(s.id);
    const rowClass = isSelected ? ' class="row-selected"' : (anySelected ? ' class="row-dim"' : '');
    return `<tr${rowClass} onclick="togglePerson(${s.id})" title="Click to filter all charts by ${s.name}">
      <td style="text-align:left;font-weight:600;">${s.name}</td>
      <td>${s.teamLabel}</td>
      <td>${s.assigned.toLocaleString()}</td>
      <td>${s.interested.toLocaleString()}</td>
      <td><div class="progress-wrap"><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${Math.min(s.conv*3,100)}%;background:${s.conv>=25?'#10b981':s.conv>=20?'#f59e0b':'#f43f5e'};"></div></div><span class="progress-pct">${s.conv.toFixed(1)}%</span></div></td>
      <td><div class="progress-wrap"><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${s.sla}%;background:${s.sla>=90?'#10b981':s.sla>=75?'#f59e0b':'#f43f5e'};"></div></div><span class="progress-pct">${s.sla.toFixed(0)}%</span></div></td>
      <td>${s.response} mins</td>
    </tr>`;
  }).join('');
}

function renderTeamTable(teams){
  const body=document.getElementById('teamSlaBody');
  if(!teams.length){ body.innerHTML='<tr><td colspan="6" style="text-align:center;color:var(--clr-text-sub);padding:24px;font-style:italic;">No teams match the selected filters.</td></tr>'; return; }
  const anySelected = state.team.size>0;
  body.innerHTML = teams.map(t=>{
    const badge = t.status==='Compliant'?'exceeded':t.status==='At Risk'?'on-track':'under';
    const isSelected = state.team.has(t.team);
    const rowClass = isSelected ? ' class="row-selected"' : (anySelected ? ' class="row-dim"' : '');
    return `<tr${rowClass} onclick="toggleTeam('${t.team}')" title="Click to filter all charts by ${t.name}">
      <td style="text-align:left;font-weight:600;">${t.name}</td>
      <td>${t.total.toLocaleString()}</td>
      <td>${t.completed.toLocaleString()}</td>
      <td>${t.breached.toLocaleString()}</td>
      <td><div class="progress-wrap"><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${t.comp}%;background:${t.comp>=90?'#10b981':t.comp>=75?'#f59e0b':'#f43f5e'};"></div></div><span class="progress-pct">${t.comp.toFixed(1)}%</span></div></td>
      <td><span class="badge ${badge}">${t.status}</span></td>
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
  const {sales} = getFilteredData();
  const rows=[['Name','Team','Assigned','Interested','Conv %','SLA %','Response(mins)'],
    ...sales.map(s=>[s.name,TEAM_LABELS[s.team]||s.team,s.assigned,s.interested,s.conv,s.sla,s.response])];
  const csv=rows.map(r=>r.join(',')).join('\n');
  const a=document.createElement('a');a.href='data:text/csv,'+encodeURIComponent(csv);a.download='performance-report.csv';a.click();
  toast('Report exported as CSV');
}

// ═══════════════════════════════════════════
// INIT — fetch live figures, then build the dashboard
// ═══════════════════════════════════════════
fetch(window.PERF_CFG.dataUrl, {headers:{'X-Requested-With':'XMLHttpRequest'}})
  .then(r=>r.json())
  .then(d=>{
    RAW = {sales:d.sales||[], teams:d.teams||[], funnel:d.funnel||[]};
    TEAM_LABELS = {};
    RAW.teams.forEach(t=>{ TEAM_LABELS[t.team] = t.name; });
    GF_OPTIONS.team = RAW.teams.map(t=>({val:t.team, label:t.name}));
    buildGfLists();
    initCharts();
    updateGfButtons();
    updateAll();
  })
  .catch(()=>toast('Could not load performance data'));

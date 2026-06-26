/* ═══════════════════════════════════════════════════
   DATA — loaded from the backend via AJAX (no localStorage).
   CFG is injected by the template (URLs + CSRF).
═══════════════════════════════════════════════════ */
const CFG = window.LEAD_MGMT_CFG || {};
let leads = [];

function ajaxGet(url){ return fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'}}).then(r=>r.json()); }
function ajaxPost(url,body){
  return fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':CFG.csrf,'X-Requested-With':'XMLHttpRequest'},body:JSON.stringify(body)})
    .then(async r=>{ const d=await r.json().catch(()=>({})); if(!r.ok||d.ok===false) throw new Error(d.error||'Request failed'); return d; });
}

function loadLeadsFromServer(){
  return ajaxGet(CFG.urls.leads).then(d=>{ leads=(d.leads||[]); }).catch(()=>{ leads=[]; });
}

/* ═══════════════════════════════════════════════════
   STATE
═══════════════════════════════════════════════════ */
let searchQuery='', currentPage=1, totalPages=1;
let PAGE_SIZE=100;
let stageEditId=null, _selectedStage=null;
let historyLeadId=null, historyTab='all';
let sortField=null, sortAscMap={};
let globalFilter='all';
let openFilterKey=null;
let filterDateOpen=false;
const activeDateFilter=new Set();
const _dateTreeOpenYears=new Set();
let filterUpdatedOpen=false;
const activeUpdatedDateFilter=new Set();
const _updatedTreeOpenYears=new Set();

const CAMP_TYPE_LABELS = {
  'EVENT': 'Event',
  'TV_AD': 'TV Ad',
  'STREET_AD': 'Street Ad',
  'SOCIAL_MEDIA_AD': 'Social Media Ad',
  'EXHIBITION': 'Exhibition'
};

const STAGE_ORDER = ['Fresh','Follow-up','Meeting','Interested','Not Interested','Not Reached','Frozen'];
const STAGE_CLASS = {
  'Fresh':'stage-fresh','Follow-up':'stage-followup','Meeting':'stage-meeting',
  'Interested':'stage-interested','Not Interested':'stage-notinterested',
  'Not Reached':'stage-notreached','Frozen':'stage-frozen'
};

/* ── Filters config (for column filters — mutually dependent) ── */
const activeFilters = { name:new Set(), phone:new Set(), source:new Set(), stage:new Set(), status:new Set() };
const FILTER_CONFIG = {
  name:   { dd:'filterNameDropdown',   btn:'filterNameBtn',   list:'filterNameList',   search:'filterNameSearch',   getValue: l=>l.name||'' },
  phone:  { dd:'filterPhoneDropdown',  btn:'filterPhoneBtn',  list:'filterPhoneList',  search:'filterPhoneSearch',  getValue: l=>fmtPhone(l.phone)||'' },
  source: { dd:'filterSourceDropdown', btn:'filterSourceBtn', list:'filterSourceList', search:null,                 getValue: l=>l.source||'' },
  stage:  { dd:'filterStageDropdown',  btn:'filterStageBtn',  list:'filterStageList',  search:null,                 getValue: l=>l.stage||'Fresh' },
  status: { dd:'filterStatusDropdown', btn:'filterStatusBtn', list:'filterStatusList', search:null,                 getValue: l=>l.active?'Active':'Inactive' },
};

/* ═══════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════ */
function clearSearchInput() {
  searchQuery = '';
  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.value = '';
  }
}
function escHtml(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function fmtDate(ts){ if(!ts)return'—'; const d=new Date(ts); return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()]+' '+d.getDate()+', '+d.getFullYear(); }
function fmtDatetime(ts){ if(!ts)return'—'; const d=new Date(ts); return fmtDate(ts)+' '+d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}); }
function fmtPhone(p){ if(!p)return'—'; return String(p).trim(); }

/* ── SLA timer ── */
function getSlaMs(lead) {
  // Backend supplies the absolute SLA deadline (ms). Remaining = deadline - now.
  if (!lead.slaDeadline) return null;
  return lead.slaDeadline - Date.now();
}
function fmtSla(ms) {
  if (ms === null) return { html: '<span style="color:var(--clr-gray);font-size:.78rem">—</span>', ms: null };
  if (ms <= 0) return { html:'<span class="sla-timer sla-expired">Expired</span>', ms };
  
  const SEC = 1000;
  const MIN = 60 * SEC;
  const HR = 60 * MIN;
  const DAY = 24 * HR;
  const MON = 30 * DAY;
  
  const months = Math.floor(ms / MON);
  const days = Math.floor((ms % MON) / DAY);
  const hours = Math.floor((ms % DAY) / HR);
  const minutes = Math.floor((ms % HR) / MIN);
  const seconds = Math.floor((ms % MIN) / SEC);
  
  const pad = n => String(n).padStart(2,'0');
  
  let timeStr = '';
  if (months > 0) {
    timeStr = `${months}mo ${days}d ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  } else if (days > 0) {
    timeStr = `${days}d ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  } else {
    timeStr = `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  }
  
  const cls = ms < 3600000 ? 'sla-urgent' : ms < 7200000 ? 'sla-warn' : 'sla-ok';
  return { html:`<span class="sla-timer ${cls}">${timeStr}</span>`, ms };
}

/* ═══════════════════════════════════════════════════
   PHONE POPOVER
═══════════════════════════════════════════════════ */
let _phoneDigits='';
function openPhoneModal(id,evt){
  const l=leads.find(x=>x.id===id); if(!l||!l.phone)return;
  if(evt)evt.stopPropagation();
  _phoneDigits=String(l.phone).replace(/\D/g,'');
  document.getElementById('phoneModalNumber').textContent=fmtPhone(l.phone);
  const btn=document.getElementById('phoneModalCopyBtn');
  btn.classList.remove('copied');
  document.getElementById('phoneModalCopyLabel').textContent='Copy Number';
  const pop=document.getElementById('phoneModal');
  pop.classList.add('open');
  if(evt&&evt.currentTarget){
    const r=evt.currentTarget.getBoundingClientRect(),pw=198,ph=80;
    let left=r.left,top=r.bottom+6;
    if(left+pw>window.innerWidth-8)left=window.innerWidth-pw-8;
    if(top+ph>window.innerHeight-8)top=r.top-ph-6;
    pop.style.left=left+'px'; pop.style.top=top+'px';
  }
}
function closePhoneModal(){ document.getElementById('phoneModal').classList.remove('open'); }
document.addEventListener('click',e=>{ if(document.getElementById('phoneModal').classList.contains('open')&&!document.getElementById('phoneModal').contains(e.target)&&!e.target.closest('.phone-link'))closePhoneModal(); });
document.addEventListener('scroll',closePhoneModal,true);
function copyPhoneFromModal(){
  const text=document.getElementById('phoneModalNumber').textContent;
  const done=()=>{ const btn=document.getElementById('phoneModalCopyBtn'); btn.classList.add('copied'); document.getElementById('phoneModalCopyLabel').textContent='Copied!'; setTimeout(()=>{ btn.classList.remove('copied'); document.getElementById('phoneModalCopyLabel').textContent='Copy Number'; },1500); };
  if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done).catch(()=>{ const ta=document.createElement('textarea');ta.value=text;document.body.appendChild(ta);ta.select();try{document.execCommand('copy');}catch(e){}ta.remove();done(); });
  else { const ta=document.createElement('textarea');ta.value=text;document.body.appendChild(ta);ta.select();try{document.execCommand('copy');}catch(e){}ta.remove();done(); }
}
function sendWhatsappFromModal(){ if(_phoneDigits)window.open('https://wa.me/'+_phoneDigits,'_blank'); }

/* ═══════════════════════════════════════════════════
   SOURCE / CAMPAIGN POPOVER
═══════════════════════════════════════════════════ */
const SRC_ICONS = {
  'Event':          '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  'Social Media Ad':'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/>',
  'TV Ad':          '<rect x="2" y="7" width="20" height="15" rx="2"/><polyline points="17 2 12 7 7 2"/>',
  'Street Ad':      '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
  'Exhibition':     '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>',
  'Campaign':       '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  'Broker':         '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  'Other':          '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
};

// Label for the specificSource field depending on source type
const SPEC_LABEL = {
  'Event':          'Event Name',
  'Exhibition':     'Exhibition Name',
  'TV Ad':          'Ad Name',
  'Street Ad':      'Location / Ad Name',
  'Social Media Ad':'Ad / Post Name',
  'Campaign':       'Event / Ad Name',
  'Other':          'Details',
};

function openSrcPopover(id, evt) {
  const l = leads.find(x => x.id === id); if (!l) return;

  const campName  = (l.campaign || '').trim();
  const brokerName = (l.broker || '').trim();
  const specSrc   = (l.specificSource || '').trim();
  const isBroker  = !!brokerName;
  const isCampaign = !!campName && !isBroker;

  if (!isBroker && !isCampaign) {
    return;
  }

  if (evt) evt.stopPropagation();
  const pop = document.getElementById('srcPopover');
  const srcType   = isCampaign ? (CAMP_TYPE_LABELS[l.campaign_child_type] || 'Other') : (l.source || 'Other');

  // Choose icon
  const iconKey = isBroker ? 'Broker' : srcType;
  const iconSvg = SRC_ICONS[iconKey] || SRC_ICONS['Other'];
  document.getElementById('srcPopIcon').innerHTML =
    `<svg viewBox="0 0 24 24" style="width:15px;height:15px;stroke:var(--clr-orange);fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round">${iconSvg}</svg>`;

  if (isBroker) {
    document.getElementById('srcPopTitle').textContent = brokerName;
    document.getElementById('srcPopType').textContent  = 'Broker Referral';
    document.getElementById('srcPopBody').innerHTML =
      `<div class="src-pop-row"><span class="src-pop-label">Broker Name</span><span class="src-pop-value">${escHtml(brokerName)}</span></div>`;
  } else if (isCampaign) {
    document.getElementById('srcPopTitle').textContent = campName;
    document.getElementById('srcPopType').textContent  = 'Campaign · ' + srcType;
    let bodyHtml = `<div class="src-pop-row"><span class="src-pop-label">Campaign Name</span><span class="src-pop-value">${escHtml(campName)}</span></div>`;
    bodyHtml += `<div class="src-pop-row"><span class="src-pop-label">Campaign Type</span><span class="src-pop-value">${escHtml(srcType)}</span></div>`;
    if (specSrc) {
      const specLabel = SPEC_LABEL[srcType] || 'Details';
      bodyHtml += `<div class="src-pop-row"><span class="src-pop-label">${escHtml(specLabel)}</span><span class="src-pop-value">${escHtml(specSrc)}</span></div>`;
    }
    document.getElementById('srcPopBody').innerHTML = bodyHtml;
  }

  pop.classList.add('open');

  // Position below the clicked tag
  const target = evt && (evt.currentTarget || evt.target.closest('.source-tag'));
  if (target) {
    const r = target.getBoundingClientRect();
    const pw = 250;
    pop.style.visibility = 'hidden';
    pop.style.display    = 'block';
    const ph = pop.offsetHeight || 150;
    pop.style.visibility = '';
    pop.style.display    = '';
    let left = r.left, top = r.bottom + 6;
    if (left + pw > window.innerWidth - 8) left = window.innerWidth - pw - 8;
    if (top + ph > window.innerHeight - 8) top = r.top - ph - 6;
    pop.style.left = left + 'px';
    pop.style.top  = top  + 'px';
  }
}
function closeSrcPopover() { document.getElementById('srcPopover').classList.remove('open'); }
document.addEventListener('click', e => {
  if (document.getElementById('srcPopover').classList.contains('open') &&
      !document.getElementById('srcPopover').contains(e.target) &&
      !e.target.closest('.source-tag')) closeSrcPopover();
});
document.addEventListener('scroll', closeSrcPopover, true);

/* ═══════════════════════════════════════════════════
   STAGE MODAL
═══════════════════════════════════════════════════ */
const NEXT_ACTIONS = {
  'Follow-up': [{ val:'reminder', label:'📅 Set a reminder to call back', hasDate:true, type:'reminder' }],
  'Meeting':   [{ val:'meeting',  label:'🗓 Schedule a meeting', hasDate:true, type:'meeting' }],
  'Interested':[{ val:'proposal', label:'📋 Send proposal / offer details' }],
  'Fresh':     [{ val:'call',     label:'📞 Plan a call' }],
  'Not Reached':[{ val:'retry',   label:'🔄 Retry call later' }],
  'Frozen':    [{ val:'frozenCall', label:'❄️ Call back after a period', type:'frozenCall' }],
};

function openStageModal(id){
  const l=leads.find(x=>x.id===id); if(!l)return;
  stageEditId=id; _selectedStage=null;
  document.getElementById('stageModalSub').textContent='Lead: '+l.name;
  
  const optInterested = document.getElementById('optInterested');
  if (optInterested) {
    optInterested.style.display = l.stage === 'Interested' ? 'none' : '';
  }

  document.querySelectorAll('.stage-opt').forEach(opt=>{
    opt.classList.remove('selected');
  });
  // reset
  document.getElementById('stageFeedbackSection').classList.remove('show');
  document.getElementById('stageFeedback').value='';
  document.getElementById('stageReason').value='';
  document.getElementById('reminderDate').value='';
  document.getElementById('reminderTime').value='';
  document.getElementById('meetingDate').value='';
  document.getElementById('meetingTime').value='';
  document.getElementById('meetingLocation').value='';
  document.getElementById('frozenDays').value='';
  validateStageForm();
  document.getElementById('stageModal').classList.add('open');
}

function selectStage(val,el){
  _selectedStage=val;
  document.querySelectorAll('.stage-opt').forEach(o=>o.classList.remove('selected'));
  el.classList.add('selected');
  renderStageFeedbackSection(val);
  validateStageForm();
}

function renderStageFeedbackSection(stage){
  const sec=document.getElementById('stageFeedbackSection');
  const reasonGrp=document.getElementById('reasonGroup');
  const nextSec=document.getElementById('nextActionSection');
  const reminderRow=document.getElementById('reminderDateRow');
  const meetingRow=document.getElementById('meetingDateRow');
  const meetingLocRow=document.getElementById('meetingLocationRow');
  const nextGrid=document.getElementById('nextActionGrid');
  const feedbackLabel=document.getElementById('feedbackLabel');
  const feedbackGrp=document.getElementById('feedbackGroup');

  sec.classList.add('show');

  // Show/hide reason (only Not Interested)
  reasonGrp.style.display = stage==='Not Interested'?'':'none';
  nextSec.style.display    = stage==='Not Interested'?'none':'';
  
  if (feedbackGrp) {
    feedbackGrp.style.display = stage==='Not Reached'?'none':'';
  }

  reminderRow.classList.add('field-hidden');
  meetingRow.classList.add('field-hidden');
  meetingLocRow.classList.add('field-hidden');
  document.getElementById('frozenDaysRow').classList.add('field-hidden');

  feedbackLabel.textContent = stage==='Not Interested'?'Additional Notes (optional)':'Feedback / Call Summary';

  // Render next actions
  nextGrid.innerHTML='';
  const actions=NEXT_ACTIONS[stage]||[];
  actions.forEach((a,i)=>{
    const div=document.createElement('div'); div.className='next-action-opt';
    div.dataset.val=a.val; div.dataset.type=a.type||'';
    div.innerHTML=`<input type="radio" name="nextAction" value="${a.val}"> ${a.label}`;
    div.onclick=()=>{ div.querySelector('input').checked=true; onNextActionSelect(a.val,a.type); document.querySelectorAll('.next-action-opt').forEach(o=>o.classList.toggle('selected',o===div)); };
    nextGrid.appendChild(div);
    // Auto-select when there's exactly one option (Meeting / Follow-up), so
    // the date field is visible right away instead of requiring an extra click.
    if(actions.length===1&&i===0){
      div.querySelector('input').checked=true;
      div.classList.add('selected');
      onNextActionSelect(a.val,a.type);
    }
  });
}

function onNextActionSelect(val,type){
  document.getElementById('reminderDateRow').classList.toggle('field-hidden', type!=='reminder');
  document.getElementById('meetingDateRow').classList.toggle('field-hidden', type!=='meeting');
  document.getElementById('meetingLocationRow').classList.toggle('field-hidden', type!=='meeting');
  document.getElementById('frozenDaysRow').classList.toggle('field-hidden', type!=='frozenCall');
}

function closeStageModal(){ document.getElementById('stageModal').classList.remove('open'); stageEditId=null; _selectedStage=null; }
document.getElementById('stageModalClose').addEventListener('click',closeStageModal);
document.getElementById('stageModalCancel').addEventListener('click',closeStageModal);
document.getElementById('stageModal').addEventListener('click',e=>{ if(e.target===e.currentTarget)closeStageModal(); });

document.getElementById('stageModalSave').addEventListener('click',()=>{
  if(!stageEditId||!_selectedStage)return;
  const l=leads.find(x=>x.id===stageEditId); if(!l)return;
  const feedback=document.getElementById('stageFeedback').value.trim();
  const reason=document.getElementById('stageReason').value;

  // Validation
  if(_selectedStage==='Not Interested'&&!reason){ Swal.fire({title:'Reason required',text:'Please select a reason for Not Interested.',icon:'warning',confirmButtonColor:'var(--clr-orange)'}); return; }

  const selectedActionEl=document.querySelector('.next-action-opt.selected');
  const nextActionVal=selectedActionEl?selectedActionEl.dataset.val:null;
  const nextActionType=selectedActionEl?selectedActionEl.dataset.type:null;

  if(_selectedStage==='Frozen'&&nextActionType==='frozenCall'){
    const daysVal=parseInt(document.getElementById('frozenDays').value);
    if(!daysVal||daysVal<1){ Swal.fire({title:'Call-back period required',text:"Enter the number of days the lead asked to be called back after.",icon:'warning',confirmButtonColor:'var(--clr-orange)'}); return; }
  }
  if(_selectedStage==='Meeting'){
    const md=document.getElementById('meetingDate').value;
    if(!md){ Swal.fire({title:'Meeting date required',text:'Please set the meeting date so it appears correctly in the lead history.',icon:'warning',confirmButtonColor:'var(--clr-orange)'}); return; }
  }
  if(_selectedStage==='Follow-up'){
    const rd=document.getElementById('reminderDate').value;
    if(!rd){ Swal.fire({title:'Follow-up date required',text:'Please set the reminder date so it appears correctly in the lead history.',icon:'warning',confirmButtonColor:'var(--clr-orange)'}); return; }
  }

  // Build the payload; the backend routes to the right service
  // (FollowUpService / MeetingService / LeadStageService) and writes the
  // audit log + lead history server-side.
  const prevStage=l.stage;
  const payload={
    lead_id: l.id,
    stage_code: STAGE_CODE[_selectedStage] || 'FRESH',
    feedback: feedback||'',
    reason: reason||'',
    reminder_date: document.getElementById('reminderDate').value||'',
    reminder_time: document.getElementById('reminderTime').value||'',
    meeting_date: document.getElementById('meetingDate').value||'',
    meeting_time: document.getElementById('meetingTime').value||'',
    meeting_location: document.getElementById('meetingLocation').value.trim()||'',
    frozen_days: parseInt(document.getElementById('frozenDays').value)||0,
  };
  const saveBtn=document.getElementById('stageModalSave');
  saveBtn.disabled=true;
  ajaxPost(CFG.urls.stageUpdate, payload)
    .then(()=>loadLeadsFromServer())
    .then(()=>{ closeStageModal(); renderTable(); showToast('success','Stage Updated',`"${l.name}" moved from ${prevStage} to ${_selectedStage}.`); })
    .catch(err=>{ Swal.fire({title:'Update failed',text:String(err.message||err),icon:'error',confirmButtonColor:'var(--clr-orange)'}); })
    .finally(()=>{ saveBtn.disabled=false; });
});

// Display stage label -> backend stage code.
const STAGE_CODE = {
  'Fresh':'FRESH','Follow-up':'FOLLOW_UP','Meeting':'MEETING','Interested':'INTERESTED',
  'Not Interested':'NOT_INTERESTED','Not Reached':'NOT_REACHED','Frozen':'FROZEN',
};

/* ═══════════════════════════════════════════════════
   HISTORY MODAL
═══════════════════════════════════════════════════ */
function openHistoryModal(id){
  const l=leads.find(x=>x.id===id); if(!l)return;
  historyLeadId=id; historyTab='all';
  document.getElementById('historyModalSub').textContent=l.name+' · '+fmtPhone(l.phone);
  document.querySelectorAll('.history-tab').forEach((t,i)=>t.classList.toggle('active',i===0));
  document.getElementById('historyContent').innerHTML='<div class="history-empty">Loading…</div>';
  document.getElementById('historyModal').classList.add('open');
  // History is built server-side from stage/follow-up/meeting/note records.
  ajaxGet(CFG.urls.history+'?lead_id='+encodeURIComponent(id))
    .then(d=>{ l.history=d.history||[]; if(historyLeadId===id) renderHistoryContent(l); })
    .catch(()=>{ document.getElementById('historyContent').innerHTML='<div class="history-empty">Could not load history.</div>'; });
}
function closeHistoryModal(){ document.getElementById('historyModal').classList.remove('open'); historyLeadId=null; }
document.getElementById('historyModalClose').addEventListener('click',closeHistoryModal);
document.getElementById('historyModalClose2').addEventListener('click',closeHistoryModal);
document.getElementById('historyModal').addEventListener('click',e=>{ if(e.target===e.currentTarget)closeHistoryModal(); });

function switchHistoryTab(tab,el){
  historyTab=tab;
  document.querySelectorAll('.history-tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  const l=leads.find(x=>x.id===historyLeadId); if(!l)return;
  renderHistoryContent(l);
}

function renderHistoryContent(l){
  const cont=document.getElementById('historyContent');
  const allHistory=[...(l.history||[])].sort((a,b)=>(b.ts||0)-(a.ts||0));

  const dotIcons={
    created:'<polyline points="20 6 9 17 4 12"/>',
    stage:'<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    meeting:'<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    followup:'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/>',
    note:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    assignment:'<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  };

  function bodyOf(h){
    let bodyHtml='';
    if(h.feedback)   bodyHtml+=`<div class="history-body">📝 ${escHtml(h.feedback)}</div>`;
    if(h.reason)     bodyHtml+=`<div class="history-body" style="margin-top:6px">🚫 Reason: ${escHtml(h.reason)}</div>`;
    if(h.reminderDate) bodyHtml+=`<div class="history-body" style="margin-top:6px">⏰ Reminder: ${escHtml(h.reminderDate)}${h.reminderTime?' at '+h.reminderTime:''}</div>`;
    if(h.callbackDate) bodyHtml+=`<div class="history-body" style="margin-top:6px">❄️ Call back on: ${escHtml(h.callbackDate)} (${escHtml(String(h.frozenDays||''))} day${h.frozenDays===1?'':'s'} after freezing)</div>`;
    if(h.meetingDate)  bodyHtml+=`<div class="history-body" style="margin-top:6px">📅 Meeting: ${escHtml(h.meetingDate)}${h.meetingTime?' at '+h.meetingTime:''}${h.meetingLocation?' · '+escHtml(h.meetingLocation):''}</div>`;
    return bodyHtml;
  }
  function itemHtml(h){
    const dc=h.type||'note';
    const ic=dotIcons[dc]||dotIcons.note;
    return `<div class="history-item">
      <div class="history-dot ${dc}"><svg viewBox="0 0 24 24">${ic}</svg></div>
      <div class="history-content">
        <div class="history-label">${escHtml(h.label)}</div>
        <div class="history-meta">${fmtDatetime(h.ts)}</div>
        ${bodyOf(h)}
      </div>
    </div>`;
  }
  function timeline(items){
    return '<div class="history-timeline">'+items.map(h=>itemHtml(h)).join('')+'</div>';
  }
  function emptySection(label){
    return `<div class="history-empty">No ${label} yet.</div>`;
  }

  const meetings  = allHistory.filter(h=>h.type==='meeting');
  const followups = allHistory.filter(h=>h.type==='followup');

  // Tab counters
  const tabAll=document.getElementById('tabCountAll'); if(tabAll) tabAll.textContent=allHistory.length;
  const tabMeet=document.getElementById('tabCountMeetings'); if(tabMeet) tabMeet.textContent=meetings.length;
  const tabFollow=document.getElementById('tabCountFollowups'); if(tabFollow) tabFollow.textContent=followups.length;

  if(!allHistory.length){
    cont.innerHTML='<div class="history-empty">No activity found.</div>';
    return;
  }

  if(historyTab==='meetings'){
    cont.innerHTML = meetings.length ? timeline(meetings) : emptySection('meetings');
    return;
  }
  if(historyTab==='followups'){
    cont.innerHTML = followups.length ? timeline(followups) : emptySection('follow-ups');
    return;
  }

  // All Activity — flat chronological list, newest first
  cont.innerHTML = timeline(allHistory);
}

/* ═══════════════════════════════════════════════════
   GLOBAL FILTER
═══════════════════════════════════════════════════ */
function setGlobalFilter(f){
  clearSearchInput();
  globalFilter=f;
  document.querySelectorAll('.gf-btn').forEach(b=>b.classList.remove('active'));
  const map={all:'gfAll',followups:'gfFollowups',meetings:'gfMeetings',today:'gfTodayActions',active:'gfActive',inactive:'gfInactive'};
  if(map[f]) document.getElementById(map[f])?.classList.add('active');
  currentPage=1; renderTable();
}
function clearGlobalFilter(){ setGlobalFilter('all'); }

function kpiFilter(stageOrAll){
  clearSearchInput();
  if(stageOrAll==='all'){ globalFilter='all'; document.querySelectorAll('.gf-btn').forEach(b=>b.classList.remove('active')); document.getElementById('gfAll')?.classList.add('active'); }
  else { globalFilter='kpi:'+stageOrAll; document.querySelectorAll('.gf-btn').forEach(b=>b.classList.remove('active')); }
  currentPage=1; renderTable();
}

/* ═══════════════════════════════════════════════════
   FILTER SYSTEM (column filters — mutually dependent)
═══════════════════════════════════════════════════ */
// Returns the list after applying ALL filters EXCEPT the given field
function getLeadsExcluding(excludeField){
  let list=[...leads];
  const q=searchQuery.trim().toLowerCase();
  if(q) list=list.filter(l=>(l.id && l.id.toLowerCase() === q)||(l.name||'').toLowerCase().includes(q)||(l.phone||'').includes(q));
  applyGlobalFilterToList(list); // not pure, handled below
  // Apply column filters except excludeField
  Object.entries(activeFilters).forEach(([field,set])=>{
    if(field===excludeField||!set.size)return;
    const cfg=FILTER_CONFIG[field];
    list=list.filter(l=>set.has(cfg.getValue(l)));
  });
  if(activeDateFilter.size) list=list.filter(l=>{ if(!l.createdAt)return false; const d=new Date(l.createdAt); const ym=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'); return activeDateFilter.has(ym); });
  if(activeUpdatedDateFilter.size) list=list.filter(l=>{ const ts=l.updatedAt||l.createdAt; if(!ts)return false; const d=new Date(ts); const ym=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'); return activeUpdatedDateFilter.has(ym); });
  return list;
}

// Actually: we need global filter too. Let's build getDisplayList properly.
function applyGlobalFilter(list){
  const now=Date.now();
  if(globalFilter==='followups')  return list.filter(l=>l.stage==='Follow-up');
  if(globalFilter==='meetings')   return list.filter(l=>l.stage==='Meeting');
  if(globalFilter==='active')     return list.filter(l=>l.active!==false);
  if(globalFilter==='inactive')   return list.filter(l=>l.active===false);
  if(globalFilter==='today'){
    return list.filter(l=>{
      const hist=l.history||[];
      return hist.some(h=>{
        if(h.type==='followup'&&h.reminderDate){
          const t=new Date(h.reminderDate); const n=new Date(); return t.toDateString()===n.toDateString();
        }
        if(h.type==='followup'&&h.callbackDate){
          const t=new Date(h.callbackDate); const n=new Date(); return t.toDateString()===n.toDateString();
        }
        if(h.type==='meeting'&&h.meetingDate){
          const t=new Date(h.meetingDate); const n=new Date(); return t.toDateString()===n.toDateString();
        }
        return false;
      });
    });
  }
  if(globalFilter.startsWith('kpi:')) return list.filter(l=>l.stage===globalFilter.slice(4));
  return list;
}
function applyGlobalFilterToList(list){ return applyGlobalFilter(list); }

function getUniqueValues(field){
  // Get unique values from current filtered set (excluding this field)
  let base=[...leads];
  const q=searchQuery.trim().toLowerCase();
  if(q) base=base.filter(l=>(l.id && l.id.toLowerCase() === q)||(l.name||'').toLowerCase().includes(q)||(l.phone||'').includes(q));
  base=applyGlobalFilter(base);
  // Apply other column filters
  Object.entries(activeFilters).forEach(([f,set])=>{
    if(f===field||!set.size)return;
    const cfg=FILTER_CONFIG[f];
    base=base.filter(l=>set.has(cfg.getValue(l)));
  });
  if(activeDateFilter.size) base=base.filter(l=>{ if(!l.createdAt)return false; const d=new Date(l.createdAt); const ym=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'); return activeDateFilter.has(ym); });
  if(activeUpdatedDateFilter.size) base=base.filter(l=>{ const ts=l.updatedAt||l.createdAt; if(!ts)return false; const d=new Date(ts); const ym=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'); return activeUpdatedDateFilter.has(ym); });
  const cfg=FILTER_CONFIG[field];
  const vals=new Set();
  base.forEach(l=>{ const v=cfg.getValue(l); if(v)vals.add(v); });
  if(field==='stage') return STAGE_ORDER.filter(s=>vals.has(s));
  return [...vals].sort((a,b)=>a.localeCompare(b));
}

function renderFilterList(field){
  const cfg=FILTER_CONFIG[field];
  const list=document.getElementById(cfg.list); if(!list)return;
  const searchEl=cfg.search?document.getElementById(cfg.search):null;
  const q=searchEl?searchEl.value.toLowerCase():'';
  const vals=getUniqueValues(field);
  list.innerHTML='';
  vals.filter(v=>!q||v.toLowerCase().includes(q)).forEach(v=>{
    const id='flt_'+field+'_'+v.replace(/\W/g,'_');
    const checked=activeFilters[field].has(v);
    const div=document.createElement('div'); div.className='filter-item';
    div.innerHTML=`<input type="checkbox" id="${id}" ${checked?'checked':''} onchange="toggleFilterItem('${field}','${escHtml(v)}',this.checked)"><label for="${id}">${escHtml(v)}</label>`;
    list.appendChild(div);
  });
  if(!list.children.length) list.innerHTML='<div style="padding:12px 14px;font-size:.8rem;color:var(--clr-gray)">No values found</div>';
}

function toggleFilterItem(field,val,checked){
  clearSearchInput();
  if(checked)activeFilters[field].add(val); else activeFilters[field].delete(val);
  currentPage=1; renderTable();
  // Re-render all open filter dropdowns (full dependency)
  if(openFilterKey&&openFilterKey!==field) renderFilterList(openFilterKey);
  if(filterDateOpen) renderDateFilter();
  if(filterUpdatedOpen) renderUpdatedFilter();
}
function selectAllFilter(field){ clearSearchInput(); getUniqueValues(field).forEach(v=>activeFilters[field].add(v)); renderFilterList(field); currentPage=1; renderTable(); }
function clearAllFilter(field){ clearSearchInput(); activeFilters[field].clear(); renderFilterList(field); currentPage=1; renderTable(); }

function closeAllFilters(){
  Object.values(FILTER_CONFIG).forEach(cfg=>document.getElementById(cfg.dd)?.classList.remove('open'));
  document.getElementById('filterDateDropdown')?.classList.remove('open');
  document.getElementById('filterUpdatedDropdown')?.classList.remove('open');
  filterDateOpen=false; filterUpdatedOpen=false; openFilterKey=null;
}
function positionDropdown(ddId,btnId){
  const dd=document.getElementById(ddId),r=document.getElementById(btnId).getBoundingClientRect();
  dd.classList.add('open');
  dd.style.top=r.bottom+4+'px';
  dd.style.left=Math.min(r.left,window.innerWidth-dd.offsetWidth-8)+'px';
}
function toggleFilter(field){
  const cfg=FILTER_CONFIG[field];
  const isOpen=document.getElementById(cfg.dd).classList.contains('open');
  closeAllFilters();
  if(!isOpen){ renderFilterList(field); positionDropdown(cfg.dd,cfg.btn); openFilterKey=field; if(cfg.search){const si=document.getElementById(cfg.search);if(si){si.value='';si.focus();}} }
}
Object.entries(FILTER_CONFIG).forEach(([field,cfg])=>{ document.getElementById(cfg.btn)?.addEventListener('click',e=>{e.stopPropagation();toggleFilter(field);}); });
document.addEventListener('click',e=>{ if(!e.target.closest('.filter-dropdown')&&!e.target.closest('.th-icon-btn'))closeAllFilters(); });

/* ── Date filter (Created) ── */
function buildDateTree(field='createdAt', excludeDateField=null){
  // Build from leads that pass all OTHER active filters (dependent)
  let base=[...leads];
  const q=searchQuery.trim().toLowerCase();
  if(q) base=base.filter(l=>(l.id && l.id.toLowerCase() === q)||(l.name||'').toLowerCase().includes(q)||(l.phone||'').includes(q));
  base=applyGlobalFilter(base);
  Object.entries(activeFilters).forEach(([f,set])=>{
    if(!set.size)return;
    const cfg=FILTER_CONFIG[f];
    base=base.filter(l=>set.has(cfg.getValue(l)));
  });
  // If we are building the "updated" tree, still apply createdAt filter (and vice versa)
  if(excludeDateField!=='createdAt' && activeDateFilter.size)
    base=base.filter(l=>{ if(!l.createdAt)return false; const d=new Date(l.createdAt); return activeDateFilter.has(d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')); });
  if(excludeDateField!=='updatedAt' && activeUpdatedDateFilter.size)
    base=base.filter(l=>{ const ts=l.updatedAt||l.createdAt; if(!ts)return false; const d=new Date(ts); return activeUpdatedDateFilter.has(d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')); });

  const map={};
  base.forEach(l=>{
    const ts = field==='updatedAt' ? (l.updatedAt||l.createdAt) : l.createdAt;
    if(!ts)return;
    const d=new Date(ts),year=String(d.getFullYear()),month=year+'-'+String(d.getMonth()+1).padStart(2,'0');
    if(!map[year])map[year]=new Set();
    map[year].add(month);
  });
  return map;
}
function renderDateTreeGeneric(opts){
  const {containerId, field, activeSet, openYearsSet, excludeDateField} = opts;
  const container=document.getElementById(containerId); if(!container)return;
  const tree=buildDateTree(field, excludeDateField);
  const monthNames=['January','February','March','April','May','June','July','August','September','October','November','December'];
  container.innerHTML='';
  Object.keys(tree).sort().reverse().forEach(year=>{
    const months=[...tree[year]].sort();
    const allChecked=months.every(m=>activeSet.has(m));
    const isOpen=openYearsSet.has(year);
    const wrapper=document.createElement('div');
    const yearRow=document.createElement('div'); yearRow.className='date-tree-year';
    const cb=document.createElement('input'); cb.type='checkbox'; cb.style.cssText='accent-color:var(--clr-orange);width:14px;height:14px;cursor:pointer;margin-right:6px;flex-shrink:0';
    cb.checked=allChecked; cb.indeterminate=!allChecked&&months.some(m=>activeSet.has(m));
    cb.onchange=()=>{ clearSearchInput(); if(cb.checked)months.forEach(m=>activeSet.add(m)); else months.forEach(m=>activeSet.delete(m)); currentPage=1;renderTable();renderDateTreeGeneric(opts); if(openFilterKey)renderFilterList(openFilterKey); };
    const chev=document.createElement('span'); chev.className='date-tree-chevron'+(isOpen?' open':''); chev.textContent='▶';
    yearRow.addEventListener('click',e=>{ if(e.target===cb)return; if(openYearsSet.has(year))openYearsSet.delete(year); else openYearsSet.add(year); renderDateTreeGeneric(opts); });
    yearRow.appendChild(cb); const label=document.createElement('span'); label.textContent=year; label.style.flex='1'; yearRow.appendChild(label); yearRow.appendChild(chev);
    const monthsDiv=document.createElement('div'); monthsDiv.className='date-tree-months'+(isOpen?' open':'');
    months.forEach(ym=>{ const mLabel=document.createElement('label'); mLabel.className='filter-item'; const mCb=document.createElement('input'); mCb.type='checkbox'; mCb.checked=activeSet.has(ym); mCb.style.cssText='accent-color:var(--clr-orange);width:14px;height:14px;cursor:pointer;flex-shrink:0'; mCb.onchange=()=>{ clearSearchInput(); if(mCb.checked)activeSet.add(ym); else activeSet.delete(ym); cb.checked=months.every(m=>activeSet.has(m)); cb.indeterminate=!cb.checked&&months.some(m=>activeSet.has(m)); currentPage=1;renderTable(); if(openFilterKey)renderFilterList(openFilterKey); if(filterUpdatedOpen&&field!=='updatedAt')renderUpdatedFilter(); if(filterDateOpen&&field!=='createdAt')renderDateFilter(); }; const mNum=parseInt(ym.split('-')[1])-1; const mSpan=document.createElement('span'); mSpan.style.cssText='font-size:.83rem;color:var(--clr-text)'; mSpan.textContent=monthNames[mNum]; mLabel.appendChild(mCb);mLabel.appendChild(mSpan); monthsDiv.appendChild(mLabel); });
    wrapper.appendChild(yearRow);wrapper.appendChild(monthsDiv);container.appendChild(wrapper);
  });
  if(!Object.keys(tree).length)container.innerHTML='<div style="padding:10px 14px;font-size:.82rem;color:var(--clr-text-sub)">No dates available</div>';
}
function renderDateFilter(){
  renderDateTreeGeneric({containerId:'filterDateList', field:'createdAt', activeSet:activeDateFilter, openYearsSet:_dateTreeOpenYears, excludeDateField:'createdAt'});
}
function selectAllDateFilter(){ clearSearchInput(); const tree=buildDateTree('createdAt','createdAt'); Object.values(tree).forEach(s=>s.forEach(m=>activeDateFilter.add(m))); currentPage=1;renderTable();renderDateFilter(); if(openFilterKey)renderFilterList(openFilterKey); }
function clearAllDateFilter(){ clearSearchInput(); activeDateFilter.clear(); currentPage=1;renderTable();renderDateFilter(); if(openFilterKey)renderFilterList(openFilterKey); }
document.getElementById('filterDateBtn')?.addEventListener('click',e=>{ e.stopPropagation(); const isOpen=filterDateOpen; closeAllFilters(); filterDateOpen=!isOpen; if(filterDateOpen){ const dd=document.getElementById('filterDateDropdown'); const r=document.getElementById('filterDateBtn').getBoundingClientRect(); dd.classList.add('open'); dd.style.top=r.bottom+4+'px'; dd.style.left=Math.min(r.left,window.innerWidth-dd.offsetWidth-8)+'px'; renderDateFilter(); } });

/* ── Date filter (Last Updated) ── */
function renderUpdatedFilter(){
  renderDateTreeGeneric({containerId:'filterUpdatedList', field:'updatedAt', activeSet:activeUpdatedDateFilter, openYearsSet:_updatedTreeOpenYears, excludeDateField:'updatedAt'});
}
function selectAllUpdatedFilter(){ clearSearchInput(); const tree=buildDateTree('updatedAt','updatedAt'); Object.values(tree).forEach(s=>s.forEach(m=>activeUpdatedDateFilter.add(m))); currentPage=1;renderTable();renderUpdatedFilter(); if(openFilterKey)renderFilterList(openFilterKey); }
function clearAllUpdatedFilter(){ clearSearchInput(); activeUpdatedDateFilter.clear(); currentPage=1;renderTable();renderUpdatedFilter(); if(openFilterKey)renderFilterList(openFilterKey); }
document.getElementById('filterUpdatedBtn')?.addEventListener('click',e=>{ e.stopPropagation(); const isOpen=filterUpdatedOpen; closeAllFilters(); filterUpdatedOpen=!isOpen; if(filterUpdatedOpen){ const dd=document.getElementById('filterUpdatedDropdown'); const r=document.getElementById('filterUpdatedBtn').getBoundingClientRect(); dd.classList.add('open'); dd.style.top=r.bottom+4+'px'; dd.style.left=Math.min(r.left,window.innerWidth-dd.offsetWidth-8)+'px'; renderUpdatedFilter(); } });

/* ═══════════════════════════════════════════════════
   SORT
═══════════════════════════════════════════════════ */
const SORT_BTNS={
  sortNameBtn:    l=>(l.name||'').toLowerCase(),
  sortStageBtn:   l=>STAGE_ORDER.indexOf(l.stage||'Fresh'),
  sortSourceBtn:  l=>(l.source||'').toLowerCase(),
  sortDateBtn:    l=>l.createdAt||0,
  sortUpdatedBtn: l=>l.updatedAt||l.createdAt||0,
};
function applySortBtn(btnId){
  const prev=sortAscMap[btnId];
  if(prev==null)sortAscMap[btnId]=true; else if(prev===true)sortAscMap[btnId]=false; else{delete sortAscMap[btnId];}
  sortField=sortAscMap[btnId]!=null?btnId:null;
  Object.keys(SORT_BTNS).forEach(id=>{ const b=document.getElementById(id); if(!b)return; b.classList.remove('active-sort'); b.querySelector('svg').innerHTML='<path d="M3 6h18M7 12h10M11 18h2"/>'; });
  if(sortField){ const b=document.getElementById(btnId); if(b){ b.classList.add('active-sort'); b.querySelector('svg').innerHTML=sortAscMap[btnId]?'<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 4 20 7 17 10" style="stroke-width:1.8"/>':"<path d='M3 6h18M7 12h10M11 18h2'/><polyline points='17 14 20 17 17 20' style='stroke-width:1.8'/>"; } }
  currentPage=1; renderTable();
}
Object.keys(SORT_BTNS).forEach(btnId=>{ document.getElementById(btnId)?.addEventListener('click',()=>applySortBtn(btnId)); });

/* ═══════════════════════════════════════════════════
   GET DISPLAY LIST
═══════════════════════════════════════════════════ */
function getDisplayList(){
  let list=[...leads];
  const q=searchQuery.trim().toLowerCase();
  if(q) list=list.filter(l=>(l.id && l.id.toLowerCase() === q)||(l.name||'').toLowerCase().includes(q)||(l.phone||'').includes(q));
  list=applyGlobalFilter(list);
  Object.entries(activeFilters).forEach(([field,set])=>{ if(!set.size)return; const cfg=FILTER_CONFIG[field]; list=list.filter(l=>set.has(cfg.getValue(l))); });
  if(activeDateFilter.size) list=list.filter(l=>{ if(!l.createdAt)return false; const d=new Date(l.createdAt); const ym=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'); return activeDateFilter.has(ym); });
  if(activeUpdatedDateFilter.size) list=list.filter(l=>{ const ts=l.updatedAt||l.createdAt; if(!ts)return false; const d=new Date(ts); const ym=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'); return activeUpdatedDateFilter.has(ym); });
  if(sortField&&sortAscMap[sortField]!=null){ const getVal=SORT_BTNS[sortField]; const asc=sortAscMap[sortField]; list.sort((a,b)=>{ const va=getVal(a),vb=getVal(b); if(typeof va==='number')return asc?va-vb:vb-va; return asc?String(va).localeCompare(String(vb)):String(vb).localeCompare(String(va)); }); }
  return list;
}

/* ═══════════════════════════════════════════════════
   PAGINATION
═══════════════════════════════════════════════════ */
function goPage(p){ if(p<1||p>totalPages)return; currentPage=p; renderTable(); }
function changePageSize(val){
  PAGE_SIZE=parseInt(val)||100;
  currentPage=1;
  renderTable();
}
function renderPagination(total){
  totalPages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  if(currentPage>totalPages)currentPage=totalPages;
  const bar=document.getElementById('paginationBar');
  bar.style.display='flex';
  const sizeSel=document.getElementById('pgSizeSelect');
  if(sizeSel&&sizeSel.value!==String(PAGE_SIZE))sizeSel.value=String(PAGE_SIZE);
  const start=total?(currentPage-1)*PAGE_SIZE+1:0,end=Math.min(currentPage*PAGE_SIZE,total);
  document.getElementById('pgInfo').textContent='Showing '+start+'–'+end+' of '+total+' leads';
  document.getElementById('pgFirst').disabled=currentPage===1;
  document.getElementById('pgPrev').disabled=currentPage===1;
  document.getElementById('pgNext').disabled=currentPage===totalPages;
  document.getElementById('pgLast').disabled=currentPage===totalPages;
  const nums=document.getElementById('pgNumbers'); nums.innerHTML='';
  let s=Math.max(1,currentPage-2),e=Math.min(totalPages,s+4);s=Math.max(1,e-4);
  if(s>1){addPgNum(nums,1);if(s>2)nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>');}
  for(let i=s;i<=e;i++)addPgNum(nums,i);
  if(e<totalPages){if(e<totalPages-1)nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>');addPgNum(nums,totalPages);}
}
function addPgNum(container,n){ const b=document.createElement('button'); b.className='pg-btn'+(n===currentPage?' active':''); b.textContent=n; b.onclick=()=>goPage(n); container.appendChild(b); }

/* ═══════════════════════════════════════════════════
   RENDER TABLE
═══════════════════════════════════════════════════ */
function renderTable(){
  const list=getDisplayList();

  // KPIs (always from full leads)
  document.getElementById('kpiTotal').textContent=leads.length;
  document.getElementById('kpiFresh').textContent=leads.filter(l=>l.stage==='Fresh').length;
  document.getElementById('kpiFollowup').textContent=leads.filter(l=>l.stage==='Follow-up').length;
  document.getElementById('kpiMeeting').textContent=leads.filter(l=>l.stage==='Meeting').length;
  document.getElementById('kpiInterested').textContent=leads.filter(l=>l.stage==='Interested').length;
  document.getElementById('kpiNotReached').textContent=leads.filter(l=>l.stage==='Not Reached').length;
  document.getElementById('kpiNotInterested').textContent=leads.filter(l=>l.stage==='Not Interested').length;

  // Global filter counts
  const followupCount=leads.filter(l=>l.stage==='Follow-up').length;
  const meetingCount=leads.filter(l=>l.stage==='Meeting').length;
  const todayCount=leads.filter(l=>(l.history||[]).some(h=>{ if(h.type==='followup'&&h.reminderDate){const t=new Date(h.reminderDate);const n=new Date();return t.toDateString()===n.toDateString();} if(h.type==='followup'&&h.callbackDate){const t=new Date(h.callbackDate);const n=new Date();return t.toDateString()===n.toDateString();} if(h.type==='meeting'&&h.meetingDate){const t=new Date(h.meetingDate);const n=new Date();return t.toDateString()===n.toDateString();}return false;})).length;
  const fc=document.getElementById('gfFollowupsCount'); if(fc)fc.textContent=followupCount||'';
  const mc=document.getElementById('gfMeetingsCount'); if(mc)mc.textContent=meetingCount||'';
  const tc=document.getElementById('gfTodayCount'); if(tc)tc.textContent=todayCount||'';

  // Search hint
  const anyFilter=Object.values(activeFilters).some(s=>s.size>0)||activeDateFilter.size>0;
  document.getElementById('searchHint').textContent=(searchQuery.trim()||anyFilter||globalFilter!=='all')?`${list.length} result${list.length!==1?'s':''} found`:`${leads.length} lead${leads.length!==1?'s':''}`;

  renderPagination(list.length);
  const tbody=document.getElementById('tableBody');
  if(!list.length){
    tbody.innerHTML=`<tr class="no-results-row"><td colspan="9"><div class="no-results-icon"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span>No leads found</span></div></td></tr>`;
    return;
  }
  const pageData=list.slice((currentPage-1)*PAGE_SIZE,currentPage*PAGE_SIZE);
  tbody.innerHTML=pageData.map(l=>{
    const stageClass=STAGE_CLASS[l.stage]||'stage-fresh';
    const inactive=l.active===false;
    const sla=fmtSla(getSlaMs(l));
    const statusHtml=inactive?'<span class="status-badge status-inactive"><span class="status-dot"></span>Inactive</span>':'<span class="status-badge status-active"><span class="status-dot"></span>Active</span>';
    let srcLabel = '—';
    let srcIconKey = 'Other';
    if (l.broker) {
      srcLabel = 'Broker';
      srcIconKey = 'Broker';
    } else if (l.campaign) {
      const typeLabel = CAMP_TYPE_LABELS[l.campaign_child_type] || 'Campaign';
      srcLabel = typeLabel;
      srcIconKey = typeLabel;
    } else {
      srcLabel = l.source || '—';
      srcIconKey = l.source || 'Other';
    }
    const hasPopover = !!l.broker || !!l.campaign;
    const sourceHtml = `<span class="source-tag"${hasPopover ? ` onclick="openSrcPopover('${l.id}',event)" title="View details"` : ' style="cursor:default"'}><svg viewBox="0 0 24 24">${SRC_ICONS[srcIconKey]||SRC_ICONS['Other']}</svg>${escHtml(srcLabel)}</span>`;
    return `<tr class="${inactive?'lead-inactive':''}">
      <td style="text-align:left">
        <div style="font-weight:500">${escHtml(l.name)}</div>
      </td>
      <td style="font-size:.82rem;letter-spacing:.03em">
        ${l.phone?`<span class="phone-link" onclick="openPhoneModal('${l.id}',event)" title="Copy / WhatsApp"><svg viewBox="0 0 24 24"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/></svg>${fmtPhone(l.phone)}</span>`:'—'}
      </td>
      <td>${sourceHtml}</td>
      <td><span class="stage-badge ${stageClass}">${escHtml(l.stage||'Fresh')}</span></td>
      <td>${inactive?'<span style="color:var(--clr-gray);font-size:.78rem">—</span>':sla.html}</td>
      <td>${statusHtml}</td>
      <td style="font-size:.78rem;color:var(--clr-text-sub)">${fmtDate(l.createdAt)}</td>
      <td style="font-size:.78rem;color:var(--clr-text-sub)">${fmtDate(l.updatedAt||l.createdAt)}</td>
      <td>
        <div class="action-btns">
          ${(!inactive && (getSlaMs(l) === null || getSlaMs(l) > 0))?`<button class="action-btn stage-btn" title="Update Stage" onclick="openStageModal('${l.id}')"><svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></button>`:'<div style="width:32px"></div>'}
          <button class="action-btn history" title="View History" onclick="openHistoryModal('${l.id}')"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

/* ═══════════════════════════════════════════════════
   STAGE UPDATE VALIDATION
═══════════════════════════════════════════════════ */
function validateStageForm() {
  const saveBtn = document.getElementById('stageModalSave');
  if (!saveBtn) return;

  if (!_selectedStage) {
    saveBtn.style.display = 'none';
    return;
  }

  let isValid = true;
  if (_selectedStage === 'Not Interested') {
    const val = document.getElementById('stageReason').value;
    if (!val) isValid = false;
  } else if (_selectedStage === 'Frozen') {
    const val = parseInt(document.getElementById('frozenDays').value);
    if (!val || val < 1) isValid = false;
  } else if (_selectedStage === 'Meeting') {
    const val = document.getElementById('meetingDate').value;
    if (!val) isValid = false;
  } else if (_selectedStage === 'Follow-up') {
    const val = document.getElementById('reminderDate').value;
    if (!val) isValid = false;
  }

  saveBtn.style.display = isValid ? '' : 'none';
}

document.getElementById('stageReason')?.addEventListener('change', validateStageForm);
document.getElementById('frozenDays')?.addEventListener('input', validateStageForm);
document.getElementById('meetingDate')?.addEventListener('input', validateStageForm);
document.getElementById('reminderDate')?.addEventListener('input', validateStageForm);

/* ═══════════════════════════════════════════════════
   SEARCH
═══════════════════════════════════════════════════ */
document.getElementById('searchInput').addEventListener('input',e=>{ searchQuery=e.target.value; currentPage=1; renderTable(); });

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
   SLA TIMER TICK
═══════════════════════════════════════════════════ */
setInterval(()=>{
  const rows=document.querySelectorAll('#tableBody tr:not(.no-results-row)');
  const pageData=getDisplayList().slice((currentPage-1)*PAGE_SIZE,currentPage*PAGE_SIZE);
  rows.forEach((row,i)=>{
    const l=pageData[i]; if(!l||l.active===false)return;
    const cells=row.querySelectorAll('td');
    if(cells[4]) cells[4].innerHTML=fmtSla(getSlaMs(l)).html;
    if(getSlaMs(l) !== null && getSlaMs(l) <= 0) {
      const stageBtn = row.querySelector('.action-btn.stage-btn');
      if (stageBtn) {
        const parent = stageBtn.parentElement;
        const spacer = document.createElement('div');
        spacer.style.width = '32px';
        parent.replaceChild(spacer, stageBtn);
      }
    }
  });
},1000);

/* ═══════════════════════════════════════════════════
   EXPORT
═══════════════════════════════════════════════════ */
document.getElementById('btnExport').addEventListener('click',()=>{
  const list=getDisplayList();
  const headers=['Name','Phone','Source','Stage','Status','Created','Last Updated'];
  const rows=list.map(l=>[l.name,l.phone,l.source,l.stage,l.active===false?'Inactive':'Active',fmtDate(l.createdAt),fmtDate(l.updatedAt||l.createdAt)]);
  const csv=[headers,...rows].map(r=>r.map(c=>`"${String(c||'').replace(/"/g,'""')}"`).join(',')).join('\n');
  const blob=new Blob([csv],{type:'text/csv'}); const url=URL.createObjectURL(blob);
  const a=document.createElement('a'); a.href=url; a.download='sales-leads.csv'; a.click(); URL.revokeObjectURL(url);
  showToast('success','Exported',`${list.length} leads exported.`);
});

/* ═══════════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════════ */
const urlParams = new URLSearchParams(window.location.search);
const searchParam = urlParams.get('search');
if (searchParam) {
  searchQuery = searchParam.trim();
  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.value = searchQuery;
  }
  window.history.replaceState({}, document.title, window.location.pathname);
}
loadLeadsFromServer().then(()=>{
  if (searchQuery) {
    globalFilter = 'all';
    document.querySelectorAll('.gf-btn').forEach(b=>b.classList.remove('active'));
    document.getElementById('gfAll')?.classList.add('active');
    currentPage = 1;
    renderTable();
  } else {
    setGlobalFilter('all');
  }
});
// Refresh the dataset periodically so SLA/stage changes by others show up.
setInterval(()=>{ loadLeadsFromServer().then(renderTable); }, 60000);

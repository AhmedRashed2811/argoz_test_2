/* ═══════════════════════════════════════════════════
   DATA — loaded from the backend via AJAX (no localStorage).
   CFG (URLs + CSRF) is injected by the template. This is the
   admin "All Leads" database view, limited to leads.lead.view_all.
═══════════════════════════════════════════════════ */
const CFG = window.ALL_LEADS_CFG || {};
let leads = [];
let SALESMEN = [];   // [{id,name,team,team_id}] loaded for the Edit modal
let TEAMS_LIST = []; // [{id,name}] loaded for the Edit modal

function ajaxGet(url){ return fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'}}).then(r=>r.json()); }
function ajaxPost(url,body){
  return fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':CFG.csrf,'X-Requested-With':'XMLHttpRequest'},body:JSON.stringify(body)})
    .then(async r=>{ const d=await r.json().catch(()=>({})); if(!r.ok||d.ok===false) throw new Error(d.error||'Request failed'); return d; });
}
function loadLeadsFromServer(){
  return ajaxGet(CFG.urls.leads).then(d=>{ leads=(d.leads||[]); }).catch(()=>{ leads=[]; });
}

/* ── Avatar colour helpers (display only) ── */
const AGENT_COLORS = ['#e07b20','#2980b9','#8e44ad','#27ae60','#c0392b','#1abc9c','#d68910','#7f8c8d'];
function agentColor(name){ let h=0;for(const c of (name||''))h=(h*31+c.charCodeAt(0))%AGENT_COLORS.length; return AGENT_COLORS[h]; }
function agentInitials(name){ return (name||'?').split(' ').map(w=>w[0]||'').join('').slice(0,2).toUpperCase(); }

/* ═══════════════════════════════════════════════════
   STATE
═══════════════════════════════════════════════════ */
let searchQuery='', currentPage=1, totalPages=1, PAGE_SIZE=100;
let stageEditId=null, _selectedStage=null;
let lifecycleEditId=null, _selectedLifecycle=null;
let deactivateEditId=null;
let historyLeadId=null, historyTab='all';
let sortField=null, sortAscMap={};
let globalFilter='all';
let openFilterKey=null;
let filterDateOpen=false, filterUpdatedOpen=false;
const activeDateFilter=new Set(), _dateTreeOpenYears=new Set();
const activeUpdatedDateFilter=new Set(), _updatedTreeOpenYears=new Set();

const STAGE_ORDER=['Fresh','Follow-up','Meeting','Interested','Not Interested','Not Reached','Frozen'];
const STAGE_CLASS={
  'Fresh':'stage-fresh','Follow-up':'stage-followup','Meeting':'stage-meeting',
  'Interested':'stage-interested','Not Interested':'stage-notinterested',
  'Not Reached':'stage-notreached','Frozen':'stage-frozen'
};
const LIFECYCLE_CLASS={'New':'lc-new','Warm':'lc-warm','Hot':'lc-hot','Cold':'lc-cold','Dead':'lc-dead'};
const LIFECYCLE_ORDER=['New','Warm','Hot','Cold','Dead'];

/* ── Filter config (mutually dependent) ── */
const activeFilters={name:new Set(),phone:new Set(),source:new Set(),stage:new Set(),status:new Set(),lifecycle:new Set(),assigned:new Set(),createdBy:new Set(),team:new Set()};
const FILTER_CONFIG={
  name:      {dd:'filterNameDropdown',      btn:'filterNameBtn',      list:'filterNameList',      search:'filterNameSearch',      getValue:l=>l.name||''},
  phone:     {dd:'filterPhoneDropdown',     btn:'filterPhoneBtn',     list:'filterPhoneList',     search:'filterPhoneSearch',     getValue:l=>fmtPhone(l.phone)||''},
  source:    {dd:'filterSourceDropdown',    btn:'filterSourceBtn',    list:'filterSourceList',    search:null,                    getValue:l=>l.source||''},
  stage:     {dd:'filterStageDropdown',     btn:'filterStageBtn',     list:'filterStageList',     search:null,                    getValue:l=>l.stage||'Fresh'},
  status:    {dd:'filterStatusDropdown',    btn:'filterStatusBtn',    list:'filterStatusList',    search:null,                    getValue:l=>l.active===false?'Inactive':'Active'},
  lifecycle: {dd:'filterLifecycleDropdown', btn:'filterLifecycleBtn', list:'filterLifecycleList', search:null,                    getValue:l=>l.lifecycle||'New'},
  assigned:  {dd:'filterAssignedDropdown',  btn:'filterAssignedBtn',  list:'filterAssignedList',  search:'filterAssignedSearch',  getValue:l=>l.assignedTo||''},
  createdBy: {dd:'filterCreatedByDropdown', btn:'filterCreatedByBtn', list:'filterCreatedByList', search:'filterCreatedBySearch', getValue:l=>l.createdBy||''},
  team:      {dd:'filterTeamDropdown',      btn:'filterTeamBtn',      list:'filterTeamList',      search:null,                    getValue:l=>l.team||''},
};

/* ═══════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════ */
function escHtml(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function fmtDate(ts){if(!ts)return'—';const d=new Date(ts);return['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()]+' '+d.getDate()+', '+d.getFullYear();}
function fmtDatetime(ts){if(!ts)return'—';const d=new Date(ts);return fmtDate(ts)+' '+d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});}
function fmtPhone(p){if(!p)return'—';return String(p).trim();}

/* ── SLA ── */
function getSlaMs(l){ if(!l.slaDeadline) return -1; return l.slaDeadline - Date.now(); }
function fmtSla(ms){
  if(ms<=0)return{html:'<span class="sla-timer sla-expired">Expired</span>',ms};
  const h=Math.floor(ms/3600000),m=Math.floor((ms%3600000)/60000),s=Math.floor((ms%60000)/1000);
  const pad=n=>String(n).padStart(2,'0');
  const cls=ms<3600000?'sla-urgent':ms<7200000?'sla-warn':'sla-ok';
  return{html:`<span class="sla-timer ${cls}">${pad(h)}:${pad(m)}:${pad(s)}</span>`,ms};
}

/* ── Source icons ── */
const SRC_ICONS={
  'Event':          '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  'Social Media Ad':'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/>',
  'TV Ad':          '<rect x="2" y="7" width="20" height="15" rx="2"/><polyline points="17 2 12 7 7 2"/>',
  'Street Ad':      '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
  'Exhibition':     '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/>',
  'Campaign':       '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  'Broker':         '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  'Other':          '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
};
const SPEC_LABEL={'Event':'Event Name','Exhibition':'Exhibition Name','TV Ad':'Ad Name','Street Ad':'Location / Ad Name','Social Media Ad':'Ad / Post Name','Campaign':'Event / Ad Name','Other':'Details'};

/* ═══════════════════════════════════════════════════
   PHONE POPOVER
═══════════════════════════════════════════════════ */
let _phoneDigits='';
function openPhoneModal(id,evt){
  const l=leads.find(x=>x.id===id);if(!l||!l.phone)return;
  if(evt)evt.stopPropagation();
  _phoneDigits=String(l.phone).replace(/\D/g,'');
  document.getElementById('phoneModalNumber').textContent=fmtPhone(l.phone);
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

/* ═══════════════════════════════════════════════════
   STAGE MODAL
═══════════════════════════════════════════════════ */
const NEXT_ACTIONS={
  'Follow-up':[{val:'reminder',label:'📅 Set a reminder to call back',type:'reminder'}],
  'Meeting':  [{val:'meeting',label:'🗓 Schedule a meeting',type:'meeting'}],
  'Interested':[{val:'proposal',label:'📋 Send proposal / offer details'}],
  'Fresh':    [{val:'call',label:'📞 Plan a call'}],
  'Not Reached':[{val:'retry',label:'🔄 Retry call later'}],
  'Frozen':   [{val:'frozenCall',label:'❄️ Call back after a period',type:'frozenCall'}],
};

if (((window.ALL_LEADS_CFG && window.ALL_LEADS_CFG.not_reached_reminder_mode) || 'AUTOMATIC') === 'MANUAL') {
  NEXT_ACTIONS['Not Reached'] = [{val:'retry',label:'📅 Set a reminder to retry call later',type:'reminder'}];
}

function openStageModal(id){
  const l=leads.find(x=>x.id===id);if(!l)return;
  stageEditId=id;_selectedStage=null;
  document.getElementById('stageModalSub').textContent='Lead: '+l.name;
  const current=l.stage||'Fresh';
  document.querySelectorAll('.stage-opt').forEach(opt=>{
    const txt=opt.textContent.replace(/[\u{1F7E2}\u{1F535}\u{1F7E3}\u{1F7E0}\u{1F534}\u26AA\u274C\u2764\uFE0F\u2744\uFE0F]\s*/gu,'').trim();
    opt.classList.remove('selected');
    // Hide the stage the lead is already in (e.g. Interested \u2192 no Interested option).
    opt.style.display = (txt===current) ? 'none' : '';
  });
  document.getElementById('stageFeedbackSection').classList.remove('show');
  ['stageFeedback','stageReason','reminderDate','reminderTime','meetingDate','meetingTime','meetingLocation','frozenDays'].forEach(id=>{ try{document.getElementById(id).value='';}catch(e){} });
  // The save button only appears once a target stage is picked.
  document.getElementById('stageModalSave').style.display='none';
  document.getElementById('stageModal').classList.add('open');
}

function selectStage(val,el){
  _selectedStage=val;
  document.querySelectorAll('.stage-opt').forEach(o=>o.classList.remove('selected'));
  el.classList.add('selected');
  renderStageFeedbackSection(val);
}

function renderStageFeedbackSection(stage){
  const sec=document.getElementById('stageFeedbackSection');
  sec.classList.add('show');
  document.getElementById('stageModalSave').style.display='';
  document.getElementById('reasonGroup').style.display=stage==='Not Interested'?'':'none';
  document.getElementById('nextActionSection').style.display=stage==='Not Interested'?'none':'';
  ['reminderDateRow','meetingDateRow','meetingLocationRow','frozenDaysRow'].forEach(id=>document.getElementById(id).classList.add('field-hidden'));
  // Not Reached = nobody answered, so there is nothing to summarise.
  const fbGroup=document.getElementById('stageFeedback').closest('.form-group');
  if(fbGroup) fbGroup.style.display = stage==='Not Reached' ? 'none' : '';
  document.getElementById('feedbackLabel').textContent=stage==='Not Interested'?'Additional Notes (optional)':'Feedback / Call Summary';
  const grid=document.getElementById('nextActionGrid');grid.innerHTML='';
  const actions=NEXT_ACTIONS[stage]||[];
  actions.forEach((a,i)=>{
    const div=document.createElement('div');div.className='next-action-opt';div.dataset.val=a.val;div.dataset.type=a.type||'';
    div.innerHTML=`<input type="radio" name="nextAction" value="${a.val}"> ${a.label}`;
    div.onclick=()=>{div.querySelector('input').checked=true;onNextActionSelect(a.val,a.type);document.querySelectorAll('.next-action-opt').forEach(o=>o.classList.toggle('selected',o===div));};
    grid.appendChild(div);
    if(actions.length===1&&i===0){div.querySelector('input').checked=true;div.classList.add('selected');onNextActionSelect(a.val,a.type);}
  });
}

function onNextActionSelect(val,type){
  document.getElementById('reminderDateRow').classList.toggle('field-hidden',type!=='reminder');
  document.getElementById('meetingDateRow').classList.toggle('field-hidden',type!=='meeting');
  document.getElementById('meetingLocationRow').classList.toggle('field-hidden',type!=='meeting');
  document.getElementById('frozenDaysRow').classList.toggle('field-hidden',type!=='frozenCall');
}

function closeStageModal(){document.getElementById('stageModal').classList.remove('open');stageEditId=null;_selectedStage=null;}
document.getElementById('stageModalClose').addEventListener('click',closeStageModal);
document.getElementById('stageModalCancel').addEventListener('click',closeStageModal);
document.getElementById('stageModal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeStageModal();});

document.getElementById('stageModalSave').addEventListener('click',()=>{
  if(!stageEditId||!_selectedStage)return;
  const l=leads.find(x=>x.id===stageEditId);if(!l)return;
  const feedback=document.getElementById('stageFeedback').value.trim();
  const reason=document.getElementById('stageReason').value;
  if(_selectedStage==='Not Interested'&&!reason){Swal.fire({title:'Reason required',text:'Please select a reason.',icon:'warning',confirmButtonColor:'var(--clr-orange)'});return;}
  const selEl=document.querySelector('.next-action-opt.selected');
  const nextVal=selEl?selEl.dataset.val:null,nextType=selEl?selEl.dataset.type:null;
  if(_selectedStage==='Frozen'&&nextType==='frozenCall'){const d=parseInt(document.getElementById('frozenDays').value);if(!d||d<1){Swal.fire({title:'Call-back period required',text:'Enter the number of days.',icon:'warning',confirmButtonColor:'var(--clr-orange)'});return;}}
  if(_selectedStage==='Meeting'&&!document.getElementById('meetingDate').value){Swal.fire({title:'Meeting date required',icon:'warning',confirmButtonColor:'var(--clr-orange)'});return;}
  if(_selectedStage==='Follow-up'&&!document.getElementById('reminderDate').value){Swal.fire({title:'Follow-up date required',icon:'warning',confirmButtonColor:'var(--clr-orange)'});return;}
  if(_selectedStage==='Not Reached'&&((window.ALL_LEADS_CFG && window.ALL_LEADS_CFG.not_reached_reminder_mode) || 'AUTOMATIC')==='MANUAL'&&!document.getElementById('reminderDate').value){Swal.fire({title:'Reminder date required',icon:'warning',confirmButtonColor:'var(--clr-orange)'});return;}

  // Route through the shared backend endpoint (services handle audit, history,
  // reminders and notifications server-side).
  const prev=l.stage;
  const payload={
    lead_id:l.id, stage_code:STAGE_CODE[_selectedStage]||'FRESH',
    feedback:feedback||'', reason:reason||'',
    reminder_date:document.getElementById('reminderDate').value||'',
    reminder_time:document.getElementById('reminderTime').value||'',
    meeting_date:document.getElementById('meetingDate').value||'',
    meeting_time:document.getElementById('meetingTime').value||'',
    meeting_location:document.getElementById('meetingLocation').value.trim()||'',
    frozen_days:parseInt(document.getElementById('frozenDays').value)||0,
  };
  const btn=document.getElementById('stageModalSave'); btn.disabled=true;
  ajaxPost(CFG.urls.stageUpdate,payload)
    .then(()=>loadLeadsFromServer())
    .then(()=>{ closeStageModal(); renderTable(); showToast('success','Stage Updated',`"${l.name}" → ${_selectedStage}`); })
    .catch(err=>Swal.fire({title:'Update failed',text:String(err.message||err),icon:'error',confirmButtonColor:'var(--clr-orange)'}))
    .finally(()=>{ btn.disabled=false; });
});

// Display stage label -> backend stage code.
const STAGE_CODE = {
  'Fresh':'FRESH','Follow-up':'FOLLOW_UP','Meeting':'MEETING','Interested':'INTERESTED',
  'Not Interested':'NOT_INTERESTED','Not Reached':'NOT_REACHED','Frozen':'FROZEN',
};

/* ═══════════════════════════════════════════════════
   LIFECYCLE MODAL
═══════════════════════════════════════════════════ */
function openLifecycleModal(id){
  const l=leads.find(x=>x.id===id);if(!l)return;
  lifecycleEditId=id;_selectedLifecycle=l.lifecycle||'New';
  document.getElementById('lifecycleModalSub').textContent='Lead: '+l.name;
  document.querySelectorAll('.lifecycle-opt').forEach(opt=>{
    const txt=opt.textContent.replace(/[🌱🔥🌋🧊💀\s]/gu,'').trim();
    opt.classList.toggle('selected',txt===_selectedLifecycle);
  });
  document.getElementById('lifecycleNote').value='';
  document.getElementById('lifecycleModal').classList.add('open');
}

function selectLifecycle(val,el){
  _selectedLifecycle=val;
  document.querySelectorAll('.lifecycle-opt').forEach(o=>o.classList.remove('selected'));
  el.classList.add('selected');
}

function closeLifecycleModal(){document.getElementById('lifecycleModal').classList.remove('open');lifecycleEditId=null;_selectedLifecycle=null;}
document.getElementById('lifecycleModalClose').addEventListener('click',closeLifecycleModal);
document.getElementById('lifecycleModalCancel').addEventListener('click',closeLifecycleModal);
document.getElementById('lifecycleModal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeLifecycleModal();});

document.getElementById('lifecycleModalSave').addEventListener('click',()=>{
  if(!lifecycleEditId||!_selectedLifecycle)return;
  const l=leads.find(x=>x.id===lifecycleEditId);if(!l)return;
  const note=document.getElementById('lifecycleNote').value.trim();
  const btn=document.getElementById('lifecycleModalSave'); btn.disabled=true;
  ajaxPost(CFG.urls.lifecycle,{lead_id:l.id,lifecycle:_selectedLifecycle,note:note})
    .then(()=>loadLeadsFromServer())
    .then(()=>{ closeLifecycleModal(); renderTable(); showToast('success','Lifecycle Updated',`"${l.name}" lifecycle set to ${_selectedLifecycle}`); })
    .catch(err=>Swal.fire({title:'Update failed',text:String(err.message||err),icon:'error',confirmButtonColor:'var(--clr-orange)'}))
    .finally(()=>{ btn.disabled=false; });
});

/* ═══════════════════════════════════════════════════
   DEACTIVATE MODAL
═══════════════════════════════════════════════════ */
function openDeactivateModal(id){
  const l=leads.find(x=>x.id===id);if(!l)return;
  deactivateEditId=id;
  const isActive=l.active!==false;
  document.getElementById('deactivateModalTitle').textContent=isActive?'Deactivate Lead':'Reactivate Lead';
  document.getElementById('deactivateModalSub').textContent='Lead: '+l.name;
  document.getElementById('deactivateModalMsg').textContent=isActive
    ?`Deactivating "${l.name}" will mark them as inactive and hide them from active pipelines. You can reactivate at any time.`
    :`Reactivating "${l.name}" will restore them to active status and restart the SLA timer.`;
  document.getElementById('deactivateReason').value='';
  document.getElementById('deactivateReason').placeholder=isActive?'Why is this lead being deactivated?':'Why is this lead being reactivated?';
  document.getElementById('deactivateModalSave').textContent=isActive?'Deactivate':'Reactivate';
  document.getElementById('deactivateModalSave').className=isActive?'btn-save-red':'btn-save';
  document.getElementById('deactivateModal').classList.add('open');
}

function closeDeactivateModal(){document.getElementById('deactivateModal').classList.remove('open');deactivateEditId=null;}
document.getElementById('deactivateModalClose').addEventListener('click',closeDeactivateModal);
document.getElementById('deactivateModalCancel').addEventListener('click',closeDeactivateModal);
document.getElementById('deactivateModal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeDeactivateModal();});

document.getElementById('deactivateModalSave').addEventListener('click',()=>{
  if(!deactivateEditId)return;
  const l=leads.find(x=>x.id===deactivateEditId);if(!l)return;
  const isActive=l.active!==false;
  const reason=document.getElementById('deactivateReason').value.trim();
  const btn=document.getElementById('deactivateModalSave'); btn.disabled=true;
  ajaxPost(CFG.urls.setActive,{lead_id:l.id,active:!isActive,reason:reason})
    .then(()=>loadLeadsFromServer())
    .then(()=>{ closeDeactivateModal(); renderTable(); showToast(isActive?'error':'success',isActive?'Lead Deactivated':'Lead Reactivated',`"${l.name}" has been ${isActive?'deactivated':'reactivated'}.`); })
    .catch(err=>Swal.fire({title:'Action failed',text:String(err.message||err),icon:'error',confirmButtonColor:'var(--clr-orange)'}))
    .finally(()=>{ btn.disabled=false; });
});

/* ═══════════════════════════════════════════════════
   HISTORY MODAL
═══════════════════════════════════════════════════ */
function openHistoryModal(id){
  const l=leads.find(x=>x.id===id);if(!l)return;
  historyLeadId=id;historyTab='all';
  document.getElementById('historyModalSub').textContent=l.name+' · '+fmtPhone(l.phone);
  // Lead info summary
  const team=l.team||'—';
  document.getElementById('historyLeadInfo').innerHTML=`
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Stage</div><span class="stage-badge ${STAGE_CLASS[l.stage]||'stage-fresh'}">${escHtml(l.stage||'Fresh')}</span></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Lifecycle</div><span class="lifecycle-badge ${LIFECYCLE_CLASS[l.lifecycle||'New']||'lc-new'}">${escHtml(l.lifecycle||'New')}</span></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Status</div>${l.active===false?'<span class="status-badge status-inactive"><span class="status-dot"></span>Inactive</span>':'<span class="status-badge status-active"><span class="status-dot"></span>Active</span>'}</div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Assigned To</div><div style="font-size:.82rem;color:var(--clr-text);font-weight:500">${escHtml(l.assignedTo||'—')}</div></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Team</div><div style="font-size:.82rem;color:var(--clr-text);font-weight:500">${escHtml(team)}</div></div>
      <div><div style="font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--clr-text-sub);margin-bottom:3px">Created By</div><div style="font-size:.82rem;color:var(--clr-text);font-weight:500">${escHtml(l.createdBy||'—')}</div></div>
    </div>`;
  document.querySelectorAll('.history-tab').forEach((t,i)=>t.classList.toggle('active',i===0));
  document.getElementById('historyContent').innerHTML='<div class="history-empty">Loading…</div>';
  document.getElementById('historyModal').classList.add('open');
  // History is built server-side from stage/assignment/follow-up/meeting/note records.
  ajaxGet(CFG.urls.history+'?lead_id='+encodeURIComponent(id))
    .then(d=>{ l.history=d.history||[]; if(historyLeadId===id) renderHistoryContent(l); })
    .catch(()=>{ document.getElementById('historyContent').innerHTML='<div class="history-empty">Could not load history.</div>'; });
}

function closeHistoryModal(){document.getElementById('historyModal').classList.remove('open');historyLeadId=null;}
document.getElementById('historyModalClose').addEventListener('click',closeHistoryModal);
document.getElementById('historyModalClose2').addEventListener('click',closeHistoryModal);
document.getElementById('historyModal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeHistoryModal();});

function switchHistoryTab(tab,el){
  historyTab=tab;
  document.querySelectorAll('.history-tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  const l=leads.find(x=>x.id===historyLeadId);if(!l)return;
  renderHistoryContent(l);
}

function renderHistoryContent(l){
  const cont=document.getElementById('historyContent');
  const allH=[...(l.history||[])].sort((a,b)=>(b.ts||0)-(a.ts||0));
  const dotIcons={
    created:'<polyline points="20 6 9 17 4 12"/>',
    stage:'<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    meeting:'<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    followup:'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/>',
    lifecycle:'<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
    note:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
  };
  // person who acted — stored on entry if available, fall back to lead's assigned agent
  function byWhom(h){ return h.by || h.agent || l.assignedTo || null; }

  function bodyOf(h){
    let b='';
    // Who performed this step
    const who = byWhom(h);
    if(who) b+=`<div class="history-body" style="margin-top:6px">👤 By: <strong>${escHtml(who)}</strong></div>`;
    // Meeting details
    if(h.type==='meeting'){
      if(h.meetingDate){
        let dateStr=escHtml(h.meetingDate);
        if(h.meetingTime) dateStr+=' at '+escHtml(h.meetingTime);
        b+=`<div class="history-body" style="margin-top:6px">📅 Meeting date: <strong>${dateStr}</strong></div>`;
      }
      if(h.meetingLocation) b+=`<div class="history-body" style="margin-top:6px">📍 Location: ${escHtml(h.meetingLocation)}</div>`;
      if(h.feedback)        b+=`<div class="history-body" style="margin-top:6px">📝 Notes: ${escHtml(h.feedback)}</div>`;
    }
    // Follow-up details
    else if(h.type==='followup'){
      if(h.reminderDate){
        let dateStr=escHtml(h.reminderDate);
        if(h.reminderTime) dateStr+=' at '+escHtml(h.reminderTime);
        b+=`<div class="history-body" style="margin-top:6px">⏰ Follow-up date: <strong>${dateStr}</strong></div>`;
      }
      if(h.callbackDate) b+=`<div class="history-body" style="margin-top:6px">❄️ Call back on: <strong>${escHtml(h.callbackDate)}</strong> (${h.frozenDays} day${h.frozenDays===1?'':'s'} after freezing)</div>`;
      if(h.feedback)     b+=`<div class="history-body" style="margin-top:6px">📝 Notes: ${escHtml(h.feedback)}</div>`;
    }
    // Other entry types
    else{
      if(h.feedback)       b+=`<div class="history-body" style="margin-top:6px">📝 ${escHtml(h.feedback)}</div>`;
      if(h.reason)         b+=`<div class="history-body" style="margin-top:6px">🚫 Reason: ${escHtml(h.reason)}</div>`;
      if(h.prevLifecycle)  b+=`<div class="history-body" style="margin-top:6px">🔄 ${escHtml(h.prevLifecycle)} → ${escHtml(h.newLifecycle||'')}</div>`;
    }
    return b;
  }
  function itemHtml(h){
    const dc=h.type||'note',ic=dotIcons[dc]||dotIcons.note;
    return `<div class="history-item"><div class="history-dot ${dc}"><svg viewBox="0 0 24 24">${ic}</svg></div><div class="history-content"><div class="history-label">${escHtml(h.label)}</div><div class="history-meta">${fmtDatetime(h.ts)}</div>${bodyOf(h)}</div></div>`;
  }
  const meetings=allH.filter(h=>h.type==='meeting');
  const followups=allH.filter(h=>h.type==='followup');
  document.getElementById('tabCountAll').textContent=allH.length;
  document.getElementById('tabCountMeetings').textContent=meetings.length;
  document.getElementById('tabCountFollowups').textContent=followups.length;
  if(!allH.length){cont.innerHTML='<div class="history-empty">No activity found.</div>';return;}
  if(historyTab==='meetings'){cont.innerHTML=meetings.length?'<div class="history-timeline">'+meetings.map(itemHtml).join('')+'</div>':'<div class="history-empty">No meetings yet.</div>';return;}
  if(historyTab==='followups'){cont.innerHTML=followups.length?'<div class="history-timeline">'+followups.map(itemHtml).join('')+'</div>':'<div class="history-empty">No follow-ups yet.</div>';return;}
  cont.innerHTML='<div class="history-timeline">'+allH.map(itemHtml).join('')+'</div>';
}

/* ═══════════════════════════════════════════════════
   GLOBAL FILTER
═══════════════════════════════════════════════════ */
function setGlobalFilter(f){
  globalFilter=f;
  document.querySelectorAll('.gf-btn').forEach(b=>b.classList.remove('active'));
  const map={all:'gfAll',followups:'gfFollowups',meetings:'gfMeetings',today:'gfTodayActions',active:'gfActive',inactive:'gfInactive'};
  if(map[f])document.getElementById(map[f])?.classList.add('active');
  currentPage=1;renderTable();
}
function clearGlobalFilter(){setGlobalFilter('all');}
function kpiFilter(stageOrAll){
  if(stageOrAll==='all'){globalFilter='all';document.querySelectorAll('.gf-btn').forEach(b=>b.classList.remove('active'));document.getElementById('gfAll')?.classList.add('active');}
  else{globalFilter='kpi:'+stageOrAll;document.querySelectorAll('.gf-btn').forEach(b=>b.classList.remove('active'));}
  currentPage=1;renderTable();
}
function clearAllFiltersAndGlobal(){
  Object.keys(activeFilters).forEach(f=>activeFilters[f].clear());
  activeDateFilter.clear();activeUpdatedDateFilter.clear();
  searchQuery='';document.getElementById('searchInput').value='';
  setGlobalFilter('all');
}

function applyGlobalFilter(list){
  const now=Date.now();
  if(globalFilter==='followups')return list.filter(l=>l.stage==='Follow-up');
  if(globalFilter==='meetings')return list.filter(l=>l.stage==='Meeting');
  if(globalFilter==='active')return list.filter(l=>l.active!==false);
  if(globalFilter==='inactive')return list.filter(l=>l.active===false);
  if(globalFilter==='today')return list.filter(l=>(l.history||[]).some(h=>{
    const check=d=>d&&new Date(d).toDateString()===new Date().toDateString();
    return(h.type==='followup'&&(check(h.reminderDate)||check(h.callbackDate)))||(h.type==='meeting'&&check(h.meetingDate));
  }));
  if(globalFilter.startsWith('kpi:'))return list.filter(l=>l.stage===globalFilter.slice(4));
  return list;
}

/* ═══════════════════════════════════════════════════
   FILTER SYSTEM (mutually dependent)
═══════════════════════════════════════════════════ */
function getUniqueValues(field){
  let base=[...leads];
  const q=searchQuery.trim().toLowerCase();
  if(q)base=base.filter(l=>(l.name||'').toLowerCase().includes(q)||(l.phone||'').includes(q)||(l.assignedTo||'').toLowerCase().includes(q)||(l.team||'').toLowerCase().includes(q));
  base=applyGlobalFilter(base);
  Object.entries(activeFilters).forEach(([f,set])=>{
    if(f===field||!set.size)return;
    const cfg=FILTER_CONFIG[f];
    base=base.filter(l=>set.has(cfg.getValue(l)));
  });
  if(activeDateFilter.size)base=base.filter(l=>{if(!l.createdAt)return false;const d=new Date(l.createdAt);return activeDateFilter.has(d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'));});
  if(activeUpdatedDateFilter.size)base=base.filter(l=>{const ts=l.updatedAt||l.createdAt;if(!ts)return false;const d=new Date(ts);return activeUpdatedDateFilter.has(d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'));});
  const cfg=FILTER_CONFIG[field];
  const vals=new Set();
  base.forEach(l=>{const v=cfg.getValue(l);if(v)vals.add(v);});
  if(field==='stage')return STAGE_ORDER.filter(s=>vals.has(s));
  if(field==='lifecycle')return LIFECYCLE_ORDER.filter(s=>vals.has(s));
  return [...vals].sort((a,b)=>a.localeCompare(b));
}

function renderFilterList(field){
  const cfg=FILTER_CONFIG[field];
  const list=document.getElementById(cfg.list);if(!list)return;
  const searchEl=cfg.search?document.getElementById(cfg.search):null;
  const q=searchEl?searchEl.value.toLowerCase():'';
  const vals=getUniqueValues(field);
  list.innerHTML='';
  vals.filter(v=>!q||v.toLowerCase().includes(q)).forEach(v=>{
    const id='flt_'+field+'_'+v.replace(/\W/g,'_');
    const div=document.createElement('div');div.className='filter-item';
    div.innerHTML=`<input type="checkbox" id="${id}" ${activeFilters[field].has(v)?'checked':''} onchange="toggleFilterItem('${field}','${escHtml(v).replace(/'/g,"\\'")}',this.checked)"><label for="${id}">${escHtml(v)}</label>`;
    list.appendChild(div);
  });
  if(!list.children.length)list.innerHTML='<div style="padding:12px 14px;font-size:.8rem;color:var(--clr-gray)">No values found</div>';
}

function toggleFilterItem(field,val,checked){
  if(checked)activeFilters[field].add(val);else activeFilters[field].delete(val);
  currentPage=1;renderTable();
  if(openFilterKey&&openFilterKey!==field)renderFilterList(openFilterKey);
  if(filterDateOpen)renderDateFilter();
  if(filterUpdatedOpen)renderUpdatedFilter();
}
function selectAllFilter(field){getUniqueValues(field).forEach(v=>activeFilters[field].add(v));renderFilterList(field);currentPage=1;renderTable();}
function clearAllFilter(field){activeFilters[field].clear();renderFilterList(field);currentPage=1;renderTable();}

function closeAllFilters(){
  Object.values(FILTER_CONFIG).forEach(cfg=>document.getElementById(cfg.dd)?.classList.remove('open'));
  document.getElementById('filterDateDropdown')?.classList.remove('open');
  document.getElementById('filterUpdatedDropdown')?.classList.remove('open');
  filterDateOpen=false;filterUpdatedOpen=false;openFilterKey=null;
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
  if(!isOpen){renderFilterList(field);positionDropdown(cfg.dd,cfg.btn);openFilterKey=field;if(cfg.search){const si=document.getElementById(cfg.search);if(si){si.value='';si.focus();}}}
}
Object.entries(FILTER_CONFIG).forEach(([field,cfg])=>{document.getElementById(cfg.btn)?.addEventListener('click',e=>{e.stopPropagation();toggleFilter(field);});});
document.addEventListener('click',e=>{if(!e.target.closest('.filter-dropdown')&&!e.target.closest('.th-icon-btn'))closeAllFilters();});

/* ── Date filter (Created) ── */
function buildDateTree(field,excludeDateField){
  let base=[...leads];
  const q=searchQuery.trim().toLowerCase();
  if(q)base=base.filter(l=>(l.name||'').toLowerCase().includes(q)||(l.phone||'').includes(q)||(l.assignedTo||'').toLowerCase().includes(q));
  base=applyGlobalFilter(base);
  Object.entries(activeFilters).forEach(([f,set])=>{if(!set.size)return;const cfg=FILTER_CONFIG[f];base=base.filter(l=>set.has(cfg.getValue(l)));});
  if(excludeDateField!=='createdAt'&&activeDateFilter.size)base=base.filter(l=>{if(!l.createdAt)return false;const d=new Date(l.createdAt);return activeDateFilter.has(d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'));});
  if(excludeDateField!=='updatedAt'&&activeUpdatedDateFilter.size)base=base.filter(l=>{const ts=l.updatedAt||l.createdAt;if(!ts)return false;const d=new Date(ts);return activeUpdatedDateFilter.has(d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'));});
  const map={};
  base.forEach(l=>{const ts=field==='updatedAt'?(l.updatedAt||l.createdAt):l.createdAt;if(!ts)return;const d=new Date(ts),year=String(d.getFullYear()),month=year+'-'+String(d.getMonth()+1).padStart(2,'0');if(!map[year])map[year]=new Set();map[year].add(month);});
  return map;
}
function renderDateTreeGeneric({containerId,field,activeSet,openYearsSet,excludeDateField}){
  const container=document.getElementById(containerId);if(!container)return;
  const tree=buildDateTree(field,excludeDateField);
  const monthNames=['January','February','March','April','May','June','July','August','September','October','November','December'];
  container.innerHTML='';
  Object.keys(tree).sort().reverse().forEach(year=>{
    const months=[...tree[year]].sort();
    const allChecked=months.every(m=>activeSet.has(m));
    const isOpen=openYearsSet.has(year);
    const wrapper=document.createElement('div');
    const yearRow=document.createElement('div');yearRow.className='date-tree-year';
    const cb=document.createElement('input');cb.type='checkbox';cb.style.cssText='accent-color:var(--clr-orange);width:14px;height:14px;cursor:pointer;margin-right:6px;flex-shrink:0';
    cb.checked=allChecked;cb.indeterminate=!allChecked&&months.some(m=>activeSet.has(m));
    cb.onchange=()=>{if(cb.checked)months.forEach(m=>activeSet.add(m));else months.forEach(m=>activeSet.delete(m));currentPage=1;renderTable();renderDateTreeGeneric({containerId,field,activeSet,openYearsSet,excludeDateField});if(openFilterKey)renderFilterList(openFilterKey);};
    const chev=document.createElement('span');chev.className='date-tree-chevron'+(isOpen?' open':'');chev.textContent='▶';
    yearRow.addEventListener('click',e=>{if(e.target===cb)return;if(openYearsSet.has(year))openYearsSet.delete(year);else openYearsSet.add(year);renderDateTreeGeneric({containerId,field,activeSet,openYearsSet,excludeDateField});});
    yearRow.appendChild(cb);const label=document.createElement('span');label.textContent=year;label.style.flex='1';yearRow.appendChild(label);yearRow.appendChild(chev);
    const monthsDiv=document.createElement('div');monthsDiv.className='date-tree-months'+(isOpen?' open':'');
    months.forEach(ym=>{const mLabel=document.createElement('label');mLabel.className='filter-item';const mCb=document.createElement('input');mCb.type='checkbox';mCb.checked=activeSet.has(ym);mCb.style.cssText='accent-color:var(--clr-orange);width:14px;height:14px;cursor:pointer;flex-shrink:0';mCb.onchange=()=>{if(mCb.checked)activeSet.add(ym);else activeSet.delete(ym);cb.checked=months.every(m=>activeSet.has(m));cb.indeterminate=!cb.checked&&months.some(m=>activeSet.has(m));currentPage=1;renderTable();if(openFilterKey)renderFilterList(openFilterKey);};const mNum=parseInt(ym.split('-')[1])-1;const mSpan=document.createElement('span');mSpan.style.cssText='font-size:.83rem;color:var(--clr-text)';mSpan.textContent=monthNames[mNum];mLabel.appendChild(mCb);mLabel.appendChild(mSpan);monthsDiv.appendChild(mLabel);});
    wrapper.appendChild(yearRow);wrapper.appendChild(monthsDiv);container.appendChild(wrapper);
  });
  if(!Object.keys(tree).length)container.innerHTML='<div style="padding:10px 14px;font-size:.82rem;color:var(--clr-text-sub)">No dates available</div>';
}
function renderDateFilter(){renderDateTreeGeneric({containerId:'filterDateList',field:'createdAt',activeSet:activeDateFilter,openYearsSet:_dateTreeOpenYears,excludeDateField:'createdAt'});}
function selectAllDateFilter(){const tree=buildDateTree('createdAt','createdAt');Object.values(tree).forEach(s=>s.forEach(m=>activeDateFilter.add(m)));currentPage=1;renderTable();renderDateFilter();if(openFilterKey)renderFilterList(openFilterKey);}
function clearAllDateFilter(){activeDateFilter.clear();currentPage=1;renderTable();renderDateFilter();if(openFilterKey)renderFilterList(openFilterKey);}
document.getElementById('filterDateBtn')?.addEventListener('click',e=>{e.stopPropagation();const isOpen=filterDateOpen;closeAllFilters();filterDateOpen=!isOpen;if(filterDateOpen){const dd=document.getElementById('filterDateDropdown');const r=document.getElementById('filterDateBtn').getBoundingClientRect();dd.classList.add('open');dd.style.top=r.bottom+4+'px';dd.style.left=Math.min(r.left,window.innerWidth-dd.offsetWidth-8)+'px';renderDateFilter();}});

function renderUpdatedFilter(){renderDateTreeGeneric({containerId:'filterUpdatedList',field:'updatedAt',activeSet:activeUpdatedDateFilter,openYearsSet:_updatedTreeOpenYears,excludeDateField:'updatedAt'});}
function selectAllUpdatedFilter(){const tree=buildDateTree('updatedAt','updatedAt');Object.values(tree).forEach(s=>s.forEach(m=>activeUpdatedDateFilter.add(m)));currentPage=1;renderTable();renderUpdatedFilter();if(openFilterKey)renderFilterList(openFilterKey);}
function clearAllUpdatedFilter(){activeUpdatedDateFilter.clear();currentPage=1;renderTable();renderUpdatedFilter();if(openFilterKey)renderFilterList(openFilterKey);}
document.getElementById('filterUpdatedBtn')?.addEventListener('click',e=>{e.stopPropagation();const isOpen=filterUpdatedOpen;closeAllFilters();filterUpdatedOpen=!isOpen;if(filterUpdatedOpen){const dd=document.getElementById('filterUpdatedDropdown');const r=document.getElementById('filterUpdatedBtn').getBoundingClientRect();dd.classList.add('open');dd.style.top=r.bottom+4+'px';dd.style.left=Math.min(r.left,window.innerWidth-dd.offsetWidth-8)+'px';renderUpdatedFilter();}});

/* ═══════════════════════════════════════════════════
   SORT
═══════════════════════════════════════════════════ */
const SORT_BTNS={
  sortNameBtn:     l=>(l.name||'').toLowerCase(),
  sortStageBtn:    l=>STAGE_ORDER.indexOf(l.stage||'Fresh'),
  sortSourceBtn:   l=>(l.source||'').toLowerCase(),
  sortDateBtn:     l=>l.createdAt||0,
  sortUpdatedBtn:  l=>l.updatedAt||l.createdAt||0,
  sortLifecycleBtn:l=>LIFECYCLE_ORDER.indexOf(l.lifecycle||'New'),
  sortAssignedBtn: l=>(l.assignedTo||'').toLowerCase(),
  sortTeamBtn:     l=>(l.team||'').toLowerCase(),
};
function applySortBtn(btnId){
  const prev=sortAscMap[btnId];
  if(prev==null)sortAscMap[btnId]=true;else if(prev===true)sortAscMap[btnId]=false;else{delete sortAscMap[btnId];}
  sortField=sortAscMap[btnId]!=null?btnId:null;
  Object.keys(SORT_BTNS).forEach(id=>{const b=document.getElementById(id);if(!b)return;b.classList.remove('active-sort');b.querySelector('svg').innerHTML='<path d="M3 6h18M7 12h10M11 18h2"/>';});
  if(sortField){const b=document.getElementById(btnId);if(b){b.classList.add('active-sort');b.querySelector('svg').innerHTML=sortAscMap[btnId]?'<path d="M3 6h18M7 12h10M11 18h2"/><polyline points="17 4 20 7 17 10" style="stroke-width:1.8"/>':"<path d='M3 6h18M7 12h10M11 18h2'/><polyline points='17 14 20 17 17 20' style='stroke-width:1.8'/>";}}
  currentPage=1;renderTable();
}
Object.keys(SORT_BTNS).forEach(btnId=>{document.getElementById(btnId)?.addEventListener('click',()=>applySortBtn(btnId));});

/* ═══════════════════════════════════════════════════
   GET DISPLAY LIST
═══════════════════════════════════════════════════ */
function getDisplayList(){
  let list=[...leads];
  const q=searchQuery.trim().toLowerCase();
  if(q)list=list.filter(l=>(l.name||'').toLowerCase().includes(q)||(l.phone||'').includes(q)||(l.assignedTo||'').toLowerCase().includes(q)||(l.team||'').toLowerCase().includes(q)||(l.createdBy||'').toLowerCase().includes(q));
  list=applyGlobalFilter(list);
  Object.entries(activeFilters).forEach(([field,set])=>{if(!set.size)return;const cfg=FILTER_CONFIG[field];list=list.filter(l=>set.has(cfg.getValue(l)));});
  if(activeDateFilter.size)list=list.filter(l=>{if(!l.createdAt)return false;const d=new Date(l.createdAt);return activeDateFilter.has(d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'));});
  if(activeUpdatedDateFilter.size)list=list.filter(l=>{const ts=l.updatedAt||l.createdAt;if(!ts)return false;const d=new Date(ts);return activeUpdatedDateFilter.has(d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0'));});
  if(sortField&&sortAscMap[sortField]!=null){const getVal=SORT_BTNS[sortField];const asc=sortAscMap[sortField];list.sort((a,b)=>{const va=getVal(a),vb=getVal(b);if(typeof va==='number')return asc?va-vb:vb-va;return asc?String(va).localeCompare(String(vb)):String(vb).localeCompare(String(va));});}
  return list;
}

/* ═══════════════════════════════════════════════════
   PAGINATION
═══════════════════════════════════════════════════ */
function goPage(p){if(p<1||p>totalPages)return;currentPage=p;renderTable();}
function changePageSize(val){PAGE_SIZE=parseInt(val)||100;currentPage=1;renderTable();}
function renderPagination(total){
  totalPages=Math.max(1,Math.ceil(total/PAGE_SIZE));
  if(currentPage>totalPages)currentPage=totalPages;
  const bar=document.getElementById('paginationBar');bar.style.display='flex';
  const sizeSel=document.getElementById('pgSizeSelect');if(sizeSel&&sizeSel.value!==String(PAGE_SIZE))sizeSel.value=String(PAGE_SIZE);
  const start=total?(currentPage-1)*PAGE_SIZE+1:0,end=Math.min(currentPage*PAGE_SIZE,total);
  document.getElementById('pgInfo').textContent='Showing '+start+'–'+end+' of '+total+' leads';
  document.getElementById('pgFirst').disabled=currentPage===1;
  document.getElementById('pgPrev').disabled=currentPage===1;
  document.getElementById('pgNext').disabled=currentPage===totalPages;
  document.getElementById('pgLast').disabled=currentPage===totalPages;
  const nums=document.getElementById('pgNumbers');nums.innerHTML='';
  let s=Math.max(1,currentPage-2),e=Math.min(totalPages,s+4);s=Math.max(1,e-4);
  if(s>1){addPgNum(nums,1);if(s>2)nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>');}
  for(let i=s;i<=e;i++)addPgNum(nums,i);
  if(e<totalPages){if(e<totalPages-1)nums.insertAdjacentHTML('beforeend','<span style="padding:0 3px;color:var(--clr-gray);font-size:.8rem">…</span>');addPgNum(nums,totalPages);}
}
function addPgNum(container,n){const b=document.createElement('button');b.className='pg-btn'+(n===currentPage?' active':'');b.textContent=n;b.onclick=()=>goPage(n);container.appendChild(b);}

/* ═══════════════════════════════════════════════════
   RENDER TABLE
═══════════════════════════════════════════════════ */
function renderTable(){
  const list=getDisplayList();

  // KPIs
  document.getElementById('kpiTotal').textContent=leads.length;
  document.getElementById('kpiFresh').textContent=leads.filter(l=>l.stage==='Fresh').length;
  document.getElementById('kpiFollowup').textContent=leads.filter(l=>l.stage==='Follow-up').length;
  document.getElementById('kpiMeeting').textContent=leads.filter(l=>l.stage==='Meeting').length;
  document.getElementById('kpiInterested').textContent=leads.filter(l=>l.stage==='Interested').length;
  document.getElementById('kpiNotReached').textContent=leads.filter(l=>l.stage==='Not Reached').length;
  document.getElementById('kpiNotInterested').textContent=leads.filter(l=>l.stage==='Not Interested').length;

  // Global filter badge counts
  const fc=document.getElementById('gfFollowupsCount');if(fc)fc.textContent=leads.filter(l=>l.stage==='Follow-up').length||'';
  const mc=document.getElementById('gfMeetingsCount');if(mc)mc.textContent=leads.filter(l=>l.stage==='Meeting').length||'';
  const tc=document.getElementById('gfTodayCount');if(tc)tc.textContent=leads.filter(l=>(l.history||[]).some(h=>{const chk=d=>d&&new Date(d).toDateString()===new Date().toDateString();return(h.type==='followup'&&(chk(h.reminderDate)||chk(h.callbackDate)))||(h.type==='meeting'&&chk(h.meetingDate));})).length||'';

  // Search hint
  const anyF=Object.values(activeFilters).some(s=>s.size>0)||activeDateFilter.size>0||activeUpdatedDateFilter.size>0;
  document.getElementById('searchHint').textContent=(searchQuery.trim()||anyF||globalFilter!=='all')?`${list.length} result${list.length!==1?'s':''} found`:`${leads.length} lead${leads.length!==1?'s':''}`;

  renderPagination(list.length);
  const tbody=document.getElementById('tableBody');
  if(!list.length){
    tbody.innerHTML=`<tr class="no-results-row"><td colspan="14"><div class="no-results-icon"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span>No leads found</span></div></td></tr>`;
    return;
  }
  const pageData=list.slice((currentPage-1)*PAGE_SIZE,currentPage*PAGE_SIZE);
  tbody.innerHTML=pageData.map(l=>{
    const stageClass=STAGE_CLASS[l.stage]||'stage-fresh';
    const inactive=l.active===false;
    const sla=fmtSla(getSlaMs(l));
    const statusHtml=inactive?'<span class="status-badge status-inactive"><span class="status-dot"></span>Inactive</span>':'<span class="status-badge status-active"><span class="status-dot"></span>Active</span>';
    const srcLabel=l.broker?'Broker':l.campaign?'Campaign':(l.source||'—');
    const srcIconKey=l.broker?'Broker':l.campaign?'Campaign':(l.source||'Other');
    const sourceHtml=`<span class="source-tag" onclick="openSrcPopover('${l.id}',event)"><svg viewBox="0 0 24 24">${SRC_ICONS[srcIconKey]||SRC_ICONS['Other']}</svg>${escHtml(srcLabel)}</span>`;
    const lcClass=LIFECYCLE_CLASS[l.lifecycle||'New']||'lc-new';
    const lcHtml=`<span class="lifecycle-badge ${lcClass}">${escHtml(l.lifecycle||'New')}</span>`;
    const agentCol=l.agentColor||agentColor(l.assignedTo||'');
    const assignedHtml=l.assignedTo?`<span style="font-size:.82rem;color:var(--clr-text)">${escHtml(l.assignedTo)}</span>`:'<span style="color:var(--clr-gray);font-size:.78rem">Unassigned</span>';
    const createdByHtml=l.createdBy?`<span style="font-size:.82rem;color:var(--clr-text)">${escHtml(l.createdBy)}</span>`:'<span style="color:var(--clr-gray)">—</span>';
    const teamColor=l.team?agentColor(l.team):'#aaa';
    const teamHtml=l.team?`<span class="team-badge" style="background:${teamColor}18;color:${teamColor};border-color:${teamColor}30">${escHtml(l.team)}</span>`:'<span style="color:var(--clr-gray);font-size:.78rem">—</span>';

    return `<tr class="${inactive?'lead-inactive':''}">
      <td style="text-align:left">
        <div style="font-weight:600;font-size:.87rem">${escHtml(l.name)}</div>
      </td>
      <td>
        ${l.phone?`<span class="phone-link" onclick="openPhoneModal('${l.id}',event)"><svg viewBox="0 0 24 24"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.11 10.5 19.79 19.79 0 0 1 2 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L6.09 9.91a16 16 0 0 0 6 6z"/></svg><span style="font-size:.82rem;letter-spacing:.02em">${fmtPhone(l.phone)}</span></span>`:'—'}
      </td>
      <td>${sourceHtml}</td>
      <td><span class="stage-badge ${stageClass}">${escHtml(l.stage||'Fresh')}</span></td>
      <td>${inactive?'<span style="color:var(--clr-gray);font-size:.78rem">—</span>':sla.html}</td>
      <td>${statusHtml}</td>
      <td>${assignedHtml}</td>
      <td>${createdByHtml}</td>
      <td>${teamHtml}</td>
      <td style="font-size:.78rem;color:var(--clr-text-sub)">${fmtDate(l.createdAt)}</td>
      <td style="font-size:.78rem;color:var(--clr-text-sub)">${fmtDate(l.updatedAt||l.createdAt)}</td>
      <td>
        <div class="action-btns">
          ${CFG.readOnly ? '' : `
          <button class="action-btn edit-btn" title="Edit Lead" onclick="openEditModal('${l.id}')"><svg viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>`}
          <button class="action-btn history" title="View History" onclick="openHistoryModal('${l.id}')"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></button>
          ${CFG.readOnly ? '' : `
          <button class="action-btn ${inactive?'activate':'deactivate'}" title="${inactive?'Reactivate':'Deactivate'} Lead" onclick="openDeactivateModal('${l.id}')">
            ${inactive
              ?'<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>'
              :'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>'}
          </button>`}
        </div>
      </td>
    </tr>`;
  }).join('');
}

/* ═══════════════════════════════════════════════════
   SEARCH
═══════════════════════════════════════════════════ */
document.getElementById('searchInput').addEventListener('input',e=>{searchQuery=e.target.value;currentPage=1;renderTable();});

/* ═══════════════════════════════════════════════════
   TOAST
═══════════════════════════════════════════════════ */
function showToast(type,title,msg){
  const icons={success:'<polyline points="20 6 9 17 4 12"/>',error:'<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',info:'<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'};
  const t=document.createElement('div');t.className='toast '+type;
  t.innerHTML=`<div class="toast-icon"><svg viewBox="0 0 24 24">${icons[type]||''}</svg></div><div class="toast-body"><div class="toast-title">${escHtml(title)}</div><div class="toast-msg">${escHtml(msg)}</div></div><button class="toast-dismiss" onclick="this.parentElement.remove()">✕</button>`;
  document.getElementById('toastContainer').appendChild(t);
  setTimeout(()=>{t.classList.add('toast-out');setTimeout(()=>t.remove(),300);},3500);
}

/* ═══════════════════════════════════════════════════
   SLA TIMER TICK
═══════════════════════════════════════════════════ */
setInterval(()=>{
  const rows=document.querySelectorAll('#tableBody tr:not(.no-results-row)');
  const pageData=getDisplayList().slice((currentPage-1)*PAGE_SIZE,currentPage*PAGE_SIZE);
  rows.forEach((row,i)=>{
    const l=pageData[i];if(!l||l.active===false)return;
    const cells=row.querySelectorAll('td');
    if(cells[4])cells[4].innerHTML=fmtSla(getSlaMs(l)).html;
  });
},1000);

/* ═══════════════════════════════════════════════════
   EXPORT
═══════════════════════════════════════════════════ */
document.getElementById('btnExport').addEventListener('click',()=>{
  const list=getDisplayList();
  const headers=['ID','Name','Phone','Source','Campaign','Specific Source','Source Type','Broker','Stage','Status','Lifecycle','Assigned To','Created By','Team','SLA (hrs left)','Created','Last Updated'];
  const rows=list.map(l=>[l.id,l.name,l.phone,l.source,l.campaign||'',l.specificSource||'',l.campaign_child_type||'',l.broker||'',l.stage,l.active===false?'Inactive':'Active',l.lifecycle||'New',l.assignedTo||'',l.createdBy||'',l.team||'',Math.max(0,Math.floor(getSlaMs(l)/3600000)),fmtDate(l.createdAt),fmtDate(l.updatedAt||l.createdAt)]);
  const csv=[headers,...rows].map(r=>r.map(c=>`"${String(c||'').replace(/"/g,'""')}"`).join(',')).join('\n');
  const blob=new Blob([csv],{type:'text/csv'});const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download='all-leads.csv';a.click();URL.revokeObjectURL(url);
  showToast('success','Exported',`${list.length} leads exported.`);
});

/* ═══════════════════════════════════════════════════
   EDIT LEAD MODAL
═══════════════════════════════════════════════════ */
(function(){
  const agentSel = document.getElementById('editLeadAssigned');

  // Real salesmen + teams for the Edit dropdowns (loaded once).
  function fillAssignedOptions(){
    agentSel.innerHTML = '<option value="">— Unassigned —</option>';
    SALESMEN.forEach(s => { const o=document.createElement('option'); o.value=s.id; o.textContent=s.name; agentSel.appendChild(o); });
  }
  Promise.all([
    ajaxGet(CFG.urls.salesmen).then(d=>{ SALESMEN=d.salesmen||[]; }).catch(()=>{}),
    ajaxGet(CFG.urls.teams).then(d=>{ TEAMS_LIST=d.teams||[]; }).catch(()=>{}),
  ]).then(fillAssignedOptions);

  function openEditModal(id){
    const l = leads.find(x=>x.id===id); if(!l) return;
    document.getElementById('editLeadId').value = id;
    document.getElementById('editLeadSub').textContent = l.name;
    document.getElementById('editLeadName').value = l.name||'';
    document.getElementById('editLeadPhone').value = l.phone||'';
    document.getElementById('editLeadStage').value = l.stage||'Fresh';
    if(!agentSel.options.length) fillAssignedOptions();
    document.getElementById('editLeadAssigned').value = l.assignedToId||'';
    document.getElementById('editLeadNotes').value = '';
    document.getElementById('editLeadModal').classList.add('open');
  }
  window.openEditModal = openEditModal;

  function closeEditModal(){ document.getElementById('editLeadModal').classList.remove('open'); }
  document.getElementById('editLeadModalClose').onclick = closeEditModal;
  document.getElementById('editLeadModalCancel').onclick = closeEditModal;
  document.getElementById('editLeadModal').addEventListener('click', e => { if(e.target===e.currentTarget) closeEditModal(); });

  document.getElementById('editLeadModalSave').onclick = function(){
    const id = document.getElementById('editLeadId').value;
    const name = document.getElementById('editLeadName').value.trim();
    if(!name){ showToast('error','Validation','Name is required.'); return; }
    // Persisted server-side via services: contact fields + note directly, stage
    // and assignment routed to their services (audit + history server-side).
    const payload = {
      lead_id: id,
      name: name,
      phone: document.getElementById('editLeadPhone').value.trim(),
      note: document.getElementById('editLeadNotes').value.trim(),
      stage_code: STAGE_CODE[document.getElementById('editLeadStage').value] || '',
      salesman_id: document.getElementById('editLeadAssigned').value || '',
    };
    const btn = document.getElementById('editLeadModalSave'); btn.disabled = true;
    ajaxPost(CFG.urls.edit, payload)
      .then(()=>loadLeadsFromServer())
      .then(()=>{ renderTable(); closeEditModal(); showToast('success','Saved',`${name} updated successfully.`); })
      .catch(err=>Swal.fire({title:'Save failed',text:String(err.message||err),icon:'error',confirmButtonColor:'var(--clr-orange)'}))
      .finally(()=>{ btn.disabled=false; });
  };
})();

/* ═══════════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════════ */
loadLeadsFromServer().then(()=>{ setGlobalFilter('all'); renderTable(); });
setInterval(()=>{ loadLeadsFromServer().then(renderTable); }, 60000);

/* Dynamic lead-creation page (leads spec §4). Reuses the prototype's UX —
   searchable dropdowns, phone validation, review modal — but all data is loaded
   over AJAX and submission posts to leads:api_create. No business logic lives
   here; the server (SourceRouterService) enforces sources, assignment and SLA. */
'use strict';
const CFG = window.LEAD_CFG;
const state = { source: null, language: null, isHead: false, isSalesman: false,
                isBroker: false, canManual: false, headAssignment: 'SELF_OR_MANUAL_TEAM',
                channel: { wk: null, cc: null }, walkinSalesman: null };

/* ───────── helpers ───────── */
function $(id) { return document.getElementById(id); }
function getJSON(url) { return fetch(url, { credentials: 'same-origin' }).then(r => r.json()); }
function postJSON(url, body) {
  return fetch(url, {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CFG.csrf },
    body: JSON.stringify(body),
  });
}

/* ───────── countries (static — phone validation only) ───────── */
const countries = [
  { flag:'🇪🇬', name:'Egypt', code:'+20', len:11 },
  { flag:'🇦🇪', name:'UAE', code:'+971', len:9 },
  { flag:'🇸🇦', name:'Saudi Arabia', code:'+966', len:9 },
  { flag:'🇶🇦', name:'Qatar', code:'+974', len:8 },
  { flag:'🇰🇼', name:'Kuwait', code:'+965', len:8 },
  { flag:'🇧🇭', name:'Bahrain', code:'+973', len:8 },
  { flag:'🇴🇲', name:'Oman', code:'+968', len:8 },
  { flag:'🇯🇴', name:'Jordan', code:'+962', len:9 },
  { flag:'🇱🇧', name:'Lebanon', code:'+961', len:[7,8] },
  { flag:'🇸🇾', name:'Syria', code:'+963', len:9 },
  { flag:'🇬🇧', name:'United Kingdom', code:'+44', len:10 },
  { flag:'🇺🇸', name:'United States', code:'+1', len:10 },
  { flag:'🇫🇷', name:'France', code:'+33', len:9 },
  { flag:'🇩🇪', name:'Germany', code:'+49', len:[10,11] },
  { flag:'🇹🇷', name:'Turkey', code:'+90', len:10 },
  { flag:'🇮🇳', name:'India', code:'+91', len:10 },
];
let selectedCountry = countries[0];

/* ───────── languages (static list — Arabic default) ───────── */
const languages = [
  { code:'ar', name:'Arabic',     native:'عربي' },
  { code:'en', name:'English',    native:'English' },
  { code:'fr', name:'French',     native:'Français' },
  { code:'de', name:'German',     native:'Deutsch' },
  { code:'es', name:'Spanish',    native:'Español' },
  { code:'it', name:'Italian',    native:'Italiano' },
  { code:'ru', name:'Russian',    native:'Русский' },
  { code:'zh', name:'Chinese',    native:'中文' },
  { code:'tr', name:'Turkish',    native:'Türkçe' },
  { code:'other', name:'Other',   native:'Other' },
];

function expectedPhoneLengthLabel(c) { return Array.isArray(c.len) ? c.len.join(' or ') : String(c.len); }
function getPhoneDigits() { return ($('f_phone').value || '').replace(/\D/g, ''); }
function validatePhoneNumber() {
  const d = getPhoneDigits();
  if (!d) return null;
  const lens = Array.isArray(selectedCountry.len) ? selectedCountry.len : [selectedCountry.len];
  if (!lens.includes(d.length))
    return `${selectedCountry.name} numbers should have ${expectedPhoneLengthLabel(selectedCountry)} digits (you entered ${d.length}).`;
  return null;
}
function refreshPhoneHint() {
  const hint = $('phone-hint'), el = $('f_phone'); if (!hint) return;
  const d = getPhoneDigits(), err = validatePhoneNumber();
  if (!d) { hint.textContent = `${selectedCountry.name} numbers are ${expectedPhoneLengthLabel(selectedCountry)} digits, excluding ${selectedCountry.code}.`; hint.classList.remove('error'); el.classList.remove('field-error'); }
  else if (err) { hint.textContent = err; hint.classList.add('error'); el.classList.add('field-error'); }
  else { hint.textContent = '✓ Valid number'; hint.classList.remove('error'); el.classList.remove('field-error'); }
}
function onPhoneInput() { refreshPhoneHint(); updateSummary(); }

/* ───────── generic searchable dropdowns ───────── */
const DD = {};   // name -> {el, list, search, display, items, selected, cfg}

const ddConfig = {
  country: {
    static: () => countries.map(c => ({ id: c.code + c.name, name: `${c.name} ${c.code}`, _c: c })),
    optionHtml: it => `<span class="flag">${it._c.flag}</span><span class="lang-name">${it._c.name}</span><span class="code">${it._c.code}</span>`,
    onSelect: it => { selectedCountry = it._c; $('cc-flag').textContent = it._c.flag; $('cc-code').textContent = it._c.code; refreshPhoneHint(); updateSummary(); },
  },
  language: {
    static: () => languages.map(l => ({ id: l.code, name: l.name, native: l.native })),
    optionHtml: it => `<span class="lang-name">${it.name}</span><span class="lang-native">${it.native}</span>`,
    onSelect: it => { state.language = it.id; $('lang-display').textContent = it.name; $('camp-lang-display').textContent = it.name; reloadLanguageScoped(); updateSummary(); },
  },
  campaign: { load: () => getJSON(CFG.urls.campaigns).then(d => d.campaigns),
              onSelect: () => loadCampaignChannels() },
  camp_platform: { load: () => campChildrenURL('social_media_ad'), onSelect: () => loadCampChild() },
  camp_child: { load: () => Promise.resolve(DD.camp_child.items) },
  camp_assign: { load: salesmenLoader },
  broker: { load: () => getJSON(CFG.urls.brokers).then(d => d.brokers),
            onSelect: () => { if (state.brokerAlsoAssignSalesman) $('broker-salesman-section').style.display = 'flex'; } },
  broker_salesman: { load: salesmenLoader },
  sg_member: { load: () => getJSON(CFG.urls.teamMembers).then(d => d.members) },
  cc_agent: { load: () => getJSON(CFG.urls.ccAgents).then(d => d.agents) },
  cc_salesman: { load: salesmenLoader },
  ref_salesman: { load: salesmenLoader },
  exhib_salesman: { load: salesmenLoader },
  exhib_record: { load: () => recordsURL('exhibition') },
  wk_platform: { onSelect: () => loadRecord('wk') },
  wk_record: {},
  cc_platform: { onSelect: () => loadRecord('cc') },
  cc_record: {},
};

function salesmenLoader() {
  const u = CFG.urls.salesmen + (state.language ? `?language=${encodeURIComponent(state.language)}` : '');
  return getJSON(u).then(d => d.salesmen);
}
function campChildrenURL(channel, platform) {
  const id = DD.campaign.selected && DD.campaign.selected.id;
  if (!id) return Promise.resolve([]);
  let u = `${CFG.urls.campaignChildren}?campaign=${id}&channel=${channel}`;
  if (platform) u += `&platform=${platform}`;
  return getJSON(u).then(d => d.items);
}
function loadTeamsAndSalesmen() {
  return Promise.all([
    getJSON(CFG.urls.teams).then(d => d.teams),
    salesmenLoader(),
  ]).then(([teams, sm]) => [
    ...teams.map(t => ({ id: 'team:' + t.id, name: 'Team — ' + t.name })),
    ...sm.map(s => ({ id: s.id, name: s.name + (s.team ? ' — ' + s.team : '') })),
  ]);
}

function initDropdowns() {
  document.querySelectorAll('.searchable-dropdown[data-dd]').forEach(el => {
    const name = el.dataset.dd;
    const d = {
      el, list: el.querySelector('.sd-list'), search: el.querySelector('.sd-search input'),
      display: el.querySelector('.sd-display'), items: [], selected: null,
      cfg: ddConfig[name] || {}, loaded: false,
    };
    DD[name] = d;
    el.querySelector('.sd-trigger').addEventListener('click', () => toggleDD(name));
    if (d.search) d.search.addEventListener('input', () => renderDD(name, d.search.value));
  });
}
function toggleDD(name) {
  const d = DD[name], open = d.el.classList.contains('open');
  document.querySelectorAll('.searchable-dropdown.open').forEach(x => x.classList.remove('open'));
  if (open) return;
  d.el.classList.add('open');
  if (!d.loaded && d.cfg.load) { d.cfg.load().then(items => { d.items = items || []; d.loaded = true; renderDD(name, ''); }); }
  else { if (d.cfg.static) { d.items = d.cfg.static(); } renderDD(name, ''); }
  if (d.search) setTimeout(() => d.search.focus(), 50);
}
function renderDD(name, q) {
  const d = DD[name];
  const items = (d.items || []).filter(it => it.name.toLowerCase().includes((q || '').toLowerCase()));
  if (!items.length) { d.list.innerHTML = '<div class="sd-empty">No results</div>'; return; }
  d.list.innerHTML = items.map(it => {
    const inner = d.cfg.optionHtml ? d.cfg.optionHtml(it) : `<span class="lang-name">${it.name}</span>`;
    const sel = d.selected && d.selected.id === it.id ? ' selected' : '';
    return `<div class="sd-option${sel}" data-id="${it.id}">${inner}</div>`;
  }).join('');
  d.list.querySelectorAll('.sd-option').forEach(o => o.addEventListener('click', () => selectDD(name, o.dataset.id)));
}
function selectDD(name, id) {
  const d = DD[name];
  const it = (d.items || []).find(x => String(x.id) === String(id));
  if (!it) return;
  d.selected = it;
  if (d.display) { d.display.textContent = it.name; d.display.style.color = 'var(--clr-text)'; }
  d.el.classList.remove('open');
  if (d.search) d.search.value = '';
  if (d.cfg.onSelect) d.cfg.onSelect(it);
}
function resetDD(name) {
  const d = DD[name]; if (!d) return;
  d.selected = null; d.items = []; d.loaded = false;
  if (d.display) { d.display.textContent = '— Select —'; d.display.style.color = 'var(--clr-text-sub)'; }
}
function ddVal(name) { return DD[name] && DD[name].selected ? DD[name].selected.id : null; }

document.addEventListener('click', e => {
  if (!e.target.closest('.searchable-dropdown'))
    document.querySelectorAll('.searchable-dropdown.open').forEach(x => x.classList.remove('open'));
});

function reloadLanguageScoped() {
  ['broker_salesman', 'cc_salesman', 'ref_salesman', 'exhib_salesman', 'sg_member', 'camp_assign']
    .forEach(n => { if (DD[n]) { DD[n].loaded = false; DD[n].selected = null; const dsp = DD[n].display; if (dsp) { dsp.textContent = '— Select —'; dsp.style.color = 'var(--clr-text-sub)'; } } });
}

/* ───────── campaign channel cascade ───────── */
function onCampChannel(val) {
  $('camp-platform-group').style.display = val === 'social_media_ad' ? '' : 'none';
  const childGroup = $('camp-child-group');
  resetDD('camp_child'); resetDD('camp_platform');
  if (!val) { childGroup.style.display = 'none'; return; }
  if (val === 'social_media_ad') { childGroup.style.display = 'none'; return; }
  childGroup.style.display = '';
  $('camp-child-label').firstChild.textContent =
    ({ event: 'Event ', tv_ad: 'TV Ad ', street_ad: 'Street Ad ', exhibition: 'Exhibition ' }[val]) || 'Detail ';
  campChildrenURL(val).then(items => { DD.camp_child.items = items; DD.camp_child.loaded = true; });
}
function loadCampChild() {
  $('camp-child-group').style.display = '';
  $('camp-child-label').firstChild.textContent = 'Ad Name ';
  resetDD('camp_child');
  campChildrenURL('social_media_ad', ddVal('camp_platform')).then(items => {
    DD.camp_child.items = items; DD.camp_child.loaded = true;
  });
}
function loadCampaignChannels() {
  resetDD('camp_child'); resetDD('camp_platform');
  $('camp-child-group').style.display = 'none';
  $('camp-platform-group').style.display = 'none';
  const sel = $('camp-channel'); sel.innerHTML = '<option value="">— Select Channel —</option>';
  const cid = ddVal('campaign'); if (!cid) return;
  getJSON(`${CFG.urls.campaignChannels}?campaign=${cid}`).then(d => {
    (d.channels || []).forEach(c => {
      const o = document.createElement('option'); o.value = c.value; o.textContent = c.label;
      sel.appendChild(o);
    });
  });
}

/* ───────── generic channel→record cascade (walk-in / call-center) ───────── */
function recordsURL(channel, platform) {
  let u = `${CFG.urls.records}?type=${channel}`;
  if (platform) u += `&platform=${platform}`;
  return getJSON(u).then(d => d.items);
}
const RECORD_CHANNELS = ['event', 'tv_ad', 'street_ad', 'exhibition'];
function onChannelPick(prefix, val) {
  state.channel[prefix] = val;
  resetDD(prefix + '_record'); resetDD(prefix + '_platform');
  const pg = $(prefix + '-platform-group'), rg = $(prefix + '-record-group');
  if (pg) pg.style.display = 'none';
  if (rg) rg.style.display = 'none';
  if (val === 'social_media_ad') {
    if (pg) { pg.style.display = ''; recordsURL('social_media_ad').then(items => { DD[prefix + '_platform'].items = items; DD[prefix + '_platform'].loaded = true; }); }
  } else if (RECORD_CHANNELS.includes(val)) {
    loadRecord(prefix);
  }
}
function loadRecord(prefix) {
  const ch = state.channel[prefix];
  const rg = $(prefix + '-record-group'); if (rg) rg.style.display = '';
  const lbl = $(prefix + '-record-label');
  if (lbl) lbl.firstChild.textContent = ({ event: 'Event ', tv_ad: 'TV Ad ', street_ad: 'Street Ad ', exhibition: 'Exhibition ', social_media_ad: 'Ad Name ' }[ch]) || 'Detail ';
  resetDD(prefix + '_record');
  recordsURL(ch, ddVal(prefix + '_platform')).then(items => {
    DD[prefix + '_record'].items = items; DD[prefix + '_record'].loaded = true;
  });
}

/* ───────── self-generated head assignment (policy-driven) ───────── */
function renderHeadAssign() {
  const auto = state.headAssignment === 'AUTO_ROUND_ROBIN_TEAM';
  $('sg-assign-group').style.display = auto ? 'none' : '';
  $('sg-auto-info').style.display = auto ? '' : 'none';
  $('sg-member-select').style.display = 'none';
  if (!auto) document.querySelectorAll('input[name="sg_assign"]').forEach(r => { r.checked = r.value === 'self'; });
}

/* ───────── walk-in rotation (interactive; pointer moves server-side) ───────── */
function loadWalkin() { getJSON(CFG.urls.walkinState).then(renderWalkin); }
function walkinAdvance() { postJSON(CFG.urls.walkinAdvance, {}).then(r => r.json()).then(renderWalkin); }
function optSelect(id, label, list) {
  const opts = ['<option value="">— Select —</option>'].concat(
    (list || []).map(p => `<option value="${p.id}">${p.name}${p.team ? ' — ' + p.team : ''}</option>`)).join('');
  return `<div class="form-group" style="margin-top:8px"><label>${label} <span class="req">*</span></label><select id="${id}" onchange="pickWalkin(this.value)">${opts}</select></div>`;
}
function pickWalkin(v) { state.walkinSalesman = v || null; }
function renderWalkin(s) {
  state.walkinSalesman = null;
  const box = $('wk-rotation'), pol = s.policy;
  $('wk-policy-text').textContent = {
    OPEN_FLOOR: 'Open Floor — any available salesman may meet the visitor.',
    TEAM_TURN: "Team Turn — the team whose turn it is sends a salesman (its head assigns). If none are available, pass to the next team.",
    FULL_ROTATION: 'Full Rotation — the next salesman in the company-wide rotation meets the visitor.',
  }[pol] || 'Reception policy.';
  if (pol === 'OPEN_FLOOR') {
    box.innerHTML = optSelect('wk-pick', 'Available Salesman', s.salesmen);
  } else if (pol === 'FULL_ROTATION') {
    const cur = (s.order || [])[s.current_index];
    state.walkinSalesman = cur ? cur.id : null;
    box.innerHTML = cur
      ? `<div class="info-banner orange"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg><span>Next in rotation: <strong>${cur.name}</strong> — ${cur.team}. Confirm to assign, or skip if unavailable.</span></div>
         <div style="margin-top:8px"><button type="button" class="btn btn-outline" onclick="walkinAdvance()">Unavailable — Skip to Next</button></div>`
      : '<div class="info-banner red"><span>No available salesmen — lead will escalate to manual.</span></div>';
  } else if (pol === 'TEAM_TURN') {
    const cur = s.current_team;
    let html = cur ? `<div class="info-banner orange"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg><span>It is the turn of <strong>${cur.name}</strong>.</span></div>`
                   : '<div class="info-banner red"><span>No teams configured.</span></div>';
    html += optSelect('wk-pick', 'Assign Team Member', s.members || []);
    html += `<div style="margin-top:8px"><button type="button" class="btn btn-outline" onclick="walkinAdvance()">No one available — Pass to Next Team</button></div>`;
    box.innerHTML = html;
  }
}

function toggleCampDist(v) { $('camp-assign-group').style.display = v === 'manual' ? '' : 'none'; }
function toggleCCDist(v) { $('cc-assign-group').style.display = v === 'manual' ? '' : 'none'; }
function toggleRefDist(v) { $('ref-assign-group').style.display = v === 'manual' ? '' : 'none'; }
function toggleSGAssign(v) { $('sg-member-select').style.display = v === 'member' ? '' : 'none'; }
function toggleBrokerPolicy(v) { $('broker-salesman-group').style.display = v === 'salesman' ? '' : 'none'; }

/* ───────── source selection ───────── */
const SOURCE_LABELS = {};
function renderSources(sources) {
  const grid = $('source-grid');
  if (!sources.length) { grid.innerHTML = '<div class="sd-empty">You have no permission to create leads.</div>'; return; }
  grid.innerHTML = sources.map(s => {
    SOURCE_LABELS[s.code] = s.label;
    return `<button type="button" class="source-btn" id="src-${s.code}" data-src="${s.code}"><span>${s.label}</span></button>`;
  }).join('');
  grid.querySelectorAll('.source-btn').forEach(b => b.addEventListener('click', () => selectSource(b.dataset.src)));
  // Hide manual-distribution options for users who cannot assign manually.
  if (!state.canManual) ['camp-manual-opt', 'cc-manual-opt', 'ref-manual-opt'].forEach(id => { const e = $(id); if (e) e.style.display = 'none'; });
}
function selectSource(code) {
  state.source = code;
  document.querySelectorAll('.source-btn').forEach(b => b.classList.toggle('selected', b.dataset.src === code));
  document.querySelectorAll('.source-partial').forEach(p => p.classList.remove('active'));
  const partial = $('partial-' + code); if (partial) partial.classList.add('active');
  $('sum-source').textContent = SOURCE_LABELS[code] || code;
  if (code === 'self_generated') {
    $('sg-head-view').style.display = state.isHead ? 'flex' : 'none';
    $('sg-salesman-view').style.display = state.isSalesman ? '' : 'none';
    if (state.isHead) renderHeadAssign();
  }
  if (code === 'broker') {
    $('broker-self-panel').style.display = state.isBroker ? 'flex' : 'none';
    $('broker-staff-panel').style.display = state.isBroker ? 'none' : 'flex';
    if (state.isBroker && state.brokerAlsoAssignSalesman) $('broker-salesman-section').style.display = 'flex';
  }
  if (code === 'call_center') $('cc-agent-group').style.display = '';
  if (code === 'walk_in') loadWalkin();
}

/* ───────── summary ───────── */
function updateSummary() {
  $('sum-name').textContent = $('f_name').value || '—';
  const ph = $('f_phone').value;
  $('sum-phone').textContent = ph ? `${selectedCountry.code} ${ph}` : '—';
  $('sum-lang').textContent = DD.language && DD.language.selected ? DD.language.selected.name : '—';
}

/* ───────── duplicate + existing client ───────── */
function checkDuplicate() {
  const phone = $('f_phone').value.trim();
  if (!phone) { Swal.fire({ icon: 'info', title: 'Enter a phone number first', confirmButtonColor: '#e07b20' }); return; }
  getJSON(`${CFG.urls.duplicate}?phone=${encodeURIComponent(phone)}`).then(d => {
    const body = $('dup-modal-body');
    if (!d.is_duplicate) { body.innerHTML = '<div class="info-banner blue">No existing lead with this phone number.</div>'; }
    else {
      const e = d.existing || {};
      body.innerHTML = `<div class="info-banner orange" style="margin-bottom:14px">An existing lead was found with this phone number${d.requires_manual ? ' (active, within SLA — creating again escalates to manual distribution).' : '.'}</div>
        <div class="matched-card"><div class="matched-card-name">${e.name || ''}</div>
        <div class="matched-card-meta"><span>${e.phone || ''}</span><span>Source: ${e.source || '—'}</span><span>Stage: ${e.stage || '—'}</span><span>Salesman: ${e.salesman || '—'}</span></div></div>`;
    }
    $('dup-modal-bg').style.display = '';
  });
}
function closeDupModal() { $('dup-modal-bg').style.display = 'none'; }

function lookupExistingClient() {
  const phone = $('existing-search').value.trim();
  if (!phone) return;
  getJSON(`${CFG.urls.existing}?phone=${encodeURIComponent(phone)}`).then(d => {
    const box = $('existing-result');
    if (!d.found) { box.style.display = 'block'; box.innerHTML = '<div class="info-banner red">No existing client found with this phone.</div>'; return; }
    const c = d.client;
    // Pre-fill name/phone for submission.
    if (!$('f_name').value) $('f_name').value = c.name;
    if (!$('f_phone').value) $('f_phone').value = c.phone;
    updateSummary();
    box.style.display = 'block';
    box.innerHTML = `<div class="matched-card"><div class="matched-card-name">${c.name}</div>
      <div class="matched-card-meta"><span>${c.phone}</span><span>Last salesman: <strong>${c.original_salesman || '—'}</strong> ${c.original_salesman_active ? '(active)' : '(inactive)'}</span>
      <span class="badge fresh"><span class="dot"></span>${c.status}</span></div></div>`;
  });
}

/* ───────── review ───────── */
function openReview() {
  const missing = validateForm();
  if (missing.length) { Swal.fire({ title: 'Missing Required Fields', icon: 'warning', confirmButtonColor: '#e07b20',
    html: '<ul style="text-align:left;display:inline-block;padding-left:18px">' + missing.map(m => `<li>${m}</li>`).join('') + '</ul>' }); return; }
  const name = $('f_name').value || '—';
  const phone = $('f_phone').value ? `${selectedCountry.code} ${$('f_phone').value}` : '—';
  $('review-client-grid').innerHTML = `
    <div class="review-item"><label>Full Name</label><span>${name}</span></div>
    <div class="review-item"><label>Phone</label><span>${phone}</span></div>
    <div class="review-item"><label>Email</label><span>${$('f_email').value || '—'}</span></div>
    <div class="review-item"><label>Language</label><span>${DD.language.selected ? DD.language.selected.name : '—'}</span></div>`;
  $('review-source-detail').innerHTML = `<strong>${SOURCE_LABELS[state.source] || '—'}</strong>`;
  $('review-overlay').classList.add('active'); document.body.style.overflow = 'hidden';
}
function closeReview() { $('review-overlay').classList.remove('active'); document.body.style.overflow = ''; }

/* ───────── validation + submit ───────── */
function needRecord(prefix, m) {
  const ch = state.channel[prefix]; if (!ch) return;
  if (ch === 'social_media_ad') {
    if (!ddVal(prefix + '_platform')) m.push('Social Platform');
    if (!ddVal(prefix + '_record')) m.push('Ad Name');
  } else if (RECORD_CHANNELS.includes(ch) && !ddVal(prefix + '_record')) {
    m.push('Channel Detail');
  }
}
function validateForm() {
  const m = [];
  if (!$('f_name').value.trim()) m.push('Full Name');
  if (!$('f_phone').value.trim()) m.push('Phone Number');
  else if (validatePhoneNumber()) m.push(validatePhoneNumber());
  if (!state.language) m.push('Lead Language');
  if (!state.source) { m.push('Lead Source'); return m; }
  const s = state.source;
  if (s === 'self_generated' && state.isHead && state.headAssignment !== 'AUTO_ROUND_ROBIN_TEAM') {
    const a = document.querySelector('input[name="sg_assign"]:checked').value;
    if (a === 'member' && !ddVal('sg_member')) m.push('Team Member');
  }
  if (s === 'campaign') {
    if (!ddVal('campaign')) m.push('Campaign');
    const ch = $('camp-channel').value;
    if (!ch) m.push('Campaign Channel');
    else if (ch === 'social_media_ad') { if (!ddVal('camp_platform')) m.push('Social Platform'); if (!ddVal('camp_child')) m.push('Ad Name'); }
    else if (!ddVal('camp_child')) m.push('Channel Detail');
    if (document.querySelector('input[name="camp_dist"]:checked').value === 'manual' && !ddVal('camp_assign')) m.push('Assign To');
  }
  if (s === 'broker') {
    if (!state.isBroker && !ddVal('broker')) m.push('Broker');
    if (document.querySelector('input[name="broker_policy"]:checked').value === 'salesman' && !ddVal('broker_salesman')) m.push('Salesman');
  }
  if (s === 'walk_in') {
    if (!state.channel.wk) m.push('How Did You Know Us'); else needRecord('wk', m);
    if (!state.walkinSalesman) m.push('Salesman to meet the visitor');
  }
  if (s === 'call_center') {
    if (!state.channel.cc) m.push('How Caller Heard'); else needRecord('cc', m);
    if (document.querySelector('input[name="cc_dist"]:checked').value === 'manual' && !ddVal('cc_salesman')) m.push('Assign To');
  }
  if (s === 'exhibition') {
    if (!ddVal('exhib_record')) m.push('Exhibition');
    if (!ddVal('exhib_salesman')) m.push('Assigned Salesman');
  }
  if (s === 'referral') { if (!$('ref-name').value.trim()) m.push('Referrer Name');
    if (document.querySelector('input[name="ref_dist"]:checked').value === 'manual' && !ddVal('ref_salesman')) m.push('Assign To'); }
  return m;
}

function buildPayload() {
  const p = {
    source_code: state.source,
    name: $('f_name').value.trim(), phone: $('f_phone').value.trim(),
    email: $('f_email').value.trim(), country_code: selectedCountry.code,
    language_code: state.language, notes: $('f_notes').value.trim(),
  };
  const s = state.source;
  if (s === 'self_generated' && state.isHead) {
    p.sg_assign = document.querySelector('input[name="sg_assign"]:checked').value;
    p.sg_member_id = ddVal('sg_member');
  }
  if (s === 'campaign') {
    p.campaign_id = ddVal('campaign');
    p.channel = $('camp-channel').value;
    if (p.channel === 'social_media_ad') { p.social_platform_id = ddVal('camp_platform'); p.social_ad_id = ddVal('camp_child'); }
    else p.child_id = ddVal('camp_child');
    p.dist = document.querySelector('input[name="camp_dist"]:checked').value;
    if (p.dist === 'manual') p.assign_id = ddVal('camp_assign');
  }
  if (s === 'broker') {
    if (!state.isBroker) p.broker_id = ddVal('broker');
    p.broker_policy = document.querySelector('input[name="broker_policy"]:checked').value;
    if (p.broker_policy === 'salesman') p.salesman_id = ddVal('broker_salesman');
  }
  if (s === 'walk_in') {
    p.channel = state.channel.wk || '';
    p.record_id = ddVal('wk_record');
    p.social_platform_id = ddVal('wk_platform');
    p.salesman_id = state.walkinSalesman;
  }
  if (s === 'call_center') {
    p.channel = state.channel.cc || '';
    p.record_id = ddVal('cc_record');
    p.social_platform_id = ddVal('cc_platform');
    p.cc_agent_id = ddVal('cc_agent');
    p.dist = document.querySelector('input[name="cc_dist"]:checked').value;
    if (p.dist === 'manual') p.salesman_id = ddVal('cc_salesman');
  }
  if (s === 'exhibition') {
    p.record_id = ddVal('exhib_record');
    p.salesman_id = ddVal('exhib_salesman');
  }
  if (s === 'referral') {
    p.referrer_name = $('ref-name').value.trim();
    p.dist = document.querySelector('input[name="ref_dist"]:checked').value;
    if (p.dist === 'manual') p.salesman_id = ddVal('ref_salesman');
  }
  return p;
}

function submitLead() {
  const missing = validateForm();
  if (missing.length) { openReview(); return; }
  postJSON(CFG.urls.create, buildPayload()).then(async r => {
    const d = await r.json();
    if (r.ok && d.ok) {
      Swal.fire({ title: 'Lead Created!', icon: 'success', confirmButtonText: 'View Lead', confirmButtonColor: '#e07b20',
        showCancelButton: true, cancelButtonText: 'Add Another' })
        .then(res => { if (res.isConfirmed) window.location.href = d.redirect; else window.location.reload(); });
    } else {
      Swal.fire({ title: 'Could not create lead', text: d.error || 'Unexpected error', icon: 'error', confirmButtonColor: '#e07b20' });
    }
  }).catch(() => Swal.fire({ title: 'Network error', icon: 'error', confirmButtonColor: '#e07b20' }));
}

/* ───────── init ───────── */
function preselectLanguage() {
  // Default to Arabic so the user doesn't pick it every time (company default).
  const d = DD.language;
  d.items = d.cfg.static(); d.loaded = true;
  selectDD('language', 'ar');
}

function init() {
  initDropdowns();
  refreshPhoneHint();
  preselectLanguage();
  getJSON(CFG.urls.sources).then(d => {
    state.isHead = d.is_head; state.isSalesman = d.is_salesman;
    state.isBroker = d.is_broker; state.canManual = d.can_manual;
    state.headAssignment = d.head_assignment || 'SELF_OR_MANUAL_TEAM';
    state.brokerAlsoAssignSalesman = d.broker_also_assign_salesman;
    renderSources(d.sources);
    if (d.sources.length) selectSource(d.sources[0].code);
  });
}
document.addEventListener('DOMContentLoaded', init);

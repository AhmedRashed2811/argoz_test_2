// State tracking
const roleDefaultCodes = new Set();
const permItemMap = {};

function initRoles() {
  const sel = document.getElementById('inp-default_role');
  if (!sel) return;
  
  // Clear any existing options except first
  sel.innerHTML = '<option value="">— Select a role —</option>';
  
  (window.ROLES || []).forEach(r => {
    const o = document.createElement('option');
    o.value = r.id;
    o.textContent = `${r.name} (${r.code})`;
    sel.appendChild(o);
  });
  sel.addEventListener('change', onRoleChange);
}

function buildPermissions() {
  const container = document.getElementById('permissionsContainer');
  if (!container) return;
  container.innerHTML = '';

  const grouped = {};
  (window.PERMISSIONS || []).forEach(p => {
    if (!grouped[p.module]) grouped[p.module] = [];
    grouped[p.module].push(p);
  });

  Object.keys(grouped).forEach(mod => {
    const group = document.createElement('div');
    group.className = 'module-group';
    group.setAttribute('data-module', mod);

    const header = document.createElement('div');
    header.className = 'module-header';
    header.innerHTML = `
      <h3>${mod}</h3>
      <div class="module-actions">
        <button type="button" class="btn-mod" onclick="setModule('${mod}',true)">All</button>
        <button type="button" class="btn-mod" onclick="setModule('${mod}',false)">None</button>
      </div>`;
    group.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'perms-grid';
    grid.id = 'pgrid-' + mod;

    grouped[mod].forEach(perm => {
      const item = document.createElement('div');
      item.className = 'perm-item';
      item.setAttribute('data-code', perm.code);
      item.setAttribute('data-name', perm.name.toLowerCase());
      item.setAttribute('data-desc', (perm.desc || '').toLowerCase());
      item.innerHTML = `
        <span class="vcb"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></span>
        <div class="perm-info">
          <div class="perm-name">${perm.name}</div>
          <div class="perm-code">${perm.code}</div>
          <div class="perm-badges">
            <span class="badge-inh">Inherited</span>
            <span class="badge-ovr">Override</span>
          </div>
        </div>`;

      item.addEventListener('click', () => togglePerm(item));

      permItemMap[perm.code] = item;
      grid.appendChild(item);
    });

    group.appendChild(grid);
    container.appendChild(group);
  });
}

function togglePerm(item) {
  const code = item.getAttribute('data-code');
  const isChecked = item.classList.contains('checked');
  setPerm(item, code, !isChecked);
}

function setPerm(item, code, checked) {
  const isDefault = roleDefaultCodes.has(code);

  if (checked) item.classList.add('checked');
  else item.classList.remove('checked');

  item.classList.remove('is-inherited', 'is-override');
  if (checked && isDefault) item.classList.add('is-inherited');
  if (checked !== isDefault) item.classList.add('is-override');
}

function onRoleChange() {
  const roleSelect = document.getElementById('inp-default_role');
  if (!roleSelect) return;
  const roleId = roleSelect.value;
  roleDefaultCodes.clear();

  if (!roleId) {
    Object.keys(permItemMap).forEach(code => {
      setPerm(permItemMap[code], code, false);
    });
    return;
  }

  const defaults = (window.ROLE_PERMS || {})[roleId] || [];
  defaults.forEach(c => roleDefaultCodes.add(c));

  (window.PERMISSIONS || []).forEach(p => {
    const item = permItemMap[p.code];
    if (item) setPerm(item, p.code, roleDefaultCodes.has(p.code));
  });
}

function setModule(mod, checkAll) {
  const grid = document.getElementById('pgrid-' + mod);
  if (!grid) return;
  grid.querySelectorAll('.perm-item').forEach(item => {
    const code = item.getAttribute('data-code');
    setPerm(item, code, checkAll);
  });
}

function filterPermissions() {
  const q = document.getElementById('permSearch').value.toLowerCase().trim();
  document.querySelectorAll('.perm-item').forEach(item => {
    const match = !q
      || item.getAttribute('data-name').includes(q)
      || item.getAttribute('data-code').includes(q)
      || item.getAttribute('data-desc').includes(q);
    item.style.display = match ? '' : 'none';
  });
  document.querySelectorAll('.module-group').forEach(g => {
    const vis = g.querySelectorAll('.perm-item:not([style*="display: none"])');
    g.style.display = vis.length ? '' : 'none';
  });
}

function initPage() {
  if (window.IS_EDIT) {
    const user = window.USER_DATA || {};
    
    document.getElementById('pageTitle').textContent = `Edit User — ${user.first_name || ''} ${user.last_name || ''}`;
    document.getElementById('pageSubtitle').textContent = 'Update profile details. Permissions are managed via the Permission Matrix.';
    document.getElementById('field-password').style.display = 'none';
    document.getElementById('submitLabel').textContent = 'Save Changes';
    document.title = 'Edit User · Argoz CRM';

    document.getElementById('formLayout').classList.add('edit-mode');
    document.getElementById('rightCol').style.display = 'none';

    // Pre-fill fields
    document.getElementById('inp-first_name').value = user.first_name || '';
    document.getElementById('inp-last_name').value = user.last_name || '';
    document.getElementById('inp-email').value = user.email || '';
    document.getElementById('inp-job_title').value = user.job_title || '';

    let phone = user.phone || '';
    if (phone.startsWith('+20')) phone = phone.slice(3).trim();
    document.getElementById('inp-phone').value = phone;

    if (user.default_role) {
      setTimeout(() => {
        document.getElementById('inp-default_role').value = user.default_role;
      }, 50);
    }
  } else {
    document.title = 'Create User · Argoz CRM';
  }
}

function validate() {
  let ok = true;
  const checks = [
    { id: 'first_name', fn: v => v.trim().length > 0, msg: 'Required' },
    { id: 'last_name', fn: v => v.trim().length > 0, msg: 'Required' },
    { id: 'email', fn: v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v), msg: 'Valid email required' },
  ];
  if (!window.IS_EDIT) checks.push({ id: 'password', fn: v => v.length >= 8, msg: 'Minimum 8 characters' });

  checks.forEach(c => {
    const inp = document.getElementById(`inp-${c.id}`);
    const field = document.getElementById(`field-${c.id}`);
    const err = document.getElementById(`err-${c.id}`);
    if (!inp || !field) return;
    const pass = c.fn(inp.value);
    field.classList.toggle('has-error', !pass);
    if (!pass) { if (err) err.textContent = c.msg; ok = false; }
  });

  const role = document.getElementById('inp-default_role').value;
  const roleField = document.getElementById('field-default_role');
  if (roleField) {
    roleField.classList.toggle('has-error', !role);
  }
  if (!role) ok = false;

  return ok;
}

// Wire form submission
const submitBtn = document.getElementById('submitBtn');
if (submitBtn) {
  submitBtn.addEventListener('click', async () => {
    if (!validate()) return;
    submitBtn.classList.add('loading');

    let phoneRaw = document.getElementById('inp-phone').value.trim();
    const fullPhone = phoneRaw ? `+20 ${phoneRaw.replace(/^0/, '')}` : '';

    const checkedCodes = Object.keys(permItemMap).filter(code => permItemMap[code].classList.contains('checked'));

    const payload = {
      first_name: document.getElementById('inp-first_name').value.trim(),
      last_name: document.getElementById('inp-last_name').value.trim(),
      email: document.getElementById('inp-email').value.trim(),
      phone: fullPhone,
      job_title: document.getElementById('inp-job_title').value.trim(),
      default_role: document.getElementById('inp-default_role').value,
      permissions: window.IS_EDIT ? [] : checkedCodes,
    };
    if (!window.IS_EDIT) payload.password = document.getElementById('inp-password').value;

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    let apiUrl = window.IS_EDIT ? window.API_EDIT_URL : window.API_CREATE_URL;

    const errBanner = document.getElementById('errorBanner');
    const errList = document.getElementById('errorList');
    if (errBanner) errBanner.style.display = 'none';
    if (errList) errList.innerHTML = '';

    try {
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || ''
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      submitBtn.classList.remove('loading');

      if (res.ok && data.ok) {
        showToast('success',
          window.IS_EDIT ? 'User Updated' : 'User Created',
          `${payload.first_name} ${payload.last_name} was ${window.IS_EDIT ? 'updated' : 'added'} successfully.`
        );
        setTimeout(() => {
          window.location.href = window.DIRECTORY_URL;
        }, 1500);
      } else {
        // Show validation errors returned from backend
        if (errBanner && errList) {
          errBanner.style.display = 'block';
          if (data.errors) {
            Object.keys(data.errors).forEach(field => {
              const messages = data.errors[field];
              messages.forEach(msg => {
                const li = document.createElement('li');
                li.textContent = `${field}: ${msg}`;
                errList.appendChild(li);
              });
              
              // highlight target field
              const targetField = document.getElementById(`field-${field}`);
              if (targetField) {
                targetField.classList.add('has-error');
                const targetErr = document.getElementById(`err-${field}`);
                if (targetErr) targetErr.textContent = messages.join(' ');
              }
            });
          } else {
            const li = document.createElement('li');
            li.textContent = data.error || 'Server error occurred.';
            errList.appendChild(li);
          }
        }
        showToast('error', 'Action Failed', data.error || 'Please correct the validation errors below.');
      }
    } catch (err) {
      console.error('Submit API failed', err);
      submitBtn.classList.remove('loading');
      showToast('error', 'Error', 'Failed to communicate with server. Check connection.');
    }
  });
}

const togglePwBtn = document.getElementById('togglePw');
if (togglePwBtn) {
  const EYE_OPEN = '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/>';
  const EYE_CLOSED = '<path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a18.5 18.5 0 0 1 4.06-5.06M9.9 4.24A9.9 9.9 0 0 1 12 4c7 0 11 7 11 7a18.5 18.5 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
  togglePwBtn.addEventListener('click', () => {
    const inp = document.getElementById('inp-password');
    const ico = document.getElementById('eyeIcon');
    if (!inp || !ico) return;
    const pw = inp.type === 'password';
    inp.type = pw ? 'text' : 'password';
    ico.innerHTML = pw ? EYE_CLOSED : EYE_OPEN;
  });
}

function showToast(type, title, msg) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = {
    success: `<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`,
    error: `<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
    info: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  };
  el.innerHTML = `<div class="toast-icon">${icons[type] || icons.info}</div><div><div class="toast-title">${title}</div><div class="toast-msg">${msg}</div></div>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

document.addEventListener("DOMContentLoaded", () => {
  initRoles();
  buildPermissions();
  initPage();
});

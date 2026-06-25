// JavaScript for Role create/edit form
const selectedPermissions = new Set(window.SELECTED_PERMISSION_IDS || []);

function initPermissions() {
  const items = document.querySelectorAll('.perm-item');
  items.forEach(item => {
    // Only bind click handler if not disabled
    if (item.classList.contains('disabled')) return;
    
    item.addEventListener('click', () => {
      const id = item.getAttribute('data-id');
      const isChecked = item.classList.contains('checked');
      if (isChecked) {
        item.classList.remove('checked');
        selectedPermissions.delete(id);
        selectedPermissions.delete(String(id));
      } else {
        item.classList.add('checked');
        selectedPermissions.add(id);
      }
    });
  });
}

function setModule(moduleName, check) {
  const group = document.querySelector(`.module-group[data-module="${moduleName}"]`);
  if (!group) return;

  group.querySelectorAll('.perm-item').forEach(item => {
    if (item.classList.contains('disabled')) return;
    const id = item.getAttribute('data-id');
    if (check) {
      item.classList.add('checked');
      selectedPermissions.add(id);
    } else {
      item.classList.remove('checked');
      selectedPermissions.delete(id);
      selectedPermissions.delete(String(id));
    }
  });
}

function filterPermissions() {
  const q = document.getElementById('permSearch').value.toLowerCase().trim();
  
  document.querySelectorAll('.module-group').forEach(group => {
    let groupVisible = 0;
    group.querySelectorAll('.perm-item').forEach(item => {
      const name = item.getAttribute('data-name') || '';
      const code = item.getAttribute('data-code') || '';
      const desc = item.getAttribute('data-desc') || '';
      const match = !q || name.includes(q) || code.includes(q) || desc.includes(q);
      
      item.style.display = match ? 'flex' : 'none';
      if (match) groupVisible++;
    });

    group.style.display = groupVisible > 0 ? '' : 'none';
  });
}

function initPage() {
  const submitBtn = document.getElementById('submitBtn');
  if (!submitBtn) return;

  submitBtn.addEventListener('click', async () => {
    if (submitBtn.classList.contains('loading')) return;

    const name = document.getElementById('inp-name').value.trim();
    const codeInput = document.getElementById('inp-code');
    const code = codeInput ? codeInput.value.trim() : '';
    const description = document.getElementById('inp-description').value.trim();
    const isActiveInput = document.getElementById('inp-is_active');
    const is_active = isActiveInput ? isActiveInput.checked : true;

    const errBanner = document.getElementById('errorBanner');
    const errList = document.getElementById('errorList');
    if (errBanner) errBanner.style.display = 'none';
    if (errList) errList.innerHTML = '';

    // Field highlights
    document.querySelectorAll('.field').forEach(f => f.classList.remove('has-error'));

    if (!name) {
      showToast('error', 'Validation Error', 'Role Name is required.');
      const f = document.getElementById('field-name');
      if (f) f.classList.add('has-error');
      return;
    }
    if (!window.IS_EDIT && !code) {
      showToast('error', 'Validation Error', 'Role Code is required.');
      const f = document.getElementById('field-code');
      if (f) f.classList.add('has-error');
      return;
    }

    submitBtn.classList.add('loading');

    const payload = {
      name: name,
      code: code,
      description: description,
      is_active: is_active,
      permissions: Array.from(selectedPermissions)
    };

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    const apiUrl = window.IS_EDIT ? window.API_EDIT_URL : window.API_CREATE_URL;

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
          window.IS_EDIT ? 'Role Updated' : 'Role Created',
          `Role "${payload.name}" was ${window.IS_EDIT ? 'updated' : 'created'} successfully.`
        );
        setTimeout(() => {
          window.location.href = window.DIRECTORY_URL;
        }, 1500);
      } else {
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
      showToast('error', 'Error', 'Failed to communicate with server.');
    }
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
  };
  el.innerHTML = `<div class="toast-icon">${icons[type]}</div><div><div class="toast-title">${title}</div><div class="toast-msg">${msg}</div></div>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

document.addEventListener("DOMContentLoaded", () => {
  initPermissions();
  initPage();
});

// JavaScript for Sales Team create/edit page
const selectedHeads = new Set(window.CURRENT_HEAD_IDS || []);
const selectedMembers = new Set(window.CURRENT_MEMBER_IDS || []);

function buildUserGrids() {
  renderGrid('heads-grid', window.AVAILABLE_HEADS || [], selectedHeads, 'heads', 'head-count', 'selected-head');
  renderGrid('members-grid', window.AVAILABLE_MEMBERS || [], selectedMembers, 'members', 'member-count', 'selected-member');
}

function renderGrid(gridId, users, selectedSet, name, countId, selectedClass) {
  const grid = document.getElementById(gridId);
  if (!grid) return;

  if (users.length === 0) {
    grid.innerHTML = `<div class="empty-pool">No available users matching this role context.</div>`;
    updateSelectionCount(selectedSet.size, countId);
    return;
  }

  grid.innerHTML = users.map(u => {
    const isSelected = selectedSet.has(u.id) || selectedSet.has(String(u.id));
    const initial = (u.full_name || u.email || '?').charAt(0).toUpperCase();
    return `
      <div class="user-item ${isSelected ? selectedClass : ''}" 
           data-id="${u.id}" 
           data-search="${(u.full_name || '').toLowerCase()} ${u.email.toLowerCase()}"
           onclick="toggleSelection(this, '${name}', '${countId}', '${selectedClass}')">
        <div class="avatar">${initial}</div>
        <div class="user-info">
          <div class="u-name">${u.full_name || u.email}</div>
          <div class="u-email">${u.email}</div>
        </div>
        <div class="tick">✓</div>
      </div>
    `;
  }).join('');

  // Update initial selected set size just in case
  updateSelectionCount(selectedSet.size, countId);
}

function toggleSelection(item, name, countId, selectedClass) {
  const id = item.getAttribute('data-id');
  const targetSet = name === 'heads' ? selectedHeads : selectedMembers;
  const isSelected = item.classList.contains(selectedClass);

  if (isSelected) {
    item.classList.remove(selectedClass);
    targetSet.delete(id);
    targetSet.delete(Number(id));
  } else {
    item.classList.add(selectedClass);
    targetSet.add(id);
  }

  updateSelectionCount(targetSet.size, countId);
}

function updateSelectionCount(count, countId) {
  const el = document.getElementById(countId);
  if (el) el.textContent = count;
}

function filterGrid(gridId, query) {
  const q = query.toLowerCase().trim();
  const items = document.querySelectorAll(`#${gridId} .user-item`);
  items.forEach(item => {
    const searchStr = item.getAttribute('data-search') || '';
    item.style.display = searchStr.includes(q) ? 'flex' : 'none';
  });
}

function initPage() {
  const submitBtn = document.getElementById('submitBtn');
  if (!submitBtn) return;

  submitBtn.addEventListener('click', async () => {
    if (submitBtn.classList.contains('loading')) return;

    const name = document.getElementById('inp-name').value.trim();
    const region = document.getElementById('inp-region').value.trim();
    const orderIndexStr = document.getElementById('inp-order_index').value;
    const order_index = orderIndexStr ? parseInt(orderIndexStr, 10) : 0;

    const errBanner = document.getElementById('errorBanner');
    const errList = document.getElementById('errorList');
    if (errBanner) errBanner.style.display = 'none';
    if (errList) errList.innerHTML = '';

    // Clear previous field errors
    document.querySelectorAll('.field').forEach(f => f.classList.remove('has-error'));

    if (!name) {
      showToast('error', 'Validation Error', 'Team Name is required.');
      const f = document.getElementById('field-name');
      if (f) f.classList.add('has-error');
      return;
    }

    submitBtn.classList.add('loading');

    const payload = {
      name: name,
      region: region,
      order_index: order_index,
      heads: Array.from(selectedHeads),
      members: Array.from(selectedMembers)
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
          window.IS_EDIT ? 'Team Updated' : 'Team Created',
          `Team "${payload.name}" was ${window.IS_EDIT ? 'updated' : 'created'} successfully.`
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
  buildUserGrids();
  initPage();
});

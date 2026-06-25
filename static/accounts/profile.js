// State variable
let PROFILE_DATA = null;

async function loadProfileData() {
  try {
    const res = await fetch(window.API_DATA_URL);
    if (!res.ok) throw new Error('Failed to load profile data');
    PROFILE_DATA = await res.json();
    renderProfile();
  } catch (err) {
    console.error('Failed to load profile details', err);
    alert('Failed to load profile details.');
  }
}

function renderProfile() {
  const { target, permissions, accessible_pages } = PROFILE_DATA;

  // Avatar initial: prefer first_name, fallback to email
  const initial = (target.first_name || target.email || '?').charAt(0).toUpperCase();
  const displayName = (target.first_name && target.last_name)
    ? `${target.first_name} ${target.last_name}`
    : (target.full_name || target.email);

  const roleName = target.profile?.default_role?.name;
  const jobTitle = target.profile?.job_title;
  const department = target.profile?.department;

  // Render Left Identity Panel
  const identityEl = document.getElementById('user-panel');
  if (identityEl) {
    identityEl.innerHTML = `
      <div class="user-avatar-lg">${initial}</div>
      <h3>${displayName}</h3>
      <div class="user-email">${target.email}</div>
      ${(jobTitle || department)
        ? `<div class="user-meta-row">${[jobTitle, department].filter(Boolean).join(' · ')}</div>`
        : ''}
      ${roleName ? `<div><span class="role-badge">Role: ${roleName}</span></div>` : ''}
    `;
  }

  // Populate info fields (readonly)
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val || '';
  };
  setVal('inp-first_name', target.first_name);
  setVal('inp-last_name', target.last_name);
  setVal('inp-email', target.email);
  setVal('inp-job_title', jobTitle);
  
  let phone = target.phone || '';
  if (phone.startsWith('+20')) phone = phone.slice(3).trim();
  setVal('inp-phone', phone);
  
  const roleSelect = document.getElementById('inp-default_role');
  if (roleSelect && roleName) {
    roleSelect.innerHTML = `<option value="">${roleName}</option>`;
  }

  // Render Pages list
  const pagesLabelEl = document.getElementById('pages-label');
  if (pagesLabelEl) {
    pagesLabelEl.textContent = `Accessible Menus / Pages (${accessible_pages.length})`;
  }

  const pageList = document.getElementById('page-list');
  if (pageList) {
    if (!accessible_pages.length) {
      pageList.innerHTML = `<li class="no-pages">No menu pages accessible.</li>`;
    } else {
      pageList.innerHTML = [...accessible_pages]
        .sort((a, b) => a.menu_order - b.menu_order)
        .map(p => `
          <li class="page-item">
            <span class="pg-icon">${p.icon || '📄'}</span>
            <span>${p.name}</span>
          </li>`).join('');
    }
  }

  // Capabilities heading
  const capHeadingEl = document.getElementById('cap-heading');
  if (capHeadingEl) {
    capHeadingEl.textContent = `Granted Capabilities (${permissions.length} active codes)`;
  }

  // Permissions grid
  const grid = document.getElementById('perm-grid');
  if (grid) {
    if (!permissions.length) {
      grid.innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <h3>No Active Permissions</h3>
          <p>This user holds no active permission codes under the current role baseline.</p>
        </div>`;
    } else {
      grid.innerHTML = permissions.map(p => `
        <div class="perm-card"
             data-code="${p.code}"
             data-name="${p.name.toLowerCase()}"
             data-desc="${(p.description || '').toLowerCase()}">
          <div class="perm-card-header">
            <span class="perm-name">${p.name}</span>
            <span class="module-tag">${p.module}</span>
          </div>
          <span class="perm-code">${p.code}</span>
          ${p.description ? `<span class="perm-desc">${p.description}</span>` : ''}
        </div>`).join('');
    }
  }
}

function filterPerms() {
  if (!PROFILE_DATA) return;
  const q = document.getElementById('perm-search').value.toLowerCase();
  const cards = document.querySelectorAll('.perm-card');
  let visible = 0;

  cards.forEach(card => {
    const match = (card.dataset.code + card.dataset.name + card.dataset.desc).includes(q);
    card.style.display = match ? 'flex' : 'none';
    if (match) visible++;
  });

  const total = PROFILE_DATA.permissions.length;
  const capHeadingEl = document.getElementById('cap-heading');
  if (capHeadingEl) {
    capHeadingEl.textContent = q
      ? `Granted Capabilities (${visible} of ${total} active codes)`
      : `Granted Capabilities (${total} active codes)`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadProfileData();
});

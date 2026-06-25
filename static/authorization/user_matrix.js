// State variables
let PAGE_DATA = null;
const currentRoleDefaults = new Set();

async function loadMatrixData() {
  try {
    const res = await fetch(window.API_DATA_URL);
    if (!res.ok) throw new Error('Failed to load matrix data');
    PAGE_DATA = await res.json();
    
    // Set up default role defaults
    currentRoleDefaults.clear();
    const defaultRoleId = PAGE_DATA.target.profile.default_role ? String(PAGE_DATA.target.profile.default_role.id) : "";
    if (defaultRoleId && PAGE_DATA.role_permissions[defaultRoleId]) {
      PAGE_DATA.role_permissions[defaultRoleId].forEach(code => currentRoleDefaults.add(code));
    }
    
    renderProfile();
    renderPermissions();
    
    // Initialize checkboxes on load
    document.querySelectorAll('input[name="permissions"]').forEach(cb => updatePermissionBadge(cb));
    recalculateMetrics();
    
    // Prevent clicking the checkbox labels from double toggling
    document.querySelectorAll('.permission-item').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'LABEL') {
          const cb = item.querySelector('input[type="checkbox"]');
          if (cb) { cb.checked = !cb.checked; onPermissionManualChange(cb); }
        }
      });
    });
  } catch (err) {
    console.error('Failed to boot matrix', err);
    if (window.Swal) {
      Swal.fire({ title: 'Error', text: 'Failed to load user permission details.', icon: 'error' });
    } else {
      alert('Failed to load user permission details.');
    }
  }
}

function renderProfile() {
  const target = PAGE_DATA.target;
  const initial = (target.full_name || target.email || "?").trim().charAt(0).toUpperCase();
  document.getElementById("avatar-placeholder").textContent = initial;
  document.getElementById("target-name").textContent = target.full_name || target.email;
  document.getElementById("target-email").textContent = target.email;
  const statusBadge = document.getElementById("target-status-badge");
  if (statusBadge) {
    statusBadge.className = "user-badge";
    if (target.is_active) {
      statusBadge.textContent = "Active";
      statusBadge.classList.add("active");
    } else {
      statusBadge.textContent = "Inactive";
      statusBadge.classList.add("inactive");
    }
  }
  const profile = target.profile || {};
  document.getElementById("info-job-title").textContent = profile.job_title || "-";
  const seedRoleName = profile.default_role ? profile.default_role.name : "None";
  document.getElementById("info-seed-role").textContent = seedRoleName;
  document.getElementById("seed-role-inline").textContent = seedRoleName;
}

function groupPermissionsByModule(permissions) {
  const groups = {};
  permissions.forEach(perm => {
    if (!groups[perm.module]) groups[perm.module] = [];
    groups[perm.module].push(perm);
  });
  return groups;
}

function renderPermissions() {
  const container = document.getElementById("permissions-container");
  container.innerHTML = "";
  const grouped = groupPermissionsByModule(PAGE_DATA.permissions);

  Object.keys(grouped).forEach(moduleName => {
    const group = document.createElement("div");
    group.className = "module-group";
    group.setAttribute("data-module", moduleName);

    const header = document.createElement("div");
    header.className = "module-header";

    const h3 = document.createElement("h3");
    h3.textContent = `${moduleName} Module`;

    const actions = document.createElement("div");
    actions.className = "module-actions";

    const allBtn = document.createElement("button");
    allBtn.type = "button"; allBtn.className = "btn-text"; allBtn.textContent = "All";
    allBtn.onclick = () => toggleModulePermissions(moduleName, true);

    const noneBtn = document.createElement("button");
    noneBtn.type = "button"; noneBtn.className = "btn-text"; noneBtn.textContent = "None";
    noneBtn.onclick = () => toggleModulePermissions(moduleName, false);

    actions.appendChild(allBtn); actions.appendChild(noneBtn);
    header.appendChild(h3); header.appendChild(actions);

    const grid = document.createElement("div");
    grid.className = "permissions-grid";

    grouped[moduleName].forEach(perm => {
      const item = document.createElement("div");
      item.className = "permission-item";
      item.setAttribute("data-code", perm.code);
      item.setAttribute("data-name", (perm.name || "").toLowerCase());
      item.setAttribute("data-desc", (perm.description || "").toLowerCase());

      const label = document.createElement("label");
      label.className = "permission-label";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox"; checkbox.name = "permissions"; checkbox.value = perm.code;
      checkbox.checked = PAGE_DATA.user_active_permissions.includes(perm.code);
      checkbox.addEventListener("change", () => onPermissionManualChange(checkbox));

      const customCb = document.createElement("span");
      customCb.className = "custom-checkbox";

      const info = document.createElement("div");
      info.className = "perm-info";

      const nameSpan = document.createElement("span");
      nameSpan.className = "perm-name"; nameSpan.textContent = perm.name;

      const codeSpan = document.createElement("span");
      codeSpan.className = "perm-code"; codeSpan.textContent = perm.code;

      info.appendChild(nameSpan); info.appendChild(codeSpan);

      if (perm.description) {
        const descSpan = document.createElement("span");
        descSpan.className = "perm-desc"; descSpan.textContent = perm.description;
        info.appendChild(descSpan);
      }

      label.appendChild(checkbox); label.appendChild(customCb); label.appendChild(info);

      const badgeInherited = document.createElement("span");
      badgeInherited.className = "badge badge-inherited"; badgeInherited.style.display = "none";
      badgeInherited.textContent = "Inherited";

      const badgeOverride = document.createElement("span");
      badgeOverride.className = "badge badge-override"; badgeOverride.style.display = "none";
      badgeOverride.textContent = "Override";

      item.appendChild(label); item.appendChild(badgeInherited); item.appendChild(badgeOverride);
      grid.appendChild(item);
    });

    group.appendChild(header); group.appendChild(grid);
    container.appendChild(group);
  });
}

function updatePermissionBadge(cb) {
  const code = cb.value;
  const itemContainer = cb.closest('.permission-item');
  if (!itemContainer) return;
  const badgeInherited = itemContainer.querySelector('.badge-inherited');
  const badgeOverride = itemContainer.querySelector('.badge-override');
  const isChecked = cb.checked;
  const isDefault = currentRoleDefaults.has(code);

  if (isChecked === isDefault) {
    badgeOverride.style.display = 'none';
    if (isChecked) {
      badgeInherited.style.display = 'inline-block';
      itemContainer.classList.add('inherited-active');
      itemContainer.classList.remove('override-active');
    } else {
      badgeInherited.style.display = 'none';
      itemContainer.classList.remove('inherited-active', 'override-active');
    }
  } else {
    badgeInherited.style.display = 'none';
    badgeOverride.style.display = 'inline-block';
    itemContainer.classList.add('override-active');
    itemContainer.classList.remove('inherited-active');
  }
}

function recalculateMetrics() {
  const checkboxes = document.querySelectorAll('input[name="permissions"]');
  let activeCount = 0, overrideCount = 0;
  checkboxes.forEach(cb => {
    if (cb.checked) activeCount++;
    if (cb.checked !== currentRoleDefaults.has(cb.value)) overrideCount++;
  });
  const activeEl = document.getElementById("count-active");
  const overrideEl = document.getElementById("count-overrides");
  if (activeEl) activeEl.innerText = activeCount;
  if (overrideEl) overrideEl.innerText = overrideCount;
}

function onPermissionManualChange(cb) { updatePermissionBadge(cb); recalculateMetrics(); }

function toggleModulePermissions(moduleName, checkAll) {
  const container = document.querySelector(`.module-group[data-module="${moduleName}"]`);
  if (container) {
    container.querySelectorAll('input[name="permissions"]').forEach(cb => {
      if (cb.checked !== checkAll) { cb.checked = checkAll; updatePermissionBadge(cb); }
    });
    recalculateMetrics();
  }
}

function filterPermissions() {
  const query = document.getElementById("permission-search").value.toLowerCase();
  document.querySelectorAll(".permission-item").forEach(item => {
    const match = (item.getAttribute("data-name") || "").includes(query)
               || (item.getAttribute("data-code") || "").toLowerCase().includes(query)
               || (item.getAttribute("data-desc") || "").includes(query);
    item.style.display = match ? "flex" : "none";
  });
  document.querySelectorAll(".module-group").forEach(group => {
    const visible = group.querySelectorAll('.permission-item:not([style*="display: none"])');
    group.style.display = visible.length === 0 ? "none" : "block";
  });
}

// Handle Form AJAX Saving Overrides
const matrixForm = document.getElementById("matrix-form");
if (matrixForm) {
  matrixForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const checked = Array.from(document.querySelectorAll('input[name="permissions"]:checked')).map(cb => cb.value);
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    try {
      const res = await fetch(window.API_SAVE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || ''
        },
        body: JSON.stringify({ permissions: checked })
      });

      const data = await res.json();
      if (res.ok && data.ok) {
        if (window.Swal) {
          Swal.fire({
            title: 'Saved!',
            text: 'Permission overrides updated successfully.',
            icon: 'success',
            timer: 1500,
            showConfirmButton: false
          });
        } else {
          alert('Permission overrides updated successfully.');
        }
        recalculateMetrics();
        document.querySelectorAll('input[name="permissions"]').forEach(cb => updatePermissionBadge(cb));
      } else {
        const errorMsg = data.error || 'Failed to save matrix overrides.';
        if (window.Swal) {
          Swal.fire({ title: 'Save Failed', text: errorMsg, icon: 'error' });
        } else {
          alert(errorMsg);
        }
      }
    } catch (err) {
      console.error('Failed to save permissions matrix', err);
      if (window.Swal) {
        Swal.fire({ title: 'Error', text: 'A network error occurred. Please try again.', icon: 'error' });
      } else {
        alert('A network error occurred. Please try again.');
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadMatrixData();
});

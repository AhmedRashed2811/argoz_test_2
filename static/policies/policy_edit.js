// JavaScript for Policy edit form

function selectOption(card, code) {
  document.querySelectorAll('.option-card').forEach(c => c.classList.remove('selected'));
  card.classList.add('selected');
  const radio = card.querySelector('input[type="radio"]');
  if (radio) {
    radio.checked = true;
  }
}

function selectBool(val) {
  const yes = document.getElementById('bool-yes');
  const no = document.getElementById('bool-no');
  if (yes && no) {
    yes.classList.toggle('selected-yes', val);
    yes.classList.toggle('selected-no', false);
    no.classList.toggle('selected-no', !val);
    no.classList.toggle('selected-yes', false);
  }
  
  const yesRadio = document.querySelector('input[name="bool_value"][value="true"]');
  const noRadio = document.querySelector('input[name="bool_value"][value="false"]');
  if (val && yesRadio) {
    yesRadio.checked = true;
  } else if (!val && noRadio) {
    noRadio.checked = true;
  }
}

function initPage() {
  const form = document.getElementById('policy-form');
  const submitBtn = document.getElementById('submitBtn');
  if (!form || !submitBtn) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (submitBtn.classList.contains('loading')) return;

    const valType = window.POLICY_TYPE;
    const payload = {};

    const errBanner = document.getElementById('errorBanner');
    const errList = document.getElementById('errorList');
    if (errBanner) errBanner.style.display = 'none';
    if (errList) errList.innerHTML = '';

    if (valType === 'OPTION') {
      const selectedRadio = document.querySelector('input[name="option"]:checked');
      payload.option = selectedRadio ? selectedRadio.value : '';
      if (!payload.option) {
        showToast('error', 'Validation Error', 'Please select an option.');
        return;
      }
    } else if (valType === 'DURATION') {
      const hInput = document.getElementById('id_hours');
      const mInput = document.getElementById('id_minutes');
      payload.hours = parseInt(hInput ? hInput.value : 0, 10);
      payload.minutes = parseInt(mInput ? mInput.value : 0, 10);
      if (isNaN(payload.hours) || payload.hours < 0) {
        showToast('error', 'Validation Error', 'Hours must be a non-negative number.');
        return;
      }
      if (isNaN(payload.minutes) || payload.minutes < 0 || payload.minutes > 59) {
        showToast('error', 'Validation Error', 'Minutes must be between 0 and 59.');
        return;
      }
    } else if (valType === 'INTEGER') {
      const intInput = document.querySelector('input[name="integer_value"]');
      payload.integer_value = parseInt(intInput ? intInput.value : 0, 10);
      if (isNaN(payload.integer_value) || payload.integer_value < 0) {
        showToast('error', 'Validation Error', 'Value must be a non-negative integer.');
        return;
      }
    } else if (valType === 'BOOLEAN') {
      const selectedRadio = document.querySelector('input[name="bool_value"]:checked');
      payload.bool_value = selectedRadio ? selectedRadio.value : 'false';
    } else if (valType === 'CODE') {
      const codeInput = document.querySelector('input[name="code_value"]');
      payload.code_value = codeInput ? codeInput.value.trim() : '';
      if (!payload.code_value) {
        showToast('error', 'Validation Error', 'Code value is required.');
        return;
      }
    } else if (valType === 'COMPOSITE') {
      payload.enabled = !!document.getElementById('composite-enabled')?.checked;
      document.querySelectorAll('.composite-int').forEach(inp => {
        const v = parseInt(inp.value, 10);
        if (isNaN(v) || v < 0) { inp.value = 0; }
        payload[inp.dataset.key] = Math.max(0, isNaN(v) ? 0 : v);
      });
      document.querySelectorAll('.weekday-grid').forEach(grid => {
        payload[grid.dataset.key] = Array.from(
          grid.querySelectorAll('.composite-weekday:checked')
        ).map(cb => parseInt(cb.value, 10));
      });
    } else if (valType === 'JSON') {
      const jsonTextarea = document.querySelector('textarea[name="value_json"]');
      payload.value_json = jsonTextarea ? jsonTextarea.value.trim() : '';
      if (payload.value_json) {
        try {
          JSON.parse(payload.value_json);
        } catch (err) {
          showToast('error', 'Validation Error', 'Invalid JSON syntax. Please verify.');
          return;
        }
      }
    }

    submitBtn.classList.add('loading');

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    const apiUrl = window.API_EDIT_URL;

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
        showToast('success', 'Policy Configured', 'Policy value saved successfully.');
        setTimeout(() => {
          window.location.href = window.DIRECTORY_URL;
        }, 1500);
      } else {
        if (errBanner && errList) {
          errBanner.style.display = 'block';
          const li = document.createElement('li');
          li.textContent = data.error || 'Server error occurred.';
          errList.appendChild(li);
        }
        showToast('error', 'Action Failed', data.error || 'Failed to update policy.');
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

function initComposite() {
  const toggle = document.getElementById('composite-enabled');
  const fields = document.getElementById('composite-fields');
  if (!toggle || !fields) return;
  const sync = () => { fields.style.opacity = toggle.checked ? '1' : '.45';
                       fields.style.pointerEvents = toggle.checked ? 'auto' : 'none'; };
  toggle.addEventListener('change', sync); sync();
  document.querySelectorAll('.weekday-chip input').forEach(cb => {
    cb.addEventListener('change', () => cb.closest('.weekday-chip').classList.toggle('selected', cb.checked));
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initPage();
  initComposite();
});

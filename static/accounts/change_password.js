// Change password client-side interactions & AJAX

function setupEyeToggle(btnId, inputId, iconId) {
  const btn = document.getElementById(btnId);
  const inp = document.getElementById(inputId);
  const ico = document.getElementById(iconId);
  if (!btn || !inp || !ico) return;
  
  const EYE_OPEN = '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/>';
  const EYE_CLOSED = '<path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a18.5 18.5 0 0 1 4.06-5.06M9.9 4.24A9.9 9.9 0 0 1 12 4c7 0 11 7 11 7a18.5 18.5 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';

  btn.addEventListener('click', () => {
    const isPw = inp.type === 'password';
    inp.type = isPw ? 'text' : 'password';
    ico.innerHTML = isPw ? EYE_CLOSED : EYE_OPEN;
  });
}

function showFieldError(wrapEl, errEl, message) {
  wrapEl.classList.add('error');
  errEl.textContent = message;
  errEl.classList.add('show');
}

function clearFieldError(wrapEl, errEl) {
  wrapEl.classList.remove('error');
  errEl.textContent = '';
  errEl.classList.remove('show');
}

function showAlert(message, isSuccess = false) {
  const alertBox = document.getElementById('alertBox');
  if (!alertBox) return;
  alertBox.textContent = message;
  alertBox.classList.add('show');
  if (isSuccess) {
    alertBox.style.background = '#eafaf1';
    alertBox.style.borderColor = '#b7e4c7';
    alertBox.style.color = '#1e7e45';
  } else {
    alertBox.style.background = '#fdecea';
    alertBox.style.borderColor = '#f5c6c0';
    alertBox.style.color = '#c0392b';
  }
}

function hideAlert() {
  const alertBox = document.getElementById('alertBox');
  if (alertBox) alertBox.classList.remove('show');
}

document.addEventListener("DOMContentLoaded", () => {
  setupEyeToggle('toggleCurrent', 'f-current', 'eyeCurrent');
  setupEyeToggle('toggleNew', 'f-new', 'eyeNew');
  setupEyeToggle('toggleConfirm', 'f-confirm', 'eyeConfirm');

  const form = document.getElementById('changePasswordForm');
  const currentInp = document.getElementById('f-current');
  const newInp = document.getElementById('f-new');
  const confirmInp = document.getElementById('f-confirm');

  const currentWrap = document.getElementById('currentWrap');
  const newWrap = document.getElementById('newWrap');
  const confirmWrap = document.getElementById('confirmWrap');

  const currentErr = document.getElementById('currentErr');
  const newErr = document.getElementById('newErr');
  const confirmErr = document.getElementById('confirmErr');

  if (currentInp) currentInp.addEventListener('input', () => clearFieldError(currentWrap, currentErr));
  if (newInp) newInp.addEventListener('input', () => clearFieldError(newWrap, newErr));
  if (confirmInp) confirmInp.addEventListener('input', () => clearFieldError(confirmWrap, confirmErr));

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideAlert();
      clearFieldError(currentWrap, currentErr);
      clearFieldError(newWrap, newErr);
      clearFieldError(confirmWrap, confirmErr);

      const currentVal = currentInp.value;
      const newVal = newInp.value;
      const confirmVal = confirmInp.value;

      let hasError = false;

      if (!currentVal) {
        showFieldError(currentWrap, currentErr, 'Current password is required.');
        hasError = true;
      }

      if (!newVal) {
        showFieldError(newWrap, newErr, 'New password is required.');
        hasError = true;
      } else if (newVal.length < 8) {
        showFieldError(newWrap, newErr, 'New password must be at least 8 characters long.');
        hasError = true;
      }

      if (newVal !== confirmVal) {
        showFieldError(confirmWrap, confirmErr, 'Passwords do not match.');
        hasError = true;
      }

      if (hasError) return;

      const submitBtn = document.getElementById('submitBtn');
      if (submitBtn) submitBtn.classList.add('loading');

      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

      try {
        const response = await fetch(window.API_SUBMIT_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken || ''
          },
          body: JSON.stringify({
            current_password: currentVal,
            new_password: newVal
          })
        });

        const data = await response.json();
        if (submitBtn) submitBtn.classList.remove('loading');

        if (response.ok && data.ok) {
          showAlert('Password changed successfully! Redirecting...', true);
          setTimeout(() => {
            window.location.href = window.PROFILE_URL;
          }, 1500);
        } else {
          const errorMsg = data.error || 'Failed to change password. Please check the errors.';
          showAlert(errorMsg);
          if (errorMsg.toLowerCase().includes('current')) {
            showFieldError(currentWrap, currentErr, errorMsg);
          } else if (errorMsg.toLowerCase().includes('new') || errorMsg.toLowerCase().includes('length') || errorMsg.toLowerCase().includes('character')) {
            showFieldError(newWrap, newErr, errorMsg);
          }
        }
      } catch (err) {
        console.error('AJAX password change failed', err);
        if (submitBtn) submitBtn.classList.remove('loading');
        showAlert('An unexpected network error occurred. Please try again.');
      }
    });
  }
});

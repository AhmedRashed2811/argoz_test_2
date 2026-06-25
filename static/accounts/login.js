// --- Password show/hide toggle ---
const eyeBtn = document.getElementById('eyeBtn');
const pw = document.getElementById('f-pw');
const eyeIco = document.getElementById('eyeIco');
const EYE_OPEN = '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/>';
const EYE_OFF = '<path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-7-11-7a18.5 18.5 0 0 1 5.06-6.06M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 7 11 7a18.5 18.5 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';

if (eyeBtn && pw && eyeIco) {
  eyeBtn.addEventListener('click', () => {
    const show = pw.type === 'password';
    pw.type = show ? 'text' : 'password';
    eyeIco.innerHTML = show ? EYE_OFF : EYE_OPEN;
    eyeBtn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  });
}

// --- DOM refs ---
const form = document.getElementById('loginForm');
const emailInput = document.getElementById('f-email');
const pwInput = document.getElementById('f-pw');
const emailWrap = document.getElementById('emailWrap');
const pwWrap = document.getElementById('pwWrap');
const emailErr = document.getElementById('emailErr');
const pwErr = document.getElementById('pwErr');
const alertBox = document.getElementById('alertBox');

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

function showAlert(message) {
  alertBox.textContent = message;
  alertBox.classList.add('show');
}

function hideAlert() {
  alertBox.textContent = '';
  alertBox.classList.remove('show');
}

function isValidEmailFormat(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

// Clear errors as the user types
if (emailInput) {
  emailInput.addEventListener('input', () => clearFieldError(emailWrap, emailErr));
}
if (pwInput) {
  pwInput.addEventListener('input', () => clearFieldError(pwWrap, pwErr));
}

if (form) {
  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    hideAlert();
    clearFieldError(emailWrap, emailErr);
    clearFieldError(pwWrap, pwErr);

    const emailVal = emailInput.value.trim();
    const pwVal = pwInput.value;

    let hasError = false;

    // Required field validation
    if (!emailVal) {
      showFieldError(emailWrap, emailErr, 'Email address is required.');
      hasError = true;
    } else if (!isValidEmailFormat(emailVal)) {
      showFieldError(emailWrap, emailErr, 'Please enter a valid email address.');
      hasError = true;
    }

    if (!pwVal) {
      showFieldError(pwWrap, pwErr, 'Password is required.');
      hasError = true;
    }

    if (hasError) {
      return;
    }

    // Get CSRF Token from DOM
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    const rememberVal = document.getElementById('remember')?.checked || false;

    try {
      const response = await fetch(window.location.pathname, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || ''
        },
        body: JSON.stringify({ email: emailVal, password: pwVal, remember: rememberVal })
      });

      const data = await response.json();
      if (response.ok && data.ok) {
        showAlert('Login successful! Redirecting...');
        alertBox.style.background = '#eafaf1';
        alertBox.style.borderColor = '#b7e4c7';
        alertBox.style.color = '#1e7e45';
        
        // Find if next param exists
        const urlParams = new URLSearchParams(window.location.search);
        const nextUrl = urlParams.get('next') || '/';
        
        setTimeout(() => {
          window.location.href = nextUrl;
        }, 600);
      } else {
        const errorMsg = data.error || 'Incorrect email or password. Please try again.';
        showAlert(errorMsg);
        if (errorMsg.toLowerCase().includes('email')) {
          showFieldError(emailWrap, emailErr, errorMsg);
        } else if (errorMsg.toLowerCase().includes('password')) {
          showFieldError(pwWrap, pwErr, errorMsg);
        }
      }
    } catch (err) {
      console.error('AJAX login failed', err);
      showAlert('An unexpected network error occurred. Please try again.');
    }
  });
}

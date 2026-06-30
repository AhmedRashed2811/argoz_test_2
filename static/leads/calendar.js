/* Sales Calendar — follow-ups, meetings, SLA deadlines, freeze returns.
   Data loads per-month from leads:api_calendar (server-scoped own/team/all). */
(function () {
  const CFG = window.CAL_CFG || {};
  const grid = document.getElementById('calGrid');
  const titleEl = document.getElementById('calTitle');
  const loadingEl = document.getElementById('calLoading');

  const MONTHS = ['January','February','March','April','May','June','July',
                  'August','September','October','November','December'];
  const KIND = {
    followup: { cls: 'followup', label: 'Follow-up',
      icon: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>' },
    meeting: { cls: 'meeting', label: 'Meeting',
      icon: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>' },
    sla: { cls: 'sla', label: 'SLA deadline',
      icon: '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/>' },
    freeze: { cls: 'freeze', label: 'Freeze return',
      icon: '<line x1="12" y1="2" x2="12" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><path d="m20 16-4-4 4-4"/><path d="m4 8 4 4-4 4"/><path d="m16 4-4 4-4-4"/><path d="m8 20 4-4 4 4"/>' },
  };

  function kindOf(ev) { return ev.type; }

  const today = new Date();
  today.setHours(0, 0, 0, 0); // midnight, for date-only past comparisons
  let viewY = today.getFullYear();
  let viewM = today.getMonth(); // 0-11
  const cache = {};             // "Y-M" -> { dateStr: [events] }

  function ymKey(y, m) { return y + '-' + m; }
  function pad(n) { return String(n).padStart(2, '0'); }
  function dateStr(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }

  function fetchMonth(y, m) {
    const key = ymKey(y, m);
    if (cache[key]) return Promise.resolve(cache[key]);
    loadingEl.classList.add('show');
    const url = CFG.apiUrl + '?year=' + y + '&month=' + (m + 1);
    return fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(r => r.json())
      .then(data => {
        const byDate = {};
        (data.events || []).forEach(ev => {
          (byDate[ev.date] = byDate[ev.date] || []).push(ev);
        });
        cache[key] = byDate;
        return byDate;
      })
      .catch(() => ({}))
      .finally(() => loadingEl.classList.remove('show'));
  }

  function render() {
    titleEl.textContent = MONTHS[viewM] + ' ' + viewY;
    fetchMonth(viewY, viewM).then(byDate => {
      // Only redraw if still on this month (avoid race on fast nav).
      if (titleEl.textContent !== MONTHS[viewM] + ' ' + viewY) return;
      grid.innerHTML = '';
      const first = new Date(viewY, viewM, 1);
      const startDay = first.getDay();              // 0=Sun
      const daysInMonth = new Date(viewY, viewM + 1, 0).getDate();
      const prevDays = new Date(viewY, viewM, 0).getDate();
      const totalCells = Math.ceil((startDay + daysInMonth) / 7) * 7;
      const todayStr = dateStr(today);

      for (let i = 0; i < totalCells; i++) {
        const dayNum = i - startDay + 1;
        let cellDate, other = false;
        if (dayNum < 1) { cellDate = new Date(viewY, viewM - 1, prevDays + dayNum); other = true; }
        else if (dayNum > daysInMonth) { cellDate = new Date(viewY, viewM + 1, dayNum - daysInMonth); other = true; }
        else { cellDate = new Date(viewY, viewM, dayNum); }

        const ds = dateStr(cellDate);
        const isPast = cellDate < today;
        // Past days carry no events (filtered server-side) and aren't clickable.
        const events = isPast ? [] : (byDate[ds] || []);
        grid.appendChild(buildCell(cellDate, ds, events, other, ds === todayStr, isPast));
      }
    });
  }

  function buildCell(cellDate, ds, events, other, isToday, isPast) {
    const cell = document.createElement('div');
    cell.className = 'cal-day' + (other ? ' other-month' : '') + (isPast ? ' past' : '')
      + (isToday ? ' today' : '') + (events.length ? ' has-events' : '');
    const num = document.createElement('span');
    num.className = 'cal-daynum';
    num.textContent = cellDate.getDate();
    cell.appendChild(num);

    if (events.length) {
      const wrap = document.createElement('div');
      wrap.className = 'cal-events';
      const shown = events.slice(0, 3);
      shown.forEach((ev, idx) => {
        const k = kindOf(ev);
        const chip = document.createElement('div');
        chip.className = 'cal-chip ' + KIND[k].cls;
        chip.style.animationDelay = (idx * 40) + 'ms';
        chip.innerHTML = '<span class="chip-time">' + esc(ev.time) + '</span>'
          + '<span class="chip-name">' + esc(ev.lead_name) + '</span>';
        wrap.appendChild(chip);
      });
      if (events.length > 3) {
        const more = document.createElement('div');
        more.className = 'cal-more';
        more.textContent = '+' + (events.length - 3) + ' more';
        wrap.appendChild(more);
      }
      cell.appendChild(wrap);

      // Compact dot row for small screens.
      const dots = document.createElement('div');
      dots.className = 'cal-dots';
      [...new Set(events.map(kindOf))].forEach(k => {
        const dot = document.createElement('span');
        dot.className = 'cal-dot ' + KIND[k].cls;
        dots.appendChild(dot);
      });
      cell.appendChild(dots);

      cell.addEventListener('click', () => openDay(cellDate, events));
    }
    return cell;
  }

  /* ── Day modal ── */
  const backdrop = document.getElementById('calModalBackdrop');
  const modalBody = document.getElementById('calModalBody');

  function openDay(cellDate, events) {
    const wd = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][cellDate.getDay()];
    document.getElementById('calModalWeekday').textContent = wd.slice(0, 3);
    document.getElementById('calModalDayNum').textContent = cellDate.getDate();
    document.getElementById('calModalDate').textContent = wd + ', ' + MONTHS[cellDate.getMonth()] + ' ' + cellDate.getDate();
    document.getElementById('calModalCount').textContent =
      events.length + (events.length === 1 ? ' event scheduled' : ' events scheduled');

    modalBody.innerHTML = '';
    events.forEach((ev, idx) => modalBody.appendChild(buildEventRow(ev, idx)));
    backdrop.classList.add('show');
    document.body.style.overflow = 'hidden';
  }

  function buildEventRow(ev, idx) {
    const k = kindOf(ev);
    const row = document.createElement('div');
    row.className = 'cal-evt ' + KIND[k].cls;
    row.style.animationDelay = (idx * 55) + 'ms';

    const meta = [];
    if (ev.stage) meta.push('Stage: ' + ev.stage);
    if (ev.salesman) meta.push('Owner: ' + ev.salesman);
    if (ev.extra && ev.extra.location) meta.push('Location: ' + ev.extra.location);
    if (ev.type === 'freeze' && ev.extra && ev.extra.status) meta.push('Reminder: ' + ev.extra.status);
    if (ev.type === 'followup' && ev.extra && ev.extra.notes) meta.push(ev.extra.notes);

    row.innerHTML =
      '<div class="cal-evt-icon"><svg viewBox="0 0 24 24">' + KIND[k].icon + '</svg></div>'
      + '<div class="cal-evt-main">'
      +   '<div class="cal-evt-toprow">'
      +     '<span class="cal-evt-kind">' + esc(KIND[k].label) + '</span>'
      +     '<span class="cal-evt-time">' + esc(ev.time) + '</span>'
      +   '</div>'
      +   '<div class="cal-evt-name">' + esc(ev.lead_name) + '</div>'
      +   '<div class="cal-evt-meta">' + meta.map(m => '<span>' + esc(m) + '</span>').join('') + '</div>'
      +   '<button class="cal-evt-go">View lead'
      +     '<svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>'
      +   '</button>'
      + '</div>';
    row.querySelector('.cal-evt-go').addEventListener('click', () => {
      window.location.href = CFG.leadsUrl + '?search=' + encodeURIComponent(ev.lead_phone || ev.lead_name);
    });
    return row;
  }

  function closeModal() {
    backdrop.classList.remove('show');
    document.body.style.overflow = '';
  }
  document.getElementById('calModalClose').addEventListener('click', closeModal);
  backdrop.addEventListener('click', e => { if (e.target === backdrop) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && backdrop.classList.contains('show')) closeModal(); });

  /* ── Navigation ── */
  document.getElementById('calPrev').addEventListener('click', () => {
    viewM--; if (viewM < 0) { viewM = 11; viewY--; } render();
  });
  document.getElementById('calNext').addEventListener('click', () => {
    viewM++; if (viewM > 11) { viewM = 0; viewY++; } render();
  });
  document.getElementById('calTodayBtn').addEventListener('click', () => {
    viewY = today.getFullYear(); viewM = today.getMonth(); render();
  });

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  render();
})();

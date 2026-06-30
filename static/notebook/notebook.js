/* Argoz CRM — personal notebook widget. AJAX CRUD over the notebook API.
   Markup is server-rendered in base.html; this only wires behaviour. No page
   reloads. Mirrors chat.js patterns so the two widgets behave alike. */
(function () {
  const CFG = (window.LAYOUT_CFG || {}).notebook;
  const nbBtn = document.getElementById('nbBtn');
  if (!CFG || !nbBtn) return;

  const $ = (id) => document.getElementById(id);
  const panel = $('nbPanel'), backdrop = $('nbBackdrop');
  const listBody = $('nbListBody');
  const editor = $('nbEditor'), titleInput = $('nbTitle'), bodyInput = $('nbBodyInput');
  const saveBtn = editor.querySelector('.nb-save-btn'), saveState = $('nbSaveState');
  const deleteBtn = $('nbDeleteBtn'), editorLabel = $('nbEditorLabel'), editorStamp = $('nbEditorStamp');

  let notes = [];
  let current = null;    // the note being edited, or null for a new note
  let saving = false;

  /* ── helpers ── */
  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const headers = () => ({ 'X-CSRFToken': (window.LAYOUT_CFG.csrf) || '' });
  const fetchJSON = (url, opts) =>
    fetch(url, Object.assign({ credentials: 'same-origin', headers: headers() }, opts)).then(r => r.json());
  const fillTmpl = (tmpl, id) => tmpl.replace('00000000-0000-0000-0000-000000000000', id);
  function fmtDay(iso) {
    const d = new Date(iso); if (isNaN(d)) return '';
    const now = new Date();
    if (d.toDateString() === now.toDateString())
      return 'Today ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  /* ── list ── */
  async function loadList() {
    const d = await fetchJSON(CFG.listUrl).catch(() => null);
    if (!d) return;
    notes = d.notes || [];
    renderList();
  }
  function renderList() {
    const q = ($('nbSearch').value || '').trim().toLowerCase();
    const rows = notes.filter(n => !q ||
      n.title.toLowerCase().includes(q) || (n.body || '').toLowerCase().includes(q));
    if (!rows.length) {
      listBody.innerHTML = emptyState('No notes yet', 'Tap the + button to write one.');
      return;
    }
    listBody.innerHTML = rows.map(n => {
      const title = n.title
        ? `<span class="nb-row-title">${esc(n.title)}</span>`
        : `<span class="nb-row-title untitled">Untitled</span>`;
      return `
        <div class="nb-row" data-id="${n.id}">
          <div class="nb-row-top">${title}<span class="nb-row-time">${esc(fmtDay(n.updated_at))}</span></div>
          ${n.preview ? `<div class="nb-row-preview">${esc(n.preview)}</div>` : ''}
        </div>`;
    }).join('');
    listBody.querySelectorAll('.nb-row').forEach(el =>
      el.addEventListener('click', () => openNote(el.dataset.id)));
  }

  /* ── editor ── */
  function openNote(id) {
    const n = notes.find(x => x.id === id);
    if (!n) return;
    current = n;
    titleInput.value = n.title || '';
    bodyInput.value = n.body || '';
    editorLabel.textContent = 'Note';
    editorStamp.textContent = 'Edited ' + fmtDay(n.updated_at);
    deleteBtn.hidden = false;
    saveState.textContent = '';
    setView('editor');
    titleInput.focus();
  }
  function newNote() {
    current = null;
    titleInput.value = ''; bodyInput.value = '';
    editorLabel.textContent = 'New note';
    editorStamp.textContent = '';
    deleteBtn.hidden = true;
    saveState.textContent = '';
    setView('editor');
    titleInput.focus();
  }
  function upsert(note) {
    const i = notes.findIndex(n => n.id === note.id);
    if (i === -1) notes.unshift(note);
    else notes[i] = note;
    // keep most-recently-edited on top (server orders the same way)
    notes.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
  }

  async function save() {
    if (saving) return;
    const title = titleInput.value.trim(), body = bodyInput.value.trim();
    if (!title && !body) { saveState.textContent = 'Nothing to save'; return; }
    saving = true; saveBtn.disabled = true; saveState.textContent = 'Saving…';
    const fd = new FormData();
    fd.append('title', title); fd.append('body', body);
    const isNew = !current;
    const url = current ? fillTmpl(CFG.updateTmpl, current.id) : CFG.createUrl;
    try {
      const d = await fetchJSON(url, { method: 'POST', body: fd });
      if (d && d.ok) {
        upsert(d.note);
        current = null;
        renderList();
        setView('list');               // back to all notes
        toast(isNew ? 'Note added successfully' : 'Note updated successfully');
      } else {
        saveState.textContent = (d && d.error) || 'Could not save';
      }
    } catch (_) { saveState.textContent = 'Could not save'; }
    finally { saving = false; saveBtn.disabled = false; }
  }
  editor.addEventListener('submit', (e) => { e.preventDefault(); save(); });

  async function remove() {
    if (!current) { setView('list'); return; }
    const ok = await confirmDelete();
    if (!ok) return;
    const d = await fetchJSON(fillTmpl(CFG.deleteTmpl, current.id), { method: 'POST' }).catch(() => null);
    if (!d || !d.ok) return;
    notes = notes.filter(n => n.id !== current.id);
    current = null;
    renderList();
    setView('list');
  }
  deleteBtn.addEventListener('click', remove);

  function confirmDelete() {
    if (window.Swal) {
      return window.Swal.fire({
        title: 'Delete note?', text: 'This cannot be undone.', icon: 'warning',
        showCancelButton: true, confirmButtonText: 'Delete', confirmButtonColor: '#c0392b',
      }).then(r => r.isConfirmed);
    }
    return Promise.resolve(window.confirm('Delete this note?'));
  }

  /* ── panel control ── */
  function setView(v) { panel.setAttribute('data-view', v); }
  function open() {
    // only one bottom-right panel at a time — close chat if it's open
    const chatPanel = $('chatPanel'), chatBackdrop = $('chatBackdrop');
    if (chatPanel) chatPanel.classList.remove('open');
    if (chatBackdrop) chatBackdrop.classList.remove('open');
    panel.classList.add('open'); backdrop.classList.add('open');
    setView('list');
    loadList();
  }
  function close() { panel.classList.remove('open'); backdrop.classList.remove('open'); }
  nbBtn.addEventListener('click', (e) => { e.stopPropagation(); panel.classList.contains('open') ? close() : open(); });
  backdrop.addEventListener('click', close);
  panel.querySelectorAll('[data-nb-close]').forEach(b => b.addEventListener('click', close));
  panel.querySelectorAll('[data-nb-back]').forEach(b => b.addEventListener('click', () => { setView('list'); current = null; }));
  $('nbNewBtn').addEventListener('click', newNote);
  $('nbSearch').addEventListener('input', renderList);

  function toast(text) {
    if (window.Swal) {
      window.Swal.fire({
        toast: true, position: 'top-end', icon: 'success', title: text,
        showConfirmButton: false, timer: 2200, timerProgressBar: true,
      });
    }
  }

  function emptyState(title, sub) {
    return `<div class="nb-empty">
      <svg viewBox="0 0 24 24"><path d="M6 4H17.5C18.33 4 19 4.67 19 5.5V18.5C19 19.33 18.33 20 17.5 20H6V4Z"/><path d="M6 4V20"/></svg>
      <h4>${esc(title)}</h4>${sub ? `<p>${esc(sub)}</p>` : ''}</div>`;
  }
})();

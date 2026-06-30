// JavaScript for Policies list page
(function () {
  function qs(selector, root = document) { return root.querySelector(selector); }
  function qsa(selector, root = document) { return Array.from(root.querySelectorAll(selector)); }

  function filterPolicies() {
    const input = qs('#policy-search');
    const q = (input ? input.value : '').toLowerCase().trim();
    let visibleCards = 0;

    qsa('.policy-card').forEach(card => {
      const searchStr = card.getAttribute('data-search') || '';
      const visible = !q || searchStr.includes(q);
      card.hidden = !visible;
      if (visible) visibleCards += 1;
    });

    qsa('.policy-group').forEach(group => {
      const visible = qsa('.policy-card:not([hidden])', group).length > 0;
      group.hidden = !visible;
      if (q && visible) group.classList.remove('is-collapsed');
    });

    qsa('.module-section').forEach(section => {
      const visible = qsa('.policy-group:not([hidden])', section).length > 0;
      section.hidden = !visible;
    });

    const empty = qs('#policy-empty-search');
    if (empty) empty.style.display = q && visibleCards === 0 ? 'block' : 'none';
  }

  function openDrawer() {
    const drawer = qs('#policyDrawer');
    const backdrop = qs('#policyDrawerBackdrop');
    if (!drawer || !backdrop) return;
    backdrop.hidden = false;
    drawer.setAttribute('aria-hidden', 'false');
    drawer.classList.add('is-open');
  }

  function closeDrawer() {
    const drawer = qs('#policyDrawer');
    const backdrop = qs('#policyDrawerBackdrop');
    if (!drawer || !backdrop) return;
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    backdrop.hidden = true;
  }

  function setDrawerLoading(title) {
    const body = qs('#policyDrawerBody');
    const drawerTitle = qs('#drawerTitle');
    if (drawerTitle) drawerTitle.textContent = title || 'Configure policy';
    if (body) body.innerHTML = '<div class="drawer-placeholder">Loading policy settings...</div>';
  }

  async function loadPolicyEditor(link) {
    const card = link.closest('.policy-card');
    const title = qs('.policy-name', card)?.childNodes[0]?.textContent?.trim() || 'Configure policy';
    setDrawerLoading(title);
    openDrawer();

    try {
      const res = await fetch(link.href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const html = await res.text();
      if (!res.ok) throw new Error('Could not load policy editor.');

      const doc = new DOMParser().parseFromString(html, 'text/html');
      const cardContent = doc.querySelector('.glass-card');
      const body = qs('#policyDrawerBody');
      if (!cardContent || !body) throw new Error('Policy editor content is unavailable.');

      body.innerHTML = '';
      body.appendChild(cardContent);
      window.POLICY_TYPE = link.dataset.policyType;
      window.API_EDIT_URL = link.dataset.apiUrl;
      window.DIRECTORY_URL = window.location.href;
      window.POLICY_EMBEDDED = true;
      window.ACTIVE_POLICY_ID = link.dataset.policyId;

      if (typeof window.initPage === 'function') window.initPage();
      if (typeof window.initComposite === 'function') window.initComposite();
    } catch (err) {
      const body = qs('#policyDrawerBody');
      if (body) body.innerHTML = '<div class="drawer-placeholder error">Unable to load this policy. Please try again.</div>';
    }
  }

  function updatePolicyCard(detail) {
    if (!detail || !detail.policy_id) return;
    const card = qs('.policy-card[data-policy-id="' + detail.policy_id + '"]');
    if (!card) return;

    card.classList.toggle('is-set', !!detail.is_set);
    card.classList.toggle('not-set', !detail.is_set);
    const value = qs('.policy-value', card);
    if (value) {
      value.textContent = detail.is_set ? (detail.current_display || 'Configured') : 'Not configured';
      value.classList.toggle('value-set', !!detail.is_set);
      value.classList.toggle('value-unset', !detail.is_set);
    }
    recalcCounts();
  }

  function recalcCounts() {
    let configuredTotal = 0;
    qsa('.policy-group').forEach(group => {
      const cards = qsa('.policy-card', group);
      const configured = cards.filter(card => card.classList.contains('is-set')).length;
      configuredTotal += configured;
      const count = qs('.group-count', group);
      if (count) count.textContent = configured + '/' + cards.length;
    });

    qsa('.module-section').forEach(section => {
      const key = section.dataset.module;
      const cards = qsa('.policy-card', section);
      const configured = cards.filter(card => card.classList.contains('is-set')).length;
      const label = configured + '/' + cards.length;
      const moduleCount = qs('[data-module-total="' + key + '"]');
      const navCount = qs('[data-module-count="' + key + '"]');
      if (moduleCount) moduleCount.textContent = label;
      if (navCount) navCount.textContent = label;
    });

    const configured = qs('#configured-count');
    if (configured) configured.textContent = String(configuredTotal);
  }

  function bindEvents() {
    const search = qs('#policy-search');
    if (search) search.addEventListener('input', filterPolicies);

    qsa('.group-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const group = btn.closest('.policy-group');
        if (!group) return;
        const collapsed = group.classList.toggle('is-collapsed');
        btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      });
    });

    qsa('.module-nav-link, .group-nav-link').forEach(link => {
      link.addEventListener('click', () => {
        qsa('.module-nav-link, .group-nav-link').forEach(item => item.classList.remove('active'));
        link.classList.add('active');
      });
    });

    qsa('.js-policy-edit').forEach(link => {
      link.addEventListener('click', event => {
        event.preventDefault();
        loadPolicyEditor(link);
      });
    });

    const backdrop = qs('#policyDrawerBackdrop');
    qsa('.js-drawer-close, #policyDrawerClose').forEach(btn => btn.addEventListener('click', closeDrawer));
    if (backdrop) backdrop.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeDrawer();
    });

    document.addEventListener('policy:saved', event => {
      updatePolicyCard(event.detail);
      filterPolicies();
    });
  }

  window.filterPolicies = filterPolicies;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindEvents);
  } else {
    bindEvents();
  }
})();

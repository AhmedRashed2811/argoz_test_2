// JavaScript for Permission Catalog page
let activeRisk = 'ALL';

document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.perm-card');
  const counts = { LOW: 0, MEDIUM: 0, HIGH: 0 };
  
  cards.forEach(c => {
    const r = c.getAttribute('data-risk');
    if (counts[r] !== undefined) counts[r]++;
  });

  const totalEl = document.getElementById('stat-total');
  const lowEl = document.getElementById('stat-low');
  const medEl = document.getElementById('stat-medium');
  const highEl = document.getElementById('stat-high');

  if (totalEl) totalEl.textContent = cards.length;
  if (lowEl) lowEl.textContent = counts.LOW;
  if (medEl) medEl.textContent = counts.MEDIUM;
  if (highEl) highEl.textContent = counts.HIGH;

  // Set up header toggle clicks
  document.querySelectorAll('.module-header').forEach(header => {
    header.addEventListener('click', () => {
      toggleGroup(header.parentElement);
    });
  });
});

function setRisk(btn, risk) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeRisk = risk;
  applyFilters();
}

function applyFilters() {
  const q = document.getElementById('perm-search').value.toLowerCase().trim();
  let visible = 0;

  document.querySelectorAll('.module-group').forEach(group => {
    let groupVisible = 0;
    
    group.querySelectorAll('.perm-card').forEach(card => {
      const name = card.getAttribute('data-name') || '';
      const code = card.getAttribute('data-code') || '';
      const risk = card.getAttribute('data-risk') || '';
      
      const matchSearch = !q || name.includes(q) || code.includes(q);
      const matchRisk = activeRisk === 'ALL' || risk === activeRisk;
      const show = matchSearch && matchRisk;
      
      card.style.display = show ? 'flex' : 'none';
      if (show) {
        groupVisible++;
        visible++;
      }
    });

    // Update count badge
    const badge = group.querySelector('[data-module-count]');
    if (badge) badge.textContent = groupVisible;

    // Show/hide entire group
    group.style.display = groupVisible > 0 ? 'block' : 'none';
  });

  const visibleCountEl = document.getElementById('visible-count');
  if (visibleCountEl) visibleCountEl.textContent = visible;

  const noResultsEl = document.getElementById('no-results-msg');
  if (noResultsEl) noResultsEl.style.display = visible === 0 ? 'block' : 'none';
}

function toggleGroup(group) {
  group.classList.toggle('collapsed');
}

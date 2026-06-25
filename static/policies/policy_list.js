// JavaScript for Policies list page
function filterPolicies() {
  const q = document.getElementById('policy-search').value.toLowerCase().trim();
  
  document.querySelectorAll('.policy-card').forEach(card => {
    const searchStr = card.getAttribute('data-search') || '';
    card.style.display = searchStr.includes(q) ? 'flex' : 'none';
  });

  document.querySelectorAll('.module-section').forEach(section => {
    const visible = section.querySelectorAll('.policy-card:not([style*="display: none"])').length;
    section.style.display = visible > 0 ? '' : 'none';
  });
}

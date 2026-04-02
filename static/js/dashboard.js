/**
 * ValueBet FC — Dashboard JS
 * Filtrage historique + déclenchement manuel des pipelines
 */

// ── Filtrage du tableau historique ─────────────────────────────────────

function filterHistory() {
  const market = document.getElementById('filter-market')?.value || '';
  const status = document.getElementById('filter-status')?.value || '';
  const rows = document.querySelectorAll('.history-row');

  rows.forEach(row => {
    const rowMarket = row.dataset.market || '';
    const rowStatus = row.dataset.status || '';
    const marketOk = !market || rowMarket === market;
    const statusOk = !status || rowStatus === status;
    row.style.display = (marketOk && statusOk) ? '' : 'none';
  });

  updateFilterCount(rows);
}

function updateFilterCount(rows) {
  const visible = Array.from(rows).filter(r => r.style.display !== 'none').length;
  const title = document.querySelector('.section-title');
  if (title) {
    let badge = title.querySelector('.badge-count');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'badge-count';
      title.appendChild(badge);
    }
    badge.textContent = visible;
  }
}

// ── Déclenchement manuel du pipeline ──────────────────────────────────

async function triggerMorning() {
  showToast('⏳ Pipeline matin en cours…', 'info');
  try {
    const resp = await fetch('/api/trigger/morning', { method: 'POST' });
    const data = await resp.json();
    if (resp.ok) {
      showToast('✅ Pipeline matin terminé !', 'success');
      setTimeout(() => window.location.reload(), 1500);
    } else {
      showToast('❌ Erreur pipeline matin', 'error');
    }
  } catch (e) {
    showToast('❌ Erreur réseau', 'error');
  }
}

async function triggerEvening() {
  showToast('⏳ Pipeline soir en cours…', 'info');
  try {
    const resp = await fetch('/api/trigger/evening', { method: 'POST' });
    if (resp.ok) {
      showToast('✅ Bilan calculé et envoyé !', 'success');
      setTimeout(() => window.location.reload(), 1500);
    }
  } catch (e) {
    showToast('❌ Erreur réseau', 'error');
  }
}

// ── Toast notifications ────────────────────────────────────────────────

function showToast(message, type = 'info') {
  const existing = document.getElementById('vbfc-toast');
  if (existing) existing.remove();

  const colors = {
    success: '#00c896',
    error: '#ff4d6d',
    info: '#3d7fff',
  };

  const toast = document.createElement('div');
  toast.id = 'vbfc-toast';
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    background: #1a1e2b; color: ${colors[type] || '#e8eaf0'};
    border: 1px solid ${colors[type] || '#252a3a'};
    padding: 12px 20px; border-radius: 8px;
    font-family: Inter, sans-serif; font-size: 13px; font-weight: 600;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    animation: slideIn 0.25s ease;
  `;

  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from { transform: translateY(20px); opacity: 0; }
      to   { transform: translateY(0);    opacity: 1; }
    }
  `;
  document.head.appendChild(style);
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ── Auto-refresh toutes les 5 minutes si paris pending ────────────────

document.addEventListener('DOMContentLoaded', () => {
  const hasPending = document.querySelectorAll('.bet-card').length > 0;
  if (hasPending) {
    setInterval(() => {
      fetch('/api/value-bets/today')
        .then(r => r.json())
        .then(data => {
          // Rechargement léger si nouveaux paris détectés
          const currentCount = document.querySelectorAll('.bet-card').length;
          if (data.length !== currentCount) {
            window.location.reload();
          }
        })
        .catch(() => {});
    }, 5 * 60 * 1000);
  }
});
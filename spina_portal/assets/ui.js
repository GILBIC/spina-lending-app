export const asArray = (value) => (Array.isArray(value) ? value : []);

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

export function formatMoney(value) {
  if (value == null || value === '') {
    return '—';
  }
  const amount = Number(String(value).replaceAll(',', ''));
  if (!Number.isFinite(amount)) {
    return escapeHtml(value);
  }
  return new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: 'PHP',
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatDate(value) {
  if (!value) {
    return '—';
  }
  const date = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return escapeHtml(value);
  }
  return new Intl.DateTimeFormat('en-PH', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}

export function formatDateTime(value) {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return escapeHtml(value);
  }
  return new Intl.DateTimeFormat('en-PH', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

export function titleCase(value) {
  return String(value ?? '')
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function statusTone(value) {
  const normalized = String(value ?? '').trim().toLowerCase();
  if (['active', 'approved', 'accepted', 'paid', 'received', 'resolved', 'posted', 'complete', 'completed'].includes(normalized)) {
    return 'success';
  }
  if (['pending', 'open', 'answered', 'review', 'waiting', 'partial', 'pass', 'advance'].includes(normalized)) {
    return 'warning';
  }
  if (['rejected', 'revoked', 'locked', 'inactive', 'voided', 'overdue', 'failed', 'blocked'].includes(normalized)) {
    return 'danger';
  }
  return 'info';
}

export function badge(value, tone = statusTone(value)) {
  return `<span class="badge ${escapeHtml(tone)}">${escapeHtml(titleCase(value || 'Unknown'))}</span>`;
}

export function metricCard(label, value, detail = '') {
  return `<article class="metric-card">
    <span class="metric-label">${escapeHtml(label)}</span>
    <strong class="metric-value">${value}</strong>
    ${detail ? `<span class="meta">${escapeHtml(detail)}</span>` : ''}
  </article>`;
}

export function detailItem(label, value) {
  return `<div class="detail-item"><span>${escapeHtml(label)}</span><strong>${value}</strong></div>`;
}

export function emptyState(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

export function errorCard(error, fallback = 'This section is temporarily unavailable.') {
  const message = error?.message || fallback;
  const code = error?.code && error.code !== 'request_failed' ? ` (${escapeHtml(error.code)})` : '';
  return `<div class="error-card"><strong>Could not load this section${code}.</strong><br>${escapeHtml(message)}</div>`;
}

export function loadingPanel(message = 'Loading authoritative SPINA records…') {
  return `<div class="loading-panel"><div><div class="spinner" aria-hidden="true"></div><strong>${escapeHtml(message)}</strong></div></div>`;
}

export function sessionPermissions(session) {
  return [...new Set([
    ...asArray(session?.permissions),
    ...asArray(session?.user?.permissions),
  ].map((permission) => String(permission).trim()).filter(Boolean))];
}

export function hasPermission(session, permission) {
  return sessionPermissions(session).includes(permission);
}

export async function settledRequest(api, path, options, fallback) {
  try {
    return { data: await api.request(path, options), error: null };
  } catch (error) {
    return { data: fallback, error };
  }
}

export function setButtonBusy(button, busy, busyText = 'Saving…') {
  if (!button) return;
  if (busy) {
    button.dataset.originalText = button.textContent;
    button.textContent = busyText;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
  }
}

export function showToast(message, type = 'info', duration = 5200) {
  const region = globalThis.document?.getElementById('status-region');
  if (!region) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = String(message ?? '');
  region.append(toast);
  globalThis.setTimeout?.(() => toast.remove(), duration);
}

export function navigationMarkup(items) {
  return asArray(items)
    .map(
      (item, index) => `<button class="nav-button${index === 0 ? ' active' : ''}" type="button" data-nav-target="${escapeHtml(item.id)}">
        <span>${escapeHtml(item.label)}</span>
        ${item.count != null ? `<span class="nav-count">${escapeHtml(item.count)}</span>` : ''}
      </button>`,
    )
    .join('');
}

export function bindNavigation(navRoot, contentRoot) {
  navRoot?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-nav-target]');
    if (!button) return;
    const target = contentRoot?.querySelector(`#${CSS.escape(button.dataset.navTarget)}`);
    if (!target) return;
    for (const item of navRoot.querySelectorAll('.nav-button')) {
      item.classList.toggle('active', item === button);
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

export function localBusinessDate(value = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Manila',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(value);
  const map = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${map.year}-${map.month}-${map.day}`;
}

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
  return formatExactMoney(value);
}

export function formatExactMoney(value, { minimumFractionDigits = 2 } = {}) {
  if (value == null || value === '') {
    return '—';
  }
  const match = String(value).trim().replaceAll(',', '').match(/^([+-]?)(\d+)(?:\.(\d+))?$/);
  if (!match) {
    return escapeHtml(value);
  }
  const [, sign, whole, fraction = ''] = match;
  const cents = fraction.padEnd(minimumFractionDigits, '0');
  return `${sign}₱${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${cents ? `.${cents}` : ''}`;
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
    timeZone: 'Asia/Manila',
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
  return `<div class="error-card"><strong>We couldn’t complete this request.</strong><br>${escapeHtml(message)}</div>`;
}

export function loadingPanel(message = 'Loading your records…') {
  return `<div class="loading-panel" role="status"><div><div class="spinner" aria-hidden="true"></div><strong>${escapeHtml(message)}</strong></div></div>`;
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
  let group;
  return asArray(items).map((item, index) => {
    const heading = item.group && item.group !== group
      ? `<p class="nav-group-label">${escapeHtml(item.group)}</p>` : '';
    group = item.group;
    return `${heading}<button class="nav-button${index === 0 ? ' active' : ''}" type="button" data-nav-target="${escapeHtml(item.id)}" data-nav-label="${escapeHtml(item.label)}"${index === 0 ? ' aria-current="page"' : ''}>
        <span>${escapeHtml(item.label)}</span>
        ${item.count != null ? `<span class="nav-count">${escapeHtml(item.count)}</span>` : ''}
      </button>`;
  }).join('');
}

export function bindNavigation(navRoot, contentRoot, { onNavigate = () => {} } = {}) {
  let selectedId = null;
  function activate(requestedId = selectedId, { focus = false } = {}) {
    const buttons = Array.from(navRoot?.querySelectorAll('[data-nav-target]') || []);
    const sections = Array.from(contentRoot?.querySelectorAll('[data-workspace-section]') || []);
    const available = buttons.filter(button => sections.some(section => section.getAttribute('id') === button.getAttribute('data-nav-target')));
    const selected = available.find(button => button.getAttribute('data-nav-target') === requestedId) || available[0];
    if (!selected) return false;
    selectedId = selected.getAttribute('data-nav-target');
    const target = sections.find(section => section.getAttribute('id') === selectedId);
    // Keep mounted forms and their unsaved values while showing one task at a time.
    for (const section of sections) section.hidden = section !== target;
    for (const button of buttons) {
      button.classList.toggle('active', button === selected);
      if (button === selected) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    }
    const label = selected.getAttribute('data-nav-label') || selected.textContent;
    if (label && !target.getAttribute('aria-label') && !target.getAttribute('aria-labelledby')) target.setAttribute('aria-label', label);
    // Collapse the phone menu before measuring the destination's scroll position.
    onNavigate({ id: selectedId, label, userInitiated: focus });
    if (focus) {
      target.setAttribute('tabindex', '-1');
      target.focus({ preventScroll: true });
      target.scrollIntoView({ behavior: 'auto', block: 'start' });
    }
    return true;
  }
  function navigate(event) {
    const button = event.target.closest?.('[data-nav-target]');
    if (!button) return;
    const id = button.getAttribute('data-nav-target');
    if (!Array.from(navRoot?.querySelectorAll('[data-nav-target]') || []).some(item => item.getAttribute('data-nav-target') === id)) return;
    event.preventDefault();
    activate(id, { focus: true });
  }
  navRoot?.addEventListener('click', navigate);
  contentRoot?.addEventListener('click', navigate);
  return { activate, reset: () => { selectedId = null; } };
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

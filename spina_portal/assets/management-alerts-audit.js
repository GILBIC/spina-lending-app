import { asArray, badge, emptyState, escapeHtml as h, formatDate, formatDateTime, formatMoney, titleCase } from './ui.js';

const DOMAIN_LABELS = new Map([
  ['payment_updates', 'Payment updates'], ['approvals', 'Approvals'],
  ['remittance_custody', 'Remittance & custody'], ['financial', 'Financial'],
]);
const DESTINATIONS = new Map([
  ['staff_devices', 'management-operations'], ['client_registrations', 'management-clients-loans'],
  ['renewals', 'management-clients-loans'], ['support', 'management-operations'],
  ['remittance_review', 'management-collections'], ['financial_accounting', 'management-accounting-hub'],
]);
const domainLabel = (domain) => DOMAIN_LABELS.get(domain) || titleCase(domain || 'Other');

export function managementAlertNavigationTarget(code) {
  return DESTINATIONS.get(code) ?? null;
}

function recordMarkup(item, { event = false } = {}) {
  const destination = managementAlertNavigationTarget(item.navigation_code);
  const tag = destination ? 'button' : 'article';
  const facts = event
    ? [item.reference, item.current_state ? titleCase(item.current_state) : '', item.source_label,
      item.actor_name ? `Maker: ${item.actor_name}` : '', item.checker_name ? `Checker: ${item.checker_name}` : '', item.reason]
    : [];
  return `<${tag} class="data-card management-audit-row" ${destination ? `type="button" data-nav-target="${destination}"` : ''}
    data-alert-domain="${h(item.domain || '')}" ${event ? `data-audit-event-key="${h(item.event_key || '')}"` : `data-alert-code="${h(item.code || '')}"`}>
    <strong>${h(item.title || (event ? 'Audit event' : 'Alert'))}</strong>
    <span class="meta">${h(domainLabel(item.domain))}${event ? ` · ${formatDateTime(item.occurred_at)}` : ''}</span>
    ${event ? facts.filter(Boolean).map((fact) => `<span>${h(fact)}</span>`).join('')
      : `<span>${h(item.count ?? '—')}${item.amount != null ? ` · ${formatMoney(item.amount)}` : ''}</span>`}
    ${event && item.business_date ? `<span class="meta">Business date ${formatDate(item.business_date)}</span>` : ''}
    ${badge(item.severity || 'info')}
  </${tag}>`;
}

export function managementAlertsAuditMarkup(snapshot = {}) {
  const domains = [...new Set(asArray(snapshot.visible_domains))];
  const alerts = asArray(snapshot.alerts);
  const events = asArray(snapshot.events);
  return `<div class="management-alerts-audit">
    <p>Review alerts and permanent audit history.</p>
    <p class="meta">${h(snapshot.event_total_count ?? events.length)} authorized events · Last ${h(snapshot.window_days ?? '—')} days · Updated ${formatDateTime(snapshot.generated_at)}${snapshot.limit != null ? ` · Up to ${h(snapshot.limit)} events shown` : ''}</p>
    <div class="inline-actions management-audit-filters" role="group" aria-label="Visible audit domains">
      <button type="button" class="button button-outline" data-alert-domain-filter="all" aria-pressed="true">All</button>
      ${domains.map((domain) => `<button type="button" class="button button-outline" data-alert-domain-filter="${h(domain)}" aria-pressed="false">${h(domainLabel(domain))}</button>`).join('')}
    </div>
    <div class="list-stack">${alerts.length ? alerts.map((item) => recordMarkup(item)).join('') : emptyState('No current alerts.')}</div>
    <h3>Permanent audit history</h3>
    <div class="list-stack">${events.length ? events.map((item) => recordMarkup(item, { event: true })).join('') : emptyState('No audit events in this snapshot.')}</div>
    ${snapshot.notice ? `<p class="meta">${h(snapshot.notice)}</p>` : ''}
  </div>`;
}

export function bindManagementAlertsAudit(root, { signal } = {}) {
  if (!root) return () => {};
  let disposed = false;
  const handlers = new Map();
  const buttons = Array.from(root.querySelectorAll('[data-alert-domain-filter]'));
  for (const button of buttons) {
    const handler = () => {
      if (disposed || signal?.aborted) return;
      const domain = button.getAttribute('data-alert-domain-filter');
      for (const item of root.querySelectorAll('[data-alert-domain]')) {
        if (domain === 'all' || item.getAttribute('data-alert-domain') === domain) item.removeAttribute('hidden');
        else item.setAttribute('hidden', '');
      }
      for (const chip of buttons) chip.setAttribute('aria-pressed', chip === button ? 'true' : 'false');
    };
    handlers.set(button, handler);
    button.addEventListener('click', handler);
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    for (const [button, handler] of handlers) button.removeEventListener('click', handler);
    signal?.removeEventListener('abort', dispose);
  }
  signal?.addEventListener('abort', dispose, { once: true });
  if (signal?.aborted) dispose();
  return dispose;
}

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
const TASKS = new Map([
  ['staff_devices','management-staff'],['client_registrations','management-client-accounts'],
  ['renewals','management-renewals'],['support','management-support'],
  ['remittance_review','management-remittances'],['financial_accounting','management-accounting'],
]);
const domainLabel = (domain) => DOMAIN_LABELS.get(domain) || titleCase(domain || 'Other');

export function managementAlertNavigationTarget(code) {
  return DESTINATIONS.get(code) ?? null;
}

function recordMarkup(item, { event = false } = {}) {
  const destination = managementAlertNavigationTarget(item.navigation_code);
  const tag = destination && !event ? 'button' : 'article';
  const facts = event
    ? [item.reference, item.current_state ? titleCase(item.current_state) : '', item.source_label,
      item.actor_name ? `Maker: ${item.actor_name}` : '', item.checker_name ? `Checker: ${item.checker_name}` : '', item.reason]
    : [];
  const navigation=destination?`data-nav-target="${destination}" data-management-destination="${h(TASKS.get(item.navigation_code))}"`:'';
  return `<${tag} class="data-card management-audit-row" ${tag==='button' ? `type="button" ${navigation}` : ''}
    data-alert-domain="${h(item.domain || '')}" ${event ? `data-audit-event-key="${h(item.event_key || '')}"` : `data-alert-code="${h(item.code || '')}"`}>
    <strong>${h(item.title || (event ? 'Audit event' : 'Alert'))}</strong>
    <span class="meta">${h(domainLabel(item.domain))}${event ? ` · ${formatDateTime(item.occurred_at)}` : ''}</span>
    ${event ? `<details><summary>Event details</summary>${facts.filter(Boolean).map((fact) => `<p>${h(fact)}</p>`).join('')}${destination?`<button class="button button-outline" type="button" ${navigation}>Open related queue</button>`:''}</details>`
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
    <p class="meta" data-audit-visible></p><button type="button" class="button button-outline" data-audit-more hidden>Show 10 more events</button>
    ${snapshot.notice ? `<p class="meta">${h(snapshot.notice)}</p>` : ''}
  </div>`;
}

export function bindManagementAlertsAudit(root, { signal, navigateTask } = {}) {
  if (!root) return () => {};
  let disposed = false;
  const handlers = new Map();
  const buttons = Array.from(root.querySelectorAll('[data-alert-domain-filter]'));
  let domain='all',cap=10;
  const more=root.querySelector('[data-audit-more]'),count=root.querySelector('[data-audit-visible]');
  function render() {
    let matched=0,shown=0,total=0;
    for(const item of root.querySelectorAll('[data-alert-domain]')) {
      const event=item.getAttribute('data-audit-event-key')!==null;
      const match=domain==='all'||item.getAttribute('data-alert-domain')===domain;
      if(event){total++;if(match)matched++;}
      if(match&&(!event||matched<=cap)){item.removeAttribute('hidden');if(event)shown++;}else item.setAttribute('hidden','');
    }
    if(count)count.textContent=`${shown} visible · ${matched} matching · ${total} loaded events`;
    if(more)more.hidden=matched<=cap;
  }
  for (const button of buttons) {
    const handler = () => {
      if (disposed || signal?.aborted) return;
      domain = button.getAttribute('data-alert-domain-filter');cap=10;render();
      for (const chip of buttons) chip.setAttribute('aria-pressed', chip === button ? 'true' : 'false');
    };
    handlers.set(button, handler);
    button.addEventListener('click', handler);
  }
  const reveal=()=>{if(disposed||signal?.aborted)return;cap+=10;render();};more?.addEventListener('click',reveal);if(more)handlers.set(more,reveal);
  if(navigateTask)for(const button of root.querySelectorAll('[data-management-destination]')){
    const navigate=event=>{event.stopPropagation();if(!disposed&&!signal?.aborted)navigateTask(button.getAttribute('data-nav-target'),button.getAttribute('data-management-destination'));};
    button.addEventListener('click',navigate);handlers.set(button,navigate);
  }
  render();
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

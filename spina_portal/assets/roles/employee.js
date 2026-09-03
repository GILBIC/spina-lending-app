import { buildEmployeeViewModel } from '../presenters.js';
import {
  asArray,
  badge,
  emptyState,
  errorCard,
  escapeHtml,
  formatDateTime,
  formatMoney,
  hasPermission,
  loadingPanel,
  metricCard,
  settledRequest,
  setButtonBusy,
  showToast,
} from '../ui.js';

function activityRows(items) {
  if (!items.length) return emptyState('No Employee update is available.');
  return `<div class="timeline">${items
    .slice(0, 50)
    .map(
      (item) => `<article class="timeline-item">
        <strong>${escapeHtml(item.title || item.notification_type || 'SPINA update')}</strong>
        <span>${escapeHtml(item.message || '')}</span>
        <span class="meta">${escapeHtml(item.sender_name || '')}${item.created_at ? ` · ${formatDateTime(item.created_at)}` : ''}</span>
      </article>`,
    )
    .join('')}</div>`;
}

function supportQueue(items) {
  if (!items.length) return emptyState('No open Client support request is assigned to this queue.');
  return `<div class="list-stack">${items
    .map(
      (request) => `<article class="list-item">
        <div class="section-heading">
          <div>
            <strong>${escapeHtml(request.client_name || request.client_code || 'Client')}</strong>
            <div class="meta">${escapeHtml(request.category || 'other')} · ${escapeHtml(request.subject || 'Support')}</div>
          </div>
          ${badge(request.status)}
        </div>
        <p>${escapeHtml(request.message || '')}</p>
        ${request.reference_text ? `<p class="meta">Reference: ${escapeHtml(request.reference_text)}</p>` : ''}
        ${request.management_response ? `<div class="notice-card"><strong>Current response:</strong> ${escapeHtml(request.management_response)}</div>` : ''}
        <form class="entry-form employee-support-review" data-request-id="${escapeHtml(request.request_id)}">
          <label>Action<select name="action"><option value="answered">Answer</option><option value="resolved">Resolve</option></select></label>
          <label>Response<textarea name="response" minlength="3" maxlength="2000" required></textarea></label>
          <button class="button button-primary" type="submit">Save response</button>
        </form>
      </article>`,
    )
    .join('')}</div>`;
}

function remittanceRows(items, canReceive) {
  if (!items.length) return emptyState('No remittance notification is waiting for this Employee.');
  return `<div class="list-stack">${items
    .map(
      (item) => `<article class="list-item">
        <div class="section-heading">
          <div>
            <strong>${escapeHtml(item.remittance_number || item.title || 'Remittance')}</strong>
            <div class="meta">From ${escapeHtml(item.collector_name || 'Collector')} · ${formatMoney(item.total_amount)}</div>
          </div>
          ${badge(item.status || (item.is_pending ? 'pending' : 'received'))}
        </div>
        <p>${escapeHtml(item.custody_message || item.message || '')}</p>
        <div class="detail-grid">
          <div class="detail-item"><span>Clients</span><strong>${escapeHtml(item.client_count ?? '—')}</strong></div>
          <div class="detail-item"><span>Transactions</span><strong>${escapeHtml(item.transaction_count ?? '—')}</strong></div>
          <div class="detail-item"><span>Collection date</span><strong>${escapeHtml(item.collection_date || '—')}</strong></div>
        </div>
        ${item.is_pending && canReceive ? `<button class="button button-secondary accept-remittance" type="button" data-notification-id="${escapeHtml(item.notification_id)}">Review complete — accept cash custody</button>` : ''}
      </article>`,
    )
    .join('')}</div>`;
}

function accountSection(account) {
  const profile = account.profile ?? {};
  const devices = asArray(account.devices);
  return `<div class="card-grid">
    <article class="data-card"><h3>Employee account</h3><div class="kv-list">
      <div class="kv-row"><span>Name</span><strong>${escapeHtml(profile.full_name || '—')}</strong></div>
      <div class="kv-row"><span>Username</span><strong>${escapeHtml(profile.username || '—')}</strong></div>
      <div class="kv-row"><span>Role</span><strong>${escapeHtml(profile.role || 'Employee')}</strong></div>
      <div class="kv-row"><span>Status</span>${badge(profile.status || 'unknown')}</div>
    </div></article>
    <article class="data-card"><h3>Devices</h3>${devices.length ? `<div class="list-stack">${devices.map((device) => `<div class="list-item"><strong>${escapeHtml(device.platform || 'Device')} ${device.is_current ? '· This device' : ''}</strong><span class="meta">Version ${escapeHtml(device.app_version || '—')} · ${formatDateTime(device.last_seen_at)}</span>${badge(device.status)}</div>`).join('')}</div>` : emptyState('No device record is available.')}</article>
  </div>`;
}

function bindActions(context) {
  for (const form of context.root.querySelectorAll('.employee-support-review')) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      setButtonBusy(button, true, 'Saving…');
      const data = new FormData(form);
      try {
        await context.api.request(`/api/v1/management/support/${encodeURIComponent(form.dataset.requestId)}/review`, {
          method: 'POST',
          body: {
            action: data.get('action'),
            response: String(data.get('response') || '').trim(),
          },
        });
        showToast('Client support response saved.', 'success');
        await mountEmployeeWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }

  for (const button of context.root.querySelectorAll('.accept-remittance')) {
    button.addEventListener('click', async () => {
      const confirmed = globalThis.confirm?.(
        'Confirm only after reviewing every included payment and physically receiving the cash. Continue?',
      );
      if (!confirmed) return;
      setButtonBusy(button, true, 'Accepting…');
      try {
        await context.api.request(
          `/api/v1/notifications/${encodeURIComponent(button.dataset.notificationId)}/accept-remittance`,
          { method: 'POST', body: { review_acknowledged: true }, financial: true },
        );
        showToast('Remittance accepted. Cash custody is now recorded under your account.', 'success');
        await mountEmployeeWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }
}

export async function mountEmployeeWorkspace(context) {
  const { root, api, session, setNavigation } = context;
  const canViewRemittance = hasPermission(session, 'remittance.view');
  const canReceiveRemittance = hasPermission(session, 'remittance.receive');
  const canManageSupport = hasPermission(session, 'support.manage');
  setNavigation([
    { id: 'employee-overview', label: 'My workday' },
    ...(canViewRemittance ? [{ id: 'employee-remittance', label: 'Remittance' }] : []),
    ...(canManageSupport ? [{ id: 'employee-support', label: 'Client support' }] : []),
    { id: 'employee-updates', label: 'Updates' },
    { id: 'employee-account', label: 'Account' },
  ]);
  root.innerHTML = loadingPanel('Loading permitted Employee work…');

  const [account, activity, remittances, support] = await Promise.all([
    settledRequest(api, '/api/v1/account', {}, {}),
    settledRequest(api, '/api/v1/activity-notifications', {}, []),
    canViewRemittance
      ? settledRequest(api, '/api/v1/notifications', {}, [])
      : Promise.resolve({ data: [], error: null }),
    canManageSupport
      ? settledRequest(api, '/api/v1/management/support?status=open', {}, { requests: [] })
      : Promise.resolve({ data: { requests: [] }, error: null }),
  ]);
  const model = buildEmployeeViewModel({
    session,
    account: account.data,
    notifications: activity.data,
    remittances: remittances.data,
    support: support.data,
  });

  root.innerHTML = `<header class="workspace-header" id="employee-overview">
    <div><p class="eyebrow">Employee workspace</p><h1>Hello, ${escapeHtml(model.displayName)}</h1><p>Your visible work comes from exact SPINA permissions. Collector collection and Management approval authority are never inherited by a generic Employee account.</p></div>
  </header>
  <section class="metric-grid">
    ${metricCard('Connected functions', escapeHtml(model.connectedActions.length))}
    ${metricCard('Open support', escapeHtml(model.openSupportCount))}
    ${metricCard('Remittance notices', escapeHtml(model.remittances.length))}
    ${metricCard('Account updates', escapeHtml(model.notifications.length))}
  </section>
  <section class="section-card">
    <div class="section-heading"><div><h2>Available today</h2><p>Only implemented functions allowed by your server session are active.</p></div></div>
    <div class="card-grid">${model.connectedActions.map((action) => `<article class="data-card"><h3>${escapeHtml(action.label)}</h3><p class="meta">${escapeHtml(action.section || 'Employee')}</p>${badge('available', 'success')}</article>`).join('')}</div>
  </section>
  <section class="section-card">
    <div class="section-heading"><div><h2>Not connected yet</h2><p>These items are visible for clarity but cannot create or change an official record.</p></div></div>
    <div class="card-grid">${model.unavailable.map((item) => `<article class="data-card"><h3>${escapeHtml(item.label)}</h3><p>${escapeHtml(item.message)}</p>${badge('unavailable', 'warning')}</article>`).join('')}</div>
  </section>
  ${canViewRemittance ? `<section class="section-card" id="employee-remittance"><div class="section-heading"><div><h2>Remittance custody</h2><p>Accept only after item review and physical cash receipt.</p></div></div>${remittances.error ? errorCard(remittances.error) : remittanceRows(model.remittances, canReceiveRemittance)}</section>` : ''}
  ${canManageSupport ? `<section class="section-card" id="employee-support"><div class="section-heading"><div><h2>Client support queue</h2><p>Responses do not change loans, balances, or receipts.</p></div></div>${support.error ? errorCard(support.error) : supportQueue(model.supportRequests)}</section>` : ''}
  <section class="section-card" id="employee-updates"><div class="section-heading"><div><h2>Updates</h2><p>Activity intended for this signed-in account.</p></div></div>${activity.error ? errorCard(activity.error) : activityRows(model.notifications)}</section>
  <section class="section-card" id="employee-account"><div class="section-heading"><div><h2>Account and devices</h2><p>Review your active SPINA identity and sessions.</p></div></div>${account.error ? errorCard(account.error) : accountSection(model.account)}</section>`;

  bindActions(context);
}

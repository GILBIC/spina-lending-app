import { mountAccountCredentials } from '../account-credentials.js';
import { mountRemittanceReview } from '../remittance-review.js';
import { mountAreaManagement } from '../area-management.js';
import { mountEmployeeOperations } from '../employee-operations.js';
import { buildEmployeeViewModel } from '../presenters.js';
import { mountOfficeCifSelection } from '../office-cif-selection.js';
import { mountOfficeApplicationReview } from '../office-application-review.js';
import { mountOfficeFirstLoan } from '../office-first-loan.js';
import { mountOfficeOnboarding } from '../office-onboarding.js';
import {
  asArray,
  badge,
  emptyState,
  errorCard,
  escapeHtml,
  formatDateTime,
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
}

export async function mountEmployeeWorkspace(context) {
  if (context.signal?.aborted) return;
  context.remittanceReviewCleanup?.();
  context.remittanceReviewCleanup = null;
  context.accountCredentialsCleanup?.();
  context.accountCredentialsCleanup = null;
  context.employeeOperationsCleanup?.();
  context.employeeOperationsCleanup = null;
  context.officeCifCleanup?.();
  context.officeCifCleanup = null;
  context.officeApplicationCleanup?.();
  context.officeApplicationCleanup = null;
  context.officeFirstLoanCleanup?.();
  context.officeFirstLoanCleanup = null;
  context.officeOnboardingCleanup?.();
  context.officeOnboardingCleanup = null;
  const { root, api, session, setNavigation } = context;
  const canReviewCif = hasPermission(session, 'client_onboarding.requirement.review');
  const canViewRemittance = hasPermission(session, 'remittance.view');
  const canManageSupport = hasPermission(session, 'support.manage');
  const canUseAreaManagement = [
    'area.manage',
    'area.collector.assign',
    'area.client.assign',
    'area.retire',
  ].some((permission) => hasPermission(session, permission));
  setNavigation([
    { id: 'employee-overview', label: 'Today', group: 'Daily work' },
    { id: 'employee-operations', label: 'My tasks & attendance', group: 'Daily work' },
    ...(canReviewCif ? [{ id: 'employee-onboarding', label: 'Office intake', group: 'Daily work' }, { id: 'employee-cif-review', label: 'CIF review', group: 'Daily work' }, { id: 'employee-application-review', label: 'Application review', group: 'Daily work' }, { id: 'employee-first-loan', label: 'First-loan work', group: 'Daily work' }] : []),
    ...(canViewRemittance ? [{ id: 'employee-remittance', label: 'Remittance notices', group: 'Daily work' }] : []),
    ...(canManageSupport ? [{ id: 'employee-support', label: 'Client support', group: 'Daily work' }] : []),
    { id: 'employee-updates', label: 'Updates', group: 'Records' },
    ...(canUseAreaManagement ? [{ id: 'employee-area-management', label: 'Area Management', group: 'Administration' }] : []),
    { id: 'employee-account', label: 'My account', group: 'Administration' },
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
  if (context.signal?.aborted) return;
  const model = buildEmployeeViewModel({
    session,
    account: account.data,
    notifications: activity.data,
    remittances: remittances.data,
    support: support.data,
  });

  const dailyLinks = [
    ['employee-operations', 'My tasks & attendance', 'Review assigned work and your time record.'],
    ...(canReviewCif ? [['employee-onboarding', 'Office intake', 'Check new client requirements.'], ['employee-cif-review', 'Review client information', 'Continue an intake review.'], ['employee-application-review', 'Review applications', 'Check submitted loan details.'], ['employee-first-loan', 'First-loan work', 'Complete authorized office steps.']] : []),
    ...(canViewRemittance ? [['employee-remittance', 'Review remittance', remittances.error ? 'Notices unavailable — refresh.' : `${model.remittances.length} notices`]] : []),
    ...(canManageSupport ? [['employee-support', 'Answer clients', support.error ? 'Queue unavailable — refresh.' : `${model.openSupportCount} open`]] : []),
  ];
  root.innerHTML = `<section class="section-card" id="employee-overview" data-workspace-section><header class="workspace-header">
    <div><p class="eyebrow">Employee</p><h1>Today's work</h1><p>Choose a task assigned to your account.</p></div>
  </header>
  ${support.error || remittances.error || activity.error ? '<div class="notice-card warning">Some work counts could not load. Open the task or refresh before deciding there is no pending work.</div>' : ''}
  <div class="section-heading"><div><h2>Open a task</h2><p>Only work allowed for your account appears here.</p></div></div>
  <div class="daily-actions">${dailyLinks.map(([target, label, detail]) => `<button class="task-link" type="button" data-nav-target="${target}"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(detail)}</span></button>`).join('')}</div>
  <section class="metric-grid">
    ${metricCard('Connected functions', escapeHtml(model.connectedActions.length))}
    ${metricCard('Open support', support.error ? 'Unavailable' : escapeHtml(model.openSupportCount))}
    ${metricCard('Remittance notices', remittances.error ? 'Unavailable' : escapeHtml(model.remittances.length))}
    ${metricCard('Account updates', activity.error ? 'Unavailable' : escapeHtml(model.notifications.length))}
  </section>
  </section>
  <section class="section-card" id="employee-operations" data-workspace-section><div data-employee-operations></div></section>
  ${canReviewCif ? '<section class="section-card" id="employee-onboarding" data-workspace-section><h2>Office intake and requirements</h2><div data-office-onboarding></div></section>' : ''}
  ${canReviewCif ? `<section class="section-card" id="employee-cif-review" data-workspace-section><div class="section-heading"><div><h2>CIF information review</h2><p>Find the office intake record to review the applicant's information.</p></div></div><div data-office-cif-selection></div></section>` : ''}
  ${canReviewCif ? '<section class="section-card" id="employee-application-review" data-workspace-section><div class="section-heading"><div><h2>Loan application review</h2><p>Open recorded request and repayment information using the office references.</p></div></div><div data-office-application-review></div></section>' : ''}
  ${canReviewCif ? '<section class="section-card" id="employee-first-loan" data-workspace-section><h2>First-loan approval and office release</h2><div data-office-first-loan></div></section>' : ''}
  ${canUseAreaManagement ? '<section class="section-card" id="employee-area-management" data-workspace-section></section>' : ''}
  ${canViewRemittance ? `<section class="section-card" id="employee-remittance" data-workspace-section><div class="section-heading"><div><h2>Remittance custody</h2><p>Accept only after item review and physical cash receipt.</p></div></div>${remittances.error ? errorCard(remittances.error) : '<div data-remittance-review></div>'}</section>` : ''}
  ${canManageSupport ? `<section class="section-card" id="employee-support" data-workspace-section><div class="section-heading"><div><h2>Client support queue</h2><p>Responses do not change loans, balances, or receipts.</p></div></div>${support.error ? errorCard(support.error) : supportQueue(model.supportRequests)}</section>` : ''}
  <section class="section-card" id="employee-updates" data-workspace-section><div class="section-heading"><div><h2>Updates</h2><p>Activity intended for this signed-in account.</p></div></div>${activity.error ? errorCard(activity.error) : activityRows(model.notifications)}</section>
  <section class="section-card" id="employee-account" data-workspace-section><div class="section-heading"><div><h2>Account and devices</h2><p>Review your active SPINA identity and sessions.</p></div></div>${account.error ? errorCard(account.error) : accountSection(model.account)}<div data-account-credentials></div></section>`;

  context.activateNavigation?.();
  context.remittanceReviewCleanup = mountRemittanceReview({
    root: root.querySelector('[data-remittance-review]'), api, session, notifications: model.remittances, signal: context.signal,
  });
  context.accountCredentialsCleanup = mountAccountCredentials({
    root: root.querySelector('[data-account-credentials]'), api, session, signal: context.signal,
  });
  context.employeeOperationsCleanup = mountEmployeeOperations({
    root: root.querySelector('[data-employee-operations]'), api, session, signal: context.signal,
  });
  if (canReviewCif) {
    context.officeFirstLoanCleanup = mountOfficeFirstLoan({
      root: root.querySelector('[data-office-first-loan]'), api, session, signal: context.signal,
    });
    context.officeOnboardingCleanup = mountOfficeOnboarding({
      root: root.querySelector('[data-office-onboarding]'), api, session, signal: context.signal,
    });
    context.officeCifCleanup = mountOfficeCifSelection({
      root: root.querySelector('[data-office-cif-selection]'), api, session, signal: context.signal,
    });
    context.officeApplicationCleanup = mountOfficeApplicationReview({
      root: root.querySelector('[data-office-application-review]'), api, session, signal: context.signal,
    });
  }
  bindActions(context);
  if (canUseAreaManagement) {
    const areaRoot = root.querySelector('#employee-area-management');
    if (areaRoot) await mountAreaManagement({ ...context, root: areaRoot });
  }
}

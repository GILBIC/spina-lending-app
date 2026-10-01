import { mountManagementCollectionActions } from '../management-collection-actions.js';
import { mountManagementJournalActions } from '../management-journal-actions.js';
import { mountManagementAccounting } from '../management-accounting.js';
import { mountAccountCredentials } from '../account-credentials.js';
import { mountAreaManagement } from '../area-management.js';
import { buildManagementViewModel } from '../presenters.js';
import { mountOfficeCifSelection } from '../office-cif-selection.js';
import { mountOfficeApplicationReview } from '../office-application-review.js';
import { mountOfficeFirstLoan } from '../office-first-loan.js';
import { mountOfficeOnboarding } from '../office-onboarding.js';
import { mountPaymentProofs } from '../payment-proofs.js';
import { mountEmployeeOperations } from '../employee-operations.js';
import {
  bindClientAccountAdmin,
  clientAccountAdminMarkup,
} from '../client-account-admin.js';
import { staffInviteMarkup, submitStaffInvitation } from '../staff-invite.js';
import {
  changeManagedDeviceStatus,
  deviceAction,
  loadManagedDevices,
  renderManagedDevicePanel,
} from '../management-devices.js';
import {
  financialStatementsMarkup,
  loadManagementFinancialStatements,
} from '../management-financial-statements.js';
import {
  bindManagementAccountingExport,
  loadManagementGeneralJournal,
  loadManagementTrialBalance,
  managementGeneralJournalMarkup,
} from '../management-general-journal.js';
import {
  bindManagementLoanOperations,
  loadManagementLoanOperations,
  managementLoanOperationsMarkup,
} from '../management-loan-operations.js';
import {
  bindManagementPastDueReport,
  loadManagementPastDueReport,
  managementPastDueReportMarkup,
} from '../management-past-due-report.js';
import {
  asArray,
  badge,
  emptyState,
  errorCard,
  escapeHtml,
  formatDate,
  formatDateTime,
  formatMoney,
  hasPermission,
  loadingPanel,
  metricCard,
  settledRequest,
  setButtonBusy,
  showToast,
  titleCase,
} from '../ui.js';

const MANAGEMENT_METRIC_PRESENTATION = Object.freeze({
  'portfolio.active_clients': { label: 'Active clients', group: 'portfolio' },
  'portfolio.active_loans': { label: 'Active loans', group: 'portfolio' },
  'portfolio.overdue_loans': { label: 'Overdue loans', group: 'attention' },
  'portfolio.outstanding_balance': { label: 'Outstanding balance', group: 'portfolio' },
  'collections.latest_day': { label: 'Latest collections', group: 'collections', countNoun: 'payment' },
  'collections.unremitted': { label: 'Unremitted collections', group: 'collections', countNoun: 'collection' },
  'queues.remittances_assigned': { label: 'Assigned remittances', group: 'collections', countNoun: 'remittance' },
  'queues.renewals_protected': { label: 'Renewal requests', group: 'attention' },
  'queues.staff_registrations': { label: 'Staff registrations', group: 'attention' },
  'queues.client_registrations': { label: 'Client registrations', group: 'attention' },
  'queues.collector_mobile_devices': { label: 'Collector devices', group: 'attention' },
  'queues.borrower_support': { label: 'Client support', group: 'attention' },
  'activity.unread': { label: 'Unread updates', group: 'attention' },
});

const MANAGEMENT_METRIC_GROUPS = Object.freeze([
  ['portfolio', 'Portfolio'],
  ['collections', 'Collections'],
  ['attention', 'Needs attention'],
]);

function pluralizedCount(metric, noun) {
  if (metric.count == null || !noun) return '';
  const count = Number(metric.count);
  return `${escapeHtml(metric.count)} ${escapeHtml(noun)}${count === 1 ? '' : 's'}`;
}

function managementMetricCard(metric) {
  const presentation = MANAGEMENT_METRIC_PRESENTATION[metric.key];
  if (!presentation) return '';
  const value = metric.amount != null
    ? formatMoney(metric.amount)
    : metric.count != null
      ? escapeHtml(metric.count)
      : '—';
  const details = [];
  const countDetail = metric.amount != null ? pluralizedCount(metric, presentation.countNoun) : '';
  if (countDetail) details.push(countDetail);
  if (metric.as_of_date) details.push(formatDate(metric.as_of_date));
  return `<article class="metric-card management-metric-card">
    <span class="metric-label">${escapeHtml(presentation.label)}</span>
    <strong class="metric-value">${value}</strong>
    ${details.length ? `<span class="meta">${details.join(' · ')}</span>` : ''}
  </article>`;
}

function overviewMetrics(metrics) {
  const known = asArray(metrics).filter((metric) => MANAGEMENT_METRIC_PRESENTATION[metric?.key]);
  if (!known.length) return emptyState('No Management metric is currently available.');
  return MANAGEMENT_METRIC_GROUPS.map(([group, title]) => {
    const cards = known
      .filter((metric) => MANAGEMENT_METRIC_PRESENTATION[metric.key].group === group)
      .map(managementMetricCard)
      .join('');
    if (!cards) return '';
    return `<section class="management-overview-group" data-management-metric-group="${group}">
      <div class="section-heading"><div><h2>${escapeHtml(title)}</h2></div></div>
      <div class="metric-grid">${cards}</div>
    </section>`;
  }).join('');
}

function loanTable(data) {
  const loans = asArray(data.loans);
  if (!loans.length) return emptyState('No loan matches the current search.');
  return `<div class="table-wrap"><table class="mobile-card-table management-loan-table">
    <thead><tr><th>Client</th><th>Loan</th><th>Type</th><th>Principal</th><th>Official balance</th><th>Daily</th><th>Due</th><th>Status</th></tr></thead>
    <tbody>${loans.map((loan) => `<tr>
      <td data-label="Client"><strong>${escapeHtml(loan.client_name || 'Client')}</strong><br><span class="meta">${escapeHtml(loan.client_code || '')} · ${escapeHtml(loan.client_area || '')}</span></td>
      <td data-label="Loan">${escapeHtml(loan.loan_number || '—')}</td>
      <td data-label="Type">${escapeHtml(loan.loan_type_name || '—')}</td>
      <td data-label="Principal">${formatMoney(loan.principal)}</td>
      <td data-label="Official balance">${formatMoney(loan.remaining_balance)}</td>
      <td data-label="Daily">${formatMoney(loan.daily_amount)}</td>
      <td data-label="Due">${formatDate(loan.due_date)}</td>
      <td data-label="Status">${badge(loan.loan_status || 'unknown')}${loan.is_overdue ? '<br><span class="badge danger">Overdue</span>' : ''}</td>
    </tr>`).join('')}</tbody>
  </table></div>`;
}

function bindManagementOfficeWorkflow(root) {
  const workflow = root.querySelector('[data-office-workflow]');
  if (!workflow) return () => {};

  const buttons = Array.from(workflow.querySelectorAll('[data-office-step-target]'));
  const panels = Array.from(workflow.querySelectorAll('[data-office-step]'));
  const panelByStep = new Map(
    panels.map((panel) => [panel.getAttribute('data-office-step'), panel]),
  );

  const read = (step, name) => {
    const control = panelByStep.get(step)?.querySelector(`[name="${name}"]`);
    return String(control?.value || '').trim();
  };
  const writeIfEmpty = (step, name, value) => {
    if (!value) return;
    const control = panelByStep.get(step)?.querySelector(`[name="${name}"]`);
    if (control && !String(control.value || '').trim()) control.value = value;
  };
  const currentReferences = () => ({
    intake:
      read('intake', 'applicationReference')
      || read('cif', 'applicationReference')
      || read('application', 'intakeReference')
      || read('first-loan', 'intakeReference'),
    application:
      read('application', 'applicationReference')
      || read('first-loan', 'applicationReference'),
  });

  function activate(step) {
    if (!panelByStep.has(step)) return;
    const references = currentReferences();
    if (step === 'cif') {
      writeIfEmpty('cif', 'applicationReference', references.intake);
    } else if (step === 'application') {
      writeIfEmpty('application', 'intakeReference', references.intake);
    } else if (step === 'first-loan') {
      writeIfEmpty('first-loan', 'intakeReference', references.intake);
      writeIfEmpty('first-loan', 'applicationReference', references.application);
    }

    for (const panel of panels) {
      if (panel.getAttribute('data-office-step') === step) panel.removeAttribute('hidden');
      else panel.setAttribute('hidden', '');
    }
    for (const button of buttons) {
      if (button.getAttribute('data-office-step-target') === step) {
        button.setAttribute('aria-current', 'step');
      } else {
        button.removeAttribute('aria-current');
      }
    }
  }

  const removers = buttons.map((button) => {
    const handler = () => activate(button.getAttribute('data-office-step-target'));
    button.addEventListener('click', handler);
    return () => button.removeEventListener('click', handler);
  });

  activate('intake');
  return () => removers.forEach((remove) => remove());
}

function alertsMarkup(alerts, events) {
  const alertCards = alerts.length
    ? `<div class="card-grid">${alerts.map((alert) => `<article class="data-card"><div class="section-heading"><div><h3>${escapeHtml(alert.title || titleCase(alert.code))}</h3><p>${escapeHtml(alert.domain || '')}</p></div>${badge(alert.severity || 'info')}</div><strong class="metric-value">${escapeHtml(alert.count ?? 0)}</strong>${alert.amount != null ? `<p>${formatMoney(alert.amount)}</p>` : ''}</article>`).join('')}</div>`
    : emptyState('No actionable alert is visible under the current permissions.');
  const eventList = events.length
    ? `<div class="timeline">${events.slice(0, 60).map((event) => `<article class="timeline-item"><strong>${escapeHtml(event.title || event.action_code || 'Activity')}</strong><span>${escapeHtml(event.reference || event.current_state || '')}</span><span class="meta">${escapeHtml(event.actor_name || '')}${event.occurred_at ? ` · ${formatDateTime(event.occurred_at)}` : ''}</span>${event.reason ? `<span>${escapeHtml(event.reason)}</span>` : ''}</article>`).join('')}</div>`
    : emptyState('No recent allowlisted audit event is available.');
  return `${alertCards}<div class="section-heading" style="margin-top:1rem"><div><h2>Recent audit activity</h2></div></div>${eventList}`;
}

function renewalQueue(items) {
  if (!items.length) return emptyState('No pending renewal request requires review.');
  return `<div class="list-stack">${items.map((request) => `<article class="list-item"><div class="section-heading"><div><strong>${escapeHtml(request.client_name || 'Client')}</strong><div class="meta">${escapeHtml(request.loan_number || 'Loan')} · ${escapeHtml(request.loan_type_name || '')}</div></div>${badge(request.status)}</div><div class="detail-grid"><div class="detail-item"><span>Current principal</span><strong>${formatMoney(request.current_principal)}</strong></div><div class="detail-item"><span>Remaining</span><strong>${formatMoney(request.remaining_balance)}</strong></div><div class="detail-item"><span>Requested</span><strong>${formatMoney(request.requested_amount)}</strong></div></div>${request.client_message ? `<p>${escapeHtml(request.client_message)}</p>` : ''}<form class="entry-form management-renewal-review" data-request-id="${escapeHtml(request.request_id)}"><label>Decision<select name="decision"><option value="approved">Approve request</option><option value="rejected">Reject request</option></select></label><label>Review note<textarea name="reviewNote" maxlength="1000" placeholder="Required when rejecting"></textarea></label><button class="button button-primary" type="submit">Confirm review</button></form></article>`).join('')}</div>`;
}

function supportQueue(items) {
  if (!items.length) return emptyState('No open support request requires review.');
  return `<div class="list-stack">${items.map((request) => `<article class="list-item"><div class="section-heading"><div><strong>${escapeHtml(request.client_name || 'Client')}</strong><div class="meta">${escapeHtml(request.category || 'other')} · ${escapeHtml(request.subject || 'Support')}</div></div>${badge(request.status)}</div><p>${escapeHtml(request.message || '')}</p>${request.reference_text ? `<p class="meta">Reference: ${escapeHtml(request.reference_text)}</p>` : ''}<form class="entry-form management-support-review" data-request-id="${escapeHtml(request.request_id)}"><label>Action<select name="action"><option value="answered">Answer</option><option value="resolved">Resolve</option></select></label><label>Response<textarea name="response" minlength="3" maxlength="2000" required></textarea></label><button class="button button-primary" type="submit">Save response</button></form></article>`).join('')}</div>`;
}

function staffRows(accounts, canManageDevices) {
  if (!accounts.length) return emptyState('No staff account is visible under the current filters.');
  const actionLabel = canManageDevices ? 'Manage phones' : 'View';
  return `<div class="table-wrap"><table><thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Status</th><th>Devices</th><th>Updated</th><th>Action</th></tr></thead><tbody>${accounts.map((account) => `<tr><td><strong>${escapeHtml(account.full_name || '—')}</strong><br><span class="meta">${escapeHtml(account.email || '')}</span></td><td>${escapeHtml(account.username || '—')}</td><td>${escapeHtml(asArray(account.roles).join(', ') || '—')}</td><td>${badge(account.status)}</td><td>${escapeHtml(account.device_count ?? 0)}</td><td>${formatDateTime(account.updated_at)}</td><td><button class="button button-outline button-small" type="button" data-manage-staff-id="${escapeHtml(account.id || '')}">${actionLabel}</button></td></tr>`).join('')}</tbody></table></div>`;
}

function accountCard(account) {
  const profile = account.profile ?? {};
  return `<div class="data-card"><div class="kv-list"><div class="kv-row"><span>Name</span><strong>${escapeHtml(profile.full_name || '—')}</strong></div><div class="kv-row"><span>Username</span><strong>${escapeHtml(profile.username || '—')}</strong></div><div class="kv-row"><span>Email</span><strong>${escapeHtml(profile.email || '—')}</strong></div><div class="kv-row"><span>Roles</span><strong>${escapeHtml(asArray(profile.roles).join(', ') || profile.role || 'Management')}</strong></div><div class="kv-row"><span>Status</span>${badge(profile.status || 'unknown')}</div></div></div>`;
}

function bindStaffInvite(context) {
  const form = context.root.querySelector('#management-staff-invite-form');
  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const button = form.querySelector('button[type="submit"]');
    setButtonBusy(button, true, 'Sending…');
    try {
      const result = await submitStaffInvitation(context.api, {
        fullName: data.get('fullName'),
        username: data.get('username'),
        email: data.get('email'),
        role: data.get('role'),
      });
      form.reset();
      const invited = result?.account?.full_name || result?.account?.username || 'staff member';
      showToast(`Invitation sent to ${invited}.`, 'success');
      await mountManagementWorkspace(context);
    } catch (error) {
      showToast(error.message, 'error');
      setButtonBusy(button, false);
    }
  });
}

function deviceConfirmation(account, device, action) {
  const roles = asArray(account.roles).map((role) => String(role).trim().toLowerCase());
  const platform = titleCase(device.platform || 'phone');
  const current = titleCase(device.status || 'unknown');
  const requested = titleCase(action.nextStatus);
  let consequence = 'The phone keeps its current server-authoritative access rules.';
  if (device.status === 'pending' && action.nextStatus === 'active' && roles.includes('collector')) {
    consequence = 'Approving this phone may revoke another active Collector phone for this account.';
  } else if (device.status === 'pending' && action.nextStatus === 'active') {
    consequence = 'Approving this phone allows protected SPINA access for this account.';
  } else if (device.status === 'active' && action.nextStatus === 'revoked') {
    consequence = 'Revoking this phone blocks future protected requests from this device.';
  } else if (device.status === 'revoked' && action.nextStatus === 'active') {
    consequence = 'Restoring this phone allows protected requests again.';
  }
  return `${action.label} for ${account.full_name || account.username || 'this staff account'}?\n\nPhone: ${platform}\nCurrent: ${current}\nRequested: ${requested}\n\n${consequence}`;
}

function bindManagedDeviceActions(context, account, devices) {
  const detail = context.root.querySelector('#management-staff-device-detail');
  if (!detail) return;
  for (const button of detail.querySelectorAll('.managed-device-action')) {
    button.addEventListener('click', async () => {
      const index = Number.parseInt(button.dataset.managedDeviceIndex || '', 10);
      const device = Number.isInteger(index) ? devices[index] : null;
      const action = device ? deviceAction(device.status) : null;
      if (!device || !action) {
        showToast('The registered phone state is stale. Open the staff record again.', 'error');
        return;
      }
      if (!globalThis.confirm?.(deviceConfirmation(account, device, action))) return;
      setButtonBusy(button, true, action.nextStatus === 'active' ? 'Saving…' : 'Revoking…');
      try {
        await changeManagedDeviceStatus(context.api, device.id, action.nextStatus);
        const refreshed = await loadManagedDevices(context.api, account.id);
        detail.innerHTML = renderManagedDevicePanel(account, refreshed, { canManageDevices: true });
        bindManagedDeviceActions(context, account, refreshed);
        showToast(
          action.nextStatus === 'revoked'
            ? 'Phone access revoked from the authoritative server record.'
            : device.status === 'pending'
              ? 'Phone approved from the authoritative server record.'
              : 'Phone access restored from the authoritative server record.',
          'success',
        );
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }
}

function bindStaffDevices(context, accounts) {
  const detail = context.root.querySelector('#management-staff-device-detail');
  if (!detail) return;
  const canManageDevices = hasPermission(context.session, 'device.manage');
  const accountById = new Map(
    accounts.map((account) => [String(account.id || ''), account]),
  );
  for (const button of context.root.querySelectorAll('[data-manage-staff-id]')) {
    button.addEventListener('click', async () => {
      const account = accountById.get(String(button.dataset.manageStaffId || ''));
      if (!account) {
        detail.innerHTML = emptyState('The selected staff record is no longer available. Refresh Management.');
        return;
      }
      if (!canManageDevices) {
        detail.innerHTML = renderManagedDevicePanel(account, [], { canManageDevices: false });
        detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      setButtonBusy(button, true, 'Loading…');
      detail.innerHTML = loadingPanel('Loading registered phones…');
      try {
        const devices = await loadManagedDevices(context.api, account.id);
        detail.innerHTML = renderManagedDevicePanel(account, devices, { canManageDevices: true });
        bindManagedDeviceActions(context, account, devices);
        detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (error) {
        detail.innerHTML = errorCard(error);
      } finally {
        setButtonBusy(button, false);
      }
    });
  }
}

function bindRenewals(context) {
  for (const form of context.root.querySelectorAll('.management-renewal-review')) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const decision = String(data.get('decision'));
      const reviewNote = String(data.get('reviewNote') || '').trim();
      if (decision === 'rejected' && reviewNote.length < 3) {
        showToast('Enter a clear rejection reason.', 'error');
        return;
      }
      if (!globalThis.confirm?.(`Confirm ${decision} for this renewal request?`)) return;
      const button = form.querySelector('button[type="submit"]');
      setButtonBusy(button, true, 'Saving…');
      try {
        await context.api.request(`/api/v1/management/renewals/${encodeURIComponent(form.dataset.requestId)}/review`, { method: 'POST', body: { decision, review_note: reviewNote } });
        showToast(`Renewal request ${decision}.`, 'success');
        await mountManagementWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }
}

function bindSupport(context) {
  for (const form of context.root.querySelectorAll('.management-support-review')) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const button = form.querySelector('button[type="submit"]');
      setButtonBusy(button, true, 'Saving…');
      try {
        await context.api.request(`/api/v1/management/support/${encodeURIComponent(form.dataset.requestId)}/review`, { method: 'POST', body: { action: data.get('action'), response: String(data.get('response') || '').trim() } });
        showToast('Support review saved.', 'success');
        await mountManagementWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }
}

function bindLoanSearch(context) {
  const form = context.root.querySelector('#management-loan-search');
  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const target = context.root.querySelector('#management-loan-results');
    const button = form.querySelector('button[type="submit"]');
    setButtonBusy(button, true, 'Searching…');
    target.innerHTML = '<div class="loading-panel"><div class="spinner"></div></div>';
    try {
      const loans = await context.api.request(`/api/v1/management/loans?q=${encodeURIComponent(String(data.get('query') || '').trim())}&status=${encodeURIComponent(String(data.get('status') || 'active'))}`);
      target.innerHTML = loanTable(loans);
    } catch (error) {
      target.innerHTML = errorCard(error);
    } finally {
      setButtonBusy(button, false);
    }
  });
}

export async function mountManagementWorkspace(context) {
  if (context.signal?.aborted) return;
  const journalEvidenceVersion = context.journalEvidenceVersion = (context.journalEvidenceVersion || 0) + 1;
  for (const key of ['collectionActionsCleanup', 'journalActionsCleanup', 'managementAccountingCleanup']) { context[key]?.(); context[key] = null; }
  context.accountCredentialsCleanup?.();
  context.accountCredentialsCleanup = null;
  context.accountingExportCleanup?.();
  context.accountingExportCleanup = null;
  context.employeeOperationsCleanup?.();
  context.employeeOperationsCleanup = null;
  context.paymentProofCleanup?.();
  context.paymentProofCleanup = null;
  context.officeCifCleanup?.();
  context.officeCifCleanup = null;
  context.officeApplicationCleanup?.();
  context.officeApplicationCleanup = null;
  context.officeFirstLoanCleanup?.();
  context.officeFirstLoanCleanup = null;
  context.officeOnboardingCleanup?.();
  context.officeOnboardingCleanup = null;
  context.officeWorkflowCleanup?.();
  context.officeWorkflowCleanup = null;
  const { root, api, session, setNavigation } = context;
  const canCollectionActions = ['collection.create', 'collection.void.unremitted', 'lending.no_collection.manage', 'lending.contract_collection.activate'].some(permission => hasPermission(session, permission));
  const canReviewCif = hasPermission(session, 'client_onboarding.requirement.review');
  const canDashboard = hasPermission(session, 'management.dashboard.view');
  const canViewFinancialStatements = hasPermission(session, 'accounting.view');
  const canViewGeneralJournal = canViewFinancialStatements;
  const canRenewals = hasPermission(session, 'renewal.manage');
  const canSupport = hasPermission(session, 'support.manage');
  const canReviewPaymentProof = hasPermission(session, 'client_payment_proof.review');
  const canManageAccounts = hasPermission(session, 'account.manage');
  const canManageDevices = hasPermission(session, 'device.manage');
  const canViewStaff = canManageAccounts || canManageDevices;
  const canUseAreaManagement = [
    'area.manage',
    'area.collector.assign',
    'area.client.assign',
    'area.retire',
  ].some((permission) => hasPermission(session, permission));
  setNavigation([
    { id: 'management-overview', label: 'Today' },
    { id: 'management-clients-loans', label: 'Clients & loans' },
    { id: 'management-collections', label: 'Collections' },
    { id: 'management-accounting-hub', label: 'Accounting' },
    { id: 'management-operations', label: 'People & operations' },
    { id: 'management-account', label: 'Account' },
  ]);
  root.innerHTML = loadingPanel('Loading server-authoritative Management priorities…');

  const [account, overview, loans, loanOperations, pastDueReport, financialStatements, generalJournal, trialBalance, alerts, renewals, support, staff] = await Promise.all([
    settledRequest(api, '/api/v1/account', {}, {}),
    canDashboard ? settledRequest(api, '/api/v1/management/dashboard-overview', {}, { metrics: [] }) : Promise.resolve({ data: { metrics: [] }, error: null }),
    settledRequest(api, '/api/v1/management/loans?status=active', {}, { summary: {}, loans: [] }),
    loadManagementLoanOperations(api)
      .then((data) => ({ data, error: null }))
      .catch((error) => ({ data: { summary: {}, entries: [], audits: [], notice: '' }, error })),
    canDashboard
      ? loadManagementPastDueReport(api)
          .then((data) => ({ data, error: null }))
          .catch((error) => ({ data: { schema_available: true, summary: {}, rows: [] }, error }))
      : Promise.resolve({ data: { schema_available: true, summary: {}, rows: [] }, error: null }),
    canViewFinancialStatements
      ? loadManagementFinancialStatements(api)
          .then((data) => ({ data, error: null }))
          .catch((error) => ({ data: { statements: null }, error }))
      : Promise.resolve({ data: { statements: null }, error: null }),
    canViewGeneralJournal
      ? loadManagementGeneralJournal(api)
          .then((data) => ({ data, error: null }))
          .catch((error) => ({ data: { entries: [], can_manage: false, automatic_loan_posting_enabled: false }, error }))
      : Promise.resolve({ data: { entries: [], can_manage: false, automatic_loan_posting_enabled: false }, error: null }),
    canViewGeneralJournal
      ? loadManagementTrialBalance(api)
          .then((data) => ({ data, error: null }))
          .catch((error) => ({ data: { trial_balance: null }, error }))
      : Promise.resolve({ data: { trial_balance: null }, error: null }),
    canDashboard ? settledRequest(api, '/api/v1/management/alerts-audit?window_days=30&limit=100', {}, { alerts: [], events: [] }) : Promise.resolve({ data: { alerts: [], events: [] }, error: null }),
    canRenewals ? settledRequest(api, '/api/v1/management/renewals?status=pending', {}, { requests: [] }) : Promise.resolve({ data: { requests: [] }, error: null }),
    canSupport ? settledRequest(api, '/api/v1/management/support?status=open', {}, { requests: [] }) : Promise.resolve({ data: { requests: [] }, error: null }),
    canViewStaff ? settledRequest(api, '/api/v1/management/accounts?staff_only=true', {}, { accounts: [] }) : Promise.resolve({ data: { accounts: [] }, error: null }),
  ]);
  if (context.signal?.aborted) return;
  const model = buildManagementViewModel({ account: account.data, overview: overview.data, loans: loans.data, alerts: alerts.data, renewals: renewals.data, support: support.data });
  const staffAccounts = asArray(staff.data.accounts);
  const dailyLinks = [
    ['management-clients-loans', 'Clients & loan decisions',
      canRenewals && !renewals.error ? String(model.pendingRenewals.length) + ' renewals waiting' : 'Review borrowers, applications, loans, and evidence.'],
    ['management-collections', 'Collections', 'Review collection activity, corrections, and past-due work.'],
    ['management-operations', 'People & operations',
      canSupport && !support.error ? String(model.openSupport.length) + ' client support requests open' : 'Manage staff, areas, employee work, and audit activity.'],
    ...(canViewFinancialStatements || canViewGeneralJournal
      ? [['management-accounting-hub', 'Accounting', 'Open accounting, statements, journals, and trial balance.']]
      : []),
  ];

  root.innerHTML = `<section class="section-card management-today" id="management-overview" data-workspace-section><header class="workspace-header"><div><p class="eyebrow">Management</p><h1>Today</h1><p>Today's portfolio, collections, and work requiring attention.</p></div>${model.generatedAt ? `<span class="meta">Updated ${formatDateTime(model.generatedAt)}</span>` : ''}</header>
  ${renewals.error || support.error ? '<div class="notice-card warning">Some work queues could not load. Open the task or refresh before deciding there is no pending work.</div>' : ''}
  ${canDashboard ? (overview.error ? errorCard(overview.error) : overviewMetrics(model.metrics)) : `<div class="notice-card warning">Your account does not have Management dashboard permission.</div>`}
  <div class="section-heading management-work-queues-heading"><div><h2>Work queues</h2><p>Open the area you need to work on.</p></div></div>
  ${dailyLinks.length ? `<div class="daily-actions">${dailyLinks.map(([target, label, detail]) => `<button class="task-link" type="button" data-nav-target="${target}"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(detail)}</span></button>`).join('')}</div>` : emptyState('No review queue is assigned to this account.')}
  </section>
  <section class="workspace-group" id="management-clients-loans" data-workspace-section>
    <header class="workspace-header workspace-group-header"><div><p class="eyebrow">Management</p><h1>Clients & loans</h1><p>Review borrowers, applications, loans, renewals, and payment evidence.</p></div></header>
  ${canReviewCif ? `<section class="section-card office-workflow-card" data-office-workflow>
    <div class="office-workflow-nav" role="group" aria-label="Office workflow">
      <button class="office-workflow-step" type="button" data-office-step-target="intake" aria-current="step">1. Office intake</button>
      <button class="office-workflow-step" type="button" data-office-step-target="cif">2. CIF review</button>
      <button class="office-workflow-step" type="button" data-office-step-target="application">3. Application review</button>
      <button class="office-workflow-step" type="button" data-office-step-target="first-loan">4. First loan</button>
    </div>
    <div data-office-step="intake">
      <section id="management-onboarding"><h2>Office intake and requirements</h2><div data-office-onboarding></div></section>
    </div>
    <div data-office-step="cif" hidden>
      <section id="management-cif-review"><div class="section-heading"><div><h2>CIF information review</h2><p>Continue the selected office intake. SPINA rechecks the reference before showing Client information.</p></div></div><div data-office-cif-selection></div></section>
    </div>
    <div data-office-step="application" hidden>
      <section id="management-application-review"><div class="section-heading"><div><h2>Loan application review</h2><p>Continue the selected Client and application. SPINA rechecks both references before loading saved details.</p></div></div><div data-office-application-review></div></section>
    </div>
    <div data-office-step="first-loan" hidden>
      <section id="management-first-loan"><h2>First-loan approval and office release</h2><p class="meta">Selected references are carried forward for convenience and revalidated by the protected first-loan workflow.</p><div data-office-first-loan></div></section>
    </div>
  </section>` : ''}
  <section class="section-card" id="management-loans"><div class="section-heading"><div><h2>Clients and loans</h2><p>Search the official portfolio. This view does not create or release loans.</p></div></div><form id="management-loan-search" class="search-bar"><input name="query" aria-label="Search clients and loans" placeholder="Client, code, area, or loan number" /><select name="status" aria-label="Loan status"><option value="active">Active</option><option value="paid">Paid</option><option value="all">All</option></select><button class="button button-primary" type="submit">Search</button></form><div class="metric-grid">${metricCard('Active loans', escapeHtml(model.loanSummary.active_loan_count ?? 0))}${metricCard('Active clients', escapeHtml(model.loanSummary.active_client_count ?? 0))}${metricCard('Remaining portfolio', formatMoney(model.loanSummary.active_remaining_total || 0))}${metricCard('Overdue active', escapeHtml(model.loanSummary.overdue_active_count ?? 0))}</div><div id="management-loan-results">${loans.error ? errorCard(loans.error) : loanTable(loans.data)}</div></section>
  ${canRenewals ? `<section class="section-card" id="management-renewals"><div class="section-heading"><div><h2>Renewal review</h2><p>Approval records the decision only; it does not itself release a new loan.</p></div></div>${renewals.error ? errorCard(renewals.error) : renewalQueue(model.pendingRenewals)}</section>` : ''}
  ${canReviewPaymentProof ? '<section class="section-card" id="management-payment-proofs"><h2>Payment evidence review</h2><div data-management-payment-proofs></div></section>' : ''}
  ${canManageAccounts ? `<section class="section-card" id="management-client-accounts"><div class="section-heading"><div><h2>Client accounts</h2><p>Select an existing borrower record, enter the borrower's email, and let SPINA generate the credentials.</p></div></div>${clientAccountAdminMarkup()}</section>` : ''}
  </section>
  <section class="workspace-group" id="management-collections" data-workspace-section>
    <header class="workspace-header workspace-group-header"><div><p class="eyebrow">Management</p><h1>Collections</h1><p>Monitor collections, protected corrections, and past-due reasons.</p></div></header>
  ${canCollectionActions ? '<section class="section-card" id="management-collection-actions"><div data-management-collection-actions></div></section>' : ''}
  <section class="section-card" id="management-loan-operations"><div class="section-heading"><div><h2>Loan operations</h2><p>Read-only monitoring of authoritative collections, remittances, corrections, and void history. Use the dedicated protected workflows for authorized changes.</p></div></div><form id="management-loan-operations-search" class="search-bar"><input name="q" aria-label="Search collection history" placeholder="Client, receipt, loan, or collector" /><select name="status" aria-label="Collection status"><option value="all">All entries</option><option value="unremitted">Unremitted</option><option value="submitted">Remittance submitted</option><option value="received">Received</option><option value="voided">Voided</option></select><button class="button button-primary" type="submit">Search</button></form><div id="management-loan-operations-results">${loanOperations.error ? errorCard(loanOperations.error) : managementLoanOperationsMarkup(loanOperations.data)}</div></section>
  ${canDashboard ? `<section class="section-card" id="management-past-due-report"><div class="section-heading"><div><h2>Past-due reasons</h2><p>Read-only server summary of Past-Due reasons. No penalty, balance, or schedule calculation is performed in Web.</p></div></div><form id="management-past-due-report-search" class="search-bar"><input type="date" name="start_date" aria-label="Start date" /><input type="date" name="end_date" aria-label="End date" /><input name="area" aria-label="Area" maxlength="200" placeholder="Area" /><select name="reason_code" aria-label="Past-due reason"><option value="">All reasons</option><option value="no_cash">No cash</option><option value="client_absent">Client absent</option><option value="business_slow">Business slow</option><option value="sick_hospital">Sick/Hospital</option><option value="emergency">Emergency</option><option value="promised_to_pay_later">Promised to pay later</option><option value="other">Other</option></select><select name="event_kind" aria-label="Past-due event"><option value="">All events</option><option value="unable_to_pay">Full Unable to Pay</option><option value="partial_payment">Partial-payment Past Due</option></select><button class="button button-primary" type="submit">Filter</button></form><div id="management-past-due-report-results">${pastDueReport.error ? errorCard(pastDueReport.error) : managementPastDueReportMarkup(pastDueReport.data)}</div></section>` : ''}
  </section>
  <section class="workspace-group" id="management-accounting-hub" data-workspace-section>
    <header class="workspace-header workspace-group-header"><div><p class="eyebrow">Management</p><h1>Accounting</h1><p>Review accounting records, statements, journals, and trial balance.</p></div></header>\n  ${!canViewFinancialStatements && !canViewGeneralJournal ? emptyState('No accounting tools are assigned to this account.') : ''}
  ${canViewFinancialStatements ? '<section class="section-card" id="management-accounting"><div data-management-accounting></div></section>' : ''}
  ${canViewFinancialStatements ? `<section class="section-card" id="management-financial-statements"><div class="section-heading"><div><h2>Financial statements</h2><p>Read-only posted General Ledger statements from the protected SPINA accounting service.</p></div></div>${financialStatements.error ? errorCard(financialStatements.error) : financialStatementsMarkup(financialStatements.data)}</section>` : ''}
  ${canViewGeneralJournal ? `<section class="section-card" id="management-general-journal"><div class="section-heading"><div><h2>General journal & trial balance</h2><p>Review accounting evidence and use the authorized journal actions below.</p></div></div>${generalJournal.error ? errorCard(generalJournal.error) : ''}${trialBalance.error ? errorCard(trialBalance.error) : ''}<div data-management-journal-evidence>${managementGeneralJournalMarkup({ journals: generalJournal.data, trialBalance: trialBalance.data })}</div><div data-management-journal-actions></div></section>` : ''}
  </section>
  <section class="workspace-group" id="management-operations" data-workspace-section>
    <header class="workspace-header workspace-group-header"><div><p class="eyebrow">Management</p><h1>People & operations</h1><p>Manage staff, areas, employee work, support, and audit activity.</p></div></header>
  ${canDashboard ? `<section class="section-card" id="management-alerts"><div class="section-heading"><div><h2>Alerts and audit</h2><p>Read-only allowlisted activity from owning Spina records.</p></div></div>${alerts.error ? errorCard(alerts.error) : alertsMarkup(model.alerts, model.recentEvents)}</section>` : ''}
  ${canUseAreaManagement ? '<section class="section-card" id="management-area-management"></section>' : ''}
  ${canViewStaff ? `<section class="section-card" id="management-staff"><div class="section-heading"><div><h2>Staff and devices</h2><p>Invite staff, inspect registered phones, and apply only server-authorized device changes.</p></div></div>${staffInviteMarkup(session)}${staff.error ? errorCard(staff.error) : staffRows(staffAccounts, canManageDevices)}<div id="management-staff-device-detail" class="section-card" style="margin-top:1rem">${emptyState('Select a staff account to review registered phones.')}</div></section>` : ''}
  <section class="section-card" id="management-employee-operations"><div data-employee-operations></div></section>
  ${canSupport ? `<section class="section-card" id="management-support"><div class="section-heading"><div><h2>Client support</h2><p>Answer concerns without changing financial records.</p></div></div>${support.error ? errorCard(support.error) : supportQueue(model.openSupport)}</section>` : ''}
  </section>
  <section class="section-card" id="management-account" data-workspace-section><div class="section-heading"><div><h2>My account</h2></div></div>${account.error ? errorCard(account.error) : accountCard(account.data)}<div data-account-credentials></div></section>`;

  context.activateNavigation?.();
  context.accountCredentialsCleanup = mountAccountCredentials({
    root: root.querySelector('[data-account-credentials]'), api, session, signal: context.signal,
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
    context.officeWorkflowCleanup = bindManagementOfficeWorkflow(root);
  }
  context.employeeOperationsCleanup = mountEmployeeOperations({
    root: root.querySelector('[data-employee-operations]'), api, session, signal: context.signal,
  });
  if (canReviewPaymentProof) {
    context.paymentProofCleanup = mountPaymentProofs({
      root: root.querySelector('[data-management-payment-proofs]'), api, mode: 'management', signal: context.signal,
    });
  }
  if (canCollectionActions) context.collectionActionsCleanup = mountManagementCollectionActions({root: root.querySelector('[data-management-collection-actions]'), api, session, sessionStore: context.sessionStore, signal: context.signal});
  if (canViewFinancialStatements) context.managementAccountingCleanup = await mountManagementAccounting({root: root.querySelector('[data-management-accounting]'), api, session, signal: context.signal});
  if (context.signal?.aborted) return;
  bindLoanSearch(context);
  bindManagementLoanOperations(context);
  bindManagementPastDueReport(context);
  if (canViewGeneralJournal) {
    context.accountingExportCleanup = bindManagementAccountingExport(context);
    context.journalActionsCleanup = mountManagementJournalActions({
      root: root.querySelector('[data-management-journal-actions]'), api, session, signal: context.signal,
      onSaved: async () => {
        const [journals, trialBalance] = await Promise.all([loadManagementGeneralJournal(api), loadManagementTrialBalance(api)]);
        if (context.signal?.aborted || context.journalEvidenceVersion !== journalEvidenceVersion) return;
        context.accountingExportCleanup?.();
        root.querySelector('[data-management-journal-evidence]').innerHTML = managementGeneralJournalMarkup({journals, trialBalance});
        context.accountingExportCleanup = bindManagementAccountingExport(context);
      },
    });
  }
  bindRenewals(context);
  bindSupport(context);
  bindClientAccountAdmin(context);
  bindStaffInvite(context);
  bindStaffDevices(context, staffAccounts);
  if (canUseAreaManagement) {
    const areaRoot = root.querySelector('#management-area-management');
    if (areaRoot) await mountAreaManagement({ ...context, root: areaRoot });
  }
}

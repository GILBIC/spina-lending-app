import {createManagementTaskController} from '../management-workspace-tasks.js';
import {mountManagementPortfolio} from '../management-portfolio.js';
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
import { mountCashDisbursement } from '../cash-disbursement.js';
import { bindManagementAlertsAudit, managementAlertsAuditMarkup } from '../management-alerts-audit.js';
import {
  bindClientAccountAdmin,
  clientAccountAdminMarkup,
} from '../client-account-admin.js';
import { staffInviteMarkup, submitStaffInvitation } from '../staff-invite.js';
import {
  bindManagedDevicePanel,
  changeManagedDeviceStatus,
  deviceAction,
  loadManagedDevices,
  renderManagedDevicePanel,
} from '../management-devices.js';
import {
  financialStatementsMarkup,
  loadManagementFinancialStatements,
  mountManagementFinancialStatements,
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

function renewalQueue(items) {
  if (!items.length) return '<p class="management-queue-empty" role="status" data-management-queue-empty="renewals">No renewal requests waiting.</p>';
  return `<div class="list-stack">${items.map((request) => `<article class="list-item"><div class="section-heading"><div><strong>${escapeHtml(request.client_name || 'Client')}</strong><div class="meta">${escapeHtml(request.loan_number || 'Loan')} · ${escapeHtml(request.loan_type_name || '')}</div></div>${badge(request.status)}</div><div class="detail-grid"><div class="detail-item"><span>Current principal</span><strong>${formatMoney(request.current_principal)}</strong></div><div class="detail-item"><span>Remaining</span><strong>${formatMoney(request.remaining_balance)}</strong></div><div class="detail-item"><span>Requested</span><strong>${formatMoney(request.requested_amount)}</strong></div></div>${request.client_message ? `<p>${escapeHtml(request.client_message)}</p>` : ''}<form class="entry-form management-renewal-review" data-request-id="${escapeHtml(request.request_id)}"><label>Decision<select name="decision"><option value="approved">Approve request</option><option value="rejected">Reject request</option></select></label><label>Review note<textarea name="reviewNote" maxlength="1000" placeholder="Required when rejecting"></textarea></label><button class="button button-primary" type="submit">Confirm review</button></form></article>`).join('')}</div>`;
}

function supportQueue(items) {
  if (!items.length) return '<p class="management-queue-empty" role="status" data-management-queue-empty="support">No open support requests.</p>';
  return `<div class="list-stack">${items.map((request) => `<article class="list-item"><div class="section-heading"><div><strong>${escapeHtml(request.client_name || 'Client')}</strong><div class="meta">${escapeHtml(request.category || 'other')} · ${escapeHtml(request.subject || 'Support')}</div></div>${badge(request.status)}</div><p>${escapeHtml(request.message || '')}</p>${request.reference_text ? `<p class="meta">Reference: ${escapeHtml(request.reference_text)}</p>` : ''}<form class="entry-form management-support-review" data-request-id="${escapeHtml(request.request_id)}"><label>Action<select name="action"><option value="answered">Answer</option><option value="resolved">Resolve</option></select></label><label>Response<textarea name="response" minlength="3" maxlength="2000" required></textarea></label><button class="button button-primary" type="submit">Save response</button></form></article>`).join('')}</div>`;
}

function staffRows(accounts, canManageDevices) {
  if (!accounts.length) return emptyState('No staff account is visible under the current filters.');
  const actionLabel = canManageDevices ? 'Manage devices' : 'View account';
  return `<div class="table-wrap"><table><thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Status</th><th>Devices</th><th>Account updated</th><th>Action</th></tr></thead><tbody>${accounts.map((account) => `<tr data-staff-row-id="${escapeHtml(account.id || '')}" aria-selected="false"><td><strong>${escapeHtml(account.full_name || '—')}</strong><br><span class="meta">${escapeHtml(account.email || '')}</span></td><td>${escapeHtml(account.username || '—')}</td><td>${escapeHtml(asArray(account.roles).map((role) => titleCase(String(role).trim().toLowerCase())).join(', ') || '—')}</td><td>${badge(account.status)}</td><td>${escapeHtml(account.device_count ?? 'Not reported')}</td><td>${formatDateTime(account.updated_at)}</td><td><button class="button button-outline button-small" type="button" data-manage-staff-id="${escapeHtml(account.id || '')}">${actionLabel}</button></td></tr>`).join('')}</tbody></table></div>`;
}

function accountCard(account) {
  const profile = account.profile ?? {};
  const roles = asArray(profile.roles)
    .map((role) => String(role).trim())
    .filter(Boolean);
  const additionalAccess = roles
    .filter((role) => role.toLowerCase() !== 'management')
    .map((role) => titleCase(String(role).toLowerCase()));
  return `<div class="data-card"><div class="kv-list"><div class="kv-row"><span>Name</span><strong>${escapeHtml(profile.full_name || '—')}</strong></div><div class="kv-row"><span>Username</span><strong>${escapeHtml(profile.username || '—')}</strong></div><div class="kv-row"><span>Email</span><strong>${escapeHtml(profile.email || '—')}</strong></div><div class="kv-row"><span>Workspace</span><strong>Management</strong></div>${additionalAccess.length ? `<div class="kv-row"><span>Additional access</span><strong>${escapeHtml(additionalAccess.join(', '))}</strong></div>` : ''}<div class="kv-row"><span>Status</span>${badge(profile.status || 'unknown')}</div></div></div>`;
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
  const platform = titleCase(device.platform || 'device');
  const current = titleCase(device.status || 'unknown');
  const requested = titleCase(action.nextStatus);
  const status = String(device.status || '').trim().toLowerCase();
  let consequence = 'The device keeps its current server-authoritative access rules.';
  if (status === 'pending' && action.nextStatus === 'active' && roles.includes('collector')) {
    consequence = 'Approving this device may revoke another active Collector device for this account.';
  } else if (status === 'pending' && action.nextStatus === 'active') {
    consequence = 'Approving this device allows protected SPINA access for this account.';
  } else if (status === 'active' && action.nextStatus === 'revoked') {
    consequence = 'Revoking this device blocks future protected requests from this device.';
  } else if (status === 'revoked' && action.nextStatus === 'active') {
    consequence = 'Restoring this device allows protected requests again.';
  }
  return `${action.label} for ${account.full_name || account.username || 'this staff account'}?\n\nDevice: ${platform}\nCurrent: ${current}\nRequested: ${requested}\n\n${consequence}`;
}

export function bindStaffDevices(context, accounts) {
  const detail = context.root.querySelector('#management-staff-device-detail');
  if (!detail) return () => {};
  const canManageDevices = hasPermission(context.session, 'device.manage');
  const accountById = new Map(accounts.map((account) => [String(account.id || ''), account]));
  const listeners = [];
  let panelCleanup = () => {};
  let selectionVersion = 0;
  let selectedId = '';
  let disposed = false;
  let busy = false;
  const active = (version) => !disposed && !context.signal?.aborted && version === selectionVersion;

  function select(id) {
    selectedId = id;
    for (const row of context.root.querySelectorAll('[data-staff-row-id]')) {
      row.setAttribute('aria-selected', String(row.getAttribute('data-staff-row-id') === id));
    }
  }

  function close() {
    selectionVersion += 1;
    panelCleanup();
    select('');
    detail.innerHTML = '';
    detail.setAttribute('hidden', '');
  }

  function showPanel(account, devices, version) {
    panelCleanup();
    detail.innerHTML = renderManagedDevicePanel(account, devices, { canManageDevices });
    const removeFilters = bindManagedDevicePanel(detail);
    const remove = [removeFilters];
    const on = (button, handler) => {
      button?.addEventListener('click', handler);
      remove.push(() => button?.removeEventListener('click', handler));
    };
    on(detail.querySelector('[data-managed-device-close]'), close);
    for (const button of detail.querySelectorAll('.managed-device-action')) {
      on(button, async () => {
        if (!active(version) || busy || !hasPermission(context.session, 'device.manage')) return;
        const index = Number(button.getAttribute('data-managed-device-index'));
        const device = Number.isInteger(index) ? devices[index] : null;
        const action = device ? deviceAction(device.status) : null;
        if (!device?.id || !action) return;
        if (!globalThis.confirm?.(deviceConfirmation(account, device, action))) return;
        busy = true;
        for (const control of detail.querySelectorAll('.managed-device-action')) control.disabled = true;
        try {
          await changeManagedDeviceStatus(context.api, device.id, action.nextStatus);
          const refreshed = await loadManagedDevices(context.api, account.id);
          if (!active(version)) return;
          showPanel(account, refreshed, version);
          showToast('Device access updated from the authoritative server record.', 'success');
        } catch (error) {
          if (!active(version)) return;
          panelCleanup();
          detail.innerHTML = `${errorCard(error)}<p class="meta">Open the staff account again to refresh its device records before another change.</p><button class="button button-quiet" type="button" data-managed-device-close>Close</button>`;
          const closeButton = detail.querySelector('[data-managed-device-close]');
          closeButton.addEventListener('click', close);
          panelCleanup = () => closeButton.removeEventListener('click', close);
        } finally {
          busy = false;
        }
      });
    }
    panelCleanup = () => { for (const cleanup of remove) cleanup(); };
  }

  for (const button of context.root.querySelectorAll('[data-manage-staff-id]')) {
    const open = async () => {
      if (disposed || context.signal?.aborted || busy) return;
      const account = accountById.get(String(button.getAttribute('data-manage-staff-id') || ''));
      const version = ++selectionVersion;
      panelCleanup();
      detail.removeAttribute('hidden');
      if (!account) {
        select('');
        detail.innerHTML = emptyState('The selected staff record is no longer available. Refresh Management.');
        return;
      }
      select(String(account.id));
      if (!canManageDevices) {
        showPanel(account, [], version);
        detail.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
        return;
      }
      detail.innerHTML = loadingPanel('Loading registered devices…');
      try {
        const devices = await loadManagedDevices(context.api, account.id);
        if (!active(version) || selectedId !== String(account.id)) return;
        showPanel(account, devices, version);
        detail.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
      } catch (error) {
        if (active(version)) detail.innerHTML = errorCard(error);
      }
    };
    button.addEventListener('click', open);
    listeners.push(() => button.removeEventListener('click', open));
  }
  function cleanup() {
    if (disposed) return;
    disposed = true;
    close();
    for (const remove of listeners) remove();
    context.signal?.removeEventListener('abort', cleanup);
  }
  context.signal?.addEventListener('abort', cleanup, { once: true });
  if (context.signal?.aborted) cleanup();
  return cleanup;
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

export async function mountManagementWorkspace(context) {
  if(context.signal?.aborted)return;
  context.managementTaskController?.dispose();
  context.accountingExportCleanup = null;
  const {root,api,session,setNavigation}=context;
  const getSession=context.getSession || (()=>context.signal?.aborted?null:context.session);
  const active=()=>!context.signal?.aborted && !!getSession();
  const can=permission=>hasPermission(getSession(),permission);
  const canCollectionActions=['collection.create','collection.void.unremitted','lending.no_collection.manage','lending.contract_collection.activate'].some(can);
  const canReviewCif=can('client_onboarding.requirement.review');
  const canDashboard=can('management.dashboard.view');
  const canViewFinancialStatements=can('accounting.view'),canViewGeneralJournal=canViewFinancialStatements;
  const canPrepareCashDisbursement=can('cash_disbursement.prepare');
  const canRenewals=can('renewal.manage'),canSupport=can('support.manage'),canReviewPaymentProof=can('client_payment_proof.review');
  const canManageAccounts=can('account.manage'),canManageDevices=can('device.manage'),canViewStaff=canManageAccounts||canManageDevices;
  const canReceiveRemittance=can('remittance.receive');
  const canUseAreaManagement=['area.manage','area.collector.assign','area.client.assign','area.retire'].some(can);
  const empty={data:{},error:null};
  const account=empty,overview=empty,loans=empty,loanOperations=empty,pastDueReport=empty,financialStatements=empty,generalJournal=empty,trialBalance=empty,alerts=empty,renewals=empty,support=empty,staff=empty;
  const model=buildManagementViewModel({account:{},overview:{},loans:{},alerts:{},renewals:{},support:{}});
  const staffAccounts=[];
  const dailyLinks=[['management-clients-loans','Clients & loan decisions','Review borrowers, applications, loans, and evidence.'],['management-collections','Collections','Review collection activity, corrections, and past-due work.'],['management-operations','People & operations','Manage staff, areas, employee work, and audit activity.'],...(canViewFinancialStatements||canPrepareCashDisbursement?[['management-accounting-hub','Accounting','Open statements, journals and accounting work.']]:[])];
  setNavigation([
    { id: 'management-overview', label: 'Today' },
    { id: 'management-clients-loans', label: 'Clients & loans' },
    { id: 'management-collections', label: 'Collections' },
    { id: 'management-accounting-hub', label: 'Accounting' },
    { id: 'management-operations', label: 'People & operations' },
    { id: 'management-account', label: 'Account' },
  ]);
  root.innerHTML = `<section class="section-card management-today" id="management-overview" data-workspace-section><header class="workspace-header"><div><p class="eyebrow">Management</p><h1>Today</h1><p>Today's portfolio, collections, and work requiring attention.</p></div>${model.generatedAt ? `<span class="meta">Updated ${formatDateTime(model.generatedAt)}</span>` : ''}</header>
  ${renewals.error || support.error ? '<div class="notice-card warning">Some work queues are unavailable. Open the task or refresh before deciding there is no pending work.</div>' : ''}
  <div data-management-overview>${loadingPanel('Loading current Management overview…')}</div>
  <div class="section-heading management-work-queues-heading"><div><h2>Work queues</h2><p>Open the area you need to work on.</p></div></div>
  ${dailyLinks.length ? `<div class="daily-actions">${dailyLinks.map(([target, label, detail]) => `<button class="task-link" type="button" data-nav-target="${target}"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(detail)}</span></button>`).join('')}</div>` : emptyState('No review queue is assigned to this account.')}
  </section>
  <section class="workspace-group" id="management-clients-loans" data-workspace-section>
    <header class="workspace-header workspace-group-header"><div><p class="eyebrow">Management</p><h1>Clients & loans</h1><p>Review borrowers, applications, loans, renewals, and payment evidence.</p></div></header><div data-management-task-navigation class="management-task-navigation" role="group" aria-label="Management tasks"></div>
  ${canReviewCif ? `<section class="section-card office-workflow-card" id="management-office" data-office-workflow>
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
  <section class="section-card" id="management-loans" data-screen-share-section><div data-management-portfolio></div></section>
  ${canRenewals ? `<section class="section-card" id="management-renewals"><div class="section-heading"><div><h2>Renewal review</h2><p>Review authoritative terms, borrower readiness and protected continuation.</p></div></div><div data-management-renewal-workflow></div></section>` : ''}
  ${canReviewPaymentProof ? '<section class="section-card" id="management-payment-proofs"><h2>Payment evidence review</h2><div data-management-payment-proofs></div></section>' : ''}
  ${canManageAccounts ? `<section class="section-card" id="management-client-accounts"><div class="section-heading"><div><h2>Client accounts</h2><p>Select an existing borrower record, enter the borrower's email, and let SPINA generate the credentials.</p></div></div>${clientAccountAdminMarkup()}</section>` : ''}
  </section>
  <section class="workspace-group" id="management-collections" data-workspace-section>
    <header class="workspace-header workspace-group-header"><div><p class="eyebrow">Management</p><h1>Collections</h1><p>Monitor collections, protected corrections, and past-due reasons.</p></div></header><div data-management-task-navigation class="management-task-navigation" role="group" aria-label="Management tasks"></div>
  ${canCollectionActions ? '<section class="section-card" id="management-collection-actions"><div data-management-collection-actions></div></section>' : ''}
  <section class="section-card" id="management-loan-operations" data-screen-share-section><div class="section-heading"><div><h2>Loan operations</h2><p>Read-only monitoring of authoritative collections, remittances, corrections, and void history. Use the dedicated protected workflows for authorized changes.</p></div></div><form id="management-loan-operations-search" class="search-bar"><input name="q" aria-label="Search collection history" placeholder="Client, receipt, loan, or collector" /><select name="status" aria-label="Collection status"><option value="all">All entries</option><option value="unremitted">Unremitted</option><option value="submitted">Remittance submitted</option><option value="received">Received</option><option value="voided">Voided</option></select><button class="button button-primary" type="submit">Search</button></form><div id="management-loan-operations-results">${loanOperations.error ? errorCard(loanOperations.error) : managementLoanOperationsMarkup(loanOperations.data)}</div></section>
  ${canDashboard ? `<section class="section-card" id="management-past-due-report"><div class="section-heading"><div><h2>Past-due reasons</h2><p>Review recorded past-due reasons and amounts by date, area, reason, or event.</p></div></div><form id="management-past-due-report-search" class="past-due-filter-grid"><label>Start date<input type="date" name="start_date" /></label><label>End date<input type="date" name="end_date" /></label><label>Area<input name="area" maxlength="200" placeholder="All areas" /></label><label>Reason<select name="reason_code"><option value="">All reasons</option><option value="no_cash">No cash</option><option value="client_absent">Client absent</option><option value="business_slow">Business slow</option><option value="sick_hospital">Sick/Hospital</option><option value="emergency">Emergency</option><option value="promised_to_pay_later">Promised to pay later</option><option value="other">Other</option></select></label><label>Event<select name="event_kind"><option value="">All events</option><option value="unable_to_pay">Unable to pay</option><option value="partial_payment">Partial payment</option></select></label><button class="button button-primary" type="submit">Filter</button></form><div id="management-past-due-report-results">${pastDueReport.error ? errorCard(pastDueReport.error) : managementPastDueReportMarkup(pastDueReport.data)}</div></section>` : ''}
  ${canReceiveRemittance ? '<section class="section-card" id="management-remittances"><div data-management-remittance-review></div></section>' : ''}</section>
  <section class="workspace-group" id="management-accounting-hub" data-workspace-section>
    <header class="workspace-header workspace-group-header"><div><p class="eyebrow">Management</p><h1>Accounting</h1><p>Review accounting records, statements, journals, and trial balance.</p></div></header><div data-management-task-navigation class="management-task-navigation" role="group" aria-label="Management tasks"></div>\n  ${!canViewFinancialStatements && !canViewGeneralJournal && !canPrepareCashDisbursement ? emptyState('No accounting tools are assigned to this account.') : ''}
  ${canPrepareCashDisbursement ? '<section class="section-card" id="management-cash-disbursement"><div data-cash-disbursement></div></section>' : ''}
  ${canViewFinancialStatements ? '<section class="section-card" id="management-accounting"><div data-management-accounting></div></section>' : ''}
  ${canViewFinancialStatements ? `<section class="section-card" id="management-financial-statements"><div class="section-heading"><div><h2>Financial statements</h2><p>Read-only posted General Ledger statements from the protected SPINA accounting service.</p></div></div>${financialStatements.error ? errorCard(financialStatements.error) : financialStatementsMarkup(financialStatements.data)}</section>` : ''}
  ${canViewGeneralJournal ? `<section class="section-card" id="management-general-journal"><div class="section-heading"><div><h2>General journal & trial balance</h2><p>Review accounting evidence and use the authorized journal actions below.</p></div></div>${generalJournal.error ? errorCard(generalJournal.error) : ''}${trialBalance.error ? errorCard(trialBalance.error) : ''}<div data-management-journal-evidence>${managementGeneralJournalMarkup({ journals: generalJournal.data, trialBalance: trialBalance.data })}</div><div data-management-journal-actions></div></section>` : ''}
  </section>
  <section class="workspace-group" id="management-operations" data-workspace-section>
    <header class="workspace-header workspace-group-header"><div><p class="eyebrow">Management</p><h1>People & operations</h1><p>Manage staff, areas, employee work, support, and audit activity.</p></div></header><div data-management-task-navigation class="management-task-navigation" role="group" aria-label="Management tasks"></div>
  ${canDashboard ? `<section class="section-card" id="management-alerts"><div class="section-heading"><div><h2>Alerts and audit</h2></div></div><div data-management-alerts-audit>${alerts.error ? errorCard(alerts.error) : managementAlertsAuditMarkup(alerts.data)}</div></section>` : ''}
  ${canUseAreaManagement ? '<section class="section-card" id="management-area-management"></section>' : ''}
  ${canViewStaff ? `<section class="section-card" id="management-staff"><div class="section-heading"><div><h2>Staff and devices</h2><p>Invite staff and manage registered devices.</p></div></div>${staffInviteMarkup(session)}<div data-management-staff-list></div><div id="management-staff-device-detail" class="section-card" hidden></div></section>` : ''}
  <section class="section-card" id="management-employee-operations"><div data-employee-operations></div></section>
  ${canSupport ? `<section class="section-card" id="management-support"><div class="section-heading"><div><h2>Client support</h2><p>Answer concerns without changing financial records.</p></div></div><div data-management-support-list></div></section>` : ''}
  </section>
  <section class="workspace-group" id="management-account" data-workspace-section><h1>Account</h1><div data-management-task-navigation class="management-task-navigation" role="group" aria-label="Account tasks"></div><section class="section-card" id="management-profile"><h2>My account</h2><div data-management-account-profile></div><div data-account-credentials></div></section><section class="section-card" id="management-updates"><h2>My updates</h2><div data-management-updates></div></section></section>`;


  const cleanups=[];
  let overviewVersion=0,accountVersion=0;
  async function refreshOverview(){
    if(!active())return;const version=++overviewVersion;const target=root.querySelector('[data-management-overview]');
    if(!target)return;
    if(!canDashboard){target.innerHTML='<p>Management dashboard permission is not assigned.</p>';return;}
    try{const data=await api.request('/api/v1/management/dashboard-overview');if(active()&&version===overviewVersion)target.innerHTML=`${data.generated_at ? `<p class="meta">Updated ${formatDateTime(data.generated_at)}</p>` : ''}${overviewMetrics(asArray(data.metrics))}`;}
    catch(error){if(active()&&version===overviewVersion){target.innerHTML=`${errorCard(error)}<button type="button" class="button button-outline" data-overview-retry>Retry overview</button>`;target.querySelector('[data-overview-retry]')?.addEventListener('click',()=>void refreshOverview(),{once:true});}}
  }
  async function refreshAccount(){
    const version=++accountVersion;const target=root.querySelector('[data-management-account-profile]');
    try{const data=await api.request('/api/v1/account');if(active()&&target&&version===accountVersion)target.innerHTML=accountCard(data);}
    catch(error){if(active()&&target&&version===accountVersion)target.innerHTML=errorCard(error);}
  }
  const tasks=[];
  const add=(id,group,label,mount,permission)=>{if(root.querySelector(`#${id}`))tasks.push({id,group,label,mount,allowed:()=>!permission||can(permission)});};
  const options=selector=>({root:root.querySelector(selector),api,session:getSession(),getSession,signal:context.signal});
  function readTask({load,render,target,bind}){
    let version=0,cleanup=()=>{};
    const refresh=async()=>{const request=++version;try{const data=await load();if(!active()||request!==version)return;cleanup();target.innerHTML=render(data);cleanup=bind?.(data)||(()=>{});}catch(error){if(active()&&request===version){cleanup();target.innerHTML=`${errorCard(error)}<button type="button" class="button button-outline" data-read-retry>Retry</button>`;target.querySelector('[data-read-retry]')?.addEventListener('click',()=>void refresh(),{once:true});}}};
    return {refresh,dispose(){version++;cleanup();}};
  }
  add('management-overview','management-overview','Today',()=>({refresh:()=>Promise.all([refreshOverview(),refreshAccount()])}));
  add('management-loans','management-clients-loans','Portfolio',async()=>{const h=mountManagementPortfolio({...options('[data-management-portfolio]')});await h.refresh();return h;});
  add('management-office','management-clients-loans','Office applications',()=>{
    const handlers=[mountOfficeFirstLoan(options('[data-office-first-loan]')),mountOfficeOnboarding(options('[data-office-onboarding]')),mountOfficeCifSelection(options('[data-office-cif-selection]')),mountOfficeApplicationReview(options('[data-office-application-review]')),bindManagementOfficeWorkflow(root)];
    return ()=>handlers.forEach(dispose=>dispose?.());
  },'client_onboarding.requirement.review');
  add('management-renewals','management-clients-loans','Renewals',async()=>{
    const target=root.querySelector('[data-management-renewal-workflow]');
    const h=readTask({target,load:()=>api.request('/api/v1/management/renewals?status=pending'),render:data=>renewalQueue(asArray(data.requests)),bind:()=>bindRenewals(context)});await h.refresh();return h;
  },'renewal.manage');
  add('management-payment-proofs','management-clients-loans','Payment evidence',()=>mountPaymentProofs({...options('[data-management-payment-proofs]'),mode:'management'}),'client_payment_proof.review');
  add('management-client-accounts','management-clients-loans','Client accounts',()=>bindClientAccountAdmin(context),'account.manage');
  add('management-collection-actions','management-collections','Collection actions',()=>mountManagementCollectionActions({...options('[data-management-collection-actions]'),sessionStore:context.sessionStore}));
  add('management-loan-operations','management-collections','Loan operations & history',async()=>{
    const h=readTask({target:root.querySelector('#management-loan-operations-results'),load:()=>loadManagementLoanOperations(api),render:managementLoanOperationsMarkup});bindManagementLoanOperations(context);await h.refresh();return h;
  });
  add('management-past-due-report','management-collections','Past-due report',async()=>{const h=readTask({target:root.querySelector('#management-past-due-report-results'),load:()=>loadManagementPastDueReport(api),render:managementPastDueReportMarkup});bindManagementPastDueReport(context);await h.refresh();return h;},'management.dashboard.view');
  add('management-financial-statements','management-accounting-hub','Financial statements',async()=>{const h=mountManagementFinancialStatements(options('#management-financial-statements'));await h.refresh();return h;},'accounting.view');
  add('management-general-journal','management-accounting-hub','Journal & Trial Balance',async()=>{
    const target=root.querySelector('[data-management-journal-evidence]');let actions=()=>{},exports=()=>{},version=0;
    const refresh=async()=>{const generation=++version;const [journals,trialBalance]=await Promise.all([loadManagementGeneralJournal(api),loadManagementTrialBalance(api)]);if(!active()||generation!==version)return;exports();target.innerHTML=managementGeneralJournalMarkup({journals,trialBalance});exports=bindManagementAccountingExport(context);context.accountingExportCleanup=exports;return journals;};
    const journals=await refresh();if(active())actions=mountManagementJournalActions({...options('[data-management-journal-actions]'),evidenceRoot:target,initialJournals:journals,onSaved:refresh});return{refresh,dispose(){version++;actions?.();exports?.();}};
  },'accounting.view');
  add('management-cash-disbursement','management-accounting-hub','Cash Disbursement',()=>mountCashDisbursement(options('[data-cash-disbursement]')),'cash_disbursement.prepare');
  add('management-accounting','management-accounting-hub','Accounting workflows',()=>mountManagementAccounting(options('[data-management-accounting]')),'accounting.view');
  add('management-staff','management-operations','Staff & devices',async()=>{
    const target=root.querySelector('[data-management-staff-list]');
    const h=readTask({target,load:()=>api.request('/api/v1/management/accounts?staff_only=true'),render:data=>staffRows(asArray(data.accounts),canManageDevices),bind:data=>bindStaffDevices(context,asArray(data.accounts))});
    context.refreshStaff=h.refresh;bindStaffInvite(context);await h.refresh();return h;
  });
  add('management-area-management','management-operations','Areas',()=>mountAreaManagement({...context,root:root.querySelector('#management-area-management')}));
  add('management-employee-operations','management-operations','Employee work',()=>mountEmployeeOperations(options('[data-employee-operations]')));
  add('management-support','management-operations','Client support',async()=>{
    const target=root.querySelector('[data-management-support-list]');
    const h=readTask({target,load:()=>api.request('/api/v1/management/support?status=open'),render:data=>supportQueue(asArray(data.requests)),bind:()=>bindSupport(context)});await h.refresh();return h;
  },'support.manage');
  add('management-alerts','management-operations','Alerts & audit',async()=>{const h=readTask({target:root.querySelector('[data-management-alerts-audit]'),load:()=>api.request('/api/v1/management/alerts-audit?window_days=30&limit=100'),render:managementAlertsAuditMarkup,bind:()=>bindManagementAlertsAudit(root.querySelector('[data-management-alerts-audit]'),{signal:context.signal})});await h.refresh();return h;},'management.dashboard.view');
  add('management-profile','management-account','Profile & security',()=>({refresh:refreshAccount,dispose:mountAccountCredentials(options('[data-account-credentials]'))}));
  for(const task of tasks)if(task.id!==task.group)root.querySelector(`#${task.id}`).hidden=true;
  const taskController=createManagementTaskController({root,signal:context.signal,getSession,tasks,beforeTaskChange:context.beforeTaskChange,afterTaskChange:context.afterTaskChange});
  context.managementTaskController=taskController;
  context.refreshOverview=refreshOverview;
  context.registerWorkspaceHandle?.(taskController);
  context.activateNavigation?.();
  void taskController.activate('management-overview');
  void refreshAccount();void refreshOverview();
  return taskController;
}

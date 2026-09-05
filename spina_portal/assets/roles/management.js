import { buildManagementViewModel } from '../presenters.js';
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

function metricValue(metric) {
  if (metric.amount != null) return formatMoney(metric.amount);
  if (metric.count != null) return escapeHtml(metric.count);
  return '—';
}

function overviewMetrics(metrics) {
  if (!metrics.length) return emptyState('No Management metric is currently available.');
  return `<div class="metric-grid">${metrics.map((metric) => metricCard(titleCase(metric.key), metricValue(metric), metric.as_of_date ? `As of ${formatDate(metric.as_of_date)}` : '')).join('')}</div>`;
}

function loanTable(data) {
  const loans = asArray(data.loans);
  if (!loans.length) return emptyState('No loan matches the current search.');
  return `<div class="table-wrap"><table>
    <thead><tr><th>Client</th><th>Loan</th><th>Type</th><th>Principal</th><th>Official balance</th><th>Daily</th><th>Due</th><th>Status</th></tr></thead>
    <tbody>${loans.map((loan) => `<tr>
      <td><strong>${escapeHtml(loan.client_name || 'Client')}</strong><br><span class="meta">${escapeHtml(loan.client_code || '')} · ${escapeHtml(loan.client_area || '')}</span></td>
      <td>${escapeHtml(loan.loan_number || '—')}</td>
      <td>${escapeHtml(loan.loan_type_name || '—')}</td>
      <td>${formatMoney(loan.principal)}</td>
      <td>${formatMoney(loan.remaining_balance)}</td>
      <td>${formatMoney(loan.daily_amount)}</td>
      <td>${formatDate(loan.due_date)}</td>
      <td>${badge(loan.loan_status || 'unknown')}${loan.is_overdue ? '<br><span class="badge danger">Overdue</span>' : ''}</td>
    </tr>`).join('')}</tbody>
  </table></div>`;
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
  const { root, api, session, setNavigation } = context;
  const canDashboard = hasPermission(session, 'management.dashboard.view');
  const canRenewals = hasPermission(session, 'renewal.manage');
  const canSupport = hasPermission(session, 'support.manage');
  const canManageAccounts = hasPermission(session, 'account.manage');
  const canManageDevices = hasPermission(session, 'device.manage');
  const canViewStaff = canManageAccounts || canManageDevices;
  setNavigation([
    { id: 'management-overview', label: 'Overview' },
    { id: 'management-loans', label: 'Clients & loans' },
    ...(canDashboard ? [{ id: 'management-alerts', label: 'Alerts & audit' }] : []),
    ...(canRenewals ? [{ id: 'management-renewals', label: 'Renewals' }] : []),
    ...(canSupport ? [{ id: 'management-support', label: 'Support' }] : []),
    ...(canManageAccounts ? [{ id: 'management-client-accounts', label: 'Client accounts' }] : []),
    ...(canViewStaff ? [{ id: 'management-staff', label: 'Staff & devices' }] : []),
    { id: 'management-account', label: 'My account' },
  ]);
  root.innerHTML = loadingPanel('Loading server-authoritative Management priorities…');

  const [account, overview, loans, alerts, renewals, support, staff] = await Promise.all([
    settledRequest(api, '/api/v1/account', {}, {}),
    canDashboard ? settledRequest(api, '/api/v1/management/dashboard-overview', {}, { metrics: [] }) : Promise.resolve({ data: { metrics: [] }, error: null }),
    settledRequest(api, '/api/v1/management/loans?status=active', {}, { summary: {}, loans: [] }),
    canDashboard ? settledRequest(api, '/api/v1/management/alerts-audit?window_days=30&limit=100', {}, { alerts: [], events: [] }) : Promise.resolve({ data: { alerts: [], events: [] }, error: null }),
    canRenewals ? settledRequest(api, '/api/v1/management/renewals?status=pending', {}, { requests: [] }) : Promise.resolve({ data: { requests: [] }, error: null }),
    canSupport ? settledRequest(api, '/api/v1/management/support?status=open', {}, { requests: [] }) : Promise.resolve({ data: { requests: [] }, error: null }),
    canViewStaff ? settledRequest(api, '/api/v1/management/accounts?staff_only=true', {}, { accounts: [] }) : Promise.resolve({ data: { accounts: [] }, error: null }),
  ]);
  const model = buildManagementViewModel({ account: account.data, overview: overview.data, loans: loans.data, alerts: alerts.data, renewals: renewals.data, support: support.data });
  const staffAccounts = asArray(staff.data.accounts);

  root.innerHTML = `<header class="workspace-header" id="management-overview"><div><p class="eyebrow">Management workspace</p><h1>Hello, ${escapeHtml(model.displayName)}</h1><p>Review live priorities and protected queues. Every official value and decision remains server-authoritative.</p></div>${model.generatedAt ? `<span class="meta">Generated ${formatDateTime(model.generatedAt)}</span>` : ''}</header>
  ${canDashboard ? (overview.error ? errorCard(overview.error) : overviewMetrics(model.metrics)) : `<div class="notice-card warning">Your account does not have Management dashboard permission.</div>`}
  <section class="section-card" id="management-loans"><div class="section-heading"><div><h2>Clients and loans</h2><p>Search the official portfolio. This view does not create or release loans.</p></div></div><form id="management-loan-search" class="search-bar"><input name="query" placeholder="Client, code, area, or loan number" /><select name="status"><option value="active">Active</option><option value="paid">Paid</option><option value="all">All</option></select><button class="button button-primary" type="submit">Search</button></form><div class="metric-grid">${metricCard('Active loans', escapeHtml(model.loanSummary.active_loan_count ?? 0))}${metricCard('Active clients', escapeHtml(model.loanSummary.active_client_count ?? 0))}${metricCard('Remaining portfolio', formatMoney(model.loanSummary.active_remaining_total || 0))}${metricCard('Overdue active', escapeHtml(model.loanSummary.overdue_active_count ?? 0))}</div><div id="management-loan-results">${loans.error ? errorCard(loans.error) : loanTable(loans.data)}</div></section>
  ${canDashboard ? `<section class="section-card" id="management-alerts"><div class="section-heading"><div><h2>Alerts and audit</h2><p>Read-only allowlisted activity from owning Spina records.</p></div></div>${alerts.error ? errorCard(alerts.error) : alertsMarkup(model.alerts, model.recentEvents)}</section>` : ''}
  ${canRenewals ? `<section class="section-card" id="management-renewals"><div class="section-heading"><div><h2>Renewal review</h2><p>Approval records the decision only; it does not itself release a new loan.</p></div></div>${renewals.error ? errorCard(renewals.error) : renewalQueue(model.pendingRenewals)}</section>` : ''}
  ${canSupport ? `<section class="section-card" id="management-support"><div class="section-heading"><div><h2>Client support</h2><p>Answer concerns without changing financial records.</p></div></div>${support.error ? errorCard(support.error) : supportQueue(model.openSupport)}</section>` : ''}
  ${canManageAccounts ? `<section class="section-card" id="management-client-accounts"><div class="section-heading"><div><h2>Client accounts</h2><p>Select an existing borrower record, enter the borrower's email, and let SPINA generate the credentials.</p></div></div>${clientAccountAdminMarkup()}</section>` : ''}
  ${canViewStaff ? `<section class="section-card" id="management-staff"><div class="section-heading"><div><h2>Staff and devices</h2><p>Invite staff, inspect registered phones, and apply only server-authorized device changes.</p></div></div>${staffInviteMarkup(session)}${staff.error ? errorCard(staff.error) : staffRows(staffAccounts, canManageDevices)}<div id="management-staff-device-detail" class="section-card" style="margin-top:1rem">${emptyState('Select a staff account to review registered phones.')}</div></section>` : ''}
  <section class="section-card" id="management-account"><div class="section-heading"><div><h2>My account</h2></div></div>${account.error ? errorCard(account.error) : accountCard(account.data)}</section>`;

  bindLoanSearch(context);
  bindRenewals(context);
  bindSupport(context);
  bindClientAccountAdmin(context);
  bindStaffInvite(context);
  bindStaffDevices(context, staffAccounts);
}

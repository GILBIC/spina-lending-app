import { buildClientViewModel } from '../presenters.js';
import {
  asArray,
  badge,
  detailItem,
  emptyState,
  errorCard,
  escapeHtml,
  formatDate,
  formatDateTime,
  formatMoney,
  loadingPanel,
  metricCard,
  settledRequest,
  setButtonBusy,
  showToast,
} from '../ui.js';
import { classifyLoanType } from '../collector-contract.js';

function loanCard(loan) {
  const type = classifyLoanType(loan.loan_type_name ?? loan.loan_type_code);
  const typeLabel = type === 'seven-by-seven' ? '7x7' : loan.loan_type_name || 'Regular';
  return `<article class="loan-card ${type}">
    <div class="section-heading">
      <div>
        <span class="badge ${type === 'seven-by-seven' ? 'info' : 'warning'}">${escapeHtml(typeLabel)}</span>
        <h3 class="loan-title">${escapeHtml(loan.loan_number || 'Loan')}</h3>
      </div>
      ${badge(loan.status || loan.loan_status || 'unknown')}
    </div>
    <div class="loan-meta">
      ${detailItem('Original principal', formatMoney(loan.principal))}
      ${detailItem('Official balance', formatMoney(loan.remaining_balance))}
      ${detailItem('Daily amount', formatMoney(loan.daily_amount))}
      ${detailItem('Paid amount', formatMoney(loan.paid_amount))}
      ${detailItem('Released', formatDate(loan.date_released))}
      ${detailItem('Due date', formatDate(loan.due_date))}
    </div>
    <div class="inline-actions">
      ${loan.pass_count ? `<span class="badge warning">Missed / PASS ${escapeHtml(loan.pass_count)}</span>` : ''}
      ${loan.advance_until ? `<span class="badge success">ADV through ${formatDate(loan.advance_until)}</span>` : ''}
    </div>
  </article>`;
}

function paymentRows(payments) {
  if (!payments.length) return emptyState('No official payment receipt is available yet.');
  return `<div class="table-wrap"><table>
    <thead><tr><th>Date</th><th>Loan</th><th>Type</th><th>Amount</th><th>Receipt</th><th>Official balance</th><th>Status</th></tr></thead>
    <tbody>${payments
      .map(
        (payment) => `<tr>
          <td>${formatDate(payment.collection_date)}</td>
          <td><strong>${escapeHtml(payment.loan_number || '—')}</strong><br><span class="meta">${escapeHtml(payment.loan_type_name || '')}</span></td>
          <td>${escapeHtml(payment.entry_type || 'payment')}</td>
          <td>${formatMoney(payment.amount)}</td>
          <td>${escapeHtml(payment.receipt_number || '—')}</td>
          <td>${formatMoney(payment.official_balance)}</td>
          <td>${payment.is_voided ? badge('voided', 'danger') : badge(payment.status || 'accepted')}</td>
        </tr>`,
      )
      .join('')}</tbody>
  </table></div>`;
}

function renewalRows(requests) {
  if (!requests.length) return emptyState('No renewal request has been submitted.');
  return `<div class="list-stack">${requests
    .map(
      (request) => `<article class="list-item">
        <div class="section-heading">
          <div><strong>${escapeHtml(request.loan_number || 'Loan renewal')}</strong><div class="meta">Requested ${formatMoney(request.requested_amount)} · ${formatDateTime(request.submitted_at)}</div></div>
          ${badge(request.status)}
        </div>
        ${request.client_message ? `<p>${escapeHtml(request.client_message)}</p>` : ''}
        ${request.review_note ? `<div class="notice-card"><strong>Management note:</strong> ${escapeHtml(request.review_note)}</div>` : ''}
      </article>`,
    )
    .join('')}</div>`;
}

function supportRows(requests) {
  if (!requests.length) return emptyState('No support request has been submitted.');
  return `<div class="list-stack">${requests
    .map(
      (request) => `<article class="list-item">
        <div class="section-heading">
          <div><strong>${escapeHtml(request.subject || 'Support request')}</strong><div class="meta">${escapeHtml(request.category || 'other')} · ${formatDateTime(request.created_at)}</div></div>
          ${badge(request.status)}
        </div>
        <p>${escapeHtml(request.message || '')}</p>
        ${request.management_response ? `<div class="notice-card"><strong>SPINA response:</strong> ${escapeHtml(request.management_response)}</div>` : ''}
      </article>`,
    )
    .join('')}</div>`;
}

function notificationRows(items) {
  if (!items.length) return emptyState('You have no new SPINA updates.');
  return `<div class="timeline">${items
    .slice(0, 30)
    .map(
      (item) => `<article class="timeline-item">
        <strong>${escapeHtml(item.title || item.notification_type || 'SPINA update')}</strong>
        <span>${escapeHtml(item.message || '')}</span>
        <span class="meta">${formatDateTime(item.created_at)}</span>
      </article>`,
    )
    .join('')}</div>`;
}

function accountCard(account) {
  const profile = account.profile ?? {};
  const devices = asArray(account.devices);
  return `<div class="card-grid">
    <article class="data-card">
      <h3>Profile</h3>
      <div class="kv-list">
        <div class="kv-row"><span>Name</span><strong>${escapeHtml(profile.full_name || '—')}</strong></div>
        <div class="kv-row"><span>Username</span><strong>${escapeHtml(profile.username || '—')}</strong></div>
        <div class="kv-row"><span>Email</span><strong>${escapeHtml(profile.email || '—')}</strong></div>
        <div class="kv-row"><span>Status</span>${badge(profile.status || 'unknown')}</div>
      </div>
    </article>
    <article class="data-card">
      <h3>Registered devices</h3>
      ${devices.length ? `<div class="list-stack">${devices.map((device) => `<div class="list-item"><strong>${escapeHtml(device.platform || 'Device')} ${device.is_current ? '· This device' : ''}</strong><span class="meta">Version ${escapeHtml(device.app_version || '—')} · Last seen ${formatDateTime(device.last_seen_at)}</span>${badge(device.status)}</div>`).join('')}</div>` : emptyState('No registered device record is available.')}
    </article>
  </div>`;
}

function renderWorkspace(root, model, raw, errors) {
  const latestPayment = model.payments[0];
  const renewalLoans = asArray(raw.renewals.loans).filter((loan) => loan.eligible === true && !loan.pending_request_id);
  root.innerHTML = `<header class="workspace-header" id="client-overview">
    <div><p class="eyebrow">Client workspace</p><h1>Hello, ${escapeHtml(model.displayName)}</h1><p>Review your own official loans, payments, receipts, requests, and account security. Values come directly from SPINA.</p></div>
  </header>
  <section class="metric-grid">
    ${metricCard('Active loans', escapeHtml(model.activeLoanCount))}
    ${metricCard('Pending renewals', escapeHtml(model.pendingRenewalCount))}
    ${metricCard('Open support', escapeHtml(model.openSupportCount))}
    ${metricCard('Latest receipt', latestPayment ? escapeHtml(latestPayment.receipt_number || 'Recorded') : 'None')}
  </section>

  <section class="section-card" id="client-loans">
    <div class="section-heading"><div><h2>My loans</h2><p>Regular and 7x7 obligations are always shown separately.</p></div></div>
    ${errors.loans ? errorCard(errors.loans) : model.allLoans.length ? `<div class="loan-grid">${model.regularLoans.map(loanCard).join('')}${model.sevenBySevenLoans.map(loanCard).join('')}${model.otherLoans.map(loanCard).join('')}</div>` : emptyState('No linked loan is available on this account.')}
  </section>

  <section class="section-card" id="client-payments">
    <div class="section-heading"><div><h2>Payments and official receipts</h2><p>A receipt appears only after SPINA accepts an official collection.</p></div></div>
    ${errors.payments ? errorCard(errors.payments) : paymentRows(model.payments)}
  </section>

  <section class="section-card" id="client-renewals">
    <div class="section-heading"><div><h2>Renewal requests</h2><p>A request never creates or releases a new loan. Management approval and office processing remain required.</p></div></div>
    ${errors.renewals ? errorCard(errors.renewals) : renewalRows(model.renewals)}
    <details ${renewalLoans.length ? '' : 'hidden'}>
      <summary>Submit a renewal request</summary>
      <form id="client-renewal-form" class="entry-form">
        <label>Eligible loan<select name="loanId" required>${renewalLoans.map((loan) => `<option value="${escapeHtml(loan.loan_id)}">${escapeHtml(loan.loan_number)} · ${escapeHtml(loan.loan_type_name)}</option>`).join('')}</select></label>
        <label>Requested amount<input name="requestedAmount" inputmode="decimal" required placeholder="0.00" /></label>
        <label>Message<textarea name="message" maxlength="1000" placeholder="Optional reason or request details"></textarea></label>
        <button class="button button-primary" type="submit">Send renewal request</button>
      </form>
    </details>
  </section>

  <section class="section-card" id="client-support">
    <div class="section-heading"><div><h2>Support</h2><p>Ask about a payment, loan, renewal, or account. Support messages do not change financial records.</p></div></div>
    ${errors.support ? errorCard(errors.support) : supportRows(model.supportRequests)}
    <details>
      <summary>Send a support request</summary>
      <form id="client-support-form" class="entry-form">
        <label>Category<select name="category" required><option value="payment">Payment</option><option value="loan">Loan</option><option value="renewal">Renewal</option><option value="account">Account</option><option value="other">Other</option></select></label>
        <label>Subject<input name="subject" minlength="3" maxlength="120" required /></label>
        <label>Reference<input name="referenceText" maxlength="120" placeholder="Receipt or loan number (optional)" /></label>
        <label>Message<textarea name="message" minlength="3" maxlength="2000" required></textarea></label>
        <button class="button button-primary" type="submit">Send support request</button>
      </form>
    </details>
  </section>

  <section class="section-card" id="client-payment-instructions">
    <div class="section-heading"><div><h2>Payment instructions</h2><p>Opening a payment provider page does not itself create an official SPINA payment.</p></div></div>
    ${errors.gcash ? errorCard(errors.gcash) : `<div class="notice-card ${model.paymentInstructions.payment_available ? '' : 'warning'}"><strong>${model.paymentInstructions.payment_available ? 'GCash checkout available' : 'GCash checkout not connected'}</strong><br>${escapeHtml(model.paymentInstructions.message || model.paymentInstructions.official_payment_rule || 'Ask your collector or office for the approved payment instructions.')}</div>`}
  </section>

  <section class="section-card" id="client-updates">
    <div class="section-heading"><div><h2>Updates</h2><p>Notices intended for your account only.</p></div></div>
    ${errors.notifications ? errorCard(errors.notifications) : notificationRows(model.notifications)}
  </section>

  <section class="section-card" id="client-account">
    <div class="section-heading"><div><h2>Account and devices</h2><p>Review your SPINA profile and registered sessions.</p></div></div>
    ${errors.account ? errorCard(errors.account) : accountCard(model.account)}
  </section>`;
}

function bindForms(context, raw) {
  const renewalForm = context.root.querySelector('#client-renewal-form');
  renewalForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = renewalForm.querySelector('button[type="submit"]');
    setButtonBusy(button, true, 'Sending…');
    const data = new FormData(renewalForm);
    try {
      await context.api.request('/api/v1/client/renewals', {
        method: 'POST',
        body: {
          loan_id: data.get('loanId'),
          requested_amount: String(data.get('requestedAmount') || '').trim(),
          message: String(data.get('message') || '').trim(),
        },
      });
      showToast('Renewal request sent for Management review.', 'success');
      await mountClientWorkspace(context);
    } catch (error) {
      showToast(error.message, 'error');
      setButtonBusy(button, false);
    }
  });

  const supportForm = context.root.querySelector('#client-support-form');
  supportForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = supportForm.querySelector('button[type="submit"]');
    setButtonBusy(button, true, 'Sending…');
    const data = new FormData(supportForm);
    try {
      await context.api.request('/api/v1/client/support', {
        method: 'POST',
        body: {
          category: data.get('category'),
          subject: String(data.get('subject') || '').trim(),
          message: String(data.get('message') || '').trim(),
          reference_text: String(data.get('referenceText') || '').trim(),
        },
      });
      showToast('Support request sent.', 'success');
      await mountClientWorkspace(context);
    } catch (error) {
      showToast(error.message, 'error');
      setButtonBusy(button, false);
    }
  });
}

export async function mountClientWorkspace(context) {
  const { root, api, setNavigation } = context;
  setNavigation([
    { id: 'client-overview', label: 'Overview' },
    { id: 'client-loans', label: 'My loans' },
    { id: 'client-payments', label: 'Payments' },
    { id: 'client-renewals', label: 'Renewals' },
    { id: 'client-support', label: 'Support' },
    { id: 'client-payment-instructions', label: 'Payment instructions' },
    { id: 'client-updates', label: 'Updates' },
    { id: 'client-account', label: 'Account' },
  ]);
  root.innerHTML = loadingPanel('Loading your official Client records…');

  const [account, loans, payments, renewals, support, gcash, notifications] = await Promise.all([
    settledRequest(api, '/api/v1/account', {}, {}),
    settledRequest(api, '/api/v1/client/loans', {}, { loans: [] }),
    settledRequest(api, '/api/v1/client/payments', {}, { payments: [] }),
    settledRequest(api, '/api/v1/client/renewals', {}, { loans: [], requests: [] }),
    settledRequest(api, '/api/v1/client/support', {}, { requests: [] }),
    settledRequest(api, '/api/v1/client/gcash/config', {}, { payment_available: false }),
    settledRequest(api, '/api/v1/activity-notifications', {}, []),
  ]);
  const raw = {
    account: account.data,
    loans: loans.data,
    payments: payments.data,
    renewals: renewals.data,
    support: support.data,
    gcash: gcash.data,
    notifications: notifications.data,
  };
  const model = buildClientViewModel(raw);
  renderWorkspace(root, model, raw, {
    account: account.error,
    loans: loans.error,
    payments: payments.error,
    renewals: renewals.error,
    support: support.error,
    gcash: gcash.error,
    notifications: notifications.error,
  });
  bindForms(context, raw);
}

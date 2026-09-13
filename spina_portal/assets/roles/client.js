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
import {
  bindClientGcashPanel,
  renderClientGcashPanel,
} from '../client-gcash.js';
import {
  bindClientScheduleButtons,
  formatAuthoritativeMoney,
} from '../client-schedule.js';
import { renderClientStatement } from '../client-statement.js';

export function loanCard(loan) {
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
      ${loan.loan_id ? `<button class="button button-secondary" type="button" data-client-schedule-loan="${escapeHtml(loan.loan_id)}">View schedule</button>` : ''}
    </div>
    <div data-client-schedule-panel hidden></div>
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

export function clientRenewalRows(requests) {
  if (!requests.length) return emptyState('No renewal request has been submitted.');
  return `<div class="list-stack">${requests
    .map((request) => {
      const requestId = String(request.request_id || '').trim();
      const isPending = String(request.status || '').trim().toLowerCase() === 'pending';
      return `<article class="list-item">
        <div class="section-heading">
          <div><strong>${escapeHtml(request.loan_number || 'Loan renewal')}</strong><div class="meta">Requested ${formatMoney(request.requested_amount)} · ${formatDateTime(request.submitted_at)}</div></div>
          ${badge(request.status)}
        </div>
        ${request.client_message ? `<p>${escapeHtml(request.client_message)}</p>` : ''}
        ${request.review_note ? `<div class="notice-card"><strong>Management note:</strong> ${escapeHtml(request.review_note)}</div>` : ''}
        ${isPending && requestId ? `<button class="button button-secondary" type="button" data-client-renewal-cancel="${escapeHtml(requestId)}">Cancel request</button>` : ''}
      </article>`;
    })
    .join('')}</div>`;
}

export function clientRenewalWorkflowRows(requests) {
  if (!requests.length) return emptyState('No renewal workflow is awaiting your action.');
  return `<div class="list-stack">${requests
    .map((request) => {
      const requestId = String(request.request_id || '').trim();
      const status = String(request.status || '').trim().toLowerCase();
      const clientDecision = String(request.client_decision || '').trim().toLowerCase();
      const signers = asArray(request.signers);
      const borrowerSigner = signers.find(
        (signer) => String(signer.party_role || '').trim().toLowerCase() === 'borrower',
      );
      const otherSigners = signers.filter(
        (signer) => String(signer.party_role || '').trim().toLowerCase() !== 'borrower',
      );
      const canDecide = Boolean(requestId && status === 'approved' && !clientDecision);
      const canSign = Boolean(
        requestId &&
        status === 'approved' &&
        clientDecision === 'accepted' &&
        request.office_processing_required !== true &&
        borrowerSigner?.signer_id &&
        borrowerSigner.signed !== true &&
        borrowerSigner.government_id_verified === true &&
        borrowerSigner.selfie_verified === true,
      );
      const canConfirmCash = Boolean(
        requestId && request.cash_given_to_client_at && !request.client_cash_confirmed_at,
      );
      const requestedAmount = formatAuthoritativeMoney(request.requested_amount);
      const approvedPrincipal = formatAuthoritativeMoney(request.approved_principal);
      const offsetAmount = formatAuthoritativeMoney(request.renewal_offset_amount);
      const netAmount = formatAuthoritativeMoney(request.net_release_amount);

      return `<article class="list-item">
        <div class="section-heading">
          <div>
            <strong>${escapeHtml(request.loan_number || 'Renewal progress')}</strong>
            <div class="meta">${escapeHtml(request.loan_type_name || 'Loan')} · Requested ${requestedAmount}</div>
          </div>
          ${badge(request.status || 'unknown')}
        </div>
        <div class="loan-meta">
          ${request.approved_principal != null ? `<div class="detail-item"><span>Management approved</span><strong>${approvedPrincipal}</strong></div>` : ''}
          ${request.renewal_offset_amount != null ? `<div class="detail-item"><span>Old-loan settlement</span><strong>${offsetAmount}</strong></div>` : ''}
          ${request.net_release_amount != null ? `<div class="detail-item"><span>Locked net cash</span><strong>${netAmount}</strong></div>` : ''}
          ${clientDecision ? `<div class="detail-item"><span>Your decision</span><strong>${escapeHtml(clientDecision)}</strong></div>` : ''}
          ${request.signer_readiness_status ? `<div class="detail-item"><span>Signer status</span><strong>${escapeHtml(request.signer_readiness_status)}</strong></div>` : ''}
        </div>
        ${request.review_note ? `<div class="notice-card"><strong>Management note:</strong> ${escapeHtml(request.review_note)}</div>` : ''}
        ${canDecide ? `<div class="inline-actions">
          <button class="button button-primary" type="button" data-client-renewal-decision-request="${escapeHtml(requestId)}" data-client-renewal-decision="accepted">Accept &amp; Continue</button>
          <button class="button button-secondary" type="button" data-client-renewal-decision-request="${escapeHtml(requestId)}" data-client-renewal-decision="declined">Decline</button>
        </div>` : ''}
        ${clientDecision === 'accepted' ? `<div class="notice-card">
          <strong>Your signer step</strong>
          ${request.office_processing_required === true
            ? '<p>Office Processing Required — remote signature is disabled for this renewal.</p>'
            : borrowerSigner
              ? `<p class="meta">Own app ${borrowerSigner.has_app === true ? '✓' : '—'} · Government ID ${borrowerSigner.government_id_verified === true ? '✓' : 'Pending'} · Selfie ${borrowerSigner.selfie_verified === true ? '✓' : 'Pending'} · Signature ${borrowerSigner.signed === true ? '✓' : 'Pending'}</p>${canSign ? `<button class="button button-primary" type="button" data-client-renewal-sign-request="${escapeHtml(requestId)}" data-client-renewal-sign-signer="${escapeHtml(borrowerSigner.signer_id)}">Sign Renewal</button>` : ''}`
              : '<p>Waiting for Management to register your borrower signer requirement.</p>'}
          ${otherSigners.length ? '<p class="meta">Other required signers must complete their own verification and signature from their own SPINA account.</p>' : ''}
        </div>` : ''}
        ${canConfirmCash ? `<div class="notice-card">
          <strong>Collector marked ${netAmount} as given to you.</strong>
          <p>Confirm only after you personally receive the cash. The Collector cannot confirm this for you.</p>
          <button class="button button-primary" type="button" data-client-renewal-cash-confirm="${escapeHtml(requestId)}">I Received the Cash</button>
        </div>` : ''}
        ${request.client_cash_confirmed_at ? `<div class="notice-card">
          <strong>Cash received: Confirmed by you</strong>
          <p class="meta">Handover proof: ${escapeHtml(request.handover_proof_status || 'pending')} · Activation: ${escapeHtml(request.activation_status || 'pending')}</p>
          ${request.activation_status === 'active' ? '' : '<p>Your renewed loan is not collectible yet while Management verification remains pending.</p>'}
        </div>` : ''}
      </article>`;
    })
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

export function clientNotificationRows(items) {
  if (!items.length) return emptyState('You have no new SPINA updates.');
  return `<div class="timeline">${items
    .slice(0, 30)
    .map((item) => {
      const notificationId = String(item.notification_id || '').trim();
      const isRead = item.is_read === true;
      return `<article class="timeline-item">
        <div class="section-heading">
          <strong>${escapeHtml(item.title || item.notification_type || 'SPINA update')}</strong>
          ${badge(isRead ? 'Read' : 'Unread', isRead ? 'success' : 'warning')}
        </div>
        <span>${escapeHtml(item.message || '')}</span>
        <span class="meta">${formatDateTime(item.created_at)}</span>
        ${!isRead && notificationId ? `<button class="button button-secondary" type="button" data-client-notification-read="${escapeHtml(notificationId)}">Mark as read</button>` : ''}
      </article>`;
    })
    .join('')}</div>`;
}

export function clientAccountCard(account) {
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
      ${devices.length ? `<div class="list-stack">${devices.map((device) => {
        const canRevoke = Boolean(
          device.id &&
          device.is_current !== true &&
          String(device.status || '').trim().toLowerCase() === 'active',
        );
        return `<div class="list-item"><strong>${escapeHtml(device.platform || 'Device')} ${device.is_current ? '· This device' : ''}</strong><span class="meta">Version ${escapeHtml(device.app_version || '—')} · Last seen ${formatDateTime(device.last_seen_at)}</span>${badge(device.status)}${device.is_current ? '<span class="meta">Use Sign out to end access on this device.</span>' : ''}${canRevoke ? `<button class="button button-secondary" type="button" data-client-revoke-device="${escapeHtml(device.id)}">Revoke</button>` : ''}</div>`;
      }).join('')}</div>` : emptyState('No registered device record is available.')}
    </article>
  </div>`;
}

export async function requestClientDeviceRevocation({
  api,
  deviceId,
  confirmRevoke = globalThis.confirm,
}) {
  const normalized = String(deviceId || '').trim();
  if (!normalized) {
    throw new Error('A registered device is required.');
  }
  if (typeof confirmRevoke !== 'function' || !confirmRevoke('Revoke this device? You will need to sign in again on that device.')) {
    return false;
  }
  await api.request(
    `/api/v1/account/devices/${encodeURIComponent(normalized)}/revoke`,
    { method: 'POST' },
  );
  return true;
}

export async function requestClientNotificationRead({ api, notificationId }) {
  const normalized = String(notificationId || '').trim();
  if (!normalized) {
    throw new Error('A notification is required.');
  }
  return api.request(
    `/api/v1/activity-notifications/${encodeURIComponent(normalized)}/read`,
    { method: 'POST' },
  );
}

export async function requestClientRenewalCancellation({
  api,
  requestId,
  confirmCancel = globalThis.confirm,
}) {
  const normalized = String(requestId || '').trim();
  if (!normalized) {
    throw new Error('A renewal request is required.');
  }
  if (
    typeof confirmCancel !== 'function' ||
    !confirmCancel('Cancel this renewal request? Only this pending request will be cancelled.')
  ) {
    return false;
  }
  await api.request(
    `/api/v1/client/renewals/${encodeURIComponent(normalized)}/cancel`,
    { method: 'POST' },
  );
  return true;
}

export async function requestClientRenewalDecision({
  api,
  requestId,
  decision,
  confirmAction = globalThis.confirm,
}) {
  const normalizedId = String(requestId || '').trim();
  const normalizedDecision = String(decision || '').trim().toLowerCase();
  if (!normalizedId) throw new Error('A renewal request is required.');
  if (!['accepted', 'declined'].includes(normalizedDecision)) {
    throw new Error('A valid renewal decision is required.');
  }
  const message = normalizedDecision === 'accepted'
    ? 'Accept Management-approved renewal terms and continue? This does not release cash or activate the new loan.'
    : 'Decline this approved renewal? No new loan will be released from this approval.';
  if (typeof confirmAction !== 'function' || !confirmAction(message)) return false;
  await api.request(
    `/api/v1/client/renewals/${encodeURIComponent(normalizedId)}/decision`,
    { method: 'POST', body: { decision: normalizedDecision } },
  );
  return true;
}

export async function requestClientRenewalSignature({
  api,
  requestId,
  signerId,
  confirmAction = globalThis.confirm,
}) {
  const normalizedRequest = String(requestId || '').trim();
  const normalizedSigner = String(signerId || '').trim();
  if (!normalizedRequest || !normalizedSigner) {
    throw new Error('A renewal request and signer are required.');
  }
  if (
    typeof confirmAction !== 'function' ||
    !confirmAction('Sign this renewal from your own SPINA account? Never sign for another person.')
  ) {
    return false;
  }
  await api.request(
    `/api/v1/renewals/${encodeURIComponent(normalizedRequest)}/signers/${encodeURIComponent(normalizedSigner)}/sign`,
    { method: 'POST', body: {} },
  );
  return true;
}

export async function requestClientRenewalCashConfirmation({
  api,
  requestId,
  confirmAction = globalThis.confirm,
}) {
  const normalized = String(requestId || '').trim();
  if (!normalized) throw new Error('A renewal request is required.');
  if (
    typeof confirmAction !== 'function' ||
    !confirmAction('Confirm only if you personally received the locked renewal cash from the Collector.')
  ) {
    return false;
  }
  await api.request(
    `/api/v1/client/renewals/${encodeURIComponent(normalized)}/cash-confirm`,
    { method: 'POST', body: {} },
  );
  return true;
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

  <section class="section-card" id="client-statement">
    <div class="section-heading"><div><h2>Statement</h2><p>Read-only loan and official payment records from the protected SPINA server.</p></div></div>
    ${errors.statement ? errorCard(errors.statement) : renderClientStatement(raw.statement)}
  </section>

  <section class="section-card" id="client-renewals">
    <div class="section-heading"><div><h2>Renewal requests</h2><p>After you submit, your permanently assigned Collector must recommend the request before Management reviews and decides it. A request never creates or releases a new loan. If approved, complete only your own signer step; any other required signer must use their own SPINA account.</p></div></div>
    ${errors.renewals ? errorCard(errors.renewals) : clientRenewalRows(model.renewals)}
    <details ${renewalLoans.length ? '' : 'hidden'}>
      <summary>Submit a renewal request</summary>
      <form id="client-renewal-form" class="entry-form">
        <label>Eligible loan<select name="loanId" required>${renewalLoans.map((loan) => `<option value="${escapeHtml(loan.loan_id)}">${escapeHtml(loan.loan_number)} · ${escapeHtml(loan.loan_type_name)}</option>`).join('')}</select></label>
        <label>Requested amount<input name="requestedAmount" inputmode="decimal" required placeholder="0.00" /></label>
        <label>Message<textarea name="message" maxlength="1000" placeholder="Optional reason or request details"></textarea></label>
        <button class="button button-primary" type="submit">Send renewal request</button>
      </form>
    </details>
    <div class="section-heading"><div><h3>Renewal progress</h3><p>Approved terms, signer readiness, cash handover and activation status below come directly from SPINA.</p></div></div>
    ${errors.renewalWorkflow ? errorCard(errors.renewalWorkflow) : clientRenewalWorkflowRows(asArray(raw.renewalWorkflow.requests))}
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
    ${errors.gcash ? errorCard(errors.gcash) : renderClientGcashPanel({ capability: raw.gcash, loans: asArray(raw.loans.loans) })}
  </section>

  <section class="section-card" id="client-updates">
    <div class="section-heading"><div><h2>Updates</h2><p>Notices intended for your account only.</p></div></div>
    ${errors.notifications ? errorCard(errors.notifications) : clientNotificationRows(model.notifications)}
  </section>

  <section class="section-card" id="client-account">
    <div class="section-heading"><div><h2>Account and devices</h2><p>Review your SPINA profile and registered sessions.</p></div></div>
    ${errors.account ? errorCard(errors.account) : clientAccountCard(model.account)}
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
      showToast('Renewal request sent. Your assigned Collector must recommend it before Management review.', 'success');
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

function bindClientAccountDeviceSecurity(context) {
  for (const button of context.root.querySelectorAll('[data-client-revoke-device]')) {
    button.addEventListener('click', async () => {
      const deviceId = button.dataset.clientRevokeDevice;
      try {
        const revoked = await requestClientDeviceRevocation({
          api: context.api,
          deviceId,
        });
        if (!revoked) return;
        showToast('Device access revoked.', 'success');
        await mountClientWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
      }
    });
  }
}

function bindClientNotificationReadActions(context) {
  for (const button of context.root.querySelectorAll('[data-client-notification-read]')) {
    button.addEventListener('click', async () => {
      const notificationId = button.dataset.clientNotificationRead;
      setButtonBusy(button, true, 'Marking…');
      try {
        await requestClientNotificationRead({
          api: context.api,
          notificationId,
        });
        showToast('Update marked as read.', 'success');
        await mountClientWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }
}

function bindClientRenewalCancellation(context) {
  for (const button of context.root.querySelectorAll('[data-client-renewal-cancel]')) {
    button.addEventListener('click', async () => {
      const requestId = button.dataset.clientRenewalCancel;
      try {
        const cancelled = await requestClientRenewalCancellation({
          api: context.api,
          requestId,
        });
        if (!cancelled) return;
        showToast('Renewal request cancelled.', 'success');
        await mountClientWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
      }
    });
  }
}

function bindClientRenewalWorkflowActions(context) {
  for (const button of context.root.querySelectorAll('[data-client-renewal-decision-request][data-client-renewal-decision]')) {
    button.addEventListener('click', async () => {
      const requestId = button.dataset.clientRenewalDecisionRequest;
      const decision = button.dataset.clientRenewalDecision;
      setButtonBusy(button, true, decision === 'accepted' ? 'Accepting…' : 'Declining…');
      try {
        const acted = await requestClientRenewalDecision({
          api: context.api,
          requestId,
          decision,
        });
        if (!acted) {
          setButtonBusy(button, false);
          return;
        }
        showToast(decision === 'accepted' ? 'Renewal accepted. Complete your own signer step next.' : 'Renewal declined.', 'success');
        await mountClientWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }

  for (const button of context.root.querySelectorAll('[data-client-renewal-sign-request][data-client-renewal-sign-signer]')) {
    button.addEventListener('click', async () => {
      const requestId = button.dataset.clientRenewalSignRequest;
      const signerId = button.dataset.clientRenewalSignSigner;
      setButtonBusy(button, true, 'Signing…');
      try {
        const signed = await requestClientRenewalSignature({
          api: context.api,
          requestId,
          signerId,
        });
        if (!signed) {
          setButtonBusy(button, false);
          return;
        }
        showToast('Your renewal signature was recorded.', 'success');
        await mountClientWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }

  for (const button of context.root.querySelectorAll('[data-client-renewal-cash-confirm]')) {
    button.addEventListener('click', async () => {
      const requestId = button.dataset.clientRenewalCashConfirm;
      setButtonBusy(button, true, 'Confirming…');
      try {
        const confirmed = await requestClientRenewalCashConfirmation({
          api: context.api,
          requestId,
        });
        if (!confirmed) {
          setButtonBusy(button, false);
          return;
        }
        showToast('Cash receipt confirmed.', 'success');
        await mountClientWorkspace(context);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }
}

export async function mountClientWorkspace(context) {
  const { root, api, setNavigation } = context;
  setNavigation([
    { id: 'client-overview', label: 'Overview' },
    { id: 'client-loans', label: 'My loans' },
    { id: 'client-payments', label: 'Payments' },
    { id: 'client-statement', label: 'Statement' },
    { id: 'client-renewals', label: 'Renewals' },
    { id: 'client-support', label: 'Support' },
    { id: 'client-payment-instructions', label: 'Payment instructions' },
    { id: 'client-updates', label: 'Updates' },
    { id: 'client-account', label: 'Account' },
  ]);
  root.innerHTML = loadingPanel('Loading your official Client records…');

  const [account, loans, payments, statement, renewals, renewalWorkflow, support, gcash, notifications] = await Promise.all([
    settledRequest(api, '/api/v1/account', {}, {}),
    settledRequest(api, '/api/v1/client/loans', {}, { loans: [] }),
    settledRequest(api, '/api/v1/client/payments', {}, { payments: [] }),
    settledRequest(api, '/api/v1/client/statement', {}, { client: {}, loans: [], payments: [] }),
    settledRequest(api, '/api/v1/client/renewals', {}, { loans: [], requests: [] }),
    settledRequest(api, '/api/v1/client/renewal-workflow', {}, { requests: [] }),
    settledRequest(api, '/api/v1/client/support', {}, { requests: [] }),
    settledRequest(api, '/api/v1/client/gcash/config', {}, { payment_available: false }),
    settledRequest(api, '/api/v1/activity-notifications', {}, []),
  ]);
  const raw = {
    account: account.data,
    loans: loans.data,
    payments: payments.data,
    statement: statement.data,
    renewals: renewals.data,
    renewalWorkflow: renewalWorkflow.data,
    support: support.data,
    gcash: gcash.data,
    notifications: notifications.data,
  };
  const model = buildClientViewModel(raw);
  renderWorkspace(root, model, raw, {
    account: account.error,
    loans: loans.error,
    payments: payments.error,
    statement: statement.error,
    renewals: renewals.error,
    renewalWorkflow: renewalWorkflow.error,
    support: support.error,
    gcash: gcash.error,
    notifications: notifications.error,
  });
  bindForms(context, raw);
  bindClientScheduleButtons(context);
  bindClientGcashPanel(context);
  bindClientAccountDeviceSecurity(context);
  bindClientNotificationReadActions(context);
  bindClientRenewalCancellation(context);
  bindClientRenewalWorkflowActions(context);
}

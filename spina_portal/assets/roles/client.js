import {mountTreasuryClaim} from '../treasury-payment-claim.js';
import {createTreasuryRoleGate} from '../treasury-role-tasks.js';
import {createClientReadController,createClientMutationController} from '../client-workspace-state.js';
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
  loadingPanel,
  metricCard,
  setButtonBusy,
  clearButtonBusyFocus,
  showToast,
} from '../ui.js';
import { classifyLoanType,normalizeMoney } from '../collector-contract.js';
import {
  bindClientGcashPanel,
  renderClientGcashPanel, validClientGcashCapability,
} from '../client-gcash.js';
import {
  bindClientScheduleButtons,
  formatAuthoritativeMoney, renderClientPayoff, createClientScheduleController, clientInstallmentGuidance, manilaToday,
} from '../client-schedule.js';
import { renderClientStatement } from '../client-statement.js';
import {bindClientPaymentDetails} from '../client-payment-details.js';
import {downloadClientRecordCopy} from '../client-documents.js';
import { mountClientDocuments } from '../client-documents.js';
import { mountPaymentProofs } from '../payment-proofs.js';

function clientHomeObligationSummary(schedule) { return renderClientPayoff(schedule); }

export function loanCard(loan, obligationSchedule = null) {
  const type = classifyLoanType(loan.loan_type_name ?? loan.loan_type_code);
  const typeLabel = type === 'seven-by-seven' ? '7x7' : loan.loan_type_name || 'Regular';
  const obligationSummary = type === 'seven-by-seven'
    ? clientHomeObligationSummary(obligationSchedule)
    : '';
  return `<article class="loan-card ${type}">
    <div class="section-heading">
      <div>
        <span class="badge ${type === 'seven-by-seven' ? 'info' : 'warning'}">${escapeHtml(typeLabel)}</span>
        <h3 class="loan-title">${escapeHtml(loan.loan_number || 'Loan')}</h3>
      </div>
      ${badge(loan.status || loan.loan_status || 'unknown')}
    </div>
    <div class="loan-meta">
      ${detailItem('Original principal', formatAuthoritativeMoney(loan.principal))}
      ${detailItem('Official balance', formatAuthoritativeMoney(loan.remaining_balance))}
      ${detailItem('Required payment', formatAuthoritativeMoney(loan.daily_amount))}
      ${detailItem('Paid amount', formatAuthoritativeMoney(loan.paid_amount))}
      ${detailItem('Released', formatDate(loan.date_released))}
      ${detailItem('First contractual payment', formatDate(loan.first_payment_date))}
      ${detailItem('Due date', formatDate(loan.due_date))}
    </div>
    <div data-client-loan-summary="${escapeHtml(loan.loan_id)}">${obligationSummary}</div>
    <div class="inline-actions">
      ${loan.pass_count ? `<span class="badge warning">Missed / PASS ${escapeHtml(loan.pass_count)}</span>` : ''}
      ${loan.advance_until ? `<span class="badge success">ADV through ${formatDate(loan.advance_until)}</span>` : ''}
      ${loan.loan_id ? `<button class="button button-secondary" type="button" data-client-schedule-loan="${escapeHtml(loan.loan_id)}">View schedule</button>` : ''}
    </div>
    <div data-client-schedule-panel hidden></div>
  </article>`;
}

export async function loadClientHomeObligationSchedules(api, portfolio, controller = createClientScheduleController({api})) {
 const loans=asArray(portfolio?.loans).filter(loan=>String(loan.status||loan.loan_status).toLowerCase()==='active'&&classifyLoanType(loan.loan_type_name??loan.loan_type_code)==='seven-by-seven'&&loan.loan_id);
 return Object.fromEntries(await Promise.all(loans.map(async loan=>[loan.loan_id,await controller.load(loan.loan_id)])));
}
function paymentRows(payments) {
  if (!payments.length) return emptyState('No official payment receipt is available yet.');
  return `<div class="table-wrap"><table class="mobile-card-table client-payment-table">
    <thead><tr><th>Date</th><th>Loan</th><th>Type</th><th>Amount</th><th>Receipt</th><th>Official balance</th><th>Status</th></tr></thead>
    <tbody>${payments
      .map(
        (payment) => `<tr>
          <td data-label="Date">${formatDate(payment.collection_date)}</td>
          <td data-label="Loan"><strong>${escapeHtml(payment.loan_number || '—')}</strong><br><span class="meta">${escapeHtml(payment.loan_type_name || '')}</span></td>
          <td data-label="Type">${escapeHtml(payment.entry_type || 'payment')}</td>
          <td data-label="Amount">${formatAuthoritativeMoney(payment.amount)}</td>
          <td data-label="Receipt">${escapeHtml(payment.receipt_number || '—')}<button class="button button-secondary" type="button" data-payment-details="${escapeHtml(payment.transaction_id)}">View payment details</button><div data-payment-detail-panel="${escapeHtml(payment.transaction_id)}" hidden></div></td>
          <td data-label="Balance">${formatAuthoritativeMoney(payment.official_balance)}</td>
          <td data-label="Status">${payment.is_voided ? badge('voided', 'danger') : badge(payment.status || 'accepted')}</td>
        </tr>`,
      )
      .join('')}</tbody>
  </table></div>`;
}

export function clientRenewalEligibilityRows(loans) {
  return loans.map((loan) => `<article class="list-item">
    <strong>${escapeHtml(loan.loan_number || 'Loan')}</strong>
    <div class="detail-grid">
      ${detailItem('Signed contractual total', formatAuthoritativeMoney(loan.contractual_total))}
      ${detailItem('Paid amount', formatAuthoritativeMoney(loan.paid_amount))}
      ${detailItem('Paid percentage', loan.paid_percent == null ? 'Unavailable' : `${escapeHtml(loan.paid_percent)}%`)}
    </div>
    <p>${escapeHtml(loan.eligibility_message || 'Renewal eligibility is unavailable.')}</p>
  </article>`).join('');
}

export function clientRenewalRows(requests,{readOnly=false}={}) {
  if (!requests.length) return emptyState('No renewal request has been submitted.');
  return `<div class="list-stack">${requests
    .map((request) => {
      const requestId = String(request.request_id || '').trim();
      const isPending = String(request.status || '').trim().toLowerCase() === 'pending';
      return `<article class="list-item">
        <div class="section-heading">
          <div><strong>${escapeHtml(request.loan_number || 'Loan renewal')}</strong><div class="meta">Requested ${formatAuthoritativeMoney(request.requested_amount)} · ${formatDateTime(request.submitted_at)}</div></div>
          ${badge(request.status)}
        </div>
        ${request.client_message ? `<p>${escapeHtml(request.client_message)}</p>` : ''}
        ${request.review_note ? `<div class="notice-card"><strong>Management note:</strong> ${escapeHtml(request.review_note)}</div>` : ''}
        ${!readOnly && isPending && requestId ? `<button class="button button-secondary" type="button" data-client-renewal-cancel="${escapeHtml(requestId)}">Cancel request</button>` : ''}
      </article>`;
    })
    .join('')}</div>`;
}

function clientRenewalActions(request, borrowerSigner) {
  const requestId = String(request.request_id || '').trim();
  const status = String(request.status || '').trim().toLowerCase();
  const clientDecision = String(request.client_decision || '').trim().toLowerCase();
  return {
    canDecide: Boolean(requestId && status === 'approved' && !clientDecision),
    canSign: Boolean(
      requestId && status === 'approved' && clientDecision === 'accepted'
      && request.office_processing_required === false && ['pending','ready'].includes(request.signer_readiness_status) && borrowerSigner?.has_app === true && borrowerSigner?.signer_id
      && borrowerSigner.signed !== true && borrowerSigner.government_id_verified === true
      && borrowerSigner.selfie_verified === true,
    ),
    canConfirmCash: Boolean(requestId && request.cash_given_to_client_at && !request.client_cash_confirmed_at),
  };
}

const clientRenewalStageLabels={
 signer_readiness_status:{pending:'Verification or signatures pending',ready:'Signers ready',office_required:'Office processing required'},
 handover_proof_status:{not_submitted:'Not submitted',under_review:'Under review',approved:'Approved',correction_required:'Correction required',flagged:'Flagged for review'},
 activation_status:{not_released:'Not released',released_pending_management:'Released; awaiting Management verification',active:'Active'},
};
function clientRenewalStageLabel(field,value){
 const labels=clientRenewalStageLabels[field];return Object.hasOwn(labels,value)?labels[value]:`Status unavailable${value?` (${escapeHtml(value)})`:''}`;
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
      const { canDecide, canSign, canConfirmCash } = clientRenewalActions(request, borrowerSigner);
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
        ${request.client_message?`<p>${escapeHtml(request.client_message)}</p>`:''}
        ${status==='pending'&&requestId?`<button class="button button-secondary" type="button" data-client-renewal-cancel="${escapeHtml(requestId)}">Cancel request</button>`:''}
        <div class="loan-meta">
          ${request.approved_principal != null ? `<div class="detail-item"><span>Management approved</span><strong>${approvedPrincipal}</strong></div>` : ''}
          ${request.renewal_offset_amount != null ? `<div class="detail-item"><span>Old-loan settlement</span><strong>${offsetAmount}</strong></div>` : ''}
          ${request.net_release_amount != null ? `<div class="detail-item"><span>Locked net cash</span><strong>${netAmount}</strong></div>` : ''}
          ${clientDecision ? `<div class="detail-item"><span>Your decision</span><strong>${escapeHtml(clientDecision)}</strong></div>` : ''}
          ${request.signer_readiness_status ? `<div class="detail-item"><span>Signer status</span><strong>${clientRenewalStageLabel('signer_readiness_status',request.signer_readiness_status)}</strong></div>` : ''}
        </div>
        ${request.review_note ? `<div class="notice-card"><strong>Management note:</strong> ${escapeHtml(request.review_note)}</div>` : ''}
        ${[['Collector note','collector_comment'],['Collector reason','collector_reason_code'],['Management override reason','management_override_reason']].filter(([,field])=>request[field]).map(([label,field])=>`<div class="notice-card"><strong>${label}:</strong> ${escapeHtml(request[field])}</div>`).join('')}
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
          ${otherSigners.length ? '<p class="meta">Every other required signer must use their own SPINA account to complete verification and signing.</p>' : ''}
        </div>` : ''}
        ${canConfirmCash ? `<div class="notice-card">
          <strong>Collector marked ${netAmount} as given to you.</strong>
          <p>Confirm only after you personally receive the cash. The Collector cannot confirm this for you.</p>
          <button class="button button-primary" type="button" data-client-renewal-cash-confirm="${escapeHtml(requestId)}">I Received the Cash</button>
        </div>` : ''}
        ${request.client_cash_confirmed_at ? `<div class="notice-card">
          <strong>Cash received: Confirmed by you</strong>
          <p class="meta">Handover proof: ${clientRenewalStageLabel('handover_proof_status',request.handover_proof_status)} · Activation: ${clientRenewalStageLabel('activation_status',request.activation_status)}</p>
          ${request.activation_status === 'active' ? '' : '<p>Your renewed loan is not collectible yet while Management verification remains pending.</p>'}
        </div>` : ''}
      </article>`;
    })
    .join('')}</div>`;
}

export function clientRenewalPresentation({eligibilityState,requestsState,workflowState,selectedRequestId,view='current'}) {
 const requests=requestsState?.status==='ready'?asArray(requestsState.data?.requests):[];
 const progress=workflowState?.status==='ready'?asArray(workflowState.data?.requests):[];
 const terminal=request=>['cancelled','rejected','declined'].includes(String(request.status).toLowerCase())||request.client_decision==='declined'||request.activation_status==='active';
 const cards=requests.map(request=>{const found=progress.find(item=>item.request_id===request.request_id)||null;const conflict=found&&['loan_id','client_id','status','requested_amount'].some(key=>request[key]!=null&&found[key]!=null&&request[key]!==found[key]);const workflow=conflict?null:found;const record=workflow?{...request,...workflow}:request;let nextStep;
 if(conflict)nextStep='Renewal sources changed or disagree. Refresh both records before continuing.';
  else if(!workflow&&request.status==='approved')nextStep='Renewal progress unavailable. Refresh before continuing.';
 else if(terminal(record))nextStep=record.activation_status==='active'?'Renewed loan active. Open My loans for its saved schedule.':'No further action on this request.';
 else if(record.client_cash_confirmed_at)nextStep='Waiting for Management verification and activation.';
 else if(record.cash_given_to_client_at)nextStep='Confirm cash only after you personally receive it.';
 else if(record.office_processing_required===true)nextStep='Continue the required steps at the office.';
 else if(record.status==='approved'&&!record.client_decision)nextStep='Review approved terms and choose your decision.';
 else if(record.client_decision==='accepted'){
  const signers=asArray(record.signers),own=signers.find(signer=>signer.party_role==='borrower');
  if(!['pending','ready','office_required'].includes(record.signer_readiness_status))nextStep='Signer status unavailable. Refresh to check the current renewal stage.';
  else if(record.signer_readiness_status==='office_required')nextStep='Continue the required steps at the office.';
  else if(!own)nextStep='Waiting for Management to register your borrower signer requirement.';
  else if(own.signed===true)nextStep=record.signer_readiness_status==='pending'&&signers.some(signer=>signer.party_role!=='borrower'&&signer.signed===false)?'Your signer step is complete. Other signers must finish in their own SPINA accounts.':'Your signer step is complete. Waiting for the next office step.';
  else if(clientRenewalActions(record,own).canSign)nextStep='Complete your own signer step. Other signers use their own accounts.';
  else nextStep='Waiting for your signer verification before signing. Contact the office for help.';
 }
 else if(record.status==='pending')nextStep='Your assigned Collector recommends this request before Management decides.';
 else nextStep='Refresh to check the current request stage.';
 return {request,workflow,nextStep,conflict,terminal:conflict?false:terminal(record)};}).filter(card=>(view==='history'?card.terminal:!card.terminal)&&(!selectedRequestId||card.request.request_id===selectedRequestId));
 return {status:requestsState?.status||'idle',cards,eligibilityState,workflowStatus:workflowState?.status||'idle'};
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

function clientNotificationCount(items){return `${items.length} loaded updates · ${items.filter(item=>item.is_read!==true).length} unread among loaded updates`;}

export function clientNotificationRows(items, {visibleLimit=30, authorizedRecords}={}) {
  if (!items.length) return emptyState('You have no new SPINA updates.');
  return `<p data-client-updates-count tabindex="-1">${clientNotificationCount(items)}</p><div class="timeline">${items
    .slice(0, visibleLimit)
    .map((item) => {
      const notificationId = String(item.notification_id || '').trim();
      const isRead = item.is_read === true;const target=authorizedRecords?clientNotificationTarget(item,authorizedRecords):null;
      return `<article class="timeline-item">
        <div class="section-heading">
          <strong>${escapeHtml(item.title || item.notification_type || 'SPINA update')}</strong>
          <span data-client-notification-status tabindex="-1">${badge(isRead ? 'Read' : 'Unread', isRead ? 'success' : 'warning')}</span>
        </div>
        <span>${escapeHtml(item.message || '')}</span>${target?`<button class="button button-secondary" type="button" data-client-notification-payment="${escapeHtml(target.recordId)}">Open related payment record</button>`:''}
        <span class="meta">${formatDateTime(item.created_at)}</span>
        ${!isRead && notificationId ? `<button class="button button-secondary" type="button" data-client-notification-read="${escapeHtml(notificationId)}">Mark as read</button>` : ''}
      </article>`;
    })
    .join('')}</div>${visibleLimit<items.length?'<button class="button button-secondary" type="button" data-client-updates-more>Show more updates</button>':''}`;
}

// Verified producers: cross_collector_activity migration and collection_void_repository.
export function clientNotificationTarget(notification, records, producerMap={client_payment_posted:'payment',client_payment_voided:'payment'}) {
 if(!records?.userId||notification?.recipient_user_id!==records.userId||producerMap[notification.notification_type]!=='payment')return null;
 const id=notification.transaction_id;if(typeof id!=='string'||!asArray(records.payments).some(payment=>payment.transaction_id===id))return null;
 return {sectionId:'client-payments',recordId:id,kind:'payment'};
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

const clientUuid=value=>typeof value==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const clientText=value=>String(value??'').trim().replace(/\s+/g,' ');
const recordedTime=value=>typeof value==='string'&&value.length>0&&!Number.isNaN(Date.parse(value));
function unconfirmedClientResult(){return Object.assign(new Error('Submission could not be confirmed. Check its saved status with the office before trying again.'),{code:'client_result_unverified'});}
export function verifyClientCreatedRequest(result,{kind,body,clientId}) {
 const record=result?.request;
 if(!record||!clientUuid(record.request_id)||!clientUuid(record.client_id)||(clientId&&record.client_id!==clientId))throw unconfirmedClientResult();
 if(kind==='support'){
  if(record.status!=='open'||!recordedTime(record.created_at)||record.category!==body.category||['subject','message','reference_text'].some(key=>record[key]!==clientText(body[key])))throw unconfirmedClientResult();
 }else if(record.status!=='pending'||!recordedTime(record.submitted_at)||record.loan_id!==body.loan_id||record.requested_amount!==normalizeMoney(body.requested_amount,'Requested amount')||record.client_message!==clientText(body.message))throw unconfirmedClientResult();
 return record;
}
function verifyClientRenewalResult(result,{requestId,decision,signerId,cash=false,cancel=false,expectedRecord}) {
 const record=result?.request;
 if(!record||record.request_id!==requestId||['loan_id','client_id','requested_amount','approved_principal','renewal_offset_amount','net_release_amount','amount_locked_at'].some(key=>expectedRecord?.[key]!=null&&record[key]!==expectedRecord[key])||(decision&&record.client_decision!==decision)||(cancel&&record.status!=='cancelled')||(cash&&!recordedTime(record.client_cash_confirmed_at))||(signerId&&!asArray(record.signers).some(signer=>signer.signer_id===signerId&&signer.signed===true)))throw unconfirmedClientResult();
 return true;
}
function clientMutationKey(button) {
 for(const [attribute,kind]of [['data-client-renewal-cancel','cancel'],['data-client-renewal-decision-request','decision'],['data-client-renewal-sign-request','sign'],['data-client-renewal-cash-confirm','cash']]){const id=button.getAttribute(attribute);if(id)return `renewal:${kind}:${id}${kind==='sign'?':'+button.getAttribute('data-client-renewal-sign-signer'):''}`;}
 return null;
}
function syncClientMutationControls(context) {
 const mutations=context.clientMutations;if(!mutations)return;
 for(const button of context.root.querySelectorAll('button')){const key=clientMutationKey(button);if(key&&mutations.blocked(key))button.disabled=true;}
 const support=context.root.querySelector('#client-support-form');if(support&&mutations.blocked('support'))support.querySelector('button[type="submit"]').disabled=true;
 const renewal=context.root.querySelector('#client-renewal-form');
 if(renewal){
  const select=renewal.querySelector('[name="loanId"]');const ready=context.clientReads?.state('renewals').status==='ready';
  const eligible=ready?asArray(context.clientRaw?.renewals?.loans).filter(loan=>loan.eligible===true&&!loan.pending_request_id):[];
  select.disabled=!ready||!eligible.length;
  const selectionStatus=renewal.querySelector('[data-client-renewal-selection-status]');const missing=ready&&select.value&&!eligible.some(loan=>loan.loan_id===select.value);
  if(selectionStatus){selectionStatus.hidden=!missing;selectionStatus.textContent=missing?'The previously selected loan is no longer eligible. Choose another eligible loan before sending this draft.':'';}
  renewal.querySelector('button[type="submit"]').disabled=!eligible.some(loan=>loan.loan_id===select.value)||mutations.pending()||mutations.blocked('renewal:create:'+select.value);
 }
 const status=context.root.querySelector('[data-client-mutation-status]');if(status){status.hidden=!mutations.uncertain();status.textContent=mutations.uncertain()?'A submission could not be confirmed. Check the saved record with the office before trying again. Refresh reads do not authorize another attempt.':'';}
}
async function runClientMutation(context,key,operation,{remember=true}={}) {
 if(!context.clientIsCurrent?.()||!context.clientMutations.begin(key))return false;
 syncClientMutationControls(context);
 try{const result=await operation();if(!context.clientIsCurrent())return false;if(result===false){context.clientMutations.complete(key,{remember:false});return false;}context.clientMutations.complete(key,{remember});return result;}
 catch(error){if(context.clientIsCurrent()){context.clientMutations.fail(key,error);if([401,403].includes(error.status))context.clientCleanup?.();}throw error;}
 finally{if(context.clientIsCurrent?.())syncClientMutationControls(context);}
}
function currentClientRenewal(context,id){const record=asArray(context.clientRaw?.renewalWorkflow?.requests).find(record=>record.request_id===id)||asArray(context.clientRaw?.renewals?.requests).find(record=>record.request_id===id);return record?structuredClone(record):undefined;}

export async function requestClientRenewalCancellation({
  api,
  expectedRecord,signal,
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
  const result=await api.request(
    `/api/v1/client/renewals/${encodeURIComponent(normalized)}/cancel`,
    { method: 'POST',...(signal?{signal}:{}) },
  );
  return verifyClientRenewalResult(result,{requestId:normalized,cancel:true,expectedRecord});
}

export async function requestClientRenewalDecision({
  api,
  expectedRecord,signal,
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
  const result=await api.request(
    `/api/v1/client/renewals/${encodeURIComponent(normalizedId)}/decision`,
    { method: 'POST', body: { decision: normalizedDecision },...(signal?{signal}:{}) },
  );
  return verifyClientRenewalResult(result,{requestId:normalizedId,decision:normalizedDecision,expectedRecord});
}

export async function requestClientRenewalSignature({
  api,
  expectedRecord,signal,
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
  const result=await api.request(
    `/api/v1/renewals/${encodeURIComponent(normalizedRequest)}/signers/${encodeURIComponent(normalizedSigner)}/sign`,
    { method: 'POST', body: {},...(signal?{signal}:{}) },
  );
  return verifyClientRenewalResult(result,{requestId:normalizedRequest,signerId:normalizedSigner,expectedRecord});
}

export async function requestClientRenewalCashConfirmation({
  api,
  expectedRecord,signal,
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
  const result=await api.request(
    `/api/v1/client/renewals/${encodeURIComponent(normalized)}/cash-confirm`,
    { method: 'POST', body: {},...(signal?{signal}:{}) },
  );
  return verifyClientRenewalResult(result,{requestId:normalized,cash:true,expectedRecord});
}

function renderWorkspace(root, model, raw, errors) {
  const latestPayment = model.payments[0];
  const renewalLoans = asArray(raw.renewals.loans).filter((loan) => loan.eligible === true && !loan.pending_request_id);
  const homeSchedules = raw.homeObligationSchedules ?? {};
  const renderLoan = (loan) => loanCard(loan, homeSchedules[loan.loan_id] ?? null);
  const renewalsUnavailable = Boolean(errors.renewals || errors.renewalWorkflow);
  const dailyLinks = [
    ['client-loans', 'My loans', 'Open My loans to check your records.'],
    ['client-renewals', 'Renewal requests', 'Open renewal requests to check progress.'],
    ['client-payments', 'View receipts', 'Open receipts to check your payment history.'],
    ['client-payment-instructions', 'Payment options', 'See how you can pay.'],
    ['client-support', 'Ask for help', 'Open Support to check your requests.'],
  ];
  root.innerHTML = `<div data-client-mutation-status role="alert" hidden></div><section class="section-card" id="client-overview" data-workspace-section><header class="workspace-header">
    <div><p class="eyebrow">My account</p><h1>Today</h1><p>See your loans, payment records, and requests that need your attention.</p></div>
  </header>
  <div class="notice-card warning" data-client-home-read-status role="status" hidden></div>
  <div class="daily-actions">${dailyLinks.map(([target, label, detail]) => `<button class="task-link" type="button" data-nav-target="${target}"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(detail)}</span></button>`).join('')}</div>
  <div data-client-home-loans></div><section class="metric-grid" data-client-home-metrics>
    ${metricCard('Active loans', errors.loans ? 'Unavailable' : escapeHtml(model.activeLoanCount))}
    ${metricCard('Pending renewals', renewalsUnavailable ? 'Unavailable' : escapeHtml(model.pendingRenewalCount))}
    ${metricCard('Open support', errors.support ? 'Unavailable' : escapeHtml(model.openSupportCount))}
    ${metricCard('Latest receipt', errors.payments ? 'Unavailable' : latestPayment ? escapeHtml(latestPayment.receipt_number || 'Recorded') : 'None')}
  </section>
  </section>

  <section class="section-card" id="client-loans" data-workspace-section>
    <div class="section-heading"><div><h2>My loans</h2><p>See your balance, amount due, and schedule for each loan. Regular and 7x7 loans stay separate.</p></div></div>
    <div data-client-region="loans">${errors.loans ? errorCard(errors.loans) : model.allLoans.length ? `<div class="loan-grid">${model.regularLoans.map(renderLoan).join('')}${model.sevenBySevenLoans.map(renderLoan).join('')}${model.otherLoans.map(renderLoan).join('')}</div>` : emptyState('No linked loan is available on this account.')}</div>
  </section>

  <section class="section-card" id="client-payments" data-workspace-section>
    <div class="section-heading"><div><h2>Payments and official receipts</h2><p>A receipt appears only after SPINA accepts an official collection.</p></div></div>
    <div data-client-region="payments">${errors.payments ? errorCard(errors.payments) : paymentRows(model.payments)}</div>
  </section>

  <section class="section-card" id="client-statement" data-workspace-section>
    <div class="section-heading"><div><h2>Statement</h2><p>Your official loan and payment history.</p></div></div>
    <div data-client-region="statement">${errors.statement ? errorCard(errors.statement) : renderClientStatement(raw.statement)}</div>
  </section>

  <section class="section-card" id="client-documents" data-workspace-section><h2>Documents and record copies</h2><div data-client-documents></div></section>
  <section class="section-card" id="client-gcash-claims" data-workspace-section data-private-panel><div data-client-treasury-claims></div></section>
  <section class="section-card" id="client-payment-proofs" data-workspace-section><h2>Payment proof</h2><div data-client-payment-proofs></div></section>

  <section class="section-card" id="client-renewals" data-workspace-section>
    <div class="section-heading"><div><h2>Renewal requests</h2><p>Submit a request for review. Your permanently assigned Collector must recommend it before Management reviews and decides. Approval does not release cash until the required steps are complete.</p></div></div>
    <div data-client-region="renewals"></div>
    <details data-client-renewal-editor>
      <summary>Submit a renewal request</summary>
      <form id="client-renewal-form" class="entry-form">
        <label>Eligible loan<select name="loanId" required aria-describedby="client-renewal-selection-status">${renewalLoans.map((loan) => `<option value="${escapeHtml(loan.loan_id)}">${escapeHtml(loan.loan_number)} · ${escapeHtml(loan.loan_type_name)}</option>`).join('')}</select></label>
        <p class="meta" id="client-renewal-selection-status" data-client-renewal-selection-status role="status" hidden></p>
        <label>Requested amount<input name="requestedAmount" inputmode="decimal" required placeholder="0.00" /></label>
        <label>Message<textarea name="message" maxlength="1000" placeholder="Optional reason or request details"></textarea></label>
        <button class="button button-primary" type="submit">Send renewal request</button>
      </form>
    </details>

    <div data-client-region="renewalWorkflow"></div>
  </section>

  <section class="section-card" id="client-support" data-workspace-section>
    <div class="section-heading"><div><h2>Support</h2><p>Ask about a payment, loan, renewal, or account. Support messages do not change financial records.</p></div></div>
    <div data-client-region="support">${errors.support ? errorCard(errors.support) : supportRows(model.supportRequests)}</div>
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

  <section class="section-card" id="client-payment-instructions" data-workspace-section>
    <div class="section-heading"><div><h2>Payment instructions</h2><p>Choose an available payment option. Your payment becomes official after SPINA records it.</p></div></div>
    <div data-client-region="gcash"></div>
  </section>

  <section class="section-card" id="client-updates" data-workspace-section>
    <div class="section-heading"><div><h2>Updates</h2><p>Notices intended for your account only.</p></div></div>
    <div data-client-region="notifications">${errors.notifications ? errorCard(errors.notifications) : clientNotificationRows(model.notifications)}</div>
  </section>

  <section class="section-card" id="client-account" data-workspace-section>
    <div class="section-heading"><div><h2>Account and devices</h2><p>Review your SPINA profile and registered sessions.</p></div></div>
    <div data-client-region="account">${errors.account ? errorCard(errors.account) : clientAccountCard(model.account)}</div>
  </section>`;
}

function bindForms(context) {
 for(const [selector,key,path,fields]of [
 ['#client-renewal-form','renewals','/api/v1/client/renewals',{loanId:'loan_id',requestedAmount:'requested_amount',message:'message'}],
 ['#client-support-form','support','/api/v1/client/support',{category:'category',subject:'subject',message:'message',referenceText:'reference_text'}]]) {
  const form=context.root.querySelector(selector);
  if(key==='renewals')form?.querySelector('[name="loanId"]').addEventListener('change',()=>{if(context.clientIsCurrent())syncClientMutationControls(context);});
  form?.addEventListener('submit',async event=>{
   event.preventDefault();const button=form.querySelector('button[type="submit"]');if(button.disabled||!context.clientIsCurrent?.())return;
   if(globalThis.navigator?.onLine===false){showToast('Connect to the internet before sending.','error');return;}
   if(key==='renewals'&&context.clientMutations.pending())return;
   const data=new FormData(form);const snapshot=Object.fromEntries(Object.keys(fields).map(name=>[name,String(data.get(name)||'')]));
   if(key==='renewals'&&(context.clientReads.state('renewals').status!=='ready'||!asArray(context.clientRaw.renewals.loans).some(loan=>loan.loan_id===snapshot.loanId&&loan.eligible===true&&!loan.pending_request_id))){showToast('Refresh renewal eligibility before submitting this draft.','error');return;}
   const submittedClientId=context.clientRaw[key]?.client?.client_id||context.clientRaw.loans?.client?.client_id;
   const mutationKey=key==='support'?'support':'renewal:create:'+snapshot.loanId;if(!context.clientMutations.begin(mutationKey))return;setButtonBusy(button,true,'Sending…');let saved=false;
   try {
    const body=Object.fromEntries(Object.entries(fields).map(([name,field])=>[field,snapshot[name].trim()]));if(key==='renewals')normalizeMoney(body.requested_amount,'Requested amount');const submitted=await context.api.request(path,{method:'POST',body,signal:context.clientSignal});if(!context.clientIsCurrent())return;verifyClientCreatedRequest(submitted,{kind:key==='support'?'support':'renewal',body,clientId:submittedClientId});context.clientMutations.complete(mutationKey,{remember:key==='renewals'});
    if(!context.clientIsCurrent())return;saved=true;
    for(const name of Object.keys(fields)){const field=form.querySelector(`[name="${name}"]`);if(field&&field.value===snapshot[name]&&field.tagName!=='SELECT'&&name!=='category'&&name!=='loanId')field.value='';}
    await refreshClientSavedRecords(context,key==='renewals'?['renewals','renewalWorkflow']:['support'],key==='support'?'Support request sent.':'Renewal request sent. Your assigned Collector must recommend it before Management review.');
   }catch(error){if(context.clientIsCurrent()){if(!saved)context.clientMutations.fail(mutationKey,error);if([401,403].includes(error.status)){context.clientCleanup();return;}showToast(saved?'Saved; refreshing records failed.':error.message,'error');}}
   finally{if(context.clientIsCurrent()){setButtonBusy(button,false);syncClientMutationControls(context);}else clearButtonBusyFocus(button);}
  });
 }
}

function bindClientAccountDeviceSecurity(context) {
  for (const button of context.root.querySelectorAll('[data-client-revoke-device]')) {
    button.addEventListener('click', async () => {
      if(button.disabled||!context.clientIsCurrent?.()||globalThis.navigator?.onLine===false)return;
      const deviceId = button.dataset.clientRevokeDevice;
      button.disabled=true;
      try {
        const revoked = await requestClientDeviceRevocation({
          api: context.api,
          deviceId,
        });
        if(!context.clientIsCurrent())return;
        if (!revoked) {button.disabled=false;return;}
        showToast('Device access revoked.', 'success');
        await refreshClientRegion(context, 'account');
      } catch (error) {
        if(context.clientIsCurrent()) {if([401,403].includes(error.status)){context.clientCleanup();return;}showToast(error.message, 'error');button.disabled=false;}
      }
    });
  }
}

function bindClientNotificationReadActions(context) {
  const signal=context.signal,generation=context.clientWorkspaceGeneration,pending=context.clientNotificationPending;
  const currentMount=()=>!signal?.aborted&&context.clientWorkspaceGeneration===generation&&context.clientIsCurrent();
  const currentButton=id=>{const button=context.root.querySelector(`[data-client-notification-read="${id}"]`);return button?.isConnected?button:null;};
  for(const button of context.root.querySelectorAll('[data-client-notification-read]')){
    const notificationId=button.dataset.clientNotificationRead;
    if(pending.has(notificationId))setButtonBusy(button,true,'Marking…');
    button.addEventListener('click',async()=>{
      if(button.disabled||button.hidden||pending.has(notificationId)||!currentMount()||currentButton(notificationId)!==button||globalThis.navigator?.onLine===false)return;
      const ownItem=()=>asArray(context.clientRaw?.notifications).find(note=>note.notification_id===notificationId&&note.recipient_user_id===(context.getSession?.()??context.session)?.user?.id);
      const itemBefore=ownItem();if(!itemBefore||itemBefore.is_read===true)return;
      let saved=false;pending.add(notificationId);setButtonBusy(button,true,'Marking…');
      try{
        const result=await requestClientNotificationRead({api:context.api,notificationId});
        if(!currentMount())return;
        if(result?.notification_id!==notificationId||result.is_read!==true||result.recipient_user_id!==(context.getSession?.()??context.session)?.user?.id)throw new Error('The update could not be confirmed as read. Refresh Updates before trying again.');
        const item=ownItem();if(!item)return;
        saved=true;item.is_read=true;
        const target=currentButton(notificationId);
        const status=target?.parentElement.querySelector('[data-client-notification-status]');if(status)status.innerHTML=badge('Read','success');
        const count=context.root.querySelector('[data-client-updates-count]');if(count)count.textContent=clientNotificationCount(asArray(context.clientRaw?.notifications));
        showToast('Update marked as read.','success');
      }catch(error){
        if(currentMount()&&[401,403].includes(error.status)){context.clientCleanup();return;}
        if(currentMount()&&ownItem())showToast(error.message,'error');
      }finally{
        pending.delete(notificationId);
        if(currentMount()){
          const target=currentButton(notificationId);if(target!==button)clearButtonBusyFocus(button);
          if(target){setButtonBusy(target,false);
            if(saved){
              if(target===button&&target.ownerDocument.activeElement===target&&!target.closest('[hidden]'))target.parentElement.querySelector('[data-client-notification-status]').focus({preventScroll:true});
              target.hidden=true;
            }
          }
        }else clearButtonBusyFocus(button);
      }
    });
  }
}

function bindClientRenewalCancellation(context) {
  for (const button of context.root.querySelectorAll('[data-client-renewal-cancel]')) {
    button.addEventListener('click', async () => {
      if(button.disabled||!context.clientIsCurrent?.()||globalThis.navigator?.onLine===false)return;
      const requestId = button.dataset.clientRenewalCancel;
      button.disabled=true;
      try {
        const cancelled = await runClientMutation(context,clientMutationKey(button),()=>requestClientRenewalCancellation({
          api: context.api,expectedRecord:currentClientRenewal(context,requestId),signal:context.clientSignal,
          requestId,
        }));
        if(!context.clientIsCurrent())return;
        if (!cancelled) {button.disabled=false;syncClientMutationControls(context);return;}
        await refreshClientSavedRecords(context,['renewals','renewalWorkflow'],'Renewal request cancelled.');
      } catch (error) {
        if(context.clientIsCurrent()) {showToast(error.message, 'error');button.disabled=false;syncClientMutationControls(context);}
      }
    });
  }
}

function bindClientRenewalWorkflowActions(context) {
  for (const button of context.root.querySelectorAll('[data-client-renewal-decision-request]')) {
    button.addEventListener('click', async () => {
      if(button.disabled||!context.clientIsCurrent?.()||globalThis.navigator?.onLine===false)return;
      const requestId = button.dataset.clientRenewalDecisionRequest;
      const decision = button.dataset.clientRenewalDecision;
      setButtonBusy(button, true, decision === 'accepted' ? 'Accepting…' : 'Declining…');
      try {
        const acted = await runClientMutation(context,clientMutationKey(button),()=>requestClientRenewalDecision({
          api: context.api,expectedRecord:currentClientRenewal(context,requestId),signal:context.clientSignal,
          requestId,
          decision,
        }));
        if(!context.clientIsCurrent())return;
        if (!acted) {
          setButtonBusy(button, false);syncClientMutationControls(context);
          return;
        }
        await refreshClientSavedRecords(context,['renewals','renewalWorkflow'],decision === 'accepted' ? 'Renewal accepted. Complete your own signer step next.' : 'Renewal declined.');
      } catch (error) {
        if(context.clientIsCurrent()) {showToast(error.message, 'error');setButtonBusy(button, false);syncClientMutationControls(context);}
        else clearButtonBusyFocus(button);
      }
    });
  }

  for (const button of context.root.querySelectorAll('[data-client-renewal-sign-request]')) {
    button.addEventListener('click', async () => {
      if(button.disabled||!context.clientIsCurrent?.()||globalThis.navigator?.onLine===false)return;
      const requestId = button.dataset.clientRenewalSignRequest;
      const signerId = button.dataset.clientRenewalSignSigner;
      setButtonBusy(button, true, 'Signing…');
      try {
        const signed = await runClientMutation(context,clientMutationKey(button),()=>requestClientRenewalSignature({
          api: context.api,expectedRecord:currentClientRenewal(context,requestId),signal:context.clientSignal,
          requestId,
          signerId,
        }));
        if(!context.clientIsCurrent())return;
        if (!signed) {
          setButtonBusy(button, false);syncClientMutationControls(context);
          return;
        }
        await refreshClientSavedRecords(context,['renewals','renewalWorkflow'],'Your renewal signature was recorded.');
      } catch (error) {
        if(context.clientIsCurrent()) {showToast(error.message, 'error');setButtonBusy(button, false);syncClientMutationControls(context);}
        else clearButtonBusyFocus(button);
      }
    });
  }

  for (const button of context.root.querySelectorAll('[data-client-renewal-cash-confirm]')) {
    button.addEventListener('click', async () => {
      if(button.disabled||!context.clientIsCurrent?.()||globalThis.navigator?.onLine===false)return;
      const requestId = button.dataset.clientRenewalCashConfirm;
      setButtonBusy(button, true, 'Confirming…');
      try {
        const confirmed = await runClientMutation(context,clientMutationKey(button),()=>requestClientRenewalCashConfirmation({
          api: context.api,expectedRecord:currentClientRenewal(context,requestId),signal:context.clientSignal,
          requestId,
        }));
        if(!context.clientIsCurrent())return;
        if (!confirmed) {
          setButtonBusy(button, false);syncClientMutationControls(context);
          return;
        }
        await refreshClientSavedRecords(context,['renewals','renewalWorkflow'],'Cash receipt confirmed.');
      } catch (error) {
        if(context.clientIsCurrent()) {showToast(error.message, 'error');setButtonBusy(button, false);syncClientMutationControls(context);}
        else clearButtonBusyFocus(button);
      }
    });
  }
}

export function refreshClientRegion(context,key) {return context.clientLoad?.(key,{refresh:true})??Promise.resolve({status:'idle',data:null,error:null,revision:0});}

async function refreshClientSavedRecords(context,keys,message) {
  let failed=false;
  for(const key of keys){
    if(!context.clientIsCurrent())return;
    try{const result=await refreshClientRegion(context,key);failed=result.status!=='ready'||failed;}
    catch{failed=true;}
  }
  if(context.clientIsCurrent())showToast(failed?'Saved; refreshing records failed. Use Refresh to read the saved records.':message,'success');
}

function authorityScope(session) {return JSON.stringify([session?.user?.id,session?.user?.role,session?.user?.client_id,session?.client_id,session?.device?.id,session?.device_id,session?.permissions,session?.user?.permissions]);}
export async function mountClientWorkspace(context) {
 if(context.signal?.aborted)return;context.clientCleanup?.();
 const generation=(context.clientWorkspaceGeneration??0)+1;context.clientWorkspaceGeneration=generation;
 const {root,api:originalApi,setNavigation}=context;const scope=authorityScope(context.getSession?.()??context.session);const controller=new AbortController();let disposed=false,visible='client-overview',notificationsLimit=30,renewalView='current';const childCleanups=[];const notificationPending=new Set();context.clientNotificationPending=notificationPending;childCleanups.push(()=>notificationPending.clear());const initialized=new Set();const mutations=createClientMutationController();context.clientMutations=mutations;let treasuryHandle=null;const treasuryGate=createTreasuryRoleGate(originalApi,{isTreasuryPending:()=>treasuryHandle?.isWritePending()===true,isRolePending:()=>mutations.pending()||mutations.uncertain()||context.clientProofHandle?.isUncertain()===true,getRoleWriteOwner:path=>path.startsWith('/api/v1/client/payment-proofs')&&context.clientProofHandle?{isWritePending:()=>context.clientProofHandle.isUncertain()}:{isWritePending:()=>mutations.pending()||mutations.uncertain()}}),api=treasuryGate.api;context.api=api;
 const current=()=>{const session=context.getSession?context.getSession():context.session;const ok=!disposed&&!context.signal?.aborted&&context.clientWorkspaceGeneration===generation&&(!context.getSession||session!==null)&&authorityScope(session)===scope;if(!ok&&!disposed)dispose();return ok;};
 function dispose(){
  if(disposed)return;disposed=true;
  if(context.clientWorkspaceGeneration===generation){
   // Clear private values before child abort handlers detach their editors.
   for(const selector of ['input','textarea','select'])for(const field of root.querySelectorAll(selector)){field.value='';field.checked=false;field.disabled=true;}
   for(const button of root.querySelectorAll('button')){button.disabled=true;clearButtonBusyFocus(button);}
  }
  controller.abort();mutations.dispose();reads.dispose();for(const cleanup of childCleanups)cleanup?.();context.clientDocumentCleanup?.();context.clientProofCleanup?.();context.clientScheduleCleanup?.();if(context.clientWorkspaceGeneration===generation){context.beforeTaskChange?.();root.innerHTML='';context.afterTaskChange?.();}context.signal?.removeEventListener('abort',dispose);
 }
 context.clientCleanup=dispose;context.clientSignal=controller.signal;context.clientIsCurrent=current;
 const sections=[['client-overview','Today'],['client-loans','My loans'],['client-renewals','Renewal requests'],['client-payment-instructions','Payment options'],['client-payment-proofs','Payment proof'],['client-gcash-claims','GCash proof & status'],['client-support','Ask for help'],['client-payments','Payments & receipts'],['client-statement','Statement'],['client-documents','Documents'],['client-updates','Updates'],['client-account','Account & devices']];setNavigation(sections.map(([id,label])=>({id,label,group:['client-account'].includes(id)?'Administration':['client-payments','client-statement','client-documents','client-updates'].includes(id)?'Records':'Daily work'})));
 const raw={account:{},loans:{loans:[]},payments:{payments:[]},statement:{},renewals:{loans:[],requests:[]},renewalWorkflow:{requests:[]},support:{requests:[]},gcash:{},notifications:[],homeObligationSchedules:{}};context.clientRaw=raw;
 const homeSources=['loans','payments','renewals','renewalWorkflow','support'];
 let scheduleView=null,gcashHandle=null,paymentDetailsCleanup=null,statementCopyController=null;
 childCleanups.push(()=>gcashHandle?.dispose(),()=>paymentDetailsCleanup?.(),()=>statementCopyController?.abort());
 const reads=createClientReadController({signal:controller.signal,isCurrent:current,onChange:(key,state)=>{if(!current())return;if(state.status==='error'&&[401,403].includes(state.error?.status)){dispose();return;}if(key.startsWith('schedule:')){const id=key.slice(9);updateLoanSummary(id,state);scheduleView?.renderState(id);return;}if(state.status==='ready')raw[key]=state.data;renderRegion(key);if(homeSources.includes(key))renderHomeCopy();if(key==='loans'&&initialized.has('gcash'))renderRegion('gcash');}});context.clientReads=reads;
 let linkedClientId=null;
 const paths={account:'/api/v1/account',loans:'/api/v1/client/loans',payments:'/api/v1/client/payments',statement:'/api/v1/client/statement',renewals:'/api/v1/client/renewals',renewalWorkflow:'/api/v1/client/renewal-workflow',support:'/api/v1/client/support',gcash:'/api/v1/client/gcash/config',notifications:'/api/v1/activity-notifications'};
 function unavailable(key){const state=reads.state(key);return state.status==='error'?`<div class="notice-card warning"><strong>${escapeHtml(key)} records unavailable</strong>${errorCard(state.error)}<button class="button button-secondary" type="button" data-client-retry="${key}">Retry</button></div>`:loadingPanel(`Loading ${key} records…`);}
 function setRegion(key,html){const region=root.querySelector(`[data-client-region="${key}"]`);if(!region)return;if(key==='notifications')for(const button of region.querySelectorAll('[data-client-notification-read]'))clearButtonBusyFocus(button);context.beforeTaskChange?.();region.innerHTML=html;context.afterTaskChange?.();for(const b of region.querySelectorAll('[data-client-retry]'))b.addEventListener('click',()=>load(key,{refresh:true}));}
 function updateLoanSummary(id,state){raw.homeObligationSchedules[id]=state;for(const node of root.querySelectorAll('[data-client-loan-summary]'))if(node.getAttribute('data-client-loan-summary')===id){context.beforeTaskChange?.();node.innerHTML=classifyLoanType(asArray(raw.loans.loans).find(l=>l.loan_id===id)?.loan_type_name??asArray(raw.loans.loans).find(l=>l.loan_id===id)?.loan_type_code)==='seven-by-seven'?renderClientPayoff(state):'';context.afterTaskChange?.();}renderHome();}
 function renderHomeCopy(){
  const overview=root.querySelector('#client-overview'),actions=overview?.querySelector('.daily-actions');if(!actions)return;
  const model=buildClientViewModel(raw);
  const detail=(key,idle,ready,label)=>{const status=reads.state(key).status;return status==='ready'?ready:status==='error'?`${label} unavailable — open this task to retry.`:status==='loading'?`Loading ${label.toLowerCase()}…`:idle;};
  const renewalState=reads.state('renewals'),workflowState=reads.state('renewalWorkflow');
  const renewalReady=renewalState.status==='ready'&&workflowState.status==='ready';
  const actionCount=renewalReady?clientRenewalPresentation({requestsState:renewalState,workflowState}).cards.filter(card=>card.workflow&&Object.values(clientRenewalActions({...card.request,...card.workflow},asArray(card.workflow.signers).find(signer=>signer.party_role==='borrower'))).some(Boolean)).length:0;
  const renewalDetail=[renewalState,workflowState].some(state=>state.status==='error')?'Renewals unavailable — open requests to retry.':[renewalState,workflowState].some(state=>state.status==='loading')?'Loading renewal records…':renewalReady?(actionCount?`${actionCount} action${actionCount===1?'':'s'} for you`:model.pendingRenewalCount?`${model.pendingRenewalCount} pending`:'Review your renewal requests.'):'Open renewal requests to check progress.';
  for(const [target,label,text]of [
   ['client-loans','My loans',detail('loans','Open My loans to check your records.',model.allLoans.length?'See your balance, amount due, and schedule.':'No linked loan is recorded.','Loans')],
   ['client-payments','View receipts',detail('payments','Open receipts to check your payment history.',model.payments.length?'Review your payment history.':'No official receipt yet.','Payments')],
   ['client-renewals',renewalReady&&(actionCount||model.pendingRenewalCount)?'Continue a renewal':'Renewal requests',renewalDetail],
   ['client-support','Ask for help',detail('support','Open Support to check your requests.',model.openSupportCount?`${model.openSupportCount} open request${model.openSupportCount===1?'':'s'}`:'Send a question to the office.','Support')],
  ]){const button=actions.querySelector(`[data-nav-target="${target}"]`);if(button){button.querySelector('strong').textContent=label;button.querySelector('span').textContent=text;}}
  const notice=overview.querySelector('[data-client-home-read-status]');if(notice){const failed=homeSources.some(key=>reads.state(key).status==='error');notice.hidden=!failed;notice.textContent=failed?'Some records could not load. Open the task to retry before deciding there is no action needed.':'';}
 }
 function renderHome(){const state=reads.state('loans');const loans=state.status==='ready'?asArray(raw.loans.loans).filter(l=>String(l.status||l.loan_status).toLowerCase()==='active'):[];const node=root.querySelector('[data-client-home-loans]');if(node)node.innerHTML=state.status==='ready'?(loans.length?loans.map(loan=>{const scheduleState=reads.state(`schedule:${loan.loan_id}`);const guidance=clientInstallmentGuidance({loan,scheduleState,today:manilaToday()});return `<article class="notice-card"><strong>${escapeHtml(loan.loan_number||'Loan')}</strong><p>Agreed installment ${formatAuthoritativeMoney(loan.daily_amount)}</p><p>${escapeHtml(guidance.status==='stale'?'Schedule date changed. Refresh before using the current amount.':guidance.message)}</p>${classifyLoanType(loan.loan_type_name??loan.loan_type_code)==='seven-by-seven'?renderClientPayoff(reads.state(`schedule:${loan.loan_id}`)):''}${scheduleState.status==='ready'?`<p>Server past due ${guidance.pastDueAmount===null?'Unavailable':formatAuthoritativeMoney(guidance.pastDueAmount)} · ${escapeHtml(guidance.pastDueCount??'Unavailable')} rows</p>`:''}<button class="button button-secondary" type="button" data-nav-target="client-loans">Open schedule</button></article>`;}).join(''):emptyState('No active loan is recorded.')):unavailable('loans');const metrics=root.querySelector('[data-client-home-metrics]');if(metrics){const renewalReady=reads.state('renewals').status==='ready';const count=asArray(raw.renewals.requests).filter(r=>r.status==='pending').length;metrics.innerHTML=metricCard('Active loans',state.status==='ready'?String(loans.length):'Unavailable')+metricCard('Pending renewals',renewalReady?String(count):'Unavailable');}}
 function documents(){if(!initialized.has('documents')||!root.querySelector('[data-client-documents]'))return;context.clientDocumentCleanup?.();context.clientDocumentCleanup=mountClientDocuments({root:root.querySelector('[data-client-documents]'),api,loansState:reads.state('loans'),paymentsState:reads.state('payments'),onRetry:key=>load(key,{refresh:true}),signal:controller.signal});}
 function renderRegion(key){const state=reads.state(key);if(key==='loans'){const region=root.querySelector('[data-client-region="loans"]');const cards=region?.querySelectorAll('.loan-card')||[];const ids=Array.from(cards).map(card=>card.querySelector('[data-client-schedule-loan]')?.getAttribute('data-client-schedule-loan'));if(cards.length&&state.status==='loading'){for(const card of cards)card.querySelector('[data-client-schedule-loan]').disabled=true;renderHome();return;}if(cards.length&&state.status==='ready'&&JSON.stringify(ids)===JSON.stringify(asArray(raw.loans.loans).map(l=>l.loan_id))){for(const card of cards){const id=card.querySelector('[data-client-schedule-loan]').getAttribute('data-client-schedule-loan');const loan=asArray(raw.loans.loans).find(l=>l.loan_id===id);const temporary=card.ownerDocument.createElement('div');temporary.innerHTML=loanCard(loan,reads.state(`schedule:${id}`));context.beforeTaskChange?.();card.querySelector('.loan-meta').innerHTML=temporary.querySelector('.loan-meta').innerHTML;card.querySelector('.section-heading').innerHTML=temporary.querySelector('.section-heading').innerHTML;card.querySelector('[data-client-schedule-loan]').disabled=false;context.afterTaskChange?.();}renderHome();documents();return;}childCleanups.push(context.clientScheduleCleanup);context.clientScheduleCleanup?.();setRegion('loans',state.status==='ready'?asArray(raw.loans.loans).map(loan=>loanCard(loan,reads.state(`schedule:${loan.loan_id}`))).join('')||emptyState('No linked loan is available on this account.'):unavailable(key));context.clientScheduleCleanup=bindClientScheduleButtons({...context,signal:controller.signal,onController:handle=>scheduleView=handle});renderHome();documents();return;}
 if(key==='payments'){paymentDetailsCleanup?.();setRegion(key,state.status==='ready'?paymentRows(asArray(raw.payments.payments)):unavailable(key));paymentDetailsCleanup=bindClientPaymentDetails({root,paymentsState:()=>reads.state('payments'),onDownload:async(id,{signal})=>{
  try{await downloadClientRecordCopy({api,kind:'payment',transactionId:id,signal,isCurrent:current});}
  catch(error){if(current()&&[401,403].includes(error?.status))dispose();throw error;}
 },signal:controller.signal,isCurrent:current,beforeTaskChange:context.beforeTaskChange,afterTaskChange:context.afterTaskChange});documents();if(reads.state('notifications').status==='ready')renderRegion('notifications');return;}
 if(key==='renewals'){
  renderRenewals();const select=root.querySelector('#client-renewal-form')?.querySelector('[name="loanId"]');
  if(select&&state.status==='ready'){
   const selected=select.value;const eligible=asArray(raw.renewals.loans).filter(loan=>loan.eligible===true&&!loan.pending_request_id);
   const missing=selected&&!eligible.some(loan=>loan.loan_id===selected);
   select.innerHTML='<option value="">Choose an eligible loan</option>'+(missing?`<option value="${escapeHtml(selected)}" disabled>Previous loan unavailable</option>`:'')+eligible.map(loan=>`<option value="${escapeHtml(loan.loan_id)}">${escapeHtml(loan.loan_number||'Loan')}</option>`).join('');
   select.value=selected;
  }
  syncClientMutationControls(context);return;
 }
 if(key==='renewalWorkflow'){renderRenewals();return;}
 if(key==='gcash'){if(!initialized.has('gcash'))return;if(root.querySelector('#client-gcash-form')){gcashHandle?.updateReadState();return;}gcashHandle?.dispose();setRegion(key,renderClientGcashPanel({capability:state.data,capabilityState:state,loans:asArray(raw.loans.loans),loansState:reads.state('loans')}));gcashHandle=bindClientGcashPanel({...context,signal:controller.signal});return;}
 if(key==='statement'){statementCopyController?.abort();statementCopyController=null;}
 const renderers={account:()=>clientAccountCard(raw.account),statement:()=>renderClientStatement(raw.statement),support:()=>supportRows(asArray(raw.support.requests)),notifications:()=>clientNotificationRows(raw.notifications,{visibleLimit:notificationsLimit,authorizedRecords:{userId:(context.getSession?.()??context.session)?.user?.id,payments:reads.state('payments').status==='ready'?asArray(raw.payments.payments):[]}})};if(renderers[key])setRegion(key,state.status==='ready'?renderers[key]():unavailable(key));if(key==='statement'){
  const button=root.querySelector('[data-client-statement-copy]'),status=root.querySelector('[data-client-statement-download-status]');
  if(button){const copyController=new AbortController();statementCopyController=copyController;let downloading=false;
   const currentView=()=>!copyController.signal.aborted&&current();
   button.addEventListener('click',async()=>{
    if(!currentView()||downloading)return;downloading=true;button.disabled=true;status.textContent='';
    try{await downloadClientRecordCopy({api,kind:'statement',signal:copyController.signal,isCurrent:current});}
    catch(error){if(current()&&[401,403].includes(error?.status))dispose();else if(currentView())status.textContent=error.message;}
    finally{if(currentView()){downloading=false;button.disabled=false;}}
   });
  }
 }if(key==='account')bindClientAccountDeviceSecurity(context);if(key==='notifications'){bindClientNotificationReadActions(context);for(const button of root.querySelectorAll('[data-client-notification-payment]'))button.addEventListener('click',async()=>{if(!current())return;const id=button.getAttribute('data-client-notification-payment');if(reads.state('payments').status!=='ready'||!asArray(raw.payments.payments).some(p=>p.transaction_id===id))return;context.navigateTo?.('client-payments');await activate('client-payments');root.querySelector(`[data-payment-details="${id}"]`)?.click?.();});const more=root.querySelector('[data-client-updates-more]');more?.addEventListener('click',()=>{if(!current()||root.querySelector('[data-client-updates-more]')!==more)return;const focused=more.ownerDocument.activeElement===more;notificationsLimit+=30;renderRegion('notifications');if(focused)(root.querySelector('[data-client-updates-more]')||root.querySelector('[data-client-updates-count]'))?.focus({preventScroll:true});});}}
 function renderRenewals(){renderHome();
 const presentation=clientRenewalPresentation({eligibilityState:reads.state('renewals'),requestsState:reads.state('renewals'),workflowState:reads.state('renewalWorkflow'),view:renewalView});
 const tabs=`<div class="inline-actions">${['current','eligibility','history'].map(view=>`<button class="button button-secondary" type="button" data-client-renewal-view="${view}" aria-pressed="${renewalView===view}">${view==='current'?'Current requests':view==='eligibility'?'Eligibility':'History'}</button>`).join('')}</div>`;
 const content=renewalView==='eligibility'?(reads.state('renewals').status==='ready'?clientRenewalEligibilityRows(asArray(raw.renewals.loans)):unavailable('renewals')):presentation.status!=='ready'?unavailable('renewals'):presentation.cards.length?presentation.cards.map(card=>`<div data-client-renewal-record="${escapeHtml(card.request.request_id)}"><p class="notice-card"><strong>Next step:</strong> ${escapeHtml(card.nextStep)}</p>${card.workflow?clientRenewalWorkflowRows([{...card.request,...card.workflow}]):clientRenewalRows([card.request],{readOnly:card.conflict})}</div>`).join(''):emptyState(renewalView==='history'?'No completed renewal request is loaded.':'No current renewal request is loaded.');
 setRegion('renewals',tabs+content);setRegion('renewalWorkflow','');for(const button of root.querySelectorAll('[data-client-renewal-view]'))button.addEventListener('click',()=>{const view=button.getAttribute('data-client-renewal-view');if(!current()||root.querySelector(`[data-client-renewal-view="${view}"]`)!==button)return;const focused=button.ownerDocument.activeElement===button;renewalView=view;renderRenewals();if(focused)root.querySelector(`[data-client-renewal-view="${view}"]`)?.focus({preventScroll:true});});bindClientRenewalCancellation(context);bindClientRenewalWorkflowActions(context);syncClientMutationControls(context);
 }
 const load=(key,options)=>{if(!current()||!paths[key]||(key==='notifications'&&notificationPending.size))return Promise.resolve(reads.state(key));return reads.load(key,async({signal})=>{const value=await api.request(paths[key],{signal});const arrays={loans:'loans',payments:'payments',renewals:'requests',renewalWorkflow:'requests',support:'requests'};if(arrays[key]&&!Array.isArray(value?.[arrays[key]]))throw Error('The protected records response is incomplete. Retry this read.');if(key==='gcash'&&!validClientGcashCapability(value))throw Error('Payment configuration unavailable. Retry this read.');if(key==='notifications'&&!Array.isArray(value))throw Error('The updates response is incomplete.');if(key==='notifications'){const userId=(context.getSession?.()??context.session)?.user?.id;if(userId&&value.some(item=>item.recipient_user_id!==userId))throw Error('The updates do not match this account.');}if(['loans','payments','statement'].includes(key)&&value?.client?.client_id){if(linkedClientId&&value.client.client_id!==linkedClientId){dispose();throw Error('The linked borrower changed. Sign in again.');}linkedClientId=value.client.client_id;}return value;},options);};context.clientLoad=load;
 const schedules=createClientScheduleController({api,reads,signal:controller.signal,isCurrent:current});context.clientSchedules=schedules;childCleanups.push(()=>schedules.dispose());
 renderWorkspace(root,buildClientViewModel(raw),raw,Object.fromEntries(Object.keys(paths).map(key=>[key,Error('Loading records…')])));for(const key of Object.keys(paths))renderRegion(key);bindForms(context);context.activateNavigation?.();
 const dependencies={'client-overview':['account','loans'],'client-loans':['loans'],'client-payments':['payments'],'client-statement':['statement'],'client-renewals':['renewals','renewalWorkflow'],'client-support':['support'],'client-updates':['notifications','payments'],'client-account':['account'],'client-documents':['loans','payments'],'client-payment-instructions':['loans','gcash'],'client-payment-proofs':['loans'],'client-gcash-claims':['loans']};
 async function activate(id){if(!current())return;visible=id;const keys=dependencies[id]||[];const pending=keys.map(key=>load(key));if(id==='client-gcash-claims'&&!treasuryHandle){await Promise.all(pending);if(!current()||reads.state('loans').status!=='ready'||!linkedClientId)return;const target=root.querySelector('[data-client-treasury-claims]');if(!target)return;treasuryHandle=mountTreasuryClaim({root:target,api,getSession:()=>context.getSession?context.getSession():context.session,signal:controller.signal,mode:'client',borrowerContext:()=>({client_id:linkedClientId,loans:asArray(raw.loans.loans)}),beforeTaskChange:context.beforeTaskChange,afterTaskChange:context.afterTaskChange,canStartWrite:treasuryGate.canStartWrite});childCleanups.push(treasuryHandle);await treasuryHandle.ready;}if(id==='client-documents'){initialized.add('documents');documents();}if(id==='client-payment-instructions'&&!initialized.has('gcash')){initialized.add('gcash');renderRegion('gcash');}if(id==='client-payment-proofs'&&!initialized.has('proofs')){initialized.add('proofs');await Promise.all(pending);if(!current())return;if(!root.querySelector('[data-client-payment-proofs]'))return;context.clientProofCleanup=mountPaymentProofs({root:root.querySelector('[data-client-payment-proofs]'),api,loans:asArray(raw.loans.loans),loansState:reads.state('loans'),getLoansState:()=>reads.state('loans'),signal:controller.signal,registerHandle:h=>context.clientProofHandle=h});}}
 async function refreshVisible(){if(!current())return;if(visible==='client-updates'&&notificationPending.size){showToast('An update is being marked as read. Refresh after it finishes.','warning');return false;}if(treasuryHandle?.isWritePending()||treasuryGate.isWritePending())return false;if(visible==='client-gcash-claims')return treasuryHandle?.refreshReadOnly();if(mutations.pending()){showToast('A submission is pending. Refresh after it finishes; your drafts are retained.','warning');return false;}if(visible==='client-payment-proofs'){await context.clientProofHandle?.refreshReadOnly();return;}const results=await Promise.all((dependencies[visible]||[]).map(key=>load(key,{refresh:true})));if(['client-overview','client-loans'].includes(visible))for(const loan of asArray(raw.loans.loans))if(String(loan.status||loan.loan_status).toLowerCase()==='active')void schedules.load(loan.loan_id,{refresh:true});return results;}
 let displayDay=manilaToday();const rollover=setInterval(()=>{if(!current())return;const day=manilaToday();if(day!==displayDay){displayDay=day;renderHome();}},30000);rollover.unref?.();childCleanups.push(()=>clearInterval(rollover));
 context.registerWorkspaceHandle?.({activate,refreshVisible,dispose,isWritePending:()=>treasuryHandle?.isWritePending()||treasuryGate.isWritePending()||mutations.pending()||context.clientProofHandle?.isUncertain()||root.querySelector('#client-support-form')?.querySelector('button[type="submit"]')?.disabled===true});context.signal?.addEventListener('abort',dispose,{once:true});
 void load('account');void load('loans').then(state=>{if(state.status!=='ready'||!current())return;void loadClientHomeObligationSchedules(api,state.data,schedules);for(const loan of asArray(state.data.loans))if(String(loan.status||loan.loan_status).toLowerCase()==='active')void schedules.load(loan.loan_id);});void load('notifications');
 if(!context.registerWorkspaceHandle)for(const [id]of sections)void activate(id);
 return dispose;
}

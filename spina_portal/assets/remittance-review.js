import { asArray, badge, emptyState, escapeHtml, hasPermission } from './ui.js';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const money = (value) => typeof value === 'string' && /^(0|[1-9]\d*)\.\d{2}$/.test(value);
const text = (value) => typeof value === 'string' && value.length > 0;
const date = (value) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
const count = (value) => Number.isSafeInteger(value) && value >= 0;

function reviewable(notice, actorId) {
  return UUID.test(actorId) && UUID.test(notice?.notification_id) && UUID.test(notice?.remittance_id)
    && notice.recipient_user_id === actorId && UUID.test(notice.sender_user_id)
    && notice.sender_user_id !== actorId && notice.status === 'pending' && notice.is_pending === true;
}

function validDetail(record, notice, actorId) {
  return record?.remittance_id === notice.remittance_id && record.recipient_user_id === actorId
    && record.collector_user_id === notice.sender_user_id && record.collector_user_id !== actorId
    && record.status === 'submitted' && text(record.remittance_number)
    && date(record.collection_date) && money(record.total_amount)
    && count(record.transaction_count) && record.transaction_count > 0
    && Array.isArray(record.items) && record.items.length === record.transaction_count
    && new Set(record.items.map((item) => item?.transaction_id)).size === record.items.length
    && record.items.every((item) => UUID.test(item?.transaction_id) && UUID.test(item.client_id)
      && UUID.test(item.loan_id) && text(item.client_name) && text(item.loan_type)
      && date(item.collection_date) && text(item.entry_type) && money(item.amount)
      && text(item.receipt_number) && Array.isArray(item.covered_dates) && item.covered_dates.every(date))
    && count(record.refund_due_release_count) && money(record.refund_due_release_total)
    && Array.isArray(record.refund_due_releases)
    && record.refund_due_releases.length === record.refund_due_release_count
    && new Set(record.refund_due_releases.map((item) => item?.release_id)).size === record.refund_due_releases.length
    && record.refund_due_releases.every((item) => UUID.test(item?.release_id)
      && UUID.test(item.client_id) && UUID.test(item.loan_id) && text(item.client_name)
      && text(item.loan_type) && money(item.amount) && text(item.evidence_reference)
      && text(item.released_at) && item.cash_effect === 'outflow');
}

function acceptedResult(result, notice, actorId) {
  const updated = result?.notification;
  return result?.remittance_id === notice.remittance_id && result.status === 'received'
    && result.custody_user_id === actorId && text(result.received_at)
    && updated?.notification_id === notice.notification_id && updated.remittance_id === notice.remittance_id
    && updated.recipient_user_id === actorId && updated.sender_user_id === notice.sender_user_id
    && updated.status === 'accepted' && updated.is_pending === false;
}

export function buildRemittanceRejection({record, actorId, reason, reviewed}) {
  const normalized = typeof reason === 'string' ? reason.trim() : '';
  if (!UUID.test(actorId) || !UUID.test(record?.remittance_id) || !UUID.test(record?.collector_user_id)
    || record.collector_user_id === actorId || record.recipient_user_id !== actorId
    || record.status !== 'submitted' || reviewed !== true || !normalized || normalized.length > 500) {
    throw new Error('Review the complete pending remittance and enter a reason of 1–500 characters.');
  }
  return {path:`/api/v1/remittances/${record.remittance_id}/reject`,options:{method:'POST',body:{review_acknowledged:true,reason:normalized},financial:true}};
}

export function rejectedRemittanceMatches(result, record, actorId, reason) {
  return result?.remittance_id === record?.remittance_id && result.collector_user_id === record.collector_user_id
    && result.recipient_user_id === actorId && result.status === 'rejected'
    && result.rejected_by_user_id === actorId && text(result.rejected_at)
    && result.rejection_reason === reason.trim();
}

function detailMarkup(record) {
  return `<article class="data-card">
    <h3>Review ${escapeHtml(record.remittance_number)}</h3>
    <p>From ${escapeHtml(record.collector_name)} to ${escapeHtml(record.recipient_name)} · ${escapeHtml(record.collection_date)}</p>
    <p><strong>Server cash total: PHP ${escapeHtml(record.total_amount)}</strong></p>
    <p>${escapeHtml(record.transaction_count)} transactions · ${escapeHtml(record.payment_count)} payments · ${escapeHtml(record.unable_to_pay_count)} unable to pay · ${escapeHtml(record.covered_payment_count)} covered payments · ${escapeHtml(record.client_count)} clients</p>
    <h4>Full payment list</h4>
    <div class="list-stack">${record.items.map((item) => `<article class="list-item" data-remittance-item>
      <strong>${escapeHtml(item.client_name)}</strong>
      <p>${escapeHtml(item.loan_type)} · ${escapeHtml(item.entry_type)} · PHP ${escapeHtml(item.amount)}</p>
      <p>Receipt: ${escapeHtml(item.receipt_number)} · Collection date: ${escapeHtml(item.collection_date)}</p>
      <p>Covered dates: ${item.covered_dates.length ? item.covered_dates.map(escapeHtml).join(', ') : 'None recorded'}</p>
      ${item.note ? `<p>${escapeHtml(item.note)}</p>` : ''}
    </article>`).join('')}</div>
    <h4>Refund Due cash outflows</h4>
    <p>Server refund total: PHP ${escapeHtml(record.refund_due_release_total)}</p>
    ${record.refund_due_releases.length ? `<div class="list-stack">${record.refund_due_releases.map((item) => `<article class="list-item" data-remittance-refund>
      <strong>${escapeHtml(item.client_name)}</strong>
      <p>${escapeHtml(item.loan_type)} · Cash outflow: PHP ${escapeHtml(item.amount)}</p>
      <p>Evidence: ${escapeHtml(item.evidence_reference)} · Released: ${escapeHtml(item.released_at)}</p>
    </article>`).join('')}</div>` : '<p>No refund cash outflow is included.</p>'}
    ${record.note ? `<p>Handover note: ${escapeHtml(record.note)}</p>` : ''}
    <p>Cash stays under the sender's responsibility until you physically receive it and SPINA confirms acceptance.</p>
    <form class="entry-form" data-remittance-accept-form>
      <label><input type="checkbox" name="reviewedPayments" /> I reviewed every included payment, receipt, covered date and refund cash outflow.</label>
      <label><input type="checkbox" name="physicallyReceived" /> I physically received and counted the cash matching the server cash total.</label>
      <button class="button button-primary" type="submit" data-remittance-accept disabled>Accept cash custody</button>
      <label>Reason for rejecting this remittance <textarea name="rejectionReason" maxlength="500"></textarea></label>
      <label><input type="checkbox" name="confirmRejection" /> Reject ${escapeHtml(record.remittance_number)}: cash remains with the sender and this handover cannot be accepted.</label>
      <button class="button button-secondary" type="button" data-remittance-reject disabled>Reject remittance</button>
    </form>
    <button class="button button-secondary" type="button" data-remittance-close>Close review</button>
  </article>`;
}

export function mountRemittanceReview({ root, api, session, notifications, signal, loadNotifications, onNoticesChanged,
  getSession = () => session, registerHandle, isOnline = () => globalThis.navigator?.onLine !== false }) {
  if (!root) return () => {};
  let notices = asArray(notifications).filter((notice) => notice && typeof notice === 'object');
  const actorId = session?.user?.id;
  const canReceive = hasPermission(session, 'remittance.receive');
  const controller = new AbortController();
  const listeners = [];
  let disposed = false;
  let generation = 0;
  let loading = false;
  let submitting = false;
  let locked = false;
  let pendingDecision = null;
  const finalized = new Set();
  let opener = null;
  root.innerHTML = '<div class="list-stack" data-remittance-notices></div><div role="status" aria-live="polite" tabindex="-1" data-remittance-message></div><button class="button button-secondary" type="button" data-remittance-retry>Refresh remittances</button><div data-remittance-detail></div>';
  const rows = root.querySelector('[data-remittance-notices]');
  const message = root.querySelector('[data-remittance-message]');
  const detail = root.querySelector('[data-remittance-detail]');
  const active = () => !disposed && !signal?.aborted;
  const authorized = (receive = false) => {
    const current = getSession();
    return current?.user?.id === actorId && hasPermission(current, 'remittance.view')
      && (!receive || hasPermission(current, 'remittance.receive'));
  };

  function on(element, type, handler) {
    element.addEventListener(type, handler);
    listeners.push(() => element.removeEventListener(type, handler));
  }

  function clearDetail() {
    generation += 1;
    loading = false;
    for (const input of detail.querySelectorAll('input')) input.checked = false;
    for (const input of detail.querySelectorAll('textarea')) input.value = '';
    detail.innerHTML = '';
  }

  function updateButtons() {
    for (const button of rows.querySelectorAll('[data-review-notification]')) {
      button.disabled = locked || loading || submitting;
    }
    for (const input of detail.querySelectorAll('input')) input.disabled = locked || submitting;
    for (const input of detail.querySelectorAll('textarea')) input.disabled = locked || submitting;
    const retry = root.querySelector('[data-remittance-retry]');
    if (retry) retry.disabled = submitting || loading;
    const close = detail.querySelector('[data-remittance-close]');
    if (close) close.disabled = submitting;
    const accept = detail.querySelector('[data-remittance-accept]');
    if (accept) accept.disabled = locked || submitting
      || !detail.querySelector('[name="reviewedPayments"]').checked
      || !detail.querySelector('[name="physicallyReceived"]').checked;
    const reject = detail.querySelector('[data-remittance-reject]');
    if (reject) reject.disabled = locked || submitting || !detail.querySelector('[name="reviewedPayments"]').checked
      || !detail.querySelector('[name="confirmRejection"]').checked
      || !detail.querySelector('[name="rejectionReason"]').value.trim();
  }

  function offline() {
    if (isOnline()) return false;
    clearDetail();
    message.textContent = 'An online connection is required. Reconnect and open Review remittance again.';
    updateButtons();
    return true;
  }

  function uncertain() {
    locked = true;
    clearDetail();
    message.textContent = 'SPINA could not confirm this decision. Do not repeat the handover or decision. Use Refresh to check the authoritative remittance status before any new action.';
    updateButtons();
  }

  function denied() {
    cleanup();
    root.textContent = 'Remittance access is no longer available. Sign in again to refresh your permissions.';
  }

  function renderNotices() {
    rows.innerHTML = notices.length ? notices.map((notice, index) => `<article class="list-item">
      <strong>${escapeHtml(notice.remittance_number || 'Remittance')}</strong>
      <p>From ${escapeHtml(notice.collector_name || 'Collector')} · PHP ${escapeHtml(notice.total_amount ?? 'Unavailable')}</p>
      ${badge(notice.status || 'unknown')}
      <p>${escapeHtml(notice.collection_date || '')} · ${escapeHtml(notice.transaction_count ?? '—')} transactions · ${escapeHtml(notice.client_count ?? '—')} clients</p>
      ${canReceive && !finalized.has(notice.notification_id) && reviewable(notice, actorId) ? `<button class="button button-secondary" type="button" data-review-notification="${escapeHtml(notice.notification_id)}" data-review-index="${index}">Review remittance</button>` : ''}
    </article>`).join('') : emptyState('No remittance notification is waiting for this Employee.');
    for (const button of rows.querySelectorAll('[data-review-notification]')) {
      on(button, 'click', () => {opener = button; openReview(notices[Number(button.getAttribute('data-review-index'))]);});
    }
    updateButtons();
  }

  async function openReview(notice) {
    if (!active() || locked || loading || submitting || !reviewable(notice, actorId)) return;
    if(finalized.has(notice.notification_id))return;
    if (!authorized(true)) {denied();return;}
    clearDetail();
    if (offline()) return;
    loading = true;
    updateButtons();
    const current = generation;
    message.textContent = 'Loading the complete remittance for review…';
    try {
      const records = await api.request('/api/v1/remittances', { signal: controller.signal });
      if (!active() || current !== generation) return;
      const matches = asArray(records).filter((record) => record?.remittance_id === notice.remittance_id);
      if (matches.length !== 1 || !validDetail(matches[0], notice, actorId)) {
        message.textContent = 'The complete pending remittance could not be verified. Use Refresh to check its current status.';
        return;
      }
      detail.innerHTML = detailMarkup(matches[0]);
      const reviewedEvidence = JSON.stringify(matches[0]);
      message.textContent = 'Review the complete list, then confirm physical cash receipt.';
      const reviewed = detail.querySelector('[name="reviewedPayments"]');
      const received = detail.querySelector('[name="physicallyReceived"]');
      const reason = detail.querySelector('[name="rejectionReason"]');
      const confirm = detail.querySelector('[name="confirmRejection"]');
      on(reviewed, 'change', updateButtons);
      on(received, 'change', updateButtons);
      on(reason, 'input', updateButtons);
      on(confirm, 'change', updateButtons);
      reviewed.focus?.();
      on(detail.querySelector('[data-remittance-close]'), 'click', () => {
        if (!active() || submitting || current !== generation) return;
        clearDetail(); message.textContent = ''; updateButtons();
        opener?.focus?.();
      });
      async function decide(kind, event) {
        event.preventDefault();
        if (!active() || locked || submitting || current !== generation || offline()) return;
        if (!authorized(true)) {denied();return;}
        if (!reviewed.checked || (kind === 'accept' && !received.checked)) {
          message.textContent = 'Confirm the full item review and physical cash receipt before accepting.';
          return;
        }
        let action;
        try {
          if (kind === 'reject') {
            if (!confirm.checked) throw new Error('Confirm the named rejection and its consequence.');
            action = buildRemittanceRejection({record:matches[0],actorId,reason:reason.value,reviewed:reviewed.checked});
          } else action = {path:`/api/v1/notifications/${notice.notification_id}/accept-remittance`,options:{method:'POST',body:{review_acknowledged:true},financial:true}};
        } catch (error) {message.textContent=error.message;return;}
        submitting = true;
        updateButtons();
        message.textContent = 'Confirming cash receipt with SPINA…';
        try {
          // Current-authority preflight is enabled for workspace callers. Legacy
          // notification-only consumers retain the established accept contract.
          if (loadNotifications) {
            const freshNotices = await loadNotifications();
            const freshRecords = await api.request('/api/v1/remittances',{signal:controller.signal});
            if (!active() || current !== generation) return;
            if (!authorized(true)) {denied();return;}
            const matchingNotices=asArray(freshNotices).filter(item=>item?.notification_id===notice.notification_id);
            const matchingRecords=asArray(freshRecords).filter(item=>item?.remittance_id===notice.remittance_id);
            if (matchingNotices.length!==1 || !reviewable(matchingNotices[0],actorId)
              || matchingNotices[0].sender_user_id!==notice.sender_user_id || matchingNotices[0].remittance_id!==notice.remittance_id
              || matchingRecords.length!==1 || !validDetail(matchingRecords[0],notice,actorId)
              || JSON.stringify(matchingRecords[0])!==reviewedEvidence) {
              clearDetail();message.textContent='The pending evidence changed. Open a fresh review before deciding.';return;
            }
          }
          pendingDecision={kind,notice,record:matches[0],reason:action.options.body.reason};
          const result = await api.request(action.path,{...action.options,signal:controller.signal});
          if (!active() || current !== generation) return;
          if(!authorized(true)){denied();return;}
          if (!(kind==='accept'?acceptedResult(result,notice,actorId):rejectedRemittanceMatches(result,matches[0],actorId,action.options.body.reason))) {uncertain();return;}
          clearDetail();
          finalized.add(notice.notification_id);
          locked=true;
          if(kind==='accept')notices=notices.map(item=>item.notification_id===notice.notification_id?result.notification:item);
          renderNotices();
          const saved=kind==='accept'?'Remittance accepted. Cash custody is now recorded under your account.':'Rejection saved. Cash remains with the sender.';
          message.textContent=saved;
          if(loadNotifications){try{
            const updated=await loadNotifications();if(!active())return;
            if(!authorized()) {denied();return;}
            if(!Array.isArray(updated))throw new Error('Invalid notices');
            notices=updated;onNoticesChanged?.(notices);renderNotices();
            // The verified write stays final even if a stale GET still shows pending.
            notices=notices.filter(item=>item.notification_id!==notice.notification_id || !item.is_pending);
            renderNotices();message.textContent=saved;
          }catch(error){if(!active())return;if([401,403].includes(error?.status))denied();else message.textContent=`${saved} Notices could not refresh. Use Refresh for a read-only check.`;}}
          pendingDecision=null;locked=false;message.focus?.();
        } catch (error) {
          if (!active() || current !== generation) return;
          if ([401, 403].includes(error?.status)) denied();
          else if(pendingDecision)uncertain();
          else message.textContent='Current remittance evidence could not refresh. No decision was sent. Use Refresh and review again.';
        } finally {
          submitting = false;
          if (active()) updateButtons();
        }
      }
      on(detail.querySelector('form'),'submit',event=>decide('accept',event));
      on(detail.querySelector('[data-remittance-reject]'),'click',event=>decide('reject',event));
    } catch (error) {
      if (!active() || current !== generation) return;
      if ([401, 403].includes(error?.status)) denied();
      else message.textContent = 'The complete remittance is unavailable. Check the connection and open Review remittance again.';
    } finally {
      if (active() && current === generation) { loading = false; updateButtons(); }
    }
  }

  async function refreshReadOnly() {
    if(!active() || loading || submitting || offline())return;
    if(!authorized()) {denied();return;}
    loading=true;updateButtons();
    try {
      const updated=loadNotifications?await loadNotifications():notices;
      if(!active())return;
      if(!authorized()) {denied();return;}
      if(!Array.isArray(updated))throw new Error('Invalid notices');
      if(pendingDecision){
        const records=await api.request('/api/v1/remittances',{signal:controller.signal});
        if(!active())return;
        const {kind,record,notice,reason}=pendingDecision;
        const matching=asArray(records).filter(item=>item?.remittance_id===record.remittance_id);
        const matchingNotices=updated.filter(item=>item?.notification_id===notice.notification_id);
        const verified=matching.length===1 && (kind==='reject'?rejectedRemittanceMatches(matching[0],record,actorId,reason):
          matching[0].status==='received' && matching[0].recipient_user_id===actorId && matching[0].collector_user_id===record.collector_user_id
          && text(matching[0].received_at) && matchingNotices.length===1 && matchingNotices[0].status==='accepted'
          && matchingNotices[0].is_pending===false && matchingNotices[0].recipient_user_id===actorId && matchingNotices[0].remittance_id===record.remittance_id);
        if(!verified){message.textContent='Decision remains unconfirmed. No write will be repeated; check again or contact the authorized reviewer.';return;}
        finalized.add(notice.notification_id);pendingDecision=null;locked=false;clearDetail();message.textContent='The saved decision is confirmed by the current server records.';
      }else message.textContent='Current remittance notices loaded.';
      notices=updated;onNoticesChanged?.(notices);renderNotices();
    }catch(error){if(!active())return;if([401,403].includes(error?.status))denied();else message.textContent='Remittance notices could not refresh. Use Refresh to retry the read.';}
    finally{loading=false;if(active())updateButtons();}
  }

  function cleanup() {
    if (disposed) return;
    disposed = true;
    controller.abort();
    signal?.removeEventListener('abort', cleanup);
    for (const remove of listeners) remove();
    clearDetail();
    notices = [];
    pendingDecision=null;
    finalized.clear();
    rows.innerHTML = '';
    root.innerHTML = '';
  }

  signal?.addEventListener('abort', cleanup, { once: true });
  on(root.querySelector('[data-remittance-retry]'),'click',refreshReadOnly);
  registerHandle?.({refreshReadOnly,openRecord:async(id)=>{const notice=notices.find(item=>item?.remittance_id===id||item?.notification_id===id);if(notice)await openReview(notice);},isUncertain:()=>locked,isWritePending:()=>submitting,dispose:cleanup});
  if (signal?.aborted || !hasPermission(session, 'remittance.view')) cleanup();
  else renderNotices();
  return cleanup;
}

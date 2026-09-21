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

function detailMarkup(record) {
  return `<article class="data-card">
    <h3>Review ${escapeHtml(record.remittance_number)}</h3>
    <p>From ${escapeHtml(record.collector_name)} to ${escapeHtml(record.recipient_name)} · ${escapeHtml(record.collection_date)}</p>
    <p><strong>Server cash total: PHP ${escapeHtml(record.total_amount)}</strong></p>
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
    </form>
    <button class="button button-secondary" type="button" data-remittance-close>Close review</button>
  </article>`;
}

export function mountRemittanceReview({ root, api, session, notifications, signal, isOnline = () => globalThis.navigator?.onLine !== false }) {
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
  root.innerHTML = '<div class="list-stack" data-remittance-notices></div><div role="status" aria-live="polite" data-remittance-message></div><div data-remittance-detail></div>';
  const rows = root.querySelector('[data-remittance-notices]');
  const message = root.querySelector('[data-remittance-message]');
  const detail = root.querySelector('[data-remittance-detail]');
  const active = () => !disposed && !signal?.aborted;

  function on(element, type, handler) {
    element.addEventListener(type, handler);
    listeners.push(() => element.removeEventListener(type, handler));
  }

  function clearDetail() {
    generation += 1;
    loading = false;
    for (const input of detail.querySelectorAll('input')) input.checked = false;
    detail.innerHTML = '';
  }

  function updateButtons() {
    for (const button of rows.querySelectorAll('[data-review-notification]')) {
      button.disabled = locked || loading || submitting;
    }
    for (const input of detail.querySelectorAll('input')) input.disabled = locked || submitting;
    const close = detail.querySelector('[data-remittance-close]');
    if (close) close.disabled = submitting;
    const accept = detail.querySelector('[data-remittance-accept]');
    if (accept) accept.disabled = locked || submitting
      || !detail.querySelector('[name="reviewedPayments"]').checked
      || !detail.querySelector('[name="physicallyReceived"]').checked;
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
    message.textContent = 'SPINA could not confirm acceptance. Do not repeat the handover. Use Refresh to check the authoritative remittance status before any new action.';
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
      ${canReceive && reviewable(notice, actorId) ? `<button class="button button-secondary" type="button" data-review-notification="${escapeHtml(notice.notification_id)}" data-review-index="${index}">Review remittance</button>` : ''}
    </article>`).join('') : emptyState('No remittance notification is waiting for this Employee.');
    for (const button of rows.querySelectorAll('[data-review-notification]')) {
      on(button, 'click', () => openReview(notices[Number(button.getAttribute('data-review-index'))]));
    }
    updateButtons();
  }

  async function openReview(notice) {
    if (!active() || locked || loading || submitting || !reviewable(notice, actorId)) return;
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
      message.textContent = 'Review the complete list, then confirm physical cash receipt.';
      const reviewed = detail.querySelector('[name="reviewedPayments"]');
      const received = detail.querySelector('[name="physicallyReceived"]');
      on(reviewed, 'change', updateButtons);
      on(received, 'change', updateButtons);
      on(detail.querySelector('[data-remittance-close]'), 'click', () => {
        if (!active() || submitting || current !== generation) return;
        clearDetail(); message.textContent = ''; updateButtons();
      });
      on(detail.querySelector('form'), 'submit', async (event) => {
        event.preventDefault();
        if (!active() || locked || submitting || current !== generation || offline()) return;
        if (!reviewed.checked || !received.checked) {
          message.textContent = 'Confirm the full item review and physical cash receipt before accepting.';
          return;
        }
        submitting = true;
        updateButtons();
        message.textContent = 'Confirming cash receipt with SPINA…';
        try {
          const result = await api.request(`/api/v1/notifications/${notice.notification_id}/accept-remittance`, {
            method: 'POST', body: { review_acknowledged: true }, financial: true, signal: controller.signal,
          });
          if (!active() || current !== generation) return;
          if (!acceptedResult(result, notice, actorId)) { uncertain(); return; }
          clearDetail();
          notices = notices.map((item) => item.notification_id === notice.notification_id ? result.notification : item);
          renderNotices();
          message.textContent = 'Remittance accepted. Cash custody is now recorded under your account.';
        } catch (error) {
          if (!active() || current !== generation) return;
          if ([401, 403].includes(error?.status)) denied();
          else uncertain();
        } finally {
          submitting = false;
          if (active()) updateButtons();
        }
      });
    } catch (error) {
      if (!active() || current !== generation) return;
      if ([401, 403].includes(error?.status)) denied();
      else message.textContent = 'The complete remittance is unavailable. Check the connection and open Review remittance again.';
    } finally {
      if (active() && current === generation) { loading = false; updateButtons(); }
    }
  }

  function cleanup() {
    if (disposed) return;
    disposed = true;
    controller.abort();
    signal?.removeEventListener('abort', cleanup);
    for (const remove of listeners) remove();
    clearDetail();
    notices = [];
    rows.innerHTML = '';
    root.innerHTML = '';
  }

  signal?.addEventListener('abort', cleanup, { once: true });
  if (signal?.aborted || !hasPermission(session, 'remittance.view')) cleanup();
  else renderNotices();
  return cleanup;
}

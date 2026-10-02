import {
  asArray,
  badge,
  emptyState,
  errorCard,
  escapeHtml,
  formatDate,
  formatDateTime,
  formatMoney,
  loadingPanel,
  metricCard,
} from './ui.js';

const OPERATIONS_PATH = '/api/v1/management/loan-operations';
const OPERATION_STATUSES = new Set([
  'all',
  'unremitted',
  'submitted',
  'received',
  'voided',
]);

export function loadManagementLoanOperations(
  api,
  { query = '', status = 'all' } = {},
) {
  const normalizedQuery = String(query ?? '').trim();
  const requestedStatus = String(status ?? '').trim().toLowerCase();
  const normalizedStatus = OPERATION_STATUSES.has(requestedStatus)
    ? requestedStatus
    : 'all';
  return api.request(
    `${OPERATIONS_PATH}?q=${encodeURIComponent(normalizedQuery)}&status=${encodeURIComponent(normalizedStatus)}`,
  );
}

function plural(count, noun) {
  const value = Number(count ?? 0);
  return `${escapeHtml(count ?? 0)} ${noun}${value === 1 ? '' : 's'}`;
}

function summaryItem(label, value, detail = '') {
  return `<article class="loan-ops-summary-item">
    <span>${escapeHtml(label)}</span>
    <strong>${value}</strong>
    ${detail ? `<small>${detail}</small>` : ''}
  </article>`;
}

function summaryMarkup(summary = {}) {
  const date = summary.latest_collection_date
    ? formatDate(summary.latest_collection_date)
    : 'No collection date returned';
  return `<div class="loan-ops-summary">
    <section class="loan-ops-summary-group" data-loan-ops-summary-group="latest-day">
      <h4>Latest collection day</h4>
      <div class="loan-ops-summary-items">
        ${summaryItem('Collected', formatMoney(summary.latest_day_amount), date)}
        ${summaryItem('Payments', escapeHtml(summary.latest_day_payment_count ?? 0), plural(summary.latest_day_payment_count ?? 0, 'payment'))}
        ${summaryItem('Unable to pay', escapeHtml(summary.latest_day_unable_to_pay_count ?? 0), `${escapeHtml(summary.latest_day_unable_to_pay_count ?? 0)} unable to pay`)}
      </div>
    </section>
    <section class="loan-ops-summary-group" data-loan-ops-summary-group="remittance">
      <h4>Remittance</h4>
      <div class="loan-ops-summary-items">
        ${summaryItem('Unremitted', formatMoney(summary.unremitted_amount), Number(summary.unremitted_entry_count ?? 0) === 1 ? '1 entry' : `${escapeHtml(summary.unremitted_entry_count ?? 0)} entries`)}
        ${summaryItem('Pending', formatMoney(summary.pending_remittance_amount), plural(summary.pending_remittance_count ?? 0, 'remittance'))}
        ${summaryItem('Received', formatMoney(summary.received_remittance_amount), plural(summary.received_remittance_count ?? 0, 'remittance'))}
      </div>
    </section>
    <section class="loan-ops-summary-group" data-loan-ops-summary-group="audit">
      <h4>Audit</h4>
      <div class="loan-ops-summary-items">
        ${summaryItem('Corrections', escapeHtml(summary.correction_count ?? 0), plural(summary.correction_count ?? 0, 'correction'))}
        ${summaryItem('Voids', escapeHtml(summary.void_count ?? 0), plural(summary.void_count ?? 0, 'void'))}
      </div>
    </section>
  </div>`;
}
function coveredDatesMarkup(values) {
  const dates = asArray(values);
  return dates.length ? dates.map((value) => formatDate(value)).join(', ') : '—';
}

function entriesMarkup(entries) {
  const items = asArray(entries);
  if (!items.length) {
    return emptyState('No collection activity matches the current server filter.');
  }
  return `<div class="loan-operation-cards">${items.map((entry) => {
    const covered = asArray(entry.covered_dates);
    return `<article class="loan-operation-card">
      <div class="loan-operation-card-heading">
        <div>
          <strong>${escapeHtml(entry.client_name || '—')}</strong>
          <span class="meta">${escapeHtml(entry.loan_number || '—')} · ${escapeHtml(entry.loan_type_name || '—')}</span>
        </div>
        ${badge(entry.status === 'wallet_applied' ? 'Recipient funds applied' : entry.status || 'unknown')}
      </div>
      <div class="loan-operation-primary">
        <div><span>Amount</span><strong>${formatMoney(entry.amount)}</strong></div>
        <div><span>Official balance</span><strong>${formatMoney(entry.official_balance)}</strong></div>
        <div><span>Receipt</span><strong>${escapeHtml(entry.receipt_number || '—')}</strong></div>
        <div><span>Collection date</span><strong>${formatDate(entry.collection_date)}</strong></div>
      </div>
      <p class="meta">Recorded by: ${escapeHtml(entry.collector_name || '—')}${entry.remittance_number ? ` · Remittance ${escapeHtml(entry.remittance_number)}` : ''}</p>
      ${covered.length ? `<p class="meta"><strong>Covered dates:</strong> ${coveredDatesMarkup(covered)}</p>` : ''}
      <details class="loan-operation-technical" data-loan-ops-technical>
        <summary>Details</summary>
        <div class="detail-grid">
          <div class="detail-item"><span>Client code</span><strong>${escapeHtml(entry.client_code || '—')}</strong></div>
          <div class="detail-item"><span>Accepted</span><strong>${formatDateTime(entry.accepted_at)}</strong></div>
          <div class="detail-item"><span>Entry type</span><strong>${escapeHtml(entry.entry_type || '—')}</strong></div>
          <div class="detail-item"><span>Edit revision</span><strong>edit v${escapeHtml(entry.edit_version ?? 0)}</strong></div>
        </div>
        ${entry.void_reason ? `<p><strong>Void reason:</strong> ${escapeHtml(entry.void_reason)}</p>` : ''}
      </details>
    </article>`;
  }).join('')}</div>`;
}
function auditsMarkup(audits) {
  const items = asArray(audits);
  if (!items.length) {
    return emptyState('No recent correction or void audit activity is available.');
  }
  return `<div class="loan-operation-audits">${items.map((event) => `<article class="loan-operation-audit">
    <div class="loan-operation-card-heading">
      <div>
        <strong>${escapeHtml(event.client_name || '—')}</strong>
        <span class="meta">${escapeHtml(event.loan_number || '—')} · ${escapeHtml(event.receipt_number || '—')}</span>
      </div>
      ${badge(event.event_type || 'audit')}
    </div>
    <p>${escapeHtml(event.reason || '—')}</p>
    <p class="meta">${escapeHtml(event.actor_name || '—')} · ${formatDateTime(event.happened_at)}</p>
  </article>`).join('')}</div>`;
}
export function managementLoanOperationsMarkup(payload = {}) {
  const summary = payload.summary ?? {};
  const notice = String(payload.notice ?? '').trim();

  return `<div class="loan-operations-view">
    ${notice ? `<div class="notice-card loan-operations-notice"><strong>Read-only history</strong><p>Review collections, remittances, corrections, and voids. Use the protected action workflows to make changes.</p><details><summary>About this view</summary><p>${escapeHtml(notice)}</p></details></div>` : ''}
    ${summaryMarkup(summary)}
    <div class="loan-ops-tabs" role="tablist" aria-label="Loan operations views">
      <button type="button" class="loan-ops-tab active" data-loan-ops-tab="activity" aria-selected="true">Collection activity</button>
      <button type="button" class="loan-ops-tab" data-loan-ops-tab="audits" aria-selected="false">Corrections &amp; voids</button>
    </div>
    <section data-loan-ops-panel="activity">
      <div class="section-heading"><div><h3>Collection activity</h3><p>Collections and remittance status from SPINA records.</p></div></div>
      ${entriesMarkup(payload.entries)}
    </section>
    <section data-loan-ops-panel="audits" hidden>
      <div class="section-heading"><div><h3>Corrections &amp; voids</h3><p>Permanent correction and void history.</p></div></div>
      ${auditsMarkup(payload.audits)}
    </section>
  </div>`;
}
export function bindManagementLoanOperations(context) {
  const form = context.root.querySelector('#management-loan-operations-search');
  const target = context.root.querySelector('#management-loan-operations-results');
  if (!form || !target) return;

  const queryInput = form.querySelector('[name="q"]');
  const statusInput = form.querySelector('[name="status"]');

  const bindLocalViews = () => {
    const tabs = context.root.querySelectorAll?.('[data-loan-ops-tab]') ?? [];
    const panels = context.root.querySelectorAll?.('[data-loan-ops-panel]') ?? [];
    const activate = (id) => {
      for (const panel of panels) {
        if (panel.getAttribute('data-loan-ops-panel') === id) panel.removeAttribute('hidden');
        else panel.setAttribute('hidden', '');
      }
      for (const tab of tabs) {
        const selected = tab.getAttribute('data-loan-ops-tab') === id;
        tab.setAttribute('aria-selected', selected ? 'true' : 'false');
        if (selected) tab.setAttribute('class', 'loan-ops-tab active');
        else tab.setAttribute('class', 'loan-ops-tab');
      }
    };
    for (const tab of tabs) {
      tab.addEventListener?.('click', (event) => {
        event?.preventDefault?.();
        activate(tab.getAttribute('data-loan-ops-tab'));
      });
    }
  };

  const reload = async () => {
    target.innerHTML = loadingPanel('Loading loan operations…');
    try {
      const data = await loadManagementLoanOperations(context.api, {
        query: queryInput?.value ?? '',
        status: statusInput?.value ?? 'all',
      });
      target.innerHTML = managementLoanOperationsMarkup(data);
      bindLocalViews();
    } catch (error) {
      target.innerHTML = errorCard(error);
    }
  };

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    await reload();
  });
  statusInput?.addEventListener('change', reload);
  bindLocalViews();
}
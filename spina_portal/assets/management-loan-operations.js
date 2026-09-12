import {
  asArray,
  badge,
  emptyState,
  escapeHtml,
  formatDate,
  formatDateTime,
  formatMoney,
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

function summaryMarkup(summary = {}) {
  return `<div class="metric-grid">
    ${metricCard(
      'Latest collections',
      formatMoney(summary.latest_day_amount),
      summary.latest_collection_date ? `Latest day ${formatDate(summary.latest_collection_date)}` : 'No collection date returned',
    )}
    ${metricCard(
      'Payments / unable',
      `${escapeHtml(summary.latest_day_payment_count ?? 0)} / ${escapeHtml(summary.latest_day_unable_to_pay_count ?? 0)}`,
      summary.latest_collection_date ? `Latest day ${formatDate(summary.latest_collection_date)}` : 'Server-returned counts',
    )}
    ${metricCard(
      'Unremitted cash',
      formatMoney(summary.unremitted_amount),
      `${escapeHtml(summary.unremitted_entry_count ?? 0)} entries`,
    )}
    ${metricCard(
      'Pending remittance',
      formatMoney(summary.pending_remittance_amount),
      `${escapeHtml(summary.pending_remittance_count ?? 0)} remittances`,
    )}
    ${metricCard(
      'Received cash',
      formatMoney(summary.received_remittance_amount),
      `${escapeHtml(summary.received_remittance_count ?? 0)} remittances`,
    )}
    ${metricCard(
      'Corrections / voids',
      `${escapeHtml(summary.correction_count ?? 0)} / ${escapeHtml(summary.void_count ?? 0)}`,
      'Server-returned audit counts',
    )}
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
  return `<div class="table-wrap"><table>
    <thead><tr><th>Receipt / date</th><th>Client / loan</th><th>Collector / type</th><th>Amount / official balance</th><th>Covered dates</th><th>Status</th></tr></thead>
    <tbody>${items
      .map(
        (entry) => `<tr>
          <td><strong>${escapeHtml(entry.receipt_number || '—')}</strong><br><span class="meta">${formatDate(entry.collection_date)} · ${formatDateTime(entry.accepted_at)}</span></td>
          <td><strong>${escapeHtml(entry.client_name || '—')}</strong><br><span class="meta">${escapeHtml(entry.client_code || '—')} · ${escapeHtml(entry.loan_number || '—')} · ${escapeHtml(entry.loan_type_name || '—')}</span></td>
          <td>${escapeHtml(entry.collector_name || '—')}<br><span class="meta">${escapeHtml(entry.entry_type || '—')} · edit v${escapeHtml(entry.edit_version ?? 0)}</span></td>
          <td><strong>${formatMoney(entry.amount)}</strong><br><span class="meta">Balance ${formatMoney(entry.official_balance)}</span></td>
          <td>${coveredDatesMarkup(entry.covered_dates)}</td>
          <td>${badge(entry.status || 'unknown')}${entry.remittance_number ? `<br><span class="meta">${escapeHtml(entry.remittance_number)}</span>` : ''}${entry.void_reason ? `<br><span>${escapeHtml(entry.void_reason)}</span>` : ''}</td>
        </tr>`,
      )
      .join('')}</tbody>
  </table></div>`;
}

function auditsMarkup(audits) {
  const items = asArray(audits);
  if (!items.length) {
    return emptyState('No recent correction or void audit activity is available.');
  }
  return `<div class="list-stack">${items
    .map(
      (event) => `<article class="list-item">
        <div class="section-heading"><div><strong>${escapeHtml(event.client_name || '—')}</strong><p>${escapeHtml(event.loan_number || '—')} · ${escapeHtml(event.receipt_number || '—')}</p></div>${badge(event.event_type || 'audit')}</div>
        <span>${escapeHtml(event.reason || '—')}</span>
        <span class="meta">${escapeHtml(event.actor_name || '—')} · ${formatDateTime(event.happened_at)}</span>
      </article>`,
    )
    .join('')}</div>`;
}

export function managementLoanOperationsMarkup(payload = {}) {
  const summary = payload.summary ?? {};
  const notice = String(payload.notice ?? '').trim();

  return `<div class="list-stack">
    ${notice ? `<div class="notice-card"><strong>Read-only monitoring</strong><br>${escapeHtml(notice)}</div>` : ''}
    ${summaryMarkup(summary)}
    <div class="section-heading"><div><h3>Collection activity</h3><p>Official server-returned collection and remittance state.</p></div></div>
    ${entriesMarkup(payload.entries)}
    <div class="section-heading" style="margin-top:1rem"><div><h3>Corrections & voids</h3><p>Permanent audit history returned by the owning SPINA records.</p></div></div>
    ${auditsMarkup(payload.audits)}
  </div>`;
}

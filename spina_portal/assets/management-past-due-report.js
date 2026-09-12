import {
  asArray,
  emptyState,
  escapeHtml,
  formatMoney,
  metricCard,
} from './ui.js';

const PAST_DUE_REPORT_PATH = '/api/v1/management/past-due/reasons';
const REASON_CODES = new Set([
  'no_cash',
  'client_absent',
  'business_slow',
  'sick_hospital',
  'emergency',
  'promised_to_pay_later',
  'other',
]);
const EVENT_KINDS = new Set(['unable_to_pay', 'partial_payment']);

function normalizedFilter(value) {
  return String(value ?? '').trim();
}

function appendQuery(parts, name, value) {
  if (!value) return;
  parts.push(`${name}=${encodeURIComponent(value)}`);
}

export function loadManagementPastDueReport(
  api,
  {
    startDate = '',
    endDate = '',
    area = '',
    reasonCode = '',
    eventKind = '',
  } = {},
) {
  const query = [];
  appendQuery(query, 'start_date', normalizedFilter(startDate));
  appendQuery(query, 'end_date', normalizedFilter(endDate));
  appendQuery(query, 'area', normalizedFilter(area));

  const normalizedReason = normalizedFilter(reasonCode).toLowerCase();
  if (REASON_CODES.has(normalizedReason)) {
    appendQuery(query, 'reason_code', normalizedReason);
  }

  const normalizedKind = normalizedFilter(eventKind).toLowerCase();
  if (EVENT_KINDS.has(normalizedKind)) {
    appendQuery(query, 'event_kind', normalizedKind);
  }

  const suffix = query.length ? `?${query.join('&')}` : '';
  return api.request(`${PAST_DUE_REPORT_PATH}${suffix}`);
}

function summaryMarkup(summary = {}) {
  return `<div class="metric-grid">
    ${metricCard(
      'Past-Due events',
      escapeHtml(summary.event_count ?? 0),
      'Server-returned event count',
    )}
    ${metricCard(
      'Past-Due amount',
      formatMoney(summary.total_past_due_amount),
      'Server-returned total',
    )}
    ${metricCard(
      'Remaining Past-Due',
      formatMoney(summary.remaining_past_due_amount),
      'Server-returned remaining amount',
    )}
  </div>`;
}

function rowsMarkup(rows) {
  const items = asArray(rows);
  if (!items.length) {
    return emptyState('No Past-Due reason rows match the current server filters.');
  }

  return `<div class="table-wrap"><table>
    <thead><tr><th>Client</th><th>Collector / Area</th><th>Reason</th><th>Event</th><th>Count</th><th>Past-Due amount</th><th>Remaining</th></tr></thead>
    <tbody>${items
      .map(
        (row) => `<tr>
          <td><strong>${escapeHtml(row.client_name || '—')}</strong></td>
          <td>${escapeHtml(row.collector_name || '—')}<br><span class="meta">${escapeHtml(row.area || '—')}</span></td>
          <td>${escapeHtml(row.reason_label || row.reason_code || '—')}</td>
          <td>${escapeHtml(row.event_kind_label || row.event_kind || '—')}</td>
          <td>${escapeHtml(row.event_count ?? 0)}</td>
          <td>${formatMoney(row.total_past_due_amount)}</td>
          <td>${formatMoney(row.remaining_past_due_amount)}</td>
        </tr>`,
      )
      .join('')}</tbody>
  </table></div>`;
}

export function managementPastDueReportMarkup(payload = {}) {
  if (payload.schema_available === false) {
    return '<div class="notice-card warning"><strong>Past-Due reporting is not available.</strong><br>The authoritative reporting schema is not available on this server.</div>';
  }

  return `<div class="list-stack">
    <div class="notice-card"><strong>Read-only Past-Due reporting</strong><br>Summary totals and reason rows are returned by the protected SPINA server. This Web view does not calculate delinquency, penalties, balances, or schedules.</div>
    ${summaryMarkup(payload.summary ?? {})}
    <div class="section-heading"><div><h3>Reason summary</h3><p>Server-returned Client, Collector, Area, reason, and event grouping.</p></div></div>
    ${rowsMarkup(payload.rows)}
  </div>`;
}

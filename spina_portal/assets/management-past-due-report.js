import {
  asArray,
  emptyState,
  errorCard,
  escapeHtml,
  formatMoney,
  loadingPanel,
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
  return `<div class="metric-grid past-due-summary-grid">
    ${metricCard(
      'Past-due events',
      escapeHtml(summary.event_count ?? 0),
      'Recorded events',
    )}
    ${metricCard(
      'Amount past due',
      formatMoney(summary.total_past_due_amount),
      'Total amount',
    )}
    ${metricCard(
      'Still past due',
      formatMoney(summary.remaining_past_due_amount),
      'Remaining amount',
    )}
  </div>`;
}

function zeroLike(value) {
  const text = String(value ?? '0').trim();
  return /^0+(?:\.0+)?$/.test(text);
}

function isEmptyReport(summary = {}, rows = []) {
  return Number(summary.event_count ?? 0) === 0
    && zeroLike(summary.total_past_due_amount)
    && zeroLike(summary.remaining_past_due_amount)
    && asArray(rows).length === 0;
}

function rowsMarkup(rows) {
  const items = asArray(rows);
  if (!items.length) {
    return emptyState('No past-due reasons match the current filters.');
  }

  return `<div class="table-wrap"><table class="mobile-card-table past-due-table">
    <thead><tr><th>Client</th><th>Collector / Area</th><th>Reason</th><th>Event</th><th>Count</th><th>Amount past due</th><th>Still past due</th></tr></thead>
    <tbody>${items
      .map(
        (row) => `<tr>
          <td data-label="Client"><strong>${escapeHtml(row.client_name || '—')}</strong></td>
          <td data-label="Collector / Area">${escapeHtml(row.collector_name || '—')}<br><span class="meta">${escapeHtml(row.area || '—')}</span></td>
          <td data-label="Reason">${escapeHtml(row.reason_label || row.reason_code || '—')}</td>
          <td data-label="Event">${escapeHtml(row.event_kind_label || row.event_kind || '—')}</td>
          <td data-label="Count">${escapeHtml(row.event_count ?? 0)}</td>
          <td data-label="Amount past due">${formatMoney(row.total_past_due_amount)}</td>
          <td data-label="Still past due">${formatMoney(row.remaining_past_due_amount)}</td>
        </tr>`,
      )
      .join('')}</tbody>
  </table></div>`;
}
export function managementPastDueReportMarkup(payload = {}) {
  if (payload.schema_available === false) {
    return '<div class="notice-card warning"><strong>Past-Due reporting is not available.</strong><br>The authoritative reporting schema is not available on this server.</div>';
  }

  const summary = payload.summary ?? {};
  const rows = asArray(payload.rows);
  if (isEmptyReport(summary, rows)) {
    return `<div class="past-due-zero-state" data-past-due-zero>
      <strong>No past-due reasons found for these filters.</strong>
      <span class="meta">Read-only report from SPINA records.</span>
    </div>`;
  }

  return `<div class="list-stack past-due-report">
    <div class="notice-card past-due-readonly-notice"><strong>Read-only report</strong><br>Amounts and reasons come from SPINA records.</div>
    ${summaryMarkup(summary)}
    <div class="section-heading"><div><h3>Reasons by client and area</h3><p>Review recorded reasons, events, and remaining amounts.</p></div></div>
    ${rowsMarkup(rows)}
  </div>`;
}

export function bindManagementPastDueReport(context) {
  const form = context.root.querySelector('#management-past-due-report-search');
  const target = context.root.querySelector('#management-past-due-report-results');
  if (!form || !target) return;
  const owner=(context.getSession?.()||context.session)?.user?.id;
  let disposed=false,generation=0;
  const alive=()=>!disposed&&!context.signal?.aborted&&(!context.getSession||context.getSession()?.user?.id===owner);

  const reload = async () => {
    if(!alive())return false;
    const version=++generation;
    target.innerHTML = loadingPanel('Loading authoritative Past-Due reporting…');
    try {
      const data = await loadManagementPastDueReport(context.api, {
        startDate: form.querySelector('[name="start_date"]')?.value ?? '',
        endDate: form.querySelector('[name="end_date"]')?.value ?? '',
        area: form.querySelector('[name="area"]')?.value ?? '',
        reasonCode: form.querySelector('[name="reason_code"]')?.value ?? '',
        eventKind: form.querySelector('[name="event_kind"]')?.value ?? '',
      });
      if(!alive()||version!==generation)return false;
      target.innerHTML = managementPastDueReportMarkup(data);
      return true;
    } catch (error) {
      if(alive()&&version===generation)target.innerHTML = `${errorCard(error)}<button type="button" class="button button-outline" data-past-due-retry>Retry past-due report</button>`;
      target.querySelector('[data-past-due-retry]')?.addEventListener('click',()=>void reload(),{once:true});
      return false;
    }
  };

  const submit=async (event) => {
    event.preventDefault();
    await reload();
  };
  form.addEventListener('submit',submit);
  function dispose(){if(disposed)return;disposed=true;generation++;form.removeEventListener('submit',submit);context.signal?.removeEventListener('abort',dispose);}
  context.signal?.addEventListener('abort',dispose,{once:true});
  return {refresh:reload,dispose};
}

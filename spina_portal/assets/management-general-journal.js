import {
  asArray,
  badge,
  emptyState,
  escapeHtml,
  formatDate,
  formatDateTime,
  formatMoney,
  titleCase,
} from './ui.js';

const JOURNALS_PATH = '/api/v1/management/financial-accounting/journals';
const TRIAL_BALANCE_PATH = '/api/v1/management/financial-accounting/trial-balance';
const EXPORT_PATH = '/api/v1/management/financial-accounting/export';
const exportMounts = new WeakMap();

export function loadManagementGeneralJournal(api) {
  return api.request(JOURNALS_PATH);
}

export function loadManagementTrialBalance(api) {
  return api.request(TRIAL_BALANCE_PATH);
}

function exportDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000-')) return null;
  const time = Date.parse(`${value}T00:00:00.000Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? time : null;
}

function exportErrorMessage(error) {
  if (error?.code === 'invalid_export_file') return 'SPINA did not return a valid accounting file. Try again.';
  const messages = {
    0: 'SPINA could not reach the server. Check the connection and try again.',
    401: 'Your session has expired. Sign in again to download accounting books.',
    403: 'Accounting download access is unavailable for this account or device. Refresh after access is approved.',
    409: 'The accounting records need review before this download can be prepared. Contact Management.',
    413: 'This export is too large. Choose a smaller date range.',
    422: 'Choose valid dates in order, covering no more than 366 days including both dates.',
    503: 'The accounting service is temporarily unavailable. Try again later.',
  };
  return messages[error?.status] || 'The accounting download could not be prepared. Try again.';
}

export function bindManagementAccountingExport({ root, api, signal }) {
  exportMounts.get(root)?.();
  const form = root.querySelector('[data-accounting-export]');
  const status = root.querySelector('[data-accounting-export-status]');
  if (!form || !status) return () => {};
  const start = form.querySelector('[name="start_date"]');
  const end = form.querySelector('[name="end_date"]');
  const button = form.querySelector('button');
  const controller = new AbortController();
  const urls = new Map();
  let disposed = false;
  let pending = false;
  let accessDenied = false;

  function disable(disabled) {
    for (const element of [start, end, button]) element.disabled = disabled;
  }
  function revoke(url) {
    if (!urls.has(url)) return;
    clearTimeout(urls.get(url));
    urls.delete(url);
    URL.revokeObjectURL(url);
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    controller.abort();
    form.removeEventListener('submit', download);
    signal?.removeEventListener('abort', dispose);
    disable(true);
    for (const url of urls.keys()) revoke(url);
    if (exportMounts.get(root) === dispose) exportMounts.delete(root);
  }
  async function download(event) {
    event.preventDefault();
    if (disposed || pending || accessDenied) return;
    const startDate = start.value;
    const endDate = end.value;
    const startTime = exportDate(startDate);
    const endTime = exportDate(endDate);
    if (startTime === null || endTime === null || endTime < startTime || (endTime - startTime) / 86400000 >= 366) {
      status.setAttribute('role', 'alert');
      status.textContent = exportErrorMessage({ status: 422 });
      return;
    }
    pending = true;
    disable(true);
    status.setAttribute('role', 'status');
    status.textContent = 'Preparing your accounting review copy…';
    try {
      const blob = await api.request(`${EXPORT_PATH}?start_date=${startDate}&end_date=${endDate}`, {
        responseType: 'blob', signal: controller.signal,
      });
      if (disposed) return;
      if (!(blob instanceof Blob) || !blob.size || blob.type.split(';', 1)[0].toLowerCase() !== 'application/zip') {
        throw Object.assign(new Error('Invalid accounting file'), { code: 'invalid_export_file' });
      }
      const url = URL.createObjectURL(blob);
      urls.set(url, setTimeout(() => revoke(url), 1000));
      try {
        const link = document.createElement('a');
        link.href = url;
        link.download = `spina-accounting-${startDate}-to-${endDate}.zip`;
        link.click();
      } catch (error) {
        revoke(url);
        throw error;
      }
      status.textContent = 'Accounting review copy download prepared.';
    } catch (error) {
      if (disposed) return;
      accessDenied = [401, 403].includes(error?.status);
      status.setAttribute('role', 'alert');
      status.textContent = exportErrorMessage(error);
    } finally {
      pending = false;
      if (!disposed) disable(accessDenied);
    }
  }

  exportMounts.set(root, dispose);
  disable(false);
  form.addEventListener('submit', download);
  signal?.addEventListener('abort', dispose, { once: true });
  if (signal?.aborted) dispose();
  return dispose;
}

function journalLineRows(lines) {
  const items = asArray(lines);
  if (!items.length) {
    return '<tr><td colspan="5">No journal lines were returned.</td></tr>';
  }
  return items
    .map(
      (line) => `<tr>
        <td>${escapeHtml(line.account_code || '—')}</td>
        <td>${escapeHtml(line.account_name || '—')}</td>
        <td>${escapeHtml(line.description || '—')}</td>
        <td>${formatMoney(line.debit)}</td>
        <td>${formatMoney(line.credit)}</td>
      </tr>`,
    )
    .join('');
}

function journalEntriesMarkup(entries) {
  const items = asArray(entries);
  if (!items.length) {
    return emptyState('No General Journal entry is currently available.');
  }
  return `<div class="list-stack">${items
    .map(
      (entry) => `<article class="data-card">
        <div class="section-heading">
          <div>
            <h3>${escapeHtml(entry.entry_number || 'Unnumbered journal')}</h3>
            <p>${formatDate(entry.posting_date)} · ${escapeHtml(entry.period_label || 'No period label')}</p>
          </div>
          ${badge(entry.status || 'unknown')}
        </div>
        <p>${escapeHtml(entry.description || '—')}</p>
        <div class="detail-grid">
          <div class="detail-item"><span>Source</span><strong>${escapeHtml(titleCase(entry.source_type || 'unspecified'))}</strong></div>
          <div class="detail-item"><span>Reference</span><strong>${escapeHtml(entry.source_reference || '—')}</strong></div>
          <div class="detail-item"><span>Created by</span><strong>${escapeHtml(entry.created_by_name || '—')}</strong></div>
          <div class="detail-item"><span>Posted by</span><strong>${escapeHtml(entry.posted_by_name || '—')}</strong></div>
          <div class="detail-item"><span>Total debit</span><strong>${formatMoney(entry.total_debit)}</strong></div>
          <div class="detail-item"><span>Total credit</span><strong>${formatMoney(entry.total_credit)}</strong></div>
        </div>
        <p class="meta">Created ${formatDateTime(entry.created_at)}${entry.posted_at ? ` · Posted ${formatDateTime(entry.posted_at)}` : ''}</p>
        <div class="table-wrap"><table>
          <thead><tr><th>Account</th><th>Name</th><th>Description</th><th>Debit</th><th>Credit</th></tr></thead>
          <tbody>${journalLineRows(entry.lines)}</tbody>
        </table></div>
      </article>`,
    )
    .join('')}</div>`;
}

function trialBalanceRows(lines) {
  const items = asArray(lines);
  if (!items.length) {
    return '<tr><td colspan="7">No Trial Balance line is currently available.</td></tr>';
  }
  return items
    .map(
      (line) => `<tr>
        <td>${escapeHtml(line.account_code || '—')}</td>
        <td>${escapeHtml(line.account_name || '—')}</td>
        <td>${escapeHtml(titleCase(line.account_type || '—'))}</td>
        <td>${escapeHtml(titleCase(line.normal_balance || '—'))}</td>
        <td>${formatMoney(line.total_debit)}</td>
        <td>${formatMoney(line.total_credit)}</td>
        <td>${line.debit_balance && Number(line.debit_balance) !== 0 ? formatMoney(line.debit_balance) : formatMoney(line.credit_balance)}</td>
      </tr>`,
    )
    .join('');
}

function trialBalanceMarkup(payload) {
  const trial = payload?.trial_balance;
  if (!trial || typeof trial !== 'object') {
    return emptyState('No Trial Balance is currently available.');
  }
  return `<article class="data-card">
    <div class="section-heading">
      <div>
        <h3>Trial Balance</h3>
        <p>${escapeHtml(trial.period_label || 'All posted periods')}</p>
      </div>
      ${trial.balanced === true ? badge('balanced', 'success') : badge('not balanced', 'danger')}
    </div>
    <div class="detail-grid">
      <div class="detail-item"><span>Total debits</span><strong>${formatMoney(trial.total_debits)}</strong></div>
      <div class="detail-item"><span>Total credits</span><strong>${formatMoney(trial.total_credits)}</strong></div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Account</th><th>Name</th><th>Type</th><th>Normal</th><th>Total debit</th><th>Total credit</th><th>Ending balance</th></tr></thead>
      <tbody>${trialBalanceRows(trial.lines)}</tbody>
    </table></div>
  </article>`;
}

export function managementGeneralJournalMarkup({ journals = {}, trialBalance = {} } = {}) {
  const managementNotice = journals.can_manage === true
    ? 'The server reports journal-management permission for this account, but this Web surface is intentionally read-only.'
    : 'This Web surface is read-only.';
  const automaticPostingNotice = journals.automatic_loan_posting_enabled === true
    ? 'Automatic loan posting is enabled by the authoritative server.'
    : 'Automatic loan posting is not enabled.';

  return `<div class="list-stack">
    <div class="notice-card"><strong>Read-only accounting view</strong><br>${escapeHtml(managementNotice)} ${escapeHtml(automaticPostingNotice)}</div>
    <article class="data-card">
      <h3>Download accounting books</h3>
      <p>Download posted journal entries, ledger, trial balance and accounting audit records for an inclusive date range of up to 366 days. Opening balances are included.</p>
      <p class="meta">Accounting review copy. BIR registration and SAF acceptance require separate review and approval.</p>
      <form class="entry-form" data-accounting-export>
        <label>Start date<input type="date" name="start_date" min="0001-01-01" max="9999-12-31" required /></label>
        <label>End date<input type="date" name="end_date" min="0001-01-01" max="9999-12-31" required /></label>
        <button class="button button-secondary" type="submit">Download accounting review copy (ZIP)</button>
      </form>
      <div data-accounting-export-status role="status" aria-live="polite"></div>
    </article>
    ${trialBalanceMarkup(trialBalance)}
    <div class="section-heading"><div><h3>General Journal</h3><p>Server-returned journal entries and lines only.</p></div></div>
    ${journalEntriesMarkup(journals.entries)}
  </div>`;
}

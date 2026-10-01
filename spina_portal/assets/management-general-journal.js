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
  const tabs = Array.from(root.querySelectorAll?.('[data-accounting-book-tab]') ?? []);
  const panels = Array.from(root.querySelectorAll?.('[data-accounting-book-panel]') ?? []);
  const tabHandlers = new Map();

  function activateBookView(id) {
    for (const panel of panels) {
      if (panel.getAttribute('data-accounting-book-panel') === id) panel.removeAttribute('hidden');
      else panel.setAttribute('hidden', '');
    }
    for (const tab of tabs) {
      const selected = tab.getAttribute('data-accounting-book-tab') === id;
      tab.setAttribute('aria-selected', selected ? 'true' : 'false');
    }
  }

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
    for (const [tab, handler] of tabHandlers) tab.removeEventListener('click', handler);
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
  for (const tab of tabs) {
    const handler = (event) => {
      event?.preventDefault?.();
      if (disposed) return;
      activateBookView(tab.getAttribute('data-accounting-book-tab'));
    };
    tabHandlers.set(tab, handler);
    tab.addEventListener('click', handler);
  }
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
      (entry) => `<article class="data-card journal-evidence-card" data-journal-entry-id="${escapeHtml(entry.entry_id || '')}">
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
        <div class="inline-actions journal-evidence-actions" data-journal-actions-for="${escapeHtml(entry.entry_id || '')}"></div>
      </article>`,
    )
    .join('')}</div>`;
}

function isZeroMoney(value) {
  const text = String(value ?? '0').trim();
  return /^[+-]?0+(?:\.0+)?$/.test(text);
}

function trialBalanceLineHasActivity(line) {
  return ['total_debit', 'total_credit', 'debit_balance', 'credit_balance']
    .some((key) => !isZeroMoney(line?.[key]));
}

function trialBalanceEndingBalance(line) {
  return !isZeroMoney(line?.debit_balance)
    ? formatMoney(line.debit_balance)
    : formatMoney(line?.credit_balance);
}

function trialBalanceRows(lines) {
  const items = asArray(lines);
  if (!items.length) {
    return '<tr><td colspan="4">No Trial Balance line is currently available.</td></tr>';
  }
  return items
    .map(
      (line) => `<tr>
        <td data-label="Account"><strong>${escapeHtml(line.account_code || '—')} · ${escapeHtml(line.account_name || '—')}</strong><br><span class="meta">${escapeHtml(titleCase(line.account_type || '—'))} · ${escapeHtml(titleCase(line.normal_balance || '—'))} normal</span></td>
        <td data-label="Debit">${formatMoney(line.total_debit)}</td>
        <td data-label="Credit">${formatMoney(line.total_credit)}</td>
        <td data-label="Ending balance">${trialBalanceEndingBalance(line)}</td>
      </tr>`,
    )
    .join('');
}

function trialBalanceTable(lines) {
  return `<div class="table-wrap"><table class="mobile-card-table trial-balance-table">
    <thead><tr><th>Account</th><th>Debit</th><th>Credit</th><th>Ending balance</th></tr></thead>
    <tbody>${trialBalanceRows(lines)}</tbody>
  </table></div>`;
}

function trialBalanceMarkup(payload) {
  const trial = payload?.trial_balance;
  if (!trial || typeof trial !== 'object') {
    return emptyState('No Trial Balance is currently available.');
  }
  const lines = asArray(trial.lines);
  const activeLines = lines.filter(trialBalanceLineHasActivity);
  const noPostedActivity = activeLines.length === 0
    && isZeroMoney(trial.total_debits)
    && isZeroMoney(trial.total_credits);
  const balanceState = trial.balanced === true
    ? (noPostedActivity ? '<span class="badge info">Balanced · no posted activity</span>' : badge('balanced', 'success'))
    : badge('not balanced', 'danger');
  const allAccountsDisclosure = lines.length
    ? `<details data-trial-balance-all-accounts><summary>Show all accounts</summary>${trialBalanceTable(lines)}</details>`
    : '';

  return `<article class="data-card trial-balance-card">
    <div class="section-heading">
      <div>
        <h3>Trial Balance</h3>
        <p>${escapeHtml(trial.period_label || 'All posted activity')}</p>
      </div>
      ${balanceState}
    </div>
    <div class="detail-grid trial-balance-totals">
      <div class="detail-item"><span>Total debits</span><strong>${formatMoney(trial.total_debits)}</strong></div>
      <div class="detail-item"><span>Total credits</span><strong>${formatMoney(trial.total_credits)}</strong></div>
    </div>
    ${noPostedActivity
      ? `<div class="trial-balance-zero" data-trial-balance-zero><strong>No posted journal activity yet.</strong><span class="meta">The authoritative Trial Balance is currently zero.</span></div>${allAccountsDisclosure}`
      : `${trialBalanceTable(activeLines.length ? activeLines : lines)}${activeLines.length < lines.length ? allAccountsDisclosure : ''}`}
  </article>`;
}

export function managementGeneralJournalMarkup({ journals = {}, trialBalance = {} } = {}) {
  const automaticPosting = journals.automatic_loan_posting_enabled === true ? 'on' : 'off';
  const reviewNotice = journals.can_manage === true
    ? `Review drafts before posting. Automatic posting is ${automaticPosting}.`
    : `Read-only accounting evidence. Automatic posting is ${automaticPosting}.`;

  return `<div class="list-stack general-journal-workspace">
    <div class="notice-card"><strong>Accounting evidence</strong><br>${escapeHtml(reviewNotice)}</div>
    <div class="accounting-book-tabs" role="tablist" aria-label="Accounting books">
      <button type="button" class="accounting-book-tab active" data-accounting-book-tab="journal" aria-selected="true">General Journal</button>
      <button type="button" class="accounting-book-tab" data-accounting-book-tab="trial-balance" aria-selected="false">Trial Balance</button>
    </div>
    <section data-accounting-book-panel="journal">
      <div class="section-heading"><div><h3>General Journal</h3><p>Posted and draft journal evidence returned by SPINA.</p></div></div>
      ${journalEntriesMarkup(journals.entries)}
    </section>
    <section data-accounting-book-panel="trial-balance" hidden>
      ${trialBalanceMarkup(trialBalance)}
    </section>
    <details class="accounting-export-details" data-accounting-export-details>
      <summary>Export accounting books</summary>
      <div class="data-card">
        <p>Download posted journal entries, ledger, trial balance and accounting audit records for an inclusive date range of up to 366 days. Opening balances are included.</p>
        <p class="meta">Accounting review copy. BIR registration and SAF acceptance require separate review and approval.</p>
        <form class="entry-form" data-accounting-export>
          <label>Start date<input type="date" name="start_date" min="0001-01-01" max="9999-12-31" required /></label>
          <label>End date<input type="date" name="end_date" min="0001-01-01" max="9999-12-31" required /></label>
          <button class="button button-secondary" type="submit">Download accounting review copy (ZIP)</button>
        </form>
        <div data-accounting-export-status role="status" aria-live="polite"></div>
      </div>
    </details>
  </div>`;
}

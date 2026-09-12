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

export function loadManagementGeneralJournal(api) {
  return api.request(JOURNALS_PATH);
}

export function loadManagementTrialBalance(api) {
  return api.request(TRIAL_BALANCE_PATH);
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
    ${trialBalanceMarkup(trialBalance)}
    <div class="section-heading"><div><h3>General Journal</h3><p>Server-returned journal entries and lines only.</p></div></div>
    ${journalEntriesMarkup(journals.entries)}
  </div>`;
}

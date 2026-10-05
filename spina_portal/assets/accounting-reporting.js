import { escapeHtml as h, formatMoney, titleCase } from './ui.js';
import { disclosureMarkup, validateDisclosures } from './accounting-disclosures.js';

const exact = (value) => typeof value === 'string' && /^-?(0|[1-9]\d{0,15})\.\d{2}$/.test(value);
const id = (value) => typeof value === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(value);
const check = (value) => { if (!value) throw Error('Reporting evidence is incomplete. Reload before continuing.'); };
const amount = (value) => value === null || value === undefined ? 'Unavailable' : formatMoney(value);
const facts = (items) => `<dl>${items.map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(value)}</dd>`).join('')}</dl>`;
export const cashCategories = ['operating', 'investing', 'financing', 'internal'];

export function cashAllocations(rows, expectedAmount) {
  check(exact(expectedAmount) && Array.isArray(rows) && rows.length > 0 && rows.length <= 20);
  const expected = BigInt(expectedAmount.replace('.', ''));
  check(expected !== 0n);
  let total = 0n;
  for (const row of rows) {
    check(cashCategories.includes(row.category) && exact(row.amount));
    const value = BigInt(row.amount.replace('.', '')); check(value * expected > 0n); total += value;
  }
  check(total === expected);
  return rows.map(({ category, amount }) => ({ category, amount }));
}

export function validateReportingSupplement(value) {
  if (value?.journal_disclosures != null) validateDisclosures(value.journal_disclosures);
  const equity = value?.changes_in_equity, cash = value?.cash_flows, notes = value?.notes;
  check(equity && cash && notes && Array.isArray(value.noncash_activity));
  for (const field of ['opening_equity', 'profit_or_loss', 'closing_equity', 'reconciliation_difference']) check(exact(equity[field]));
  check(typeof equity.reconciled === 'boolean' && Array.isArray(equity.other_equity_movements));
  for (const row of equity.other_equity_movements) check(typeof row.account_code === 'string' && typeof row.account_name === 'string' && exact(row.amount));
  check(['cash_definition_required', 'cash_definition_changed', 'classification_required', 'complete_for_posted_ledger', 'cash_reconciliation_required'].includes(cash.status) && typeof cash.reconciled === 'boolean' && Number.isSafeInteger(cash.unclassified_line_count) && cash.unclassified_line_count >= 0 && Array.isArray(cash.unclassified_lines) && Array.isArray(cash.cash_lines) && cash.categories && typeof cash.categories === 'object' && !Array.isArray(cash.categories));
  for (const field of ['opening_cash', 'closing_cash', 'net_cash_flow', 'reconciliation_difference']) check(cash[field] === null || exact(cash[field]));
  if (cash.policy !== null) {
    check(id(cash.policy?.id) && id(cash.policy.book_id) && id(cash.policy.fiscal_period_id) && Number.isSafeInteger(cash.policy.version) && cash.policy.version > 0 && typeof cash.policy.cash_definition_valid === 'boolean');
    check(Array.isArray(cash.policy.cash_account_codes) && cash.policy.cash_account_codes.length > 0 && cash.policy.cash_account_codes.length <= 3 && cash.policy.cash_account_codes.every((code) => ['1010', '1020', '1030'].includes(code)) && new Set(cash.policy.cash_account_codes).size === cash.policy.cash_account_codes.length);
    if (cash.status === 'cash_definition_changed') {
      check(cash.policy.cash_definition_valid === false && cash.reconciled === false && ['opening_cash', 'closing_cash', 'net_cash_flow', 'reconciliation_difference'].every((key) => cash[key] === null) && cash.opening_balance_adjustments == null && Object.keys(cash.categories).length === 0);
    } else {
      check(cash.policy.cash_definition_valid === true && exact(cash.opening_balance_adjustments));
      for (const category of ['operating', 'investing', 'financing']) for (const field of ['receipts', 'payments', 'net']) check(exact(cash.categories?.[category]?.[field]));
    }
  } else check(cash.status === 'cash_definition_required' && cash.reconciled === false && ['opening_cash', 'closing_cash', 'net_cash_flow', 'reconciliation_difference'].every((key) => cash[key] === null));
  for (const row of cash.cash_lines) check(id(row.journal_line_id) && id(row.journal_entry_id) && ['1010', '1020', '1030'].includes(row.account_code) && exact(row.amount) && typeof row.source_type === 'string' && typeof row.is_opening_adjustment === 'boolean' && (row.source_type !== 'opening_balance' || row.is_opening_adjustment) && Number.isSafeInteger(row.classification_version) && row.classification_version >= 0 && (row.allocations === null || Array.isArray(row.allocations)));
  check(Array.isArray(notes.items) && ['reporting_policy_required', 'retained_management_notes'].includes(notes.status));
  for (const row of notes.items) check(['title', 'text', 'evidence_reference', 'evidence_digest'].every((key) => typeof row[key] === 'string' && row[key].length > 0));
  for (const row of value.noncash_activity) check(id(row.journal_entry_id) && typeof row.posting_date === 'string' && exact(row.gross_debit));
  if (value.comparative != null) {
    const prior = value.comparative; check(id(prior.period?.period_id) && typeof prior.period.label === 'string');
    for (const [part, lists, totals] of [['profit_or_loss', ['income_lines', 'expense_lines'], ['total_income', 'total_expenses', 'net_income']], ['financial_position', ['asset_lines', 'liability_lines', 'equity_lines'], ['total_assets', 'total_liabilities', 'recorded_equity', 'unclosed_earnings_to_date', 'total_equity', 'total_liabilities_and_equity']]]) {
      check(prior[part]); for (const total of totals) check(exact(prior[part][total]));
      for (const list of lists) { check(Array.isArray(prior[part][list])); for (const row of prior[part][list]) check(typeof row.account_code === 'string' && typeof row.account_name === 'string' && exact(row.amount)); }
    }
  }
  return value;
}

export function reportingSupplementMarkup(value, renderComparative = null) {
  if (!value) return '<p>Additional report evidence is unavailable. No complete reporting conclusion can be drawn.</p>';
  try { validateReportingSupplement(value); } catch { return '<p role="alert">Additional report evidence is incomplete. Refresh before relying on these reports.</p>'; }
  const equity = value.changes_in_equity, cash = value.cash_flows, notes = value.notes;
  return `<article class="data-card"><h3>Statement of Changes in Equity</h3>${facts([['Opening equity', amount(equity.opening_equity)], ['Profit or loss', amount(equity.profit_or_loss)], ['Closing equity', amount(equity.closing_equity)], ['Reconciliation difference', amount(equity.reconciliation_difference)]])}<p>${equity.reconciled ? 'Reconciled for the posted ledger' : 'Equity reconciliation needs review'}</p>${equity.other_equity_movements.map((row) => `<p>${h(row.account_code)} · ${h(row.account_name)} · ${h(amount(row.amount))}</p>`).join('')}<p>Formal retained-earnings transfers are excluded to avoid counting profit twice.</p></article>
  <article class="data-card"><h3>Statement of Cash Flows</h3><p>${h(cash.status === 'cash_definition_changed' ? 'Cash definition changed; review a new policy.' : titleCase(cash.status))}</p><p>Cash accounts: ${h(cash.policy?.cash_account_codes.join(', ') || 'Unavailable')}</p>${facts([['Opening cash', amount(cash.opening_cash)], ['Opening balance adjustments', amount(cash.opening_balance_adjustments)], ['Closing cash', amount(cash.closing_cash)], ['Net cash flow', amount(cash.net_cash_flow)], ['Reconciliation difference', amount(cash.reconciliation_difference)]])}${['operating', 'investing', 'financing'].map((category) => cash.categories?.[category] ? `<h4>${h(titleCase(category))}</h4>${facts([['Receipts', amount(cash.categories[category].receipts)], ['Payments', amount(cash.categories[category].payments)], ['Net', amount(cash.categories[category].net)]])}` : '').join('')}<p>Unclassified cash lines: ${cash.unclassified_line_count}. ${cash.reconciled ? 'Reconciled for the posted ledger.' : 'Cash flow evidence needs review.'}</p><p>Review cash definitions and line classifications in Reporting evidence. Internal transfers must offset within one journal or match both protected cash legs of one owned transfer in this period. Fees remain separate.</p></article>
  <article class="data-card"><h3>Retained reporting notes</h3><p>${h(notes.framework_label || 'Reporting framework has not been supplied.')}</p>${notes.items.map((row) => `<details><summary>${h(row.title)}</summary><p style="white-space:pre-wrap">${h(row.text)}</p>${facts([['Evidence reference', row.evidence_reference], ['Evidence fingerprint', row.evidence_digest]])}</details>`).join('') || '<p>No retained reporting notes are available.</p>'}</article>
  ${value.journal_disclosures ? disclosureMarkup(value.journal_disclosures) : `<article class="data-card"><h3>Journals with no cash movement</h3><p>This inventory excludes mixed journals containing both cash and noncash activity. Further noncash disclosure may be required.</p>${value.noncash_activity.map((row) => `<p>${h(row.entry_number || row.journal_entry_id)} · ${h(row.posting_date)} · Gross debit ${h(amount(row.gross_debit))}</p>`).join('') || `<p>${cash.policy?.cash_definition_valid === true ? 'No noncash activity returned for this period.' : 'Noncash activity is unavailable until a valid cash definition is retained.'}</p>`}</article>`}
  ${value.comparative && renderComparative ? `<details><summary>Comparative period · ${h(value.comparative.period?.label || 'Prior period')}</summary>${renderComparative(value.comparative)}</details>` : '<p>No comparative period returned.</p>'}<p>These reports cover the posted ledger only. Retained notes and classifications do not certify statutory compliance or complete source recognition.</p>`;
}

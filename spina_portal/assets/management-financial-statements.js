import {
  asArray,
  badge,
  emptyState,
  escapeHtml,
  formatDate,
  formatMoney,
} from './ui.js';

const STATEMENTS_PATH = '/api/v1/management/financial-accounting/statements';

export function loadManagementFinancialStatements(api) {
  return api.request(STATEMENTS_PATH);
}

function statementRows(lines) {
  const rows = asArray(lines);
  if (!rows.length) {
    return '<tr><td colspan="3">No posted General Ledger line is available.</td></tr>';
  }
  return rows
    .map(
      (line) => `<tr>
        <td>${escapeHtml(line.account_code || '—')}</td>
        <td>${escapeHtml(line.account_name || '—')}</td>
        <td>${formatMoney(line.amount)}</td>
      </tr>`,
    )
    .join('');
}

function statementTable(title, lines) {
  return `<article class="data-card">
    <h3>${escapeHtml(title)}</h3>
    <div class="table-wrap"><table>
      <thead><tr><th>Account</th><th>Name</th><th>Amount</th></tr></thead>
      <tbody>${statementRows(lines)}</tbody>
    </table></div>
  </article>`;
}

function totalItem(label, value) {
  return `<div class="detail-item"><span>${escapeHtml(label)}</span><strong>${formatMoney(value)}</strong></div>`;
}

export function financialStatementsMarkup(payload) {
  const statements = payload?.statements;
  if (!statements || typeof statements !== 'object') {
    return emptyState('No Financial Statement pack is currently available.');
  }

  const period = statements.period ?? {};
  const profitOrLoss = statements.profit_or_loss ?? {};
  const financialPosition = statements.financial_position ?? {};

  return `<div class="list-stack">
    <article class="data-card">
      <div class="section-heading">
        <div>
          <h3>${escapeHtml(period.label || 'Financial Statements')}</h3>
          <p>${formatDate(period.start_date)} – ${formatDate(period.end_date)}</p>
        </div>
        ${badge(period.status || 'unknown')}
      </div>
      <p class="meta">Source: ${escapeHtml(statements.source || 'authoritative server record')}</p>
    </article>

    <article class="data-card">
      <div class="section-heading"><div><h3>Statement of Profit or Loss</h3><p>Server-returned posted General Ledger values only.</p></div></div>
      <div class="card-grid">
        ${statementTable('Income', profitOrLoss.income_lines)}
        ${statementTable('Expenses', profitOrLoss.expense_lines)}
      </div>
      <div class="detail-grid">
        ${totalItem('Total income', profitOrLoss.total_income)}
        ${totalItem('Total expenses', profitOrLoss.total_expenses)}
        ${totalItem('Net income', profitOrLoss.net_income)}
      </div>
    </article>

    <article class="data-card">
      <div class="section-heading">
        <div><h3>Statement of Financial Position</h3><p>As of ${formatDate(financialPosition.as_of_date)}</p></div>
        ${financialPosition.balanced === true ? badge('balanced', 'success') : badge('not balanced', 'danger')}
      </div>
      <div class="card-grid">
        ${statementTable('Assets', financialPosition.asset_lines)}
        ${statementTable('Liabilities', financialPosition.liability_lines)}
        ${statementTable('Equity', financialPosition.equity_lines)}
      </div>
      <div class="detail-grid">
        ${totalItem('Total assets', financialPosition.total_assets)}
        ${totalItem('Total liabilities', financialPosition.total_liabilities)}
        ${totalItem('Recorded equity', financialPosition.recorded_equity)}
        ${totalItem('Unclosed earnings to date', financialPosition.unclosed_earnings_to_date)}
        ${totalItem('Total equity', financialPosition.total_equity)}
        ${totalItem('Total liabilities and equity', financialPosition.total_liabilities_and_equity)}
      </div>
    </article>

    ${statements.notice ? `<div class="notice-card"><strong>Statement notice</strong><br>${escapeHtml(statements.notice)}</div>` : ''}
  </div>`;
}

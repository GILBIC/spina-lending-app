import {
  asArray,
  badge,
  emptyState,
  escapeHtml,
  formatDate,
  formatDateTime,
} from './ui.js';
import { formatAuthoritativeMoney } from './client-schedule.js';

function loanRows(loans) {
  if (!loans.length) return emptyState('No loan record is available on this statement.');
  return `<div class="table-wrap"><table>
    <thead><tr><th>Loan</th><th>Type</th><th>Principal</th><th>Daily amount</th><th>Official balance</th><th>Released</th><th>Due date</th><th>Status</th></tr></thead>
    <tbody>${loans.map((loan) => `<tr>
      <td><strong>${escapeHtml(loan.loan_number || '—')}</strong></td>
      <td>${escapeHtml(loan.loan_type_name || loan.loan_type_code || 'Loan')}</td>
      <td>${formatAuthoritativeMoney(loan.principal)}</td>
      <td>${formatAuthoritativeMoney(loan.daily_amount)}</td>
      <td>${formatAuthoritativeMoney(loan.remaining_balance)}</td>
      <td>${formatDate(loan.date_released)}</td>
      <td>${formatDate(loan.due_date)}</td>
      <td>${badge(loan.status || 'unknown')}</td>
    </tr>`).join('')}</tbody>
  </table></div>`;
}

function paymentRows(payments) {
  if (!payments.length) return emptyState('No official payment receipt is available on this statement.');
  return `<div class="table-wrap"><table>
    <thead><tr><th>Date</th><th>Loan</th><th>Amount</th><th>Receipt</th><th>Official balance</th><th>Recorded</th><th>Status</th></tr></thead>
    <tbody>${payments.map((payment) => `<tr>
      <td>${formatDate(payment.collection_date)}</td>
      <td><strong>${escapeHtml(payment.loan_number || '—')}</strong><br><span class="meta">${escapeHtml(payment.loan_type_name || '')}</span></td>
      <td>${formatAuthoritativeMoney(payment.amount)}</td>
      <td>${escapeHtml(payment.receipt_number || '—')}</td>
      <td>${formatAuthoritativeMoney(payment.official_balance)}</td>
      <td>${formatDateTime(payment.recorded_at)}</td>
      <td>${payment.is_voided ? badge('voided', 'danger') : badge(payment.status || 'posted')}</td>
    </tr>`).join('')}</tbody>
  </table></div>`;
}

export function renderClientStatement(statement = {}) {
  const client = statement.client ?? {};
  const loans = asArray(statement.loans);
  const payments = asArray(statement.payments);

  return `<div class="list-stack">
    <article class="notice-card">
      <div class="section-heading">
        <div>
          <h3>Statement of Account</h3>
          <p class="meta">Read-only official loan and payment records supplied by the protected SPINA server.</p>
        </div>
        ${badge(client.status || 'unknown')}
      </div>
      <div class="loan-meta">
        <div class="detail-item"><span>Client</span><strong>${escapeHtml(client.client_name || '—')}</strong></div>
        <div class="detail-item"><span>Client code</span><strong>${escapeHtml(client.client_code || '—')}</strong></div>
        <div class="detail-item"><span>Area</span><strong>${escapeHtml(client.area || '—')}</strong></div>
      </div>
    </article>
    <article class="data-card">
      <div class="section-heading"><div><h3>Loan records</h3><p class="meta">Amounts below are server-returned values; this view does not recalculate them.</p></div></div>
      ${loanRows(loans)}
    </article>
    <article class="data-card">
      <div class="section-heading"><div><h3>Official payment records</h3><p class="meta">Receipt references and balances are shown exactly from posted SPINA records.</p></div></div>
      ${paymentRows(payments)}
    </article>
  </div>`;
}

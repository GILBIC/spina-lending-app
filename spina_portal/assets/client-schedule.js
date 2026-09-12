import {
  asArray,
  badge,
  escapeHtml,
  formatDate,
  formatMoney,
  setButtonBusy,
} from './ui.js';

export function renderClientSchedule(schedule = {}) {
  const rows = asArray(schedule.rows);
  const typeLabel = schedule.is_7x7 === true ? '7x7' : schedule.loan_type || 'Loan';
  const maturityLabel =
    schedule.contractual_maturity && schedule.operational_maturity &&
    schedule.contractual_maturity !== schedule.operational_maturity
      ? 'Current operational completion'
      : 'Current completion';

  return `<div class="notice-card">
    <strong>Authoritative SPINA schedule · ${escapeHtml(typeLabel)}</strong>
    <p class="meta">Read-only. Dates, amounts, status and maturity below come from the protected server schedule.</p>
    <div class="loan-meta">
      <div class="detail-item"><span>Contractual maturity</span><strong>${formatDate(schedule.contractual_maturity)}</strong></div>
      <div class="detail-item"><span>${escapeHtml(maturityLabel)}</span><strong>${formatDate(schedule.operational_maturity)}</strong></div>
      <div class="detail-item"><span>Past due</span><strong>${formatMoney(schedule.past_due_amount)}</strong></div>
      <div class="detail-item"><span>Schedule status</span><strong>${escapeHtml(schedule.maturity_status || '—')}</strong></div>
    </div>
    ${rows.length ? `<div class="table-wrap"><table>
      <thead><tr><th>Date</th><th>Required amount</th><th>Status</th><th>Remaining</th><th>Note</th></tr></thead>
      <tbody>${rows.map((row) => `<tr>
        <td>${formatDate(row.payment_date)}</td>
        <td>${formatMoney(row.amount)}</td>
        <td>${badge(row.status || 'scheduled')}</td>
        <td>${formatMoney(row.details?.remaining_amount)}</td>
        <td>${escapeHtml(row.details?.note || '—')}</td>
      </tr>`).join('')}</tbody>
    </table></div>` : '<div class="empty-state">No schedule rows are available for this loan.</div>'}
  </div>`;
}

export function bindClientScheduleButtons(context) {
  const { root, api } = context;
  for (const button of root.querySelectorAll('[data-client-schedule-loan]')) {
    button.addEventListener('click', async () => {
      const loanId = String(button.dataset.clientScheduleLoan || '').trim();
      const panel = button.closest('.loan-card')?.querySelector('[data-client-schedule-panel]');
      if (!loanId || !panel) return;

      setButtonBusy(button, true, 'Loading schedule…');
      panel.hidden = false;
      panel.innerHTML = '<div class="loading-panel"><strong>Loading authoritative schedule…</strong></div>';
      try {
        const schedule = await api.request(
          `/api/v1/client/loans/${encodeURIComponent(loanId)}/schedule`,
        );
        panel.innerHTML = renderClientSchedule(schedule);
        setButtonBusy(button, false);
        button.textContent = 'Refresh schedule';
      } catch (error) {
        panel.innerHTML = `<div class="error-card"><strong>Schedule unavailable.</strong><br>${escapeHtml(error?.message || 'The authoritative schedule could not be loaded.')}</div>`;
        setButtonBusy(button, false);
      }
    });
  }
}

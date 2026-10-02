import {asArray, badge, emptyState, errorCard, escapeHtml, formatDate, formatMoney, metricCard} from './ui.js';

const validCount = value => Number.isSafeInteger(value) && value >= 0;
const validMoney = value => typeof value === 'string' && /^\d+(?:\.\d{1,2})?$/.test(value);

export function managementPortfolioSummaryMarkup({status, summary = {}}) {
  const ready = status === 'ready';
  const count = value => ready && validCount(value) ? escapeHtml(value) : '—';
  return `<h3>Active portfolio · all clients</h3>
    ${status === 'error' ? '<p role="status">Portfolio summary unavailable</p>' : status === 'loading' ? '<p role="status">Loading portfolio…</p>' : ''}
    <div class="metric-grid management-loan-summary">
      ${metricCard('Active clients', count(summary.active_client_count))}
      ${metricCard('Active loans', count(summary.active_loan_count))}
      ${metricCard('Outstanding balance', ready && validMoney(summary.active_remaining_total) ? formatMoney(summary.active_remaining_total) : '—')}
      ${metricCard('Overdue loans', count(summary.overdue_active_count))}
    </div>`;
}

export function mountManagementPortfolio({root, api, signal, initialResult, getSession = () => null}) {
  let disposed = false;
  let generation = 0;
  const owner = getSession()?.user?.id;
  const alive = () => !disposed && !signal?.aborted && getSession()?.user?.id === owner;
  if (!root) return {refresh: async () => {}, dispose() {}};
  root.innerHTML = `<div class="section-heading"><div><h2>Clients & loans</h2><p>Search the official portfolio. A Client may have both Regular and 7x7 loans.</p></div></div>
    <form id="management-loan-search" class="search-bar">
      <input name="query" maxlength="120" aria-label="Search clients and loans" placeholder="Client name, code, area, or loan number" />
      <select name="status" aria-label="Loan status"><option value="active">Active</option><option value="paid">Paid</option><option value="all">All</option></select>
      <button class="button button-primary" type="submit">Search</button></form>
    <div data-portfolio-summary></div><h3>Search results</h3><div id="management-loan-results"></div>
    <button class="button button-outline" type="button" data-portfolio-retry hidden>Retry portfolio</button>`;
  const summaryRoot = root.querySelector('[data-portfolio-summary]');
  const results = root.querySelector('#management-loan-results');
  const retry = root.querySelector('[data-portfolio-retry]');
  const form = root.querySelector('#management-loan-search');
  function render(result) {
    if (!alive()) return;
    const failed = result.error || !result.data || !Array.isArray(result.data.loans);
    summaryRoot.innerHTML = managementPortfolioSummaryMarkup({status: failed ? 'error' : 'ready', summary: result.data?.summary});
    results.innerHTML = failed ? errorCard(result.error || new Error('Portfolio response unavailable. Retry this read.')) : loanTable(result.data);
    retry.hidden = !failed;
  }
  async function refresh() {
    if (!alive()) return;
    const version = ++generation;
    const query = String(form.querySelector('[name="query"]').value || '').trim();
    const selected = form.querySelector('[name="status"]').value || 'active';
    const status = ['active','paid','all'].includes(selected) ? selected : 'active';
    summaryRoot.innerHTML = managementPortfolioSummaryMarkup({status:'loading'});
    results.innerHTML = '<p role="status">Loading search results…</p>';
    retry.hidden = true;
    try {
      const data = await api.request(`/api/v1/management/loans?q=${encodeURIComponent(query)}&status=${status}&limit=100&offset=0`);
      if (alive() && generation === version) render({data});
    } catch (error) {
      if (alive() && generation === version) render({error});
    }
  }
  const search = event => {event.preventDefault(); void refresh();};
  const retryRead = () => {void refresh();};
  form.addEventListener('submit',search);
  retry.addEventListener('click',retryRead);
  function dispose() {
    if (disposed) return;
    disposed = true; generation += 1;
    form.removeEventListener('submit',search); retry.removeEventListener('click',retryRead);
    signal?.removeEventListener('abort',dispose);
  }
  signal?.addEventListener('abort',dispose,{once:true});
  if (initialResult) render(initialResult);
  else summaryRoot.innerHTML = managementPortfolioSummaryMarkup({status:'loading'});
  return {refresh,dispose};
}

function managementLoanTypeLabel(loan) {
  const raw = String(loan.loan_type_name || loan.loan_type_code || 'Loan').trim();
  const normalized = raw.toLowerCase().replaceAll('-', '').replaceAll('_', '').replaceAll(' ', '');
  return normalized === '7x7' || normalized === 'sevenbyseven' ? '7x7' : raw || 'Loan';
}

function managementClientLoanGroups(loans) {
  const groups = new Map();
  for (const loan of loans) {
    const key = String(
      loan.client_id
      || loan.client_code
      || `${loan.client_name || ''}|${loan.client_area || ''}`,
    );
    if (!groups.has(key)) groups.set(key, { client: loan, loans: [] });
    groups.get(key).loans.push(loan);
  }
  return [...groups.values()];
}

function managementLoanItem(loan) {
  const typeLabel = managementLoanTypeLabel(loan);
  const typeTone = typeLabel === '7x7' ? 'info' : 'warning';
  return `<article class="client-loan-item" data-client-loan-item>
    <div class="client-loan-item-heading">
      <div class="inline-actions">
        ${badge(typeLabel, typeTone)}
        <strong>${escapeHtml(loan.loan_number || 'Loan')}</strong>
      </div>
      <div class="inline-actions">
        ${badge(loan.loan_status || 'unknown')}
        ${loan.is_overdue ? '<span class="badge danger">Overdue</span>' : ''}
      </div>
    </div>
    <div class="detail-grid client-loan-detail-grid">
      <div class="detail-item"><span>Principal</span><strong>${formatMoney(loan.principal)}</strong></div>
      <div class="detail-item"><span>Official balance</span><strong>${formatMoney(loan.remaining_balance)}</strong></div>
      <div class="detail-item"><span>Daily amount</span><strong>${formatMoney(loan.daily_amount)}</strong></div>
      <div class="detail-item"><span>Due</span><strong>${formatDate(loan.due_date)}</strong></div>
    </div>
  </article>`;
}

function loanTable(data) {
  const loans = asArray(data.loans);
  if (!loans.length) return emptyState('No loan matches the current search.');
  const groups = managementClientLoanGroups(loans);
  return `<div class="client-loan-groups">${groups.map(({ client, loans: clientLoans }) => `
    <section class="client-loan-group" data-client-loan-group="${escapeHtml(client.client_id || client.client_code || '')}">
      <header class="client-loan-group-header">
        <div>
          <h3>${escapeHtml(client.client_name || 'Client')}</h3>
          <p class="meta">${escapeHtml(client.client_code || 'No client code')}${client.client_area ? ` · ${escapeHtml(client.client_area)}` : ''}</p>
        </div>
        <span class="badge info">${clientLoans.length} ${clientLoans.length === 1 ? 'loan' : 'loans'}</span>
      </header>
      <div class="client-loan-items">${clientLoans.map(managementLoanItem).join('')}</div>
    </section>
  `).join('')}</div>`;
}


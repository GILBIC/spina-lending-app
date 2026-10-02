import {asArray, badge, emptyState, errorCard, escapeHtml, formatDate, formatMoney, metricCard} from './ui.js';

const validCount = value => Number.isSafeInteger(value) && value >= 0;
const validMoney = value => typeof value === 'string' && /^\d+(?:\.\d{1,2})?$/.test(value);
const validId = value => typeof value === 'string' && /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(value);

export function managementLoanDetailMarkup(loan) {
  const text = value => value === null || value === undefined || value === '' ? '—' : escapeHtml(value);
  const money = value => validMoney(value) ? formatMoney(value) : '—';
  const fields = [
    ['Client', text(loan.client_name)], ['Client reference', text(loan.client_code)],
    ['Principal', money(loan.principal)], ['Official balance', money(loan.remaining_balance)],
    ['Agreed daily amount', money(loan.daily_amount)], ['Paid amount', money(loan.paid_amount)],
    ['Paid percentage', validMoney(loan.paid_percent) ? `${text(loan.paid_percent)}%` : '—'],
    ['Released', formatDate(loan.date_released)], ['Due', formatDate(loan.due_date)],
    ['Last payment', formatDate(loan.last_payment_date)], ['Advance through', formatDate(loan.advance_until)],
    ['PASS count', validCount(loan.pass_count) ? text(loan.pass_count) : '—'],
    ['Payment count', validCount(loan.payment_count) ? text(loan.payment_count) : '—'],
    ['Loan status', text(loan.loan_status)], ['Client status', text(loan.client_status)],
    ['Renewal status', text(loan.renewal_request_status)], ['Record version', text(loan.state_version)],
  ];
  return `<h3 tabindex="-1" data-portfolio-detail-title>${text(loan.loan_number || 'Loan details')}</h3><p class="meta">Read-only facts from this portfolio response. Refresh closes this detail so changed records can be selected again.</p><div class="detail-grid">${fields.map(([label,value])=>`<div class="detail-item"><span>${label}</span><strong>${value}</strong></div>`).join('')}</div><button type="button" class="button button-outline" data-portfolio-close>Close details</button>`;
}

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
  let offset = 0;
  let returned = 0;
  let loading = false;
  let queryKey = '';
  let detailCleanup = () => {};
  const owner = getSession()?.user?.id;
  const alive = () => !disposed && !signal?.aborted && getSession()?.user?.id === owner;
  if (!root) return {refresh: async () => {}, dispose() {}};
  root.innerHTML = `<div class="section-heading"><div><h2>Clients & loans</h2><p>Search the official portfolio. A Client may have both Regular and 7x7 loans.</p></div></div>
    <form id="management-loan-search" class="search-bar">
      <input name="query" maxlength="120" aria-label="Search clients and loans" placeholder="Client name, code, area, or loan number" />
      <select name="status" aria-label="Loan status"><option value="active">Active</option><option value="paid">Paid</option><option value="all">All</option></select>
      <button class="button button-primary" type="submit">Search</button></form>
    <div data-portfolio-summary></div><h3>Search results</h3><div id="management-loan-results"></div>
    <button class="button button-outline" type="button" data-portfolio-retry hidden>Retry portfolio</button>
    <div class="inline-actions"><button class="button button-outline" type="button" data-portfolio-previous disabled>Previous page</button><span class="meta" data-portfolio-page></span><button class="button button-outline" type="button" data-portfolio-next disabled>Next page</button></div>
    <p class="meta">Pages show up to 100 loan entries. Records can change between pages; search or refresh for current results. The portfolio summary covers all active clients.</p>
    <section class="data-card" data-portfolio-detail hidden></section>`;
  const summaryRoot = root.querySelector('[data-portfolio-summary]');
  const results = root.querySelector('#management-loan-results');
  const retry = root.querySelector('[data-portfolio-retry]');
  const form = root.querySelector('#management-loan-search');
  const detail = root.querySelector('[data-portfolio-detail]');
  const previous = root.querySelector('[data-portfolio-previous]');
  const next = root.querySelector('[data-portfolio-next]');
  const page = root.querySelector('[data-portfolio-page]');
  const closeDetail = () => {detailCleanup();detailCleanup=()=>{};detail.hidden=true;detail.innerHTML='';};
  function updatePaging() {
    previous.disabled = loading || offset === 0;
    next.disabled = loading || returned < 100;
    page.textContent = `Page ${offset / 100 + 1} · ${returned} returned loan entries`;
  }
  function render(result) {
    if (!alive()) return;
    const failed = result.error || !result.data || !Array.isArray(result.data.loans);
    summaryRoot.innerHTML = managementPortfolioSummaryMarkup({status: failed ? 'error' : 'ready', summary: result.data?.summary});
    results.innerHTML = failed ? errorCard(result.error || new Error('Portfolio response unavailable. Retry this read.')) : loanTable(result.data);
    retry.hidden = !failed;
    loading = false;
    returned = failed ? 0 : result.data.loans.length;
    updatePaging();
    if (!failed) for (const button of results.querySelectorAll('[data-portfolio-open]')) {
      button.addEventListener('click', () => {
        if (!alive() || loading) return;
        const loan = result.data.loans.find(row => validId(row.loan_id) && validId(row.client_id)
          && row.loan_id === button.getAttribute('data-portfolio-open') && row.client_id === button.getAttribute('data-portfolio-client'));
        if (!loan) return;
        closeDetail();detail.innerHTML=managementLoanDetailMarkup(loan);detail.hidden=false;
        detail.querySelector('[data-portfolio-detail-title]')?.focus();
        const close=()=>{closeDetail();button.focus?.();};
        const control=detail.querySelector('[data-portfolio-close]');control.addEventListener('click',close);
        detailCleanup=()=>control.removeEventListener('click',close);
      });
    }
  }
  async function refresh() {
    if (!alive()) return;
    const version = ++generation;
    const query = String(form.querySelector('[name="query"]').value || '').trim();
    const selected = form.querySelector('[name="status"]').value || 'active';
    const status = ['active','paid','all'].includes(selected) ? selected : 'active';
    const key = `${query}|${status}`;
    if (queryKey !== key) offset=0;
    queryKey=key;loading=true;closeDetail();updatePaging();
    summaryRoot.innerHTML = managementPortfolioSummaryMarkup({status:'loading'});
    results.innerHTML = '<p role="status">Loading search results…</p>';
    retry.hidden = true;
    try {
      const data = await api.request(`/api/v1/management/loans?q=${encodeURIComponent(query)}&status=${status}&limit=100&offset=${offset}`);
      if (alive() && generation === version) render({data});
    } catch (error) {
      if (alive() && generation === version) render({error});
    }
  }
  const search = event => {event.preventDefault();offset=0;void refresh();};
  const retryRead = () => {void refresh();};
  const previousPage=()=>{if(!alive()||loading||offset===0)return;offset=Math.max(0,offset-100);void refresh();};
  const nextPage=()=>{if(!alive()||loading||returned<100)return;offset+=100;void refresh();};
  form.addEventListener('submit',search);
  retry.addEventListener('click',retryRead);
  previous.addEventListener('click',previousPage);next.addEventListener('click',nextPage);
  function dispose() {
    if (disposed) return;
    disposed = true; generation += 1;
    form.removeEventListener('submit',search); retry.removeEventListener('click',retryRead);
    previous.removeEventListener('click',previousPage);next.removeEventListener('click',nextPage);closeDetail();
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
    ${validId(loan.loan_id) && validId(loan.client_id) ? `<button type="button" class="button button-outline button-small" data-portfolio-open="${escapeHtml(loan.loan_id)}" data-portfolio-client="${escapeHtml(loan.client_id)}">View loan details</button>` : ''}
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


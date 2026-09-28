import { sessionHasRole } from './roles.js';
import { asArray, escapeHtml as h, formatMoney, formatDate, hasPermission, titleCase } from './ui.js';

const BASE = '/api/v1/management/financial-accounting';
const WORKBOOK = `${BASE}/opening-balance-workbook`;
const UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const DIGEST = /^[0-9a-f]{64}$/i;
const mounts = new WeakMap();
const tabs = { periods: 'Overview & periods', close: 'Period close', capital: 'Initial capital', workbook: 'Opening workbook', opening: 'Opening journal', measurement: 'Loan measurement', outcomes: 'Historical outcomes', tax: 'Tax & ECL' };
const fact = (name, value) => `<div class="detail-item"><span>${h(name)}</span><strong>${h(value ?? 'Not available')}</strong></div>`;
const input = (name, label, { type = 'text', value = '', max = 500, required = true } = {}) => `<label>${h(label)}<input name="${name}" type="${type}" value="${h(value)}" maxlength="${max}"${required ? ' required' : ''} /></label>`;
const select = (name, label, choices, selected = '') => `<label>${h(label)}<select name="${name}" required><option value="">Choose…</option>${choices.map(([value, text]) => `<option value="${h(value)}"${value === selected ? ' selected' : ''}>${h(text)}</option>`).join('')}</select></label>`;
const button = (attribute, label) => `<button type="button" class="button button-outline" ${attribute}>${h(label)}</button>`;
const form = (attribute, fields, label) => `<form class="entry-form" ${attribute}>${fields}<button class="button button-primary" type="submit">${h(label)}</button></form>`;
function requireThat(condition, message) { if (!condition) throw new Error(message); }
function id(value) { requireThat(typeof value === 'string' && UUID.test(value), 'The server record identity is incomplete. Reload before continuing.'); return value; }
function money(value, nullable = false) {
  const text = String(value ?? '').trim();
  if (nullable && text === '') return null;
  requireThat(/^(0|[1-9]\d{0,15})(?:\.\d{1,2})?$/.test(text), 'Enter a non-negative amount with at most two decimal places.');
  const [whole, cents = ''] = text.split('.'); return `${whole}.${cents.padEnd(2, '0')}`;
}
function exact(value, signed = false) {
  requireThat(typeof value === 'string' && (signed ? /^-?\d+\.\d{2}$/ : /^\d+\.\d{2}$/).test(value), 'The server amount is incomplete. Reload before continuing.'); return value;
}
function date(value) { requireThat(/^\d{4}-\d{2}-\d{2}$/.test(value) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value, 'Enter a valid calendar date.'); return value; }
function token() { return Array.from(globalThis.crypto.getRandomValues(new Uint8Array(32)), (byte) => byte.toString(16).padStart(2, '0')).join(''); }

export async function mountManagementAccounting({ root, api, session, signal }) {
  mounts.get(root)?.();
  let disposed = false, epoch = 0, busy = false, blocked = false, selected = 'periods', page = 0;
  let data, listeners = [], childCleanup, childController;
  const can = (permission) => sessionHasRole(session, 'management') && hasPermission(session, permission);
  const active = (value = epoch) => !disposed && !signal?.aborted && value === epoch;
  function clearListeners() { for (const remove of listeners) remove(); listeners = []; childController?.abort(); childController = null; childCleanup?.(); childCleanup = null; }
  function dispose() { if (disposed) return; disposed = true; epoch++; clearListeners(); root.innerHTML = ''; signal?.removeEventListener('abort', dispose); if (mounts.get(root) === dispose) mounts.delete(root); }
  function listen(element, event, action) {
    if (!element) return;
    const handler = (e) => { e.preventDefault(); if (!active() || busy) return; try { action(e); } catch (error) { message(error.message); } };
    element.addEventListener(event, handler); listeners.push(() => element.removeEventListener(event, handler));
  }
  function message(text) { const region = root.querySelector('[data-accounting-message]'); if (region) region.textContent = text; }
  function frame(content) {
    clearListeners();
    root.innerHTML = `<nav aria-label="Accounting workflows">${Object.entries(tabs).map(([key, label]) => `<button type="button" class="button button-outline" data-accounting-tab="${key}"${busy || blocked ? ' disabled' : ''}>${label}</button>`).join('')}</nav><h3>${tabs[selected]}</h3>${button('data-accounting-refresh', 'Reload authoritative records')}<div data-accounting-message role="status"></div>${content}`;
    listen(root.querySelector('[data-accounting-refresh]'), 'click', () => load());
    for (const tab of root.querySelectorAll('[data-accounting-tab]')) listen(tab, 'click', () => { if (blocked) return; selected = tab.getAttribute('data-accounting-tab'); page = 0; void load(); });
  }
  function bindForm(selector, action) { for (const element of root.querySelectorAll(selector)) listen(element, 'submit', () => { if (!blocked) action(element); }); }
  const field = (element, name) => String(element.querySelector(`[name="${name}"]`)?.value ?? '').trim();
  function text(element, name, min = 1, max = 500) { const value = field(element, name); requireThat(value.length >= min && value.length <= max, `Complete ${titleCase(name)} within ${min}–${max} characters.`); return value; }
  function permission(value) { requireThat(can(value), 'This accounting permission is no longer available.'); }
  function review(title, facts, consequence, { path, method = 'POST', body, validate }) {
    requireThat(!blocked, 'Reload authoritative records before preparing another action.');
    requireThat(globalThis.navigator?.onLine !== false, 'Reconnect before preparing an accounting action.');
    const capturedEpoch = ++epoch;
    frame(`<article class="notice-card"><h4>${h(title)}</h4><div class="detail-grid">${facts.map(([key, value]) => fact(key, value)).join('')}</div><p>${h(consequence)}</p>${button('data-accounting-confirm', `Confirm: ${title}`)} ${button('data-accounting-cancel', 'Cancel')}</article>`);
    listen(root.querySelector('[data-accounting-cancel]'), 'click', () => render());
    listen(root.querySelector('[data-accounting-confirm]'), 'click', async () => {
      if (!active(capturedEpoch) || blocked || busy) return;
      busy = true;
      for (const control of root.querySelectorAll('button')) control.disabled = true;
      try {
        const result = await api.request(path, { method, body, financial: true, signal });
        if (!active(capturedEpoch)) return;
        requireThat(validate(result), 'The saved result could not be verified.');
        busy = false;
        await load();
      } catch (error) {
        if (!active(capturedEpoch)) return;
        busy = false;
        if ([401, 403, 426].includes(error.status)) { dispose(); root.innerHTML = '<p role="alert">Accounting access is unavailable. Sign in again or refresh your permissions.</p>'; return; }
        blocked = true;
        frame('<p role="alert">The action outcome is uncertain or the record changed. Reload authoritative records before preparing another action. No request will be retried automatically.</p>');
        message(error.message);
      }
    });
  }
  function periods() {
    requireThat(Array.isArray(data.fiscal_periods) && Array.isArray(data.accounts), 'The accounting overview is incomplete.');
    const manage = can('accounting.period.manage') && data.period_management_enabled === true;
    const summary = data.summary ?? {}, foundation = data.foundation ?? {};
    frame(`<p>${h(data.notice)}</p><h4>Operational source summary</h4><div class="detail-grid">${fact('Active loans', summary.active_loan_count)}${fact('Active principal', formatMoney(summary.active_principal))}${fact('Operational outstanding', formatMoney(summary.operational_outstanding))}${fact('Unremitted cash', formatMoney(summary.unremitted_cash))}${fact('Received remittances', formatMoney(summary.received_remittance_total))}${fact('Posted journals', foundation.posted_journal_count)}${fact('Draft journals', foundation.draft_journal_count)}</div><h4>Fiscal periods</h4>${data.fiscal_periods.map((row, index) => `<article class="sub-card"><h4>${h(row.label)}</h4><p>${formatDate(row.start_date)} – ${formatDate(row.end_date)} · ${h(titleCase(row.status))}</p><p>Posted journals: ${h(row.posted_journal_count ?? '—')} · Draft journals: ${h(row.draft_journal_count ?? '—')}</p>${manage && ['open', 'review'].includes(row.status) ? button(`data-period-status="${index}"`, row.status === 'open' ? 'Move to review' : 'Return to open') : ''}</article>`).join('')}
      ${manage ? form('data-period-create', input('label', 'Period label', { max: 80 }) + input('start_date', 'Start date', { type: 'date' }) + input('end_date', 'End date', { type: 'date' }), 'Review new fiscal period') : ''}
      <details><summary>Chart of accounts</summary>${data.accounts.map((row) => `<article class="sub-card"><h4>${h(row.code)} · ${h(row.name)}</h4><p>${h(titleCase(row.account_type))} · Normal balance ${h(row.normal_balance)} · ${row.is_posting === true ? 'Posting' : 'Summary'} · ${row.is_active === true ? 'Active' : 'Inactive'}</p></article>`).join('')}</details>
      <details><summary>Loan accounting policies</summary>${asArray(data.policies).map((row) => `<article class="sub-card"><h4>${h(row.name)}</h4><p>${h(row.operational_rule)}</p><p>${h(row.accounting_rule)}</p><p>${h(row.renewal_rule)}</p></article>`).join('')}</details>
      <details><summary>Loan cutover readiness · ${h(titleCase(data.cutover?.summary?.overall_status))}</summary>${asArray(data.cutover?.loans).map((row) => `<article class="sub-card"><h4>${h(row.loan_number)} · ${h(row.client_name)}</h4><p>${h(titleCase(row.readiness_status))}</p><p>${h(asArray(row.blockers).join('; '))}</p></article>`).join('')}</details>`);
    bindForm('[data-period-create]', (element) => {
      permission('accounting.period.manage'); const body = { label: text(element, 'label', 3, 80), start_date: date(field(element, 'start_date')), end_date: date(field(element, 'end_date')) };
      requireThat(body.end_date >= body.start_date, 'End date must follow the start date.');
      review('Create fiscal period', [['Label', body.label], ['Start', body.start_date], ['End', body.end_date]], 'Creates an open period. This does not post a journal or change a balance.', { path: `${BASE}/fiscal-periods`, body, validate: (result) => UUID.test(result?.period?.period_id ?? '') });
    });
    for (const element of root.querySelectorAll('[data-period-status]')) listen(element, 'click', () => {
      permission('accounting.period.manage'); const row = data.fiscal_periods[Number(element.getAttribute('data-period-status'))]; const target = row.status === 'open' ? 'review' : 'open';
      review('Change fiscal period status', [['Period', row.label], ['Current status', row.status], ['Next status', target]], 'Changes workflow state only. Formal period close is a separate protected action.', { path: `${BASE}/fiscal-periods/${id(row.period_id)}/status`, body: { status: target, confirm_close: false }, validate: (result) => result?.period?.period_id === row.period_id && result.period.status === target });
    });
  }
  function workbook() {
    requireThat(data.summary && Array.isArray(data.lines), 'The opening workbook is incomplete.');
    const summary = data.summary, manage = can('accounting.cutover.manage') && data.management_enabled === true;
    const editable = manage && summary.status === 'draft' && UUID.test(summary.workbook_id ?? '');
    frame(`<p>${h(data.notice)}</p><p>Cutover ${formatDate(summary.cutover_date)} · ${h(titleCase(summary.status))}</p><p>Debits ${formatMoney(summary.total_debit)} · Credits ${formatMoney(summary.total_credit)} · Variance ${formatMoney(summary.balance_variance)}</p>
      ${manage && !summary.workbook_id ? form('data-workbook-create', input('cutover_date', 'Cutover date', { type: 'date' }), 'Review workbook initialization') : ''}
      ${data.lines.map((row, index) => `<article class="sub-card"><h4>${h(row.account_code)} · ${h(row.account_name)}</h4><p>Source reference ${formatMoney(row.source_reference_amount)} · ${h(row.source_basis)}</p><p>${h(row.guidance)}</p><p>Proposed debit ${formatMoney(row.proposed_debit)} · Credit ${formatMoney(row.proposed_credit)} · ${h(titleCase(row.verification_status))}</p>${editable ? form(`data-workbook-line="${index}"`, input('debit', 'Proposed debit', { value: row.proposed_debit, required: false }) + input('credit', 'Proposed credit', { value: row.proposed_credit, required: false }) + select('verification_status', 'Evidence status', [['pending', 'Pending'], ['verified', 'Verified']], row.verification_status) + input('evidence_note', 'Evidence note', { value: row.evidence_note, required: false }), 'Review opening line') : ''}</article>`).join('')}
      ${editable ? form('data-workbook-policy', select('confirmed', 'Profit and loss migration policy approved', [['true', 'Confirmed'], ['false', 'Not confirmed']], String(summary.profit_loss_policy_confirmed === true)) + input('policy_note', 'Approved policy evidence note', { value: summary.profit_loss_policy_note, max: 1000, required: false }), 'Review policy evidence') : ''}
      ${editable && summary.ready_for_review === true ? button('data-workbook-status="review_ready"', 'Mark review ready') : manage && summary.status === 'review_ready' ? button('data-workbook-status="draft"', 'Reopen workbook draft') : ''}`);
    const valid = (result) => result?.summary && Array.isArray(result.lines) && (!summary.workbook_id || result.summary.workbook_id === summary.workbook_id);
    bindForm('[data-workbook-create]', (element) => { permission('accounting.cutover.manage'); const cutover = date(field(element, 'cutover_date')); review('Initialize opening workbook', [['Cutover date', cutover]], 'Snapshots source references for review. Does not post to the General Ledger.', { path: WORKBOOK, body: { cutover_date: cutover }, validate: valid }); });
    bindForm('[data-workbook-line]', (element) => {
      permission('accounting.cutover.manage'); const row = data.lines[Number(element.getAttribute('data-workbook-line'))];
      const body = { debit: money(field(element, 'debit'), true), credit: money(field(element, 'credit'), true), verification_status: field(element, 'verification_status'), evidence_note: field(element, 'evidence_note') || null };
      requireThat(['pending', 'verified'].includes(body.verification_status), 'Choose an evidence status.');
      requireThat(!(body.debit && body.debit !== '0.00' && body.credit && body.credit !== '0.00'), 'A line cannot have both a positive debit and credit.');
      requireThat(body.verification_status !== 'verified' || ((body.debit !== null || body.credit !== null) && (body.evidence_note?.length ?? 0) >= 3), 'Verified lines require an explicit amount and evidence note.');
      review('Save opening workbook line', [['Account', `${row.account_code} ${row.account_name}`], ['Debit', formatMoney(body.debit)], ['Credit', formatMoney(body.credit)], ['Evidence status', body.verification_status], ['Evidence note', body.evidence_note]], 'Records reviewed workbook evidence. Does not post a journal.', { path: `${WORKBOOK}/${id(summary.workbook_id)}/lines/${encodeURIComponent(row.account_code)}`, method: 'PUT', body, validate: valid });
    });
    bindForm('[data-workbook-policy]', (element) => { permission('accounting.cutover.manage'); const confirmed = field(element, 'confirmed'); requireThat(['true', 'false'].includes(confirmed), 'Choose the policy confirmation state.'); const note = text(element, 'policy_note', confirmed === 'true' ? 5 : 0, 1000); review('Save cutover policy evidence', [['Confirmed', confirmed === 'true' ? 'Yes' : 'No'], ['Policy note', note]], 'Records the approved policy evidence; it does not post an opening balance.', { path: `${WORKBOOK}/${id(summary.workbook_id)}/policy`, method: 'PUT', body: { confirmed: confirmed === 'true', policy_note: note || null }, validate: valid }); });
    for (const element of root.querySelectorAll('[data-workbook-status]')) listen(element, 'click', () => { permission('accounting.cutover.manage'); const status = element.getAttribute('data-workbook-status'); review('Change workbook status', [['Cutover date', summary.cutover_date], ['Current', summary.status], ['Next', status]], 'Journal preparation and posting remain separate protected actions.', { path: `${WORKBOOK}/${id(summary.workbook_id)}/status`, body: { status }, validate: valid }); });
  }
  function opening() {
    const draft = data.journal_draft;
    if (!draft) { frame('<p>Initialize an opening workbook before preparing its journal.</p>'); return; }
    id(draft.workbook_id);
    const prepare = can('accounting.opening_balance.prepare') && draft.preparation_ready === true && draft.draft_prepared === false;
    const post = can('accounting.opening_balance.post') && draft.opening_balance_posting_enabled === true && draft.automatic_source_posting_enabled === false && draft.posting_ready === true && draft.journal_status === 'draft';
    frame(`<p>${h(draft.notice)}</p><p>Cutover ${formatDate(draft.cutover_date)} · ${h(titleCase(draft.journal_status || 'Not prepared'))}</p><p>Debits ${formatMoney(draft.total_debit)} · Credits ${formatMoney(draft.total_credit)}</p><p>${h(draft.preparation_blocker || draft.posting_blocker || '')}</p>${prepare ? button('data-opening-prepare', 'Review journal preparation') : ''}${post ? button('data-opening-post', 'Review opening journal posting') : ''}`);
    const valid = (result) => result?.journal_draft?.workbook_id === draft.workbook_id;
    listen(root.querySelector('[data-opening-prepare]'), 'click', () => { permission('accounting.opening_balance.prepare'); review('Prepare opening journal', [['Cutover', draft.cutover_date], ['Workbook status', draft.workbook_status]], 'Prepares a system-generated draft. It does not post balances.', { path: `${WORKBOOK}/${draft.workbook_id}/journal-draft`, body: { confirm: true }, validate: valid }); });
    listen(root.querySelector('[data-opening-post]'), 'click', () => {
      permission('accounting.opening_balance.post'); const body = { confirm: true, journal_entry_id: id(draft.journal_entry_id), total_debit: exact(draft.total_debit), total_credit: exact(draft.total_credit) };
      requireThat(body.total_debit === body.total_credit, 'The opening journal is not balanced.');
      review('Post opening journal', [['Journal', draft.entry_number || draft.journal_entry_id], ['Cutover', draft.cutover_date], ['Debit', formatMoney(body.total_debit)], ['Credit', formatMoney(body.total_credit)]], 'Posts immutable opening balances to the General Ledger. The server revalidates the selected journal and totals.', { path: `${WORKBOOK}/${draft.workbook_id}/journal-draft/post`, body, validate: valid });
    });
  }
  function measurement() {
    requireThat(Array.isArray(data.measurement?.loans), 'Loan measurement data is incomplete.');
    const measurement = data.measurement;
    frame(`<p>${h(measurement.notice)}</p>${measurement.loans.map((row) => `<article class="sub-card"><h4>${h(row.loan_number)} · ${h(row.client_name)}</h4><p>${h(row.measurement_status)} · ${h(row.measurement_note)}</p><div class="detail-grid">${fact('Principal', formatMoney(row.principal))}${fact('Operational balance', formatMoney(row.operational_balance))}${fact('Gross carrying amount', formatMoney(row.gross_carrying_amount))}${fact('Effective interest income', formatMoney(row.effective_interest_income))}${fact('Cutover date', row.cutover_date)}</div></article>`).join('') || '<p>No loan measurements are available.</p>'}`);
  }
  function render() {
    if (!active()) return;
    if (selected === 'periods') periods();
    else if (selected === 'workbook') workbook();
    else if (selected === 'opening') opening();
    else if (selected === 'measurement') measurement();
    else if (selected === 'close') close();
    else if (selected === 'capital') capital();
    else if (selected === 'outcomes') outcomes();
  }
  async function load() {
    if (!active() || busy) return;
    const currentEpoch = ++epoch; blocked = false;
    frame('<p>Loading protected accounting records…</p>'); busy = true;
    try {
      if (selected === 'tax') {
        busy = false;
        frame('<div id="management-tax-ecl"></div>');
        childController = new AbortController();
        const childSignal = childController.signal;
        const module = await import('./management-tax-ecl.js');
        if (!active(currentEpoch)) return;
        const cleanup = await module.mountManagementTaxEcl({ root: root.querySelector('#management-tax-ecl'), api, session, signal: childSignal });
        if (!active(currentEpoch)) cleanup?.(); else childCleanup = cleanup;
      } else {
        const paths = { periods: BASE, close: `${BASE}/period-close`, capital: `${BASE}/initial-capital-funding?limit=100&offset=${page * 100}`, workbook: WORKBOOK, opening: WORKBOOK, measurement: WORKBOOK, outcomes: `${BASE}/ecl-outcome-review?review_status=all&limit=100&offset=${page * 100}` };
        data = await api.request(paths[selected], { signal });
        if (!active(currentEpoch)) return;
        if (selected === 'opening' && data.summary?.workbook_id) {
          const workbookId = id(data.summary.workbook_id);
          data = await api.request(`${WORKBOOK}/${workbookId}/journal-draft`, { signal });
          requireThat(data.journal_draft?.workbook_id === workbookId, 'The journal does not match the selected workbook.');
        }
        if (!active(currentEpoch)) return;
        busy = false; render();
      }
    } catch (error) {
      if (!active(currentEpoch)) return;
      if ([401, 403, 426].includes(error.status)) { dispose(); root.innerHTML = '<p role="alert">Accounting access is unavailable. Sign in again or refresh your permissions.</p>'; return; }
      busy = false; blocked = true; frame(`<p role="alert">${h(error.message || 'Accounting records could not be loaded.')}</p>`);
    } finally { if (active(currentEpoch)) busy = false; }
  }
  function close() {
    requireThat(Array.isArray(data.items), 'The period-close queue is incomplete.');
    const protectedPolicy = (row) => row.protected_period_close_enabled === true && row.retained_earnings_close_enabled === true && row.closed_period_posting_protection_enabled === true && row.period_reopen_enabled === false && row.automatic_source_posting === false;
    const canPrepare = (row) => protectedPolicy(row) && data.permissions?.close_prepare === true && can('accounting.period.close.prepare') && row.close_status === 'ready_to_prepare';
    const canPost = (row) => protectedPolicy(row) && data.permissions?.close_post === true && can('accounting.period.close.post') && row.close_status === 'prepared_confirmation_required' && UUID.test(row.preparation_id ?? '') && UUID.test(row.journal_entry_id ?? '') && DIGEST.test(row.close_digest ?? '') && Number.isInteger(row.temporary_account_count) && typeof row.net_income === 'string' && typeof row.retained_earnings_balance_before === 'string';
    frame(`<p>${h(data.notice)}</p>${data.items.map((row, index) => `<article class="sub-card"><h4>${h(row.label)}</h4><p>${h(titleCase(row.close_status))} · ${h(row.close_blocker || '')}</p><div class="detail-grid">${fact('Period end', row.end_date)}${fact('Net income', formatMoney(row.net_income))}${fact('Retained earnings before close', formatMoney(row.retained_earnings_balance_before))}${fact('Temporary accounts', row.temporary_account_count)}</div>${canPrepare(row) ? button(`data-close-prepare="${index}"`, 'Review close preparation') : ''}${canPost(row) ? button(`data-close-post="${index}"`, 'Review retained earnings & close') : ''}</article>`).join('') || '<p>No fiscal periods are available.</p>'}`);
    for (const element of root.querySelectorAll('[data-close-prepare]')) listen(element, 'click', () => {
      const row = data.items[Number(element.getAttribute('data-close-prepare'))]; requireThat(canPrepare(row), 'Current close preparation authority is required.');
      review('Prepare formal period close', [['Period', row.label], ['End', row.end_date], ['Status', row.fiscal_period_status]], 'Prepares the protected close from current posted journals. It does not close the period yet.', { path: `${BASE}/period-close/${id(row.fiscal_period_id)}/prepare`, body: { confirm: true }, validate: (result) => result?.item?.fiscal_period_id === row.fiscal_period_id });
    });
    for (const element of root.querySelectorAll('[data-close-post]')) listen(element, 'click', () => {
      const row = data.items[Number(element.getAttribute('data-close-post'))]; requireThat(canPost(row), 'Current protected close evidence is required.');
      const body = { confirm: true, confirmation_token: token(), expected_close_digest: row.close_digest, expected_net_income: exact(row.net_income, true), expected_retained_earnings_account_code: '3100', expected_period_end_date: date(row.end_date) };
      review('Post retained earnings & close', [['Period', row.label], ['End', row.end_date], ['Net income', formatMoney(row.net_income)], ['Retained earnings before', formatMoney(row.retained_earnings_balance_before)]], 'Immutably posts the retained-earnings close and closes this fiscal period. The reviewed evidence is revalidated by the server.', { path: `${BASE}/period-close/${id(row.fiscal_period_id)}/post`, body, validate: (result) => result?.item?.fiscal_period_id === row.fiscal_period_id });
    });
  }
  function pagination(count) {
    return `<p>Records ${page * 100 + 1}–${page * 100 + count}</p>${page > 0 ? button('data-accounting-previous', 'Previous 100') : ''}${count === 100 ? button('data-accounting-next', 'Next 100') : ''}`;
  }
  function bindPagination() {
    listen(root.querySelector('[data-accounting-previous]'), 'click', () => { page--; void load(); });
    listen(root.querySelector('[data-accounting-next]'), 'click', () => { page++; void load(); });
  }
  function capital() {
    requireThat(Array.isArray(data.items) && Array.isArray(data.cash_accounts), 'The initial-capital queue is incomplete.');
    const protectedPolicy = (row) => row.protected_initial_capital_funding_enabled === true && row.synthetic_opening_balance_required === false && row.automatic_source_posting === false;
    const allowed = (name) => protectedPolicy(data) && data.permissions?.[name] === true && can(`accounting.initial_capital.${name === 'evidence_record' ? 'evidence.record' : name}`);
    const canPrepare = (row) => allowed('prepare') && protectedPolicy(row) && row.capital_account_code === '3000' && row.accounting_status === 'evidence_ready' && row.journal_entry_id == null && row.fiscal_period_id == null && row.accounting_blocker == null;
    const canPost = (row) => allowed('post') && protectedPolicy(row) && row.capital_account_code === '3000' && row.accounting_status === 'prepared_not_posted' && UUID.test(row.journal_entry_id ?? '') && row.journal_status === 'draft' && UUID.test(row.fiscal_period_id ?? '') && UUID.test(row.prepared_by_user_id ?? '') && typeof row.prepared_at === 'string';
    frame(`<p>${h(data.notice)}</p>${allowed('evidence_record') ? form('data-capital-evidence', input('funding_date', 'Actual funding date', { type: 'date' }) + input('amount', 'Actual amount received') + select('cash_account_code', 'Receiving cash account', data.cash_accounts.map((row) => [row.code, `${row.code} · ${row.name}`])) + input('evidence_source', 'Evidence source', { max: 120 }) + input('evidence_reference', 'Retained evidence reference', { max: 240 }) + input('evidence_digest', 'Evidence fingerprint (SHA-256)', { max: 64 }) + input('evidence_note', 'Retained evidence and reconciliation note', { max: 4000 }), 'Review actual capital evidence') : ''}
      ${data.items.map((row, index) => `<article class="sub-card"><h4>${h(row.evidence_reference)}</h4><p>${formatDate(row.funding_date)} · ${formatMoney(row.amount)} · ${h(titleCase(row.accounting_status))}</p><p>${h(row.cash_account_code)} · ${h(row.cash_account_name)}</p><p>${h(row.evidence_note)}</p><p>${h(row.accounting_blocker || '')}</p>${canPrepare(row) ? button(`data-capital-prepare="${index}"`, 'Review capital journal preparation') : ''}${canPost(row) ? button(`data-capital-post="${index}"`, 'Review capital journal posting') : ''}</article>`).join('')}${pagination(data.items.length)}`);
    bindPagination();
    bindForm('[data-capital-evidence]', (element) => {
      requireThat(allowed('evidence_record'), 'Capital evidence permission is required.');
      const body = { idempotency_key: globalThis.crypto.randomUUID(), funding_date: date(field(element, 'funding_date')), amount: money(field(element, 'amount')), cash_account_code: field(element, 'cash_account_code'), evidence_source: text(element, 'evidence_source', 1, 120), evidence_reference: text(element, 'evidence_reference', 1, 240), evidence_digest: field(element, 'evidence_digest').toLowerCase(), evidence_note: text(element, 'evidence_note', 20, 4000) };
      requireThat(body.amount !== '0.00' && DIGEST.test(body.evidence_digest) && data.cash_accounts.some((row) => row.code === body.cash_account_code), 'Choose an eligible cash account, positive exact amount and valid evidence fingerprint.');
      review('Record initial capital evidence', [['Funding date', body.funding_date], ['Actual amount', formatMoney(body.amount)], ['Cash account', body.cash_account_code], ['Source', body.evidence_source], ['Reference', body.evidence_reference], ['Evidence note', body.evidence_note]], 'Records an actual funding event with retained evidence. It does not transfer money or post a journal.', { path: `${BASE}/initial-capital-funding/evidence`, body, validate: (result) => UUID.test(result?.item?.evidence_id ?? '') && result.item.amount === body.amount && result.item.evidence_digest === body.evidence_digest });
    });
    for (const element of root.querySelectorAll('[data-capital-prepare]')) listen(element, 'click', () => { const row = data.items[Number(element.getAttribute('data-capital-prepare'))]; requireThat(canPrepare(row), 'Current capital evidence is required.'); review('Prepare initial capital journal', [['Reference', row.evidence_reference], ['Amount', formatMoney(row.amount)], ['Cash account', row.cash_account_code]], 'Prepares a draft for the actual funding evidence. It does not post the journal yet.', { path: `${BASE}/initial-capital-funding/${id(row.evidence_id)}/prepare`, body: { confirm: true }, validate: (result) => result?.item?.evidence_id === row.evidence_id }); });
    for (const element of root.querySelectorAll('[data-capital-post]')) listen(element, 'click', () => {
      const row = data.items[Number(element.getAttribute('data-capital-post'))]; requireThat(canPost(row) && DIGEST.test(row.evidence_digest ?? ''), 'Current prepared capital evidence is required.');
      const body = { confirm: true, confirmation_token: token(), expected_evidence_digest: row.evidence_digest, expected_amount: exact(row.amount), expected_cash_account_code: row.cash_account_code, expected_posting_date: date(row.funding_date), expected_fiscal_period_id: id(row.fiscal_period_id) };
      review('Post initial capital journal', [['Reference', row.evidence_reference], ['Funding date', row.funding_date], ['Amount', formatMoney(row.amount)], ['Cash account', row.cash_account_code], ['Capital account', '3000']], 'Immutably posts the prepared actual capital funding journal. No synthetic opening balance is created.', { path: `${BASE}/initial-capital-funding/${id(row.evidence_id)}/post`, body, validate: (result) => result?.item?.evidence_id === row.evidence_id });
    });
  }
  function outcomes() {
    requireThat(Array.isArray(data.episodes), 'The historical outcome queue is incomplete.');
    const canReview = can('accounting.ecl.review') && data.review_permission === true;
    frame(`<p>${h(data.notice)}</p>${data.episodes.map((row, index) => `<article class="sub-card"><h4>${h(row.episode_key)} · ${h(row.borrower_key)}</h4><p>${h(titleCase(row.source_quality_status))} · ${h(titleCase(row.review_status))}</p><p>${h(row.source_quality_note || '')}</p><div class="detail-grid">${fact('Principal', formatMoney(row.principal))}${fact('Cash collected', formatMoney(row.cash_collected))}${fact('Outcome evidence', row.outcome_evidence)}${fact('Current reviewed label', row.explicit_default_label === true ? 'Default' : row.explicit_default_label === false ? 'Non-default' : 'Not reviewed')}</div><p>${h(row.review_note || '')}</p>${canReview && row.source_quality_status === 'ready_for_outcome_labeling' ? form(`data-outcome-review="${index}"`, select('default_label', 'Evidence-backed outcome', [['true', 'Default'], ['false', 'Non-default']]) + select('evidence_basis', 'Evidence basis', [['source_document', 'Source document'], ['collection_history', 'Collection history'], ['renewal_settlement', 'Renewal settlement'], ['management_review', 'Management review']]) + input('evidence_reference', 'Retained evidence reference', { max: 300 }) + input('review_note', 'Review note', { max: 1000 }), 'Review outcome label') : ''}</article>`).join('')}${pagination(data.episodes.length)}`);
    bindPagination();
    bindForm('[data-outcome-review]', (element) => {
      permission('accounting.ecl.review'); const row = data.episodes[Number(element.getAttribute('data-outcome-review'))];
      const decision = field(element, 'default_label'), basis = field(element, 'evidence_basis');
      requireThat(Number.isSafeInteger(row.historical_episode_id) && row.historical_episode_id > 0 && ['true', 'false'].includes(decision) && ['source_document', 'collection_history', 'renewal_settlement', 'management_review'].includes(basis), 'Choose a reviewed outcome and evidence basis for this episode.');
      const body = { default_label: decision === 'true', evidence_basis: basis, evidence_reference: text(element, 'evidence_reference', 1, 300), review_note: text(element, 'review_note', 1, 1000) };
      review('Record historical outcome review', [['Episode', row.episode_key], ['Borrower', row.borrower_key], ['Outcome', body.default_label ? 'Default' : 'Non-default'], ['Evidence', body.evidence_reference], ['Review note', body.review_note]], 'Records an explicit reviewed label with audit history. It does not calculate ECL or post a journal.', { path: `${BASE}/ecl-outcome-review/${row.historical_episode_id}`, body, validate: (result) => result?.historical_episode_id === row.historical_episode_id });
    });
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true });
  if (!can('accounting.view') || signal?.aborted) { root.innerHTML = '<p>Management accounting access is required.</p>'; return dispose; }
  await load(); return dispose;
}

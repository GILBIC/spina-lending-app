import { sessionHasRole } from './roles.js';
import { escapeHtml as h, formatMoney, hasPermission } from './ui.js';
import { createTreasuryClient } from './treasury-api.js';
import { cashAllocations, cashCategories, reportingSupplementMarkup, validateReportingSupplement } from './accounting-reporting.js';

const BASE = '/api/v1/management/financial-accounting';
const UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const DIGEST = /^[a-f0-9]{64}$/;
const MONEY = /^(0|[1-9]\d{0,15})\.\d{2}$/;
const kinds = { '2000': ['trade_payable', 'Trade payable'], '2300': ['borrowing_external', 'External borrowing'], '2310': ['borrowing_owner', 'Owner borrowing'], '2320': ['interest', 'Interest payable'], '2330': ['wages', 'Wages payable'], '2340': ['contrib', 'Contributions payable'] };
const mounts = new WeakMap();
const check = (ok, message = 'These accounting records are incomplete. Refresh before continuing.') => { if (!ok) throw Error(message); };
const isId = (value) => typeof value === 'string' && UUID.test(value);
const isMoney = (value, signed = false) => typeof value === 'string' && MONEY.test(signed ? value.replace(/^-/, '') : value);
const isDate = (value) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
const scopeKey = (session) => JSON.stringify([session?.user, session?.permissions, session?.access_token, session?.device_id]);
const button = (attr, label) => `<button type="button" class="button button-outline" ${attr}>${h(label)}</button>`;
const input = (name, label, type = 'text', required = true) => `<label>${h(label)}<input name="${name}" type="${type}"${required ? ' required' : ''} maxlength="${name === 'evidence_digest' ? 64 : 1000}" /></label>`;
const select = (name, label, rows, value = '') => `<label>${h(label)}<select name="${name}" required><option value="">Choose…</option>${rows.map(([id, text]) => `<option value="${h(id)}"${id === value ? ' selected' : ''}>${h(text)}</option>`).join('')}</select></label>`;
const facts = (rows) => `<dl>${rows.map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(value ?? 'Not supplied')}</dd>`).join('')}</dl>`;
const evidenceFields = () => input('evidence_reference', 'Retained evidence reference') + input('evidence_digest', 'Evidence fingerprint (SHA-256)');

// A failed response never causes a new request identity or an automatic retry.
export function createSourceAccountingClient({ api, session, getSession = () => session, signal, onDenied = () => {} }) {
  const initial = scopeKey(getSession()), controller = new AbortController();
  let disposed = false, attempt = null, busy = false;
  function dispose() { disposed = true; attempt = null; controller.abort(); signal?.removeEventListener('abort', dispose); }
  function current() { if (disposed || signal?.aborted || scopeKey(getSession()) !== initial) { dispose(); throw Error('Access changed. Reopen this accounting task.'); } }
  async function request(path, options = {}) {
    current();
    try { const value = await api.request(BASE + path, { ...options, signal: controller.signal }); current(); return value; }
    catch (error) { if ([401, 403, 426].includes(error.status)) { dispose(); onDenied(); } throw error; }
  }
  async function send() {
    current(); check(!busy && attempt, 'Recover the unchanged request before another action.');
    check(globalThis.navigator?.onLine !== false, 'Reconnect before sending this request.');
    busy = true; const held = attempt;
    try { const value = await request(held.path, { method: 'POST', body: structuredClone(held.body), financial: true }); check(held.validate(value), 'The saved result could not be verified. Retry the unchanged request.'); attempt = null; return value; }
    finally { busy = false; }
  }
  signal?.addEventListener('abort', dispose, { once: true });
  return { get: request, submit: async (path, body, validate) => { current(); check(!attempt && !busy, 'Recover the unchanged request before another action.'); attempt = { path, body: structuredClone(body), validate }; return send(); }, retry: send, pending: () => attempt !== null, reset: () => { check(!busy); attempt = null; }, dispose };
}

export function receiptSource(value, { bookId, accountId, receiptId, mappingId }) {
  check(value?.book_id === bookId && value.treasury_account_id === accountId && value.receipt_id === receiptId && value.mapping_id === mappingId && [value.event_id, value.fiscal_period_id].every(isId) && DIGEST.test(value.source_digest) && isMoney(value.amount) && value.amount !== '0.00' && isDate(value.posting_date));
  check(['1010', '1030'].includes(value.mapping?.cash_snapshot?.code) && value.mapping?.liability_snapshot?.code === '2200' && DIGEST.test(value.evidence?.sha256));
  return value;
}

export function liabilitySchedule(value, bookId) {
  check(value?.book?.book_id === bookId && isDate(value.as_of) && value.comprehensive_source_coverage === false && typeof value.registered_controls_reconciled === 'boolean');
  for (const key of ['obligations', 'movements', 'reconciliation', 'unregistered_lines']) check(Array.isArray(value[key]));
  for (const row of value.obligations) check(isId(row.obligation_id) && row.book_id === bookId && kinds[row.account_code]?.[0] === row.kind && typeof row.counterparty === 'string' && isMoney(row.recognized_amount) && isMoney(row.outstanding_amount) && (row.due_date === null || isDate(row.due_date)));
  for (const row of value.movements) check([row.claim_id, row.obligation_id, row.journal_line_id].every(isId) && ['recognition', 'settlement', 'reversal'].includes(row.kind) && isDate(row.posting_date) && isMoney(row.signed_amount, true) && (row.reverses_claim_id === null || isId(row.reverses_claim_id)));
  for (const row of value.reconciliation) check(kinds[row.account_code] && [row.ledger_balance, row.schedule_balance, row.difference].every((v) => isMoney(v, true)) && Number.isSafeInteger(row.unregistered_line_count) && row.unregistered_line_count >= 0);
  for (const row of value.unregistered_lines) check([row.journal_line_id, row.journal_entry_id].every(isId) && kinds[row.account_code] && isDate(row.posting_date) && isMoney(row.debit) && isMoney(row.credit) && typeof row.source_type === 'string' && (row.source_reference === null || typeof row.source_reference === 'string') && (row.reversal_of_entry_id === null || isId(row.reversal_of_entry_id)));
  return value;
}

export async function mountManagementSourceAccounting({ root, api, session, getSession = () => session, signal, mode }) {
  mounts.get(root)?.();
  const controller = new AbortController();
  const initialScope = scopeKey(getSession());
  let disposed = false, epoch = 0, busy = false, removers = [], book, canConfigureBook = false, workspace, accountId = '', mapping, receipts, offset = 0, source, prepared, schedule, asOf = '', afterWrite;
  let reportPeriods = [], reportPeriodId = '', report = null, reportPolicy = null;
  const canManage = () => sessionHasRole(getSession(), 'management') && hasPermission(getSession(), 'accounting.journal.manage');
  const client = createSourceAccountingClient({ api, session, getSession, signal: controller.signal, onDenied: deny });
  const treasury = createTreasuryClient(api, { getSession, signal: controller.signal, onDenied: deny });
  const live = (generation = epoch) => {
    if (!disposed && scopeKey(getSession()) !== initialScope) deny();
    return !disposed && !signal?.aborted && generation === epoch;
  };
  function dispose() { if (disposed) return; disposed = true; epoch++; controller.abort(); client.dispose(); treasury.dispose(); clear(); book = workspace = mapping = receipts = source = prepared = schedule = report = reportPolicy = null; reportPeriods = []; afterWrite = null; root.innerHTML = ''; signal?.removeEventListener('abort', dispose); if (mounts.get(root) === dispose) mounts.delete(root); }
  function deny() { dispose(); root.innerHTML = '<p role="alert">Accounting access is unavailable. Reopen with current permissions.</p>'; }
  function clear() { removers.forEach((remove) => remove()); removers = []; }
  function listen(selector, event, action) { for (const element of root.querySelectorAll(selector)) { const handler = async (e) => { e.preventDefault(); if (!live() || busy) return; try { await action(element); } catch (error) { if (live()) message(error.message); } }; element.addEventListener(event, handler); removers.push(() => element.removeEventListener(event, handler)); } }
  function message(value) { const node = root.querySelector('[data-source-message]'); if (node) node.textContent = value; }
  function frame(content) { if (!live()) return; clear(); root.innerHTML = `<p data-source-message role="status"></p>${content}`; }
  function lock(value) { busy = value; for (const tag of ['button', 'input', 'select']) for (const node of root.querySelectorAll(tag)) node.disabled = value; }
  function field(form, name) { return String(form.querySelector(`[name="${name}"]`)?.value ?? '').trim(); }
  function evidence(form) { const evidence_reference = field(form, 'evidence_reference'), evidence_digest = field(form, 'evidence_digest').toLowerCase(); check(evidence_reference.length > 0 && evidence_reference.length <= 1000 && DIGEST.test(evidence_digest), 'Supply the retained evidence reference and its 64-character SHA-256 fingerprint.'); return { evidence_reference, evidence_digest }; }
  function account() { return workspace?.accounts.find((row) => row.id === accountId); }
  function receiptScope(receiptId, mappingId = mapping?.id) { return { bookId: book.book_id, accountId, receiptId, mappingId }; }
  function validatePreparation(value, expectedSource = source, requestId = null) {
    const row = value?.preparation; check(row && isId(row.id) && row.book_id === book.book_id && row.treasury_account_id === accountId && row.actor_user_id === getSession()?.user?.id && DIGEST.test(row.confirmation_token) && DIGEST.test(row.source_digest) && (!requestId || row.request_id === requestId));
    const snapshot = receiptSource({ ...row.snapshot, source_digest: row.source_digest }, receiptScope(row.receipt_id, row.mapping_id));
    check(row.event_id === snapshot.event_id);
    check(!expectedSource || (snapshot.receipt_id === expectedSource.receipt_id && snapshot.event_id === expectedSource.event_id && snapshot.mapping_id === expectedSource.mapping_id && snapshot.source_digest === expectedSource.source_digest && snapshot.amount === expectedSource.amount));
    if (value.posting !== null) { const posted = value.posting; check(posted && posted.preparation_id === row.id && posted.book_id === row.book_id && posted.receipt_id === row.receipt_id && posted.treasury_account_id === accountId && posted.event_id === row.event_id && posted.source_digest === row.source_digest && isId(posted.journal_entry_id) && typeof posted.exact_posted === 'boolean' && typeof posted.correction_pending === 'boolean'); }
    return true;
  }
  async function freshBook() { const payload = await client.get('/book'), value = payload?.book; const unconfigured = value?.status === 'unconfigured' && value.book_id === null && value.kind === null && value.entity_label === null; check((mode === 'book' && unconfigured) || (value?.status === 'configured' && isId(value.book_id) && ['owner_operations', 'corporate_legal', 'synthetic'].includes(value.kind) && typeof value.entity_label === 'string'), 'Configure the immutable accounting book before using this workflow.'); if (book?.book_id && book.book_id !== value.book_id) { dispose(); throw Error('Accounting book changed. Reopen this task.'); } book = value; canConfigureBook = payload.can_configure === true; }
  async function load() {
    check(!client.pending(), 'Retry the unchanged pending request before refreshing.'); const generation = ++epoch;
    source = prepared = mapping = receipts = schedule = null; frame('<p>Loading accounting records…</p>'); lock(true);
    try {
      await freshBook(); if (!live(generation)) return;
      if (mode === 'book') renderBook();
      else if (mode === 'reporting') {
        const overview = await client.get(''); if (!live(generation)) return;
        check(Array.isArray(overview.fiscal_periods) && overview.fiscal_periods.every((row) => isId(row.period_id) && typeof row.label === 'string'));
        reportPeriods = overview.fiscal_periods; if (!reportPeriods.some((row) => row.period_id === reportPeriodId)) reportPeriodId = reportPeriods[0]?.period_id || '';
        if (reportPeriodId) await loadReport(generation); else frame('<p>No accounting periods are available.</p>');
      }
      else if (mode === 'receipts') { check(canManage(), 'Receipt accounting requires journal management permission.'); workspace = await treasury.workspace(); if (!live(generation)) return; workspace.accounts = workspace.accounts.filter((row) => row.balance !== null && ['physical_cash', 'gcash', 'bank'].includes(row.kind) && row.active !== false); check(workspace.accounts.every((row) => isId(row.id) && typeof row.alias === 'string')); if (!workspace.accounts.some((row) => row.id === accountId)) accountId = ''; if (accountId) await loadAccount(generation); else renderReceipts(); }
      else { schedule = liabilitySchedule(await client.get('/liabilities' + (asOf ? `?as_of=${asOf}` : '')), book.book_id); if (live(generation)) renderLiabilities(); }
    } catch (error) { if (live(generation)) { frame(`<p role="alert">${h(error.message)}</p>${button('data-load', 'Retry read')}`); listen('[data-load]', 'click', load); } }
    finally { if (live(generation)) lock(false); }
  }
  async function loadAccount(generation = ++epoch) {
    source = prepared = mapping = receipts = null; frame('<p>Loading selected account…</p>'); lock(true);
    try {
      const result = await client.get(`/treasury/accounts/${accountId}/cash-mapping`); if (!live(generation)) return;
      check(result.book_id === book.book_id && result.treasury_account_id === accountId && (result.mapping === null || (isId(result.mapping.id) && result.mapping.book_id === book.book_id && result.mapping.treasury_account_id === accountId && Number.isSafeInteger(result.mapping.version) && result.mapping.version > 0)));
      mapping = result.mapping;
      const page = await treasury.list('receipts', { accountId, limit: 50, offset }); if (!live(generation)) return;
      check(page.items.every((row) => isId(row.id) && row.account_id === accountId && isMoney(row.amount)));
      receipts = page; renderReceipts();
    } catch (error) {
      if (live(generation)) { mapping = receipts = null; renderReceipts(); message(error.message); }
    } finally { if (live(generation)) lock(false); }
  }
  async function send(retry = false, intent = null) {
    const generation = epoch; lock(true);
    try {
      await freshBook(); if (!live(generation)) return;
      const result = retry ? await client.retry() : await client.submit(intent.path, intent.body, intent.validate);
      if (!live(generation)) return; lock(false); await afterWrite(result);
    } catch (error) {
      if (!live(generation)) return; lock(false);
      const rejected = [409, 422].includes(error.status);
      frame(`<p role="alert">${rejected ? 'The reviewed action was rejected. Reload current records before making changes.' : 'The action outcome is uncertain. Retry this unchanged request to recover its result.'}</p><p>${h(error.message)}</p>${client.pending() ? button('data-retry', 'Retry unchanged request') : ''}${rejected ? button('data-reload-rejected', 'Reload and review current records') : ''}`);
      listen('[data-retry]', 'click', () => send(true)); listen('[data-reload-rejected]', 'click', () => { client.reset(); return load(); });
    }
  }
  function review(title, details, consequence, intent, complete) {
    check(canManage() && !client.pending(), 'Current journal management permission is required.'); afterWrite = complete;
    frame(`<article class="notice-card"><h4 tabindex="-1" data-review-title>${h(title)}</h4>${facts(details)}<p>${h(consequence)}</p>${button('data-confirm', `Confirm: ${title}`)} ${button('data-cancel', 'Cancel')}</article>`);
    root.querySelector('[data-review-title]')?.focus(); listen('[data-confirm]', 'click', () => send(false, intent)); listen('[data-cancel]', 'click', () => mode === 'book' ? renderBook() : mode === 'reporting' ? renderReport() : mode === 'receipts' ? renderReceipts() : renderLiabilities());
  }
  async function loadReport(generation = ++epoch) {
    report = reportPolicy = null; frame('<p>Loading reporting evidence for this period…</p>'); lock(true);
    try {
      const policyResult = await client.get(`/statements/reporting-policy?period_id=${reportPeriodId}`); if (!live(generation)) return;
      check(policyResult.policy === null || (isId(policyResult.policy?.id) && policyResult.policy.book_id === book.book_id && policyResult.policy.fiscal_period_id === reportPeriodId && Number.isSafeInteger(policyResult.policy.version) && policyResult.policy.version > 0));
      const payload = await client.get(`/statements?period_id=${reportPeriodId}`); if (!live(generation)) return;
      check(payload.statements?.period?.period_id === reportPeriodId); report = validateReportingSupplement(payload.statements.reporting_supplement); reportPolicy = policyResult.policy;
      check((report.cash_flows.policy?.id ?? null) === (reportPolicy?.id ?? null)); renderReport();
    } catch (error) { if (live(generation)) { report = reportPolicy = null; frame(`<p role="alert">${h(error.message)}</p>${button('data-report-retry', 'Retry reporting read')}`); listen('[data-report-retry]', 'click', () => loadReport()); } }
    finally { if (live(generation)) lock(false); }
  }
  function renderReport() {
    if (!report) return;
    frame(`${select('report_period', 'Accounting period', reportPeriods.map((row) => [row.period_id, row.label]), reportPeriodId)}${canManage() ? button('data-report-policy', reportPolicy ? 'Review a new reporting policy version' : 'Define reporting basis and cash accounts') : ''}<h4>Posted cash lines</h4>${report.cash_flows.cash_lines.map((row, index) => `<article class="sub-card"><strong>${h(row.entry_number)} · ${h(row.account_code)}</strong><p>${h(formatMoney(row.amount))} · ${row.classification_version ? `Classification version ${row.classification_version}` : 'Classification required'}</p>${row.is_opening_adjustment === true ? '<p>Opening balance adjustment — separate from cash flow classification.</p>' : canManage() && reportPolicy?.cash_definition_valid === true && report.cash_flows.status !== 'cash_definition_changed' ? button(`data-report-classify="${index}"`, 'Review cash flow classification') : ''}</article>`).join('')}${reportingSupplementMarkup(report)}`);
    listen('[name="report_period"]', 'change', (node) => { check(reportPeriods.some((row) => row.period_id === node.value)); reportPeriodId = node.value; return loadReport(); });
    listen('[data-report-policy]', 'click', () => { const draft = { framework_label: reportPolicy?.framework_label || '', evidence_reference: reportPolicy?.evidence_reference || '', evidence_digest: reportPolicy?.evidence_digest || '' }; for (const code of ['1010', '1020', '1030']) draft[`cash_${code}`] = reportPolicy?.cash_account_codes?.includes(code) ? 'yes' : 'no'; (reportPolicy?.notes || [{}]).forEach((note, index) => { for (const key of ['title', 'text', 'evidence_reference', 'evidence_digest']) draft[`note_${index}_${key}`] = note[key] || ''; }); renderPolicyEditor(draft, reportPolicy?.notes?.length || 1); });
    listen('[data-report-classify]', 'click', (node) => { const row = report.cash_flows.cash_lines[Number(node.getAttribute('data-report-classify'))]; const allocations = row.allocations?.length ? row.allocations : [{ category: '', amount: row.amount }], draft = {}; allocations.forEach((item, index) => { draft[`allocation_${index}_category`] = item.category; draft[`allocation_${index}_amount`] = item.amount; }); renderClassificationEditor(row, draft, allocations.length); });
  }
  function capture(form) { return Object.fromEntries([...form.querySelectorAll('[name]')].map((control) => [control.getAttribute('name'), control.value])); }
  function restore(draft) { for (const control of root.querySelectorAll('[name]')) if (draft[control.getAttribute('name')] !== undefined) control.value = draft[control.getAttribute('name')]; }
  function renderPolicyEditor(draft, count) {
    frame(`<h4>Retain reporting basis and notes</h4><p>Choose the actual cash definition and framework for this period. Retained notes do not certify statutory compliance.</p><form data-report-policy-form>${input('framework_label', 'Reporting framework or basis')}${['1010', '1020', '1030'].map((code) => select(`cash_${code}`, `Include ${code} in cash`, [['yes', 'Include'], ['no', 'Exclude']])).join('')}${evidenceFields()}${Array.from({ length: count }, (_, index) => `<fieldset><legend>Note ${index + 1}</legend>${input(`note_${index}_title`, 'Note title')}<label>Note text<textarea name="note_${index}_text" maxlength="20000" required></textarea></label>${input(`note_${index}_evidence_reference`, 'Note evidence reference')}${input(`note_${index}_evidence_digest`, 'Note evidence fingerprint (SHA-256)')}</fieldset>`).join('')}${count < 50 ? button('data-add-note', 'Add note') : ''}${count > 1 ? button('data-remove-note', 'Remove last note') : ''}<button type="submit" class="button button-primary">Review reporting policy</button></form>${button('data-report-back', 'Cancel')}`); restore(draft);
    listen('[data-add-note]', 'click', () => renderPolicyEditor(capture(root.querySelector('[data-report-policy-form]')), count + 1)); listen('[data-remove-note]', 'click', () => renderPolicyEditor(capture(root.querySelector('[data-report-policy-form]')), count - 1)); listen('[data-report-back]', 'click', renderReport);
    listen('[data-report-policy-form]', 'submit', (form) => {
      const values = capture(form), notes = Array.from({ length: count }, (_, index) => Object.fromEntries(['title', 'text', 'evidence_reference', 'evidence_digest'].map((key) => [key, (values[`note_${index}_${key}`] || '').trim()])));
      check(notes.every((note) => note.title.length > 0 && note.title.length <= 200 && note.text.length > 0 && note.text.length <= 20000 && note.evidence_reference.length > 0 && note.evidence_reference.length <= 1000 && DIGEST.test(note.evidence_digest)), 'Complete every retained note and its evidence.');
      const body = { request_id: crypto.randomUUID(), book_id: book.book_id, period_id: reportPeriodId, expected_version: reportPolicy?.version || 0, cash_account_codes: ['1010', '1020', '1030'].filter((code) => values[`cash_${code}`] === 'yes'), framework_label: field(form, 'framework_label'), notes, ...evidence(form), reviewed: true };
      check(body.cash_account_codes.length && body.framework_label.length > 0 && body.framework_label.length <= 200, 'Choose at least one cash account and enter the actual reporting framework or basis.');
      review('Retain reporting policy', [['Period', reportPeriods.find((row) => row.period_id === reportPeriodId).label], ['Reporting basis', body.framework_label], ['Cash accounts', body.cash_account_codes.join(', ')], ['Evidence reference', body.evidence_reference], ['Evidence fingerprint', body.evidence_digest], ...notes.flatMap((note) => [[note.title, note.text], ['Note evidence reference', note.evidence_reference], ['Note evidence fingerprint', note.evidence_digest]])], 'Retains a new policy version and the reviewed notes. Existing cash lines require classifications for this policy. No journal or cash movement is created.', { path: '/statements/reporting-policy', body, validate: (result) => isId(result?.policy_id) }, () => loadReport());
    });
  }
  function renderClassificationEditor(row, draft, count) {
    check(row.source_type !== 'opening_balance' && row.is_opening_adjustment === false && reportPolicy?.cash_definition_valid === true && report.cash_flows.status !== 'cash_definition_changed');
    frame(`<h4>Classify posted cash movement</h4>${facts([['Journal', row.entry_number], ['Account', row.account_code], ['Signed cash amount', formatMoney(row.amount)]])}<p>Use signed exact amounts. Splits must equal this cash line. Internal transfers must offset within one journal or match both protected cash legs of one owned transfer in this period. Fees remain separate.</p><form data-report-classification-form>${Array.from({ length: count }, (_, index) => `<fieldset><legend>Allocation ${index + 1}</legend>${select(`allocation_${index}_category`, 'Cash flow category', cashCategories.map((category) => [category, category === 'internal' ? 'Internal transfer' : category[0].toUpperCase() + category.slice(1)]))}${input(`allocation_${index}_amount`, 'Signed amount (two decimal places)')}</fieldset>`).join('')}${evidenceFields()}${count < 20 ? button('data-add-allocation', 'Add allocation') : ''}${count > 1 ? button('data-remove-allocation', 'Remove last allocation') : ''}<button type="submit" class="button button-primary">Review cash flow classification</button></form>${button('data-report-back', 'Cancel')}`); restore(draft);
    listen('[data-add-allocation]', 'click', () => renderClassificationEditor(row, capture(root.querySelector('[data-report-classification-form]')), count + 1)); listen('[data-remove-allocation]', 'click', () => renderClassificationEditor(row, capture(root.querySelector('[data-report-classification-form]')), count - 1)); listen('[data-report-back]', 'click', renderReport);
    listen('[data-report-classification-form]', 'submit', (form) => {
      const allocations = cashAllocations(Array.from({ length: count }, (_, index) => ({ category: field(form, `allocation_${index}_category`), amount: field(form, `allocation_${index}_amount`) })), row.amount);
      const body = { request_id: crypto.randomUUID(), book_id: book.book_id, policy_id: reportPolicy.id, journal_line_id: row.journal_line_id, expected_version: row.classification_version, expected_amount: row.amount, allocations, ...evidence(form), reviewed: true };
      review('Retain cash flow classification', [['Journal', row.entry_number], ['Cash account', row.account_code], ['Signed cash amount', formatMoney(row.amount)], ...allocations.map((item) => [item.category === 'internal' ? 'Internal transfer' : item.category, formatMoney(item.amount)]), ['Evidence reference', body.evidence_reference], ['Evidence fingerprint', body.evidence_digest]], 'Retains classification evidence for this exact posted cash line. It does not post or move cash. Unmatched internal transfers remain incomplete.', { path: '/statements/cash-flow-classifications', body, validate: (result) => isId(result?.classification_id) }, () => loadReport());
    });
  }
  function renderBook() {
    if (book.status === 'configured') { frame(`<h4>Immutable accounting book</h4>${facts([['Entity name', book.entity_label], ['Book kind', book.kind === 'owner_operations' ? 'Owner operations' : book.kind === 'corporate_legal' ? 'Corporate legal' : 'Synthetic'], ['Book reference', book.book_id], ['Evidence reference', book.evidence_reference]])}<p>This identity is permanent. Keep owner and corporate accounting in separate books.</p>`); return; }
    frame(`<p>Start your first accounting book by identifying whose transactions it will record. You do not need an old ledger. Choose the actual entity for this ledger; a separate legal entity needs its own book.</p><p>Setup records the identity only. Review any existing cash, loans and obligations from their evidence before entering opening amounts. If no opening balances are needed, begin with actual transactions. Do not invent a balance or assume zero because there are no old books.</p>${canManage() && canConfigureBook ? `<form data-book-form>${select('kind', 'Book kind', [['owner_operations', 'Owner operations'], ['corporate_legal', 'Corporate legal']])}${input('entity_label', 'Exact entity name')}${evidenceFields()}<button type="submit" class="button button-primary">Review permanent book identity</button></form>` : '<p>Current journal management permission is required to configure the book.</p>'}`);
    listen('[data-book-form]', 'submit', (form) => {
      const body = { kind: field(form, 'kind'), entity_label: field(form, 'entity_label'), ...evidence(form), confirm: true };
      check(['owner_operations', 'corporate_legal'].includes(body.kind) && body.entity_label.length > 0 && body.entity_label.length <= 200, 'Choose owner operations or corporate legal and enter the exact entity name.');
      review('Set permanent book identity', [['Entity name', body.entity_label], ['Book kind', body.kind === 'owner_operations' ? 'Owner operations' : 'Corporate legal'], ['Evidence reference', body.evidence_reference], ['Evidence fingerprint', body.evidence_digest]], 'This permanently binds this ledger to the named entity and book kind. It cannot be changed. Keep owner and corporate records in separate books.', { path: '/book', body, validate: (result) => result?.book?.status === 'configured' && isId(result.book.book_id) && ['kind', 'entity_label', 'evidence_reference', 'evidence_digest'].every((key) => result.book[key] === body[key]) }, (result) => { book = result.book; renderBook(); });
    });
  }
  function receiptFacts(value) { return [['Receipt', value.receipt.reference || value.receipt_id], ['Posting date', value.posting_date], ['Verified amount', formatMoney(value.amount)], ['Debit', `${value.mapping.cash_snapshot.code} · ${value.mapping.cash_snapshot.name}`], ['Credit', '2200 · Unapplied Borrower Funds'], ['Recipient evidence fingerprint', value.evidence.sha256]]; }
  function renderReceipts() {
    if (accountId && !receipts) {
      frame(`<p>Selected account records are unavailable.</p>${button('data-retry-account', 'Retry account read')}${button('data-change-account', 'Choose another account')}`);
      listen('[data-retry-account]', 'click', () => loadAccount());
      listen('[data-change-account]', 'click', () => { accountId = ''; offset = 0; epoch++; source = prepared = mapping = receipts = null; renderReceipts(); });
      return;
    }
    frame(`<p>Recognize verified borrower cash as cash received and unapplied borrower funds. Loan payments, interest and fees remain separate.</p>${select('wallet', 'Treasury account', workspace.accounts.map((row) => [row.id, row.alias]), accountId)}${accountId ? `<h4>Cash account mapping</h4><p>${mapping ? `${h(mapping.cash_snapshot.code)} · ${h(mapping.cash_snapshot.name)} · Version ${mapping.version}` : 'No cash account mapping is configured.'}</p>${hasPermission(getSession(), 'treasury.account.manage') ? `<details><summary>${mapping ? 'Review a new mapping version' : 'Configure cash account mapping'}</summary><form data-mapping-form>${facts([['Treasury account', account().alias], ['Cash account', account().kind === 'physical_cash' ? '1010 · Cash - Office' : '1030 · Cash - Bank / GCash']])}${evidenceFields()}<button type="submit" class="button button-primary">Review cash account mapping</button></form></details>` : ''}<h4>Verified receipts</h4><p>Showing ${receipts?.items.length ? offset + 1 : 0}–${offset + (receipts?.items.length ?? 0)} of ${receipts?.total_count ?? 0} receipts.</p>${(receipts?.items || []).map((row, index) => `<article class="sub-card"><strong>${h(row.reference || row.id)}</strong><p>${h(formatMoney(row.amount))} · ${h(row.effective_at || '')}</p>${mapping ? button(`data-review-receipt="${index}"`, 'Review receipt accounting') : '<p>Configure this account mapping before reviewing receipt accounting.</p>'}</article>`).join('')}${offset > 0 ? button('data-previous', 'Previous receipts') : ''}${receipts?.has_more ? button('data-next', 'Next receipts') : ''}<details><summary>Open a saved receipt preparation</summary><form data-preparation-form>${input('preparation_id', 'Saved preparation reference')}<button type="submit" class="button button-outline">Open preparation</button></form></details>` : '<p>Choose an authorized private Treasury account.</p>'}`);
    listen('[name="wallet"]', 'change', async (node) => { accountId = node.value; offset = 0; epoch++; source = prepared = mapping = receipts = null; if (!accountId) renderReceipts(); else { check(workspace.accounts.some((row) => row.id === accountId)); await loadAccount(epoch); } });
    listen('[data-previous]', 'click', () => { offset -= 50; return loadAccount(); }); listen('[data-next]', 'click', () => { offset += 50; return loadAccount(); });
    listen('[data-mapping-form]', 'submit', (form) => {
      const body = { cash_code: account().kind === 'physical_cash' ? '1010' : '1030', expected_version: mapping?.version ?? 0, request_id: crypto.randomUUID(), ...evidence(form), confirm: true };
      review('Save cash account mapping', [['Treasury account', account().alias], ['Cash account', body.cash_code], ['Evidence reference', body.evidence_reference], ['Evidence fingerprint', body.evidence_digest]], 'Retains a new mapping version for this accounting book. This does not post money.', { path: `/treasury/accounts/${accountId}/cash-mapping`, body, validate: (value) => isId(value?.mapping?.id) && value.mapping.request_id === body.request_id && value.mapping.book_id === book.book_id && value.mapping.treasury_account_id === accountId && value.mapping.version === body.expected_version + 1 && value.mapping.cash_snapshot?.code === body.cash_code && value.mapping.evidence_reference === body.evidence_reference && value.mapping.evidence_digest === body.evidence_digest }, () => loadAccount());
    });
    listen('[data-review-receipt]', 'click', async (node) => {
      const receipt = receipts.items[Number(node.getAttribute('data-review-receipt'))], generation = ++epoch; source = prepared = null; lock(true);
      try { const value = await client.get(`/treasury/receipts/${receipt.id}/review?mapping_id=${mapping.id}`); if (!live(generation)) return; source = receiptSource(value, receiptScope(receipt.id)); const body = { mapping_id: mapping.id, source_digest: source.source_digest, request_id: crypto.randomUUID() }; review('Prepare receipt accounting', receiptFacts(source), 'Saves this reviewed receipt for separate posting confirmation. Preparation does not post a journal.', { path: `/treasury/receipts/${receipt.id}/prepare`, body, validate: (result) => validatePreparation(result, source, body.request_id) }, (result) => { prepared = result; renderPreparation(); }); }
      finally { if (live(generation)) lock(false); }
    });
    listen('[data-preparation-form]', 'submit', async (form) => { const preparationId = field(form, 'preparation_id'); check(isId(preparationId), 'Enter a valid saved preparation reference.'); const generation = ++epoch; source = prepared = null; lock(true); try { const result = await client.get(`/treasury/receipt-preparations/${preparationId}`); if (!live(generation)) return; validatePreparation(result, null); check(result.preparation.id === preparationId); prepared = result; renderPreparation(); } finally { if (live(generation)) lock(false); } });
  }
  function renderPreparation() {
    const row = prepared.preparation, snapshot = { ...row.snapshot, source_digest: row.source_digest }, posting = prepared.posting;
    frame(`<h4>${posting?.exact_posted ? 'Receipt cash recognized' : 'Receipt prepared for review'}</h4>${facts([['Preparation reference', row.id], ...receiptFacts(snapshot)])}${posting ? `<p>${posting.exact_posted ? 'The exact receipt cash journal is posted.' : 'Posting evidence needs investigation.'} ${posting.correction_pending ? 'A later correction needs separate accounting review.' : ''}</p>${facts([['Journal reference', posting.journal_entry_id]])}` : button('data-post-receipt', 'Review receipt posting')}${button('data-receipt-back', 'Back to receipts')}`);
    listen('[data-receipt-back]', 'click', renderReceipts);
    listen('[data-post-receipt]', 'click', () => review('Post receipt cash journal', receiptFacts(snapshot), 'Posts the verified cash received and the matching unapplied borrower liability. It does not apply a loan payment or recognize interest.', { path: `/treasury/receipt-preparations/${row.id}/post`, body: { source_digest: row.source_digest, confirmation_token: row.confirmation_token, confirm: true }, validate: (result) => validatePreparation(result, snapshot) && result.preparation.id === row.id && result.posting?.exact_posted === true && result.journal_entry_id === result.posting.journal_entry_id }, (result) => { prepared = result; renderPreparation(); }));
  }
  function renderLiabilities() {
    frame(`<p>This schedule links evidence to posted liability lines. It does not create cash or journal entries. Unpaid obligations can remain valid. Treasury, Collector and tax have separate schedules.</p><form data-as-of>${input('as_of', 'As of date', 'date')}<button type="submit" class="button button-outline">Load date</button></form><p>As of ${h(schedule.as_of)} · ${schedule.registered_controls_reconciled ? 'Registered liability controls reconciled' : 'Liability reconciliation needs review'}. This does not certify complete accounting readiness.</p><h4>Control reconciliation</h4>${schedule.reconciliation.map((row) => `<article class="sub-card"><strong>${h(row.account_code)} · ${h(kinds[row.account_code][1])}</strong>${facts([['Posted ledger', formatMoney(row.ledger_balance)], ['Liability schedule', formatMoney(row.schedule_balance)], ['Difference', formatMoney(row.difference)], ['Unregistered posted lines', row.unregistered_line_count]])}</article>`).join('')}<h4>Obligations</h4>${schedule.obligations.map((row) => `<article class="sub-card"><strong>${h(row.counterparty)} · ${h(kinds[row.account_code][1])}</strong>${facts([['Outstanding', formatMoney(row.outstanding_amount)], ['Due date', row.due_date], ['Evidence reference', row.evidence_reference]])}<details><summary>Recorded movements</summary>${schedule.movements.filter((movement) => movement.obligation_id === row.obligation_id).map((movement) => `<p>${h(movement.posting_date)} · ${h(movement.kind)} · ${h(formatMoney(movement.signed_amount))} · ${h(movement.claim_id)}</p>`).join('')}</details></article>`).join('') || '<p>No obligations registered as of this date.</p>'}<h4>Unregistered posted liability lines</h4>${schedule.unregistered_lines.map((row, index) => `<article class="sub-card"><strong>${h(row.entry_number || row.journal_entry_id)} · ${h(row.account_code)}</strong><p>${h(row.posting_date)} · Debit ${h(formatMoney(row.debit))} · Credit ${h(formatMoney(row.credit))}</p>${canManage() && ['manual', 'opening_balance'].includes(row.source_type) && row.credit !== '0.00' && row.debit === '0.00' ? button(`data-register-line="${index}"`, 'Register obligation') : ''}${canManage() && ((row.source_type === 'manual' && row.debit !== '0.00' && row.credit === '0.00') || row.source_type === 'reversal') ? button(`data-movement-line="${index}"`, row.source_type === 'reversal' ? 'Record linked correction' : 'Record settlement') : ''}</article>`).join('') || '<p>No unregistered posted lines as of this date.</p>'}`);
    root.querySelector('[name="as_of"]').value = schedule.as_of;
    listen('[data-as-of]', 'submit', (form) => { asOf = field(form, 'as_of'); check(isDate(asOf), 'Choose a valid date.'); return load(); });
    listen('[data-register-line]', 'click', (node) => liabilityForm(schedule.unregistered_lines[Number(node.getAttribute('data-register-line'))], true));
    listen('[data-movement-line]', 'click', (node) => liabilityForm(schedule.unregistered_lines[Number(node.getAttribute('data-movement-line'))], false));
  }
  function liabilityForm(line, registration) {
    const reversal = line.source_type === 'reversal', obligations = schedule.obligations.filter((row) => row.account_code === line.account_code), claims = schedule.movements.filter((claim) => obligations.some((row) => row.obligation_id === claim.obligation_id) && !schedule.movements.some((row) => row.reverses_claim_id === claim.claim_id));
    const amount = line.credit !== '0.00' ? line.credit : line.debit;
    frame(`<h4>${registration ? 'Register obligation' : reversal ? 'Record linked correction' : 'Record settlement'}</h4>${facts([['Journal', line.entry_number || line.journal_entry_id], ['Posting date', line.posting_date], ['Account', `${line.account_code} · ${kinds[line.account_code][1]}`], ['Posted amount', formatMoney(amount)]])}<form data-liability-form>${registration ? input('counterparty', 'Counterparty') + input('due_date', 'Contractual due date (optional)', 'date', false) : select('obligation_id', 'Obligation', obligations.map((row) => [row.obligation_id, `${row.counterparty} · ${formatMoney(row.outstanding_amount)}`]))}${reversal ? select('reverses_claim_id', 'Original recorded movement', claims.map((row) => [row.claim_id, `${obligations.find((item) => item.obligation_id === row.obligation_id).counterparty} · ${row.posting_date} · ${row.kind} · ${formatMoney(row.signed_amount)}`])) : ''}${evidenceFields()}<button type="submit" class="button button-primary">Review liability evidence</button></form>${button('data-cancel-form', 'Cancel')}`);
    listen('[data-cancel-form]', 'click', renderLiabilities);
    listen('[data-liability-form]', 'submit', (form) => {
      const body = { request_id: crypto.randomUUID(), expected_book_id: book.book_id, journal_line_id: line.journal_line_id, expected_account_code: line.account_code, expected_amount: amount, expected_posting_date: line.posting_date, expected_source_type: line.source_type, expected_source_reference: line.source_reference, ...evidence(form), reviewed: true };
      let obligation;
      if (registration) { body.kind = kinds[line.account_code][0]; body.counterparty = field(form, 'counterparty'); body.due_date = field(form, 'due_date') || null; check(body.counterparty.length > 0 && body.counterparty.length <= 200 && (body.due_date === null || isDate(body.due_date)), 'Enter the actual counterparty and a valid optional due date.'); }
      else { obligation = obligations.find((row) => row.obligation_id === field(form, 'obligation_id')); check(obligation, 'Choose an existing obligation for this liability account.'); body.kind = reversal ? 'reversal' : 'settlement'; body.reverses_claim_id = reversal ? field(form, 'reverses_claim_id') : null; if (reversal) check(claims.some((row) => row.claim_id === body.reverses_claim_id && row.obligation_id === obligation.obligation_id), 'Choose the exact original movement for this obligation.'); }
      review(registration ? 'Register liability evidence' : reversal ? 'Record liability correction' : 'Record liability settlement', [['Counterparty', body.counterparty || obligation.counterparty], ['Liability account', `${line.account_code} · ${kinds[line.account_code][1]}`], ['Posted amount', formatMoney(amount)], ['Posting date', line.posting_date], ['Due date', body.due_date ?? obligation?.due_date], ['Evidence reference', body.evidence_reference], ['Evidence fingerprint', body.evidence_digest]], 'Links the retained evidence to this exact posted liability line. It does not post a journal or transfer money. The server rechecks the original line and any linked correction.', { path: '/liabilities' + (registration ? '' : `/${obligation.obligation_id}/movements`), body, validate: (value) => isId(registration ? value?.obligation_id : value?.claim_id) }, load);
    });
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true });
  if (!sessionHasRole(session, 'management') || !hasPermission(session, 'accounting.view') || signal?.aborted) { deny(); return dispose; }
  await load(); return dispose;
}

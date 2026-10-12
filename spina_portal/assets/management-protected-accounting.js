import { sessionHasRole } from './roles.js';
import { escapeHtml as h, formatMoney, hasPermission, titleCase } from './ui.js';
import { createTreasuryClient } from './treasury-api.js';
import { createSourceAccountingClient } from './management-source-accounting.js';

const id = (v) => typeof v === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(v);
const digest = (v) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const money = (v) => typeof v === 'string' && /^(0|[1-9]\d{0,15})\.\d{2}$/.test(v);
const signedMoney = (v) => typeof v === 'string' && /^-?(0|[1-9]\d{0,15})\.\d{2}$/.test(v) && v !== '-0.00';
const date = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;
const check = (v, text = 'The retained accounting evidence is incomplete. Reload before continuing.') => { if (!v) throw Error(text); };
const pick = (v, keys) => Object.fromEntries(keys.map((key) => [key, v[key]]));
const facts = (rows) => `<dl>${rows.map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(value ?? 'Unavailable')}</dd>`).join('')}</dl>`;
const button = (key, text) => `<button type="button" class="button button-outline" ${key}>${h(text)}</button>`;
const fields = (name, label) => `<label>${h(label)}<input name="${name}" required maxlength="64" /></label>`;
const choice = (name, label, rows, selected) => `<label>${h(label)}<select name="${name}" required><option value="">Choose…</option>${rows.map(([value, text]) => `<option value="${h(value)}"${value === selected ? ' selected' : ''}>${h(text)}</option>`).join('')}</select></label>`;
const cents = (v) => BigInt(v.replace('.', ''));
const activeMounts = new WeakMap();
const blockerLabels = {
  accounting_book_identity_required: 'Configure the accounting book identity.',
  single_protected_regular_anchor_required: 'One protected Regular loan release boundary is required.',
  protected_regular_anchor_not_exact: 'The protected loan release evidence needs reconciliation.',
  elapsed_eir_boundary_adapter_required: 'Elapsed interest through this cutoff still requires supported accounting proof.',
  source_state_requires_extended_assessment_adapter: 'This loan history requires an additional supported assessment.',
  dated_quantitative_measurement_required: 'An actual quantitative allowance measurement at this cutoff is required.',
  dated_measurement_source_snapshot_mismatch: 'The dated allowance measurement does not match its source evidence.',
  dated_contractual_cashflow_snapshot_mismatch: 'The retained contractual cash flows need reconciliation.',
  dated_forward_evidence_required: 'Forward-looking evidence valid at this cutoff is required.',
  dated_receivable_components_not_reconciled: 'The dated receivable components do not reconcile.',
  dated_allowance_posting_not_reconciled: 'The dated allowance and its posting do not reconcile.',
  unrecognized_loan_control_journal: 'A loan control journal requires separate accounting review.',
};

export function applicationSource(value, { bookId, accountId, applicationId }) {
  check(value?.book_id === bookId && value.treasury_account_id === accountId && value.application_id === applicationId && [value.receipt_id, value.transaction_id, value.event_id, value.loan_id, value.fiscal_period_id].every(id) && date(value.posting_date) && digest(value.source_digest) && money(value.amount) && value.amount !== '0.00');
  const payoff = value.product_model === 'fixed_daily' && value.accounting_policy_version === 'treasury_regular_original_full_payoff_v1';
  const regular = payoff || value.product_model === 'fixed_daily' && ['treasury_regular_original_first_cash_v1', 'treasury_regular_original_chronological_cash_v1', 'treasury_regular_renewal_chronological_cash_v1'].includes(value.accounting_policy_version);
  const seven = value.product_model === 'seven_by_seven' && value.accounting_policy_version === 'treasury_seven_by_seven_application_v1';
  check(regular || seven);
  const principal = regular ? '1100' : '1110', income = regular ? '4000' : '4010';
  check(Array.isArray(value.lines) && value.lines.length >= 2 && value.lines.length <= (payoff ? 6 : 5));
  let balance = 0n, accrued = 0n, earned = 0n, applied = 0n, settlement = 0n;
  const numbers = new Set(), coordinates = new Set();
  for (const line of value.lines) {
    check(Number.isInteger(line.line_number) && line.line_number > 0 && !numbers.has(line.line_number) && ['2200', principal, '1120', income, ...(payoff ? ['4030', '5020'] : [])].includes(line.account_code) && typeof line.account_snapshot?.name === 'string' && money(line.debit) && money(line.credit));
    const debit = cents(line.debit), credit = cents(line.credit), coordinate = `${line.account_code}:${debit > 0n ? 'debit' : 'credit'}`;
    check((debit > 0n) !== (credit > 0n) && !coordinates.has(coordinate));
    check(line.account_code === '1120' || (line.account_code === '2200' ? debit === cents(value.amount) && credit === 0n : line.account_code === '5020' ? credit === 0n : debit === 0n));
    numbers.add(line.line_number); coordinates.add(coordinate); balance += debit - credit;
    if (line.account_code === '1120') { accrued += debit; applied += credit; }
    if (line.account_code === income) earned += credit;
    if (line.account_code === principal) applied += credit;
    if (line.account_code === '4030' || line.account_code === '5020') settlement += credit - debit;
  }
  check(balance === 0n && accrued === earned && applied + settlement === cents(value.amount) && value.lines.filter((line) => line.account_code === '2200').length === 1);
  let reviewed;
  if (payoff) {
    const p = value.payoff;
    check(id(p?.payoff_review_id) && p.payoff_treatment === 'full_contractual_payoff_no_rebate' && typeof p.contract_evidence_reference === 'string' && p.contract_evidence_reference.length >= 3 && typeof p.payoff_review_rationale === 'string' && p.payoff_review_rationale.length >= 20 && money(p.gross_carrying_before) && signedMoney(p.settlement_difference));
    check(applied === cents(p.gross_carrying_before) && settlement === cents(p.settlement_difference) && value.lines.filter((line) => ['4030', '5020'].includes(line.account_code)).length <= 1);
    reviewed = pick(p, ['payoff_review_id', 'payoff_treatment', 'contract_evidence_reference', 'payoff_review_rationale', 'gross_carrying_before', 'settlement_difference']);
  }
  let closedTerm;
  if (value.closed_term !== undefined) { const c = value.closed_term; check(regular && id(c?.closed_term_review_id) && c.closed_term_treatment === 'original_eir_through_maturity_no_extension' && typeof c.closed_term_rationale === 'string' && c.closed_term_rationale.length >= 20); closedTerm = pick(c, ['closed_term_review_id', 'closed_term_treatment', 'closed_term_rationale']); }
  return { ...pick(value, ['book_id', 'treasury_account_id', 'application_id', 'receipt_id', 'transaction_id', 'event_id', 'loan_id', 'fiscal_period_id', 'posting_date', 'source_digest', 'amount', 'product_model', 'accounting_policy_version']), ...(payoff ? { payoff: reviewed } : {}), ...(closedTerm ? { closed_term: closedTerm } : {}), lines: value.lines.map((line) => ({ ...pick(line, ['line_number', 'account_code', 'debit', 'credit']), name: line.account_snapshot.name })) };
}

export function cutoffCandidate(value, { bookId, periodId, loanId }) {
  check(value?.book?.book_id === bookId && value.period_id === periodId && value.loan_id === loanId && typeof value.ready === 'boolean' && typeof value.current_confirmation === 'boolean' && value.comprehensive_source_coverage === false && Array.isArray(value.blockers) && value.blockers.every((v) => typeof v === 'string' && v.length > 0) && [value.preparation_id, value.confirmation_id].every((v) => v === null || id(v)));
  if (!value.ready) check(value.blockers.length > 0 && ['source_digest', 'measurement', 'balances', 'boundary', 'cutoff_date', 'policy_version', 'preparation_id', 'confirmation_id'].every((key) => value[key] === null) && value.current_confirmation === false);
  else {
    check(value.blockers.length === 0 && digest(value.source_digest) && date(value.cutoff_date) && value.policy_version === 'regular_release_day_cutoff_assessment_v1' && id(value.measurement?.id) && value.measurement.date === value.cutoff_date && Number.isInteger(value.measurement.version) && value.measurement.version > 0 && digest(value.measurement.calculation_digest) && money(value.measurement.ecl_amount) && value.boundary?.anchor_date === value.cutoff_date && typeof value.boundary.release_source_key === 'string');
    check(['1100', '1110', '1120', '1190'].every((code) => money(value.balances?.[code])) && (!value.current_confirmation || id(value.confirmation_id)));
  }
  return { ...pick(value, ['period_id', 'loan_id', 'ready', 'blockers', 'source_digest', 'current_confirmation', 'preparation_id', 'confirmation_id', 'cutoff_date', 'policy_version']), measurement: value.ready ? pick(value.measurement, ['id', 'date', 'version', 'calculation_digest', 'ecl_amount']) : null, balances: value.ready ? pick(value.balances, ['1100', '1110', '1120', '1190']) : null, boundary: value.ready ? pick(value.boundary, ['anchor_date', 'release_source_key']) : null };
}

export function payoffCandidate(value, { bookId, accountId, applicationId }) {
  check(value?.ready === true && value.book_id === bookId && value.treasury_account_id === accountId && value.application_id === applicationId && Array.isArray(value.blockers) && value.blockers.length === 0 && digest(value.source_digest) && money(value.amount) && money(value.gross_carrying_before) && signedMoney(value.settlement_difference) && typeof value.contract_evidence_reference === 'string' && value.contract_evidence_reference.length >= 3 && (value.review_id === null || id(value.review_id)));
  check(cents(value.amount) - cents(value.gross_carrying_before) === cents(value.settlement_difference));
  return pick(value, ['ready', 'source_digest', 'book_id', 'treasury_account_id', 'application_id', 'contract_evidence_reference', 'amount', 'gross_carrying_before', 'settlement_difference', 'review_id']);
}

export function closedTermCandidate(value, { bookId, accountId, applicationId }) {
  check(value?.ready === true && value.book_id === bookId && value.treasury_account_id === accountId && value.application_id === applicationId && id(value.loan_id) && date(value.contractual_due_date) && digest(value.source_digest) && Array.isArray(value.blockers) && value.blockers.length === 0 && value.treatment === 'original_eir_through_maturity_no_extension' && typeof value.contract_evidence_reference === 'string' && value.contract_evidence_reference.length >= 3 && (value.review_id === null || id(value.review_id)));
  return pick(value, ['ready', 'source_digest', 'book_id', 'treasury_account_id', 'application_id', 'loan_id', 'contractual_due_date', 'treatment', 'contract_evidence_reference', 'review_id']);
}

export async function mountProtectedAccounting({ root, api, session, getSession = () => session, signal, mode }) {
  activeMounts.get(root)?.();
  const controller = new AbortController(), application = mode === 'applications';
  const sessionScope = () => { const value = getSession(); return JSON.stringify([value?.user, value?.permissions, value?.access_token, value?.device_id]); };
  const initialScope = sessionScope();
  let disposed = false, epoch = 0, busy = false, removers = [], book, wallets = [], periods = [], accountId = '', periodId = '', reference = '', source, prepared, candidate, payoff, closedTerm, reviewIntent;
  const can = (permission) => sessionHasRole(getSession(), 'management') && hasPermission(getSession(), permission);
  const current = (generation = epoch) => {
    if (!disposed && sessionScope() !== initialScope) denied();
    return !disposed && !signal?.aborted && generation === epoch;
  };
  function clearListeners() { removers.forEach((remove) => remove()); removers = []; }
  function dispose() { if (disposed) return; disposed = true; epoch++; controller.abort(); client.dispose(); treasury.dispose(); clearListeners(); source = prepared = candidate = payoff = closedTerm = reviewIntent = book = null; wallets = periods = []; root.innerHTML = ''; signal?.removeEventListener('abort', dispose); }
  function denied() { dispose(); root.innerHTML = '<p role="alert">Accounting access changed. Reopen with current permissions.</p>'; }
  const client = createSourceAccountingClient({ api, session, getSession, signal: controller.signal, onDenied: denied });
  const treasury = createTreasuryClient(api, { getSession, signal: controller.signal, onDenied: denied });
  function frame(markup) { if (!current()) return; clearListeners(); root.innerHTML = `<p data-message role="status"></p><p>Posted ledger only. This review does not certify complete accounting readiness.</p>${markup}`; }
  function message(text) { const node = root.querySelector('[data-message]'); if (node) node.textContent = text; }
  function lock(value) { busy = value; for (const tag of ['button', 'input', 'select', 'textarea']) for (const node of root.querySelectorAll(tag)) node.disabled = value; }
  function listen(selector, event, action) { for (const node of root.querySelectorAll(selector)) { const handler = async (e) => { e.preventDefault(); if (!current() || busy) return; try { await action(node); } catch (error) { if (current()) message(error.message); } }; node.addEventListener(event, handler); removers.push(() => node.removeEventListener(event, handler)); } }
  function field(form, name) { return String(form.querySelector(`[name="${name}"]`)?.value || '').trim(); }
  async function freshBook() { const result = await client.get('/book'), value = result.book; check(value?.status === 'configured' && id(value.book_id) && typeof value.entity_label === 'string', 'Configure the accounting book before reviewing source evidence.'); if (book && book.book_id !== value.book_id) { denied(); throw Error('Accounting book changed.'); } book = value; }
  async function load() {
    const generation = ++epoch; source = prepared = candidate = payoff = closedTerm = reviewIntent = null; frame('<p>Loading authorized accounting sources…</p>'); lock(true);
    try { await freshBook(); if (!current(generation)) return;
      if (application) { check(can('accounting.journal.manage')); const workspace = await treasury.workspace(); if (!current(generation)) return; check(workspace.enabled && workspace.owner_configured); wallets = workspace.accounts.filter((row) => row.balance !== null && row.active !== false && ['physical_cash', 'gcash', 'bank'].includes(row.kind)); check(wallets.every((row) => id(row.id) && typeof row.alias === 'string')); }
      else { const value = await client.get(''); if (!current(generation)) return; check(Array.isArray(value.fiscal_periods) && value.fiscal_periods.every((row) => id(row.period_id) && typeof row.label === 'string')); periods = value.fiscal_periods; }
      render();
    } catch (error) { if (current(generation)) { frame(`<p role="alert">${h(error.message)}</p>${button('data-load', 'Retry read')}`); listen('[data-load]', 'click', load); } }
    finally { if (current(generation)) lock(false); }
  }
  function appFacts(value) { return [['Loan product', value.product_model === 'fixed_daily' ? 'Regular' : '7×7'], ['Accounting basis', value.payoff ? 'Reviewed full contractual payoff' : value.accounting_policy_version === 'treasury_regular_renewal_chronological_cash_v1' ? 'Renewed contract and chronological cash' : value.accounting_policy_version === 'treasury_regular_original_first_cash_v1' ? 'Original contract, first cash payment' : value.product_model === 'fixed_daily' ? 'Original contract and chronological cash' : 'Verified 7×7 contract and effective interest'], ['Application reference', value.application_id], ['Receipt reference', value.receipt_id], ['Loan reference', value.loan_id], ['Posting date', value.posting_date], ['Applied amount', formatMoney(value.amount)], ...(value.closed_term ? [['Closed-term review', value.closed_term.closed_term_review_id], ['Original interest treatment', 'Stops at signed maturity; no extension'], ['Term rationale', value.closed_term.closed_term_rationale]] : []), ...(value.payoff ? [['Payoff review', value.payoff.payoff_review_id], ['Signed contract evidence', value.payoff.contract_evidence_reference], ['Settlement difference', formatMoney(value.payoff.settlement_difference)], ['Treatment rationale', value.payoff.payoff_review_rationale]] : []), ...value.lines.map((line) => [`${line.account_code} · ${line.name}`, `Debit ${formatMoney(line.debit)} · Credit ${formatMoney(line.credit)}`])]; }
  const payoffFacts = (value) => [['Application reference', value.application_id], ['Signed contract evidence', value.contract_evidence_reference], ['Actual contractual payment', formatMoney(value.amount)], ['Carrying amount cleared', formatMoney(value.gross_carrying_before)], ['Settlement gain / loss', formatMoney(value.settlement_difference)]];
  const closedTermFacts = (value) => [['Loan reference', value.loan_id], ['Signed contract evidence', value.contract_evidence_reference], ['Original contractual maturity', value.contractual_due_date], ['Treatment', 'Original EIR through maturity, no extension']];
  function assessmentFacts(value) { return [['Loan reference', value.loan_id], ['Cutoff date', value.cutoff_date], ['Release boundary', value.boundary.anchor_date], ['Dated ECL measurement', value.measurement.date], ['Measured allowance', formatMoney(value.measurement.ecl_amount)], ...Object.entries(value.balances).map(([code, amount]) => [`Posted ${code} balance`, formatMoney(amount)]), ['Source evidence fingerprint', value.source_digest]]; }
  function validatePrep(result, expected, requestId = null, preparationId = null) {
    const row = result?.preparation; check(row && id(row.id) && row.actor_user_id === getSession()?.user?.id && digest(row.confirmation_token) && (!requestId || row.request_id === requestId) && (!preparationId || row.id === preparationId));
    const projected = applicationSource({ ...row.snapshot, source_digest: row.source_digest }, { bookId: book.book_id, accountId, applicationId: row.application_id });
    for (const key of ['book_id', 'application_id', 'transaction_id', 'receipt_id', 'treasury_account_id', 'loan_id']) check(row[key] === projected[key]);
    if (expected) check(JSON.stringify(projected) === JSON.stringify(expected));
    if (result.posting !== null) { const posted = result.posting; check(posted && posted.preparation_id === row.id && id(posted.journal_entry_id) && typeof posted.exact_posted === 'boolean' && typeof posted.correction_pending === 'boolean'); for (const key of ['book_id', 'application_id', 'transaction_id', 'receipt_id', 'treasury_account_id', 'loan_id', 'source_digest']) check(posted[key] === row[key]); }
    return true;
  }
  function showReview(title, details, consequence, intent) {
    check(can(intent.permission) && !client.pending(), 'Current accounting permission is required.'); reviewIntent = intent;
    frame(`<article><h4 tabindex="-1" data-review-title>${h(title)}</h4>${facts(details)}<p>${h(consequence)}</p>${button('data-confirm', `Confirm: ${title}`)}${button('data-cancel', 'Cancel')}</article>`);
    root.querySelector('[data-review-title]')?.focus(); listen('[data-confirm]', 'click', () => send(false)); listen('[data-cancel]', 'click', render);
  }
  async function send(retry) {
    const generation = epoch, held = reviewIntent; check(held && can(held.permission)); lock(true);
    try { await freshBook(); if (!current(generation)) return; const result = retry ? await client.retry() : await client.submit(held.path, held.body, held.validate); if (!current(generation)) return; lock(false); held.complete(result); }
    catch (error) { if (current(generation)) { frame(`<p role="alert">${h(error.message)}</p><p>The result is not confirmed. Retry the unchanged request to recover its result.</p>${button('data-retry', 'Retry unchanged request')}${[409, 422].includes(error.status) ? button('data-reload', 'Reload current evidence') : ''}`); listen('[data-retry]', 'click', () => send(true)); listen('[data-reload]', 'click', () => { client.reset(); return load(); }); } }
    finally { if (current(generation)) lock(false); }
  }
  async function lookup(recover = false, fullPayoff = false, matured = false) {
    const generation = ++epoch; source = prepared = candidate = payoff = closedTerm = reviewIntent = null; render(); lock(true);
    try {
      if (application) { check(wallets.some((row) => row.id === accountId) && id(reference), 'Choose an authorized wallet and an existing application or preparation reference.');
        if (fullPayoff) { const result = await client.get(`/treasury/applications/${reference}/payoff-review`); if (!current(generation)) return; payoff = payoffCandidate(result, { bookId: book.book_id, accountId, applicationId: reference }); render(); return; }
        if (matured) { const result = await client.get(`/treasury/applications/${reference}/closed-term-review`); if (!current(generation)) return; closedTerm = closedTermCandidate(result, { bookId: book.book_id, accountId, applicationId: reference }); render(); return; }
        const result = await client.get(recover ? `/treasury/application-preparations/${reference}` : `/treasury/applications/${reference}/review`); if (!current(generation)) return;
        if (recover) { validatePrep(result); prepared = result; source = applicationSource({ ...result.preparation.snapshot, source_digest: result.preparation.source_digest }, { bookId: book.book_id, accountId, applicationId: result.preparation.application_id }); }
        else source = applicationSource(result, { bookId: book.book_id, accountId, applicationId: reference });
      } else { check(periods.some((row) => row.period_id === periodId) && id(reference), 'Choose an actual period and existing loan reference.'); const result = await client.get(`/period-assessments/${periodId}/loans/${reference}`); if (!current(generation)) return; candidate = cutoffCandidate(result, { bookId: book.book_id, periodId, loanId: reference }); }
      render();
    } catch (error) { if (current(generation)) { render(); message(error.message); } }
    finally { if (current(generation)) lock(false); }
  }
  function render() {
    const closedTermMarkup = closedTerm ? `<article><h4>Closed contractual term</h4>${facts(closedTermFacts(closedTerm))}<p>Review the signed contract and confirm that original interest stops at its maturity. Actual overdue cash then reduces existing carrying balances; any full settlement difference requires the separate payoff review.</p>${closedTerm.review_id ? `<p>Retained review: ${h(closedTerm.review_id)}</p>${button('data-payoff-reviewed', 'Load reviewed application accounting')}` : `<form data-closed-term-review><label>Signed contract evidence reference<input name="contract_reference" required maxlength="1000" /></label><label>Treatment rationale<textarea name="rationale" minlength="20" maxlength="2000" required></textarea></label><label><input name="term_confirm" type="checkbox" required /> I verified original interest ends at contractual maturity with no extension.</label><button type="submit" class="button button-primary">Review closed-term treatment</button></form>`}</article>` : '';
    const detail = application ? source ? `<article>${facts(appFacts(source))}<p>No cash is recognized again. The original receipt remains the cash entry; this applies retained funds using the reviewed principal and interest amounts.</p>${prepared ? `<h4>${prepared.posting?.exact_posted ? 'Application accounting posted' : 'Application prepared for review'}</h4>${facts([['Preparation reference', prepared.preparation.id], ...(prepared.posting ? [['Journal reference', prepared.posting.journal_entry_id]] : [])])}${prepared.posting ? `<p>${prepared.posting.correction_pending ? 'A later source change requires separate correction review.' : 'Retained posting evidence is available.'}</p>` : button('data-post-application', 'Review application posting')}` : button('data-prepare-application', 'Prepare application accounting')}</article>` : '' : candidate ? `<article><h4>${candidate.current_confirmation ? 'Current cutoff proof confirmed' : candidate.ready ? 'Dated cutoff proof available' : 'Cutoff assessment blocked'}</h4><p>This confirms actual dated proof only. Other sources, elapsed interest, tax and liabilities remain independent checks.</p>${candidate.ready ? facts(assessmentFacts(candidate)) : `<ul>${candidate.blockers.map((code) => `<li>${h(blockerLabels[code] || titleCase(code))}</li>`).join('')}</ul><p>No waiver or acknowledgement can replace missing dated proof.</p>`}${candidate.ready && !candidate.current_confirmation ? candidate.preparation_id ? can('accounting.period.close.post') ? button('data-confirm-assessment', 'Review cutoff confirmation') : '<p>Period-close posting permission is required to confirm.</p>' : can('accounting.period.close.prepare') ? '<form data-assessment-prepare><label>Review rationale<textarea name="review_rationale" minlength="20" maxlength="2000" required></textarea></label><button type="submit" class="button button-primary">Review assessment preparation</button></form>' : '<p>Period-close preparation permission is required.</p>' : ''}</article>` : '';
    frame(`<h4>${h(book.entity_label)} · ${book.kind === 'owner_operations' ? 'Owner operations' : book.kind === 'corporate_legal' ? 'Corporate legal' : 'Synthetic'}</h4><p>${application ? 'Review an existing Treasury application. Supported Regular payments and single-loan 7×7 applications require posted receipt cash and exact loan evidence. Review the product and accounting basis below.' : 'Review a loan using actual evidence for the selected cutoff. Only a supported Regular loan release-day boundary with dated allowance proof can proceed.'}</p><form data-source-lookup>${application ? choice('wallet', 'Treasury account', wallets.map((row) => [row.id, row.alias]), accountId) : choice('period_id', 'Accounting period', periods.map((row) => [row.period_id, row.label]), periodId)}${fields(application ? 'application_id' : 'loan_id', application ? 'Existing application reference' : 'Loan reference from the loan register or close review')}<button type="submit" class="button button-primary">Load accounting review</button>${application ? button('data-recover', 'Open saved preparation using this reference') + button('data-load-payoff', 'Review full payoff treatment') + button('data-load-closed-term', 'Review closed contractual term') : ''}</form><section data-evidence>${detail}${payoff ? `<article><h4>Full contractual payoff treatment</h4>${facts(payoffFacts(payoff))}<p>Confirm from the signed contract that this payment settles every installment without a rebate. The accounting review clears the carrying amount and separately reports the settlement difference.</p>${payoff.review_id ? `<p>Retained review: ${h(payoff.review_id)}</p>${button('data-payoff-reviewed', 'Load reviewed application accounting')}` : `<form data-payoff-review><label>Signed contract evidence reference<input name="contract_reference" required maxlength="1000" /></label><label>Treatment rationale<textarea name="rationale" minlength="20" maxlength="2000" required></textarea></label><label><input name="no_rebate" type="checkbox" required /> I verified full contractual payoff without a rebate.</label><button type="submit" class="button button-primary">Review payoff treatment</button></form>`}</article>` : ''}${closedTermMarkup}</section>`);
    root.querySelector(`[name="${application ? 'application_id' : 'loan_id'}"]`).value = reference;
    const readForm = (form) => { accountId = field(form, 'wallet'); periodId = field(form, 'period_id'); reference = field(form, application ? 'application_id' : 'loan_id'); };
    listen('[data-source-lookup]', 'submit', (form) => { readForm(form); return lookup(); }); listen('[data-recover]', 'click', () => { readForm(root.querySelector('[data-source-lookup]')); return lookup(true); });
    for (const event of ['input', 'change']) listen('[data-source-lookup]', event, () => { source = prepared = candidate = payoff = closedTerm = reviewIntent = null; root.querySelector('[data-evidence]').innerHTML = ''; });
    listen('[data-load-payoff]', 'click', () => { readForm(root.querySelector('[data-source-lookup]')); return lookup(false, true); });
    listen('[data-payoff-reviewed]', 'click', () => lookup());
    listen('[data-load-closed-term]', 'click', () => { readForm(root.querySelector('[data-source-lookup]')); return lookup(false, false, true); });
    listen('[data-closed-term-review]', 'submit', (form) => {
      const held = closedTerm, rationale = field(form, 'rationale'), contractReference = field(form, 'contract_reference');
      check(held && !held.review_id && rationale.length >= 20 && rationale.length <= 2000 && contractReference === held.contract_evidence_reference && form.querySelector('[name="term_confirm"]')?.checked, 'Verify the exact signed maturity, no-extension treatment and substantive rationale.');
      showReview('Retain closed contractual term', [...closedTermFacts(held), ['Rationale', rationale]], 'Retains the original term treatment. Review actual cash application accounting separately.', {
        permission: 'accounting.journal.manage', path: `/treasury/applications/${held.application_id}/closed-term-review`,
        body: { source_digest: held.source_digest, request_id: crypto.randomUUID(), treatment: held.treatment, contract_evidence_reference: contractReference, review_rationale: rationale, confirm: true },
        validate: (value) => { const checked = closedTermCandidate(value, { bookId: book.book_id, accountId, applicationId: held.application_id }); check(checked.source_digest === held.source_digest && id(checked.review_id)); return true; },
        complete: (value) => { closedTerm = closedTermCandidate(value, { bookId: book.book_id, accountId, applicationId: held.application_id }); render(); },
      });
    });

    listen('[data-payoff-review]', 'submit', (form) => {
      const held = payoff, rationale = field(form, 'rationale'), contractReference = field(form, 'contract_reference'), requestId = crypto.randomUUID();
      check(held && !held.review_id && rationale.length >= 20 && rationale.length <= 2000 && contractReference === held.contract_evidence_reference && form.querySelector('[name="no_rebate"]')?.checked, 'Verify the exact signed-contract reference, no-rebate treatment and substantive rationale.');
      showReview('Retain full payoff treatment', [...payoffFacts(held), ['Treatment', 'Full contractual payoff without rebate'], ['Rationale', rationale]], 'Retains this treatment evidence. Review and post the resulting application accounting separately.', {
        permission: 'accounting.journal.manage', path: `/treasury/applications/${held.application_id}/payoff-review`,
        body: { source_digest: held.source_digest, request_id: requestId, treatment: 'full_contractual_payoff_no_rebate', contract_evidence_reference: contractReference, review_rationale: rationale, confirm: true },
        validate: (value) => { const checked = payoffCandidate(value, { bookId: book.book_id, accountId, applicationId: held.application_id }); check(checked.source_digest === held.source_digest && id(checked.review_id)); return true; },
        complete: (value) => { payoff = payoffCandidate(value, { bookId: book.book_id, accountId, applicationId: held.application_id }); render(); },
      });
    });
    listen('[data-prepare-application]', 'click', () => { const expected = source, requestId = crypto.randomUUID(); check(expected); showReview('Prepare application accounting', appFacts(expected), 'Retains these exact application and interest coordinates. A separate confirmation is required to post.', { permission: 'accounting.journal.manage', path: `/treasury/applications/${expected.application_id}/prepare`, body: { request_id: requestId, source_digest: expected.source_digest }, validate: (value) => validatePrep(value, expected, requestId), complete: (value) => { prepared = value; render(); } }); });
    listen('[data-post-application]', 'click', () => { const held = prepared, expected = source; check(held && expected && !held.posting); showReview('Post application accounting', appFacts(expected), 'Posts the reviewed consumption of unapplied funds and the protected principal and interest entries. No cash is recognized again.', { permission: 'accounting.journal.manage', path: `/treasury/application-preparations/${held.preparation.id}/post`, body: { source_digest: expected.source_digest, confirmation_token: held.preparation.confirmation_token, confirm: true }, validate: (value) => validatePrep(value, expected, null, held.preparation.id) && value.posting?.exact_posted === true && value.journal_entry_id === value.posting.journal_entry_id, complete: (value) => { prepared = value; render(); } }); });
    listen('[data-assessment-prepare]', 'submit', (form) => { const expected = candidate, rationale = field(form, 'review_rationale'); check(expected?.ready && rationale.length >= 20 && rationale.length <= 2000, 'Explain the actual dated proof reviewed in 20–2000 characters.'); showReview('Prepare dated cutoff assessment', [...assessmentFacts(expected), ['Review rationale', rationale]], 'Retains this actual cutoff proof for a separate confirmation. It creates no journal and does not waive any blocker.', { permission: 'accounting.period.close.prepare', path: `/period-assessments/${periodId}/loans/${expected.loan_id}/prepare`, body: { expected_book_id: book.book_id, source_digest: expected.source_digest, review_rationale: rationale }, validate: (value) => id(value?.preparation_id), complete: (value) => { candidate = { ...expected, preparation_id: value.preparation_id }; render(); } }); });
    listen('[data-confirm-assessment]', 'click', () => { const expected = candidate; check(expected?.ready && id(expected.preparation_id)); showReview('Confirm dated cutoff proof', assessmentFacts(expected), 'Confirms the retained proof after the server rechecks the exact dated evidence. It creates no journal and does not certify complete period readiness.', { permission: 'accounting.period.close.post', path: `/period-assessments/preparations/${expected.preparation_id}/confirm`, body: { expected_book_id: book.book_id, source_digest: expected.source_digest, confirm: true }, validate: (value) => id(value?.confirmation_id), complete: (value) => { candidate = { ...expected, confirmation_id: value.confirmation_id, current_confirmation: true }; render(); } }); });
  }
  activeMounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true });
  if (!can('accounting.view') || signal?.aborted) { denied(); return dispose; }
  await load(); return dispose;
}

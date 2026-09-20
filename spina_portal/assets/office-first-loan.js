import { sessionHasRole } from './roles.js';
import { emptyState, errorCard, escapeHtml as esc, hasPermission, loadingPanel } from './ui.js';

const mounts = new WeakMap();
const BASE = '/api/v1/management/first-loans';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const HASH = /^[0-9a-f]{64}$/;
const MONEY = /^\d+(?:\.\d{1,2})?$/;
const uid = (value) => typeof value === 'string' && UUID.test(value);
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const money = (value) => typeof value === 'string' && MONEY.test(value);
const button = (action, label) => `<button class="button button-outline" type="button" data-action="${action}">${label}</button>`;
const input = (name, label, type = 'text', value = '') => `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" autocomplete="off" /></label>`;

function validLoan(value, review) {
  return object(value) && uid(value.loan_id) && value.client_id === review.client_id && uid(value.packet_id)
    && HASH.test(value.packet_hash) && ['approved_pending_release', 'released', 'cancelled'].includes(value.status)
    && object(value.packet) && value.packet.loan_id === value.loan_id && value.packet.client_id === review.client_id
    && value.packet.packet_id === value.packet_id && value.packet.application?.application_id === review.application_id
    && object(value.packet.terms) && money(value.packet.terms.principal) && money(value.packet.net_cash)
    && object(value.packet.borrower) && typeof value.packet.borrower.full_name === 'string'
    && Array.isArray(value.packet.schedule) && value.packet.schedule.length > 0
    && value.packet.schedule.every((row) => Number.isSafeInteger(row.installment_number) && row.installment_number > 0
      && /^\d{4}-\d{2}-\d{2}$/.test(row.due_date) && ['contractual_amount', 'principal_component', 'interest_component'].every((key) => money(row[key])))
    && (value.authorization === null || (object(value.authorization) && uid(value.authorization.id) && typeof value.authorization.revoked === 'boolean'))
    && (value.document === null || (object(value.document) && uid(value.document.id) && HASH.test(value.document.content_sha256)));
}

export function mountOfficeFirstLoan({ root, api, session, signal }) {
  mounts.get(root)?.();
  root.innerHTML = '';
  let disposed = false;
  let token = {};
  let state = 'editing';
  let review = null;
  let context = null;
  let loan = null;
  let decisions = [];
  let evidence = {};
  let preserveStatus = false;
  let listeners = [];
  let actionListeners = [];
  const urls = [];
  const manager = sessionHasRole(session, 'management') && hasPermission(session, 'lending.first_loan.approve');
  const staff = sessionHasRole(session, 'employee', 'management') && hasPermission(session, 'lending.first_loan.release');
  const canManageCredentials = sessionHasRole(session, 'employee', 'management') && hasPermission(session, 'client.credential.manage');
  let form, intake, reference, clearButton, workspace, status;

  function on(element, event, callback, action = false) {
    element.addEventListener(event, callback);
    (action ? actionListeners : listeners).push(() => element.removeEventListener(event, callback));
  }
  function wipe(element) {
    if (!element) return;
    for (const control of [...element.querySelectorAll('input'), ...element.querySelectorAll('textarea'), ...element.querySelectorAll('select')]) {
      control.value = '';
      if (control.getAttribute('type') === 'checkbox') control.checked = false;
    }
  }
  function clearActions() { for (const remove of actionListeners) remove(); actionListeners = []; }
  function invalidate() {
    token = {};
    state = 'editing'; review = null; context = null; loan = null; evidence = {}; decisions = [];
    clearActions(); wipe(workspace); wipe(status); preserveStatus = false;
    if (workspace) workspace.innerHTML = '';
    if (status) status.innerHTML = '';
    for (const url of urls.splice(0)) URL.revokeObjectURL(url);
  }
  function dispose() {
    if (disposed) return;
    disposed = true; invalidate(); wipe(root);
    for (const remove of listeners) remove(); listeners = [];
    signal?.removeEventListener('abort', dispose);
    if (mounts.get(root) === dispose) { mounts.delete(root); root.innerHTML = ''; }
  }
  function current(request) { return !disposed && request === token; }
  function showError(error, blocked = false) {
    wipe(status); preserveStatus = false;
    status.innerHTML = `<div role="alert">${errorCard(error)}</div>${blocked ? '<p>Reload the authoritative record before trying another action.</p>' : ''}`;
  }
  function denyAccess(error) {
    invalidate();
    intake.value = ''; reference.value = '';
    showError(error);
  }
  function disableActions() {
    for (const control of [...workspace.querySelectorAll('button'), ...workspace.querySelectorAll('input'), ...workspace.querySelectorAll('select'), ...workspace.querySelectorAll('textarea')]) control.disabled = state !== 'editing';
    const reload = workspace.querySelector('[data-action="reload"]');
    if (reload) reload.disabled = state === 'saving';
  }
  function field(name) { return workspace.querySelector(`[name="${name}"]`); }
  function text(name) { return field(name)?.value.trim() || ''; }
  function action(name, callback) { const element = workspace.querySelector(`[data-action="${name}"]`); if (element) on(element, 'click', callback, true); }

  async function refresh(request = token) {
    const result = await api.request(`${BASE}/by-application/${encodeURIComponent(review.application_id)}`, { signal });
    if (!current(request)) return;
    if (!object(result) || !Array.isArray(result.loans) || !result.loans.every((item) => validLoan(item, review))) throw new Error('The first-loan response is invalid or does not match this application.');
    const next = result.loans.find((item) => item.status !== 'cancelled') || result.loans[0] || null;
    if (next?.packet_hash !== loan?.packet_hash) evidence = {};
    else if (next?.authorization?.id !== loan?.authorization?.id) delete evidence.borrower_cash_received;
    if (next?.evidence !== undefined) {
      if (!object(next.evidence) || !Object.entries(next.evidence).every(([purpose, value]) => ['borrower_contract_signed', 'borrower_cash_received'].includes(purpose) && object(value) && /^office-evidence:[0-9a-f-]{36}$/i.test(value.evidence_reference))) throw new Error('The recorded signing evidence response is invalid.');
      evidence = Object.fromEntries(Object.entries(next.evidence).map(([purpose, value]) => [purpose, value.evidence_reference]));
    }
    if (result.decisions !== undefined && (!Array.isArray(result.decisions) || !result.decisions.every((item) => uid(item.id) && uid(item.application_version_id) && ['rejected', 'approval_cancelled'].includes(item.decision) && typeof item.reason === 'string'))) throw new Error('The recorded Management decision response is invalid.');
    decisions = result.decisions || [];
    loan = next; state = 'editing'; render();
  }

  async function open(event) {
    event?.preventDefault();
    if (disposed) return;
    invalidate();
    const request = token;
    const intakeRef = intake.value.trim(); const applicationRef = reference.value.trim();
    if (!intakeRef || !applicationRef) { showError(new Error('Enter both office references.')); return; }
    status.innerHTML = loadingPanel('Loading first-loan records…');
    try {
      const selection = await api.request(`/api/v1/management/onboarding/applicants/by-reference/${encodeURIComponent(intakeRef)}/cif-client`, { signal });
      if (!current(request)) return;
      if (!uid(selection?.client_id) || selection.application_reference?.trim().toLowerCase() !== intakeRef.toLowerCase()) throw new Error('The intake response does not match the selected reference.');
      const saved = await api.request(`/api/v1/management/clients/${selection.client_id}/loan-applications/by-reference/${encodeURIComponent(applicationRef)}/review-summary`, { signal });
      if (!current(request)) return;
      if (!object(saved) || saved.client_id !== selection.client_id || saved.application_reference !== applicationRef || !uid(saved.application_id) || !uid(saved.application_version_id) || !object(saved.information) || !Array.isArray(saved.missing_fields)) throw new Error('The application response is invalid or does not match the selected Client.');
      review = saved;
      const options = await api.request(`${BASE}/context`, { signal });
      if (!current(request)) return;
      if (!object(options) || !Array.isArray(options.products) || !Array.isArray(options.templates)
        || !options.products.every((p) => uid(p.id) && typeof p.name === 'string' && ['fixed_daily', 'fixed_total', 'seven_by_seven'].includes(p.calculation_mode) && money(p.daily_interest_per_1000))
        || !options.templates.every((t) => typeof t.version === 'string' && HASH.test(t.content_sha256) && typeof t.approved_for_execution === 'boolean')) throw new Error('Approved product and template configuration is unavailable.');
      context = options;
      await refresh(request);
      if (current(request)) status.innerHTML = '';
    } catch (error) { if (current(request)) { if ([401, 403].includes(error?.status)) { denyAccess(error); return; } wipe(workspace); workspace.innerHTML = ''; showError(error); } }
  }

  async function mutate(path, buildBody, validate = object, after) {
    if (disposed || state !== 'editing') return;
    const request = token;
    state = 'saving'; disableActions(); wipe(status); preserveStatus = false; status.innerHTML = loadingPanel('Recording the office action…');
    try {
      const body = typeof buildBody === 'function' ? await buildBody() : buildBody;
      if (!current(request)) return;
      const result = await api.request(path, { method: 'POST', body, signal, financial: true });
      if (!current(request)) return;
      if (!validate(result)) throw new Error('The result could not be verified.');
      if (after) await after(result, request); else await refresh(request);
      if (current(request)) { state = 'editing'; disableActions(); if (!preserveStatus) status.innerHTML = ''; }
    } catch (error) {
      if (!current(request)) return;
      if ([401, 403].includes(error?.status)) { denyAccess(error); return; }
      state = [400, 422].includes(error?.status) || error?.beforeWrite ? 'editing' : 'blocked';
      disableActions(); showError(error, state === 'blocked');
    }
  }

  function approvalMarkup() {
    return `<form data-approval class="entry-form"><h4>Management exact-term approval</h4>
      <p>Confirm the product, pricing review, exact schedule and authorized deductions. Approval leaves the loan pending office release.</p>
      <label>Approved product<select name="product"><option value="">Choose product</option>${context.products.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select></label>
      ${input('principal', 'Approved principal (PHP)', 'text', review.information.request?.requested_amount || '')}
      ${input('interestRate', 'Regular: approved total-contract interest rate (%)')}${input('interest', 'Regular: exact total contractual interest (PHP)')}
      ${input('installment', 'Agreed payment amount (PHP)')}
      <label>Payment frequency<select name="frequency">${['daily', 'weekly', 'semi_monthly', 'monthly', 'balloon', 'custom'].map((value) => `<option value="${value}">${value.replace('_', ' ')}</option>`).join('')}</select></label>
      ${input('count', 'Regular: number of installments', 'number')}${input('basisDate', 'Approved office release-date basis', 'date', context.server_business_date || '')}
      ${input('firstDate', 'First contractual payment date', 'date', review.information.request?.preferred_first_payment_date || '')}
      ${input('semiDays', 'Semi-monthly payment days (for example 15,30)', 'text', '15,30')}
      <label>Custom dates and amounts, one per line: date | amount<textarea name="customRows"></textarea></label>
      <label>Authorized upfront deductions, one per line: code | amount | authority reference<textarea name="deductions"></textarea></label>
      ${input('pricingReference', 'Approved pricing review reference')}${input('accountEmail', 'Selected Client account email', 'email')}
      <label>Controlled contractual template<select name="template"><option value="">Choose template</option>${context.templates.map((t) => `<option value="${esc(t.version)}">${esc(t.version)}${t.approved_for_execution ? '' : ' — execution approval pending'}</option>`).join('')}</select></label>
      <p>7x7 uses the catalog daily-interest basis and authoritative generated maturity. Its exact compliance review remains required before signing.</p>
      <button class="button button-primary" type="submit">Approve exact terms</button></form>
      <form data-reject class="entry-form">${input('decisionReason', 'Management rejection reason')}<button class="button button-outline" type="submit">Reject application</button></form>`;
  }

  function termsBody() {
    const product = context.products.find((item) => item.id === text('product'));
    if (!product) throw Object.assign(new Error('Choose the approved product.'), { beforeWrite: true });
    const seven = product.calculation_mode === 'seven_by_seven';
    const lines = (name) => text(name).split('\n').filter((line) => line.trim()).map((line) => line.split('|').map((part) => part.trim()));
    const deductions = lines('deductions').map((row) => { if (row.length !== 3) throw Object.assign(new Error('Each deduction needs code, exact amount and authority reference.'), { beforeWrite: true }); return { code: row[0], amount: row[1], authority_reference: row[2] }; });
    const custom = lines('customRows').map((row) => { if (row.length !== 2) throw Object.assign(new Error('Each custom installment needs a date and exact amount.'), { beforeWrite: true }); return { due_date: row[0], amount: row[1] }; });
    return { request_id: crypto.randomUUID(), application_version_id: review.application_version_id, template_version: text('template'), terms: {
      loan_type_id: product.id, product_code: seven ? 'seven_by_seven' : 'regular', principal: text('principal'),
      contractual_interest: seven ? null : text('interest'), interest_rate_percent: seven ? null : text('interestRate'),
      daily_interest_per_1000: seven ? product.daily_interest_per_1000 : null, payment_frequency: text('frequency'),
      schedule_basis_date: text('basisDate'), first_due_date: text('firstDate'), installment_amount: text('installment'),
      installment_count: seven || !text('count') ? null : Number(text('count')), semi_monthly_days: text('semiDays').split(',').map(Number),
      custom_installments: custom, deductions, pricing_review_reference: text('pricingReference'), account_email: text('accountEmail'),
    } };
  }

  function loanMarkup() {
    const packet = loan.packet;
    return `<h4>${esc(loan.loan_number)} — ${esc(loan.status.replaceAll('_', ' '))}</h4>
      <p>${esc(packet.borrower.full_name)} · ${esc(packet.product_name || '')}</p>
      <div class="detail-grid"><div>Approved principal: PHP ${esc(packet.terms.principal)}</div><div>Authorized cash: PHP ${esc(packet.net_cash)}</div><div>Release-date basis: ${esc(packet.terms.schedule_basis_date)}</div><div>First contractual payment: ${esc(packet.schedule[0].due_date)}</div></div>
      <details><summary>Complete locked payment schedule (${packet.schedule.length} installments)</summary><div class="table-wrap"><table><thead><tr><th>No.</th><th>Date</th><th>Payment</th><th>Principal</th><th>Interest</th></tr></thead><tbody>${packet.schedule.map((r) => `<tr><td>${r.installment_number}</td><td>${esc(r.due_date)}</td><td>PHP ${esc(r.contractual_amount)}</td><td>PHP ${esc(r.principal_component)}</td><td>PHP ${esc(r.interest_component)}</td></tr>`).join('')}</tbody></table></div></details>
      <p>${loan.document ? 'Approved loan documents are ready to download.' : 'The exact populated PDF packet must be generated before signing or release.'}</p>
      ${manager && loan.status === 'approved_pending_release' && packet.terms.product_code === 'seven_by_seven' ? complianceMarkup() : ''}
      <div class="action-row">${manager && loan.status === 'approved_pending_release' && !loan.document ? button('documents', 'Generate locked PDF packet') : ''}${loan.document ? button('download', 'Download locked PDF packet') : ''}</div>
      ${loan.status === 'approved_pending_release' ? `${manager ? `<div class="action-row">${loan.document ? button('authorize', 'Authorize exact office release') : ''}</div>${input('revokeReason', 'Reason to revoke authorization or cancel approval')}<div class="action-row">${loan.authorization && !loan.authorization.revoked ? button('revoke', 'Revoke release authorization') : ''}${button('cancel', 'Cancel unreleased approval')}</div>` : ''}
      <p>Management release authorization: ${loan.authorization ? (loan.authorization.revoked ? 'Revoked' : 'Recorded') : 'Required'}</p>
      ${staff && loan.document ? `<form data-contract class="entry-form"><label>Named borrower’s signed exact contract packet<input name="contractFile" type="file" accept="application/pdf,image/png,image/jpeg" /></label><label><input name="witnessedSignature" type="checkbox" />I witnessed the named borrower sign this exact printed packet at the office.</label><button class="button button-outline" type="submit">Record borrower contract signature</button></form>
      <p>${evidence.borrower_contract_signed ? 'Your exact contract signing evidence is recorded.' : 'Record the actual borrower signature before release.'}</p>
      ${loan.authorization && !loan.authorization.revoked ? `<form data-cash class="entry-form"><label>Borrower’s actual cash-receipt confirmation<input name="cashFile" type="file" accept="application/pdf,image/png,image/jpeg" /></label><button class="button button-outline" type="submit">Record actual cash acknowledgment</button></form>
      <form data-release class="entry-form">${input('cashAmount', 'Actual cash personally received by the named borrower (PHP)')}<label><input name="borrowerConfirmed" type="checkbox" />The named borrower confirmed receiving this exact cash at the office.</label><button class="button button-primary" type="submit">Record completed office release</button></form>` : ''}` : ''}` : ''}
      ${loan.status === 'released' ? `<p>Actual release: ${esc(loan.release?.released_at || '')}</p><p>Official release receipt: ${esc(loan.release?.receipt?.receipt_reference || '')}</p><p>Cash received: PHP ${esc(loan.release?.receipt?.actual_cash_received || '')}</p><p>Client account: ${esc(loan.credential_intent?.status || 'pending')}</p>${canManageCredentials ? button('credentials', 'Retry account setup') : ''}` : ''}`;
  }

  function complianceMarkup() {
    if (!hasPermission(session, 'lending.contract_schedule.manage')) return '<p>Management contract schedule permission is required to record the exact 7x7 compliance review.</p>';
    return `<details><summary>Exact 7x7 pricing and disclosure review</summary><form data-compliance class="entry-form"><p>This uses the existing compliance authority for this locked packet. A proposed signature-date basis does not record a borrower signature.</p>
      ${[['applicability_review_ready', 'Legal applicability reviewed'], ['pricing_cap_review_ready', 'Pricing caps reviewed'], ['disclosure_ready', 'Disclosures ready'], ['total_cost_cap_review_ready', 'Total-cost caps reviewed']].map(([name, label]) => `<label><input type="checkbox" name="${name}" />${label}</label>`).join('')}
      ${input('policyVersion', 'Approved penalty policy version')}${input('penaltyRate', 'Contractual monthly penalty rate', 'text', '0.030000')}${input('rateCeiling', 'Approved applicable penalty-rate ceiling')}${input('lifetimeCeiling', 'Approved lifetime non-principal cost ceiling (PHP)')}${input('countedCost', 'Counted non-principal cost at contract lock (PHP)')}${input('complianceEvidence', 'Pricing/compliance evidence reference')}<label>Review note<textarea name="complianceNote"></textarea></label><button class="button button-outline" type="submit">Record exact 7x7 compliance review</button></form></details>`;
  }

  function complianceBody() {
    const terms = loan.packet.terms;
    return { loan_id: loan.loan_id, payment_frequency: terms.payment_frequency, contract_reference: loan.packet.contract_reference,
      contract_signed_date: terms.schedule_basis_date, effective_from: terms.schedule_basis_date, grace_days: terms.grace_days,
      first_due_date: terms.first_due_date, agreed_daily_payment: terms.installment_amount,
      ...Object.fromEntries(['applicability_review_ready', 'pricing_cap_review_ready', 'disclosure_ready', 'total_cost_cap_review_ready'].map((name) => [name, field(name).checked === true])),
      penalty_policy_version: text('policyVersion'), penalty_monthly_rate: text('penaltyRate'), penalty_proration_days: 30,
      penalty_rate_ceiling: text('rateCeiling'), lifetime_nonprincipal_cost_ceiling: text('lifetimeCeiling'), counted_nonprincipal_cost_at_contract_lock: text('countedCost'),
      evidence_reference: text('complianceEvidence'), review_note: text('complianceNote') };
  }

  async function upload(name, purpose) {
    const witnessed = purpose === 'borrower_contract_signed' && field('witnessedSignature')?.checked === true;
    if (purpose === 'borrower_contract_signed' && !witnessed) throw Object.assign(new Error('Confirm that you witnessed the named borrower sign this exact packet.'), { beforeWrite: true });
    const file = field(name)?.files?.[0];
    if (!file || file.size > 10485760 || !['application/pdf', 'image/png', 'image/jpeg'].includes(file.type)) throw Object.assign(new Error('Select a signed PDF, PNG or JPEG of at most 10 MiB.'), { beforeWrite: true });
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = ''; for (let offset = 0; offset < bytes.length; offset += 8192) binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
    return { request_id: crypto.randomUUID(), packet_hash: loan.packet_hash, purpose, media_type: file.type,
      content_base64: btoa(binary), witnessed_wet_signature: witnessed, authorization_id: purpose === 'borrower_cash_received' ? loan.authorization.id : null };
  }

  function showCredentials(result) {
    wipe(status); preserveStatus = true;
    const values = result?.credentials;
    if (result?.status === 'completed' && object(values) && typeof values.username === 'string' && typeof values.password === 'string') {
      status.innerHTML = `<p>Provide these one-time credentials to the borrower now.</p><p>Username: ${esc(values.username)}</p>${input('issuedPassword', 'One-time password', 'password', values.password)}<button class="button button-outline" type="button" data-toggle-issued-password aria-pressed="false">Show password</button><p>${esc(result.delivery?.detail || '')}</p>`;
      const password = status.querySelector('[name="issuedPassword"]');
      const toggle = status.querySelector('[data-toggle-issued-password]');
      password.setAttribute('readonly', '');
      on(toggle, 'click', () => {
        if (disposed || status.querySelector('[name="issuedPassword"]') !== password) return;
        const reveal = password.getAttribute('type') === 'password';
        password.setAttribute('type', reveal ? 'text' : 'password');
        toggle.textContent = reveal ? 'Hide password' : 'Show password';
        toggle.setAttribute('aria-pressed', String(reveal));
      }, true);
    } else status.innerHTML = `<p>${esc(result?.detail || 'Credential setup result recorded. Reload the account status.')}</p>`;
  }

  function render() {
    clearActions(); wipe(workspace);
    workspace.innerHTML = `<h3>First loan · ${esc(review.application_reference)}</h3><p>Saved application version ${esc(review.version_number)}. CIF/application confirmation, loan signing and cash acknowledgment remain separate.</p>${button('reload', 'Reload saved record')}
      ${loan ? loanMarkup() : emptyState('No first-loan approval has been recorded for this application.')}
      ${decisions.length ? `<details><summary>Recorded Management decisions</summary>${decisions.map((decision) => `<p>${esc(decision.decision.replaceAll('_', ' '))}: ${esc(decision.reason)} · ${esc(decision.recorded_at || '')}</p>`).join('')}</details>` : ''}
      ${manager && (!loan || loan.status === 'cancelled') ? approvalMarkup() : ''}`;
    action('reload', () => { if (state === 'saving') return; open(); });
    const approval = workspace.querySelector('[data-approval]');
    if (approval) on(approval, 'submit', (event) => { event.preventDefault(); mutate(`${BASE}/approve`, termsBody, (value) => validLoan(value, review)); }, true);
    const reject = workspace.querySelector('[data-reject]');
    if (reject) on(reject, 'submit', (event) => { event.preventDefault(); mutate(`${BASE}/reject`, () => ({ request_id: crypto.randomUUID(), application_version_id: review.application_version_id, reason: text('decisionReason') }), (value) => uid(value?.decision_id) && value.decision === 'rejected'); }, true);
    if (!loan) return;
    const endpoint = `${BASE}/${loan.loan_id}`;
    const packetBody = () => ({ request_id: crypto.randomUUID(), packet_hash: loan.packet_hash });
    const compliance = workspace.querySelector('[data-compliance]');
    if (compliance) on(compliance, 'submit', (event) => { event.preventDefault(); mutate('/api/v1/management/financial-accounting/contract-schedules/7x7-pricing-compliance/review', complianceBody,
      (value) => value?.loan_id === loan.loan_id && HASH.test(value.terms_fingerprint)); }, true);
    action('documents', () => mutate(`${endpoint}/documents`, () => ({ packet_hash: loan.packet_hash }), (value) => uid(value?.id) && HASH.test(value.content_sha256) && Number.isSafeInteger(value.byte_count) && value.byte_count > 0));
    action('authorize', () => mutate(`${endpoint}/authorize-release`, packetBody, (value) => uid(value?.authorization_id) && value.packet_hash === loan.packet_hash));
    action('cancel', () => mutate(`${endpoint}/cancel-approval`, () => ({ ...packetBody(), reason: text('revokeReason') }), (value) => validLoan(value, review)));
    action('revoke', () => mutate(`${endpoint}/revoke-release`, () => ({ request_id: crypto.randomUUID(), authorization_id: loan.authorization.id, reason: text('revokeReason') }), (value) => uid(value?.revocation_id)));
    for (const [selector, name, purpose] of [['[data-contract]', 'contractFile', 'borrower_contract_signed'], ['[data-cash]', 'cashFile', 'borrower_cash_received']]) {
      const target = workspace.querySelector(selector);
      if (target) on(target, 'submit', (event) => { event.preventDefault(); mutate(`${endpoint}/evidence`, () => upload(name, purpose),
        (value) => value?.packet_hash === loan.packet_hash && value.purpose === purpose && /^office-evidence:[0-9a-f-]{36}$/i.test(value.evidence_reference),
        async (value, request) => { evidence[purpose] = value.evidence_reference; await refresh(request); }); }, true);
    }
    const release = workspace.querySelector('[data-release]');
    if (release) on(release, 'submit', (event) => {
      event.preventDefault();
      mutate(`${endpoint}/release`, () => {
        if (!evidence.borrower_contract_signed || !evidence.borrower_cash_received) throw Object.assign(new Error('Record your exact contract signing and actual cash-receipt evidence first.'), { beforeWrite: true });
        return { ...packetBody(), authorization_id: loan.authorization.id, contract_evidence_reference: evidence.borrower_contract_signed,
          cash_evidence_reference: evidence.borrower_cash_received, cash_amount: text('cashAmount'), borrower_confirmed: field('borrowerConfirmed').checked === true };
      }, (value) => validLoan(value, review) && value.status === 'released', async (value, request) => {
        await refresh(request); if (current(request)) showCredentials(value.credentials);
      });
    }, true);
    action('credentials', () => mutate(`${endpoint}/credentials`, {}, object, async (value, request) => { await refresh(request); if (current(request)) showCredentials(value); }));
    action('download', async () => {
      if (state !== 'editing') return;
      const request = token;
      const selected = { loanId: loan.loan_id, packetHash: loan.packet_hash,
        documentId: loan.document.id, documentHash: loan.document.content_sha256,
        filename: `${loan.loan_number}-locked-contract.pdf` };
      const unchanged = () => current(request) && loan?.loan_id === selected.loanId
        && loan.packet_hash === selected.packetHash && loan.document?.id === selected.documentId
        && loan.document.content_sha256 === selected.documentHash;
      try {
        const blob = await api.request(`${endpoint}/documents`, { responseType: 'blob', signal });
        if (!unchanged()) return;
        const url = URL.createObjectURL(blob); urls.push(url);
        const link = document.createElement('a'); link.href = url; link.download = selected.filename; link.click();
      } catch (error) { if (unchanged()) { if ([401, 403].includes(error?.status)) denyAccess(error); else showError(error); } }
    });
  }

  mounts.set(root, dispose);
  if (signal?.aborted) { dispose(); return dispose; }
  signal?.addEventListener('abort', dispose, { once: true });
  if (!sessionHasRole(session, 'employee', 'management') || !hasPermission(session, 'client_onboarding.requirement.review')) {
    root.innerHTML = emptyState('Authorized office access is required.'); return dispose;
  }
  root.innerHTML = `<form class="entry-form">${input('intakeReference', 'Office intake reference')}${input('applicationReference', 'Loan application reference')}<div class="action-row"><button class="button button-primary" type="submit">Open first-loan workflow</button><button class="button button-outline" type="button">Clear</button></div></form><div data-first-loan-workspace></div><div data-first-loan-status role="status" aria-live="polite"></div>`;
  form = root.querySelector('form'); intake = root.querySelector('[name="intakeReference"]'); reference = root.querySelector('[name="applicationReference"]');
  clearButton = form.querySelector('button[type="button"]'); workspace = root.querySelector('[data-first-loan-workspace]'); status = root.querySelector('[data-first-loan-status]');
  on(form, 'submit', open);
  for (const control of [intake, reference]) { on(control, 'input', invalidate); on(control, 'change', invalidate); }
  on(clearButton, 'click', () => { invalidate(); intake.value = ''; reference.value = ''; intake.focus(); });
  return dispose;
}

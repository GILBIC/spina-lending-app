import { sessionHasRole } from './roles.js';
import { escapeHtml as h, formatMoney, hasPermission } from './ui.js';
import { createTreasuryClient } from './treasury-api.js';
import { createSourceAccountingClient } from './management-source-accounting.js';

const id = (v) => typeof v === 'string' && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(v);
const digest = (v) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const money = (v) => typeof v === 'string' && /^(0|[1-9]\d{0,15})\.\d{2}$/.test(v);
const date = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;
const check = (ok, text = 'The retained payout accounting evidence is incomplete. Reload before continuing.') => { if (!ok) throw Error(text); };
const pick = (v, keys) => Object.fromEntries(keys.map((key) => [key, v[key]]));
const cents = (v) => BigInt(v.replace('.', ''));
const button = (key, text) => `<button type="button" class="button button-outline" ${key}>${h(text)}</button>`;
const choice = (name, label, rows, selected) => `<label>${h(label)}<select name="${name}" required><option value="">Choose…</option>${rows.map(([value, text, disabled]) => `<option value="${h(value)}"${value === selected ? ' selected' : ''}${disabled ? ' disabled' : ''}>${h(text)}</option>`).join('')}</select></label>`;
const facts = (rows) => `<dl>${rows.map(([label, value]) => `<dt>${h(label)}</dt><dd>${h(value)}</dd>`).join('')}</dl>`;
const mounts = new WeakMap();

const substantive = (value, minimum = 20) => { check(typeof value === 'string' && value.trim().length >= minimum && value.trim().length <= 2000, `Supply explicit evidence of ${minimum}–2000 characters.`); return value.trim(); };
function impairedBoundary(value, allowance) {
  check(value&&['allowance_before','allowance_after'].every(k=>money(value[k]))&&['allowance_unwind','impairment_adjustment'].every(k=>typeof value[k]==='string'&&/^-?(0|[1-9]\d{0,15})\.\d{2}$/.test(value[k])));
  check(cents(value.allowance_before)+cents(value.allowance_unwind)+cents(value.impairment_adjustment)===cents(value.allowance_after)&&value.allowance_after===allowance);
  return pick(value,['allowance_before','allowance_unwind','impairment_adjustment','allowance_after']);
}
const boundaryFacts=v=>v?[['Allowance before impaired boundary',v.allowance_before],['Gross/net allowance reconciliation',v.allowance_unwind],['Impairment adjustment',v.impairment_adjustment],['Allowance after impaired boundary',v.allowance_after]]:[];
export function renewalCandidate(value, { bookId, accountId, payoutId }) {
  check(value?.policy_version === 'native_regular_renewal_measurement_v1' && value.book_id === bookId && value.treasury_account_id === accountId && value.payout_id === payoutId && ['execution_id','old_loan_id','new_loan_id','accounting_asset_id','schedule_id'].every(key => id(value[key])) && value.old_loan_id !== value.new_loan_id && date(value.effective_date) && digest(value.source_digest));
  const monetary = ['fresh_cash','old_loan_component','old_accrued_interest','old_allowance','old_gross_carrying','revised_pv','nominal_settlement','contractual_total'];
  check(monetary.every(key => money(value[key])) && cents(value.old_loan_component) + cents(value.old_accrued_interest) === cents(value.old_gross_carrying) && typeof value.original_daily_eir === 'string' && /^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value.original_daily_eir) && Number(value.original_daily_eir) > 0 && Number.isFinite(Number(value.original_daily_eir)));
  let retained = null;
  check(value.predecessor_credit_impaired===undefined||typeof value.predecessor_credit_impaired==='boolean');
  check(value.predecessor_credit_impaired===true ? value.derecognition_blocker==='successor_credit_adjusted_eir_policy_required' : value.derecognition_blocker==null);
  const boundary=value.predecessor_credit_impaired===true?impairedBoundary(value.credit_impaired_boundary,value.old_allowance):null;
  check(boundary!==null||value.credit_impaired_boundary==null);
  if (value.retained_review != null) { const row = value.retained_review; check(id(row.id) && ['modification_no_derecognition','derecognition'].includes(row.decision) && digest(row.measurement_digest)); retained = pick(row,['id','decision','measurement_digest']); }
  check(!value.predecessor_credit_impaired||retained?.decision!=='derecognition');
  return {...pick(value,['policy_version','book_id','payout_id','execution_id','old_loan_id','new_loan_id','accounting_asset_id','treasury_account_id','effective_date','source_digest','original_daily_eir','schedule_id','contract_reference','evidence_reference',...monetary]),...(value.predecessor_credit_impaired===undefined?{}:pick(value,['predecessor_credit_impaired','derecognition_blocker'])),...(boundary?{credit_impaired_boundary:boundary}:{}),retained_review:retained};
}
export function renewalReviewInputs(value, candidate) {
  check(['modification_no_derecognition','derecognition'].includes(value.decision), 'Choose the reviewed renewal treatment explicitly.');
  check(value.decision!=='derecognition'||!candidate.derecognition_blocker,'Derecognition requires a supported initial credit status and credit-adjusted EIR policy for the successor.');
  const qualitative = value.qualitative_assessment;
  check(qualitative?.signed_contract_reviewed === true && qualitative.cash_flow_terms_reviewed === true && qualitative.substantial_change_assessed === true, 'Confirm the signed contract bundle and both qualitative assessments.');
  check(money(value.settlement_consideration) && money(value.settlement_rebate) && cents(value.settlement_consideration) + cents(value.settlement_rebate) === cents(candidate.nominal_settlement), 'Consideration and rebate must equal the signed nominal settlement.');
  const result = {decision:value.decision,accounting_policy_reference:substantive(value.accounting_policy_reference,1),qualitative_assessment:{signed_contract_reviewed:true,cash_flow_terms_reviewed:true,substantial_change_assessed:true,decision_basis:substantive(qualitative.decision_basis)},decision_rationale:substantive(value.decision_rationale),settlement_consideration:value.settlement_consideration,settlement_rebate:value.settlement_rebate,settlement_basis:substantive(value.settlement_basis),new_initial_fair_value:null,fair_value_effective_date:null,fair_value_basis:null,day_one_difference_rationale:null};
  if (value.decision === 'derecognition') {
    check(money(value.new_initial_fair_value) && value.new_initial_fair_value !== '0.00' && value.fair_value_effective_date === candidate.effective_date, 'Supply positive fair value dated at the renewal effective date.');
    Object.assign(result,{new_initial_fair_value:value.new_initial_fair_value,fair_value_effective_date:value.fair_value_effective_date,fair_value_basis:substantive(value.fair_value_basis),day_one_difference_rationale:substantive(value.day_one_difference_rationale)});
  } else check(['new_initial_fair_value','fair_value_effective_date','fair_value_basis','day_one_difference_rationale'].every(key => value[key] == null || value[key] === ''), 'Modification retains the original EIR; clear new fair-value inputs.');
  return result;
}

export function payoutSource(value, { bookId, accountId, payoutId, stage }) {
  check(['debit', 'completion'].includes(stage) && value?.book_id === bookId && value.payout_id === payoutId && value.stage === stage && value.treasury_account_id === accountId && [value.event_id, value.loan_id, value.client_id, value.fiscal_period_id].every(id) && (stage === 'completion' ? id(value.disbursement_event_id) : value.disbursement_event_id === null) && digest(value.source_digest) && date(value.posting_date) && money(value.amount) && value.amount !== '0.00' && money(value.fee) && (stage === 'debit' || value.fee === '0.00'));
  check(value.accounting_policy_version == null || value.accounting_policy_version === 'native_regular_renewal_completion_v1');
  if (value.accounting_policy_version === 'native_regular_renewal_completion_v1') return renewalCompletionSource(value);
  check(Array.isArray(value.lines) && value.lines.length === (value.fee === '0.00' ? 2 : 3));
  const rows = value.lines;
  for (const line of rows) check(Number.isInteger(line.line_number) && line.line_number > 0 && ['1030', '1050', '1100', '5240'].includes(line.account_code) && typeof line.account_snapshot?.name === 'string' && money(line.debit) && money(line.credit));
  check(new Set(rows.map((line) => line.line_number)).size === rows.length);
  const transit = rows.filter((line) => line.account_code === '1050'), counter = rows.filter((line) => line.account_code === (stage === 'debit' ? '1030' : '1100')), fee = rows.filter((line) => line.account_code === '5240');
  check(transit.length === 1 && counter.length === 1 && fee.length === (value.fee === '0.00' ? 0 : 1));
  check(transit[0][stage === 'debit' ? 'debit' : 'credit'] === value.amount && transit[0][stage === 'debit' ? 'credit' : 'debit'] === '0.00');
  check(cents(counter[0][stage === 'debit' ? 'credit' : 'debit']) === cents(value.amount) + cents(value.fee) && counter[0][stage === 'debit' ? 'debit' : 'credit'] === '0.00');
  if (fee.length) check(fee[0].debit === value.fee && fee[0].credit === '0.00');
  return { ...pick(value, ['book_id', 'payout_id', 'stage', 'event_id', 'loan_id', 'client_id', 'disbursement_event_id', 'treasury_account_id', 'fiscal_period_id', 'posting_date', 'amount', 'fee', 'source_digest']), lines: rows.map((line) => ({ ...pick(line, ['line_number', 'account_code', 'debit', 'credit']), name: line.account_snapshot.name })) };
}

function renewalCompletionSource(value) {
  check(value.stage==='completion' && id(value.old_loan_id) && value.old_loan_id!==value.loan_id && id(value.accounting_asset_id) && id(value.renewal_review_id) && ['modification_no_derecognition','derecognition'].includes(value.renewal_decision));
  const m=value.measurement, amountKeys=['old_gross_carrying','old_allowance','fresh_cash','new_initial_carrying','new_initial_allowance'];
  check(m && amountKeys.every(key=>money(m[key])) && ['old_asset_difference','new_asset_difference'].every(key=>typeof m[key]==='string' && /^-?(0|[1-9]\d{0,15})\.\d{2}$/.test(m[key])) && m.fresh_cash===value.amount && m.accounting_asset_continues===(value.renewal_decision==='modification_no_derecognition'));
  check(m.accounting_asset_continues ? m.new_initial_allowance===m.old_allowance && m.new_asset_difference==='0.00' : m.new_initial_allowance==='0.00' && value.accounting_asset_id===value.loan_id);
  check(value.predecessor_credit_impaired===undefined||typeof value.predecessor_credit_impaired==='boolean');
  const boundary=value.predecessor_credit_impaired===true?impairedBoundary(value.credit_impaired_boundary,m.old_allowance):null;
  check(boundary ? value.renewal_decision==='modification_no_derecognition' : value.credit_impaired_boundary==null);
  const rows=value.lines; check(Array.isArray(rows) && rows.length>=3 && rows.length<=(boundary?14:10) && new Set(rows.map(row=>row.line_number)).size===rows.length);
  const roles={renewed_asset:['1100','debit','new'],old_loan_component:['1100','credit','old'],old_accrued_interest:['1120','credit','old'],fresh_cash_transit:['1050','credit','new'],old_allowance:['1190','debit','old'],continued_allowance:['1190','credit','new']};
  for(const row of rows) {
    check(Number.isInteger(row.line_number) && row.line_number>0 && money(row.debit) && money(row.credit) && (cents(row.debit)>0n)!==(cents(row.credit)>0n) && typeof row.account_snapshot?.name==='string');
    let role=roles[row.component];
    if(['old_asset_difference','new_asset_difference'].includes(row.component))role=[cents(m[row.component])>=0n?'4020':'5010',cents(m[row.component])>=0n?'credit':'debit',row.component==='old_asset_difference'?'old':'new'];
    if(row.component==='old_asset_elapsed_interest')role=row.account_code==='1120'?['1120','debit','old']:['4000','credit','old'];
    if(boundary&&row.component==='old_asset_allowance_unwind'){const increase=cents(boundary.allowance_unwind)>0n;role=row.account_code==='4000'?['4000',increase?'debit':'credit','old']:['1190',increase?'credit':'debit','old'];}
    if(boundary&&row.component==='old_asset_impaired_adjustment'){const positive=cents(boundary.impairment_adjustment)>0n;role=row.account_code==='5000'?['5000',positive?'debit':'credit','old']:['1190',positive?'credit':'debit','old'];}
    check(role && row.account_code===role[0] && row[role[1]]!=='0.00' && row.loan_id===(role[2]==='old'?value.old_loan_id:value.loan_id));
  }
  const sum=(component,side)=>rows.filter(row=>row.component===component).reduce((n,row)=>n+cents(row[side]),0n);
  for(const component of Object.keys(roles).concat(['old_asset_difference','new_asset_difference']))check(rows.filter(row=>row.component===component).length<=1);
  check(sum('renewed_asset','debit')===cents(m.new_initial_carrying) && sum('fresh_cash_transit','credit')===cents(m.fresh_cash) && sum('old_loan_component','credit')+sum('old_accrued_interest','credit')===cents(m.old_gross_carrying) && sum('old_allowance','debit')===cents(m.old_allowance) && sum('continued_allowance','credit')===cents(m.new_initial_allowance));
  for(const key of ['old_asset_difference','new_asset_difference'])check(sum(key,'credit')-sum(key,'debit')===cents(m[key]));
  for(const [component,amount,accounts] of [['old_asset_elapsed_interest',null,['1120','4000']],['old_asset_allowance_unwind',boundary?cents(boundary.allowance_unwind):0n,['4000','1190']],['old_asset_impaired_adjustment',boundary?cents(boundary.impairment_adjustment):0n,['5000','1190']]]){
    const pair=rows.filter(r=>r.component===component), absolute=amount===null?null:amount<0n?-amount:amount;
    check(pair.length===(absolute===0n?0:pair.length===0&&absolute===null?0:2));
    if(pair.length)check(new Set(pair.map(r=>r.account_code)).size===2&&pair.every(r=>accounts.includes(r.account_code))&&sum(component,'debit')===sum(component,'credit')&&(absolute===null||sum(component,'debit')===absolute));
  }
  check(sum('old_asset_elapsed_interest','debit')===sum('old_asset_elapsed_interest','credit') && rows.reduce((n,row)=>n+cents(row.debit)-cents(row.credit),0n)===0n);
  return {...pick(value,['book_id','payout_id','stage','event_id','loan_id','client_id','disbursement_event_id','treasury_account_id','fiscal_period_id','posting_date','amount','fee','source_digest','accounting_policy_version','old_loan_id','accounting_asset_id','renewal_review_id','renewal_decision']),...(boundary?{predecessor_credit_impaired:true,credit_impaired_boundary:boundary}:{}),measurement:pick(m,[...amountKeys,'old_asset_difference','new_asset_difference','accounting_asset_continues']),lines:rows.map(row=>({...pick(row,['line_number','account_code','debit','credit','loan_id','component']),name:row.account_snapshot.name}))};
}

export async function mountPayoutAccounting({ root, api, session, getSession = () => session, signal }) {
  mounts.get(root)?.();
  const controller = new AbortController();
  let disposed = false, generation = 0, busy = false, listeners = [], book, wallets = [], accountId = '', stage = 'debit', reference = '', source, prepared, intent, renewal;
  const can = () => sessionHasRole(getSession(), 'management') && hasPermission(getSession(), 'accounting.view') && hasPermission(getSession(), 'accounting.journal.manage');
  const canRenewal = () => can() && hasPermission(getSession(), 'accounting.renewal_treatment_decision.manage');
  const sessionScope = (value) => JSON.stringify([value?.user, value?.permissions, value?.access_token, value?.device_id]);
  const initialScope = sessionScope(session);
  function current(g = generation) { if (!disposed && sessionScope(getSession()) !== initialScope) denied(); return !disposed && !signal?.aborted && g === generation; }
  function clearListeners() { listeners.forEach((remove) => remove()); listeners = []; }
  function dispose() { if (disposed) return; disposed = true; generation++; controller.abort(); client.dispose(); treasury.dispose(); clearListeners(); book = source = prepared = intent = renewal = null; wallets = []; root.innerHTML = ''; signal?.removeEventListener('abort', dispose); if (mounts.get(root) === dispose) mounts.delete(root); }
  function denied() { dispose(); root.innerHTML = '<p role="alert">Accounting access changed. Reopen with current permissions.</p>'; }
  const client = createSourceAccountingClient({ api, session, getSession, signal: controller.signal, onDenied: denied });
  const treasury = createTreasuryClient(api, { getSession, signal: controller.signal, onDenied: denied });
  function frame(markup) { if (!current()) return; clearListeners(); root.innerHTML = `<p data-message role="status"></p>${markup}`; }
  function message(text) { const node = root.querySelector('[data-message]'); if (node) node.textContent = text; }
  function lock(value) { busy = value; for (const tag of ['button', 'input', 'select']) for (const node of root.querySelectorAll(tag)) node.disabled = value; }
  function listen(selector, event, action) { for (const node of root.querySelectorAll(selector)) { const handler = async (e) => { e.preventDefault(); if (!current() || busy) return; try { await action(node); } catch (error) { if (current()) message(error.message); } }; node.addEventListener(event, handler); listeners.push(() => node.removeEventListener(event, handler)); } }
  function scope(payoutId) { return { bookId: book.book_id, accountId, payoutId, stage }; }
  async function freshBook(g) { const result = await client.get('/book'); if (!current(g)) return; const value = result.book; check(value?.status === 'configured' && id(value.book_id) && typeof value.entity_label === 'string', 'Configure the accounting book before reviewing payouts.'); if (book && book.book_id !== value.book_id) { denied(); throw Error('Accounting book changed.'); } book = value; }
  async function load() {
    check(!client.pending(), 'Recover the unchanged request first.'); const g = ++generation; source = prepared = intent = renewal = null; frame('<p>Loading authorized wallets…</p>'); lock(true);
    try { check(can(), 'Current Management journal permission is required.'); await freshBook(g); if (!current(g)) return; const workspace = await treasury.workspace(); if (!current(g)) return; check(workspace.enabled && workspace.owner_configured); wallets = workspace.accounts.filter((row) => row.balance !== null && row.active !== false && ['gcash', 'bank'].includes(row.kind)); check(wallets.every((row) => id(row.id) && typeof row.alias === 'string')); render(); }
    catch (error) { if (current(g)) { frame(`<p role="alert">${h(error.message)}</p>${button('data-load', 'Retry read')}`); listen('[data-load]', 'click', load); } }
    finally { if (current(g)) lock(false); }
  }
  function details(value) { return [['Payout reference', value.payout_id], ['Actual stage', value.stage === 'debit' ? 'Verified wallet debit' : 'Borrower completion'], ['Funding wallet', wallets.find((row) => row.id === value.treasury_account_id)?.alias || value.treasury_account_id], ['Loan reference', value.loan_id], ['Actual posting date', value.posting_date], ['Principal', formatMoney(value.amount)], ['Actual wallet fee', formatMoney(value.fee)], ...(value.measurement ? [['Renewal treatment',value.renewal_decision],['Old operational loan',value.old_loan_id],['Accounting asset',value.accounting_asset_id],['Retained treatment review',value.renewal_review_id],...Object.entries(value.measurement).map(([key,amount])=>[key,typeof amount==='boolean'?String(amount):formatMoney(amount)])] : []), ...boundaryFacts(value.credit_impaired_boundary), ...value.lines.map((line) => [`${line.account_code}  -  ${line.name}${line.loan_id ? ` — loan ${line.loan_id}` : ''}`, `Debit ${formatMoney(line.debit)}  -  Credit ${formatMoney(line.credit)}`])]; }
  function validatePreparation(value, expected = null, requestId = null, preparationId = null) {
    const row = value?.preparation; check(row && id(row.id) && row.actor_user_id === getSession()?.user?.id && digest(row.confirmation_token) && (!requestId || row.request_id === requestId) && (!preparationId || row.id === preparationId));
    const projected = payoutSource({ ...row.snapshot, source_digest: row.source_digest }, scope(row.payout_id));
    for (const key of ['book_id', 'payout_id', 'stage', 'event_id', 'treasury_account_id', 'loan_id', 'client_id', 'disbursement_event_id']) check(row[key] === projected[key]);
    if (expected) check(JSON.stringify(projected) === JSON.stringify(expected));
    if (value.posting !== null) { const posted = value.posting; check(posted && posted.preparation_id === row.id && id(posted.journal_entry_id) && typeof posted.exact_posted === 'boolean' && typeof posted.correction_pending === 'boolean'); for (const key of ['book_id', 'payout_id', 'stage', 'event_id', 'treasury_account_id', 'loan_id', 'client_id', 'disbursement_event_id', 'source_digest']) check(posted[key] === row[key]); }
    return true;
  }
  async function lookup(recover = false, measureRenewal = false) {
    check(wallets.some((row) => row.id === accountId) && id(reference), 'Choose the authorized funding wallet and an existing payout or preparation reference.');
    check(!client.pending(), 'Recover the unchanged request first.');
    const g = ++generation; source = prepared = intent = renewal = null; render(); lock(true);
    try { await freshBook(g); if (!current(g)) return;
      if (measureRenewal) { check(canRenewal(), 'Current renewal treatment permission is required.'); check(stage === 'completion', 'Choose borrower completion to review renewal treatment.'); const result = await client.get(`/treasury/payouts/${reference}/renewal-measurement`); if (!current(g)) return; renewal = renewalCandidate(result,scope(reference)); }
      else if (recover) { const result = await client.get(`/treasury/payout-preparations/${reference}`); if (!current(g)) return; validatePreparation(result, null, null, reference); prepared = result; source = payoutSource({ ...result.preparation.snapshot, source_digest: result.preparation.source_digest }, scope(result.preparation.payout_id)); }
      else { const query = new URLSearchParams({ stage }); const result = await client.get(`/treasury/payouts/${reference}/review?${query}`); if (!current(g)) return; source = payoutSource(result, scope(reference)); }
      render();
    } catch (error) { if (current(g)) { source = prepared = renewal = null; render(); message(error.message); } }
    finally { if (current(g)) lock(false); }
  }
  function renewalFacts(value) { return [...boundaryFacts(value.credit_impaired_boundary),...(value.predecessor_credit_impaired!==undefined?[['Predecessor credit-impaired',String(value.predecessor_credit_impaired)]]:[]),...(value.derecognition_blocker?[['Derecognition unavailable','Supported successor initial credit status and credit-adjusted EIR policy are required. Modification remains subject to explicit review.']]:[]),['Renewal effective date',value.effective_date],['Signed schedule',value.schedule_id],...(value.contract_reference ? [['Contract reference',value.contract_reference]] : []),...(value.evidence_reference ? [['Signed evidence reference',value.evidence_reference]] : []),['Old operational loan',value.old_loan_id],['New operational loan',value.new_loan_id],['Existing accounting asset',value.accounting_asset_id],['Fresh cash',formatMoney(value.fresh_cash)],['Old gross carrying amount',formatMoney(value.old_gross_carrying)],['Old allowance',formatMoney(value.old_allowance)],['Original daily EIR',value.original_daily_eir],['Revised present value at original EIR',formatMoney(value.revised_pv)],['Signed nominal settlement',formatMoney(value.nominal_settlement)]]; }
  function renewalMarkup() {
    if (!renewal) return '';
    if (renewal.retained_review) return `<h4>Renewal treatment retained</h4>${facts(renewalFacts(renewal))}${facts([['Treatment',renewal.retained_review.decision],['Review reference',renewal.retained_review.id]])}<p>Load the borrower-completion accounting review to prepare and separately post the retained treatment.</p>`;
    const input = (name,label,type='text') => `<label>${h(label)}<input name="${name}" type="${type}" maxlength="2000" /></label>`;
    return `<h4>Renewal measurement and treatment</h4>${facts(renewalFacts(renewal))}<p>Use the retained contract, settlement and accounting policy evidence. Select the treatment explicitly; no amount or fair value is inferred.</p><form data-renewal-review>${input('evidence_id','Uploaded signed-contract, settlement and measurement bundle ID')}${choice('decision','Reviewed treatment',[['modification_no_derecognition','Modification — accounting asset continues'],['derecognition','Derecognition — new accounting asset',!!renewal.derecognition_blocker]], '')}${input('accounting_policy_reference','Accounting policy reference')}<label><input type="checkbox" name="signed_contract_reviewed" />Uploaded bundle contains the signed renewal contract matching the displayed schedule and references, plus settlement and measurement support</label><label><input type="checkbox" name="cash_flow_terms_reviewed" />Contractual cash-flow changes reviewed</label><label><input type="checkbox" name="substantial_change_assessed" />Substantial change assessed against the policy</label>${input('qualitative_basis','Qualitative assessment (at least 20 characters)')}${input('decision_rationale','Treatment rationale (at least 20 characters)')}${input('settlement_consideration','Settlement consideration (exact decimal)')}${input('settlement_rebate','Settlement rebate (enter 0.00 when evidenced as none)')}${input('settlement_basis','Settlement basis (at least 20 characters)')}<p>For derecognition only, provide all four fair-value fields. For modification, leave them empty.</p>${input('new_initial_fair_value','New initial fair value')}${input('fair_value_effective_date','Fair value effective date','date')}${input('fair_value_basis','Fair value basis')}${input('day_one_difference_rationale','Day-one difference rationale, including a zero difference')}<button type="submit">Review renewal treatment</button></form>`;
  }
  function reviewRenewal(form) {
    check(canRenewal() && renewal && !renewal.retained_review && !client.pending());
    const field = key => String(form.querySelector(`[name="${key}"]`)?.value || '').trim();
    const evidenceId = field('evidence_id'); check(id(evidenceId),'Supply the uploaded private measurement evidence ID.');
    const reviewInput = renewalReviewInputs({...Object.fromEntries(['decision','accounting_policy_reference','decision_rationale','settlement_consideration','settlement_rebate','settlement_basis','new_initial_fair_value','fair_value_effective_date','fair_value_basis','day_one_difference_rationale'].map(key=>[key,field(key)])),qualitative_assessment:{signed_contract_reviewed:form.querySelector('[name="signed_contract_reviewed"]').checked,cash_flow_terms_reviewed:form.querySelector('[name="cash_flow_terms_reviewed"]').checked,substantial_change_assessed:form.querySelector('[name="substantial_change_assessed"]').checked,decision_basis:field('qualitative_basis')}},renewal);
    const held = renewal, requestId = crypto.randomUUID();
    intent = {path:`/treasury/payouts/${held.payout_id}/renewal-measurement`,body:{source_digest:held.source_digest,request_id:requestId,evidence_id:evidenceId,confirm:true,review:reviewInput},validate:v=>{check(v?.payout_id===held.payout_id && v.book_id===held.book_id && v.source_digest===held.source_digest && v.request_id===requestId && v.decision===reviewInput.decision && id(v.id) && digest(v.measurement_digest));return true;},complete:v=>{renewal={...held,retained_review:pick(v,['id','decision','measurement_digest'])};}};
    frame(`<h4>Retain renewal treatment</h4>${facts(renewalFacts(held))}${facts([['Uploaded evidence',evidenceId],['Treatment',reviewInput.decision],['Policy reference',reviewInput.accounting_policy_reference],['Qualitative assessment',reviewInput.qualitative_assessment.decision_basis],['Decision rationale',reviewInput.decision_rationale],['Consideration',reviewInput.settlement_consideration],['Rebate',reviewInput.settlement_rebate],['Settlement basis',reviewInput.settlement_basis],...(reviewInput.decision==='derecognition'?[['New fair value',reviewInput.new_initial_fair_value],['Fair value date',reviewInput.fair_value_effective_date],['Fair value basis',reviewInput.fair_value_basis],['Day-one difference rationale',reviewInput.day_one_difference_rationale]]:[])])}<p>This retains the treatment and evidence only. Journal preparation and posting remain separate confirmations.</p>${button('data-confirm','Confirm: retain renewal treatment')}${button('data-cancel','Cancel')}`);
    listen('[data-confirm]','click',()=>send(false)); listen('[data-cancel]','click',()=>{intent=null;render();});
  }
  function review(posting) {
    check(can() && source && !client.pending()); check(!source.measurement || canRenewal(), 'Current renewal treatment permission is required.'); const expected = source, requestId = crypto.randomUUID(), held = prepared;
    const title = posting ? 'Post payout stage accounting' : 'Prepare payout stage accounting';
    intent = posting ? { path: `/treasury/payout-preparations/${held.preparation.id}/post`, body: { source_digest: held.preparation.source_digest, confirmation_token: held.preparation.confirmation_token, confirm: true }, validate: (v) => validatePreparation(v, expected, null, held.preparation.id) && v.posting?.exact_posted === true && v.journal_entry_id === v.posting.journal_entry_id } : { path: `/treasury/payouts/${expected.payout_id}/prepare`, body: { stage, source_digest: expected.source_digest, request_id: requestId }, validate: (v) => validatePreparation(v, expected, requestId) };
    frame(`<article><h4 tabindex="-1" data-title>${h(title)}</h4>${facts(details(expected))}<p>${posting ? 'Posts this exact actual stage. A debit records cash leaving for loan payout transit; borrower completion moves that same principal into the approved loan receivable without another cash credit.' : 'Retains these exact actual-stage coordinates. Posting requires a separate confirmation.'}</p>${button('data-confirm', `Confirm: ${title}`)}${button('data-cancel', 'Cancel')}</article>`); root.querySelector('[data-title]')?.focus(); listen('[data-confirm]', 'click', () => send(false)); listen('[data-cancel]', 'click', render);
  }
  async function send(retry) { const g = generation, held = intent; check(can() && held); lock(true); try { await freshBook(g); if (!current(g)) return; const value = retry ? await client.retry() : await client.submit(held.path, held.body, held.validate); if (!current(g)) return; if (held.complete) held.complete(value); else prepared = value; intent = null; render(); } catch (error) { if (current(g)) { frame(`<p role="alert">${h(error.message)}</p><p>The result is not confirmed. Retry this unchanged request to recover it.</p>${button('data-retry', 'Retry unchanged request')}${[409, 422].includes(error.status) ? button('data-reload', 'Reload current evidence') : ''}`); listen('[data-retry]', 'click', () => send(true)); listen('[data-reload]', 'click', () => { client.reset(); return load(); }); } } finally { if (current(g)) lock(false); } }
  function render() {
    frame(`<h4>${h(book.entity_label)}</h4><p>Review the actual wallet debit separately from protected borrower completion. Receipt by a Collector leaves the amount in loan payout transit. Overall accounting readiness remains a separate review.</p><form data-payout-lookup>${choice('account_id', 'Funding wallet', wallets.map((row) => [row.id, row.alias]), accountId)}${choice('stage', 'Actual stage', [['debit', 'Verified wallet debit'], ['completion', 'Borrower completion']], stage)}<label>Existing payout or saved preparation reference<input name="reference" maxlength="36" required /></label><button type="submit" class="button button-primary">Load payout accounting review</button>${button('data-recover', 'Open saved preparation')}${canRenewal() ? button('data-renewal-load', 'Review renewal treatment') : ''}</form><section data-evidence>${renewalMarkup()}${source ? `${facts(details(source))}${prepared ? `<h4>${prepared.posting?.exact_posted ? 'Payout stage accounting posted' : 'Payout stage prepared for review'}</h4><p>Preparation ${h(prepared.preparation.id)}</p>${prepared.posting ? `<p>Journal ${h(prepared.posting.journal_entry_id)}</p><p>${prepared.posting.correction_pending ? 'A later source change requires correction review.' : 'Retained exact posting evidence is available.'}</p>` : button('data-post-payout', 'Review payout stage posting')}` : button('data-prepare-payout', 'Prepare payout stage accounting')}` : ''}</section>`);
    root.querySelector('[name="reference"]').value = reference;
    function formValues(form) { const value = (key) => String(form.querySelector(`[name="${key}"]`)?.value || '').trim(); accountId = value('account_id'); stage = value('stage'); reference = value('reference'); }
    listen('[data-payout-lookup]', 'submit', (form) => { formValues(form); return lookup(); }); listen('[data-recover]', 'click', () => { formValues(root.querySelector('[data-payout-lookup]')); return lookup(true); });
    for (const event of ['input', 'change']) listen('[data-payout-lookup]', event, () => { source = prepared = intent = renewal = null; root.querySelector('[data-evidence]').innerHTML = ''; });
    listen('[data-renewal-load]', 'click', () => { formValues(root.querySelector('[data-payout-lookup]')); return lookup(false,true); });
    listen('[data-renewal-review]','submit',reviewRenewal);
    listen('[data-prepare-payout]', 'click', () => review(false)); listen('[data-post-payout]', 'click', () => review(true));
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true }); if (signal?.aborted) { dispose(); return dispose; } await load(); return dispose;
}

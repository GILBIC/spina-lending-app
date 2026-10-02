import {buildCollectionSubmission} from './collector-contract.js';
import {buildCombinedSubmission, buildCorrection, collectorMutation, collectionResultMatches, combinedPairs, createCombinedReview, formatServerMoney, EXTRA_CHOICES, selectableScheduleDates} from './collector-workflow-contract.js';
import {escapeHtml as h, hasPermission} from './ui.js';
import {formatAuthoritativeMoney as formatMoney} from './client-schedule.js';

const value = (root, name) => root.querySelector(`[name="${name}"]`)?.value || '';
const cents=value=>{const match=String(value ?? '').trim().match(/^(\d+)(?:\.(\d{1,2}))?$/);return match?BigInt(match[1])*100n+BigInt((match[2] || '').padEnd(2,'0')):null;};
export function collectorPaymentDetailState(entry,entryType,amount,reason) {
  const entered=cents(amount),obligation=cents(entry?.contract_today_unpaid_amount);
  const isRegular=String(entry?.loan_type || '').toLowerCase().includes('regular');
  return {reasonRequired:entryType==='pass' || (isRegular && entered!==null && obligation!==null && entered<obligation),optionsVisible:obligation===null || (entered!==null && entered>obligation) || entry?.contract_no_collection_today===true,explanationRequired:reason==='other',promiseRequired:reason==='promised_to_pay_later'};
}
export function bindCollectorPaymentDetails(form,{getEntry,getEntryType=()=>value(form,'entryType') || 'payment'}={}) {
  const field=name=>form.querySelector(`[name="${name}"]`);
  function update(flags={}) {
    const state=collectorPaymentDetailState(getEntry?.() || {},getEntryType(),value(form,'amount'),value(form,'reasonCode'));
    state.reasonRequired ||= flags.regular_past_due_followup_required===true;
    state.optionsVisible ||= flags.extra_choice_required===true;
    const show=(name,visible,required=false)=>{const input=field(name);if(!input)return;const label=input.closest?.('label');if(label)label.hidden=!visible;input.required=required;};
    const pass=getEntryType()==='pass';show('amount',!pass,!pass);
    show('reasonCode',state.reasonRequired || Boolean(value(form,'reasonCode')) || Boolean(form.querySelector('[data-payment-options]')?.open),state.reasonRequired);
    show('followupNote',state.reasonRequired || Boolean(value(form,'reasonCode')),state.explanationRequired);
    show('promiseDate',state.promiseRequired,state.promiseRequired);show('promiseAmount',state.promiseRequired,state.promiseRequired);
    const options=form.querySelector('[data-payment-options]');if(options && (state.reasonRequired || state.optionsVisible))options.open=true;
    return state;
  }
  const change=()=>update();form.addEventListener('input',change);form.addEventListener('change',change);form.querySelector('[data-payment-options]')?.addEventListener('toggle',change);update();
  const cleanup=()=>{form.removeEventListener('input',change);form.removeEventListener('change',change);form.querySelector('[data-payment-options]')?.removeEventListener('toggle',change);};cleanup.update=update;return cleanup;
}
export function allocationField() {
  return '<label class="allocation-only">Payment allocation<select name="allocation"><option value="scheduled">Scheduled payment</option><option value="extra_as_advance">Extra cash as Advance</option><option value="extra_as_principal_reduction">Extra cash as Principal Reduction</option><option value="no_collection_voluntary">Voluntary payment on a No Collection date</option></select></label>';
}
export function followupFields() {
  return `<label>Past Due reason (required for short Regular payment)<select name="reasonCode"><option value="">No follow-up</option><option value="no_cash">No cash</option><option value="client_absent">Client absent</option><option value="business_slow">Business slow</option><option value="sick_hospital">Sick / hospital</option><option value="emergency">Emergency</option><option value="promised_to_pay_later">Promised to pay later</option><option value="other">Other</option></select></label><label>Follow-up note<textarea name="followupNote" maxlength="500"></textarea></label><label>Promised payment date<input name="promiseDate" type="date" /></label><label>Promised amount<input name="promiseAmount" inputmode="decimal" /></label>`;
}

export function readFollowup(form) {
  const reason = value(form,'reasonCode');
  return reason ? {reason_code:reason, note:value(form,'followupNote'), promised_payment_date:reason === 'promised_to_pay_later' ? value(form,'promiseDate') : null, promised_amount:reason === 'promised_to_pay_later' ? value(form,'promiseAmount') : null} : null;
}

export function renderCombinedPreview(result) {
  return `<div class="notice-card"><strong>${h(result.message || 'Review both loan allocations before saving.')}</strong><p>Cash ${formatServerMoney(result.cash_received_amount)} · Expected ${formatServerMoney(result.expected_total_amount)} · Short ${formatServerMoney(result.short_amount)} · Extra ${formatServerMoney(result.extra_amount)}</p>${(result.legs || []).map(leg => `<p>${h(leg.loan_type === 'seven_by_seven' ? '7x7' : 'Regular')}: Scheduled ${formatServerMoney(leg.scheduled_amount)} + Extra ${formatServerMoney(leg.extra_amount)} = ${formatServerMoney(leg.total_amount)}${leg.projected_covered_dates?.length ? `<br>Covered dates: ${leg.projected_covered_dates.map(h).join(', ')}` : ''}</p>`).join('')}</div>`;
}

// Uses the workspace guard for every request that can change financial state.
// No replay queue: uncertainty locks the workspace until authoritative refresh.
export function mountCollectorWorkflows({root, api, session, getSession=()=>session, entries, routeDate, getRoute, registerRouteConsumer=()=>()=>{}, guard, identity, onSaved, signal}) {
  const confirmedPairs=new Set(),pairKey=pair=>JSON.stringify([routeDate,...(pair || []).map(item=>item.route_entry_id).sort()]);
  let pairs = hasPermission(getSession(),'collection.create') ? combinedPairs(entries) : [];
  let canCorrect = hasPermission(getSession(),'collection.correct.own_unremitted');
  let choices = entries.filter(entry => (hasPermission(getSession(),'collection.create') && entry.can_enter_payment && !entry.processed_today) || (canCorrect && entry.can_edit_today && !entry.today_is_locked));
  const signature=route=>JSON.stringify([route?.route_date,(route?.entries || []).map(item=>[item.route_entry_id,item.loan_id,item.client_id,item.route_revision,item.processed_today,item.can_enter_payment,item.can_edit_today,item.today_is_locked])]);
  let routeSignature=signature({route_date:routeDate,entries}),stale=false;
  const review = createCombinedReview(api);
  let disposed = false;
  let selected = null;
  let scheduleDates = [];
  let loadVersion = 0;
  const current = () => !disposed && guard.current && !signal?.aborted && Boolean(getSession());
  root.innerHTML = `<h2>Combined Pay and covered-date payments</h2>
    ${pairs.length ? `<form data-combined-form class="entry-form"><label>Client<select name="pair">${pairs.map((pair,index) => `<option value="${index}">${h(pair[0].client_name)} · Regular + 7x7</option>`).join('')}</select></label><label>Total cash received<input name="amount" inputmode="decimal" required /></label><label>Borrower’s choice for extra cash<select name="extraChoice"><option value="">Choose if cash exceeds both obligations</option>${Object.entries(EXTRA_CHOICES).map(([key,label]) => `<option value="${key}">${label}</option>`).join('')}</select></label>${followupFields()}<button class="button button-outline" data-preview type="button">Preview server allocation</button><div data-combined-preview></div><button class="button button-primary" data-combined-save type="submit" disabled>Confirm reviewed payment</button></form>` : '<p>No available Regular + 7x7 pair is on this route.</p>'}
    <h2>Covered dates and corrections</h2><p>Load the saved schedule to choose covered dates. Corrections are available only for your unlocked, unremitted entry.</p>
    ${choices.length ? `<label>Loan<select name="scheduleLoan">${choices.map((entry,index) => `<option value="${index}">${h(entry.client_name)} · ${h(entry.loan_type)}</option>`).join('')}</select></label><button class="button button-outline" type="button" data-load-schedule>Load schedule / entry</button><div data-schedule-form></div>` : '<p>No editable loan is available.</p>'}
    <div data-workflow-status role="status"></div><button class="button button-outline" type="button" data-review-route hidden>Review updated route choices</button>`;
  const status = message => { if(current()) root.querySelector('[data-workflow-status]').textContent = message; };
  const run = async (operation) => {
    if (!current() || stale || !guard.begin()) return;
    try { await operation(); }
    catch(error) { if(current()) status(error.message); }
    finally {guard.finish();}
  };
  const form = root.querySelector('[data-combined-form]');
  const paymentDetails=form?bindCollectorPaymentDetails(form,{getEntry:()=>({loan_type:'Regular'}),getEntryType:()=> 'payment'}):null;
  const invalidate = () => {review.invalidate(); if(form) {form.querySelector('[data-combined-save]').disabled = true;form.querySelector('[data-combined-preview]').innerHTML = '';} };
  form?.addEventListener('input', invalidate);
  form?.addEventListener('change', invalidate);
  form?.querySelector('[data-preview]').addEventListener('click', () => run(async () => {
    if(confirmedPairs.has(pairKey(pairs[Number(value(form,'pair')) || 0])))throw new Error('This Combined Pay was already saved. Review another current loan pair.');
    const draft = buildCombinedSubmission({...identity(3),routeDate,entries:pairs[Number(value(form,'pair')) || 0],amount:value(form,'amount'),extraChoice:value(form,'extraChoice'),pastDueFollowup:readFollowup(form)});
    const result = await review.preview(draft);
    if (!current() || !result) return;
    form.querySelector('[data-combined-preview]').innerHTML = renderCombinedPreview(result);
    paymentDetails?.update(result);
    try {review.submission(); form.querySelector('[data-combined-save]').disabled = guard.locked;status('Review the allocation above, then confirm.');}
    catch(error) {form.querySelector('[data-combined-save]').disabled = true;status(error.message);}
  }));
  form?.addEventListener('submit', event => {
    event.preventDefault();
    run(async () => {
      const key=pairKey(pairs[Number(value(form,'pair')) || 0]);
      if(confirmedPairs.has(key))throw new Error('This Combined Pay was already saved. Review another current loan pair.');
      const request = review.submission();
      const result = await collectorMutation({api,guard,path:'/api/v1/collector/collections/combined',options:{method:'POST',...request},verify:result=>['accepted','duplicate'].includes(result.status) && result.client_transaction_id===request.body.client_transaction_id && result.total_amount===request.body.cash_received_amount && Array.isArray(result.legs) && result.legs.length>0 && result.legs.every(leg=>request.body.legs.some(item=>item.loan_id===leg.loan_id) && typeof leg.receipt_number==='string' && leg.receipt_number.length>0)});
      if (!current()) return;
      confirmedPairs.add(key);invalidate();
      status(result.message || 'Combined payment saved.');
      await onSaved(result,{source:'combined',entryIds:request.body.legs.map(item=>item.route_entry_id)});
    });
  });
  root.querySelector('[name="scheduleLoan"]')?.addEventListener('change', () => {loadVersion += 1;selected=null;root.querySelector('[data-schedule-form]').innerHTML='';});
  root.querySelector('[data-load-schedule]')?.addEventListener('click', () => run(async () => {
    const version = ++loadVersion;
    const entry = choices[Number(value(root,'scheduleLoan')) || 0];
    const correcting = entry.processed_today === true;
    const schedule = await api.request(`/api/v1/collector/loans/${encodeURIComponent(entry.loan_id)}/schedule`);
    if (!current() || version !== loadVersion) return;
    selected = entry;
    scheduleDates = selectableScheduleDates(schedule);
    if(correcting) {
      for(const date of entry.today_covered_dates || []) if(!scheduleDates.some(row=>row.date===date)) scheduleDates.push({date,amount:null});
      scheduleDates.sort((left,right)=>left.date.localeCompare(right.date));
    }
    const target = root.querySelector('[data-schedule-form]');
    target.innerHTML = `<form data-dates-form class="entry-form"><p>${h(entry.client_name)} · ${h(entry.loan_type)} · ${h(schedule.contract_reference || '')}</p><label>Entry type<select name="entryType">${correcting ? '<option value="payment">Payment</option><option value="advance">Covered-date payment</option><option value="pass">Unable to pay</option>' : '<option value="advance">Covered-date payment / ADV</option>'}</select></label><label>Amount<input name="amount" inputmode="decimal" value="${h(correcting ? entry.today_amount || '' : '')}" /></label><fieldset><legend>Saved installment dates</legend>${scheduleDates.map(row=>`<label><input name="coveredDate" type="checkbox" value="${h(row.date)}" ${(entry.today_covered_dates || []).includes(row.date) ? 'checked' : ''} />${h(row.date)}${row.amount == null ? ' · Current entry' : ` · Remaining ${formatMoney(row.amount)}`}</label>`).join('') || '<p>No unpaid saved installment is available.</p>'}</fieldset>${correcting ? '<label>Correction reason<textarea name="reason" maxlength="500" required></textarea></label>' : ''}<label>Note<textarea name="note" maxlength="500">${h(correcting ? entry.today_note || '' : '')}</textarea></label><button class="button button-primary" type="submit">${correcting ? 'Save correction' : 'Save covered-date payment'}</button></form>`;
    const datesForm = target.querySelector('[data-dates-form]');
    if (correcting) datesForm.querySelector('[name="entryType"]').value = entry.today_entry_type || 'payment';
    datesForm.addEventListener('submit', event => {
      event.preventDefault();
      run(async () => {
        if (selected !== entry || version !== loadVersion) throw new Error('Reload the schedule before saving.');
        const dates = [...datesForm.querySelectorAll('[name="coveredDate"]')].filter(node=>node.checked).map(node=>node.value);
        const amount = value(datesForm,'amount');
        const note = value(datesForm,'note');
        let result;
        if(correcting) {
          if(!hasPermission(getSession(),'collection.correct.own_unremitted')) throw new Error('Collection correction permission is required.');
          const request = buildCorrection({entry,entryType:value(datesForm,'entryType'),amount,coveredDates:dates,reason:value(datesForm,'reason'),note});
          result = await collectorMutation({api,guard,path:request.path,options:{method:'PATCH',body:request.body},verify:result=>result.transaction_id===entry.today_transaction_id && typeof result.route_revision==='string' && result.route_revision.length>0});
        } else {
          const request = buildCollectionSubmission({...identity(),entry,routeDate,entryType:'advance',amount,note,coveredDates:dates});
          result = await collectorMutation({api,guard,path:'/api/v1/collector/collections',options:{method:'POST',...request},verify:collectionResultMatches(request)});
        }
        if(current()){selected=null;loadVersion+=1;for(const button of datesForm.querySelectorAll('button'))button.disabled=true;await onSaved(result,{source:correcting?'correction':'covered-date',entryIds:[entry.route_entry_id]});}
      });
    });
    status('Review the saved installment dates before confirming.');
    guard.sync();
  }));
  const unsubscribe=registerRouteConsumer(route=>{if(!current() || signature(route)===routeSignature)return;stale=true;loadVersion+=1;selected=null;invalidate();status('Route changed — review again. Retained values are not current authorization.');root.querySelector('[data-review-route]').hidden=false;for(const button of root.querySelectorAll('button'))if(button.getAttribute('data-review-route')===null)button.disabled=true;});
  root.querySelector('[data-review-route]').addEventListener('click',()=>{const route=getRoute?.();if(!current() || !route?.route_date || guard.locked)return;entries=route.entries;routeDate=route.route_date;routeSignature=signature(route);canCorrect=hasPermission(getSession(),'collection.correct.own_unremitted');pairs=hasPermission(getSession(),'collection.create')?combinedPairs(entries):[];choices=entries.filter(entry=>(hasPermission(getSession(),'collection.create') && entry.can_enter_payment && !entry.processed_today) || (canCorrect && entry.can_edit_today && !entry.today_is_locked));if(form){const select=form.querySelector('[name="pair"]');select.innerHTML=pairs.map((pair,index)=>`<option value="${index}">${h(pair[0].client_name)} · Regular + 7x7</option>`).join('');select.value='0';form.querySelector('[data-preview]').disabled=!pairs.length;form.querySelector('[data-combined-save]').disabled=true;}const select=root.querySelector('[name="scheduleLoan"]');if(select){select.innerHTML=choices.map((entry,index)=>`<option value="${index}">${h(entry.client_name)} · ${h(entry.loan_type)}</option>`).join('');select.value='0';root.querySelector('[data-load-schedule]').disabled=!choices.length;}stale=false;root.querySelector('[data-review-route]').hidden=true;status('Current route choices reviewed. Preview again or reload the saved schedule before confirming.');guard.sync();});
  function dispose() {disposed=true;loadVersion+=1;review.invalidate();paymentDetails?.();unsubscribe();signal?.removeEventListener('abort',dispose);}
  signal?.addEventListener('abort',dispose,{once:true});
  if(signal?.aborted) dispose();
  return dispose;
}

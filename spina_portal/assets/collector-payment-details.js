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


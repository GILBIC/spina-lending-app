import test from 'node:test';
import assert from 'node:assert/strict';
import {collectorPaymentDetailState,readFollowup,bindCollectorPaymentDetails,followupFields,allocationField} from '../assets/collector-workflows.js';
import {Element,fire} from './helpers/dom.mjs';

test('mounted payment controls align hidden required and follow-up payload through short pass promise and Other changes',()=>{
  const form=new Element('form');form.innerHTML='<input name="entryType" value="payment" /><label>Amount<input name="amount" value="100.00" /></label><details data-payment-options>'+allocationField()+followupFields()+'</details>';
  const field=name=>form.querySelector(`[name="${name}"]`),options=form.querySelector('[data-payment-options]');options.open=false;
  const cleanup=bindCollectorPaymentDetails(form,{getEntry:()=>({loan_type:'Regular',contract_today_unpaid_amount:'100.00'})});
  assert.equal(field('amount').required,true);assert.equal(field('reasonCode').closest('label').hidden,true);assert.equal(field('promiseDate').required,false);
  field('amount').value='50.00';fire(form,'input');assert.equal(options.open,true);assert.equal(field('reasonCode').required,true);assert.equal(field('reasonCode').closest('label').hidden,false);
  field('reasonCode').value='promised_to_pay_later';fire(form,'change');for(const name of ['promiseDate','promiseAmount']){assert.equal(field(name).required,true);assert.equal(field(name).closest('label').hidden,false);}
  field('promiseDate').value='2026-10-04';field('promiseAmount').value='50.00';field('reasonCode').value='other';fire(form,'change');assert.equal(field('followupNote').required,true);assert.equal(field('promiseDate').required,false);assert.equal(field('promiseDate').closest('label').hidden,true);assert.equal(readFollowup(form).promised_payment_date,null);assert.equal(readFollowup(form).promised_amount,null);
  field('entryType').value='pass';fire(form,'change');assert.equal(field('amount').required,false);assert.equal(field('amount').closest('label').hidden,true);assert.equal(field('reasonCode').required,true);
  field('entryType').value='payment';field('amount').value='150.00';field('reasonCode').value='';fire(form,'change');assert.equal(field('amount').required,true);assert.equal(field('reasonCode').required,false);assert.equal(options.open,true);assert.match(form.innerHTML,/no_collection_voluntary/);
  cleanup();
});
test('ordinary payment compact short Regular and pass reveal reasons without Number rounding',()=>{assert.equal(collectorPaymentDetailState({loan_type:'Regular',contract_today_unpaid_amount:'100.00'},'payment','100.00','').reasonRequired,false);assert.equal(collectorPaymentDetailState({loan_type:'Regular',contract_today_unpaid_amount:'100.00'},'payment','50.00','').reasonRequired,true);assert.equal(collectorPaymentDetailState({loan_type:'Regular',contract_today_unpaid_amount:'90071992547409.92'},'payment','90071992547409.91','').reasonRequired,true);assert.equal(collectorPaymentDetailState({loan_type:'7x7',contract_today_unpaid_amount:'100.00'},'payment','50.00','').reasonRequired,false);assert.equal(collectorPaymentDetailState({},'pass','','').reasonRequired,true);});
test('unknown obligation keeps options available and promise fields follow reason',()=>{assert.equal(collectorPaymentDetailState({},'payment','100','').optionsVisible,true);assert.equal(collectorPaymentDetailState({},'payment','100','other').explanationRequired,true);assert.equal(collectorPaymentDetailState({},'payment','100','promised_to_pay_later').promiseRequired,true);const values={reasonCode:'no_cash',promiseDate:'2026-10-03',promiseAmount:'50'};assert.equal(readFollowup({querySelector:s=>({value:values[s.match(/"(.*)"/)[1]]||''})}).promised_amount,null);});
